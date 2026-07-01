from __future__ import annotations

import csv
import io
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext, actor_context_to_json, derive_actor_context
from family_finance_os.models import (
    CanonicalTransaction,
    Category,
    DecisionEvent,
    FundPool,
    Receipt,
    ReceiptLineItem,
)

MONEY_QUANT = Decimal("0.01")
SOURCE_TYPES = {"manual", "csv_import", "vendor_scraper"}
RECEIPT_STATUSES = {"draft", "active", "matched", "needs_review", "archived"}
REVIEW_STATUSES = {"unreviewed", "needs_review", "reviewed"}
CSV_COLUMNS = [
    "merchant",
    "purchase_date",
    "receipt_total",
    "line_description",
    "line_quantity",
    "line_amount",
    "category_id",
    "transaction_id",
]
IMPORT_PREVIEW_FILENAME = "preview.json"
IMPORT_UPLOAD_FILENAME = "upload.csv"


class ReceiptError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 422,
        detail: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}


class ReceiptLineRequest(BaseModel):
    item_description: str = Field(min_length=1)
    line_total: Decimal
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None
    category_id: Optional[str] = None
    subcategory: Optional[str] = None
    fund_pool_id: Optional[str] = None
    tax_relevant_candidate: bool = False
    reimbursement_candidate: bool = False
    business_candidate: bool = False
    review_status: Optional[str] = None


class ActorReceiptRequest(BaseModel):
    actor: str = Field(default="owner", min_length=1)
    actor_context: Optional[ActorContext] = None
    note: Optional[str] = None


class ReceiptCreateRequest(ActorReceiptRequest):
    merchant_name: str = Field(min_length=1, max_length=255)
    purchase_date: str = Field(min_length=10, max_length=10)
    receipt_total: Decimal
    currency: str = Field(default="USD", min_length=3, max_length=3)
    canonical_transaction_id: Optional[str] = None
    source_type: str = Field(default="manual", min_length=1, max_length=40)
    status: Optional[str] = None
    lines: list[ReceiptLineRequest] = Field(default_factory=list)


class ReceiptPatchRequest(ActorReceiptRequest):
    merchant_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    purchase_date: Optional[str] = Field(default=None, min_length=10, max_length=10)
    receipt_total: Optional[Decimal] = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    canonical_transaction_id: Optional[str] = None
    status: Optional[str] = None
    review_status: Optional[str] = None
    lines: Optional[list[ReceiptLineRequest]] = None


def list_receipts(
    session: Session,
    *,
    status: Optional[str] = None,
    review_status: Optional[str] = None,
    transaction_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    statement = select(Receipt).order_by(Receipt.purchase_date.desc(), Receipt.created_at.desc())
    if status is not None:
        statement = statement.where(Receipt.status == status)
    if review_status is not None:
        statement = statement.where(Receipt.review_status == review_status)
    if transaction_id is not None:
        statement = statement.where(Receipt.canonical_transaction_id == transaction_id)
    receipts = session.scalars(statement).all()
    return [serialize_receipt(session, receipt) for receipt in receipts]


def get_receipt(session: Session, receipt_id: str) -> dict[str, Any]:
    receipt = _get_receipt(session, receipt_id)
    return serialize_receipt(session, receipt)


def create_receipt(session: Session, request: ReceiptCreateRequest) -> dict[str, Any]:
    receipt = _build_receipt(session, request)
    session.add(receipt)
    session.flush()
    if request.lines:
        _replace_lines(session, receipt, request.lines)
    _refresh_receipt_state(session, receipt)
    _record_decision(
        session,
        receipt=receipt,
        decision_type="receipt_create",
        previous_value=None,
        approved_value=_receipt_decision_payload(session, receipt),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.commit()
    session.refresh(receipt)
    return serialize_receipt(session, receipt)


def update_receipt(session: Session, receipt_id: str, request: ReceiptPatchRequest) -> dict[str, Any]:
    receipt = _get_receipt(session, receipt_id)
    before = _receipt_decision_payload(session, receipt)
    if request.merchant_name is not None:
        receipt.merchant_name = request.merchant_name.strip()
    if request.purchase_date is not None:
        _validate_iso_date(request.purchase_date)
        receipt.purchase_date = request.purchase_date
    if request.receipt_total is not None:
        receipt.receipt_total = _money_decimal(request.receipt_total)
    if request.currency is not None:
        receipt.currency = request.currency.strip().upper()
    if request.canonical_transaction_id is not None:
        receipt.canonical_transaction_id = _resolve_transaction_id(session, request.canonical_transaction_id)
    if request.status is not None:
        _validate_status(request.status)
        receipt.status = request.status
    if request.review_status is not None:
        _validate_review_status(request.review_status)
        receipt.review_status = request.review_status
    if request.lines is not None:
        _replace_lines(session, receipt, request.lines)
    _refresh_receipt_state(session, receipt)
    _record_decision(
        session,
        receipt=receipt,
        decision_type="receipt_update",
        previous_value=before,
        approved_value=_receipt_decision_payload(session, receipt),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.commit()
    session.refresh(receipt)
    return serialize_receipt(session, receipt)


def list_receipt_review_queue(session: Session) -> dict[str, Any]:
    receipts = session.scalars(
        select(Receipt)
        .where(Receipt.status != "archived")
        .order_by(Receipt.purchase_date.desc(), Receipt.created_at.desc())
    ).all()
    items = []
    for receipt in receipts:
        reasons = _queue_reasons(session, receipt)
        if not reasons:
            continue
        payload = serialize_receipt(session, receipt)
        payload["queue_reasons"] = reasons
        items.append(payload)
    return {"items": items, "count": len(items)}


def preview_receipt_import(
    data_root: Path,
    *,
    filename: str,
    content: bytes,
    actor: str,
    actor_context: Optional[ActorContext] = None,
) -> dict[str, Any]:
    import_id = str(uuid4())
    import_dir = _safe_import_dir(data_root, import_id)
    upload_path = import_dir / IMPORT_UPLOAD_FILENAME
    upload_path.write_bytes(content)
    text = content.decode("utf-8-sig")
    receipts, findings = _parse_receipt_csv(text)
    preview = {
        "id": import_id,
        "status": "validated" if not findings else "blocked",
        "original_filename": filename,
        "stored_path": str(upload_path),
        "accepted_count": len(receipts),
        "rejected_count": len(findings),
        "findings": findings,
        "receipts": receipts,
        "actor": actor,
        "actor_context": derive_actor_context(actor, actor_context).model_dump(),
    }
    (import_dir / IMPORT_PREVIEW_FILENAME).write_text(json.dumps(preview, sort_keys=True), encoding="utf-8")
    return _serialize_import_preview(preview)


def accept_receipt_import(
    session: Session,
    data_root: Path,
    import_id: str,
    request: ActorReceiptRequest,
) -> dict[str, Any]:
    preview_path = _safe_import_dir(data_root, import_id, create=False) / IMPORT_PREVIEW_FILENAME
    if not preview_path.exists():
        raise ReceiptError("receipt_import_not_found", "Receipt import was not found.", 404)
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    if preview.get("status") == "accepted":
        raise ReceiptError("receipt_import_already_accepted", "Receipt import is already accepted.", 409)
    if preview.get("status") == "blocked":
        raise ReceiptError("receipt_csv_invalid", "Receipt import has validation findings and cannot be accepted.")
    created = []
    for receipt_payload in preview["receipts"]:
        create_request = ReceiptCreateRequest(
            actor=request.actor,
            actor_context=request.actor_context,
            note=request.note,
            merchant_name=receipt_payload["merchant_name"],
            purchase_date=receipt_payload["purchase_date"],
            receipt_total=Decimal(receipt_payload["receipt_total"]),
            canonical_transaction_id=receipt_payload.get("canonical_transaction_id"),
            source_type="csv_import",
            lines=[
                ReceiptLineRequest(
                    item_description=line["item_description"],
                    line_total=Decimal(line["line_total"]),
                    quantity=Decimal(line["quantity"]) if line.get("quantity") else None,
                    category_id=line.get("category_id"),
                )
                for line in receipt_payload.get("lines", [])
            ],
        )
        created.append(create_receipt(session, create_request))
    preview["status"] = "accepted"
    preview["created_receipt_ids"] = [receipt["id"] for receipt in created]
    preview_path.write_text(json.dumps(preview, sort_keys=True), encoding="utf-8")
    return {
        "import": _serialize_import_preview(preview),
        "created_count": len(created),
        "receipts": created,
    }


def persist_vendor_scraper_receipts(
    session: Session,
    *,
    vendor_key: str,
    receipts: list[dict[str, Any]],
    actor: str,
    actor_context: Optional[ActorContext] = None,
) -> list[dict[str, Any]]:
    """Persist normalized scraper output through the same receipt services as manual entry."""
    created: list[dict[str, Any]] = []
    for payload in receipts:
        request = ReceiptCreateRequest(
            actor=actor,
            actor_context=actor_context,
            merchant_name=payload["merchant_name"],
            purchase_date=payload["purchase_date"],
            receipt_total=Decimal(str(payload["receipt_total"])),
            canonical_transaction_id=payload.get("canonical_transaction_id"),
            source_type="vendor_scraper",
            lines=[
                ReceiptLineRequest(
                    item_description=line["item_description"],
                    line_total=Decimal(str(line["line_total"])),
                    quantity=Decimal(str(line["quantity"])) if line.get("quantity") is not None else None,
                    unit_price=Decimal(str(line["unit_price"])) if line.get("unit_price") is not None else None,
                    category_id=line.get("category_id"),
                    subcategory=line.get("subcategory"),
                    fund_pool_id=line.get("fund_pool_id"),
                    review_status=line.get("review_status"),
                )
                for line in payload.get("lines", [])
            ],
        )
        created.append(create_receipt(session, request))
    return created


def serialize_receipt(session: Session, receipt: Receipt) -> dict[str, Any]:
    lines = session.scalars(
        select(ReceiptLineItem)
        .where(ReceiptLineItem.receipt_id == receipt.id)
        .order_by(ReceiptLineItem.line_number)
    ).all()
    line_total = sum((_money_decimal(line.line_total) for line in lines), Decimal("0.00")).quantize(MONEY_QUANT)
    receipt_total = _money_decimal(receipt.receipt_total)
    return {
        "id": receipt.id,
        "canonical_transaction_id": receipt.canonical_transaction_id,
        "merchant_name": receipt.merchant_name,
        "purchase_date": receipt.purchase_date,
        "receipt_total": _money(receipt_total),
        "currency": receipt.currency,
        "source_type": receipt.source_type,
        "source_file_id": receipt.source_file_id,
        "stored_artifact_path": receipt.stored_artifact_path,
        "status": receipt.status,
        "review_status": receipt.review_status,
        "applied_as_split_decision_event_id": receipt.applied_as_split_decision_event_id,
        "lines": [_serialize_line(session, line) for line in lines],
        "summary": {
            "line_count": len(lines),
            "items_total": _money(line_total),
            "unaccounted_amount": _money((receipt_total - line_total).quantize(MONEY_QUANT)),
            "queue_reasons": _queue_reasons(session, receipt),
        },
        "created_at": receipt.created_at,
        "updated_at": receipt.updated_at,
    }


def _build_receipt(session: Session, request: ReceiptCreateRequest) -> Receipt:
    if request.source_type not in SOURCE_TYPES:
        raise ReceiptError("receipt_source_type_invalid", "Receipt source type is not supported.")
    _validate_iso_date(request.purchase_date)
    receipt_total = _money_decimal(request.receipt_total)
    if receipt_total <= Decimal("0.00"):
        raise ReceiptError("receipt_total_invalid", "Receipt total must be positive.")
    transaction_id = _resolve_transaction_id(session, request.canonical_transaction_id)
    if transaction_id:
        transaction = session.get(CanonicalTransaction, transaction_id)
        if transaction is None:
            raise ReceiptError("receipt_transaction_invalid", "Linked transaction was not found.", 404)
        transaction_amount = abs(_money_decimal(transaction.amount))
        if transaction_amount != receipt_total:
            status = "needs_review"
            review_status = "needs_review"
        else:
            status = "matched"
            review_status = "unreviewed"
    else:
        status = "needs_review"
        review_status = "needs_review"
    if request.status is not None:
        _validate_status(request.status)
        status = request.status
    return Receipt(
        merchant_name=request.merchant_name.strip(),
        purchase_date=request.purchase_date,
        receipt_total=receipt_total,
        currency=request.currency.strip().upper(),
        canonical_transaction_id=transaction_id,
        source_type=request.source_type,
        status=status,
        review_status=review_status,
    )


def _replace_lines(session: Session, receipt: Receipt, lines: list[ReceiptLineRequest]) -> None:
    existing = session.scalars(select(ReceiptLineItem).where(ReceiptLineItem.receipt_id == receipt.id)).all()
    for line in existing:
        session.delete(line)
    session.flush()
    for index, line_request in enumerate(lines, start=1):
        line = _build_line(session, receipt, index, line_request)
        session.add(line)


def _build_line(
    session: Session,
    receipt: Receipt,
    line_number: int,
    request: ReceiptLineRequest,
) -> ReceiptLineItem:
    line_total = _money_decimal(request.line_total)
    if line_total <= Decimal("0.00"):
        raise ReceiptError("receipt_line_total_invalid", "Receipt line total must be positive.")
    category_id = request.category_id
    if category_id and session.get(Category, category_id) is None:
        raise ReceiptError("receipt_line_category_invalid", "Receipt line category must exist.")
    if request.fund_pool_id and session.get(FundPool, request.fund_pool_id) is None:
        raise ReceiptError("receipt_line_fund_pool_invalid", "Receipt line fund pool must exist.")
    review_status = request.review_status or ("needs_review" if not category_id else "unreviewed")
    _validate_review_status(review_status)
    return ReceiptLineItem(
        receipt_id=receipt.id,
        line_number=line_number,
        item_description=request.item_description.strip(),
        quantity=_optional_money_decimal(request.quantity, quant=MONEY_QUANT, places=4),
        unit_price=_optional_money_decimal(request.unit_price),
        line_total=line_total,
        category_id=category_id,
        subcategory=_clean_optional(request.subcategory),
        fund_pool_id=request.fund_pool_id,
        tax_relevant_candidate=request.tax_relevant_candidate,
        reimbursement_candidate=request.reimbursement_candidate,
        business_candidate=request.business_candidate,
        review_status=review_status,
    )


def _refresh_receipt_state(session: Session, receipt: Receipt) -> None:
    lines = session.scalars(
        select(ReceiptLineItem).where(ReceiptLineItem.receipt_id == receipt.id).order_by(ReceiptLineItem.line_number)
    ).all()
    reasons = _queue_reasons(session, receipt, lines=lines)
    if not receipt.canonical_transaction_id:
        receipt.status = "needs_review"
    elif reasons:
        receipt.status = "needs_review"
        receipt.review_status = "needs_review"
    elif lines:
        receipt.status = "matched"
    else:
        receipt.status = "active"


def _queue_reasons(
    session: Session,
    receipt: Receipt,
    *,
    lines: Optional[list[ReceiptLineItem]] = None,
) -> list[str]:
    if lines is None:
        lines = session.scalars(
            select(ReceiptLineItem).where(ReceiptLineItem.receipt_id == receipt.id).order_by(ReceiptLineItem.line_number)
        ).all()
    reasons: list[str] = []
    if not receipt.canonical_transaction_id:
        reasons.append("unmatched_receipt")
    line_total = sum((_money_decimal(line.line_total) for line in lines), Decimal("0.00")).quantize(MONEY_QUANT)
    receipt_total = _money_decimal(receipt.receipt_total)
    if lines and line_total != receipt_total:
        reasons.append("receipt_total_mismatch")
    if any(line.category_id is None for line in lines):
        reasons.append("line_category_needed")
    if len(lines) >= 3 and len({line.category_id for line in lines if line.category_id}) >= 2:
        reasons.append("mixed_basket_candidate")
    if any(line.reimbursement_candidate for line in lines):
        reasons.append("reimbursement_candidate")
    if any(line.tax_relevant_candidate for line in lines):
        reasons.append("medical_tax_candidate")
    if any(line.business_candidate for line in lines):
        reasons.append("side_hustle_candidate")
    duplicate = session.scalar(
        select(Receipt.id)
        .where(
            Receipt.id != receipt.id,
            Receipt.merchant_name == receipt.merchant_name,
            Receipt.purchase_date == receipt.purchase_date,
            Receipt.receipt_total == receipt.receipt_total,
            Receipt.status != "archived",
        )
        .limit(1)
    )
    if duplicate:
        reasons.append("duplicate_receipt_candidate")
    if receipt.review_status == "reviewed" and not reasons:
        return []
    if receipt.review_status == "reviewed":
        return []
    return reasons


def _parse_receipt_csv(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ReceiptError("receipt_csv_invalid", "Receipt CSV must include a header row.")
    missing = [column for column in CSV_COLUMNS if column not in (reader.fieldnames or [])]
    if missing:
        raise ReceiptError(
            "receipt_csv_invalid",
            f"Receipt CSV is missing required columns: {', '.join(missing)}",
        )
    grouped: dict[tuple[str, str, str, Optional[str]], dict[str, Any]] = {}
    findings: list[dict[str, Any]] = []
    for row_number, row in enumerate(reader, start=2):
        merchant = (row.get("merchant") or "").strip()
        purchase_date = (row.get("purchase_date") or "").strip()
        receipt_total_raw = (row.get("receipt_total") or "").strip()
        line_description = (row.get("line_description") or "").strip()
        if not merchant or not purchase_date or not receipt_total_raw or not line_description:
            findings.append({"row": row_number, "code": "receipt_csv_invalid", "message": "Missing required field."})
            continue
        try:
            _validate_iso_date(purchase_date)
            receipt_total = _money_decimal(receipt_total_raw)
            line_amount = _money_decimal((row.get("line_amount") or "").strip() or receipt_total_raw)
        except ReceiptError as exc:
            findings.append({"row": row_number, "code": exc.code, "message": exc.message})
            continue
        transaction_id = (row.get("transaction_id") or "").strip() or None
        key = (merchant, purchase_date, _money(receipt_total), transaction_id)
        if key not in grouped:
            grouped[key] = {
                "merchant_name": merchant,
                "purchase_date": purchase_date,
                "receipt_total": _money(receipt_total),
                "canonical_transaction_id": transaction_id,
                "lines": [],
            }
        grouped[key]["lines"].append(
            {
                "item_description": line_description,
                "line_total": _money(line_amount),
                "quantity": (row.get("line_quantity") or "").strip() or None,
                "category_id": (row.get("category_id") or "").strip() or None,
            }
        )
    return list(grouped.values()), findings


def _serialize_line(session: Session, line: ReceiptLineItem) -> dict[str, Any]:
    category = session.get(Category, line.category_id) if line.category_id else None
    pool = session.get(FundPool, line.fund_pool_id) if line.fund_pool_id else None
    return {
        "id": line.id,
        "line_number": line.line_number,
        "item_description": line.item_description,
        "quantity": _optional_money_str(line.quantity, places=4),
        "unit_price": _optional_money_str(line.unit_price),
        "line_total": _money(_money_decimal(line.line_total)),
        "category_id": line.category_id,
        "category_display_name": category.display_name if category else None,
        "subcategory": line.subcategory,
        "fund_pool_id": line.fund_pool_id,
        "fund_pool_name": pool.name if pool else None,
        "tax_relevant_candidate": line.tax_relevant_candidate,
        "reimbursement_candidate": line.reimbursement_candidate,
        "business_candidate": line.business_candidate,
        "review_status": line.review_status,
    }


def _serialize_import_preview(preview: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": preview["id"],
        "status": preview["status"],
        "original_filename": preview["original_filename"],
        "stored_path": preview["stored_path"],
        "accepted_count": preview["accepted_count"],
        "rejected_count": preview["rejected_count"],
        "findings": preview["findings"],
        "receipts": preview.get("receipts", []),
    }


def _record_decision(
    session: Session,
    *,
    receipt: Receipt,
    decision_type: str,
    previous_value: Any,
    approved_value: Any,
    actor: str,
    actor_context: Optional[ActorContext],
    notes: Optional[str],
) -> DecisionEvent:
    event = DecisionEvent(
        target_type="receipt",
        target_id=receipt.id,
        decision_type=decision_type,
        field_name="receipt",
        previous_value=_decision_value(previous_value),
        proposed_value=_decision_value(approved_value),
        approved_value=_decision_value(approved_value),
        actor=actor,
        actor_context_json=actor_context_to_json(derive_actor_context(actor, actor_context)),
        notes=notes.strip() if notes else None,
        suggestion_source="owner",
    )
    session.add(event)
    session.flush()
    return event


def _decision_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, default=str)


def _receipt_decision_payload(session: Session, receipt: Receipt) -> dict[str, Any]:
    payload = serialize_receipt(session, receipt)
    payload.pop("summary", None)
    return payload


def _get_receipt(session: Session, receipt_id: str) -> Receipt:
    receipt = session.get(Receipt, receipt_id)
    if receipt is None:
        raise ReceiptError("receipt_not_found", "Receipt was not found.", 404)
    return receipt


def _resolve_transaction_id(session: Session, transaction_id: Optional[str]) -> Optional[str]:
    if not transaction_id:
        return None
    cleaned = transaction_id.strip()
    return cleaned or None


def _validate_iso_date(value: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ReceiptError("receipt_date_invalid", "Purchase date must use YYYY-MM-DD format.")


def _validate_status(value: str) -> None:
    if value not in RECEIPT_STATUSES:
        raise ReceiptError("receipt_status_invalid", "Receipt status is not supported.")


def _validate_review_status(value: str) -> None:
    if value not in REVIEW_STATUSES:
        raise ReceiptError("receipt_review_status_invalid", "Receipt review status is not supported.")


def _safe_import_dir(data_root: Path, import_id: str, *, create: bool = True) -> Path:
    if not re.fullmatch(r"[0-9a-f-]{36}", import_id):
        raise ReceiptError("receipt_import_id_invalid", "Receipt import id is invalid.")
    import_dir = (data_root / "receipts" / "imports" / import_id).resolve()
    if data_root.resolve() not in import_dir.parents:
        raise ReceiptError("receipt_import_path_unsafe", "Receipt import path must stay under DATA_ROOT.")
    if create:
        import_dir.mkdir(parents=True, exist_ok=True)
    return import_dir


def _money_decimal(value: Decimal | str | float | int) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _optional_money_decimal(
    value: Optional[Decimal],
    *,
    quant: Decimal = MONEY_QUANT,
    places: int = 2,
) -> Optional[Decimal]:
    if value is None:
        return None
    if places == 4:
        return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return _money_decimal(value)


def _optional_money_str(value: Optional[Decimal], *, places: int = 2) -> Optional[str]:
    if value is None:
        return None
    if places == 4:
        return str(Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
    return _money(_money_decimal(value))


def _money(value: Decimal) -> str:
    return format(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP), "f")


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None

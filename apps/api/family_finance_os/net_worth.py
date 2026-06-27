from __future__ import annotations

"""Manual net worth snapshots and CSV import support.

Balance sign convention: snapshot balances are stored as positive amounts. The
`asset_or_liability` field controls rollup sign, so assets add to net worth and
liabilities subtract from net worth. Estimates are labeled with
`valuation_method="estimate"`, require confidence and source notes, and are not
included in actual net worth unless explicitly represented in the separate
with-estimates view.
"""

import csv
import json
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from family_finance_os.actors import ActorContext, actor_context_to_json, derive_actor_context
from family_finance_os.models import DecisionEvent, NetWorthSnapshot


MONEY_QUANT = Decimal("0.01")
ASSET_OR_LIABILITY_VALUES = {"asset", "liability"}
VALUATION_METHODS = {"actual", "estimate"}
CONFIDENCE_VALUES = {"high", "medium", "low"}
CSV_COLUMNS = [
    "snapshot_date",
    "asset_or_liability",
    "account_name",
    "institution",
    "category",
    "subcategory",
    "balance",
    "valuation_method",
    "confidence",
    "source_notes",
]
IMPORT_PREVIEW_FILENAME = "preview.json"
IMPORT_UPLOAD_FILENAME = "upload.csv"


class NetWorthError(ValueError):
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


class ActorNetWorthRequest(BaseModel):
    actor: str = Field(default="owner", min_length=1)
    actor_context: Optional[ActorContext] = None
    note: Optional[str] = None


class NetWorthSnapshotCreateRequest(ActorNetWorthRequest):
    snapshot_date: str = Field(min_length=10, max_length=10)
    asset_or_liability: str = Field(min_length=1, max_length=20)
    account_name: str = Field(min_length=1, max_length=160)
    institution: Optional[str] = Field(default=None, max_length=160)
    category: str = Field(min_length=1, max_length=80)
    subcategory: Optional[str] = Field(default=None, max_length=120)
    balance: Decimal
    valuation_method: str = Field(default="actual", min_length=1, max_length=40)
    confidence: Optional[str] = Field(default=None, max_length=40)
    source_notes: Optional[str] = None
    include_in_actual_net_worth: Optional[bool] = None


class NetWorthSnapshotPatchRequest(ActorNetWorthRequest):
    snapshot_date: Optional[str] = Field(default=None, min_length=10, max_length=10)
    asset_or_liability: Optional[str] = Field(default=None, min_length=1, max_length=20)
    account_name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    institution: Optional[str] = Field(default=None, max_length=160)
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    subcategory: Optional[str] = Field(default=None, max_length=120)
    balance: Optional[Decimal] = None
    valuation_method: Optional[str] = Field(default=None, min_length=1, max_length=40)
    confidence: Optional[str] = Field(default=None, max_length=40)
    source_notes: Optional[str] = None
    include_in_actual_net_worth: Optional[bool] = None


def list_net_worth_snapshots(
    session: Session,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> list[dict[str, Any]]:
    statement = select(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_date, NetWorthSnapshot.created_at)
    if from_date is not None:
        _validate_iso_date(from_date, "invalid_from_date")
        statement = statement.where(NetWorthSnapshot.snapshot_date >= from_date)
    if to_date is not None:
        _validate_iso_date(to_date, "invalid_to_date")
        statement = statement.where(NetWorthSnapshot.snapshot_date <= to_date)
    return [serialize_snapshot(snapshot) for snapshot in session.scalars(statement).all()]


def create_net_worth_snapshot(session: Session, request: NetWorthSnapshotCreateRequest) -> dict[str, Any]:
    values = _prepare_snapshot_values(request.model_dump())
    snapshot = NetWorthSnapshot(**values)
    session.add(snapshot)
    session.flush()
    _record_decision(
        session,
        target_id=snapshot.id,
        decision_type="net_worth_snapshot_create",
        previous_value=None,
        approved_value=serialize_snapshot(snapshot),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.commit()
    session.refresh(snapshot)
    return serialize_snapshot(snapshot)


def update_net_worth_snapshot(session: Session, snapshot_id: str, request: NetWorthSnapshotPatchRequest) -> dict[str, Any]:
    snapshot = _get_snapshot(session, snapshot_id)
    before = serialize_snapshot(snapshot)
    current = {
        "snapshot_date": snapshot.snapshot_date,
        "asset_or_liability": snapshot.asset_or_liability,
        "account_name": snapshot.account_name,
        "institution": snapshot.institution,
        "category": snapshot.category,
        "subcategory": snapshot.subcategory,
        "balance": Decimal(snapshot.balance),
        "valuation_method": snapshot.valuation_method,
        "confidence": snapshot.confidence,
        "source_notes": snapshot.source_notes,
        "include_in_actual_net_worth": snapshot.include_in_actual_net_worth,
    }
    updates = request.model_dump(exclude={"actor", "actor_context", "note"}, exclude_unset=True)
    values = _prepare_snapshot_values({**current, **updates})
    for key, value in values.items():
        setattr(snapshot, key, value)
    session.flush()
    _record_decision(
        session,
        target_id=snapshot.id,
        decision_type="net_worth_snapshot_update",
        previous_value=before,
        approved_value=serialize_snapshot(snapshot),
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.commit()
    session.refresh(snapshot)
    return serialize_snapshot(snapshot)


def delete_net_worth_snapshot(session: Session, snapshot_id: str, request: ActorNetWorthRequest) -> dict[str, Any]:
    snapshot = _get_snapshot(session, snapshot_id)
    before = serialize_snapshot(snapshot)
    _record_decision(
        session,
        target_id=snapshot.id,
        decision_type="net_worth_snapshot_delete",
        previous_value=before,
        approved_value=None,
        actor=request.actor,
        actor_context=request.actor_context,
        notes=request.note,
    )
    session.delete(snapshot)
    session.commit()
    return {"snapshot": before, "deleted": True}


def net_worth_summary(
    session: Session,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    include_estimates: bool = False,
) -> dict[str, Any]:
    snapshots = _snapshots_for_summary(session, from_date=from_date, to_date=to_date)
    latest_snapshot_date = max((snapshot.snapshot_date for snapshot in snapshots), default=None)
    latest = [snapshot for snapshot in snapshots if snapshot.snapshot_date == latest_snapshot_date]
    actual = _rollup(latest, include_estimates=False)
    with_estimates = {**_rollup(latest, include_estimates=True), "includes_estimates": True}
    dates = sorted({snapshot.snapshot_date for snapshot in snapshots})
    series = []
    for snapshot_date in dates:
        dated = [snapshot for snapshot in snapshots if snapshot.snapshot_date == snapshot_date]
        rollup = _rollup(dated, include_estimates=include_estimates)
        series.append({"snapshot_date": snapshot_date, **rollup, "includes_estimates": include_estimates})
    return {
        "include_estimates": include_estimates,
        "latest_snapshot_date": latest_snapshot_date,
        "actual": actual,
        "with_estimates": with_estimates,
        "series": series,
    }


def preview_net_worth_import(
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
    rows = [_jsonable_snapshot_values(row) for row in _parse_csv_rows(text)]
    preview = {
        "id": import_id,
        "status": "validated",
        "original_filename": filename,
        "stored_path": str(upload_path),
        "accepted_count": len(rows),
        "rejected_count": 0,
        "findings": [],
        "rows": rows,
        "actor": actor,
        "actor_context": derive_actor_context(actor, actor_context).model_dump(),
    }
    (import_dir / IMPORT_PREVIEW_FILENAME).write_text(json.dumps(preview, sort_keys=True), encoding="utf-8")
    return _serialize_import_preview(preview)


def accept_net_worth_import(
    session: Session,
    data_root: Path,
    import_id: str,
    request: ActorNetWorthRequest,
) -> dict[str, Any]:
    preview_path = _safe_import_dir(data_root, import_id, create=False) / IMPORT_PREVIEW_FILENAME
    if not preview_path.exists():
        raise NetWorthError("net_worth_import_not_found", "Net worth import was not found.", 404)
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    if preview.get("status") == "accepted":
        raise NetWorthError("net_worth_import_already_accepted", "Net worth import is already accepted.", 409)
    created = []
    for row in preview["rows"]:
        snapshot = NetWorthSnapshot(**_prepare_snapshot_values(row))
        session.add(snapshot)
        session.flush()
        _record_decision(
            session,
            target_id=snapshot.id,
            decision_type="net_worth_snapshot_create",
            previous_value=None,
            approved_value=serialize_snapshot(snapshot),
            actor=request.actor,
            actor_context=request.actor_context,
            notes=request.note,
        )
        created.append(snapshot)
    _record_import_decision(session, import_id=import_id, preview=preview, request=request, created_count=len(created))
    preview["status"] = "accepted"
    preview["created_snapshot_ids"] = [snapshot.id for snapshot in created]
    preview_path.write_text(json.dumps(preview, sort_keys=True), encoding="utf-8")
    session.commit()
    return {
        "import": _serialize_import_preview(preview),
        "created_count": len(created),
        "snapshots": [serialize_snapshot(snapshot) for snapshot in created],
    }


def serialize_snapshot(snapshot: NetWorthSnapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "snapshot_date": snapshot.snapshot_date,
        "asset_or_liability": snapshot.asset_or_liability,
        "account_name": snapshot.account_name,
        "institution": snapshot.institution,
        "category": snapshot.category,
        "subcategory": snapshot.subcategory,
        "balance": _money(Decimal(snapshot.balance)),
        "valuation_method": snapshot.valuation_method,
        "confidence": snapshot.confidence,
        "source_notes": snapshot.source_notes,
        "include_in_actual_net_worth": snapshot.include_in_actual_net_worth,
        "created_at": snapshot.created_at,
        "updated_at": snapshot.updated_at,
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
        "rows": preview["rows"],
    }


def _snapshots_for_summary(
    session: Session,
    *,
    from_date: Optional[str],
    to_date: Optional[str],
) -> list[NetWorthSnapshot]:
    statement = select(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_date, NetWorthSnapshot.created_at)
    if from_date is not None:
        _validate_iso_date(from_date, "invalid_from_date")
        statement = statement.where(NetWorthSnapshot.snapshot_date >= from_date)
    if to_date is not None:
        _validate_iso_date(to_date, "invalid_to_date")
        statement = statement.where(NetWorthSnapshot.snapshot_date <= to_date)
    return session.scalars(statement).all()


def _rollup(snapshots: list[NetWorthSnapshot], *, include_estimates: bool) -> dict[str, str]:
    assets = Decimal("0.00")
    liabilities = Decimal("0.00")
    for snapshot in snapshots:
        if snapshot.valuation_method == "estimate":
            if not include_estimates:
                continue
        elif not snapshot.include_in_actual_net_worth:
            continue
        balance = Decimal(snapshot.balance)
        if snapshot.asset_or_liability == "asset":
            assets += balance
        else:
            liabilities += balance
    return {
        "assets": _money(assets),
        "liabilities": _money(liabilities),
        "net_worth": _money(assets - liabilities),
    }


def _parse_csv_rows(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise NetWorthError("net_worth_csv_empty", "CSV file is empty.")
    fieldnames = [field.strip() for field in reader.fieldnames]
    unexpected = sorted(set(fieldnames) - set(CSV_COLUMNS))
    missing = [column for column in CSV_COLUMNS if column not in fieldnames]
    if unexpected:
        raise NetWorthError(
            "net_worth_csv_unexpected_columns",
            "Net worth CSV contains unsupported columns.",
            detail={"unexpected_columns": unexpected},
        )
    if missing:
        raise NetWorthError(
            "net_worth_csv_missing_columns",
            "Net worth CSV is missing required columns.",
            detail={"missing_columns": missing},
        )

    rows = []
    findings = []
    for index, raw_row in enumerate(reader, start=2):
        row = {column: (raw_row.get(column) or "").strip() for column in CSV_COLUMNS}
        try:
            rows.append(_prepare_snapshot_values(row))
        except NetWorthError as exc:
            findings.append({"row_number": index, "code": _csv_finding_code(exc.code), "message": exc.message})
    if findings:
        raise NetWorthError(
            "net_worth_csv_validation_failed",
            "Net worth CSV rows failed validation.",
            detail={"findings": findings},
        )
    return rows


def _prepare_snapshot_values(values: dict[str, Any]) -> dict[str, Any]:
    snapshot_date = _validate_iso_date(str(values.get("snapshot_date") or ""), "invalid_snapshot_date")
    asset_or_liability = str(values.get("asset_or_liability") or "").strip()
    if asset_or_liability not in ASSET_OR_LIABILITY_VALUES:
        raise NetWorthError("invalid_asset_or_liability", "asset_or_liability must be asset or liability.")
    account_name = _required_text(values.get("account_name"), "account_name_required", "Account display name is required.")
    institution = _clean_optional(values.get("institution"))
    category = _required_text(values.get("category"), "category_required", "Category is required.")
    subcategory = _clean_optional(values.get("subcategory"))
    balance = _non_negative_money(values.get("balance"))
    valuation_method = str(values.get("valuation_method") or "actual").strip()
    if valuation_method not in VALUATION_METHODS:
        raise NetWorthError("invalid_valuation_method", "valuation_method must be actual or estimate.")
    confidence = _clean_optional(values.get("confidence"))
    source_notes = _clean_optional(values.get("source_notes"))
    if valuation_method == "estimate":
        if confidence not in CONFIDENCE_VALUES or not source_notes:
            raise NetWorthError(
                "estimate_metadata_required",
                "Estimated snapshots require confidence and source notes.",
            )
        include_in_actual = False
    else:
        confidence = confidence or "high"
        if confidence not in CONFIDENCE_VALUES:
            raise NetWorthError("invalid_confidence", "confidence must be high, medium, or low.")
        include_value = values.get("include_in_actual_net_worth")
        include_in_actual = True if include_value is None else bool(include_value)
    if _looks_like_account_identifier(account_name) or _looks_like_account_identifier(institution):
        raise NetWorthError("account_identifier_not_allowed", "Account numbers or full identifiers are not allowed.")
    return {
        "snapshot_date": snapshot_date,
        "asset_or_liability": asset_or_liability,
        "account_name": account_name,
        "institution": institution,
        "category": category,
        "subcategory": subcategory,
        "balance": balance,
        "valuation_method": valuation_method,
        "confidence": confidence,
        "source_notes": source_notes,
        "include_in_actual_net_worth": include_in_actual,
    }


def _safe_import_dir(data_root: Path, import_id: str, *, create: bool = True) -> Path:
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", import_id):
        raise NetWorthError("net_worth_import_not_found", "Net worth import was not found.", 404)
    root = data_root / "net_worth_imports"
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise NetWorthError("net_worth_import_storage_unsafe", "Net worth import storage must be inside DATA_ROOT.", 409)
    root.mkdir(exist_ok=True)
    import_dir = root / import_id
    if import_dir.is_symlink() or (import_dir.exists() and not import_dir.is_dir()):
        raise NetWorthError("net_worth_import_storage_unsafe", "Net worth import storage must be inside DATA_ROOT.", 409)
    if create:
        import_dir.mkdir(exist_ok=True)
    return import_dir


def _get_snapshot(session: Session, snapshot_id: str) -> NetWorthSnapshot:
    snapshot = session.get(NetWorthSnapshot, snapshot_id)
    if snapshot is None:
        raise NetWorthError("net_worth_snapshot_not_found", "Net worth snapshot was not found.", 404)
    return snapshot


def _record_decision(
    session: Session,
    *,
    target_id: str,
    decision_type: str,
    previous_value: Any,
    approved_value: Any,
    actor: str,
    actor_context: Optional[ActorContext],
    notes: Optional[str],
) -> DecisionEvent:
    event = DecisionEvent(
        target_type="net_worth_snapshot",
        target_id=target_id,
        decision_type=decision_type,
        field_name="record",
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


def _record_import_decision(
    session: Session,
    *,
    import_id: str,
    preview: dict[str, Any],
    request: ActorNetWorthRequest,
    created_count: int,
) -> DecisionEvent:
    event = DecisionEvent(
        target_type="net_worth_import",
        target_id=import_id,
        decision_type="net_worth_csv_import_accept",
        field_name="status",
        previous_value="validated",
        proposed_value="accepted",
        approved_value=_decision_value({"status": "accepted", "created_count": created_count, "filename": preview["original_filename"]}),
        actor=request.actor,
        actor_context_json=actor_context_to_json(derive_actor_context(request.actor, request.actor_context)),
        notes=request.note.strip() if request.note else None,
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
    return json.dumps(value, sort_keys=True)


def _validate_iso_date(value: str, code: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise NetWorthError(code, "Date must use YYYY-MM-DD format.") from exc
    return parsed.isoformat()


def _non_negative_money(value: Any) -> Decimal:
    amount = Decimal(str(value or "0"))
    if amount < Decimal("0.00"):
        raise NetWorthError("invalid_balance", "Balance must be greater than or equal to zero.")
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _money(value: Decimal) -> str:
    return str(Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def _required_text(value: Any, code: str, message: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise NetWorthError(code, message)
    return cleaned


def _clean_optional(value: Any) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _csv_finding_code(error_code: str) -> str:
    if error_code in {"invalid_snapshot_date", "invalid_valuation_method", "estimate_metadata_required"}:
        return error_code
    return f"net_worth_{error_code}"


def _jsonable_snapshot_values(values: dict[str, Any]) -> dict[str, Any]:
    return {
        **values,
        "balance": _money(Decimal(values["balance"])),
    }


def _looks_like_account_identifier(value: Optional[str]) -> bool:
    return bool(value and re.search(r"\d{6,}", value))

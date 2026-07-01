from __future__ import annotations

from typing import Any

from family_finance_os.vendor_scrape_contracts import (
    VendorScrapeAdapterOutput,
    VendorScrapeLineOutput,
    VendorScrapeQuality,
    VendorScrapeReceiptOutput,
)
from family_finance_os.vendor_adapters.base import (
    REVIEW_LINE_TYPES,
    VendorAdapter,
    merchant_label,
    metadata_json,
    money_decimal,
    money_str,
)


class CostcoAdapter(VendorAdapter):
    vendor_key = "costco"

    def normalize(self, raw: dict[str, Any], *, run_id: str) -> VendorScrapeAdapterOutput:
        warnings: list[str] = []
        receipts: list[VendorScrapeReceiptOutput] = []
        receipt_shape = str(raw.get("receipt_shape") or "warehouse")
        merchant_name = merchant_label("Costco", raw)
        if receipt_shape not in {"warehouse", "online"}:
            warnings.append(f"costco_unknown_receipt_shape:{receipt_shape}")

        source_receipts = raw.get("receipts") or raw.get("orders") or []
        for index, receipt_raw in enumerate(source_receipts, start=1):
            receipt, receipt_warnings = _normalize_receipt(
                receipt_raw,
                merchant_name=merchant_name,
                receipt_shape=receipt_shape,
                fallback_index=index,
            )
            warnings.extend(receipt_warnings)
            receipts.append(receipt)

        line_count = sum(len(receipt.lines) for receipt in receipts)
        return VendorScrapeAdapterOutput(
            vendor_key=self.vendor_key,
            run_id=run_id,
            receipts=receipts,
            quality=VendorScrapeQuality(
                receipt_count=len(receipts),
                line_count=line_count,
                warnings=warnings,
            ),
        )


def _normalize_receipt(
    receipt_raw: dict[str, Any],
    *,
    merchant_name: str,
    receipt_shape: str,
    fallback_index: int,
) -> tuple[VendorScrapeReceiptOutput, list[str]]:
    warnings: list[str] = []
    external_id = str(
        receipt_raw.get("transaction_id")
        or receipt_raw.get("order_id")
        or receipt_raw.get("receipt_id")
        or f"synthetic-costco-{receipt_shape}-{fallback_index}"
    )
    purchase_date = str(
        receipt_raw.get("transaction_date")
        or receipt_raw.get("order_date")
        or receipt_raw.get("purchase_date")
        or "1970-01-01"
    )[:10]

    raw_lines = receipt_raw.get("lines") or receipt_raw.get("items") or []
    lines: list[VendorScrapeLineOutput] = []
    departments: set[str] = set()

    for line_number, line_raw in enumerate(raw_lines, start=1):
        line_type = str(line_raw.get("line_type") or line_raw.get("component_type") or "item").lower()
        department = str(line_raw.get("department") or line_raw.get("dept") or "general")
        departments.add(department)
        needs_review = line_type in REVIEW_LINE_TYPES
        line_metadata = metadata_json(review_reason=line_type) if needs_review else None
        lines.append(
            VendorScrapeLineOutput(
                line_number=line_number,
                item_description=str(line_raw.get("description") or line_raw.get("item_description") or "Costco item"),
                quantity=str(line_raw.get("quantity") or "1"),
                line_total=money_str(line_raw.get("amount") or line_raw.get("line_total") or "0.00"),
                review_status="needs_review" if needs_review else None,
                metadata_json=line_metadata,
            )
        )

    if len(lines) >= 3 and len(departments) >= 2:
        warnings.append(f"costco_mixed_basket_candidate:{external_id}")

    receipt_total = receipt_raw.get("total") or receipt_raw.get("receipt_total") or receipt_raw.get("order_total")
    if receipt_total is None and lines:
        receipt_total = money_str(sum(money_decimal(line.line_total) for line in lines))

    receipt_needs_review = any(line.review_status == "needs_review" for line in lines)
    receipt = VendorScrapeReceiptOutput(
        external_receipt_id=external_id,
        merchant_name=merchant_name,
        purchase_date=purchase_date,
        receipt_total=money_str(receipt_total) if receipt_total is not None else None,
        lines=lines,
    )
    if receipt_needs_review:
        warnings.append(f"costco_review_required_lines:{external_id}")
    return receipt, warnings

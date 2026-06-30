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

WALMART_RECEIPT_SHAPES = frozenset({"pickup", "delivery", "order"})


class WalmartAdapter(VendorAdapter):
    vendor_key = "walmart"

    def normalize(self, raw: dict[str, Any], *, run_id: str) -> VendorScrapeAdapterOutput:
        warnings: list[str] = []
        receipts: list[VendorScrapeReceiptOutput] = []
        receipt_shape = str(raw.get("receipt_shape") or "order")
        merchant_name = merchant_label("Walmart", raw)
        if receipt_shape not in WALMART_RECEIPT_SHAPES:
            warnings.append(f"walmart_unknown_receipt_shape:{receipt_shape}")

        source_orders = raw.get("orders") or raw.get("receipts") or []
        for index, order in enumerate(source_orders, start=1):
            receipt, order_warnings = _normalize_order(
                order,
                merchant_name=merchant_name,
                receipt_shape=receipt_shape,
                fallback_index=index,
            )
            warnings.extend(order_warnings)
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


def _normalize_order(
    order: dict[str, Any],
    *,
    merchant_name: str,
    receipt_shape: str,
    fallback_index: int,
) -> tuple[VendorScrapeReceiptOutput, list[str]]:
    warnings: list[str] = []
    external_id = str(order.get("order_id") or order.get("receipt_id") or f"synthetic-walmart-{receipt_shape}-{fallback_index}")
    purchase_date = str(order.get("order_date") or order.get("purchase_date") or "1970-01-01")[:10]

    raw_lines = order.get("lines") or order.get("items") or []
    lines: list[VendorScrapeLineOutput] = []

    for line_number, line_raw in enumerate(raw_lines, start=1):
        component_type = str(line_raw.get("component_type") or line_raw.get("line_type") or "item").lower()
        needs_review = component_type in REVIEW_LINE_TYPES
        if component_type in {"substitution", "refund"}:
            warnings.append(f"walmart_{component_type}:{external_id}:{line_number}")
        if component_type in {"pickup_fee", "delivery_fee"}:
            warnings.append(f"walmart_fee_line:{external_id}:{line_number}")

        line_metadata = metadata_json(review_reason=component_type, receipt_shape=receipt_shape) if needs_review else None
        lines.append(
            VendorScrapeLineOutput(
                line_number=line_number,
                item_description=str(line_raw.get("description") or line_raw.get("item_description") or "Walmart item"),
                quantity=str(line_raw.get("quantity") or "1"),
                line_total=money_str(line_raw.get("amount") or line_raw.get("line_total") or "0.00"),
                review_status="needs_review" if needs_review else None,
                metadata_json=line_metadata,
            )
        )

    receipt_total = order.get("order_total") or order.get("receipt_total") or order.get("total")
    if receipt_total is None and lines:
        receipt_total = money_str(sum(money_decimal(line.line_total) for line in lines))

    return (
        VendorScrapeReceiptOutput(
            external_receipt_id=external_id,
            merchant_name=merchant_name,
            purchase_date=purchase_date,
            receipt_total=money_str(receipt_total) if receipt_total is not None else None,
            lines=lines,
        ),
        warnings,
    )

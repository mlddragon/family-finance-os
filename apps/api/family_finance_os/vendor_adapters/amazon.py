from __future__ import annotations

from typing import Any

from family_finance_os.vendor_scrape_contracts import (
    VendorScrapeAdapterOutput,
    VendorScrapeLineOutput,
    VendorScrapeQuality,
    VendorScrapeReceiptOutput,
)
from family_finance_os.vendor_adapters.base import (
    VendorAdapter,
    merchant_label,
    metadata_json,
    money_decimal,
    money_str,
)


class AmazonAdapter(VendorAdapter):
    vendor_key = "amazon"

    def normalize(self, raw: dict[str, Any], *, run_id: str) -> VendorScrapeAdapterOutput:
        warnings: list[str] = []
        receipts: list[VendorScrapeReceiptOutput] = []
        merchant_name = merchant_label("Amazon", raw)

        order_sources: list[dict[str, Any]] = []
        if isinstance(raw.get("orders"), list):
            order_sources.extend(raw["orders"])
        if isinstance(raw.get("order_details"), list):
            order_sources.extend(raw["order_details"])
        if isinstance(raw.get("order_detail"), dict):
            order_sources.append(raw["order_detail"])

        for index, order in enumerate(order_sources, start=1):
            receipt, order_warnings = _normalize_order(order, merchant_name=merchant_name, fallback_index=index)
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
    fallback_index: int,
) -> tuple[VendorScrapeReceiptOutput, list[str]]:
    warnings: list[str] = []
    external_id = str(order.get("order_id") or order.get("id") or f"synthetic-amazon-order-{fallback_index}")
    purchase_date = str(order.get("order_date") or order.get("purchase_date") or order.get("date") or "1970-01-01")[:10]

    payment_groups = order.get("payment_groups") or []
    split_charge = bool(order.get("split_charge")) or len(payment_groups) > 1
    grouped_order = bool(order.get("grouped_order"))
    if split_charge:
        warnings.append(f"amazon_split_charge:{external_id}")
    if grouped_order:
        warnings.append(f"amazon_grouped_order:{external_id}")

    lines: list[VendorScrapeLineOutput] = []
    items = order.get("items") or order.get("line_items") or []
    for line_number, item in enumerate(items, start=1):
        line_total = money_str(item.get("price") or item.get("amount") or item.get("line_total") or "0.00")
        review_status = "needs_review" if split_charge or grouped_order else None
        line_metadata = None
        if split_charge:
            line_metadata = metadata_json(review_reason="split_charge")
        elif grouped_order:
            line_metadata = metadata_json(review_reason="grouped_order")
        lines.append(
            VendorScrapeLineOutput(
                line_number=line_number,
                item_description=str(item.get("title") or item.get("description") or item.get("name") or "Amazon item"),
                quantity=str(item.get("quantity") or "1"),
                line_total=line_total,
                review_status=review_status,
                metadata_json=line_metadata,
            )
        )

    receipt_total = order.get("order_total") or order.get("total") or order.get("receipt_total")
    if receipt_total is None and lines:
        receipt_total = money_str(sum(money_decimal(line.line_total) for line in lines))

    receipt = VendorScrapeReceiptOutput(
        external_receipt_id=external_id,
        merchant_name=merchant_name,
        purchase_date=purchase_date,
        receipt_total=money_str(receipt_total) if receipt_total is not None else None,
        lines=lines,
    )
    return receipt, warnings

from __future__ import annotations

from family_finance_os.vendor_adapters.amazon import AmazonAdapter
from family_finance_os.vendor_adapters.base import VendorAdapter
from family_finance_os.vendor_adapters.costco import CostcoAdapter
from family_finance_os.vendor_adapters.walmart import WalmartAdapter

ADAPTER_CLASSES: dict[str, type[VendorAdapter]] = {
    "amazon": AmazonAdapter,
    "costco": CostcoAdapter,
    "walmart": WalmartAdapter,
}

ADAPTER_DISPLAY_NAMES: dict[str, str] = {
    "amazon": "Amazon",
    "costco": "Costco",
    "walmart": "Walmart",
}


def get_adapter(vendor_key: str) -> VendorAdapter:
    adapter_class = ADAPTER_CLASSES.get(vendor_key)
    if adapter_class is None:
        from family_finance_os.vendor_scrape_contracts import VendorScrapeError

        raise VendorScrapeError(
            "vendor_adapter_not_found",
            f"Vendor adapter '{vendor_key}' was not found.",
            status_code=404,
        )
    return adapter_class()

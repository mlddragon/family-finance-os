from __future__ import annotations

import json
from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Optional

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from family_finance_os.vendor_scrape_contracts import VendorScrapeAdapterOutput

MONEY_QUANT = Decimal("0.01")
COLLECT_FIXTURE_PREFIX = "vendor_collect_"
SYNTHETIC_FIXTURE_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "synthetic"
REVIEW_LINE_TYPES = frozenset(
    {
        "membership",
        "travel",
        "pharmacy",
        "service",
        "substitution",
        "refund",
        "pickup_fee",
        "delivery_fee",
    }
)


class VendorAdapter(ABC):
    vendor_key: str

    @abstractmethod
    def normalize(self, raw: dict[str, Any], *, run_id: str) -> VendorScrapeAdapterOutput:
        """Convert vendor-shaped collect output to the adapter contract."""

    def collect(self, mode: str, *, data_root: Path, run_id: str) -> dict[str, Any]:
        from family_finance_os.vendor_scrape_contracts import VendorScrapeError

        if mode == "synthetic":
            payload = load_collect_fixture(self.vendor_key)
        elif mode == "manual_browser_assist":
            payload = load_inbox_collect_payload(data_root, self.vendor_key)
        else:
            raise VendorScrapeError("vendor_scrape_mode_invalid", "Vendor scrape mode is not supported.")
        payload = {**payload, "run_id": run_id}
        return payload


def load_collect_fixture(vendor_key: str, *, fixture_name: Optional[str] = None) -> dict[str, Any]:
    from family_finance_os.vendor_scrape_contracts import VendorScrapeError

    filename = fixture_name or f"{COLLECT_FIXTURE_PREFIX}{vendor_key}.json"
    fixture_path = SYNTHETIC_FIXTURE_DIR / filename
    if not fixture_path.exists():
        raise VendorScrapeError(
            "vendor_scrape_fixture_not_found",
            f"Synthetic collect fixture for '{vendor_key}' was not found.",
            status_code=404,
        )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def load_inbox_collect_payload(data_root: Path, vendor_key: str) -> dict[str, Any]:
    from family_finance_os.vendor_scrape_contracts import VendorScrapeError

    inbox_dir = _safe_inbox_directory(data_root, vendor_key)
    json_files = sorted(path for path in inbox_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json")
    if not json_files:
        raise VendorScrapeError(
            "vendor_scrape_collect_empty",
            (
                f"No JSON files found in vendor scrape inbox for '{vendor_key}'. "
                f"Drop browser-export JSON into {inbox_dir}."
            ),
            status_code=409,
        )

    merged: dict[str, Any] = {"inbox_files": [path.name for path in json_files]}
    payloads: list[dict[str, Any]] = []
    for path in json_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise VendorScrapeError(
                "vendor_scrape_collect_invalid",
                f"Inbox file '{path.name}' must contain a JSON object.",
            )
        payloads.append(payload)

    if len(payloads) == 1:
        merged.update(payloads[0])
        return merged

    for key in ("orders", "receipts", "order_details"):
        combined: list[Any] = []
        for payload in payloads:
            value = payload.get(key)
            if isinstance(value, list):
                combined.extend(value)
        if combined:
            merged[key] = combined
    for payload in payloads:
        for key, value in payload.items():
            if key in {"orders", "receipts", "order_details", "inbox_files"}:
                continue
            if key not in merged:
                merged[key] = value
    return merged


def _safe_inbox_directory(data_root: Path, vendor_key: str) -> Path:
    from family_finance_os.vendor_scrape_contracts import VendorScrapeError

    if not vendor_key or vendor_key.strip() != vendor_key or ".." in vendor_key or "/" in vendor_key:
        raise VendorScrapeError(
            "vendor_scrape_output_path_unsafe",
            "Vendor scrape inbox path is not safe.",
            status_code=409,
        )
    data_root_resolved = data_root.resolve()
    inbox_dir = (data_root_resolved / "vendor_scrapes" / "inbox" / vendor_key).resolve()
    try:
        inbox_dir.relative_to(data_root_resolved)
    except ValueError as exc:
        raise VendorScrapeError(
            "vendor_scrape_output_path_unsafe",
            "Vendor scrape inbox path must stay under DATA_ROOT.",
            status_code=409,
        ) from exc
    inbox_dir.mkdir(parents=True, exist_ok=True)
    return inbox_dir


def money_decimal(value: str | Decimal | int | float) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def money_str(value: Decimal | str | int | float) -> str:
    return format(money_decimal(value), "f")


def metadata_json(**fields: Any) -> str:
    return json.dumps(fields, sort_keys=True)


def is_synthetic_raw(raw: dict[str, Any]) -> bool:
    marker = raw.get("synthetic_fixture_marker", "")
    return isinstance(marker, str) and "SYNTHETIC" in marker.upper()


def merchant_label(vendor_display: str, raw: dict[str, Any]) -> str:
    if is_synthetic_raw(raw):
        return f"SYNTHETIC {vendor_display}"
    return vendor_display

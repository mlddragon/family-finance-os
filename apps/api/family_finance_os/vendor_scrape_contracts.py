from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from family_finance_os.actors import ActorContext


class VendorScrapeError(ValueError):
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


class VendorScrapeLineOutput(BaseModel):
    line_number: int = Field(ge=1)
    item_description: str = Field(min_length=1)
    quantity: Optional[str] = None
    line_total: str
    category_id: Optional[str] = None
    review_status: Optional[str] = None
    metadata_json: Optional[str] = None


class VendorScrapeReceiptOutput(BaseModel):
    external_receipt_id: str = Field(min_length=1)
    merchant_name: str = Field(min_length=1)
    purchase_date: str = Field(min_length=10, max_length=10)
    receipt_total: Optional[str] = None
    lines: list[VendorScrapeLineOutput] = Field(default_factory=list)


class VendorScrapeQuality(BaseModel):
    receipt_count: int = 0
    line_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class VendorScrapeAdapterOutput(BaseModel):
    vendor_key: str
    run_id: str
    receipts: list[VendorScrapeReceiptOutput] = Field(default_factory=list)
    quality: VendorScrapeQuality = Field(default_factory=VendorScrapeQuality)


class ActorVendorScrapeRequest(BaseModel):
    actor: str = Field(default="owner", min_length=1)
    actor_context: Optional[ActorContext] = None


class VendorScrapeRunRequest(ActorVendorScrapeRequest):
    vendor_key: str = Field(min_length=1, max_length=40)
    mode: str = Field(min_length=1, max_length=40)
    date_from: Optional[str] = Field(default=None, min_length=10, max_length=10)
    date_to: Optional[str] = Field(default=None, min_length=10, max_length=10)
    output_directory: Optional[str] = None


class VendorScrapeCancelRequest(ActorVendorScrapeRequest):
    pass

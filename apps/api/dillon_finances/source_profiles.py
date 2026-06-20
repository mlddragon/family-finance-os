from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class SourceProfile:
    source_key: str
    display_name: str
    account_type: str
    required: bool
    freshness_threshold_days: int
    accepted_file_extensions: tuple[str, ...]
    expected_headers: tuple[str, ...]
    optional_headers: tuple[str, ...]
    amount_sign_policy: str
    parser_version: str
    confirmation_status: str = "pending_owner_sample"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


SOURCE_PROFILES: tuple[SourceProfile, ...] = (
    SourceProfile(
        source_key="alliant_checking",
        display_name="Alliant Checking",
        account_type="checking",
        required=True,
        freshness_threshold_days=14,
        accepted_file_extensions=(".csv",),
        expected_headers=("Date", "Description", "Amount", "Balance"),
        optional_headers=(),
        amount_sign_policy="debits_negative_credits_positive",
        parser_version="alliant_checking:v1",
    ),
    SourceProfile(
        source_key="alliant_savings",
        display_name="Alliant Savings",
        account_type="savings",
        required=True,
        freshness_threshold_days=14,
        accepted_file_extensions=(".csv",),
        expected_headers=("Date", "Description", "Amount", "Balance"),
        optional_headers=(),
        amount_sign_policy="debits_negative_credits_positive",
        parser_version="alliant_savings:v1",
    ),
    SourceProfile(
        source_key="alliant_credit_card",
        display_name="Alliant Credit Card",
        account_type="credit_card",
        required=True,
        freshness_threshold_days=14,
        accepted_file_extensions=(".csv",),
        expected_headers=("Date", "Description", "Amount", "Balance", "Post Date"),
        optional_headers=(),
        amount_sign_policy="charges_positive_payments_negative",
        parser_version="alliant_credit_card:v1",
    ),
    SourceProfile(
        source_key="chase_prime_visa",
        display_name="Chase Prime Visa",
        account_type="credit_card",
        required=True,
        freshness_threshold_days=14,
        accepted_file_extensions=(".csv",),
        expected_headers=("Transaction Date", "Post Date", "Description", "Category", "Amount"),
        optional_headers=("Type", "Memo"),
        amount_sign_policy="charges_negative_payments_positive",
        parser_version="chase_prime_visa:v1",
    ),
)


def list_source_profiles() -> tuple[SourceProfile, ...]:
    return SOURCE_PROFILES


def iter_source_profiles() -> Iterable[SourceProfile]:
    return iter(SOURCE_PROFILES)


def get_source_profile(source_key: str) -> SourceProfile:
    for profile in SOURCE_PROFILES:
        if profile.source_key == source_key:
            return profile
    raise KeyError(f"Unknown source profile: {source_key}")

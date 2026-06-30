from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path


SYNTHETIC_MARKER = "SYNTHETIC import pack fixture — not real financial data"
PACK_VERSION = "1.0.0"
IMPORT_PACK_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic" / "imports"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fresh_dates(*, offset_days: int = 1) -> tuple[str, str]:
    transaction_date = date.today() - timedelta(days=offset_days)
    post_date = date.today()
    return transaction_date.isoformat(), post_date.isoformat()


def _stale_dates(*, offset_days: int = 60) -> tuple[str, str]:
    transaction_date = date.today() - timedelta(days=offset_days)
    post_date = transaction_date + timedelta(days=1)
    return transaction_date.isoformat(), post_date.isoformat()


def _csv_lines(rows: list[str]) -> str:
    return "\n".join(rows) + "\n"


def build_alliant_checking_csv(*, transaction_date: str) -> str:
    balance = 5200.00
    rows = ["Date,Description,Amount,Balance"]
    entries = [
        ("SYNTHETIC PAYROLL DEPOSIT", 2450.00),
        ("SYNTHETIC UTILITY BILL", -125.32),
        ("SYNTHETIC TRANSFER TO SAVINGS", -300.00),
        ("SYNTHETIC GROCERY ACH", -86.41),
        ("SYNTHETIC MORTGAGE PAYMENT", -1850.00),
        ("SYNTHETIC SUBSCRIPTION STREAMING", -15.99),
        ("SYNTHETIC ATM WITHDRAWAL", -120.00),
        ("SYNTHETIC INSURANCE AUTO", -142.50),
        ("SYNTHETIC AMAZON MARKETPLACE ACH", -64.28),
        ("SYNTHETIC INTEREST CREDIT", 4.25),
        ("SYNTHETIC PHARMACY COPAY", -22.00),
        ("SYNTHETIC SIDE HUSTLE DEPOSIT", 350.00),
    ]
    for description, amount in entries:
        balance = round(balance + amount, 2)
        rows.append(f"{transaction_date},{description},{amount:.2f},{balance:.2f}")
    return _csv_lines(rows)


def build_alliant_savings_csv(*, transaction_date: str) -> str:
    balance = 12000.00
    rows = ["Date,Description,Amount,Balance"]
    entries = [
        ("SYNTHETIC TRANSFER FROM CHECKING", 300.00),
        ("SYNTHETIC INTEREST", 4.25),
        ("SYNTHETIC EMERGENCY FUND DEPOSIT", 500.00),
        ("SYNTHETIC SMALL TRANSFER OUT", -75.00),
        ("SYNTHETIC GOAL RESERVE DEPOSIT", 200.00),
        ("SYNTHETIC CD ROLLOVER IN", 1000.00),
        ("SYNTHETIC CHARITABLE TRANSFER OUT", -50.00),
        ("SYNTHETIC MONTHLY AUTO SAVE", 150.00),
    ]
    for description, amount in entries:
        balance = round(balance + amount, 2)
        rows.append(f"{transaction_date},{description},{amount:.2f},{balance:.2f}")
    return _csv_lines(rows)


def build_alliant_credit_card_csv(*, transaction_date: str, post_date: str) -> str:
    balance = 915.75
    rows = ["Date,Description,Amount,Balance,Post Date"]
    entries = [
        ("SYNTHETIC HARDWARE STORE", 78.42),
        ("SYNTHETIC GROCERY MARKET", 84.25),
        ("SYNTHETIC GAS STATION", 52.10),
        ("SYNTHETIC AMAZON PURCHASE", 119.99),
        ("SYNTHETIC RESTAURANT DATE NIGHT", 68.50),
        ("SYNTHETIC PHARMACY", 31.20),
        ("SYNTHETIC ANNUAL MEMBERSHIP FEE", 95.00),
        ("SYNTHETIC INTEREST CHARGE", 18.44),
        ("SYNTHETIC REFUND CREDIT", -24.99),
        ("SYNTHETIC CARD PAYMENT", -450.00),
        ("SYNTHETIC HOME IMPROVEMENT", 156.73),
        ("SYNTHETIC PET SUPPLIES", 42.18),
    ]
    for description, amount in entries:
        balance = round(max(balance + amount, 0.0), 2)
        rows.append(f"{transaction_date},{description},{amount:.2f},{balance:.2f},{post_date}")
    return _csv_lines(rows)


def build_chase_prime_visa_csv(*, transaction_date: str, post_date: str) -> str:
    rows = ["Transaction Date,Post Date,Description,Category,Type,Amount"]
    entries = [
        ("SYNTHETIC GROCERY MARKET", "Food & Drink", "Sale", -62.41),
        ("SYNTHETIC ONLINE ORDER", "Shopping", "Sale", -44.18),
        ("AMAZON MARKETPLACE", "Shopping", "Sale", -128.47),
        ("WALMART SUPERCENTER", "Groceries", "Sale", -96.33),
        ("COSTCO WHOLESALE", "Groceries", "Sale", -214.88),
        ("SYNTHETIC UTILITY COMPANY", "Bills & Utilities", "Sale", -89.12),
        ("SYNTHETIC STREAMING SERVICE", "Bills & Utilities", "Sale", -15.99),
        ("SYNTHETIC GAS STATION", "Gas", "Sale", -48.76),
        ("SYNTHETIC RESTAURANT", "Food & Drink", "Sale", -54.20),
        ("TARGET STORE", "Shopping", "Sale", -73.65),
        ("SYNTHETIC HOME IMPROVEMENT", "Home", "Sale", -132.40),
        ("SYNTHETIC MEDICAL PHARMACY", "Health & Wellness", "Sale", -28.50),
        ("SYNTHETIC TRAVEL BOOKING", "Travel", "Sale", -412.00),
        ("SYNTHETIC COFFEE SHOP", "Food & Drink", "Sale", -6.75),
        ("SYNTHETIC CARD PAYMENT", "Payment", "Payment", 350.00),
        ("SYNTHETIC REFUND CREDIT", "Shopping", "Return", 19.99),
    ]
    for description, category, txn_type, amount in entries:
        rows.append(
            f"{transaction_date},{post_date},{description},{category},{txn_type},{amount:.2f}"
        )
    return _csv_lines(rows)


def build_net_worth_csv(*, snapshot_date: str) -> str:
    rows = [
        "snapshot_date,asset_or_liability,account_name,institution,category,subcategory,balance,valuation_method,confidence,source_notes",
        f"{snapshot_date},asset,SYNTHETIC Checking,Local Credit Union,liquid_cash,checking,5200.00,actual,high,",
        f"{snapshot_date},asset,SYNTHETIC Savings,Local Credit Union,liquid_cash,savings,12829.25,actual,high,",
        f"{snapshot_date},asset,SYNTHETIC Brokerage,Example Brokerage,investment,taxable,18500.00,actual,high,",
        f"{snapshot_date},asset,SYNTHETIC Vehicle,Garage,vehicle,sedan,8000.00,estimate,medium,{SYNTHETIC_MARKER}",
        f"{snapshot_date},asset,SYNTHETIC Home Equity Estimate,Appraisal Service,home,primary_residence,120000.00,estimate,low,{SYNTHETIC_MARKER}",
        f"{snapshot_date},liability,SYNTHETIC Card,Card Issuer,consumer_debt,card,915.75,actual,high,",
        f"{snapshot_date},liability,SYNTHETIC Auto Loan,Credit Union,consumer_debt,auto,8400.00,actual,high,",
        f"{snapshot_date},liability,SYNTHETIC Mortgage,Lender,consumer_debt,mortgage,210000.00,actual,high,",
    ]
    return _csv_lines(rows)


def build_receipts_csv(*, purchase_date: str) -> str:
    rows = [
        "merchant,purchase_date,receipt_total,line_description,line_quantity,line_amount,category_id,transaction_id",
        f"SYNTHETIC Amazon,{purchase_date},128.47,SYNTHETIC household supplies,1,48.47,,",
        f"SYNTHETIC Amazon,{purchase_date},128.47,SYNTHETIC book bundle,1,40.00,,",
        f"SYNTHETIC Amazon,{purchase_date},128.47,SYNTHETIC pantry item,1,40.00,,",
        f"SYNTHETIC Walmart,{purchase_date},96.33,SYNTHETIC groceries,1,62.33,,",
        f"SYNTHETIC Walmart,{purchase_date},96.33,SYNTHETIC household,1,34.00,,",
        f"SYNTHETIC Costco,{purchase_date},214.88,SYNTHETIC bulk groceries,1,120.00,,",
        f"SYNTHETIC Costco,{purchase_date},214.88,SYNTHETIC household goods,1,54.88,,",
        f"SYNTHETIC Costco,{purchase_date},214.88,SYNTHETIC pharmacy line,1,40.00,,",
        f"SYNTHETIC Hardware Store,{purchase_date},78.42,SYNTHETIC paint supplies,1,78.42,,",
    ]
    return _csv_lines(rows)


def build_blocked_wrong_header_csv() -> str:
    return _csv_lines(
        [
            "Wrong,Header",
            "SYNTHETIC WRONG HEADER,12.34",
        ]
    )


def build_manifest(*, files: dict[str, dict[str, int | str]]) -> dict[str, object]:
    fresh_txn, fresh_post = _fresh_dates()
    stale_txn, _ = _stale_dates()
    return {
        "synthetic_fixture_marker": SYNTHETIC_MARKER,
        "pack_version": PACK_VERSION,
        "generated_for_dates": {
            "fresh_transaction_date": fresh_txn,
            "fresh_post_date": fresh_post,
            "stale_transaction_date": stale_txn,
        },
        "files": files,
        "manual_import_order": [
            "alliant_checking.csv",
            "alliant_savings.csv",
            "alliant_credit_card.csv",
            "chase_prime_visa.csv",
            "net_worth.csv",
            "receipts.csv",
        ],
        "feature_coverage": [
            "ledger_import_all_four_sources",
            "review_and_approval_workflows",
            "mixed_basket_merchants_amazon_walmart_costco",
            "card_payments_refunds_interest",
            "internal_transfers_and_income",
            "net_worth_actual_and_estimate_rows",
            "receipt_csv_import_and_review_queues",
            "blocked_import_validation_via_blocked_wrong_header.csv",
            "stale_source_testing_via_chase_prime_visa_stale.csv",
        ],
    }


def generate_import_pack(*, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    fresh_txn, fresh_post = _fresh_dates()
    stale_txn, stale_post = _stale_dates()
    snapshot_date = fresh_post

    files: dict[str, str] = {
        "alliant_checking.csv": build_alliant_checking_csv(transaction_date=fresh_txn),
        "alliant_savings.csv": build_alliant_savings_csv(transaction_date=fresh_txn),
        "alliant_credit_card.csv": build_alliant_credit_card_csv(
            transaction_date=fresh_txn,
            post_date=fresh_post,
        ),
        "chase_prime_visa.csv": build_chase_prime_visa_csv(
            transaction_date=fresh_txn,
            post_date=fresh_post,
        ),
        "chase_prime_visa_stale.csv": build_chase_prime_visa_csv(
            transaction_date=stale_txn,
            post_date=stale_post,
        ),
        "net_worth.csv": build_net_worth_csv(snapshot_date=snapshot_date),
        "receipts.csv": build_receipts_csv(purchase_date=fresh_txn),
        "blocked_wrong_header.csv": build_blocked_wrong_header_csv(),
    }

    file_stats: dict[str, dict[str, int | str]] = {}
    for filename, content in files.items():
        path = output_dir / filename
        path.write_text(content, encoding="utf-8")
        row_count = max(len(content.strip().splitlines()) - 1, 0)
        file_stats[filename] = {"rows": row_count, "path": f"tests/fixtures/synthetic/imports/{filename}"}

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(build_manifest(files=file_stats), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic manual-import CSV pack.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=IMPORT_PACK_DIR,
        help="Directory for generated CSV fixtures.",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.is_relative_to(_repo_root()):
        pass
    generate_import_pack(output_dir=output_dir)
    print(f"Generated synthetic import pack in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

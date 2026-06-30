# Synthetic manual import pack

**SYNTHETIC import pack fixture — not real financial data.**

CSV files in this directory support **manual import and approval QA** without running `make qa-seed`. They are also the source of truth for `scripts/qa_seed.py` scenario imports.

## Regenerate (fresh dates)

Source freshness checks use transaction dates. Regenerate before manual QA if files are older than your freshness threshold (default 14 days):

```bash
make generate-synthetic-imports
```

## Manual import order

Upload from **Sources → Scan inbox** or the import UI. Confirm source profiles first if prompted.

| File | Source key / endpoint | Rows (approx.) | Covers |
| --- | --- | --- | --- |
| `alliant_checking.csv` | `alliant_checking` | 12 | Payroll, utilities, transfers, subscriptions, mixed outflows |
| `alliant_savings.csv` | `alliant_savings` | 8 | Transfers, interest, goal deposits |
| `alliant_credit_card.csv` | `alliant_credit_card` | 12 | Purchases, refunds, payments, interest, fees |
| `chase_prime_visa.csv` | `chase_prime_visa` | 16 | Amazon/Walmart/Costco, utilities, travel, payment/refund |
| `chase_prime_visa_stale.csv` | `chase_prime_visa` | 16 | Same shape as fresh Chase file but **stale dates** for freshness QA |
| `net_worth.csv` | `POST /api/net-worth/imports` | 8 | Actual + estimate assets/liabilities |
| `receipts.csv` | `POST /api/receipts/imports` | 9 lines / 4 receipts | Mixed-basket receipt lines (link to transactions after import) |
| `blocked_wrong_header.csv` | any upload | 1 | Blocking validation / quarantine testing |

See `manifest.json` for row counts and feature coverage notes.

## Suggested manual QA flow

1. Reset or use an empty `DATA_ROOT` (no seed): `make qa-reset CONFIRM="RESET QA DATA"` then `make qa-up` — **skip** `qa-seed`.
2. Confirm source profiles in Settings if required.
3. Import the four ledger CSVs in order; validate and accept each batch (acknowledge warnings when shown).
4. Import `net_worth.csv` and `receipts.csv` through their respective import endpoints or UI when available.
5. Exercise Review (unreviewed transactions), splits (mixed-basket merchants), receipt review queue, and approval flows.
6. Optionally upload `blocked_wrong_header.csv` to verify blocking validation without accepting.

## Relationship to seed scenarios

`make qa-seed` loads these same ledger files programmatically. Scenario-specific behavior (e.g. stale Chase for `stale-source`) is applied by choosing `chase_prime_visa_stale.csv` in the seed script.

Generated QA database state, manifests under `DATA_ROOT/manifests/`, and accepted imports remain outside git.

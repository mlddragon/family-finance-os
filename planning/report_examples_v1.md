# Report Examples v1

This document provides synthetic examples for the v1 report and monthly close artifacts described in `planning/report_monthly_close_artifacts_v1.md`. It is a planning artifact only. It does not create report code, create schema, generate artifacts, or include real financial data.

All values, sources, merchants, dates, ids, and amounts below are synthetic.

## Example 1: Import And Validation Summary

Example file:

```text
DATA_ROOT/reports/runs/rr_2026_06_validation_example/validation_summary.md
```

Example Markdown:

```markdown
# Import And Validation Summary

Period: 2026-06
Report run: rr_2026_06_validation_example
Status: Provisional

## Source Coverage

| Source | Required | Latest Import | Latest Transaction | Freshness | Status |
|---|---:|---|---|---|---|
| Alliant Checking | Yes | 2026-06-18 | 2026-06-17 | Current | Ready |
| Alliant Savings | Yes | 2026-06-18 | 2026-06-16 | Current | Ready |
| Alliant Credit Card | Yes | 2026-06-18 | 2026-06-17 | Current | Warning |
| Chase Prime Visa | Yes | 2026-06-01 | 2026-05-30 | Stale | Provisional |

## Imported Files

| File | Source | Rows | Date Min | Date Max | Validation |
|---|---|---:|---|---|---|
| alliant_checking_redacted.csv | Alliant Checking | 124 | 2026-06-01 | 2026-06-17 | Passed |
| alliant_savings_redacted.csv | Alliant Savings | 18 | 2026-06-01 | 2026-06-16 | Passed |
| alliant_card_redacted.csv | Alliant Credit Card | 88 | 2026-06-01 | 2026-06-17 | Warning |
| chase_prime_redacted.csv | Chase Prime Visa | 92 | 2026-05-01 | 2026-05-30 | Stale |

## Validation Findings

| Severity | Code | Target | Message | Status |
|---|---|---|---|---|
| Warning | source_stale | Chase Prime Visa | Latest transaction is 19 days old. | Open |
| Warning | amount_sign_unexpected | Alliant Credit Card row 44 | Positive credit requires review. | Acknowledged |
| Info | export_overlap_detected | Alliant Checking | 12 rows overlap prior accepted batch. | Resolved |

## Result

Accepted with warnings. Reports using Chase Prime Visa data are provisional. Final monthly close is blocked until Chase is current for the close period.
```

Example machine-readable rows:

```text
severity,code,target,message,status
warning,source_stale,Chase Prime Visa,Latest transaction is 19 days old,open
warning,amount_sign_unexpected,Alliant Credit Card row 44,Positive credit requires review,acknowledged
info,export_overlap_detected,Alliant Checking,12 rows overlap prior accepted batch,resolved
```

## Example 2: Cashflow Summary

Example file:

```text
DATA_ROOT/reports/runs/rr_2026_06_cashflow_example/cashflow_summary.csv
```

Example table:

```text
month,income,spending,transfers,net_cashflow,source_coverage,validation_status,provisional_reason
2026-06,7400.00,-6925.00,-1200.00,475.00,3_of_4_required_sources_current,provisional,Chase Prime Visa stale
2026-05,7350.00,-7810.00,-1200.00,-460.00,4_of_4_required_sources_current,final,
2026-04,7350.00,-7040.00,-1200.00,310.00,4_of_4_required_sources_current,final,
```

Reading intent:

- `income`, `spending`, and `transfers` are separated so payments and internal movements do not inflate spending.
- `net_cashflow` is provisional when required source coverage is incomplete or stale.
- The UI should show the provisional reason next to any displayed total.

## Example 3: Category Spending Summary

Example file:

```text
DATA_ROOT/reports/runs/rr_2026_06_category_example/category_spending_summary.csv
```

Example table:

```text
month,category,subcategory,spending_amount,transaction_count,reviewed_amount,unreviewed_amount,review_exposure_pct,provisional_status
2026-06,Housing,Mortgage,-2100.00,1,-2100.00,0.00,0.00,final
2026-06,Groceries,General Groceries,-965.50,18,-720.25,-245.25,25.40,provisional
2026-06,Transportation,Fuel,-315.20,7,-315.20,0.00,0.00,final
2026-06,Shopping,General Shopping,-842.80,14,-220.00,-622.80,73.90,provisional
2026-06,Medical,Pharmacy,-118.42,3,-40.00,-78.42,66.22,provisional
```

Reading intent:

- Review exposure is visible instead of hidden.
- Provisional categories should guide review priority before financial conclusions are treated as final.
- Vendor/item detail can later enrich categories, but ledger transactions remain the cashflow source.

## Example 4: Review Backlog Summary

Example file:

```text
DATA_ROOT/reports/runs/rr_2026_06_review_backlog_example/review_backlog_summary.csv
```

Example table:

```text
review_reason,count,dollar_exposure,source,category,blocking_or_provisional_impact
Uncategorized transaction,22,-1480.35,All Sources,Unknown,provisional_reports
Possible transfer,6,-2400.00,Alliant Checking,Transfer,report_classification
Large transaction,4,-1975.20,All Sources,Mixed,review_priority
Possible reimbursement,3,-640.00,Chase Prime Visa,Mixed,advisor_note
Medical/tax candidate,2,-118.42,Alliant Credit Card,Medical,advisor_note
```

Reading intent:

- This report tells the owner what review work changes confidence the most.
- Counts alone are not enough; dollar exposure is required.
- Review reasons should map back to queue filters in the UI.

## Example 5: Top Merchants/Sources

Example file:

```text
DATA_ROOT/reports/runs/rr_2026_06_top_merchants_example/top_merchants_sources.csv
```

Example table:

```text
merchant_or_source,category,amount,transaction_count,review_exposure,provisional_status
REDACTED MORTGAGE,Housing,-2100.00,1,0.00,final
REDACTED GROCERY,Groceries,-640.25,9,-140.25,provisional
REDACTED RETAILER,Shopping,-580.10,7,-520.10,provisional
REDACTED UTILITY,Utilities,-310.00,2,0.00,final
REDACTED FUEL,Transportation,-225.60,5,0.00,final
```

Reading intent:

- Merchant names can be shown in operator views but should be redacted in committed examples.
- Review exposure highlights which merchant totals are not yet trustworthy.
- Later vendor plugins can add item-level explanation without changing ledger totals.

## Example 6: Monthly Close Memo

Example file:

```text
DATA_ROOT/monthly_close/2026-06/draft/memo/monthly_close_memo.md
```

Example Markdown:

```markdown
# Monthly Close Memo

Month: 2026-06
Close id: close_2026_06_draft_example
Status: Draft / Provisional

## Close Readiness

June is not ready for final close. Chase Prime Visa is stale, and two warning findings remain open. Reports can be used for review, but not for final decisions.

## What Changed

- Net cashflow is positive by 475.00 based on current accepted data.
- Shopping and grocery categories have material unreviewed exposure.
- Internal transfers appear consistent, but six possible-transfer rows still need review.

## What Is Safe To Trust

- Alliant Checking, Alliant Savings, and Alliant Credit Card imports are current.
- Housing and utility totals have no open review exposure.
- Imported raw files are preserved and hashed.

## What Remains Provisional

- Chase Prime Visa data is stale.
- Shopping category total has 73.90% review exposure.
- Grocery category total has 25.40% review exposure.

## Open Blockers

- Chase Prime Visa must be refreshed through month end before final close.
- Duplicate ambiguity must be resolved for any rows that affect June totals.

## Recommended Next Actions

1. Import current Chase Prime Visa export.
2. Review uncategorized and large Shopping transactions.
3. Resolve possible transfer rows before final close.
4. Regenerate close draft after validation passes.
```

Reading intent:

- The memo is narrative, but it must cite the underlying validation and report artifacts in the real implementation.
- It should be safe to hand to an advisor only when provisional status is unmistakable.

## Example 7: Monthly Close Manifest

Example file:

```text
DATA_ROOT/monthly_close/2026-06/draft/manifest.json
```

Example JSON:

```json
{
  "close_id": "close_2026_06_draft_example",
  "month": "2026-06",
  "status": "draft",
  "created_at": "2026-06-30T20:15:00-05:00",
  "finalized_at": null,
  "actor": "owner",
  "source_import_batch_ids": [
    "batch_alliant_checking_example",
    "batch_alliant_savings_example",
    "batch_alliant_card_example"
  ],
  "report_run_ids": [
    "rr_2026_06_validation_example",
    "rr_2026_06_cashflow_example",
    "rr_2026_06_category_example"
  ],
  "validation_state": {
    "blocking": 0,
    "warnings": 2,
    "provisional": true,
    "provisional_reasons": ["Chase Prime Visa stale"]
  },
  "artifacts": [
    {
      "path": "validation/validation_summary.md",
      "type": "validation_summary",
      "sha256": "synthetic_hash_validation_summary",
      "bytes": 1234
    },
    {
      "path": "reports/cashflow_summary.csv",
      "type": "cashflow_summary",
      "sha256": "synthetic_hash_cashflow",
      "bytes": 456
    }
  ],
  "supersedes_close_id": null
}
```

Reading intent:

- The manifest is the bundle entrypoint for the UI and advisor flow.
- It should tell the app what exists, what it means, and whether it is final.
- Hashes and byte sizes are synthetic in this document.

## Example 8: Advisor Export

Example files:

```text
DATA_ROOT/monthly_close/2026-06/draft/advisor_export/advisor_summary.md
DATA_ROOT/monthly_close/2026-06/draft/advisor_export/advisor_tables.json
```

Example advisor summary:

```markdown
# Advisor Summary

Month: 2026-06
Status: Provisional

This export is intended for owner-directed advisor analysis. It includes current report outputs and validation status. It should not be treated as final because Chase Prime Visa is stale.

## Data Trust

- Required sources current: 3 of 4.
- Blocking validation findings: 0.
- Warning validation findings: 2.
- Final monthly close: blocked until Chase Prime Visa is refreshed.

## Key Figures

- Income: 7400.00.
- Spending: -6925.00.
- Transfers: -1200.00.
- Net cashflow: 475.00 provisional.

## Review Exposure

- Shopping: -622.80 unreviewed.
- Groceries: -245.25 unreviewed.
- Medical: -78.42 unreviewed.

## Requested Advisor Focus

1. Identify the highest-impact review items.
2. Avoid recommendations that assume Chase data is current.
3. Treat all provisional categories as review targets, not final facts.
```

Example advisor tables JSON:

```json
{
  "status": "provisional",
  "month": "2026-06",
  "validation": {
    "required_sources_current": 3,
    "required_sources_total": 4,
    "blocking_findings": 0,
    "warning_findings": 2,
    "provisional_reasons": ["Chase Prime Visa stale"]
  },
  "cashflow": {
    "income": 7400.0,
    "spending": -6925.0,
    "transfers": -1200.0,
    "net_cashflow": 475.0
  },
  "review_exposure": [
    {"category": "Shopping", "unreviewed_amount": -622.8},
    {"category": "Groceries", "unreviewed_amount": -245.25},
    {"category": "Medical", "unreviewed_amount": -78.42}
  ]
}
```

Reading intent:

- Advisor export must carry validation status with the numbers.
- It should be generated only by explicit owner action.
- It can include raw transaction detail later only when the owner explicitly chooses that export scope.

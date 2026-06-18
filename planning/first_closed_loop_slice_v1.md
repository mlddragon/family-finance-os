# First Closed-Loop Slice v1

This document defines the first minimally viable closed-loop product slice for Dillon Finances. It is a planning artifact only. It does not approve app implementation, create schema, add dependencies, or migrate financial data.

## Status

- Slice definition approved by owner.
- App implementation has not started.
- Data model and audit design have been captured in `planning/data_model_audit_design_v1.md`.
- UI mockups have been approved for v1 planning in `planning/ui_mockups_v1.md`.
- This slice should guide the next UI, import validation, report artifact, test, and implementation planning work.

## Product Goal

v1 proves the ledger-first household finance operating loop with the smallest useful scope:

```text
manual export
  -> guided import
  -> validation
  -> normalized ledger state
  -> classification
  -> stale/validation review queue
  -> ledger classification review queue
  -> owner-approved controlled decision event
  -> updated derived state
  -> budget/cashflow reports
  -> monthly close bundle
  -> advisor-ready export
  -> next import refresh prompt
```

The purpose is to prove that data can move through the product without hidden mutation, double-counting, fake precision, or unreviewed decisions becoming facts.

## Stage Plan

### v1: Ledger Closed Loop

Prove the closed loop using core bank and card exports:

- Alliant Checking.
- Alliant Savings.
- Alliant Credit Card.
- Chase Prime Visa.

### v1.1: Amazon Enrichment

Add Amazon as the first vendor enrichment plugin after the ledger loop is stable. Amazon should use the shared vendor contract and must not become the core architecture.

### v1.2: Walmart And Costco Enrichment

Add Walmart and Costco through the same vendor-detail framework after Amazon proves the plugin path.

## v1 Source Inputs

Approved v1 inputs:

- Alliant Checking export.
- Alliant Savings export.
- Alliant Credit Card export.
- Chase Prime Visa export.

Input boundaries:

- Manual export only.
- Files placed in `DATA_ROOT/inbox/` or uploaded through the local browser UI.
- No bank aggregators.
- No stored credentials.
- No browser automation.
- No PDF parsing.
- No old prototype data migration.

## v1 Review Queues

v1 includes two review queue families.

### Import And Validation Issues

Examples:

- Missing expected file.
- Stale source.
- Wrong schema.
- Duplicate transaction ID.
- Date parse failure.
- Unexpected amount sign.
- Unsupported account or source.
- Import batch mismatch.
- File moved to quarantine.

### Ledger Classification Review

Examples:

- Unknown merchant.
- Uncategorized transaction.
- Low-confidence category.
- Large transaction over threshold.
- Possible transfer.
- Possible reimbursement or job expense.
- Possible medical/tax candidate.
- Possible side-hustle candidate.
- Possible project candidate.

Deferred review queues:

- Vendor item review is deferred to vendor enrichment stages.
- True ledger transaction splits are deferred until after the event model is proven.

## v1 Controlled Update Scope

v1 supports exactly one controlled write path:

- Owner-approved ledger classification decisions through append-only decision events.

Classification decision fields may include:

- Category.
- Subcategory.
- Review status.
- Review reason.
- Transfer flag/status.
- Reimbursement candidate/status.
- Medical/tax candidate/status.
- Side-hustle candidate flag.
- Project candidate flag.

Rules:

- Raw files are never mutated.
- Imported ledger records are not directly overwritten.
- Reviewed current state is derived from normalized ledger records plus approved decision events.
- Every controlled update must be auditable and reversible.

## v1 Reports And Outputs

v1 reports should be the minimum set needed to close the loop.

### Import And Validation Summary

Answers:

- What files were imported?
- Which sources passed or failed?
- What is the latest transaction date by source?
- Which sources are stale?
- What are row counts by file/source?
- Were duplicates, schema issues, or date/amount problems found?

### Cashflow Summary

Shows by month:

- Income.
- Spending.
- Transfers.
- Net cashflow.

### Category Spending Summary

Shows:

- Spending by category and subcategory.
- Reviewed exposure.
- Unreviewed exposure.
- Provisional status where review exposure is material.

### Review Backlog Summary

Shows:

- Counts by review reason.
- Dollar exposure by review reason.
- Counts and dollars by category/source where useful.

### Top Merchants/Sources

Shows high-impact merchants and transaction sources for prioritization.

### Monthly Close Memo

Markdown narrative covering:

- What changed.
- What needs review.
- What is safe to trust.
- What remains provisional.
- Recommended next actions.

Deferred reports:

- Budget target variance.
- Vendor category impact.
- Net worth.
- Retirement.
- Reimbursement aging.
- Tax reports.

## v1 Success Criteria

v1 is complete only when the product can prove the following end-to-end with synthetic data first, then owner-approved real local exports:

1. Import Alliant and Chase exports without committing raw data.
2. Preserve raw files and record import batches.
3. Validate schema, row counts, dates, duplicates, amount signs, and source/account identity.
4. Normalize ledger records into SQLite.
5. Generate import/validation review queues.
6. Generate ledger classification review queues.
7. Apply at least one owner-approved classification decision as an append-only event.
8. Derive reviewed current state without mutating raw or imported records.
9. Generate the approved v1 reports.
10. Generate a monthly close bundle.
11. Produce an advisor-ready export for ChatGPT/OpenAI analysis.
12. Prompt the next refresh action.
13. Pass tests and validation checks.
14. Demonstrate that no financial data is written into git-tracked paths.

## v1 Non-Goals

Out of scope for v1:

- Amazon enrichment.
- Walmart enrichment.
- Costco enrichment.
- Vendor item-level categorization.
- Ledger transaction splits.
- Automated bank connections.
- Stored credentials.
- Stored browser sessions.
- PDF parsing.
- Budget target enforcement or variance reporting.
- Net worth planning.
- Retirement planning.
- Household-facing envelope UI.
- LAN/NAS exposure.
- Authentication/login.
- Live AI API integration.
- Local LLM integration.
- Paid tools or services.
- Old prototype code migration.
- Old raw, normalized, reviewed, or generated financial data migration.

## v1 UI Scope

v1 UI is operator-facing and read-mostly.

### Home / Current Status

Shows:

- Latest import status.
- Data freshness.
- Validation status.
- Open review counts.
- Latest monthly close status.
- Next refresh action.

### Import Inbox

Shows:

- Detected files.
- Source identification.
- Validation results.
- Quarantine items.
- Next action.

### Review Queues

Shows:

- Import/validation issues.
- Ledger classification review.

### Reports

Shows:

- v1 report list.
- Monthly close memo.
- Generated export artifacts.

### Settings

Shows:

- `DATA_ROOT` status.
- Local-only/network status.
- Source definitions.
- Category taxonomy basics.
- Freshness thresholds.
- Review thresholds.

Controlled writes in v1 UI:

- Approved classification decision events, only after the audit model is approved.
- Settings changes, only after the settings audit model is approved.
- Otherwise, the UI remains read-only until those gates pass.

## v1 Data Freshness Model

Approved freshness behavior:

- Track latest successful import per source.
- Track latest transaction date per source.
- Show days since latest transaction per source.
- Fresh/stale status is based on configurable thresholds.
- Reports are marked provisional if any required source is stale, missing, or has blocking validation failures.

Initial defaults:

- Checking and card sources become stale after 14 days.
- Monthly close requires all required sources imported through the target month end.
- Owner can later edit thresholds in Settings.

## Required Gates Before Implementation

Before implementation planning starts, the following gates apply:

- Completed: data model and audit design have been captured in `planning/data_model_audit_design_v1.md`.
- Completed: UI mockups for v1 screens have been approved in `planning/ui_mockups_v1.md`.
- Drafted for review: import validation contract has been captured in `planning/import_validation_contract_v1.md`.
- Drafted for review: report and monthly close artifact detail has been captured in `planning/report_monthly_close_artifacts_v1.md`.
- Remaining: settings/config audit design.
- Remaining: controlled decision event model.
- Drafted for review: test and validation strategy has been captured in `planning/test_validation_strategy_v1.md`.

## Next Recommended Work

The next planning work should be one of:

1. Owner review of `planning/report_monthly_close_artifacts_v1.md`.
2. Owner review of `planning/test_validation_strategy_v1.md`.
3. Settings/config audit design.
4. Controlled decision event model.
5. Implementation plan after the above gates are approved.

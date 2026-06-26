# v1.1 D1 Receipts Engineering Plan

Status: Draft  
Build phase: Phase 4  
Schema note: `planning/engineering/v1_1_a1_schema.md` is not present in this checkout. Use the table and API names below from `planning/v1_1_expansion_decision_record.md`; align to A1 on merge.

## Purpose

Implement manual receipt entry, receipt CSV import, line-item review queues, and D11 promote-to-splits behavior before vendor scrapers.

D5 sets the phase order:

- Main pass: manual receipt/line-item entry, CSV import, review queues.
- Scrapers come last after the rest of v1.1 is stable.

D11 sets precedence:

- Receipt line items are enrichment by default.
- Transaction splits drive reports, Pool remaining, and targets.
- "Apply receipt lines as splits" requires explicit UI action, confirmation, and a decision event.

## Non-goals

- No vendor scraper implementation in D1.
- No OCR or image attachment processing.
- No automatic promotion from receipt lines to splits.
- No replacement of ledger transactions with receipt lines.
- No storage of real receipts or generated receipt artifacts in git.

## Schema/API

### Tables

Expected A1 tables or equivalents:

- `receipts`
- `receipt_lines`
- `receipt_imports` or existing `import_batches` with receipt type
- existing `transaction_allocations`
- existing `decision_events`

`receipts` fields:

- `id`
- `transaction_id` nullable until matched
- `merchant`
- `receipt_date`
- `total_amount`
- `source_type` - `manual`, `csv_import`, `scraper`
- `source_vendor`
- `review_status`
- audit metadata

`receipt_lines` fields:

- `id`
- `receipt_id`
- `line_index`
- `description`
- `quantity`
- `amount`
- `category_key`
- `fund_pool_id`
- `review_required`
- `review_reason`
- `promoted_to_allocation_id`
- audit metadata

### CSV Import

Input columns:

- `merchant`
- `receipt_date`
- `receipt_total`
- `line_description`
- `line_quantity`
- `line_amount`
- `category_key`
- optional `transaction_id`
- optional `source_vendor`

Import validation:

- Date and amount parsing.
- Required merchant/date/total fields.
- Line totals may be partial, but over-total requires warning or rejection as A1 defines.
- Optional transaction id must resolve to an imported/canonical transaction.
- CSV files stay under external `DATA_ROOT`.

### API Shape

Proposed endpoints:

- `GET /api/receipts?status=open&transaction_id=...`
- `POST /api/receipts`
- `GET /api/receipts/{receipt_id}`
- `PATCH /api/receipts/{receipt_id}`
- `POST /api/receipts/imports`
- `POST /api/receipts/imports/{import_id}/accept`
- `GET /api/receipt-review-queue`
- `POST /api/receipts/{receipt_id}/promote-to-splits`

Promotion request:

```json
{
  "actor": "owner",
  "actor_context": {},
  "transaction_id": "txn_synthetic_001",
  "confirmation": "apply_receipt_lines_as_splits",
  "note": "Use receipt lines for mixed basket allocation"
}
```

Error codes:

- `receipt_not_found`
- `receipt_transaction_required`
- `receipt_lines_required`
- `receipt_promotion_confirmation_required`
- `receipt_promotion_total_mismatch`
- `receipt_csv_invalid`

### Review Queues

Queue types:

- unmatched receipt
- receipt total mismatch
- line category needed
- mixed basket candidate
- reimbursement candidate
- medical tax candidate
- side-hustle candidate
- duplicate receipt candidate

Receipt queues should appear in Review while preserving existing validation/review queues.

## UI (Mockup Screen)

Mockup reference: `planning/mockups/v1_1/index.html`, Screen E.

Receipt entry surface:

- Launch from Transactions and Review.
- Manual fields: Merchant, Date, Total, linked transaction.
- Line item editor with Add line item.
- Show Items total, Receipt total, and Unaccounted amount.
- Saving partial itemization is allowed and should be labeled optional.
- Buttons: Cancel, Save and start split from items, Save receipt.

Promotion UX:

- "Save and start split from items" opens Split editor with proposed allocation lines.
- User must review and save split separately or confirm `promote-to-splits` action.
- Show D11 language: receipt lines are enrichment until applied as splits.
- If both receipt lines and splits exist, show reconciliation hints and no auto-merge.

## Test Plan

Backend unit tests:

- Manual receipt create saves header and ordered lines.
- Partial receipt itemization is allowed.
- CSV import validates required fields and rejects invalid rows.
- Review queue records are created for unmatched, category-needed, and total-mismatch cases.
- Promotion requires confirmation and linked transaction.
- Promotion creates balanced `transaction_allocations` only when totals match policy.
- Promotion writes decision event and links receipt lines to allocation ids.

API tests:

- Receipt routes require transaction/review permissions as A3 defines.
- Import accept uses synthetic fixtures and stores files under `DATA_ROOT`.
- Error responses use stable detail codes.

Frontend tests:

- Receipt entry launches from Transactions and Review.
- Line item totals update Unaccounted amount.
- Save receipt works with partial itemization.
- Promotion path opens Split editor or confirmation flow.
- D11 precedence hint is visible when receipt and split data coexist.

Human QA:

- Create a synthetic receipt linked to a synthetic card transaction.
- Save partial lines and confirm reports do not change.
- Promote lines to splits and confirm reports, Pool remaining, and targets change only after split save/confirmation.

## Dependencies on A1/A2/A3

- A1: final receipt tables, import linkage, and review queue modeling.
- A2: spendable/funds remain driven by splits, not raw receipt lines.
- A3: permissions and actor audit context.
- B2: split API and D11 promotion contract.
- E1: scraper output must create receipt headers/lines first, reusing D1 contracts.

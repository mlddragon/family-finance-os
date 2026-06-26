# v1.1 B2 Splits Engineering Plan

Status: Draft  
Build phase: Phase 2  
Schema note: `planning/engineering/v1_1_a1_schema.md` is not present in this checkout. Use the table and API names below from `planning/v1_1_expansion_decision_record.md`; align to A1 on merge.

## Purpose

Add transaction splits through `transaction_allocations` so a single imported ledger transaction can drive multiple categories, fund pools, targets, flags, and reports while preserving the imported row as the source-of-truth cashflow fact.

D11 governs precedence: receipt line items enrich transactions by default, but splits drive reports, pool remaining, and targets. Receipt lines become splits only through an explicit "Apply receipt lines as splits" action with confirmation and a decision event.

## Non-goals

- Do not mutate imported row amounts or duplicate imported transactions.
- Do not auto-create splits from receipt lines, vendor lines, or category suggestions.
- Do not allow unbalanced allocations to affect reports.
- Do not replace existing category review decisions until the split is saved.
- Do not implement tax, reimbursement, or side-hustle workflows beyond carrying allocation flags needed by later tracks.

## Schema/API

### Tables

Expected A1 table:

- `transaction_allocations`

Required fields or equivalents:

- `id`
- `transaction_id`
- `line_index`
- `amount`
- `category_key`
- `subcategory_key`
- `fund_pool_id`
- `financial_goal_id`
- `budget_target_id`
- `allocation_note`
- flags for `reimbursement_candidate`, `medical_tax_candidate`, `side_hustle_candidate`, and similar review queues as A1 permits
- audit metadata

Constraints:

- Allocation amounts for a transaction must balance exactly to the transaction amount before save.
- Line order must be stable for audit and UI replay.
- Deleted/replaced split sets should remain auditable through decision events. A1 may choose hard replacement plus event history or soft versioning.

### API Shape

Proposed endpoints:

- `GET /api/transactions/{transaction_id}/allocations`
- `PUT /api/transactions/{transaction_id}/allocations`
- `DELETE /api/transactions/{transaction_id}/allocations`
- `POST /api/transactions/{transaction_id}/allocations/from-receipt`

`PUT` payload:

```json
{
  "actor": "owner",
  "actor_context": {},
  "lines": [
    {
      "amount": "-120.00",
      "category_key": "groceries",
      "subcategory_key": null,
      "fund_pool_id": "pool_groceries",
      "note": "Synthetic example"
    }
  ],
  "note": "Split mixed basket"
}
```

Error codes should be stable:

- `transaction_not_found`
- `allocation_lines_required`
- `allocation_amount_invalid`
- `allocation_total_mismatch`
- `allocation_category_invalid`
- `allocation_permission_denied`

### Report Rollup Changes

Current reporting groups by `transaction["category_current"]`. B2 changes report inputs so allocation lines are preferred when present:

1. If balanced `transaction_allocations` exist, reports use allocation lines.
2. If no split exists, reports use the reviewed transaction category.
3. Receipt line items never affect reports unless promoted to splits through the D11 action.

Affected rollups:

- category spending summary
- reviewed transaction export
- fund pool spent / Pool remaining
- budget target actuals
- dashboard category spend chart
- analyst pack summaries
- monthly close bundle summaries

## UI (Mockup Screen)

Mockup reference: `planning/mockups/v1_1/index.html`, Screen D.

Split editor behavior:

- Launch from Review and Transactions.
- Show imported fact as read-only: date, source, merchant, and amount.
- Show editable allocation rows with amount, category, optional pool/goal/target, and note.
- Show Transaction amount, Allocated, Remainder, and balanced/unbalanced status.
- Disable Save split until the remainder is zero and all required fields validate.
- Audit preview must state that the imported row remains unchanged and linked.
- Save creates one split decision event with line count and before/after allocation state.

The editor can start as a contextual panel/screen following existing `ReviewScreen` and `TransactionsScreen` patterns before becoming a reusable modal.

## Test Plan

Backend unit tests:

- Balanced split save succeeds and replaces prior active lines according to A1 versioning.
- Unbalanced split save fails with `allocation_total_mismatch`.
- Empty lines and zero-value lines fail validation.
- Allocation category and fund pool references must exist.
- Decision event records actor context and before/after lines.
- Receipt promotion endpoint requires explicit confirmation and receipt linkage.

Reporting tests:

- Category rollup uses splits when present.
- Fund pool remaining uses split allocation amounts.
- Unsplitted transactions preserve current category rollup behavior.
- Receipt lines without splits do not affect totals.
- Split and receipt coexistence produces reconciliation hints but no auto-merge.

Frontend tests:

- Split editor renders selected transaction fact read-only.
- Add/remove allocation line updates remainder.
- Save is disabled while unbalanced.
- Successful save refreshes Transactions, Review, Reports, Funds, and Dashboard queries as needed.

Human QA:

- With synthetic mixed-basket transactions, create a balanced split and confirm category and pool totals change.
- Add receipt lines to the same transaction and verify D11 precedence labels and hints.

## Dependencies on A1/A2/A3

- A1: final `transaction_allocations` schema, balance constraints, and migration strategy.
- A2: spendable and funds calculations consume allocation-aware outflows.
- A3: permissions for review decisions, split saves, and suggestion/approval behavior.
- B1: fund pool and budget target references must exist before allocation lines can point to them.
- D1: receipt promotion depends on this split API.

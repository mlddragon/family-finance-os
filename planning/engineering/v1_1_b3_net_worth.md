# v1.1 B3 Net Worth Engineering Plan

Status: Draft  
Build phase: Phase 2  
Schema source: `planning/engineering/v1_1_a1_schema.md` controls the table names and field contracts for this track.

## Purpose

Implement manual net worth snapshots with CSV import so the product can track actual balances and clearly labeled estimates without feeding estimates into Spendable balance.

D6 is the controlling decision:

- Manual snapshots support `valuation_method`: `actual` or `estimate`.
- Estimates require confidence, as-of date, and notes/source.
- Dashboard net worth defaults to actual balances only.
- Include estimates toggle shows a secondary series and warning banner.
- Estimates never feed Spendable balance.
- Analyst pack includes both views with `includes_estimates` flag.

## Non-goals

- Do not connect to financial institutions.
- Do not scrape account balances.
- Do not infer home, vehicle, retirement, or debt estimates automatically.
- Do not include account numbers or full identifiers.
- Do not treat estimated assets as liquid cash or spendable reserves.

## Schema/API

### Tables

Expected A1 table:

- `net_worth_snapshots`

Required fields or equivalents:

- `id`
- `snapshot_date`
- `asset_or_liability` - controlled values `asset` or `liability`
- `account_name`
- `institution`
- `category`
- `subcategory`
- `balance`
- `valuation_method` - `actual` or `estimate`
- `confidence`
- `source_notes`
- `include_in_actual_net_worth`
- import/source metadata where the implementation links CSV jobs or source files
- audit metadata

Validation:

- `balance` must be numeric. Use the A1-recommended positive amount convention, with `asset_or_liability` determining rollup sign.
- `valuation_method=estimate` requires `confidence`, `snapshot_date`, and `source_notes`.
- `valuation_method=actual` should allow source notes but not require estimate confidence.
- Snapshot dates must be valid ISO dates.
- CSV imports must reject account numbers or columns outside the allowed contract if A1 defines a strict allowlist.

### CSV Import

Input columns:

- `snapshot_date`
- `asset_or_liability`
- `account_name`
- `institution`
- `category`
- `subcategory`
- `balance`
- `valuation_method`
- `confidence`
- `source_notes`

CSV import follows existing upload/import patterns:

- Store uploaded files under external `DATA_ROOT`.
- Create an import batch or net-worth import job.
- Validate before accepting rows.
- Use synthetic fixtures only in tests.

### API Shape

Proposed endpoints:

- `GET /api/net-worth/snapshots?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `POST /api/net-worth/snapshots`
- `PATCH /api/net-worth/snapshots/{snapshot_id}`
- `POST /api/net-worth/imports`
- `POST /api/net-worth/imports/{import_id}/accept`
- `GET /api/net-worth/summary?from=YYYY-MM-DD&to=YYYY-MM-DD&include_estimates=false`

Summary response:

```json
{
  "include_estimates": false,
  "latest_snapshot_date": "2026-06-30",
  "actual": {
    "assets": "184250.00",
    "liabilities": "0.00",
    "net_worth": "184250.00"
  },
  "with_estimates": {
    "assets": "262400.00",
    "liabilities": "0.00",
    "net_worth": "262400.00",
    "includes_estimates": true
  },
  "series": []
}
```

### Decision Events

Create decision events for:

- Manual snapshot create/update/delete.
- CSV import acceptance or voiding.
- Estimate inclusion setting changes, if persisted.

## UI (Mockup Screen)

Mockup reference: `planning/mockups/v1_1/index.html`, Dashboard net worth tile in Screen C.

Initial UI surfaces:

- Net worth tile on Dashboard with "Actual net worth" default.
- Secondary "With estimates" metric.
- Confidence metric, for example `Confidence: Mixed`, with subtext "Estimates never feed Spendable balance".
- Toggle: "Include estimates (home, vehicle, other)".
- Warning banner when estimates are shown.
- Entry/import surface can live under Dashboard or Reports until a dedicated Net Worth screen is approved.
- Manual-entry and CSV-import surfaces do not have an approved mockup yet. Add a lightweight wireframe before the B3 UI PR. Backend/API work is unblocked.

Manual entry form:

- Date, asset/liability, account display name, institution, category, balance, valuation method.
- Estimate-specific fields become required when valuation method is `estimate`.
- Do not collect account numbers.

CSV import UI:

- Upload CSV.
- Show validation result, rejected rows, and accepted count.
- Require accept action before rows affect summaries.

## Test Plan

Backend unit tests:

- Actual snapshot saves with required base fields.
- Estimate snapshot rejects missing confidence, as-of date, or source note.
- Summary excludes estimates by default.
- Summary includes estimates only when requested and sets `includes_estimates=true`.
- Spendable engine ignores all net worth estimates and non-liquid asset snapshots.
- CSV import rejects invalid dates, invalid valuation methods, and missing estimate metadata.

API tests:

- Snapshot and import routes require configured permissions.
- Import accept produces deterministic rows from synthetic CSV fixtures.
- Error responses use stable `detail.code` values.

Frontend tests:

- Dashboard defaults to actual net worth.
- Include-estimates toggle shows warning banner and secondary series.
- Manual form enforces estimate fields.
- CSV import preview shows validation failures without accepting rows.

Human QA:

- Import a synthetic CSV with one actual cash account, one actual liability, and one estimated vehicle value.
- Verify actual-only and with-estimates totals differ.
- Verify Spendable balance is unchanged by the estimated vehicle value.

## Dependencies on A1/A2/A3

- A1: final snapshot table names, import job linkage, allowed enums, and constraints.
- A2: spendable engine must explicitly ignore estimates.
- A3: permissions and actor audit context for snapshot entry/import.
- B4: analyst pack includes actual-only and with-estimates views.
- C1: Dashboard consumes the summary endpoint and estimate warning labels.

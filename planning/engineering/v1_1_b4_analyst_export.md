# v1.1 B4 Analyst Export Engineering Plan

Status: Draft  
Build phase: Phase 2  
Schema source: `planning/engineering/v1_1_a1_schema.md` defines no dedicated analyst-pack table. Use the existing local job/artifact pattern unless a later approved schema doc changes it.

## Purpose

Replace the v1 advisor export concept with an explicit local analyst pack bundle that the owner can generate and decide where to use. The app must not call AI services or transmit financial data.

The analyst pack should gather reviewed summaries, funds, cashflow, net worth views, validation/confidence notes, and optional raw transaction rows into a reproducible local bundle under `DATA_ROOT`.

## Non-goals

- No in-app AI.
- No provider calls, model calls, hosted analysis, embeddings, sync, or upload.
- No account numbers or credentials in the bundle.
- No raw transaction rows by default.
- No auto-scheduled recurring exports in the first pass; recurring detection is a local heuristic only.

## Schema/API

### Tables and Artifacts

Use existing `jobs` and `artifacts` patterns from `reporting.py`, with a new report/export type:

- `job_type = "analyst_pack_export"`
- `artifact_type = "analyst_pack_manifest"`
- `artifact_type = "analyst_pack_summary"`
- `artifact_type = "analyst_pack_prompt"`
- optional `artifact_type = "analyst_pack_transactions_export"`

Artifacts plus job output are sufficient for v1.1.

### Bundle Schema

Recommended directory:

`DATA_ROOT/exports/analyst_pack/{job_id}/`

Files:

- `manifest.json`
- `summary.json`
- `summary.md`
- `prompts/{prompt_key}.md`
- optional `reviewed_transactions.csv`

`manifest.json`:

```json
{
  "schema_version": "v1.1",
  "pack_type": "analyst_pack",
  "month": "2026-06",
  "generated_at": "2026-06-30T12:00:00Z",
  "includes_raw_transactions": false,
  "includes_estimates": false,
  "artifacts": [],
  "validation_summary": {},
  "privacy_boundary": "local_file_only_no_in_app_ai"
}
```

`summary.json` sections:

- period metadata and confidence/provisional labels
- cashflow summary
- category spending totals
- fund pool commitments and Pool remaining
- Reserved goal balance
- net worth actual-only and with-estimates views
- review backlog
- recurring heuristic findings
- validation and source freshness notes

### Prompt Library Files

Store prompt templates in source control because they contain no financial data:

- `apps/api/family_finance_os/prompt_library/monthly_spending_review.md`
- `apps/api/family_finance_os/prompt_library/cashflow_savings_rate.md`
- `apps/api/family_finance_os/prompt_library/goal_progress_check_in.md`

Prompt templates must instruct the external analyst not to infer beyond provided data and to respect provisional labels. The UI copies prompt text but does not send it anywhere.

### Recurring Heuristic

The export can include a local heuristic summary for likely recurring transactions:

- Group by normalized merchant, amount band, direction, and monthly cadence.
- Require at least three occurrences unless settings define a lower threshold.
- Mark as `candidate`, never confirmed.
- Exclude transfers unless reviewed as recurring bills/income.
- Include `confidence`, `reason`, and source transaction ids only when raw rows are enabled; otherwise include aggregate counts and date range.

### API Shape

Proposed endpoints:

- `GET /api/analyst-pack/options?month=YYYY-MM`
- `POST /api/analyst-pack/build`
- `GET /api/analyst-pack/prompts`
- `GET /api/artifacts/{artifact_id}/download` remains the download path

Build request:

```json
{
  "actor": "owner",
  "actor_context": {},
  "month": "2026-06",
  "include_raw_transactions": false,
  "include_estimates": false,
  "prompt_key": "cashflow_savings_rate"
}
```

Error codes:

- `analyst_pack_invalid_option`
- `analyst_pack_prompt_not_found`
- `analyst_pack_artifact_unsafe`
- `analyst_pack_permission_denied`

## UI (Mockup Screen)

Mockup reference: `planning/mockups/v1_1/index.html`, Screen G.

Reports / Analyst export surface:

- "Build export pack" primary action.
- Checklist of included sections.
- Add a net worth checklist row for actual net worth, with an include-estimates control that drives `include_estimates` in the build request. Screen G's approved checklist omits this row, so extend the mockup before the B4 UI PR.
- Raw transaction rows unchecked by default and clearly marked as line-level detail.
- Account numbers/balances marked as never included where applicable.
- Privacy boundary panel: local generation, no AI or external service call.
- Prompt picker with monthly spending review, cashflow and savings-rate analysis, goal progress check-in, and custom.
- Prompt preview and "Copy prompt".
- Preview pack and Export pack buttons.
- Estimate-toggle copy must match B3/D6: actual net worth is the default, estimates are optional, and estimates never feed Spendable balance.

Use existing `ReportsScreen` patterns for artifacts, report runs, monthly close, and export permissions.

## Test Plan

Backend unit tests:

- Bundle path is always inside `DATA_ROOT`.
- Manifest includes privacy boundary and selected options.
- Raw transaction export is excluded by default.
- Include-estimates option sets `includes_estimates=true` and includes both net worth views.
- Prompt lookup rejects unknown prompt keys.
- Recurring heuristic marks candidates but does not mutate transactions.

API tests:

- Build route requires export permission.
- Generated artifacts register sha256 and byte size.
- Artifact download rejects paths outside `DATA_ROOT` and integrity mismatches.

Frontend tests:

- Raw transaction checkbox defaults off.
- Privacy boundary text is visible.
- Prompt picker changes preview.
- Copy prompt action copies only prompt text, not data.
- Build action refreshes artifact list.

Human QA:

- Generate a synthetic pack with default options and inspect manifest, summary, and prompt files.
- Repeat with raw transactions enabled and confirm the UI makes the sensitivity obvious.
- Confirm no network calls are made as part of pack build or prompt copy.

## Dependencies on A1/A2/A3

- A1: final artifact/job schema or dedicated analyst pack table.
- A2: spendable and funds summaries included in pack.
- A3: export permission and actor/session context.
- B1/B2/B3: funds, splits, and net worth sections must be allocation-aware and estimate-aware.
- C1: dashboard chart endpoint logic can share summary builders with the pack.

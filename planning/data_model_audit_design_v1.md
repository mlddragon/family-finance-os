# Data Model And Audit Design v1

This document captures approved data model and audit design direction for the first Dillon Finances implementation planning cycle. It is a planning artifact only. It does not create a database schema, add code, add dependencies, or migrate financial data.

## Status

- Data model design direction approved by owner.
- Exact schema has not been designed.
- App implementation has not started.
- No financial data has been migrated.
- This document should guide the later schema and implementation plan.

## Design Goal

The v1 data model must prove that household financial data can move through the closed loop without hidden mutation, double-counting, fake precision, or unreviewed decisions becoming facts.

The model must keep these concepts separate:

- Evidence.
- Imported operational state.
- Human decisions.
- Derived views and outputs.

## Decision 1: Four-Layer Model

Approved direction: four-layer data model.

### Layer 1: Evidence Layer

Original proof of source data.

Stored on disk under `DATA_ROOT`, outside git:

- `inbox/`
- `raw/`
- `processed/`
- `quarantine/`

Stored in SQLite as metadata:

- Source file records.
- File paths.
- File hashes.
- Original filenames.
- Import batch links.
- Validation status.
- Parser/version references.

Raw bank exports remain evidence and are never rewritten.

### Layer 2: Operational State Layer

The app's normalized working memory.

Stored in SQLite:

- Sources and accounts.
- Import batches.
- Source file records.
- Imported row identities.
- Canonical ledger transactions.
- Validation results.
- Jobs.
- Settings.
- Artifact records.

Normalized ledger facts remain imported facts, not final owner-approved reviewed truth.

### Layer 3: Decision/Event Layer

Human judgment and controlled changes.

Stored in SQLite as append-only events:

- Owner classification decisions.
- Review status decisions.
- Settings changes.
- Future rollback/supersede decisions.
- Future AI-suggested proposals after approval gates.

Events are never edited. Corrections create new events.

### Layer 4: Derived/Output Layer

Views and artifacts generated from evidence, operational state, and decision events.

Examples:

- Reviewed/current transaction view.
- Review queues.
- Reports.
- Monthly close bundles.
- Advisor-ready exports.
- Settings snapshots.

Derived outputs can be regenerated unless they are finalized monthly close artifacts.

## Decision 2: Raw Files And Import Evidence

Approved direction: raw files on disk, immutable metadata and hashes in SQLite.

Lifecycle:

1. New files land in `DATA_ROOT/inbox/`.
2. Files that fail or need owner attention move or copy to `DATA_ROOT/quarantine/`.
3. Successfully imported raw files are preserved under:

```text
DATA_ROOT/raw/{source}/{YYYY}/{import_batch_id}/
```

SQLite source file record should capture:

- Original filename.
- Stored path.
- Source type.
- File hash.
- Byte size.
- Detected account/source.
- Import batch id.
- Received timestamp.
- Imported timestamp.
- Validation status.
- Row count.
- Parser/version used.

Rules:

- Raw files are not stored in git.
- Raw files are not mutated.
- SQLite stores file metadata and references, not raw file blobs as the primary state.

Serious alternatives considered:

- Store raw file blobs inside SQLite: stronger self-containment, but larger database, harder manual inspection, worse fit for NAS backups.
- Store only file paths without hashes: simpler, but weak auditability.

## Decision 3: Jobs And Import Batches

Approved direction: separate job records from import batch records.

### Job Records

Jobs track backend operations the app performs.

Examples:

- Import detection.
- Validation.
- Import.
- Report generation.
- Monthly close.
- Export.
- Future enrichment.

Job record should capture:

- Job type.
- Status.
- Started timestamp.
- Finished timestamp.
- Actor.
- Input artifact references.
- Output artifact references.
- Error summary.
- Logs path.
- Retry/root job link if applicable.

### Import Batch Records

Import batches track coherent accepted financial import events.

Import batch record should capture:

- Batch id.
- Source scope.
- Statement/export period if known.
- Received timestamp.
- Imported timestamp.
- Source file ids.
- Validation status.
- Row counts.
- Transaction date min/max.
- Parser/version.
- Supersedes/superseded-by link if reimported.

Rules:

- A job can create or update an import batch.
- A job is not itself an import batch.
- Report jobs may use import batches without becoming part of them.

## Decision 4: Normalized Ledger Transactions

Approved direction: normalized ledger transactions are immutable imported facts after successful import.

Normalized ledger facts should capture:

- Stable transaction id.
- Source account id.
- Import batch id.
- Source file id.
- Source row number.
- Posted date.
- Authorized/effective date when available.
- Raw description.
- Normalized merchant.
- Amount.
- Direction.
- Balance if available.
- Initial category suggestion.
- Initial subcategory suggestion.
- Initial review flags/reasons.
- Transfer candidate flag.
- Reimbursement candidate flag.
- Medical/tax candidate flag.
- Project candidate flag.
- Side-hustle candidate flag.
- Import parser/version.
- Created timestamp.

Rules:

- Do not edit normalized ledger rows for human review.
- Do not overwrite imported rows on reimport.
- If an import needs correction, create a new import batch/version and link superseded records.
- Human classification decisions live in decision events.
- Reports use derived reviewed state, not mutated imported rows.

## Decision 5: Transaction Identity And Reimport Behavior

Approved direction: two transaction identities.

### Imported Row Identity

A deterministic id for the exact imported row from a specific source file/import batch.

Example basis:

- Source account.
- Source file hash.
- Source row number.
- Normalized raw row hash.

Purpose:

- Prove exact evidence.
- Preserve overlapping imports.
- Trace file and row provenance.

### Canonical Transaction Identity

A stable transaction id representing the real-world ledger transaction across imports.

Example basis:

- Account.
- Posted date.
- Amount.
- Source-provided id if available.
- Description fingerprint.
- Collision checks.

Purpose:

- Prevent duplicate spending when overlapping exports are imported.
- Drive reports.
- Attach decisions to the real transaction.

Rules:

- Imported rows prove evidence.
- Canonical transactions drive reporting.
- Duplicate/overlap detection links imported rows to the same canonical transaction.
- Ambiguous matches go to validation review, not silent merge.

## Decision 6: Decision Events

Approved direction: append-only decision event model for owner-approved classification changes.

Decision event should capture:

- Event id.
- Target type: transaction, source, setting, report, etc.
- Target id.
- Decision type.
- Field changed.
- Previous value.
- Proposed value.
- Approved value.
- Actor.
- Reason/notes.
- Source of suggestion: user, rule, AI, import heuristic.
- Created timestamp.
- Supersedes/reverts event id if applicable.

Supported v1 decision types may include:

- Category change.
- Subcategory change.
- Review status change.
- Review reason change.
- Transfer flag/status.
- Reimbursement candidate/status.
- Medical/tax candidate/status.
- Project candidate flag.
- Side-hustle candidate flag.

Rules:

- Events are never edited.
- Corrections are new events.
- Rollback is a new event that reverts or supersedes a prior event.
- Current reviewed state is derived by applying active/latest decision events over canonical transactions.
- Decision events export as CSV/JSON plus Markdown summary.

## Decision 7: Validation Results

Approved direction: validation results are first-class records.

Validation can attach to:

- Source files.
- Import batches.
- Imported rows.
- Canonical transactions.
- Jobs.
- Report runs.
- Monthly close bundles.

Each validation finding should capture:

- Severity: info, warning, blocking.
- Stable machine-readable validation code.
- Human-readable message.
- Target type.
- Target id.
- Detected timestamp.
- Status: open, acknowledged, resolved, ignored.
- Resolution event/link where applicable.

Rules:

- Blocking validation failures prevent import acceptance or report/monthly close readiness.
- Warnings can allow progress but mark reports provisional.
- Every report/monthly close records the validation state it relied on.
- Stale, missing, duplicate, and schema issues should be visible in the UI.

## Decision 8: Settings And Config Audit

Approved direction: settings changes are controlled, validated, and auditable.

Active settings live in SQLite and are edited through the Settings UI.

Settings domains:

- Source definitions.
- Account metadata.
- Category taxonomy.
- Review thresholds.
- Freshness thresholds.
- Import parser settings.
- Report settings.
- Local/network mode.
- Future vendor plugin settings.

Each settings change should create an append-only settings event:

- Setting key/domain.
- Previous value.
- New value.
- Actor.
- Reason/notes.
- Validation result.
- Timestamp.
- Supersedes/reverts event id if applicable.

Settings exports:

- Current settings snapshot as JSON/YAML.
- Settings change log as CSV/JSON.
- Human-readable Markdown summary for monthly close or major changes.

## Decision 9: Derived State And Materialization

Approved direction: derived views by default, materialized snapshots where useful.

For live UI:

- Compute reviewed/current transaction state from canonical transactions plus decision events.
- Use database views or query-layer composition.
- Do not store duplicate current transaction rows unless performance requires it.

For monthly close:

- Create immutable snapshots/artifacts:
  - Reviewed transaction export for that close.
  - Validation state summary.
  - Report outputs.
  - Decision event export.
  - Settings snapshot.
  - Advisor-ready bundle.

Rules:

- Avoid duplicated live state drifting out of sync.
- Monthly close snapshots preserve historical reporting state.
- Past reports should remain reproducible even if settings or decisions later change.

## Decision 10: Monthly Close Bundle

Approved direction: each monthly close bundle gets both a SQLite record and a filesystem artifact folder.

SQLite close record should capture:

- Close id.
- Month.
- Status.
- Created timestamp.
- Actor.
- Source import batches included.
- Validation state summary.
- Report run ids.
- Settings snapshot id.
- Decision export id.
- Artifact folder path.
- Provisional/final status.
- Notes.

Filesystem folder:

```text
DATA_ROOT/monthly_close/YYYY-MM/
  validation_summary.md
  validation_findings.csv
  cashflow_summary.csv
  category_spending_summary.csv
  review_backlog_summary.csv
  top_merchants_sources.csv
  monthly_close_memo.md
  reviewed_transactions.csv
  decision_events.csv
  settings_snapshot.json
  advisor_export/
```

Rules:

- Monthly close bundles are immutable after finalization.
- Corrections create a revised close version, not silent edits.
- Reports clearly state whether the close is provisional or final.

## Decision 11: Artifact Registry

Approved direction: generated files stay on disk, while SQLite stores artifact metadata.

Artifact record should capture:

- Artifact id.
- Artifact type: report, export, validation summary, monthly close file, log, advisor bundle, etc.
- Path.
- Hash.
- Byte size.
- Created timestamp.
- Producing job id.
- Source inputs or dependency ids.
- Retention category.
- Sensitive-data classification.
- Human-readable title/description.

Purpose:

- The filesystem holds the files.
- SQLite knows what the files are.
- The UI can show Reports and Monthly Close artifacts without guessing from folders.
- Artifact lineage can be audited.

## Transaction Retrieval In The UI

When the UI retrieves transaction data, it should request a reviewed/current view rather than reading raw ledger rows directly.

Expected flow:

1. UI asks backend for transactions matching filters.
2. Backend queries canonical transactions.
3. Backend joins/imports evidence metadata where needed.
4. Backend applies active/latest decision events.
5. Backend returns current reviewed fields alongside original imported facts.
6. Detail views can show source file reference, imported row provenance, validation findings, and decision history.

Example response shape, not an implementation contract:

```json
{
  "transaction_id": "txn_123",
  "posted_date": "2026-03-14",
  "merchant": "Walgreens",
  "amount": -42.18,
  "category_current": "Medical",
  "category_original": "Uncategorized",
  "review_status": "approved",
  "source": "Chase Prime Visa",
  "source_file": "chase_march.csv",
  "decision_history_count": 1
}
```

The UI should make it possible to inspect:

- Imported facts.
- Current reviewed values.
- Validation status.
- Source file reference.
- Decision history.
- Rollback option where allowed.

## Performance And Scale Posture

The approved model is expected to be lightweight for household financial data.

Expected data size:

- Years of bank/card transactions should remain small by SQLite standards.
- Review events should remain small even with several decisions per transaction.
- Vendor item detail later may grow faster, but should remain separate from the v1 ledger core.

Performance approach:

- Index posted date, source account, canonical transaction id, imported row id, review/status fields, and common filter fields.
- Use views/query composition for reviewed state.
- Generate reports as jobs, not on every page load.
- Use immutable monthly close artifacts for historical snapshots.
- Add materialized current-state tables only if measured performance requires them.
- Consider DuckDB later for heavy analytics if SQLite reporting becomes constrained.

## Deferred Schema Decisions

The following are intentionally deferred to implementation planning:

- Exact table names.
- Exact column names.
- Exact indexes.
- Exact SQLite migration tooling.
- Exact transaction identity hash algorithm.
- Exact validation code taxonomy.
- Exact category taxonomy schema.
- Exact settings schema.
- Exact artifact retention categories.
- Exact sensitive-data classification values.
- Exact export file schemas.

## Required Gates Before Implementation

Before implementation planning starts, these gates apply:

- Completed: UI mockups for v1 screens have been approved in `planning/ui_mockups_v1.md`.
- Completed: Alliant/Chase import validation contract has been approved in `planning/import_validation_contract_v1.md`.
- Completed: initial category taxonomy/settings scope has been approved in `planning/settings_config_audit_design_v1.md`.
- Completed: report artifact structure details have been approved in `planning/report_monthly_close_artifacts_v1.md`.
- Completed: test and validation strategy has been approved in `planning/test_validation_strategy_v1.md`.
- Completed: controlled decision event model has been approved in `planning/controlled_decision_event_model_v1.md`.
- Drafted for review: v1 implementation plan has been captured in `planning/v1_implementation_plan.md`.

## Next Recommended Work

The next planning work should be one of:

1. Owner review of `planning/v1_implementation_plan.md`.
2. App implementation after the implementation plan is approved and merged.

# Dillon Finances v1 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for implementation milestones when available. Execute one milestone PR at a time. Do not begin app code until this implementation plan is approved and merged.

**Goal:** Build the first local Docker MVP for Dillon Finances that proves the full household finance closed loop with synthetic data first.

**Architecture:** Single-container Docker Compose app for v1. FastAPI serves backend APIs and the compiled React UI from one container, with SQLite and generated artifacts stored under an external `DATA_ROOT` mounted outside git. The app is local-first, binds to `127.0.0.1` by default, and uses append-only events for controlled owner decisions and settings changes.

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Alembic, SQLite, React, TypeScript, Vite, TanStack Query, TanStack Table, pytest, Vitest, Playwright, Docker Compose, GitHub Actions.

---

## Non-Negotiable Boundaries

- No real financial data, raw exports, normalized rows, generated reports, database files, credentials, cookies, browser sessions, API keys, or AI transcripts with transaction detail in git.
- No live AI/API integration in v1.
- No bank aggregators, stored credentials, browser automation, PDF parsing, vendor enrichment, transaction splits, delete/ignore decisions, LAN/NAS exposure, authentication, or local LLM integration in v1.
- Every milestone lands through a branch and PR.
- `main` remains deployable enough to run existing checks after every merge.
- Owner approval is required before using real local exports for smoke validation.
- Header-only or sanitized source samples are required before parser acceptance tests are considered final.

## Runtime Defaults

- Local repository: `/Users/masondillon/GitHub/Dillon_Finances`.
- **Production default (Decision 16 / #108):** host `DATA_ROOT` under the public user directory; installer chooses profile or custom local/UNC path.
- **Dev/Compose interim:** host data directory `~/Dillon_Finances_Data` (personal) and `~/Dillon_Finances_QA_Data` (QA) via env/compose overrides until installer ships.
- Container data mount: `/data`.
- App port: host `127.0.0.1:8080` to container `8080`.
- Default `DATA_ROOT`: `/data`.
- SQLite path: `/data/database/family_finance_os.sqlite3`.
- App actor for v1 audit records: `mason`.
- Container user: non-root UID/GID `10001:10001`.

`DATA_ROOT` must contain:

```text
inbox/
raw/
processed/
quarantine/
database/
reports/
monthly_close/
exports/
logs/
```

The app must refuse startup if `DATA_ROOT` resolves inside the git repository.

**User file I/O (Decision 16, owner 2026-06-30):** User imports and exports go through the UI into `DATA_ROOT`. App-internal assets ship in the image. QA runtime fixtures are materialized by `make qa-seed`. Backport: [#107](https://github.com/mlddragon/family-finance-os/issues/107).

## Milestone PR Sequence

### PR 1: Implementation Plan

Purpose: record this plan before app code starts.

Files:

- Create `planning/v1_implementation_plan.md`.

Required checks:

- Placeholder scan on this document and changed planning pointers.
- Sensitive artifact scan.
- Confirm no app code, schema, dependencies, generated artifacts, or financial data were added.

Owner checkpoint:

- Owner reviews and approves this plan PR.
- App code starts only after this PR is merged.

### PR 2: Scaffold, Docker, And Repository Safety

Purpose: establish the runnable project shell and safety checks without implementing finance workflows.

Create structure:

```text
apps/
  api/
    family_finance_os/
      __init__.py
      main.py
  web/
    src/
tests/
  api/
  web/
  e2e/
  fixtures/
    synthetic/
scripts/
docker/
.github/
  workflows/
```

Implementation requirements:

- Add Python project metadata for API package and test tooling.
- Add Vite React TypeScript project for the UI.
- Add one Dockerfile that builds the React app and runs the FastAPI app.
- Add `docker-compose.yml` with `127.0.0.1:8080:8080`, `DATA_ROOT=/data`, and `~/Dillon_Finances_Data:/data`.
- Add `/api/health` returning app name, version, data-root status, local-only status, and database availability status.
- Add a static UI shell served by FastAPI after build.
- Add `scripts/check_sensitive_artifacts.py` to fail on blocked artifact patterns unless explicitly allowlisted synthetic docs are used.
- Add GitHub Actions for synthetic-only checks.

Tests:

- `pytest` passes with an API health test.
- `npm test` or `vitest` passes with a basic UI render test.
- Sensitive artifact script passes.
- Docker build succeeds.
- `docker compose up` serves health and the UI at `127.0.0.1:8080`.

Acceptance:

- No financial workflow is implemented yet.
- No database schema is created beyond health/startup support if needed.
- No secrets or real data are present.

### PR 3: SQLite Foundation And Audit Core

Purpose: create durable local state and audit foundations.

Implementation requirements:

- Add SQLite connection management and Alembic migrations.
- Add startup directory bootstrap for required `DATA_ROOT` folders.
- Add startup guard for `DATA_ROOT` inside the repo.
- Add SQLAlchemy models and migrations for:
  - `sources`
  - `source_accounts`
  - `source_files`
  - `import_batches`
  - `imported_rows`
  - `canonical_transactions`
  - `validation_findings`
  - `settings`
  - `settings_events`
  - `decision_events`
  - `jobs`
  - `report_runs`
  - `artifacts`
  - `monthly_closes`
- Use UUID-style text ids for externally referenced records.
- Store created/updated timestamps in UTC ISO format.
- Keep imported row facts immutable after accepted import.
- Add a lightweight job recorder for import, validation, report, close, and export jobs.

Tests:

- Migration upgrade creates every table on a temporary SQLite database.
- Startup guard rejects a `DATA_ROOT` inside the repo.
- Startup bootstrap creates required folders in a temporary data root.
- Models can insert and query a source, source file, import batch, validation finding, setting, decision event, job, report run, artifact, and close record.
- Sensitive artifact scan still passes.

Acceptance:

- SQLite file is created only under test temp dirs or external `DATA_ROOT`.
- No runtime database file is committed.

### PR 4: Settings And Source Profiles

Purpose: make settings first-class and define v1 source profiles.

Implementation requirements:

- Seed default settings in SQLite on first startup.
- Add settings API:
  - `GET /api/settings`
  - `PATCH /api/settings`
- Settings changes create append-only settings events.
- Add settings validation for freshness thresholds, source metadata, and `DATA_ROOT` safety.
- Add source profile registry for:
  - Alliant Checking
  - Alliant Savings
  - Alliant Credit Card
  - Chase Prime Visa
- Source profile fields:
  - source key
  - display name
  - account type
  - required flag
  - freshness threshold days
  - accepted file extensions
  - expected headers
  - amount sign policy
  - parser version
- Add Settings UI page with tabs for Data root, Sources, Thresholds, Reports, Privacy, and Future integrations.
- Show local-only mode and `DATA_ROOT` status in the global header.

Owner checkpoint:

- Owner provides header-only or sanitized source examples before parser acceptance tests are finalized.
- If exact Alliant headers differ from synthetic assumptions, update source profile tests before parser implementation proceeds.

Tests:

- Settings read and patch APIs work.
- Settings events are append-only.
- High-impact settings require notes.
- Invalid freshness thresholds are rejected.
- `DATA_ROOT` inside repo is rejected.
- Source profile registry recognizes approved source keys.
- Settings UI renders and shows local-only status.

Acceptance:

- Settings are active SQLite-backed product state.
- JSON/YAML/CSV are not active household config.

### PR 5: Import, Validation, And Quarantine

Purpose: safely detect, validate, accept, or quarantine v1 ledger exports.

Implementation requirements:

- Add APIs:
  - `GET /api/status`
  - `GET /api/inbox/scan`
  - `POST /api/inbox/scan`
  - `POST /api/uploads`
  - `POST /api/import-batches/{id}/validate`
  - `POST /api/import-batches/{id}/accept`
  - `GET /api/validation-findings`
- Uploads and inbox scans create source file records.
- Validation creates first-class findings with severity: info, warning, blocking.
- Accepted warnings require explicit acknowledgment.
- Blocking findings prevent batch acceptance.
- Accepted files are preserved under `DATA_ROOT/raw/{source}/{YYYY}/{import_batch_id}/`.
- Blocked files move or copy to `DATA_ROOT/quarantine/` with reason metadata.
- Supported v1 import files are CSV-like ledger exports only.
- Reject XLS/XLSX, PDF, credential/session files, and unsupported extensions.

Validation codes must cover:

- `file_missing`
- `file_unreadable`
- `file_empty`
- `unsupported_file_type`
- `schema_mismatch`
- `ambiguous_source`
- `source_account_unconfirmed`
- `date_parse_failed`
- `amount_parse_failed`
- `amount_precision_invalid`
- `amount_sign_unexpected`
- `row_count_mismatch`
- `duplicate_imported_row`
- `duplicate_canonical_candidate`
- `overlapping_export`
- `source_stale`
- `required_source_missing`
- `batch_validation_incomplete`

Tests:

- Synthetic valid file validates cleanly.
- Missing, empty, unsupported, malformed date, malformed amount, wrong header, stale source, duplicate, and overlap cases produce expected findings.
- Warnings require acknowledgment.
- Blocking findings prevent acceptance.
- Quarantine flow writes only under temp `DATA_ROOT`.
- Source files are hashed and stored with metadata.
- No raw data fixtures are real.

Acceptance:

- Import validation can be demonstrated entirely with synthetic data.
- No silent dedupe exists.

### PR 6: Normalization And Ledger Identity

Purpose: turn accepted source rows into immutable ledger facts and canonical transactions.

Implementation requirements:

- Add parser services for v1 source profiles.
- Normalize accepted rows into imported ledger facts.
- Compute imported row identity from source account, source file hash, source row number, and normalized row hash.
- Compute canonical transaction identity from account, posted date, amount, source transaction id when available, and description fingerprint.
- Preserve overlapping imports as evidence.
- Link imported rows to canonical transactions.
- Ambiguous canonical matches create blocking validation findings instead of silent merge.
- Add transaction APIs:
  - `GET /api/transactions`
  - `GET /api/transactions/{id}`

Tests:

- Imported row id is deterministic.
- Canonical id is deterministic for duplicate real-world transaction candidates.
- Reimport does not overwrite imported rows.
- Ambiguous duplicate blocks controlled review.
- Transaction API returns reviewed/current view with original imported facts and validation status.

Acceptance:

- Synthetic files can be accepted and normalized into SQLite.
- Reports can later use canonical transactions without double-counting.

### PR 7: Controlled Decision Events

Purpose: implement the first controlled write path.

Implementation requirements:

- Add `POST /api/decision-events`.
- Support decision types:
  - category change
  - subcategory change
  - review status change
  - review reason change
  - transfer flag/status
  - reimbursement candidate/status
  - medical/tax candidate/status
  - project candidate flag
  - side-hustle candidate flag
- Attach ledger decisions to canonical transactions only.
- Validate target existence, non-ambiguous canonical identity, allowed field, controlled value, category/subcategory pairing, conflicts, required notes, and explicit user action.
- Routine category notes are optional.
- High-impact notes are required.
- Corrections and rollbacks create new superseding or revert events.
- Current reviewed state derives from canonical transactions plus active/latest events.
- Suggestions from rules/Codex/future AI remain proposals until owner save.

UI requirements:

- Ledger Review page shows imported fact, current derived state, proposed decision, validation status, and audit preview.
- Save is disabled for ambiguous identity, out-of-scope fields, missing required note, or blocking validation.
- Transaction detail shows decision history.

Tests:

- Decision event insert is append-only.
- Imported facts do not change.
- Current reviewed state reflects active latest events.
- Supersede/revert behavior works.
- Required high-impact notes are enforced.
- Suggestions cannot create events without explicit save.
- UI can save one classification decision using synthetic data.

Acceptance:

- Owner can save at least one synthetic classification decision as an append-only event.

### PR 8: Backend API And Operator UI MVP

Purpose: deliver the complete local operator interface around the approved mockups.

Implementation requirements:

- Implement global layout with Home, Sources, Review, Transactions, Reports, Settings.
- Home shows local-only status, latest import status, freshness, validation counts, review counts, monthly close status, and next action.
- Sources shows required sources, inbox files, validation status, quarantine items, and actions.
- Validation Issues shows severity, code, target, message, status, and affected reports.
- Ledger Review supports filters, selected transaction detail, decision proposal, and audit preview.
- Transactions shows reviewed/current transaction view and audit timeline.
- Reports/Monthly Close shows readiness and generated artifact links.
- Settings shows active settings and settings audit history.
- Use TanStack Query for API data fetching and TanStack Table for dense tables.
- Keep UI local-browser focused, dense, and operator-oriented.

Tests:

- API contract tests for all minimum endpoints.
- Vitest component tests for core screens.
- Playwright smoke test for navigation and rendered local-only status.
- Playwright decision-save flow against synthetic seeded data.
- Accessibility smoke checks for labels, focus, and keyboard navigation on core controls.

Acceptance:

- Docker app is usable in a browser at `127.0.0.1:8080`.
- UI does not imply raw facts were overwritten.

### PR 9: Reports, Monthly Close, And Advisor Export

Purpose: complete reporting and close artifacts.

Implementation requirements:

- Add `POST /api/reports/run`.
- Add `POST /api/monthly-close/draft`.
- Add `POST /api/monthly-close/finalize`.
- Add `POST /api/exports/advisor`.
- Generate:
  - import and validation summary
  - cashflow summary
  - category spending summary
  - review backlog summary
  - top merchants/sources
  - monthly close memo
  - reviewed transaction export
  - decision event export
  - settings snapshot
  - advisor summary/export
- Store artifact files under `DATA_ROOT/reports`, `DATA_ROOT/monthly_close`, and `DATA_ROOT/exports`.
- Register every artifact in SQLite with hash, byte size, type, path, producing job, source inputs, validation state, and sensitivity classification.
- Draft close can be provisional.
- Final close is blocked by missing required source coverage, stale required sources, or open blocking validation.
- Every close bundle includes `manifest.json`.

Tests:

- Report calculators produce expected synthetic outputs.
- Reports carry freshness, validation, and provisional status.
- Final close blocked path works.
- Draft close writes manifest and artifacts.
- Final close retains immutable bundle.
- Advisor export is explicit owner action and includes validation state.

Acceptance:

- Synthetic closed loop reaches monthly close draft, final close when eligible, and advisor export.

### PR 10: Hardening, End-To-End Validation, And Owner Smoke Package

Purpose: reduce bugs and security risk before v1 MVP acceptance.

Implementation requirements:

- Add full synthetic happy path test under Docker:
  1. Place synthetic files in inbox.
  2. Validate and accept import batch.
  3. Normalize ledger facts.
  4. Create review queues.
  5. Save one decision event.
  6. Generate reports.
  7. Generate monthly close bundle.
  8. Generate advisor export.
  9. Confirm next refresh prompt/status.
- Add blocked path test for stale/missing/blocking validation.
- Add security checks:
  - app binds to `127.0.0.1` by default
  - no secrets required
  - no live AI/API calls
  - `DATA_ROOT` outside repo
  - no raw data copied into Docker image
  - sensitive artifact scan in CI
- Add local owner smoke checklist for real-data verification that records only sanitized evidence.
- Add README runbook for Docker startup, shutdown, data root reset, backup/export locations, and troubleshooting.

Tests:

- Full backend/unit/integration suite passes.
- Vitest suite passes.
- Playwright suite passes.
- Docker E2E suite passes.
- Sensitive artifact scan passes.
- Manual smoke checklist exists and contains no real data.

Acceptance:

- v1 MVP acceptance criteria are satisfied with synthetic data.
- Owner can perform a local real-data smoke run only after explicit approval.

## Minimum API Surface

Required endpoints by v1:

- `GET /api/health`
- `GET /api/status`
- `GET /api/inbox/scan`
- `POST /api/inbox/scan`
- `POST /api/uploads`
- `POST /api/import-batches/{id}/validate`
- `POST /api/import-batches/{id}/accept`
- `GET /api/validation-findings`
- `GET /api/transactions`
- `GET /api/transactions/{id}`
- `POST /api/decision-events`
- `GET /api/settings`
- `PATCH /api/settings`
- `POST /api/reports/run`
- `POST /api/monthly-close/draft`
- `POST /api/monthly-close/finalize`
- `POST /api/exports/advisor`

Every API response should include stable ids, explicit status, and enough display metadata for the UI to avoid interpreting raw filesystem state.

## Required Synthetic Fixture Coverage

Synthetic fixtures may be committed only if obviously fake.

Fixture sets required by PR 10:

- Valid Alliant Checking export.
- Valid Alliant Savings export.
- Valid Alliant Credit Card export.
- Valid Chase Prime Visa export.
- Missing required source scenario.
- Stale source scenario.
- Wrong header/schema scenario.
- Malformed date scenario.
- Malformed amount scenario.
- Unexpected amount sign scenario.
- Duplicate imported row scenario.
- Ambiguous canonical transaction scenario.
- Warning acknowledgment scenario.
- High-impact decision requiring note.

No real merchant names, real transaction descriptions, real account identifiers, real household financial values, or real generated reports are allowed.

## Owner Checkpoints

- Approve this implementation plan PR before app code starts.
- Confirm header-only/sanitized Alliant and Chase samples before parser acceptance tests are finalized.
- Approve any deviation from the approved tech stack.
- Approve any dependency that is paid, networked, AI-related, credential-related, storage/database-level, or hard to replace.
- Approve any workflow that sends transaction-level or item-level data outside the local machine/NAS.
- Approve any real-data smoke run and review only sanitized results.

## Definition Of Done For v1 MVP

- `docker compose up` runs the app locally at `127.0.0.1:8080`.
- Synthetic Alliant and Chase data completes the full closed loop.
- Raw files are preserved under `DATA_ROOT`, not git.
- SQLite contains operational state, validation findings, settings, decision events, jobs, report runs, artifacts, and monthly close records.
- Owner can save at least one classification decision as an append-only event.
- Reports, monthly close draft/final behavior, and advisor export work with validation/provisional labels.
- CI passes synthetic tests and artifact scans.
- No real financial data, credentials, generated reports, runtime databases, or API keys are present in git.

# Test And Validation Strategy v1

This document defines the proposed v1 test and validation strategy for Dillon Finances. It is a planning artifact only. It does not create app code, test code, database schema, dependencies, fixtures, generated reports, or financial data artifacts.

## Status

- Approved by owner for v1 planning on 2026-06-18.
- App implementation has not started.
- Test implementation has not started.
- No real transaction data, raw exports, normalized data, generated reports, database files, or credentials have been added.
- This strategy should guide the later implementation plan and test scaffold.

## Recommendation

Strong recommendation: use a synthetic-data-first validation strategy with layered automated checks. The first implementation should combine repository safety checks, unit tests, service/integration tests, artifact reproducibility tests, and later UI smoke tests. This is the right default for a local-first financial product because it proves data integrity without putting real transaction rows in git or requiring cloud services. Real financial exports should be used only in local owner-approved manual verification runs, with sanitized outcomes documented and no raw data committed.

The most important principle is that tests must prove the closed loop without hiding uncertainty. A report that is based on stale, missing, blocked, or materially unreviewed data must carry that state. A human decision must be auditable as an append-only event. Imported facts must remain immutable.

Serious alternatives considered:

- Real-data fixtures in the repo: highest fidelity, but unacceptable for privacy and GitHub exposure risk.
- Manual-only validation: useful for final owner review, but too weak to protect future changes.
- Full end-to-end browser automation first: valuable later, but premature before the service boundaries, schema, and controlled write model are implemented.
- Cloud test environments: unnecessary for v1 and inconsistent with the local-first privacy model.

## Strategy Goals

The v1 test strategy must prove:

- Raw source exports are never mutated or committed.
- Imports preserve source-file evidence and hashes.
- Validation blocks unsafe imports and labels warnings clearly.
- Normalized ledger facts are immutable imported facts.
- Human review decisions are append-only events.
- Reviewed current state is derived, not directly overwritten.
- Reports and monthly close bundles carry source coverage, freshness, validation, and review exposure.
- Advisor-ready exports are explicit owner actions and carry provisional labels when applicable.
- No generated financial artifacts enter git-tracked paths.

## Test Data Policy

Approved default for implementation planning: repository fixtures should be synthetic only.

Allowed in git:

- Synthetic transaction rows with fake dates, fake merchants, fake amounts, and fake local account keys.
- Header-only examples for source profiles when needed.
- Redacted documentation examples that contain no real transaction rows.
- Synthetic report examples.

Not allowed in git:

- Real raw exports.
- Real normalized transaction rows.
- Real account identifiers.
- Real receipt or item details.
- Real generated reports.
- SQLite, DuckDB, or other database files containing financial data.
- Credentials, tokens, cookies, browser sessions, or API keys.

Local-only real-data verification is allowed only after owner approval for the specific run. Results should be recorded as sanitized evidence such as pass/fail status, source count, row count, validation counts, and high-level notes.

## Test Layers

### 1. Repository Safety Checks

Purpose: prevent accidental financial-data commits.

Checks should cover:

- No committed files with sensitive artifact extensions such as `.csv`, `.xlsx`, `.xls`, `.pdf`, `.db`, `.sqlite`, `.duckdb`, or `.env` unless explicitly approved for synthetic documentation.
- `.gitignore` continues to exclude local data roots, databases, generated reports, caches, environment files, and temporary artifacts.
- Planning-only PRs contain no app implementation code, schema, dependencies, credentials, or financial artifacts unless the PR explicitly changes scope after owner review.

Recommended placement later:

- Local pre-commit-style script or repository check command.
- GitHub Actions check using synthetic-only repository contents.

### 2. Source Profile And Header Checks

Purpose: prove source/account identity before parsing real rows.

Tests should cover:

- Alliant Checking header profile.
- Alliant Savings header profile.
- Alliant Credit Card header profile.
- Chase Prime Visa header profile.
- Missing expected columns.
- Extra columns.
- Ambiguous source detection.
- Wrong account/source mapping.
- Source/account metadata that avoids unnecessary full account identifiers.

Required owner gate before parser implementation:

- Confirm source headers using synthetic or header-only samples.
- Confirm credit-card purchase, payment, refund, fee, and interest sign conventions using synthetic rows.

### 3. Import Validation Unit Tests

Purpose: prove each validation code behaves predictably.

Tests should cover:

- Missing, unreadable, and empty files.
- Unsupported file types.
- Parse failures.
- Schema mismatches.
- Row-count mismatches.
- Date parse failures.
- Amount parse failures.
- Source/account ambiguity.
- Duplicate imported row identities.
- Duplicate canonical transaction candidates.
- Overlapping exports.
- Unexpected amount signs by source profile.
- Missing required source in a refresh cycle.
- Stale source based on configurable freshness thresholds.
- Warning acknowledgment.
- Blocking finding resolution.

Rules:

- Blocking findings stop import acceptance until resolved.
- Warning findings require explicit acknowledgment before acceptance.
- No validation issue should disappear without a resolution event or superseding validation run.

### 4. Normalization And Identity Tests

Purpose: prevent silent mutation, double-counting, and identity drift.

Tests should cover:

- Imported row identity is deterministic for the exact imported row.
- Canonical transaction identity is deterministic for the same real-world transaction candidate.
- Imported rows remain immutable after acceptance.
- Reimports create linked batches rather than overwriting old imported rows.
- Overlapping exports are preserved as evidence and resolved through canonical identity logic.
- Ambiguous matches enter validation review instead of silent merge.
- Source file metadata and hashes remain linked to normalized rows.

### 5. Decision Event Tests

Purpose: prove controlled writes are auditable and reversible.

Tests should cover:

- Classification decisions append events instead of editing normalized ledger facts.
- Events capture actor, timestamp, previous value, proposed value, approved value, reason, source suggestion, and rollback/supersede linkage where applicable.
- Current reviewed state is derived from imported facts plus active decision events.
- Superseded decisions remain visible in history.
- Rollback creates a new event rather than deleting prior history.
- AI-suggested proposals remain proposals until owner approval.

### 6. Report Validation Tests

Purpose: prove reports do not fake confidence.

Tests should cover:

- Cashflow separates income, spending, transfers, and net cashflow.
- Category spending preserves ledger totals and exposes unreviewed exposure.
- Review backlog counts and dollar exposure match validation and classification inputs.
- Top merchants/sources use reviewed state while exposing provisional status.
- Reports include source coverage, freshness, validation state, and provisional/final status.
- Reports do not double-count vendor/detail enrichment rows as ledger transactions.
- Report reruns create new report-run records and artifacts.

### 7. Monthly Close And Artifact Tests

Purpose: prove close bundles are reproducible, inspectable, and immutable after finalization.

Tests should cover:

- Draft close bundles can be replaced before finalization.
- Final close bundles are retained and not silently overwritten.
- Revisions create retained revision bundles.
- Final close revisions require an owner note.
- Every draft, final, and revision bundle includes `manifest.json`.
- Manifest metadata records artifact list, source inputs, hashes, validation snapshot, settings snapshot, and provisional/final status.
- Final close is blocked when required sources are missing, stale, or have open blocking validation findings.
- Draft close can exist with provisional labels when warnings or stale sources remain.

### 8. Advisor Export Tests

Purpose: prove advisor exports are explicit, traceable, and labeled correctly.

Tests should cover:

- Advisor-ready draft export requires explicit owner action.
- Export includes validation state and source freshness.
- Export clearly labels provisional data.
- Export excludes credentials, stored sessions, and unnecessary full account identifiers.
- Export references generated artifacts rather than inventing new numbers.
- No live AI API call is made in v1.

### 9. UI Smoke Tests Later

Purpose: prove the local browser UI shows the same truth as the backend.

These tests should be added only after the implementation plan approves UI code.

Future checks should cover:

- Home status reflects latest import, validation, review backlog, and monthly close state.
- Import screen shows candidate files, validation results, quarantine state, and next action.
- Validation screen makes blocking issues impossible to miss.
- Review queue applies controlled decision events only after explicit owner action.
- Reports screen shows provisional/final state and artifact links.
- Settings changes create settings events and validate risky values.

### 10. End-To-End Synthetic Scenarios

Purpose: prove the minimum closed loop.

Happy path scenario:

1. Synthetic Alliant and Chase files are placed in a test inbox.
2. Import validation passes with no blocking findings.
3. Raw evidence is preserved with metadata and hashes.
4. Rows normalize into immutable ledger facts.
5. Review queues are generated.
6. One classification decision is applied as an append-only event.
7. Reviewed current state reflects the decision.
8. v1 reports are generated.
9. Monthly close draft is generated.
10. Advisor-ready export is generated with validation status.
11. Next refresh action is visible.

Blocked path scenario:

1. A required source is missing or stale.
2. A synthetic file has a blocking schema or amount-sign issue.
3. Import acceptance is blocked.
4. Report or close output is blocked or clearly provisional.
5. Owner-facing status shows the next required action.

## Local And CI Execution Model

Recommended default:

- GitHub Actions may run repository safety checks and synthetic-data tests.
- CI must not require real financial data, credentials, paid services, cloud databases, OpenAI API calls, local LLMs, bank connections, or browser sessions.
- Any check that uses `DATA_ROOT` with real files must be local-only, off by default, and owner-triggered.
- CI should fail if sensitive artifact files are added accidentally.

This is approved as the v1 testing direction. Adding the actual GitHub Actions workflow file remains a later implementation task and should happen in its own branch/PR.

## Owner Review Gates

Approved owner decisions:

- Synthetic-only repository fixtures are the default.
- GitHub Actions may run synthetic-only safety and test checks.
- Local real-data smoke checks are manual-only and off by default.
- Sensitive artifact scanning should be required for every PR.
- Live AI/API tests are not included in v1.

Data integrity gates during implementation:

- Stop before adding real data fixtures.
- Stop before allowing generated reports into git.
- Stop before adding any schema that mutates normalized ledger facts for review decisions.
- Stop before adding any AI/network test that can send transaction-level data externally.
- Stop before relaxing blocking validation rules.

## Non-Goals

- No app implementation.
- No test implementation.
- No database schema.
- No dependencies.
- No GitHub Actions workflow yet.
- No synthetic fixture files yet.
- No real financial data.
- No generated reports.
- No live AI API calls.
- No local LLM integration.
- No old prototype test migration.

## Recommended Next Step

Codex can create the first implementation plan with a test scaffold that proves the v1 closed loop using synthetic data only, after the remaining planning gates are approved.

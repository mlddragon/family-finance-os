# v1 Completion Audit

Status: synthetic v1 MVP foundation complete through v0.5.0 governance; owner real-data smoke deferred until after `v1.0.0-rc.N` and explicit owner approval. Pre-RC validation uses synthetic QA only (`docs/qa_validation_strategy.md`).

This document maps the approved v1 implementation plan to current evidence. It does not add app code, schema, fixtures, generated reports, raw data, credentials, API keys, or runtime databases.

## Current Scope

The v1 product candidate proves the closed loop with synthetic data:

source files arrive -> ingestion -> validation -> normalization -> review queue -> owner decision event -> controlled update -> reports -> monthly close -> advisor export -> next refresh action

The product remains local-first for v1:

- Docker Compose runs the app locally.
- Personal browser UI is served at `127.0.0.1:28080` (`ffos-personal`).
- QA synthetic demo UI is served at `127.0.0.1:28081` (`ffos-qa`).
- SQLite operational state and file evidence live under external `DATA_ROOT`.
- Raw files, generated artifacts, databases, secrets, and real financial data stay out of git.
- No live AI/API calls, bank aggregators, credentials, LAN exposure, or authentication are included in v1.

## Milestone Evidence

| Area | Status | Evidence |
| --- | --- | --- |
| Scaffold, Docker, and safety | Complete | `docker-compose.yml`, Dockerfile, `README.md`, `.github/workflows/ci.yml`, `scripts/check_sensitive_artifacts.py`, `scripts/check_v1_security_contract.py` |
| SQLite foundation and audit core | Complete | `apps/api/family_finance_os/database.py`, migrations, models, `tests/api/test_database_foundation.py` |
| Settings and source profiles | Complete | `apps/api/family_finance_os/settings_service.py`, `apps/api/family_finance_os/source_profiles.py`, `tests/api/test_settings_api.py`, `tests/api/test_source_profiles.py` |
| Import, validation, and quarantine | Complete | `apps/api/family_finance_os/import_validation.py`, `tests/api/test_import_validation.py`, synthetic fixtures |
| Normalization and ledger identity | Complete | `apps/api/family_finance_os/ledger_normalization.py`, `tests/api/test_ledger_normalization.py` |
| Controlled decision events | Complete | `apps/api/family_finance_os/decision_events.py`, `tests/api/test_decision_events.py` |
| Backend API and UI MVP | Complete | `apps/api/family_finance_os/main.py`, `apps/web/src/App.tsx`, `apps/web/e2e/operator-ui.spec.ts` |
| Reports, monthly close, advisor export | Complete | `apps/api/family_finance_os/reporting.py`, `tests/api/test_reports_monthly_close.py` |
| Hardening and synthetic E2E | Complete for synthetic v1 | `tests/api/test_v1_hardening_e2e.py`, `scripts/run_docker_e2e.py`, PRs #23 through #42 |
| Owner real-data smoke | Deferred to v1.0.0 RC | `docs/owner_smoke_checklist_v1.md`, `docs/qa_validation_strategy.md` |
| QA named scenarios (5) | Complete | `make qa-seed QA_SCENARIO=...`, README scenario table |
| Actor/persona context + permission enforcement (B.1) | Complete on synthetic | `permissions.py`, UI gating, Settings permission preview (QA) |
| Elevated mode (B.2) | Complete on synthetic | `elevated_mode.py`, Control plane UI, API tests |
| Suggestions and approvals (B.3) | Complete on synthetic | `suggestions.py`, `approvals.py`; approval mode off by default |
| Self-hosted QA auto-update | Complete | PR #85, `.github/workflows/qa-auto-update.yml` |
| Amazon vendor enrichment | **Post-v1.0.0** | Deferred per `planning/first_closed_loop_slice_v1.md` and owner decision |

## Acceptance Criteria Audit

| v1 acceptance criterion | Status | Evidence |
| --- | --- | --- |
| `docker compose up` runs the local browser app on approved localhost ports. | Complete with synthetic Docker verification | Personal default `127.0.0.1:28080`; QA default `127.0.0.1:28081`; Docker E2E and CI synthetic closed-loop paths pass. |
| Synthetic Alliant and Chase files complete the full closed loop. | Complete | `scripts/run_docker_e2e.py` accepted Alliant Checking, Alliant Savings, Alliant Credit Card, and Chase Prime Visa synthetic files; produced 5 transactions, 16 artifacts, final monthly close, and refresh next action. |
| Raw files are preserved under `DATA_ROOT`, not git. | Complete for v1 flow | Import acceptance stores source files under `DATA_ROOT/raw/...`; quarantine stores blocked files under `DATA_ROOT/quarantine/...`; sensitive-artifact scan passes. |
| SQLite contains operational state, validation findings, settings, decisions, jobs, report runs, artifacts, and monthly close records. | Complete | Database migrations and model tests cover required v1 tables; integration tests exercise inserts and runtime flows. |
| Owner can review and save at least one classification decision as an append-only event. | Complete with synthetic data | Backend decision event tests and Playwright operator UI smoke test save a category decision through the browser flow. |
| Reports, monthly close draft/final behavior, and advisor export work with validation/provisional labels. | Complete with synthetic data | Report/monthly close tests cover core artifacts, provisional draft close, final close, blocked close, and advisor export. |
| CI passes synthetic tests and artifact scans. | Complete on current top PR | PR #42 CI run passed sensitive artifact scan, v1 security contract, API/script tests, npm audit, web tests, browser smoke, web build, Docker image build, and Docker E2E. |
| No real financial data, credentials, generated reports, runtime databases, or API keys are present in git. | Complete by automated scan and review boundary | Sensitive artifact scan passes; `.gitignore` and data handling docs prohibit committing these artifacts. |

## Current Verification Snapshot

Latest local verification on the top stacked branch before this audit:

- Python tests: 91 passed.
- Sensitive artifact scan: no sensitive artifacts found.
- v1 security contract: passed.
- Web unit tests: 8 passed.
- Web dependency audit: 0 high-or-higher vulnerabilities reported.
- Web build: passed.
- Browser smoke tests: 4 passed.
- Docker synthetic closed loop: 4 accepted sources, 5 transactions, 16 artifacts, final close, refresh next action.

Latest GitHub verification:

- PR #42, `[codex] harden SQLite database paths`, CI run completed successfully on 2026-06-19.
- The CI run included synthetic artifact scanning, backend tests, npm audit, UI tests, browser smoke, web build, Docker build, and Docker E2E.

## Security And Privacy Readiness

Completed v1 safeguards:

- `DATA_ROOT` must stay outside the git repository.
- Required `DATA_ROOT` child directories reject symlink escapes and file collisions.
- SQLite database parent and database file paths reject symlink/file-collision hazards.
- Import storage paths are constrained to `DATA_ROOT`.
- Artifact storage and downloads are constrained to `DATA_ROOT`.
- Source imports and artifact downloads require regular files.
- Source file integrity and artifact integrity are checked before sensitive operations.
- The app binds locally by default.
- CI blocks common financial data, database, report, credential, and secret artifacts.

Known v1 boundaries:

- No authentication in localhost-only v1.
- No LAN/NAS exposure in v1.
- No live AI/API integration in v1.
- No bank aggregator or credential storage in v1.
- No real-data fixtures in git.

## Pending Before v1.0.0 RC Tag

Required before tagging `v1.0.0-rc.N`:

1. Run the full synthetic verification set at `127.0.0.1:28081` per `docs/qa_validation_strategy.md` and record in `planning/v1_synthetic_qa_record.md`.
2. Complete governance QA script (permissions, elevation, suggestions/approvals).
3. Green CI and Security workflows on `main`.
4. RC release gates in `docs/runbooks/v1-rc-release-gates.md` (tag protection, waived Codex #80 for RC).

## Pending Before v1.0.0 Stable

Required after RC tag:

1. Owner explicitly approves a local real-data smoke run.
2. Perform owner smoke using `docs/owner_smoke_checklist_v1.md` against personal `ffos-personal` at `127.0.0.1:28080`.
3. Record only sanitized smoke evidence: counts, statuses, validation codes, and pass/fail notes.
4. Do not record raw transaction descriptions, account details, balances, filenames with private information, generated reports, databases, screenshots containing financial rows, or transaction-level values in git or GitHub.

Until owner approves real-data smoke, **do not** treat personal-data validation as a release blocker. Use the five QA seed scenarios and CI instead.

## Recommended Next Step

Complete synthetic QA marathon and tag `v1.0.0-rc.1`. Schedule owner real-data smoke only after RC tag and explicit owner approval.

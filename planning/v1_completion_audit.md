# v1 Completion Audit

Status: synthetic v1 MVP foundation complete through v0.4.0; owner real-data smoke deferred to v1.0.0 RC. Pre-RC validation uses synthetic QA only (`docs/qa_validation_strategy.md`).

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
| Actor/persona context | Complete (no enforcement yet) | Actor context APIs/UI; permission enforcement deferred |
| Self-hosted QA auto-update | Complete | PR #85, `.github/workflows/qa-auto-update.yml` |

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

## Pending Before v1.0.0 RC Owner Acceptance

Required before declaring owner-accepted v1.0.0 RC:

1. Complete v1 RC foundation work on `phase/v1-rc-foundation` (permission enforcement, approved preview model, remaining planning gates).
2. Run the full verification set with synthetic QA scenarios at `127.0.0.1:28081` per `docs/qa_validation_strategy.md`.
3. Merge v1 RC foundation into the release line and tag `v1.0.0-rc` when scope is complete.
4. Owner explicitly approves a local real-data smoke run (deferred until this RC gate).
5. Perform the owner smoke using `docs/owner_smoke_checklist_v1.md` against personal `ffos-personal` at `127.0.0.1:28080`.
6. Record only sanitized smoke evidence: counts, statuses, validation codes, and pass/fail notes.
7. Do not record raw transaction descriptions, account details, balances, filenames with private information, generated reports, databases, screenshots containing financial rows, or transaction-level values in git or GitHub.

Until v1.0.0 RC, **do not** treat owner real-data smoke as a release blocker. Use the five QA seed scenarios and CI instead.

## Recommended Next Step

Continue v1 RC foundation implementation and synthetic QA validation. Schedule owner real-data smoke only after v1.0.0 RC scope is merged and explicitly approved.

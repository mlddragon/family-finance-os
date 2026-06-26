# QA Validation Strategy

This document defines how Family Finance OS is validated before v1.0.0 release candidate (RC). It complements CI synthetic checks and the semi-persistent QA environment.

## Scope Until v1.0.0 RC

**Use synthetic QA data only.** Owner real-data smoke is deferred until v1.0.0 RC.

Until then, validation must rely on:

- Automated CI (synthetic fixtures, security scans, Docker E2E)
- Semi-persistent QA at `http://127.0.0.1:28081` with named seed scenarios
- Human QA scripts attached to pull requests for behavior changes

Do not run owner real-data imports, real monthly close, or real advisor export validation against personal `DATA_ROOT` as a release gate before v1.0.0 RC.

## QA Runtime

| Setting | Value |
| --- | --- |
| Compose project | `ffos-qa` (legacy `dillon-qa` deprecated) |
| Host URL | `http://127.0.0.1:28081` |
| Data root | External synthetic QA `DATA_ROOT` outside git |
| Dataset kind | `synthetic` |
| Dev mode | Enabled only when `APP_ENV=qa` and `DEV_MODE=true` |

Personal runtime (`ffos-personal` at `http://127.0.0.1:28080`) is for owner local operation and is **not** a pre-RC validation gate.

## Named Seed Scenarios

All five scenarios are implemented. Seed with `make qa-seed QA_SCENARIO=<name>` after optional `make qa-reset CONFIRM="RESET QA DATA"`.

| Scenario | Purpose |
| --- | --- |
| `baseline` | Smallest useful closed-loop synthetic dataset |
| `stale-source` | Stale or missing required source warnings |
| `blocked-import` | Blocking validation findings and quarantine behavior |
| `review-backlog` | Unreviewed transactions and review-queue work |
| `monthly-close-ready` | Dataset ready for draft/final monthly close and advisor export |

Each seed writes a manifest under QA `DATA_ROOT/manifests/` describing scenario name, version, fixtures, and expected outcomes.

Update synthetic fixtures and scenario definitions in git when product behavior changes require new validation coverage. Generated QA state (SQLite, reports, bundles, exports) must remain outside git.

## Validation Layers

### 1. CI (every PR)

- Sensitive artifact scan
- v1 security contract checks
- Backend and web unit tests
- Browser smoke tests (synthetic)
- Docker image build and synthetic closed-loop E2E

### 2. Semi-persistent QA (local and self-hosted)

- `make qa-up` / `make qa-seed` for repeatable scenario validation
- Self-hosted **QA auto-update** workflow (PR #85) rebuilds QA when dependency files merge to `main`
- See [docs/runbooks/qa-self-hosted-runner.md](runbooks/qa-self-hosted-runner.md)

### 3. Human QA scripts (PR gate)

PRs that change app, UI, API, Docker, import, review, report, or data-integrity behavior must include a human QA script with scope, preconditions, steps, expected results, stop conditions, and known gaps.

## Deferred Until v1.0.0 RC

- Owner real-data smoke using [docs/owner_smoke_checklist_v1.md](owner_smoke_checklist_v1.md)
- Personal-data validation as a release acceptance criterion
- Permission enforcement and view-as preview implementation (see `planning/issue_55_view_as_decision_record.md`)

## Evidence Boundaries

Sanitized evidence only in git and GitHub:

- Counts, statuses, validation codes, pass/fail notes
- Scenario names and manifest presence

Never commit or record in docs/PRs:

- Raw transaction rows, merchants, balances, account identifiers
- Real filenames, generated reports, SQLite databases, credentials

## Related Documents

- [planning/semi_persistent_qa_environment.md](../planning/semi_persistent_qa_environment.md)
- [docs/qa_feature_requirements.md](qa_feature_requirements.md)
- [docs/data_handling_policy.md](data_handling_policy.md)
- [planning/v1_completion_audit.md](../planning/v1_completion_audit.md)

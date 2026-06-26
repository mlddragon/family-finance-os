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

## Governance validation (0.5.0)

Run on semi-persistent QA (`http://127.0.0.1:28081`) before RC tag. Aligns with [planning/v040_orchestration_master_qa_plan.md](../planning/v040_orchestration_master_qa_plan.md) §3.

**Preconditions:** `make qa-up`; QA synthetic banner visible; seed `review-backlog` for suggestion steps.

### Permission matrix by persona

1. **Finance Manager** — import upload, review save, reports, monthly close enabled.
2. **Finance Contributor** — review save disabled; suggestion affordances visible where implemented.
3. **Administrator** — routine financial mutations disabled; settings edits per matrix.
4. **Settings → Permission preview** (expand collapsible section) — change preview persona; confirm matrix matches mutating vs read-only expectations.

### Control-plane elevation

1. Header **Control plane** dropdown — select **Administrator Mode** or **Financial Governor Mode**.
2. Lightbox requires **purpose** selection; Confirm disabled until chosen.
3. For **Approval-rule change** purpose, note is required; other purposes allow empty note.
4. While elevated, import/review/report mutations disabled; status strip shows mode and countdown.
5. Switch elevated context — lightbox re-prompts (no silent switch).
6. **Operator Mode** exits elevation without lightbox.

### Suggestions and approvals

1. On `review-backlog`, as **Finance Contributor**, create a suggestion on a transaction.
2. As **Finance Manager**, accept and dismiss suggestions from the queue.
3. **Optional second pass:** enable `approval.approval_mode_enabled` in QA Settings only; convert suggestion to approval; approve or deny from approvals queue.

**Stop if:** personal `:28080` data affected; elevated mode allows financial mutations; preview panel allows writes; real financial data appears in notes or screenshots.

## Deferred until after v1.0.0-rc.N

- Owner real-data smoke using [docs/owner_smoke_checklist_v1.md](owner_smoke_checklist_v1.md)
- Personal-data validation as a release acceptance criterion for **stable** v1.0.0
- True impersonation / auth ([#55](https://github.com/mlddragon/family-finance-os/issues/55) — preview only today)

## Implemented on main (no longer deferred)

- Permission enforcement and non-mutating permission preview — B.1 ([#87](https://github.com/mlddragon/family-finance-os/pull/87), [#89](https://github.com/mlddragon/family-finance-os/pull/89), [#96](https://github.com/mlddragon/family-finance-os/pull/96))
- Elevated mode and suggestions/approvals — B.2/B.3 ([#94](https://github.com/mlddragon/family-finance-os/pull/94), [#96](https://github.com/mlddragon/family-finance-os/pull/96))

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

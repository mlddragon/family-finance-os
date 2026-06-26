# v1.0.0 RC Foundation — Review Guide

Branch: **`phase/v1-rc-foundation`**

Review this branch as a single phase before opening a merge PR to `main`. Tracking issue: [#90](https://github.com/mlddragon/family-finance-os/issues/90).

## Owner direction applied

| Decision | Outcome |
| --- | --- |
| Real-data smoke | **Deferred until v1.0.0 RC** — use QA synthetic data ([docs/qa_validation_strategy.md](../docs/qa_validation_strategy.md)) |
| Issue #55 view-as | **Non-mutating permission preview in B.1** ([planning/issue_55_view_as_decision_record.md](../planning/issue_55_view_as_decision_record.md)) |
| Validation path | Expand synthetic QA scenarios as needed; no personal `DATA_ROOT` in CI or docs |

## Merged PRs (into this branch)

| PR | Scope |
| --- | --- |
| [#86](https://github.com/mlddragon/family-finance-os/pull/86) | Planning doc refresh, CHANGELOG 0.3/0.4 released, QA validation strategy |
| [#87](https://github.com/mlddragon/family-finance-os/pull/87) | Permission matrix B.1 backend: evaluator, migration, API 403 enforcement |
| [#88](https://github.com/mlddragon/family-finance-os/pull/88) | Phase A polish: v1 RC runbook, issue status comments (#72, #80, #73, #55) |
| [#89](https://github.com/mlddragon/family-finance-os/pull/89) | Permission UI: hide/disable mutating controls; QA preview panel |

## Human QA script (synthetic only)

**Preconditions:** Docker Desktop running; QA at http://127.0.0.1:28081 (`make qa-up`).

1. Open QA UI; confirm red synthetic banner.
2. Select **Finance Manager** persona — import, review save, reports, and close controls enabled.
3. Select **Finance Contributor** — review save disabled; suggestion hint visible.
4. Select **Administrator** — financial mutating controls disabled; settings may remain available per matrix.
5. Open **Permission preview** panel (QA only); preview **Report Viewer**; confirm read-oriented allows, mutations denied.
6. Run `make qa-seed QA_SCENARIO=review-backlog` after reset; confirm scenario still seeds.

**Stop if:** personal port 28080 affected; preview allows writes; real financial data required.

## Verification commands

```bash
.venv/bin/python -m pytest
cd apps/web && npm test
cd apps/web && npm run build
```

## After approval

1. Open PR: `phase/v1-rc-foundation` → `main`
2. Close or update #90
3. Continue B.2 (elevated mode) and B.3 (suggestions/approvals) on new phase branches

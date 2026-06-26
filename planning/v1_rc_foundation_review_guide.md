# v1.0.0 RC Validation Guide

Use this guide on **`main`** after the 0.5.0 governance release. Tracking issue [#90](https://github.com/mlddragon/family-finance-os/issues/90) is closed; RC foundation and B.2/B.3 are merged.

## Owner direction (locked)

| Decision | Outcome |
| --- | --- |
| v1.0.0 stable scope | Closed loop + governance on synthetic QA through RC; **no Amazon enrichment in v1.0.0** |
| Real-data smoke | **After** `v1.0.0-rc.N` tag and explicit owner approval — [docs/owner_smoke_checklist_v1.md](../docs/owner_smoke_checklist_v1.md) |
| Issue #55 view-as | Non-mutating permission preview in Settings (QA only) — [planning/issue_55_view_as_decision_record.md](issue_55_view_as_decision_record.md) |
| RC gates | Enable `v*` tag protection ([#72](https://github.com/mlddragon/family-finance-os/issues/72)); waive Codex auto-setup ([#80](https://github.com/mlddragon/family-finance-os/issues/80)) for RC; solo-maintainer bypass ([#73](https://github.com/mlddragon/family-finance-os/issues/73)) |

## Landed on main (0.5.0)

| Area | PR / evidence |
| --- | --- |
| B.1 permission enforcement + preview | #87, #89, #96 (preview in Settings, collapsible) |
| B.2 elevated mode backend + UI | #94, #96 (Control plane header dropdown + lightbox) |
| B.3 suggestions + approvals | #94 |
| QA deploy cache fix | #96 (`index.html` no-cache) |

## Preconditions

- Docker Desktop running
- QA at http://127.0.0.1:28081 (`make qa-up` or `make qa-update`)
- Synthetic data only — no personal `DATA_ROOT` in validation notes

## Closed-loop QA (five scenarios)

For each scenario:

```bash
make qa-reset CONFIRM="RESET QA DATA"
make qa-seed QA_SCENARIO=<name>
```

| Scenario | Expected signal |
| --- | --- |
| `baseline` | Closed loop operable; manifests present |
| `stale-source` | Stale/missing required source warnings |
| `blocked-import` | Blocking validation / quarantine visible |
| `review-backlog` | Unreviewed transactions in review queue |
| `monthly-close-ready` | Reports/close/export readiness |

Record sanitized pass/fail in [planning/v1_synthetic_qa_record.md](v1_synthetic_qa_record.md).

## Governance QA (synthetic)

See [docs/qa_validation_strategy.md](../docs/qa_validation_strategy.md) — **Governance validation (0.5.0)** section.

Summary:

1. QA banner on every screen checked.
2. **Finance Manager** — import, review, reports, close enabled.
3. **Finance Contributor** — review save disabled; suggestions path available.
4. **Administrator** — financial mutations disabled; settings per matrix.
5. **Settings → Permission preview** (QA only, collapsed by default) — matrix matches persona.
6. **Control plane** — Operator / Administrator / Financial Governor; lightbox requires purpose; `approval_rule_change` requires note.
7. Elevated mode — financial mutations read-only; exit via Operator Mode.
8. Suggestions — contributor propose; manager accept/dismiss on `review-backlog`.
9. Approval mode (optional second pass) — enable `approval.approval_mode_enabled` in QA Settings only; convert suggestion → approval → approve/deny.

**Stop if:** personal `:28080` affected; preview allows writes; real financial data required.

## Verification commands

```bash
.venv/bin/python -m pytest
cd apps/web && npm test && npm run build
```

CI on `main` must be green before RC tag.

## After synthetic sign-off

1. Complete [docs/runbooks/v1-rc-release-gates.md](../docs/runbooks/v1-rc-release-gates.md) checklist
2. Tag `v1.0.0-rc.1` (prerelease)
3. Owner approves real-data smoke
4. Run [docs/owner_smoke_checklist_v1.md](../docs/owner_smoke_checklist_v1.md) on `ffos-personal` (`:28080`)
5. Tag stable `v1.0.0` when smoke passes

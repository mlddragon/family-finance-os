# v0.4.0 Orchestration And Master QA Plan

This document defines the v0.4.0 orchestration run for the five current workstreams. It is a planning and coordination artifact only. It does not implement app behavior, change schemas, create runtime data, add authentication, enforce permissions, add approval mode, add elevated mode, or add QA browser reset controls.

## Status

- Created for PR 1 of the v0.4.0 run.
- Active GitHub milestone: `0.4.0 Planning And QA Scenario Foundation`.
- Active target label: `target:0.4.0`.
- Issue #50 was completed by PR #58 and closed before this PR.
- Issues #51, #52, #53, #54, #55, and #59 are tracked under the v0.4.0 milestone.
- The stale `0.3.0 Planning` milestone has no open issues and was closed during this orchestration setup.
- The active Codex Goal for execution must stay open until all accepted PRs are merged, branches are deleted, issue state is updated, final verification passes, human QA is approved, and post-QA cleanup is complete.

## Workstreams

| Workstream | GitHub issue | Planned PR | Scope | Owner checkpoint |
| --- | --- | --- | --- | --- |
| Backlog, roadmap, and QA orchestration | #50, #51-#55, #59 | PR 1 | GitHub hygiene, milestone setup, workstream map, master QA plan | Confirm v0.4.0 shape and master QA coverage |
| Permission matrix and data scopes | #51 | PR 2 | Planning-only permission/data-scope model | Approve default permission model |
| Shared elevated mode | #53 | PR 3 | Planning-only elevated-mode lifecycle and naming | Approve elevated-mode model |
| Suggestions and approval model | #52, #54 | PR 4 | Planning-only suggestions/approval request lifecycle | Approve queue boundaries and approval defaults |
| QA scenario expansion | #59 | PR 5 | Script-level named QA scenarios beyond `baseline` | Confirm seeded scenarios in QA |

Issue #55 remains a tracked later decision for role/user troubleshooting and view-as tooling. It should stay planning-only unless the owner explicitly pulls that decision into an implementation milestone.

## Execution Rules

- Codex remains the top-level orchestrator and accepts, rejects, or requests revision on all subagent work.
- Subagents may be used only for scoped work with disjoint ownership.
- Planning PRs must not change app behavior.
- Implementation PRs must include focused tests and a human QA script.
- No PR may commit real financial data, normalized financial data, generated reports, databases, logs, credentials, API keys, or runtime artifacts.
- Any architecture, privacy, security, cost, data-integrity, or AI-provider decision requires explicit owner review before implementation.
- The Goal is not complete when human QA passes. Completion requires post-QA merge, branch cleanup, issue/milestone updates, final verification, and QA readiness confirmation.

## Merge Order

1. PR 1: v0.4.0 orchestration, backlog hygiene, and master QA plan.
2. PR 2: permission matrix and data scopes.
3. PR 3: shared elevated mode.
4. PR 4: suggestions and approval model.
5. PR 5: QA scenario expansion.

PRs 2, 3, and 4 may be drafted in parallel after PR 1 is approved. Final merge should still be serialized so the orchestrator can resolve vocabulary and decision consistency. PR 5 may run in parallel with planning review because it is a QA-scenario implementation lane, but it must not add browser reset/reseed controls or permission/approval behavior.

## PR Acceptance Gates

Each PR must pass these gates before owner QA:

- Scope matches its workstream and issue.
- Required tests/checks pass.
- PR body includes a focused QA script.
- No out-of-scope app behavior is introduced.
- No generated runtime artifacts or financial data are in git.
- Owner review gates are explicit when decisions are being proposed.

The orchestrator rejects a PR if it:

- Implements permission enforcement, elevated mode, approval mode, auth, or impersonation in a planning-only lane.
- Weakens QA/personal data separation.
- Creates UI access to personal reset or data-root switching.
- Adds paid tooling, cloud dependencies, AI/provider calls, or credential behavior without approval.
- Creates conflicts with already-approved product direction.

## Master Human QA Plan

This master QA plan is the superset checklist for the v0.4.0 run. Individual PRs must still include their own focused QA scripts.

### 1. Repo Hygiene

1. Confirm the active branch or PR only contains expected files for the workstream.
2. Run `git diff --check`.
3. Run `.venv/bin/python scripts/check_sensitive_artifacts.py .`.
4. Run `.venv/bin/python scripts/check_v1_security_contract.py .`.
5. Confirm `git status --short` does not show generated reports, SQLite databases, logs, raw files, normalized data, credentials, or runtime artifacts.

Expected result:

- No sensitive artifacts are present.
- Security contract passes.
- Planning-only PRs do not modify runtime code.

Stop if:

- Any real financial data, generated financial artifact, credential, database, or raw/source export appears in git.
- A planning-only PR changes app behavior.

### 2. Planning Document Review

For PRs 1-4:

1. Read each new planning document.
2. Confirm it states whether it is planning-only.
3. Confirm it references the relevant GitHub issue(s).
4. Confirm owner decisions are separated from routine engineering decisions.
5. Confirm terminology matches the PRD and existing planning documents.
6. Confirm deferred items are explicit and are not silently implemented.

Expected result:

- Each planning document is decision-ready for owner review.
- No implementer would need to invent permission, elevation, suggestion, or approval rules not captured in the document.

Stop if:

- The document decides an impactful architecture, privacy, data-integrity, AI, or cost-bearing item without owner review.
- The document contradicts the Administrator/Finance Manager split, audit-first posture, or local-first privacy model.

### 3. Permission, Elevation, And Approval Review

For PRs 2-4:

1. Confirm Administrator is scoped to system administration, not financial-data ownership.
2. Confirm Finance Manager is the highest financial-data authority.
3. Confirm default deny is the baseline.
4. Confirm explicit deny overrides inherited allow.
5. Confirm current display names are primary in normal audit UI, while event-time names remain available in details when needed.
6. Confirm elevated mode makes routine financial workflows read-only.
7. Confirm approval-rule changes require notes.
8. Confirm approval mode is off by default and its management UI is hidden unless enabled.
9. Confirm the first high-value threshold default remains configurable and starts at `$500`.
10. Confirm suggestions are not effective controlled-state changes until accepted or converted through an approved path.

Expected result:

- The three planning docs can be used as the basis for later implementation without reopening settled product decisions.

Stop if:

- Administrator is allowed to perform routine financial edits by default.
- Suggestions bypass human approval.
- Approval mode becomes mandatory by default.
- The plan requires comprehensive RBAC, auth, or impersonation before the owner has approved that scope.

### 4. QA Scenario Review

For PR 5:

1. Pull the PR branch.
2. Start QA at `http://127.0.0.1:28081`.
3. Run `make qa-reset CONFIRM="RESET QA DATA"`.
4. Seed `baseline` and confirm current behavior still works.
5. Seed `stale-source`.
6. Confirm the scenario manifest exists under QA `DATA_ROOT` and clearly marks synthetic data.
7. Confirm operator summary shows stale or missing source behavior.
8. Run reset again.
9. Seed `blocked-import`.
10. Confirm operator summary and UI show blocking validation/quarantine behavior.
11. Run reset again.
12. Seed `review-backlog`.
13. Confirm review queue state visibly contains unreviewed work.
14. Run reset again.
15. Seed `monthly-close-ready`.
16. Confirm reports/monthly close/export readiness state matches the scenario expectation.
17. Confirm the red QA banner appears on every screen checked.
18. Confirm generated QA artifacts include `QA synthetic demo - not real financial data` where applicable.

Expected result:

- Every named scenario can be reset and seeded without personal data.
- QA remains obviously synthetic.
- Scenario manifests and generated artifacts stay outside git.

Stop if:

- Reset can target personal data or a non-QA data root.
- The QA banner is missing in QA mode.
- A generated QA artifact lacks the synthetic marker.
- Any browser UI control exposes personal reset, data-root switching, or destructive QA controls outside QA/dev mode.
- Real financial data appears anywhere in QA, git, screenshots, logs, manifests, reports, or exports.

### 5. Final Integration QA

After all approved PRs are merged:

1. Switch to `main`.
2. Pull latest from GitHub.
3. Confirm all feature branches for merged PRs are deleted locally and remotely.
4. Confirm GitHub issues are closed or updated according to each PR outcome.
5. Run full verification:
   - `git diff --check`
   - `.venv/bin/python -m pytest`
   - `.venv/bin/python scripts/check_sensitive_artifacts.py .`
   - `.venv/bin/python scripts/check_v1_security_contract.py .`
   - `npm test -- --run` from `apps/web`
   - `npm run build` from `apps/web`
   - `npm run test:e2e` from `apps/web`
6. Rebuild QA from `main` with `make qa-up`.
7. Run guarded reset.
8. Seed the agreed post-QA default scenario, initially `baseline` unless the owner requests another scenario.
9. Confirm `http://127.0.0.1:28081/api/status` reports QA/synthetic/dev-mode identity.
10. Confirm `git status --short --branch` is clean on `main`.

Expected result:

- `main` is clean and verified.
- QA is rebuilt from `main`.
- QA is left in the agreed ready state for continued human review.
- The active Goal can be marked complete only after this post-QA cleanup is finished.

Stop if:

- Any verification fails.
- Any branch cleanup would delete unmerged work.
- GitHub issue/milestone state is inconsistent with merged work.
- QA cannot be rebuilt or reseeded safely from `main`.

## Post-QA Cleanup Requirements

After the owner says QA passed for a PR:

1. Merge the PR using the repo's existing PR merge style.
2. Delete the remote branch.
3. Delete the local branch if present and safe.
4. Pull/update local `main`.
5. Update or close linked GitHub issues.
6. Confirm working tree is clean.
7. Continue to the next workstream or, for the final PR, run final integration QA.

If a local branch is not cleanly merge-detectable because of squash history, verify patch-equivalence before deleting it. Do not force-delete unrelated branches without inspection.

## Final Handoff Requirements

The final handoff after all five workstreams must include:

- Active Goal completion status.
- Merged PRs.
- Closed or updated GitHub issues.
- Verification commands and results.
- QA URL and seeded scenario state.
- Branch cleanup status.
- Remaining known follow-ups.

# Repo Setup Summary

## Files created

- `README.md`
- `.gitignore`
- `docs/`
- `docs/product_requirements.md`
- `planning/`
- `planning/prior_work_audit.md`
- `planning/clarifying_questions.md`
- `planning/initial_product_plan.md`
- `planning/repo_setup_summary.md`

## Files intentionally not migrated

- Old Streamlit app code under `app/`.
- Old dashboard configuration and dashboard requirements.
- Old prototype scripts for imports, scraping, matching, enrichment, report building, review overrides, and validation.
- Old tests and fixtures.
- Raw financial exports.
- Normalized financial outputs.
- Generated reports.
- Snapshots.
- Old review CSVs and manual override files.
- Local virtual environments and caches.
- Credentials, secrets, browser sessions, or account access artifacts.

## Materials migrated

- The updated PRD from `mlddragon/Family_Finance_planner/docs/product_requirements.md` was migrated to `docs/product_requirements.md`.

## Assumptions made

- The new repository should live under `/Users/masondillon/Documents/Dillon Finances/Dillon_Finances`.
- The prior repo is available locally at `/Users/masondillon/GitHub/Family_Finance_planner`.
- "Create the new repo" means create a local git repository scaffold; no remote repository was created or pushed.
- The old repo is product research and historical evidence, not implementation scaffolding.
- Financial data directories should be ignored by default and should not be committed.
- The PRD remains the source of truth even where some sections mention prototype-era recommendations; owner direction overrides any old assumption that Streamlit or CSV must be used.

## Open questions

- What is the first minimally viable closed-loop slice?
- Should the first product runtime be local browser, desktop app, command workflow, or another local-first pattern?
- Should product state use a local database, auditable files, or a hybrid?
- What import sources are first priority?
- What review workflow should be proven first?
- What level of AI access to data is acceptable?
- What backup/export model is acceptable for sensitive local state?
- Which architecture and technical decisions does the owner want to approve directly?

## Recommended next conversation

The first clarifying-question interview has been completed and captured in `planning/owner_decision_record.md`. The next conversation should convert those owner decisions into architecture options for the first closed-loop slice. Codex should recommend a primary architecture and any serious alternatives, then stop for owner approval before implementation planning.

## Implementation status

Updated 2026-06-25 for the v1 RC foundation phase.

- **Repository:** Public [`mlddragon/family-finance-os`](https://github.com/mlddragon/family-finance-os); pyproject version `0.4.0`; tags `v0.1.0` through `v0.4.0` exist.
- **Implemented milestones:** v0.1.0 (local Docker MVP), v0.2.0 (open-source readiness), v0.3.0 (QA/demo and actor context), v0.4.0 (rehome, `FFOS_*` env vars, public release prep).
- **App stack:** FastAPI backend, React/Vite frontend, SQLite under external `DATA_ROOT`, Docker Compose local-first runtime.
- **Personal runtime:** Compose project `ffos-personal` at `http://127.0.0.1:28080` (legacy `dillon-personal` deprecated).
- **QA runtime:** Compose project `ffos-qa` at `http://127.0.0.1:28081` with five seed scenarios: `baseline`, `stale-source`, `blocked-import`, `review-backlog`, `monthly-close-ready`.
- **Actor/persona context:** Implemented for audit context; permission enforcement not yet implemented.
- **Validation until v1.0.0 RC:** Synthetic QA and CI only; owner real-data smoke deferred. See `docs/qa_validation_strategy.md`.
- **QA auto-update:** Self-hosted runner workflow merged in PR #85 rebuilds QA on dependency merges to `main`.
- **Open v1 RC work:** Permission matrix enforcement, elevated/approval modes, non-mutating permission preview (issue #55, approved 2026-06-25), and owner real-data smoke at v1.0.0 RC.

# AI Agent Instructions

This file is the canonical repo guidance for AI agents working in Family Finance OS.

## Product Source Of Truth

- Read `docs/product_requirements.md` before product-shaping work.
- Read `docs/data_handling_policy.md`, `SECURITY.md`, `CONTRIBUTING.md`, and relevant `planning/` docs before implementation work.
- Treat prior prototype repositories as research only. Do not assume Streamlit, CSV storage, old scripts, or old repo structure are the product foundation.

## Privacy And Data Boundaries

- Do not commit raw financial data, normalized financial data, generated reports, database files, logs, credentials, API keys, or local runtime artifacts.
- Use synthetic fixtures only. Synthetic files and generated synthetic artifacts must be clearly marked as synthetic.
- Runtime state belongs under an external `DATA_ROOT`, never inside the git repository.
- Do not introduce paid tooling, hosted services, cloud dependencies, provider calls, or AI model calls without explicit owner approval.

## Primary Engineer Responsibilities

Cursor, human contributors, and other implementation agents own product engineering:

- Features, bug fixes, refactors, tests, docs, and Docker/CI changes via pull requests.
- Routine low-impact engineering decisions that fit the approved stack and repository patterns.
- Human QA scripts for app, UI, API, Docker, import, review, report, or data-integrity changes.

Primary engineers must not weaken security boundaries, skip required CI checks, or merge with open P0/P1 security findings.

## Workflow And Review

- Create a feature branch for meaningful work and use GitHub pull requests for traceability.
- Do not push directly to `main`.
- Include a human QA script in PR notes for app behavior, UI, API, Docker, import, review, report, or data-integrity changes.
- Stop for owner review on impactful product/architecture decisions, data-integrity/security/privacy decisions, and cost-bearing decisions.
- For owner decision reviews, use the recommendation-first flow in `.cursor/skills/decision-card-review/SKILL.md` and record approved outcomes in planning docs or issue decision records.

## Engineering Guardrails

- Keep v1 local-first and Docker-friendly unless the owner approves a different runtime direction.
- Preserve append-only audit behavior for financial decisions and settings changes.
- Keep operational codes stable in APIs. User-facing display text should come from locale files or install settings where appropriate.
- Prefer small, reviewable changes with focused tests.
- Keep generated runtime artifacts out of git, including QA/demo outputs.
- **User file I/O:** imports and exports go through the UI; runtime user files live under external `DATA_ROOT` (default: public user directory; installer: profile or local/UNC path — [#108](https://github.com/mlddragon/family-finance-os/issues/108)); app-internal shipped assets stay in the image/package; QA runtime fixtures are materialized by `make qa-seed` (see `planning/architecture_decisions_v1.md` Decision 16, [#107](https://github.com/mlddragon/family-finance-os/issues/107)). Do not add runtime reads of `tests/fixtures/` from installed package paths.

## Testing And QA

- Run relevant automated tests before opening or updating a PR.
- Keep CI synthetic-only and disposable.
- Add or update tests for behavior changes before implementation when practical.
- Human QA scripts should include scope, preconditions, exact steps, expected results, stop conditions, and known intentional gaps.

## Review guidelines

Codex GitHub code review reads this section from `AGENTS.md`. Codex is the **security and privacy analyst**, not the primary implementer.

- Flag only **P0** and **P1** issues in GitHub reviews.
- **P0**: secret/credential exposure, raw financial data in git, public app binding, auth bypass, SQL injection, path traversal into `DATA_ROOT`, missing protection for sensitive exports.
- **P1**: weakened `.gitignore` or CI security checks, new external data transmission, dependency with known critical CVE, audit log bypass, personal/QA data-root confusion, Docker/network exposure regressions.
- **P2+**: style, refactors, feature gaps — note briefly but do not block merge.
- On every PR, check: sensitive-artifact boundaries, `DATA_ROOT` / `APP_ENV` separation, new dependencies (supply chain, egress, license), Docker/network exposure, auth/permissions/audit integrity.
- Do not suggest feature work or refactors unless they fix a confirmed P0/P1 finding.
- Do not request or reproduce real household financial data in review comments.

Subscription setup: [docs/runbooks/codex-subscription-setup.md](docs/runbooks/codex-subscription-setup.md). Request reviews manually with `@codex review` only — **automatic reviews stay off** unless the owner enables them.

## Codex Review Guidelines

Codex acts as security and privacy analyst, not primary engineer.

### Priority definitions

- **P0**: Secret or credential exposure, raw financial data in git, public binding of the local app, auth bypass, SQL injection, path traversal into `DATA_ROOT`, missing protection for sensitive exports.
- **P1**: Weakened `.gitignore` or CI security checks, new external data transmission, dependency with known critical CVE, audit log bypass, personal/QA data-root confusion, Docker/network exposure regressions.
- **P2+**: Style, refactors, feature gaps — note but do not block merge.

### Required review focus on every PR

- Sensitive-artifact and secret-pattern boundaries.
- `DATA_ROOT` / `APP_ENV` separation between personal and QA runtimes.
- New dependencies: supply chain, network egress, license compatibility.
- Docker and network exposure changes.
- Auth, permissions, actor context, and audit trail integrity.

### Out of scope for Codex

- Feature implementation unless explicitly requested to fix a confirmed P0/P1 finding.
- Product architecture decisions.
- Routine refactors without security impact.

## Current Defaults

- Local personal runtime defaults to Docker on `127.0.0.1`.
- QA/demo runtime must be visibly distinct from personal runtime and must use synthetic data only.
- The default product name is `Family Finance OS`.
- GitHub home (after rehome): `mlddragon/family-finance-os`.

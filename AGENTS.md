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

## Workflow And Review

- Create a feature branch for meaningful work and use GitHub pull requests for traceability.
- Do not push directly to `main`.
- Include a human QA script in PR notes for app behavior, UI, API, Docker, import, review, report, or data-integrity changes.
- Stop for owner review on impactful product/architecture decisions, data-integrity/security/privacy decisions, and cost-bearing decisions.
- Make routine low-impact engineering decisions directly when they fit the approved stack and repository patterns.

## Engineering Guardrails

- Keep v1 local-first and Docker-friendly unless the owner approves a different runtime direction.
- Preserve append-only audit behavior for financial decisions and settings changes.
- Keep operational codes stable in APIs. User-facing display text should come from locale files or install settings where appropriate.
- Prefer small, reviewable changes with focused tests.
- Keep generated runtime artifacts out of git, including QA/demo outputs.

## Testing And QA

- Run relevant automated tests before opening or updating a PR.
- Keep CI synthetic-only and disposable.
- Add or update tests for behavior changes before implementation when practical.
- Human QA scripts should include scope, preconditions, exact steps, expected results, stop conditions, and known intentional gaps.

## Current Defaults

- Local personal runtime defaults to Docker on `127.0.0.1`.
- QA/demo runtime must be visibly distinct from personal runtime and must use synthetic data only.
- The default product name is `Family Finance OS`.

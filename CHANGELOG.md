# Changelog

All notable changes to Family Finance OS will be tracked here.

## 0.4.0 - Planned

- Rehome GitHub repository to `mlddragon/family-finance-os`.
- Rename Python package to `family_finance_os` and default SQLite file to `family_finance_os.sqlite3` with legacy `dillon_finances.sqlite3` fallback.
- Replace runtime env vars with `FFOS_*` while keeping one-release Compose fallbacks for `DILLON_FINANCES_*`.
- Add dedicated Security CI workflow, agent entrypoints, and Codex security-analyst role guidance.
- Archive prior prototype repository `Family_Finance_planner` as private research reference.

## 0.3.0 - Planned

- Add root AI-agent guidance through `AGENTS.md`, `CODEX.md`, and `CHATGPT.md`.
- Improve Settings usability by hiding read-only settings by default.
- Show friendly setting names, current values, and default values in the default Settings table.
- Add optional Settings table columns for changed status, domain, setting key, and editable status.
- Show saved notes in Settings audit history.
- Add personal/QA runtime identity with visible UI environment markers.
- Move personal Docker default to `127.0.0.1:28080` and add QA synthetic default at `127.0.0.1:28081`.
- Add script-level QA reset/seed foundation with one `baseline` synthetic scenario.
- Add synthetic markers to QA-generated reports, close bundles, advisor exports, and scenario manifests.
- Add lightweight local actor/persona context for future audit and permissions work.
- Document deferred permission matrix, elevated mode, suggestions, approvals, and view-as decisions.
- Update the PRD immediate roadmap to reflect the current Docker/SQLite product path.

## 0.2.0 - 2026-06-21

- Add AGPL-3.0-only licensing and basic contribution/security guidance.
- Add i18n scaffolding with maintained `en-US` resources.
- Replace owner-specific runtime defaults with generic install settings.
- Add SQLite-backed branding, household, locale, operator, and report-title settings.
- Add stable system category keys, editable display labels/aliases, and custom category support.
- Treat Alliant and Chase source profiles as available templates instead of required fresh-install sources.
- Add safety checks for owner-specific runtime defaults.

## 0.1.0 - 2026-06-20

- Baseline local Docker MVP.
- FastAPI backend, React/Vite frontend, SQLite operational state, and synthetic-data CI checks.
- Source ingestion, validation, quarantine/void, normalization, review decisions, reports, monthly close, advisor export, and local Docker E2E path.

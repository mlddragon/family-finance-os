# Changelog

All notable changes to Family Finance OS will be tracked here.

## 0.2.0 - Planned

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

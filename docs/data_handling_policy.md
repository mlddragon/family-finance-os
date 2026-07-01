# Data Handling Policy

## Purpose

This policy defines what belongs in the Dillon Finances repository during planning and future implementation.

## Allowed In Git

- Product requirements.
- Planning documents.
- Architecture decision records after owner approval.
- Source code after implementation begins.
- Empty templates and synthetic fixtures.
- Non-sensitive configuration examples.
- Tests using synthetic data only.

## Not Allowed In Git

- Raw financial exports.
- Normalized financial data.
- Generated financial reports.
- Real account snapshots.
- Real review decisions.
- Real receipts, statements, order exports, or PDFs.
- Credentials, tokens, cookies, browser profiles, or session state.
- AI transcripts containing transaction-level or item-level financial details unless explicitly approved and sanitized.

## Synthetic Test Data

Synthetic fixtures must be obviously fake. They should use:

- Fake merchants.
- Fake accounts.
- Fake dates and amounts.
- No real transaction descriptions.
- No real household names beyond approved project owner references in documentation.

## Data Directory Rule

If future tooling creates local data directories such as `raw/`, `normalized/`, `reports/`, `snapshots/`, `exports/`, or `imports/`, those directories remain untracked unless the owner explicitly approved a different plan.

## Runtime File Placement (owner 2026-06-30)

Three tiers:

1. **User file I/O** — Imports and exports flow through the application UI. Users do not routinely add or remove files directly from `DATA_ROOT` subfolders.
2. **`DATA_ROOT` (external, mounted)** — All user/runtime file artifacts (imports, raw copies, reports, exports, vendor inputs, quarantine, etc.) and the SQLite database. Never inside git.
3. **Docker image / package** — App-internal-only assets (static UI, locale, built-in templates). Not household financial data.
4. **QA seeding** — Committed synthetic *templates* may stay in git. Runtime copies required for Docker QA or full QA gates are materialized under `DATA_ROOT` by `make qa-seed`, not loaded from repo-relative paths in installed package code.

**Default location (owner 2026-06-30):** `DATA_ROOT` defaults to the host **public user directory**. A future installer ([#108](https://github.com/mlddragon/family-finance-os/issues/108)) lets the user choose the **current user profile** path or a **custom local or UNC network path**. Dev/Compose env overrides remain valid until the installer ships.

See `planning/owner_decision_record.md`, `planning/architecture_decisions_v1.md` Decision 16, and GitHub issues [#106](https://github.com/mlddragon/family-finance-os/issues/106) / [#107](https://github.com/mlddragon/family-finance-os/issues/107) / [#108](https://github.com/mlddragon/family-finance-os/issues/108).

## External Services

Any external service that may receive financial data is a data integrity, privacy, and security decision. It requires explicit owner review before implementation or use.

## AI Use

AI may help with product planning and implementation. AI access to financial data requires an explicit review gate and should prefer validated summaries over raw transaction detail.

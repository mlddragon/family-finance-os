# v1.1 Phase 1 Engineering Overview

## Purpose

Define the implementation-ready Phase 1 engineering frame for v1.1 before application code is written. This document turns the approved D1-D11 decisions into a track sequence, shared backend conventions, terminology lock, dependency map, and test strategy for the `0.6.0` target line.

v1.1 moves Family Finance OS from the v1 local operator console into a planning-aware household ledger with:

- Spendable balance and card obligation on Home.
- Fund pools, fund commitments, pool remaining, and reserved goal balance.
- Passphrase + TOTP authentication with recovery.
- Transaction allocations, receipt line items, manual net worth snapshots, and analyst export support.
- Append-only audit attribution to authenticated users.
- Local-first, synthetic-safe, Docker-friendly behavior.

The approved build order remains:

1. Schema + spendable engine + auth.
2. Funds, splits, net worth, analyst export.
3. Dashboard + charts.
4. Receipt manual/CSV.
5. Last: Amazon, Costco, and Walmart scraper framework/adapters.

## Non-goals

- No application code is specified as already implemented by this document.
- No banking credentials, hosted services, telemetry, OAuth, passkeys, email OTP, or external financial-data transmission.
- No per-user ledgers or household data silos in v1.1.
- No automatic promotion of receipt line items into transaction splits.
- No vendor scraper work before the core v1.1 ledger, UI, receipt, and close flows are stable.
- No real household financial data, screenshots, session files, recovery kits, or generated artifacts in git.

## Program Scope

Target version: `0.6.0` after the v1.0.0 stable / post-RC foundation.

Phase 1 docs cover:

- `A1`: Schema foundation for planning, spendable, auth, splits, receipts, net worth, and snapshots.
- `A2`: Spendable balance engine and Home/operator summary integration.
- `A3`: Local authentication, session, recovery, QA dev bypass, permission and audit integration.

Phase 1 must unblock later track docs and implementation without forcing later writers to reinvent shared model or API conventions.

## PR Sequence A1 -> E4

| PR | Track | Scope | Depends on | Notes |
| --- | --- | --- | --- | --- |
| A1 | Schema | Migration `0009` for finance planning tables and migration `0010` for auth tables if split for reviewability | Existing migrations `0001`-`0008` | Must land before A2, A3, B*, C*, D*, E*. |
| A2 | Spendable | Spendable service, `GET /api/spendable`, operator-summary additions, snapshot write path for monthly close | A1 finance tables | Can ship before Funds UI if seed fixtures create pools/goals/obligations. |
| A3 | Auth | Passphrase + TOTP + recovery, session middleware, first-boot owner enrollment, invitation flow, QA dev bypass | A1 auth tables or `0010`; existing permissions/elevated mode | Must protect API mutations before multi-user UI work. |
| B1 | Funds | Fund pool CRUD, monthly fund commitments, pool remaining, goal linking UI/API | A1, A2, A3 | Uses terminology lock from D2. |
| B2 | Splits | Transaction allocation API/UI, app-layer sum validation, decision event creation | A1, A3, B1 optional | Splits drive reports, pools, targets, and receipt reconciliation. |
| B3 | Net worth | Manual actual/estimate snapshots and dashboard/report read paths | A1, A3 | Estimates never feed Spendable balance. |
| B4 | Analyst export | Local-only export pack additions for v1.1 summaries | A1, A2, B1-B3 | Must preserve privacy boundary and explicit user action. |
| B5 | Monthly close | Close blockers/warnings for funds and spendable, snapshot bundle additions | A1, A2, B1-B4, existing close flow | Final close override requires Financial Governor elevation and audit. |
| C1 | Dashboard | Charts and dashboard tiles for cashflow, category spend, pools, net worth, confidence | A2, B1-B5 | Uses mockup Dashboard screen. |
| D1 | Receipts manual/CSV | Receipt headers, line items, CSV import/review queue, promote-to-split action | A1, A3, B2 | Receipt lines are enrichment until explicit split promotion. |
| E1 | Scraper framework | Local vendor scrape run records, credential/session artifact boundaries, shared adapter contract | D1, B2, B4 | Must be local `DATA_ROOT` only. |
| E2 | Amazon scraper | Amazon adapter using scraper framework | E1 | Runs after all other v1.1 core work is stable. |
| E3 | Costco scraper | Costco adapter using scraper framework | E1, E2 lessons | Same credential/session artifact gates. |
| E4 | Walmart scraper | Walmart adapter using scraper framework | E1-E3 lessons | Last adapter in this pass. |

## Shared Conventions

### Migration Numbering

- Existing Alembic revisions are `0001_create_audit_core` through `0008_suggestions_approvals`.
- v1.1 starts at `0009`.
- Use one finance-planning migration when feasible: `0009_v1_1_finance_planning_core`.
- Use a separate auth migration when review size or risk warrants it: `0010_v1_1_auth_core`.
- Continue explicit `revision`, `down_revision`, `branch_labels = None`, `depends_on = None`.
- Continue `_id_columns()` with:
  - `id` as `String(36)` primary key.
  - `created_at` as `String(40)` not null.
  - `updated_at` as `String(40)` not null.
- Use `String(10)` for ISO dates, `String(7)` for `YYYY-MM` months, `String(40)` for ISO timestamps, `Numeric(14, 2)` for money, `Text` for JSON payload text, and explicit indexes for common filters.
- Downgrades drop new tables in reverse dependency order and drop indexes before tables where Alembic requires it.
- Do not migrate financial data from prior prototypes or from local runtime artifacts.

### API Prefix Patterns

- Continue FastAPI route style in `apps/api/family_finance_os/main.py`.
- API routes use `/api/...`.
- Collection reads use `GET /api/<resource>`.
- Detail reads use `GET /api/<resource>/<id>`.
- Mutating commands use action-oriented POST routes when they are workflow actions:
  - Existing examples: `/api/import-batches/{id}/validate`, `/api/monthly-close/draft`, `/api/exports/advisor`.
  - v1.1 examples: `/api/transaction-allocations/{transaction_id}/replace`, `/api/receipts/{receipt_id}/apply-as-splits`.
- New responses should return stable machine codes plus human text when errors occur:
  - `detail.code`
  - `detail.message`
- UI client methods belong in `apps/web/src/api.ts` and should mirror existing `apiJson` error behavior.
- Stable operational identifiers stay in API/database values. User-facing display text belongs in locale/install settings where practical.

### Audit Event Patterns

- Imported ledger facts remain immutable. Do not mutate `imported_rows`.
- Human decisions remain append-only:
  - Transaction review/classification decisions continue through `decision_events`.
  - Settings changes continue through `settings_events`.
  - Permission changes continue through `permission_state_events`.
  - Elevated mode entries/exits continue through `elevated_mode_events`.
- v1.1 should use decision events for:
  - Transaction split replace/apply decisions.
  - Receipt line promotion to splits.
  - Goal reserved balance changes when user-directed.
  - Budget target and fund commitment changes when modeled as auditable planning decisions.
- All audited user actions must include authenticated user attribution after A3:
  - Legacy `actor` remains for compatibility where already present.
  - `actor_context_json` should include `user_id`, display name, role/persona/group keys, and auth source when available.
- Financial Governor elevated override is required for final monthly close when D9 blockers are present.

### Terminology Lock From D2

Use these terms verbatim in UI, docs, API display payloads, and test names where user-facing:

- Fund pool
- Fund commitment
- Spendable balance
- Reserved goal balance
- Pool remaining
- Provisional exposure
- Card obligation

Do not use these user-facing terms:

- envelope
- give every dollar a job
- available to spend
- age of money

Database names may use concise snake_case equivalents (`fund_pools`, `spendable_balance_snapshots`) but UI labels must use the locked terminology.

## Schema/API Touchpoints

- A1 creates the v1.1 schema foundation documented in `v1_1_a1_schema.md`.
- A2 reads:
  - `source_accounts`, `canonical_transactions`, `imported_rows`, `decision_events`.
  - `fund_pools`, `financial_goals`, `manual_obligations`, `spendable_balance_snapshots`.
- A3 reads/writes:
  - `users`, `user_sessions`, `totp_secrets`, `recovery_codes`.
  - Existing permission/elevated-mode/audit tables through actor context.
- Later tracks read/write:
  - `monthly_pool_commitments`, `transaction_allocations`, `budget_targets`, `receipts`, `receipt_line_items`, `net_worth_snapshots`.

## UI Touchpoints

Approved mockup screen IDs from `planning/mockups/v1_1/index.html`:

- `data-screen="home"`: Spendable balance, provisional exposure toggle, card obligation, fund commitment summary.
- `data-screen="funds"`: Fund pools, fund commitments, pool remaining, reserved goal balance.
- `data-screen="dashboard"`: Cashflow, category spend, pool target progress, net worth estimate toggle.
- `data-screen="split"`: Transaction allocation editor and audit preview.
- `data-screen="receipt"`: Manual receipt/line-item entry and save/start split actions.
- `data-screen="export"`: Analyst export privacy boundary and contents.
- `data-auth="login"`: Login, TOTP, recovery-code fallback, QA bypass variant.
- `data-auth="enroll"`: First-boot owner enrollment and recovery codes.

## Testing Strategy Per Track

### A1 Schema

- Alembic upgrade from `0008` to `head` on empty SQLite.
- Alembic downgrade from `head` to `0008`.
- ORM model smoke test creates one row per new table with synthetic values.
- Constraint/index tests for required goal name, unique keys, FK behavior, and cascade/no-cascade expectations.
- Sensitive-artifact checks remain green.

### A2 Spendable

- Unit tests for formula, provisional toggle, card obligation, stale data, missing balances, negative balances, over-reserved goals, and zero-data states.
- API tests for `GET /api/spendable`.
- Operator summary tests for added spendable payload.
- Monthly close tests for snapshot creation and D9 draft/final warnings/blockers.

### A3 Auth

- Unit tests for Argon2id passphrase hashing/verification, TOTP verification windows, recovery code one-time use, and session expiry.
- API integration tests for first-boot enrollment, login, logout, invitation acceptance, and recovery reset.
- Middleware tests for authenticated/unauthenticated API behavior.
- QA tests proving dev bypass is unavailable outside QA/DEV_MODE and visibly marked when active.
- Security checks for HttpOnly, SameSite=Strict, localhost-bound cookie behavior, and no secrets in git.

### B1-B5 Planning/Reporting

- Service tests for pool remaining, budget target math, split sum validation, goal-name validation, net worth actual-vs-estimate separation, export contents, and monthly close blockers.
- UI tests for screen copy and interaction states using locked terminology.
- Human QA scripts for each UI/API behavior PR.

### C1 Dashboard

- API-contract tests for dashboard data payloads.
- UI tests for chart rendering states, warning banners, estimate toggle, and provisional confidence labels.

### D1 Receipts

- Unit tests for receipt/header and line-item validation.
- Integration tests for receipt-to-transaction linking and explicit "apply receipt lines as splits" decision event.
- CSV import tests with synthetic-only fixtures.

### E1-E4 Scrapers

- Unit tests with synthetic HTML/export fixtures only.
- No credentials, cookies, browser profiles, or session artifacts in git.
- Human QA script per vendor using local `DATA_ROOT`.
- Audit tests for scrape runs and produced receipt lines.

## Open Questions

None for Phase 1 documentation. D1-D11 are approved for this pass. Implementation PRs may still surface low-level engineering choices, but they should stay within this document set and stop for owner review only if they change product, privacy, data-integrity, security, or cost-bearing decisions.

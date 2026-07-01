# Owner Decision Record

This document captures owner decisions from the interactive planning interview after the initial repository setup. It records product and architecture constraints only. It is not an implementation plan.

## Status

Updated 2026-06-30. The decision content below remains the owner-approved planning record; this section tracks current implementation alignment only.

- **User file I/O via UI only approved 2026-06-30:** all user-facing import and export flows through the application UI; runtime user files under external `DATA_ROOT`; app-internal shipped files in the Docker image; QA-only runtime fixtures generated via `make qa-seed`. Backport: [GitHub #107](https://github.com/mlddragon/family-finance-os/issues/107). Vendor synthetic collect seeding: [GitHub #106](https://github.com/mlddragon/family-finance-os/issues/106).
- **`DATA_ROOT` default location approved 2026-06-30:** default under the **public user directory** (platform-specific); future installer offers **current user profile** or **custom local/UNC drive** path. Tracking: [GitHub #108](https://github.com/mlddragon/family-finance-os/issues/108).

- v0.1.0 through v0.5.0 are implemented on the public `family-finance-os` repository (pyproject `0.5.0` after RC prep).
- Approved architecture direction is landed: local Docker Compose, browser UI, SQLite operational state, external `DATA_ROOT`, synthetic CI, personal/QA side-by-side runtimes.
- Personal instance: `ffos-personal` at `127.0.0.1:28080`. QA synthetic instance: `ffos-qa` at `127.0.0.1:28081` (legacy `dillon-*` Compose names deprecated).
- Permission enforcement (B.1), elevated mode (B.2), suggestions/approvals (B.3), and QA permission preview in Settings are implemented on synthetic QA. Authentication and true impersonation remain deferred.
- Issue #55 view-as direction approved 2026-06-25: non-mutating permission preview in B.1; true impersonation deferred. See `planning/issue_55_view_as_decision_record.md`.
- Owner real-data smoke is deferred until after `v1.0.0-rc.N` and explicit owner approval; use synthetic QA validation until then. See `docs/qa_validation_strategy.md`.
- Amazon vendor enrichment is explicitly **post-v1.0.0 stable** (v1.1 direction per `planning/first_closed_loop_slice_v1.md`).
- **Source profile manual confirmation removal approved 2026-06-30 (Option 1):** drop the Settings attestation step; per-import validate+accept is sufficient format verification. Remove spendable/monthly-close blockers tied to `pending_owner_sample`. Tracking: [GitHub #103](https://github.com/mlddragon/family-finance-os/issues/103). Supersedes [#102](https://github.com/mlddragon/family-finance-os/issues/102).
- Remaining owner approvals still gate cost-bearing tooling, cloud dependencies, AI data-access changes, credential automation, and major architecture shifts beyond the landed v1 foundation.

## Runtime And Deployment

- The first product target is Mason's Mac.
- The app should run through Docker from the beginning so it is portable to any machine that can run Docker.
- A future move to a local NAS running Docker is expected.
- Routine operation should be a local browser app served from Docker.
- The first product should run from the repo through Docker Compose.
- Later packaging can target a cleaner Mac, local, or NAS deployment bundle.
- A local development server is acceptable for planning and mockup review if it binds locally by default and does not expose financial data externally unless explicitly configured.
- Deployment should avoid cloud dependencies unless explicitly approved.
- Multi-device access is a later requirement, likely through local network or NAS hosting before any public internet access.

## Offline And Local-First Rules

- Once source exports are available locally, the core financial loop should run fully offline.
- Core loop includes import, validation, normalization, review, reporting, and export.
- Raw and transaction-level financial data are hard local-first by default.
- Redacted or aggregate summaries may be considered for hosting later only after explicit owner review.
- Raw transaction data should not leave the local Mac or NAS by default.
- Any exception requires explicit approval for purpose, destination, retention period, and deletion plan.
- Remote access is out of scope until the local Docker product is stable.

## Storage And Auditability

- A local database is acceptable for product state if important data remains exportable and auditable.
- SQLite is the likely durable application-state default.
- DuckDB may be considered later for heavier analytical/reporting queries.
- CSV should remain an import, export, audit, and interoperability format, not the long-term internal storage layer.
- Avoid opaque proprietary formats.
- Avoid cloud-only storage.
- Avoid spreadsheets as primary state.
- Avoid Parquet or Arrow as primary state for now unless a specific analytics need appears.
- Core operational state can live in SQLite.
- Controlled decisions, import summaries, validation results, reports, and audit exports must be human-readable and inspectable outside the app.

## UI Direction

- The first UI should be operator-focused.
- Household-facing views should come later after the core loop is proven.
- The UI should be browser-based and local, served from Docker.
- No desktop app is needed for the first product slice.
- Household-facing views should eventually use envelope-style language as a presentation layer.
- Envelope labels must map back to controlled categories or buckets and must not override ledger accuracy, validation, or review exposure.
- The first UI should start read-only.
- Review decisions should become the first controlled write workflow only after the data model and audit trail are approved.
- Household-facing views should hide ledger terminology by default.
- Operator views can expose ledger and audit detail.
- Sensitive merchant and item details should appear in operator/review views by default.
- Household-facing views should use category/envelope summaries unless detail is explicitly enabled.
- Operator view comes first, but navigation and future permission boundaries should allow separate family views later.

## UI Mockup Gates

Mockups are required and owner-approved before implementing:

- Operator dashboard/current status.
- Import and validation status.
- Review queue.
- Controlled decision/edit flow.
- Budget/cashflow reporting.
- Household envelope view before that feature is built.

## Data Privacy Boundaries

By default, the following should not leave the local Mac/NAS except under explicitly approved workflows:

- Raw exports.
- Transaction-level rows.
- Account identifiers.
- Credentials and session data.
- Receipt/order detail.
- Item titles.
- Review decisions.
- Household notes.

Credentials, tokens, passwords, browser sessions, and account-access artifacts remain out of scope for storage or AI processing unless separately reviewed. The default answer for account-access secrets is no.

## AI And Agent Role

- ChatGPT, OpenAI, and Codex are approved coworker tools for this project.
- The owner currently treats ChatGPT/OpenAI as an active financial analyst that may receive raw transaction data when explicitly fed for analysis.
- This is an approved exception to the local-first default.
- OpenAI access is task/context based: the system should not proactively send all data by default.
- Other AI providers or third-party services are not approved to receive raw transaction-level data unless explicitly approved later.
- A future locally hosted LLM may replace or reduce OpenAI raw-data access as the product matures.
- AI may propose category rules, review decisions, budget targets, and data corrections.
- Human approval is required before AI-proposed changes are applied.
- The system must keep an audit trail for AI-assisted recommendations and changes.
- Major financial recommendations should be blocked or explicitly provisional until relevant validation and review gates pass.
- This includes budget targets, spending cuts, reimbursement totals, medical/tax candidates, side-hustle profitability, net worth, retirement, debt payoff, and affordability decisions.
- AI recommendations should be stored as auditable artifacts with citations to validated outputs or source summaries.
- No new paid AI tooling, paid API usage, or recurring AI service should be added without explicit approval, estimated monthly cap, and data-processing scope.
- Existing ChatGPT/OpenAI use remains the approved exception. The owner does not want a separate cost document for that existing use.

## First Closed-Loop Sources

The first closed-loop slice should be staged:

1. Core ledger sources first:
   - Alliant checking.
   - Alliant savings.
   - Alliant credit card.
   - Chase Prime Visa.
2. Amazon enrichment second.
3. Walmart and Costco enrichment third through the same vendor-detail framework.

No known near-term institution or account changes affect this plan.

PDF statements are later reconciliation scope. The first slice should rely on exported transaction files.

## Import Expectations

- Manual downloads are acceptable for the first slice, but the product should reduce friction where reasonable.
- The product should include a guided import checklist before automated import connectors.
- Manual work should be simplified through predictable drop zones, stale/missing file detection, schema validation, freshness checks, and clear next actions.
- Browser-assisted vendor exports are acceptable when the user logs in manually.
- Browser-assisted flows must not store credentials or session artifacts in the repo.
- Captured vendor files should remain local and feed shared vendor schemas.
- Bank aggregation services are off limits by default unless explicitly approved as paid/external-data tools.

## Source Profile Confirmation

Approved 2026-06-30. **Option 1 — remove manual confirmation.**

- Do **not** require a one-time Settings attestation (`profile_confirmation_status` / “Confirm source sample”) before imports or reporting can be trusted.
- **Per-import validation** (header match, schema checks, validate+accept) is the runtime format gate.
- Remove operator-facing confirmation UI and downstream blockers (Spendable `unconfirmed_liquid_source`, monthly-close `unconfirmed_source_profiles`) tied to `pending_owner_sample`.
- Planning-era “confirm header samples before parser implementation” remains historical context in `planning/import_validation_contract_v1.md`; it is not a runtime workflow requirement.

Implementation tracking: [GitHub #103](https://github.com/mlddragon/family-finance-os/issues/103). Supersedes [#102](https://github.com/mlddragon/family-finance-os/issues/102).

## Review Workflow

- Mason performs v1 review decisions.
- AI may draft suggestions.
- Household-facing summaries can come later.
- Early versions require owner approval for all controlled-state updates.
- Later iterations may add automation for high-confidence changes after confidence thresholds, audit rules, and rollback behavior are reviewed.
- Review decisions must be reversible with visible history.
- History should include who, what, when, why, previous value, new value, source suggestion, and rollback path.

Controlled-state updates requiring early owner approval include:

- Category changes.
- Ledger transaction splits.
- Reimbursement status.
- Medical/tax status.
- Project assignment.
- Budget target enforcement.
- Vendor match acceptance.
- Delete/ignore decisions.
- Rules affecting future auto-classification.

## Splits And Vendor Item Detail

- Ledger transaction splits can be deferred for v1.
- Vendor item-level categorization/allocation is required for Amazon, Walmart, and Costco enrichment.
- Vendor item detail must remain enrichment/reporting detail and must not change account-ledger transaction grain.

## Review Queue Priority

The first review priority is:

1. Stale/validation issues.
2. Vendor item/category review.

## Net Worth And Retirement

- Net worth tracking is a later phase, not part of the first closed-loop slice.
- Manual balance snapshots are acceptable for early net worth.
- The long-term maturity goal is increasing automation until imports, validation, reporting, and alerts are largely automatic.
- Retirement account details and planning assumptions are deferred to the later retirement phase.
- Home and vehicle values may be included only after owner approval.
- Home and vehicle values must be labeled as estimates with source, date, and confidence.
- Until cashflow is stable, the product should not recommend increased retirement contributions, major discretionary purchases, new debt, refinancing/recasting, aggressive liquidity-draining debt payoff, project funding, or investment changes.

## Household User Experience

The future family-facing two-minute view should answer:

- Are we okay this month?
- What is left in key envelopes?
- What changed or spiked?
- What needs review?
- What is the next household action?

## Backup And Export

- Preferred backup target is NAS snapshots/backups plus optional local external drive.
- GitHub is only for code, docs, planning, and non-data files.
- Encrypted cloud backup may be considered later only with explicit approval.
- Monthly close should automatically generate an export bundle.
- The monthly close bundle should include validation summary, reports, review status, controlled decisions, and advisor memo.
- All controlled decisions must be exportable as human-readable files such as CSV/JSON plus Markdown summaries.
- Raw imports, monthly normalized snapshots, monthly close reports, and export bundles should be retained indefinitely unless an owner-approved archive/purge policy is created.
- Intermediate rebuilds can be replaceable.

## Delegation And Approval Boundaries

The owner wants direct approval for major architecture, privacy, cost, and data-integrity decisions. Codex should provide strong recommendations with a concise rationale and serious alternatives worth considering.

Direct owner approval is required for:

- Database/storage model.
- UI framework.
- Hosted/cloud components.
- External services.
- Paid tools.
- AI data-access policy changes.
- Import automation touching credentials or sessions.
- Data migration from the prior repo.
- Source-of-truth rules.
- Review-decision rules.
- Database choice.
- UI framework choice.
- Import automation approach.
- AI integration pattern.

Codex may make routine decisions without owner approval when they are:

- Free/open-source.
- Reversible.
- Inside an approved stack.
- Not material to architecture, privacy, cost, data integrity, or long-term maintainability.

Examples include file organization inside approved structure, test names, lint/format settings, small helper libraries inside an approved stack, documentation cleanup, and implementation details inside an approved plan.

Codex does not need approval for every small dependency. Codex must stop for approval before adding a dependency that is:

- Paid.
- Networked.
- Security-sensitive.
- Storage/database-related.
- UI-framework-level.
- AI-related.
- Credential-related.
- Hard to replace.

Cost-bearing approval is required for:

- New paid subscriptions.
- Metered APIs.
- Cloud services.
- Hosted databases.
- Paid dependencies.
- Paid bank/data connectors.
- Paid AI beyond the existing approved OpenAI/ChatGPT workflow.
- Any tool that creates recurring operational cost.

## User File I/O And Runtime File Placement

Approved 2026-06-30.

- All **user-facing** import and export files must flow through the **application UI**. Users must not add or remove files directly from application folders (`DATA_ROOT` subdirectories, inbox paths, export folders, vendor scrape inboxes, etc.) as part of normal operation.
- On the backend, user and runtime file artifacts (imports, raw copies, reports, exports, vendor collect inputs, quarantine, logs tied to user actions) live under **external `DATA_ROOT`**. Exact folder and subfolder layout is an engineering decision; design the tree for all eventual user file input and output.
- **App-internal-only** data (locale, static UI, JSON schema templates, built-in defaults—not household financial data) may live inside the **Docker image** / installed Python package.
- Committed **synthetic templates** may remain in git (`tests/fixtures/synthetic/`, seed script sources). Anything required at **runtime in Docker QA or full QA gates** that does not ship in the image must be **materialized under `DATA_ROOT`** by `make qa-seed` (and aligned E2E helpers such as `scripts/run_docker_e2e.py`), not resolved via repo-relative paths from installed package code.
- Direct filesystem access to `DATA_ROOT` remains acceptable for **backup, recovery, and operator disaster recovery** documentation—not for routine import/export workflow.

**Default location and installer (approved 2026-06-30):**

- By default, `DATA_ROOT` lives in the **public user directory** for the host OS—not inside the application install tree, Docker image, or git repo.
- When a full **installer** is implemented, it must let the owner choose:
  1. **Current user profile** — standard profile-accessible data location for the active user.
  2. **Custom drive location** — another local path or a **UNC network path** (e.g. `\\server\share\...` on Windows).
- Platform-specific default paths and Docker volume wiring are engineering decisions; illustrative examples appear in `planning/architecture_decisions_v1.md` Decision 16.
- Until the installer exists, dev/Compose may continue using explicit env overrides (e.g. `~/Dillon_Finances_Data`).

Implementation tracking:

- [GitHub #106](https://github.com/mlddragon/family-finance-os/issues/106) — vendor synthetic collect fixtures under `DATA_ROOT` + qa-seed (immediate Docker QA blocker).
- [GitHub #107](https://github.com/mlddragon/family-finance-os/issues/107) — backport across code, runbooks, and docs.
- [GitHub #108](https://github.com/mlddragon/family-finance-os/issues/108) — installer default public user directory + profile/custom local/UNC path selection.

## Automation Maturity Ladder

The product should mature through these stages:

1. Manual but guided.
2. Semi-automated with checklists and validation.
3. Automated where credentials, privacy, and operational risk are approved.
4. Mature steady state where periodic reports and alerts are generated automatically, and human review focuses on exceptions.

## Next Planning Step

The first architecture decision pass has been captured in `planning/architecture_decisions_v1.md`, and the first closed-loop slice has been captured in `planning/first_closed_loop_slice_v1.md`. The next planning step should produce the required UI mockups, write the data model and audit design proposal, or define the Alliant/Chase import validation contract before implementation planning.

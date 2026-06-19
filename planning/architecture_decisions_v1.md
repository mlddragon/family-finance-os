# Architecture Decisions v1

This document captures approved architecture direction for the first Dillon Finances implementation planning cycle. It is a planning artifact only. It does not start app implementation, create schema, add dependencies, or approve live AI integration.

## Status

- App implementation has not started.
- UI implementation has not started.
- Database schema has not been created.
- Framework and dependency installation has not started.
- The decisions below define the default architecture for the next implementation plan.
- Any change to these decisions should happen through a new branch and PR.

## Decision 1: Overall App Shape

Approved direction: Dockerized local modular monolith.

The first product should be a local browser app running through Docker. It should use a modular monolith shape: one coherent app/runtime at first, but with explicit internal API/service boundaries so the frontend, backend, and worker roles can split later without a rewrite.

Core shape:

- Docker Compose runtime.
- Local browser UI.
- FastAPI-style backend service layer.
- SQLite operational state in mounted local data outside git.
- Human-readable audit/export folders.
- Backend jobs for import, validation, normalization, enrichment, reporting, and exports.
- Read-only UI first; controlled writes later after data/audit model approval.

Why this was chosen:

This balances simplicity, privacy, portability, and long-term maintainability. It runs on Mason's Mac now, can move to a NAS later, keeps financial data local, and avoids recreating a patchwork script/project structure.

Serious alternatives considered:

- Separate API and frontend containers from day one: cleaner long term, but more moving parts before the core loop is proven.
- Python-only dashboard framework: faster for prototypes, but too close to the old Streamlit patch-project risk.
- Command-first pipeline with UI later: simpler technically, but delays review workflow and operator visibility.

Future migration note:

Moving from the modular monolith to separate frontend/backend containers should be low to moderate difficulty if UI code talks through stable APIs and domain logic stays out of page handlers.

## Decision 2: Backend/Core Technology

Approved direction: Python backend with FastAPI-style service boundaries.

Why this was chosen:

Python is a strong fit for ingestion, validation, financial data processing, reports, exports, and future AI-adjacent workflows. FastAPI is widely used, free/open-source, Docker-friendly, testable, and gives clear API contracts for a later frontend/backend split.

Serious alternatives considered:

- TypeScript/Node backend: good for UI-heavy products, weaker for data/reporting iteration.
- Django: robust and batteries-included, but heavier than needed unless admin/auth conventions become important early.
- Go or Rust: durable and deployable, but slower for this data-product iteration cycle.

## Decision 3: Frontend/UI Technology

Approved direction: React + TypeScript.

Why this was chosen:

The product needs a serious operator UI: review queues, filters, tables, validation status, controlled decision flows, settings, reports, and later household-facing views. React + TypeScript is common, well supported, long-term maintainable, and pairs cleanly with FastAPI.

Serious alternatives considered:

- Server-rendered templates with HTMX: simpler stack, but less flexible for rich review workflows.
- Svelte/SvelteKit: strong developer experience, but smaller ecosystem.
- Streamlit: good for prototypes, explicitly not selected as the product UI foundation.

UI implementation remains gated by approved mockups.

## Decision 4: Database And Analytics Storage

Approved direction: SQLite-only operational state for v1, with export-first auditability.

SQLite should hold durable application state. CSV, JSON, and Markdown are audit/export formats, not the internal source of truth. DuckDB is deferred as a later analytics decision gate if reporting complexity or performance requires it. Postgres is not needed early.

Why this was chosen:

SQLite is local-first, simple, durable, Docker/NAS-friendly, widely supported, and easy to back up as a file. It avoids CSV-as-state while preserving full exportability.

Serious alternatives considered:

- SQLite + DuckDB from the start: stronger analytics posture, more moving parts.
- Postgres in Docker: robust, but operationally heavier than needed.
- Files-only state: risks recreating the spreadsheet/CSV design problem.

## Decision 5: Data Directory And Persistence Layout

Approved direction: external mounted `DATA_ROOT` outside git.

Recommended layout:

```text
data_root/
  raw/
  inbox/
  processed/
  database/
  exports/
  reports/
  monthly_close/
  logs/
  quarantine/
```

Directory roles:

- `raw/`: preserved source exports.
- `inbox/`: new files waiting for import.
- `processed/`: imported copies or normalized import artifacts.
- `database/`: SQLite database.
- `exports/`: human-readable controlled-state exports.
- `reports/`: regenerated reports.
- `monthly_close/`: immutable monthly close bundles.
- `logs/`: local logs.
- `quarantine/`: files that fail validation or need owner attention.

Runtime guardrail:

The app should refuse to run if financial data storage is configured inside the git repo.

Serious alternatives considered:

- Data folders under the repo but gitignored: simpler, but higher accidental-commit risk.
- One flat data folder: simpler initially, messy quickly.

## Decision 6: Job Execution Model

Approved direction: in-process backend jobs for v1, with durable job records in SQLite.

Jobs include import, validation, normalization, enrichment, reporting, export, and monthly close generation. Each job should create a durable record with status, timestamps, inputs, outputs, validation results, errors, and artifact links.

Why this was chosen:

It keeps v1 operationally simple while still creating audit visibility. The domain logic can later move to a worker container if jobs become slow, scheduled, or NAS-oriented.

Serious alternatives considered:

- Separate worker container from day one: cleaner for long-running jobs, but extra operational overhead.
- Redis/RQ/Celery: powerful, unnecessary for v1.
- Command-only scripts: weaker product loop and weaker audit visibility.

## Decision 7: Import Workflow Boundary

Approved direction: guided manual imports first.

Flow:

1. User manually downloads bank/vendor exports.
2. User places files in `DATA_ROOT/inbox/` or uploads through the local UI.
3. App detects candidate files.
4. App identifies source type where possible.
5. App validates schema, freshness, duplicates, and expected fields.
6. App preserves raw files.
7. App writes import batch records and validation results.
8. Invalid or ambiguous files go to `quarantine/` with a clear next action.

Boundaries:

- No stored bank credentials.
- No bank aggregators.
- Browser-assisted vendor capture can be designed later under the vendor plugin framework.

Serious alternatives considered:

- Direct bank/vendor connectors now: too much privacy, cost, and vendor-lock-in risk.
- Filesystem-only, no upload UI: simpler but less friendly.
- Browser-assisted vendor capture for all vendors immediately: too much scope before the core loop is proven.

## Decision 8: Reporting And Export Model

Approved direction: database-backed reports with file exports as durable artifacts.

Reports are generated by backend jobs from validated SQLite-backed state. Each report run records inputs, validation status, generated files, timestamps, and errors. Reports export to Markdown for narrative and CSV/JSON for tables. Monthly close creates immutable bundles under `monthly_close/YYYY-MM/`.

Why this was chosen:

It prevents generated reports from becoming hidden app state while preserving inspectability for Mason, Codex, and ChatGPT/OpenAI analysis workflows.

Serious alternatives considered:

- Reports only in the database: easier for app querying, weaker auditability.
- Reports only as files: human-readable, but risks CSV-as-state confusion.
- BI/dashboard tool: overkill and likely privacy/maintenance burden for v1.

## Decision 9: Review And Controlled Writes

Approved direction: read-only UI first, then append-only review decision events for controlled writes.

When controlled writes are enabled, every write should create an append-only decision event with:

- Previous value.
- Proposed value.
- Approved value.
- Reviewer/actor.
- Timestamp.
- Reason.
- Source suggestion, if any.
- Rollback linkage.

Current state should be derived from events rather than silently overwriting facts.

Why this was chosen:

This protects ledger integrity and allows AI/UI suggestions without silent mutation.

Serious alternatives considered:

- Direct row updates: simpler, but loses auditability and rollback clarity.
- Manual CSV override files only: auditable, but less product-like and harder to evolve.
- Full event sourcing everywhere: rigorous, but too heavy for v1.

## Decision 10: Vendor Enrichment Boundary

Approved direction: minimal vendor plugin contract.

Vendor plugins should follow the conceptual stages:

```text
discover -> extract -> normalize -> validate -> match -> enrich -> review -> report
```

Staging:

1. Core ledger imports first.
2. Amazon plugin first because prototype learning exists.
3. Walmart and Costco next through the same contract.

Core ledger should consume canonical vendor outputs:

- Order/receipt headers.
- Item/detail rows.
- Financial components.
- Match records.
- Review queues.
- Reporting allocations.

Ledger rule:

Vendor item rows enrich reporting but never become account-ledger transactions.

Serious alternatives considered:

- Build Amazon directly first and abstract later: faster short-term, high sprawl risk.
- Fully generic plugin framework before any vendor works: cleaner, but likely over-abstracted.
- Separate repo/package per vendor: premature.

## Decision 11: AI Integration Boundary

Approved direction: no live AI integration in v1, but include provider-agnostic LLM boundary scaffolding in design.

V1 should not wire OpenAI API, local LLM calls, credentials, model configs, or paid/networked AI dependencies into the runtime.

Design may include:

- Provider-neutral interfaces.
- Request/response shapes.
- Approval gates.
- Stubs.
- Pseudocode.
- Artifact and citation expectations.

Likely future providers:

- OpenAI API.
- Locally hosted open-source model.

Boundaries:

- No proactive data sending.
- No model execution until explicit later approval.
- AI recommendations, when later implemented, must be auditable and citation-backed.
- Human approval remains required before AI-proposed changes enter controlled state.

Why this was chosen:

It keeps v1 clean while preventing a future rewrite when AI integration becomes real.

Serious alternatives considered:

- Built-in OpenAI API integration from v1: convenient, but adds cost, network behavior, and sensitive-data controls too early.
- No AI boundary at all: too restrictive and mismatched with the intended product direction.
- Local LLM first: attractive long term, not practical yet.

## Decision 12: Docker Runtime Shape

Approved direction: single app container via Docker Compose for v1.

Runtime shape:

```text
docker-compose.yml
  app:
    FastAPI backend + served React build
    mounts external DATA_ROOT
    binds to 127.0.0.1 by default
```

Guardrails:

- `DATA_ROOT` must be mounted and outside git.
- Default bind address is `127.0.0.1`.
- NAS/local-network exposure requires explicit configuration.
- No secrets required for v1.
- No raw data copied into the image.
- Clean boundaries should allow later split into API, web, and worker containers.

Serious alternatives considered:

- Separate frontend/backend containers from day one: more future-ready, but unnecessary early overhead.
- Add Postgres/Redis containers: not needed for SQLite/in-process jobs.
- Run directly on host without Docker: easier for dev, but conflicts with portability goal.

## Decision 13: Configuration And Policy Model

Approved direction: SQLite-backed active settings with a first-class Settings UI.

Settings/config should live in SQLite once the app exists. Normal review and editing should happen through a Settings UI, not hand-edited YAML/JSON files.

Rules:

- Settings changes validate before save.
- Every settings change creates an audit event.
- YAML/JSON exports are audit, backup, and interoperability artifacts.
- Repo-tracked config is limited to seed defaults, examples, schemas, and reference docs.

Configuration areas:

- Category taxonomy.
- Import source definitions.
- Vendor plugin settings.
- Review rules.
- Matching thresholds.
- Report settings.
- UI/display settings.

Serious alternatives considered:

- YAML files as active config: inspectable, harder to validate/edit/audit safely in-app.
- Database-only config with no exports: easy for app, too opaque.
- Repo-tracked household config: good for defaults, bad for real household settings.

## Decision 14: Authentication And Access Control

Approved direction: no login for localhost-only v1; actor-ready audit model.

Rules:

- App binds to `127.0.0.1` by default.
- No password/login while running only on Mason's Mac.
- No multi-user roles in v1.
- Audit/review records include an actor field for future identity support.
- LAN/NAS/network exposure requires a later explicit access-control decision.
- Settings should clearly show local-only versus network-exposed mode.

Serious alternatives considered:

- Basic local password from v1: safer if accidentally exposed, but adds secret management and friction.
- Full user accounts/roles now: premature.
- Rely only on network controls forever: unacceptable once LAN/NAS/multi-device access arrives.

## Decision 15: Monorepo Layout

Approved direction: single repo with clear top-level app, module, docs, planning, test, Docker, and script boundaries.

Conceptual future layout:

```text
Dillon_Finances/
  apps/
    api/
    web/
  packages/
    core/
    vendors/
    reports/
  docs/
  planning/
  tests/
  docker/
  scripts/
```

Implementation note:

Even if deployed as one container, code should be organized so API, web UI, domain core, vendor plugins, and reporting logic can evolve independently.

Serious alternatives considered:

- Flat Python-first repo: faster initially, higher script-sprawl risk.
- Separate frontend/backend repos: too much coordination overhead now.
- Everything under `src/`: workable, but less clear once React, FastAPI, vendor plugins, reports, and Docker all exist.

## Deferred Decisions And Explicit Gates

These decisions are not approved for implementation yet and require future owner review:

- Exact database schema.
- Detailed UI implementation specifications derived from approved mockups.
- Exact FastAPI project scaffold.
- Exact React tooling/build stack.
- Any new dependency installation.
- Any live AI integration or API key handling.
- Any local LLM integration.
- Any LAN/NAS exposure or authentication model.
- Any import automation touching credentials or browser sessions.
- Any migration of old prototype code.
- Any migration of raw, normalized, reviewed, or generated financial data.
- Any generated reports or source financial data entering git.

## Routine Decisions Codex May Make Later Inside An Approved Plan

After implementation planning is approved, Codex may make routine choices that are free/open-source, reversible, local-first, and not material to architecture, privacy, cost, data integrity, or long-term maintainability.

Examples:

- Internal file names inside the approved layout.
- Test names.
- Formatting/lint details.
- Small helper functions.
- Documentation cleanup.
- Implementation details inside an approved plan.

## Next Step

The first closed-loop slice has been captured in `planning/first_closed_loop_slice_v1.md`, the data model/audit design has been captured in `planning/data_model_audit_design_v1.md`, UI mockups have been approved in `planning/ui_mockups_v1.md`, the import validation contract has been captured in `planning/import_validation_contract_v1.md`, report/monthly close artifacts have been captured in `planning/report_monthly_close_artifacts_v1.md`, the test/validation strategy has been approved in `planning/test_validation_strategy_v1.md`, the settings/config audit design has been approved in `planning/settings_config_audit_design_v1.md`, the controlled decision event model has been approved in `planning/controlled_decision_event_model_v1.md`, and the v1 implementation plan has been drafted in `planning/v1_implementation_plan.md`. The next planning step is not implementation. It should be:

1. Owner review of `planning/v1_implementation_plan.md`.

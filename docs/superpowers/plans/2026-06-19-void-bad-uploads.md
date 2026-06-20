# Void Bad Uploads Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a v1-safe way to void bad import batches, with optional physical file destruction for non-accepted batches.

**Architecture:** Import batches gain a first-class void lifecycle that removes bad uploads from active workflow without erasing audit metadata. Optional file destruction deletes stored files only for non-accepted batches and records destruction metadata on source files plus append-only import batch events.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, SQLite, Pydantic, React/TypeScript, TanStack Query/Table, pytest, Vitest, Playwright.

---

### Task 1: Data Model And Migration

**Files:**
- Modify: `apps/api/dillon_finances/models.py`
- Modify: `apps/api/dillon_finances/migrations/versions/0001_create_audit_core.py`
- Create: `apps/api/dillon_finances/migrations/versions/0002_import_batch_void_events.py`
- Test: `tests/api/test_database_foundation.py`

- [x] Add `storage_status`, `destroyed_at`, `destroyed_by`, and `destroyed_reason` to `SourceFile`.
- [x] Add `ImportBatchEvent` with batch id, event type, actor, notes, and metadata JSON.
- [x] Add Alembic migration coverage for existing databases.
- [x] Test that the schema exposes source-file destruction metadata and import-batch events.

### Task 2: Backend Void Service And API

**Files:**
- Modify: `apps/api/dillon_finances/import_validation.py`
- Modify: `apps/api/dillon_finances/main.py`
- Test: `tests/api/test_import_validation.py`

- [x] Add `POST /api/import-batches/{id}/void`.
- [x] Require actor and reason.
- [x] Default to non-destructive void: mark batch/source files `voided`, resolve open batch validation findings, record an event, and keep files on disk.
- [x] Add optional `destroy_files`; when true, delete stored files only for non-accepted batches and record destruction metadata.
- [x] Block void/destruction for accepted batches in v1.
- [x] Ensure reports, source coverage, and active batch lists ignore voided batches through existing accepted-batch filters.

### Task 3: Web UI

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/App.tsx`
- Test: `apps/web/src/App.test.tsx`

- [x] Add a `Void upload` action in the import-batch action column for non-accepted batches.
- [x] Open a confirmation dialog with required reason and optional unchecked `Destroy stored files` checkbox.
- [x] Call the void API and refresh source, validation, summary, and transaction state.
- [x] Show a clear success message that distinguishes void-only from file destruction.

### Task 4: Verification And Docker Reload

**Files:**
- Existing verification scripts and Docker Compose only.

- [x] Run backend tests, artifact scans, security contract, web unit tests, audit, build, Playwright, and Docker e2e.
- [x] Restart the normal Docker app on `127.0.0.1:8080` with the new branch code.
- [ ] Push the branch and open a stacked PR.

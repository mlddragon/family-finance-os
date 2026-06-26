# v0.4.0 Elevated Mode Planning

This document covers GitHub issue #53: shared elevated mode for system administration and financial governance.

## Implementation Status

**B.2 backend (phase-b2-elevated-mode): implemented.**

- Shared elevated-mode lifecycle with `system_administration` and `financial_governance` contexts.
- Append-only `elevated_mode_events` audit table (entered, exited, expired).
- In-memory active sessions keyed by `X-Elevated-Session-Id` with 15-minute inactivity expiry.
- API: `GET/POST /api/elevated-mode/{status,enter,exit,touch}`.
- Permission integration: routine financial mutations denied while elevated; context-specific elevated saves remain allowed.
- UI, auth, and approval-rule mutation endpoints remain deferred.

Original planning content below remains the product source of truth for naming, purpose codes, and scope boundaries.

This document originally stated it does not implement elevated-mode UI, API behavior, authentication, RBAC enforcement, schema changes, migrations, approval mode, or runtime behavior. Backend API and schema portions are now implemented per B.2; UI and auth remain out of scope here.

## Recommendation

Use one shared mechanism named **Elevated mode** with separate elevated contexts:

- **System Administration elevated mode**
- **Financial Governance elevated mode**

This is clearer than `Admin mode`, which is too narrow, and `Manage mode`, which is too vague for audit and risk review.

## Shared Elevation Mechanism

Elevated mode should be one reusable lifecycle, not separate custom flows per feature area.

Entering elevated mode should require:

- eligible future permission for the selected elevated context
- no unsaved workflow edits in the current screen
- a selected purpose from a controlled dropdown
- a required note
- an audit event before elevated controls become available

Only one elevated context should be active at a time. Switching contexts should require exit and re-entry with a new purpose and note.

Elevated mode expires after **15 minutes of inactivity**. Expiry should remove elevated authority, write an expiry audit event, and require a fresh entry before any elevated save. Expiry must not auto-save pending edits.

## Purpose Dropdown And Required Note

The purpose dropdown should use stable internal codes with plain-language display labels.

Recommended System Administration purposes:

- user, group, or permission management
- source or system settings
- maintenance or health review
- runtime troubleshooting

Recommended Financial Governance purposes:

- approval-rule change
- governance setting change
- threshold or risk-rule review
- monthly-close governance review

The note is always required when entering elevated mode. Approval-rule changes also require their own owner note every time, even if the elevation entry note already exists.

## System Administration Elevated Mode

System Administration elevated mode is for control-plane administration:

- users, groups, personas, and future permissions
- system and source administration settings
- maintenance, runtime health, and troubleshooting
- enough read-only system state to diagnose problems

Administrator access must not become the default authority for routine financial-data work. While this mode is active, routine financial workflows remain read-only.

Source settings need later implementation care: ordinary source-display settings may be administrative, while source settings that materially affect financial readiness, validation, or reporting may need Financial Governance review or owner-approved approval rules.

## Financial Governance Elevated Mode

Financial Governance elevated mode is for high-risk financial controls:

- approval rules
- approval-mode governance settings, once separately approved
- financial governance thresholds and policy controls
- future controls that affect review, close, export, or approval readiness

Finance Manager should remain the highest financial-data authority. This mode is not a shortcut for editing transactions, imports, review decisions, or reports.

## Read-Only Financial Workflows While Elevated

While any elevated mode is active, routine financial workflows should be read-only unless a later owner-approved design explicitly says otherwise.

Read-only workflows include:

- import and quarantine actions
- transaction review decisions
- routine category, reimbursement, medical, project, and side-hustle review edits
- monthly close finalization
- report or advisor-export generation

This prevents control-plane work from being mixed with normal financial operations in the same session.

## Audit Events

The shared mechanism should create append-only audit events for:

- elevated mode entered
- elevated mode exited
- elevated mode expired

Each event should capture:

- actor context
- elevated context
- purpose
- required note
- timestamp
- session or correlation id
- exit or expiry reason where applicable

Audit payloads should avoid raw financial data and should preserve stable operational codes.

## Owner Review Gates

Owner review is required before implementation for:

- final naming and purpose-dropdown values
- permission eligibility for each elevated context
- audit event schema or migration design
- any auth, RBAC, login, or enforcement behavior
- any ability for Administrator to edit routine financial data
- any ability for Financial Governance mode to change ordinary transaction workflow state
- approval-rule families, defaults, thresholds, and second-person approval behavior
- any hosted, networked, AI-provider, or cost-bearing dependency

## Deferred Items

Deferred out of this planning PR:

- elevated-mode UI/API implementation
- auth, login, RBAC, and permission enforcement
- schema changes and migrations
- approval queue and suggestions queue lifecycle
- optional approval mode implementation
- view-as, impersonation, and permission simulation
- second-person approval workflows
- recovery behavior for stale elevated drafts
- runtime session enforcement details

## Human QA Script

### Scope

Confirm this PR only adds planning for GitHub issue #53 and does not implement elevated mode or change app behavior.

### Preconditions

- Review this PR after or alongside PRs #60 and #61.
- Use repository files only; do not run against real financial data.
- No local app URL is required because this is planning-only.

### Steps

1. Review the PR diff and confirm it is limited to planning documentation.
2. Confirm the document references issue #53 and states that it is planning-only.
3. Confirm it recommends one shared elevated-mode mechanism with System Administration and Financial Governance contexts.
4. Confirm it includes purpose dropdown, required note, 15-minute inactivity expiry, and enter/exit/expiry audit events.
5. Confirm it says unsaved workflow edits block elevation.
6. Confirm it says routine financial workflows are read-only while elevated.
7. Confirm it says approval-rule changes always require notes.
8. Confirm owner review gates and deferred items are explicit.
9. Confirm no UI, API, auth, RBAC, schema, migration, runtime, financial data, generated report, database, log, or credential files are changed.

### Expected Results

- The PR is decision-ready for owner review.
- The plan matches the Administrator versus Finance Manager split.
- No implementer would need to invent elevated-mode lifecycle, naming, audit, timeout, or scope rules.
- No runtime behavior changes are included.

### Stop Conditions

- Stop if the PR changes app behavior, schemas, migrations, auth, RBAC, or runtime code.
- Stop if Administrator can perform routine financial edits by default.
- Stop if approval-rule changes can happen without notes.
- Stop if real financial data or generated runtime artifacts appear in git.

### Notes

This QA script uses documentation review only. Implementation verification belongs to a later implementation PR after owner approval.

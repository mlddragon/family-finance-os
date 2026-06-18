# Controlled Decision Event Model v1

This document defines the proposed v1 controlled decision event model for Dillon Finances. It is a planning artifact only. It does not create app code, database schema, dependencies, migrations, settings/config files, credentials, generated artifacts, or financial data.

## Status

- Approved by owner for v1 planning on 2026-06-18.
- App implementation has not started.
- Controlled-write implementation has not started.
- Database schema has not been created.
- No raw exports, normalized data, reviewed data, decision records, generated reports, or credentials have been added.
- This document should guide the later implementation plan and first controlled-write workflow.

## Recommendation

Strong recommendation: make v1 controlled ledger review decisions append-only events attached to canonical transactions, not edits to imported rows. The first controlled write path should be narrow: owner-approved classification and review-status decisions from the review UI, with rollback handled by new superseding/revert events.

This is the right shape for a family financial operating system because the product needs to preserve source evidence while still letting the owner make judgment calls. It avoids the old prototype risk of review decisions becoming patch files or mutated rows that are hard to audit, reverse, or explain during monthly close.

Serious alternatives considered:

- Directly update reviewed fields on transaction rows: simpler for early UI work, but loses history and makes rollback/audit weaker.
- Store decisions in manual CSV override files: inspectable, but too close to the old spreadsheet/script process and weaker for durable UI workflows.
- Full generic event sourcing for every object from day one: rigorous, but too heavy before the v1 ledger loop is proven.

## Product Goal

The event model must prove that owner judgment can enter the product without becoming hidden mutation.

It should support:

- Owner-approved review decisions.
- Clear audit history.
- Reversal and supersession.
- Derived reviewed/current state.
- Report and monthly close reproducibility.
- Human-readable decision exports.
- Future AI/rule suggestions that remain proposals until owner approval.

## v1 Controlled Write Scope

v1 controlled write scope is intentionally narrow.

Allowed v1 ledger decision event types:

- Category change.
- Subcategory change.
- Review status change.
- Review reason change.
- Transfer flag/status.
- Reimbursement candidate/status.
- Medical/tax candidate/status.
- Project candidate flag.
- Side-hustle candidate flag.

Deferred controlled decisions:

- Ledger transaction splits.
- Delete/ignore ledger decisions.
- Vendor match acceptance.
- Vendor item category allocation.
- Budget target enforcement.
- Auto-classification rules.
- Automated high-confidence changes.
- Net worth or retirement planning assumptions.

Settings changes are covered by `planning/settings_config_audit_design_v1.md`. They should use the same append-only audit posture, but the first closed-loop success criterion for controlled writes is a ledger classification decision event.

## Decision Target

Recommended default: ledger classification decisions attach to canonical transactions.

Why:

- Canonical transactions represent the real-world ledger transaction across overlapping imports.
- Reports should use canonical transactions to avoid double-counting.
- Imported rows remain evidence and should not receive human review mutations.

Rules:

- Imported rows are never overwritten by review decisions.
- Canonical transaction identity drives reporting and decision attachment.
- Decision details may reference imported row ids, source file ids, and validation finding ids as evidence.
- Ambiguous canonical identity blocks decision application until validation resolves the ambiguity.

## Event Contract

Each controlled decision event should capture:

- Event id.
- Event family: ledger decision, validation resolution, settings event, close event, or future proposal event.
- Event type.
- Target type.
- Target id.
- Field or fields changed.
- Previous derived value.
- Proposed value.
- Approved value.
- Actor.
- Reason or note.
- Source of suggestion: owner, rule, import heuristic, Codex, future AI proposal.
- Evidence references.
- Validation status at decision time.
- Created timestamp.
- Supersedes or reverts event id when applicable.
- Decision batch id when multiple events are approved together.

This is not a schema specification. Exact table names, column names, indexes, and JSON structure remain deferred to implementation planning.

## Event Immutability

Rules:

- Decision events are never edited.
- Corrections create new events.
- Rollback creates a new event that reverts or supersedes a prior event.
- Superseded events remain visible in audit history.
- Current reviewed state is derived from active/latest events.
- Monthly close records the decision event range or snapshot it used.

The UI should never imply that imported facts changed. It should show imported facts, current derived state, proposed decision, and audit preview separately.

## Owner Approval And Save Behavior

Recommended default: every v1 controlled decision requires explicit owner save action.

Save flow:

1. UI shows imported fact and current derived state.
2. UI shows proposed decision.
3. UI shows audit preview.
4. Owner saves the decision.
5. Backend validates the target and decision.
6. Backend writes append-only event.
7. Reviewed/current state updates through derivation.

Batch behavior:

- v1 may support approving multiple selected decisions only if the UI shows a clear audit preview for the batch.
- Batch approval should create either one decision batch record plus per-target events, or a clearly linked event group.
- No hidden bulk auto-apply.

Notes:

- A short reason can be prefilled from the review reason for routine category decisions.
- Owner-entered notes should be optional for routine category decisions.
- Owner-entered notes should be required for high-impact decisions.

High-impact decision examples:

- Marking a transaction as reimbursement-related.
- Marking a transaction as medical/tax-related.
- Marking a transaction as side-hustle/project-related.
- Reverting or superseding a prior owner decision.
- Any future delete/ignore decision.
- Any future automated or AI-suggested decision approval.

## Validation Before Save

Every proposed decision should validate before save.

Validation should check:

- Target exists.
- Target is a canonical transaction, not a raw/imported row mutation.
- Target canonical identity is not ambiguous.
- Target is not blocked by unresolved validation that prevents safe review.
- Field is allowed for v1.
- Approved value is a valid controlled value.
- Category/subcategory combination is valid.
- Decision does not conflict with existing active decision state.
- Required note exists for high-impact changes.
- User action is explicit.

Severity:

- Info: context only.
- Warning: save can proceed with visible acknowledgment.
- Blocking: save is prevented until fixed.

## Derived Reviewed State

Reviewed/current transaction state should be derived from:

- Canonical transactions.
- Imported fact references.
- Active/latest decision events.
- Validation state.
- Active settings snapshot where relevant.

Rules:

- Imported facts remain immutable.
- Active decision events overlay reviewed fields.
- Superseded/reverted events remain in history but do not define current state.
- Report queries use reviewed/current state plus validation/provisional state.
- Detail views can show both original imported value and current reviewed value.

Materialized current-state tables may be added later only if measured performance requires them. If added, they are rebuildable derived state, not the source of truth.

## AI And Rule Suggestions

Recommended default: suggestions are not decisions.

Rules:

- Rule/import/Codex/future-AI suggestions can populate proposed values.
- Suggestions must cite evidence or explain their source when available.
- Suggestions cannot update controlled state without owner approval.
- No live AI API calls are included in v1.
- Future AI-generated proposals require separate privacy, cost, data-scope, and audit approval.

## Exports And Monthly Close

Decision events should be exportable and included in monthly close context.

Exports should include:

- Decision event export as JSON or CSV.
- Human-readable Markdown decision summary.
- Decision event range or snapshot id used by report runs.
- Superseded/reverted decision visibility.
- Actor, reason/note, timestamp, and source suggestion.

Monthly close should capture:

- Decision event range or snapshot id.
- Reviewed transaction export.
- Open review exposure.
- Decision event export.
- Settings snapshot.
- Validation state.

Generated exports remain under `DATA_ROOT`, outside git.

## UI Behavior

The review UI should show:

- Imported fact.
- Current derived state.
- Proposed decision.
- Validation status.
- Audit preview.
- Required note indicator when applicable.
- Save, skip, and audit history actions.

The transaction detail UI should show:

- Canonical transaction id.
- Imported row/source file references.
- Active decisions.
- Superseded/reverted decisions.
- Validation findings.
- Report inclusion references where useful.

Disabled states:

- Save disabled when target identity is ambiguous.
- Save disabled when the decision field is outside v1 scope.
- Save disabled when required note is missing.
- Save disabled when unresolved blocking validation prevents safe decision application.

## Relationship To Validation Resolution

Validation findings are first-class records. Some validation findings may need owner resolution decisions later.

v1 recommendation:

- Ledger classification decisions are the first controlled write path.
- Validation resolution actions can be designed as the same event-family pattern, but should remain narrower than general review decisions.
- Blocking duplicate/canonical identity findings should be resolved before ledger classification decisions attach to affected targets.

## Owner Review Gates

Approved owner decisions:

- v1 ledger review decisions should attach to canonical transactions, not imported rows.
- v1 controlled write scope should stay limited to classification, review status/reason, and review flags.
- Every v1 controlled decision requires explicit owner save action.
- Routine category decisions may use optional notes, while high-impact decisions require an owner note.
- Rollback/correction should create new superseding or revert events rather than editing prior events.
- AI/rule/Codex suggestions remain proposals until owner approval.
- Decision event exports and monthly close snapshots are required.

Data integrity gates during implementation:

- Stop before directly mutating imported ledger facts for review decisions.
- Stop before allowing controlled decisions on ambiguous canonical transactions.
- Stop before adding automated high-confidence changes.
- Stop before adding delete/ignore behavior.
- Stop before adding live AI/provider decision writes.
- Stop before omitting decision history from reports/monthly close exports.

## Non-Goals

- No app implementation.
- No database schema.
- No event table or migration.
- No frontend write workflow.
- No test implementation.
- No generated exports.
- No financial data.
- No old override file migration.
- No automatic decision application.
- No live AI/API integration.
- No transaction splits.
- No vendor item review.
- No delete/ignore decisions.

## Recommended Next Step

Codex can prepare the implementation plan after confirming no planning gates remain open. App implementation remains blocked until that implementation plan is approved.

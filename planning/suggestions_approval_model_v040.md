# Suggestions And Approval Model v0.4.0

This is a planning-only document for GitHub issues [#52](https://github.com/mlddragon/Dillon_Finances/issues/52) and [#54](https://github.com/mlddragon/Dillon_Finances/issues/54). It does not implement an approval engine, suggestions queue UI/API, schema, migrations, authentication, RBAC enforcement, or runtime behavior.

## Recommendation

Use two separate concepts:

- **Suggestion:** an advisory proposal. It is never effective controlled state by itself.
- **Approval request:** a first-class governance object waiting for an eligible second-person decision.

This preserves ledger integrity, keeps approval mode optional, and lets low-risk recommendation workflows exist without pretending every suggestion is a formal approval.

## Suggestions Vs Approvals Boundary

Suggestions can come from a contributor, Financial Analyst, import heuristic, rule, Codex, or future AI. They may prefill proposed values, but they cannot mutate imported facts, reviewed state, settings, reports, exports, or monthly close state.

Approval requests are created only when policy requires second-person control or when a user without direct authority proposes a controlled action. The approvals queue contains formal pending requests, not general recommendations.

Default role direction:

- Finance Manager remains the highest financial-data authority.
- Administrator manages system administration and should not become the default owner of financial-data actions.
- Financial Analyst may create recommendations/suggestions in allowed scopes but cannot approve by default.
- AI/system suggestions require human action before affecting controlled state.

## Suggestion Lifecycle

Recommended states:

- `active`: suggestion is visible and still matches the target state.
- `accepted_direct`: an eligible actor converts the suggestion into a direct controlled decision because policy allows direct action.
- `converted_to_approval_request`: human action turns the suggestion into a formal approval request.
- `dismissed`: human action closes the suggestion without applying it.
- `stale`: suggestion is no longer reliable because of age, target changes, validation changes, or superseding evidence.
- `superseded`: a newer suggestion or applied decision replaces it.

Suggestions should become stale when the target value changes, the relevant validation state changes, or a future configurable age threshold is exceeded. This planning document does not set a suggestion stale-age default unless the owner explicitly approves one later.

## Conversion Rules

When a user acts on a suggestion, the future backend should evaluate actor authority, target validity, field scope, approval mode, and approval rules.

- If the actor has direct authority and no enabled approval trigger applies, accepting the suggestion creates an append-only decision/settings/event record.
- If approval mode is enabled and a rule applies, accepting the suggestion creates an approval request.
- If the actor lacks direct authority, the suggestion can be converted into an approval request when approval mode and rules support that path.
- If approval mode is off, no approvals queue should appear; unauthorized contributor suggestions remain advisory until an eligible actor acts.
- Bank-sourced transactions can continue flowing into balances and net worth while categorization/review awaits action.
- Manual contributor transactions should not flow into decision/report state until approved or matched to a bank-sourced item.

## Approval Request Model

Approval requests should be first-class objects, separate from decision events. A request should contain target type/id, action, field or field set, proposed value, previous/current derived value, proposer, created time, expiration time, status, policy trigger, evidence, notes, and links to source suggestions.

Rules:

- Only one active pending request may exist per `target/action/field`.
- Multi-field requests must reserve each target/action/field tuple they affect.
- The proposer cannot approve their own request.
- v1 should require only one eligible second-person approval.
- Default expiration is 14 days.
- Expired requests require a new proposal.
- Approval mode may be enabled even when no eligible second approver exists, but affected requests are blocked until eligibility is fixed.
- Approval applies the requested action only after validation still passes at application time.

Lifecycle events:

- `proposed`
- `approved`
- `rejected`
- `cancelled`
- `expired`
- `superseded`
- `applied`

## Approval Defaults And Triggers

Approval mode should be **OFF by default**. Approval-management UI should stay hidden unless the master toggle is enabled. When enabled, use a master toggle plus per-area/rule enablement.

The initial high-value threshold should be configurable and default to `$500`.

Recommended high-risk trigger catalog when approval mode is enabled:

- Controlled financial-data changes at or above the high-value threshold.
- Approval-rule changes, always with a required note.
- Reimbursement, medical/tax, side-hustle, project, transfer, delete/ignore, split, or rollback/supersession decisions.
- Manual contributor transactions before bank matching.
- Vendor match acceptance and future vendor item allocation decisions.
- Advisor-ready exports, monthly close finalization, and monthly close revisions.
- Rules affecting future auto-classification.
- Future AI/system-generated proposals.
- Settings that affect source-of-truth, import automation, approval rules, data retention, exports, or financial controls.

When approval mode is off, high-risk actions should still follow the approved controlled-write posture: explicit owner action, validation, notes where required, and append-only audit events.

## Audit And Event Expectations

All suggestion, approval, and application events should be append-only. Current state should be derived from imported facts plus active/latest approved events; imported ledger facts must not be mutated.

Suggestion audit should record creation, dismissal, direct acceptance, conversion, staleness, and supersession.

Approval audit should record proposal, approval, rejection, cancellation, expiration, supersession, and application.

Audit records should capture actor context, timestamp, target, action, field, previous value, proposed value, approved/applied value when applicable, reason/note, source suggestion, evidence references, validation state, request id, policy trigger, approver, and supersession/revert linkage. Normal audit UI should show current display names first, with event-time names available in details when audit fidelity requires them.

## Owner Review Gates

Owner approval is required before implementation for:

- final suggestions versus approvals boundary
- approval mode defaults and visibility
- high-risk trigger catalog and `$500` default threshold
- role eligibility for proposing and approving
- any schema, migration, API, UI, auth, RBAC, or enforcement work
- any AI/provider, paid service, hosted service, external-data, or credential behavior
- any rule that would auto-apply suggestions without explicit human action

Implementation must stop if it would make suggestions effective without approval, make approval mode mandatory by default, let a proposer approve their own request, mutate imported ledger facts, or bypass append-only audit history.

## Deferred Items

Deferred from this planning PR:

- approval engine implementation
- suggestions queue UI/API
- approvals queue UI/API
- database schema, migrations, indexes, and concrete table names
- auth, RBAC enforcement, impersonation, and view-as tooling
- multi-approver quorum, delegation, escalation, notifications, and reminders
- automated high-confidence decisions
- live AI/provider calls or paid tooling
- vendor item allocation approval workflows
- real-data migration or any runtime data changes

## Human QA Script

### Scope

Confirm this PR is planning-only and decision-complete for suggestions, approvals, issue #52, and issue #54.

### Preconditions

- Review this PR after or alongside PRs #60, #61, and #62.
- No app runtime is required.
- Do not use real financial data for this review.

### Steps

1. Confirm the diff only adds or edits planning/documentation files.
2. Confirm `planning/suggestions_approval_model_v040.md` states it is planning-only.
3. Confirm it references GitHub issues #52 and #54.
4. Confirm suggestions are advisory and cannot affect controlled state without human action.
5. Confirm approval requests are first-class objects with proposal, approval, rejection, cancellation, expiration, supersession, and application events.
6. Confirm one active pending request per target/action/field, proposer-cannot-approve-own-request, 14-day expiration, and configurable `$500` default threshold are documented.
7. Confirm approval mode is off by default and approval-management UI is hidden unless enabled.
8. Confirm owner review gates and deferred implementation items are explicit.
9. Confirm no schema, migration, UI/API, auth, RBAC, runtime, or financial-data files are included.

### Expected Results

- The PR gives an implementer enough direction without inventing approval behavior.
- The document matches local-first, audit-first, optional-approval product direction.
- No app behavior changes are introduced.

### Stop Conditions

- Stop if the PR changes runtime code, migrations, schema, API routes, UI behavior, auth/RBAC, or generated artifacts.
- Stop if approval mode becomes mandatory by default.
- Stop if suggestions can bypass human approval or audit.
- Stop if any real financial data or runtime artifact appears in the diff.

### Notes

This QA is document review only. Runtime approval behavior remains intentionally unimplemented.

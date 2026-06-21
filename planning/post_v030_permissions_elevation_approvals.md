# Post-v0.3.0 Permissions, Elevation, Suggestions, And Approvals

This is a planning-only document. It does not implement authentication, full RBAC, approval mode, impersonation, or view-as troubleshooting.

## Status

- v0.3.0 adds a lightweight local actor/persona envelope for audit context.
- v0.3.0 does not enforce permissions.
- Existing write APIs still accept the legacy `actor` string for compatibility.
- The structured `actor_context` field prepares event history for future auth/RBAC without deciding the final auth system.

## Permission Matrix Direction

Default roles to preserve for future expansion:

- `Administrator`: system settings, updates, runtime administration, user/group management, and RBAC configuration.
- `Finance Manager`: top-level financial-data owner for imports, exports, review decisions, reporting, monthly close, and data approvals.
- `Finance Contributor`: limited financial-data contribution and suggested changes.
- `Financial Analyst`: report and analysis access; transaction-level access only through future scoped grants or explicit exports.
- `Report Viewer`: report visibility without financial-data modification authority.

Future permission state should be minimal, structured, and auditable. The model should support inherited allows and explicit denies, with deny taking precedence over inherited allow.

## Data Scopes

Expected future scopes:

- Runtime/system settings.
- Source profiles and imports.
- Canonical transactions and review decisions.
- Reports, monthly close, and advisor exports.
- User/group/persona administration.
- Approval-rule configuration.
- External analyst/report-sharing grants.

Financial Manager should be the primary owner of financial data scopes. Administrator should be able to view enough system state to troubleshoot but should not become the default owner of financial-data actions.

## Elevated Mode

Future elevated mode should reuse one UI pattern for high-risk/admin work.

Initial direction:

- A user with Administrator permissions can enter elevated mode for system administration.
- A user with Finance Manager permissions can enter elevated mode for approval rules and other high-risk financial controls.
- While elevated as Administrator, financial-data editing should be read-only unless a later owner-approved permission explicitly allows it.
- Approval-rule changes should require a note every time.

The final name can be decided later. Candidate labels: `Elevated mode`, `Admin mode`, or `Manage mode`.

## Suggestions Queue Vs Approvals Queue

Future distinction:

- Suggestions queue: proposed changes that are not effective until accepted, such as contributor suggestions or future AI/rule suggestions.
- Approvals queue: changes requiring a second person because optional approval mode is enabled or thresholds/risk rules apply.

For v1 direction:

- Bank-sourced transactions should still flow into balances and net worth even if categorization/review awaits approval.
- Manual contributor transactions should not flow into decision/report state until approved or matched to a bank-sourced item.
- Future automation may allow high-confidence changes, but only after explicit owner-approved rules and audit behavior.

## Optional Approval Mode

Future approval mode should be a simple on/off setting at first. When off, approval management UI should stay hidden. When on, a Settings sub-tab can expose approval rules.

Initial defaults to consider later:

- Enable rule families but keep most hidden until needed.
- Include a configurable high-value threshold, initially discussed as `$500`.
- Include approval coverage hooks for financial-data changes, manual transactions, exports, monthly close, approval-rule changes, and potentially admin settings.

## View-As And Troubleshooting

View-as/impersonation remains deferred.

Preferred near-term concept:

- Provide a non-mutating permission simulation or preview that explains what a selected role/persona would be allowed to do.
- Avoid true impersonation until authentication, audit guarantees, and high-risk controls are mature.

Product rule: if a user cannot do something, the UI should hide it or visibly disable it. A logged unauthorized attempt in normal UI flow should be treated as a likely product bug unless a future security model explicitly needs that event.

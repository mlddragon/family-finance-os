# v0.4.0 Permission Matrix And Data Scopes

This is a planning-only document for GitHub issue #51. It does not implement authentication, full RBAC, database schema, permission enforcement, UI/API behavior, migrations, elevated mode, approval mode, or impersonation.

## Sources

- `AGENTS.md`
- `docs/product_requirements.md`
- `planning/post_v030_permissions_elevation_approvals.md`
- `planning/v040_orchestration_master_qa_plan.md`
- GitHub issue #51: Design permission matrix, data scopes, and default group boundaries

## Recommendation Summary

Use a default-deny permission model where an action and a data scope must both be allowed before future controlled behavior is available.

Use inherited allow from groups, personas, and system personas. Use explicit deny as the highest-precedence rule. New actions and new data scopes are denied until explicitly configured.

Keep Administrator and Finance Manager separate:

- `Administrator` owns system administration, runtime configuration, user/group/persona administration, and permission configuration.
- `Finance Manager` owns financial data, financial decisions, imports, exports, review decisions, monthly close, reporting authority, and approval-rule configuration.

Do not add user-specific overrides by default. v1 permission planning should support group, persona, and system-persona rules only.

## Terms

| Term | Recommendation |
| --- | --- |
| Role | Product-facing label for a default responsibility bundle, such as `Finance Manager`. |
| Group | Assignable permission container used for inherited allows and explicit denies. |
| Persona | Local actor/persona context used for audit and future permission simulation. |
| System persona | Narrow app-controlled actor for internal work such as imports, report generation, QA seeding, or future migrations. |
| User | Future authenticated human identity. User-specific permission overrides are deferred. |

## Evaluation Rules

1. Evaluate the requested action key.
2. Evaluate the requested data scope key and optional scope selector.
3. Collect matching rules from group, persona, and system-persona membership.
4. If any matching explicit deny exists, deny.
5. If any matching allow exists and no matching deny exists, allow.
6. Otherwise deny.
7. Treat new or unknown action keys and data scope keys as denied until configured.
8. Record permission-state changes as auditable events.

Action permission and data scope are separate. For example, `reports.generate` does not imply `transactions.edit`, and `transactions.view` does not imply `review.decide`.

## Default Groups

| Group | Default boundary |
| --- | --- |
| `Administrator` | System ownership only. Can manage runtime settings, user/group/persona configuration, and permission configuration. Not the default owner of financial-data actions. |
| `Finance Manager` | Financial-data owner and final authority. Can run imports, make review decisions, generate exports, run monthly close, and manage approval-rule configuration. |
| `Finance Contributor` | Limited contribution role. Can propose or suggest financial-data changes but cannot make controlled financial decisions effective by default. |
| `Financial Analyst` | Trusted analysis role. Can view reports and provide recommendations; transaction-level access requires scoped grants or explicit exports. |
| `Report Viewer` | Report-only read role. No financial-data modification authority. |

## Action Permission Matrix

Legend:

- `Allow`: default allow for the group.
- `Scoped`: only with an explicit data-scope grant.
- `Suggest`: can propose a change but not make it effective.
- `Deny`: default deny.

| Action | Administrator | Finance Manager | Finance Contributor | Financial Analyst | Report Viewer |
| --- | --- | --- | --- | --- | --- |
| View runtime status | Allow | Allow | Deny | Deny | Deny |
| Manage runtime/system settings | Allow | Deny | Deny | Deny | Deny |
| Manage users, groups, personas | Allow | Deny | Deny | Deny | Deny |
| Configure permission matrix | Allow | Deny | Deny | Deny | Deny |
| Configure source profiles/import settings | Scoped | Allow | Deny | Deny | Deny |
| Run imports | Deny | Allow | Deny | Deny | Deny |
| View canonical transactions | Scoped | Allow | Scoped | Scoped | Deny |
| Create manual financial records | Deny | Allow | Suggest | Deny | Deny |
| Edit/categorize transactions | Deny | Allow | Suggest | Deny | Deny |
| Make review decisions effective | Deny | Allow | Suggest | Deny | Deny |
| View reports | Scoped | Allow | Scoped | Allow | Allow |
| Generate reports | Deny | Allow | Deny | Scoped | Deny |
| Create advisor/report exports | Deny | Allow | Deny | Scoped | Deny |
| Run monthly close | Deny | Allow | Deny | Deny | Deny |
| Configure approval rules | Deny | Allow | Deny | Deny | Deny |
| View audit history | Allow for system audit | Allow for financial audit | Scoped | Scoped | Scoped |
| Manage external analyst/report-sharing grants | Deny | Allow | Deny | Deny | Deny |

Administrator can receive scoped read access where needed for troubleshooting, but routine financial edits remain denied unless a future owner-approved permission explicitly allows them.

## Data Scope Matrix

| Data scope | Administrator | Finance Manager | Finance Contributor | Financial Analyst | Report Viewer |
| --- | --- | --- | --- | --- | --- |
| Runtime/system settings | Own | Read | None | None | None |
| User/group/persona administration | Own | None | None | None | None |
| Permission configuration | Own | None | None | None | None |
| Source profiles and import configuration | Scoped support | Own | None | None | None |
| Imported source records | Scoped support read | Own | None | Scoped read | None |
| Canonical transactions | Scoped support read | Own | Scoped suggestion | Scoped read | None |
| Review decisions/category overrides | Scoped support read | Own | Suggest only | Scoped read | None |
| Reports and dashboards | Scoped support read | Own | Scoped read | Scoped read | Read published reports |
| Monthly close | None | Own | None | Scoped read | Published close outputs only |
| Advisor/export artifacts | None | Own | None | Scoped export participation | Published exports only |
| Approval-rule configuration | None | Own | None | None | None |
| Audit history | System audit | Financial audit | Scoped own activity | Scoped read | Scoped read |
| External analyst/report-sharing grants | None | Own | None | None | None |
| QA synthetic data | Scoped dev/support only | Scoped QA ownership | Scoped QA contribution | Scoped QA read | Scoped QA report read |

`Own` means the group is the default authority for that scope. It does not imply every action is allowed; the action matrix must also allow the requested action.

## System Personas

System personas should be narrow and task-bound. They should not inherit broad Administrator or Finance Manager authority.

Recommended initial system personas:

| System persona | Boundary |
| --- | --- |
| `system:importer` | Read configured source inputs and write import outputs for an approved import run. |
| `system:report_generator` | Read approved reporting inputs and write report artifacts. |
| `system:monthly_close` | Execute monthly close steps only when invoked by an allowed Finance Manager action. |
| `system:qa_seed` | Reset/seed QA synthetic data only through approved QA/dev paths, never personal data. |
| `system:audit_writer` | Append audit events for controlled system actions. |

## Minimal Auditable Permission-State Model

A future implementation should keep permission state minimal and append-auditable.

Recommended conceptual fields:

| Field | Purpose |
| --- | --- |
| `permission_event_id` | Stable event identifier. |
| `recorded_at` | Event timestamp. |
| `actor_context` | Actor/persona/system persona responsible for the change. |
| `target_kind` | `group`, `persona`, or `system_persona`. |
| `target_id` | Stable target identifier. |
| `operation` | `grant_allow`, `grant_deny`, or `revoke_rule`. |
| `effect` | `allow` or `deny` for active grants. |
| `action_key` | Controlled action identifier. |
| `data_scope_key` | Controlled data scope identifier. |
| `scope_selector` | Optional narrowed selector, such as report family, source profile, account family, or environment. |
| `reason_note` | Required explanation for permission-state changes. |
| `supersedes_event_id` | Optional pointer used when a later event replaces an earlier rule. |

Current state should be derived from auditable events. Do not mutate history in place.

## Audit Name Display Rule

Normal audit UI should show the current display/preferred name for human-readable actor context.

Audit details should preserve event-time identity context when needed for fidelity, including event-time display name, persona id, group ids, system persona id, and legacy actor string if present.

Historical or legal names should not be centered in normal audit views. Show them only in clearly labeled details when audit, compliance, or legal integrity requires that context.

## UI Availability Rule

If a user/persona cannot do something, the UI should hide the action by default.

Use a disabled visible state only when it teaches something useful, such as:

- a Finance Contributor can submit a suggestion but cannot approve it;
- approval mode is disabled and the management UI is intentionally hidden;
- a read-only setting is visible because the user explicitly chose to show read-only settings.

A logged unauthorized attempt in normal UI flow should be treated as a likely product bug unless a future security model explicitly needs that event.

## Owner Review Gates

Require owner review before implementing or changing:

- authentication;
- full RBAC;
- user-specific permission overrides;
- database schema or migrations for permission state;
- permission enforcement in UI or API code;
- any Administrator default access to routine financial edits;
- any system persona with broad financial-data authority;
- external analyst/report-sharing flows;
- approval mode or elevated mode behavior;
- destructive QA/personal data controls;
- paid tooling, hosted services, cloud dependencies, provider calls, AI calls, or credential behavior.

## Deferred Items

The following are intentionally deferred:

- real authentication;
- comprehensive RBAC;
- user-specific overrides;
- database schema and migrations;
- UI/API enforcement;
- elevated mode implementation;
- approval mode implementation;
- true impersonation/view-as behavior;
- non-mutating permission simulation UI;
- external advisor/report-sharing implementation;
- high-confidence automation that makes financial changes effective;
- browser reset/reseed controls.

## Human QA Script

### Scope

Confirm this PR adds a planning-only permission matrix and data-scope model for issue #51 without implementing permissions, auth, UI/API enforcement, migrations, or app behavior.

### Preconditions

- Review the PR branch for `planning/permission_matrix_data_scopes_v040.md`.
- Use repository files only; do not use personal financial data.
- No local app run is required for this planning-only PR.

### Steps

1. Open `planning/permission_matrix_data_scopes_v040.md`.
2. Confirm the document states it is planning-only and references issue #51.
3. Confirm default deny, inherited allow, and explicit deny precedence are documented.
4. Confirm action permissions are separate from data scopes.
5. Confirm Administrator is system-focused and is not the default financial-data owner.
6. Confirm Finance Manager is the highest financial-data authority.
7. Confirm default groups include Administrator, Finance Manager, Finance Contributor, Financial Analyst, and Report Viewer.
8. Confirm personas and system personas are covered without adding user-specific overrides by default.
9. Confirm current display names are recommended for normal audit UI, with event-time names only in details.
10. Confirm unavailable UI actions should be hidden by default or visibly disabled only when useful.
11. Confirm owner review gates and deferred items are explicit.
12. Confirm the PR diff does not include app behavior, permission enforcement, auth, schema, migration, UI/API, runtime artifacts, logs, credentials, raw data, normalized data, generated reports, or databases.

### Expected Results

- The document is decision-ready for owner review.
- The default matrices satisfy issue #51 acceptance criteria.
- No implementer needs to invent the Administrator/Finance Manager boundary.
- No out-of-scope implementation appears in the PR.

### Stop Conditions

- Stop if the PR changes runtime code, schema, migrations, UI/API behavior, auth, permission enforcement, or approval/elevated-mode behavior.
- Stop if Administrator is granted routine financial edit authority by default.
- Stop if user-specific overrides become a default v1 requirement.
- Stop if any real financial data, generated financial artifact, credential, database, or runtime artifact appears in git.

### Notes

This QA script uses document review only. It does not validate runtime permission behavior because runtime enforcement is intentionally out of scope.

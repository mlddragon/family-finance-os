# Settings And Config Audit Design v1

This document defines the proposed v1 settings/config audit design for Dillon Finances. It is a planning artifact only. It does not create app code, config files, database schema, dependencies, category data, credentials, or financial data artifacts.

## Status

- Approved by owner for v1 planning on 2026-06-18.
- App implementation has not started.
- Settings implementation has not started.
- Database schema has not been created.
- No household settings, category files, raw exports, normalized data, generated reports, or credentials have been added.
- This document should guide the later implementation plan and controlled settings write path.

## Recommendation

Strong recommendation: make active settings SQLite-backed product state, editable through the Settings UI, with every saved change recorded as an append-only settings event. Keep JSON/YAML/CSV as export, backup, seed-default, and review formats, not as the normal editing interface. This matches the owner's request for a Settings page, avoids hand-editing fragile config files, and lets monthly close bundles capture exactly which settings shaped the outputs.

The strongest reason for this approach is auditability. Settings affect freshness, validation, review priority, source identity, category behavior, report readiness, privacy posture, and future automation. A household finance product should not let those rules drift through silent code edits or untracked local files.

Serious alternatives considered:

- YAML/JSON as active config: inspectable and easy to back up, but weaker for validation, UI editing, audit history, and rollback.
- Repo-tracked household config: traceable through git, but inappropriate for private household rules and too easy to mix with product code.
- Database-only settings with no exports: simple for the app, but too opaque for backup, review, advisor workflows, and disaster recovery.

## Product Goal

The settings system should let the owner safely review, tune, export, and eventually automate product behavior without changing code.

It should support:

- Clear current settings in the UI.
- Validated settings changes.
- Append-only settings history.
- Rollback/supersede behavior through new events.
- Settings snapshots for reports and monthly close.
- Human-readable exports for backup and review.
- Guardrails around privacy, local data paths, and future network exposure.

## Active Settings Boundary

Approved direction to carry forward: active settings live in SQLite once the app exists.

Rules:

- The Settings UI is the normal review/edit surface.
- Settings changes validate before save.
- Successful saves create append-only settings events.
- Exports are generated artifacts, not the active source of truth.
- Seed defaults may live in repo-tracked examples or reference docs, but household-specific active settings stay outside git.
- The app should refuse unsafe settings that place financial data under the git repo.

## v1 Settings Domains

### 1. Data Root And Storage Safety

Purpose:

- Ensure financial data lives under `DATA_ROOT`, outside git.

Recommended v1 behavior:

- Show active `DATA_ROOT`.
- Show whether the path is reachable.
- Show whether the path appears to be inside the repository.
- Show expected folder status for inbox, raw, processed, quarantine, database, reports, monthly close, exports, and logs.
- Block saving a `DATA_ROOT` value that points inside the git repo.

Initial edit posture:

- Editable only through an explicit high-impact settings flow.
- Requires validation before save.
- Requires an owner note.

### 2. Local And Network Exposure

Purpose:

- Make privacy posture visible and prevent accidental LAN/public exposure.

Recommended v1 behavior:

- Show local-only mode in the global header and Settings UI.
- Default UI binding should be localhost-only.
- NAS/LAN exposure remains disabled unless explicitly configured later.
- Public internet exposure is out of scope.

Initial edit posture:

- Read-only for v1 unless a later deployment planning gate approves LAN/NAS settings.
- Any future network exposure setting requires explicit owner approval.

### 3. Source Definitions

Purpose:

- Define required ledger sources and import expectations.

Recommended v1 source definitions:

- Alliant Checking.
- Alliant Savings.
- Alliant Credit Card.
- Chase Prime Visa.

Settings should include:

- Source name.
- Required/optional status.
- Account type.
- Local account nickname or stable local key.
- Account last4 when useful and approved.
- Freshness threshold.
- Import mode.
- Active/inactive status.
- Source-profile confirmation status.

Initial edit posture:

- Source display names, required status, and freshness thresholds can be editable after validation.
- Source-profile identity confirmation should be treated as a high-impact settings event.
- Full account identifiers should not be stored unless separately approved.

### 4. Freshness Thresholds

Purpose:

- Decide when sources become stale and when reports become provisional.

Recommended v1 defaults:

- Checking and card sources become stale after 14 days.
- Monthly close requires all required sources imported through the target month end.

Initial edit posture:

- Editable in v1.
- Validate that thresholds are positive and reasonable.
- Notes are optional unless the change materially relaxes readiness checks.

### 5. Review Thresholds

Purpose:

- Drive review queues without hardcoding household-specific behavior.

Recommended v1 threshold families:

- Large transaction threshold.
- Low-confidence category threshold.
- Review exposure threshold for provisional reporting.
- Possible transfer/reimbursement/medical/tax/project/side-hustle candidate flags.

Initial edit posture:

- Display in v1.
- Editable only after the controlled decision/settings event path is implemented.
- High-impact changes that reduce review pressure should require an owner note.

### 6. Category Taxonomy Basics

Purpose:

- Provide controlled category/subcategory options for ledger classification and reports.

Recommended v1 scope:

- Define a small active category taxonomy sufficient for ledger classification review.
- Keep envelope labels as a presentation layer that maps back to controlled categories or buckets.
- Do not import the old prototype taxonomy directly.
- Do not treat category taxonomy as spreadsheet state.
- Track category activation, deactivation, renames, and merges through settings events.

Initial edit posture:

- Read-only seed defaults can be visible early.
- Category edits should wait for settings-event validation and owner review.
- Category delete should not be a destructive operation; prefer deactivate or supersede.

### 7. Report And Monthly Close Settings

Purpose:

- Control report readiness, provisional labels, artifact generation, and monthly close behavior.

Settings should include:

- Current reporting period.
- Monthly close readiness thresholds.
- Advisor export defaults.
- Artifact retention labels.
- Whether draft reports are allowed when sources are stale or warnings remain.

Initial edit posture:

- Mostly read-only in v1 until report generation exists.
- Any setting that changes final close readiness should require an owner note.

### 8. Future Vendor Plugin Settings

Purpose:

- Reserve a place for Amazon, Walmart, and Costco enrichment configuration without building those plugins in v1.

Recommended v1 behavior:

- Show vendor enrichment as deferred/inactive.
- Do not store credentials, cookies, browser sessions, or account-access artifacts.
- Do not add vendor item-level settings until the vendor plugin contract is approved.

Initial edit posture:

- Read-only deferred state only.

### 9. Future AI Boundary Settings

Purpose:

- Keep the future LLM boundary visible without adding live AI integration.

Recommended v1 behavior:

- No OpenAI API keys.
- No local LLM settings.
- No model configs.
- No proactive data sending.
- A read-only statement may show that live AI integration is not enabled.

Initial edit posture:

- Read-only deferred state only.
- Any future AI setting requires owner approval for privacy, cost, data scope, and retention.

## Settings Event Contract

Each saved settings change should create an append-only settings event.

Event data should capture:

- Event id.
- Setting domain.
- Setting key or target id.
- Previous value.
- New value.
- Actor.
- Reason or note.
- Validation result.
- Created timestamp.
- Supersedes/reverts event id when applicable.
- Source of suggestion: owner, Codex, rule, import validation, future AI proposal.

Rules:

- Settings events are never edited.
- Corrections create new events.
- Rollback creates a new event that supersedes or reverts a prior event.
- Settings history remains visible in the UI.
- Monthly close records the settings snapshot it used.

## Settings Validation Model

Every settings change should validate before save.

Validation should check:

- Type and allowed values.
- Required fields.
- Path safety for `DATA_ROOT`.
- Whether local data paths are outside git.
- Whether network exposure remains local-only unless separately approved.
- Whether freshness and review thresholds are reasonable.
- Whether source definitions remain internally consistent.
- Whether category changes would orphan active reviewed transactions or reports.
- Whether report/monthly close readiness rules are being relaxed.

Severity:

- Info: context only.
- Warning: save can proceed with visible acknowledgment.
- Blocking: save is prevented until fixed.

High-impact settings should require an owner note:

- `DATA_ROOT` changes.
- Source identity/profile confirmation.
- Disabling required sources.
- Relaxing freshness thresholds materially.
- Relaxing review exposure thresholds materially.
- Category rename, merge, deactivate, or reparent.
- Monthly close finalization/readiness rule changes.
- Any future LAN/NAS exposure setting.
- Any future AI/network/provider setting.

## Settings Snapshots And Exports

Settings snapshots should be generated as durable artifacts.

Snapshots are needed for:

- Report runs.
- Monthly close bundles.
- Advisor-ready exports.
- Backup/recovery.
- Audit review.

Recommended export formats:

- Current settings snapshot as JSON.
- Settings change log as JSON or CSV.
- Human-readable Markdown summary for monthly close and major changes.

Rules:

- Exports are generated under `DATA_ROOT`, outside git.
- Exports include enough metadata to understand when and why settings changed.
- Exports do not become the active editing source.
- Monthly close bundles include the settings snapshot used for that close.

## UI Behavior

The Settings UI should show:

- Current active values.
- Validation state.
- Last changed timestamp.
- Last actor.
- Whether a note is required.
- Whether the setting is editable now, read-only, deferred, or requires a separate review gate.
- Audit preview before save.

Recommended tabs:

- Data root.
- Sources.
- Categories.
- Thresholds.
- Reports.
- Privacy.
- Future integrations.

Save behavior:

1. Owner edits one or more settings.
2. UI validates draft changes.
3. UI shows audit preview.
4. Owner adds a note when required.
5. Save creates settings events.
6. Derived state and report readiness update from active settings.

## Initial v1 Edit Scope

Recommended default for implementation planning:

- Editable early:
  - Freshness thresholds.
  - Source display names.
  - Source required/optional status after validation.
  - Review thresholds after settings-event path exists.

- Read-only early:
  - `DATA_ROOT` status unless changing it is explicitly approved.
  - Local/network exposure.
  - Category taxonomy until category settings events are designed.
  - Report/monthly close readiness rules until report generation exists.
  - Vendor plugin settings.
  - AI/provider settings.

This keeps the Settings page useful without making the first version a risky configuration editor.

## Owner Review Gates

Approved owner decisions:

- Active settings should live in SQLite and be edited through the Settings UI.
- JSON/YAML/CSV should be export, seed-default, reference, backup, and review formats, not active household config.
- The initial editable scope should be narrow: freshness thresholds and low-risk source metadata first.
- High-impact settings should require an owner note.
- Category taxonomy edits should use deactivate/supersede, rename, or merge events instead of destructive deletes.
- Future LAN/NAS exposure and AI/provider settings remain read-only deferred states until separately approved.

Data integrity/security gates during implementation:

- Stop before storing household-specific active settings in git.
- Stop before allowing financial data paths inside the repo.
- Stop before storing credentials, browser sessions, cookies, or API keys in settings.
- Stop before adding network exposure settings that can expose financial data beyond localhost.
- Stop before adding any live AI/provider settings or paid/networked dependency.
- Stop before allowing category changes that silently rewrite historical reviewed transactions.

## Non-Goals

- No app implementation.
- No database schema.
- No settings/config files.
- No default category file.
- No migration of old prototype config.
- No generated settings exports.
- No credentials.
- No financial data.
- No vendor plugin implementation.
- No live AI/API integration.
- No LAN/NAS exposure implementation.

## Recommended Next Step

Codex can continue to the controlled decision event model planning gate. App implementation remains blocked until the remaining planning gates are approved.

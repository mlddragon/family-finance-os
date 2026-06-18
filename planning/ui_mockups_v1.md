# UI Mockups v1

This document captures proposed low-fidelity UI mockups for the first Dillon Finances operator experience. It is a planning artifact only. It does not start app implementation, create frontend code, create backend code, add dependencies, create schema, or migrate financial data.

## Status

- Approved by owner for v1 planning on 2026-06-18.
- App implementation has not started.
- Mockups use synthetic/redacted examples only.
- Visual styling is intentionally low fidelity.
- These mockups are approved as the v1 UI direction, but UI implementation remains gated by the remaining planning artifacts.

## Product Intent

The v1 UI should make the household financial operating loop visible and controlled:

```text
source data arrives
  -> ingestion
  -> validation
  -> normalization
  -> enrichment/classification
  -> review queue
  -> human decision
  -> controlled update
  -> reporting
  -> recommendation
  -> next action
  -> next data refresh
```

The first UI is operator-facing, local-browser-based, and read-mostly. It should help the owner understand data freshness, validation health, review workload, reporting confidence, and the next concrete action without hiding uncertainty.

## Design Principles

- Show data trust before showing financial conclusions.
- Make provisional states visible wherever reports or summaries depend on stale, missing, blocked, or unreviewed data.
- Keep raw evidence, imported facts, decisions, and derived outputs conceptually separate in the UI.
- Prefer dense, scannable operator screens over marketing-style presentation.
- Keep the navigation stable and predictable.
- Require explicit owner action before any controlled write.
- Use synthetic/redacted examples in all committed mockups.

## Proposed Navigation

Primary navigation:

- Home.
- Sources.
- Review.
- Transactions.
- Reports.
- Settings.

Secondary navigation should be contextual, not a second permanent sidebar. The first implementation can use tabs or segmented controls inside each major screen where needed.

## Global Layout

Every screen should share the same frame:

```text
+--------------------------------------------------------------------------------+
| Dillon Finances                         Data: Local only     Last refresh: 2d   |
+----------------------+---------------------------------------------------------+
| Home                 | Screen title                         [Primary action]   |
| Sources              | Short status line                                      |
| Review               |---------------------------------------------------------|
| Transactions         | Main content                                            |
| Reports              |                                                         |
| Settings             |                                                         |
+----------------------+---------------------------------------------------------+
```

Global header should show:

- Local-only/network exposure status.
- Latest successful refresh timestamp.
- Blocking validation count.
- Current month close status.

The sidebar should stay narrow and functional. It should not include financial summaries; those belong in the main content.

## Screen 1: Home / Current Status

Purpose: show whether the system is ready to trust, what needs attention, and what the next action is.

```text
+--------------------------------------------------------------------------------+
| Home                                               [Run inbox scan] [Import]    |
| Ledger freshness: 3 of 4 sources current      Validation: 1 blocking, 4 warn   |
+--------------------------------------------------------------------------------+
| Next action                                                                    |
| Import Chase Prime Visa export. Latest Chase transaction is 19 days old.        |
+--------------------------------------------------------------------------------+
| Source freshness                         | Review workload                      |
| Alliant Checking       Current   Jun 16  | Blocking validation       1          |
| Alliant Savings        Current   Jun 15  | Needs classification      42         |
| Alliant Credit Card    Current   Jun 16  | Large transactions        5          |
| Chase Prime Visa       Stale     May 30  | Possible transfers        8          |
+--------------------------------------------------------------------------------+
| Reporting confidence                                                           |
| Cashflow summary       Provisional: Chase is stale                              |
| Category spending      Provisional: $1,842 unreviewed exposure                  |
| Monthly close          Not ready: June has blocking validation                  |
+--------------------------------------------------------------------------------+
| Recent activity                                                                 |
| Jun 18  Imported Alliant Checking export: 244 rows, 0 blocking                  |
| Jun 18  Review decision applied: category update for REDACTED MERCHANT          |
| Jun 17  Monthly close memo generated for May                                    |
+--------------------------------------------------------------------------------+
```

Primary visible states:

- Ready.
- Provisional.
- Blocked.
- Stale.
- Missing source.
- Needs review.

Owner review questions:

- Does this screen make the next action obvious enough?
- Should home show dollar exposure, counts only, or both?
- Should reporting confidence be above or below review workload?

## Screen 2: Sources / Import Inbox

Purpose: show file arrival, source detection, validation results, quarantine, and import readiness.

```text
+--------------------------------------------------------------------------------+
| Sources / Import Inbox                                    [Upload file] [Scan] |
| Inbox: 2 files detected        Quarantine: 1        Required sources: 4         |
+--------------------------------------------------------------------------------+
| Required source status                                                        |
| Source                 Latest txn   Freshness   Last import   Status           |
| Alliant Checking       Jun 16       Current     Jun 18        Ready            |
| Alliant Savings        Jun 15       Current     Jun 18        Ready            |
| Alliant Credit Card    Jun 16       Current     Jun 18        Warning          |
| Chase Prime Visa       May 30       Stale       Jun 01        Action needed    |
+--------------------------------------------------------------------------------+
| Inbox files                                                                    |
| File name                         Detected source      Validation     Action    |
| chase_prime_redacted.csv          Chase Prime Visa     Not run        Validate  |
| alliant_card_redacted.csv         Alliant Credit Card  Warning       Review    |
+--------------------------------------------------------------------------------+
| Validation detail                                                              |
| alliant_card_redacted.csv                                                       |
| Warning: 2 duplicate candidate rows overlap with import batch IMP-00031.        |
| Warning: transaction date max is older than expected for this source.           |
|                                                                                |
| [Send to quarantine] [Accept with warnings] [Cancel]                            |
+--------------------------------------------------------------------------------+
```

Interaction intent:

- File upload or inbox scan is allowed, but acceptance into normalized state should require validation results.
- Blocking validation prevents import acceptance.
- Warnings can proceed only when visibly acknowledged.
- Quarantined files remain visible, with reason and recovery action.

Owner review questions:

- Should imports be accepted one file at a time or as a batch?
- Should warning acknowledgment happen in this screen or in the validation screen?
- What source status wording is most natural: current/stale/missing or ready/action needed?

## Screen 3: Validation Issues

Purpose: make data integrity failures first-class and impossible to miss.

```text
+--------------------------------------------------------------------------------+
| Review / Validation Issues                          [Acknowledge selected]     |
| 1 blocking     4 warnings     2 info     Reports affected: Cashflow, Close     |
+--------------------------------------------------------------------------------+
| Filters: [Blocking] [Warning] [Open] [Source: All] [Target: All]                |
+--------------------------------------------------------------------------------+
| Severity  Code                 Target              Message              Status |
| Blocking  duplicate_canonical  Chase row 118       Ambiguous duplicate  Open   |
| Warning   stale_source         Chase Prime Visa    19 days since txn    Open   |
| Warning   amount_sign_check    Alliant Card file   Refund sign unusual  Open   |
| Warning   low_review_coverage  Category report     18% unreviewed       Open   |
+--------------------------------------------------------------------------------+
| Issue detail                                                                   |
| Code: duplicate_canonical                                                       |
| Target: Chase Prime Visa import row 118                                         |
| Why it matters: accepting this row may double-count spending.                   |
| Evidence: row hash, source file id, candidate canonical transaction ids.        |
|                                                                                |
| Allowed actions: [Open related rows] [Quarantine file] [Mark as duplicate]      |
+--------------------------------------------------------------------------------+
```

Interaction intent:

- Validation issues are reviewable objects, not hidden logs.
- Blocking issues should show exactly what they block.
- Warnings should show which reports become provisional.
- Acknowledgment is not the same as resolution.

Owner review questions:

- Should validation issues live under Review, Sources, or both?
- Which actions should be available in v1 for blocking duplicate cases?
- Is "acknowledge" useful, or should v1 only support resolved/ignored?

## Screen 4: Ledger Classification Review Queue

Purpose: let the owner focus on the highest-impact transactions needing judgment.

```text
+--------------------------------------------------------------------------------+
| Review / Ledger Classification                         [Apply decision]        |
| Queue: 42 transactions      Exposure: $4,920.18      Selected: 1               |
+--------------------------------------------------------------------------------+
| Filters: [Uncategorized] [Large] [Transfer?] [Medical/Tax?] [Source: All]      |
| Sort: Exposure desc      Period: Current month      Review status: Open        |
+--------------------------------------------------------------------------------+
| Date       Source      Merchant             Amount      Current      Reason     |
| Jun 14     Chase       REDACTED MERCHANT    -428.11     Unknown      Large      |
| Jun 13     Alliant     REDACTED PAYROLL    2,940.00     Income?      Low conf   |
| Jun 12     Alliant CC  REDACTED STORE       -189.45     Household?   Category   |
| Jun 10     Alliant     REDACTED TRANSFER    -500.00     Transfer?    Transfer   |
+--------------------------------------------------------------------------------+
| Selected transaction                                                           |
| Imported fact                                                                   |
| Date: Jun 14    Source: Chase Prime Visa    Amount: -428.11                    |
| Raw description: REDACTED MERCHANT                                             |
|                                                                                |
| Current derived state                                                           |
| Category: Unknown    Review status: Open    Flags: Large transaction            |
|                                                                                |
| Proposed decision                                                               |
| Category: [Household]     Subcategory: [Supplies]                              |
| Flags: [ ] Transfer  [ ] Reimbursement  [ ] Medical/Tax  [ ] Side hustle        |
| Reason: [Large transaction reviewed]                                            |
|                                                                                |
| Audit preview                                                                   |
| This will create 1 append-only decision event. Imported facts will not change.  |
|                                                                                |
| [Save decision] [Skip] [Open audit history]                                     |
+--------------------------------------------------------------------------------+
```

Interaction intent:

- The table should support filtering, sorting, and selecting without changing data.
- The decision panel should show imported fact, current derived state, proposed decision, and audit effect separately.
- Save should create decision events only after the controlled-write model is implemented and approved.
- Before write support exists, the same screen can be read-only with disabled save controls.

Owner review questions:

- Should decision editing happen in a side drawer, bottom panel, or dedicated detail page?
- Which decision fields are too much for v1?
- Should the queue prioritize dollar exposure, confidence, or source freshness first?

## Screen 5: Transaction Explorer

Purpose: retrieve and inspect reviewed/current transaction data without implying raw facts were overwritten.

```text
+--------------------------------------------------------------------------------+
| Transactions                                             [Export reviewed view] |
| Showing reviewed/current view, not raw import rows                              |
+--------------------------------------------------------------------------------+
| Search: [merchant, amount, notes]   Period: [Current month]   Source: [All]     |
| Category: [All]   Review: [All]   Flags: [Any]   Confidence: [Any]             |
+--------------------------------------------------------------------------------+
| Date       Merchant             Source    Amount     Category      Review       |
| Jun 14     REDACTED MERCHANT    Chase     -428.11    Household     Reviewed     |
| Jun 13     REDACTED PAYROLL     Alliant  2,940.00    Income        Provisional  |
| Jun 12     REDACTED STORE       Card      -189.45    Unknown       Open         |
+--------------------------------------------------------------------------------+
| Transaction detail                                                             |
| Canonical transaction id: txn_redacted_001                                      |
| Imported rows: 1                                                                |
| Source file: chase_prime_redacted.csv                                           |
| Decision events: 2                                                              |
| Validation status: no blocking issues                                           |
|                                                                                |
| Timeline                                                                        |
| 1. Imported from file, parser v0.1                                               |
| 2. Initial category suggestion: Unknown                                          |
| 3. Owner decision: Household / Supplies                                          |
| 4. Report inclusion: June cashflow, category spending                            |
+--------------------------------------------------------------------------------+
```

Interaction intent:

- The default table should show the reviewed/current view.
- Detail should expose the audit chain and imported evidence links.
- Raw rows are inspectable through metadata and evidence references, not by editing raw imported facts.
- Export must use the same reviewed/current query path shown in the UI.

Owner review questions:

- Should this be a separate screen in v1, or should it be folded into Review?
- Which audit details should be shown by default versus behind an advanced section?
- Should export be available before monthly close is ready?

## Screen 6: Reports / Monthly Close

Purpose: show report readiness, confidence, generated artifacts, monthly close status, and advisor-ready export.

```text
+--------------------------------------------------------------------------------+
| Reports / Monthly Close                                  [Generate close draft]|
| Current period: June 2026      Status: Not ready      Confidence: Provisional   |
+--------------------------------------------------------------------------------+
| Readiness                                                                      |
| Required sources current: 3 of 4                                                |
| Blocking validation: 1                                                          |
| Unreviewed exposure: $1,842.00                                                  |
| Settings snapshot: available                                                    |
+--------------------------------------------------------------------------------+
| Reports                                                                         |
| Report                       Status        Reason                     Action    |
| Import validation summary    Ready         No blocking source issues   View     |
| Cashflow summary             Provisional   Chase source stale          View     |
| Category spending            Provisional   Unreviewed exposure         View     |
| Review backlog               Ready         Queue generated             View     |
| Monthly close memo           Blocked       Duplicate issue open        Resolve  |
+--------------------------------------------------------------------------------+
| Monthly close bundle                                                            |
| Close id: not created                                                           |
| Would include: reviewed transaction export, validation summary, reports,         |
| decision event export, settings snapshot, advisor-ready summary.                |
|                                                                                |
| [Preview provisional memo] [Open validation blockers] [Export advisor draft]    |
+--------------------------------------------------------------------------------+
```

Interaction intent:

- Reports should show readiness before content.
- Provisional reports can be viewed, but must be labeled.
- Monthly close should not finalize while blocking issues remain.
- Advisor-ready export should make data boundary explicit before generation.

Owner review questions:

- Should advisor-ready export be available while reports are provisional?
- What should the UI call monthly close so it feels natural?
- Which report should be the default report landing page?

## Screen 7: Settings

Purpose: review and edit product settings through the UI instead of relying on YAML or JSON files.

```text
+--------------------------------------------------------------------------------+
| Settings                                                  [Save changes]        |
| Changes create settings events. Exports remain available for backup/review.     |
+--------------------------------------------------------------------------------+
| Tabs: [Data root] [Sources] [Categories] [Thresholds] [Reports] [Privacy]       |
+--------------------------------------------------------------------------------+
| Data root                                                                       |
| DATA_ROOT: /local/path/outside/git                                              |
| Status: reachable      Git-tracked: no      Last checked: Jun 18                |
|                                                                                |
| Local/network mode                                                              |
| UI binding: localhost only                                                      |
| NAS/LAN exposure: disabled                                                      |
+--------------------------------------------------------------------------------+
| Source definitions                                                              |
| Source                 Required   Freshness threshold   Import mode             |
| Alliant Checking       Yes        14 days               Manual file             |
| Alliant Savings        Yes        14 days               Manual file             |
| Alliant Credit Card    Yes        14 days               Manual file             |
| Chase Prime Visa       Yes        14 days               Manual file             |
+--------------------------------------------------------------------------------+
| Audit preview                                                                   |
| Saving will create a settings event with previous value, new value, actor,      |
| timestamp, validation result, and optional note.                                |
+--------------------------------------------------------------------------------+
```

Interaction intent:

- Settings are first-class product state.
- The UI should show whether `DATA_ROOT` is safe and outside git.
- Changes should require validation and create settings events.
- JSON/YAML export is for backup/review, not normal editing.

Owner review questions:

- Should settings changes require a note in v1?
- Which settings should be editable first versus read-only?
- Should privacy/local-network state be its own top-level page?

## Cross-Screen States

The UI should consistently represent:

- Current: data is fresh enough and no blocking validation applies.
- Stale: source is older than the configured freshness threshold.
- Missing: required source has never been imported or is missing for the period.
- Warning: issue exists but does not block progress.
- Blocking: issue prevents import acceptance, monthly close, or trusted reporting.
- Provisional: report or derived view can be shown but should not be treated as final.
- Reviewed: owner decision exists and is active.
- Open: item still needs review.
- Superseded: older event or artifact replaced by a newer audited event.

## Controlled Write Boundaries

The first UI can be implemented read-only where needed, but the mockups reserve space for these future controlled writes:

- Owner-approved classification decision events.
- Owner-approved validation resolution decisions.
- Owner-approved settings changes.
- Monthly close draft/finalization events.

The UI must not directly edit:

- Raw files.
- Imported rows.
- Canonical transaction facts.
- Generated finalized artifacts.

## Mockup Approval Questions

Before implementation planning, the owner should approve or revise:

- Whether the screen list is right for v1.
- Whether validation issues should be a separate screen, part of Review, or both.
- Whether transaction explorer is needed in v1 or can be merged into Review.
- Whether settings should be editable in v1 or read-only first with edit controls staged.
- Whether monthly close and advisor export should be one screen or separate screens.
- Whether the proposed decision panel has the right amount of information.
- Whether read-only-first with staged controlled-write controls feels acceptable.

## Out Of Scope For These Mockups

- App implementation.
- Visual design system.
- Exact component library.
- Database schema.
- API contracts.
- Authentication.
- LAN/NAS deployment.
- Live AI or LLM integration.
- Vendor enrichment screens for Amazon, Walmart, or Costco.
- Household-facing budget/envelope UI.
- Mobile-first layouts.

## Recommended Next Step

The mockups are approved for v1. The next planning artifacts should be:

1. Import validation contract for Alliant and Chase.
2. Report and monthly close artifact detail.
3. Test and validation strategy.
4. Settings/config audit design.
5. Owner review of controlled decision event model.
6. Implementation plan after product, UI, data, and architecture gates are approved.

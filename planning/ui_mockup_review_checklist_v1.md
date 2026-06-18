# UI Mockup Review Checklist v1

This checklist records owner review of `planning/ui_mockups_v1.md`. It is a planning artifact only and does not approve app implementation.

## Approval Status

- Mockups approved by owner for v1 planning on 2026-06-18.
- UI implementation has not started.
- Remaining implementation gates still apply.

## Review Record

### Screen Scope

Approved v1 screen set:

- Home / Current Status.
- Sources / Import Inbox.
- Validation Issues.
- Ledger Classification Review Queue.
- Transaction Explorer.
- Reports / Monthly Close.
- Settings.

Decision:

- Keep all seven screens.

### Home Screen

Review prompts retained for traceability:

- Should the next action be the topmost element?
- Should home show dollar exposure, counts only, or both?
- Should reporting confidence appear above review workload?

Approved default:

- Keep next action first.
- Show both counts and dollar exposure where available.
- Show review workload before reporting confidence so the owner sees what work drives provisional reports.

### Import And Source Workflow

Review prompts retained for traceability:

- Should imports be accepted one file at a time or as a multi-file batch?
- Should warnings be acknowledged on the Sources screen, Validation screen, or both?
- Should quarantine be visible on the Sources screen by default?

Approved default:

- Accept imports as batches when files belong to the same refresh cycle, but allow single-file validation.
- Show warnings in both places, with resolution owned by Validation Issues.
- Keep quarantine visible on Sources.

### Validation Workflow

Review prompts retained for traceability:

- Should Validation Issues be its own screen?
- Should v1 include acknowledge, resolve, and ignore actions?
- Which duplicate-resolution action should be allowed first?

Approved default:

- Keep Validation Issues as its own Review sub-screen.
- Support open, resolved, ignored, and acknowledged statuses in the model, but expose only open, resolved, and ignored in the first UI.
- Do not silently resolve duplicate candidates. Require an explicit owner decision or quarantine.

### Ledger Review Workflow

Review prompts retained for traceability:

- Should transaction decisions happen in a side drawer, bottom panel, or detail page?
- Which fields are necessary for v1 classification review?
- Should the queue prioritize dollar exposure, confidence, or age first?

Approved default:

- Use a side drawer on desktop-width screens and a full detail page on narrow screens later.
- Include category, subcategory, review status, review reason, transfer flag, reimbursement flag, medical/tax flag, side-hustle flag, and project flag.
- Default sort should prioritize blocking/high-exposure/high-uncertainty items.

### Transaction Explorer

Review prompts retained for traceability:

- Is a separate Transaction Explorer needed in v1?
- Which audit details should be shown by default?
- Should exports be allowed before monthly close is ready?

Approved default:

- Keep a separate Transaction Explorer because it proves the reviewed/current retrieval model.
- Show imported row count, source file, validation status, and decision-event count by default.
- Allow provisional exports only when clearly labeled.

### Reports And Monthly Close

Review prompts retained for traceability:

- Should monthly close and reports share one screen?
- Should advisor-ready export be allowed while reports are provisional?
- What should the product call the monthly close workflow?

Approved default:

- Keep reports and monthly close together for v1.
- Allow advisor-ready draft export only with provisional labels and validation summary included.
- Use "Monthly Close" internally and consider friendlier labels later after workflow feels stable.

### Settings

Review prompts retained for traceability:

- Should settings be editable in v1 or read-only first?
- Should settings changes require a note?
- Should privacy/local-network state be top-level or a Settings tab?

Approved default:

- Settings page exists in v1.
- Early settings can be read-only until the settings-event write path is implemented.
- Editable settings should require validation and an optional note. Require notes only for high-impact changes.
- Privacy/local-network state can start as a Settings tab and appear in the global header.

## Data Integrity Review

Confirm the UI makes these conditions visible:

- Missing required source.
- Stale source.
- Blocking validation.
- Warning validation.
- Duplicate risk.
- Unreviewed dollar exposure.
- Provisional report state.
- Monthly close not ready.
- Controlled write audit preview.

## Privacy Review

Confirm the UI avoids:

- Showing real financial data in committed examples.
- Assuming hosted deployment.
- Assuming bank credentials.
- Assuming proactive external AI calls.
- Hiding local/network exposure state.

## Implementation Gate

UI implementation should not start until:

- Owner approves or revises the screen scope.
- Owner approves or revises the controlled-write posture.
- Owner approves or revises report/monthly close visibility.
- Import validation contract is captured.
- Report and monthly close artifact structure is captured.
- Test and validation strategy is captured.

## Review Outcome

- Approved as-is for v1 planning.
- UI implementation remains blocked until the remaining planning gates are captured.

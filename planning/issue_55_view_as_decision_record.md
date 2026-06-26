# Issue #55 View-As And Troubleshooting Decision Record

This document records the owner decision for GitHub issue [#55](https://github.com/mlddragon/family-finance-os/issues/55): role/user troubleshooting and view-as tooling.

## Status

- **Decision approved:** 2026-06-25
- **Implementation gate:** v1.0.0 RC planning and implementation; not part of the completed v0.4.0 foundation.
- **Related planning:** `planning/post_v030_permissions_elevation_approvals.md`, `planning/v040_orchestration_master_qa_plan.md`

## Approved Direction (B.1)

Implement a **non-mutating permission preview** for troubleshooting:

- Provide a dry-run or preview path that answers whether an action would be hidden, disabled, allowed, denied, or require approval for a selected role or persona.
- The preview must not mutate product state, create misleading audit history, or perform actions on behalf of another user.
- UI copy and API responses must clearly label preview/simulation mode.

## Explicitly Deferred

- **True impersonation** (acting as another user with mutating authority) remains deferred until authentication, strong audit guarantees, and high-risk controls are mature.
- Session takeover, audit attribution as another user, and impersonation-like write flows are out of scope for the first permission-preview slice.

## Product Rules Preserved

- Hide unavailable actions unless a disabled state teaches something useful.
- A logged unauthorized attempt in normal UI flow should be treated as a likely product bug unless a future security model explicitly requires that event.

## Acceptance Criteria For Future Implementation

- Troubleshooting preview does not create misleading audit history.
- Any future impersonation-like flow is clearly labeled and strongly audited before it ships.
- Dry-run can answer visibility and permission outcome for the selected role/persona without side effects.

## Next Step

Carry the approved B.1 preview model into v1.0.0 RC permission enforcement planning. Do not implement preview or impersonation behavior until that milestone scope is explicitly approved.

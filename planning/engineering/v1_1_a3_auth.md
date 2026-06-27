# A3 Auth Engineering Spec

## Purpose

Define the v1.1 local authentication contract per D3, D8, and D10 so backend, UI, tests, and recovery documentation implement the same passphrase, TOTP, session, first-boot, invitation, QA bypass, permission, audit, and recovery behavior.

Authentication protects one local household ledger. It identifies which household user is acting, maps that user into the existing permission personas, and provides stable audit attribution for financial decisions, settings changes, permission changes, elevated-mode events, imports, exports, monthly close, and recovery actions.

## Non-goals

- No application code, route code, migration code, seed data, recovery files, screenshots, session artifacts, or generated recovery kits in this document.
- No OAuth, passkeys, email OTP, SMS OTP, hosted identity provider, cloud synchronization, telemetry, or external auth service.
- No per-user ledger partitioning. All authenticated users share one household ledger in one local SQLite database under one `DATA_ROOT`.
- No raw passphrases, plaintext TOTP secrets, plaintext recovery codes, raw invitation tokens, session tokens, cookies, or recovery kits in git, logs, SQLite plaintext secret fields, or test artifacts.
- No silent reset flow. Auth recovery requires the recovery kit or approved break-glass input plus local machine access.
- No weakening of personal runtime security for QA convenience. The dev bypass is explicit QA/DEV_MODE behavior only.

## Schema/API Touchpoints

A3 uses the auth tables from `v1_1_a1_schema.md`, preferably in migration `0010_v1_1_auth_core` if auth is split from finance planning tables.

### Auth Tables

`users` stores local household identities:

- `username` is normalized lowercase and unique.
- `display_name` is the UI/audit label.
- `role` is one of `viewer`, `contributor`, or `administrator` and maps into permission persona/group keys.
- `status` controls access: `pending_invitation`, `active`, `disabled`, or `recovery_locked`.
- `passphrase_hash` stores only an Argon2id encoded hash.
- `totp_required` defaults to `true` for personal mode.
- `recovery_required` remains `true` until the user acknowledges saved recovery codes.
- `invited_by_user_id`, `invitation_token_hash`, and `invitation_expires_at` support administrator invitation.

`user_sessions` stores server-side sessions for HttpOnly cookie tokens:

- `session_token_hash` is unique and stores only a hash of a random session token.
- `created_from` is one of `login`, `recovery`, or `dev_bypass`.
- `last_seen_at`, `idle_expires_at`, and `absolute_expires_at` enforce D3 lifetimes: idle 8h, absolute max 7d.
- `revoked_at` and `revoked_reason` preserve logout, expiration, admin disable, and recovery reset history.
- `client_host` should identify localhost personal runtime; requests from non-local hosts must not receive personal session cookies.

`totp_secrets` stores locally protected TOTP seed material and metadata:

- `secret_ciphertext` must not be plaintext and must never be logged.
- One active confirmed TOTP secret is allowed per active user.
- `last_used_counter` should be used where the TOTP library exposes enough information to reject replay within the same time step.

`recovery_codes` stores one-time recovery code hashes and labels:

- Plaintext codes are displayed once during enrollment/regeneration and never stored.
- `status` tracks `active`, `used`, or `revoked`.
- `used_session_id` links recovery sign-in to the session created by that recovery event where applicable.

### Existing Tables

- `permission_state_events` remains the append-only record for permission override changes.
- `elevated_mode_events` remains the append-only record for System Administration and Financial Governance elevation.
- `decision_events` and `settings_events` remain the audit spine for financial and configuration decisions, now with authenticated user attribution in `actor_context_json`.
- `jobs`, `report_runs`, `monthly_closes`, `import_batch_events`, and `validation_finding_events` should receive authenticated actor context for user-triggered workflows.

### Auth API Surface

| Route | Method | Purpose |
| --- | --- | --- |
| `/api/auth/status` | GET | Returns whether first-boot enrollment is required and whether the current request is authenticated. |
| `/api/auth/enroll-owner` | POST | First-boot owner passphrase/TOTP/recovery enrollment. |
| `/api/auth/login` | POST | Passphrase + TOTP login. |
| `/api/auth/logout` | POST | Revoke the current session and clear cookie. |
| `/api/auth/recovery-login` | POST | Recovery-code fallback sign-in. |
| `/api/auth/invitations` | POST | Administrator creates an invitation. |
| `/api/auth/invitations/accept` | POST | Invited user completes passphrase/TOTP/recovery enrollment. |
| `/api/auth/users/{user_id}/disable` | POST | Administrator disables a user and revokes sessions. |
| `/api/auth/recovery/reset` | POST | Locked-down reset entry point used by the recovery runbook. |
| `/api/auth/dev-bypass` | POST | QA-only DEV_MODE synthetic user session. |

Error payloads should follow existing API convention with stable `detail.code` and `detail.message` values.

## UI Touchpoints

Approved mockup screen IDs and controls:

- Auth stage: `#auth-stage`.
- Login card: `data-auth="login"`.
- Enrollment card: `data-auth="enroll"`.
- QA banner: `#auth-qa-banner`.
- Passphrase login field in the login card.
- TOTP field: `#totp-field`.
- Recovery field: `#recovery-field`.
- Recovery link: `#recovery-link`.
- QA bypass region: `#qa-bypass`.
- Enrollment wizard panels: `data-wizard-panel="1"`, `data-wizard-panel="2"`, and `data-wizard-panel="3"`.

The implementation should preserve the mockup structure: passphrase + TOTP login, recovery-code fallback, first-boot owner enrollment, one-time recovery code display/acknowledgement, and a visibly distinct QA dev-bypass state.

## Middleware And Session Spec

### Session Cookie

- Cookie name: `ffos_session`.
- Value: random opaque token with at least 256 bits of entropy.
- Storage: hash the token into `user_sessions.session_token_hash`; never store the raw token server-side.
- Attributes:
  - `HttpOnly`
  - `SameSite=Strict`
  - `Secure` when served over HTTPS; local HTTP development must still bind to `127.0.0.1` only.
  - `Path=/`
  - `Max-Age` aligned with the 7-day absolute session maximum.
- Scope: localhost-bound personal runtime. Do not set broad domain cookies.
- Do not expose the session token to JavaScript, `localStorage`, or `sessionStorage`.

### Lifetimes

- Idle expiration: 8 hours from `last_seen_at`.
- Absolute expiration: 7 days from session creation.
- On authenticated request, update `last_seen_at` and `idle_expires_at` only when doing so will not extend past `absolute_expires_at`.
- Expired sessions are treated as unauthenticated and should be revoked with `revoked_reason = "expired"` as a best-effort cleanup.

### Request Middleware

For each API request:

1. If the route is public auth bootstrap/login metadata, allow it without a session.
2. If QA DEV_MODE bypass is active and the request hits the explicit bypass route, resolve a synthetic user session as described below.
3. Otherwise read the session cookie, hash the token, and load an unrevoked `user_sessions` row.
4. Reject if the user is not `active`, the session is idle expired, the session is absolute expired, or request host is outside the allowed local binding.
5. Build `ActorContext` from the authenticated user:
   - `actor_key`: `user:<users.id>`
   - `actor_type`: `human`
   - `display_name`: `users.display_name`
   - `source`: `auth_session`, `recovery`, or `dev_bypass`
   - `persona_key`/`group_keys`: derived from role mapping.
6. Attach the actor context to request state and existing permission/elevated-mode calls.

Public unauthenticated routes should be limited to health/status, auth status, first-boot enrollment when no users exist, login, recovery login, invitation acceptance, and static login shell assets.

### Role Mapping

Recommended initial mapping into the current permission matrix:

| User role | Persona/group mapping | Notes |
| --- | --- | --- |
| `administrator` | Administrator-oriented group plus permission/elevated-mode management capability | Can invite users, disable users, manage permission configuration, and enter System Administration when permission checks pass. |
| `contributor` | Finance contributor behavior | Can suggest or perform only actions allowed by the existing permission evaluator. |
| `viewer` | Report viewer behavior | Read-oriented access only, subject to current permission matrix. |

Implementation must use the existing `PermissionEvaluator` as the final authorization gate. Authentication identifies the user; permissions decide whether the action is allowed.

## First-Boot Enrollment

First boot is required when no `users` row exists.

Flow:

1. `GET /api/auth/status` returns `requires_owner_enrollment = true`.
2. UI shows `data-auth="enroll"` from the approved mockup:
   - Step 1: passphrase and confirmation.
   - Step 2: TOTP QR/manual key and first code confirmation.
   - Step 3: one-time recovery codes and acknowledgement.
3. Backend creates one owner user:
   - `role = "administrator"`
   - `status = "active"` only after passphrase hash, confirmed TOTP, generated recovery codes, and recovery acknowledgement are complete.
   - `totp_required = true`
   - `recovery_required = false` after acknowledgement.
4. Backend generates the household recovery kit:
   - one-time recovery codes shown once
   - instructions for using and storing the kit
   - no raw financial data
   - saved outside `DATA_ROOT` at an owner-chosen path or printed, per D10.
5. Backend creates a login session only after enrollment fully succeeds.
6. Audit records the enrollment event with actor context for the new owner. The event payload must not include secret material.

Partial enrollment handling:

- If TOTP confirmation fails or recovery acknowledgement is not completed, keep the user non-active or roll back the transaction.
- Do not allow a partially enrolled user to access ledger routes.
- If an enrollment transaction fails, do not leave plaintext generated codes in logs or files.

## User Invitation

Only an authenticated administrator with permission to manage users/groups/personas may invite or disable users.

Invitation creation:

- Administrator submits username, display name, and role.
- Backend normalizes username and rejects duplicates.
- Backend creates `users.status = "pending_invitation"` with `invited_by_user_id`, hashed one-time invitation token, and an expiration.
- Plain invitation token is shown once or copied by the administrator. The implementation must not email or transmit it externally in v1.1.
- The invitation creation is audited with authenticated actor context.

Invitation acceptance:

1. User submits invitation token.
2. Backend hashes token and loads an unexpired `pending_invitation` user.
3. User sets passphrase, confirms TOTP, receives one-time recovery codes, and acknowledges saving them.
4. Backend clears or revokes the invitation token and sets `status = "active"`.
5. Backend creates a session and records actor context for the new user.

Invitation expiry/revocation:

- Expired invitations cannot be accepted.
- Administrator may revoke an invitation by disabling or deleting the pending invitation record according to implementation preference; revocation must be audited.
- Reissuing an invitation creates a fresh token hash and expiry. Do not reuse raw tokens.

## QA DEV_MODE Bypass

QA bypass exists only to keep synthetic CI, local demos, and e2e tests practical while personal runtime uses passphrase + TOTP.

Activation requirements:

- Requires explicit QA/DEV_MODE configuration. Recommended gate: `APP_ENV = "qa"` or `"development"` plus a dedicated `DEV_MODE_AUTH_BYPASS = "1"` setting.
- Must be off by default in personal runtime and production-like Docker runs.
- Must be synthetic-only and visibly marked. UI uses the approved auth mockup QA banner: "QA synthetic demo - not real financial data" or equivalent locked QA wording.
- Must not operate against a personal `DATA_ROOT`.
- Must not operate when the app is publicly bound.

Bypass behavior:

- Provides fixed synthetic users such as synthetic owner/admin, synthetic contributor, and synthetic viewer.
- Creates or resolves sessions with `user_sessions.created_from = "dev_bypass"` and actor context `source = "dev_bypass"`.
- Still runs through the permission evaluator based on the synthetic user's role/group mapping.
- All responses should expose enough runtime metadata for the web app and e2e tests to show the visible QA banner.

Security constraints:

- Any attempt to use bypass outside QA/DEV_MODE returns `403` with stable code `dev_bypass_not_allowed` and creates no session.
- Bypass must not disable secret-pattern checks or sensitive-artifact checks.
- Bypass must not create recovery kits, raw credentials, browser profiles, or session artifacts in the repo.

## Integration With Permissions And Elevated Mode

Authentication is not a replacement for authorization. Every existing protected API mutation should continue to call `PermissionEvaluator.require(...)` or equivalent.

Actor context rules:

- Authenticated requests should pass a full `ActorContext` into permission checks instead of relying only on legacy actor strings.
- `actor_context_json` should include `user_id`, `display_name`, `role`, persona/group keys, and auth source where available.
- Legacy `actor` string fields may remain for compatibility, but new audit payloads should prefer structured actor context.
- Request actor strings cannot spoof another authenticated user or persona.

Permission integration:

- `administrator` users are allowed to manage user invitations and permission configuration only where the current permission matrix grants it.
- `contributor` and `viewer` users cannot escalate by changing request actor strings.
- System personas continue to work for importer, validator, report generator, monthly close, and QA seed jobs. System jobs must identify their system persona separately from human auth sessions.
- Permission override changes append `permission_state_events` with authenticated actor context.

Elevated-mode integration:

- System Administration elevation remains required for sensitive runtime/user/permission workflows where existing checks require it.
- Financial Governance elevation remains separate and is used for financial override workflows such as D9 monthly close blockers.
- Entering, exiting, and expiring elevated mode append `elevated_mode_events` with authenticated actor context.
- Elevated mode is not an auth session extension. It has its existing 15-minute inactivity timeout and read-only restrictions outside the allowed elevated actions.
- Financial close override requires Financial Governance elevated mode, purpose code `monthly_close_governance_review`, a non-empty note, and an audit event.

Audit requirements:

- Login success/failure may be recorded in auth-specific audit records if implementation adds them; never record passphrases, codes, tokens, or TOTP secrets.
- User creation, invitation, invitation acceptance, user disable, recovery code regeneration, recovery login, and recovery reset must be auditable.
- Financial decision events after A3 should include authenticated user attribution.

## Dependencies And Security Notes

### `argon2-cffi`

- Use Argon2id for passphrase hashing.
- Store only the encoded hash in `users.passphrase_hash`.
- Do not log passphrases or passphrase-derived material.
- Use library defaults unless local Docker or CI performance requires tuned parameters.
- Rehash on successful login when parameters are outdated.

### `pyotp`

- Use TOTP with 6 digits and the standard 30-second interval.
- Recommended verification window is minimal, typically `valid_window=1`.
- Never log TOTP codes or seeds.
- Store TOTP seed material in `totp_secrets.secret_ciphertext`; do not store plaintext secrets.
- If no local secret-protection strategy exists at implementation time, stop for owner review before weakening this requirement.

Both dependencies are local-only and must not introduce network transmission, hosted auth, telemetry, or financial-data egress.

## `docs/runbooks/auth-recovery.md` Outline

Create `docs/runbooks/auth-recovery.md` during the implementation PR. The runbook should be owner-facing and include:

1. Scope and warnings:
   - local-only household instance
   - no raw financial data deletion
   - no silent reset
   - stop if the recovery kit is unavailable
2. Preconditions:
   - physical/local machine access
   - app bound to localhost
   - recovery kit or master recovery code available
   - current `DATA_ROOT` identified outside the git repo
3. Normal recovery-code sign-in:
   - use one active recovery code
   - code is marked used
   - session created from `recovery`
   - user regenerates replacement codes after sign-in
4. Break-glass reset:
   - place recovery file or master recovery code under `DATA_ROOT/recovery/` per D10
   - start locked-down reset flow
   - verify local physical access and required recovery input
   - disable all existing users
   - revoke all active sessions with `recovery_reset`
   - require new owner enrollment
   - preserve financial tables and source metadata
5. Post-reset verification:
   - new owner can sign in with passphrase + TOTP
   - old users cannot sign in
   - old sessions are invalid
   - financial data remains present
   - recovery audit event is present
6. Security cleanup:
   - remove transient recovery trigger files from `DATA_ROOT/recovery/`
   - store new recovery kit outside `DATA_ROOT`
   - confirm no recovery files or logs were created in git

## Test Plan

### Unit Tests

- Argon2id passphrase hashing stores an encoded hash and verifies correct/incorrect passphrases.
- TOTP enrollment requires a valid confirmation code before the secret becomes active.
- TOTP login accepts only the approved verification window and rejects replay if counter tracking is implemented.
- Recovery codes are hashed, displayed once, marked used after successful recovery login, and cannot be reused.
- Invitation tokens are hashed, expire correctly, and cannot be reused after acceptance.
- Session token hashing never stores raw tokens.
- Session idle expiry occurs after 8h and absolute expiry occurs after 7d.
- User status values block authentication for `disabled`, `pending_invitation`, and `recovery_locked`.

### API Integration Tests

- First-boot status reports owner enrollment required when no users exist.
- Owner enrollment creates administrator user, confirmed TOTP, recovery code hashes, and an authenticated session.
- Login requires passphrase and TOTP.
- Logout revokes the current session and clears the cookie.
- Invitation creation requires administrator permission.
- Invitation acceptance activates the invited user and clears/revokes the invitation token.
- Disabled user login fails and active sessions are revoked.
- Recovery-code sign-in creates a `created_from = "recovery"` session and marks the code used.
- Recovery reset disables all users, revokes all sessions, requires new owner enrollment, and preserves financial data.

### Middleware And Permission Tests

- Unauthenticated protected API requests return `401` with stable auth code `authentication_required`.
- Authenticated but unauthorized requests return existing `403 permission_denied` behavior.
- Actor context from an auth session reaches permission evaluation and audit payloads.
- Request actor strings cannot spoof another user or persona.
- Elevated mode enter/exit/touch uses authenticated actor context and keeps its 15-minute inactivity semantics.

### QA DEV_MODE Tests

- Dev bypass is unavailable when QA/DEV_MODE settings are absent.
- Dev bypass creates only synthetic sessions with `created_from = "dev_bypass"`.
- UI receives runtime metadata to display a visible QA banner.
- Bypass users still obey permission matrix expectations for administrator, contributor, and viewer roles.
- QA bypass cannot run against a personal `DATA_ROOT`.
- QA bypass cannot run when the app is publicly bound.

### Cookie/Security Tests

- Session cookie is `HttpOnly` and `SameSite=Strict`.
- Cookie scope is localhost-bound and does not set a broad domain.
- Personal runtime rejects non-localhost host binding for session creation.
- Secret-pattern and sensitive-artifact checks remain green:
  - `python3 scripts/check_sensitive_artifacts.py .`
  - `python3 scripts/check_secret_patterns.py .`
  - `python3 scripts/check_v1_security_contract.py .`

### UI/E2E Smoke Tests

- `data-auth="login"` supports passphrase, TOTP, recovery-code fallback, and logout.
- `data-auth="enroll"` walks through passphrase, authenticator confirmation, recovery code display, and acknowledgement.
- QA auth variant shows the visible synthetic-data banner when bypass is active.
- Authenticated Home/API flows continue to show local-only runtime status.

## Open Questions

None for D3/D8/D10 product shape. Implementation must still choose the exact local TOTP secret-protection mechanism, but it must preserve the schema fields, no-plaintext-secret rule, local-only boundary, dependency notes, and tests above.

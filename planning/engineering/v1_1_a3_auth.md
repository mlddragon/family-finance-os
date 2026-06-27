# A3 Auth Engineering Spec

## Purpose

Define the v1.1 local authentication implementation for D3 and D10: passphrase + TOTP + recovery codes, HttpOnly sessions, first-boot owner enrollment, administrator invitations, QA DEV_MODE bypass, permission/elevated-mode integration, user-attributed audit, dependency notes, and the recovery runbook outline.

Authentication protects the local app without changing the v1.1 data model rule: one household, one `DATA_ROOT`, one SQLite DB, shared ledger, permissions control actions, audit records the actor.

## Non-goals

- No code implementation in this document.
- No OAuth, email OTP, passkeys, SMS, hosted auth, SSO, cloud sync, or paid auth services in v1.1.
- No per-user ledgers or row-level household data silos.
- No silent recovery reset without recovery kit or break-glass file.
- No plaintext passphrases, TOTP seeds, recovery codes, session tokens, cookies, credentials, or browser session artifacts in git.
- No DEV_MODE bypass in personal production-like runtime.

## Schema/API Touchpoints

A3 depends on A1 auth tables:

- `users`
- `user_sessions`
- `totp_secrets`
- `recovery_codes`

A3 also integrates with existing tables/services:

- `permission_state_events`
- `elevated_mode_events`
- `decision_events`
- `settings_events`
- `jobs`, `report_runs`, `monthly_closes`
- Existing `ActorContext`, `PermissionEvaluator`, and elevated mode registry.

New/changed API routes:

| Route | Method | Purpose |
| --- | --- | --- |
| `/api/auth/status` | GET | Returns auth mode, enrollment state, current user summary, QA bypass state, and CSRF/session metadata if needed. |
| `/api/auth/enroll-owner` | POST | First-boot owner enrollment with passphrase, TOTP confirmation, recovery acknowledgement. |
| `/api/auth/login` | POST | Passphrase + TOTP login. |
| `/api/auth/login/recovery` | POST | Passphrase + one-time recovery code login when authenticator is unavailable. |
| `/api/auth/logout` | POST | Revoke current session and clear cookie. |
| `/api/auth/invitations` | POST | Administrator creates invitation for additional user. |
| `/api/auth/invitations/accept` | POST | Invited user sets passphrase, confirms TOTP, receives recovery codes. |
| `/api/auth/recovery/reset` | POST | Break-glass reset flow after recovery proof. |
| `/api/auth/dev-bypass` | POST | QA-only DEV_MODE synthetic user session. |

Existing routes must read the authenticated user/actor context after middleware lands.

## UI Touchpoints

Approved mockup IDs:

- Auth stage: `#auth-stage`
- Login card: `data-auth="login"`
- Enrollment card: `data-auth="enroll"`
- QA banner: `#auth-qa-banner`
- Passphrase field: login card passphrase input.
- TOTP field: `#totp-field`
- Recovery fallback field: `#recovery-field`
- Recovery link: `#recovery-link`
- QA bypass region: `#qa-bypass`
- Enrollment steps:
  - `data-wizard-panel="1"` passphrase
  - `data-wizard-panel="2"` authenticator
  - `data-wizard-panel="3"` recovery codes

Settings UI later needs:

- User management/invitations.
- Recovery kit regeneration warning.
- Active sessions/revoke sessions.
- DEV_MODE banner in QA only.

## Auth Policy

Personal runtime:

- First boot creates the owner.
- Owner and additional users authenticate with:
  - Passphrase verified against Argon2id hash.
  - TOTP 6-digit code verified against active TOTP secret.
  - One-time recovery codes as fallback for lost authenticator.
- Sessions:
  - HttpOnly cookie.
  - `SameSite=Strict`.
  - `Secure` when served over HTTPS; local HTTP on `127.0.0.1` should document why Secure is not set.
  - Localhost-bound host behavior; no public binding.
  - Idle timeout: 8 hours.
  - Absolute max: 7 days.
- Login and recovery failures are rate limited.
- Disabled users cannot authenticate.
- Recovery reset disables all users, invalidates all sessions, and does not delete financial data.

QA runtime:

- Optional DEV_MODE bypass only when both are true:
  - Runtime identity is QA/synthetic.
  - Explicit env/config enables dev bypass.
- Bypass creates fixed synthetic users and visible banner.
- Bypass must never run against personal `DATA_ROOT`.

## FastAPI Middleware

Add auth middleware after existing app initialization and before route handlers perform permission checks.

Responsibilities:

1. Read session cookie.
2. Hash the presented token and find an active `user_sessions` row.
3. Check:
   - `revoked_at is null`
   - `idle_expires_at > now`
   - `absolute_expires_at > now`
   - associated `users.status == "active"`
4. Refresh `last_seen_at` and `idle_expires_at` for valid sessions, using throttling to avoid writes on every static asset request.
5. Attach authenticated user context to `request.state`.
6. Derive `ActorContext` from authenticated user for route handlers.
7. Let unauthenticated requests reach only:
   - `/api/health`
   - `/api/status`
   - `/api/auth/status`
   - `/api/auth/enroll-owner` when no users exist.
   - `/api/auth/login`
   - `/api/auth/login/recovery`
   - `/api/auth/invitations/accept`
   - static login shell assets.
8. Return `401` with stable code `authentication_required` for protected API requests.

Interaction with existing elevated mode middleware:

- Keep `X-Elevated-Session-Id` for elevated-mode state.
- Elevated mode must require an authenticated active session.
- Elevated mode `actor_context_json` must use authenticated user context, not arbitrary request body actor strings.

## Session Cookie Spec

Cookie name: `ffos_session`.

Cookie value:

- Random 32+ bytes URL-safe token.
- Store only hash in `user_sessions.session_token_hash`.
- Rotate on login and recovery login.
- Clear on logout and recovery reset.

Attributes:

| Attribute | Value |
| --- | --- |
| `HttpOnly` | true |
| `SameSite` | `Strict` |
| `Path` | `/` |
| `Max-Age` | 7 days max, aligned with `absolute_expires_at` |
| `Secure` | true on HTTPS; false only for local HTTP dev/personal runtime |

Security notes:

- Do not expose token to JavaScript.
- Do not store session token in `localStorage` or `sessionStorage`.
- Existing elevated session id currently uses `sessionStorage`; after A3, consider server-side elevated session binding to authenticated `user_id` in the implementation PR or B5 hardening.

## First-Boot Owner Enrollment

Enrollment is available only when no active users exist.

Flow:

1. User opens app.
2. `/api/auth/status` returns `enrollment_required: true`.
3. UI shows `data-auth="enroll"`.
4. Step 1: passphrase and confirmation.
5. Backend validates passphrase minimum policy and hashes with Argon2id.
6. Step 2: backend creates TOTP seed, returns QR/manual key for one-time display, and requires a valid 6-digit TOTP code before confirming.
7. Step 3: backend creates recovery codes, returns plaintext once for display/download/print, stores only hashes.
8. User checks acknowledgement that recovery codes are saved.
9. Backend marks owner `active`, recovery acknowledged, creates session, and redirects to app.

Owner user:

- `role = "administrator"` for system/user administration.
- Permission/persona mapping should also grant Finance Manager capabilities where owner needs financial governance. Implementation must document whether this is a composite group set or a selected persona.

Audit:

- Create an auth audit event pattern. If no dedicated table is introduced in A1, use `settings_events` or `decision_events` only where semantically appropriate and create structured job/audit logs for auth lifecycle. Preferred implementation is an `auth_events` table in a later hardening migration only if needed; do not add it silently in A3 without updating A1.

## User Invitation Flow

Only authenticated administrator can invite additional users.

Create invitation:

- `POST /api/auth/invitations`
- Requires permission equivalent to `users_groups_personas.manage`.
- Request includes username, display name, role, optional expiry.
- Store invitation token hash in `users.invitation_token_hash`; user status `pending_invitation`.
- Return plaintext invite token/URL once.
- Audit actor context.

Accept invitation:

- `POST /api/auth/invitations/accept`
- Validate invitation token hash and expiry.
- User sets passphrase and confirms TOTP.
- Generate recovery codes and require acknowledgement.
- Mark user `active`, clear invitation token hash, create session.

Disable/revoke:

- Administrator can disable users.
- Disabling a user revokes all active sessions.
- Disabling users does not alter financial data.

## QA DEV_MODE Bypass Rules

DEV_MODE bypass is allowed only for QA synthetic environments.

Required gates:

- `APP_ENV` or runtime identity must be QA/demo/synthetic.
- `DATA_ROOT` must be QA/demo path, not personal path.
- Explicit env flag such as `AUTH_DEV_BYPASS=true`.
- `runtime.is_synthetic` or equivalent runtime payload is true.
- UI must show visible banner: "QA synthetic demo - not real financial data".

Behavior:

- `POST /api/auth/dev-bypass` creates or reuses fixed synthetic users:
  - synthetic owner/admin
  - synthetic contributor
  - synthetic viewer
- Session `created_from = "dev_bypass"`.
- Actor context source marks `dev_bypass`.
- Operator summary/runtime payload includes bypass active state.

Forbidden:

- No bypass route in personal runtime.
- No bypass if bind host is public.
- No bypass if `DATA_ROOT` is not clearly synthetic.
- No bypass for owner real-data smoke.

Tests must prove the forbidden cases return `403` with stable code `dev_bypass_not_allowed`.

## Integration With Permissions And Elevated Mode

Existing roles/personas:

- `administrator`
- `finance_manager`
- `finance_contributor`
- `financial_analyst`
- `report_viewer`

D8 maps authenticated users to existing permission personas:

- Viewer -> read/report/audit-limited persona such as `report_viewer`.
- Contributor -> suggestion-capable persona such as `finance_contributor`.
- Administrator -> user/system administration and may also hold Finance Manager role if owner/admin.

Implementation requirement:

- Route handlers should no longer trust arbitrary `actor` body values when an authenticated session exists.
- Backwards-compatible request bodies may keep `actor` for tests/CLI until A3 migration is complete, but authenticated context wins.
- `PermissionEvaluator.require(...)` should receive actor context derived from authenticated user.
- Existing system personas remain for backend jobs:
  - `system:importer`
  - `system:validator`
  - `system:report_generator`
  - `system:monthly_close`
  - `system:qa_seed`

Elevated mode:

- Entering elevated mode requires authenticated user permission.
- Financial Governor override for monthly close D9 blockers requires:
  - Financial governance elevated context.
  - Purpose code such as `monthly_close_governance_review`.
  - Non-empty note.
  - Audit event in `elevated_mode_events`.
- Elevated mode remains time-limited and read-only except for allowed actions.

## User-Attributed Audit

After A3, all user-triggered mutations must record authenticated user details:

- `user_id`
- `username`
- `display_name`
- `role`
- mapped group/persona keys
- auth source: `session`, `recovery`, or `dev_bypass`

Targets:

- `decision_events.actor_context_json`
- `settings_events.actor_context_json`
- `permission_state_events.actor_context_json`
- `elevated_mode_events.actor_context_json`
- `import_batch_events.actor_context_json`
- `validation_finding_events.actor_context_json`
- `jobs.actor_context_json`
- `report_runs.actor_context_json`
- `monthly_closes.actor_context_json`

Stable legacy `actor` strings can remain but should be derived from authenticated user, for example `user:<username>`.

## Dependencies

### `argon2-cffi`

Purpose:

- Argon2id passphrase hashing.

Security notes:

- Use Argon2id mode through the library's password hasher.
- Store only encoded hash.
- Choose memory/time/parallelism parameters that are safe for local Docker and CI. Defaults from the maintained library are acceptable unless tests prove they are too slow.
- Do not log passphrases.
- Do not allow empty or trivial passphrases.
- Rehash on login when library reports parameters need update.

### `pyotp`

Purpose:

- TOTP seed generation and verification.

Security notes:

- Use 6-digit TOTP with standard 30-second interval.
- Allow minimal clock skew window, recommended `valid_window=1`.
- Store TOTP secret as locally protected ciphertext or an equivalent protected value. If encryption-at-rest is not available in A3, document the local threat model and stop for owner review before storing plaintext seeds.
- Never return the TOTP seed after enrollment confirmation.
- Do not log TOTP codes or seeds.

Dependency policy:

- Both dependencies are local-only and do not transmit financial data.
- Pin through the repo's normal dependency management flow when implementation begins.
- Run dependency/security checks before PR.

## Recovery Design Per D10

Household recovery kit:

- Generated at first boot.
- Contains one-time recovery codes and instructions.
- Stored outside `DATA_ROOT` at owner-chosen path or printed.
- Not committed to git.

Recovery login:

- User can use passphrase + one unused recovery code if authenticator is lost.
- Successful recovery login marks recovery code used.
- UI should strongly prompt TOTP reset/regenerate recovery kit.

Break-glass reset:

- Recovery file or master recovery code in `DATA_ROOT/recovery/` triggers locked-down reset flow.
- Requires physical access to machine and elevated administrator flow.
- Reset disables all users.
- Reset invalidates sessions.
- Reset requires new owner enrollment.
- Reset does not delete financial data.
- No silent reset without recovery kit.

## `docs/runbooks/auth-recovery.md` Outline

The implementation PR must add the runbook with this structure:

1. Purpose and scope.
2. What the recovery kit contains.
3. Where the recovery kit should and should not be stored.
4. Normal recovery login with one-time recovery code.
5. Lost authenticator but passphrase known.
6. Lost passphrase/authenticator break-glass reset.
7. What reset changes:
   - disables users
   - revokes sessions
   - requires new owner enrollment
   - preserves financial data
8. QA DEV_MODE recovery behavior.
9. Stop conditions:
   - suspected compromise
   - missing recovery kit
   - personal/QA data-root confusion
   - public binding
10. Evidence safe to record in issues/PRs:
   - statuses, timestamps, user ids
   - no recovery codes, secrets, cookies, screenshots with financial data.

## Test Plan

### Unit Tests

- Argon2id hash verifies correct passphrase.
- Incorrect passphrase fails without leaking which factor failed.
- Hash recheck identifies outdated parameters.
- TOTP verifies current code and allowed adjacent window.
- TOTP rejects replay when `last_used_counter` is implemented.
- Recovery code hash verifies once, then cannot be reused.
- Session token hash lookup works; raw token is never stored.
- Idle expiration at 8h.
- Absolute expiration at 7d.
- Disabled user cannot authenticate.

### API Integration Tests

- `/api/auth/status` returns enrollment required when no users exist.
- Owner enrollment creates active user, TOTP secret, recovery code hashes, and session.
- Owner enrollment is blocked after active user exists.
- Login requires passphrase and TOTP.
- Recovery login requires passphrase and active recovery code.
- Logout revokes session and clears cookie.
- Invitation create requires administrator permission.
- Invitation accept creates active user and recovery codes.
- Protected API route returns `401` unauthenticated.
- Authenticated mutation records user-attributed `actor_context_json`.

### QA DEV_MODE Tests

- Bypass succeeds in QA synthetic runtime with explicit flag.
- Bypass is visible in `/api/auth/status`, `/api/operator-summary`, and UI banner.
- Bypass fails in personal runtime.
- Bypass fails when `DATA_ROOT` is not synthetic.
- Bypass fails when bind host is public.

### Permission/Elevated Mode Tests

- Authenticated viewer cannot mutate financial data.
- Contributor receives suggestion route behavior where existing matrix allows suggestion.
- Administrator can manage invitations/users.
- Finance Manager can run financial close actions per existing matrix.
- Elevated mode enter uses authenticated actor context.
- Financial close override requires governance elevated mode and non-empty note.

### Security/Artifact Tests

- Sensitive artifact and secret pattern checks pass.
- No recovery kit, cookie, session token, TOTP seed, or passphrase appears in git.
- Cookie attributes include HttpOnly and SameSite=Strict.
- Session token is not accessible through JS client state.

## Open Questions

- TOTP secret storage needs an implementation choice: locally encrypted ciphertext versus documented local plaintext risk. Recommendation: use protected ciphertext if the repo already has or approves a local key strategy; otherwise stop for owner review before storing plaintext TOTP seeds.
- Whether A3 adds a dedicated `auth_events` table should be decided before code. Recommendation: do not add it in Phase 1 unless audit requirements cannot be met through existing event tables and structured logs.

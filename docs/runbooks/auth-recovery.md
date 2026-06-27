# Auth Recovery Runbook

## Scope And Warnings

This runbook is for a local-only Family Finance OS household instance. Recovery restores access to the local ledger; it must not delete raw, normalized, or generated financial data.

There is no silent reset flow. Stop if the recovery kit or approved break-glass input is unavailable.

## Preconditions

- You have physical access to the local machine running the app.
- The app is bound to localhost, not a public interface.
- The current `DATA_ROOT` is identified and is outside the git repository.
- You have one active recovery code from the recovery kit, or an approved break-glass recovery input.

## Normal Recovery-Code Sign-In

1. Open the local app and choose the recovery sign-in path.
2. Enter the username and one active recovery code.
3. Confirm the session was created from `recovery`.
4. Confirm the used code is marked used and cannot be reused.
5. Regenerate and store replacement recovery codes after sign-in.

## Break-Glass Reset

Use break-glass only when normal recovery-code sign-in is unavailable.

1. Place the approved recovery trigger file or master recovery code under `DATA_ROOT/recovery/`.
2. Start the locked-down reset flow from the local machine.
3. Verify local physical access and the required recovery input.
4. Disable all existing users.
5. Revoke all active sessions with reason `recovery_reset`.
6. Require new owner enrollment.
7. Preserve financial tables, source metadata, imports, decisions, reports, and monthly close history.

## Post-Reset Verification

- The new owner can sign in with passphrase and TOTP.
- Old users cannot sign in.
- Old sessions are invalid.
- Financial data remains present.
- A recovery audit event is present.

## Security Cleanup

- Remove transient recovery trigger files from `DATA_ROOT/recovery/`.
- Store the new recovery kit outside `DATA_ROOT`.
- Confirm no recovery files, generated kits, logs, secrets, cookies, or session artifacts were created in git.

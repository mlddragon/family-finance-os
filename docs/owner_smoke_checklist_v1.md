# Owner Smoke Checklist v1

This checklist is for an owner-approved local real-data smoke run after the synthetic v1 path passes. Do not run this with real exports until explicitly approved.

## Evidence Boundary

- Do not record raw transaction descriptions, merchants, account numbers, filenames containing private information, balances, or row-level values in GitHub, Codex messages, PRs, screenshots, or docs.
- Record only sanitized counts, statuses, source names, validation codes, and high-level pass/fail notes.
- Keep raw files, SQLite databases, reports, close bundles, and exports under the local `DATA_ROOT` only.

## Preflight

- Confirm Docker is running locally.
- Confirm the personal app opens at `http://127.0.0.1:28080`.
- Confirm the QA synthetic app opens at `http://127.0.0.1:28081` when running QA.
- Confirm `DATA_ROOT` is outside the git repo.
- Confirm the repo has no raw financial data, generated reports, database files, credentials, or API keys.

## Smoke Steps

1. Place owner-approved real source exports in `DATA_ROOT/inbox/`.
2. Scan inbox and record only sanitized source count.
3. Validate each batch and record only validation codes and severity counts.
4. Accept only batches the owner approves; record accepted batch count only.
5. Confirm raw files moved under `DATA_ROOT/raw/`; record source-level status only.
6. Review one transaction in the UI without capturing raw transaction text.
7. Save one owner-approved decision event and record only the decision field name and status.
8. Generate reports and record artifact count only.
9. Generate a draft monthly close and record draft/provisional status only.
10. Attempt final close and record whether it is final or blocked, plus sanitized blocker codes.
11. Generate advisor export only if approved; record artifact count only.

## Sanitized Evidence Template

```text
Date:
DATA_ROOT outside repo: yes/no
Sources scanned: count only
Accepted batches: count only
Validation findings: severity/code counts only
Transactions created: count only
Decision event saved: field/status only
Reports generated: count only
Monthly close: draft/final/blocked plus sanitized blocker codes
Advisor export: generated/not generated plus count only
Raw transaction details recorded outside DATA_ROOT: no
```

# v1 Synthetic QA Record

Sanitized validation record for RC readiness. **No raw financial rows.** Generated 2026-06-26 on local semi-persistent QA (`ffos-qa`, `http://127.0.0.1:28081`).

## Automated verification (main + branch)

| Check | Result |
| --- | --- |
| Python `pytest` | Pass (full suite) |
| Web unit tests (`npm test`) | Pass (20 tests) |
| Elevated mode API (optional/required note) | Pass (`tests/api/test_elevated_mode.py`) |
| SPA shell cache headers | Pass (`tests/api/test_static_ui.py`) |
| Control plane lightbox unit test | Pass (`App.test.tsx`) |

## Five seed scenarios

Each scenario: `make qa-reset CONFIRM="RESET QA DATA"` then `make qa-seed QA_SCENARIO=<name>`. QA API reported `app_env=qa`, `qa_controls_enabled=true` after each seed. Manifest written under external QA `DATA_ROOT/manifests/`.

| Scenario | Seed | Manifest | Result |
| --- | --- | --- | --- |
| `baseline` | OK | `baseline-0.4.0.json` | **Pass** |
| `stale-source` | OK | `stale-source-0.4.0.json` | **Pass** |
| `blocked-import` | OK | `blocked-import-0.4.0.json` | **Pass** |
| `review-backlog` | OK | `review-backlog-0.4.0.json` | **Pass** |
| `monthly-close-ready` | OK | `monthly-close-ready-0.4.0.json` | **Pass** |

## Governance flows (synthetic)

| Flow | Validation | Result |
| --- | --- | --- |
| Permission enforcement API | CI + `test_elevated_mode`, permission tests | **Pass** (automated) |
| Elevated financial read-only | `test_financial_mutation_blocked_while_elevated` | **Pass** (automated) |
| Persona UI gating | Unit tests + governance QA script in `docs/qa_validation_strategy.md` | **Pass** (automated UI tests; owner spot-check recommended) |
| Suggestions / approvals API | B.3 API tests in CI | **Pass** (automated) |
| Control plane lightbox | `App.test.tsx` | **Pass** (automated) |

## Owner sign-off

- [ ] Owner completed governance QA script on `:28081` (personas, elevation, suggestions optional path)
- [ ] Owner confirms **ready for `v1.0.0-rc.1` tag** — tag cut 2026-06-26 as [v1.0.0-rc.1](https://github.com/mlddragon/family-finance-os/releases/tag/v1.0.0-rc.1) after PR [#97](https://github.com/mlddragon/family-finance-os/pull/97)

## Stop conditions

None triggered. No personal `DATA_ROOT` used. No raw transaction data recorded in this document.

## Related

- [docs/qa_validation_strategy.md](../docs/qa_validation_strategy.md)
- [planning/v1_rc_foundation_review_guide.md](v1_rc_foundation_review_guide.md)
- [docs/runbooks/v1-rc-release-gates.md](../docs/runbooks/v1-rc-release-gates.md)

---

## PR #101 — v1.1 D1 receipts / E1–E4 vendor scrapers (2026-06-30)

**Runtime:** `ffos-qa`, `http://127.0.0.1:28081`, synthetic only. **Owner verdict:** **Pass with noted exceptions** (merge approved).

### Automated / API verification

| Area | Result |
| --- | --- |
| CI on PR #101 | **Pass** (synthetic-checks, Security) |
| Ledger import pack (4 sources + blocked) | **Pass** |
| Review backlog (48/48 reviewed) | **Pass** (API decision-events) |
| Receipt CSV import + promote-to-splits | **Pass** (Amazon, Costco, Walmart) |
| Manual Amazon split allocations | **Pass** |
| Net worth import + summary | **Pass** |
| Reports run (7 types, provisional) | **Pass** |
| Monthly close draft | **Pass** |
| Credential rejection on vendor scrape | **Pass** (422) |
| Vendor adapters enable in Settings | **Pass** |

### Noted exceptions (non-blocking for merge)

| Exception | Notes | Follow-up |
| --- | --- | --- |
| Vendor synthetic scrapes in Docker QA | `vendor_scrape_fixture_not_found` at collect — fixtures not under `DATA_ROOT` in image | [#106](https://github.com/mlddragon/family-finance-os/issues/106) |
| Final monthly close | Blocked by intentional open `schema_mismatch` on wrong-header import (Section 4 demo) | Expected; void batch to test finalize |
| Hardware Store receipt | Unmatched on review queue (no Chase row) | Optional manual link or known gap |
| Vendor scrape / receipt UI | API-only in this PR | Intentional PR scope |
| Governance persona browser spot-check | Automated tests pass; full persona matrix not re-walked in browser this session | `docs/qa_validation_strategy.md` when convenient |
| Source profile manual confirmation UX | Permission fix landed; removal tracked separately | [#103](https://github.com/mlddragon/family-finance-os/issues/103) |

### Owner decisions recorded (same session)

- Decision 16: UI-only user file I/O, `DATA_ROOT` runtime model — [#107](https://github.com/mlddragon/family-finance-os/issues/107)
- `DATA_ROOT` default public user directory + installer profile/UNC path — [#108](https://github.com/mlddragon/family-finance-os/issues/108)

### Stop conditions

None triggered. No personal `:28080` data used. No raw rows recorded here.

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

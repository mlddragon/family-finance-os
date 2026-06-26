# v1.1 Decision Rollup

Owner-facing summary of the 2026-06-26 v1.1 expansion review. This is a concise index over the
full record in [v1_1_expansion_decision_record.md](v1_1_expansion_decision_record.md) and the
wireframes in [ui_mockups_v1_1_funds_dashboard.md](ui_mockups_v1_1_funds_dashboard.md).

## Program goal

v1.1 turns Family Finance OS from a read-mostly operator console into a planning-aware household
ledger: an honest, single-number **Spendable balance** on Home, **fund pools** with commitments and
pool remaining, an analytical **Dashboard**, transaction **splits** and manual **receipt** capture,
real **passphrase + TOTP** authentication with recovery codes, manual **net worth** snapshots, and a
local-only **analyst export** — all local-first, synthetic-data-safe, append-only on decisions, and
with vendor scrapers deliberately sequenced last.

## Decisions at a glance (D1–D11)

| # | Decision | One-line outcome |
|---|----------|------------------|
| D1 | Spendable balance formula | Headline = verified liquid cash − reserved goal balance − manual obligations; provisional exposure is opt-in, card obligation shown separately. |
| D2 | Product terminology | Locked vocabulary (below); banned words never shown in UI or copy. |
| D3 | Authentication | Passphrase (Argon2id) + TOTP + one-time recovery codes; localhost-bound sessions; QA dev bypass behind a red banner only. |
| D4 | Mockup gate | Wireframes + HTML mockups **owner-approved 2026-06-26**; Funds/Dashboard/Split/Auth UI PRs unlocked. |
| D5 | Receipts & scrapers | Manual receipt/line-item + CSV + review queues this pass; Amazon → Costco → Walmart scrapers strictly last. |
| D6 | Net worth estimates | Manual snapshots with actual vs estimate; estimates never feed Spendable balance; dashboard toggle + warning. |
| D7 | Goals vs projects | One `financial_goals` entity with `goal_type`; no separate projects table; goals require a name. |
| D8 | Multi-user household data | One household, one `DATA_ROOT`, one shared ledger; permissions gate actions, audit records the actor. |
| D9 | Monthly close rules | Draft close allowed with warnings; final close blocked on negative/overcommit conditions absent Governor override. |
| D10 | Auth recovery | First-boot recovery kit stored outside `DATA_ROOT`; break-glass reset disables users without deleting financial data. |
| D11 | Split vs receipt precedence | Splits drive reports/pool remaining; receipt lines are enrichment; promote-to-split is explicit, no auto-merge. |

## Locked terminology

Use verbatim in all labels and copy:

- **Fund pool** — a named container for planned money (e.g., Groceries, Auto).
- **Fund commitment** — the monthly amount committed to a pool.
- **Spendable balance** — verified liquid cash − reserved goal balance − manual obligations.
- **Reserved goal balance** — money set aside toward goals, subtracted from spendable.
- **Pool remaining** — what is left in a given pool this period.
- **Provisional exposure** — unreviewed outflows that may reduce spendable once confirmed.
- **Card obligation** — outstanding credit card balance owed, shown separately.

Banned (never shown): `envelope`, `give every dollar a job`, `available to spend`, `age of money`.

## Build order (approved)

1. Schema + spendable engine + auth (backend).
2. Funds, splits, net worth, analyst export (API + UI).
3. Dashboard + charts.
4. Receipt manual/CSV.
5. **Last:** Amazon → Costco → Walmart scraper framework and adapters.

Target version line: `0.6.0` after v1.0.0 stable / post-RC foundation.

## Model routing (owner preference)

- **UI mockups / UX review:** Opus 4.8 high-thinking subagent.
- **Implementation / fixes / tests:** GPT-5.5 subagent.

## Interactive HTML mockups

Standalone, dependency-free visual mockups (open in a browser, no build, no backend) live at:

- [mockups/v1_1/index.html](mockups/v1_1/index.html) — single-page nav across Home, Funds,
  Dashboard, Split editor, Receipt entry, Auth (incl. QA dev-bypass variant), and Analyst export.
- See [mockups/v1_1/README.md](mockups/v1_1/README.md) for how to preview locally.

These are **owner-approved 2026-06-26** — UI implementation PRs for Funds, Dashboard, Split, Auth, and related screens may proceed.

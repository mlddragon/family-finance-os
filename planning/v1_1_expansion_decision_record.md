# v1.1 Expansion Decision Record

Planning-only. Captures owner decisions from the 2026-06-26 interactive review for the next feature pass (funds, auth, dashboard, net worth, splits, receipts, analyst export, vendor scrapers).

All planning decisions D1–D11 are recorded. Interactive HTML mockups **owner-approved 2026-06-26** — UI implementation PRs for Funds, Dashboard, Split, Auth, and related screens may proceed.

## Approved Decisions

### D1: Spendable balance formula (2026-06-26)

- **Headline spendable** = verified liquid cash − reserved goal balances − manual upcoming obligations.
- **Provisional exposure** (unreviewed outflows) is a separate line; excluded from headline by default; user may toggle to include.
- Credit card purchases reduce pool remaining / category targets but not verified liquid until payment imports.
- **Card obligation** shown separately from headline spendable.

### D2: Product terminology (2026-06-26)

Use verbatim in UI: Fund pool, Fund commitment, Spendable balance, Reserved goal balance, Pool remaining, Provisional exposure, Card obligation.

Do not use: envelope, give every dollar a job, available to spend, age of money.

### D3: Authentication (2026-06-26)

- Personal: passphrase (Argon2id) + TOTP + one-time recovery codes at enrollment.
- Sessions: HttpOnly, SameSite=Strict, localhost-bound; idle 8h, absolute max 7d.
- First boot creates owner; additional users via administrator invitation.
- QA: optional dev bypass with fixed synthetic users and visible banner when active.
- Not in MVP: passkeys, email OTP, OAuth.

### D4: Mockup gate (2026-06-26)

- Wireframe + HTML mockups in `planning/ui_mockups_v1_1_funds_dashboard.md` and `planning/mockups/v1_1/` — **owner-approved 2026-06-26**; Funds/Dashboard/Split/Auth UI PRs unlocked.

### D5: Receipt detail and vendor scrapers (2026-06-26)

- **Main pass:** manual receipt/line-item entry + CSV import + review queues.
- **Also in this pass (last):** Amazon, Costco, and Walmart scraping — after all other v1.1 work is finalized and stable.
- Scraper gates: no credentials in git, no session artifacts in repo, local `DATA_ROOT` only, auditable scrape runs, human QA script per vendor.

### D6: Net worth estimates (2026-06-26)

- Manual snapshots support `valuation_method`: **actual** or **estimate** (home, vehicle, other).
- Estimates require confidence, as-of date, and notes/source.
- Dashboard net worth tile: **actual balances only** by default; toggle **Include estimates** shows secondary series + warning banner.
- Estimates never feed **Spendable balance**.
- Analyst pack includes both views with `includes_estimates` flag.

### D7: Goals vs projects (2026-06-26)

- Single **`financial_goals`** entity; no separate projects table in v1.1.
- Fields include: name, target amount, target date (optional), linked fund pool, reserved balance, status, **goal_type** (`emergency` | `sinking_fund` | `purchase` | `other`).
- PRD “projects” map to `goal_type` values, not a second model.
- Side-hustle / reimbursement / medical tax remain transaction flags and review queues.
- **Owner qualification:** selecting **Goal** (creating or choosing a goal) must require a **goal name** before save — no anonymous or type-only goals.

### D8: Multi-user household data (2026-06-26)

- One household, one `DATA_ROOT`, one SQLite DB on the personal instance.
- All authenticated users share the same ledger; permissions control actions, not data silos.
- Roles map to existing permission personas (viewer, contributor, administrator).
- Audit trail records which user performed each action.
- No per-user ledgers in v1.1; member-specific views use filters/tags later if needed.

### D9: Monthly close rules for funds and spendable (2026-06-26)

- **Draft close:** allowed with warnings for negative pool remaining, reserved goals exceeding liquid, negative headline spendable, or missing fund commitments; provisional labels apply.
- **Final close:** blocked for the above conditions unless Financial Governor elevated override with purpose note and audit event.
- Existing blockers remain: unreviewed transactions, stale required sources, open blocking validation findings.
- Close bundle includes fund pool summary and spendable snapshot.

### D10: Auth recovery (2026-06-26)

- Household recovery kit generated at first boot (one-time codes + instructions), stored outside `DATA_ROOT` (owner-chosen path or printed).
- Break-glass: recovery file or master recovery code in `DATA_ROOT/recovery/` triggers locked-down reset flow (physical access + elevated administrator on machine).
- Reset disables all users, requires new owner enrollment, invalidates sessions; **does not delete financial data**.
- Runbook: `docs/runbooks/auth-recovery.md`. No silent reset without recovery kit.

### D11: Split vs receipt allocation precedence (2026-06-26)

- Receipt line items are enrichment by default; transaction splits drive reports, pool remaining, and targets.
- **Apply receipt lines as splits** — explicit UI action with user confirmation and decision event.
- If both exist: show reconciliation hints; no auto-merge.
- Vendor scraper output creates receipt lines first; review queue prompts promote-to-splits when matched.

## Model routing (owner preference)

- UI mockups / UX review: Opus 4.8 high thinking subagent.
- Implementation / fixes / tests: GPT-5.5 subagent.

## Mockup artifacts

- [ui_mockups_v1_1_funds_dashboard.md](ui_mockups_v1_1_funds_dashboard.md) — ASCII wireframes (approved reference).
- [mockups/v1_1/index.html](mockups/v1_1/index.html) — interactive HTML mockups (**owner-approved 2026-06-26**); see [mockups/v1_1/README.md](mockups/v1_1/README.md).
- [v1_1_decision_rollup.md](v1_1_decision_rollup.md) — concise owner-facing rollup of D1–D11 with build order, terminology, and links.

## Open Decisions

All v1.1 expansion decisions D1–D11 are recorded above. No open planning decisions remain for this pass.

## Build order (approved)

1. Schema + spendable engine + auth (backend)
2. Funds, splits, net worth, analyst export (API + UI)
3. Dashboard + charts
4. Receipt manual/CSV
5. **Last:** Amazon → Costco → Walmart scraper framework and adapters

Target version line: `0.6.0` after v1.0.0 stable / post-RC foundation.

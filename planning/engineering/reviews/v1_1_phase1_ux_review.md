# v1.1 Phase 1 Engineering Docs — UX Review

Reviewer role: Sr UX/UI designer (Opus)
Scope: UX alignment only. No code reviewed, no code changed.
Date: 2026-06-26
Branch: `feat/v1-1-engineering`

## Inputs reviewed

- `planning/v1_1_expansion_decision_record.md` (D1-D11; D1 spendable formula, D2 terminology lock, D3/D8/D10 auth)
- `planning/v1_1_decision_rollup.md` (owner-facing rollup, locked terminology)
- `planning/mockups/v1_1/index.html` + `app.js` (owner-approved 2026-06-26): Screen A Home, Screen F/F-qa Auth (login + enrollment wizard)
- `planning/mockups/v1_1/README.md` (screen index / interaction notes)
- Phase 1 engineering docs: `v1_1_00_overview.md`, `v1_1_a1_schema.md`, `v1_1_a2_spendable.md`, `v1_1_a3_auth.md`

## Method

For each Phase 1 doc: confirm terminology against the D2 lock, confirm formula/behavior against the governing decision (D1 for spendable, D3/D8/D10 for auth), and compare the doc's UI/touchpoint section against the matching approved mockup screen. Phase 1 is mostly backend (schema, engine, auth contract); only A2 (Home Screen A) and A3 (Auth Screen F/F-qa) have approved screens to diff against. A1 has no user-facing surface of its own.

Banned-phrase scan (`envelope`, `give every dollar a job`, `available to spend`, `age of money`) across the four Phase 1 docs and the Home + Auth mockup markup returned **no user-facing violations**. The only hits are the prohibition lists themselves (`v1_1_00_overview.md` §Terminology Lock).

## Summary table

| Doc | Mockup screen | Decision check | Terminology | Status |
| --- | --- | --- | --- | --- |
| 00 Overview | screen-ID map only | D2 lock restated correctly | Pass | Approved |
| A1 Schema | none (backend) | D6/D7/D8 schema shape | Pass (DB snake_case allowed) | Approved |
| A2 Spendable | A (Home) | D1 formula exact | Pass | Approved with notes |
| A3 Auth | F / F-qa (login + enroll) | D3/D8/D10 | Pass (auth; n/a banned terms) | Approved with notes |

---

## 00 Overview — Approved

No user-facing surface. Acts as the terminology lock, screen-ID map, PR sequence, and shared-conventions index for Phase 1+.

- **D2 terminology lock** is restated verbatim (Fund pool, Fund commitment, Spendable balance, Reserved goal balance, Pool remaining, Provisional exposure, Card obligation) with the banned list (§Terminology Lock From D2). Matches the decision record and rollup.
- **Screen-ID map** (§UI Touchpoints) correctly enumerates `home`, `funds`, `dashboard`, `split`, `receipt`, `export`, and the `data-auth="login"` / `data-auth="enroll"` auth stages. These IDs exist in the approved mockup.
- **PR sequence** (A1 → A2 → A3 → B* → C* → D* → E*) matches the approved build order.

### Recommended doc edits
- None blocking. Optional: the README labels screens A–G with the auth variants as `F`/`F-qa`; the overview uses lowercase `data-screen` IDs only. Adding the letter labels (A Home … F Auth) in §UI Touchpoints would make cross-referencing the mockup and the review set easier, but is cosmetic.

---

## A1 Schema — Approved

Mockup screen: none. A1 is the migration/table contract; it has no UI of its own and is UX-neutral.

### Terminology compliance
Compliant. DB identifiers use concise snake_case (`fund_pools`, `spendable_balance_snapshots`, `manual_obligations`, `financial_goals`) which D2/overview explicitly permit, provided UI labels use the locked terms. No user-facing strings are introduced here. No banned terms.

### Decision alignment
- **D7** goal-name-required is enforced at the schema layer: `financial_goals.name` is NOT NULL plus a `CheckConstraint("length(trim(name)) > 0")` and app-layer blank/whitespace rejection (§`financial_goals`). This backs the "no anonymous or type-only goals" qualification.
- **D6** net worth supports `valuation_method` actual/estimate, `confidence`, `source_notes`, and `include_in_actual_net_worth`, with the app-layer rule that estimates never feed Spendable balance (§`net_worth_snapshots`). Matches D6 and A2.
- **D8** one shared ledger: tables carry `created_by_user_id`/`updated_by_user_id` attribution columns, not per-user partitions. Matches D8.
- **D1** inputs are all present as first-class tables (`manual_obligations`, `financial_goals.reserved_balance`, `spendable_balance_snapshots`).

### Notes (non-blocking, not UX defects)
1. **Net worth `balance` sign convention is unresolved** (§`net_worth_snapshots` notes "implementer must choose one convention and document in B3"). Fine for A1, but the dashboard tile (Screen C, B3) and any UI rollup sign depend on it — flag as a B3 pre-UI decision, not an A1 blocker.
2. **User-attribution FK timing** (soft reference in `0009` vs hard FK after `0010`) is left to the migration PR. Acceptable; it has no UX impact.

### Recommended doc edits
- None. A1 is implementation-ready from a UX standpoint.

---

## A2 Spendable — Approved with notes

Mockup screen: A (Home).

### Decision (D1) alignment — exact
The doc's formula (§Formula) is character-for-character D1: `headline = verified_liquid_cash − reserved_goal_balance − manual_upcoming_obligations`, provisional exposure subtracted only when the toggle is on, card obligation reported separately. Screen A renders this exactly: breakdown line "Verified liquid cash $6,180.00 − Reserved goal balance $1,900.00 − Manual obligations $867.42", headline `$3,412.58`, hidden provisional term, and a separate Card obligation panel. The toggle math ($3,412.58 ↔ $1,570.58) matches the doc's unit-test matrix.

### Terminology compliance
Compliant. Uses Spendable balance, Reserved goal balance, Provisional exposure, Card obligation, Fund commitment, Pool remaining verbatim (§UI Touchpoints). The toggle/note copy in §Provisional Exposure Toggle Semantics ("Excludes $X provisional exposure (unreviewed outflows)." / "Include provisional exposure ($X unreviewed).") matches Screen A's `#spendable-note` and `#provisional-toggle` strings exactly. No banned terms.

### Mockup screen alignment gaps
1. **Card obligation is a per-card table in the mockup, a scalar in the API contract.** Screen A renders Card obligation as a table with columns `Card` / `Owed` / `Note` and two rows carrying per-row notes ("Pool remaining already reflects this", "Statement due Jul 02"), under the heading "Card obligation (not yet netted)". The `GET /api/spendable` response (§API Contract) exposes a scalar `card_obligation` plus a generic `source_details[]` whose example only shows a `liquid_cash` role. There is no per-card `owed` + `note` shape, and the "(not yet netted)" framing is a deliberate tone choice not captured. (Same class of gap flagged for B1 in the Phase 2-5 review.)
2. **Breakdown line labels not locked to Screen A.** The mockup commits to the exact breakdown labels "Verified liquid cash", "Reserved goal balance", "Manual obligations". D1 prose says "manual *upcoming* obligations"; A2's payload key is `manual_obligations_total`. The shorthand is acceptable (not a banned term), but A2 does not pin the user-facing breakdown line labels, leaving the implementer to re-derive them.
3. **Home "Where your money is committed" tiles are not backed by `/api/spendable`.** Screen A shows three committed tiles ("Fund commitments this month", "Pool remaining (all pools)", "Reserved goal balance"). A2 lists these under §UI Touchpoints but the spendable payload provides none of them — they are B1/funds-summary data. A2 should state that the Home screen is only *partially* backed by A2 (headline + card obligation), and the committed tiles depend on B1. This is a sequencing fact that affects when Home can render in full.
4. **Confidence/stale surfacing on Home is implicit.** A2 defines `confidence` (current/provisional/stale/blocked) and warning codes, but Screen A folds the stale-source signal into the "Next action" card ("Latest Chase transaction is 19 days old …") and a Card-obligation subhead, with no standalone confidence chip on the headline. A2 should say where confidence/warnings surface on Home so the implementer doesn't invent a new chip.

### Recommended doc edits
- §API Contract: model card obligation as a per-card list (e.g. `card_obligation_items[]` with `card`, `owed`, `note`/`status`) plus the scalar total, so Screen A's table and Note column are backed. Keep the "(not yet netted)" heading intent in §UI Touchpoints.
- §UI Touchpoints: pin the three breakdown line labels (Verified liquid cash / Reserved goal balance / Manual obligations) to match Screen A, and note "Manual obligations" is the display shorthand for D1's manual upcoming obligations.
- §UI Touchpoints: add an explicit note that the Home "Where your money is committed" tiles are sourced from B1 funds summary, not `/api/spendable`, so the full Home render depends on B1 (A2 backs the headline + card obligation only).
- §UI Touchpoints / §API Contract: state where `confidence`/`warnings` surface on Home (Next-action card + card-obligation subhead per Screen A) rather than a new headline chip.

---

## A3 Auth — Approved with notes

Mockup screens: F (Personal login + first-boot enrollment) and F-qa (QA dev-bypass variant).

### Decision (D3/D8/D10) alignment
- **D3:** Argon2id passphrase + TOTP + one-time recovery codes; HttpOnly, SameSite=Strict, localhost-bound sessions; idle 8h / absolute 7d; first-boot owner then administrator invitation; QA dev bypass behind a visible banner. The doc matches all of these (§Middleware And Session Spec, §First-Boot Enrollment, §QA DEV_MODE Bypass).
- **D8:** one shared household ledger, role→persona mapping, audit records the actor (§Integration With Permissions). Matches.
- **D10:** first-boot recovery kit stored outside `DATA_ROOT`, break-glass reset via `DATA_ROOT/recovery/`, reset preserves financial data, runbook `docs/runbooks/auth-recovery.md` (§First-Boot Enrollment, §`docs/runbooks/auth-recovery.md` Outline). Matches.

### Terminology compliance
Auth introduces no D2 financial terms; the locked vocabulary is largely n/a here. Banned-phrase scan of the login + enroll mockup markup and the A3 doc is clean. Login foot copy "Local only · 127.0.0.1 · No data leaves device" is consistent with the local-first privacy posture.

### Mockup screen (F / F-qa) alignment

Strong structural match. A3 §UI Touchpoints enumerates `#auth-stage`, `data-auth="login"`, `data-auth="enroll"`, `#auth-qa-banner`, `#totp-field`, `#recovery-field`, `#recovery-link`, `#qa-bypass`, and `data-wizard-panel="1|2|3"` — all present in the mockup. The 3-step enrollment wizard (passphrase+confirm → authenticator QR/manual key + 6-digit confirm → 10 recovery codes + acknowledgment-gated continue) matches §First-Boot Enrollment.

Gaps:
1. **Show-passphrase control omitted.** The login card has a `#toggle-passphrase` "Show passphrase" affordance (mockup line, `app.js` toggle). A3 §UI Touchpoints lists the passphrase field but not the show/hide control.
2. **QA variant mechanism could be misread as a user toggle.** The mockup exposes a `data-authmode` Personal / QA dev-bypass **tab** that reveals the red `#auth-qa-banner` + `#qa-bypass` button. In the mockup this is a demo affordance; in the real app the QA banner + bypass must appear **only** when env-gated DEV_MODE bypass is active (`APP_ENV=qa|development` + `DEV_MODE_AUTH_BYPASS=1`), never as a user-facing toggle in personal runtime. A3 describes the env gating correctly but does not call out that the mockup's Personal/QA tab is demo-only, so an implementer could build a user toggle. Worth an explicit note.
3. **Recovery-code count and "Download .txt" vs D10 storage.** Mockup Step 3 commits to **10** one-time codes and offers "Copy codes" + "Download .txt". A3/§First-Boot says "one-time recovery codes shown once" without a count, and D10 requires the kit be stored **outside `DATA_ROOT`** (owner-chosen path or printed). A3 should (a) pin the code count to 10 to match the approved screen, and (b) specify that Copy/Download writes outside `DATA_ROOT` and never into the repo, and that the downloaded kit is the owner's responsibility per D10.
4. **Passphrase strength indicator unspecified.** Step 1 shows a "Strength: Strong" meter. A3 locks no passphrase strength policy. Minor; A3 should note a strength indicator exists with no specific complexity policy locked for v1.1 (so the implementer doesn't invent a hard policy).

### Recommended doc edits
- §UI Touchpoints: add the `#toggle-passphrase` show/hide control to the login-card control list.
- §QA DEV_MODE Bypass (or §UI Touchpoints): add a note that the mockup's Personal/QA `data-authmode` tab is a demo-only switch; in the app the QA banner + dev-bypass button render only under env-gated DEV_MODE and are never a user-facing toggle in personal runtime.
- §First-Boot Enrollment: pin recovery-code count to 10 (matching Screen F Step 3) and state that the Copy/Download recovery-kit actions write outside `DATA_ROOT`, never into git, consistent with D10.
- §First-Boot Enrollment: note the passphrase strength indicator with no locked complexity policy for v1.1.

(Recovery-code sign-in fallback, invitation acceptance, recovery reset/break-glass, and the recovery runbook have **no approved mockup**, which is correct — they are runbook/non-primary-UI surfaces. No UI gate; flag invitation-acceptance and recovery-login screens for a lightweight wireframe before any dedicated UI PR, but they are out of the Phase 1 critical path.)

---

## D1 / D2 / Auth-vs-Mockup-F findings (cross-cut)

### D1 (Spendable formula) vs mockup
Exact match. Screen A's breakdown, headline, opt-in provisional term, and separate card-obligation panel are a faithful render of D1, and A2 codifies the same formula and toggle semantics. The only refinement is mechanical: lock the breakdown line labels and back the per-card obligation table in the API contract (A2 edits above). No formula drift.

### D2 (Terminology) vs mockup F + A2/A3
Clean. Locked terms appear verbatim where financial terms are used (A2, Home, Funds); banned terms appear nowhere in the Home or Auth mockup or in the Phase 1 docs except the prohibition lists. Auth (F/F-qa) introduces no D2 financial vocabulary, so there is no terminology risk there. "Verified liquid cash" and "Manual obligations" are Screen-A breakdown labels, not locked terms and not banned — A2 should treat them as fixed display labels (edit above).

### Auth vs mockup F
Login and enrollment structure match the approved Screen F/F-qa. The four gaps are additive UX details (show-passphrase control, QA-variant-is-env-gated-not-a-toggle, recovery-code count + D10-compliant download, strength indicator) — none change the auth contract, and all are fast-follow doc edits, not redesigns.

---

## Overall gate: Can implementation start for A1 / A2 / A3?

**A1 Schema — GO (no conditions).** Backend-only, UX-neutral, D6/D7/D8 schema shape correct, goal-name-required enforced. The net worth `balance` sign convention is a B3 pre-UI decision, not an A1 blocker.

**A2 Spendable — GO for backend + the spendable portion of Home; apply doc edits as fast-follow.** D1 formula is exact and Screen A is approved and backs the headline, breakdown, provisional toggle, and card-obligation surface. Before/alongside the Home UI PR, land the A2 edits (per-card card-obligation shape, pinned breakdown labels, confidence/warning surfacing) and note that the Home "Where your money is committed" tiles depend on B1 (so a complete Home render is gated on B1 funds summary, but the spendable engine + `/api/spendable` + the headline/card panels are not).

**A3 Auth — GO; apply doc edits as fast-follow.** D3/D8/D10 are faithfully specified and Screen F/F-qa (login + enrollment) is approved and matches. Land the four A3 edits (show-passphrase control, QA-variant-is-env-gated note, recovery-code count + D10-compliant download path, strength indicator) before the auth UI PR. Recovery-code login, invitation acceptance, and break-glass reset have no mockup but are non-primary/runbook surfaces and are out of the Phase 1 critical path; give them a lightweight wireframe before any dedicated UI PR.

No terminology blockers. No D1 formula drift. No code changes were made as part of this review.

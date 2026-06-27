# v1.1 Phase 1 Engineering Docs — UX Review

Reviewer role: Sr UX/UI designer (Opus)
Scope: UX alignment only. No code reviewed, no code changed.
Date: 2026-06-26
Branch: `feat/v1-1-engineering`

## Inputs reviewed

- `planning/v1_1_expansion_decision_record.md` (D1-D11; D1 spendable formula, D2 terminology lock, D3/D8/D10 auth)
- `planning/mockups/v1_1/index.html` (owner-approved 2026-06-26): Screen A Home, plus Auth stage `data-auth="login"` (F1) and `data-auth="enroll"` (F2/F3), and the Personal / QA dev-bypass mode tabs (F-qa)
- `planning/engineering/v1_1_00_overview.md`
- `planning/engineering/v1_1_a1_schema.md`
- `planning/engineering/v1_1_a2_spendable.md`
- `planning/engineering/v1_1_a3_auth.md`

## Method

For each doc: confirm terminology against the D2 lock, verify the D1 spendable formula and headline numbers against Screen A, compare the auth contract against the approved login/enroll/QA mockup, and list specific, section-referenced doc edits. A full-tree scan for the four banned phrases (`envelope`, `give every dollar a job`, `available to spend`, `age of money`) returned **no user-facing violations in any Phase 1 doc** — the only hits are the prohibition lists themselves (`v1_1_00_overview.md` §Terminology Lock) and unrelated older planning docs.

## Summary table

| Doc | Mockup surface | Terminology (D2) | Status |
| --- | --- | --- | --- |
| Overview | screen-ID map (all) | Pass | Approved |
| A1 Schema | A Home (snapshot fields), C net worth tile | Pass | Approved with notes |
| A2 Spendable | A Home (headline + card table) | Pass | Approved with notes |
| A3 Auth | Auth login / enroll / QA bypass | Pass | **Changes requested** (doc hygiene blocker) |

---

## Overview (`v1_1_00_overview.md`) — Approved

No mockup screen of its own; defines the screen-ID map and the D2 terminology lock the other docs inherit.

### Terminology compliance
Compliant. §Terminology Lock From D2 reproduces the seven locked terms and the four banned terms verbatim, and correctly carves out snake_case DB names (`fund_pools`, `spendable_balance_snapshots`) while requiring locked UI labels. This is the right canonical source for the set.

### Mockup alignment
- §UI Touchpoints maps every approved screen ID (`home`, `funds`, `dashboard`, `split`, `receipt`, `export`, `data-auth="login"`, `data-auth="enroll"`) to its surface. All eight match the mockup.
- Home touchpoints ("Spendable balance, provisional exposure toggle, card obligation, fund commitment summary") match Screen A's panels.

### Recommended doc edits (optional, non-blocking)
- §UI Touchpoints: the receipt line says "save/start split actions"; the mockup button is literally **"Save & start split from items"**. Use the mockup string so the receipt track (D1) backs the exact label.
- Cross-cutting housekeeping: the earlier Phase 2-5 review flagged a stale "A1 not present in this checkout" note across B1-E1. A1 and A2 are now committed on this branch, so that hedge can be cleared in the downstream docs (tracked here for continuity, not an Overview defect).

---

## A1 Schema (`v1_1_a1_schema.md`) — Approved with notes

Backend schema doc; reviewed for the fields that back user-facing surfaces (Home spendable, net worth tile, goals).

### Terminology compliance
Compliant. §Table Definitions tie each table back to a locked term (e.g. `fund_pools` → "Fund pool / Fund commitment / Pool remaining"), and the doc explicitly states DB snake_case is allowed but UI labels must use D2 terms. No banned terms.

### Decision alignment
- **D7 goal-name-required** is enforced at the schema layer: `financial_goals.name` is NOT NULL plus `CheckConstraint("length(trim(name)) > 0")` and an app-layer blank/whitespace reject. This correctly backs the Screen B "Manage goals" flow's name-before-save rule.
- **D1 spendable** is reproducible: `spendable_balance_snapshots` carries `headline_spendable`, `verified_liquid_cash`, `reserved_goal_balance`, `manual_obligations_total`, `provisional_exposure`, `include_provisional`, and `card_obligation` as separate columns — matching the D1 decomposition and Screen A's breakdown line.
- **D6 net worth** is backed: `valuation_method` (actual/estimate), `confidence` (required for estimates), `source_notes` (required for estimates), `include_in_actual_net_worth`, and `category` examples (`home`, `vehicle`) line up with Screen C's "Actual / With estimates / Confidence" tile and "Estimates never feed Spendable balance" rule.

### Mockup alignment gaps
1. **Snapshot `card_obligation` is a single scalar; Screen A renders a per-card table.** `spendable_balance_snapshots.card_obligation` is correctly scalar for a close/rollup snapshot, but Screen A's Home shows a per-card table (`Card`, `Owed`, `Note`). The per-card breakdown must come from the A2 live payload, not this snapshot. This is a layering note, not a schema defect (see A2 finding #1 and the Phase 2-5 B1 finding).
2. **No locked column for the "Manual obligations" Home line.** `manual_obligations` is correctly modeled, but D1/D2 do not lock a display label for this line, and Screen A shows it as "Manual obligations" while D1 prose says "manual upcoming obligations." Flagging for label consistency (see A2 finding #2); no schema change needed.

### Recommended doc edits
- §`spendable_balance_snapshots`: add a one-line note that per-card obligation detail (the Screen A table) is served by the A2 live payload `source_details`, and the snapshot stores only the summed `card_obligation` for close reproducibility.
- §Relationship To Existing Tables → `settings`: it already notes A2 may add liquid-inclusion settings; cross-reference the eventual display label for manual obligations so the Home line text is owned in one place.

---

## A2 Spendable (`v1_1_a2_spendable.md`) — Approved with notes

Mockup surface: Screen A (Home) headline panel + card obligation table. This is the D1 core and the tightest doc-to-mockup numeric match in Phase 1.

### Terminology compliance
Compliant. §UI Touchpoints lists the required locked terms (Spendable balance, Reserved goal balance, Provisional exposure, Card obligation, Fund commitment, Pool remaining) and references the exact mockup IDs (`#spendable-label`, `#spendable-amount`, `#provisional-toggle`, `#prov-op`, `#prov-term`, `#spendable-note`). No banned terms.

### D1 formula verification — exact match
- Formula `headline = verified_liquid_cash − reserved_goal_balance − manual_upcoming_obligations`, with provisional subtracted only when toggled, matches D1 verbatim.
- Worked numbers match Screen A to the cent: headline `$3,412.58` = `6,180.00 − 1,900.00 − 867.42`; toggle-on headline `$1,570.58` = `3,412.58 − 1,842.00`; `card_obligation $1,523.23` = `1,204.33 + 318.90` (Screen A's two card rows). The unit-test matrix encodes the same values.
- Provisional default off, separate line, and the toggle/notes copy ("Excludes $X provisional exposure (unreviewed outflows)." / "Include provisional exposure ($X unreviewed).") match Screen A's `#spendable-note` and `#provisional-toggle` strings exactly.
- D6 boundary ("Estimates from `net_worth_snapshots` never feed Spendable balance") is stated in §Edge Cases and the test matrix.

### Mockup alignment gaps
1. **Card obligation payload does not yet back the Screen A "Note" column.** Screen A's card table has three columns — `Card`, `Owed`, `Note` — with per-row notes ("Pool remaining already reflects this", "Statement due Jul 02"). The A2 `source_details` example carries `source_key`, `display_name`, `role`, `latest_transaction_date`, `balance`, `confidence` but no note/owed-labeled field for card rows, and the sample only shows a `liquid_cash` row. As specced, the UI can render `Card` and `Owed` but has nothing to populate `Note`.
2. **"Manual obligations" Home label not pinned.** §UI Touchpoints lists the locked terms but not the Home breakdown line label; Screen A shows "Manual obligations $867.42" while the formula/prose use "manual upcoming obligations." Pick one user-facing string.
3. **Card panel title.** Screen A titles the panel "Card obligation (not yet netted)". The doc uses "Card obligation" consistently (good), but the parenthetical "(not yet netted)" framing — the deliberate reassurance that card balances are intentionally excluded from headline — is not captured as UI copy intent.

### Recommended doc edits
- §API Contract → `source_details`: specify that card-obligation entries appear in `source_details` with the normalized positive `owed` amount and an optional `note` field (or state explicitly that the `Note` column is static UI copy), so Screen A's three-column table is fully backed. Mirror this with the Phase 2-5 B1 per-card recommendation so A2 and B1 stay consistent.
- §UI Touchpoints: pin the Home breakdown label for manual obligations (recommend "Manual obligations" to match the approved mockup) and note it should be consistent with A1/settings.
- §Provisional Exposure Toggle Semantics or §UI Touchpoints: capture the "(not yet netted)" card-panel framing as the intended UX tone (card balances are deliberately separate from headline until payment imports).

---

## A3 Auth (`v1_1_a3_auth.md`) — Changes requested

Mockup surface: Auth stage — `data-auth="login"` (F1), `data-auth="enroll"` (F2/F3), and the Personal / QA dev-bypass mode tabs with `#auth-qa-banner` (F-qa).

### Blocking doc-hygiene issues (the reason this is Changes requested)
1. **The doc is absent from the working tree.** `git status` shows `D planning/engineering/v1_1_a3_auth.md` (deleted, unstaged). The file does not currently exist on disk, so GPT cannot implement A3 against a tracked, in-tree spec. It must be restored.
2. **The last committed version is the document duplicated end-to-end.** `git show HEAD:…/v1_1_a3_auth.md` contains two full concatenated copies of the spec (~728 lines; the spec ends and restarts at "# A3 Auth Engineering Spec"). The two copies have **diverged**, which creates ambiguity for the implementer:
   - First copy's Auth API table includes `POST /api/auth/dev-bypass`; the second copy's table omits it.
   - First copy: bypass outside QA/DEV_MODE returns `403` with stable code `dev_bypass_not_allowed`. Second copy: "returns a stable auth error" (unnamed code).
   - First copy lists "Must not operate when the app is publicly bound" (and a matching QA test); the second copy drops that constraint and test.
   - Section headings differ ("Schema/API Touchpoints" vs "Schema touchpoints"; "Middleware And Session Spec" vs "Middleware/session spec").

These are not UX defects in the content — they are a readiness blocker. A single canonical copy must be restored to the tree before A3 implementation starts.

### Terminology compliance
Compliant (reviewing the complete first copy). No banned terms; auth copy is functional/system text, and the QA banner string ("QA synthetic demo — not real financial data") matches the mockup `#auth-qa-banner`.

### Decision + mockup alignment (content is strong)
- **D3/D8/D10 fully covered:** Argon2id passphrase + TOTP + one-time recovery codes; sessions HttpOnly, SameSite=Strict, localhost-bound, idle 8h / absolute 7d; first-boot owner, administrator invitation, QA dev bypass; D10 recovery kit + break-glass reset + `docs/runbooks/auth-recovery.md` outline. All present and consistent with the decision record.
- **Login (F1):** §UI Touchpoints references `data-auth="login"`, `#totp-field`, `#recovery-field`, `#recovery-link`, and `#qa-bypass` — all match the mockup login card.
- **Enroll (F2/F3):** the three wizard panels (`data-wizard-panel="1/2/3"` → passphrase, authenticator, recovery codes) map exactly to the mockup's Step 1/2/3.
- **QA bypass (F-qa):** synthetic-only, visibly banner-marked, off by default, must run through the permission evaluator — matches the mockup's Personal / QA tab model and the danger-styled "Dev bypass (QA only) · synthetic owner" button.

### Mockup alignment gaps (address while restoring the doc)
1. **Recovery-code copy/download affordances not specified.** Mockup enroll Step 3 has "Copy codes" and "Download .txt" controls plus the `#recovery-ack` acknowledgement checkbox. The doc covers "shown once" + acknowledgement but not the copy/download controls — and per D10 a download must target an owner-chosen path **outside `DATA_ROOT`** and never the repo. Worth stating so the implementer doesn't write the kit into a tracked location.
2. **Passphrase strength feedback unmentioned.** Mockup enroll Step 1 shows a "Strength: Strong" indicator. The doc doesn't note whether strength feedback is presentational or backed; call it out so the UI PR has a clear answer.
3. **"Show passphrase" toggle** (`#toggle-passphrase`) on the login card is not referenced. Trivial, but list it with the other login controls for completeness.
4. **QA bypass button label** ("Dev bypass (QA only) · synthetic owner") should be named as the locked QA string alongside the banner copy, so QA UI text matches the approved mockup verbatim.

### Recommended doc edits
- **Restore a single canonical `v1_1_a3_auth.md` to the working tree and de-duplicate it.** Keep the more complete first copy (it has the named `dev_bypass_not_allowed` code, the `POST /api/auth/dev-bypass` route, and the public-binding constraint + test) and delete the second concatenated copy. Reconcile the section-heading casing to one style.
- §UI Touchpoints: add the recovery-code Copy/Download controls and `#recovery-ack`, the passphrase strength indicator, and the `#toggle-passphrase` control; note the D10 rule that any downloaded recovery kit must go outside `DATA_ROOT` and never into git.
- §QA DEV_MODE Bypass: pin the QA banner and bypass-button strings as the locked QA wording mirroring the mockup.

---

## Cross-cutting findings

1. **D2 terminology is clean across Phase 1.** Locked terms are used verbatim where they surface; banned terms appear only in the prohibition lists. No terminology blocker for any of A1/A2/A3.
2. **D1 spendable is implementation-ready.** A2's formula, edge cases, and worked numbers match Screen A to the cent and align with A1's snapshot columns. This is the strongest doc-to-mockup tie in the set.
3. **One contract gap to settle before the Home UI PR:** card obligation is exposed as a scalar (A1 snapshot) and per-source list (A2 `source_details`), but neither yet backs Screen A's `Note` column. Same root issue the Phase 2-5 review raised for B1 — fix A2 and B1 together for one card-obligation contract.
4. **A3 is gated on doc hygiene, not content.** The spec is missing from the tree and the committed copy is duplicated/divergent. Backend security design itself is sound and decision-aligned; it just needs one clean canonical doc in the tree.

---

## Overall gate: Can GPT start A1 / A2 / A3 implementation?

- **A1 Schema — Yes, start now.** Approved with minor notes; the two notes are cross-references, not blockers. Migrations `0009`/`0010` can proceed.
- **A2 Spendable — Yes, start now (after/with A1).** Approved with notes; the formula and numbers are locked to D1 and Screen A. Apply the card-obligation `source_details` and label edits before or alongside the Home UI PR — none block the spendable service or `GET /api/spendable`.
- **A3 Auth — Not yet; one blocking fix first.** Restore a single, de-duplicated `v1_1_a3_auth.md` to the working tree (it is currently deleted on disk, and the committed version is doubled with divergent details). The content is approved-with-notes once restored. Backend auth work should not start against an absent/ambiguous spec; this is a quick housekeeping fix, after which A3 is cleared.

No terminology blockers. No code changes were made as part of this review.

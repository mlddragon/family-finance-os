# v1.1 Phase 2-5 Engineering Docs — UX Review

Reviewer role: Sr UX/UI designer (Opus)
Scope: UX/UI alignment only. No code reviewed, no code changed.
Date: 2026-06-26
Branch: `feat/v1-1-engineering`

## Inputs reviewed

- `planning/v1_1_expansion_decision_record.md` — decisions D1-D11, including the D2 terminology lock.
- `planning/mockups/v1_1/index.html` (owner-approved 2026-06-26) and its `README.md`: Screen A Home, B Funds, C Dashboard, D Split, E Receipt, G Analyst export, plus the Auth login/enroll stage.
- Phase 2-5 engineering docs: `v1_1_b1_funds.md`, `v1_1_b2_splits.md`, `v1_1_b3_net_worth.md`, `v1_1_b4_analyst_export.md`, `v1_1_b5_monthly_close.md`, `v1_1_c1_dashboard.md`, `v1_1_d1_receipts.md`, `v1_1_e1_scraper_framework.md`.
- `v1_1_00_overview.md` (terminology lock, mockup screen-ID map) and `v1_1_a1_schema.md` (now present and committed) for table/field cross-checks.

## Method

For each doc I (1) checked user-facing terminology against the D2 lock, (2) compared the doc's "UI (Mockup Screen)" section against the matching approved mockup screen field-by-field, and (3) wrote specific, section-referenced edits. A repo scan for the four banned phrases (`envelope`, `give every dollar a job`, `available to spend`, `age of money`) plus `zero-based` returned **no user-facing violations**: the only hits are the prohibition lists themselves (`v1_1_00_overview.md` §Terminology Lock and B1 §Non-goals). Where a doc exposes data the mockup cannot drive (or vice versa), I flag it as a contract mismatch rather than a copy nit.

## Summary table

| Doc | Mockup screen | Terminology | Status |
| --- | --- | --- | --- |
| B1 Funds | A Home + B Funds | Pass | Changes requested |
| B2 Splits | D Split | Pass | Approved with notes |
| B3 Net worth | C Dashboard tile | Pass | Approved with notes |
| B4 Analyst export | G Export | Pass | Changes requested |
| B5 Monthly close | none (Reports surface) | Pass | Approved with notes |
| C1 Dashboard | C Dashboard | Pass | Approved |
| D1 Receipts | E Receipt | Pass | Approved with notes |
| E1 Scraper framework | none (Sources/Review) | Pass | Approved with notes |

"Changes requested" = an API-vs-mockup contract gap that should be closed before the UI PR. "Approved with notes" = ship-ready with fast-follow copy/spec edits. Terminology passes everywhere.

---

## B1 Funds — Changes requested

Mockup screens: A (Home), B (Funds).

### Terminology check
Compliant. Uses Fund pool, Fund commitment, Spendable balance, Reserved goal balance, Pool remaining, Provisional exposure, and Card obligation verbatim (§Purpose, §UI). §Non-goals explicitly bans envelope and zero-based language. Minor consistency note: the UI label is "Manual obligations" (mockup Home + B1 §UI), while D1 and the payload use "manual upcoming obligations" / `manual_upcoming_obligations`. Not a D2-locked term, so acceptable, but pick one user-facing label and keep it consistent across Home and any obligations form.

### Mockup gaps
1. **Card obligation is per-card in the mockup, scalar in the API (contract gap).** Home Screen A renders a card-obligation table (`Card`, `Owed`, `Note`) with two rows and per-row notes ("Pool remaining already reflects this", "Statement due Jul 02"). The `GET /api/funds/summary` payload (§API Shape) exposes only a scalar `card_obligation`, and §UI → Home changes says only "Card obligation" with no per-card breakdown or note column. The mocked UI cannot be built from the documented payload.
2. **"Where your money is committed" tiles are underspecified (contract gap).** Screen A shows exactly three tiles — "Fund commitments this month", "Pool remaining (all pools)", "Reserved goal balance" — but `commitment_health` carries only `funded_this_month`, `fund_commitments`, `uncommitted`, `overcommitted`. There is no aggregate **pool-remaining-across-all-pools** field to back tile two.
3. **Overcommit reassurance copy missing.** Screen B's warning band carries the deliberate "Nothing is blocked, but pool remaining assumes full funding" framing. §UI → Funds screen only says "Show warning band when commitments exceed funding" and drops the not-blocked tone.
4. **Pool status vocabulary not enumerated.** Screen B uses "On track", "Not started", and a danger badge "Over by $X"; the doc lists a generic "status" column.
5. **No approved mockup for goal create/edit.** D7 requires a goal-name-before-save form with a `goal_type` selector (`emergency`/`sinking_fund`/`purchase`/`other`), and Screen B has a "Manage goals" button, but there is no approved goal create/edit screen. The doc leans on existing form patterns; that reuse should be stated explicitly, not left implicit.

### Recommended edits
- §API Shape: replace scalar `card_obligation` with a per-card list (e.g. `card_obligations[]` of `{card, owed, note}`) plus a total, and add an aggregate `pool_remaining_total` (in `commitment_health` or a new `committed_overview`) so Screen A's three tiles and card table are backed.
- §UI → Home changes: name the card-obligation table columns (`Card`, `Owed`, `Note`) and the three "Where your money is committed" tiles.
- §UI → Funds screen: capture the overcommit band's "nothing is blocked; pool remaining assumes full funding" intent and enumerate the pool status set (On track / Not started / Over by $X).
- §UI → Funds screen: add an explicit note that goal create/edit reuses existing form patterns with no dedicated approved mockup, and that goal-name-required + `goal_type` selection live there (see implementation gate).

---

## B2 Splits — Approved with notes

Mockup screen: D (Split).

### Terminology check
Compliant. Uses Pool remaining; the D11 enrichment-vs-splits precedence framing is correct (§Purpose). No banned terms. This is the tightest doc-to-mockup match in the set — imported-fact read-only block, allocation rows, Transaction amount / Allocated / Remainder, balanced status, audit preview, and save-disabled-until-balanced all align with Screen D.

### Mockup gaps
1. **Receipt-promotion launch path omitted from the editor section.** Screen E's "Save & start split from items" navigates into Screen D pre-filled, and D1 depends on this. §UI lists launch points as "Review and Transactions" only.
2. **Reset control + reconciliation hints absent from the UI narrative.** Screen D includes a Reset button, and the D11 flow shows reconciliation hints when receipt + split coexist. B2 mentions reconciliation hints only in §Test Plan, not in the editor UX description.

### Recommended edits
- §UI → Split editor behavior: add a third launch source ("from Receipt entry via promote-to-splits, pre-filled with proposed lines") and note the Reset control.
- §UI → Split editor behavior: state where D11 reconciliation hints surface in the editor when a linked receipt already has lines.

---

## B3 Net worth — Approved with notes

Mockup screen: C (Dashboard net worth tile).

### Terminology check
Compliant. "Estimates never feed Spendable balance" appears repeatedly; Spendable balance used verbatim. No banned terms. The estimate guardrails (confidence + as-of date + source note required) match A1's `net_worth_snapshots` app-layer validation.

### Mockup gaps
1. **Confidence metric missing from the tile spec.** Screen C's net worth tile shows three metrics — Actual net worth, With estimates, and **Confidence: Mixed** ("Estimates never feed Spendable balance"). B3 §UI lists actual / with-estimates / toggle / banner but omits the Confidence metric.
2. **No approved mockup for the manual entry form or CSV import preview** — correctly acknowledged. §UI states the entry/import surface lives under Dashboard or Reports "until a dedicated Net Worth screen is approved." Right handling; treat it as an explicit pre-implementation UX dependency for those two surfaces (validation result, rejected rows, accepted count, estimate-required fields).

### Recommended edits
- §UI → Initial UI surfaces: add the "Confidence" tile metric to match Screen C, with the "Estimates never feed Spendable balance" subtext.
- §UI: add a one-line callout that the manual-entry and CSV-import surfaces have no approved mockup yet and should get a lightweight wireframe before the B3 UI PR (backend/API/dashboard-tile work is unblocked).

---

## B4 Analyst export — Changes requested

Mockup screen: G (Analyst export).

### Terminology check
Compliant. Uses Pool remaining and Reserved goal balance; "analyst pack" cleanly replaces the legacy "advisor export"; privacy-boundary copy aligns with Screen G. No banned terms.

### Mockup gaps
1. **No include-estimates control in the export UI (contract gap).** The build request carries `include_estimates` and the bundle includes both net worth views, but Screen G's checklist has **no net worth section and no include-estimates checkbox**. The mocked UI cannot set an option the API exposes.
2. **Recurring-heuristic findings not surfaced in the UI.** §Recurring Heuristic specifies candidate recurring transactions in `summary.json`, but Screen G's checklist has no "Recurring transaction candidates (heuristic)" row, so the user cannot see or opt into that section.
3. Otherwise the checklist maps cleanly: reviewed summary, category totals, fund pool commitments + pool remaining, cashflow 6-month, raw rows off-by-default, account numbers never included, validation/confidence notes.

### Recommended edits
- §UI → Reports / Analyst export surface: add a "Net worth (actual; include estimates)" checklist row + include-estimates control, and note that Screen G's approved checklist must be extended (it currently omits this).
- §UI: add a "Recurring transaction candidates (heuristic, not confirmed)" checklist row so the recurring section is visible and labeled as candidate-only.
- §UI: cross-reference B3/D6 so the estimates-toggle copy in the export matches the dashboard banner language.

---

## B5 Monthly close — Approved with notes

Mockup screen: none (extends the existing Reports surface).

### Terminology check
Compliant. Uses Pool remaining, Reserved goal balance, and Spendable balance verbatim; the D9 draft-allowed / final-blocked framing and Financial Governor override are correct. No banned terms.

### Mockup gaps
1. **Net-new override interaction has no mockup.** The final-close-disabled-with-reason state, the Governor override purpose-note field, and the new funds/spendable gate grouping are net-new interactions, but the Reports stub in the mockup is "Unchanged from v1." §UI deliberately reuses existing badges/bands and says "No separate mockup screen is required" — defensible, but this is a high-stakes, audit-generating, elevated action with no specified copy or state design.
2. **Disabled-final-close reason copy unspecified.** The doc says the button is "disabled with reason" but gives no reason string(s) and does not say how the `funds_and_spendable` blocker/warning lists render.

### Recommended edits
- §UI → Reports / Monthly close changes: specify the disabled-final-close reason copy, how the `funds_and_spendable` blockers/warnings render (reuse the warning-band pattern), and the override purpose-note field label + required-state messaging.
- §UI: recommend a lightweight wireframe (or annotated Reports screenshot) for the Governor override flow before the B5 UI PR, given it is elevated and audited. Backend/gate logic is unblocked.

---

## C1 Dashboard — Approved

Mockup screen: C (Dashboard).

### Terminology check
Compliant. Provisional labeling and net-worth actual-default framing are correct. No banned terms.

### Mockup alignment
Strong, no material gaps:
- Header Freshness / Confidence / Reviewed % matches Screen C.
- Six-month cashflow with provisional marker, category spend, pool target progress (incl. over-target danger "Over by $41"), and the net worth tile with toggle + banner all map to Screen C.
- The doc correctly upgrades the mockup's static div bars to Recharts and **adds** accessibility guidance (text alternatives), which improves on the mockup; Screen C's chart already carries an `aria-label`, so keep that pattern.

### Recommended edits (optional, non-blocking)
- §UI → Dashboard screen: note the period control ("Last 6 months") shown in Screen C's status strip so the `months` param has a UI affordance.

---

## D1 Receipts — Approved with notes

Mockup screen: E (Receipt entry).

### Terminology check
Compliant. The D11 "receipt lines are enrichment until applied as splits" framing is present; Pool remaining used verbatim. No banned terms. Matches Screen E well: manual header fields, line-item editor with Add line item, Items total / Receipt total / Unaccounted, optional-itemization labeling, and the three buttons Cancel / Save & start split from items / Save receipt.

### Mockup gaps
1. **Linked-transaction controls not described.** Screen E shows "Change" and "Unlink" controls on the linked-transaction line; §UI lists "linked transaction" as a field but not those interactions.
2. **Total readonly-when-linked behavior unstated.** In Screen E the Total field is `readonly` and mirrors the linked transaction amount ($189.45). §UI / §CSV treat receipt total as an entered value and never say Total becomes derived/readonly when a transaction is linked.
3. **Receipt review queues have no mockup.** §Review Queues defines eight queue types (unmatched, total mismatch, category needed, mixed-basket, reimbursement, medical-tax, side-hustle, duplicate) that "appear in Review," but Review is a stub in the mockup. The queue items have no approved visual.

### Recommended edits
- §UI → Receipt entry surface: add Change / Unlink linked-transaction controls and define unlink behavior (header total becomes user-entered again; lines retained).
- §UI or §Schema/API: clarify whether `total_amount` is readonly/derived when `transaction_id` is set (as Screen E implies) vs. freely entered for unlinked receipts.
- §UI: note that the receipt review-queue presentation reuses the existing Review queue pattern and has no dedicated approved mockup (low risk; Review already exists in v1).

---

## E1 Scraper framework — Approved with notes

Mockup screen: none (attaches to existing Sources and Review).

### Terminology check
Compliant. D11 promotion language and "receipt lines first" framing are correct. No banned terms.

### Mockup gaps
1. **No approved mockup for any scraper UX** — correctly acknowledged. The vendor-adapter list, enabled/disabled state, run controls, job progress, and required safety copy have no approved screen. §UI defers to Sources/Review and enumerates the required UI copy (local only; no credentials in git; output becomes receipt lines first; apply-as-splits is an explicit later action), which is the right minimum given D5 sequences this last.

### Recommended edits
- §UI: note that a Sources adapter wireframe (adapter list, last-run, run button, safety banner, job progress) should be approved **before the E2 Amazon adapter UI PR**; the E1 framework + API + audit work is unblocked without it.

This is the lowest-risk gate item — D5 sequences all scraper work last and every adapter is disabled-by-default pending per-vendor human QA.

---

## Cross-cutting findings

1. **Stale "A1 not present" banner in every Phase 2-5 doc (now demonstrably false).** Each doc's header says `v1_1_a1_schema.md` "is not present in this checkout" and hedges table/field names with "align to A1 on merge." A1 (and A2, A3) now exist and are committed on this branch. The placeholder table/field names in B1-E1 should be reconciled against the real A1 schema (e.g. `monthly_pool_commitments`, `receipt_line_items`, `pool_category_links`, `manual_obligations`, `spendable_balance_snapshots`) so implementation targets final names, not decision-record approximations. Not a UX defect, but it affects implementation readiness for every approved track — see gate item below.
2. **Missing mockups cluster in forms and elevated flows:** goal create/edit (B1), net worth manual entry + CSV import (B3), Governor override (B5), receipt review queues (D1), and the scraper Sources surface (E1). Backend/API for these is unblocked; the **UI PRs** for these specific surfaces should get lightweight wireframes first. Screen-backed surfaces (Home, Funds tables, Split, Receipt entry, Dashboard, Analyst export) are ready.
3. **Three API-vs-mockup contract mismatches to fix before the relevant UI builds:** B1 scalar card obligation vs. per-card table, B1 missing aggregate pool-remaining tile field, and B4 `include_estimates` (plus recurring heuristic) vs. an export checklist with no estimates/recurring controls.

---

## Implementation gate — can engineering start the approved tracks?

**Yes for the screen-backed scope, with the doc edits above treated as fast-follow.** No terminology blockers anywhere.

- **Start now (UX-ready):** B2 splits, C1 dashboard, and the screen-backed parts of B1 funds (Home spendable + card panel + Funds pool/commitment tables), B3 net worth (API + dashboard tile), and D1 receipt entry. These map to approved Screens D, C, A/B, C, and E.
- **Close the contract gap first, then build UI:** B1 (extend `funds/summary` to per-card obligations + aggregate pool remaining) and B4 (add the include-estimates + recurring controls to Screen G). Backend can proceed in parallel; the UI PRs should wait on these payload/checklist edits.
- **Start backend now, gate the UI PR on a wireframe:** B5 monthly close (specify override copy/states, ideally a Governor-override wireframe) and the form/queue surfaces in cross-cutting #2 (goal create/edit, net worth entry + CSV import, receipt review queues).
- **Defer per build order:** E1 framework backend proceeds once D1/B2/B4 are stable; E2-E4 adapter UI waits on a Sources wireframe and per-vendor human QA.
- **Housekeeping that touches all tracks:** reconcile the stale "A1 not present" banner (cross-cutting #1) so implementation targets the final A1 schema names rather than decision-record placeholders.

No code changes were made as part of this review.

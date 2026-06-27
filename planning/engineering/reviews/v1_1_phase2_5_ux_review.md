# v1.1 Phase 2-5 Engineering Docs — UX Review

Reviewer role: Sr UX/UI designer (Opus)
Scope: UX alignment only. No code reviewed, no code changed.
Date: 2026-06-26
Branch: `feat/v1-1-engineering`

## Inputs reviewed

- `planning/v1_1_expansion_decision_record.md` (D1-D11; D2 terminology lock)
- `planning/mockups/v1_1/index.html` (owner-approved 2026-06-26): Screens A Home, B Funds, C Dashboard, D Split, E Receipt, G Analyst export, plus Auth login/enroll
- Engineering docs: `v1_1_b1_funds.md`, `v1_1_b2_splits.md`, `v1_1_b3_net_worth.md`, `v1_1_b4_analyst_export.md`, `v1_1_b5_monthly_close.md`, `v1_1_c1_dashboard.md`, `v1_1_d1_receipts.md`, `v1_1_e1_scraper_framework.md`
- `v1_1_00_overview.md` for terminology lock and mockup screen-ID map

## Method

For each doc: confirm terminology against the D2 lock, compare the doc's "UI (Mockup Screen)" section against the matching approved mockup screen, and list specific, section-referenced doc edits. A full-tree scan for the four banned phrases (`envelope`, `give every dollar a job`, `available to spend`, `age of money`) plus `zero-based` returned **no user-facing violations** — the only hits are the prohibition lists themselves (`v1_1_00_overview.md` and B1 Non-goals).

## Summary table

| Doc | Mockup screen | Terminology | Status |
| --- | --- | --- | --- |
| B1 Funds | A Home + B Funds | Pass | Approved with notes |
| B2 Splits | D Split | Pass | Approved with notes |
| B3 Net worth | C Dashboard tile | Pass | Approved with notes |
| B4 Analyst export | G Export | Pass | Approved with notes |
| B5 Monthly close | none (Reports surface) | Pass | Approved with notes |
| C1 Dashboard | C Dashboard | Pass | Approved |
| D1 Receipts | E Receipt | Pass | Approved with notes |
| E1 Scraper framework | none (Sources/Review) | Pass | Approved with notes |

---

## B1 Funds — Approved with notes

Mockup screens: A (Home), B (Funds).

### Terminology compliance
Compliant. Uses Fund pool, Fund commitment, Spendable balance, Reserved goal balance, Pool remaining, Provisional exposure, Card obligation verbatim. Non-goals (§Non-goals) explicitly ban envelope and zero-based language. No D2 violations.

### Mockup screen alignment gaps
1. **Card obligation is per-card in the mockup, single-value in the doc.** Home Screen A renders a card-obligation table (`Card`, `Owed`, `Note`) with two rows and a per-row note ("Pool remaining already reflects this", "Statement due Jul 02"). The `GET /api/funds/summary` payload (§API Shape) exposes only a scalar `card_obligation`, and the Home UI list (§UI → Home changes) says only "Card obligation" without the per-card breakdown or note column.
2. **Home "Where your money is committed" metrics underspecified.** Screen A shows exactly three tiles: "Fund commitments this month", "Pool remaining (all pools)", "Reserved goal balance". The doc (§UI → Home changes) says only "Add 'Where your money is committed' metrics linking to Funds" and the payload has no aggregate **pool remaining across all pools** field (`commitment_health` carries `funded_this_month`, `fund_commitments`, `uncommitted`, `overcommitted` only).
3. **Overcommit reassurance copy missing.** Screen B warning band carries the "Nothing is blocked, but pool remaining assumes full funding" reassurance. The doc (§UI → Funds screen) says "Show warning band when commitments exceed funding" without capturing the not-blocked framing, which is a deliberate UX tone choice.
4. **Pool status vocabulary not enumerated.** Screen B uses "On track", "Not started", and a danger badge "Over by $X". The doc lists a generic "status" column.
5. **No approved mockup for goal create/edit.** D7 + the doc require a goal-name-before-save form, and Screen B has a "Manage goals" button, but no goal create/edit form screen is in the approved mockup. The doc relies on existing form patterns; this should be called out as an intentional reuse rather than a silent gap.

### Recommended doc edits
- §API Shape: change `card_obligation` to a per-card list (e.g. `card_obligation_items[]` with `card`, `owed`, `note`) plus a total, and add an aggregate `pool_remaining_total` to `commitment_health` (or a top-level `committed_overview`) so Screen A's three tiles are backed.
- §UI → Home changes: specify the card-obligation table columns (`Card`, `Owed`, `Note`) and the three "Where your money is committed" tiles by name.
- §UI → Funds screen: add the overcommit band copy intent ("nothing is blocked; pool remaining assumes full funding") and enumerate the pool status set (On track / Not started / Over by $X).
- §UI → Funds screen: add an explicit note that goal create/edit reuses existing form patterns with no dedicated approved mockup, and that goal-name-required + goal_type selection live there.

---

## B2 Splits — Approved with notes

Mockup screen: D (Split).

### Terminology compliance
Compliant. Uses Pool remaining; D11 enrichment-vs-splits framing is correct. No banned terms.

### Mockup screen alignment gaps
1. **Receipt-promotion entry path not described in the editor section.** Screen E's "Save & start split from items" navigates into Screen D, and D1 depends on the split editor opening with proposed allocation lines. B2 §UI lists launch points as "Review and Transactions" only, omitting the receipt-promotion entry that arrives pre-filled.
2. **Reset button + reconciliation hints not in the UI section.** Screen D includes a Reset button and the broader D11 flow shows reconciliation hints when receipt+split coexist. B2 mentions reconciliation hints only under tests, not in the editor UX description.

### Recommended doc edits
- §UI → Split editor behavior: add a third launch source ("from Receipt entry via promote-to-splits, pre-filled with proposed lines") and note the Reset control.
- §UI → Split editor behavior: state where D11 reconciliation hints surface in the editor when a linked receipt already has lines.

Otherwise B2 is the tightest doc-to-mockup match in the set (imported-fact read-only block, allocation rows, remainder/balanced status, audit preview, save-disabled-until-balanced all align with Screen D).

---

## B3 Net worth — Approved with notes

Mockup screen: C (Dashboard net worth tile).

### Terminology compliance
Compliant. "Estimates never feed Spendable balance" stated repeatedly; Spendable balance used verbatim. No banned terms.

### Mockup screen alignment gaps
1. **Confidence label missing from the tile spec.** Screen C net worth tile shows a third metric "Confidence: Mixed" with subtext "Estimates never feed Spendable balance". B3 §UI lists actual / with-estimates / toggle / banner but not the Confidence metric.
2. **No approved mockup for manual entry form or CSV import** — correctly acknowledged. B3 §UI states the entry/import surface lives under Dashboard or Reports "until a dedicated Net Worth screen is approved." This is the right handling; flag it as an explicit pre-implementation UX dependency for the entry/import screens.

### Recommended doc edits
- §UI → Initial UI surfaces: add the "Confidence" tile metric to match Screen C, with the "Estimates never feed Spendable balance" subtext.
- §UI: add a one-line callout that the manual-entry and CSV-import surfaces have no approved mockup yet and should get a lightweight wireframe before the B3 UI PR (backend/API work is unblocked).

---

## B4 Analyst export — Approved with notes

Mockup screen: G (Analyst export).

### Terminology compliance
Compliant. Uses Pool remaining, Reserved goal balance; "analyst pack" replaces legacy "advisor export". Privacy-boundary copy aligns. No banned terms.

### Mockup screen alignment gaps
1. **No include-estimates control in the export UI.** B4's build request carries `include_estimates` and the bundle includes both net worth views, but Screen G's checklist has **no net worth section and no include-estimates checkbox**. The export UI as mocked cannot set the option the API exposes.
2. **Checklist item parity.** Screen G checklist items map cleanly to the doc except for the net worth gap above; the rest (reviewed summary, category totals, fund pool commitments + pool remaining, cashflow 6mo, raw rows off, account numbers never, validation notes) align.

### Recommended doc edits
- §UI → Reports / Analyst export surface: add an explicit "Net worth (actual; include estimates)" checklist row + include-estimates control so the UI can drive the `include_estimates` build option, and note that Screen G's approved checklist must be extended for this (mockup currently omits it).
- §Non-goals or §UI: cross-reference B3/D6 so the estimates toggle copy in the export matches the dashboard banner language.

---

## B5 Monthly close — Approved with notes

Mockup screen: none (extends existing Reports surface).

### Terminology compliance
Compliant. Uses Pool remaining, Reserved goal balance, Spendable balance verbatim; D9 draft/final framing is correct. No banned terms.

### Mockup screen alignment gaps
1. **Net-new override interaction has no mockup.** The Final-close-disabled-with-reason state, the Governor override purpose-note field, and the funds/spendable gate grouping are new interactions. The Reports stub in the mockup is "Unchanged from v1." B5 §UI deliberately reuses existing badges/bands and states "No separate mockup screen is required," but the override flow is a high-stakes, audit-generating action that currently has no specified copy or state design.
2. **Disabled-final-close reason copy unspecified.** The doc says the button is "disabled with reason" but does not give the reason string(s) or how the blocker list renders.

### Recommended doc edits
- §UI → Reports / Monthly close changes: specify the disabled-final-close reason copy and how the `funds_and_spendable` blocker/warning lists render (reuse warning-band pattern), and the override purpose-note field label + required-state messaging.
- §UI: add a short note recommending a lightweight wireframe (or annotated Reports screenshot) for the Governor override flow before the B5 UI PR, given it is an elevated, audited action. Backend/gate logic is unblocked.

---

## C1 Dashboard — Approved

Mockup screen: C (Dashboard).

### Terminology compliance
Compliant. Provisional labeling, net-worth actual-default framing correct. No banned terms.

### Mockup screen alignment
Strong alignment, no material gaps:
- Header Freshness / Confidence / Reviewed % matches Screen C.
- Six-month cashflow with provisional marker, category spend, pool target progress (incl. over-target danger "Over by $41"), and net worth tile with toggle + banner all map to Screen C.
- The doc correctly upgrades the mockup's static div bars to Recharts and **adds** accessibility guidance (text alternatives), which improves on the mockup; Screen C's chart already carries an aria-label, so keep that pattern.

### Recommended doc edits (optional, non-blocking)
- §UI → Dashboard screen: note the period control ("Last 6 months") shown in Screen C's status strip so the cashflow `months` param has a UI affordance.

---

## D1 Receipts — Approved with notes

Mockup screen: E (Receipt entry).

### Terminology compliance
Compliant. D11 "receipt lines are enrichment until applied as splits" framing present; Pool remaining used. No banned terms.

### Mockup screen alignment gaps
1. **Linked-transaction controls not described.** Screen E shows "Change" and "Unlink" controls on the linked transaction line. D1 §UI lists "linked transaction" as a field but not the change/unlink interactions.
2. **Total readonly-when-linked behavior unstated.** In Screen E the Total field is `readonly` (mirrors the linked transaction amount $189.45). D1 §UI / §CSV treat receipt total as an entered value and do not specify that Total becomes derived/readonly when a transaction is linked.

### Recommended doc edits
- §UI → Receipt entry surface: add Change / Unlink linked-transaction controls and define behavior on unlink (header total becomes user-entered again; lines retained).
- §UI or §Schema/API: clarify whether `total_amount` is readonly/derived when `transaction_id` is set (as Screen E implies) vs. freely entered for unlinked receipts.

Otherwise D1 matches Screen E well (manual header fields, line-item editor with Add line item, Items total / Receipt total / Unaccounted, optional-itemization labeling, and the three buttons Cancel / Save & start split from items / Save receipt).

---

## E1 Scraper framework — Approved with notes

Mockup screen: none (attaches to existing Sources and Review).

### Terminology compliance
Compliant. D11 promotion language and "receipt lines first" framing correct. No banned terms.

### Mockup screen alignment gaps
1. **No approved mockup for any scraper UX** — correctly acknowledged. Vendor-adapter list, enabled/disabled state, run controls, job progress, and the required safety copy have no approved screen. E1 §UI defers to Sources/Review and enumerates required UI copy (local only; no credentials in git; output becomes receipt lines first; apply-as-splits is an explicit later action), which is the right minimum.

### Recommended doc edits
- §UI: add a note that a Sources adapter wireframe (adapter list, last-run, run button, safety banner, job progress) should be approved **before the E2 Amazon adapter UI PR**; the E1 framework + API + audit work is unblocked without it, consistent with E1 being last in build order.

This is the lowest-risk gate item because D5 sequences all scraper work last and every adapter is disabled-by-default pending per-vendor human QA.

---

## Cross-cutting findings

1. **Stale A1 schema note in every Phase 2-5 doc.** Each doc's header says `v1_1_a1_schema.md` "is not present in this checkout." A1 and A2 docs now exist in the tree (untracked). The "align to A1 on merge" hedging in B1-E1 (Tables sections) should be reconciled against the now-present A1 so GPT-5.5 implements against final table/enum names rather than the placeholder names from the decision record. Not a UX defect, but it affects implementation readiness for every approved track.
2. **Missing mockups concentrated in forms and elevated flows:** goal create/edit (B1), net worth manual entry + CSV import (B3), Governor override (B5), scraper Sources surface (E1). Backend/API for these is unblocked; the **UI PRs** for these specific surfaces should get lightweight wireframes first. Screen-backed surfaces (Home, Funds tables, Split, Receipt, Dashboard, Analyst export) are ready.
3. **Two API-vs-mockup contract mismatches worth fixing before UI build:** B1 single-value card obligation vs. per-card table, and B4 `include_estimates` option vs. an export checklist that has no estimates control.

---

## Overall gate: Can GPT-5.5 start implementation for approved tracks?

**Yes, for the screen-backed scope, with the doc edits above treated as fast-follow.**

- **Start now (UX-ready):** B1 funds (pools/commitments/spendable surfaces), B2 splits, B3 net worth (API + dashboard tile), C1 dashboard, D1 receipts. These map to approved Screens A/B, D, C, C, E respectively. Apply the small doc edits before or alongside the UI PRs; none block backend/API work.
- **Start backend now, gate the UI PR on a wireframe:** B4 export (add the include-estimates control to Screen G first), B5 monthly close (specify override copy/states, ideally a Governor-override wireframe), plus the form surfaces flagged in cross-cutting finding #2.
- **Defer per build order:** E1 framework backend can proceed when D1/B2/B4 are stable; E2-E4 adapter UI waits on a Sources wireframe and per-vendor human QA.
- **One blocking-ish housekeeping item for all tracks:** reconcile the stale "A1 not present" note (cross-cutting #1) so implementation targets final A1 names.

No terminology blockers. No code changes were made as part of this review.

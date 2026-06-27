# v1.1 B1 Implementation — UX Review (vs mockups)

Reviewer role: Sr UX/UI designer (Opus)
Scope: UX/UI alignment of the shipped B1 code against the owner-approved mockups. No code changed.
Date: 2026-06-26
Branch: `feat/v1-1-engineering`
Commit reviewed: `d950066` ("feat(v1.1): B1 fund pools, goals, and Funds/Home UI.")

## Verdict: Changes requested

Home and Funds match the approved mockups closely and the locked terminology is clean throughout. The items that warrant changes before this is "done" are concentrated in the **Auth stage** (no recovery-code sign-in path, and an enrollment flow that asks the owner to confirm they saved recovery codes before the codes exist) and one **functional defect** (the Funds/Home month is hard-coded). Everything on Home/Funds is either compliant or a small, fast-follow polish item.

## Inputs reviewed

- `planning/mockups/v1_1/index.html` (owner-approved 2026-06-26): Screen A Home, Screen B Funds, Auth stage (F1 login, F2/F3 enrollment wizard).
- `planning/engineering/v1_1_b1_funds.md` — B1 engineering plan and §UI intent.
- Implementation at `d950066`:
  - `apps/web/src/App.tsx` — `HomeScreen` (~L1249-1359), `FundsScreen` (~L1361-1516), `AuthStage` (~L493-647), screens/nav array (~L101-113), `emptyFundsSummary` (~L172-195).
  - `apps/web/src/types.ts` — `SpendableSummary`, `FundPoolSummary`, `FinancialGoal`, `FundsSummary` (~L143-239).
  - `apps/web/src/locales/en-US.ts` — `nav.funds` (L8).
  - `apps/api/family_finance_os/funds.py` — `funds_summary` (L139-173), `_pool_status` (L707-712).
  - `apps/web/src/styles.css` — `headline-panel`, `breakdown`, `warn-band`, `status-badge` (committed).

## Method

For Home, Funds, and the Auth stage I compared the rendered structure, copy, and column/field set against the matching mockup screen, then checked the backing types/payload so the divergence is attributed correctly (UI omission vs missing data). Terminology was checked against the D2 lock (Fund pool, Fund commitment, Spendable balance, Reserved goal balance, Pool remaining, Provisional exposure, Card obligation).

---

## Terminology check — Pass

All locked terms appear verbatim in the UI:

- "Spendable balance" headline (`App.tsx` L1281), "Verified liquid cash", "Reserved goal balance", "Manual obligations", "Provisional exposure" in the breakdown (L1284-1292).
- "Card obligation (not yet netted)" (L1312) — matches mockup `index.html` L72.
- "Fund commitments", "Pool remaining", "Funded this month", "Uncommitted"/"Overcommitted" (L1429-1438).
- Pool status set "On track" / "Not started" / "Over by $X" generated server-side in `_pool_status` (`funds.py` L707-712), matching mockup `index.html` L140-144.

Consistency note (not a D2 term, carry-over from the docs review): the UI label is "Manual obligations" (L1288) while the payload/field is `manual_upcoming_obligations`. This matches the mockup, so no change required here — just keep one user-facing label if an obligations entry form is added later.

---

## Home (Screen A) — Approved with notes

Implemented and faithful to the mockup:

- Spendable headline panel with breakdown and the provisional toggle (L1280-1308). The toggle math (`decimalSubtract(headline, provisional_exposure)` when checked, L1260-1262) correctly treats provisional exposure as an additional subtraction and leaves the default headline formula untouched — exactly the mockup's intent (`index.html` L61-68). Note copy matches both states (L1296-1300).
- Card obligation table with `Card` / `Owed` / `Note` columns (L1313-1320), header verbatim.
- "Where your money is committed" panel with the three tiles (Fund commitments this month, Pool remaining (all pools), Reserved goal balance) and an "Open Funds" button (L1333-1356).

### Mockup gaps / divergences

1. **Card obligation total not surfaced (low).** The payload carries `card_obligation_total` (`types.ts` L149; `funds.py` L157) and the mockup calls for "a total for summary use" (`v1_1_b1_funds.md` §UI → Home), but the table (L1313-1320) renders rows only, no total/footer. Add a total row or caption.
2. **Home carries the legacy operator metric grid (product decision).** Between the card-obligation panel and the committed panel, the implementation renders a six-tile operator overview — Latest import, Open blockers, Review queue, Required sources, Monthly close, Data root (L1324-1331). This is not in the approved Screen A, which is a leaner household view. Functionally fine, but it changes the page's center of gravity from "what can I spend / where is it committed" to an operator console. Flag for owner: keep operator tiles on Home, or move them behind an operator/validation surface to match the approved mockup's focus.
3. **"Next action" reduced from a callout to a heading element (low).** Mockup Screen A has a standalone next-action band with an explanatory sentence (`index.html` L86-90). The implementation collapses it to label + `<strong>` inside the screen heading with no explanation line (L1274-1277). Restore the one-line "why" if Home is meant to guide the next step.
4. **Confidence not shown on Home (low).** `spendable.confidence` is returned (`funds.py` L160) and the mockup shows "Confidence: Provisional" in the topbar status strip. Confirm this is intentionally handled in the header elsewhere; if not, surface it near the headline so a provisional spendable number is visibly qualified.

---

## Funds (Screen B) — Approved with notes

Implemented and faithful:

- Funds nav entry (`screens` L106, `nav.funds` locale L8). Mockup tags it "new" (`index.html` L28); the implementation omits the tag — cosmetic only.
- Commitment health: three metrics with the Uncommitted→Overcommitted label/ tone swap (L1430-1438). This is a small improvement over the static mockup and reads well.
- Overcommit warning band (L1414-1426) reproduces the deliberate reassurance copy verbatim: "Nothing is blocked, but pool remaining assumes full funding."
- Pools table with Pool / Commitment / Spent / Pool remaining / Status, danger badge for "Over by $X" (L1442-1463); status vocabulary enforced server-side (`funds.py` L707-712).
- Reserved goal balance table Goal / Target / Reserved / Remaining to target (L1465-1477).
- Goal create form gates on a non-empty name (disabled submit + `aria-invalid` + inline error, L1387-1394, L1484, L1503-1512) and offers the D7 `goal_type` set emergency/sinking_fund/purchase/other (L1488-1493). Matches the D7 requirement and the plan's §UI gate.

### Mockup gaps / divergences

1. **Negative "Pool remaining" cell not styled as danger (low).** Mockup applies `danger-text` to the negative number itself (e.g. −$41.10, `index.html` L141, L143) in addition to the status badge. The implementation styles only the badge (L1452-1460); the Pool remaining cell renders a plain `formatMoney` (L1451). Apply the danger class when the value is negative for visual parity.
2. **Goal form omits `target_date` and `linked_fund_pool_id` (low/fast-follow).** `financial_goals` includes both per A1/D7, and "Remaining to target" implies a date matters, but the form collects only name/type/target/reserved (L1481-1502). Acceptable for B1 (the plan only hard-requires name + goal_type), but add target date and pool link in the goal-form fast-follow.
3. **No "Manage goals" affordance (low).** Mockup Screen B has a "Manage goals" button beside the Reserved goal balance heading (`index.html` L153); the implementation instead exposes an inline "Add financial goal" form (L1479-1513). This is the plan-sanctioned "reuse existing form patterns" approach, so it's fine — noting the divergence for traceability. There is no edit/archive path for an existing goal yet.
4. **Funds/Home month is hard-coded (medium — functional defect).** `fetchFundsSummary("2026-06")` is a literal (`App.tsx` ~L659). Spendable, commitment health, pools, and the overcommit band will all show June 2026 regardless of the real date, and there is no month selector. At minimum default to the current month; ideally add the month control the summary endpoint already supports (`GET /api/funds/summary?month=`).

---

## Auth stage (Screen F) — Changes requested

The `AuthStage` (L493-647) implements local sign-in and owner enrollment with passphrase + authenticator code, the QA dev-bypass affordance, and the "Local only · 127.0.0.1" footer. Using a manual TOTP key instead of a QR image (L582-585) is acceptable and consistent with the no-external-calls boundary (the mockup QR is itself a placeholder).

### Gaps

1. **No recovery-code sign-in path (medium).** Mockup F1 provides "Lost your device? Use a recovery code" with a recovery-code field (`index.html` L461-469). The login form (L566-621) has passphrase + authenticator code only — no recovery affordance. An owner who loses their authenticator cannot sign in from the UI, which undercuts the whole point of issuing recovery codes at enrollment. Add the recovery-code entry path to login.
2. **Enrollment asks the owner to confirm saved recovery codes before the codes exist (medium — flow ordering).** The enroll submit button is disabled until `recoveryAcknowledged` is checked (L597-606, L610-617), but recovery codes are only returned and rendered in `enrollMutation.onSuccess` *after* enrollment completes, at which point `auth-status` is invalidated and the user is navigated into the app (L521-523, L632-638). So "I have saved the recovery codes" must be checked before any codes have been shown, and there is no gated step to actually save them. Mockup F3 is a dedicated final step that displays the 10 codes first and then gates on the acknowledgment (`index.html` L511-529). Restructure so the ack gate follows code display (e.g. show codes after TOTP confirm, then require ack before finishing).
3. **No staged enrollment wizard / progress indicator (low).** Mockup F2/F3 is a three-step wizard (Passphrase → Authenticator → Recovery codes) with step chips (`index.html` L479-535). The implementation mutates a single card in place. The flow works; the missing orientation is cosmetic, but fixing gap #2 naturally pushes toward the staged layout.
4. **Login extras from the mockup absent (low).** No "Show passphrase" toggle (mockup `index.html` L457). The login form also adds a Username field (L567-570) the single-owner mockup omits — fine if the backend needs it, but consider prefilling/hiding it. The authenticator input uses `maxLength={12}` with an unqualified "Authenticator code" label (L588-595), whereas the mockup is a 6-digit field labeled "(6 digits)"; the extra length only makes sense once the field also accepts recovery codes (gap #1), so align the label/length with whatever it actually accepts.

---

## Recommended fixes (prioritized)

Medium (address before B1 is considered complete):

- `App.tsx` ~L659: stop hard-coding `"2026-06"`; default to current month and/or add a month selector wired to `GET /api/funds/summary?month=`.
- `App.tsx` L566-621: add a recovery-code sign-in path on the login form (mockup F1).
- `App.tsx` L513-638: reorder enrollment so recovery codes are displayed before the "I have saved the recovery codes" ack gate, and before navigating into the app.

Low (fast-follow polish):

- `App.tsx` L1313-1320: show the `card_obligation_total` as a table total/caption.
- `App.tsx` L1451: apply danger styling to negative Pool remaining values.
- `App.tsx` L1481-1502: add `target_date` and `linked_fund_pool_id` to the goal form; add a goal edit/archive path.
- `App.tsx` L1274-1277: restore the next-action explanatory line on Home.
- Confirm Confidence is surfaced (header) for a provisional spendable headline; if not, add it near L1280.
- `App.tsx` L588-595 / L567-570: align authenticator field length+label with its real input, optionally add "Show passphrase", reconsider the login Username field.

Product decision (owner):

- Home operator metric grid (`App.tsx` L1324-1331): keep on Home or relocate to match the leaner approved Screen A.

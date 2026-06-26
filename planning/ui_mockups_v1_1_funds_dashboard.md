# UI Mockups v1.1 — Funds, Dashboard, Splits, and Auth

This document captures proposed low-fidelity UI mockups for the Family Finance OS v1.1 feature
expansion: a spendable-balance home, the funds (pool) screen, an analytical dashboard,
transaction split and receipt entry, authentication (passphrase + TOTP), and the analyst export
screen. It is a planning artifact only. It does not start app implementation, create frontend or
backend code, add dependencies, create schema, or migrate financial data.

It extends [ui_mockups_v1.md](ui_mockups_v1.md). Read that first. v1.1 keeps the same operator-facing,
local-first, read-mostly direction and the same global frame (sidebar nav, status header, single
content column). All examples are synthetic/redacted.

## Status

- Builds on the owner-approved v1 UI direction (2026-06-18).
- **Owner-approved 2026-06-26** — interactive HTML mockups at [mockups/v1_1/index.html](mockups/v1_1/index.html); UI implementation PRs may proceed.
- Reflects approved v1.1 decisions D1–D11 (see [v1_1_expansion_decision_record.md](v1_1_expansion_decision_record.md)).
- Visual styling is intentionally low fidelity in this doc; HTML mockups carry layout intent for build.
- Resolved UX questions are recorded in the decision record; remaining items are implementation gates only.
- **Interactive HTML mockups** (visual-only, no backend) render these wireframes with the real app's
  design tokens: [mockups/v1_1/index.html](mockups/v1_1/index.html). See
  [mockups/v1_1/README.md](mockups/v1_1/README.md) for how to preview. Decision index:
  [v1_1_decision_rollup.md](v1_1_decision_rollup.md).

## Approved Decisions Reflected Here

These decisions are fixed inputs to the mockups, not open questions.

### 1. Spendable balance definition

- **Spendable balance** = verified liquid cash − reserved goal balance − manual obligations.
- Spendable balance is the single headline number on Home.
- **Provisional exposure** (unreviewed outflows) is a separate, secondary line. It is **off by
  default** in the headline. The user can toggle it on to see a more conservative number.
- Credit card purchases reduce **pool remaining** but do **not** reduce verified liquid cash until
  the payment imports. The outstanding **card obligation** is shown separately, never silently
  netted into the headline.

### 2. Terminology (use exactly)

Approved vocabulary, used verbatim in all labels and copy:

- **Fund pool** — a named container for planned money (e.g., Groceries, Auto).
- **Fund commitment** — the monthly amount committed to a pool.
- **Spendable balance** — the headline number defined above.
- **Reserved goal balance** — money set aside toward goals, subtracted from spendable.
- **Pool remaining** — what is left in a given pool this period.
- **Provisional exposure** — unreviewed outflows that may reduce spendable once confirmed.
- **Card obligation** — outstanding credit card balance owed, shown separately.

Banned vocabulary, never shown in UI or copy: `envelope`, `give every dollar a job`,
`available to spend`, `age of money`.

### 3. Authentication

- Login is **passphrase + TOTP**. Recovery codes are issued at enrollment.
- First boot runs **owner enrollment** (set passphrase, enroll TOTP, save recovery codes).
- A QA-only **dev bypass** path exists and must show the red QA banner. The dev bypass and banner
  are **not** part of the personal runtime mockups; they appear only in QA wireframe variants.

## Navigation Changes From v1

v1.1 adds two primary destinations and keeps the rest. Proposed sidebar order:

- Home
- Funds  *(new)*
- Dashboard  *(new)*
- Sources
- Review
- Transactions
- Reports
- Settings

`Funds` owns pools, commitments, and pool remaining. `Dashboard` owns analytical/visual summaries
(cashflow, category bars, pool target progress, net worth placeholder). The existing `Reports`
screen keeps monthly close and advisor/analyst export. Authentication screens (login, enrollment,
recovery codes) live outside the sidebar frame because they gate access to it.

Split editing and receipt entry are **contextual** surfaces reached from Transactions/Review, not
permanent sidebar items, consistent with the v1 "secondary navigation is contextual" principle.

---

## Screen A: Home — Spendable Breakdown

**Primary user goal:** in one glance, know how much is genuinely safe to spend right now, why that
number is what it is, and what single action to take next.

**Key components:** headline spendable balance, supporting breakdown (verified liquid cash, reserved
goal balance, manual obligations), provisional exposure toggle, card obligation callout, next
action, freshness strip.

### Layout (default, provisional off)

```text
+--------------------------------------------------------------------------------+
| Home                                               [Run inbox scan] [Import]    |
| Ledger freshness: 3 of 4 sources current      Validation: 1 blocking, 4 warn   |
+--------------------------------------------------------------------------------+
| SPENDABLE BALANCE                                                              |
|   $3,412.58                                                                    |
|   Verified liquid cash $6,180.00  −  Reserved goal balance $1,900.00           |
|                                     −  Manual obligations $867.42              |
|                                                                                |
|   [ ] Include provisional exposure ($1,842.00 unreviewed)        <- toggle      |
+--------------------------------------------------------------------------------+
| Card obligation (not yet netted)                                               |
|   Chase Prime Visa     $1,204.33 owed     Pool remaining already reflects this  |
|   Alliant Credit Card    $318.90 owed     Statement due Jul 02                  |
+--------------------------------------------------------------------------------+
| Next action                                                                    |
|   Import Chase Prime Visa export. Latest Chase transaction is 19 days old, so   |
|   verified liquid cash and card obligation may be understated.                  |
+--------------------------------------------------------------------------------+
| Where your money is committed                          [Open Funds]            |
|   Fund commitments this month     $2,640.00                                     |
|   Pool remaining (all pools)        $812.17                                     |
|   Reserved goal balance           $1,900.00                                     |
+--------------------------------------------------------------------------------+
```

### Layout (provisional ON)

When the user toggles provisional exposure on, the headline recomputes to the conservative number
and the breakdown shows the deducted exposure. The change is explicit and reversible.

```text
+--------------------------------------------------------------------------------+
| SPENDABLE BALANCE (provisional)                                                |
|   $1,570.58                                                                    |
|   Verified liquid cash $6,180.00  −  Reserved goal balance $1,900.00           |
|                        −  Manual obligations $867.42  −  Provisional $1,842.00 |
|                                                                                |
|   [x] Include provisional exposure ($1,842.00 unreviewed)                       |
|   Provisional means: outflows seen in imports but not yet reviewed. Reviewing   |
|   them in [Review] will move them out of provisional.                           |
+--------------------------------------------------------------------------------+
```

### States

- **Empty (first run / no imports):** headline shows `—` with copy "No verified balances yet. Import
  a source to compute spendable balance." Breakdown rows show `Not available`. Next action points to
  Sources/Import. Provisional toggle disabled.
- **Provisional:** headline labeled `SPENDABLE BALANCE (provisional)` when toggle on; otherwise a
  small inline note "Excludes $1,842.00 provisional exposure" sits under the headline so the default
  number is never silently optimistic.
- **Blocked/warning:** if a blocking validation affects balances, a warning band sits directly above
  the headline: "1 blocking issue may affect this number — [Open validation]". Headline still shows
  but is badged `Provisional` and the cause is named.

### Operator vs future household

Operator (v1.1) sees the full breakdown, card obligation detail, and freshness caveats. A future
household-facing variant would likely show only the headline spendable balance and pool remaining,
hide validation/freshness internals, and never expose raw card balances by default. Keep the
breakdown rows componentized so the household view can drop them without a rewrite.

### Accessibility

- Headline is an `aria-live="polite"` region so toggling provisional announces the new number and
  the "(provisional)" qualifier.
- Provisional toggle is a real labeled checkbox; its label includes the dollar amount, not just
  "Include provisional".
- Status is never color-only: "provisional", "blocking", "stale" appear as text/badges with words.
  Use the existing `.metric.warn` / `.metric.danger` classes which already pair color with text.
- Negative/subtracted amounts in the breakdown use an explicit minus sign and the word "minus" in
  the accessible label, not only red text.

---

## Screen B: Funds — Pools, Commitments, Pool Remaining

**Primary user goal:** see every fund pool, how much is committed monthly, how much remains this
period, and whether the plan is overcommitted relative to fund inflow.

**Key components:** commitment summary band, pool table (commitment, spent, pool remaining, status),
overcommit warning, per-pool detail/edit drawer, reserved goal balance section.

### Layout

```text
+--------------------------------------------------------------------------------+
| Funds                                                       [Add pool]         |
| Fund commitments $2,640.00   Funded this month $2,800.00   Pool remaining $812 |
+--------------------------------------------------------------------------------+
| Commitment health                                                              |
|   Funded this month        $2,800.00                                            |
|   Fund commitments         $2,640.00                                            |
|   Uncommitted               $160.00     OK: commitments fit funding             |
+--------------------------------------------------------------------------------+
| Pools                                                                          |
| Pool             Commitment   Spent     Pool remaining   Status                |
| Groceries          $700.00   $512.40        $187.60       On track             |
| Auto & fuel        $300.00   $341.10       -$41.10        Over by $41.10        |
| Utilities          $420.00   $0.00         $420.00        Not started          |
| Dining             $200.00   $206.75        -$6.75        Over by $6.75         |
| Buffer             $120.00   $0.00         $120.00        On track              |
+--------------------------------------------------------------------------------+
| Reserved goal balance                                       [Manage goals]     |
| Goal               Target     Reserved      Remaining to target                |
| Emergency fund   $6,000.00  $1,500.00          $4,500.00                        |
| Vacation 2026    $2,000.00    $400.00          $1,600.00                        |
+--------------------------------------------------------------------------------+
```

### Overcommit warning state

When fund commitments exceed funding, a warning band appears above the pool table and the offending
total is badged. This is a warning, not a hard block — the owner stays in control.

```text
+--------------------------------------------------------------------------------+
| Warning: fund commitments exceed funding by $310.00                            |
| Commitments $3,110.00 vs funded $2,800.00. Reduce a commitment or add funding.  |
| Affected: nothing is blocked, but pool remaining assumes full funding.          |
+--------------------------------------------------------------------------------+
```

### Per-pool detail / edit drawer

Opened from a pool row. Read-only until controlled-write is approved; edit controls staged.

```text
+----------------------------------------+
| Pool: Auto & fuel                       |
| Fund commitment   [$300.00]             |
| Carryover         On / Off              |
| Linked categories Auto, Fuel            |
|                                         |
| This period                             |
|   Committed   $300.00                   |
|   Spent       $341.10                   |
|   Pool remaining  -$41.10  (Over)       |
|                                         |
| Audit preview                           |
|   Saving creates 1 settings event;      |
|   no transactions are modified.         |
|                                         |
| [Save commitment] [Close]               |
+----------------------------------------+
```

### States

- **Empty:** no pools yet. Show empty-state card: "No fund pools yet. Add a pool to start
  committing funds." Commitment health hidden until at least one pool exists.
- **Provisional:** if spent figures include provisional (unreviewed) outflows, the affected pool
  rows show `Spent (incl. provisional)` and a footnote; pool remaining is badged `Provisional`.
- **Blocked/warning:** overcommit band as above; per-pool "Over by $X" status badge. Overcommit
  never blocks navigation or import.

### Operator vs future household

Operator manages commitments, carryover, and category links. A household view would likely be
read-only per pool ("Groceries: $187.60 left") with no commitment editing and no reserved-goal math
exposed. Keep commitment editing isolated to the drawer.

### Accessibility

- Pool table status column uses words ("On track", "Over by $41.10", "Not started"), never color
  alone. Over-budget rows pair the `.danger` token with the "Over by" text.
- Negative pool remaining uses a minus sign and an accessible label "minus forty-one dollars".
- Overcommit warning band is `role="status"` and references the exact dollar gap.
- Each pool row's "open detail" control has an accessible name including the pool name
  ("Open Auto & fuel detail"), not a bare chevron.

---

## Screen C: Dashboard — Analytical Overview

**Primary user goal:** understand recent financial trajectory — cashflow over time, where money
went by category, progress toward goal targets — without losing sight of data freshness/confidence.

**Key components:** review/freshness strip, 6-month cashflow chart, category spend bars, pool target
progress, net worth tile (placeholder), all degrading gracefully to text when provisional.

### Layout

```text
+--------------------------------------------------------------------------------+
| Dashboard                                               Period: Last 6 months  |
| Freshness: 3/4 sources current   Confidence: Provisional   Reviewed: 82%       |
+--------------------------------------------------------------------------------+
| 6-month cashflow (net = inflow − outflow)                                      |
|   Jan  +  ████████            $1,210                                            |
|   Feb  +  ██████              $   840                                           |
|   Mar  -  ███                -$   410                                           |
|   Apr  +  █████████          $1,360                                            |
|   May  +  ███████            $1,020                                            |
|   Jun  ~  ████ (provisional) $   600  *Chase stale, June incomplete             |
+--------------------------------------------------------------------------------+
| Category spend (this month)            | Pool target progress                  |
|   Housing     ███████████  $1,650      |  Emergency  ████████░░  75% $4,500 left|
|   Groceries   ████         $  512      |  Vacation   ██░░░░░░░░  20% $1,600 left|
|   Auto        ███          $  341      |  Auto pool  ██████████  Over by $41    |
|   Dining      ██           $  207      |                                        |
|   Other       █            $   96      |                                        |
+--------------------------------------------------------------------------------+
| Net worth (placeholder — pending decision)                                     |
|   Estimated net worth: not enabled                                              |
|   Requires asset/liability inputs. See open UX question on net worth estimates. |
|   [Learn what this needs]                                                        |
+--------------------------------------------------------------------------------+
```

### States

- **Empty:** charts replaced by empty-state cards ("Not enough history yet — import 2+ months to see
  cashflow trend"). Net worth tile always shows placeholder until decision lands.
- **Provisional:** any period or category whose data is stale/unreviewed is marked inline with `~`
  and a `*` footnote naming the cause (e.g., "Chase stale"). The confidence badge in the header reads
  `Provisional` with the reason on hover/focus and as text.
- **Blocked/warning:** if a blocking validation affects a chart, that chart shows a small band "1
  blocking issue affects this view — [Open validation]" instead of rendering a misleading bar.

### Operator vs future household

Operator sees confidence/freshness framing and provisional markers. A household variant would show
simpler "this month / last month" comparisons and likely hide the net worth tile entirely until the
estimate methodology is owner-approved.

### Accessibility

- Bar charts are not the only representation: every bar has its numeric value as adjacent text, and
  the chart container exposes a text table alternative (or `aria-label` summarizing each series).
- Provisional markers (`~`, `*`) are paired with text footnotes; never rely on a different bar color
  alone to signal "provisional".
- Pool target progress shows percent and dollar-remaining as text next to each bar.
- Charts get a descriptive caption/`figcaption` (e.g., "Net cashflow by month, last 6 months").

---

## Screen D: Transaction Split Editor

**Primary user goal:** divide a single transaction into 2–N allocation lines (categories/pools) that
sum exactly to the transaction amount, without altering the imported fact.

**Key components:** transaction summary (read-only imported fact), allocation line list, per-line
amount + category/pool, running remainder, balance indicator, audit preview.

### Layout

```text
+--------------------------------------------------------------------------------+
| Split transaction                                                  [Close]     |
| Imported fact (not editable)                                                   |
|   Jun 12   Alliant CC   REDACTED STORE   -$189.45                              |
+--------------------------------------------------------------------------------+
| Allocations                                                                    |
|   Category / Pool          Amount        Note                                  |
| 1 [Groceries        v]   [ -$120.00 ]   [weekly food         ]   [Remove]      |
| 2 [Household        v]   [  -$49.45 ]   [paper goods         ]   [Remove]      |
| 3 [Personal care    v]   [  -$20.00 ]   [                    ]   [Remove]      |
|                                                                                |
|   [+ Add allocation line]                                                       |
+--------------------------------------------------------------------------------+
| Transaction amount   -$189.45                                                  |
| Allocated            -$189.45                                                  |
| Remainder             $0.00      Balanced — ready to save                       |
|                                                                                |
| Audit preview: creates 1 split decision event with 3 lines. Imported row is    |
| unchanged and remains linked.                                                   |
|                                                                                |
| [Save split] [Reset] [Cancel]                                                  |
+--------------------------------------------------------------------------------+
```

### States

- **Empty / initial:** opens with one line pre-filled at the full amount; a 2nd empty line is added
  when the user clicks "Add allocation line". Save disabled until 2+ lines exist (a 1-line "split"
  is just a normal categorization).
- **Unbalanced (blocked):** when remainder ≠ $0.00, the remainder row turns into a warning and Save
  is disabled: "Remainder $20.00 — allocations must sum to the transaction amount." Over-allocation
  shows "Over by $5.00".
- **Provisional:** if the underlying transaction is still unreviewed, a note reads "This transaction
  is unreviewed; saving the split will also mark it reviewed."

### Operator vs future household

Operator-only in v1.1. Splits are an advanced editing surface; a future household view would not
expose split editing.

### Accessibility

- Remainder/balance status uses words ("Balanced", "Remainder $20.00", "Over by $5.00") in addition
  to color, in an `aria-live="polite"` region so each amount edit announces the new remainder.
- Each allocation line is a labeled group ("Allocation line 2 of 3") so screen-reader users keep
  position. Remove buttons name their line ("Remove allocation line 2").
- Amount inputs use `inputmode="decimal"` and accept signed values; invalid entries surface a text
  error, not just a red border.
- Save button's disabled state is paired with a visible text reason, not silent.

---

## Screen E: Receipt / Line-Item Entry

**Primary user goal:** capture itemized receipt detail (manually) and optionally link it to an
existing transaction, so category accuracy and future analysis improve — without scrapers or external
calls.

**Key components:** receipt header (merchant, date, total), line-item table, link-to-transaction
control, totals reconciliation, save.

### Layout

```text
+--------------------------------------------------------------------------------+
| Receipt entry                                                      [Close]     |
| Merchant [REDACTED STORE      ]   Date [2026-06-12]   Total [ $189.45 ]         |
| Linked transaction:  Jun 12 · Alliant CC · -$189.45   [Change] [Unlink]         |
+--------------------------------------------------------------------------------+
| Line items                                                                     |
|   Description           Qty    Unit      Amount     Category                   |
| 1 [Bananas         ]   [ 2 ]  [$0.59]   [ $1.18 ]  [Groceries     v]  [Remove]  |
| 2 [Paper towels    ]   [ 1 ]  [$8.99]   [ $8.99 ]  [Household      v]  [Remove]  |
| 3 [Shampoo         ]   [ 1 ]  [$6.49]   [ $6.49 ]  [Personal care  v]  [Remove]  |
|                                                                                |
|   [+ Add line item]                                                             |
+--------------------------------------------------------------------------------+
| Items total      $16.66                                                        |
| Receipt total   $189.45                                                        |
| Unaccounted     $172.79   Optional — itemize as much as you want               |
|                                                                                |
| Audit preview: creates 1 receipt record linked to txn_redacted_044.            |
| [Save receipt] [Save & start split from items] [Cancel]                        |
+--------------------------------------------------------------------------------+
```

### States

- **Empty:** no linked transaction yet. Link control reads "Not linked — [Find transaction] or save
  standalone". Standalone receipts are allowed (manual capture ahead of import).
- **Linked + reconciled:** when items total equals receipt total, "Unaccounted" becomes "Reconciled
  $0.00" with an OK badge.
- **Mismatch (warning, not blocking):** if items total exceeds receipt total, show "Over receipt
  total by $3.00 — check quantities." Itemization is allowed to be partial, so under-total is a
  neutral note, not an error.
- **Provisional:** standalone receipt not yet linked to an imported transaction is badged "Unlinked
  — will reconcile when the matching transaction imports."

### Operator vs future household

Operator-only in v1.1. The "Save & start split from items" affordance bridges to Screen D so itemized
categories can pre-fill split allocations. A household view is out of scope.

### Accessibility

- The Amount column auto-calculates from Qty × Unit but stays an editable, labeled field; the
  computed value is announced when Qty/Unit change.
- Reconciliation status ("Reconciled", "Over by $3.00", "Unaccounted $172.79") is text plus token
  color, in a polite live region.
- Link/unlink controls have descriptive names ("Link to Jun 12 Alliant CC transaction").

---

## Screen F: Authentication — Login, TOTP Enrollment, Recovery Codes

These screens render outside the app frame (no sidebar). Personal runtime never shows the QA dev
bypass; the QA variant adds the red banner and a clearly-labeled bypass control.

### F1. Login (passphrase + TOTP)

**Primary user goal:** authenticate with passphrase then TOTP to reach the operator app.

```text
+-------------------------------------------------+
|              Family Finance OS                  |
|              Local sign in                      |
|                                                 |
|  Passphrase                                     |
|  [ ............................ ]   [Show]      |
|                                                 |
|  Authenticator code (6 digits)                  |
|  [ _ _ _ _ _ _ ]                                |
|                                                 |
|  [ Sign in ]                                     |
|                                                 |
|  Lost your device? [Use a recovery code]        |
|                                                 |
|  Local only · 127.0.0.1 · No data leaves device |
+-------------------------------------------------+
```

States: **default**; **error** (text band "Passphrase or code incorrect" — never reveal which);
**locked** (after N attempts, "Too many attempts. Try again in 5:00" with countdown); **recovery
mode** (TOTP field swaps to a recovery-code field with its own label).

### F2. First-boot owner enrollment

**Primary user goal:** on first run, create the owner credential set: passphrase, TOTP, recovery
codes. Stepped flow so nothing is skipped.

```text
+-------------------------------------------------+
| First-boot setup — Owner enrollment             |
| Step 2 of 3: Set up authenticator               |
| [done] Passphrase  >  [active] TOTP  >  Recovery |
+-------------------------------------------------+
| Scan this QR code in your authenticator app.     |
|                                                  |
|   [ QR CODE ]      Manual key: REDACTED-SECRET   |
|                                                  |
| Enter the 6-digit code to confirm:               |
|   [ _ _ _ _ _ _ ]                                |
|                                                  |
| [ Back ]                          [ Confirm code ]|
+-------------------------------------------------+
```

Step 1 (passphrase): two fields (enter + confirm), strength text indicator (word-based, e.g.
"Strong"), no silent acceptance of weak input. Step 3 is the recovery codes screen (F3).

### F3. Recovery codes display

**Primary user goal:** save one-time recovery codes before finishing enrollment, with an explicit
acknowledgment that they are shown once.

```text
+-------------------------------------------------+
| First-boot setup — Step 3 of 3: Recovery codes  |
|                                                 |
| Save these 10 one-time recovery codes. They are |
| shown once and let you sign in if you lose your |
| authenticator.                                  |
|                                                 |
|   1) REDACTED-AAAA   6) REDACTED-FFFF            |
|   2) REDACTED-BBBB   7) REDACTED-GGGG            |
|   3) REDACTED-CCCC   8) REDACTED-HHHH            |
|   4) REDACTED-DDDD   9) REDACTED-IIII            |
|   5) REDACTED-EEEE  10) REDACTED-JJJJ            |
|                                                 |
|   [Copy codes] [Download .txt]                  |
|                                                 |
|   [x] I have saved these codes somewhere safe.  |
|                                                 |
|                          [ Finish setup ]        |
+-------------------------------------------------+
```

States: **default** (Finish disabled until the acknowledgment box is checked); **regenerate** (from
Settings later: "Regenerating invalidates all previous codes" warning). Download writes to the
user's chosen location; codes are synthetic in mockups.

### QA dev-bypass variant (QA runtime only)

```text
+-------------------------------------------------+
| !!! QA synthetic demo - not real financial data |  <- red banner
+-------------------------------------------------+
|              Family Finance OS (QA)             |
|  [ Sign in with passphrase + TOTP ]             |
|  ----------------- or -----------------         |
|  [ Dev bypass (QA only) ]   synthetic owner      |
+-------------------------------------------------+
```

The bypass button is only rendered when `app_env === "qa"` / `qa_controls_enabled`, mirroring the
existing QA banner pattern in `App.tsx`. It must never appear in the personal runtime.

### Operator vs future household

v1.1 auth is single-owner. Multi-user household login (per-member passphrase/TOTP, scoped
permissions) is out of scope and noted as a future expansion; the enrollment flow is structured so a
later "add member" flow can reuse F2/F3.

### Accessibility

- All inputs have persistent visible labels (not placeholder-only). The 6-digit code uses a single
  labeled field or a labeled grouped input with a clear accessible name.
- Errors are text in a `role="alert"` region; lockout countdown is announced politely.
- "Show passphrase" is a labeled toggle with state announced. QR code has alt text and the manual
  key is always available as a text alternative.
- Recovery-code acknowledgment is a real checkbox gating the Finish button, with a visible reason
  when disabled.

---

## Screen G: Analyst Export

**Primary user goal:** assemble a privacy-reviewed export pack for an outside analyst (or the
owner's own LLM use elsewhere) and copy a suitable prompt — with **no in-app AI calls**.

**Key components:** export pack checklist (what's included/excluded), scope/period selector, privacy
boundary callout, prompt picker (copyable templates), generate/export action.

### Layout

```text
+--------------------------------------------------------------------------------+
| Reports / Analyst export                                  [Build export pack]  |
| Period: June 2026    Confidence: Provisional    Local only · nothing is sent   |
+--------------------------------------------------------------------------------+
| Export pack contents                                                           |
|   [x] Reviewed transaction summary (categorized, aggregated)                    |
|   [x] Category spending totals                                                  |
|   [x] Fund pool commitments and pool remaining                                  |
|   [x] Cashflow summary (6 months)                                               |
|   [ ] Raw transaction rows            (off — contains line-level detail)        |
|   [ ] Account numbers / balances      (never included)                          |
|   [x] Validation/confidence notes (so the analyst knows what is provisional)    |
+--------------------------------------------------------------------------------+
| Privacy boundary                                                               |
|   This pack is generated locally and saved to a file you choose. Family Finance |
|   OS does not call any AI or external service. You decide where it goes.        |
+--------------------------------------------------------------------------------+
| Prompt picker (copy to use in your own tool)                                   |
|   ( ) Monthly spending review                                                   |
|   (o) Cashflow & savings-rate analysis                                          |
|   ( ) Goal progress check-in                                                    |
|   ( ) Custom (write your own)                                                   |
|                                                                                |
|   Selected prompt preview:                                                      |
|   "Using the attached export pack, summarize net cashflow and savings rate for  |
|    the period. Note any months marked provisional and do not infer beyond the   |
|    provided data."                                          [Copy prompt]       |
+--------------------------------------------------------------------------------+
| [Preview pack] [Export pack (.json + .md)]                                     |
+--------------------------------------------------------------------------------+
```

### States

- **Empty:** if no reviewed data exists, checklist items are disabled with "Nothing to export yet —
  import and review first." Prompt picker still browsable.
- **Provisional:** when any included report is provisional, a band reads "This pack includes
  provisional data (June incomplete, Chase stale). The export labels each provisional section." Export
  is allowed but the provisional flag travels with the data.
- **Blocked/warning:** sensitive toggles (raw rows, account numbers) are guarded — turning on "Raw
  transaction rows" shows a confirm step naming the privacy trade-off; account numbers/balances are
  hard-disabled in v1.1.

### Operator vs future household

Operator-only. There is no in-app AI and no automatic transmission — the owner always performs the
final hand-off manually. A household variant would not expose export at all.

### Accessibility

- Checklist items are real labeled checkboxes; "never included" items are disabled with a text
  reason, not just greyed out.
- Prompt picker is a labeled radio group; the selected prompt preview is in a region announced on
  change. "Copy prompt" confirms with text ("Prompt copied"), not just a transient color flash.
- The privacy boundary statement is plain text in the reading order before the export action, so it
  cannot be missed by screen-reader users.

---

## Cross-Screen Consistency Notes

- Reuse v1 status vocabulary: Current, Stale, Missing, Warning, Blocking, Provisional, Reviewed,
  Open, Superseded. v1.1 adds no competing words.
- Money is always signed and right-aligned in tables; negative uses an explicit minus sign.
- Headline/derived numbers that depend on stale/unreviewed/blocked data are always badged with the
  cause named in text.
- Controlled-write surfaces (split save, pool commitment edit, receipt save, settings) show an audit
  preview and can ship read-only-first with staged save controls, consistent with v1.
- Reuse existing CSS tokens: `.metric`, `.metric.warn`, `.metric.danger`, `.status-badge`,
  `.empty-state`, `.next-action`, `.two-column`, `.table-wrap`. No new color-only signals.

---

## UX Review Section

### What works

- **Single honest headline.** Spendable balance is one number with its math shown inline, and
  provisional exposure is opt-in rather than hidden — this keeps the default conservative-but-clear
  and avoids overpromising a number the user cannot actually spend.
- **Card obligation stays separate.** Not netting card balances into liquid cash until payment
  imports matches how money actually moves and prevents double-counting against pools.
- **Consistent frame.** Funds and Dashboard slot into the existing sidebar + status-strip pattern,
  so v1.1 feels like the same product, not a bolt-on.
- **Provisional is first-class everywhere.** Home, Dashboard, Funds, and Export all name the cause of
  uncertainty in text, satisfying the "show data trust before conclusions" principle.
- **Auth is appropriately heavy for finance, light for a local app.** Passphrase + TOTP + recovery
  codes with a gated first-boot flow; QA bypass is quarantined behind the QA banner.

### Risks

- **Spendable-balance math legibility.** The breakdown (liquid − reserved − obligations [− provisional])
  is four moving parts. On small screens this can read as a wall of numbers; the breakdown may need
  progressive disclosure ("Show breakdown") while keeping the headline always visible.
- **Pool "spent" timing vs card obligation.** Card purchases reduce pool remaining immediately but
  not liquid cash. Users may be confused that pool remaining and spendable move on different events.
  The Funds → card-obligation relationship needs a clear one-line explainer (drafted on Home).
- **Split vs receipt overlap.** "Save & start split from items" links two editors; if both can
  create allocations there's a risk of conflicting or duplicate categorization events. The decision
  event model must define precedence (receipt-derived split vs manual split).
- **Dashboard chart fidelity.** ASCII bars stand in for real charts; the accessibility commitment
  (text table alternative, per-bar values) must survive the move to a real chart library, which is
  easy to drop during implementation.
- **Recovery code custody.** Showing codes once is correct, but a local app can't recover a lost
  passphrase + lost device + lost codes. The reset/regenerate path and its security trade-offs need
  an explicit owner decision before build.

### Open UX questions (tied to pending decisions)

1. **Net worth estimates.** The Dashboard net worth tile is a placeholder. Pending owner decision:
   do we support manual asset/liability entry (and is it in scope for v1.1), or defer net worth
   entirely? The tile's final copy and whether it appears at all depend on this.
2. **Scrapers vs manual receipts.** Receipt entry is manual-only here, consistent with the no-egress
   policy. If automated line-item capture is ever approved, does it change the receipt screen's
   primary path (manual becomes fallback) or stay a separate import source? Affects whether "manual"
   should be framed as the default or the exception.
3. **Goals vs projects.** Reserved goal balance currently models open-ended savings goals (Emergency,
   Vacation). Pending decision: are time-boxed "projects" (e.g., a renovation with a deadline and
   sub-line items) a distinct concept from goals, or a goal variant? This affects the Funds reserved
   section, Dashboard pool target progress, and whether goals need a target date field.
4. **Provisional default scope.** Provisional exposure is off in the Home headline by default. Should
   the same default apply on Funds pool "spent" and on the Dashboard, or should those screens always
   include provisional with clear marking? Consistency vs conservatism trade-off.
5. **Where split/receipt live.** Confirm splits/receipts stay contextual (launched from
   Transactions/Review) rather than becoming sidebar destinations, to avoid nav sprawl.

### Out of scope for these mockups

- App implementation, React/component code, schema, API contracts.
- Real charting library selection and visual design system.
- Multi-user household authentication and per-member permissions.
- Automated scrapers, vendor enrichment, or any external/AI calls.
- Net worth estimation methodology (pending decision).
- Mobile-first layouts.

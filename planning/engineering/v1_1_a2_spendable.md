# A2 Spendable Engineering Spec

## Purpose

Define the v1.1 Spendable balance engine per D1 so backend and UI implement the same formula, edge cases, source configuration, API contract, operator-summary changes, monthly close snapshots, and tests.

Spendable balance is a planning number, not a mutation of ledger facts. It is derived from verified liquid cash, reserved goal balance, manual upcoming obligations, and optional provisional exposure.

## Non-goals

- No code implementation in this document.
- No mutation of `imported_rows`, `canonical_transactions`, or raw source files.
- No inclusion of net worth estimate assets in Spendable balance.
- No automatic bank connections or real-time balance scraping.
- No deduction of credit card purchases from verified liquid cash until payment imports; card obligation is shown separately.
- No automatic creation of manual obligations from bill prediction in A2.

## Formula

Per D1:

```text
headline_spendable =
  verified_liquid_cash
  - reserved_goal_balance
  - manual_upcoming_obligations

if include_provisional_exposure:
  headline_spendable = headline_spendable - provisional_exposure
```

Card obligation is separate:

```text
card_obligation_total = outstanding_credit_card_balance
```

Credit card purchases reduce pool remaining and category/budget target usage through transaction allocations/reviewed current state, but they do not reduce verified liquid cash until a payment imports against a liquid account.

## Pseudocode

```python
def compute_spendable(month: str, include_provisional: bool) -> SpendablePayload:
    settings = load_spendable_settings()
    liquid_source_keys = configured_liquid_source_keys(settings)
    credit_card_source_keys = configured_credit_card_source_keys(settings)

    verified_liquid_cash = sum_latest_verified_account_balances(
        source_keys=liquid_source_keys,
        required_statuses={"accepted"},
        require_confirmed_source_profile=True,
    )

    reserved_goal_balance = sum(
        goal.reserved_balance
        for goal in active_financial_goals()
    )

    manual_obligations_total = sum(
        obligation.amount
        for obligation in active_manual_obligations(month=month)
        if obligation.linked_canonical_transaction_id is None
    )

    provisional_exposure = sum_unreviewed_outflows(
        month=month,
        include_credit_cards=True,
        include_liquid_accounts=True,
        exclude_transfers=True,
        exclude_neutral=True,
    )

    card_obligation_total, card_obligation_items = summarize_card_obligations(
        source_keys=credit_card_source_keys,
        required_statuses={"accepted"},
    )

    headline = verified_liquid_cash - reserved_goal_balance - manual_obligations_total
    if include_provisional:
        headline -= provisional_exposure

    warnings = derive_warnings(
        verified_liquid_cash=verified_liquid_cash,
        reserved_goal_balance=reserved_goal_balance,
        manual_obligations_total=manual_obligations_total,
        headline=headline,
        source_freshness=source_freshness(liquid_source_keys + credit_card_source_keys),
    )

    return SpendablePayload(
        month=month,
        headline_spendable=headline,
        verified_liquid_cash=verified_liquid_cash,
        reserved_goal_balance=reserved_goal_balance,
        manual_obligations_total=manual_obligations_total,
        provisional_exposure=provisional_exposure,
        include_provisional=include_provisional,
        card_obligation_total=card_obligation_total,
        card_obligation_items=card_obligation_items,
        confidence=confidence_from(warnings),
        warnings=warnings,
    )
```

## Edge Cases

- No accepted liquid source imports: `verified_liquid_cash = 0`, confidence `blocked`, warning code `no_verified_liquid_cash`.
- Missing required liquid source: use available verified liquid data, confidence at least `stale` or `blocked` depending existing source coverage severity.
- Stale liquid source: compute from latest accepted balance, confidence `stale`, warning code `stale_liquid_source`.
- Liquid transaction without balance: exclude that source from verified liquid cash unless a configured balance fallback exists; emit `missing_liquid_balance`.
- Reserved goal balance exceeds verified liquid cash: headline may be negative; draft close warning, final close blocker unless Financial Governor elevated override.
- Manual obligations exceed remaining cash: headline may be negative; draft close warning, final close blocker unless override.
- Negative pool remaining does not directly change Spendable balance; it is a D9 warning/final blocker via monthly close and Funds health.
- Credit card purchase imports with no corresponding payment: purchase affects pool remaining/targets and card obligation, not verified liquid cash.
- Credit card payment imports on checking and card: payment reduces verified liquid cash through the checking transaction and reduces card obligation through card balance/payment state.
- Unreviewed inflows are not provisional exposure. Only unreviewed outflows are exposure.
- Transfers should be excluded from provisional exposure once reviewed as transfers. Unreviewed likely-transfer outflows remain provisional unless backend can confidently identify neutral transfer pairs without mutating reviewed state.
- Refunds/credits reduce provisional exposure only after imported direction is inflow or reviewed current state identifies refund behavior.
- Estimates from `net_worth_snapshots` never feed Spendable balance.

## Liquid Account Configuration

Default source-profile behavior:

| Source profile | Account type | Default Spendable role |
| --- | --- | --- |
| `alliant_checking` | `checking` | liquid cash |
| `alliant_savings` | `savings` | liquid cash |
| `alliant_credit_card` | `credit_card` | card obligation |
| `chase_prime_visa` | `credit_card` | card obligation |

Recommended settings keys:

| Domain | Setting key | Type | Default | Notes |
| --- | --- | --- | --- | --- |
| `spendable` | `spendable.liquid_source_keys` | JSON array of strings | `["alliant_checking", "alliant_savings"]` | Source keys that count as verified liquid cash. |
| `spendable` | `spendable.card_obligation_source_keys` | JSON array of strings | all `credit_card` profiles | Source keys that count toward card obligation. |
| `spendable` | `spendable.include_provisional_default` | boolean | `false` | UI toggle default. |
| `spendable` | `spendable.manual_obligation_window_days` | integer | `45` | Used when querying upcoming obligations without an explicit month. |

Rules:

- Only accepted imports from confirmed source profiles can contribute to verified liquid cash by default.
- A source profile must not count in both liquid cash and card obligation.
- Disabled source profiles do not contribute.
- Settings changes are audited through `settings_events`.
- If A3 has landed, settings mutations require authenticated user attribution and existing permission checks.

## Card Obligation Calculation

Preferred v1.1 approach:

1. For each configured credit card source profile, use the latest accepted imported row with a non-null `balance`.
2. Normalize sign so each item's `owed` value and `card_obligation_total` are positive amounts owed.
3. Sum across active configured credit card source keys.
4. Emit per-card items in the payload for the Home card-obligation table, aligned with B1's `card_obligation_items` shape:
   - `card`: user-facing card/source display name.
   - `owed`: positive amount owed, serialized as a money string when known.
   - `note`: short Home-table note such as "Pool remaining already reflects this" or statement-date copy when available.
   - Optional implementation metadata such as `source_key`, `status`, `latest_transaction_date`, and `confidence` may be included when useful.
5. Emit the scalar `card_obligation_total` for summary, snapshot, operator-summary, and monthly-close use.

Fallback behavior:

- If a credit card source has accepted transactions but no balance field, include a `card_obligation_items` row with `owed: null` and a warning note/status, then exclude it from the summed `card_obligation_total`.
- Emit warning `missing_card_balance`.
- Do not synthesize card obligation by summing all card purchases unless B5 explicitly accepts that approximation for reporting only.

## Provisional Exposure Toggle Semantics

Default:

- Headline Spendable balance excludes Provisional exposure.
- UI shows the separate line: "Excludes `$X` provisional exposure (unreviewed outflows)."
- Toggle label follows mockup: "Include provisional exposure (`$X` unreviewed)."

When toggle is on:

- API recomputes `headline_spendable` with provisional exposure subtracted.
- Response includes `include_provisional: true`.
- Response still includes the same `provisional_exposure` line so the UI can show why the headline changed.
- Toggle preference is per request in A2. Persisting a user preference should wait for A3/user settings unless explicitly approved in the UI track.

Provisional exposure source:

- Sum unreviewed outflow transactions in the selected period.
- Include credit card and liquid account outflows because both represent spending exposure that may need review.
- Exclude reviewed transfer outflows, reviewed payments, neutral rows, voided/superseded canonical transactions, and transactions blocked by identity validation if they are not safe to count.

## API Contract

### `GET /api/spendable`

Query parameters:

| Name | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `month` | `YYYY-MM` string | no | current/default reporting month | Must match monthly close period handling. |
| `include_provisional` | boolean | no | `spendable.include_provisional_default` | Recomputes headline. |

Response shape:

```json
{
  "month": "2026-06",
  "headline_spendable": "3412.58",
  "verified_liquid_cash": "6180.00",
  "reserved_goal_balance": "1900.00",
  "manual_obligations_total": "867.42",
  "provisional_exposure": "1842.00",
  "include_provisional": false,
  "card_obligation_total": "1523.23",
  "card_obligation_items": [
    {
      "card": "Synthetic Rewards Card",
      "owed": "1018.23",
      "note": "Pool remaining already reflects this",
      "source_key": "alliant_credit_card",
      "status": "current"
    },
    {
      "card": "Synthetic Travel Card",
      "owed": "505.00",
      "note": "Statement due Jul 02",
      "source_key": "chase_prime_visa",
      "status": "stale"
    }
  ],
  "confidence": "provisional",
  "warnings": [
    {
      "code": "stale_card_source",
      "severity": "warning",
      "message": "Chase Prime Visa latest transaction is 19 days old."
    }
  ],
  "source_details": [
    {
      "source_key": "alliant_checking",
      "display_name": "Alliant Checking",
      "role": "liquid_cash",
      "latest_transaction_date": "2026-06-24",
      "balance": "4380.00",
      "confidence": "current"
    }
  ],
  "snapshot_id": null
}
```

Implementation notes:

- Serialize money as strings to avoid JavaScript float ambiguity, matching common API finance practice.
- `card_obligation_total` and `card_obligation_items` intentionally match the B1 funds summary shape so Home can render the same per-card table from either backing payload.
- Keep stable warning codes. Display text can later move to locale resources.
- `snapshot_id` is null for live reads unless the endpoint is explicitly asked to create/read a close snapshot.

### Operator Summary Changes

`GET /api/operator-summary` should add a top-level `spendable` object:

```json
{
  "spendable": {
    "month": "2026-06",
    "headline_spendable": "3412.58",
    "verified_liquid_cash": "6180.00",
    "reserved_goal_balance": "1900.00",
    "manual_obligations_total": "867.42",
    "provisional_exposure": "1842.00",
    "include_provisional": false,
    "card_obligation_total": "1523.23",
    "card_obligation_items": [
      {
        "card": "Synthetic Rewards Card",
        "owed": "1018.23",
        "note": "Pool remaining already reflects this"
      },
      {
        "card": "Synthetic Travel Card",
        "owed": "505.00",
        "note": "Statement due Jul 02"
      }
    ],
    "confidence": "provisional",
    "warnings": []
  }
}
```

Existing `next_action` logic should incorporate spendable warnings after validation/review blockers:

- `negative_spendable`: "Review Spendable balance blockers".
- `reserved_goals_exceed_liquid`: "Review reserved goal balance".
- `missing_fund_commitments`: "Complete Fund commitments".

Do not remove existing `runtime`, `latest_import`, `sources`, `validation`, `review`, `monthly_close`, `artifacts`, or `inbox` keys.

## Snapshot Storage For Monthly Close

Use `spendable_balance_snapshots` from A1.

Snapshot creation rules:

- Draft close writes `snapshot_type = "draft_close"`.
- Final close writes `snapshot_type = "final_close"`.
- Snapshot stores the computed amounts, `include_provisional`, warning/confidence inputs, and `monthly_close_id`.
- Final close snapshot is treated as immutable. Corrections create a revised monthly close/snapshot.
- Live UI reads should not write snapshots unless explicitly requested by a close/report workflow.

D9 monthly close rules:

- Draft close allowed with warnings for:
  - negative pool remaining
  - reserved goals exceeding liquid
  - negative headline spendable
  - missing fund commitments
  - provisional labels
- Final close blocked for the above unless Financial Governor elevated override with purpose note and audit event.
- Existing blockers remain: unreviewed transactions, stale required sources, open blocking validation findings.
- Close bundle includes fund pool summary and spendable snapshot.

## Relationship To Existing Canonical Transactions And Decision Events

- Spendable uses current reviewed state derived from `canonical_transactions` plus `decision_events`, not mutated imported rows.
- `decision_events` determine transfer/reimbursement/medical/project/side-hustle states where they affect exclusions or review status.
- Split allocation decisions in B2 will refine category/pool effects but should not change the D1 headline formula.
- Manual obligation creation/editing should be audited through settings/decision/user-event pattern chosen by B1/B5; do not silently alter spendable inputs.

## UI Touchpoints

Mockup IDs:

- `home`
  - `#spendable-label`
  - `#spendable-amount`
  - `#provisional-toggle`
  - `#prov-op`
  - `#prov-term`
  - `#spendable-note`
  - Breakdown line labels pinned to Screen A: "Verified liquid cash", "Reserved goal balance", and "Manual obligations". "Manual obligations" is the display shorthand for D1's manual upcoming obligations.
  - Card obligation table with the heading intent "Card obligation (not yet netted)" and `Card`, `Owed`, and `Note` columns, backed by `card_obligation_items`.
  - Fund commitments/pool remaining/reserved goal balance metrics. These "Where your money is committed" tiles are sourced from the B1 funds summary, not `/api/spendable`; A2 backs the Home headline, breakdown, provisional toggle, and card-obligation panel only.
- `funds`
  - Commitment health and pool remaining values feed warnings.
- `dashboard`
  - Confidence/provisional labels and net worth note that estimates never feed Spendable balance.
- `reports`
  - Monthly close consumes snapshots.

UI copy must use D2 locked terms:

- Spendable balance
- Reserved goal balance
- Provisional exposure
- Card obligation
- Fund commitment
- Pool remaining

Confidence and warning surfacing on Home follows Screen A:

- Stale or blocked source warnings feed the Home "Next action" card and relevant card-obligation subhead copy.
- Do not invent a new standalone confidence chip on the Spendable balance headline unless a later UI decision approves it.

## Test Plan

### Unit Test Matrix

| Case | Inputs | Expected |
| --- | --- | --- |
| Basic current data | Liquid `6180`, reserved `1900`, obligations `867.42`, provisional `1842`, toggle off | Headline `3412.58`; provisional separate; confidence current/provisional based warnings. |
| Toggle on | Same as basic, toggle on | Headline `1570.58`; `include_provisional = true`. |
| No liquid imports | No accepted liquid sources | Headline uses `0` liquid; warning `no_verified_liquid_cash`; confidence `blocked`. |
| Stale liquid source | Latest liquid date older than threshold | Amount included; warning `stale_liquid_source`; confidence `stale`. |
| Missing liquid balance | Accepted rows have null balance | Source excluded from liquid sum; warning `missing_liquid_balance`. |
| Reserved exceeds liquid | Liquid `1000`, reserved `1500` | Headline negative before obligations; warning `reserved_goals_exceed_liquid`. |
| Obligations exceed remaining | Liquid `1000`, reserved `200`, obligations `1200` | Headline `-400`; warning `negative_spendable`. |
| Credit purchase only | Card purchase imported, no checking payment | Card obligation/pool usage changes; verified liquid unchanged. |
| Card payment imported | Checking outflow and card payment imported | Verified liquid reduced by checking balance/payment; card obligation reduced by card balance. |
| Unreviewed inflow | Unreviewed positive transaction | Not counted as provisional exposure. |
| Reviewed transfer outflow | Transfer status confirmed | Excluded from provisional exposure. |
| Unreviewed outflow | Review status unreviewed | Included in provisional exposure. |
| Estimate net worth | Estimate asset present | Ignored by Spendable balance. |

### API Tests

- `GET /api/spendable` returns default month and toggle-off formula.
- `GET /api/spendable?include_provisional=true` returns reduced headline.
- Invalid `month` returns `422` with stable code.
- Missing source balances return warning objects, not server errors.
- Money is serialized as strings.

### Operator Summary Tests

- `/api/operator-summary` includes `spendable`.
- Existing summary keys remain present.
- `next_action` preserves validation/review priority and adds spendable actions only after higher-priority blockers.

### Monthly Close Tests

- Draft close writes one `draft_close` snapshot.
- Final close writes one `final_close` snapshot when no D9 blocker exists.
- Final close with negative spendable is blocked without Financial Governor elevated override.
- Override path requires purpose note and creates elevated/audit event linkage.

### UI Tests

- Home shows Spendable balance with D2 locked terminology.
- Toggle updates headline and explanatory note.
- Card obligation is shown separately from headline.
- Provisional exposure label appears when unreviewed outflows exist.

## Open Questions

None for D1 semantics. Implementation must choose the exact source of latest account balance per profile, but the first choice should be the latest accepted imported row with non-null `balance`, because that matches current schema and keeps A2 small.

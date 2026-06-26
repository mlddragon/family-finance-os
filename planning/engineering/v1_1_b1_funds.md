# v1.1 B1 Funds Engineering Plan

Status: Draft  
Build phase: Phase 2  
Schema note: `planning/engineering/v1_1_a1_schema.md` is not present in this checkout. Use the table and API names below from `planning/v1_1_expansion_decision_record.md`; align to A1 on merge.

## Purpose

Implement fund pools, fund commitments, financial goals, budget targets, and spendable presentation surfaces after the A1 schema and A2 spendable engine land.

This track owns the user-facing v1.1 terminology from D1, D2, D7, and D9:

- Fund pool
- Fund commitment
- Spendable balance
- Reserved goal balance
- Pool remaining
- Provisional exposure
- Card obligation

The Funds screen must make monthly commitments and overcommitment warnings visible without changing ledger source-of-truth behavior. The Home screen must show the A2 spendable headline and breakdown.

## Non-goals

- Do not implement envelope terminology or zero-based budgeting language.
- Do not create a separate projects table in v1.1. D7 requires one `financial_goals` entity.
- Do not let goals or estimates feed imported account balances.
- Do not auto-create commitments from past spending in the first implementation.
- Do not implement rollover behavior unless A1/A2 explicitly approve it.

## Schema/API

### Tables

Expected A1 tables or equivalents:

- `fund_pools`
- `fund_commitments`
- `financial_goals`
- `budget_targets`
- existing `decision_events`
- existing settings/audit tables for configurable defaults

`financial_goals` is required by D7 and must include at minimum:

- `id`
- `name` - required before save; no anonymous or type-only goals
- `goal_type` - one of `emergency`, `sinking_fund`, `purchase`, `other`
- `target_amount`
- `target_date`
- `linked_fund_pool_id`
- `reserved_balance`
- `status`
- audit metadata aligned with A1

`fund_pools` should include stable keys for API references and display names. `fund_commitments` should bind a pool to a month and committed amount. `budget_targets` should compare reviewed actuals and allocation-driven actuals to monthly targets.

### Derived Calculations

Pool remaining:

`fund_commitment.amount - reviewed_outflows_allocated_to_pool`

Home spendable:

`verified liquid cash - reserved goal balance - manual upcoming obligations`

Provisional exposure is a separate line and excluded from headline by default. Card obligation is shown separately and must not reduce verified liquid cash until card payment imports.

### API Shape

Follow existing FastAPI response patterns in `apps/api/family_finance_os/main.py`: service module functions return dictionaries, route handlers enforce permissions, errors use stable `detail.code`.

Proposed endpoints:

- `GET /api/funds/summary?month=YYYY-MM`
- `GET /api/fund-pools?month=YYYY-MM`
- `POST /api/fund-pools`
- `PATCH /api/fund-pools/{pool_id}`
- `POST /api/fund-commitments`
- `PATCH /api/fund-commitments/{commitment_id}`
- `GET /api/financial-goals`
- `POST /api/financial-goals`
- `PATCH /api/financial-goals/{goal_id}`
- `GET /api/budget-targets?month=YYYY-MM`
- `PATCH /api/budget-targets/{target_id}`

Proposed `GET /api/funds/summary` payload:

```json
{
  "month": "2026-06",
  "spendable": {
    "headline": "3412.58",
    "verified_liquid_cash": "6180.00",
    "reserved_goal_balance": "1900.00",
    "manual_upcoming_obligations": "867.42",
    "provisional_exposure": "1842.00",
    "card_obligation": "1523.23",
    "includes_provisional": false
  },
  "commitment_health": {
    "funded_this_month": "2800.00",
    "fund_commitments": "2640.00",
    "uncommitted": "160.00",
    "overcommitted": false
  },
  "pools": [],
  "goals": [],
  "budget_targets": []
}
```

### Decision Events

Create decision events for:

- Fund pool create/update/archive.
- Fund commitment create/update/delete.
- Financial goal create/update/archive, including reserved balance changes.
- Budget target create/update.
- Explicit owner override where final close proceeds despite D9 fund/spendable blockers.

Events should record actor context and before/after values in the same style as existing review/settings decisions.

## UI (Mockup Screen)

Mockup references:

- Home screen: `planning/mockups/v1_1/index.html`, Screen A.
- Funds screen: `planning/mockups/v1_1/index.html`, Screen B.

Home changes:

- Add Spendable balance headline panel.
- Show verified liquid cash, Reserved goal balance, Manual obligations, optional Provisional exposure, and Card obligation.
- Include a toggle to include provisional exposure in the displayed scenario without changing the default headline formula.
- Add "Where your money is committed" metrics linking to Funds.

Funds screen:

- Add sidebar entry `Funds`.
- Show commitment health metrics: funded this month, Fund commitments, uncommitted/overcommitted.
- Show warning band when commitments exceed funding.
- Show pool table with commitment, spent, Pool remaining, and status.
- Show Reserved goal balance table with Goal, Target, Reserved, and Remaining to target.
- Goal creation/editing must require a goal name before save per D7.

Use existing React screen patterns: `screens` array, conditional screen rendering, `work-panel`, `metric-grid`, `DataTable`, and mutation status messaging.

## Test Plan

Backend unit tests:

- Fund pool CRUD preserves stable ids and rejects duplicate active names/keys as A1 defines.
- Goal create rejects missing or blank `name`.
- Goal `goal_type` rejects values outside D7 set.
- Fund commitment totals produce correct overcommitment status.
- Spendable summary excludes provisional exposure by default.
- Card obligation is surfaced separately and not subtracted from verified liquid cash.
- Decision events are created for each mutating operation.

API tests:

- Routes require the same permission family as report/dashboard views or the A1/A3-defined fund permissions.
- Invalid payloads return stable `detail.code` values.
- Summary endpoint is deterministic for synthetic fixtures.

Frontend tests:

- Home renders spendable headline and breakdown.
- Provisional toggle changes displayed scenario text and amount without changing default payload semantics.
- Funds screen renders overcommitment warning and pool remaining values.
- Goal form blocks save when goal name is empty.

Human QA:

- Use synthetic QA data only.
- Verify Home and Funds against the approved mockup terminology.
- Create a goal, update reserved balance, update a commitment, and confirm decision events appear in audit/export surfaces.

## Dependencies on A1/A2/A3

- A1: final table names, migrations, enum values, indexes, and seed strategy.
- A2: spendable engine fields and formula outputs, including provisional exposure and card obligation.
- A3: route permissions, actor/session context, and any administrator invitation impacts.
- Monthly close B5 consumes fund/spendable blockers and close-bundle summaries from this track.

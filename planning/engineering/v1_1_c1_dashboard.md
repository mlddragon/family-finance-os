# v1.1 C1 Dashboard Engineering Plan

Status: Draft  
Build phase: Phase 3  
Schema source: `planning/engineering/v1_1_a1_schema.md` controls the table names consumed by Dashboard summary builders.

## Purpose

Implement the v1.1 Dashboard screen from the approved mockup with chart data endpoints and Recharts-based visualizations.

The Dashboard should summarize current household state without hiding uncertainty:

- freshness and confidence labels
- cashflow trend
- category spend
- pool target progress
- net worth actual-only default with include-estimates toggle
- provisional labels for incomplete or stale data

## Non-goals

- Do not introduce hosted analytics or external chart services.
- Do not build a separate Streamlit app.
- Do not show estimates as default net worth.
- Do not let dashboard chart transformations diverge from report/export rollups.
- Do not remove existing Home, Reports, Review, or Transactions views.

## Schema/API

### Dependency

Add `recharts` to the web app dependency set in the implementation PR. This documentation PR does not modify application code or dependencies.

### Chart Data Endpoints

Add read-only endpoints that return chart-ready JSON while sharing backend summary builders with reports where practical:

- `GET /api/dashboard/summary?month=YYYY-MM`
- `GET /api/dashboard/cashflow?months=6`
- `GET /api/dashboard/category-spend?month=YYYY-MM`
- `GET /api/dashboard/pool-progress?month=YYYY-MM`
- `GET /api/dashboard/net-worth?from=YYYY-MM-DD&to=YYYY-MM-DD&include_estimates=false`

Response rules:

- Amounts remain strings from backend services, matching existing report patterns.
- Include `provisional` flags and reason codes on each chart series where applicable.
- Use allocation-aware totals from B2.
- Use estimate-aware net worth views from B3.
- Do not include raw transaction rows.

Example cashflow point:

```json
{
  "month": "2026-06",
  "inflow": "5200.00",
  "outflow": "4600.00",
  "net": "600.00",
  "provisional": true,
  "provisional_reasons": ["stale_required_source", "month_incomplete"]
}
```

### Provisional Labels

Provisional status should come from the same readiness/source freshness inputs used by reports and monthly close. Labels should be deterministic:

- `provisional` for stale/missing source data, incomplete month, open review backlog, or validation warnings.
- `blocked` only for blocking validation findings or close-blocking conditions.
- `actual_only` and `includes_estimates` for net worth series.

## UI (Mockup Screen)

Mockup reference: `planning/mockups/v1_1/index.html`, Screen C.

Dashboard screen:

- Add sidebar entry `Dashboard`.
- Header shows Freshness, Confidence, and Reviewed percentage.
- Header/status strip includes a period control, starting with "Last 6 months", that drives the cashflow `months` parameter.
- Cashflow chart: six-month net cashflow with provisional marker on incomplete/stale months.
- Category spend chart: current month category totals.
- Pool target progress chart: goal and pool progress including over-target warning state.
- Net worth tile: actual net worth default, with-estimates secondary value, Include estimates toggle, and warning banner.

Implementation guidance:

- Use existing `screens` array and conditional rendering in `App.tsx`.
- Keep visual components small and testable.
- Prefer Recharts components for real implementation rather than the mockup's static div bars.
- Provide accessible labels or text alternatives for chart summaries.
- Preserve synthetic QA/demo banners and local-only runtime status.

## Test Plan

Backend unit tests:

- Cashflow endpoint returns ordered months and correct provisional labels.
- Category spend uses split allocations when present.
- Pool progress uses B1/B2 fund calculations.
- Net worth endpoint excludes estimates by default.
- Chart endpoints do not include raw rows or account identifiers.

API tests:

- Dashboard endpoints require dashboard/report view permissions.
- Query validation rejects invalid months/date ranges.
- Synthetic fixtures produce deterministic chart payloads.

Frontend tests:

- Dashboard nav item renders and switches screens.
- Cashflow, category, pool progress, and net worth widgets render loading, error, empty, and success states.
- Include-estimates toggle changes query/options and displays warning banner.
- Provisional labels render for stale or incomplete data.

Human QA:

- Seed synthetic data with six months of cashflow and one stale source.
- Verify charts match Reports totals for the same period.
- Verify estimated net worth stays hidden until toggled.

## Dependencies on A1/A2/A3

- A1: final table names and any materialized summary choices.
- A2: spendable/funds source-of-truth calculations for chart summaries.
- A3: permissions and authenticated runtime status.
- B1/B2/B3: dashboard depends on funds, splits, and net worth services.
- B5: monthly close readiness/provisional labels should be consistent with dashboard confidence labels.

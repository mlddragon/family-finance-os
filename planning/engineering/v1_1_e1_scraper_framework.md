# v1.1 E1 Scraper Framework Engineering Plan

Status: Draft  
Build phase: Phase 5 - last in build order  
Schema note: `planning/engineering/v1_1_a1_schema.md` is not present in this checkout. Use the table and API names below from `planning/v1_1_expansion_decision_record.md`; align to A1 on merge.

## Purpose

Implement the vendor scraper framework after funds, splits, net worth, analyst export, dashboard, monthly close, and manual/CSV receipts are stable.

D5 requires this work to be last. The initial adapters are:

1. Amazon
2. Costco
3. Walmart

Scrapers produce auditable receipt headers and receipt lines. They do not create ledger transactions, do not store credentials in git, and do not bypass D11 promotion rules.

## Non-goals

- Do not store credentials, tokens, cookies, browser profiles, or session state in the repo.
- Do not commit scrape outputs, raw vendor files, receipt artifacts, screenshots, or logs with financial detail.
- Do not automate bank/card access.
- Do not use scraper lines as report inputs until promoted to splits.
- Do not add external hosted scraping services.
- Do not run scrapers in CI against real vendors.

## Schema/API

### Tables

Expected A1 tables or equivalents:

- `scraper_jobs`
- `scraper_job_events`
- `vendor_adapters`
- `receipts`
- `receipt_lines`
- existing `jobs`
- existing `artifacts`
- existing `decision_events`

If A1 keeps scraper jobs inside the generic `jobs` table, use:

- `job_type = "vendor_scrape"`
- `input_json` for adapter/options
- `output_json` for counts and artifact ids

### Adapter Contract

Each adapter returns normalized receipt output:

```json
{
  "vendor_key": "amazon",
  "run_id": "job_synthetic_001",
  "receipts": [
    {
      "external_receipt_id": "synthetic-order-1",
      "merchant": "Amazon",
      "receipt_date": "2026-06-12",
      "total_amount": "42.50",
      "lines": [
        {
          "line_index": 1,
          "description": "Synthetic item",
          "quantity": "1",
          "amount": "42.50",
          "category_key": null,
          "review_required": true,
          "review_reason": "category_needed"
        }
      ]
    }
  ],
  "quality": {
    "receipt_count": 1,
    "line_count": 1,
    "warnings": []
  }
}
```

Adapter stages:

- `prepare` - validate runtime and output paths
- `collect` - human-assisted or local browser scrape where allowed
- `normalize` - convert vendor output to receipt contracts
- `validate` - row counts, totals, required fields, duplicates
- `persist` - write receipts and lines through D1 services
- `audit` - write job events and artifact metadata

### Vendor Notes

Amazon:

- Start from the existing proof-of-concept knowledge, but do not migrate old raw files into git.
- Support order/detail pages only after manual QA confirms selectors and outputs.
- Handle split charges and grouped orders as review-required when ambiguous.

Costco:

- Support warehouse and online receipt shapes separately if needed.
- Expect mixed household/grocery/large-item baskets.
- Membership, travel, pharmacy, and service lines should default to review-required categories.

Walmart:

- Support pickup/delivery/order receipt shapes separately if needed.
- Grocery/household mixed baskets likely require review.
- Substitutions, refunds, and pickup fees should be explicit line/component types.

### API Shape

Proposed endpoints:

- `GET /api/vendor-adapters`
- `POST /api/vendor-scrapes`
- `GET /api/vendor-scrapes/{job_id}`
- `GET /api/vendor-scrapes/{job_id}/events`
- `POST /api/vendor-scrapes/{job_id}/cancel`

Run request:

```json
{
  "actor": "owner",
  "actor_context": {},
  "vendor_key": "amazon",
  "mode": "manual_browser_assist",
  "date_from": "2026-06-01",
  "date_to": "2026-06-30"
}
```

Error codes:

- `vendor_adapter_not_found`
- `vendor_scrape_disabled`
- `vendor_scrape_credentials_forbidden`
- `vendor_scrape_output_path_unsafe`
- `vendor_scrape_validation_failed`
- `vendor_scrape_permission_denied`

### Security Gates

Required gates before implementation and PR:

- No credentials, cookies, tokens, browser profiles, downloaded receipts, screenshots, or logs under git.
- All outputs under external `DATA_ROOT`.
- Artifact path safety checks mirror `reporting.ensure_safe_artifact_directory`.
- Scrape jobs write auditable events with actor context.
- QA/demo mode uses synthetic vendor fixtures only.
- Human QA per vendor is required before enabling an adapter.
- Adapter disabled by default until its QA script passes.
- Any persistent session storage requires explicit owner approval and must not live in the repo.

## UI (Mockup Screen)

No dedicated scraper mockup is approved. Initial UI should attach to existing Sources and Review flows:

- Sources: vendor adapter list, enabled/disabled state, last run, run button when allowed.
- Sources: job progress, warnings, and artifact links.
- Review: receipt review queues populated by scraper output.
- Transactions/Receipts: matched receipt lines remain enrichment until D11 promotion.

UI copy must state:

- Local only.
- No credentials in git.
- Scraper output becomes receipt lines first.
- Apply receipt lines as splits is an explicit later action.

## Test Plan

Backend unit tests:

- Adapter registry lists Amazon, Costco, and Walmart disabled by default unless settings enable them.
- Job creation rejects credential/session fields.
- Output path safety rejects paths outside `DATA_ROOT`.
- Normalizer converts synthetic vendor fixtures into `receipts` and `receipt_lines`.
- Validation catches duplicate external ids, missing totals, invalid dates, and mismatched totals.
- Job events record each stage and final status.
- Scraper output does not affect reports until promoted to splits.

API tests:

- Vendor scrape routes require import/scrape permissions.
- Disabled adapters cannot run.
- Synthetic adapter run creates receipt review queue items.
- Cancel endpoint marks active job canceled and records event.

Frontend tests:

- Sources shows adapter disabled/enabled states and last-run status.
- Run action surfaces safety warning and permission errors.
- Receipt review queues update after synthetic adapter output.
- D11 precedence text appears for scraper-created receipts.

Human QA per vendor:

- Preconditions: personal data root selected intentionally, browser/session artifacts outside git, adapter enabled by settings, local bind remains `127.0.0.1`.
- Steps: run one constrained date range, inspect job events, inspect generated receipt counts, review a sample receipt, promote one synthetic or sanitized line set to splits only after confirmation.
- Expected: no credentials or session files in repo, outputs under `DATA_ROOT`, receipts reviewable, reports unchanged until split promotion.
- Stop conditions: login challenge, CAPTCHA, selector drift, missing totals, unexpected downloads, path safety failure, or any credential/session artifact inside repo.

## Dependencies on A1/A2/A3

- A1: final job, adapter, receipt, and artifact schemas.
- A2: spendable/funds must remain insulated from unpromoted receipt lines.
- A3: permissions, session security, and actor audit context.
- D1: scraper output persists through receipt services and review queues.
- B2: D11 promotion to splits remains the only path from receipt lines to report/fund impacts.
- C1/B4/B5: dashboard, analyst pack, and monthly close may surface scraper-derived receipt review status but not count unpromoted lines as spending.

# Vendor Scraper Owner QA

Local-only vendor scraper adapters (Amazon, Costco, Walmart) stay **disabled by default**. Use synthetic mode first; only enable a vendor after reviewing its output under your personal `DATA_ROOT`.

## Enable a vendor adapter

1. Open Settings → Future integrations (or `PATCH /api/settings`).
2. Set `vendor_scraper.{vendor_key}.enabled` to `true` for one vendor at a time (`amazon`, `costco`, or `walmart`).
3. Confirm the adapter appears enabled on `GET /api/vendor-adapters`.

## Synthetic CI-style run (no browser, no credentials)

```bash
curl -sS -X POST http://127.0.0.1:8000/api/vendor-scrapes \
  -H 'Content-Type: application/json' \
  -d '{"actor":"owner","vendor_key":"amazon","mode":"synthetic","date_from":"2026-06-01","date_to":"2026-06-30"}'
```

Repeat with `costco` and `walmart`. Expect job status `completed`, receipts with `source_type=vendor_scraper`, and review-queue items for lines needing category or vendor-specific review.

Inspect job events: `GET /api/vendor-scrapes/{job_id}/events` — stages should include `collect`, `normalize`, `validate`, `persist`, and `audit`.

## Manual browser assist (personal QA only)

1. Export vendor JSON manually in the browser; do **not** commit exports to git.
2. Drop one or more `.json` files into `{DATA_ROOT}/vendor_scrapes/inbox/{vendor_key}/` (non-recursive).
3. Run with `"mode": "manual_browser_assist"` and the same enablement setting as above.
4. Verify normalized artifact under `{DATA_ROOT}/vendor_scrapes/{job_id}/normalized_output.json`.

## Stop conditions

- Login challenge, CAPTCHA, or selector drift during browser export.
- Missing totals or path errors (`vendor_scrape_output_path_unsafe`, `vendor_scrape_collect_empty`).
- Any credential, cookie, or session file appearing inside the repository.

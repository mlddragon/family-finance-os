# Archived Prototype: Family_Finance_planner

The private repository [`mlddragon/Family_Finance_planner`](https://github.com/mlddragon/Family_Finance_planner) is **archived research**, not the product implementation foundation.

## What it was

A script-and-Streamlit prototype for importing family financial data into local CSVs, matching Amazon orders to Chase transactions, and building budget intelligence reports.

## What moved to Family Finance OS

| Prototype asset | Product home |
| --- | --- |
| Updated PRD | `docs/product_requirements.md` |
| Category and review concepts | `planning/` docs and product settings |
| Ledger-integrity lessons | Import validation, normalization, reporting |
| Amazon enrichment patterns | Future enrichment slices (not copied verbatim) |

## What stayed in the archive

- Streamlit dashboard under `app/`
- One-off Python scripts (scrape, match, enrich, report builders)
- CSV folder workflow (`raw/`, `normalized/`, `snapshots/`)
- Historical tests and fixtures tied to the prototype architecture

## Policy

- Do not open PRs against the archived repository.
- Do not copy prototype scripts into the product repo without an approved architecture plan.
- Use synthetic data only when referencing prototype behavior in issues or docs.

## Archive README

When archiving, replace the prototype repository README with the content in [docs/archive/family_finance_planner_README.md](family_finance_planner_README.md).

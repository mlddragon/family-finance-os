# Prior Work Audit

## Executive summary

The prior `mlddragon/Family_Finance_planner` repo contains useful product discovery, validated financial-data integrity lessons, category/review concepts, and prototype evidence. It should not be used as the implementation foundation for Dillon Finances.

The most valuable material is the updated PRD, the ledger-integrity principles, the category and review workflow concepts, and the lessons from Amazon order matching, ledger-safe enrichment, review exposure, and budget intelligence reporting. The highest-risk inheritance would be copying the old app, scripts, CSV folder structure, generated artifacts, or Streamlit/dashboard assumptions into the new product before architecture has been reviewed.

## Useful product assets from old repo

- `docs/product_requirements.md`: migrated into this repo as the primary product source of truth.
- `docs/category_taxonomy.md`: useful as a domain reference for future taxonomy design, but not migrated yet because the new controlled taxonomy format and storage model are undecided.
- `docs/review_workflow.md`: useful review-workflow reference, especially the principle that human decisions live separately from raw and generated data.
- `docs/monthly_operating_workflow.md`: useful reference for the weekly/monthly operating rhythm.
- `docs/current_system_workflow.md`: useful as a prototype-state map and cautionary document, not as a target architecture.
- `docs/amazon_ledger_integration_design.md`: useful for the vendor-detail enrichment pattern and ledger-safe item allocation lessons.
- `docs/implementation_roadmap.md`: useful as historical sequencing input, but it reflects prototype constraints and should be rewritten after architecture decisions.
- `policy/naming_policy.yaml`: useful concept for controlled naming and blocked terms; should be reviewed before migration because policy scope and enforcement mechanics belong in architecture planning.
- `config/budget_policy.yaml`: useful concept for settings-driven thresholds, target modes, review thresholds, and target enforcement states; should not be copied as a live policy before owner review.

## Useful domain concepts from old repo

- Household financial operating system, not a one-off report generator.
- Ledger transactions are the cashflow source of truth.
- Vendor/order/receipt/item detail enriches the ledger but does not replace it.
- Missing or uncertain data becomes review work.
- Review exposure should remain visible in reporting and recommendations.
- Category Taxonomy should use controlled values, not free-form labels.
- Dance, Job Expenses, Medical, Projects, Jillybean Creations, Mason Hustle, reimbursement tracking, net worth, and retirement rebuild are first-class product concerns.
- Family-facing envelope views can simplify presentation, but must map back to audit-safe underlying categories.
- Settings-driven behavior is preferable to hardcoded household rules.
- AI advisor output should cite validated local outputs and remain provisional when data uncertainty is material.

## Useful data integrity lessons

- Preserve raw source files as evidence; never hand-edit them.
- Preserve ledger row count through enrichment.
- Do not add item rows to the account ledger.
- Do not double-count ledger transactions and vendor detail rows.
- Use order/receipt header rows for matching to ledger transactions.
- Use item/detail rows for enrichment, categorization, and review after a ledger-safe match exists.
- Do not use repeated parent totals from item-level files.
- Do not use estimated prices, average allocations, or equal splits as actual financial facts.
- Use exact cents arithmetic for matching and reconciliation-sensitive work.
- Validation should check row counts, duplicate IDs, schemas, amount signs, date parsing, naming policy, output creation, and known invariants.
- High-confidence looking reports are dangerous when review exposure is high; validation status and review exposure must travel with reports.

## Useful review workflow lessons

- Human decisions should be stored separately from raw and generated outputs.
- Review statuses need controlled values.
- Review queues should be prioritized by financial impact, uncertainty, and actionability.
- Priority review areas include vendor-detail uncertainty, uncategorized spending, Medical, Job Expenses, side hustles, project assignments, and large transactions.
- Only approved or changed review decisions should update a reviewed copy or controlled decision layer.
- Targets should remain provisional when review exposure is high or category uncertainty is material.
- Review work should be replayable, auditable, and validated before reporting uses it.

## Useful budget/cashflow lessons

- Budget intelligence should distinguish total spend from operating spend.
- Reports should separate Income, Transfers, Housing, Debt, fixed required spending, variable required spending, discretionary spending, side-hustle activity, projects, and review exposure.
- Controllable-spending analysis should avoid ranking fixed obligations as primary levers.
- Category targets should carry enforcement modes such as active, light, review-first, or review-only.
- Budget recommendations should be preliminary when category review exposure can materially change totals.
- Useful budget outputs include monthly spending summary, category spending summary, trends, top merchants/sources, review exposure, vendor impact, controllable levers, and a narrative summary.

## Items not to migrate

- Old Streamlit dashboard code under `app/`.
- `.streamlit/` configuration.
- Old dashboard requirements files.
- Old prototype scripts such as importers, Amazon scrapers, matchers, enrichment scripts, report builders, and review-override scripts.
- Old test suite and fixtures, unless specific tests are later rewritten against the new architecture.
- Raw financial exports under `raw/`.
- Normalized outputs under `normalized/`.
- Generated budget reports under `reports/`.
- Snapshot artifacts under `snapshots/` or prototype subdirectories.
- Local virtual environments, caches, and pytest artifacts.
- Old CSV review files containing household decisions, unless the owner explicitly approves a controlled migration plan.
- Old folder layout as a default product architecture.

## Risks from old implementation assumptions

- Treating CSV files as the long-term storage architecture before evaluating storage needs.
- Treating Streamlit as the default UI before reviewing household user experience, local/hosted model, and mutation workflow.
- Treating the old scripts as product architecture instead of prototype proofs.
- Allowing item-level vendor records to become ledger transactions.
- Baking vendor-specific Amazon logic into core ledger design.
- Copying generated reports or normalized files into the product repo and confusing prototype outputs with source-of-truth data.
- Preserving patchwork workflows that require manual file placement, script ordering knowledge, or implicit local state.
- Over-automating classification or matching before review gates and validation confidence are defined.
- Building UI before mockups and owner review.
- Designing architecture around current files rather than the closed-loop product process in the PRD.

## Recommended migration candidates

Migrate now:

- `docs/product_requirements.md`.

Consider later, after architecture review:

- Category Taxonomy concepts from `docs/category_taxonomy.md`.
- Review workflow concepts from `docs/review_workflow.md`.
- Monthly operating rhythm from `docs/monthly_operating_workflow.md`.
- Ledger-safe vendor enrichment concepts from `docs/amazon_ledger_integration_design.md`.
- Naming policy concept from `policy/naming_policy.yaml`.
- Budget policy concepts from `config/budget_policy.yaml`.
- Validation invariant examples from the old tests and scripts, rewritten for the new system.
- Selected prototype metrics as historical evidence in planning docs, not as live data files.

Do not migrate without explicit owner approval:

- Any raw, normalized, reviewed, or generated financial CSV.
- Any dashboard code.
- Any app code.
- Any old pipeline script.
- Any credential, browser session, cache, or local environment artifact.

## Open questions

- Should the new repo eventually include empty data directories, or should all financial-data directories remain untracked and created locally by tooling?
- Which old policy/config concepts should be rewritten first after architecture approval?
- Should prototype metrics be preserved in a historical appendix, or kept only in planning notes?
- Should any old tests be used as behavioral references when designing validation gates?
- What is the owner-approved boundary between local inspectable files and any future database-backed state?

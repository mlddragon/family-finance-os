# Family Financial Advisor PRD

## 1. Product Name

Family Financial Advisor

## 2. Product North Star

Build a local, trustworthy, reusable family financial advisor that stays as current as possible, improves cashflow literacy, supports long-term financial planning, tracks net worth, and turns financial data into actionable decisions — so the household can stay afloat, get monthly cashflow positive, rebuild stability, prosper, and get back onto a realistic retirement path.

## 3. Core Mission

The product exists to help the household answer, continuously and truthfully:

1. Are we cashflow positive or negative right now?
2. Where is the money going?
3. Which expenses are fixed, necessary, discretionary, reimbursable, business-related, tax-relevant, project-related, or review-needed?
4. What are the biggest controllable levers?
5. What actions would create monthly breathing room?
6. Are we rebuilding financial stability over time?
7. Are we moving back toward long-term wealth and retirement readiness?
8. Is our net worth improving?
9. Is our financial data current enough to act on?

This is not a one-time budgeting project. It is a long-term household financial operating system.

---

# 4. Guiding Principles

## 4.1 Truth over convenience

The system must prefer accurate incomplete data over polished but false data.

Rules:

- No fake precision.
- No averaged item prices pretending to be real prices.
- No equal-split item allocations pretending to be facts.
- No inferred values unless clearly labeled as assumptions.
- No silent double-counting.
- Missing or uncertain data must be surfaced as review work.

## 4.2 Ledger integrity

Bank and credit-card transactions are the source of truth for cashflow and account balances.

Detail sources, such as vendor orders, receipts, item-level records, service charges, subscription records, or reimbursement records, enrich the ledger. They do not replace the ledger.

Example:

- Card transaction = cashflow event.
- Vendor order/item/receipt data = reporting and categorization detail.
- Vendor item rows must not become replacement ledger transactions.

## 4.3 Reusable long-term system

The system must be repeatable.

It should support a recurring operating rhythm:

1. Import latest data.
2. Validate row counts, files, balances, and known invariants.
3. Enrich and match detail sources.
4. Generate review queues.
5. Apply controlled review decisions.
6. Generate budget intelligence reports.
7. Compare against targets.
8. Produce advisor recommendations.
9. Track progress month over month.

## 4.4 Current data beats stale analysis

Reports should clearly show data freshness:

- latest import date
- latest transaction date
- failed imports
- stale accounts
- review backlog
- validation status

The product is only useful if it stays current enough to support real decisions.

## 4.5 Cashflow literacy

The product should teach the household how money moves.

Reports should clearly separate:

- income
- transfers
- fixed required spending
- variable required spending
- discretionary spending
- debt and financing costs
- business or side-hustle activity
- job-reimbursable spend
- project or sinking-fund activity
- review exposure
- long-term planning activity

## 4.6 Review queues instead of hidden uncertainty

The product should not bury ambiguity.

Examples of review queues:

- retail/vendor items needing category review
- unmatched vendor-like card charges
- mixed-basket transactions
- job expense reimbursement candidates
- medical tax candidates
- side-hustle expense candidates
- project assignment candidates
- possible transfers
- unknown merchants
- suspicious or unusual transactions

## 4.7 Local-first and auditable

The product should run locally and produce inspectable files.

Preferred characteristics:

- local CSV/Markdown/YAML outputs
- deterministic scripts
- validation checks
- controlled configuration files
- clear logs
- no required banking credentials stored in the project
- no hidden state that cannot be audited

## 4.8 Decision support, not bookkeeping theater

Reports must lead to action.

The system should help answer:

- What should we cut?
- What should we cap?
- What should we reimburse?
- What should we defer?
- What should we fund?
- What requires manual review?
- What changed since last month?
- What is the next best financial move?

## 4.9 Long-term recovery

The system should support the transition from survival mode to wealth rebuilding.

Phases:

1. Cashflow stabilization
2. Breathing room
3. Debt and risk reduction
4. Long-term wealth rebuild
5. Prosperity and optionality

Long-term planning should include:

- retirement contribution planning
- emergency fund rebuilding
- debt payoff sequencing
- mortgage/recast/refinance decisions
- tax-aware savings decisions
- side-hustle profitability
- project funding
- net worth tracking
- retirement gap tracking

## 4.10 Vendor-agnostic design

The system must avoid becoming a one-vendor product.

Vendor-specific detail sources are examples of a broader data enrichment layer. Amazon is currently the first implemented vendor detail plugin and proof of concept, but the architecture should generalize to other vendors such as Walmart, Temu, Costco, Target, Apple, Google, PayPal, Venmo, and future sources.

Specific vendors should be called out only when:

1. They already have implemented support.
2. They require materially different handling.
3. They appear as examples in documentation.
4. They have unique data export, scraping, import, matching, or validation constraints.

## 4.11 Settings-driven behavior

All trigger points, thresholds, classifications, and behavior choices should live in configuration files or controlled data files where practical. They should not be hardcoded into scripts unless there is a strong technical reason.

Normal household tuning should not require code edits.

---

# 5. Current Household Context

## 5.1 Income shock

The household previously operated around a $210k salary. After layoff and reemployment, current salary is about $150k with a possible $10k bonus.

The product must help adjust the household from the prior spending structure to the new income reality.

## 5.2 Primary near-term goal

Get monthly cashflow safely positive again with breathing room.

## 5.3 Long-term goal

After stabilization, rebuild emergency reserves, reduce financial fragility, restart retirement contributions, track net worth, and get back onto a realistic long-term wealth path.

## 5.4 Important household categories

The product must support:

- Dance as a top-level category
- Jillybean Creations as a side-hustle category
- Mason Hustle as a side-hustle category
- Job Expenses and correlated Job Reimbursement
- Medical tax review tracking
- Projects/sinking funds
- Net worth tracking
- Retirement rebuild tracking

---

# 6. Naming Policy

The project uses `policy/naming_policy.yaml`.

Blocked terms must not be used in new filenames, directory names, column names, category names, subcategory names, documentation titles, or prompts except when explicitly discussing the naming policy itself.

Use “Category Taxonomy” for the category structure.

Preferred project naming:

- Category Taxonomy
- source of truth
- primary
- canonical
- approved
- included/excluded
- allowlist/blocklist only when appropriate and allowed by policy

All new scripts, docs, columns, and outputs should validate against the naming policy.

---

# 7. Product Users

## 7.1 Primary user

Mason, household financial operator and project maintainer.

Needs:

- accurate cashflow visibility
- current actionable reports
- clear decision support
- repeatable import/report workflow
- low manual friction
- confidence that the data is not lying

## 7.2 Secondary household users

Secondary household users may prefer a simple envelope-style view of household money.

Presentation preference:

- show money as buckets/envelopes where useful
- show available, spent, remaining, and over/under target
- use plain-language categories
- avoid technical ledger terminology in family-facing views
- show review-needed amounts clearly but simply

Important constraint:

Envelope-style presentation is a visual and planning layer only. It must not override system accuracy, ledger integrity, source-of-truth rules, validation requirements, or long-term planning goals.

The primary system remains ledger-accurate and audit-focused. The secondary-user interface can present that same data in a simpler envelope accounting layout.

Suggested envelope-style views:

- Household Essentials
- Groceries & Household
- Eating Out
- Dance
- Kids
- Pets
- Medical
- Projects
- Giving
- Fun Money
- Side Hustles
- Reimbursements Pending
- Emergency Fund
- Debt Paydown
- Retirement Rebuild

These envelopes should map back to controlled categories and budget buckets, not exist as unrelated free-form labels.

## 7.3 AI agent / Codex

Codex and ChatGPT act as implementation and analysis agents.

Needs:

- clear PRD
- deterministic file contracts
- validation scripts
- implementation roadmap
- small scoped tasks
- no ambiguous source-of-truth rules
- settings/config files for normal behavior changes

---

# 8. System Architecture

## 8.1 Local-first repo

The repo is the system’s operating base.

Core directories should include:

- `raw/`
- `normalized/`
- `reports/`
- `docs/`
- `policy/`
- `config/`
- `review/`
- `tests/`
- `app/`
- `data/`
- `snapshots/`

## 8.2 Data layers

### Raw layer

Source exports and scraped files.

Examples:

- bank CSV exports
- credit-card CSV exports
- vendor order/receipt exports
- statement PDFs
- manually entered snapshots

Raw files should not be mutated.

### Normalized layer

Cleaned transaction and enrichment outputs.

Examples:

- normalized transactions
- vendor order/detail files
- vendor/ledger matches
- ledger-safe enriched transactions
- review queues
- net worth snapshots

### Reporting layer

Decision-ready summaries.

Examples:

- monthly spending summary
- category spending summary
- review exposure report
- controllable levers
- net worth report
- retirement rebuild report
- advisor memo

### Documentation layer

Product rules, taxonomy, design notes, and operating instructions.

Examples:

- `docs/category_taxonomy.md`
- `docs/project_north_star.md`
- `docs/vendor_detail_plugin_framework.md`
- `docs/amazon_ledger_integration_design.md`
- `docs/product_requirements.md`
- `docs/monthly_operating_workflow.md`

### Policy/config layer

Controlled system behavior.

Examples:

- `policy/naming_policy.yaml`
- `config/system_settings.yaml`
- `config/category_rules.csv`
- `config/category_taxonomy.yaml`
- `config/budget_policy.yaml`
- `config/vendor_plugins.yaml`
- `config/review_rules.yaml`
- `config/matching_rules.yaml`
- `config/project_registry.csv`
- `config/reimbursement_rules.csv`
- `config/tax_review_rules.csv`
- `config/dashboard_settings.yaml`

### Review layer

Human decisions and corrections.

Examples:

- `review/manual_category_overrides.csv`
- `review/vendor_item_reviews.csv`
- `review/reimbursement_review.csv`
- `review/medical_tax_review.csv`
- `review/project_assignments.csv`

---

# 9. Vendor Detail Plugin Framework

## 9.1 Purpose

The system should support a reusable plugin-style framework for vendor detail data.

Purpose:

- Import, scrape, normalize, validate, match, enrich, and review vendor-specific detail without rewriting the whole system for each vendor.
- Keep the ledger cashflow model stable while allowing richer item/service detail where available.
- Allow vendor-specific quirks to live in plugins rather than contaminating core ledger logic.

## 9.2 Core plugin stages

Each vendor detail source should implement the same conceptual stages:

1. `discover`
   - Locate source files, exports, statement data, scrape outputs, or browser-harvested data.

2. `extract`
   - Pull raw order, item, receipt, service, subscription, or payment details from source data.

3. `normalize`
   - Convert vendor-specific data into the canonical vendor-detail schema.

4. `validate`
   - Check row counts, duplicate IDs, amounts, dates, missing fields, and plugin-specific invariants.

5. `match`
   - Match vendor-level orders/receipts/service charges to bank/card ledger transactions.

6. `enrich`
   - Attach vendor detail to ledger-safe reporting outputs.

7. `review`
   - Generate review queues for unmatched, ambiguous, category-needed, tax-relevant, reimbursement-relevant, or business-relevant records.

8. `report`
   - Produce vendor impact summaries and category contribution reports.

## 9.3 Canonical vendor schemas

The system should define canonical intermediate schemas so new vendor plugins can reuse downstream matching, enrichment, review, and reporting code.

### Vendor order / receipt header

- vendor_name
- vendor_plugin
- vendor_account_hint
- vendor_order_id
- vendor_receipt_id
- order_date
- purchase_date
- order_total
- subtotal
- tax
- shipping
- discounts
- rewards_or_store_credit
- gift_card_applied
- payment_instrument
- order_status
- detail_url
- source_file
- scrape_or_import_timestamp
- needs_review
- review_reason

### Vendor item / detail row

- vendor_name
- vendor_plugin
- vendor_order_id
- vendor_receipt_id
- item_id
- item_title
- item_description
- item_quantity
- item_price_actual
- item_subtotal_actual
- seller_or_department
- item_category_initial
- item_subcategory_initial
- item_review_required
- price_confidence
- price_missing_reason
- source_page_type
- source_file
- source_url
- scrape_or_import_timestamp

### Vendor financial component row

- vendor_name
- vendor_plugin
- vendor_order_id
- vendor_receipt_id
- component_type
- component_label
- amount
- payment_instrument
- source_file
- source_url
- scrape_or_import_timestamp

### Vendor match row

- vendor_name
- vendor_plugin
- match_id
- match_type
- confidence
- ledger_transaction_id
- vendor_order_id
- vendor_receipt_id
- ledger_amount
- vendor_order_total
- amount_difference
- date_difference_days
- match_notes
- review_required

## 9.4 Plugin examples

### Amazon plugin

- order history scraping
- order detail pages
- item-level price extraction
- order-to-card matching
- split-charge handling
- ledger-safe item category allocation

### Walmart plugin

- order history or receipt exports
- mixed grocery/household/item category handling
- store pickup/delivery handling
- card transaction matching

### Temu plugin

- marketplace order/item detail
- shipping delays and grouped orders
- possible small-dollar/high-volume category review
- marketplace item categorization

### Costco plugin

- warehouse receipts and online orders if available
- mixed household/grocery/large item baskets
- annual membership and travel/services separation

### Target plugin

- store/online receipt detail
- mixed household/kids/grocery item handling

### Apple/Google plugin

- subscriptions, app purchases, cloud services, media
- recurring service categorization rather than item receipt matching

### PayPal/Venmo plugin

- person-to-person transfers
- side-hustle payments
- reimbursements
- ambiguous processor descriptions

## 9.5 Plugin design rules

- Vendor plugins may use vendor-specific scraping/import logic.
- Vendor plugins must output canonical schemas.
- Core matching/enrichment/reporting should work against canonical schemas where possible.
- Vendor-specific special cases should remain isolated in plugin code/config.
- No plugin may create account-ledger transactions from item rows.
- No plugin may overwrite raw source files.
- No plugin may store credentials.
- No plugin may use estimated item prices as actuals.
- Missing detail must be marked explicitly.

## 9.6 Vendor plugin configuration

Create a machine-readable vendor plugin registry.

Recommended file:

- `config/vendor_plugins.yaml`

Example plugin entries:

- amazon
- walmart
- temu
- costco
- target
- apple
- google
- paypal
- venmo

Each plugin should define:

- vendor display name
- enabled status
- source file paths
- import method
- scrape method if applicable
- matching rules
- date windows
- amount tolerance
- payment instrument hints
- known transaction description patterns
- output schemas
- review rules
- category rule file
- validation expectations

Example conceptual fields:

- `plugin_key`
- `vendor_name`
- `enabled`
- `detail_type`
- `input_paths`
- `output_prefix`
- `ledger_match_enabled`
- `match_date_window_days`
- `match_amount_tolerance`
- `supports_item_detail`
- `supports_financial_components`
- `requires_manual_login`
- `credential_storage_allowed`
- `review_rules`
- `category_rules_path`

Credential rule:

- `credential_storage_allowed` must default to false.

---

# 10. Source-of-Truth Rules

## 10.1 Cashflow

The ledger transaction file is the source of truth for cashflow.

Current working output:

- `normalized/family_all_transactions_enriched.csv`

Base files should not be overwritten casually.

## 10.2 Vendor detail source-of-truth rules

The bank/card ledger remains the cashflow source of truth.

Vendor detail files are source-of-truth only for the vendor-specific details they accurately contain, such as:

- order IDs
- receipt IDs
- item names
- actual historical item prices
- taxes
- shipping
- discounts
- payment instruments
- service/subscription details

Vendor detail data must be linked to the ledger through matching outputs. It must not replace the ledger.

Rules:

- Use vendor order/receipt header rows for matching to ledger transactions.
- Use vendor item rows for category enrichment and review.
- Use vendor financial component rows for reconciliation and audit.
- Do not sum repeated parent totals from item-level files.
- Do not use old or unsafe vendor files for financial reporting.
- Do not use estimated amounts as actual amounts.
- Do not double count original ledger transactions and vendor detail rows.

Amazon is currently the first implemented vendor detail source. Walmart, Temu, Costco, Target, Apple, PayPal, Venmo, and other vendors should follow the same architecture where practical.

## 10.3 Current Amazon implementation

Amazon order-level file is the source of truth for Amazon order matching.

Current accepted files:

- `raw/amazon_orders/amazon_orders_last380_enriched_v4.csv`
- `raw/amazon_orders/amazon_order_items_last380_enriched_v4.csv`
- `raw/amazon_orders/amazon_order_financials_last380_enriched_v4.csv`
- `raw/amazon_orders/amazon_order_scrape_quality_last380_enriched_v4.csv`

Rules:

- Use order-level Amazon file for card charge matching.
- Use item-level Amazon file for category enrichment.
- Use financials file for reconciliation and audit.
- Do not sum repeated order totals in item-level files.
- Do not use old files with repeated parent order totals for spending totals.
- Do not use estimated item amounts.

## 10.4 Ledger-safe vendor enrichment

Outputs should preserve ledger row count.

Rules:

- Preserve ledger row count.
- Do not add vendor item rows to the ledger.
- Use ledger-safe scaled reporting where vendor detail totals and ledger cashflow differ.
- Preserve raw actual item amounts for audit.
- Scaled reporting must reconcile to matched ledger cashflow.
- Base ledger must not be overwritten.

---

# 11. Category Taxonomy

The Category Taxonomy is documented in:

- `docs/category_taxonomy.md`

Current top-level categories:

- Income
- Transfer
- Housing
- Utilities
- Groceries
- Household
- Eating Out
- Medical
- Pets
- Dance
- Kids
- Education
- Job Expenses
- Jillybean Creations
- Mason Hustle
- Transportation
- Insurance
- Debt
- Personal Care
- Entertainment
- Subscriptions
- Projects
- Gifts / Giving
- Taxes / Government
- Banking / Fees
- Cash
- Shopping
- Review / Uncategorized

## 11.1 Special category requirements

### Dance

Dance must remain a top-level category.

Generic trip subcategories:

- Trip Fees
- Trip Lodging
- Trip Transportation
- Trip Meals
- Trip Supplies

Specific trips should be tracked using a controlled key such as `dance_trip_key`, not permanent subcategories.

### Job Expenses

Job Expenses must support reimbursement tracking.

Recommended fields:

- `reimbursement_status`
- `reimbursement_id`
- `reimbursed_amount`
- `reimbursement_source`
- `reimbursement_notes`

Correlated income category:

- Income / Job Reimbursement

### Medical

Medical category does not automatically mean tax deductible.

Recommended fields:

- `tax_medical_candidate`
- `tax_medical_status`
- `tax_year`
- `reimbursed_amount`
- `reimbursement_source`
- `hsa_fsa_paid`
- `tax_notes`

### Projects

Projects are controlled subcategories, not free text.

Recommended registry:

- `config/project_registry.csv`

Recommended fields:

- `project_key`
- `project_name`
- `status`
- `start_date`
- `target_end_date`
- `budget_target`
- `funding_source`
- `notes`

### Side hustles

Supported top-level categories:

- Jillybean Creations
- Mason Hustle

Recommended fields:

- `business_entity`
- `business_purpose`
- `revenue_or_expense`
- `tax_review_required`
- `notes`

---

# 12. Settings-Driven Triggers and Behavior

All trigger points, thresholds, classifications, and behavior choices should live in configuration files or controlled data files where practical. They should not be hardcoded into scripts unless there is a strong technical reason.

Purpose:

- reduce code changes for normal household tuning
- make behavior auditable
- allow ChatGPT/Codex/human review loops to adjust settings safely
- support long-term maintainability

Recommended config files:

- `config/system_settings.yaml`
- `config/category_taxonomy.yaml`
- `config/budget_policy.yaml`
- `config/vendor_plugins.yaml`
- `config/review_rules.yaml`
- `config/matching_rules.yaml`
- `config/project_registry.csv`
- `config/reimbursement_rules.csv`
- `config/tax_review_rules.csv`
- `config/dashboard_settings.yaml`
- `policy/naming_policy.yaml`

## 12.1 Examples of configurable behavior

### Review thresholds

- review all transactions over a configurable dollar amount
- review all unmatched vendor charges
- review all Shopping items over a configurable threshold
- review medical candidates over a threshold
- review job expenses until reimbursement status is resolved
- review side-hustle candidates until business purpose is confirmed

### Matching rules

- date windows by vendor/plugin
- amount tolerance
- split charge behavior
- grouped order behavior
- refund matching behavior
- subscription/service charge handling
- confidence labels
- review-required triggers

### Category rules

- merchant-to-category mappings
- item keyword rules
- category/subcategory approved values
- budget bucket mapping
- business/side-hustle classification rules
- tax candidate rules

### Budget behavior

- monthly targets
- warning thresholds
- hard caps
- envelope display groups
- rollover behavior if implemented
- sinking fund rules
- project funding rules

### Dashboard behavior

- visible pages
- default date range
- family-facing envelope labels
- warning states
- stale-data thresholds
- review priority thresholds

### AI advisor behavior

- weekly/monthly memo cadence
- alert thresholds
- cashflow risk triggers
- review backlog warnings
- spending spike definitions
- recommendation guardrails

## 12.2 Requirement

Every script that uses thresholds or behavior rules should read from config when practical.

If a value is hardcoded, the script should either:

1. explain why in comments, or
2. treat the hardcoded value as a default that can be overridden by config.

---

# 13. Functional Requirements

## 13.1 Data import

The system must support repeatable import workflows for:

- Alliant Checking
- Alliant Savings
- Alliant Credit Card
- Chase Prime Visa
- Rocket Mortgage/manual mortgage data
- vendor order/item/receipt history
- Walmart order history
- Temu order history
- Costco receipts/order data
- Target receipts/order data
- Venmo
- PayPal
- Greenlight
- other future accounts

Each import must produce:

- normalized output
- row count summary
- validation result
- review-needed rows
- snapshot/archive where appropriate

## 13.2 Data validation

Each pipeline must validate:

- input files exist
- expected columns present
- row counts reasonable
- duplicate transaction IDs
- amount signs
- date parsing
- source/account metadata
- forbidden column names
- blocked naming-policy violations
- output file creation
- known invariants

Validation failures must be explicit.

## 13.3 Matching and enrichment

The system must support conservative matching between ledger transactions and vendor/detail sources.

Current implemented example:

- Card transaction ↔ Amazon order-level matching

Future matching examples:

- Walmart receipts/orders ↔ card transactions
- Temu orders ↔ card transactions
- Costco receipts/orders ↔ card transactions
- Target receipts/orders ↔ card transactions
- Apple/Google subscriptions ↔ card transactions
- PayPal/Venmo payments ↔ transfers, reimbursements, side-hustle activity
- reimbursements ↔ job expenses
- refunds ↔ purchases
- transfers ↔ counterpart transactions
- mortgage/loan payments ↔ balances

Matching must separate:

- high confidence
- medium confidence
- low confidence
- review required
- unmatched

Vendor-specific match behavior should be plugin-configurable.

## 13.4 Review queues

The system must create review queues for:

- unmatched transactions
- uncertain category assignments
- high-dollar items
- mixed-basket vendor transactions
- medical tax candidates
- job reimbursement candidates
- side-hustle business candidates
- unknown merchants
- possible errors/fraud
- project assignment candidates

Review queue rows should include:

- priority
- review type
- date
- amount
- merchant/source
- current category
- suggested category
- reason
- recommended action
- source file
- status

## 13.5 Category override system

Human review decisions must be stored separately from raw and normalized data.

Recommended output:

- `review/manual_category_overrides.csv`

Overrides should be deterministic and replayable.

The system should never require manual edits to raw source files.

## 13.6 Budget intelligence

The system must generate monthly budget intelligence reports.

Required outputs:

- monthly spending summary
- category spending summary
- category monthly trend
- top merchants/sources
- review exposure summary
- controllable spending levers
- vendor category impact
- budget intelligence Markdown summary

Reports must include:

- total spending excluding Income and Transfer
- operating spending excluding Income, Transfer, Debt, Housing, Cash, Banking / Fees
- fixed required spending
- variable required spending
- discretionary spending
- business/side-hustle spending
- project/sinking fund spending
- review exposure
- month-over-month trend
- recent 3-month trend
- top controllable categories

## 13.7 Budget targets

The system must support target budgets.

Recommended config:

- `config/budget_policy.yaml`

Targets should support:

- monthly target
- warning threshold
- hard cap
- category bucket
- review threshold
- notes

Budget targets should eventually be compared against actuals in dashboard and reports.

## 13.8 Reimbursement tracking

The system must track job reimbursable spending.

Required concepts:

- job expense transaction
- reimbursement status
- submitted date
- reimbursed date
- reimbursement amount
- reimbursement deposit match
- outstanding reimbursement balance

Outputs:

- reimbursement review queue
- reimbursement aging report
- reimbursement summary

## 13.9 Medical tax review

The system must track possible tax-relevant medical expenses.

Required concepts:

- medical transaction
- tax candidate status
- reimbursement/HSA/FSA treatment
- tax year
- amount potentially eligible for review
- notes

The system must not declare expenses tax deductible automatically.

Outputs:

- medical tax review queue
- annual medical tax candidate report

## 13.10 Side-hustle tracking

The system must support Jillybean Creations and Mason Hustle.

Reports should include:

- revenue
- expenses
- net cashflow
- materials
- tools/equipment
- packaging
- shipping
- fees
- inventory
- mixed personal/business review

## 13.11 Projects and sinking funds

The system must support controlled project tracking.

Examples:

- Emergency Fund Rebuild
- Christmas / Holidays
- Home Repair Project
- Car Replacement
- Vacation / Family Goal
- Dance trip
- Technology Replacement

Projects require:

- controlled registry
- budget target
- funding plan
- transaction assignments
- remaining amount
- status

## 13.12 Net worth tracking

Net worth tracking belongs in the product.

Initial implementation can be manual snapshot-based.

Recommended file:

- `normalized/net_worth_snapshots.csv`

Required columns:

- `snapshot_date`
- `asset_or_liability`
- `account_name`
- `institution`
- `category`
- `subcategory`
- `balance`
- `valuation_method`
- `confidence`
- `notes`

Required outputs:

- `reports/net_worth/net_worth_summary.csv`
- `reports/net_worth/net_worth_summary.md`

Metrics:

- total assets
- total liabilities
- net worth
- liquid cash
- consumer debt
- mortgage balance
- home equity
- retirement balance
- retirement gap flag
- month-over-month change
- trend since baseline

Valuation rules:

- actual balances preferred
- home and vehicle values must be labeled as estimates unless from authoritative source
- estimated assets must not create false confidence

## 13.13 Retirement planning

The product must eventually support retirement rebuild planning.

Minimum concepts:

- current retirement balance
- contribution rate
- employer match if applicable
- target contribution rate
- catch-up strategy
- monthly surplus available for retirement
- retirement gap indicator
- rebuild milestones

The system should not recommend retirement contributions that break monthly cashflow stability.

## 13.14 Dashboard

The product should include a local dashboard.

Recommended first implementation:

- Streamlit
- local-only
- read-only MVP
- CSV-backed
- no login required
- no database required initially
- no mutation of source files in v1

Dashboard pages:

1. Current Status
2. Monthly Spending
3. Review Queue
4. Projects / Reimbursements / Tax
5. Net Worth / Long-Term Plan
6. Data Freshness / Validation

Dashboard should show:

- latest data refresh
- validation status
- monthly income/spend
- operating spend
- category trends
- top controllable levers
- review queue
- vendor enrichment status
- reimbursement exposure
- medical tax candidates
- project balances
- net worth snapshot
- retirement rebuild status

## 13.15 AI advisor

The AI advisor should use the reports and validation outputs to generate analysis.

Advisor should answer:

- What changed since last month?
- Why did spending spike?
- Which categories are controllable?
- What should be reviewed first?
- What cuts would create a specific monthly surplus?
- Are reimbursements outstanding?
- Are medical tax candidates being tracked?
- Are side hustles profitable?
- Is net worth improving?
- Are we on track to restart retirement contributions?

The AI advisor must cite or point to source files/outputs when possible.

## 13.16 QA and demo environment

The product should support a semi-persistent QA and demo environment as a single additive feature of this PRD.

The QA feature is specified in `docs/qa_feature_requirements.md`. That FRD defines the environment model, QA data lifecycle, synthetic scenario requirements, visual environment markers, QA-only dev mode boundary, reset rules, and contributor setup expectations.

The PRD-level requirement is:

- personal and QA environments must remain clearly separated
- personal data must run on `127.0.0.1:28080` by default
- QA synthetic data must run on `127.0.0.1:28081` by default
- QA data must be synthetic, clearly labeled, and stored outside git
- QA reset and dev controls must not create a routine path to mutate or delete personal data
- the main product mission, ledger integrity rules, and local-first privacy requirements remain unchanged

---

# 14. Non-Functional Requirements

## 14.1 Accuracy

Financial reports must avoid double-counting and fake precision.

## 14.2 Auditability

Every derived output should be traceable to source files.

## 14.3 Repeatability

Scripts should be runnable repeatedly without corrupting prior outputs.

## 14.4 Local-first privacy

Default system behavior should not require uploading financial data to external services beyond explicit user action.

## 14.5 Safety

No scripts should store banking passwords or credentials.

## 14.6 Testability

Every major pipeline should have tests or validation scripts.

## 14.7 Clear failure modes

Validation failures should be specific and actionable.

## 14.8 Controlled vocabularies

Categories, projects, reimbursement statuses, tax statuses, review statuses, plugin names, and match statuses should use controlled values.

## 14.9 Configurable behavior

Trigger points and behavior choices should be configurable, not code-bound, wherever practical.

---

# 15. Current Implemented State

## 15.1 Alliant

Status: usable.

Known output:

- `normalized/final_alliant_transactions.csv`
- Alliant data integrated into family ledger copy

## 15.2 Chase

Status: usable.

Known output:

- `normalized/combined_chase_prime_normalized_transactions.csv`

## 15.3 Vendor detail proof of concept: Amazon

Status: accepted.

Known outputs:

- `raw/amazon_orders/amazon_orders_last380_enriched_v4.csv`
- `raw/amazon_orders/amazon_order_items_last380_enriched_v4.csv`
- `raw/amazon_orders/amazon_order_financials_last380_enriched_v4.csv`
- `raw/amazon_orders/amazon_order_scrape_quality_last380_enriched_v4.csv`

Accepted metrics:

- 639 enriched orders
- 1,336 item rows
- 100% actual item price coverage
- no estimated item prices
- no forbidden allocation columns
- quality validation passed

## 15.4 Card/vendor matching proof of concept: Amazon

Status: conservative and audited.

Known outputs:

- `normalized/chase_amazon_order_matches.csv`
- `normalized/chase_amazon_unmatched_charges.csv`
- `normalized/amazon_unmatched_orders.csv`
- `normalized/chase_amazon_match_quality_summary.csv`
- `normalized/chase_amazon_matched_item_enrichment.csv`

Known metrics:

- 599 Amazon-like card charges totaling $20,552.64
- 639 Amazon orders totaling $26,846.72
- 401 matched card charges totaling $15,196.82
- 349 matched Amazon orders totaling $15,196.82
- 198 unmatched card charges totaling $5,355.82
- 290 unmatched Amazon orders totaling $11,649.90
- 317 exact single matches
- 32 split matches
- 3 review matches

## 15.5 Ledger-safe vendor enrichment proof of concept: Amazon

Status: validated.

Known outputs:

- `normalized/family_all_transactions_enriched.csv`
- `normalized/amazon_item_category_allocations.csv`
- `normalized/amazon_review_queue.csv`
- `normalized/monthly_spending_by_category_enriched.csv`
- `normalized/ledger_safe_amazon_enrichment_summary.csv`

Known metrics:

- input ledger rows: 2,095
- output ledger rows: 2,095
- row count preserved
- 401 matched card transactions enriched
- 717 item allocation rows
- 352 duplicate item rows removed
- raw item amount: $14,678.64
- scaled reporting amount: $15,196.82
- matched card cashflow amount: $15,196.82
- scaled difference: $0.00
- review queue rows: 1,118
- validation passed

## 15.6 Documentation and policy

Status: partially implemented.

Implemented:

- `policy/naming_policy.yaml`
- `docs/category_taxonomy.md`
- `docs/amazon_ledger_integration_design.md`

Needed:

- `docs/project_north_star.md`
- `docs/product_requirements.md`
- `docs/vendor_detail_plugin_framework.md`
- `docs/monthly_operating_workflow.md`
- implementation roadmap

---

# 16. Desired End State

## 16.1 Daily/weekly state

The user can run one command or open the dashboard and know:

- whether data is current
- what accounts are stale
- current cashflow picture
- current review backlog
- current top spending categories
- current controllable levers
- outstanding reimbursements
- project status
- net worth status
- retirement rebuild status

## 16.2 Monthly close

The system supports a monthly financial close:

1. Import all account data.
2. Validate all pipelines.
3. Run enrichment and matching.
4. Clear critical review queue items.
5. Generate monthly reports.
6. Compare to targets.
7. Produce advisor memo.
8. Decide next-month actions.
9. Snapshot outputs.

## 16.3 Decision outputs

The system should produce:

- “What happened?”
- “Why did it happen?”
- “What can we control?”
- “What should we do next?”
- “What needs review before we trust this?”
- “Are we improving?”

## 16.4 Long-term outputs

The system should produce:

- net worth trend
- debt trend
- emergency fund trend
- retirement contribution trend
- side-hustle profitability
- project funding progress
- household financial phase status

## 16.5 Vendor plugin end state

The final product supports multiple vendor detail plugins through a shared framework. Amazon is only the first implemented example. Future vendors such as Walmart, Temu, Costco, Target, Apple, PayPal, Venmo, and others should plug into the same pipeline wherever practical.

The product should allow most normal tuning through settings/configuration, not code edits.

Family-facing views may use an envelope accounting layout, while the underlying system remains ledger-accurate and audit-safe.

---

# 17. MVP Definition

## 17.1 MVP must include

- repeatable import workflow for current available accounts
- validated family ledger
- accepted first vendor-detail enrichment proof of concept
- card/vendor matching and ledger-safe reporting
- Category Taxonomy
- settings-driven behavior foundation
- budget intelligence reports
- review queue
- basic local dashboard
- project North Star doc
- product requirements doc
- monthly workflow doc

## 17.2 MVP does not require

- fully automated bank connections
- perfect matching of all vendor records
- full Walmart/Costco/Temu item-level automation
- automatic retirement planning
- hosted web app
- multi-user auth
- direct bill pay
- direct account control
- tax filing automation

---

# 18. Stretch Goals

- net worth snapshot v1
- retirement rebuild calculator
- Streamlit dashboard v1
- reimbursement tracker
- medical tax candidate report
- project/sinking fund tracker
- side-hustle P&L reports
- monthly advisor memo
- additional vendor item-level plugins
- recurring import runner
- alerting for stale data or spending spikes

---

# 19. Success Metrics

## 19.1 Data quality metrics

- ledger row count preserved during enrichment
- no duplicate transaction IDs
- no double-counting in reports
- validation status passed
- review exposure tracked
- import freshness tracked
- plugin validation passed

## 19.2 Budget metrics

- monthly cashflow trend
- operating spend trend
- discretionary spend trend
- required spend trend
- review-required spend percentage
- top controllable category reductions

## 19.3 Recovery metrics

- emergency cash balance
- credit card balance
- consumer debt
- net worth
- retirement balance
- retirement contribution rate
- outstanding reimbursements
- side-hustle net cashflow

## 19.4 Workflow metrics

- time to monthly close
- review queue count
- percentage of transactions auto-categorized with confidence
- stale account count
- number of manual corrections needed
- number of behavior changes handled through config rather than code

---

# 20. Major Risks

## 20.1 False confidence

Risk: reports look precise while review exposure is high.

Mitigation: always show review exposure and validation status.

## 20.2 Double-counting

Risk: item-level detail multiplies ledger totals.

Mitigation: ledger-safe enrichment rules and validation.

## 20.3 Stale data

Risk: decisions based on old exports.

Mitigation: freshness dashboard and import workflow.

## 20.4 Over-automation

Risk: forcing matches or categories that should remain review-needed.

Mitigation: conservative matching and review queues.

## 20.5 Scope creep

Risk: building dashboards, agents, net worth, and more plugins before cashflow reports stabilize.

Mitigation: implementation roadmap with phases.

## 20.6 Vendor-specific sprawl

Risk: each vendor becomes a one-off pipeline with incompatible outputs.

Mitigation: vendor detail plugin framework and canonical schemas.

## 20.7 Hardcoded behavior

Risk: normal household tuning requires code changes.

Mitigation: SQLite-backed settings exposed through the Settings UI, with auditable change events and validations.

---

# 21. Immediate Next Work

This section tracks the current versioned path from the local Docker MVP toward a releasable open-source MVP. It intentionally replaces the prototype-era CSV, YAML, and Streamlit next-work list. Those artifacts remain useful as research history, but they are not the implementation path for this product.

## 21.1 Current baseline

Version `0.1.0` established the local Docker MVP with synthetic data, SQLite operational state, import/validation/quarantine, review decisions, reports, monthly close, and advisor export.

Version `0.2.0` established open-source readiness foundations: MPL-2.0 licensing, generic default branding, i18n scaffolding with maintained `en-US`, database-backed install settings, source templates separated from required sources, and a stable category catalog.

## 21.2 Finish current verification and owner smoke tracking

The current build has already received owner smoke testing for the implemented v1 behaviors. Remaining verification work should focus on confirming repository hygiene, CI/test health, and local Docker readiness without committing real financial data, generated reports, database files, or credentials.

Owner real-data smoke testing remains a manual checkpoint. Evidence captured in the repository must be sanitized counts, source names, and pass/fail notes only.

## 21.3 Version 0.3.0 reviewability, QA, and audit foundation

Version `0.3.0` should combine the already-merged Settings/audit quality-of-life work with reviewability, QA/demo, and local actor audit foundations.

Scope:

- Settings that cannot be edited should be hidden by default, with an explicit control to show read-only settings.
- Settings lists should use friendly names, current values, and default values by default, with optional technical columns.
- Settings audit history should show saved notes.
- AI-agent repo guidance should live at the root through `AGENTS.md`, `CODEX.md`, and `CHATGPT.md`.
- Personal and QA Docker instances should run side by side with visible runtime identity.
- QA should support script-level reset/seed with a single `baseline` synthetic scenario.
- QA-generated reports, close bundles, advisor exports, and manifests should carry a clear synthetic marker.
- Local actor/persona context should be selectable in the UI and persisted beside existing actor strings for future audit/RBAC work.

Settings QoL was tracked by GitHub issues `#47`, `#48`, and `#49`. The v0.3.0 foundation work adds the QA/demo and local actor audit slice without implementing full RBAC.

## 21.4 Post-v0.3.0 permission, elevation, suggestion, and approval foundations

After the lightweight local actor foundation lands, the next product foundation is the permission and approval framing discussed with the owner:

- Administrator as an elevated administrative persona, not the owner of financial data
- Finance Manager as the highest financial-data authority
- lightweight permission matrix with immutable permission-state audit records
- deny entries that override inherited allows
- current display names in main audit views, with historical names available in details when audit fidelity requires them
- admin/elevated mode for risky settings and approval-rule changes
- optional approval mode for risky or high-value changes, hidden unless enabled
- suggestions queue versus approvals queue
- view-as/troubleshooting simulation without true impersonation until auth and audit guarantees mature

This work is further captured in `planning/post_v030_permissions_elevation_approvals.md`.

## 21.5 Later product foundations

The following remain important but should wait until the user/persona/permission foundation is stable:

- net worth snapshot and long-term planning workflows
- vendor enrichment beyond source-file imports, including Amazon, Walmart, and Costco item-level detail
- locally hosted LLM or vendor-agnostic AI scaffolding beyond approved stubs
- automated high-confidence decisions after human-reviewed rules mature
- role-limited advisor/report-sharing flows
- LAN/NAS deployment hardening and authentication

---

# 22. Explicit Non-Goals

The product must not:

- store banking credentials
- initiate payments
- move money
- make tax filing claims
- overwrite source ledger files without explicit approval
- silently mutate raw exports
- force uncertain matches
- hide review exposure
- use item-level rows as account-ledger transactions
- depend on a hosted financial app as the default source of truth
- build one-off vendor pipelines that cannot be reconciled into the common system

---

# 23. Implementation Philosophy

Build in small validated slices, but guided by the full end state.

Each Codex task should include:

- exact scope
- source files
- output files
- forbidden actions
- validation requirements
- tests
- final console summary
- readiness recommendation

Each ChatGPT analysis loop should:

- inspect summaries
- call out risks
- decide readiness
- produce the next scoped task
- avoid unnecessary back-and-forth

Each human review loop should:

- focus on high-impact review queues
- update controlled review files
- avoid editing raw data
- improve rules over time

Vendor plugins should be implemented as small projects using the shared plugin contracts instead of one-off scripts where possible.

Settings should be updated through controlled files when practical, not code edits.

---

# 24. Final Product Vision

The final product is a local financial command center.

It should let the household see the truth quickly, understand the why, review only what matters, and make decisions that improve both monthly cashflow and long-term financial recovery.

The system should become a durable monthly operating rhythm:

- stay current
- validate truth
- understand spending
- take action
- track progress
- rebuild wealth

It should support multiple detail-source plugins, configurable behavior, a ledger-accurate core, envelope-style family-facing presentation, and AI-assisted decision support.

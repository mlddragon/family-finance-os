# Clarifying Questions Before Architecture Design

These questions should be answered before architecture design and before any application implementation starts.

## Runtime environment

1. What is the primary runtime target for the first product slice: Mason's Mac only, any local desktop, a home server, or a hosted environment?
2. Should the system be usable fully offline once source exports are available?
3. Should routine operation happen through a desktop app, browser app on localhost, command runner, or a combination?

## Local vs hosted model

1. Is local-first a hard requirement for all financial data, or can some derived summaries be hosted later?
2. Are there any circumstances where raw transaction data may leave the local machine?
3. Should remote access be supported later, or explicitly out of scope until the local product is stable?

## Database and storage options

1. Is the owner open to a local database such as SQLite or DuckDB for product state if files remain exportable and auditable?
2. Should CSV remain an interchange/export format rather than the internal storage layer?
3. Are there storage formats the owner does not want used for privacy, durability, or maintainability reasons?
4. What level of human-readability is required for core state versus audit exports?

## UI direction

1. Should the first UI be operator-focused, household-facing, or split into both modes?
2. Is a browser-based local UI acceptable, or is a desktop app preferred?
3. Should the household-facing experience use envelope-style language as a primary view?
4. What must be mocked up and approved before UI implementation begins?
5. Should the first UI allow edits/review decisions, or remain read-only until the data model is proven?

## Data privacy boundaries

1. What categories of data are never allowed to leave the local machine?
2. Can AI tools read local derived summaries if raw transaction lines are excluded?
3. Can AI tools read transaction-level detail for analysis with explicit owner approval?
4. Should account names, last four digits, merchant names, and item titles be considered sensitive by default?
5. What audit trail is required for any AI-assisted recommendation or data change?

## Expected import sources

1. Which sources must be supported in the first closed-loop slice?
2. Which current sources are highest priority: Alliant Checking, Alliant Savings, Alliant Credit Card, Chase Prime Visa, Amazon, mortgage/manual balances, PayPal, Venmo, Greenlight, or others?
3. Are any institutions changing soon, making current prototype import logic less valuable?
4. Should PDF statements be in scope early, or should the first slice rely on exported transaction files?

## Manual vs automated imports

1. Is manually downloading source exports acceptable for the first product slice?
2. Should the product include an import checklist before it includes automated import connectors?
3. Are browser-assisted vendor exports acceptable when the user logs in manually?
4. Are bank aggregation services off limits unless explicitly approved as paid or external-data tools?

## Review workflow

1. Who will perform review decisions: Mason only, multiple household users, or Mason with advisor assistance?
2. Which decisions require explicit owner approval before they update controlled state?
3. Should review decisions be reversible with a visible history?
4. Should the first review workflow support transaction splits, or only category/status decisions?
5. What review queue is most valuable first: categorization, reimbursements, medical tax, projects, vendor items, or stale/validation issues?

## AI and agent role

1. Should AI act only as an advisor, or may it draft controlled changes for approval?
2. Can AI propose category rules, budget targets, or review decisions if a human approves before applying?
3. What recommendation types should be blocked until data integrity gates pass?
4. Should AI recommendations be stored as artifacts with citations to validated outputs?
5. What budget or cost gate should apply before any paid AI usage?

## Net worth and retirement planning

1. Should net worth tracking be part of the first closed-loop slice or a later phase?
2. Are manual balance snapshots acceptable for assets and liabilities?
3. Which retirement accounts and planning assumptions matter first?
4. Should home and vehicle values be tracked as estimates, excluded, or included only after explicit owner approval?
5. What decisions should the product never recommend until cashflow is stable?

## Household user experience

1. What should a non-technical household user be able to understand in under two minutes?
2. Should household-facing views hide ledger terminology by default?
3. Which views may show sensitive merchant/item details?
4. Should there be separate operator and family views from the start?

## Deployment expectations

1. Should the first product run from the repo only, or be packaged as an app later?
2. Is a local development server acceptable during early planning and mockup review?
3. Should deployment avoid any cloud dependency until explicitly approved?
4. Is multi-device access a later requirement?

## Backup and export expectations

1. What backup target is acceptable for financial product state: local external drive, encrypted cloud folder, private git repo for non-data files, or another option?
2. Should exports be generated automatically after each monthly close?
3. Should all controlled decisions be exportable as human-readable files?
4. What retention policy should apply to raw imports, normalized states, reports, and snapshots?

## Delegation boundaries

1. Which technical decisions does the owner want to approve directly?
2. Which decisions can Codex make routinely if they are free, local-first, reversible, and widely used?
3. Should Codex stop for approval before adding any new dependency?
4. Should Codex stop for approval before choosing a database, UI framework, import automation approach, or AI integration pattern?
5. What counts as a cost-bearing decision requiring explicit approval?

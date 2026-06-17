# Initial Product Planning Plan

This is not an implementation plan. It defines the planning process required before the first line of application code is written.

## Planning phases

### Phase 0: Repository foundation

Outcome: clean product repo with PRD and planning materials only.

Status: started by this setup task.

Required outputs:

- Clean repo scaffold.
- Migrated PRD.
- Prior-work audit.
- Clarifying questions.
- Initial planning gates.
- Repo setup summary.

### Phase 1: Product scope alignment

Outcome: owner and Codex agree on the first minimally viable closed-loop system.

Decisions:

- First import sources.
- First review queue.
- First reporting outputs.
- First user interface mode.
- Data privacy boundaries.
- Definition of "current enough to act."

### Phase 2: Architecture options

Outcome: owner reviews architecture options before implementation.

Decisions:

- Local-only versus local-first with optional hosted access later.
- Storage model.
- UI runtime.
- Import orchestration approach.
- Validation and audit model.
- Controlled decision storage.
- AI/advisor boundaries.

### Phase 3: Data integrity design

Outcome: explicit data contracts and review gates for source data, derived state, and controlled decisions.

Decisions:

- Ledger source-of-truth rules.
- Import validation requirements.
- Matching confidence rules.
- Review decision lifecycle.
- Report readiness rules.
- Snapshot/export requirements.

### Phase 4: UX mockups

Outcome: mockups approved before UI implementation.

Mockups should cover:

- Operator current-status view.
- Review queue workflow.
- Data freshness and validation view.
- Budget/cashflow view.
- Household-facing envelope view if included in the first slice.

### Phase 5: Implementation planning

Outcome: an implementation plan with tasks, tests, validation, and owner review checkpoints.

This phase starts only after Phases 1-4 have owner approval.

## Required owner review gates

- Approval of first closed-loop slice.
- Approval of storage model.
- Approval of UI direction.
- Approval of local versus hosted boundary.
- Approval of import source priority.
- Approval of any workflow that writes controlled decisions.
- Approval of any data migration from the old repo beyond the PRD.
- Approval of any AI access to transaction-level or item-level data.
- Approval of any paid tool, paid dependency, or external service.

## Data integrity gates

Stop for owner review before proceeding when:

- Raw data would be copied, transformed, uploaded, or retained in a new location.
- Normalized financial data would be imported into the new product state.
- A generated report would be used as source-of-truth state.
- A matching or classification rule could materially affect cashflow conclusions.
- Review decisions would be applied to controlled state.
- Item/vendor detail would affect category totals.
- Any process might overwrite base ledger, raw source, or controlled decision files.
- Any system stores credentials, tokens, browser sessions, or account identifiers beyond approved local settings.

## UI mockup gates

Mockups are required before implementing:

- Review queue editing.
- Household-facing envelope views.
- Budget target workflows.
- Data freshness/validation dashboard.
- Recommendation/advisor display.
- Net worth and retirement planning views.

Mockups should be reviewed for clarity, privacy, household usability, and whether they preserve ledger/audit truth.

## Architecture decision gates

Owner approval is required for:

- Database or storage engine.
- Application framework.
- Local desktop versus browser UI.
- Any hosted component.
- Any external data service.
- AI integration pattern.
- Authentication or multi-user model.
- Backup and export strategy.
- Migration of old review/config data.

Codex should recommend options and tradeoffs for these decisions, then stop for approval.

## Routine decisions Codex can make without owner approval

Codex can proceed on routine decisions when they are free, local, reversible, conventional, and do not affect product architecture, privacy, cost, or data integrity.

Examples:

- Markdown document organization.
- `.gitignore` coverage for sensitive local artifacts.
- Naming planning files clearly.
- Using standard repo hygiene.
- Recommending common free/open-source tools for later review.
- Adding non-sensitive planning notes.

## Impactful decisions requiring owner approval

- Storage model: SQLite, DuckDB, files, or hybrid.
- UI framework or desktop app choice.
- Whether Streamlit is rejected, retained only as a prototype reference, or reconsidered.
- Whether CSV is only an import/export format or part of active state.
- Data directory layout and retention policy.
- Import automation and source connectors.
- Controlled review state model.
- AI data access policy.
- Backup/export system.
- Any dependency that has cost, vendor lock-in, network behavior, or long-term maintenance risk.

## Decisions required before app implementation

- First closed-loop scenario.
- Primary runtime environment.
- Local/hosted/privacy boundary.
- Storage model.
- UI direction and mockup approval path.
- Import sources for the first slice.
- Manual versus automated import expectations.
- Data validation requirements.
- Review decision model.
- Report readiness rules.
- AI role and access boundaries.
- Backup/export expectations.
- Which old concepts are migrated as requirements, config, or tests.

## First minimally viable closed-loop system must prove

The first implementation slice should prove the full operating loop at small scope:

```text
source data arrives
  -> ingestion
  -> validation
  -> normalization
  -> enrichment/classification
  -> review queue
  -> human decision
  -> controlled update
  -> reporting
  -> recommendation
  -> next action
  -> next data refresh
```

It does not need to support every account, vendor, report, or household view. It must prove that data can move through the loop without hidden mutation, double-counting, fake precision, or unreviewed decisions becoming facts.

## Recommended first planning conversation

Start by choosing the first closed-loop slice. Codex should present 2-3 options, recommend one, and ask for owner approval before architecture design.

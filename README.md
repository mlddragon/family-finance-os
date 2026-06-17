# Dillon Finances

This is the new product repository for Dillon Finances, a family financial operating system.

The current repository phase is product planning and foundation setup only. App implementation has not started.

## Source Of Truth

- The primary product source of truth is [docs/product_requirements.md](docs/product_requirements.md).
- Planning notes for the migration from the prior prototype live in [planning/](planning/).
- Repository data-handling rules live in [docs/data_handling_policy.md](docs/data_handling_policy.md).
- Security expectations live in [SECURITY.md](SECURITY.md).

## Current Scope

This repo currently contains:

- The updated PRD migrated from the prior research/prototype repo.
- Planning documents for prior-work audit, clarifying questions, initial planning gates, and setup summary.
- A financial-data-safe `.gitignore`.

This repo intentionally does not contain:

- Raw financial data.
- Normalized financial data.
- Generated reports.
- Credentials or secrets.
- The old Streamlit app.
- Old prototype scripts.
- Database schema or application code.

## Working Principle

The prior `Family_Finance_planner` repo is treated as product research and validated learning, not as the implementation foundation. Architecture, storage, UI, and runtime decisions require planning and owner review before application work begins.

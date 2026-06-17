# Data Handling Policy

## Purpose

This policy defines what belongs in the Dillon Finances repository during planning and future implementation.

## Allowed In Git

- Product requirements.
- Planning documents.
- Architecture decision records after owner approval.
- Source code after implementation begins.
- Empty templates and synthetic fixtures.
- Non-sensitive configuration examples.
- Tests using synthetic data only.

## Not Allowed In Git

- Raw financial exports.
- Normalized financial data.
- Generated financial reports.
- Real account snapshots.
- Real review decisions.
- Real receipts, statements, order exports, or PDFs.
- Credentials, tokens, cookies, browser profiles, or session state.
- AI transcripts containing transaction-level or item-level financial details unless explicitly approved and sanitized.

## Synthetic Test Data

Synthetic fixtures must be obviously fake. They should use:

- Fake merchants.
- Fake accounts.
- Fake dates and amounts.
- No real transaction descriptions.
- No real household names beyond approved project owner references in documentation.

## Data Directory Rule

If future tooling creates local data directories such as `raw/`, `normalized/`, `reports/`, `snapshots/`, `exports/`, or `imports/`, those directories remain untracked unless the owner explicitly approves a different plan.

## External Services

Any external service that may receive financial data is a data integrity, privacy, and security decision. It requires explicit owner review before implementation or use.

## AI Use

AI may help with product planning and implementation. AI access to financial data requires an explicit review gate and should prefer validated summaries over raw transaction detail.

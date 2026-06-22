# Security Policy

## Sensitive Data Boundary

This repository is for product code, documentation, planning, policy, and test fixtures that do not contain real household financial data.

Do not commit:

- Raw bank, credit-card, vendor, receipt, statement, or order exports.
- Normalized transaction data.
- Generated financial reports.
- Account numbers, full card numbers, credentials, tokens, cookies, browser sessions, or API keys.
- Screenshots or PDFs containing financial account details.
- Real household review-decision files unless explicitly approved through a migration plan.

## Local-First Default

Financial data should remain local by default. Any workflow that sends raw or transaction-level data to an external service requires explicit owner review before implementation or use.

Personal and QA/demo Docker instances must use separate external data roots. QA/demo mode must use synthetic data only, should run with visible QA environment identity, and must not expose controls that reset or switch personal data roots.

## Required Review Gates

Stop for explicit owner approval before:

- Adding a dependency that uploads, syncs, indexes, or transmits financial data.
- Adding hosted infrastructure.
- Adding AI access to transaction-level or item-level financial data.
- Changing `.gitignore` rules that protect financial artifacts.
- Migrating any data from the prior prototype repository.
- Storing credentials, tokens, browser sessions, or account identifiers.

## Reporting A Security Issue

Do not open a public GitHub issue for vulnerabilities, suspected secrets, leaked financial data, or deployment-specific exposure. Use GitHub private vulnerability reporting when it is enabled for the repository. If private vulnerability reporting is not available yet, contact the repository owner directly and share only the minimum detail needed to start triage.

A safe report should include:

- The affected branch, commit, file, endpoint, or workflow.
- Whether any token, account data, host, or financial artifact may be exposed.
- Reproduction steps using synthetic data whenever possible.
- No real secrets, raw financial exports, screenshots with account data, or exploit payloads beyond what is needed for confirmation.

## Reporting A Vulnerability Or Data Leak

If sensitive data is committed or exposed:

1. Stop all further pushes.
2. Identify the affected branch, commit, and files.
3. Notify the owner immediately.
4. Rotate any exposed credentials or tokens.
5. Remove the data using an approved history-rewrite plan.
6. Treat downstream clones, forks, and artifacts as potentially exposed until confirmed otherwise.

## GitHub Repository Expectations

- Repository visibility should remain private until an explicit public-release review is complete.
- Work should land through branches and pull requests.
- Main branch should be protected where account permissions allow.
- Pull requests should document whether raw, normalized, or generated financial artifacts were excluded.
- App behavior changes should include a human QA script with observable verification steps.
- Open-source preparation must not add real household data, credentials, account identifiers, or owner-specific runtime defaults.
- Repository workflows should use least-privilege GitHub token permissions and include sensitive-artifact and secret-pattern scans.
- Public release should enable secret scanning, push protection, Dependabot alerts, and protected `main` branch rules where available.

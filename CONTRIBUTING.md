# Contributing

Family Finance OS is being prepared for future open-source release. The repository is currently private, but contributions should already follow the same traceable, privacy-first workflow expected for a sensitive financial product.

## Ground Rules

- Do not commit real financial data, normalized financial data, generated reports, database files, credentials, account identifiers, screenshots with financial details, or exported household artifacts.
- Use synthetic fixtures only. Synthetic data must be obviously fake and marked with `SYNTHETIC`.
- Keep runtime defaults generic. Household names, app display names, actor labels, report titles, source requirements, and custom categories belong in install settings, not source code defaults.
- Do not add paid tooling, hosted infrastructure, telemetry, AI providers, or network data transfer without explicit owner approval.
- App, UI, API, Docker, and workflow behavior changes need a human QA script in the PR body.

## Development

Use branches and pull requests for meaningful work. Keep PRs focused, run the relevant tests, and document data-integrity, privacy, and security impact.

Useful checks:

```bash
python -m pytest -p no:cacheprovider
python scripts/check_sensitive_artifacts.py .
cd apps/web && npm test && npm run build
```

## Localization

The maintained locale is `en-US`. Translation contributions should add locale resources without changing stable API codes, database keys, category keys, or audit values. User-facing copy can be localized; operational identifiers should remain stable.

## Categories

System category keys are stable identifiers. Display labels and aliases may be edited per install. New household-specific categories should be custom categories and should not be added to the default system catalog unless they are broadly useful.

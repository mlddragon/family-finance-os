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

## Roles

- **Contributors / Cursor**: features, fixes, tests, docs, and Docker/CI changes via pull request.
- **Codex**: security analyst via manual `@codex review` on PRs (ChatGPT subscription quota; see [docs/runbooks/codex-subscription-setup.md](docs/runbooks/codex-subscription-setup.md)).
- **Maintainers**: merge after CI, Security workflow, and human review.

## Contribution Licensing

By submitting a contribution, you represent that you have the right to license it to this project. Unless a file explicitly says otherwise, contributions to code, tests, documentation, examples, templates, and configuration are licensed under the same license as the repository: `MPL-2.0`.

Do not submit third-party material unless its license is compatible with `MPL-2.0` and the source, copyright notice, and license obligations are clearly documented in the contribution.

Useful checks:

```bash
python -m pytest -p no:cacheprovider
python scripts/check_sensitive_artifacts.py .
python scripts/check_secret_patterns.py .
python scripts/check_v1_security_contract.py .
cd apps/web && npm test && npm run build
```

## Localization

The maintained locale is `en-US`. Translation contributions should add locale resources without changing stable API codes, database keys, category keys, or audit values. User-facing copy can be localized; operational identifiers should remain stable.

## Categories

System category keys are stable identifiers. Display labels and aliases may be edited per install. New household-specific categories should be custom categories and should not be added to the default system catalog unless they are broadly useful.

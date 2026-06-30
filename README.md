# Family Finance OS

This repository contains **Family Finance OS**, a local-first family financial operating system. The public GitHub home is [`mlddragon/family-finance-os`](https://github.com/mlddragon/family-finance-os) after rehome; runtime defaults stay generic so other households can install and adapt the product.

The landed v1 build is treated as `0.1.0`. The `0.2.0` line prepares the product for future open-source release by using MPL-2.0 licensing, localization scaffolding, generic install defaults, configurable install-specific text, and a stable category catalog.

The `0.3.0` line adds reviewability, QA/demo, and audit foundations: side-by-side personal/QA Docker operation, visible runtime identity, synthetic QA seed/reset scripts, AI-agent repo guidance, and the first local actor context slice.

The `0.4.0` line rehomes the product to `family-finance-os`, renames runtime env vars to `FFOS_*`, and prepares public release while keeping legacy `DILLON_FINANCES_*` Compose fallbacks for one release.

The app runs as a local Docker Compose app, serves the personal browser UI at `127.0.0.1:28080` by default, serves QA synthetic demo mode at `127.0.0.1:28081`, stores operational state in SQLite under an external `DATA_ROOT`, and keeps raw/source evidence and generated artifacts out of git.

## License

Family Finance OS is licensed under `MPL-2.0`. See [LICENSE](LICENSE). Copyright notice: [NOTICE](NOTICE).

## Source Of Truth

- The primary product source of truth is [docs/product_requirements.md](docs/product_requirements.md).
- Planning notes for the migration from the prior prototype live in [planning/](planning/).
- Repository data-handling rules live in [docs/data_handling_policy.md](docs/data_handling_policy.md).
- Security expectations live in [SECURITY.md](SECURITY.md).
- Contribution expectations live in [CONTRIBUTING.md](CONTRIBUTING.md).
- AI-agent repository instructions live in [AGENTS.md](AGENTS.md) and [cursor.md](cursor.md).
- Codex security analyst guidance lives in [docs/security/codex-analyst.md](docs/security/codex-analyst.md).
- Codex subscription setup lives in [docs/runbooks/codex-subscription-setup.md](docs/runbooks/codex-subscription-setup.md).
- QA self-hosted auto-update setup lives in [docs/runbooks/qa-self-hosted-runner.md](docs/runbooks/qa-self-hosted-runner.md).
- Public release runbook lives in [docs/runbooks/public-release-v0.4.0.md](docs/runbooks/public-release-v0.4.0.md).
- Prior prototype archive notes live in [docs/archive/family_finance_planner.md](docs/archive/family_finance_planner.md).
- Release history lives in [CHANGELOG.md](CHANGELOG.md).

## Current Scope

This repo currently contains:

- The updated PRD migrated from the prior research/prototype repo.
- Planning documents for prior-work audit, architecture decisions, validation strategy, UI mockups, report examples, and implementation milestones.
- The v1 local Docker app and open-source readiness groundwork.
- A financial-data-safe `.gitignore`.

This repo intentionally does not contain:

- Raw financial data.
- Normalized financial data.
- Generated reports.
- Credentials or secrets.
- The old Streamlit app.
- Old prototype scripts.

## Local Docker Runbook

Personal default:

```bash
make personal-up
```

Open personal mode at:

```text
http://127.0.0.1:28080
```

QA synthetic demo default:

```bash
make qa-up
make qa-seed
```

Open QA mode at:

```text
http://127.0.0.1:28081
```

`make qa-reset CONFIRM="RESET QA DATA"` resets only the configured QA synthetic data root and refuses personal environment identity.

For a guaranteed clean QA baseline, run `make qa-reset CONFIRM="RESET QA DATA"` before `make qa-seed`.

### Manual import CSV pack (no seed)

For import and approval testing without `qa-seed`, use the synthetic CSV pack under [tests/fixtures/synthetic/imports/](tests/fixtures/synthetic/imports/). Regenerate fresh transaction dates with:

```bash
make generate-synthetic-imports
```

See that directory's README for file list, row counts, and suggested manual import order (~48 ledger transactions across four sources, plus net worth and receipt CSVs).

Named QA scenarios are script-level only. The browser does not include reset or reseed controls in v0.4.0. Scenarios are not additive; reset QA before seeding a different scenario.

```bash
make qa-reset CONFIRM="RESET QA DATA"
make qa-seed QA_SCENARIO=baseline

make qa-reset CONFIRM="RESET QA DATA"
make qa-seed QA_SCENARIO=stale-source

make qa-reset CONFIRM="RESET QA DATA"
make qa-seed QA_SCENARIO=blocked-import

make qa-reset CONFIRM="RESET QA DATA"
make qa-seed QA_SCENARIO=review-backlog

make qa-reset CONFIRM="RESET QA DATA"
make qa-seed QA_SCENARIO=monthly-close-ready
```

Scenario summaries:

| Scenario | Expected QA state |
| --- | --- |
| `baseline` | Accepted synthetic source files, a partial review set, reports, draft close, advisor export, and remaining review work. |
| `stale-source` | Required sources are enabled; Chase imports as stale; final close is blocked by stale required source coverage. |
| `blocked-import` | A bad synthetic upload creates an open blocking validation finding and a quarantined file. |
| `review-backlog` | Valid imports are accepted but transactions remain intentionally unreviewed for Ledger Review testing. |
| `monthly-close-ready` | Required sources are accepted, transactions are reviewed, reports run, final close succeeds, and advisor export exists. |

Each seed writes a manifest under `DATA_ROOT/manifests/` with the scenario name, expected operator state, validation summary, review counts, and synthetic marker. Generated QA manifests, reports, databases, exports, close bundles, logs, and raw files stay outside git.

Direct Compose remains supported. The default host port is `28080`, and it can be overridden with `FFOS_HOST_PORT` (legacy: `DILLON_FINANCES_HOST_PORT`).

Stop the app:

```bash
make personal-down
make qa-down
```

Reset local runtime state only after confirming the selected `DATA_ROOT` does not contain needed evidence:

```bash
docker compose down
rm -rf "$FFOS_DATA_ROOT"
mkdir -p "$FFOS_DATA_ROOT"
```

Legacy env vars `DILLON_FINANCES_DATA_ROOT` and `DILLON_FINANCES_HOST_PORT` still work in Compose for one release. See [docs/migration/v0.4.0-rehome.md](docs/migration/v0.4.0-rehome.md).

## DATA_ROOT Layout

The app stores runtime state under `DATA_ROOT`, mounted into the container as `/data`:

- `inbox/` for files waiting to be scanned.
- `raw/` for accepted preserved source files.
- `processed/` for future controlled processed artifacts.
- `quarantine/` for blocked files and reason metadata.
- `database/` for `family_finance_os.sqlite3`.
- `reports/` for generated report artifacts.
- `monthly_close/` for monthly close bundles and manifests.
- `exports/` for advisor/export bundles.
- `logs/` for local operational logs.
- `manifests/` for QA scenario manifests and runtime manifests.

`DATA_ROOT` must stay outside the git repository. The app refuses unsafe in-repo data roots.

## Deployment Safety

Family Finance OS is local-first by default. Do not bind the app to `0.0.0.0`, expose it through a tunnel, publish it on the public internet, or attach hosted infrastructure unless you have explicitly reviewed authentication, TLS, backups, data retention, logs, and secret handling for that deployment.

Keep `DATA_ROOT` outside the git repository and outside cloud-synced folders unless that storage location has been reviewed for financial-data safety.

## Backup And Export

Use this section as the backup and export reference for v1 operations.

Back up the full `DATA_ROOT` folder when preserving household finance evidence. The most important paths are `database/`, `raw/`, `reports/`, `monthly_close/`, and `exports/`.

Generated advisor exports are written under `DATA_ROOT/exports/`. Monthly close bundles are written under `DATA_ROOT/monthly_close/` and include `manifest.json`.

## Troubleshooting

Use this troubleshooting checklist before changing code or moving data.

- If the browser does not load, confirm Docker is running and the app is bound to `127.0.0.1:28080` for personal mode or `127.0.0.1:28081` for QA mode.
- If imports do not appear, confirm files are in `DATA_ROOT/inbox/` and have supported v1 CSV headers.
- If final close is blocked, review Validation Issues for required-source coverage, stale sources, unconfirmed source profiles, or blocking validation findings.
- If Docker cannot write runtime files, confirm the host `FFOS_DATA_ROOT` exists and is writable.
- If sensitive-artifact or secret-pattern checks fail, remove raw financial data, generated reports, database files, credentials, tokens, or deployment-local values from the repo and keep runtime artifacts only under `DATA_ROOT`.

## Working Principle

The prior `Family_Finance_planner` repo is treated as product research and validated learning, not as the implementation foundation. Architecture, storage, UI, and runtime decisions require planning and owner review before product-shaping changes.

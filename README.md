# Family Finance OS

This repository contains Family Finance OS, a local-first family financial operating system. The GitHub repository is currently named `Dillon_Finances`, but runtime defaults are intentionally generic so other households can install and adapt the product.

The landed v1 build is treated as `0.1.0`. The `0.2.0` line prepares the product for future open-source release by adding AGPL licensing, localization scaffolding, generic install defaults, configurable install-specific text, and a stable category catalog.

The `0.3.0` line adds reviewability, QA/demo, and audit foundations: side-by-side personal/QA Docker operation, visible runtime identity, synthetic QA seed/reset scripts, AI-agent repo guidance, and the first local actor context slice.

The app runs as a local Docker Compose app, serves the personal browser UI at `127.0.0.1:28080` by default, serves QA synthetic demo mode at `127.0.0.1:28081`, stores operational state in SQLite under an external `DATA_ROOT`, and keeps raw/source evidence and generated artifacts out of git.

## License

Family Finance OS is licensed under `AGPL-3.0-only`. See [LICENSE](LICENSE). Copyright notice: [NOTICE](NOTICE).

## Source Of Truth

- The primary product source of truth is [docs/product_requirements.md](docs/product_requirements.md).
- Planning notes for the migration from the prior prototype live in [planning/](planning/).
- Repository data-handling rules live in [docs/data_handling_policy.md](docs/data_handling_policy.md).
- Security expectations live in [SECURITY.md](SECURITY.md).
- Contribution expectations live in [CONTRIBUTING.md](CONTRIBUTING.md).
- AI-agent repository instructions live in [AGENTS.md](AGENTS.md).
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

Named QA scenarios are script-level only. The browser does not include reset or reseed controls in v0.4.0.

```bash
make qa-reset CONFIRM="RESET QA DATA"
make qa-seed QA_SCENARIO=baseline
make qa-seed QA_SCENARIO=stale-source
make qa-seed QA_SCENARIO=blocked-import
make qa-seed QA_SCENARIO=review-backlog
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

Direct Compose remains supported. The default host port is `28080`, and it can be overridden with `DILLON_FINANCES_HOST_PORT`.

Stop the app:

```bash
make personal-down
make qa-down
```

Reset local runtime state only after confirming the selected `DATA_ROOT` does not contain needed evidence:

```bash
docker compose down
rm -rf "$DILLON_FINANCES_DATA_ROOT"
mkdir -p "$DILLON_FINANCES_DATA_ROOT"
```

## DATA_ROOT Layout

The app stores runtime state under `DATA_ROOT`, mounted into the container as `/data`:

- `inbox/` for files waiting to be scanned.
- `raw/` for accepted preserved source files.
- `processed/` for future controlled processed artifacts.
- `quarantine/` for blocked files and reason metadata.
- `database/` for `dillon_finances.sqlite3`.
- `reports/` for generated report artifacts.
- `monthly_close/` for monthly close bundles and manifests.
- `exports/` for advisor/export bundles.
- `logs/` for local operational logs.
- `manifests/` for QA scenario manifests and runtime manifests.

`DATA_ROOT` must stay outside the git repository. The app refuses unsafe in-repo data roots.

## Backup And Export

Use this section as the backup and export reference for v1 operations.

Back up the full `DATA_ROOT` folder when preserving household finance evidence. The most important paths are `database/`, `raw/`, `reports/`, `monthly_close/`, and `exports/`.

Generated advisor exports are written under `DATA_ROOT/exports/`. Monthly close bundles are written under `DATA_ROOT/monthly_close/` and include `manifest.json`.

## Troubleshooting

Use this troubleshooting checklist before changing code or moving data.

- If the browser does not load, confirm Docker is running and the app is bound to `127.0.0.1:28080` for personal mode or `127.0.0.1:28081` for QA mode.
- If imports do not appear, confirm files are in `DATA_ROOT/inbox/` and have supported v1 CSV headers.
- If final close is blocked, review Validation Issues for required-source coverage, stale sources, unconfirmed source profiles, or blocking validation findings.
- If Docker cannot write runtime files, confirm the host `DILLON_FINANCES_DATA_ROOT` exists and is writable.
- If sensitive-artifact checks fail, remove raw financial data, generated reports, database files, or credentials from the repo and keep them only under `DATA_ROOT`.

## Working Principle

The prior `Family_Finance_planner` repo is treated as product research and validated learning, not as the implementation foundation. Architecture, storage, UI, and runtime decisions require planning and owner review before product-shaping changes.

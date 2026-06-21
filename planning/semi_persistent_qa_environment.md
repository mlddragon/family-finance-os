# Semi-Persistent QA Environment

This document captures the approved planning direction for a semi-persistent QA and demo environment for Dillon Finances. It is a planning artifact only. It does not create app code, Docker configuration, scripts, seed data, database schema, generated reports, runtime data roots, credentials, or financial data artifacts.

## Status

- Approved owner direction was captured in chat on 2026-06-21.
- v0.3.0 implements the first foundation: personal/QA runtime identity, side-by-side Docker commands, script-level QA reset/seed, one `baseline` scenario, QA UI markers, and synthetic artifact markers.
- Additional named scenarios remain deferred.
- No QA data root is committed by this document.
- No personal data root should be changed by this document.
- This document should guide the later implementation plan and pull request scope.

## Recommendation

Strong recommendation: run personal and QA as two side-by-side Docker Compose projects with separate ports, separate mounted data roots, and explicit runtime identity. The app should treat the mounted `DATA_ROOT` as a startup-time attachment, not as a browser-switchable data store.

This preserves the local-first privacy model while creating a repeatable, contributor-friendly QA environment. The same packaged Docker app should run in both environments. Code updates should reach each environment through image rebuilds and container recreation. Persistent state should survive rebuilds because it lives in external mounted data roots.

Serious alternatives considered:

- One container with a hidden UI data-store switcher: convenient, but too risky for a financial app because it makes personal and QA data roots easy to confuse.
- Disposable QA data only: clean for CI, but weak for demos and review because it cannot accumulate realistic synthetic history.
- Committed QA database snapshot: fast to load, but poor for migration review, repository hygiene, and privacy habits.
- Source bind mounts for QA updates: useful for active development, but weaker for QA because it is not testing the packaged Docker app.

## Approved Environment Model

The default local environments are:

```text
Personal instance
  Compose project: dillon-personal
  Host URL: http://127.0.0.1:28080
  Data root: owner real-data DATA_ROOT outside git
  Dataset kind: personal
  Dev mode controls: disabled

QA instance
  Compose project: dillon-qa
  Host URL: http://127.0.0.1:28081
  Data root: synthetic QA DATA_ROOT outside git
  Dataset kind: synthetic
  Dev mode controls: enabled only when APP_ENV=qa and DEV_MODE=true
```

Both environments should use the same Dockerfile and app image build path. They should differ by Compose project name, host port, mounted data root, and runtime identity settings.

## Data Roots

Personal and QA data roots must be separate host directories. Both remain outside the git repository.

Recommended defaults:

```text
~/Dillon_Finances_Data
~/Dillon_Finances_QA_Data
```

The app should continue enforcing the existing data-root safety rules:

- `DATA_ROOT` must not be the repo root.
- `DATA_ROOT` must not be inside the repo.
- Required child directories must be safe directories.
- Runtime databases, raw files, reports, monthly close bundles, exports, logs, and quarantine artifacts must stay under the selected `DATA_ROOT`.

QA data is semi-persistent. It may retain generated SQLite state, accepted synthetic raw files, reports, close bundles, exports, logs, and scenario manifests across Docker rebuilds. It should still have explicit reset and reseed workflows.

## QA Data Source Of Truth

Committed synthetic fixtures, seed scripts, and scenario definitions are the source of truth for QA data. Generated QA state is not source of truth and must remain outside git.

Allowed in git:

- Synthetic fixtures with obviously fake transactions.
- Header-only source examples.
- Scenario definitions.
- Seed/reset scripts.
- Documentation and manifests that do not contain generated financial state.

Not allowed in git:

- QA SQLite database files.
- Generated QA reports.
- QA monthly close bundles.
- QA exports.
- Runtime logs from a QA run.
- Real financial data or credentials.

## Named QA Scenarios

QA data should grow through named scenarios rather than arbitrary manual uploads. Named scenarios make demos repeatable and keep semi-persistent state understandable.

Initial scenario names should include:

- `baseline`: the smallest useful closed-loop dataset.
- `stale-source`: data that demonstrates stale or missing source warnings.
- `blocked-import`: a source file with blocking validation findings.
- `review-backlog`: unreviewed transactions and review-needed work.
- `monthly-close-ready`: a dataset ready for draft/final monthly close flows.

Scenario runs should write a manifest under QA `DATA_ROOT` describing:

- scenario name
- scenario version
- run timestamp
- seed script version or app version
- source fixtures loaded
- expected top-level outcomes
- whether the scenario was additive or reset-based

## Runtime Identity

The app should expose environment identity through API status/settings payloads and UI presentation.

Recommended runtime fields:

- `APP_ENV`: stable machine value such as `personal` or `qa`.
- `APP_ENV_LABEL`: display value such as `Personal data` or `QA synthetic demo`.
- `DATASET_KIND`: `personal` or `synthetic`.
- `DEV_MODE`: boolean flag for development controls.

The UI should show environment identity persistently. The QA instance should have stronger visual treatment than the personal instance:

- persistent red banner across the top of all screens
- header badge
- Settings environment panel
- synthetic/demo markers in generated reports and exports

Exact layout, copy, and visual styling can be decided during implementation and adjusted during QA.

## Dev Mode Boundary

Dev mode controls are QA-only.

Approved default:

- Dev mode requires both `APP_ENV=qa` and `DEV_MODE=true`.
- Personal instance must not show destructive QA controls, even if `DEV_MODE=true` is accidentally set.
- QA-only controls may include seed QA data, reset QA data, load scenario, and show dataset details.
- Personal-data reset remains a documented manual operation only.

The browser UI should not provide a general-purpose data-root switcher.

## Reset And Destructive Operations

Destructive operations should be script-driven first. Any future QA UI reset must remain behind QA environment identity, dev mode, and typed confirmation.

Approved default:

- `qa-reset` may delete and recreate only the configured QA data root.
- Reset requires exact typed confirmation, such as the QA data-root path or `RESET QA DATA`.
- Reset refuses to run unless the environment identity is QA/synthetic.
- Personal data reset is never exposed as a routine UI control.
- CI continues to use disposable temporary data roots and cleans them up after each run.

## Repo Updates Into Docker

Code updates should remain image-based for personal and QA.

Approved default:

- Rebuild personal from the repo, then recreate the `dillon-personal` container.
- Rebuild QA from the repo, then recreate the `dillon-qa` container.
- External data roots survive rebuilds.
- Local hot reload can be added later as a separate developer-only workflow.

This makes QA representative of the packaged local app rather than a special source-mounted developer runtime.

## Contributor Setup

Contributor onboarding should be QA-first.

Recommended commands should eventually include:

- `make qa-up`: start QA at `127.0.0.1:28081`.
- `make qa-seed`: load or refresh the baseline QA scenario.
- `make qa-reset`: reset only the QA data root after confirmation.
- `make personal-up`: start personal operation at `127.0.0.1:28080`.

README contributor setup should lead with QA/demo usage. Personal-data operation should be documented separately and clearly labeled as owner/local use.

## Implementation Scope For Later Plan

A later implementation plan should cover:

1. Docker/Compose environment examples for personal and QA.
2. Runtime identity environment variables and status payload fields.
3. UI environment banner and badge.
4. QA-only dev mode gates.
5. Seed/reset command design.
6. Named scenario manifest format.
7. Synthetic fixture expansion.
8. Report/export synthetic markers.
9. README contributor runbook updates.
10. Tests for environment identity, reset guards, and QA visual markers.

## Stop Conditions

Stop before implementation if any plan requires:

- committing runtime QA databases or generated artifacts
- storing real financial data in git
- exposing a UI control that can switch to personal data roots
- exposing personal reset in the browser
- requiring cloud services for local QA
- weakening existing data-root safety checks
- changing personal data root defaults without owner approval

## Relationship To Other Documents

This document records the architecture and owner decisions. The product-level feature requirements live in `docs/qa_feature_requirements.md`. The primary PRD remains `docs/product_requirements.md` and should contain only a stub section pointing to the QA FRD.

# QA And Demo Environment FRD

This Feature Requirements Document defines the QA and demo environment feature for Family Financial Advisor. It is a single additive feature under the broader product described in `docs/product_requirements.md`. It does not replace the PRD. It extends the PRD by defining how the product should support safe, semi-persistent synthetic QA and demo workflows alongside personal local operation.

This document is feature-specific. It should guide future planning and implementation work for QA environments, contributor onboarding, synthetic demo data, and environment identity. It does not create app code, Docker configuration, seed data, runtime data roots, generated artifacts, schema, dependencies, credentials, or financial data.

## 1. Feature Name

Semi-Persistent QA And Demo Environment

## 2. Feature North Star

Provide a safe, repeatable, local-first QA and demo environment that lets Mason and future contributors run the app with synthetic data, exercise realistic workflows, and review product behavior without risking personal financial data or requiring hosted infrastructure.

The QA environment should feel like the real product, not a toy mode. It should use the same Dockerized app build, the same SQLite-backed runtime model, the same import/review/report workflows, and the same data-root safety rules as the personal instance. Its data should be obviously synthetic, clearly labeled, and easy to reset or reseed.

## 3. Feature Mission

The QA feature exists to help the project answer:

1. Can a contributor run the product safely without real financial data?
2. Can Mason review new behavior against stable synthetic scenarios?
3. Can demos show realistic product flows without exposing private data?
4. Can QA state persist long enough to accumulate useful history?
5. Can QA state be reset to a known baseline when it becomes messy?
6. Can the app make it visually impossible to confuse QA synthetic data with personal data?
7. Can code updates be tested against the packaged Docker app rather than a special development runtime?
8. Can generated QA reports and exports carry synthetic/demo markers?
9. Can future scenario additions remain versioned, reviewable, and safe for git?

---

# 4. Guiding Principles

## 4.1 Personal data safety over convenience

The QA feature must not create shortcuts that make personal data easier to corrupt, erase, or expose.

Rules:

- No browser control should switch between personal and QA data roots.
- Personal reset should not be exposed as a routine UI action.
- QA destructive actions must be guarded by environment identity and explicit confirmation.
- Real financial data must not be needed to run QA, demo, tests, or contributor onboarding.

## 4.2 Same app, different environment

QA should run the same packaged app as personal operation.

The QA instance should differ through runtime configuration:

- Compose project name.
- Host port.
- Mounted data root.
- Environment identity.
- Dev mode flag.
- Dataset kind.

It should not rely on source bind mounts or code paths that are unavailable to the normal Docker app.

## 4.3 Synthetic data must be obvious

QA data should be unmistakably synthetic in the UI, generated reports, exports, manifests, and documentation.

Synthetic data should use fake merchants, fake accounts, fake amounts, fake descriptions, and fake dates. Scenario names and seed manifests should identify loaded data as synthetic.

## 4.4 Semi-persistent, not permanent

QA data should persist across app rebuilds so demos and reviews can build useful history. It should not be treated as permanent truth.

The project needs both:

- a stable QA data root that can accumulate synthetic history
- explicit reset/reseed commands that can return QA to a known baseline

## 4.5 Contributor-first onboarding

Future contributors should be able to start with QA mode before thinking about personal data.

The safe default path should be:

1. Clone repo.
2. Start QA instance.
3. Seed synthetic data.
4. Open the app at the QA port.
5. Run tests or review scenarios.

Personal operation should be documented separately for owner/local use.

## 4.6 Environment identity everywhere

The app should make the active environment visible wherever decisions are made.

QA should receive stronger treatment than personal mode because the risk of confusion is high. A persistent red banner across all QA screens is the initial approved default. Exact styling can be adjusted during QA.

---

# 5. Relationship To The Main PRD

The main PRD defines the product mission, local-first architecture, data integrity rules, review workflow, reporting, and long-term family financial operating model. This FRD defines one supporting feature: a semi-persistent QA and demo environment for safely testing and demonstrating that product.

This FRD is additive to `docs/product_requirements.md`:

- It does not change the core financial product mission.
- It does not change ledger integrity or source-of-truth rules.
- It does not loosen local-first privacy requirements.
- It does not authorize real financial data in git.
- It does not replace the synthetic-data-first test strategy.
- It adds environment identity, QA runtime behavior, QA data lifecycle, contributor setup, and demo-scenario requirements.

If there is a conflict, the stricter data-safety rule should win unless the owner explicitly approves a documented change.

---

# 6. Feature Users

## 6.1 Mason as owner/operator

Needs:

- run personal data on a stable local port
- run QA synthetic data beside personal data
- test changes before using them with personal data
- demo or review product behavior without exposing private information
- reset QA when synthetic state becomes confusing
- trust that personal data cannot be reset through QA controls

## 6.2 Future contributors

Need:

- a safe default setup that does not require real financial data
- documented commands for starting QA
- synthetic scenarios that exercise meaningful behavior
- visible environment labeling
- confidence that tests and demos use generated synthetic state

## 6.3 Reviewers and demo viewers

Need:

- understand that displayed data is synthetic
- see realistic workflows and reports
- avoid mistaking QA results for Mason's personal financial state
- inspect scenario context and data freshness at a high level

## 6.4 Codex and automation agents

Need:

- deterministic commands for starting, seeding, resetting, and validating QA
- clear write boundaries
- stop conditions for real data, generated artifacts, and destructive operations
- environment fields in API payloads to verify active mode

---

# 7. Environment Model

The product should support two default local Docker environments.

## 7.1 Personal environment

Default identity:

- Compose project: `dillon-personal`
- Host URL: `http://127.0.0.1:28080`
- Dataset kind: `personal`
- Environment label: `Personal data`
- Dev mode controls: disabled

Personal data lives under an owner-selected `DATA_ROOT` outside git. The personal instance is for real household operation and should not expose QA reset or seed controls.

## 7.2 QA environment

Default identity:

- Compose project: `dillon-qa`
- Host URL: `http://127.0.0.1:28081`
- Dataset kind: `synthetic`
- Environment label: `QA synthetic demo`
- Dev mode controls: allowed only with `APP_ENV=qa` and `DEV_MODE=true`

QA data lives under a synthetic `DATA_ROOT` outside git. The QA instance is for testing, demo, contributor onboarding, and synthetic scenario review.

## 7.3 Runtime fields

The app should expose environment identity through status/settings APIs.

Required fields:

- `APP_ENV`
- `APP_ENV_LABEL`
- `DATASET_KIND`
- `DEV_MODE`
- active data-root path
- data-root existence
- local-only status
- database status

Implementation may choose exact JSON field names, but they should be stable enough for UI display, tests, and automation.

---

# 8. QA Data Lifecycle

## 8.1 Source of truth

Committed synthetic fixtures, seed scripts, and scenario definitions are the source of truth.

Generated QA runtime state is not source of truth. It should remain under QA `DATA_ROOT` and outside git.

## 8.2 Semi-persistent state

QA state should survive Docker rebuilds. The mounted QA `DATA_ROOT` may contain:

- SQLite database
- accepted synthetic raw files
- processed artifacts
- quarantine examples
- generated reports
- monthly close bundles
- advisor exports
- logs
- scenario manifests

## 8.3 Reset and reseed

The project should provide explicit reset and seed workflows.

Reset requirements:

- reset only the configured QA data root
- require exact typed confirmation
- refuse to run unless the target is QA/synthetic
- recreate the required data-root folders
- avoid touching personal data roots

Seed requirements:

- load synthetic fixtures
- support named scenarios
- write scenario manifests
- be repeatable where practical
- explain expected outcomes

---

# 9. Named QA Scenarios

QA should grow through named scenarios, not random manual uploads.

Initial scenarios:

- `baseline`: proves the smallest useful closed loop.
- `stale-source`: shows stale or missing required source behavior.
- `blocked-import`: shows blocking validation and quarantine behavior.
- `review-backlog`: shows unreviewed transaction work.
- `monthly-close-ready`: shows report, draft close, final close, and export readiness.

Each scenario should define:

- purpose
- fixture inputs
- expected import state
- expected validation state
- expected review state
- expected report or close behavior
- whether it is additive or requires a reset

Scenario manifests should be written under QA `DATA_ROOT` and should not be committed after generation.

v0.4.0 implementation note:

- named scenarios are available through `make qa-seed QA_SCENARIO=<scenario-name>`
- reset remains script-level only through `make qa-reset CONFIRM="RESET QA DATA"`
- browser reset, reseed, and scenario-picker controls remain deferred

Expected command sequence for one scenario:

```bash
make qa-reset CONFIRM="RESET QA DATA"
make qa-seed QA_SCENARIO=monthly-close-ready
make qa-up
```

Scenario manifests are written to `DATA_ROOT/manifests/` and include the scenario name, expected operator state, validation/review summaries, generated artifact counts where applicable, and the synthetic marker.

---

# 10. UI Requirements

## 10.1 Persistent environment markers

The UI should show environment identity on every screen.

QA should include:

- persistent red banner across the top of all screens
- header badge
- clear `QA synthetic demo` wording
- Settings environment panel
- dataset kind and data-root path
- dev mode status when active

Personal mode should include a quieter but visible environment badge and should not show the red QA banner.

## 10.2 QA-only dev controls

QA dev controls may include:

- seed QA data
- reset QA data
- load named scenario
- view scenario manifest
- view dataset details

These controls must not appear unless the runtime identity is QA and dev mode is enabled.

## 10.3 Generated artifact markers

Reports, monthly close bundles, and advisor exports generated from QA should include synthetic/demo markers.

The marker should make clear:

- the artifact came from QA
- data is synthetic
- artifact should not be used for real financial decisions

---

# 11. Docker And Update Requirements

The personal and QA environments should use image-based updates.

Recommended operations:

- personal update rebuilds and recreates `dillon-personal`
- QA update rebuilds and recreates `dillon-qa`
- both use the same Dockerfile and build context
- external data roots survive rebuilds

Local hot reload can be introduced later as a separate developer workflow. It should not be the default QA or demo environment.

---

# 12. Functional Requirements

## 12.1 Start personal environment

The owner can start the personal instance on `127.0.0.1:28080` with an external personal `DATA_ROOT`.

The app must display personal environment identity and must not expose QA seed/reset controls.

## 12.2 Start QA environment

The owner or contributor can start the QA instance on `127.0.0.1:28081` with an external synthetic QA `DATA_ROOT`.

The app must display QA identity and persistent synthetic markers.

## 12.3 Seed QA data

The owner or contributor can seed QA with named synthetic scenarios.

The seed workflow should load synthetic fixtures, exercise app workflows where needed, and write a manifest describing the loaded scenario.

## 12.4 Reset QA data

The owner or contributor can reset QA to a known baseline through a guarded script first.

Any future UI reset must require QA environment identity, dev mode, and typed confirmation.

## 12.5 Show environment details

The app should show:

- environment label
- dataset kind
- active data root
- database status
- local-only status
- dev mode status
- latest loaded QA scenario when available

## 12.6 Protect personal data

The feature must prevent routine UI access to destructive personal-data operations.

Personal data should remain controlled by explicit owner-run Docker and filesystem operations.

## 12.7 Support contributor onboarding

Documentation should provide a QA-first path for contributors.

The contributor path should not require real data, secrets, bank connections, hosted services, or personal data roots.

---

# 13. Non-Functional Requirements

## 13.1 Safety

The QA feature must not weaken existing data-root safety checks.

## 13.2 Privacy

QA must not require or expose real financial data.

## 13.3 Repeatability

Named scenarios should be repeatable. Reset should restore a known baseline.

## 13.4 Representativeness

QA should run the same packaged Docker app used by personal operation.

## 13.5 Auditability

Scenario runs should leave a manifest that explains what synthetic data was loaded and why.

## 13.6 Clarity

The UI and generated artifacts should make QA synthetic status obvious.

## 13.7 Contributor usability

QA setup should be simple enough for future contributors to run without project-specific private knowledge.

---

# 14. Success Metrics

## 14.1 Environment safety metrics

- Personal and QA can run side by side on ports `28080` and `28081`.
- QA reset cannot target the personal data root.
- Personal UI does not show QA destructive controls.
- QA UI displays persistent synthetic markers.

## 14.2 QA workflow metrics

- Baseline QA seed creates a usable closed-loop dataset.
- Named scenarios load with predictable outcomes.
- Reset and reseed return QA to a known state.
- Scenario manifests identify loaded fixtures and expected behavior.

## 14.3 Contributor metrics

- A contributor can start QA without real financial data.
- README setup starts with QA/demo usage.
- CI remains synthetic-only and disposable.

---

# 15. Major Risks

## 15.1 Confusing QA with personal data

Risk: a user reviews or exports QA data as though it were real.

Mitigation: persistent red QA banner, header badge, Settings environment panel, and artifact markers.

## 15.2 Destructive operation hits personal data

Risk: reset or reseed deletes or mutates personal data.

Mitigation: QA-only reset scripts, exact typed confirmation, environment identity checks, and no personal reset UI.

## 15.3 QA state becomes incomprehensible

Risk: semi-persistent QA accumulates random manual changes and loses demo value.

Mitigation: named scenarios, manifests, and reset-to-baseline workflow.

## 15.4 QA diverges from packaged app behavior

Risk: QA uses bind-mounted source or special dev paths that do not represent the real Docker app.

Mitigation: image-based updates for QA and personal environments.

## 15.5 Synthetic fixtures become unsafe

Risk: real or sensitive data enters fixtures or generated artifacts are committed.

Mitigation: existing sensitive-artifact checks, synthetic-data policy, review discipline, and no committed runtime QA state.

---

# 16. Explicit Non-Goals

The QA feature must not:

- create hosted QA infrastructure
- require cloud databases
- require bank credentials
- store real financial data in git
- commit generated QA databases or reports
- expose a browser data-root switcher
- expose personal reset as a routine UI control
- replace CI disposable test runs
- replace owner-approved real-data smoke testing
- turn dev mode into a general admin mode for personal data

---

# 17. Implementation Philosophy

Build the QA feature in small validated slices:

1. Document environment model and commands.
2. Expose runtime identity in API status/settings.
3. Add visible environment markers.
4. Add QA-first docs.
5. Add seed/reset scripts.
6. Add named scenarios and manifests.
7. Add QA-only dev controls after backend guardrails exist.
8. Add report/export synthetic markers.

Each implementation slice should include:

- exact scope
- allowed files
- forbidden actions
- verification commands
- human QA script
- data-root safety checks
- rollback or reset notes

---

# 18. Final Feature Vision

The final QA feature lets anyone open the app in a clearly labeled synthetic mode, load realistic scenarios, test product behavior, generate demo reports, and reset safely without touching personal financial data.

It should make the project easier to contribute to, easier to review, and safer to evolve.

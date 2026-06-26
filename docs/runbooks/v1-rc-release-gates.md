# v1.0.0 RC Release Gates

Checklist for declaring a **v1.0.0 release candidate** on `mlddragon/family-finance-os`. This complements the completed [public-release-v0.4.0.md](public-release-v0.4.0.md) rehome runbook.

## Scope

v1.0.0 RC is the first formal product boundary after the v0.4.0 public foundation. It unlocks owner real-data smoke and stable release tagging decisions that were intentionally deferred during rehome.

Until RC is approved, **validate with synthetic QA only** — see [docs/qa_validation_strategy.md](../qa_validation_strategy.md).

## Pre-RC validation (synthetic QA path)

Use this path for every milestone PR and before tagging RC:

### 1. CI (every PR)

- Sensitive artifact scan
- v1 security contract checks
- Backend and web unit tests
- Browser smoke tests (synthetic)
- Docker image build and synthetic closed-loop E2E

### 2. Semi-persistent QA runtime

| Setting | Value |
| --- | --- |
| Compose project | `ffos-qa` |
| Host URL | `http://127.0.0.1:28081` |
| Data root | External synthetic `DATA_ROOT` outside git |
| Dataset kind | `synthetic` |

```bash
make qa-up
make qa-reset CONFIRM="RESET QA DATA"   # when switching scenarios
make qa-seed QA_SCENARIO=baseline       # or stale-source, blocked-import, review-backlog, monthly-close-ready
```

See [qa-self-hosted-runner.md](qa-self-hosted-runner.md) for self-hosted QA auto-update.

### 3. Human QA scripts

PRs that change app, UI, API, Docker, import, review, report, or data-integrity behavior must include a human QA script with scope, preconditions, steps, expected results, stop conditions, and known gaps.

### 4. Evidence boundaries

Sanitized evidence only in git and GitHub: counts, statuses, validation codes, pass/fail notes, scenario names.

Never commit or record: raw transaction rows, merchants, balances, account identifiers, filenames with private information, or `DATA_ROOT` artifacts.

## RC readiness checklist

Complete before tagging `v1.0.0-rc.N`:

- [x] RC foundation and 0.5.0 governance merged to `main` with green CI and Security workflows
- [x] Permission enforcement and B.1 permission preview complete per [planning/issue_55_view_as_decision_record.md](../../planning/issue_55_view_as_decision_record.md)
- [x] All five named QA seed scenarios pass on semi-persistent QA — see [planning/v1_synthetic_qa_record.md](../../planning/v1_synthetic_qa_record.md)
- [ ] Open P0/P1 security findings resolved or explicitly accepted by owner
- [ ] Tag protection enabled for `v*` ([#72](#tag-protection-and-github-releases-issue-72)) — **owner action in GitHub repo settings**
- [x] Codex subscription GitHub integration **waived for RC** ([#80](https://github.com/mlddragon/family-finance-os/issues/80)); manual `@codex review` only
- [x] Second maintainer posture reviewed ([#73](https://github.com/mlddragon/family-finance-os/issues/73)) — solo-maintainer admin bypass acceptable

## Tag protection and GitHub Releases (issue #72)

Tracked in [#72](https://github.com/mlddragon/family-finance-os/issues/72).

**Owner action before RC tag (recommended):**

1. GitHub → **Settings** → **Tags** → add rule for pattern `v*`
2. Enable: restrict deletions; restrict force-push; optionally require signed tags
3. Do not block tag creation for maintainers who will cut RC releases

**Decisions for v0.4.0 rehome (historical):**

- No tag protection on `v*` yet
- `v0.4.0` published as the public rehome boundary

**Decide before v1.0.0 RC tag:**

1. **Protect `v*` release tags?** Recommended once RC scope is stable to prevent accidental tag moves or deletion.
2. **Prerelease vs stable?** Use GitHub prerelease for `v1.0.0-rc.*` candidates; mark `v1.0.0` stable only after owner real-data smoke passes.
3. **Release notes hygiene** — confirm notes contain no real financial data, secrets, account IDs, hostnames, IPs, private endpoints, recovery keys, SSH keys, passphrases, or deployment-specific values.
4. **Release artifacts** — if any, must be generated from reviewed source with no local runtime data.

Example RC tag flow:

```bash
git checkout main
git pull origin main
git tag -a v1.0.0-rc.1 -m "v1.0.0 release candidate 1"
git push origin v1.0.0-rc.1
```

Create a GitHub Release from the tag; mark as **prerelease** until final `v1.0.0`.

## Owner real-data smoke (RC gate only)

**Do not run before v1.0.0 RC approval.**

After synthetic validation passes and an RC tag exists, owner may run [docs/owner_smoke_checklist_v1.md](../owner_smoke_checklist_v1.md) against personal `DATA_ROOT` at `http://127.0.0.1:28080`.

Trigger conditions:

- RC scope is feature-complete on `main`
- Synthetic QA and CI are green
- Owner explicitly approves real-data smoke for this RC cycle

Record only sanitized evidence (counts, statuses, validation codes, pass/fail). Raw exports, SQLite, reports, and close bundles stay under local `DATA_ROOT` only.

## Codex integration (issue #80)

Repo-side guidance is in [codex-subscription-setup.md](codex-subscription-setup.md). Owner must complete browser setup at [chatgpt.com/codex](https://chatgpt.com/codex) before `@codex review` works on PRs.

- Automatic reviews stay **OFF**
- No `OPENAI_API_KEY` repository secret
- Manual trigger only: comment `@codex review` on a PR

## Stop conditions

Stop RC tagging if:

- CI or Security workflow fails on the RC branch or `main`
- Gitleaks or sensitive-artifact scan finds credentials or raw financial data
- Synthetic QA scenarios fail on `ffos-qa`
- Owner has not approved real-data smoke but stable `v1.0.0` is being considered

## Related documents

- [docs/qa_validation_strategy.md](../qa_validation_strategy.md) — validation layers and deferred gates
- [docs/owner_smoke_checklist_v1.md](../owner_smoke_checklist_v1.md) — owner real-data smoke (RC only)
- [docs/runbooks/public-release-v0.4.0.md](public-release-v0.4.0.md) — completed v0.4.0 rehome steps
- [planning/v1_synthetic_qa_record.md](../../planning/v1_synthetic_qa_record.md) — synthetic scenario validation record
- [docs/runbooks/v1-owner-smoke-handoff.md](v1-owner-smoke-handoff.md) — post-RC owner smoke steps
- [planning/owner_decision_record.md](../../planning/owner_decision_record.md) — owner-approved planning constraints

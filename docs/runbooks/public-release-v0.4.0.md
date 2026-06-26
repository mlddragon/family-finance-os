# Public Release Runbook — v0.4.0

Owner-only checklist after the rehome PR stack merges to `main`.

## Status (2026-06-25)

**Completed on `mlddragon/family-finance-os`:**

- [x] Rehome PR stack merged; repository renamed to `family-finance-os`
- [x] Repository visibility set to **Public**
- [x] `v0.4.0` tag pushed and [GitHub Release](https://github.com/mlddragon/family-finance-os/releases/tag/v0.4.0) published
- [x] Issue #66 closed (repo protection and security settings gate)

**Remaining owner actions (tracked separately):**

| Item | Issue | Owner action |
| --- | --- | --- |
| Tag protection and first formal release boundary | [#72](https://github.com/mlddragon/family-finance-os/issues/72) | Decide `v*` tag protection and stable vs prerelease policy before **v1.0.0 RC**. See [v1-rc-release-gates.md](v1-rc-release-gates.md#tag-protection-and-github-releases-issue-72). |
| Codex subscription GitHub integration | [#80](https://github.com/mlddragon/family-finance-os/issues/80) | Complete browser setup in [codex-subscription-setup.md](codex-subscription-setup.md). Repo docs are ready; integration does not run until owner finishes ChatGPT/Codex settings. |

This runbook remains the historical record for the v0.4.0 public rehome. Use [v1-rc-release-gates.md](v1-rc-release-gates.md) for v1.0.0 RC planning.

## Preconditions

- [x] PRs #74–#77 merged
- [x] `main` CI and Security workflows green at rehome
- [x] Full-history Gitleaks scan clean
- [x] No real financial data or secrets in tracked files or history

## 1. Rename repository

**Done.** Repository is `mlddragon/family-finance-os`.

GitHub → Settings → General → Repository name:

```text
Dillon_Finances → family-finance-os
```

Update local remotes:

```bash
git remote set-url origin https://github.com/mlddragon/family-finance-os.git
```

## 2. Flip visibility to Public

**Done.**

GitHub → Settings → General → Danger zone → Change visibility → Public.

## 3. Enable security settings (issue #66)

**Done** (issue #66 closed).

- Private vulnerability reporting
- Secret scanning
- Secret scanning push protection
- Dependabot alerts (verify on)
- Dependabot security updates (verify on)

## 4. Branch protection on `main`

**Done** with solo-maintainer posture per [#73](https://github.com/mlddragon/family-finance-os/issues/73) (admin bypass allowed until a second real maintainer).

- Require pull requests before merging
- Require status checks: `CI`, all `Security` jobs
- Require branches up to date
- Require 1 approving review (allow admin bypass while solo maintainer per #73)
- Dismiss stale approvals
- Require conversation resolution
- Block force pushes and branch deletion

## 5. Archive prototype repository

On `mlddragon/Family_Finance_planner`:

1. Merge or commit archive README from `docs/archive/family_finance_planner_README.md`.
2. Set description: `Archived prototype. See mlddragon/family-finance-os.`
3. Archive repository (keep **private**).
4. Disable Actions and Dependabot.

## 6. Tag v0.4.0

**Done.** Tag `v0.4.0` exists with a GitHub Release.

```bash
git tag -a v0.4.0 -m "Public rehome release: family-finance-os"
git push origin v0.4.0
```

Create GitHub Release from tag. Release notes must not include real financial data, secrets, or deployment-specific values.

## 7. Post-release

- [x] Close issue #66
- [ ] Update issue #72 with tag protection decision — **deferred to v1.0.0 RC**; see [v1-rc-release-gates.md](v1-rc-release-gates.md)
- [ ] Enable Codex GitHub integration — **owner browser action required**; see [#80](https://github.com/mlddragon/family-finance-os/issues/80) and [codex-subscription-setup.md](codex-subscription-setup.md)
- [x] Announce default clone URL: `https://github.com/mlddragon/family-finance-os`

## Stop conditions

Stop if:

- Gitleaks or Security workflow fails on `main`
- History scan finds credentials or raw financial exports
- Any public artifact contains owner-specific hostnames, account IDs, or recovery material

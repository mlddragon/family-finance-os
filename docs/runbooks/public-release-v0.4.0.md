# Public Release Runbook — v0.4.0

Owner-only checklist after the rehome PR stack merges to `main`.

## Preconditions

- [ ] PRs #74–#77 merged
- [ ] `main` CI and Security workflows green
- [ ] Full-history Gitleaks scan clean
- [ ] No real financial data or secrets in tracked files or history

## 1. Rename repository

GitHub → Settings → General → Repository name:

```text
Dillon_Finances → family-finance-os
```

Update local remotes:

```bash
git remote set-url origin https://github.com/mlddragon/family-finance-os.git
```

## 2. Flip visibility to Public

GitHub → Settings → General → Danger zone → Change visibility → Public.

## 3. Enable security settings (issue #66)

- Private vulnerability reporting
- Secret scanning
- Secret scanning push protection
- Dependabot alerts (verify on)
- Dependabot security updates (verify on)

## 4. Branch protection on `main`

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

```bash
git tag -a v0.4.0 -m "Public rehome release: family-finance-os"
git push origin v0.4.0
```

Create GitHub Release from tag. Release notes must not include real financial data, secrets, or deployment-specific values.

## 7. Post-release

- [ ] Close issue #66
- [ ] Update issue #72 with tag protection decision
- [ ] Enable Codex GitHub integration (see `docs/security/codex-analyst.md`)
- [ ] Announce default clone URL: `https://github.com/mlddragon/family-finance-os`

## Stop conditions

Stop if:

- Gitleaks or Security workflow fails on `main`
- History scan finds credentials or raw financial exports
- Any public artifact contains owner-specific hostnames, account IDs, or recovery material

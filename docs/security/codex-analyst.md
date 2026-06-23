# Codex Security Analyst

Family Finance OS uses **Codex as security and privacy analyst**, not primary engineer.

Implementation belongs to human contributors and Cursor via pull requests.

## Current status

GitHub `@codex` integration is **not enabled yet**. Until it is:

- Security review runs through the `Security` GitHub Actions workflow.
- Human maintainers review privacy and data-integrity impact in PRs.
- Follow [CODEX.md](../../CODEX.md) and **Codex Review Guidelines** in [AGENTS.md](../../AGENTS.md).

## When integration is enabled

Configure in Codex Cloud settings:

1. Connect repository `mlddragon/family-finance-os`.
2. Enable **Code review** and **Automatic reviews** for pull requests.
3. Point Codex at `AGENTS.md` Review guidelines.

### Commands

| Comment | Purpose |
| --- | --- |
| `@codex review` | Security and privacy review; P0/P1 only |
| `@codex review for security regressions` | Narrow security pass |
| `@codex review for dependency and supply chain risk` | CVE and new dependency focus |
| `@codex fix the P1 issue` | Minimal fix for a confirmed finding when explicitly requested |

### Out of scope

Do **not** use `@codex` for feature implementation, refactors, or routine engineering unless tied to a confirmed security finding.

## CI backstop

The `Security` workflow runs on every PR:

- Gitleaks
- Financial-data guard scripts
- pip-audit and Bandit
- Trivy container scan
- Repository hygiene checks

Optional future addition: `openai/codex-action` workflow posting review comments when `OPENAI_API_KEY` is configured.

## Reporting issues

Follow [SECURITY.md](../../SECURITY.md). Do not paste real financial data or secrets in public issues.

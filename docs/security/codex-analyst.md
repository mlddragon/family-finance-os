# Codex Security Analyst

Family Finance OS uses **Codex as security and privacy analyst**, not primary engineer.

Implementation belongs to human contributors and Cursor via pull requests.

## Integration model (subscription, not API)

| Path | Billing | Status |
| --- | --- | --- |
| `@codex review` on GitHub PRs | ChatGPT **Code Reviews** quota | Configure in [codex-subscription-setup.md](../runbooks/codex-subscription-setup.md) |
| `Security` GitHub Actions workflow | GitHub Actions minutes only | **Active** — no Codex/OpenAI usage |
| `openai/codex-action` + `OPENAI_API_KEY` | API token charges | **Not used** |

## Owner setup

Follow [docs/runbooks/codex-subscription-setup.md](../runbooks/codex-subscription-setup.md):

1. Connect `mlddragon/family-finance-os` in [Codex settings](https://chatgpt.com/codex/settings).
2. Enable **code review** for this repo at [code review settings](https://chatgpt.com/codex/settings/code-review).
3. Keep **Automatic reviews OFF** to avoid burning quota on every PR.

Repository review guidance lives in root `AGENTS.md` → **`## Review guidelines`**.

## Commands (manual, quota-aware)

| Comment | Quota bucket | When to use |
| --- | --- | --- |
| `@codex review` | Code Reviews | Security/privacy pass on a PR |
| `@codex review for security regressions` | Code Reviews | Narrow security focus |
| `@codex fix the P1 issue` | Cloud Tasks | Only after a review finding, owner-approved |

Do **not** use `@codex` for feature implementation or routine engineering.

## CI backstop (non-Codex)

The `Security` workflow runs on every PR:

- Gitleaks
- Financial-data guard scripts
- pip-audit and Bandit
- Trivy container scan
- Repository hygiene checks

## Reporting issues

Follow [SECURITY.md](../../SECURITY.md). Do not paste real financial data or secrets in public issues.

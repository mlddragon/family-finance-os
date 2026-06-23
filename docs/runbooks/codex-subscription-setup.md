# Codex Subscription GitHub Setup

Use **ChatGPT/Codex plan quota**, not pay-as-you-go API billing.

## Billing model (this repo)

| Method | Billing | Use here? |
| --- | --- | --- |
| `@codex review` on GitHub | ChatGPT **Code Reviews** quota | Yes — manual only |
| `@codex` cloud tasks (fix/implement) | ChatGPT **Cloud Tasks** quota | Only when explicitly requested |
| `openai/codex-action` + `OPENAI_API_KEY` in CI | **API token charges** | **No** |

## Owner setup (browser, one time)

Complete these in order. **Do not enable Automatic reviews** until you intentionally want every PR to consume review quota.

### 1. Sign in with ChatGPT (not an API key)

Open [chatgpt.com/codex](https://chatgpt.com/codex) and sign in with your **ChatGPT subscription** account.

Do not configure this repository with an API key for cloud/GitHub features.

### 2. Connect GitHub

1. Open [Codex settings](https://chatgpt.com/codex/settings).
2. Under **Environments** (or GitHub connection), connect GitHub if prompted.
3. Install/authorize the **ChatGPT GitHub Connector** / Codex GitHub app for account `mlddragon`.
4. Grant access to **`mlddragon/family-finance-os`** only (or all repos if you prefer, but this repo is the product home).

### 3. Enable code review (manual trigger only)

1. Open [Codex code review settings](https://chatgpt.com/codex/settings/code-review).
2. Turn **on** code review for **`mlddragon/family-finance-os`**.
3. Leave **Automatic reviews OFF** (prevents reviews on every new PR without someone asking).

### 4. Verify repository guidance

Codex reads `AGENTS.md` at the repo root, especially **`## Review guidelines`**.

No extra configuration file is required in `.github/codex/` beyond this runbook.

## How to request a review (after setup)

On an open pull request, comment:

```text
@codex review
```

Optional focused pass:

```text
@codex review for security regressions
```

Expected behavior:

- Codex reacts with 👀
- Codex posts a GitHub review with **P0/P1 only**

## Quota-conscious usage

- **Code review** (`@codex review`) draws from the **Code Reviews** bucket on your plan.
- **`@codex fix …`** or other non-review `@codex` mentions start **cloud tasks** (separate quota). Avoid on PRs unless fixing a confirmed P0/P1.
- Existing **Security** GitHub Actions workflow (Gitleaks, pip-audit, Trivy, etc.) does **not** use Codex and does not consume Codex quota.

## Verification checklist

After browser setup:

- [ ] Codex GitHub app can access `mlddragon/family-finance-os`
- [ ] Code review enabled for this repo
- [ ] Automatic reviews remain **disabled**
- [ ] No `OPENAI_API_KEY` in repository secrets
- [ ] No `openai/codex-action` workflow in `.github/workflows/`
- [ ] Test on a draft PR: comment `@codex review` and confirm 👀 + review post

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `@codex` does not react | GitHub app installed; repo connected in Codex environment; code review toggled on for this repo |
| Review is generic | Confirm `AGENTS.md` contains `## Review guidelines` on `main` |
| Unexpected charges | Ensure CI does not use `OPENAI_API_KEY`; disable Automatic reviews |

See also [docs/security/codex-analyst.md](../security/codex-analyst.md).

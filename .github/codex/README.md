# Codex in this repository

Family Finance OS uses **ChatGPT/Codex subscription** GitHub code review only.

## Allowed

- Manual `@codex review` comments on pull requests (uses **Code Reviews** subscription quota)
- Repository guidance in root `AGENTS.md` → `## Review guidelines`

## Not allowed without explicit owner approval

- `OPENAI_API_KEY` repository or environment secrets
- `openai/codex-action` or any CI workflow that calls the OpenAI API
- Automatic Codex reviews on every pull request (consumes quota without an explicit request)

Setup: [docs/runbooks/codex-subscription-setup.md](../../docs/runbooks/codex-subscription-setup.md)

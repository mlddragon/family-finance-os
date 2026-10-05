# AI Start Here — Public Repository Boundary

This public repository is self-contained for contributors and automated agents. It does not advertise or locate maintainer-private systems.

## Start in this order

1. Read `AGENTS.md`, `docs/product_requirements.md`, `docs/data_handling_policy.md`, `SECURITY.md`, and the task-relevant repository plan or runbook.
2. Refresh the repository and inspect the live checkout before relying on remembered state.
3. Use only this repository and context explicitly supplied with the task.
4. If a decision requires non-public maintainer input, state the missing decision and ask a maintainer for the minimum information needed.
5. Never seek, infer, disclose, or persist maintainer-private context in public issues, pull requests, commits, logs, fixtures, or examples.

## Repository boundary

| Subject | Authoritative source |
|---|---|
| Product requirements, technical design, code, tests, security and data-handling policy, implementation detail, release state, and repository history | This repository and its refreshed checkout |
| Live runtime accounts, secrets, endpoints, real household data, generated reports, databases, logs, and credentials | Authorized systems outside this repository; do not infer or request access unless the task explicitly authorizes it |
| A non-public maintainer decision needed to proceed | Ask a maintainer for the minimum decision or sanitized context needed |
| Temporary analysis and execution context | The current task or chat; non-authoritative until written back to this repository where appropriate |

## Conflict and write-back rules

1. Follow explicit task instructions within their stated scope.
2. Resolve repository-owned facts from the refreshed repository rather than chat memory.
3. Preserve and report genuine conflicts or missing maintainer decisions instead of guessing.
4. Write repository changes through a branch and pull request with applicable tests, hygiene checks, and security scans.
5. Reference public repository paths, issues, pull requests, releases, or commits when recording technical work.
6. Keep real household data and maintainer-private details out of public git, issues, pull requests, logs, fixtures, and examples. Use clearly synthetic data only where tests require data.

## Before reporting completion

- Verify the worktree and branch state.
- Verify the base and remote branch resolve to the intended commits.
- Verify the pull request and relevant checks.
- Report unavailable evidence, unresolved conflicts, and any intentional data-integrity limitations.

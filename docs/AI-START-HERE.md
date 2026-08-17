# AI Start Here — Cross-System Routing

This public document explains where an authorized agent should look. It intentionally contains no private household records, financial data, private Notion URLs, or business context.

## Start in this order

1. Read `AGENTS.md`, `SECURITY.md`, `docs/data_handling_policy.md`, and the task-relevant product or planning document.
2. Refresh the public GitHub repository and inspect the live checkout before relying on a remembered state.
3. If the task depends on family-project identity, ownership classification, open-source intent, high-level decisions, or cross-project routing, use an authenticated owner-authorized Notion connection.
4. In Notion, search for **Dillon Project Registry**, fetch the exact **Family Finance OS** row, and follow its **Notion Hub**, **Canonical Knowledge**, and **Write-back Rule** references. The dedicated hub is named **Family Finance OS** under **Dillon Family Operating System → Family & Household**. Consult **System Architecture & Governance**, **Decision & Context Register**, or **Migration Register** only when the governing row routes the question there.

Fetch the full Notion record; a search highlight is not authoritative. If Notion or GitHub is unavailable, identify what could not be verified. Do not replace it with chat memory or copy private material into this public repository.

## Canonical boundary

| Subject | Canonical home |
|---|---|
| Product definition, implementation, security and data policy, source code, tests, technical release history, and public repository history | This GitHub repository and its refreshed local checkout |
| Family-project identity, ownership classification, open-source intent, high-level decisions, and cross-project routing | The owner's private Notion knowledge system |
| Real household financial data and runtime artifacts | Approved local data locations outside public git |
| Temporary analysis, brainstorming, and execution context | Chat; non-authoritative until written back to the canonical home |
| Migration history | The Notion Migration Register and repository migration docs; provenance only |

Do not infer legal ownership from repository visibility, licensing, or a knowledge hierarchy. Do not copy private evidence into git to make a cross-system reference self-contained.

## Interpreting Notion state

- **Approved** — owner-accepted within the record's stated scope.
- **Working** — active and useful, but provisional or carrying open questions.
- **Exploring** — under consideration, not a commitment.
- **Source Context** — evidence or provenance, not a decision by itself.
- **Superseded** — retained for history and no longer current direction.

Scope and canonical subject matter outrank timestamps. The newest record is not automatically the authoritative one.

## Conflict and write-back rules

1. Follow an explicit current owner instruction for the requested action.
2. Resolve each fact in the system that owns its subject.
3. Preserve and report genuine conflicts; do not silently choose the newest copy.
4. Write repository-owned changes through a branch and pull request with applicable tests and privacy/security checks.
5. Update the existing Family Finance OS Notion row or hub for durable identity, ownership, routing, open-source intent, or high-level status. Reference a repository path, issue, PR, release, or commit instead of copying technical detail.
6. Keep real Dillon financial data outside public git and outside public issue or pull-request text.

## Final persistence check

Before claiming completion:

- verify the worktree and branch state;
- verify local `main` and `origin/main` resolve to the intended commit;
- verify the pull request and relevant GitHub checks;
- re-fetch each changed Notion record;
- confirm each durable fact has one canonical home and the other system points to it;
- report unavailable sources, unresolved conflicts, or facts left only in chat.

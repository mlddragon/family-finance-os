---
name: decision-card-review
description: Run recommendation-first decision reviews for product, architecture, privacy, data-integrity, planning, or implementation choices. Use when the user wants to work through outstanding questions, review decisions interactively, approve PR planning choices, compare options, or make auditable owner decisions one at a time before updating docs or merging work.
---

# Decision Card Review

## Overview

Use this skill to turn a list of open decisions into a calm, auditable review flow. Present one decision at a time as a compact card with a strong recommendation, rationale, serious alternatives, and a clear approval question. After decisions are made, update the source artifact or PR branch to record the outcome.

## Workflow

1. Identify the decision set from the current PR, planning doc, code review, todo list, or user request.
2. Confirm the decisions are safe to review in chat. Stop for explicit approval on privacy, security, data-integrity, cost-bearing, or architecture decisions when required.
3. Present one decision card at a time.
4. Wait for the user's answer before presenting the next card.
5. Treat short replies like "approved", "yes", "agreed", or "y" as approval of the recommended default unless the user adds qualifications.
6. Track approved decisions during the conversation.
7. After the final decision, summarize the decision record.
8. Update the relevant artifact or PR branch so the decision record is durable.
9. Verify the update before claiming it is complete.

## Decision Card Format

Use this structure by default:

```markdown
**Decision N: Short Name**

**Recommendation:** State the strongest recommended choice in one or two sentences.

Why: Give the practical rationale. Mention the main risk the recommendation avoids.

**Recommended default:**
- Concrete behavior.
- Concrete boundary.
- Audit/review consequence if relevant.

**Alternative:**
Describe the serious alternative worth considering and its tradeoff.

**Decision needed:** Do you approve the recommended default?
```

Keep each card concise. Prefer one strong recommendation and one serious alternative. Add a second alternative only if it is genuinely plausible.

## Recommendation Style

- Lead with the best recommendation, not a neutral menu.
- Explain the recommendation in product and engineering terms.
- Make the default easy to approve or edit.
- Avoid asking the user to decide routine engineering details.
- Escalate only decisions that affect product behavior, architecture, privacy, security, cost, data integrity, maintainability, or owner workflow.
- Use plain language over jargon.

## Approval Handling

Interpret replies as follows:

- "approved", "approve", "yes", "y", "agreed", "confirmed": approve the recommended default.
- "approved, but..." or "agree-ish": record approval with the stated qualification and revise the final decision record.
- "no", "hold", or a contrary answer: stop, ask a focused follow-up, and revise the recommendation before continuing.
- Ambiguous replies: ask one short clarifying question.

Do not batch multiple decision cards unless the user explicitly asks for a bulk review.

## Durable Record

After the decision sequence:

1. Summarize all approved decisions in chat.
2. Update the source planning doc, PR branch, issue, or decision log.
3. Convert "questions for review" into "review outcome" or "approved decisions" where appropriate.
4. Keep unresolved items explicitly labeled as open.
5. Preserve implementation gates; approval of planning direction is not approval to build unless the user explicitly says so.
6. Use normal project GitHub workflow when applicable: branch, commit, push, PR, merge only with approval.

## Review Boundaries

For sensitive projects, explicitly preserve these boundaries:

- Do not introduce app implementation when the task is planning-only.
- Do not create schema, dependencies, credentials, data files, or generated artifacts unless explicitly approved.
- Do not store raw or normalized financial data in git.
- Do not silently convert a recommendation into an architecture decision without owner approval.
- Do not let an approved mockup, contract, or plan imply permission to implement before remaining gates are satisfied.

## Example

```markdown
**Decision 2: Stale Sources**

**Recommendation:** Stale sources should make reports provisional, but should only block final monthly close.

Why: You should still be able to inspect partial data, but the product must not pretend stale data is final.

**Recommended default:**
- Stale source does not block import.
- Stale source does not block provisional reports.
- Affected reports are clearly labeled provisional.
- Stale required source blocks final monthly close.

**Alternative:**
Block report generation whenever any required source is stale. This is stricter, but makes the app less useful when one source is temporarily unavailable.

**Decision needed:** Do you approve the recommended default?
```

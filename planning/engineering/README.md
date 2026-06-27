# v1.1 Engineering Documentation Process

Engineering specs for the v1.1 expansion are written **before** implementation code.

## Roles

| Role | Model | Responsibility |
| --- | --- | --- |
| Sr Engineer | GPT-5.5 | Engineering docs: schema, APIs, migrations, tests, PR boundaries |
| Sr UX/UI | Opus 4.8 | Review docs for UX fit, terminology, screen/API alignment with approved mockups |

## Gate

No implementation PR for a track merges until:

1. Engineering doc(s) for that track exist in this directory.
2. Opus review in `planning/engineering/reviews/` status is **Approved** or **Approved with notes**.
3. If **Changes requested**, GPT revises the doc and Opus re-reviews.

## Sources of truth

- Decisions: [../v1_1_expansion_decision_record.md](../v1_1_expansion_decision_record.md)
- Mockups: [../mockups/v1_1/index.html](../mockups/v1_1/index.html)
- Rollup: [../v1_1_decision_rollup.md](../v1_1_decision_rollup.md)

## Document index

| Doc | Track | Phase | Opus review | Implementation |
| --- | --- | --- | --- | --- |
| `v1_1_00_overview.md` | Program | Cross-cutting | Approved | Reference |
| `v1_1_a1_schema.md` | A1 | Phase 1 | Approved | **GO** |
| `v1_1_a2_spendable.md` | A2 | Phase 1 | Approved with notes (applied) | **GO** |
| `v1_1_a3_auth.md` | A3 | Phase 1 | Approved with notes (applied) | **GO** |
| `v1_1_b1_funds.md` | B1 | Phase 2 | Approved with notes (applied) | **GO** (UI after B1 API) |
| `v1_1_b2_splits.md` | B2 | Phase 2 | Approved with notes (applied) | **GO** |
| `v1_1_b3_net_worth.md` | B3 | Phase 2 | Approved with notes (applied) | **GO** backend; entry form wireframe before UI |
| `v1_1_b4_analyst_export.md` | B4 | Phase 2 | Approved with notes (applied) | **GO** backend; extend mockup for estimates row before UI |
| `v1_1_b5_monthly_close.md` | B5 | Phase 2 | Approved with notes (applied) | **GO** backend; Governor override wireframe before UI |
| `v1_1_c1_dashboard.md` | C1 | Phase 3 | Approved | **GO** |
| `v1_1_d1_receipts.md` | D1 | Phase 4 | Approved with notes (applied) | **GO** |
| `v1_1_e1_scraper_framework.md` | E1-E4 | Phase 5, last | Approved with notes | Defer until B–D stable; Sources wireframe before adapter UI |

Reviews: [reviews/v1_1_phase1_ux_review.md](reviews/v1_1_phase1_ux_review.md), [reviews/v1_1_phase2_5_ux_review.md](reviews/v1_1_phase2_5_ux_review.md).

# v1.1 B5 Monthly Close Engineering Plan

Status: Draft  
Build phase: Phase 2  
Schema source: `planning/engineering/v1_1_a1_schema.md` defines `spendable_balance_snapshots.monthly_close_id`; this track extends the existing monthly close tables and artifacts.

## Purpose

Extend the existing monthly close flow with D9 funds and spendable gates, Financial Governor override behavior, and close bundle additions.

Current v1 close readiness already considers unreviewed transactions, stale required sources, missing required sources, and blocking validation findings. v1.1 adds fund pool and spendable checks:

- negative Pool remaining
- Reserved goal balance exceeding liquid
- negative headline Spendable balance
- missing fund commitments

Draft close is allowed with warnings. Final close is blocked unless Financial Governor elevated override is active, has a purpose note, and writes an audit event.

## Non-goals

- Do not weaken existing validation/source/review blockers.
- Do not finalize close silently with warnings.
- Do not add personal data or generated close bundles to git.
- Do not make Governor override available to all personas.
- Do not recalculate historical closed months unless an explicit reopen/reclose design is approved later.

## Schema/API

### Tables and Artifacts

Use existing tables:

- `monthly_closes`
- `jobs`
- `artifacts`
- `decision_events`
- elevated mode/session tables from A3 or current permission foundation

Store v1.1 gate detail in `monthly_closes.validation_summary` and artifact manifests.

### Close Readiness Additions

Add a `funds_and_spendable` section to close readiness:

```json
{
  "funds_and_spendable": {
    "negative_pool_remaining": ["pool_auto", "pool_dining"],
    "reserved_goals_exceed_liquid": false,
    "negative_headline_spendable": false,
    "missing_fund_commitments": ["pool_utilities"],
    "warnings": [],
    "blockers": []
  }
}
```

Draft behavior:

- Allowed when existing draft criteria pass.
- Includes D9 fund/spendable issues as warnings.
- Sets provisional labels.

Final behavior:

- Blocks on D9 issues unless Governor override is active.
- Existing blockers remain blockers and should not be bypassed unless the existing elevated-mode policy explicitly allows them.
- Override requires purpose note and decision event.

### API Shape

Existing endpoints remain:

- `POST /api/monthly-close/draft`
- `POST /api/monthly-close/finalize`

Extend `MonthlyCloseRequest`:

```json
{
  "actor": "owner",
  "actor_context": {},
  "month": "2026-06",
  "notes": "Synthetic close note",
  "override_purpose": "Proceed despite negative pool remaining after Governor review"
}
```

Error codes:

- `final_close_blocked`
- `monthly_close_already_exists`
- `monthly_close_override_required`
- `monthly_close_override_note_required`
- `monthly_close_governor_required`

### Governor Override

Final close with D9 blockers requires:

- active elevated session for Financial Governor or A3-approved equivalent
- explicit purpose note
- decision event with blocker list, override purpose, actor context, and monthly close id
- visible provisional/override flags in returned payload and close bundle

## UI (Mockup Screen)

Mockup reference: existing Reports screen pattern plus v1.1 approved terminology.

Reports / Monthly close changes:

- Show close readiness grouped by existing validation/source/review gates and new Funds/Spendable gates.
- Render `funds_and_spendable.blockers` and `funds_and_spendable.warnings` in the existing warning-band pattern. Each item should name the affected pool or spendable input, the amount when available, and whether draft close may proceed.
- Draft close button remains available when only D9 fund/spendable warnings exist.
- Final close button is disabled with reason unless Governor override is active. Use this reason copy when D9 blockers are present: "Final close needs Financial Governor override because Funds/Spendable checks have blockers."
- If existing source, review, or validation blockers remain, keep their current blocking copy and do not imply the D9 override clears them.
- When override is available, require a purpose note field before finalizing. Field label: "Governor override purpose". Required-state message: "Enter why final close should proceed with these Funds/Spendable blockers."
- Close result shows bundle artifact links and override/provisional status.

The UI should reuse existing status badges and warning bands. Add a lightweight wireframe or annotated Reports screenshot for the Governor override flow before the B5 UI PR because the action is elevated and audited. Backend/gate logic is unblocked.

## Test Plan

Backend unit tests:

- Draft close succeeds with negative Pool remaining and marks provisional.
- Final close fails with D9 blockers without override.
- Final close succeeds with Governor override and purpose note.
- Override attempt without purpose note fails.
- Existing blockers remain present in validation summary.
- Close manifest includes fund pool summary and spendable snapshot.
- Override decision event records actor context and blockers.

API tests:

- Close endpoints preserve existing response shape.
- Error detail codes are stable.
- Artifact paths stay inside `DATA_ROOT` and integrity checks still pass.

Frontend tests:

- Reports screen displays D9 warnings.
- Final close disabled state explains blocker.
- Override purpose field is required before final close.
- Successful close refreshes artifact list and monthly close status.

Human QA:

- Use synthetic QA data with one negative pool and one missing commitment.
- Run draft close and verify warning/provisional labels.
- Attempt final close without override and confirm block.
- Enter Governor elevated mode, provide purpose note, finalize, and inspect close manifest.

## Dependencies on A1/A2/A3

- A1: final monthly close schema additions or validation summary structure.
- A2: spendable snapshot and fund/spendable gate calculations.
- A3: Governor role/elevated mode, permissions, and actor audit guarantees.
- B1: fund pool summary and Reserved goal balance.
- B2: allocation-aware actuals for pool remaining and target comparisons.
- B4: analyst pack may be included or referenced in close bundles if generated for the month.

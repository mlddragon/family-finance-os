# Owner Real-Data Smoke Handoff (post-RC)

Use this after **`v1.0.0-rc.N`** is tagged and owner **explicitly approves** real-data smoke.

## Hard gates (do not skip)

1. RC tag exists on `main` (`v1.0.0-rc.1` or later).
2. Synthetic QA record green: [planning/v1_synthetic_qa_record.md](../../planning/v1_synthetic_qa_record.md).
3. Owner written approval to run smoke (issue comment or PR note).

## Runtime

| Setting | Value |
| --- | --- |
| Compose project | `ffos-personal` |
| URL | `http://127.0.0.1:28080` |
| Data | Personal `DATA_ROOT` outside git |

```bash
make personal-up   # if not already running
```

## Checklist

Follow [docs/owner_smoke_checklist_v1.md](../owner_smoke_checklist_v1.md) (11 steps). Record only the sanitized evidence template from that doc.

## After smoke passes

1. Agent or owner tags **`v1.0.0`** stable (not prerelease).
2. Update [CHANGELOG.md](../../CHANGELOG.md) with `1.0.0` release section.
3. Close remaining RC tracking issues as appropriate.

## If smoke fails

- File issues with sanitized blocker codes only.
- Do **not** tag stable `v1.0.0` until blockers are fixed and smoke re-run passes.
- RC prerelease tag may remain; cut `v1.0.0-rc.2` if needed after fixes.

## Out of scope for smoke

- Amazon vendor enrichment (v1.1)
- Authentication / LAN exposure
- Codex automatic reviews ([#80](https://github.com/mlddragon/family-finance-os/issues/80) waived for RC)

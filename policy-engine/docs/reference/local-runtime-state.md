# Local Runtime State

Freshness: 2026-05-05
Owner: `team-platform`
Source of truth: `architecture/local_runtime_state.toml`,
`architecture/runtime_state_layout.toml`

`.polisyos/` is local runtime state. The only tracked file in this root is
`.polisyos/SCHEMA.md`; raw runtime payloads remain ignored and must be promoted
only through reviewed summaries or release evidence.

CAS state is canonical under `.polisyos/cas`. Recomputable CAS cache lives under
`.polisyos/cas/_cache`, and README/check artifacts live under
`.polisyos/cas/_readme_check`.

## Classes

| Class | Paths | Retention | Cleanup |
| --- | --- | --- | --- |
| Runs | `.polisyos/runs` | 7 days | remove run directories |
| Reports | `.polisyos/reports` | 30 days | remove report directories |
| Audits | `.polisyos/audits` | 365 days | manual approval only |
| CAS | `.polisyos/cas` | 365 days | owner-approved unreferenced blob cleanup |
| CAS cache | `.polisyos/cas/_cache` | 30 days | cleanup tool dry-run first |
| CAS readme/check artifacts | `.polisyos/cas/_readme_check` | 7 days | cleanup tool dry-run first |
| Production data | `.polisyos/production_data` | 365 days | manual approval only |
| Provider verification | `.polisyos/provider_verification` | 30 days | cleanup tool dry-run first |
| Idempotency | `.polisyos/idempotency` | 90 days | manual approval only |
| Decision validity | `.polisyos/decision_validity` | 180 days | manual approval only |
| Search registry | `.polisyos/search_registry` | 30 days | cleanup tool dry-run first |
| Runtime component state | `.polisyos/runtime` | 90 days | manual approval only |
| Security evidence | `.polisyos/security` | 365 days | manual approval only |
| Evicted legacy state | `.polisyos/evicted` | 90 days | manual approval only |
| Fact logs | `.polisyos/facts` | 30 days | cleanup tool dry-run first |
| Local keys | `.polisyos/keys` | 365 days | manual approval only |
| Scholar cache | `.polisyos/scholar_cache` | 14 days | cleanup tool dry-run first |
| Scholar jobs | `.polisyos/scholar_jobs` | 30 days | manual approval only |
| Scientist memory | `.polisyos/scientist` | 90 days | manual approval only |
| Control-plane SQLite | `.polisyos/control_plane.sqlite3`, `.polisyos/control.sqlite3` | 90 days | manual approval only |
| Future persisted local state | `.polisyos/state` | 90 days | manual approval only |

Promote only reviewed summaries into `docs/archive/reports/` or release
evidence. Raw runtime state stays local and cleanable.

Run cleanup in dry-run mode first:

```bash
uv run python tools/ops_runners/runtime/runtime_state_cleanup.py --slot runs --dry-run
```

Production snapshots cannot be deleted unless the command includes both
`--apply` and `--approve-production-snapshots`.

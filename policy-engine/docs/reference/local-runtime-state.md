# Local Runtime State

Freshness: 2026-05-03
Owner: `team-platform`
Source of truth: `architecture/local_runtime_state.toml`

`.polisyos/` is local runtime state. After Phase 2A, the canonical copy lives
only under the collapsed product root and should not be used as a committed
evidence store.

## Classes

| Class | Paths | Retention | Cleanup |
| --- | --- | --- | --- |
| Runs | `.polisyos/runs` | 7 days | remove run directories |
| Reports | `.polisyos/reports` | 30 days | remove report directories |
| Artifact cache | `.polisyos/artifacts` | 90 days | remove cached artifacts |
| Production data | `.polisyos/production_data` | 365 days | manual approval only |
| Provider verification | `.polisyos/provider_verification` | 30 days | remove local provider evidence |

Promote only reviewed summaries into `docs/archive/reports/` or release
evidence. Raw runtime state stays local and cleanable.

# tools/ops_runners/reports

Report-only operational evidence builders live here when the output is useful
to package moves, cleanup branches, or follow-on gates but must not fail CI yet.

Current reports:

| Script | Purpose | Mode |
| --- | --- | --- |
| `dead_overrides.py` | Reports stale mypy/ruff per-file override entries and missing owner/sunset metadata from the generated Phase 5.5 tool configs. | report-only |

Typical run:

```bash
uv run python tools/ops_runners/reports/dead_overrides.py --json-output .polisyos/reports/dead_overrides.json
uv run polisyos-tools workspace tool-configs --check
```

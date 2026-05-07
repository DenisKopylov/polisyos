# Operations Runners

- Owner: team-ops
- Purpose: executable operations tasks for release, migration, reporting, runtime cleanup, and data acquisition workflows.
- Allowed contents: owned operational runners, report generators, migration helpers, and command-specific fixtures or docs.
- Local verification: `uv run python tools/ops_runners/reports/dead_overrides.py --json-output _build/.tmp/wave7-closeout/dead-overrides.json`
- Maintenance: production-impacting runners must document inputs and outputs; retired ops scripts belong in `tools/archive` or are removed.

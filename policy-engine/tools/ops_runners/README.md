# Operations Runners

- Owner: team-ops
- Purpose: executable operations tasks for release, migration, reporting, runtime cleanup, and data acquisition workflows.
- Allowed contents: owned operational runners, report generators, migration helpers, and command-specific fixtures or docs.
- Local verification: `uv run python tools/ops_runners/reports/dead_overrides.py --json-output _build/.tmp/wave7-closeout/dead-overrides.json`
- The dead-override report resolves Ruff per-file matchers from the active caller root
  recorded in `configs.ruff_project_root`. Product discovery and explicit product calls
  use `ruff.toml` with the root-colocated `ruff.generated.toml`; workspace-root calls use
  the manifest-declared workspace config and prefix. Workspace paths are normalized to
  product-root paths before existence and metadata checks. Missing or malformed configs
  produce `status = failed` and a non-zero exit, never a zero-selector report.
- Maintenance: production-impacting runners must document inputs and outputs; retired ops scripts belong in `tools/archive` or are removed.

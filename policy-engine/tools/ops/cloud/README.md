# tools/cloud

Canonical cloud tooling surface for shard preparation, reviewed deployment,
pipeline execution, and cloud preflight.

Use the unified entry point:

```bash
polisyos-tools cloud --help
polisyos-tools graph --format mermaid
```

Canonical layout:

- `deploy/`: reviewed host setup and shard deploy helpers
- `pipeline/`: long-running pipeline and validation wrappers
- `shards/`: shard preparation and progress helpers
- `preflight/`: explicit preflight contracts

Dependency ordering is declared in `tools.registry`; for example, GCP preflight
precedes `run-lex-from-manifest`, which precedes shard merge workflows. The
legacy `cloud_deploy/` directory is now a compatibility bridge only.

Operational rules:

- Destructive or overwrite-prone operations must require explicit confirmation
  flags.
- Long-running commands should emit timing records via `--timing-log` or
  `POLISYOS_TOOLS_TIMING_LOG`.
- External commands must use `tools._lib.runner.run_command`, not shell strings.
- Canonical generated shard/env assets default to `tools/cloud/deploy/assets/`.

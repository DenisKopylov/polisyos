# tools/ops_runners/migrations

Operational and format migrations for artifacts and data stores.
Canonical contracts live in `ops/migrations/migration-contracts.toml`; helper
CLIs fail closed if their `helper_binding` or target class path is missing.

## Scripts

| Script                    | What It Does                                                                                         | Status                       |
| ------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------- |
| `migrate_duckdb_to_pg.py` | Migrates tenant-scoped tables from DuckDB to PostgreSQL (`--duckdb-path`, `--pg-dsn`, `--tenant-id`) | manual/Ops                   |
| `migrate.py`              | Migrates `policy_ir` / `dataset_manifest` / `run_manifest` between versions                          | canonical CLI/module surface |
| `contracts.py`            | Loads `ops/migrations/migration-contracts.toml` and validates helper bindings                        | contract bridge              |

## Related Directories

- `src/polisyos/common/migrations/*` and `src/polisyos/ir/migrations/*`
- `ops/migrations/{db,runtime_state,api_schemas,ir}/README.md`
- `runs/*` and JSON/YAML artifact manifests
- external DuckDB/PostgreSQL instances for data migration

## Typical Usage

```bash
uv run polisyos-tools migrations migrate-duckdb-to-pg --duckdb-path integration.duckdb --pg-dsn postgresql://... --tenant-id 11111111-1111-1111-1111-111111111111 --dry-run
uv run polisyos-tools migrations migrate policy_ir input.json output.json --to 1.0
```

## Known Limitations

- YAML payloads still require `PyYAML`; the JSON migration path works without it.
- CI and contributor-facing workflows now use `polisyos-tools` as the canonical entry point.

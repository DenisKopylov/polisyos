# tools/ops_runners/migrations

Operational and format migrations for artifacts and data stores.
Canonical contracts live in `ops/migrations/migration-contracts.toml`; helper
CLIs fail closed if their unique `helper_binding`, target class, workspace path,
or declared artifact converter cannot be resolved. The artifact CLI executes the
selected callable. Dataset manifest calls use a per-call Common migration edge,
so concurrent calls cannot replace each other's converter through the shared registry.

The contract loader selects the source checkout by module ancestry. An installed
runner without that ancestry may read the contract from the current workspace;
its source directory is not added to the installed runner's import path. The
layout check establishes neither workspace authenticity nor installed-code
provenance. The current tests exercise an installed-shaped path in the existing
editable environment; an installed wheel run remains a separate check.

Conversion, path normalization, strict target DTO validation, and provenance or
admission are separate operations; a successful conversion is not evidence that
an artifact is admissible for another use.

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

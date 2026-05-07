# tools/ops_runners/migrations

Операционные и форматные миграции для артефактов и хранилищ данных.
Canonical contracts live in `ops/migrations/migration-contracts.toml`; helper
CLIs fail closed if their `helper_binding` or target class path is missing.

## Скрипты

| Скрипт                    | Что делает                                                                                       | Статус                       |
| ------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------- |
| `migrate_duckdb_to_pg.py` | Перенос tenant-scoped таблиц из DuckDB в PostgreSQL (`--duckdb-path`, `--pg-dsn`, `--tenant-id`) | manual/Ops                   |
| `migrate.py`              | Миграция `policy_ir` / `dataset_manifest` / `run_manifest` между версиями                        | canonical CLI/module surface |
| `contracts.py`            | Loads `ops/migrations/migration-contracts.toml` and validates helper bindings                     | contract bridge              |

## Связь с другими директориями

- `src/polisyos/common/migrations/*` и `src/polisyos/ir/migrations/*`
- `ops/migrations/{db,runtime_state,api_schemas,ir}/README.md`
- `runs/*` и JSON/YAML манифесты артефактов
- внешние DuckDB/PostgreSQL инстансы для data migration

## Типовой запуск

```bash
uv run polisyos-tools migrations migrate-duckdb-to-pg --duckdb-path integration.duckdb --pg-dsn postgresql://... --tenant-id 11111111-1111-1111-1111-111111111111 --dry-run
uv run polisyos-tools migrations migrate policy_ir input.json output.json --to 1.0
```

## Известные ограничения

- YAML payloads по-прежнему требуют `PyYAML`; JSON migration path работает без него.
- Для CI и contributor-facing workflows canonical entrypoint now goes through `polisyos-tools`.

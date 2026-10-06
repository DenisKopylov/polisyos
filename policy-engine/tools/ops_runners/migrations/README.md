# tools/ops_runners/migrations

Операционные и форматные миграции для артефактов и хранилищ данных.
Canonical contracts live in `ops/migrations/migration-contracts.toml`; helper
CLIs fail closed if their `helper_binding` or target class path is missing.
For `policy_ir`, `dataset_manifest`, and `run_manifest`, the canonical artifact
CLI also resolves and invokes the declared callable; the binding is part of the
executable route, not only a class/path checklist. Other operational helpers
may declare a module entrypoint instead of an artifact converter callable.

## Скрипты

| Скрипт                    | Что делает                                                                                       | Статус                       |
| ------------------------- | ------------------------------------------------------------------------------------------------ | ---------------------------- |
| `migrate_duckdb_to_pg.py` | Перенос tenant-scoped таблиц из DuckDB в PostgreSQL (`--duckdb-path`, `--pg-dsn`, `--tenant-id`) | manual/Ops                   |
| `migrate.py`              | Миграция `policy_ir` / `dataset_manifest` / `run_manifest` между версиями                        | canonical CLI/module surface |
| `contracts.py`            | Loads migration contracts, validates paths, and resolves bound callables                          | contract bridge              |

## Связь с другими директориями

- `src/polisyos/common/migrations/*` и `src/polisyos/ir/migrations/*`
- `ops/migrations/{db,runtime_state,api_schemas,ir}/README.md`
- `runs/*` и JSON/YAML манифесты артефактов
- внешние DuckDB/PostgreSQL инстансы для data migration

`policy_ir` delegates to the IR migration/validation owner. `dataset_manifest`
registers the resolved Fabric converter with Common's neutral linear engine.
`run_manifest` invokes Runtime's path-only normalizer. These profiles keep
version conversion, path normalization, strict DTO validation, and provenance
or admission as separate operations; a successful conversion is not evidence
that an artifact is admissible for another use.

## Типовой запуск

```bash
uv run polisyos-tools migrations migrate-duckdb-to-pg --duckdb-path integration.duckdb --pg-dsn postgresql://... --tenant-id 11111111-1111-1111-1111-111111111111 --dry-run
uv run polisyos-tools migrations migrate policy_ir input.json output.json --to 1.0
```

## Известные ограничения

- YAML payloads по-прежнему требуют `PyYAML`; JSON migration path работает без него.
- Для CI и contributor-facing workflows canonical entrypoint now goes through `polisyos-tools`.

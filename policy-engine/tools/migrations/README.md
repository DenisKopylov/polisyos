# tools/migrations

Операционные и форматные миграции для артефактов и хранилищ данных.

## Скрипты

| Скрипт | Что делает | Статус |
|---|---|---|
| `migrate_duckdb_to_pg.py` | Перенос tenant-scoped таблиц из DuckDB в PostgreSQL (`--duckdb-path`, `--pg-dsn`, `--tenant-id`) | manual/Ops |
| `migrate.py` | Миграция `policy_ir` / `dataset_manifest` / `run_manifest` между версиями | legacy, требует исправления |

## Связь с другими директориями

- `src/polisyos/common/migrations/*` и `src/polisyos/ir/migrations/*`
- `runs/*` и JSON/YAML манифесты артефактов
- внешние DuckDB/PostgreSQL инстансы для data migration

## Типовой запуск

```bash
PYTHONPATH=src:. uv run python tools/migrations/migrate_duckdb_to_pg.py --duckdb-path integration.duckdb --pg-dsn postgresql://... --tenant-id 11111111-1111-1111-1111-111111111111 --dry-run
PYTHONPATH=src:. uv run python tools/migrations/migrate.py policy_ir input.json output.json --to 1.0
```

## Известные ограничения

- `migrate.py` импортирует `POLICY_IR_CURRENT_VERSION` из `polisyos.common.migrations`, но в этом пакете экспортируется только `MANIFEST_CURRENT_VERSION`.
- До исправления `migrate.py` следует рассматривать как legacy-утилиту и проверять выполнение вручную.

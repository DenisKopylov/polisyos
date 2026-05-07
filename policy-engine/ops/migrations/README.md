# Operational Migrations (`ops/migrations`)

- Owner: `team-ops`
- Artifact type: `migration-contracts`

`ops/migrations/` is the release-facing contract root for DB schema,
runtime-state schema, API schema, and IR schema migrations. Implementation
helpers may live in Python packages or `tools/ops_runners/**`, but every
operator-visible migration family must be declared here before release
promotion.

## Роль в системе

Migrations support:

- the PostgreSQL runtime contract in `src/polisyos/core/security/db_backend.py`,
  where tenant context is passed through `SET LOCAL app.current_tenant`;
- local `.polisyos/**` runtime-state contracts from
  `architecture/runtime_state_layout.toml`;
- Runtime API/OpenAPI and generated-client schema compatibility;
- canonical Policy IR and persisted artifact schema compatibility.

## Classed Layout

```text
ops/migrations/
  db/
  runtime_state/
  api_schemas/
  ir/
```

The source of truth for class ownership, helper bindings, release gates, and
required operator docs is `migration-contracts.toml`.

## DB Forward Sequence

1. `db/001_tenant_columns.sql`
2. `db/002_tenant_backfill.sql` (runbook-шаблон backfill)
3. `db/003_rls_enable.sql`
4. `db/004_roles_grants.sql`

`db/003_rls_disable_rollback.sql` используется только как emergency rollback
после шага `003`.

## Migration classes

| Class | Path | Operator guidance | Release gate |
| --- | --- | --- | --- |
| DB schema | `db/` | `db/README.md` | `db_migration_review` |
| Runtime-state schema | `runtime_state/` | `runtime_state/README.md` | `runtime_state_migration_review` |
| API schema | `api_schemas/` | `api_schemas/README.md` | `api_schema_compatibility` |
| IR schema | `ir/` | `ir/README.md` | `ir_migration_review` |

## Что делает каждый файл

| Файл                           | Назначение                                                                          |
| ------------------------------ | ----------------------------------------------------------------------------------- |
| `db/001_tenant_columns.sql`       | добавляет nullable `tenant_id` в tenant-scoped таблицы `world.*` и `public.*`       |
| `db/002_tenant_backfill.sql`      | фиксирует процедуру заполнения `tenant_id` и gate-проверки перед RLS                |
| `db/003_rls_enable.sql`           | включает `NOT NULL`, tenant indexes, `ENABLE/FORCE RLS`, политики `tenant_access_*` |
| `db/003_rls_disable_rollback.sql` | удаляет tenant policies и отключает RLS на затронутых таблицах                      |
| `db/004_roles_grants.sql`         | создает/настраивает роль `polisyos_app`, grants и default privileges                |

## Python Helper Bindings

`tools/ops_runners/migrations/migrate.py` and
`tools/ops_runners/migrations/migrate_duckdb_to_pg.py` are operator entrypoints,
but they are not standalone policy. Each helper is bound to a migration class in
`migration-contracts.toml`:

- `policy_ir` -> `ir`;
- `dataset_manifest` -> `api_schemas`;
- `run_manifest` -> `runtime_state`;
- `duckdb_to_postgresql` -> `db`.

The helpers fail closed when their declared contract path or class is missing.

## Breaking-Change Promotion Rule

Breaking runtime-state, API schema, IR schema, or persisted artifact changes
must update:

- the owning class README under this directory;
- `docs/runbooks/migration-release-promotion.md`;
- release notes or migration-guide material named by the relevant gate in
  `ops/release/promotion-gates.toml`.

## Операционные требования

- перед `003` во всех tenant-scoped таблицах должно быть `tenant_id IS NOT NULL`;
- роль приложения не должна иметь `BYPASSRLS`/`SUPERUSER`;
- `ALTER DATABASE polisyos SET app.current_tenant = '00000000-0000-0000-0000-000000000000'` служит fail-safe default.

## Минимальные проверки после `003`

```sql
-- 1) отсутствие NULL tenant_id (пример)
SELECT count(*) AS null_tenant_rows
FROM world.world_facts
WHERE tenant_id IS NULL;

-- 2) проверка, что RLS включен и принудителен
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname IN ('world_facts', 'run_records');
```

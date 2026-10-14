# Operational Migrations (`ops/migrations`)

- Owner: `team-ops`
- Artifact type: `migration-contracts`

`ops/migrations/` is the release-facing contract root for DB schema,
runtime-state schema, API schema, and IR schema migrations. Implementation
helpers may live in Python packages or `tools/ops_runners/**`, but every
operator-visible migration family must be declared here before release
promotion.

## Role in the System

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
2. `db/002_tenant_backfill.sql` (backfill runbook template)
3. `db/003_rls_enable.sql`
4. `db/004_roles_grants.sql`

`db/003_rls_disable_rollback.sql` is used only for emergency rollback after step `003`.

## Migration classes

| Class                | Path             | Operator guidance         | Release gate                     |
| -------------------- | ---------------- | ------------------------- | -------------------------------- |
| DB schema            | `db/`            | `db/README.md`            | `db_migration_review`            |
| Runtime-state schema | `runtime_state/` | `runtime_state/README.md` | `runtime_state_migration_review` |
| API schema           | `api_schemas/`   | `api_schemas/README.md`   | `api_schema_compatibility`       |
| IR schema            | `ir/`            | `ir/README.md`            | `ir_migration_review`            |

## What Each File Does

| File                              | Purpose                                                                                |
| --------------------------------- | -------------------------------------------------------------------------------------- |
| `db/001_tenant_columns.sql`       | adds nullable `tenant_id` to tenant-scoped tables in `world.*` and `public.*`          |
| `db/002_tenant_backfill.sql`      | defines the `tenant_id` backfill procedure and gate checks before RLS                  |
| `db/003_rls_enable.sql`           | enables `NOT NULL`, tenant indexes, `ENABLE/FORCE RLS`, and `tenant_access_*` policies |
| `db/003_rls_disable_rollback.sql` | removes tenant policies and disables RLS on affected tables                            |
| `db/004_roles_grants.sql`         | creates/configures the `polisyos_app` role, grants, and default privileges             |

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

## Operational Requirements

- before `003`, `tenant_id IS NOT NULL` must hold for every tenant-scoped table;
- the application role must not have `BYPASSRLS` or `SUPERUSER`;
- `ALTER DATABASE polisyos SET app.current_tenant = '00000000-0000-0000-0000-000000000000'` serves as the fail-safe default.

## Minimum Checks After `003`

```sql
-- 1) No NULL tenant_id values (example)
SELECT count(*) AS null_tenant_rows
FROM world.world_facts
WHERE tenant_id IS NULL;

-- 2) Check that RLS is enabled and forced
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname IN ('world_facts', 'run_records');
```

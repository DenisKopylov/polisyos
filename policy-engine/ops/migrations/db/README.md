# DB Schema Migrations

Owner: `team-platform`

This directory owns database schema and role/grant migrations that operators
must understand before staging or production promotion. Current DB migrations
target PostgreSQL tenant isolation and row-level security.

## Forward Order

1. `001_tenant_columns.sql`
2. `002_tenant_backfill.sql`
3. `003_rls_enable.sql`
4. `004_roles_grants.sql`

`003_rls_disable_rollback.sql` is emergency rollback only after `003_rls_enable.sql`.

## Operator Checks

- Confirm tenant-scoped tables have no `NULL tenant_id` rows before enabling
  RLS.
- Confirm `polisyos_app` does not have `BYPASSRLS` or `SUPERUSER`.
- Confirm `relrowsecurity` and `relforcerowsecurity` are enabled after
  `003_rls_enable.sql`.
- Attach dry-run/backfill evidence to the release candidate before production
  promotion.

## Release Gate

`ops/release/promotion-gates.toml#db_migration_review` blocks DB schema
promotion unless this README, `ops/migrations/migration-contracts.toml`, and
the affected SQL files tell the same forward/rollback story.

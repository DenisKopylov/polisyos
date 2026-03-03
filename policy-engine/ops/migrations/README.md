# SQL Migrations (`ops/migrations`)

SQL-цепочка для tenant isolation в PostgreSQL: добавление `tenant_id`, включение RLS и least-privilege роли приложения.

## Роль в системе

Миграции поддерживают runtime-контракт из `src/polisyos/core/security/db_backend.py`, где tenant-контекст передается через `SET LOCAL app.current_tenant`.

## Forward sequence

1. `001_tenant_columns.sql`
2. `002_tenant_backfill.sql` (runbook-шаблон backfill)
3. `003_rls_enable.sql`
4. `004_roles_grants.sql`

`003_rls_disable_rollback.sql` используется только как emergency rollback после шага `003`.

## Что делает каждый файл

| Файл | Назначение |
|---|---|
| `001_tenant_columns.sql` | добавляет nullable `tenant_id` в tenant-scoped таблицы `world.*` и `public.*` |
| `002_tenant_backfill.sql` | фиксирует процедуру заполнения `tenant_id` и gate-проверки перед RLS |
| `003_rls_enable.sql` | включает `NOT NULL`, tenant indexes, `ENABLE/FORCE RLS`, политики `tenant_access_*` |
| `003_rls_disable_rollback.sql` | удаляет tenant policies и отключает RLS на затронутых таблицах |
| `004_roles_grants.sql` | создает/настраивает роль `polisyos_app`, grants и default privileges |

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

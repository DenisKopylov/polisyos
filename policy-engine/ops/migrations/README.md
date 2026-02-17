# SQL Migrations (`ops/migrations`)

Миграции tenant isolation для PostgreSQL: добавление `tenant_id`, переход к RLS и least-privilege роли приложения.

## Контекст

Эти миграции поддерживают runtime-контракт из `src/polisyos/core/security/db_backend.py`, где tenant-контекст передается через `SET LOCAL app.current_tenant`.

## Порядок применения (forward)

1. `001_tenant_columns.sql`
2. `002_tenant_backfill.sql` (runbook-шаблон для backfill, не выполняет DML сам по себе)
3. `003_rls_enable.sql`
4. `004_roles_grants.sql`

`003_rls_disable_rollback.sql` не входит в forward-цепочку и используется только как emergency rollback для шага `003`.

## Что делает каждый файл

| Файл | Назначение |
|---|---|
| `001_tenant_columns.sql` | добавляет nullable `tenant_id` в tenant-scoped таблицы `world.*` и `public.*` |
| `002_tenant_backfill.sql` | описывает процесс backfill и валидацию перед включением RLS |
| `003_rls_enable.sql` | включает `NOT NULL`, индексы, `ENABLE/FORCE ROW LEVEL SECURITY`, политики `tenant_access_*` |
| `003_rls_disable_rollback.sql` | удаляет RLS policies и выключает RLS на затронутых таблицах |
| `004_roles_grants.sql` | создает/настраивает роль `polisyos_app`, grants и default privileges |

## Операционные примечания

- До `003_rls_enable.sql` все tenant-scoped строки должны иметь заполненный `tenant_id`.
- `ALTER DATABASE polisyos SET app.current_tenant = '00000000-0000-0000-0000-000000000000'` в `004` задает fail-safe default.
- Роли приложения нельзя выдавать `BYPASSRLS` или `SUPERUSER`.

## Минимальная валидация после `003`

```sql
-- пример проверки для одной таблицы
SELECT count(*) AS null_tenant_rows
FROM world.world_facts
WHERE tenant_id IS NULL;

-- проверка, что RLS включен
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname IN ('world_facts', 'run_records');
```

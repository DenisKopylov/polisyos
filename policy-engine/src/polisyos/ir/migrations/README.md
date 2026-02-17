# ir.migrations

`ir.migrations` — runtime механизм миграции schema versions для canonical policy IR payload.

## Состав

| Файл | Назначение |
|---|---|
| `base.py` | общий реестр migration-функций (`register_migration`, `migrate_artifact`) |
| `__init__.py` | policy IR API: `migrate_policy_ir`, version parsing/major bump checks |
| `policy_ir.py` | текущая canonical версия и registration migration-цепочки |
| `trinity_migration.py` | helpers проверки/нормализации Trinity payload |

## Текущее состояние

- `IR_ARTIFACT = "policy_ir"`.
- `IR_CURRENT_VERSION = "1.0"`.
- Зарегистрирована migration: `1.0 -> 1.0` (identity через `TrinityBundle.model_validate`).
- Runtime миграции legacy non-Trinity payload не поддерживаются.

## Ограничения

- `migrate_policy_ir()` требует `schema_version` в payload.
- Если major версия меняется, нужно явно указать `allow_major=True`.
- Payload с `schema_version` семейства `2.*` или с полем `semantic` отклоняется как legacy формат.

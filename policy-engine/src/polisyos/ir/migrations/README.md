# ir.migrations

`ir.migrations` — runtime механизм миграции версий schema для canonical policy IR payload.

## Состав

| Файл | Назначение |
|---|---|
| `base.py` | общий реестр migration-функций (`register_migration`, `migrate_artifact`) |
| `__init__.py` | policy IR API: `migrate_policy_ir`, version parsing, major bump checks |
| `policy_ir.py` | текущая canonical версия и регистрация migration-цепочки |
| `trinity_migration.py` | вспомогательные проверки/нормализация Trinity payload |

## Текущее состояние

- `IR_ARTIFACT = "policy_ir"`.
- `IR_CURRENT_VERSION = "1.0"`.
- Зарегистрирован migration шаг: `1.0 -> 1.0` (identity через `TrinityBundle.model_validate`).
- Runtime миграции legacy non-Trinity payload не поддерживаются.

## Ограничения и поведение

- `migrate_policy_ir()` требует `schema_version` в payload.
- `schema_version` должен быть формата `MAJOR.MINOR`.
- При major change требуется явный `allow_major=True`.
- Payload с `schema_version` семейства `2.*` или полем `semantic` отклоняется как legacy формат.
- `migrate_artifact()` защищён от циклов миграции и от отсутствующих переходов в registry.

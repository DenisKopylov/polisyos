# `polisyos.common.migrations`

Локальный реестр миграций для артефактов, владельцем схем которых является слой `polisyos.common`.

## Что здесь есть

```text
migrations/
├── __init__.py   # migrate_artifact, register_migration, MANIFEST_CURRENT_VERSION
├── base.py       # общий реестр и executor цепочки миграций
└── manifest.py   # dataset_manifest: 0.9 -> 1.0
```

## Контракт

- формат реестра: `_MIGRATIONS[artifact][from_version] -> (to_version, fn)`;
- `register_migration(artifact, from_version, to_version)` регистрирует шаг миграции;
- `migrate_artifact(data, artifact, target_version)` применяет шаги до `target_version`;
- обязательное поле входных данных: `schema_version`;
- защита от циклов миграции встроена (`visited` set).

## Текущее покрытие

- зарегистрирован только один артефакт: `dataset_manifest`;
- доступная миграция: `0.9 -> 1.0`;
- текущая версия манифеста экспортируется как `MANIFEST_CURRENT_VERSION = "1.0"`.

## Границы ответственности

- миграции `policy_ir` не находятся в этом пакете;
- для `policy_ir` использовать `polisyos.ir.migrations`.

Текущий нюанс совместимости:
- некоторые CLI-скрипты в репозитории импортируют `POLICY_IR_CURRENT_VERSION` из `polisyos.common.migrations`, но этот символ здесь не экспортируется.

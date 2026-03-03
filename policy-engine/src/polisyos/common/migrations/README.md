# `polisyos.common.migrations`

Локальный migration-слой для артефактов, схемами которых владеет `polisyos.common`.

## Состав пакета

```text
migrations/
├── __init__.py   # экспорт API
├── base.py       # реестр миграций и executor цепочки
└── manifest.py   # миграция dataset_manifest: 0.9 -> 1.0
```

## Публичный контракт

- `register_migration(artifact, from_version, to_version)` — регистрирует шаг миграции;
- `migrate_artifact(data, artifact, target_version)` — применяет шаги до целевой версии;
- `MANIFEST_CURRENT_VERSION` — текущая версия `dataset_manifest`.

Входные данные обязаны содержать `schema_version`; при цикле или разрыве цепочки функция кидает `ValueError`.

## Текущее покрытие (март 2026)

- артефакт: `dataset_manifest`;
- цепочка: `0.9 -> 1.0`;
- шаг `0.9 -> 1.0` в `manifest.py` нормализует старые поля:
  - `datasetName` -> `dataset_name`;
  - `rawHash` -> `raw_hash`.

## Границы ответственности

- `policy_ir` сюда не входит; его миграции живут в `polisyos.ir.migrations`;
- `run_manifest` в CLI обрабатывается отдельно и не использует реестр этого пакета.

## Известный интеграционный нюанс

`policy-engine/migrate.py` и `policy-engine/tools/migrations/migrate.py` импортируют `POLICY_IR_CURRENT_VERSION` из `polisyos.common.migrations`, но этот символ здесь не экспортируется. Для версии IR нужно использовать `polisyos.ir.migrations`.

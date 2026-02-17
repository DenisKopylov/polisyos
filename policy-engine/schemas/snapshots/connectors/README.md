# snapshots/connectors — baseline контрактов источников данных

Папка содержит снапшот connector-контрактов для валидации эволюции схем данных источников.

## Роль в системе

- Фиксирует публичные контракты, с которыми работают адаптеры источников данных.
- Позволяет ловить drift и проверять корректность version bump (major/minor/patch) через `SchemaEvolution`.
- Проверяется в CI в `tools/connectors/check_contracts.py --check` (workflow `.github/workflows/arch.yml`).

## Формат `contracts.json`

- `version` — версия формата snapshot файла (текущая: `1`).
- `contracts` — объект вида `{ "<contract_id>": { ...meta... } }`.
- Для каждого контракта хранятся:
  - `connector_id`, `dataset_id`, `schema_version`, `content_hash`;
  - `contract` — нормализованный payload `ConnectorSchemaContract` (без runtime timestamp).

## Актуальное состояние (2026-02-17)

- Количество контрактов: `3`.
- Ключи:
  - `eurostat.data.generic`
  - `ukons.datasets.generic`
  - `worldbank.wdi.generic`
- У всех текущих контрактов `schema_version=1.0.0`.

## Источники и инструменты

- Источник контрактов: `src/polisyos/fabric/connectors/sources/_contracts`.
- Проверка и обновление snapshot: `tools/connectors/check_contracts.py`.

## Локальные команды (из `policy-engine/`)

```bash
python3 tools/connectors/check_contracts.py --check
python3 tools/connectors/check_contracts.py --update
```

## Важно

- Не обновлять `contracts.json` вручную, если можно использовать `--update`.
- Если `SchemaEvolution` требует больший bump версии, это должно быть отражено в контракте до обновления snapshot.

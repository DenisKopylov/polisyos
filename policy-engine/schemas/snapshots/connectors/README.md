# snapshots/connectors — baseline source connector-контрактов

Папка содержит snapshot контрактов источников данных, который используется для проверки drift и корректности version bump.

## Роль в системе

- Фиксирует публичные контракты, на которые опираются source connectors.
- Проверяет эволюцию схем через `SchemaEvolution` (major/minor/patch рекомендации).
- Валидируется в CI (`polisyos-tools connectors check-contracts --check`, workflow `.github/workflows/arch.yml`).

## Формат `contracts.json`

- `version`: версия формата snapshot (`1`).
- `contracts`: объект `{ "<contract_id>": { ...meta... } }`.
- Для каждого контракта сохраняются:
  - `connector_id`, `dataset_id`, `schema_version`, `content_hash`;
  - `contract`: нормализованный `ConnectorSchemaContract` без runtime timestamp (`created_at`).

## Актуальное состояние (2026-03-03)

- Контрактов: `3`.
- Ключи:
  - `eurostat.data.generic`
  - `ukons.datasets.generic`
  - `worldbank.wdi.generic`
- Для всех контрактов текущая версия: `schema_version=1.0.0`.

## Источники и инструменты

- Источник контрактов: `src/polisyos/fabric/connectors/sources/_contracts`.
- Проверка и обновление snapshot: `polisyos-tools connectors check-contracts`.

## Команды (из `policy-engine/`)

```bash
# Проверка (по умолчанию script тоже работает в check-mode)
uv run polisyos-tools connectors check-contracts --check
```

```bash
# Обновление snapshot
uv run polisyos-tools connectors check-contracts --update
```

## Инварианты

- Не редактировать `contracts.json` вручную; использовать `--update`.
- Если `SchemaEvolution` требует большее version bump, сначала обновить `schema_version` в контракте источника, затем обновлять snapshot.

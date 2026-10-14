# snapshots — baseline для контрактных проверок

`snapshots/` содержит коммитный baseline, по которому CI проверяет drift и совместимость ABI/connector-контрактов.

## Структура

В текущем дереве baseline находятся `ir/`, `fabric/` и `connectors/`.
Каталог `scientist/` здесь отсутствует. Это краткая карта основных артефактов,
а не полный список файлов:

- `ir/_manifest.json` и `ir/*.schema.json`;
- `fabric/_manifest.json`, `fabric/*.schema.json` и соседние JSON-артефакты;
- `connectors/contracts.json`.

## Роль подпапок

| Папка                  | Назначение                                                          |
| ---------------------- | ------------------------------------------------------------------- |
| `snapshots/ir`         | ABI JSON Schema для IR-моделей (`src/polisyos/ir/**`)               |
| `snapshots/fabric`     | ABI JSON Schema для enum world-ABI (`src/polisyos/ir/world/abi.py`) |
| `snapshots/connectors` | Baseline source connector-контрактов                                |

## Формат артефактов

- `ir` и `fabric`: schema snapshots и `_manifest.json`, генерируются `tools/quality/diagnostics/gen_schema.py`.
- В `fabric/` также хранятся `connector_contract_registry.json`, `source_contracts_v2.json` и `source_scorecards.json`.
- В текущем snapshot tree нет каталога для versioned Scientist payloads; их runtime serialization behavior не описан этой инвентаризацией.
- IR/Fabric manifests carry per-model compatibility, lifecycle, and hash metadata. Version-variant runtime behavior is outside this snapshot inventory.
- `connectors/contracts.json`: формат `version=1`, payload `contracts` keyed by `contract_id`.

## Канонические источники inventory

Состав и время генерации IR и Fabric baseline задаются соответствующими
`ir/_manifest.json` и `fabric/_manifest.json`; состав connector-контрактов —
`connectors/contracts.json`. Читайте эти tracked artifacts как inventory;
этот README намеренно не дублирует их изменяемые counts и timestamps.

## Команды (из `policy-engine/`)

```bash
# Проверка baseline
python3 tools/quality/diagnostics/gen_schema.py --check
uv run polisyos-tools connectors check-contracts --check
```

```bash
# Обновление baseline
python3 tools/quality/diagnostics/gen_schema.py
uv run polisyos-tools connectors check-contracts --update
```

## Инварианты

- Не редактировать вручную `ir/*.schema.json`, `fabric/*.schema.json` и `_manifest.json`.
- Не редактировать вручную `connectors/contracts.json`; обновлять только через `check_contracts.py --update`.

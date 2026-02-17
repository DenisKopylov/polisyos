# snapshots — baseline контрактов

`snapshots/` хранит коммитные baseline-артефакты, по которым CI проверяет drift и совместимость контрактов.

## Структура

```text
snapshots/
├── ir/
│   ├── _manifest.json
│   └── *.schema.json
├── fabric/
│   ├── _manifest.json
│   └── *.schema.json
└── connectors/
    └── contracts.json
```

## Роль подпапок

| Папка | Назначение |
| --- | --- |
| `snapshots/ir` | ABI JSON Schema для IR-моделей из `src/polisyos/ir` |
| `snapshots/fabric` | ABI JSON Schema для Fabric enum-моделей (`edge_kind`, `node_kind`) |
| `snapshots/connectors` | Снапшот контрактов источников данных connectors layer |

## Форматы

- `ir` и `fabric`: `_manifest.json` + набор `*.schema.json`, генерируются `tools/diagnostics/gen_schema.py`.
- `_manifest.json` содержит `models` (метаданные по каждой ABI модели), `content_hash`, версии генератора/интерпретатора.
- `connectors/contracts.json` содержит `version` и объект `contracts`, где ключ равен `contract_id`.

## Актуальное состояние (2026-02-17)

- `ir`: `32` ABI модели, манифест `generated_at=2026-02-08T18:29:42+00:00`.
- `fabric`: `2` ABI модели, манифест `generated_at=2026-02-07T12:16:56+00:00`.
- `connectors`: `3` контракта (`eurostat.data.generic`, `ukons.datasets.generic`, `worldbank.wdi.generic`).

## Локальные команды (из `policy-engine/`)

```bash
python3 tools/diagnostics/gen_schema.py --check
python3 tools/connectors/check_contracts.py --check
```

```bash
python3 tools/diagnostics/gen_schema.py
python3 tools/connectors/check_contracts.py --update
```

## Инварианты

- Не редактировать вручную `ir/*.schema.json`, `fabric/*.schema.json`, `_manifest.json`.
- Для connector snapshot использовать `check_contracts.py --update`, а не ручные правки JSON.

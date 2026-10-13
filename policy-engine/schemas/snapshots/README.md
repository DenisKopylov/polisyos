# snapshots — baseline для контрактных проверок

`snapshots/` содержит коммитный baseline, по которому CI проверяет drift и совместимость ABI/connector-контрактов.

## Структура

```text
snapshots/
├── ir/
│   ├── _manifest.json
│   └── *.schema.json
├── fabric/
│   ├── _manifest.json
│   └── *.schema.json
├── scientist/
│   ├── _manifest.json
│   └── calibration_validation_bundle_v1_1.schema.json
└── connectors/
    ├── README.md
    └── contracts.json
```

## Роль подпапок

| Папка                  | Назначение                                                          |
| ---------------------- | ------------------------------------------------------------------- |
| `snapshots/ir`         | ABI JSON Schema для IR-моделей (`src/polisyos/ir/**`)               |
| `snapshots/fabric`     | ABI JSON Schema для enum world-ABI (`src/polisyos/ir/world/abi.py`) |
| `snapshots/scientist`  | Versioned persisted Scientist artifact schemas (`src/polisyos/scientist/governance/**`) |
| `snapshots/connectors` | Baseline source connector-контрактов                                |

## Формат артефактов

- `ir`, `fabric` и `scientist`: набор `*.schema.json` + `_manifest.json`, генерируются `tools/quality/diagnostics/gen_schema.py`.
- Для versioned Scientist payloads registry выбирает serialization schema variant только когда запрошенная версия разрешена типизированным source version field; generic model defaults remain unchanged.
- В `_manifest.json` на модель хранятся `priority`, `compat_mode`, `schema_version`, `version_field`, `sha256_full`, `sha256_semantic`; versioned registry entries also record `schema_mode` and `schema_variant_version`.
- `connectors/contracts.json`: формат `version=1`, payload `contracts` keyed by `contract_id`.

## Актуальное состояние (2026-03-03)

- `ir`: `48` моделей, `generated_at=2026-03-03T16:49:25+00:00`.
- `fabric`: `2` модели, `generated_at=2026-03-02T16:48:08+00:00`.
- `connectors`: `3` контракта (`eurostat.data.generic`, `ukons.datasets.generic`, `worldbank.wdi.generic`).

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

- Не редактировать вручную `ir/*.schema.json`, `fabric/*.schema.json`, `scientist/*.schema.json`, `_manifest.json`.
- Не редактировать вручную `connectors/contracts.json`; обновлять только через `check_contracts.py --update`.

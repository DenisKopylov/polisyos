# snapshots/fabric — ABI baseline для enum world-ABI

Папка хранит JSON Schema snapshot для `edge_kind` и `node_kind`, которые используются как стабильная enum-граница для world/fabric интеграций.

## Роль в системе

- Защищает совместимость graph-слоя через те же ABI-gate механизмы, что и `snapshots/ir`.
- Служит baseline для `tools/quality/diagnostics/gen_schema.py --check` в CI.

## Источники данных

- Реестр моделей: `src/polisyos/schemas/abi_models.py` (`module="fabric"`).
- Источник enum-классов: `src/polisyos/ir/world/abi.py`.
- Генератор: `tools/quality/diagnostics/gen_schema.py`.

## Содержимое

- `edge_kind.schema.json`
- `node_kind.schema.json`
- `_manifest.json` (метаданные модели + `sha256_full`/`sha256_semantic`)

## Актуальное состояние (2026-03-03)

- Моделей: `2`.
- `generated_at`: `2026-03-02T16:48:08+00:00`.
- Оба контракта `priority=p0`, `compat_mode=strict`, `version_field=null`.

## Команды (из `policy-engine/`)

```bash
python3 tools/quality/diagnostics/gen_schema.py --models fabric --check
python3 tools/quality/diagnostics/gen_schema.py --models fabric
```

## Инварианты

- Не редактировать вручную схемы и `_manifest.json`.
- Любое изменение enum в `src/polisyos/ir/world/abi.py` должно сопровождаться регенерацией snapshot и прохождением ABI gate.

# snapshots/fabric — ABI снапшоты Fabric enum-моделей

Папка хранит ABI JSON Schema для enum-контрактов world graph в Fabric.

## Роль в системе

- Фиксирует стабильные enum-границы для `node_kind` и `edge_kind`.
- Защищает совместимость world/fabric слоев через те же ABI-gate механизмы, что и IR снапшоты.

## Источники данных

- Реестр моделей: `schemas/abi_models.py` (`module="fabric"`).
- Исходники enum: `src/polisyos/fabric/world/**` (FQN в реестре указывает на `polisyos.ir.world.abi.*`).
- Генератор: `tools/diagnostics/gen_schema.py`.

## Что внутри

- `edge_kind.schema.json`
- `node_kind.schema.json`
- `_manifest.json` с метаданными (`priority`, `compat_mode`, `version_field`, хеши `sha256_*`).

## Актуальное состояние (2026-02-17)

- Количество моделей в манифесте: `2`.
- `generated_at`: `2026-02-07T12:16:56+00:00`.
- Оба контракта имеют `version_field=null`.

## Локальные команды (из `policy-engine/`)

```bash
python3 tools/diagnostics/gen_schema.py --models fabric --check
python3 tools/diagnostics/gen_schema.py --models fabric
```

## Важно

- Не редактировать JSON схемы и `_manifest.json` вручную.
- Любое изменение enum должно сопровождаться регенерацией snapshot и прохождением ABI gate.

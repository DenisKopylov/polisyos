# snapshots/ir — ABI снапшоты IR

Папка содержит ABI JSON Schema для IR-моделей и используется как baseline для semantic diff в `tools/diagnostics/abi_diff.py`.

## Роль в системе

- Фиксирует контракт IR между доменными моделями и потребителями (runtime, пайплайны, аналитика, governance).
- Участвует в PR-gate (`.github/workflows/abi.yml`) и архитектурном gate (`.github/workflows/arch.yml`).

## Источники данных

- Реестр моделей: `schemas/abi_models.py` (`module="ir"`).
- Исходные классы: `src/polisyos/ir/**`.
- Генератор: `tools/diagnostics/gen_schema.py`.

## Что внутри

- `*.schema.json` — JSON Schema по каждой ABI модели.
- `_manifest.json` — метаданные генерации:
  - `models.<abi_key>.schema_file`, `schema_version`, `priority`, `compat_mode`, `version_field`;
  - `sha256_full` и `sha256_semantic` для drift/compatibility анализа.

## Актуальное состояние (2026-02-17)

- Количество моделей в манифесте: `32`.
- `generated_at`: `2026-02-08T18:29:42+00:00`.
- Покрываемые домены: `trinity`, `governance`, `norm-system`, `world/fact log`, `analytics`, `gate`.

## Локальные команды (из `policy-engine/`)

```bash
python3 tools/diagnostics/gen_schema.py --models ir --check
python3 tools/diagnostics/gen_schema.py --models ir
```

```bash
python3 tools/diagnostics/gen_schema.py --output-dir /tmp/current_schemas
python3 tools/diagnostics/abi_diff.py --baseline schemas/snapshots --current /tmp/current_schemas --format markdown
```

## Важно

- Не редактировать файлы в этой директории вручную.
- Любые изменения должны идти через обновление исходных моделей и `gen_schema.py`.

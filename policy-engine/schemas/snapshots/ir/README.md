# snapshots/ir — ABI baseline для IR моделей

Папка содержит JSON Schema snapshot IR-контрактов и используется как baseline в semantic diff (`tools/quality/diagnostics/abi_diff.py`).

## Роль в системе

- Фиксирует публичный ABI между `src/polisyos/ir/**` и потребителями (runtime, пайплайны, аналитика, governance).
- Проверяется в `.github/workflows/abi.yml` и `.github/workflows/arch.yml`.

## Источники

- Реестр: `schemas/abi_models.py` (entries с `module="ir"`).
- Генератор: `tools/quality/diagnostics/gen_schema.py`.
- Проверка совместимости: `tools/quality/diagnostics/abi_diff.py`.

## Что хранится

- `*.schema.json` — схема конкретной ABI-модели.
- `_manifest.json` — индекс моделей и метаданные генерации:
  - `schema_file`, `schema_version`, `priority`, `compat_mode`, `version_field`;
  - `sha256_full` и `sha256_semantic` для drift/compatibility проверки.

## Актуальное состояние (2026-03-03)

- Моделей: `48`.
- `generated_at`: `2026-03-03T16:49:25+00:00`.
- Приоритеты: `p0=16`, `p1=23`, `p2=9`.
- Все модели активные, `compat_mode=strict`.
- `version_field=None` у `certification_result`, `data_view_request`, `outer_search_result`.
- Особенность именования: key `causal_sensitivity_result` соответствует файлу `sensitivity_result.schema.json`.

## Связи и домены

- Trinity/Policy: `trinity_bundle`, `problem_frame`, `policy_spec`, `policy_portfolio`.
- Norm-system: `norm_pack`, `norm_rule`, `norm_ref`.
- World/fact log: `claim`, `conflict_*`, `world_event`, `prov_activity`, `fact*`, `doc_*`.
- Analytics/gate: causal, transportability, calibration, certification, `gate_*`.

## Команды (из `policy-engine/`)

```bash
# Проверка и обновление только IR snapshot
python3 tools/quality/diagnostics/gen_schema.py --models ir --check
python3 tools/quality/diagnostics/gen_schema.py --models ir
```

```bash
# Локальный semantic diff перед PR
python3 tools/quality/diagnostics/gen_schema.py --output-dir /tmp/current_schemas
python3 tools/quality/diagnostics/abi_diff.py \
  --baseline schemas/snapshots \
  --current /tmp/current_schemas \
  --format markdown
```

## Инварианты

- Не редактировать файлы в этой директории вручную.
- Любые изменения проходят через изменение исходных моделей и последующий `gen_schema.py`.

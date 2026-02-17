# tools/diagnostics

Набор диагностических скриптов для ABI-контрактов, воспроизводимости среды, производительности и технических smoke-проверок.

## Роль в системе

- поддержка ABI-совместимости и snapshot-дисциплины;
- проверка контрактов для Scientist/Runtime;
- локальная диагностика окружения, provenance и источников данных.

## Скрипты

| Скрипт | Что делает | Где используется |
|---|---|---|
| `gen_schema.py` | Генерация/проверка ABI snapshots в `schemas/snapshots` | pre-commit, `arch.yml`, `abi.yml` |
| `abi_diff.py` | Семантический diff baseline/current snapshots (`PASS/WARN/FAIL`) | `abi.yml` |
| `check_state_reads.py` | AST-проверка соответствия `state_reads` у Scientist builtin nodes | `arch.yml` |
| `check_scientist_node_version_bump.py` | Требует SemVer bump у измененных builtin-нод (git diff от `--base-ref`) | `arch.yml` |
| `check_perf_regression.py` | Сравнивает benchmark JSON по порогам latency/throughput | `perf.yml` |
| `check_setup.py` | Локальный smoke-check JAX/DuckDB/Pydantic и env-настроек | ручной запуск |
| `capture_env.py` | `capture/compare/validate` для `EnvironmentManifest` | ручной запуск |
| `scan_fabric.py` | Генерация draft data-contracts из DuckDB схем | ручной запуск |
| `visualize_provenance.py` | Валидация/визуализация provenance (core graph, PROV-JSON, CAS, audit package) | ручной запуск |
| `check_udf_perf.py` | UDF perf gate по baseline JSON | legacy, требует актуализации |
| `generate_ir_schema.py` | Deprecated shim, проксирует вызов в `gen_schema.py` | deprecated |

## Входы и выходы

- `schemas/snapshots/*`, `schemas/abi_models.py`
- `data/curated/*`, `data/databases/*` (для data/fabric/UDF сценариев)
- `baseline/*.json` и benchmark JSON-артефакты
- выходы: schema snapshots, markdown/json отчеты, env manifests, provenance DOT/SVG/JSON

## Типовой запуск

```bash
PYTHONPATH=src:. uv run python tools/diagnostics/gen_schema.py --check
PYTHONPATH=src:. uv run python tools/diagnostics/check_state_reads.py
PYTHONPATH=src:. uv run python tools/diagnostics/check_scientist_node_version_bump.py --base-ref origin/main
PYTHONPATH=src:. uv run python tools/diagnostics/abi_diff.py --baseline /tmp/baseline --current /tmp/current --format markdown
```

## Известные ограничения

- В кодовой базе отсутствуют `polisyos.fabric.udf.*` и `polisyos.fabric.io.graph_store`; поэтому `check_udf_perf.py` не соответствует текущей структуре `src/polisyos`.
- `generate_ir_schema.py` поддерживается только как совместимый алиас к `gen_schema.py`.

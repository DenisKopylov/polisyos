# tools/diagnostics

Диагностический слой для контрактов, качества и verification-отчетов. Папка объединяет как CI-gates, так и ручные инженерные проверки.

## Роль в системе

- Контроль ABI/Schema drift и SemVer дисциплины.
- Проверка архитектурных контрактов Scientist/Foundry/Runtime.
- Формирование verification evidence/matrix (включая SCM v3 full-spec отчеты).
- Локальная диагностика окружения, provenance и data contracts.

## Скрипты

| Скрипт | Назначение | Контур |
|---|---|---|
| `gen_schema.py` | Генерация/проверка ABI snapshots в `schemas/snapshots` | `pre-commit`, `arch.yml`, `abi.yml` |
| `abi_diff.py` | Семантический diff baseline/current snapshots (`PASS/WARN/FAIL`) | `abi.yml` |
| `check_state_reads.py` | AST-проверка соответствия `state_reads` у Scientist builtin nodes | `arch.yml` |
| `check_scientist_node_version_bump.py` | Требует SemVer bump для измененных builtin-нод (`--base-ref`) | `arch.yml` |
| `check_perf_regression.py` | Сравнение benchmark JSON по порогам latency/throughput | `perf.yml` |
| `verify_scm_v3.py` | Прогон quick/full набора SCM v3 checks, генерация evidence/matrix + logs | manual verification |
| `verify_scm_v3_fullspec.py` | Full-spec матрица DoD/Laws/SL на базе `verify_scm_v3.py`, синхронизация canonical отчетов | manual verification |
| `check_setup.py` | Локальный smoke-check JAX/DuckDB/Pydantic и env настроек | local |
| `capture_env.py` | `capture/compare/validate` для `EnvironmentManifest` | local |
| `scan_fabric.py` | Генерация draft data-contracts из DuckDB схем | local |
| `visualize_provenance.py` | Валидация/визуализация provenance (core graph, PROV-JSON, CAS, audit package) | local |
| `check_udf_perf.py` | UDF perf gate по baseline JSON | legacy |
| `generate_ir_schema.py` | Deprecated shim: проксирует вызов в `gen_schema.py` | deprecated |

## Связи с репозиторием

- `src/polisyos/*`: runtime-контракты, builtin-ноды, артефактные модели.
- `schemas/snapshots/*`, `schemas/abi_models.py`: входы/выходы ABI слоя.
- `docs/reports/*`: основная точка вывода verification отчетов (SCM v3 evidence/matrix + logs).
- `data/curated/*`, `data/databases/*`: входы для fabric/UDF локальных проверок.
- `baseline/*.json` и benchmark artifacts: входы perf-regression сценариев.

## Типовой запуск

```bash
PYTHONPATH=src:. uv run --extra ml python tools/diagnostics/gen_schema.py --check
PYTHONPATH=src:. uv run python tools/diagnostics/abi_diff.py --baseline /tmp/baseline --current /tmp/current --format markdown
PYTHONPATH=src:. uv run python tools/diagnostics/check_state_reads.py
PYTHONPATH=src:. uv run python tools/diagnostics/check_scientist_node_version_bump.py --base-ref origin/main
PYTHONPATH=src:. uv run python tools/diagnostics/verify_scm_v3.py --profile quick --output-dir docs/reports
PYTHONPATH=src:. uv run python tools/diagnostics/verify_scm_v3_fullspec.py --output-dir docs/reports
```

## Известные ограничения

- В кодовой базе отсутствуют `polisyos.fabric.udf.*` и `polisyos.fabric.io.graph_store`; поэтому `check_udf_perf.py` сейчас не соответствует текущей структуре `src/polisyos`.
- `generate_ir_schema.py` оставлен только как backward-compatible alias к `gen_schema.py`.

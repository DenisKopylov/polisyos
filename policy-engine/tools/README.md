# Tools — инженерные CLI-инструменты Policy Engine

`tools/` — это набор standalone-скриптов для обслуживания и развития `policy-engine`:

- архитектурные и quality-гейты;
- проверки ABI/JSON Schema;
- runtime-операции (OpenAPI, клиент, архивация legacy run-ов);
- миграции данных;
- демо и бенчмарки.

Ключевое правило: зависимость однонаправленная, `tools/* -> src/polisyos/*`.

## Роль в системе

```text
src/polisyos/*     (доменный код, контракты, runtime)
      ^
      |  потребление API, валидации, генерация артефактов
      |
tools/*            (CLI-инструменты для разработки и CI)
```

`tools/` не является runtime-слоем приложения; это операционный слой для команды и CI/CD.

## Как запускать локально

Рабочая директория: `policy-engine/`.

Рекомендуемый формат запуска из исходников:

```bash
PYTHONPATH=src:. uv run python tools/<subdir>/<script>.py --help
```

Если окружение уже установлено как editable-пакет (как в CI), используется `python3 tools/...`.

## Связь с другими директориями

| Путь | Как используется `tools/` |
|---|---|
| `src/polisyos/*` | Основные импорты для линтеров, диагностики, runtime-утилит и демо |
| `schemas/snapshots/*` | Генерация и проверка ABI-снимков (`gen_schema.py`, `abi_diff.py`) |
| `schemas/runtime_api_v1.openapi.json` | Экспорт OpenAPI и генерация runtime-клиента |
| `frontend/runtime-api-client/*` | Целевая директория для `generate_runtime_client.py` |
| `tests/fabric/connectors/sources/*` | Генерируемые тесты из `tools/connectors/scaffold.py` |
| `data/curated`, `data/databases` | Источники для `scan_fabric.py`, UDF-диагностики/демо |
| `runs/*` | Инвентаризация и архивация legacy run-ов (`tools/runtime/*`) |
| `import_policy.toml`, `import_exceptions.toml`, `baseline/*` | Входы для import-gate и freeze-сравнений (`tools/lint/*`) |

## Каталог модулей

### `lint/`

| Скрипт | Назначение | Статус |
|---|---|---|
| `lint_imports.py` | Главный import-gate (ARCH00x), циклы, исключения из `import_exceptions.toml` | CI + pre-commit |
| `lint_foundry.py` | Запрет нежелательных импортов/встроек в `foundry` (политики standard/mixed/no_jax) | CI |
| `lint_connectors.py` | Проверка изоляции `fabric/connectors` от `scientist`/`foundry` | Manual/metrics |
| `lint_connector_hardening.py` | P7 hardening для production-коннекторов (`world_bank`, `eurostat`, `ukons`) | CI |
| `lint_foundry_data_plane.py` | P8 invariants (workflow aliases, fabric adapter, state snapshot assumptions) | Manual |
| `lint_legacy_cutover.py` | P10 invariants для удаления legacy runtime/facade fallback | Manual |
| `check_scholar_imports.py` | Запрет зависимостей `scholar -> polisyos.fabric.io.db` | CI |
| `collect_arch_metrics.py` | Сбор freeze-метрик (`summary.json`, `import_gate.txt`, `ruff_stats.txt` и т.д.) | CI |
| `compare_baseline.py` | Сравнение baseline/current, контроль exception policy и deep-import drift | CI |

### `diagnostics/`

| Скрипт | Назначение | Статус |
|---|---|---|
| `check_setup.py` | Smoke-check окружения (JAX, DuckDB, Pydantic, config) | Manual |
| `gen_schema.py` | Генерация/проверка ABI snapshots по реестру `schemas/abi_models.py` | CI + pre-commit |
| `abi_diff.py` | Семантический diff baseline/current snapshots, вердикт PASS/WARN/FAIL | CI |
| `capture_env.py` | `capture/compare/validate` для `EnvironmentManifest` | Manual |
| `check_perf_regression.py` | Сравнение benchmark JSON (latency/throughput thresholds) | CI |
| `check_state_reads.py` | AST-check соответствия `state_reads` у Scientist builtin nodes | CI |
| `check_scientist_node_version_bump.py` | Проверка SemVer bump у измененных builtin-ноды в git diff | CI |
| `scan_fabric.py` | Генерация draft data-contracts из DuckDB схем | Manual |
| `visualize_provenance.py` | Проверка/визуализация provenance (core graph, PROV-JSON, CAS, audit package) | Manual |
| `check_udf_perf.py` | UDF perf gate (panel/snapshot/network) по baseline JSON | Legacy/needs update |
| `generate_ir_schema.py` | Deprecated shim, проксирует вызов в `gen_schema.py` | Deprecated |

### `connectors/`

| Скрипт | Назначение | Статус |
|---|---|---|
| `scaffold.py` | Генерация каркаса нового коннектора + теста (`REST/CSV/SQL/SDMX`) | Manual |
| `check_contracts.py` | Валидация и snapshot-check контрактов коннекторов | CI |

### `runtime/`

| Скрипт | Назначение | Статус |
|---|---|---|
| `export_runtime_openapi.py` | Экспорт OpenAPI Runtime API v1 в детерминированный JSON | Manual/Release |
| `generate_runtime_client.py` | Генерация TS/JS runtime API клиента из OpenAPI | Manual/Release |
| `inventory_legacy_runs.py` | Инвентаризация `runs/<id>/manifest.json` перед cutover | Manual/Ops |
| `archive_legacy_runs.py` | Детерминированный tar.gz архив `runs/` + JSON report | Manual/Ops |

### `migrations/`

| Скрипт | Назначение | Статус |
|---|---|---|
| `migrate_duckdb_to_pg.py` | Перенос tenant-scoped таблиц DuckDB -> PostgreSQL | Manual/Ops |
| `migrate.py` | Миграция артефактов (`policy_ir`, `dataset_manifest`, `run_manifest`) | Legacy/needs update |

### `demos/` и `benchmarks/`

| Скрипт | Назначение | Статус |
|---|---|---|
| `demos/run_export_demo.py` | Тест записи simulation-данных в DuckDB | Demo |
| `demos/run_udf_query_demo.py` | Пример panel/snapshot UDF-запросов | Demo |
| `demos/run_udf_hybrid_demo.py` | DuckDB + graph UDF сценарий | Demo/legacy |
| `demos/run_laffer_demo.py` | JAX/Optax demo кривой Лаффера | Demo |
| `demos/run_mechanism_design.py` | E2E differentiable mechanism design (IR -> compile -> execute -> grad) | Demo |
| `benchmarks/bench_domain.py` | JAX проверка доменной модели | Benchmark |
| `benchmarks/bench_simulation.py` | JAX benchmark simulation loop | Benchmark |

## Что реально подключено в CI

- Pre-commit: `tools/lint/lint_imports.py`, `tools/diagnostics/gen_schema.py --check`.
- `/.github/workflows/arch.yml`:
  - `lint_imports.py`, `lint_foundry.py`, `check_state_reads.py`,
  - `check_scientist_node_version_bump.py`, `check_scholar_imports.py`,
  - `check_contracts.py --check`, `gen_schema.py --check`.
- `/.github/workflows/abi.yml`:
  - `gen_schema.py` (generate/check), `abi_diff.py`.
- `/.github/workflows/arch-freeze.yml`:
  - `lint_connector_hardening.py`, `collect_arch_metrics.py`, `compare_baseline.py`.
- `/.github/workflows/perf.yml`:
  - `check_perf_regression.py`.

## Актуальные ограничения и дрейф

- `tools/diagnostics/check_udf_perf.py` и `tools/demos/run_udf_hybrid_demo.py` ожидают `polisyos.fabric.io.graph_store`, которого сейчас нет в `src/polisyos/fabric/io`.
- `tools/migrations/migrate.py` импортирует `POLICY_IR_CURRENT_VERSION` из `polisyos.common.migrations`, но в текущем коде экспортируется только `MANIFEST_CURRENT_VERSION`; скрипт требует актуализации.
- `tools/diagnostics/generate_ir_schema.py` оставлен как deprecated compatibility shim.
- `bench_domain.py` и `bench_simulation.py` не принимают CLI-аргументы (фиксированные параметры внутри кода).
- Для `check_scientist_node_version_bump.py` актуальный флаг: `--base-ref` (не `--base`).

## Минимальный локальный gate перед PR

```bash
PYTHONPATH=src:. uv run python tools/lint/lint_imports.py --policy import_policy.toml --exceptions import_exceptions.toml
PYTHONPATH=src:. uv run python tools/lint/lint_foundry.py --repo-root .
PYTHONPATH=src:. uv run python tools/diagnostics/check_state_reads.py
PYTHONPATH=src:. uv run python tools/diagnostics/check_scientist_node_version_bump.py --base-ref origin/main
PYTHONPATH=src:. uv run python tools/lint/check_scholar_imports.py
PYTHONPATH=src:. uv run python tools/connectors/check_contracts.py --check
PYTHONPATH=src:. uv run python tools/diagnostics/gen_schema.py --check
```

# Tools — Инструменты разработчика Policy Engine

Standalone CLI-утилиты для обеспечения качества, диагностики, бенчмаркинга и демонстрации возможностей Policy Engine. Инструменты **потребляют** публичные API основного фреймворка, но никогда не импортируются из него — зависимость строго однонаправленная.

## Роль в системе

```
polisyos.*  (source)          tools/  (consumers)
  core   ←──────────────────  lint_imports, capture_env, visualize_provenance
  fabric ←──────────────────  lint_connectors, scan_fabric, demos/*, diagnostics/*
  foundry ←─────────────────  lint_foundry, benchmarks/*, run_mechanism_design
  ir     ←──────────────────  gen_schema, abi_diff, demos/*
  common ←──────────────────  migrate, benchmarks/*, diagnostics/check_setup
```

Инструменты не являются Python-пакетом (`__init__.py` отсутствует) — каждый скрипт запускается напрямую через `python tools/<script>.py`. Путь к `src/` добавляется через `sys.path.insert` внутри каждого скрипта.

## Структура

```
tools/
├── abi_diff.py                            # Семантический diff ABI-схем
├── capture_env.py                         # Захват/сравнение Environment Manifest
├── check_perf_regression.py               # Детекция регрессий pytest-benchmark
├── check_scientist_node_version_bump.py   # Проверка version bump в PR
├── check_state_reads.py                   # AST-анализ обращений к state
├── gen_schema.py                          # Pydantic → JSON Schema snapshots
├── lint_connectors.py                     # Линтер коннекторов (Законы A, E)
├── lint_foundry.py                        # Линтер чистоты foundry (Закон B)
├── lint_imports.py                        # Валидатор межмодульных импортов (Закон A)
├── migrate.py                             # Универсальная миграция артефактов
├── run_mechanism_design.py                # E2E дифференцируемый mechanism design
├── scan_fabric.py                         # DuckDB → data contracts bootstrap
├── visualize_provenance.py                # Визуализация и верификация provenance-графов
│
├── benchmarks/
│   ├── bench_domain.py                    # JAX доменная модель — масштабируемость
│   └── bench_simulation.py                # Полный симуляционный пайплайн
│
├── connectors/
│   └── scaffold.py                        # Генератор скелетов коннекторов
│
├── demos/
│   ├── run_udf_query_demo.py              # Гибридные SQL + Python UDF-запросы
│   ├── run_udf_hybrid_demo.py             # Продвинутые UDF с ML/статистикой
│   ├── run_laffer_demo.py                 # Кривая Лаффера — экономическая модель
│   └── run_export_demo.py                 # Экспорт в Parquet/JSON/CSV/HDF5
│
└── diagnostics/
    ├── check_setup.py                     # Smoke-тест всех компонентов системы
    ├── check_perf_regression.py           # Расширенный анализ регрессий
    ├── check_udf_perf.py                  # Профилирование UDF-запросов
    └── generate_ir_schema.py              # DEPRECATED shim → gen_schema.py
```

## Быстрый старт

```bash
cd policy-engine/

# 1. Проверка что всё установлено
python tools/diagnostics/check_setup.py

# 2. Архитектурные проверки
python tools/lint_imports.py
python tools/lint_foundry.py
python tools/lint_connectors.py

# 3. Валидация ABI-схем
python tools/gen_schema.py --check

# 4. Запуск демо
python tools/demos/run_udf_query_demo.py
```

## Архитектурные линтеры

Линтеры обеспечивают соблюдение пяти архитектурных законов Policy Engine через статический анализ AST.

### lint_imports.py — Закон A: направленный граф зависимостей

Анализирует все Python-файлы проекта, строит граф импортов и выявляет запрещённые обратные зависимости. Поддерживает конфигурируемые исключения и детальные отчёты о нарушениях.

```bash
python tools/lint_imports.py              # базовая проверка
python tools/lint_imports.py --verbose    # с детализацией нарушений
```

Ключевые типы: `ImportRef`, `PolicyConfig`, `ImportException`, `Violation`.

### lint_foundry.py — Закон B: чистота математического ядра

Запрещает IO/БД/сетевые импорты в `foundry/` — математическое ядро должно оставаться чистым и пригодным для JIT-компиляции.

```bash
python tools/lint_foundry.py --verbose
```

### lint_connectors.py — Законы A и E: изоляция коннекторов

Проверяет что коннекторы данных (`fabric/connectors/`) не нарушают границы слоёв и включают provenance tracking.

```bash
python tools/lint_connectors.py --verbose
```

## Управление схемами и ABI

### gen_schema.py — Закон C: контракты как источник истины

Генерирует детерминированные JSON Schema snapshots из Pydantic-моделей реестра. В режиме `--check` служит CI-гейтом — если snapshot-файлы не совпадают с текущим кодом, сборка падает.

```bash
python tools/gen_schema.py                        # генерация snapshots
python tools/gen_schema.py --check                # CI: валидация актуальности
python tools/gen_schema.py --output-dir /tmp/out  # кастомный output
```

### abi_diff.py — семантический diff ABI-схем

Сравнивает baseline и current snapshots, классифицирует изменения как breaking/non-breaking, проверяет правила version bump. Самый крупный инструмент (853 строки).

```bash
python tools/abi_diff.py \
  --baseline schemas/snapshots \
  --current /tmp/current_schemas \
  --output /tmp/abi_report.json \
  --format github
```

Ключевые типы: `ChangeKind`, `ModelSnapshot`, `SchemaChange`, `DiffReport`.

## Воспроизводимость и аудит

### capture_env.py — Закон D: Environment Manifest

CLI с тремя командами: `capture` (снимок окружения), `compare` (diff двух снимков), `validate` (проверка корректности манифеста).

```bash
python -m tools.capture_env capture --output env.json
python -m tools.capture_env compare baseline.json current.json
```

Интеграция: `core.artifacts.environment.EnvironmentManifest`.

### check_perf_regression.py — Закон D: регрессионное тестирование

Анализирует JSON-результаты pytest-benchmark, находит ближайший baseline и выявляет регрессии выше заданного порога.

```bash
python tools/check_perf_regression.py results.json --threshold 0.05
```

### migrate.py — миграция артефактов

Универсальная миграция для типов артефактов: `dataset_manifest`, `policy_ir`, `run_manifest`.

```bash
python tools/migrate.py policy_ir old.json new.json --to v2.5.0
```

Интеграция: `common.migrations.migrate_artifact`.

## Статический анализ кода

### check_state_reads.py — анализ обращений к state

AST-based инструмент, который сканирует файлы `foundry/` и определяет какие ключи `state.*` читает каждый модуль. Используется для минимизации контрактов зависимостей между компонентами.

Ключевые типы: `ReadRequirements`, `_StateReadVisitor`.

### check_scientist_node_version_bump.py — контроль версий в PR

Проверяет что при изменении builtin-файлов scientist-нод в PR присутствует соответствующий version bump в `ComponentId`. Предназначен для использования в CI при проверке pull requests.

```bash
python tools/check_scientist_node_version_bump.py --base main
```

## Provenance и data contracts

### visualize_provenance.py — Закон E: визуализация provenance-графов

Загружает provenance-граф (JSON или CAS-ссылка), выполняет верификацию целостности (orphaned nodes, dangling references, циклы в `wasDerivedFrom`) и экспортирует в Graphviz DOT или JSON.

```bash
python tools/visualize_provenance.py evidence.json --verify
python tools/visualize_provenance.py evidence.json --format dot | dot -Tpng -o graph.png
python tools/visualize_provenance.py prov.json --cas-root .polisyos --format json
```

Интеграция: `core.artifacts.ids.ArtifactID`, `core.artifacts.store.FileSystemCAS`, `core.audit.prov_json`.

### scan_fabric.py — bootstrap data contracts

Сканирует DuckDB-файлы, извлекает схему таблиц и генерирует черновик data contracts для `fabric.catalog`. Полезен при первоначальной интеграции новых источников данных.

```bash
python tools/scan_fabric.py data/ --output contracts.json
```

## Бенчмарки (`benchmarks/`)

Два бенчмарка для регрессионного тестирования производительности foundry.

| Скрипт | Что тестирует | Ключевые метрики |
|--------|--------------|------------------|
| `bench_domain.py` | `GlobalState` аллокация, JIT-компиляция, векторизованные операции | Память, время JIT, ms/step |
| `bench_simulation.py` | Полный экономический цикл через `SimulationKernel` | steps/sec, agent-steps/sec, GDP/unemployment |

```bash
python tools/benchmarks/bench_domain.py --n-agents 1000000
python tools/benchmarks/bench_simulation.py --n-steps 100 --n-agents 10000
```

Зависимости: `foundry.domain.state.GlobalState`, `foundry.engine.kernel.SimulationKernel`, JAX, Equinox.

## Генератор коннекторов (`connectors/`)

### scaffold.py — скелет нового коннектора

Генерирует source-файл и тест для нового коннектора данных по выбранному типу: **REST**, **CSV**, **SQL**, **SDMX**. Сгенерированный код сразу проходит `ConnectorTestHarness`.

```bash
python tools/connectors/scaffold.py create --name WorldBankData --type REST
# → src/polisyos/fabric/connectors/sources/world_bank_data.py
# → tests/fabric/connectors/sources/test_world_bank_data.py

python tools/connectors/scaffold.py create --name CensusData --type CSV --dry-run
```

Интеграция: `fabric.connectors.base.BaseConnector`, `fabric.connectors.testing.ConnectorTestHarness`, `ir.connectors`.

## Демонстрации (`demos/`)

End-to-end скрипты, демонстрирующие ключевые пайплайны Policy Engine. Каждый скрипт самодостаточен и генерирует необходимые тестовые данные.

| Скрипт | Пайплайн | Основные модули |
|--------|----------|----------------|
| `run_udf_query_demo.py` | Panel/Snapshot/Network UDF-запросы | `fabric.udf.engine`, `ir.data_views` |
| `run_udf_hybrid_demo.py` | ML/статистика внутри SQL через UDF | DuckDB UDF API, Pandas, NumPy |
| `run_laffer_demo.py` | Кривая Лаффера — tax rate vs revenue | `foundry.domain`, `foundry.engine` |
| `run_export_demo.py` | Экспорт state в Parquet/JSON/CSV/HDF5 | `foundry.domain.state`, `foundry.engine.kernel` |

`run_mechanism_design.py` (в корне tools) — отдельная E2E демонстрация дифференцируемого mechanism design через JAX-градиенты. Использует `core.contracts.foundry`, `foundry.compile.api`, `ir.kernel`.

## Диагностика (`diagnostics/`)

| Скрипт | Назначение | CI-роль |
|--------|-----------|---------|
| `check_setup.py` | Smoke-тест: JAX, Pydantic v2, DuckDB, Kuzu, все модули polisyos | Quality gate |
| `check_perf_regression.py` | Расширенный анализ регрессий с автоматическим поиском baseline | Nightly |
| `check_udf_perf.py` | Профилирование UDF: latency, throughput, DuckDB vs Kuzu | Performance gate |
| `generate_ir_schema.py` | **DEPRECATED** — shim, проксирует в `tools/gen_schema.py` | — |

```bash
python tools/diagnostics/check_setup.py    # первая команда при настройке окружения
```

## Матрица архитектурных законов

| Закон | Описание | Инструменты |
|-------|---------|-------------|
| **A** | Направленный граф зависимостей (только внутрь) | `lint_imports.py`, `lint_connectors.py` |
| **B** | Чистота математического ядра foundry (без IO) | `lint_foundry.py` |
| **C** | Контракты — источник истины (Pydantic + JSON Schema) | `gen_schema.py`, `abi_diff.py` |
| **D** | Воспроизводимость и аудит | `capture_env.py`, `check_perf_regression.py`, `migrate.py` |
| **E** | Evidence и provenance обязательны | `visualize_provenance.py`, `scan_fabric.py`, `lint_connectors.py` |

## CI/CD интеграция

Рекомендуемый pipeline:

```yaml
# Quality gate (каждый PR)
- python tools/diagnostics/check_setup.py
- python tools/lint_imports.py
- python tools/lint_foundry.py
- python tools/lint_connectors.py
- python tools/gen_schema.py --check
- python tools/check_scientist_node_version_bump.py --base main

# Performance (nightly)
- python tools/check_perf_regression.py results.json --threshold 0.05
- python tools/benchmarks/bench_domain.py --n-agents 1000000
- python tools/benchmarks/bench_simulation.py --n-steps 100 --n-agents 10000

# Smoke tests (integration)
- python tools/demos/run_udf_query_demo.py
```

## Troubleshooting

```bash
# PYTHONPATH — если ImportError при запуске инструмента
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"

# JAX Metal на macOS — если зависает или segfault
export POLICY_ENGINE_ALLOW_JAX_METAL=0

# Schema drift — перегенерация ABI snapshots
python tools/gen_schema.py && python tools/gen_schema.py --check

# Детальный вывод любого линтера
python tools/lint_imports.py --verbose
```

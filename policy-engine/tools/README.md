# Tools - Инструменты разработчика Policy Engine

Коллекция утилит для разработки, тестирования, диагностики и демонстрации Policy Engine. Инструменты обеспечивают соблюдение архитектурных законов и предоставляют полный спектр возможностей от линтинга кода до end-to-end демонстраций политик.

## Структура папки

```
tools/
├── benchmarks/                 # Бенчмарки производительности
│   ├── bench_domain.py         # Тест доменной модели (JAX + Equinox)
│   └── bench_simulation.py     # Тест полного симуляционного пайплайна
├── connectors/                 # Инструменты для коннекторов данных
│   └── scaffold.py             # Генератор скелетов коннекторов
├── demos/                      # Демонстрационные скрипты
│   ├── run_ingest_demo.py      # Полный ingestion пайплайн
│   ├── run_udf_query_demo.py   # UDF запросы к Unified Data Fabric
│   ├── run_optimizer_demo.py   # Оптимизация политик (NSGA-II)
│   ├── run_laffer_demo.py      # Кривая Лаффера
│   ├── run_udf_hybrid_demo.py  # Гибридные SQL + Python запросы
│   └── run_export_demo.py      # Экспорт симуляционных данных
├── diagnostics/                # Диагностика и анализ системы
│   ├── check_setup.py          # Комплексная проверка установки
│   ├── check_udf_perf.py       # Профилирование UDF производительности
│   ├── check_perf_regression.py# Проверка регрессий производительности
│   └── generate_ir_schema.py   # DEPRECATED wrapper -> tools/gen_schema.py
├── capture_env.py              # Захват Environment Manifest
├── check_perf_regression.py    # Проверка регрессий производительности
├── abi_diff.py                 # Семантический diff ABI schema snapshots
├── gen_schema.py               # Генератор JSON Schema из Pydantic
├── lint_connectors.py          # Линтер коннекторов данных
├── lint_foundry.py             # Архитектурный линтер foundry
├── lint_imports.py             # Линтер межмодульных зависимостей
├── migrate.py                  # Универсальная миграция артефактов
├── migrate_ir.py               # Миграция Policy IR
├── migrate_to_trinity.py       # Миграция в Trinity формат
├── run_mechanism_design.py     # Демонстрация механизма дизайна
├── scan_fabric.py              # Сканер DuckDB и генератор data contracts
└── visualize_provenance.py     # Визуализация provenance графов
```

## Быстрый старт

```bash
cd policy-engine/

# Системная диагностика
python tools/diagnostics/check_setup.py

# Архитектурный линтинг
python tools/lint_imports.py
python tools/lint_foundry.py

# Генерация и валидация схем
python tools/gen_schema.py --check

# Демонстрации
python tools/demos/run_ingest_demo.py
python tools/run_mechanism_design.py

# Бенчмарки
python tools/benchmarks/bench_domain.py
```

## Архитектурные линтеры

### lint_imports.py - Линтер межмодульных зависимостей
Проверяет **Закон A** - направленный граф зависимостей только внутрь. Анализирует все Python файлы, строит граф импортов, выявляет запрещенные обратные зависимости и циклы.

```bash
python tools/lint_imports.py --verbose
```

### lint_foundry.py - Линтер foundry модуля
Обеспечивает **Закон B** - чистоту математического ядра. Запрещает импорты IO/БД/сетевых библиотек в foundry.

```bash
python tools/lint_foundry.py --verbose
```

### lint_connectors.py - Линтер коннекторов данных
Проверяет **Законы A и E** - архитектурную изоляцию и provenance tracking в коннекторах данных.

```bash
python tools/lint_connectors.py --verbose
```

## Генерация схем

### gen_schema.py - Генератор JSON Schema
Генерирует и валидирует ABI snapshots из Pydantic/Enum реестра согласно **Закону C** (контракты - источник истины).

```bash
# Генерация snapshots для всех ABI моделей
python3 tools/gen_schema.py

# Валидация (CI gate)
python3 tools/gen_schema.py --check
```

### abi_diff.py - Семантический ABI diff
Сравнивает baseline/current snapshots, классифицирует breaking/non-breaking изменения и проверяет version bump правила.

```bash
python3 tools/abi_diff.py \
  --baseline schemas/snapshots \
  --current /tmp/current_schemas \
  --output /tmp/abi_report.json \
  --format github
```

## Захват окружения

### capture_env.py - Environment Manifest
Захватывает, сравнивает и валидирует Environment Manifest согласно **Закону D** (воспроизводимость и аудит).

```bash
# Захват окружения
python -m tools.capture_env capture --output env.json

# Сравнение с baseline
python -m tools.capture_env compare baseline.json current.json
```

## Проверка регрессий производительности

### check_perf_regression.py - Анализ регрессий
Анализирует результаты pytest-benchmark и выявляет регрессии производительности согласно **Закону D**.

```bash
# Проверка с автоматическим baseline
python tools/check_perf_regression.py results.json

# С кастомным threshold
python tools/check_perf_regression.py results.json --threshold 0.10
```

## Миграции

### migrate_ir.py - Миграция Policy IR
Детерминированные миграции Policy IR между версиями согласно **Закону C**.

```bash
python tools/migrate_ir.py input.json output.json --to v3.0.0
```

### migrate.py - Универсальная миграция
Миграция различных артефактов: dataset_manifest, policy_ir, run_manifest.

```bash
python tools/migrate.py policy_ir old.json new.json --to v2.5.0
```

### migrate_to_trinity.py - Миграция в Trinity формат
Конвертация PolicySurfaceIR в Trinity bundle (ProblemFrame, PolicySpec, ModelSpec).

```bash
python tools/migrate_to_trinity.py policies/ --backup --verify
```

## Диагностика

### check_setup.py - Системная проверка
Комплексный smoke test всех компонентов Policy Engine.

```bash
python tools/diagnostics/check_setup.py
```

### check_udf_perf.py - Профилирование UDF
Анализ производительности пользовательских функций в Unified Data Fabric.

```bash
python tools/diagnostics/check_udf_perf.py
```

### generate_ir_schema.py - Генерация IR схем
DEPRECATED. Скрипт сохранён как shim для обратной совместимости и проксирует вызов в `tools/gen_schema.py`.

```bash
python3 tools/diagnostics/generate_ir_schema.py --check
```

## Бенчмарки

### bench_domain.py - Доменная модель
Тестирование масштабируемости JAX доменной модели foundry.

```bash
python tools/benchmarks/bench_domain.py --n-agents 1000000
```

### bench_simulation.py - Симуляционное ядро
Полносистемный бенчмарк симуляционного пайплайна.

```bash
python tools/benchmarks/bench_simulation.py --n-steps 100 --n-agents 10000
```

## Демонстрации

### run_ingest_demo.py - Ingestion пайплайн
Полная демонстрация Unified Data Fabric ingestion: CSV → DuckDB + Kuzu.

```bash
python tools/demos/run_ingest_demo.py
```

### run_udf_query_demo.py - UDF запросы
Гибридные SQL + Python запросы к Unified Data Fabric.

```bash
python tools/demos/run_udf_query_demo.py
```

### run_optimizer_demo.py - Оптимизация политик
Многокритериальная оптимизация с PyMOO NSGA-II.

```bash
python tools/demos/run_optimizer_demo.py
```

### run_laffer_demo.py - Кривая Лаффера
Экономическая демонстрация зависимости доходов от налоговой ставки.

```bash
python tools/demos/run_laffer_demo.py
```

### run_mechanism_design.py - Дифференцируемый механизм дизайна
End-to-end оптимизация политик через JAX градиенты.

```bash
python tools/run_mechanism_design.py
```

### run_export_demo.py - Экспорт данных
Экспорт симуляционных результатов в Parquet, JSON, CSV, HDF5.

```bash
python tools/demos/run_export_demo.py
```

### scan_fabric.py - Генератор data contracts
Сканирование DuckDB и автоматическая генерация data contracts.

```bash
python tools/scan_fabric.py data/ --output contracts.json
```

### visualize_provenance.py - Визуализация provenance
Визуализация и верификация provenance графов согласно Закону E.

```bash
python tools/visualize_provenance.py evidence.json --verify
```

### visualize_provenance.py - Визуализация и верификация provenance графов

Инструмент для визуализации и верификации provenance графов согласно **Закону E** ("Evidence и provenance обязательны"). Позволяет анализировать происхождение данных, выявлять проблемы в графах зависимостей и генерировать визуализации для отладки.

**Функциональность:**

**Загрузка графов:**
- Загрузка из файлов JSON или evidence bundles
- Разрешение provenance_ref через CAS систему
- Поддержка различных форматов хранения

**Верификация целостности:**
- Проверка на orphaned nodes (узлы без связей)
- Выявление dangling references (ссылки на несуществующие узлы)
- Детекция циклов в wasDerivedFrom отношениях
- Валидация всех обязательных полей

**Визуализация:**
- Экспорт в Graphviz DOT формат для визуализации
- Цветовое кодирование по типам узлов (entities, activities, agents)
- Стилизация отношений (derived, generated, used, attributed, associated)
- Генерация PNG/SVG через Graphviz

**Экспорт:**
- JSON дамп графов с форматированием
- DOT файлы для Graphviz визуализации
- Поддержка stdout и файлового вывода

```bash
# Генерация DOT файла из evidence bundle
python tools/visualize_provenance.py evidence.json --format dot > graph.dot
dot -Tpng graph.dot -o graph.png

# Верификация графа с CAS разрешением
python tools/visualize_provenance.py provenance.json --cas-root .polisyos --verify

# Экспорт в JSON формат
python tools/visualize_provenance.py graph.json --format json --output graph_pretty.json
```

**Типы отношений в provenance:**
- `wasDerivedFrom` - трансформация данных (синие сплошные линии)
- `wasGeneratedBy` - генерация данных активностью (зеленые пунктирные)
- `used` - использование данных активностью (оранжевые точечные)
- `wasAttributedTo` - атрибуция агенту (фиолетовые сплошные)
- `wasAssociatedWith` - ассоциация агента с активностью (фиолетовые пунктирные)

**Интеграция с модулями:**
- `polisyos.core.artifacts.ids.ArtifactID` - идентификаторы артефактов
- `polisyos.core.artifacts.store.FileSystemCAS` - Content Addressable Storage
- JSON Schema валидация provenance структур

**Примеры вывода верификации:**
```
VERIFICATION FAILED:
  - ORPHANED: Node 'data_entity_123' not connected to any edge
  - DANGLING: Edge source 'activity_456' not found in nodes
  - CYCLE: Circular dependency detected in wasDerivedFrom edges
```

## Архитектурная интеграция

Инструменты обеспечивают соблюдение архитектурных законов Policy Engine:

| Инструмент | Модули | Архитектурный закон |
|------------|--------|---------------------|
| `lint_imports.py` | `core.*` | Закон A (направленный граф зависимостей) |
| `lint_foundry.py` | `foundry.*` | Закон B (чистота математического ядра) |
| `lint_connectors.py` | `fabric.connectors.*` | Законы A, E (изоляция и provenance) |
| `gen_schema.py` | `ir.contract` | Закон C (контракты как источник истины) |
| `migrate_*` | `ir.migrations` | Закон C (детерминированные миграции) |
| `capture_env.py` | `core.artifacts` | Закон D (воспроизводимость) |
| `check_perf_regression.py` | - | Закон D (регрессионное тестирование) |
| `scan_fabric.py` | `fabric.catalog` | Закон E (evidence и provenance) |
| `visualize_provenance.py` | `core.artifacts` | Закон E (evidence и provenance) |

### Архитектурные законы

**Закон A**: Направленный граф зависимостей только внутрь
**Закон B**: Чистота математического ядра foundry (без IO/side effects)
**Закон C**: Контракты как источник истины (Pydantic + JSON Schema)
**Закон D**: Воспроизводимость и аудит (manifests + trace)
**Закон E**: Evidence и provenance обязательны

## CI/CD интеграция

Рекомендуемый pipeline качества:

```yaml
# Quality gate
- python tools/diagnostics/check_setup.py
- python tools/lint_imports.py --fail-on-cycles
- python tools/lint_foundry.py
- python tools/gen_schema.py --check

# Performance regression
- python tools/check_perf_regression.py results.json --threshold 0.05

# Integration tests
- python tools/demos/run_ingest_demo.py
- python tools/demos/run_udf_query_demo.py
```

## Разработка и расширение

### Добавление нового инструмента

1. **Следуйте паттернам:**
   - Импорт sys.path manipulation для PYTHONPATH
   - Использование polisyos.common.logger
   - Argparse для CLI интерфейса
   - Docstrings на русском

2. **Категоризация:**
   - `diagnostics/` - проверки и анализ
   - `demos/` - демонстрации возможностей
   - `benchmarks/` - производительность
   - Корень - core утилиты

3. **Качество кода:**
   - Строгая типизация
   - Линтеры проходят все проверки
   - README обновляется

### Отладка инструментов

```bash
# Детальный вывод
python tools/lint_imports.py --verbose

# Сохранение логов
POLICY_ENGINE_LOG_LEVEL=DEBUG python tools/diagnostics/check_setup.py 2>&1 | tee setup.log

# Профилирование
python -m cProfile tools/benchmarks/bench_domain.py
```

## Troubleshooting

### Import errors
```bash
# Проверь PYTHONPATH
export PYTHONPATH="/path/to/policy-engine/src:$PYTHONPATH"
python tools/diagnostics/check_setup.py
```

### JAX/Metal issues (macOS)
```bash
# Принудительно CPU
export POLICY_ENGINE_ALLOW_JAX_METAL=0
python tools/diagnostics/check_setup.py
```

### Permission issues
```bash
# Используй --user для pip
pip install --user -e .[dev]
```

### Schema validation fails
```bash
# Перегенерируй ABI snapshots
python3 tools/gen_schema.py

# Проверь consistency snapshots
python3 tools/gen_schema.py --check
```

### Import violations detected
```bash
# Детальный анализ нарушений
python tools/lint_imports.py --verbose --top 20

# Проверь конкретный файл
python tools/lint_imports.py --src-root src | grep "problematic_file.py"
```

### Foundry linting fails
```bash
# Проверь запрещенные импорты
python tools/lint_foundry.py --verbose

# Исключи тестовые файлы если нужно
python tools/lint_foundry.py --exclude "test_*"
```

### scan_fabric.py не находит DuckDB файлы
```bash
# Проверь наличие файлов
ls -la data/curated/*.duckdb

# Используй кастомный glob паттерн
python tools/scan_fabric.py data/ -glob "**/*.duckdb"

# Проверь права доступа
python -c "import duckdb; print('DuckDB OK')"
```

### Некорректное определение типов/единиц
```bash
# Просмотри сгенерированные контракты
python tools/scan_fabric.py data/curated/ -v

# Ручная аннотация после генерации
# Отредактируй draft_contracts.json вручную
# Проверь units и pii_tiers
```

### visualize_provenance.py не может загрузить граф
```bash
# Проверь существование файла
ls -la evidence.json

# Для CAS артефактов проверь путь к .polisyos
ls -la .polisyos/

# Попробуй с verbose выводом
python tools/visualize_provenance.py evidence.json --cas-root .polisyos --verify -v

# Проверь JSON структуру
python -c "import json; print(json.load(open('evidence.json'))['provenance_ref'])" 2>/dev/null || echo "No provenance_ref"
```

### DOT визуализация не работает
```bash
# Установи Graphviz
# macOS: brew install graphviz
# Ubuntu: apt-get install graphviz

# Проверь установку
dot -V

# Сгенерируй и визуализируй
python tools/visualize_provenance.py evidence.json --format dot | dot -Tpng -o graph.png
```

### check_perf_regression.py не может загрузить benchmark JSON
```bash
# Проверь существование файла
ls -la benchmark_results.json

# Проверь JSON структуру
python -c "import json; data=json.load(open('benchmark_results.json')); print('benchmarks' in data)"

# Для pytest-benchmark файлов проверь формат
python -c "import json; data=json.load(open('benchmark_results.json')); print(data.keys())"
```

### Нет baseline файла для сравнения
```bash
# Создай baseline вручную
cp benchmark_results.json .benchmarks/baseline.json

# Или укажи явный путь
python tools/check_perf_regression.py current.json --baseline path/to/baseline.json

# Автоматический поиск baseline в стандартных директориях:
# - .benchmarks/*.json (отсортировано по времени модификации)
# - benchmarks/*.json
```

### Ложные регрессии из-за шума
```bash
# Увеличь threshold для нестабильных тестов
python tools/check_perf_regression.py results.json --threshold 0.15  # 15% вместо 5%

# Проверь статистику в benchmark JSON
python -c "import json; data=json.load(open('results.json')); print(data['benchmarks'][0]['stats'])"
```

## Разработка новых инструментов

### Принципы дизайна

1. **Следуйте архитектуре:** Каждый инструмент должен соответствовать одному из архитектурных законов
2. **Интегрируйтесь с модулями:** Используйте публичные API модулей, не нарушайте инкапсуляцию
3. **CLI интерфейс:** Argparse с --help, структурированный вывод
4. **Логирование:** Используйте `polisyos.common.logger`
5. **Обработка ошибок:** Четкие exit codes, информативные сообщения

### Категоризация инструментов

- **`diagnostics/`** - анализ и проверка системы
- **`demos/`** - демонстрация возможностей (создают тестовые данные)
- **`benchmarks/`** - измерение производительности
- **Корень** - core утилиты для разработки

### Тестирование

```bash
# Добавьте тесты в tests/tools/
# Следуйте паттернам существующих тестов
pytest tests/tools/ -v
```

### Документация

1. **Обновите этот README** - добавьте описание, примеры использования
2. **Добавьте docstrings** - на русском, с примерами
3. **Убедитесь в линтинге** - все инструменты проходят свои же проверки

## Поддержка и совместимость

### Системные требования

- **Python:** 3.11+ (рекомендуется 3.11 или 3.12)
- **JAX:** 0.4.x+ с соответствующими JAXlib
- **Pydantic:** v2 only (критические изменения в v1→v2)
- **Операционные системы:** Linux, macOS (Intel/Apple Silicon), Windows (WSL2)

### Зависимости

| Компонент | Версия | Примечание |
|------------|--------|------------|
| `jax` | 0.4.x+ | С JAXlib для целевой платформы |
| `jaxlib` | Совместимая с JAX | CPU или GPU версия |
| `equinox` | 0.11.x+ | Функциональное программирование |
| `pydantic` | 2.x | Только v2, v1 не поддерживается |
| `duckdb` | 0.9.x+ | Аналитическое хранилище |
| `kuzu` | 0.0.x+ | Графовая база данных |
| `pymoo` | 0.6.x+ | Многокритериальная оптимизация |

### Известные ограничения и решения

#### JAX и Apple Silicon (macOS)
```bash
# Принудительное использование CPU (рекомендуется для стабильности)
export POLICY_ENGINE_ALLOW_JAX_METAL=0
python tools/diagnostics/check_setup.py
```

#### PyYAML для YAML поддержки
```bash
# Опционально для миграций YAML файлов
pip install PyYAML
```

#### Kuzu установка
```bash
# Требует C++ компилятора
# На macOS: xcode-select --install
# На Ubuntu: apt-get install build-essential
pip install kuzu
```

#### Windows поддержка
- Полная поддержка через WSL2
- Native Windows: экспериментальная, возможны проблемы с JAX GPU

### Тестирование совместимости

```bash
# Полная проверка системной совместимости
python tools/diagnostics/check_setup.py

# Проверка с детальным логированием
POLICY_ENGINE_LOG_LEVEL=DEBUG python tools/diagnostics/check_setup.py
```

### Версионирование

Инструменты следуют семантическому версионированию основного проекта. Критические изменения в API инструментов помечаются в changelog.

---

## Архитектурная актуальность

Данная документация отражает текущее состояние Policy Engine на **2026-01-30** и соответствует принципам, описанным в `architecture.md`.

### Ключевые архитектурные достижения

- **Закон A**: Гарантированная направленность зависимостей через автоматизированное тестирование
- **Закон B**: Чистота математического ядра foundry с запретом IO операций
- **Закон C**: Контракты как источник истины с детерминированными миграциями
- **Закон D**: Полная воспроизводимость через manifests и trace систему
- **Закон E**: Evidence и provenance обязательны для всех данных (новая система data contracts)

### Интеграция с модулями

Инструменты `tools/` обеспечивают качество всей экосистемы Policy Engine:

- **Диагностика**: `diagnostics/` - проверка готовности системы
- **Качество**: `lint_*.py` - соблюдение архитектурных законов
- **Эволюция**: `migrate_*.py`, `gen_schema.py` - безопасные изменения
- **Производительность**: `benchmarks/` - регрессионное тестирование
- **Демонстрация**: `demos/` - валидация функциональности
- **Bootstrap**: `scan_fabric.py` - быстрая генерация data contracts из существующих данных

### Новые возможности (2026-02-01)

- **Data Catalog System**: Новая подсистема data contracts в `fabric.catalog/`
- **scan_fabric.py**: Bootstrap утилита для автоматической генерации data contracts
- **Enhanced Evidence Tracking**: Улучшенная система provenance и evidence bundles
- **Trinity Migration**: Поддержка миграции в новый Trinity формат (ProblemFrame, PolicySpec, ModelSpec)
- **migrate_to_trinity.py**: Специализированный инструмент для batch миграции политик в Trinity формат
- **visualize_provenance.py**: Инструмент для визуализации и верификации provenance графов
- **check_perf_regression.py**: Автоматическая проверка регрессий производительности на основе pytest-benchmark результатов
- **capture_env.py**: CLI инструмент для захвата и сравнения Environment Manifest
- **run_mechanism_design.py**: End-to-end демонстрация дифференцируемого механизма дизайна
- **diagnostics/check_perf_regression.py**: Расширенная версия проверки регрессий в diagnostics
- **lint_connectors.py**: Архитектурный линтер для коннекторов данных с проверкой Законов A и E
- **connectors/scaffold.py**: Генератор скелетов коннекторов с автоматической поддержкой REST, CSV, SQL, SDMX типов

## Troubleshooting

### Основные проблемы
```bash
# PYTHONPATH
export PYTHONPATH="/path/to/policy-engine/src:$PYTHONPATH"

# JAX Metal (macOS)
export POLICY_ENGINE_ALLOW_JAX_METAL=0

# Schema validation
python3 tools/gen_schema.py

# Import violations
python tools/lint_imports.py --verbose --top 20
```

---

*Документация актуальна на 2026-02-05. Инструменты следуют архитектурным законам A, B, C, D, E Policy Engine.*

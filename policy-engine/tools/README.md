# Tools - Инструменты разработчика Policy Engine

Коллекция утилит для разработки, тестирования, диагностики и демонстрации Policy Engine. Все инструменты следуют принципам архитектуры проекта и обеспечивают соблюдение [Законов системы](https://github.com/your-repo/architecture.md).

## Структура папки

```
tools/
├── benchmarks/           # Бенчмарки производительности
│   ├── bench_domain.py   # Тест доменной модели (JAX + Equinox)
│   └── bench_simulation.py # Тест симуляционного ядра
├── demos/               # Демонстрационные скрипты
│   ├── run_export_demo.py      # Экспорт симуляционных данных
│   ├── run_ingest_demo.py      # Ingestion пайплайн (CSV → DB)
│   ├── run_optimizer_demo.py   # Оптимизация политик (PyMOO)
│   ├── run_udf_hybrid_demo.py  # Гибридные пользовательские функции
│   └── run_udf_query_demo.py   # UDF запросы (DuckDB + Kuzu)
├── diagnostics/         # Диагностические инструменты
│   ├── check_setup.py           # Smoke test установки компонентов
│   ├── check_udf_perf.py        # Анализ производительности UDF
│   └── generate_ir_schema.py    # Генерация IR схем
├── gen_schema.py        # Генерация JSON схем (Pydantic v2)
├── lint_foundry.py      # Линтер foundry модуля (архитектурные правила)
├── lint_imports.py      # Линтер межмодульных зависимостей
├── migrate.py           # Миграция артефактов между версиями
└── migrate_ir.py        # Специализированная миграция Policy IR
```

## Быстрый старт

Все инструменты запускаются из корня проекта с корректным PYTHONPATH:

```bash
cd policy-engine/

# Проверка установки
python tools/diagnostics/check_setup.py

# Линтинг архитектуры
python tools/lint_imports.py
python tools/lint_foundry.py

# Генерация схем
python tools/gen_schema.py --check
```

## Архитектурные линтеры

### lint_imports.py - Линтер межмодульных зависимостей

Проверяет соблюдение [Закона A](https://github.com/your-repo/architecture.md#закон-a-граф-зависимостей-только-внутрь) - направленный граф зависимостей:

- `scientist` → {`ir`, `fabric`, `foundry`}
- `fabric` → {`ir`}
- `foundry` → {`ir`} (только типы/контракты)
- `ir` → никого

```bash
# Проверка всех модулей
python tools/lint_imports.py

# Детальный вывод нарушений
python tools/lint_imports.py --verbose
```

**Запрещенные паттерны:**
- Foundry модуль не может импортировать fabric (БД/IO)
- Fabric не может импортировать scientist (LLM/orchestration)
- TYPE_CHECKING импорты считаются подозрительными

### lint_foundry.py - Линтер foundry модуля

Проверяет чистоту математического ядра foundry согласно [Закону B](https://github.com/your-repo/architecture.md#закон-b-ты-строишь-компилятор):

**Запрещенные импорты в foundry:**
- `duckdb`, `kuzu`, `pandas`, `polars`, `pyarrow`
- `random`, `requests`, `httpx`, `sqlite3`, `sqlalchemy`
- `os`, `pathlib`, `shutil`, `glob`, `tempfile`
- `print`, `open` (встроенные функции)

```bash
# Линтинг foundry модуля
python tools/lint_foundry.py

# С указанием корневой папки
python tools/lint_foundry.py --repo-root /path/to/policy-engine
```

## Генерация схем

### gen_schema.py - Генератор JSON Schema

Генерирует и проверяет JSON Schema для Pydantic моделей согласно [Закону C](https://github.com/your-repo/architecture.md#закон-c-контракты-единственный-источник-истины).

```bash
# Генерация новой схемы
python tools/gen_schema.py --output policy_ir_schema.json

# Проверка актуальности существующей схемы
python tools/gen_schema.py --check --output policy_ir_schema.json

# Сравнение с текущей схемой
python tools/gen_schema.py --check --output policy_ir_schema.json 2>&1 | head -20
```

**Что проверяется:**
- Соответствие сгенерированной схемы зафиксированному snapshot
- Валидность структуры PolicyRequestIR
- Совместимость версий Pydantic

## Миграции

### migrate.py - Миграция артефактов

Миграция dataset manifests и policy IR между версиями согласно [Закону C](https://github.com/your-repo/architecture.md#закон-c-контракты-единственный-источник-истины).

```bash
# Миграция dataset manifest
python tools/migrate.py dataset_manifest data/manifest_v1.json data/manifest_v2.json --to v2.1.0

# Миграция policy IR
python tools/migrate.py policy_ir old_ir.json new_ir.json --to v3.0.0

# С поддержкой YAML (если установлена PyYAML)
python tools/migrate.py policy_ir policy.yml migrated_policy.json --to v2.5.0
```

### migrate_ir.py - Специализированная миграция Policy IR

Упрощенная версия migrate.py специально для Policy IR артефактов с поддержкой major версий.

```bash
# Базовая миграция
python tools/migrate_ir.py input_ir.json output_ir.json --to v3.0.0

# С разрешением major изменений
python tools/migrate_ir.py input_ir.json output_ir.json --to v4.0.0 --allow-major

# Из YAML в JSON
python tools/migrate_ir.py policy_v1.yml migrated_policy.json --to v2.1.0
```

## Диагностика

### check_setup.py - Smoke test установки

Комплексная проверка корректной установки всех компонентов Policy Engine согласно технологическому стеку.

```bash
# Полная проверка установки
python tools/diagnostics/check_setup.py

# Что проверяется:
# ✓ Python 3.11+
# ✓ JAX + JAXlib загрузка
# ✓ DuckDB подключение
# ✓ Pydantic v2 валидация
# ✓ Импорт всех основных модулей
# ✓ Базовые операции JAX (zeros, random)
```

**Вывод при успехе:**
```
🟢 JAX Environment: OK (platform=cpu, devices=1)
🟢 Database Connections: OK (DuckDB + Kuzu)
🟢 Core Imports: OK (Pydantic, Equinox, Diffrax)
🟢 Basic Operations: OK (tensor creation, random gen)
🚀 Policy Engine is ready for development!
```

### check_udf_perf.py - Анализ производительности UDF

Профилирование и анализ производительности пользовательских функций в контексте Unified Data Fabric.

```bash
# Анализ UDF производительности
python tools/diagnostics/check_udf_perf.py

# Метрики:
# - Время выполнения запросов
# - Память использования
# - CPU нагрузка
# - DuckDB vs Kuzu сравнение
```

### generate_ir_schema.py - Генератор IR схем

Автоматическая генерация схем для всех IR компонентов с валидацией структуры.

```bash
# Генерация полной IR схемы
python tools/diagnostics/generate_ir_schema.py

# Вывод:
# - JSON Schema для всех Pydantic моделей
# - Валидация структур данных
# - Совместимость версий
```

## Бенчмарки

### bench_domain.py - Тест доменной модели

Производительность JAX доменной модели (GlobalState, AgentState, FirmState, MarketState).

```bash
# Тест на 1M агентов
python tools/benchmarks/bench_domain.py

# Метрики:
# - Время аллокации состояния
# - Память использования
# - JAX компиляция (JIT warmup)
# - Векторизованные операции
```

**Типичный вывод:**
```
🚀 Starting Domain Model Check...
Allocating state for 1,000,000 agents...
✅ Memory allocation: 2.3GB
✅ JIT compilation: 1.2s
✅ Vectorized operations: 45ms per step
```

### bench_simulation.py - Тест симуляционного ядра

Производительность полного симуляционного пайплайна (SimulationKernel + экономическая логика).

```bash
# Полный симуляционный бенчмарк
python tools/benchmarks/bench_simulation.py

# Тестирует:
# - Экономический цикл (production → consumption → market)
# - Механизмы политик (TaxSubsidy, IncomeTax, Queue)
# - JAX JIT оптимизации
# - Память эффективность
```

## Демонстрации

### run_ingest_demo.py - Ingestion пайплайн

Демонстрация полного цикла ingestion: CSV → validation → parquet → DuckDB/Kuzu → manifests.

```bash
# Запуск полного ingestion пайплайна
python tools/demos/run_ingest_demo.py

# Этапы:
# 1. Загрузка CSV (agents.csv, interactions.csv, macro.csv)
# 2. Pydantic валидация строк
# 3. Конвертация в Parquet
# 4. Загрузка в DuckDB + Kuzu
# 5. Генерация JSON manifests
```

### run_udf_query_demo.py - UDF запросы

Демонстрация гибридных запросов с пользовательскими функциями (SQL + Python UDF).

```bash
# Запуск UDF демонстрации
python tools/demos/run_udf_query_demo.py

# Показывает:
# - Регистрацию Python функций в DuckDB
# - Гибридные SQL + Python запросы
# - Kuzu графовые запросы с UDF
```

### run_optimizer_demo.py - Оптимизация политик

Демонстрация многокритериальной оптимизации политик с PyMOO (NSGA-II).

```bash
# Запуск оптимизации
python tools/demos/run_optimizer_demo.py

# Процесс:
# 1. Настройка целевых функций (GDP, inequality, unemployment)
# 2. Определение параметров политик
# 3. NSGA-II оптимизация
# 4. Pareto front анализ
# 5. Визуализация результатов
```

### run_udf_hybrid_demo.py - Гибридные UDF

Продвинутая демонстрация комбинации SQL запросов и Python функций.

```bash
# Гибридная UDF демонстрация
python tools/demos/run_udf_hybrid_demo.py

# Возможности:
# - Комплексные агрегации
# - Машинное обучение в запросах
# - Статистические функции
# - Временные ряды анализ
```

### run_export_demo.py - Экспорт данных

Демонстрация экспорта результатов симуляции в различные форматы.

```bash
# Экспорт симуляционных данных
python tools/demos/run_export_demo.py

# Форматы экспорта:
# - Parquet (аналитические данные)
# - JSON (метаданные и конфигурация)
# - CSV (legacy совместимость)
# - HDF5 (большие массивы)
```

## Использование в CI/CD

Рекомендуемый набор команд для автоматизации:

```yaml
# .github/workflows/ci.yml
- name: Setup and diagnostics
  run: |
    python tools/diagnostics/check_setup.py

- name: Architecture linting
  run: |
    python tools/lint_imports.py
    python tools/lint_foundry.py

- name: Schema validation
  run: |
    python tools/gen_schema.py --check

- name: Performance benchmarks
  run: |
    python tools/benchmarks/bench_domain.py
    python tools/benchmarks/bench_simulation.py
```

## Архитектурные принципы

Все инструменты следуют core принципам Policy Engine:

### Закон A: Направленный граф зависимостей
- Инструменты проверяют и обеспечивают правильные импорты между модулями
- Предотвращают циклические зависимости

### Закон B: Компиляторная архитектура
- Foundry остается чистым математическим ядром
- Runtime не знает про LLM, IR не знает про JAX/DuckDB

### Закон C: Контракты как источник истины
- Все артефакты имеют schema_version
- Детерминированные миграции между версиями

### Закон D: Воспроизводимость и аудит
- Все прогоны имеют run_id, seed, repro_mode
- Полная трассировка артефактов и версий

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
# Перегенерируй схему
python tools/gen_schema.py --output policy_ir_schema.json
```

## Contributing

При добавлении новых инструментов:

1. Обновите этот README
2. Добавьте соответствующие тесты в `tests/tools/`
3. Убедитесь в прохождении всех линтеров
4. Следуйте архитектурным законам

---

*Все инструменты протестированы на Python 3.11+ с JAX, DuckDB, Kuzu и соответствующими зависимостями.*

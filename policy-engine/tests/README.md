# Policy Engine Tests

Тестовая инфраструктура для Policy Engine - AI-driven Policy Simulation System. Тесты обеспечивают качество кода, валидируют архитектурные границы и проверяют корректность работы всех компонентов системы.

## Архитектурный контекст

Согласно [архитектуре проекта](../architecture.md), тесты организованы по слоям компилятора:

- **IR (Contract Tests)**: Валидация контрактов и схем данных
- **Fabric (Integration Tests)**: Тестирование Unified Data Fabric
- **Foundry (Unit Tests)**: Тестирование JAX-ядра симуляции
- **Scientist (Integration Tests)**: Тестирование оркестрации и workflow

## Структура тестовой иерархии

```
tests/
├── conftest.py                    # Конфигурация pytest и настройка окружения
├── contract/                      # Тесты контрактов IR и схем валидации
│   ├── test_ir_contract.py        # PolicyRequestIR, TargetSelector, валидация
│   ├── test_ir_migrations.py      # Миграции схем IR
│   ├── test_fabric_gates.py       # Входные фильтры Fabric
│   ├── test_kernel_models.py      # Валидация моделей ядра IR (slots, units, merge rules)
│   └── test_surface_ir.py         # Тестирование Surface IR, линкера и fingerprint'ов
├── core_phase0/                   # Тесты базовых компонентов core (Phase 0)
│   ├── conftest.py                # Специфичная конфигурация для core тестов
│   ├── test_artifact_store.py     # FileSystemCAS, дедупликация, верификация
│   ├── test_canon_json.py         # Каноническая JSON сериализация
│   ├── test_registry_bundle.py    # Сборка и загрузка registry bundles
│   └── test_run_context.py        # Контекст выполнения и артефакты
├── foundry/                       # Тесты симуляционных компонентов
│   ├── test_gradients.py          # Градиенты политик (JAX/Equinox)
│   ├── test_fiscal.py             # Фискальные механизмы
│   ├── test_global_state.py       # Глобальное состояние симуляции
│   ├── test_health.py             # Проверки здоровья системы
│   ├── test_jit_stability.py      # JIT-стабильность
│   ├── test_production_kernel.py  # Production kernel
│   ├── test_constraints_executor.py # Исполнение ограничений (constraints)
│   ├── test_patch_executor.py     # Patch executor и state delta
│   ├── test_program_graph_ops.py  # Операции с программными графами
│   └── test_*.py                  # Другие тесты foundry
├── integration/                   # Интеграционные тесты workflow
│   ├── test_workflow_smoke.py     # Полный smoke-test pipeline
│   └── test_workflow_llm.py       # Интеграция с LLM компонентами
└── scientist/                     # Тесты компонентов scientist
    └── test_compiler.py           # Компилятор политик из IR
```

## Категории тестов

### Contract Tests (`contract/`)

**Цель**: Обеспечение корректности структур данных и API контрактов на всех уровнях IR.

**Ключевые тесты:**
- **IR Contract Validation**: Валидация `PolicyRequestIR`, селекторов, транслируемых строк
- **Schema Migrations**: Тестирование миграций схем между версиями
- **Fabric Gates**: Проверка входных фильтров и предусловий
- **Kernel Models**: Валидация моделей ядра (slots, units, merge rules, time semantics)
- **Surface IR**: Тестирование Surface IR, линкера, семантических fingerprint'ов

**Принципы:**
- Roundtrip тестирование: `yaml → model → yaml` сохраняет канонический формат
- Alias acceptance: Принимает `En/Ua/Ru`, сериализует в `en/ua/ru`
- Limits enforcement: Огромные payload'ы не "валят пайплайн"
- Entity DAG validation: Циклы в графах сущностей ловятся
- Type safety: Строгая валидация типов, запрет float значений, Decimal enforcement
- Linker validation: Проверка корректности связывания политик с механизмами
- Semantic fingerprinting: Детерминированные хэши для политик независимо от порядка

### Core Phase 0 Tests (`core_phase0/`)

**Цель**: Тестирование фундаментальных компонентов core layer - artifact store, канонической сериализации и registry систем.

**Ключевые тесты:**
- **Artifact Store**: FileSystemCAS, дедупликация контента, верификация integrity
- **Canonical JSON**: Детерминированная сериализация, запрет float/NaN, нормализация
- **Registry Bundle**: Сборка и загрузка registry bundles из artifact store
- **Run Context**: Контекст выполнения, артефакты и метаданные producer'а

**Принципы:**
- Content-addressable storage: SHA256-based addressing, дедупликация
- Canonical serialization: Стабильные хэши независимо от порядка ключей
- Type safety: Запрет float значений, использование Decimal для денег
- Artifact immutability: Артефакты неизменяемы после создания
- Producer tracking: Метаданные о создателе и окружении

### Foundry Tests (`foundry/`)

**Цель**: Валидация математических моделей, симуляций на JAX и компонентов исполнения.

**Ключевые тесты:**
- **Gradient Health**: Проверка градиентов политик, NaN/Inf detection
- **JIT Stability**: Стабильность PyTree структур при компиляции
- **Fiscal Mechanisms**: Тестирование налоговых/субсидий механизмов
- **Kernel Production**: Тестирование production симуляционного ядра
- **Constraints Executor**: Исполнение ограничений (budget guards, validation)
- **Patch Executor**: State delta, snapshot'ы, артефакт эмиссия
- **Program Graph Ops**: Операции с программными графами, execution order

**Принципы:**
- Все тесты форсируют CPU (через conftest.py) для консистентности
- Проверка `jit(step)` компилируется и сохраняет структуру
- Gradient sanity: конечные разности vs JAX autodiff в допусках
- Invariants verification: физическая корректность после шагов симуляции
- Constraint enforcement: Валидация ограничений на runtime
- State consistency: Корректность state delta и snapshot'ов
- Graph execution: Правильный порядок операций в программных графах

### Integration Tests (`integration/`)

**Цель**: Проверка end-to-end сценариев через все слои системы.

**Ключевые тесты:**
- **Workflow Smoke Test**: Полный pipeline от IR до DecisionPacket
- **LLM Integration**: Тестирование интеграции с языковыми моделями
- **Budget Constraints**: Проверка ограничений на ресурсы

**Принципы:**
- Маркированы `pytest.mark.integration` для раздельного запуска
- Используют реальные БД (DuckDB/Kuzu) с тестовыми данными
- Проверяют полный цикл: draft → simulate → governor → decision

### Scientist Tests (`scientist/`)

**Цель**: Валидация компонентов ИИ и оптимизации.

**Ключевые тесты:**
- **Policy Compiler**: Компиляция IR в исполняемые модели foundry
- **Self-healing**: Тестирование автоматического исправления ошибок

## Конфигурация окружения (conftest.py)

Файл `conftest.py` обеспечивает консистентное окружение для всех тестов:

### JAX Configuration
```python
# Форсируем CPU для всех тестов (консистентность в CI/CD)
os.environ["JAX_PLATFORM_NAME"] = "cpu"

# Запрещаем аллокацию памяти (экономим ресурсы)
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
```

### Logging Setup
```python
# Только ошибки в тестах (убираем шум)
logger.remove()
logger.add(lambda msg: print(msg), level="ERROR")
```

## Запуск тестов

### Базовые команды

```bash
# Все тесты (быстрые unit + медленные integration)
pytest

# Только быстрые unit тесты (foundry + contract)
pytest -m "not integration"

# Только интеграционные тесты (медленные, с БД)
pytest -m integration

# С подробным выводом и остановкой на первой ошибке
pytest -v --tb=short

# С покрытием кода (требует pytest-cov)
pytest --cov=polisyos --cov-report=html
```

### Запуск по категориям

```bash
# Контрактные тесты (быстрые, без зависимостей)
pytest tests/contract/ -v

# Core Phase 0 тесты (базовые компоненты)
pytest tests/core_phase0/ -v

# Foundry тесты (JAX, математические)
pytest tests/foundry/ -v

# Интеграционные тесты (медленные, с БД)
pytest tests/integration/ -v

# Scientist тесты
pytest tests/scientist/ -v
```

### Специфические сценарии

```bash
# Тесты градиентов (требуют Equinox)
pytest tests/foundry/test_gradients.py

# Тесты workflow (требуют LLM API ключей)
pytest tests/integration/test_workflow_llm.py

# Smoke test (минимальный полный цикл)
pytest tests/integration/test_workflow_smoke.py
```

## Технологии и зависимости

### Core Testing Framework
- **pytest**: Основной фреймворк с плагинами
- **pytest-cov**: Покрытие кода (опционально)

### Domain-Specific Libraries
- **JAX/Equinox**: Для тестирования математических компонентов и симуляций
- **pandas**: Работа с тестовыми данными
- **DuckDB/Kuzu**: Интеграционные тесты с базами данных
- **Pydantic**: Валидация структур данных и контрактов
- **pathlib**: Работа с файловой системой в core тестах
- **hashlib**: SHA256 хэширование для artifact integrity

## Принципы тестирования

### Архитектурные инварианты
- **Закон A**: Граф зависимостей только внутрь (scientist → ir/fabric/foundry/core)
- **Закон B**: Компиляторная труба (NL → LLM → IR → Compilation → Runtime)
- **Закон C**: Контракты как источник истины
- **Закон D**: Core layer как фундамент (core → ir → fabric → foundry → scientist)

### Качественные требования
- **Unit Tests**: Покрывают все публичные API foundry и core компонентов
- **Contract Tests**: Валидируют границы между слоями
- **Integration Tests**: Проверяют end-to-end сценарии
- **Performance Regression**: SLA на скорость выполнения

## Связи между модулями и архитектурные зависимости

### Core Layer (`core_phase0/`)
**Artifact Store** → Используется всеми модулями для хранения immutable артефактов
- **IR**: Хранение схем и политик
- **Fabric**: Материализация данных в артефакты
- **Foundry**: Компиляция политик в executable артефакты
- **Scientist**: Хранение результатов экспериментов

**Canonical JSON** → Стандартизированная сериализация
- **IR**: Канонические представления политик
- **Registry**: Нормализованные конфигурации
- **Contracts**: Детерминированные хэши для валидации

**Registry System** → Централизованное управление метаданными
- **IR Kernel**: Слоты, механизмы, ограничения
- **Foundry**: Доступ к registry для компиляции
- **Fabric**: Registry-driven материализация

### Contract Layer (`contract/`)
**IR Contracts** → Валидация структур данных
- **Surface IR**: Семантическая модель политик
- **Kernel Models**: Базовые типы (MoneyValue, TimeSemantics, Slots)
- **Linker**: Связывание политик с механизмами

**Schema Validation** → Гарантии совместимости
- **Migrations**: Безопасные переходы между версиями
- **Fabric Gates**: Предусловия для обработки данных
- **Surface IR**: Semantic fingerprinting для дедупликации

### Foundry Layer (`foundry/`)
**Simulation Engine** → JAX-based execution
- **Constraints**: Runtime валидация ограничений
- **Patch Executor**: State management и snapshots
- **Program Graphs**: Оркестрация execution order

**Compilation Pipeline** → IR → Executable
- **IR Surface**: Исходные политики для компиляции
- **Core Artifacts**: Хранение скомпилированных программ
- **Integration**: End-to-end pipeline validation

### Integration Layer (`integration/`)
**Workflow Orchestration** → End-to-end scenarios
- **Scientist**: LLM-driven policy drafting
- **Foundry**: Simulation execution
- **Fabric**: Data ingestion и materialization
- **IR**: Policy compilation pipeline

**LLM Integration** → AI-powered components
- **Scientist Agent**: Drafter, prompt engineering
- **Workflow**: Комплексные сценарии с AI

### CI/CD интеграция
- Unit тесты запускаются на каждый PR
- Integration тесты - по расписанию или на release
- Архитектурные гейты предотвращают регрессии
- Coverage thresholds для предотвращения снижения качества

## Разработка и расширение

### Добавление новых тестов
1. Определите категорию (contract/core_phase0/foundry/integration/scientist)
2. Следуйте naming convention: `test_*.py`
3. Используйте fixtures из соответствующего `conftest.py`
4. Маркируйте медленные тесты `@pytest.mark.integration`
5. Для core тестов используйте специфичные fixtures (store, producer, env_info)

### Отладка тестов
```bash
# Запуск с отладкой (останавливается в pdb при ошибке)
pytest --pdb tests/foundry/test_gradients.py::test_tax_subsidy_gradient_value

# Запуск конкретного теста
pytest tests/contract/test_ir_contract.py::test_required_fields_enforced -v
```

### Профилирование
```bash
# Измерение времени выполнения
pytest --durations=10

# Память и CPU profiling (требует дополнительных плагинов)
pytest --profile
```

## Troubleshooting

### Распространенные проблемы

**JAX memory allocation errors:**
```bash
# Решение: проверьте что JAX_PLATFORM_NAME=cpu установлен
export JAX_PLATFORM_NAME=cpu
pytest tests/foundry/
```

**Database connection issues в integration тестах:**
```bash
# Проверьте что тестовые БД не заблокированы предыдущими запусками
rm -f tmp_path/integration.duckdb tmp_path/integration.kuzu
```

**LLM API timeouts:**
```bash
# Integration тесты с LLM могут падать по таймауту
pytest tests/integration/test_workflow_llm.py --tb=short
```

### Полезные команды диагностики

```bash
# Проверка что все зависимости установлены
python tools/diagnostics/check_setup.py

# Генерация схем для проверки контрактов
python tools/diagnostics/generate_ir_schema.py

# Линтинг тест кода
ruff check tests/
```

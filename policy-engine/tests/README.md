# Policy Engine Tests

Тестовая инфраструктура для Policy Engine - AI-driven Policy Simulation System. Тесты обеспечивают качество кода, валидируют архитектурные границы и проверяют корректность работы всех компонентов системы.

**Последнее обновление:** Январь 2026 (добавлены provenance subsystem, PROV-O экспорт и provenance tracking в Fabric layer)
**Актуальная версия архитектуры:** v2.1.4 (Provenance Tracking, PROV-O Integration, Evidence-Enhanced Fabric)

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
│   ├── test_ir_contract.py        # PolicySurfaceIR, селекторы, валидация, TranslatableString
│   ├── test_ir_migrations.py      # Миграции схем IR между версиями
│   ├── test_trinity_contracts.py  # Trinity артефакты: ProblemFrame, PolicySpec, ModelSpec
│   ├── test_trinity_migration.py  # Миграция между Surface IR и Trinity форматами
│   ├── test_fabric_gates.py       # Входные фильтры и предусловия Fabric layer
│   ├── test_kernel_models.py      # Валидация моделей ядра IR (slots, units, merge rules, time semantics)
│   └── test_surface_ir.py         # Surface IR, линкер, semantic fingerprinting, validation reports
├── core_phase0/                   # Тесты базовых компонентов core (Phase 0)
│   ├── conftest.py                # Специфичная конфигурация для core тестов
│   ├── test_artifact_store.py     # FileSystemCAS, дедупликация, верификация integrity
│   ├── test_canon_json.py         # Каноническая JSON сериализация, детерминированные хэши
│   ├── test_environment_manifest.py # Захват и сравнение environment манифестов
│   ├── test_registry_bundle.py    # Сборка и загрузка registry bundles
│   └── test_run_context.py        # Контекст выполнения и артефакты producer'а
├── demos/                         # Демо-тесты для проверки функциональности
│   └── run_laffer_demo.py         # Тест запуска демо Laffer curve из tools/demos/
├── fabric/                        # Тесты компонентов Fabric layer
│   ├── test_data_catalog.py       # Data Contract catalog system, contract validation, metric bindings, search
│   ├── test_evidence_bundle.py    # Evidence bundles, ingestion pipeline, provenance tracking
│   ├── test_provenance.py         # Provenance subsystem, entities, graphs, PROV-O export, persistence
│   └── test_trust_two_pass.py     # Trust system, uncertainty bounds, двухпроходное сравнение
├── foundry/                       # Тесты симуляционных компонентов JAX-ядра
│   ├── agent_sim/                 # Тесты симуляции агентов
│   │   └── test_monitoring.py     # MetricsCollector, ExperimentTracker, DashboardGenerator, визуализация
│   ├── plugins/                   # Тесты плагинной системы Foundry
│   │   └── test_plugin_system.py  # PluginRegistry, CompositeExecutor, EconomicsPlugin, domain configs
│   ├── test_adaptive_agents.py    # Адаптивные агенты и их поведение
│   ├── test_agent_simulation_step1.py # Шаг 1 симуляции агентов
│   ├── test_agent_simulation_step2.py # Шаг 2 симуляции агентов
│   ├── test_agent_simulation_step3.py # Шаг 3 симуляции агентов
│   ├── test_agent_simulation_step4.py # Шаг 4 симуляции агентов
│   ├── test_agent_simulation_step5.py # Шаг 5 симуляции агентов
│   ├── test_agent_simulation_step6.py # Шаг 6 симуляции агентов
│   ├── test_calibrator_fidelity.py # Управление fidelity уровнями (fluid/relaxed/hard/temperature)
│   ├── test_calibrator_mvp.py     # Полноценная калибровка параметров с оптимизацией
│   ├── test_constraints_executor.py # Исполнение ограничений (budget guards, validation)
│   ├── test_fiscal.py             # Фискальные механизмы (налоги, субсидии)
│   ├── test_global_state.py       # Глобальное состояние симуляции и его эволюция
│   ├── test_gradients.py          # Градиенты политик (JAX autodiff, Equinox)
│   ├── test_health.py             # Проверки здоровья системы и детекция аномалий
│   ├── test_jit_stability.py      # JIT-стабильность PyTree структур
│   ├── test_patch_executor.py     # Patch executor, state delta и snapshot'ы
│   ├── test_program_graph_ops.py  # Операции с программными графами, execution order
│   └── test_runtime_batch.py      # Пакетное выполнение программ с JAX
├── integration/                   # Интеграционные тесты end-to-end сценариев
│   ├── test_calibration_udf.py    # Калибровка параметров с UDF движком и историческими данными
│   ├── test_workflow_smoke.py     # Полный smoke-test pipeline (draft → simulate → governor → decision)
│   └── test_workflow_llm.py       # Интеграция с LLM компонентами и языковыми моделями
├── ir/                            # Тесты компонентов IR layer
│   └── test_loaders.py            # Загрузчики политик из различных форматов, norm_pack структуры
├── runtime/                       # Тесты runtime компонентов
│   └── test_runtime_manifest_paths.py # Управление runs, артефакты, пути
└── scientist/                     # Тесты компонентов scientist
    ├── governance/                # Тесты governance layer (validation pipeline, legal compliance)
    │   ├── test_legal_pass.py     # LegalPass, RuleBackend, NormPack validation
    │   └── test_validation_pipeline.py # ValidationPipeline, profiles, compliance issues
    ├── test_agent_protocols.py    # Протоколы агентов: PI, Drafter, Formalizer, Critic
    ├── test_compiler.py           # Компилятор политик из IR
    ├── test_multi_agent_workflow.py # Multi-agent workflow с critique system и памятью
    └── test_reflexion_loop.py     # Reflexion loop, failure cards, recovery mechanisms
```

## Категории тестов

### Contract Tests (`contract/`)

**Цель**: Обеспечение корректности структур данных и API контрактов на всех уровнях IR, включая валидацию схем, миграции и границы между слоями.

**Ключевые тесты:**
- **IR Contract Validation**: Полная валидация `PolicySurfaceIR`, селекторов, транслируемых строк, обязательных полей
- **Trinity Contracts**: Валидация Trinity артефактов (ProblemFrame, PolicySpec, ModelSpec) с типизированными ссылками
- **Trinity Migration**: Миграция между Surface IR и Trinity форматами с сохранением семантического fingerprint
- **Schema Migrations**: Тестирование миграций схем между версиями с сохранением совместимости
- **Fabric Gates**: Проверка входных фильтров, предусловий и валидационных барьеров Fabric layer
- **Kernel Models**: Комплексная валидация моделей ядра (slots, units, merge rules, time semantics, constraint registry)
- **Surface IR**: Тестирование Surface IR, линкера, семантических fingerprint'ов и validation reports

**Принципы:**
- **Roundtrip тестирование**: `yaml → model → yaml` сохраняет канонический формат без потерь
- **Alias acceptance**: Принимает `En/Ua/Ru`, сериализует в `en/ua/ru` для нормализации
- **Limits enforcement**: Огромные payload'ы обрабатываются без падения пайплайна
- **Type safety**: Строгая валидация типов, запрет float значений, принудительное использование Decimal для денег
- **Linker validation**: Проверка корректности связывания политик с механизмами и constraint'ами
- **Semantic fingerprinting**: Детерминированные хэши для политик независимо от порядка ключей/элементов
- **Validation reports**: Генерация подробных отчетов об ошибках с diff before/after

### Core Phase 0 Tests (`core_phase0/`)

**Цель**: Тестирование фундаментальных компонентов core layer - artifact store, канонической сериализации и registry систем.

**Ключевые тесты:**
- **Artifact Store**: FileSystemCAS, дедупликация контента, верификация integrity
- **Canonical JSON**: Детерминированная сериализация, запрет float/NaN, нормализация
- **Environment Manifest**: Захват и сравнение окружений (CPU/GPU/OS/Python/JAX), compatibility scoring
- **Registry Bundle**: Сборка и загрузка registry bundles из artifact store
- **Run Context**: Контекст выполнения, артефакты и метаданные producer'а

**Принципы:**
- Content-addressable storage: SHA256-based addressing, дедупликация
- Canonical serialization: Стабильные хэши независимо от порядка ключей
- Type safety: Запрет float значений, использование Decimal для денег
- Artifact immutability: Артефакты неизменяемы после создания
- Producer tracking: Метаданные о создателе и окружении

### Foundry Tests (`foundry/`)

**Цель**: Комплексная валидация математических моделей, симуляций на JAX, компонентов исполнения, систем калибровки и плагинной архитектуры.

**Ключевые тесты:**
- **Agent Simulation**: Пошаговая симуляция агентов (step1-step6), метрики, трекинг экспериментов, визуализация обучения
- **Plugin System**: PluginRegistry, CompositeExecutor, EconomicsPlugin, domain configurations и capability system
- **Adaptive Agents**: Поведение адаптивных агентов и их реакция на политики
- **Calibrator Fidelity**: Управление уровнями fidelity (fluid/relaxed/hard/temperature) для trade-off точность/производительность
- **Calibrator MVP**: Полноценная система калибровки параметров с оптимизацией, uncertainty quantification и penalty functions
- **Constraints Executor**: Исполнение ограничений (budget guards, validation, runtime checks)
- **Fiscal Mechanisms**: Тестирование налоговых/субсидий механизмов, их математическая корректность
- **Global State**: Эволюция глобального состояния симуляции, consistency checks
- **Gradient Health**: Проверка градиентов политик, NaN/Inf detection, numerical stability
- **Health Checks**: Системные проверки здоровья, детекция аномалий и edge cases
- **JIT Stability**: Стабильность PyTree структур при компиляции и сериализации
- **Patch Executor**: State delta, snapshot'ы, артефакт эмиссия и state management
- **Program Graph Ops**: Операции с программными графами, execution order, dependency resolution
- **Runtime Batch**: Пакетное выполнение программ с JAX для параллельной обработки

**Принципы:**
- **CPU Enforcement**: Все тесты форсируют CPU (через conftest.py) для консистентности результатов в CI/CD
- **JIT Compilation**: Проверка что `jit(step)` компилируется и сохраняет PyTree структуру
- **Gradient Sanity**: Сравнение конечных разностей vs JAX autodiff в заданных допусках
- **Invariants Verification**: Физическая корректность после шагов симуляции (масса, энергия, бюджет)
- **Constraint Enforcement**: Runtime валидация ограничений с graceful degradation
- **State Consistency**: Корректность state delta, snapshot'ов и rollback механизмов
- **Graph Execution**: Правильный порядок операций в программных графах с dependency tracking
- **Uncertainty Quantification**: Все калибровки предоставляют оценки неопределенности через Hessian analysis

### Demo Tests (`demos/`)

**Цель**: Тестирование интеграции с демонстрационными скриптами и инструментами из директории tools/demos/.

**Ключевые тесты:**
- **Laffer Demo**: Запуск и валидация демо-скрипта кривой Лаффера из tools/demos/

**Принципы:**
- **Tool Integration**: Проверка что демо-скрипты из tools/ корректно запускаются
- **Path Resolution**: Корректное разрешение относительных путей к репозиторию
- **Runtime Validation**: Успешное выполнение демо без ошибок

### Integration Tests (`integration/`)

**Цель**: Проверка end-to-end сценариев через все слои системы с использованием реальных баз данных и внешних зависимостей.

**Ключевые тесты:**
- **Calibration UDF**: Калибровка параметров с использованием UDF движка для получения целевых значений из исторических данных
- **Workflow Smoke Test**: Полный pipeline от IR до DecisionPacket с валидацией всех промежуточных артефактов
- **LLM Integration**: Тестирование интеграции с языковыми моделями, prompt engineering и workflow orchestration

**Принципы:**
- **Integration Markers**: Маркированы `pytest.mark.integration` для раздельного запуска от unit тестов
- **Real Databases**: Используют реальные БД (DuckDB/Kuzu) с тестовыми данными и schema validation
- **Full Pipeline**: Проверяют полный цикл: draft → IR validation → compilation → simulation → governor → decision
- **UDF Integration**: Тестируют получение целевых метрик через User Defined Functions из исторических данных
- **LLM Workflow**: Валидируют комплексные сценарии с AI-компонентами и state machine transitions

### Fabric Tests (`fabric/`)

**Цель**: Комплексная валидация компонентов Fabric layer - data catalog system, ingestion pipeline, evidence bundles, trust system и materialization engine.

**Ключевые тесты:**
- **Data Contract Catalog**: Валидация контрактов данных, metric bindings, registry system, поиск и разрешение метрик с disambiguation
- **Evidence Bundle**: Создание, валидация и persistence evidence артефактов после ingestion с provenance tracking
- **Provenance System**: Тестирование provenance подсистемы - entities, graphs, PROV-O экспорт, persistence и интеграция с evidence bundles
- **Trust & Uncertainty**: Двухпроходное сравнение данных, оценка uncertainty bounds, статистическая верификация доверия

**Принципы:**
- **Evidence Mandatory**: Evidence bundles обязательны в FabricResult контрактах (Law E enforcement)
- **Two-pass Comparison**: Двухпроходное сравнение для оптимистических/пессимистических сценариев и risk assessment
- **Uncertainty Quantification**: Persistence uncertainty bounds в artifact store с statistical guarantees
- **Ingestion Pipeline**: Полная интеграция raw → staging → curated трансформации с data quality checks
- **Trust Policies**: Многоуровневые политики доверия к источникам данных с cryptographic verification
- **Materialization Engine**: Incremental updates реляционных представлений из Fact Log с consistency guarantees

### IR Tests (`ir/`)

**Цель**: Валидация загрузчиков, преобразователей IR структур и универсального policy interface.

**Ключевые тесты:**
- **Policy Loaders**: Загрузка политик из различных форматов (PolicySurfaceIR объекты, словари, файлы) с type safety

**Принципы:**
- **Pass-through**: Прозрачная обработка уже загруженных PolicySurfaceIR объектов
- **Mapping Validation**: Строгая валидация структуры при загрузке из словарей/mapping'ов
- **Schema Versioning**: Поддержка versioning схем с backward compatibility
- **Universal Interface**: Единый интерфейс для всех форматов представления политик
- **Type Safety**: Принудительная типизация и валидация на этапе загрузки

### Runtime Tests (`runtime/`)

**Цель**: Валидация runtime API, управления жизненным циклом runs, артефактов и audit trail.

**Ключевые тесты:**
- **Manifest Paths**: Управление относительными/абсолютными путями в манифестах с portability guarantees
- **Artifact Logging**: Логирование артефактов с корректным path resolution и provenance tracking
- **Run Context**: Создание и управление run контекстами с метаданными producer'а и environment info

**Принципы:**
- **Relative Paths**: Относительные пути для portability артефактов между окружениями
- **Directory Portability**: Переносимость каталогов без потери доступа к артефактам
- **Path Resolution**: Корректное разрешение путей для разных типов артефактов (models, data, logs)
- **Audit Trail**: JSON Lines логирование всех операций с timestamps и metadata
- **Run Manifest**: Паспорт эксперимента с детерминированными seed'ами и reproducible execution


### Scientist Tests (`scientist/`)

**Цель**: Валидация компонентов ИИ, протоколов агентов, компиляции политик, систем recovery и governance layer.

**Ключевые тесты:**
- **Governance Layer**: Validation pipeline, compliance checks, pre/post-flight governance, legal validation passes
- **Agent Protocols**: Валидация протоколов PI/Drafter/Formalizer/Critic агентов с runtime поведением
- **Policy Compiler**: Компиляция IR в исполняемые модели foundry
- **Agent Pipeline**: Полный pipeline от user request до PolicySurfaceIR через агентов
- **Reflexion Loop**: Тестирование цикла draft → critique → refine с convergence
- **Multi-Agent Workflow**: Интеграция multi-agent системы с critique system и памятью агентов
- **Failure Cards**: Система обработки ошибок, recovery mechanisms и escalation logic
- **Short-Term Memory**: Persistence состояния и hints между попытками агентов

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

# Demo тесты (интеграция с tools/demos)
pytest tests/demos/ -v

# Fabric тесты (ingestion, evidence, trust)
pytest tests/fabric/ -v

# Foundry тесты (JAX, математические, калибровка, плагины)
pytest tests/foundry/ -v

# IR тесты (загрузчики, трансформации)
pytest tests/ir/ -v

# Runtime тесты (run management, artifacts)
pytest tests/runtime/ -v

# Интеграционные тесты (медленные, с БД)
pytest tests/integration/ -v

# Scientist тесты
pytest tests/scientist/ -v

# Governance layer тесты
pytest tests/scientist/governance/ -v                 # Validation pipeline
pytest tests/scientist/governance/test_legal_pass.py -v # Legal validation pass

# Новые компоненты scientist layer
pytest tests/scientist/test_multi_agent_workflow.py -v  # Multi-agent workflow
pytest tests/scientist/test_reflexion_loop.py -v       # Reflexion loop и failure cards
```

### Специфические сценарии

```bash
# Агентная симуляция и мониторинг
pytest tests/foundry/agent_sim/test_monitoring.py

# Плагинная система Foundry
pytest tests/foundry/plugins/test_plugin_system.py

# Demo скрипты
pytest tests/demos/run_laffer_demo.py

# Адаптивные агенты и их поведение
pytest tests/foundry/test_adaptive_agents.py

# Калибровка fidelity (управление точностью)
pytest tests/foundry/test_calibrator_fidelity.py

# Полноценная калибровка параметров
pytest tests/foundry/test_calibrator_mvp.py

# Пакетное выполнение программ
pytest tests/foundry/test_runtime_batch.py

# Калибровка с UDF движком (интеграционный)
pytest tests/integration/test_calibration_udf.py

# Тесты градиентов (требуют Equinox)
pytest tests/foundry/test_gradients.py

# Тесты workflow (требуют LLM API ключей)
pytest tests/integration/test_workflow_llm.py

# Smoke test (минимальный полный цикл)
pytest tests/integration/test_workflow_smoke.py

# Data contract catalog system
pytest tests/fabric/test_data_catalog.py

# Evidence bundles и ingestion
pytest tests/fabric/test_evidence_bundle.py

# Provenance subsystem
pytest tests/fabric/test_provenance.py

# Trust и uncertainty bounds
pytest tests/fabric/test_trust_two_pass.py

# Policy loaders
pytest tests/ir/test_loaders.py

# Runtime manifest paths
pytest tests/runtime/test_runtime_manifest_paths.py
```

## Технологии и зависимости

### Core Testing Framework
- **pytest**: Основной фреймворк с плагинами
- **pytest-cov**: Покрытие кода (опционально)

### Domain-Specific Libraries
- **JAX/Equinox/Optax**: Для тестирования математических компонентов, симуляций, градиентов и оптимизации
- **pandas/PyArrow**: Работа с тестовыми данными, ETL и columnar storage
- **DuckDB/Kuzu**: Интеграционные тесты с базами данных, графовыми и реляционными данными
- **Pydantic v2**: Строгая валидация структур данных и контрактов, включая legal norm schemas
- **pathlib**: Работа с файловой системой в core/runtime тестах
- **hashlib**: SHA256 хэширование для artifact integrity и content addressing
- **UDF Engine**: User Defined Functions для сложных запросов к данным с security passes
- **Calibration Engine**: Оптимизация параметров с Hessian uncertainty quantification
- **Fact Log System**: Immutable факты с provenance tracking и детерминированные ID
- **Materializer Engine**: Инкрементальная материализация реляционных представлений
- **Trust System**: Статистическая верификация доверия к данным с evidence bundles
- **Plugin System**: Модульная архитектура с capability-based plugin registry и composite executors
- **Agent Simulation**: Пошаговая симуляция агентов с метриками, трекингом экспериментов и визуализацией
- **Trinity Architecture**: Разделение политик на ProblemFrame/PolicySpec/ModelSpec с типизированными ссылками
- **Agent Protocols**: Стандартизированные интерфейсы для PI/Drafter/Formalizer/Critic агентов
- **Failure Card System**: Система обработки ошибок с recovery mechanisms и escalation logic
- **Reflexion Orchestrator**: Автоматический оркестратор retry loops с backoff и decision making
- **Short-Term Memory**: Persistence состояния агентов между попытками с hint accumulation
- **Multi-Agent Workflow**: Интегрированная система workflow с critique-based refinement
- **Legal Validation System**: Pluggable backends для оценки юридических норм с protocol-based architecture
- **Norm Pack Contracts**: Структурированные представления юридических норм (NormPack, NormRule, NormRef)
- **Rule Backend System**: Extensible evaluators для разных типов правил (AST, LLM, Stub implementations)
- **Environment Manifest**: Захват и сравнение вычислительных окружений для reproducibility

## Принципы тестирования

### Архитектурные инварианты
- **Закон A**: Граф зависимостей только внутрь (scientist → ir/fabric/foundry/runtime/core)
- **Закон B**: Компиляторная труба (NL → LLM → IR → Compilation → Runtime)
- **Закон C**: Контракты как источник истины (структура определена в IR, экспортируется в JSON Schema)
- **Закон D**: Core layer как фундамент (core → runtime → ir → fabric → foundry → scientist)
- **Закон E**: Evidence обязательны (FabricResult всегда содержит evidence_ref, Law H)
- **Закон F**: Fidelity control (система может форсировать уровни точности для производительности)
- **Закон G**: Uncertainty quantification (все калибровки предоставляют оценки неопределенности)
- **Закон H**: Evidence обязательны (data провода фиксируют provenance/evidence)
- **Закон I**: Trust policies (многоуровневые политики доверия к источникам данных)

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

### Fabric Layer (`fabric/`)
**Data Catalog System** → Metadata management and discovery
- **Data Contract Catalog**: Структурированные контракты данных с типами, гранулярностью, PII уровнями
- **Metric Bindings**: Hash-интегрированные привязки метрик к контрактам с валидацией целостности
- **Metric Searcher**: Поиск и разрешение метрик с disambiguation логикой и fuzzy matching
- **Contract Registry**: Загрузка, валидация и управление каталогом контрактов данных

**Data Ingestion & Evidence** → Raw data processing
- **Ingestion Pipeline**: Raw → Staging → Curated трансформация
- **Evidence Bundles**: Артефакты результатов ingestion с метаданными
- **Trust Engine**: Оценка доверия и uncertainty bounds для данных

**Data Trust & Validation** → Quality assurance
- **Two-pass Comparison**: Оптимистические/пессимистические сценарии
- **Uncertainty Quantification**: Статистическая оценка неопределенности
- **Core Artifacts**: Хранение evidence bundles и trust metrics

### IR Layer (`ir/`)
**Policy Loading & Transformation** → Universal policy interface
- **Policy Loaders**: Загрузка из различных форматов (объекты, словари, файлы)
- **Surface IR**: Семантическая модель политик
- **Contract Validation**: Валидация структур данных

**Schema Management** → Version compatibility
- **Schema Evolution**: Миграции между версиями IR
- **Type Safety**: Строгая валидация типов и структур

### Runtime Layer (`runtime/`)
**Run Lifecycle Management** → Execution orchestration
- **Run Manifests**: Метаданные и артефакты выполнения
- **Artifact Management**: Логирование и разрешение путей артефактов
- **Path Resolution**: Относительные/абсолютные пути для portability

**Execution Context** → Environment management
- **Run Context**: Контекст выполнения с метаданными producer'а
- **Artifact Store Integration**: Связь с core artifact storage

### Foundry Layer (`foundry/`)
**Simulation Engine** → JAX-based execution с mathematical guarantees
- **Agent Simulation**: Пошаговая симуляция агентов с метриками, экспериментальным трекингом и визуализацией
- **Plugin System**: Модульная архитектура с capability-based plugin registry и composite executors
- **Adaptive Agents**: Поведенческие модели агентов с learning capabilities
- **Constraints Executor**: Runtime валидация ограничений (budget guards, validation)
- **Patch Executor**: State management через UpdateOp и Merge Rules, snapshots
- **Program Graphs**: Оркестрация execution order с dependency tracking
- **Runtime Batch**: Пакетное выполнение для производительности и parallelization
- **Fiscal Mechanisms**: Налоговые/субсидий механизмы с mathematical correctness
- **Global State**: Эволюция состояния симуляции с consistency checks

**Calibration System** → Parameter optimization с uncertainty quantification
- **Calibrator MVP**: Полноценная калибровка параметров по целевым метрикам с optimization
- **Fidelity Control**: Управление точностью/производительностью trade-off (fluid/relaxed/hard/temperature)
- **Uncertainty Analysis**: Квантификация неопределенности через Hessian analysis и statistical methods
- **IR Surface**: Исходные политики для компиляции и validation
- **Core Artifacts**: Хранение скомпилированных программ и calibration results
- **Fabric Trust**: Интеграция с uncertainty bounds и evidence-based validation
- **Integration**: End-to-end pipeline validation с UDF-based targets

### Integration Layer (`integration/`)
**Workflow Orchestration** → End-to-end scenarios
- **Scientist**: LLM-driven policy drafting через agent protocols
- **Foundry**: Simulation execution с calibration и fidelity control
- **Fabric**: Data ingestion, evidence bundles и trust quantification
- **IR**: Policy compilation pipeline и Trinity migration
- **Governance**: Pre/post-flight validation и compliance checks

**LLM Integration** → AI-powered components
- **Agent Pipeline**: PI → Drafter → Formalizer → Critic workflow
- **Reflexion Loop**: Critique-based policy refinement и convergence с failure recovery
- **Multi-Agent Workflow**: Интегрированная система workflow с critique system
- **Failure Cards**: Error handling и recovery mechanisms для LLM interactions
- **Short-Term Memory**: State persistence между agent attempts с hint accumulation
- **Reflexion Orchestrator**: Автоматический retry management с escalation logic
- **Trinity Migration**: Seamless transition между Surface IR и Trinity formats

### Legal Validation System
**Norm Pack Contracts** → Legal rule definitions and evaluation
- **IR Layer**: NormPack, NormRule, NormRef структуры для представления юридических норм
- **Core Contracts**: Стабильные экспорты legal типов через core/contracts/legal.py
- **Scientist Governance**: LegalPass для валидации политик против юридических норм
- **Rule Backends**: Pluggable backends (StubBackend, будущие AST/LLM evaluators)

**Legal Compliance Evaluation** → Policy validation against legal frameworks
- **Governance Layer**: LegalPass с configurable backends и profile-based execution
- **Rule Types**: Obligation/Prohibition/Permission классификация норм
- **Jurisdiction Support**: Multi-jurisdiction norm packs с effective dates
- **Backend System**: Extensible rule evaluation с protocol-based architecture

### Trinity Architecture Integration
**ProblemFrame** → Policy context and constraints
- **Contract Tests**: Schema validation и reference integrity
- **IR Layer**: Migration between Surface IR и Trinity formats
- **Scientist**: Problem decomposition и context для агентов

**PolicySpec** → Intervention definitions
- **Contract Tests**: Roundtrip serialization и cross-reference validation
- **Scientist**: Formalization от draft до executable IR

**ModelSpec** → Simulation parameters
- **Contract Tests**: Data snapshot validation и assumption tracking
- **Foundry**: Calibration targets и model configuration

### CI/CD интеграция
- Unit тесты запускаются на каждый PR
- Integration тесты - по расписанию или на release
- Архитектурные гейты предотвращают регрессии
- Coverage thresholds для предотвращения снижения качества

## Разработка и расширение

### Добавление новых тестов
1. Определите категорию (contract/core_phase0/demos/fabric/foundry/ir/runtime/integration/scientist)
2. Следуйте naming convention: `test_*.py`
3. Используйте fixtures из соответствующего `conftest.py`
4. Маркируйте медленные тесты `@pytest.mark.integration`
5. Для core/runtime тестов используйте специфичные fixtures (store, producer, env_info)
6. Для fabric тестов проверяйте работу с evidence bundles и trust metrics
7. Для foundry тестов включайте проверки fidelity control и uncertainty quantification
8. Для calibration тестов тестируйте convergence, penalties и parameter recovery
9. Для plugin system тестов проверяйте capability system, composite executors и domain configs
10. Для agent simulation тестов валидируйте метрики, экспериментальный трекинг и визуализацию
11. Для demo тестов проверяйте интеграцию с tools/ и корректность path resolution

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

**Calibration convergence issues:**
```bash
# Калибровка может не сходиться при неправильных гиперпараметрах
pytest tests/foundry/test_calibrator_mvp.py::test_calibrator_recovers_income_tax_rate -v --tb=long
# Проверьте learning_rate, max_steps, seed и fidelity level
```

**Adaptive agents instability:**
```bash
# Адаптивные агенты могут показывать нестабильное поведение
pytest tests/foundry/test_adaptive_agents.py -v --tb=short
# Проверьте random seed и параметры learning rate
```

**UDF engine database issues:**
```bash
# Проверьте что тестовые БД корректно инициализированы
pytest tests/integration/test_calibration_udf.py -v --tb=short
# Очистите кэш если возникают конфликты
rm -rf tmp_path/.polisyos tmp_path/*.duckdb
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

**Fabric ingestion failures:**
```bash
# Проверьте структуру тестовых CSV файлов
pytest tests/fabric/test_evidence_bundle.py -v
# Убедитесь что raw/staging/curated директории существуют
```

**Plugin system issues:**
```bash
# Проверьте что плагины корректно регистрируются
pytest tests/foundry/plugins/test_plugin_system.py -v
# Проверьте capability system и composite executors
```

**Agent simulation failures:**
```bash
# Проверьте метрики и трекинг экспериментов
pytest tests/foundry/agent_sim/test_monitoring.py -v
# Проверьте визуализацию и dashboard generation
```

**Trinity migration failures:**
```bash
# Проверьте semantic fingerprint preservation
pytest tests/contract/test_trinity_migration.py::TestRoundTrip::test_roundtrip_semantic_fingerprint -v
# Проверьте zero data loss
pytest tests/contract/test_trinity_migration.py::TestRoundTrip::test_roundtrip_minimal -v
```

**Agent protocol failures:**
```bash
# Проверьте protocol conformance
pytest tests/scientist/test_agent_protocols.py::TestProtocolConformance -v
# Проверьте agent pipeline flow
pytest tests/scientist/test_agent_protocols.py::TestAgentPipeline::test_full_pipeline_flow -v
```

**Environment manifest issues:**
```bash
# Проверьте environment capture
pytest tests/core_phase0/test_environment_manifest.py::TestCaptureEnvironment::test_capture_returns_valid_manifest -v
# Проверьте compatibility scoring
pytest tests/core_phase0/test_environment_manifest.py::TestEnvironmentManifest::test_compatibility_score_identical -v
```

**Demo script failures:**
```bash
# Проверьте интеграцию с tools/demos
pytest tests/demos/run_laffer_demo.py -v
# Убедитесь что пути к репозиторию разрешаются корректно
```

**Reflexion loop failures:**
```bash
# Проверьте reflexion orchestrator decisions
pytest tests/scientist/test_reflexion_loop.py::TestReflexionOrchestrator -v
# Проверьте failure card generation
pytest tests/scientist/test_reflexion_loop.py::TestFailureCardSchema -v
```

**Multi-agent workflow failures:**
```bash
# Проверьте workflow orchestration
pytest tests/scientist/test_multi_agent_workflow.py::TestMultiAgentWorkflow -v
# Проверьте memory persistence
pytest tests/scientist/test_multi_agent_workflow.py::TestShortTermMemory -v
```

**Failure card recovery issues:**
```bash
# Проверьте recovery mechanisms
pytest tests/scientist/test_reflexion_loop.py::TestFailureCardConverters -v
# Проверьте state management
pytest tests/scientist/test_reflexion_loop.py::TestStateManagement -v
```

### Полезные команды диагностики

```bash
# Проверка что все зависимости установлены
python tools/diagnostics/check_setup.py

# Генерация схем для проверки контрактов
python tools/diagnostics/generate_ir_schema.py

# Диагностика calibration системы
python tools/diagnostics/check_calibration_setup.py

# Проверка fabric ingestion pipeline
python tools/diagnostics/validate_fabric_pipeline.py

# Линтинг тест кода
ruff check tests/

# Проверка JAX/calibration зависимостей
python -c "import jax, jax.numpy as jnp; from polisyos.foundry.calibration import calibrator; print('Calibration dependencies OK')"

# Диагностика trust system и evidence bundles
python -c "from polisyos.fabric.trust import TrustEngine; from polisyos.fabric.evidence import EvidenceBundle; print('Trust system OK')"

# Проверка materializer engine
python -c "from polisyos.fabric.materializer import MaterializerEngine; print('Materializer engine OK')"

# Проверка plugin system
python -c "from polisyos.foundry.plugins.core import PluginRegistry; from polisyos.foundry.plugins.economics import EconomicsPlugin; print('Plugin system OK')"

# Проверка agent simulation
python -c "from polisyos.foundry.agent_sim import MetricsCollector, ExperimentTracker; print('Agent simulation OK')"

# Проверка legal validation system
python -c "from polisyos.scientist.governance.passes.legal_pass import LegalPass; from polisyos.ir.norm_pack import NormPack; print('Legal validation OK')"

# Проверка norm pack contracts
python -c "from polisyos.core.contracts.legal import NormPack, NormRule, RuleType; print('Norm pack contracts OK')"

# Проверка Trinity architecture
python -c "from polisyos.ir.trinity import TrinityBundle; from polisyos.ir.problem_frame import ProblemFrame; print('Trinity architecture OK')"

# Проверка agent protocols
python -c "from polisyos.scientist.agent.protocols import AGENT_PROTOCOLS, AgentRole; print('Agent protocols OK')"

# Проверка failure card system
python -c "from polisyos.scientist.agent.failure_card import FailureCard, FailureSource; print('Failure card system OK')"

# Проверка reflexion orchestrator
python -c "from polisyos.scientist.agent.reflexion import ReflexionOrchestrator; print('Reflexion orchestrator OK')"

# Проверка short-term memory
python -c "from polisyos.scientist.agent.memory import ShortTermMemory; print('Short-term memory OK')"

# Проверка multi-agent workflow
python -c "from polisyos.scientist.orchestrator.workflow import build_workflow; print('Multi-agent workflow OK')"

# Проверка data contract catalog system
python -c "from polisyos.fabric.catalog.contract import DataContract, DataContractCollection; from polisyos.fabric.catalog.registry import DataContractRegistry; from polisyos.fabric.catalog.search import MetricSearcher; print('Data contract catalog OK')"

# Проверка environment manifest
python -c "from polisyos.core.artifacts.environment import capture_environment; print('Environment manifest OK')"
```

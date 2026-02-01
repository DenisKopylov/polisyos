# Foundry Tests

Комплексная валидация математических моделей, симуляций на JAX, компонентов исполнения, систем калибровки и плагинной архитектуры.

**Последнее обновление:** 1 февраля 2026
**Уровень:** Foundry Layer (Simulation Engine)
**Зависимости:** JAX, Equinox, Optax, Core artifacts, Fabric trust

## Архитектурный контекст

Foundry layer представляет собой JAX-based simulation engine с математическими гарантиями. Тесты валидируют execution, calibration, plugin system и agent simulation с полным coverage всех fidelity levels и uncertainty quantification.

## Структура тестов

```
foundry/
├── agent_sim/                     # Тесты симуляции агентов
│   └── test_monitoring.py         # MetricsCollector, ExperimentTracker, DashboardGenerator, визуализация
├── plugins/                       # Тесты плагинной системы Foundry
│   └── test_plugin_system.py      # PluginRegistry, CompositeExecutor, EconomicsPlugin, domain configs
├── test_adaptive_agents.py        # Адаптивные агенты и их поведение
├── test_agent_simulation_step1.py # Шаг 1 симуляции агентов
├── test_agent_simulation_step2.py # Шаг 2 симуляции агентов
├── test_agent_simulation_step3.py # Шаг 3 симуляции агентов
├── test_agent_simulation_step4.py # Шаг 4 симуляции агентов
├── test_agent_simulation_step5.py # Шаг 5 симуляции агентов
├── test_agent_simulation_step6.py # Шаг 6 симуляции агентов
├── test_calibrator_fidelity.py    # Управление fidelity уровнями (fluid/relaxed/hard/temperature)
├── test_calibrator_mvp.py         # Полноценная калибровка параметров с оптимизацией
├── test_conflict_detection.py     # Compile-time conflict detection (multiple writers, merge rules)
├── test_constraints_executor.py   # Исполнение ограничений (budget guards, validation)
├── test_cost_model.py             # Cost estimation model (compile/runtime costs, budget checks)
├── test_fiscal.py                 # Фискальные механизмы (налоги, субсидии)
├── test_global_state.py           # Глобальное состояние симуляции и его эволюция
├── test_gradients.py              # Градиенты политик (JAX autodiff, Equinox)
├── test_health.py                 # Проверки здоровья системы и детекция аномалий
├── test_jit_compilation_tracker.py # JIT compilation tracking и optimization metrics
├── test_jit_stability.py          # JIT-стабильность PyTree структур
├── test_merge_determinism.py      # Детерминизм операций merge и state consistency
├── test_nan_guard.py              # NaN/Inf detection guard (runtime numerical stability)
├── test_patch_executor.py         # Patch executor, state delta и snapshot'ы
├── test_program_graph_ops.py      # Операции с программными графами, execution order
└── test_runtime_batch.py          # Пакетное выполнение программ с JAX
```

## Категории тестов

### Agent Simulation (`agent_sim/`)

**Цель:** Пошаговая валидация симуляции агентов с метриками, трекингом экспериментов и визуализацией.

**Ключевые тесты:**
- **Metrics Collection**: Сбор и анализ метрик обучения (loss, reward, custom metrics)
- **Experiment Tracking**: Управление экспериментами с конфигурациями и результатами
- **Dashboard Generation**: Создание визуализаций и отчетов обучения
- **Behavior Analysis**: Кластеризация агентов по поведению и паттернам

**Принципы:**
- **Structured Metrics**: Типизированная система метрик (scalar, histogram, distribution)
- **Experiment Lifecycle**: Полный цикл от конфигурации до результатов
- **Visualization Pipeline**: Автоматическая генерация графиков и dashboards
- **Behavior Clustering**: ML-based анализ поведения агентов

### Plugin System (`plugins/`)

**Цель:** Валидация модульной архитектуры с capability-based plugin registry.

**Ключевые тесты:**
- **Plugin Registry**: Регистрация, поиск и управление плагинами
- **Composite Executors**: Оркестрация execution через multiple domains
- **Domain Configuration**: Настройка domain-specific параметров и constraints
- **Capability System**: Проверка compatibility и feature detection

**Принципы:**
- **Capability-based Design**: Плагины регистрируют свои возможности
- **Composite State**: Оркестрация состояния через multiple domains
- **Domain Isolation**: Независимое управление domain-specific logic
- **Plugin Discovery**: Автоматическое обнаружение и загрузка плагинов

### Agent Simulation Steps (step1-step6)

**Цель:** Пошаговая валидация execution pipeline симуляции агентов.

**Ключевые тесты:**
- **Active Mask Propagation**: Корректная обработка активных/неактивных агентов
- **Mechanism Execution Order**: Правильная последовательность применения механизмов
- **State Consistency**: Сохранение инвариантов состояния между шагами
- **Fidelity Level Handling**: Корректная обработка разных уровней точности

**Принципы:**
- **Mechanism Ordering**: Детерминированный порядок execution механизмов
- **State Invariants**: Сохранение физических и экономических инвариантов
- **Fidelity Trade-offs**: Управление точность/производительность балансом
- **Error Propagation**: Graceful handling ошибок в pipeline

### Adaptive Agents (`test_adaptive_agents.py`)

**Цель:** Валидация поведенческих моделей агентов с learning capabilities.

**Ключевые тесты:**
- **Learning Dynamics**: Корректность adaptation к политикам
- **Behavior Evolution**: Изменение поведения под влиянием incentives
- **Equilibrium Finding**: Сходимость к stable states
- **Diversity Preservation**: Сохранение разнообразия в популяции

**Принципы:**
- **Learning Algorithms**: Реализация reinforcement learning и adaptation
- **Behavioral Diversity**: Поддержание heterogeneous поведения
- **Policy Response**: Реакция на изменения в policy parameters
- **Stability Analysis**: Анализ convergence и equilibrium properties

### Calibrator System

**Fidelity Control** (`test_calibrator_fidelity.py`):
- **Level Switching**: Переключение между fluid/relaxed/hard/temperature
- **Performance Trade-offs**: Валидация impact на скорость/точность
- **Numerical Stability**: Сохранение stability при разных fidelity levels

**MVP Calibration** (`test_calibrator_mvp.py`):
- **Parameter Optimization**: Gradient-based optimization параметров
- **Convergence Analysis**: Сходимость к target values
- **Uncertainty Quantification**: Hessian-based uncertainty estimates
- **Penalty Functions**: Регуляризация и constraint enforcement

### Conflict Detection System (`test_conflict_detection.py`)

**Цель:** Compile-time обнаружение и валидация конфликтов в программных графах.

**Ключевые тесты:**
- **Multiple Writers Detection**: Обнаружение конфликтов при записи в один slot несколькими механизмами
- **Merge Rule Validation**: Проверка корректности merge rules (error/sum/override)
- **Slot Registry Integration**: Валидация против slot registry и merge registry
- **Conflict Report Generation**: Генерация отчетов о конфликтах с severity levels
- **Strict Mode Validation**: Проверка unknown slots в strict режиме

**Принципы:**
- **Compile-time Safety**: Предотвращение runtime конфликтов через static analysis
- **Merge Rule Enforcement**: Строгая валидация merge semantics
- **Severity Classification**: blocker/warning уровни для разных типов конфликтов
- **Issue Format Conversion**: Стандартизация отчетов для governance pipeline

### Cost Estimation System (`test_cost_model.py`)

**Цель:** Оценка стоимости выполнения программ и budget management.

**Ключевые тесты:**
- **Cost Estimation**: Расчет времени компиляции, runtime и memory usage
- **Scaling Analysis**: Валидация масштабирования с количеством агентов и шагов времени
- **Budget Enforcement**: Проверка соблюдения бюджетных ограничений
- **Telemetry Calibration**: Обновление модели на основе реальных измерений
- **Exponential Moving Average**: Калибровка через historical data

**Принципы:**
- **Mechanism-based Estimation**: Cost per mechanism с configurable multipliers
- **Resource Prediction**: Memory, CPU time и compilation time estimates
- **Budget Violations**: Detection и reporting превышений бюджета
- **Self-calibrating**: Автоматическая калибровка через runtime telemetry

### Execution Components

**Constraints Executor** (`test_constraints_executor.py`):
- **Budget Guards**: Runtime проверки бюджетных ограничений
- **Validation Logic**: Enforcement business rules
- **Graceful Degradation**: Handling constraint violations

**Fiscal Mechanisms** (`test_fiscal.py`):
- **Taxation Models**: Progressive/regressive tax schedules
- **Subsidy Systems**: Transfer payment mechanisms
- **Mathematical Correctness**: Economic model validation

**Global State** (`test_global_state.py`):
- **State Evolution**: Consistency при temporal evolution
- **Snapshot Integrity**: Correct state captures
- **Rollback Safety**: Safe state restoration

### Mathematical Validation

**Gradients** (`test_gradients.py`):
- **Autodiff Correctness**: JAX gradient computation validation
- **Finite Differences**: Comparison с numerical derivatives
- **NaN/Inf Detection**: Numerical stability monitoring

**JIT Stability** (`test_jit_stability.py`):
- **PyTree Structure**: Preservation при compilation
- **Serialization Safety**: Stable serialization/deserialization
- **Performance Consistency**: No regression в compiled execution

**JIT Compilation Tracker** (`test_jit_compilation_tracker.py`):
- **First Call Detection**: Tracking initial compilation vs cached execution
- **Signature Key Generation**: Unique identification функций по input shapes
- **Shape Distinction**: Different signatures для различных input dimensions
- **Optimization Metrics**: Compilation caching и performance optimization

**NaN Guard** (`test_nan_guard.py`):
- **Runtime Monitoring**: Detection NaN/Inf значений в state arrays
- **Diagnostic Reports**: Подробные отчеты с sample indices и cause detection
- **Profile-based Configuration**: Different guard profiles (strict/fast/mvp)
- **Check Interval Control**: Configurable frequency проверки для performance trade-off

### Advanced Execution

**Merge Determinism** (`test_merge_determinism.py`):
- **Merge Operations**: Детерминированные merge rules с consistency guarantees
- **State Evolution**: Предсказуемая эволюция состояния через merge operations
- **Conflict Resolution**: Deterministic resolution конфликтов в state updates

**Patch Executor** (`test_patch_executor.py`):
- **State Delta**: Incremental state updates
- **Snapshot Management**: Efficient state versioning
- **Artifact Emission**: Result persistence

**Program Graph Ops** (`test_program_graph_ops.py`):
- **Dependency Resolution**: Correct execution ordering
- **Graph Traversal**: Efficient DAG execution
- **Parallel Execution**: Concurrent operation scheduling

**Runtime Batch** (`test_runtime_batch.py`):
- **Batch Processing**: Vectorized execution
- **Memory Efficiency**: Optimal resource utilization
- **Scalability Testing**: Performance under load

## Запуск тестов

```bash
# Все foundry тесты (CPU-enforced)
pytest tests/foundry/ -v

# Конкретные подсистемы
pytest tests/foundry/agent_sim/ -v
pytest tests/foundry/plugins/ -v

# Пошаговая симуляция
pytest tests/foundry/test_agent_simulation_step*.py -v

# Калибровка и оптимизация
pytest tests/foundry/test_calibrator_*.py -v

# Конфликт детекция и cost estimation
pytest tests/foundry/test_conflict_detection.py -v
pytest tests/foundry/test_cost_model.py -v

# Execution компоненты
pytest tests/foundry/test_*executor*.py -v
pytest tests/foundry/test_*batch*.py -v

# Математическая валидация
pytest tests/foundry/test_gradients.py -v
pytest tests/foundry/test_jit_compilation_tracker.py -v
pytest tests/foundry/test_jit_stability.py -v
pytest tests/foundry/test_nan_guard.py -v
```

## Конфигурация окружения

### JAX Configuration (conftest.py в корне)
```python
# CPU enforcement для consistency в CI/CD
os.environ["JAX_PLATFORM_NAME"] = "cpu"
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
```

## Связи с другими модулями

### Зависимости Foundry Layer

**Core Layer** (`core/`):
- **Artifact Storage**: Persistence compiled programs и calibration results
- **Registry System**: Access to mechanisms, slots, constraints

**Fabric Layer** (`fabric/`):
- **Trust Integration**: Uncertainty bounds в calibration
- **Evidence-based Validation**: Data validation через evidence bundles

**IR Layer** (`ir/`):
- **Policy Compilation**: Surface IR → executable foundry programs

### Потребители Foundry Layer

**Scientist Layer** (`scientist/`):
- **Simulation Execution**: Running compiled policies
- **Calibration Orchestration**: Parameter optimization workflows

**Integration Layer** (`integration/`):
- **End-to-end Pipeline**: Full simulation workflows
- **UDF-based Targets**: Complex objective functions

### Архитектурные инварианты

- **Закон F**: Fidelity control (система может форсировать уровни точности)
- **Закон G**: Uncertainty quantification (все калибровки предоставляют uncertainty)
- **CPU Enforcement**: Все тесты форсируют CPU для reproducible results
- **JIT Compilation**: Validation что `jit(step)` компилируется корректно

## Разработка и расширение

### Добавление новых foundry тестов

1. **Для execution тестов**: Проверяйте roundtrip state consistency, gradient correctness
2. **Для calibration тестов**: Валидируйте convergence, uncertainty quantification, parameter recovery
3. **Для plugin тестов**: Проверяйте capability system, composite state management
4. **Для agent sim тестов**: Тестируйте metrics collection, experiment tracking, visualization
5. **Всегда форсируйте CPU**: `JAX_PLATFORM_NAME=cpu` для reproducible results

### Отладка foundry тестов

```bash
# С подробным выводом для конкретного теста
pytest tests/foundry/test_gradients.py::test_tax_subsidy_gradient_value -v -s

# С CPU enforcement (если не установлен глобально)
JAX_PLATFORM_NAME=cpu pytest tests/foundry/test_jit_stability.py -v

# Профилирование памяти
pytest tests/foundry/test_runtime_batch.py --profile
```

## Troubleshooting

### Распространенные проблемы

**JAX memory allocation errors:**
```bash
# Решение: форсируйте CPU
export JAX_PLATFORM_NAME=cpu
pytest tests/foundry/
```

**Calibration convergence issues:**
```bash
# Проверьте learning_rate, max_steps, seed
pytest tests/foundry/test_calibrator_mvp.py::test_calibrator_recovers_income_tax_rate -v --tb=long
```

**Adaptive agents instability:**
```bash
# Проверьте random seed и learning parameters
pytest tests/foundry/test_adaptive_agents.py -v --tb=short
```

**Conflict detection failures:**
```bash
# Проверьте slot registry и merge rules
pytest tests/foundry/test_conflict_detection.py::TestConflictDetectionBasics::test_multi_writer_error_rule_conflict -v
# Проверьте strict mode validation
pytest tests/foundry/test_conflict_detection.py::TestConflictDetectionEdgeCases::test_unknown_slot_strict_mode -v
```

**Cost model calibration issues:**
```bash
# Проверьте mechanism registry alignment
pytest tests/foundry/test_cost_model.py::TestCostModelBasics::test_multiplier_keys_match_registry -v
# Проверьте telemetry updates
pytest tests/foundry/test_cost_model.py::TestCostModelCalibration::test_update_from_telemetry -v
```

**NaN guard detection failures:**
```bash
# Проверьте JAX array handling
pytest tests/foundry/test_nan_guard.py::TestNaNGuardBasics::test_enabled_guard_catches_nan -v
# Проверьте profile configuration
pytest tests/foundry/test_nan_guard.py::TestNaNGuardProfileFactory::test_strict_profile_enabled -v
```

**Plugin system registration failures:**
```bash
# Проверьте capability declarations
pytest tests/foundry/plugins/test_plugin_system.py::TestPluginRegistry -v
```

**Agent simulation state corruption:**
```bash
# Проверьте mechanism ordering
pytest tests/foundry/test_agent_simulation_step1.py::test_active_mask_propagation -v
```

**Merge determinism failures:**
```bash
# Проверьте deterministic merge operations
pytest tests/foundry/test_merge_determinism.py -v
# Проверьте state consistency после merge
pytest tests/foundry/test_merge_determinism.py -v --tb=short
```

**JIT compilation tracker failures:**
```bash
# Проверьте signature key generation
pytest tests/foundry/test_jit_compilation_tracker.py::test_jit_tracker_marks_first_call -v
# Проверьте shape distinction
pytest tests/foundry/test_jit_compilation_tracker.py::test_jit_tracker_distinguishes_shapes -v
```

**Gradient computation failures:**
```bash
# Сравните с finite differences
pytest tests/foundry/test_gradients.py -v --tb=long
```

## Технологии и зависимости

### Core Simulation Stack
- **JAX**: Autodiff, JIT compilation, vectorized operations
- **Equinox**: Neural network library для gradient-based components
- **Optax**: Optimization library для calibration algorithms

### Plugin Architecture
- **Plugin Registry**: Capability-based plugin management
- **Composite Executors**: Multi-domain state orchestration
- **Domain Configuration**: Declarative domain setup

### Agent Simulation
- **Metrics Collection**: Structured metrics с visualization
- **Experiment Tracking**: ML experiment management
- **Behavior Analysis**: Clustering и pattern recognition

### Mathematical Validation
- **Gradient Testing**: Autodiff vs finite differences comparison
- **JIT Stability**: PyTree structure preservation
- **JIT Compilation Tracking**: First-call detection, signature key generation, optimization metrics
- **Numerical Analysis**: NaN/Inf detection, stability monitoring
- **NaN Guard**: Runtime numerical stability monitoring с diagnostics

### Calibration System
- **Fidelity Control**: Multi-level precision management
- **Uncertainty Quantification**: Hessian-based confidence intervals
- **Optimization**: Gradient-based parameter fitting с constraints

### Program Validation
- **Conflict Detection**: Compile-time conflict analysis для program graphs
- **Merge Rule Validation**: Slot conflict resolution и merge semantics
- **Issue Reporting**: Standardized conflict reports для governance pipeline

### Cost Estimation
- **Performance Modeling**: Mechanism-based cost estimation
- **Budget Management**: Resource constraint enforcement
- **Telemetry Calibration**: Runtime performance learning
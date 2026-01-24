# Foundry Tests

Комплексная валидация математических моделей, симуляций на JAX, компонентов исполнения, систем калибровки и плагинной архитектуры.

**Последнее обновление:** Январь 2026
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
├── test_constraints_executor.py   # Исполнение ограничений (budget guards, validation)
├── test_fiscal.py                 # Фискальные механизмы (налоги, субсидии)
├── test_global_state.py           # Глобальное состояние симуляции и его эволюция
├── test_gradients.py              # Градиенты политик (JAX autodiff, Equinox)
├── test_health.py                 # Проверки здоровья системы и детекция аномалий
├── test_jit_stability.py          # JIT-стабильность PyTree структур
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

### Advanced Execution

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

# Execution компоненты
pytest tests/foundry/test_*executor*.py -v
pytest tests/foundry/test_*batch*.py -v

# Математическая валидация
pytest tests/foundry/test_gradients.py -v
pytest tests/foundry/test_jit_stability.py -v
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
- **Numerical Analysis**: NaN/Inf detection, stability monitoring

### Calibration System
- **Fidelity Control**: Multi-level precision management
- **Uncertainty Quantification**: Hessian-based confidence intervals
- **Optimization**: Gradient-based parameter fitting с constraints
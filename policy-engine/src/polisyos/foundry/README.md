# Foundry — Policy Execution Engine

Foundry — высокопроизводительный execution engine для дифференцируемого исполнения экономических политик. Преобразует декларативные политики из Trinity IR в оптимизированные графы выполнения, калибрует параметры на реальных данных и исполняет симуляции с полной воспроизводимостью.

**155 модулей** | **JAX/Equinox** | **Patch-based execution** | **Content-addressable artifacts**

## Роль в системе

```
scientist/ → ir/ → foundry.compile → foundry.calibration → foundry.execute → artifacts
                        ↓                     ↓                    ↓
                  core/artifacts         core/contracts        core/observability
```

Foundry — чисто вычислительный backend, работающий исключительно с JAX. Никаких БД, LLM или сетевых вызовов. Основные потребители — `scientist/` (оркестрация экспериментов) и `packs/` (доменные расширения).

## Архитектура

Foundry организован послойно, от данных к оркестрации:

### Domain Layer — модель предметной области

`domain/state.py` определяет центральную модель состояния как frozen chex-dataclasses с JAX-типизацией (jaxtyping):

- **AgentState** — per-agent массивы: `active`, `age`, `skill_level`, `income`, `reported_income`, `savings`, `consumption`, `risk_aversion`, `is_employed`, `employer_id` (10 полей)
- **FirmState** — per-firm массивы: `sector_id`, `productivity`, `capital`, `labor_count`, `cash`, `inventory`, `debt`, `wage_offer`, `price` (9 полей)
- **MarketState** — скалярные макроагрегаты: `avg_price`, `total_supply`, `total_demand`, `avg_wage`, `unemployment_rate`, `interest_rate`
- **GlobalState** — композит: `step`, `agents`, `firms`, `market`, `government_balance`, `tax_rate`, `gdp`. Фабрика `empty(n_agents, n_firms)`

`domain/schema.py` — Pydantic-схемы конфигурации (`SimulationConfig`, `RegionProfile`, `AgentType`).

### Mechanism Layer — экономические механизмы

Базовый класс `Mechanism(eqx.Module)` определяет patch-first интерфейс:

```python
class Mechanism(eqx.Module):
    fidelity: FidelityLevel  # fluid / relaxed / hard
    def emit_patches(self, state, key, *, target_mask=None) -> (PatchMap, key): ...
    def invariants(self, state) -> bool: ...
```

Встроенные механизмы:
- **IncomeTax** (`fiscal.py`) — подоходный налог на `reported_income`, зачисление в `government.balance`
- **TaxSubsidy** (`fiscal.py`) — субсидии с sector-targeting маской
- **LaborMarketMechanism** (`labor.py`) — вероятностное распределение занятости, `segment_sum` по фирмам
- **QueueMechanism** (`queue.py`) — очереди с тремя fidelity (fluid/relaxed/hard-discrete)
- **AdaptiveAgentMechanism** (`agents.py`) — нейросетевой агент (Equinox MLP), наблюдения → патчи действий

`registry.py` — центральный реестр механизмов с фабрикой `create_mechanism_from_spec()`, автоматической конвертацией IR-типов (`RateValue`, `MoneyValue` → `float`).

`specs.py` — валидация параметров механизмов с поддержкой типизированных значений и диапазонов.

### Merge & Patch Layer — применение изменений

Slot-based архитектура: механизмы пишут в именованные слоты (`agents.income`, `government.balance`) через патчи вместо прямой мутации состояния.

- **MergeEngine** (`merge_engine.py`) — CRDT-inspired движок слияния. Правила: `SUM` (сложение), `OVERRIDE` (перезапись), `PRIORITY` (по приоритету), `ERROR` (запрет конфликтов). Включает `JAXMergeEngine` для использования внутри `jax.jit`
- **patch_vm** (`patch_vm.py`) — мост между patch-записями и CAS: конвертирует dict-записи в `PatchOp`, сохраняет тензоры как артефакты
- **layout** (`layout.py`) — маппинг `slot_id → state_path` из `SlotRegistry`
- **conflict_checker** (`conflict_checker.py`) — compile-time статический анализ конфликтов записи в слоты. O(n*m), классификация по `MergeConflictKind`
- **constraints_engine** (`constraints_engine.py`) — post-merge валидация ограничений

### Compile Layer — компиляция политик

Модуль `compile/` (4 файла) преобразует Trinity IR в исполняемые графы:

1. **api.py** — точка входа `compile(store, request) → CompileResult`. Выбор бэкенда компилятора
2. **trinity_compiler.py** — полный pipeline: загрузка TrinityBundle → линковка с реестрами (`ir.linker`) → построение графа → conflict checking → cost estimation → создание артефактов (ProgramGraph, ExecPlan, SlotLayout, TreasuryPlan)
3. **_graph.py** — построение `ProgramGraph` DAG из IR-интервенций. Каждая интервенция → два узла (`make_mask` + `apply_mechanism`). Зависимости по слотам (A пишет в слот, который читает B → B зависит от A). Финальные узлы: `merge_state`, `check_constraints`. Топологическая сортировка через `graphlib.TopologicalSorter`

Вспомогательные модули корневого уровня:
- **cost_model** (`cost_model.py`) — эвристическая оценка стоимости выполнения (время, память, FLOPs) с самокалибровкой через EMA на телеметрии
- **treasury** (`treasury.py`) — детерминированное RNG: `TreasuryPlan` назначает SHA-256-based salt каждому узлу графа
- **trace** (`trace.py`) — минимальные `TraceEvent`/`TraceSlice` для отладки

### Execute Layer — исполнение программ

**executor.py** — основной исполнитель `execute_program_graph()`:
- загрузка ProgramGraph/ExecPlan из CAS
- обход узлов в топологическом порядке
- выполнение selectors (`SelectorExpr` → per-agent маски)
- применение механизмов → patch-записи → merge → constraints check
- сохранение `StateDelta`, `Metrics`, `ConstraintReport` как артефактов
- поддержка `apply_state_delta()`, `apply_patch_records()`, `load_state_snapshot()`

Высокоуровневый API в `execute/api.py` — `execute(store, request) → ExecuteResult`: загружает реестры, резолвит начальное состояние (из StateSnapshot или DataSnapshot), вызывает executor, создает `SimulationResult`.

### Runtime Layer — низкоуровневое исполнение

Модуль `runtime/` (3 файла) предоставляет JIT-совместимые примитивы:

- **runtime/__init__.py** — `step()`, `run_scan()` (через `jax.lax.scan`), `execute_program_batch()` (через `jax.vmap`). JIT-aware timing с OTel-интеграцией (`JITCompilationTracker`)
- **runtime/fingerprint.py** — `EnvironmentFingerprint`: захват Python/JAX/CUDA/XLA версий, `compatibility_score()` между окружениями, `configure_determinism()` по `DeterminismTier`
- **runtime/nan_guard.py** — `NaNGuard`: runtime-детектор NaN/Inf с pattern-based диагностикой причин. Профили: STRICT (каждый шаг), MVP (каждые 10), FAST (отключено)

### Uncertainty Layer — квантификация неопределенности

Модуль `uncertainty/` (9 файлов) обеспечивает propagation неопределенности через симуляции:

- **protocol.py** — `PropagationStrategy` Protocol, `PropagationResult`
- **dispatcher.py** — `PropagationDispatcher`: автовыбор метода (Delta vs Monte Carlo). Предпочитает Delta Method если входы Normal и симуляция дифференцируема (проверка через `jax.eval_shape(jax.jacfwd(...))`)
- **delta.py** — `DeltaMethodPropagator`: Якобиан через `jax.jacfwd`, propagation ковариации `J @ Cov @ J.T`
- **monte_carlo.py** — `MonteCarloPropagator`: семплирование из входных распределений (Normal/Uniform/Triangular), batch-evaluation, percentile-based CI
- **analytical.py** — `AnalyticalPropagator`: closed-form для линейных комбинаций Normal-распределений
- **covariance.py** — извлечение std из envelopes, построение ковариационных матриц, repair до PSD
- **aggregator.py** — `aggregate_envelopes()`: объединение нескольких CI методом "widest"
- **config.py** — `PropagationConfig`: confidence_level, mc_n_samples, delta настройки

### Analysis Layer — анализ результатов

Модуль `analysis/` (2 файла) — distributional impact analysis:

- **distributional.py** — `compute_gini()`, `compute_palma_ratio()`, `build_income_quintile_breakdown()`, `build_geography_breakdown()`, `build_winners_losers_table()`, `build_distributional_report()`
- Интеграция с типами `ir.distributional` (CohortDimension, DimensionBreakdown, DistributionalReport)

### Вспомогательные модули

- **profiles.py** — `FoundryCompileProfile` (FAST/MVP/STRICT), контроль NaN guard
- **loss.py** — `policy_loss_fn()` для градиентной оптимизации: максимизация дохода + penalty за бюджетное ограничение
- **utils.py** — `soft_step()`, `soft_clamp()`, `gradient_health_report()` с диагностикой vanishing/exploding gradients
- **agent_metrics.py** — метрики качества агентного поведения: `policy_entropy()`, `saturation_rate()`, `risk_action_correlation()`

## Крупные подсистемы (отдельная документация)

| Подсистема | Файлов | Описание | README |
|---|---|---|---|
| **methods/** | 52 | Декларативный фреймворк методов: протокол, реестр, бэкенды (JAX/NumPy/Solver), каталог (causal, econometrics), тестирование | [methods/README.md](methods/README.md) |
| **agent_sim/** | 38 | Симуляция гетерогенных агентов: RL (PPO), графовые структуры, демография, эволюционные алгоритмы | [agent_sim/README.md](agent_sim/README.md) |
| **plugins/** | 12 | Расширяемая plugin-архитектура для доменов, высокоуровневый PolisySimulator API | [plugins/README.md](plugins/README.md) |
| **calibration/** | 8 | Градиентная калибровка параметров на реальных данных с Laplace-uncertainty | [calibration/README.md](calibration/README.md) |

## Fidelity Levels — уровни точности

Три уровня задаются через `FidelityLevel` (`types.py`):

| Уровень | Описание | Градиенты | Скорость |
|---|---|---|---|
| `SURROGATE_FLUID` | Непрерывные потоки (уравнения) | Полные | Быстро |
| `RELAXED_DISCRETE` | Сглаженные события (Softmax/Sigmoid) | Приближенные | Средне |
| `HARD_DISCRETE` | Честная дискретная симуляция | Нет | Медленно |

## Зависимости

### Foundry зависит от:

| Модуль | Что используется |
|---|---|
| **core/artifacts** | CAS-хранилище, ArtifactID, манифесты, environment capture |
| **core/contracts/foundry** | ProgramGraph, ExecPlan, PatchOp, CompileRequest/Result, StateDelta |
| **core/canon** | Каноническая сериализация артефактов |
| **core/observability** | Метрики, трейсинг, DeterminismTier |
| **core/registry** | Загрузка registry bundles |
| **core/compiler** | CompileReport |
| **ir/kernel** | Slot/Merge/Mechanism/Constraint registries, типизированные значения |
| **ir/trinity** | TrinityBundle — формат политик |
| **ir/calibration** | CalibrationConfig, targets, trainable params |
| **ir/uncertainty** | UncertaintyEnvelope, PropagationMethod, DistributionFamily |
| **ir/causal**, **ir/hte** | CausalEffectReport, HTEResult |
| **ir/distributional** | CohortDimension, DistributionalReport |
| **common/logger** | Логирование (минимальная зависимость) |

### Потребители Foundry:

| Модуль | Что использует |
|---|---|
| **scientist/** | compile/execute API, method system (registry, dispatch, discovery), distributional analysis, calibration reports, uncertainty propagation |
| **packs/roads** | Базовые классы methods (FoundryMethod, MethodSignature) для доменных методов |

### Внешние библиотеки:

- **JAX/JAXlib** — основа вычислений, JIT, vmap, grad, lax.scan
- **Equinox** — OOP-обертка для JAX-модулей
- **Jaxtyping** — статическая проверка размерностей
- **Chex** — frozen dataclasses, проверки типов
- **Optax** — оптимизаторы (Adam, SGD)
- **Pydantic** — валидация конфигураций и контрактов
- **NumPy/SciPy** — NumPy-backend, статистика
- **statsmodels/linearmodels** — эконометрика (time series, panel)
- **econml** (optional) — каузальный inference (CATE, DML, meta-learners)

## Архитектурные инварианты

- **Patch-based execution** — все изменения состояния через именованные патчи, нет прямой мутации
- **Slot-based state** — доступ к состоянию только через предопределенные слоты с merge rules
- **Deterministic execution** — все RNG через Treasury (SHA-256 salts), EnvironmentFingerprint для воспроизводимости
- **Static shapes** — размеры массивов фиксированы при компиляции (JAX constraint)
- **Artifact-based** — все промежуточные данные через CAS для аудита и provenance
- **Immutable state** — все изменения через `replace()`, JAX не допускает мутацию

## Структура директории

```
foundry/
├── __init__.py              # Lazy imports: compile, execute
├── base.py                  # Mechanism, ComplexMechanism (абстрактные классы)
├── types.py                 # FidelityLevel enum
├── domain/                  # GlobalState, AgentState, FirmState, MarketState, схемы
├── fiscal.py, labor.py      # Встроенные экономические механизмы
├── agents.py, queue.py      # Адаптивные агенты, очереди
├── registry.py, specs.py    # Реестр и валидация механизмов
├── merge_engine.py          # CRDT merge (SUM/OVERRIDE/PRIORITY/ERROR)
├── patch_vm.py              # Patch → PatchOp + CAS storage
├── conflict_checker.py      # Compile-time conflict detection
├── constraints_engine.py    # Post-merge constraint validation
├── compile/                 # Trinity IR → ProgramGraph → ExecPlan
├── execute/                 # High-level execute API
├── executor.py              # Core executor (execute_program_graph)
├── runtime/                 # JIT primitives, fingerprint, NaN guard
├── cost_model.py            # Heuristic cost estimation
├── treasury.py              # Deterministic RNG plan
├── layout.py                # Slot → state_path mapping
├── trace.py                 # Execution trace events
├── loss.py                  # Policy loss function
├── utils.py                 # soft_step, soft_clamp, gradient_health
├── profiles.py              # FAST/MVP/STRICT compile profiles
├── agent_metrics.py         # Agent behavior quality metrics
├── methods/                 # → methods/README.md
├── agent_sim/               # → agent_sim/README.md
├── calibration/             # → calibration/README.md
├── plugins/                 # → plugins/README.md
├── uncertainty/             # Uncertainty propagation (Delta/MC/Analytical)
└── analysis/                # Distributional impact analysis
```

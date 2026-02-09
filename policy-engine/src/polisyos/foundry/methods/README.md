# Methods — декларативный фреймворк методов

Система для определения, композиции и исполнения типобезопасных переиспользуемых методов Foundry. Поддерживает JAX/NumPy/Solver бэкенды, семантическое версионирование, автоматическую валидацию и каталог готовых методов (каузальный inference, эконометрика).

**52 модуля** | **Protocol-driven** | **Multi-backend** | **v3.5.0**

## Архитектура

```
FoundryMethod protocol → MethodRegistry → MethodComposer (DAG) → Backend dispatch
      ↓                       ↓                  ↓                     ↓
  base.py              registry.py          composer.py         backends/dispatch.py
  @foundry_method      resolve/find         link → validate     JAX/NumPy/Solver
```

## Протокол FoundryMethod

Центральный ABI определен в `base.py`. Каждый метод реализует `@runtime_checkable Protocol`:

- **MethodSignature** — FQN (`namespace.name@version`), input/output `SlotSpec`, параметры, `fidelity`, `complexity`, `backend` (JAX/NUMPY/SOLVER), флаги JIT/vmap/grad совместимости, декларации `commutes_with`/`conflicts_with`/`requires`
- **MethodMetadata** — описание, теги, цитаты, уравнения, допущения
- **pure_step(state, params) → dict** — `@staticmethod`, чистая функция без side effects
- **@foundry_method** декоратор — валидация при создании класса, патчинг namespace/version, опциональный strict Law F enforcement

Хеширование через BLAKE2b (`stable_digest()`) для детерминированных cache keys (Law H).

## Core-компоненты

### Registry (`registry.py`)

Thread-safe singleton с O(1) FQN-lookup и вторичными индексами:
- `register()` / `unregister()` / lazy registration
- `resolve(fqn)` — поиск по полному имени
- `resolve_version(name, constraint, policy)` — разрешение версий
- `find_by_criteria(name, namespace, tag, input_slot, output_slot)` — AND-combined запросы
- `RegistrySnapshot` — lock-free копия для итерации

### Discovery (`discovery.py`)

Автообнаружение методов из трех источников:
- **EntryPointSource** — `polisyos.methods` entry point group (production)
- **FileSystemSource** — сканирование директорий (development)
- **bootstrap_registry()** — convenience-функция для инициализации

### Linker (`linker.py`)

Связывание output-слотов одного метода с input-слотами другого:
- Проверка совместимости единиц, форм, типов
- Автоматическое связывание: exact name match → type-based scoring
- `LinkerConfig` — strict vs permissive режимы

### Composer (`composer.py`)

DAG-builder для цепочек методов (через `graphlib.TopologicalSorter`, Law G — без NetworkX):
- Builder pattern: `add()` → `connect()` → `validate()` → `build()`
- `CompiledMethodChain` — frozen DAG + execution order + bindings
- Учет `commutes_with`, `conflicts_with`, `requires`

### Resolution (`resolution.py`)

SemVer 2.0 с caret-compatible bounds:
- `SemVer` dataclass с `@total_ordering` (pre-release, build metadata)
- `ResolutionPolicy`: EXACT, LATEST_COMPATIBLE, LATEST, PINNED
- `VersionConstraint` — правильная обработка 0.x

### Compiler (`compiler.py`)

JAX JIT-компилятор для методов:
- `CompilationCache` — thread-safe LRU на `OrderedDict`
- `MethodCompiler` — single-flight компиляция (avoid duplicate work)
- `CompiledChainExecutor` — последовательное исполнение скомпилированной цепочки
- Разделение static params (часть cache key) и dynamic params (traced через JAX)

### Specialization (`specialization.py`)

Детерминированные cache keys для JAX-компиляции:
- `ShapeSpec` (shape + dtype)
- `BackendSpec` (platform/devices/precision/JAX config)
- `Specialization` → SHA-256 `cache_key`

### Artifacts (`artifacts.py`)

Provenance-артефакты для CAS:
- `MethodArtifact` (identity + compilation context)
- `ChainArtifact` (composition + topology)
- `ExecutionEvidence` (timing, RNG state, device info)
- `store_method_artifact()`, `store_chain_artifact()` для CAS persistence

### Types (`types/`)

- **checker.py** — статическая проверка совместимости слотов: unit dimensions, conversion/FX, shape broadcasting, bounds overlap. Генерирует `AdapterPlan` (UnitAdapter/ShapeAdapter/TypeAdapter)
- **units.py** — предопределенные единицы: валюты (UAH/USD/EUR), ratios (FRACTION/PERCENT/BP), время (YEAR/QUARTER/MONTH), counts (PERSONS/HOUSEHOLDS), rates

### Exceptions (`exceptions.py`)

Иерархия: `FoundryMethodError` → `MethodDefinitionError`, `MethodNotFoundError`, `ResolutionError`, `SlotConnectionError` → `UnitMismatchError` / `ShapeMismatchError`, `CyclicDependencyError`, `CompilationError`, `LawViolationError`.

### Components Bridge (`components_bridge.py`)

Мост `core.components.ComponentRegistry` → `MethodRegistry`: регистрация Foundry-методов как core-компонентов с валидацией `HostAbi`.

## Backends — исполнение методов

`backends/` (8 файлов) реализуют `MethodRunner` Protocol:

| Backend | Runner | Описание |
|---|---|---|
| **JAX** | `JaxRunner` | JIT-компиляция через `MethodCompiler`, `block_until_ready()` |
| **NUMPY** | `NumpyRunner` | Прямое исполнение, injection `__rng__`/`__seed__` |
| **SOLVER** | `SolverRunner` | OR-tools/PuLP, извлечение `SolverStatus` (OPTIMAL/FEASIBLE/INFEASIBLE/...) |

- **dispatch.py** — `MethodDispatcher`: singleton, маршрутизация по `ComputeBackend`
- **chain_executor.py** — `execute_heterogeneous_chain()`: исполнение цепочек с разными бэкендами, автоматическая конвертация состояния между ними
- **adapters.py** — `to_numpy()` / `to_jax()` / `adapt_state()` для переходов между бэкендами
- **protocol.py** — `MethodResult` (output + timing + reproducibility), `SolverStatus`

## Catalog — готовые методы

### Causal Inference (`catalog/causal/`, 14 файлов)

Протоколы и типизированные входные данные (`protocols.py`):
- `PanelObservationalData` — outcome (n_units, n_periods), treatment, covariates
- `HTEObservationalData` — outcome, treatment, covariates, confounders (min 40 obs)
- `RDDObservationalData` — outcome, running_variable, cutoff

Estimators:

| Метод | Класс | Namespace | Описание |
|---|---|---|---|
| Synthetic Control | `SyntheticControlMethod` | causal.inference | Constrained donor weights, placebo inference, RMSPE |
| Difference-in-Differences | `DifferenceInDifferences` | causal.inference | Standard 2x2 + staggered (Callaway-Sant'Anna), parallel trends test |
| Regression Discontinuity | `RegressionDiscontinuity` | causal.inference | Local polynomial, IK bandwidth, McCrary manipulation test |
| Structural Time Series | `StructuralTimeSeries` | causal.inference | CausalImpact (Brodersen), state-space via statsmodels |
| Causal Forest | `CausalForestEstimator` | causal.hte | EconML CausalForestDML, CATE, subgroup effects |
| Double ML | `DoubleMachineLearning` | causal.hte | EconML LinearDML/SparseDML/KernelDML |
| Meta-Learners | `MetaLearnerEstimator` | causal.hte | S/T/X-Learner (EconML), configurable base models |
| Policy Learning | `OptimalPolicyLearner` | causal.targeting | PolicyTree, budget-constrained targeting rules |

Общие утилиты (`_common.py`): `bootstrap_ci()`, `compute_rmspe()`, `compute_cohen_d()`, `build_success_report()`.

EconML-зависимые методы (CATE, DML, Meta-Learners, Policy Learning) подключаются опционально через `_econml_adapter.py` и `_registry_boot.py`.

### Econometrics (`catalog/econometrics/`, 6 файлов)

Протоколы (`protocols.py`): `PanelData`, `TimeSeriesData`, `EconometricResult` с `to_uncertainty_envelope()`.

| Метод | Класс | Библиотека | Описание |
|---|---|---|---|
| Panel FE/RE | `PanelDataEstimator` | linearmodels | Fixed Effects (PanelOLS) / Random Effects |
| IV 2SLS/GMM | `InstrumentalVariablesEstimator` | linearmodels | Инструментальные переменные, first-stage F-stat |
| ARIMA/VAR | `TimeSeriesEstimator` | statsmodels | Временные ряды, AIC/BIC диагностика |

### Optimization (`catalog/optimization/`)

Placeholder-пакет для будущего каталога.

## Testing — инфраструктура тестирования

`testing/` (7 файлов) обеспечивает проверку FoundryMethod-реализаций:

### MethodTestSuite (`suite.py`)

Категории проверок:
- **PROTOCOL** — signature, metadata, pure_step, @staticmethod, frozen dataclass
- **SIGNATURE** — semver, namespace, unique slot names
- **LAW_F** — arrays-only в pure_step (нет не-array листьев в pytree)
- **JAX_JIT** — JIT-компиляция, корректность результатов
- **JAX_VMAP** — батчинг через vmap
- **JAX_GRAD** — дифференцируемость
- **NUMERICAL** — NaN/Inf отсутствие
- **DETERMINISM** — идентичные результаты при повторных запусках (eager + JIT)

`quick_check()` — минимальная pass/fail проверка.

### Golden Records (`golden.py`)

Regression-тестирование через content-addressed снимки (Law M):
- `GoldenRecord` — context + input_hash + output_hash + tolerances
- `GoldenStore` — persistent storage: `method/backend_Nd/precision/input_hash.golden.json`
- `hash_pytree()` — детерминированное хеширование pytree (SHA-256, опциональная квантизация для float tolerance)

### Backend-specific suites

- `NumpyMethodTestSuite` — валидация output (reject object-dtype arrays)
- `SolverMethodTestSuite` — проверка формата `(output, solver_info)` tuple
- `JaxMethodTestSuite` — расширение MethodTestSuite с `run_jax_checks()`

### Fixtures (`fixtures.py`)

Фабрики тестовых данных: `SimpleFiscalState`, `SimpleAgentState`, `SimpleScalarState`, `create_sample_state()`, `create_sample_params()`, `create_test_method_class()`.

## Архитектурные законы

| Law | Описание | Enforcement |
|---|---|---|
| **F** | arrays-only в pure_step | MethodTestSuite.check_arrays_only |
| **G** | Без NetworkX, только graphlib | composer.py |
| **H** | Детерминированные cache keys (BLAKE2b/SHA-256) | specialization.py, stable_digest() |
| **I** | Разделение static/dynamic параметров | compiler.py |
| **J** | Provenance tracking | artifacts.py |
| **K** | Explicit version resolution | resolution.py |
| **L** | Multi-fidelity support | FidelityLevel в signatures |
| **M** | Golden record regression testing | golden.py |

## Структура

```
methods/
├── __init__.py           # Public API v3.5.0 (graceful degradation)
├── base.py               # FoundryMethod protocol, MethodSignature, @foundry_method
├── registry.py           # Thread-safe MethodRegistry singleton
├── discovery.py          # Auto-discovery (entry points, filesystem)
├── linker.py             # Slot binding + compatibility checking
├── composer.py           # DAG composition via graphlib
├── compiler.py           # JAX JIT compilation + cache
├── specialization.py     # Deterministic cache keys
├── resolution.py         # SemVer 2.0 resolution
├── artifacts.py          # CAS provenance artifacts
├── exceptions.py         # Exception hierarchy
├── components_bridge.py  # core.components ↔ MethodRegistry bridge
├── types/
│   ├── checker.py        # Slot compatibility analysis
│   └── units.py          # Predefined units (currencies, ratios, time)
├── backends/
│   ├── protocol.py       # MethodRunner protocol, MethodResult
│   ├── dispatch.py       # Backend routing
│   ├── jax_runner.py     # JAX JIT backend
│   ├── numpy_runner.py   # NumPy backend
│   ├── solver_runner.py  # OR-tools/PuLP backend
│   ├── chain_executor.py # Heterogeneous chain execution
│   └── adapters.py       # JAX ↔ NumPy state conversion
├── catalog/
│   ├── causal/           # SCM, DiD, RDD, STS, CATE, DML, Meta-Learners, PolicyTree
│   ├── econometrics/     # Panel FE/RE, IV 2SLS/GMM, ARIMA/VAR
│   └── optimization/     # (placeholder)
└── testing/
    ├── suite.py          # MethodTestSuite (protocol, JAX, numerical, determinism)
    ├── golden.py         # Golden record regression testing
    ├── fixtures.py       # Test data factories
    ├── numpy_suite.py    # NumPy backend validation
    ├── jax_suite.py      # JAX-focused suite
    └── solver_suite.py   # Solver backend validation
```

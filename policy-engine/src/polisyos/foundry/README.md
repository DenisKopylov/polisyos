# Polisyos Foundry: Policy Execution Engine

**Foundry** - это высокопроизводительный execution engine для дифференцируемого исполнения экономических политик в системе Policy Engine. Модуль предоставляет компилятор политик, patch-based runtime, калибровку параметров и математическую основу для моделирования и оптимизации экономических механизмов с использованием современных дифференцируемых вычислений.

## Роль в архитектуре

Foundry является **policy execution backend** в архитектуре Policy Engine, отвечая за компиляцию, калибровку и исполнение политик:

```
NL → LLM → IR (AST) → Foundry Compiler → Foundry Calibration → Foundry Runtime → Artifacts
```

Foundry **не знает** про LLM и работает исключительно с:
- ✅ JAX для дифференцируемых вычислений и JIT-компиляции
- ✅ Экономическими механизмами (налоги, субсидии, рынок труда, очереди)
- ✅ Многоуровневыми симуляциями (multi-fidelity)
- ✅ Slot-based state management и patch operations
- ✅ Program graphs и execution plans
- ✅ Калибровкой параметров на реальных данных
- ✅ Constraints engine для валидации ограничений
- ❌ Никаких БД, LLM или сетевых вызовов

## Технологический стек

- **JAX/JAXlib**: Основа всех вычислений и JIT-компиляции
- **Equinox**: OOP-обертка для JAX-модулей
- **Jaxtyping**: Статическая проверка размерностей тензоров
- **Chex**: Дополнительные проверки типов и форм
- **Pydantic**: Валидация конфигураций и схем

## Архитектура

Foundry состоит из шести основных слоев:

### 1. Compiler Layer (Компилятор)
```
compiler.py          # Компиляция политик в ProgramGraph
layout.py            # Slot layout для state management
treasury.py          # Deterministic RNG management
```

### 2. Runtime Layer (Исполнение)
```
patch_vm.py          # Patch-based виртуальная машина и merge rules
runtime.py           # Чистые JAX функции для исполнения (step, run_scan, execute_program_batch)
executor.py          # Исполнение программ с constraints и state management
constraints_engine.py # Движок ограничений и валидации
trace.py             # Система трассировки исполнения
```

### 3. Domain Layer (Модель предметной области)
```
domain/
├── state.py         # GlobalState, AgentState, FirmState, MarketState
└── schema.py        # Pydantic схемы конфигурации
```

### 4. Mechanism Layer (Механизмы)
```
base.py             # Абстрактный класс Mechanism и ComplexMechanism
types.py            # FidelityLevel enum (уровни точности)
agents.py           # Адаптивные агенты с нейронными сетями (AdaptiveAgentMechanism)
fiscal.py           # Налоговые механизмы (IncomeTax, TaxSubsidy)
labor.py            # Механизм рынка труда (LaborMarketMechanism)
queue.py            # Механизм очередей с multi-fidelity (QueueMechanism)
specs.py            # Спецификации механизмов с валидацией
registry.py         # Регистрация и фабрика механизмов
```

### 5. Calibration Layer (Калибровка моделей)
```
calibration/
├── calibrator.py     # Основной класс Calibrator для оптимизации параметров
├── pure_executor.py  # Чистый JAX executor для калибровки (без side effects)
├── bijectors.py      # Биекции для ограничения параметров (sigmoid, softplus)
├── loss.py           # Функции потерь (MSE, Huber, weighted loss)
├── preflight.py      # Подготовка данных и конфигурации для калибровки
└── report.py         # Отчёты калибровки (метрики качества, неопределённости)
```

### 6. Utils Layer (Утилиты)
```
loss.py             # Функции потерь для оптимизации политик
utils.py            # Дифференцируемые утилиты (soft_step, soft_clamp, gradient_health)
```

## Калибровка моделей (Calibration)

### Обзор

Calibration Layer предоставляет инструменты для автоматической калибровки параметров экономических моделей на реальных данных. Модуль использует градиентную оптимизацию для подбора параметров механизмов, обеспечивая соответствие моделируемых показателей реальным данным.

### Основные компоненты

#### Calibrator (Калибратор)
```python
from polisyos.foundry.calibration.calibrator import Calibrator, CalibratorInputs
from polisyos.foundry.calibration.report import CalibrationReport

# Входные данные для калибровки
inputs = CalibratorInputs(
    config=calibration_config,        # Конфигурация калибровки
    program_graph=program_graph,      # Скомпилированная политика
    exec_plan=exec_plan,              # План исполнения
    base_state=initial_state,         # Начальное состояние экономики
    mechanism_registry=mechanism_registry,
    slot_registry=slot_registry,
    merge_registry=merge_registry,
    raw_targets=real_data_targets     # Реальные данные для сравнения
)

# Запуск калибровки
calibrator = Calibrator()
report = calibrator.calibrate(inputs)

print(f"Total loss: {report.total_loss}")
print(f"Calibrated params: {report.calibrated_params}")
```

#### Функции потерь
```python
from polisyos.foundry.calibration.loss import loss_components, compute_base_loss

# Вычисление потерь по нескольким целям
total_loss, per_target_loss, per_target_base = loss_components(
    predicted=predicted_values,     # Предсказанные значения
    targets=real_values,            # Конфигурация потерь (MSE/Huber)
    configs=target_configs,         # Масштабы для относительных ошибок
    scales=target_scales,           # Веса целей
    weights=target_weights          # Реальные значения
)
```

#### Биекции параметров
```python
from polisyos.foundry.calibration.bijectors import make_bijector, to_unconstrained, from_unconstrained

# Создание биекции для ограничения параметра [0, 1]
bijector = make_bijector(lower=0.0, upper=1.0)

# Преобразование в unconstrained пространство для оптимизации
unconstrained = to_unconstrained([param_value], [bijector])

# Обратное преобразование
constrained = from_unconstrained(unconstrained, [bijector])
```

### Отчёт калибровки

```python
from polisyos.foundry.calibration.report import CalibrationReport

report = CalibrationReport(
    calibrated_params={"tax_mechanism.rate": 0.23},  # Калиброванные параметры
    total_loss=0.034,                                # Общая потеря
    per_target_loss={"gdp": 0.012, "unemployment": 0.022},  # Потери по целям
    series_comparison={                             # Сравнение временных рядов
        "gdp": CalibrationSeriesComparison(
            time=[1, 2, 3, 4],
            real=[100, 102, 105, 108],
            model=[99, 101, 104, 107]
        )
    },
    fit_quality=CalibrationFitQuality(...),         # Метрики качества подгонки
    uncertainties=CalibrationUncertainty(...)       # Оценки неопределённости
)
```

### Процесс калибровки

1. **Подготовка** (Preflight): Валидация конфигурации, подготовка данных
2. **Компиляция**: Создание оптимизируемой функции с автоматическим дифференцированием
3. **Оптимизация**: Градиентный спуск с биекциями для ограниченных параметров
4. **Анализ**: Вычисление метрик качества и оценок неопределённости
5. **Отчёт**: Сохранение результатов в artifact store

### Поддерживаемые оптимизаторы

- **Adam**: Адаптивная оптимизация (рекомендуется)
- **L-BFGS**: Квазиньютоновский метод для точной оптимизации
- **SLSQP**: Sequential Least Squares Programming с ограничениями

## Компилятор политик

### CompileArtifacts

Результат компиляции политики включает несколько артефактов:

```python
from polisyos.foundry.compiler import compile_surface_policy, CompileArtifacts

artifacts = compile_surface_policy(
    store=store,
    policy=policy_ir,
    mechanism_registry=mechanism_registry,
    slot_registry=slot_registry,
    merge_registry=merge_registry
)

# Доступные артефакты
policy_ref = artifacts.policy_ref           # Ссылка на исходную политику
program_ref = artifacts.program_ref         # Скомпилированный ProgramGraph
exec_plan_ref = artifacts.exec_plan_ref     # План исполнения с топологической сортировкой
slot_layout_ref = artifacts.slot_layout_ref # Layout слотов состояния (опционально)
treasury_plan_ref = artifacts.treasury_plan_ref  # План детерминированного RNG (опционально)
```

### Program Graph

Foundry компилирует политики из IR в **ProgramGraph** - ориентированный граф выполнения:

```python
from polisyos.core.contracts.foundry import ProgramGraph, ProgramNode, ProgramEdge

# Загрузка ProgramGraph из artifact store
program_graph = store.get_json(artifacts.program_ref)

# Структура графа
for node in program_graph.nodes:
    print(f"Node {node.node_id}: {node.op}")  # Узел с операцией

for edge in program_graph.edges:
    print(f"{edge.source} -> {edge.target}")  # Зависимости
```

ProgramGraph состоит из:
- **Nodes**: Узлы операций (механизмы, merge, constraints, data sources)
- **Edges**: Зависимости между узлами с указанием портов
- **Entrypoints**: Точки входа для исполнения (обычно "root")

### Execution Plan

После компиляции создается **ExecutionPlan** с топологическим порядком исполнения:

```python
from polisyos.core.contracts.foundry import ExecPlan

exec_plan = store.get_json(artifacts.exec_plan_ref)
print(f"Execution order: {exec_plan.order}")  # ['node1', 'node2', 'merge1', ...]
```

## Executor (Исполнитель программ)

### Обзор

Executor предоставляет высокоуровневый API для исполнения скомпилированных ProgramGraph'ов с поддержкой constraints, state management и детального логирования.

### Основные функции

#### Исполнение с constraints
```python
from polisyos.foundry.executor import execute_with_constraints
from polisyos.foundry.constraints_engine import ConstraintResult

# Исполнение с проверкой ограничений
result = execute_with_constraints(
    program_graph=program_graph,
    initial_state=initial_state,
    exec_plan=exec_plan,
    store=store,
    constraint_registry=constraint_registry,
    slot_registry=slot_registry,
    mechanism_registry=mechanism_registry,
    merge_registry=merge_registry
)

# Результат содержит финальное состояние и информацию о violations
final_state = result.final_state
constraint_result = result.constraint_result

if constraint_result.violations:
    print(f"Found {len(constraint_result.violations)} constraint violations")
    for violation in constraint_result.violations:
        print(f"- {violation}")
```

#### Step-by-step исполнение
```python
from polisyos.foundry.executor import execute_single_step

# Исполнение одного узла графа
step_result = execute_single_step(
    node_id="tax_mechanism_1",
    program_graph=program_graph,
    current_state=current_state,
    store=store,
    mechanism_registry=mechanism_registry,
    slot_registry=slot_registry,
    merge_registry=merge_registry,
    treasury_plan=treasury_plan
)

# Результат шага
new_state = step_result.final_state
patches_applied = step_result.patches_applied
metrics = step_result.metrics
```

#### Batch исполнение
```python
from polisyos.foundry.executor import execute_batch

# Исполнение для нескольких сценариев
batch_result = execute_batch(
    program_graph=program_graph,
    initial_states=[state1, state2, state3],  # Разные начальные условия
    exec_plan=exec_plan,
    store=store,
    mechanism_registry=mechanism_registry,
    slot_registry=slot_registry,
    merge_registry=merge_registry
)

# Результаты для каждого сценария
for i, result in enumerate(batch_result.results):
    print(f"Scenario {i}: GDP = {result.final_state.gdp}")
```

### State Management

Executor управляет state transitions через **StateDelta** и **StateSnapshot**:

```python
from polisyos.core.contracts.foundry import StateDelta, StateSnapshot

# StateDelta - изменения состояния между шагами
delta = StateDelta(
    step_from=0,
    step_to=1,
    slot_deltas={
        "agents.income": tensor_ref_increase,
        "government.balance": tensor_ref_decrease
    }
)

# StateSnapshot - полное состояние на момент времени
snapshot = StateSnapshot(
    step=1,
    state_ref=state_artifact_ref,
    metadata={"simulation_id": "sim_001"}
)
```

### Metrics и логирование

```python
from polisyos.core.contracts.foundry import Metrics

# Метрики исполнения
execution_metrics = Metrics(
    execution_time=1.23,           # Время исполнения в секундах
    nodes_executed=15,             # Количество выполненных узлов
    patches_applied=42,            # Количество применённых патчей
    constraints_checked=8,         # Количество проверенных ограничений
    memory_peak=512.5              # Пиковое использование памяти (MB)
)
```

## Patch-based Execution

### Slot System

Вместо прямых изменений состояния Foundry использует **slot-based** архитектуру:

```python
# Механизмы записывают в слоты вместо прямого изменения state
slots_written = ["agents.income", "government.balance"]
slots_read = ["agents.income", "market.unemployment_rate"]
```

### Patch Operations

Механизмы генерируют **патчи** вместо прямых изменений:

```python
from polisyos.core.contracts.foundry import PatchOp

# Вместо: state.agents.income += tax_amount
# Механизм генерирует:
patches = [
    PatchOp(
        slot_id="agents.income",
        op="add",
        value_ref=tax_amount_tensor_ref,
        notes=["income_tax_mechanism"]
    )
]
```

### Merge Rules

При конфликтах патчей применяются **merge rules** из **patch_vm** модуля:

```python
from polisyos.foundry.patch_vm import merge_patch_records
from polisyos.ir.kernel import MergeRuleKind

# Поддерживаемые виды merge rules
merge_kinds = [
    MergeRuleKind.SUM,        # Складывать изменения (для балансов)
    MergeRuleKind.OVERRIDE,   # Перезаписывать по приоритету
    MergeRuleKind.PRIORITY,   # Выбирать по явному приоритету
    MergeRuleKind.ERROR       # Запрещать конфликты
]

# Применение merge rules к патчам
merged_patches = merge_patch_records(
    store=artifact_store,
    patch_records=patch_records_from_mechanisms,
    slot_registry=slot_registry,
    merge_registry=merge_registry
)
```

### Artifact-based патчи

Patch VM сохраняет значения патчей как артефакты:

```python
from polisyos.foundry.patch_vm import _put_tensor, _load_tensor

# Сохранение тензора патча в artifact store
tensor_ref = _put_tensor(store, jnp.array([100.0, 200.0, 300.0]))

# Загрузка тензора из artifact store
tensor_value = _load_tensor(store, tensor_ref)
```

## Runtime Execution

### Execution Flow

Исполнение политики проходит через несколько фаз:

1. **Load Program**: Загрузка ProgramGraph из artifact store
2. **Initialize State**: Инициализация начального состояния экономики
3. **Execute Nodes**: Исполнение узлов в топологическом порядке
4. **Merge Patches**: Применение патчей с merge rules
5. **Check Constraints**: Валидация ограничений

### Runtime API

```python
from polisyos.foundry.runtime import step, run_scan, execute_program_batch

# Один шаг симуляции (чистая JAX функция)
def step(state, controls, root_key, t: int, static_bundle=None):
    """Placeholder pure JAX step; returns state unchanged and empty trace."""
    return state, {"t": t, "controls": controls}

# Исполнение последовательности контролей через lax.scan
traces = run_scan(initial_state, controls_seq, root_key, static_bundle=static_bundle)

# Batch исполнение для нескольких начальных состояний
batch_results = execute_program_batch(
    initial_states=batch_states,      # [batch_size, ...] состояния
    controls_seq=controls_seq,        # [batch_size, time_steps, ...] контролы
    root_key=root_key,                # Общий ключ для детерминизма
    static_bundle=static_bundle       # Скомпилированные компоненты
)
```

### Treasury System

Для детерминированного исполнения используется **Treasury** - система управления RNG:

```python
from polisyos.foundry.treasury import build_treasury_plan

# Каждый узел получает deterministic salt
treasury = build_treasury_plan(program_graph, root_seed=42)
node_rng = jax.random.key(treasury.node_salts[node_id])
```

## Основные понятия

### Fidelity Levels (Уровни точности)

Foundry поддерживает три уровня точности симуляции для баланса между скоростью оптимизации и реалистичностью:

```python
from polisyos.foundry.types import FidelityLevel

class FidelityLevel(str, Enum):
    SURROGATE_FLUID = "fluid"      # Непрерывные потоки (уравнения)
    RELAXED_DISCRETE = "relaxed"   # Сглаженные события (Softmax/Sigmoid)
    HARD_DISCRETE = "hard"         # Честная дискретная симуляция
```

### Mechanism (Механизм)

Абстрактный базовый класс для всех экономических механизмов политики. Современные механизмы работают через **patch system**:

```python
from polisyos.foundry.base import Mechanism
from polisyos.core.contracts.foundry import UpdateOp

class Mechanism(eqx.Module):
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID
    debug_mode: bool = False

    @abstractmethod
    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        """Инициализация состояния механизма"""

    @abstractmethod
    def step(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        """Один шаг механизма (legacy direct state changes)"""

    def emit_patches(
        self,
        state: GlobalState,
        key: jax.Array,
        *,
        target_mask=None,
    ) -> tuple[dict[str, list[UpdateOp]] | None, jax.Array]:
        """
        Patch-first execution path. Генерирует патчи вместо прямых изменений.
        """
        return None, key

    def invariants(self, state: GlobalState) -> bool:
        """Проверка физической корректности"""
        return True
```

### GlobalState (Глобальное состояние)

Экономическая модель с агентами, фирмами и рынком:

```python
@chex.dataclass(frozen=True)
class GlobalState:
    step: Int[Array, ""]                     # Текущий шаг симуляции
    agents: AgentState                       # Состояние агентов
    firms: FirmState                         # Состояние фирм
    market: MarketState                      # Состояние рынка
    government_balance: Float[Array, ""]     # Баланс правительства
    gdp: Float[Array, ""]                    # ВВП
```

#### AgentState (Агенты)
```python
@chex.dataclass(frozen=True)
class AgentState:
    # Демография и Навыки
    age: Int[Array, "n_agents"]               # Возраст
    skill_level: Float[Array, "n_agents"]     # Влияет на зарплату

    # Финансы
    income: Float[Array, "n_agents"]          # Фактический доход
    reported_income: Float[Array, "n_agents"] # Декларируемый доход (для налогов)
    savings: Float[Array, "n_agents"]         # Сбережения
    consumption: Float[Array, "n_agents"]     # Сколько потратил
    risk_aversion: Float[Array, "n_agents"]   # Отношение к риску (0-1)

    # Работа
    is_employed: Bool[Array, "n_agents"]      # Статус занятости
    employer_id: Int[Array, "n_agents"]       # ID фирмы (0..M-1) или -1
```

#### FirmState (Фирмы)
```python
@chex.dataclass(frozen=True)
class FirmState:
    # Статика
    sector_id: Int[Array, "n_firms"]          # 0=IT, 1=Agro...

    # Производственные факторы
    productivity: Float[Array, "n_firms"]     # Технологичность (A)
    capital: Float[Array, "n_firms"]          # Станки/Софт (K)
    labor_count: Float[Array, "n_firms"]      # Текущий штат (L)

    # Финансы
    cash: Float[Array, "n_firms"]             # Деньги на зарплаты
    inventory: Float[Array, "n_firms"]        # Товары на складе
    debt: Float[Array, "n_firms"]             # Долги

    # Рынок
    wage_offer: Float[Array, "n_firms"]       # Зарплатное предложение
    price: Float[Array, "n_firms"]            # Цена товара фирмы
```

#### MarketState (Рынок)
```python
@chex.dataclass(frozen=True)
class MarketState:
    # Агрегаты
    avg_price: Float[Array, ""]               # CPI (Индекс цен)
    total_supply: Float[Array, ""]            # Всего товаров
    total_demand: Float[Array, ""]            # Всего денег у покупателей

    avg_wage: Float[Array, ""]
    unemployment_rate: Float[Array, ""]
    interest_rate: Float[Array, ""]           # Ставка ЦБ
```

## Доступные механизмы

### Налоговые механизмы (fiscal.py)

Налоговые механизмы работают с **reported_income** (декларируемым доходом) вместо фактического дохода.

#### IncomeTax (Подоходный налог)
```python
from polisyos.foundry.fiscal import IncomeTax

tax = IncomeTax(rate=0.2, n_agents=1000)  # 20% налог
patches, key = tax.emit_patches(state, key)
# Налог рассчитывается на reported_income: tax_amount = reported_income * rate
```

#### TaxSubsidy (Налоговые субсидии)
```python
from polisyos.foundry.fiscal import TaxSubsidy

subsidy = TaxSubsidy(rate=0.1, n_agents=1000)  # 10% субсидия
patches, key = subsidy.emit_patches(state, key)
```

### LaborMarketMechanism (Механизм рынка труда)

Механизм моделирования рынка труда с вероятностным распределением занятости:

```python
from polisyos.foundry.labor import LaborMarketMechanism

labor_market = LaborMarketMechanism(
    employment_threshold=0.5,  # Порог занятости (0-1)
    fidelity=FidelityLevel.SURROGATE_FLUID
)

patches, key = labor_market.emit_patches(state, key)
```

### AdaptiveAgentMechanism (Адаптивные агенты)

Механизм моделирования агентов с обучением на основе нейронных сетей. Агенты наблюдают состояние экономики и принимают решения через обученные политики.

```python
from polisyos.foundry.agents import AdaptiveAgentMechanism

# Создание механизма с MLP политикой
agent_mech = AdaptiveAgentMechanism(
    observation_space=["agents.income", "agents.savings", "market.unemployment_rate"],
    action_space={
        "type": "continuous",
        "affects": ["agents.reported_income"],
        "dim": 1,
        "range": [0.0, 1.0]  # Масштаб для reported_income = income * scale
    },
    policy_model={"hidden_layers": [64, 32], "activation": "relu"},
    learning_rate=0.01,
    stochastic=True
)

patches, key = agent_mech.emit_patches(state, key)
```

#### Особенности:
- **Нейронные сети**: Политики реализованы через MLP с настраиваемой архитектурой
- **Гибкие наблюдения**: Можно наблюдать любые поля состояния экономики
- **Разные типы действий**: Непрерывные (continuous) или дискретные (discrete) действия
- **Масштабирование**: Поддержка диапазонов и нормализации для действий
- **Стохастичность**: Опциональная случайность в принятии решений

### QueueMechanism (Механизм очередей)

Многоуровневый механизм очередей с поддержкой разных fidelity:

```python
from polisyos.foundry.queue import QueueMechanism

queue = QueueMechanism(
    service_rate=0.8,      # Скорость обслуживания
    arrival_rate=1.0,      # Скорость поступления
    fidelity=FidelityLevel.RELAXED_DISCRETE
)

patches, key = queue.emit_patches(state, key)
```

## Движок симуляции

### Patch-based Execution (Современный подход)

Foundry использует patch-based модель исполнения, где механизмы генерируют патчи изменений вместо прямых модификаций состояния. Это обеспечивает:

- **Идемпотентность**: одни и те же патчи всегда дают одинаковый результат
- **Детерминизм**: результаты воспроизводимы при одинаковых входах
- **Аудит**: все изменения логируются и могут быть проверены
- **Составляемость**: патчи можно комбинировать и трансформировать

#### Patch Generation (Генерация патчей)

Механизмы генерируют патчи через метод `emit_patches()`:

```python
from polisyos.foundry.base import Mechanism
from polisyos.core.contracts.foundry import UpdateOp

class ModernTax(Mechanism):
    def emit_patches(self, state, key, *, target_mask=None):
        # Вычисляем изменения
        tax_amounts = state.agents.income * self.tax_rate

        # Генерируем патчи вместо прямых изменений
        patches = {
            "agents.income": [
                UpdateOp(delta=-tax_amounts, mask=target_mask)
            ],
            "government.balance": [
                UpdateOp(delta=jnp.sum(tax_amounts), mask=None)
            ]
        }
        return patches, key
```

#### Merge Rules (Правила слияния)

При конфликтах патчей применяются правила слияния из slot registry:

```python
from polisyos.ir.kernel import MergeRuleKind

# Поддерживаемые виды merge rules
merge_kinds = [
    MergeRuleKind.SUM,        # Складывать изменения (для балансов)
    MergeRuleKind.OVERRIDE,   # Перезаписывать по приоритету
    MergeRuleKind.PRIORITY,   # Выбирать по явному приоритету
    MergeRuleKind.ERROR       # Запрещать конфликты
]
```

#### Constraints Engine (Движок ограничений)

Валидация ограничений после применения патчей:

```python
from polisyos.foundry.constraints_engine import check_constraints

result = check_constraints(
    constraint_registry=constraint_registry,
    slot_registry=slot_registry,
    merged_ops=patch_ops,
    state_before=state
)

if result.violations:
    print(f"Найдено нарушений: {len(result.violations)}")
    for violation in result.violations:
        print(f"- {violation}")
```

## Функции потерь и оптимизация

### Policy Loss Function

Функция потерь для градиентной оптимизации политик:

```python
import jax.numpy as jnp
from polisyos.foundry.domain.state import GlobalState

def policy_loss_fn(final_state: GlobalState, min_balance: float = -1000.0) -> float:
    # Максимизация дохода (минимизация отрицательного дохода)
    avg_income = jnp.mean(final_state.agents.income)
    objective_loss = -avg_income / 1000.0

    # Штраф за нарушение бюджетных ограничений
    balance = final_state.government_balance
    violation = min_balance - balance
    penalty = jnp.maximum(0.0, violation) ** 2

    return objective_loss + 1000.0 * penalty
```

## Регистр механизмов

### Создание механизма через Intervention

```python
from polisyos.ir.contract import Intervention
from polisyos.foundry.registry import create_mechanism

# IR контракт из scientist
intervention = Intervention(
    mechanism_type="income_tax",
    parameters={"rate": 0.15}
)

# Создание механизма
mechanism = create_mechanism(intervention, n_agents=1000, n_firms=100)
```

### Доступные механизмы

```python
from polisyos.foundry.registry import MECHANISM_REGISTRY

# Доступные механизмы в registry
mechanisms = {
    "adaptive_agent": "AdaptiveAgentMechanism", # Адаптивные агенты с ML
    "tax_subsidy": "TaxSubsidy",           # Налоговые субсидии
    "income_tax": "IncomeTax",             # Подоходный налог
    "labor_market": "LaborMarketMechanism", # Рынок труда
    "queue": "QueueMechanism"              # Механизм очередей
}
```

## Спецификации механизмов

### Валидация параметров

```python
from polisyos.foundry.specs import validate_mechanism_params

# Проверка параметров перед созданием
try:
    validate_mechanism_params("income_tax", {"rate": 0.15})
    print("Параметры валидны")
except ValueError as e:
    print(f"Ошибка валидации: {e}")
```

### Структура спецификации

```python
MECHANISM_SPECS = {
    "income_tax": MechanismSpec(
        name="income_tax",
        required_params={"rate"},
        param_ranges={"rate": (0.0, 1.0)},
        param_units={"rate": "ratio"},
        description="Подоходный налог"
    )
}
```

## Утилиты

### Дифференцируемые функции

```python
from polisyos.foundry.utils import soft_step, soft_clamp

# Дифференцируемая ступенька
smooth_threshold = soft_step(x, k=10.0)

# Дифференцируемое ограничение
clamped_value = soft_clamp(x, 0.0, 1.0)
```

### Анализ градиентов

```python
from polisyos.foundry.utils import gradient_health

# Проверка здоровья градиентов
health_report = gradient_health(gradients)
if health_report.vanishing:
    print("Градиенты затухают - проблема с learning!")
```

### Trace System (Система трассировки)

Отслеживание исполнения программ для отладки и анализа:

```python
from polisyos.foundry.trace import TraceEvent, TraceSlice

# Создание события трассировки
event = TraceEvent(
    phase="execution",
    event="node_executed",
    payload={
        "node_id": "tax_mechanism_1",
        "execution_time": 0.023,
        "patches_generated": 42
    }
)

# Срез трассировки для анализа
trace_slice = TraceSlice(events=[event])
```

## Примеры использования

### Компиляция и исполнение политики

```python
from polisyos.foundry.compiler import compile_surface_policy
from polisyos.foundry.runtime import execute_program
from polisyos.core.artifacts.store import FileSystemCAS

# Компиляция политики
store = FileSystemCAS("/tmp/artifacts")
artifacts = compile_surface_policy(
    store=store,
    policy=policy_surface_ir,
    mechanism_registry=mechanism_registry,
    slot_registry=slot_registry,
    merge_registry=merge_registry
)

# Исполнение программы
initial_state = GlobalState.empty(n_agents=1000, n_firms=100)
result = execute_program(
    program_graph=artifacts.program_ref,
    exec_plan=artifacts.exec_plan_ref,
    initial_state=initial_state,
    store=store,
    treasury_plan=artifacts.treasury_plan_ref
)

print(f"Финальный GDP: {result.final_state.gdp:.2f}")
```

### Создание механизма с патчами

```python
from polisyos.foundry.base import Mechanism
from polisyos.core.contracts.foundry import UpdateOp
import jax.numpy as jnp

class ModernIncomeTax(Mechanism):
    tax_rate: float

    def emit_patches(self, state, key, *, target_mask=None):
        # Вычисляем налог
        incomes = state.agents.income
        tax_amounts = incomes * self.tax_rate

        # Генерируем патчи вместо прямых изменений
        patches = {
            "agents.income": [
                UpdateOp(delta=-tax_amounts, mask=target_mask)
            ],
            "government.balance": [
                UpdateOp(delta=jnp.sum(tax_amounts), mask=None)
            ]
        }
        return patches, key
```

### Создание адаптивного агента

```python
from polisyos.foundry.agents import AdaptiveAgentMechanism

# Агент, который оптимизирует декларируемый доход (уклонение от налогов)
tax_evasion_agent = AdaptiveAgentMechanism(
    observation_space=[
        "agents.income",           # Фактический доход
        "global.tax_rate",         # Ставка налога
        "market.unemployment_rate" # Риск безработицы
    ],
    action_space={
        "type": "continuous",
        "affects": ["agents.reported_income"],
        "dim": 1,
        "range": [0.5, 1.0]  # Декларировать 50-100% дохода
    },
    utility="risk_adjusted_income",  # Максимизировать доход с учётом риска
    learning_rate=0.01,
    stochastic=False
)

# Агент принимает решение на основе наблюдений
patches, key = tax_evasion_agent.emit_patches(state, key)
```

### Legacy симуляция (устаревшее)

```python
from polisyos.foundry.basic_simulation import simple_policy_simulation, analyze_simulation_results

# Запуск простой симуляции
time_steps, populations = simple_policy_simulation(
    population_size=1000,
    time_steps=50,
    policy_effect=0.05
)

# Анализ результатов
analysis = analyze_simulation_results(time_steps, populations)
print(f"Средний рост: {analysis['total_growth_percent']:.1f}%")
```

## Разработка новых механизмов

### 1. Создание класса механизма

```python
from polisyos.foundry.base import Mechanism
from polisyos.foundry.types import FidelityLevel

class UnemploymentBenefit(Mechanism):
    benefit_amount: jnp.ndarray
    eligibility_threshold: jnp.ndarray

    def __init__(self, benefit_amount: float, eligibility_threshold: float, **kwargs):
        self.benefit_amount = jnp.array(benefit_amount)
        self.eligibility_threshold = jnp.array(eligibility_threshold)
        self.fidelity = FidelityLevel.SURROGATE_FLUID

    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        return state, key

    def step(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        # Логика пособия по безработице
        unemployed = ~state.agents.is_employed
        eligible = state.agents.income < self.eligibility_threshold

        benefit_mask = unemployed & eligible
        additional_income = benefit_mask * self.benefit_amount

        new_income = state.agents.income + additional_income
        new_balance = state.government_balance - jnp.sum(additional_income)

        new_agents = state.agents.replace(income=new_income)

        return state.replace(agents=new_agents, government_balance=new_balance), key
```

### 2. Добавление спецификации

```python
from polisyos.foundry.specs import MECHANISM_SPECS, MechanismSpec

MECHANISM_SPECS["unemployment_benefit"] = MechanismSpec(
    name="unemployment_benefit",
    required_params={"benefit_amount", "eligibility_threshold"},
    param_ranges={
        "benefit_amount": (0.0, 1000.0),
        "eligibility_threshold": (0.0, 10000.0)
    },
    param_units={
        "benefit_amount": "currency",
        "eligibility_threshold": "currency"
    },
    description="Пособие по безработице"
)
```

### 3. Регистрация в registry

```python
from polisyos.foundry.registry import MECHANISM_REGISTRY
from polisyos.foundry.unemployment import UnemploymentBenefit

MECHANISM_REGISTRY["unemployment_benefit"] = UnemploymentBenefit
```

## Тестирование

Foundry включает comprehensive тесты:

### Compiler Tests
- **Program Graph compilation**: Корректность построения графа
- **Execution Plan**: Топологическая сортировка и валидность
- **Merge Rules**: Разрешение конфликтов патчей

### Runtime Tests
- **Patch execution**: Корректность применения патчей
- **Slot management**: Чтение/запись в правильные слоты
- **Treasury determinism**: Воспроизводимость результатов

### Legacy Tests
- **JIT-стабильности**: Градиенты не ломаются при компиляции
- **Экономических инвариантов**: Сохранение законов экономики
- **Multi-fidelity**: Эквивалентность разных уровней точности

```bash
# Запуск всех тестов foundry
pytest tests/foundry/ -v

# Тесты компилятора
pytest tests/foundry/test_constraints_executor.py -v

# Legacy тесты симуляции
pytest tests/foundry/test_jit_stability.py -v
```

## Производительность

### JIT-компиляция

Все вычисления в Foundry JIT-компилируются для максимальной производительности:

```python
# Автоматическая JIT-компиляция
kernel = SimulationKernel()  # Компилируется при создании

# Ручная JIT-компиляция функций
@jax.jit
def simulate_policy(policy_params, initial_state):
    # Логика симуляции
    pass
```

### Профилирование

```python
import jax.profiler

# Профилирование выполнения
with jax.profiler.trace("/tmp/jax-trace"):
    result = jax.jit(my_function)(args)
```

## Ограничения и допущения

### Архитектурные ограничения

- **Patch-based execution**: Все изменения через патчи, нет прямого доступа к состоянию
- **Slot-based state**: Состояние доступно только через предопределенные слоты
- **Deterministic execution**: Все RNG через Treasury для воспроизводимости
- **Static compilation**: ProgramGraph фиксирован после компиляции

### Экономическая модель

- **Patch-based изменения**: все модификации состояния через патчи
- **Slot-based state**: доступ к состоянию только через предопределенные слоты
- **Многоуровневая точность**: три уровня fidelity (fluid/relaxed/hard)
- **Детерминированное исполнение**: RNG через Treasury для воспроизводимости

### Вычислительные ограничения

- **JAX immutable state**: Все изменения через патчи или `replace()`
- **Static shapes**: Размеры массивов фиксированы при компиляции
- **Limited Python**: Только JAX-совместимые операции в runtime
- **Artifact-based**: Все данные через artifact store

## Связанные модули

### Зависимости Foundry

- **`ir/`**: Policy Surface IR, контракты механизмов, slot/merge registries, calibration configs
- **`core/artifacts`**: Artifact storage и CAS для компиляции, исполнения и калибровки
- **`core/contracts`**: Foundry-specific типы (PatchOp, ProgramGraph, ExecPlan, etc.)
- **`core/canon`**: Каноническая сериализация для артефактов
- **`ir/calibration`**: Конфигурации и типы для калибровки моделей

### Потребители Foundry

- **`scientist/`**: Использует компилятор для создания execution plans и калибратор для оптимизации параметров
- **`fabric/`**: Предоставляет данные для инициализации состояния экономики
- **`runtime/`**: Хранит результаты исполнения и обеспечивает аудит
- **`ir/`**: Определяет механизм спецификации и calibration targets

### Интеграция в Pipeline

```
scientist/ → ir/ → foundry.compiler → foundry.calibration → foundry.runtime → artifacts
                     ↓                           ↓
               fabric/ (data)             foundry.executor (constraints)
                     ↓                           ↓
               core/artifacts (CAS)        core/contracts (types)
                     ↓                           ↓
               core/canon (serialization)  ir/kernel (registries)
```

## Соглашения по коду

- **Строгая типизация**: все функции с type hints
- **Документация**: docstrings для всех публичных API
- **Именование**: snake_case для функций, PascalCase для классов
- **Импорты**: абсолютные импорты внутри polisyos
- **Логирование**: через loguru, без print statements

## Миграция и Roadmap

### Современная архитектура

Foundry полностью переведен на patch-based архитектуру:

- **emit_patches()**: Все механизмы используют патчи вместо прямых изменений
- **ProgramGraph execution**: Компиляция политик в графы выполнения
- **Constraints validation**: Валидация ограничений после каждого шага
- **Trace logging**: Полная трассировка исполнения для отладки

### Разработка новых механизмов

1. **Наследоваться от Mechanism**: Использовать абстрактный базовый класс
2. **Реализовать emit_patches()**: Генерировать патчи вместо прямых изменений
3. **Добавить в registry**: Зарегистрировать механизм для использования
4. **Добавить спецификации**: Определить параметры и ограничения

### Будущие улучшения

- **Distributed execution**: Масштабирование на кластеры
- **Advanced merge rules**: Более сложные стратегии разрешения конфликтов
- **Dynamic shapes**: Поддержка переменных размеров массивов
- **GPU acceleration**: Оптимизация для GPU-вычислений

---

Foundry представляет собой современный высокопроизводительный execution engine для дифференцируемого исполнения экономических политик, использующий patch-based архитектуру, ProgramGraph компиляцию и constraints validation для обеспечения надежности и эффективности моделирования.

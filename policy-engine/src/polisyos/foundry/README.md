# Polisyos Foundry: Policy Execution Engine

**Foundry** - это высокопроизводительный execution engine для дифференцируемого исполнения экономических политик в системе Policy Engine. Модуль предоставляет компилятор политик, patch-based runtime и математическую основу для моделирования и оптимизации экономических механизмов с использованием современных дифференцируемых вычислений.

## Роль в архитектуре

Foundry является **policy execution backend** в архитектуре Policy Engine, отвечая за компиляцию и исполнение политик:

```
NL → LLM → IR (AST) → Foundry Compiler → Runtime Execution → Artifacts
```

Foundry **не знает** про LLM и работает исключительно с:
- ✅ JAX для дифференцируемых вычислений и JIT-компиляции
- ✅ Экономическими механизмами (налоги, субсидии, очереди)
- ✅ Многоуровневыми симуляциями (multi-fidelity)
- ✅ Slot-based state management и patch operations
- ✅ Program graphs и execution plans
- ❌ Никаких БД, LLM или сетевых вызовов

## Технологический стек

- **JAX/JAXlib**: Основа всех вычислений и JIT-компиляции
- **Equinox**: OOP-обертка для JAX-модулей
- **Jaxtyping**: Статическая проверка размерностей тензоров
- **Chex**: Дополнительные проверки типов и форм
- **Pydantic**: Валидация конфигураций и схем

## Архитектура

Foundry состоит из четырех основных слоев:

### 1. Compiler Layer (Компилятор)
```
compiler.py          # Компиляция политик в ProgramGraph
layout.py            # Slot layout для state management
treasury.py          # Deterministic RNG management
```

### 2. Runtime Layer (Исполнение)
```
patch_vm.py          # Patch-based виртуальная машина
runtime.py           # Исполнение ProgramGraph'ов
executor.py          # JIT-исполнение механизмов
```

### 3. Domain Layer (Модель предметной области)
```
domain/
├── state.py         # GlobalState, AgentState, FirmState, MarketState
└── schema.py        # Pydantic схемы конфигурации
```

### 4. Mechanism Layer (Механизмы)
```
base.py             # Абстрактный класс Mechanism
types.py            # FidelityLevel enum (уровни точности)
fiscal.py           # Налоговые механизмы (IncomeTax, TaxSubsidy)
queue.py            # Механизм очередей с multi-fidelity
specs.py            # Спецификации механизмов с валидацией
registry.py         # Регистрация и фабрика механизмов
```

### 5. Legacy Layer (Устаревшее)
```
_legacy/engine/     # Legacy симуляционный движок (SimulationKernel, logic)
_legacy/basic_simulation.py # Демо и примеры (deprecated)
```
> Legacy находится в `_legacy/` и запрещён к использованию в новом коде; используйте patch VM / ProgramGraph runtime.

## Компилятор политик

### Program Graph

Foundry компилирует политики из IR в **ProgramGraph** - ориентированный граф выполнения:

```python
from polisyos.foundry.compiler import compile_surface_policy
from polisyos.ir.surface import PolicySurfaceIR

# Компилируем политику
artifacts = compile_surface_policy(
    store=store,
    policy=policy_ir,
    mechanism_registry=mechanism_registry,
    slot_registry=slot_registry,
    merge_registry=merge_registry
)

program_graph = artifacts.program_ref  # Скомпилированный граф
```

ProgramGraph состоит из:
- **Nodes**: Узлы операций (механизмы, merge, constraints)
- **Edges**: Зависимости между узлами
- **Entrypoints**: Точки входа для исполнения

### Execution Plan

После компиляции создается **ExecutionPlan** с топологическим порядком исполнения:

```python
exec_plan = artifacts.exec_plan_ref
# exec_plan.order содержит отсортированный список node_id для исполнения
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

При конфликтах патчей применяются **merge rules**:

- **SUM**: Складывать изменения (для балансов)
- **OVERRIDE**: Перезаписывать по приоритету
- **PRIORITY**: Выбирать по явному приоритету
- **ERROR**: Запрещать конфликты

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
from polisyos.foundry.runtime import execute_program
from polisyos.foundry.domain.state import GlobalState

# Исполнение программы
result = execute_program(
    program_graph=program_graph,
    initial_state=initial_state,
    exec_plan=exec_plan,
    store=artifact_store,
    treasury_plan=treasury_plan
)

final_state = result.final_state
execution_trace = result.trace
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
    step: Int[Array, ""]                    # Текущий шаг симуляции
    agents: AgentState                      # Состояние агентов
    firms: FirmState                        # Состояние фирм
    market: MarketState                     # Состояние рынка
    government_balance: Float[Array, ""]    # Баланс правительства
    gdp: Float[Array, ""]                   # ВВП
```

#### AgentState (Агенты)
```python
@chex.dataclass(frozen=True)
class AgentState:
    age: Int[Array, "n_agents"]              # Возраст
    skill_level: Float[Array, "n_agents"]    # Уровень навыков
    income: Float[Array, "n_agents"]         # Доход
    savings: Float[Array, "n_agents"]        # Сбережения
    consumption: Float[Array, "n_agents"]    # Потребление
    is_employed: Bool[Array, "n_agents"]     # Статус занятости
    employer_id: Int[Array, "n_agents"]      # ID работодателя
```

#### FirmState (Фирмы)
```python
@chex.dataclass(frozen=True)
class FirmState:
    sector_id: Int[Array, "n_firms"]         # Сектор экономики
    productivity: Float[Array, "n_firms"]    # Производительность
    capital: Float[Array, "n_firms"]         # Капитал
    labor_count: Float[Array, "n_firms"]     # Численность персонала
    cash: Float[Array, "n_firms"]            # Денежные средства
    inventory: Float[Array, "n_firms"]       # Запасы
    debt: Float[Array, "n_firms"]            # Долги
    wage_offer: Float[Array, "n_firms"]      # Предлагаемая зарплата
    price: Float[Array, "n_firms"]           # Цена продукции
```

#### MarketState (Рынок)
```python
@chex.dataclass(frozen=True)
class MarketState:
    avg_price: Float[Array, ""]              # Средняя цена (CPI)
    total_supply: Float[Array, ""]           # Общее предложение
    total_demand: Float[Array, ""]           # Общий спрос
    avg_wage: Float[Array, ""]               # Средняя зарплата
    unemployment_rate: Float[Array, ""]      # Уровень безработицы
    interest_rate: Float[Array, ""]          # Процентная ставка
```

## Доступные механизмы

### Налоговые механизмы (fiscal.py)

#### IncomeTax (Подоходный налог)
```python
from polisyos.foundry.fiscal import IncomeTax

tax = IncomeTax(rate=0.2, n_agents=1000)  # 20% налог
new_state, key = tax.step(state, key)
```

#### TaxSubsidy (Налоговые субсидии)
```python
from polisyos.foundry.fiscal import TaxSubsidy

subsidy = TaxSubsidy(rate=0.1, n_agents=1000)  # 10% субсидия
new_state, key = subsidy.step(state, key)
```

### QueueMechanism (Механизм очередей)

Многоуровневый механизм очередей с поддержкой разных fidelity:

```python
from polisyos.foundry.queue import QueueMechanism

queue = QueueMechanism(
    service_rate=0.8,      # Скорость обслуживания
    arrival_rate=1.0,      # Скорость поступления
    fidelity=FidelityLevel.RELAXED_DISCRETE
)
```

## Движок симуляции

### SimulationKernel (legacy)

JIT-скомпилированный экономический цикл (доступен только для обратной совместимости):

```python
from polisyos.foundry._legacy.engine.kernel import SimulationKernel  # deprecated

kernel = SimulationKernel()  # JIT-компиляция при создании

# Один шаг симуляции
final_state, key = kernel.step(state, key)
```

#### Экономический цикл

Каждый шаг включает четыре фазы:

1. **Производство** (Кобб-Дуглас): `Y = A × K^α × L^(1-α)`
2. **Рынок труда**: распределение работников по фирмам
3. **Рынок товаров**: ценообразование и торговля
4. **Потребление**: расходы домохозяйств

```python
# Внутри kernel.py
def _step_logic(self, state: GlobalState, key: jax.Array) -> GlobalState:
    # 1. Производство
    new_firms, produced_goods = update_firms_production(state.firms, key1)

    # 2. Рынок труда
    new_agents, new_firms = update_labor_market(state.agents, new_firms, key2)

    # 3. Рынок товаров
    new_firms, new_agents, new_market = update_goods_market(
        new_firms, new_agents, state.market, produced_goods, key3
    )

    # 4. Потребление
    final_agents = update_agents_consumption(new_agents, new_market, key4)

    # Агрегация макропоказателей
    final_market = aggregate_market_stats(final_agents, new_firms, new_market)

    return state.replace(step=state.step + 1, ...)
```

## Функции потерь и оптимизация

### Policy Loss Function

Функция потерь для градиентной оптимизации политик:

```python
from polisyos.foundry.loss import policy_loss_fn

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
from polisyos.foundry.registry import MECHANISM_SPECS

# Каталог всех механизмов
catalog = mechanism_catalog()
for mech in catalog:
    print(f"{mech['name']}: {mech['description']}")
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

- **Кобб-Дуглас**: `Y = A × K^α × L^(1-α)` с α=0.3 (в legacy engine)
- **Совершенная конкуренция**: на рынках труда и товаров
- **Рациональные агенты**: максимизация полезности
- **Закрытая экономика**: без внешней торговли

### Вычислительные ограничения

- **JAX immutable state**: Все изменения через патчи или `replace()`
- **Static shapes**: Размеры массивов фиксированы при компиляции
- **Limited Python**: Только JAX-совместимые операции в runtime
- **Artifact-based**: Все данные через artifact store

## Связанные модули

### Зависимости Foundry

- **`ir/`**: Policy Surface IR, контракты механизмов, slot/merge registries
- **`core/artifacts`**: Artifact storage для компиляции и исполнения
- **`core/contracts`**: Foundry-specific типы (PatchOp, ProgramGraph, etc.)

### Потребители Foundry

- **`scientist/`**: Использует компилятор для создания execution plans
- **`fabric/`**: Предоставляет данные для инициализации состояния
- **`runtime/`**: Хранит результаты исполнения и обеспечивает аудит

### Интеграция в Pipeline

```
scientist/ → ir/ → foundry.compiler → foundry.runtime → artifacts
                     ↓
               fabric/ (data)    core/artifacts (storage)
```

## Соглашения по коду

- **Строгая типизация**: все функции с type hints
- **Документация**: docstrings для всех публичных API
- **Именование**: snake_case для функций, PascalCase для классов
- **Импорты**: абсолютные импорты внутри polisyos
- **Логирование**: через loguru, без print statements

## Миграция и Roadmap

### Legacy Support

Текущая версия Foundry поддерживает **legacy режим** для обратной совместимости:

- **engine/kernel.py**: Простая симуляция без компиляции
- **basic_simulation.py**: Примеры использования legacy API
- **Direct state changes**: Механизмы могут работать без патчей

### Рекомендации по миграции

1. **Новые механизмы**: Использовать `emit_patches()` вместо `step()`
2. **Новые политики**: Использовать compiler API вместо прямого создания механизмов
3. **Производство**: Переходить на ProgramGraph execution для лучшей производительности

### Будущие улучшения

- **Distributed execution**: Масштабирование на кластеры
- **Advanced merge rules**: Более сложные стратегии разрешения конфликтов
- **Dynamic shapes**: Поддержка переменных размеров массивов
- **GPU acceleration**: Оптимизация для GPU-вычислений

---

Foundry эволюционировал от простого симулятора к высокопроизводительному компилятору политик, обеспечивая масштабируемость, детерминизм и эффективность исполнения экономических моделей.

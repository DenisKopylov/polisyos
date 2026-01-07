# Polisyos Foundry: JAX Simulation Core

**Foundry** - это JAX-ядро дифференцируемых симуляций экономических механизмов политики в системе Policy Engine. Модуль предоставляет математическую основу для моделирования и оптимизации экономических политик с использованием современных дифференцируемых вычислений.

## Роль в архитектуре

Foundry является **runtime backend** в архитектуре Policy Engine, отвечая за исполнение скомпилированных политик:

```
NL → LLM → IR (AST) → Compilation → Runtime (UDF + Foundry) → Artifacts
```

Foundry **не знает** про LLM и работает исключительно с:
- ✅ JAX для дифференцируемых вычислений
- ✅ Экономическими механизмами (налоги, субсидии, очереди)
- ✅ Многоуровневыми симуляциями (multi-fidelity)
- ❌ Никаких БД, LLM или сетевых вызовов

## Технологический стек

- **JAX/JAXlib**: Основа всех вычислений и JIT-компиляции
- **Equinox**: OOP-обертка для JAX-модулей
- **Jaxtyping**: Статическая проверка размерностей тензоров
- **Chex**: Дополнительные проверки типов и форм

## Архитектура

```
foundry/
├── domain/          # Экономическая модель состояний
│   ├── state.py     # GlobalState, AgentState, FirmState, MarketState
│   └── schema.py    # Pydantic схемы конфигурации
├── engine/          # Движок симуляции
│   ├── kernel.py    # SimulationKernel (JIT-шаг экономического цикла)
│   └── logic.py     # Экономическая логика (рынки, производство)
├── base.py          # Абстрактный класс Mechanism
├── types.py         # FidelityLevel enum (уровни точности)
├── fiscal.py        # Налоговые механизмы (IncomeTax, TaxSubsidy)
├── queue.py         # Механизм очередей с multi-fidelity
├── specs.py         # Спецификации механизмов с валидацией
├── registry.py      # Регистрация и фабрика механизмов
├── loss.py          # Функции потерь для оптимизации
├── utils.py         # Утилиты (soft functions, gradient health)
└── basic_simulation.py  # Демо и примеры использования
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

Абстрактный базовый класс для всех экономических механизмов политики:

```python
from polisyos.foundry.base import Mechanism

class Mechanism(eqx.Module):
    fidelity: FidelityLevel = FidelityLevel.SURROGATE_FLUID
    debug_mode: bool = False

    @abstractmethod
    def init_state(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        """Инициализация состояния механизма"""

    @abstractmethod
    def step(self, state: GlobalState, key: jax.Array) -> tuple[GlobalState, jax.Array]:
        """Один шаг механизма"""

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

### SimulationKernel

JIT-скомпилированный экономический цикл:

```python
from polisyos.foundry.engine.kernel import SimulationKernel

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

### Базовая симуляция

```python
from polisyos.foundry.basic_simulation import simple_policy_simulation, analyze_simulation_results

# Запуск симуляции
time_steps, populations = simple_policy_simulation(
    population_size=1000,
    time_steps=50,
    policy_effect=0.05
)

# Анализ результатов
analysis = analyze_simulation_results(time_steps, populations)
print(f"Средний рост: {analysis['total_growth_percent']:.1f}%")
```

### Полная симуляция с механизмом

```python
import jax
import jax.numpy as jnp
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.fiscal import IncomeTax
from polisyos.foundry.engine.kernel import SimulationKernel

# Инициализация состояния
state = GlobalState.empty(n_agents=1000, n_firms=100)
key = jax.random.PRNGKey(42)

# Создание механизма
tax = IncomeTax(rate=0.2, n_agents=1000)

# Инициализация механизма
state, key = tax.init_state(state, key)

# Движок симуляции
kernel = SimulationKernel()

# Запуск симуляции на 12 шагов (месяцев)
for step in range(12):
    state, key = kernel.step(state, key)
    state, key = tax.step(state, key)

print(f"Финальный GDP: {state.gdp:.2f}")
print(f"Средний доход: {jnp.mean(state.agents.income):.2f}")
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

Foundry включает тесты для:

- **JIT-стабильности**: проверка что градиенты не ломаются при компиляции
- **Экономических инвариантов**: сохранение законов экономики
- **Валидации параметров**: корректность входных данных
- **Multi-fidelity**: эквивалентность результатов разных уровней точности

```bash
# Запуск тестов foundry
pytest tests/foundry/ -v

# Проверка JIT-стабильности
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

### Экономическая модель

- **Кобб-Дуглас**: `Y = A × K^α × L^(1-α)` с α=0.3
- **Совершенная конкуренция**: на рынках труда и товаров
- **Рациональные агенты**: максимизация полезности
- **Закрытая экономика**: без внешней торговли

### Вычислительные ограничения

- **JAX immutable state**: все изменения через `replace()`
- **Static shapes**: размеры массивов фиксированы при компиляции
- **Limited Python**: только JAX-совместимые операции

## Связанные модули

- **`ir/`**: контракты и спецификации политик
- **`fabric/`**: данные и UDF для инициализации состояния
- **`scientist/`**: оркестрация и оптимизация политик
- **`runtime/`**: артефакты прогонов и аудит

## Соглашения по коду

- **Строгая типизация**: все функции с type hints
- **Документация**: docstrings для всех публичных API
- **Именование**: snake_case для функций, PascalCase для классов
- **Импорты**: абсолютные импорты внутри polisyos
- **Логирование**: через loguru, без print statements

---

Foundry предоставляет надежную математическую основу для моделирования экономических политик, обеспечивая баланс между точностью, производительностью и дифференцируемостью вычислений.

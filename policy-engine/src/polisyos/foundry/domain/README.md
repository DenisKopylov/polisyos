# Domain Layer (Доменная модель)

## Обзор (актуально на 2026-02-05)

Модуль `domain` определяет базовую структуру данных для экономических симуляций в системе Policy Engine. Модуль предоставляет типизированные состояния агентов, фирм, рынков и глобальной экономики, а также схемы конфигурации для валидации параметров.

## Архитектура

Модуль состоит из двух основных компонентов:

### 1. Экономические состояния (State)
- **`state.py`** - Определение всех состояний системы (агенты, фирмы, рынок, глобальное)

### 2. Схемы конфигурации (Schema)
- **`schema.py`** - Pydantic схемы для валидации конфигураций и параметров
- **Type Validation**: Строгая типизация параметров с Pydantic
- **Business Rules**: Дополнительная валидация бизнес-логики
- **Configuration Management**: Управление конфигурациями симуляций

## Экономическая модель

### AgentState (Состояние агента)

Представляет индивидуального экономического агента (домохозяйство):

```python
@chex.dataclass(frozen=True)
class AgentState:
    # Маска активности
    active: Bool[Array, "n_agents"]              # True если агент участвует в симуляции

    # Демография и навыки
    age: Int[Array, "n_agents"]                  # Возраст агента
    skill_level: Float[Array, "n_agents"]        # Уровень навыков (влияет на зарплату)

    # Финансы
    income: Float[Array, "n_agents"]             # Текущий доход
    reported_income: Float[Array, "n_agents"]    # Декларируемый доход (для налогов)
    savings: Float[Array, "n_agents"]            # Накопления
    consumption: Float[Array, "n_agents"]        # Потребление за период
    risk_aversion: Float[Array, "n_agents"]      # Отношение к риску (0.0-1.0)

    # Работа
    is_employed: Bool[Array, "n_agents"]         # Статус занятости
    employer_id: Int[Array, "n_agents"]          # ID фирмы-работодателя (-1 если безработный)

    @property
    def size(self) -> int:
        return self.income.shape[0]  # Количество агентов
```

### FirmState (Состояние фирмы)

Представляет бизнес-единицу в экономике:

```python
@chex.dataclass(frozen=True)
class FirmState:
    # Статические характеристики
    sector_id: Int[Array, "n_firms"]             # Сектор экономики (0=IT, 1=Агро, ...)

    # Производственные факторы
    productivity: Float[Array, "n_firms"]        # Производительность труда (A в модели Солоу)
    capital: Float[Array, "n_firms"]             # Основной капитал (K)
    labor_count: Float[Array, "n_firms"]         # Численность работников (L)

    # Финансы
    cash: Float[Array, "n_firms"]                # Денежные средства
    inventory: Float[Array, "n_firms"]           # Запасы товаров
    debt: Float[Array, "n_firms"]                # Задолженность

    # Рынок
    wage_offer: Float[Array, "n_firms"]          # Предлагаемая зарплата
    price: Float[Array, "n_firms"]               # Цена продукции фирмы

    @property
    def size(self) -> int:
        return self.capital.shape[0]  # Количество фирм
```

### MarketState (Состояние рынка)

Агрегированные показатели рынка:

```python
@chex.dataclass(frozen=True)
class MarketState:
    # Агрегаты
    avg_price: Float[Array, ""]                  # Средний уровень цен (CPI)
    total_supply: Float[Array, ""]               # Общее предложение товаров
    total_demand: Float[Array, ""]               # Общий спрос на товары

    # Рынок труда
    avg_wage: Float[Array, ""]                   # Средняя зарплата
    unemployment_rate: Float[Array, ""]          # Уровень безработицы

    # Финансовый рынок
    interest_rate: Float[Array, ""]              # Процентная ставка
```

### GlobalState (Глобальное состояние)

Объединяет все компоненты экономики:

```python
@chex.dataclass(frozen=True)
class GlobalState:
    step: Int[Array, ""]                         # Текущий шаг симуляции
    agents: AgentState                           # Состояние всех агентов
    firms: FirmState                             # Состояние всех фирм
    market: MarketState                          # Состояние рынка

    # Правительство и макроэкономика
    government_balance: Float[Array, ""]         # Баланс бюджета правительства
    tax_rate: Float[Array, ""]                   # Ставка налога
    gdp: Float[Array, ""]                        # ВВП

    @classmethod
    def empty(cls, n_agents: int, n_firms: int) -> "GlobalState":
        """Создание пустого состояния с дефолтными значениями"""
        return cls(...)
```

## Инициализация состояний

### Создание пустой экономики

```python
from polisyos.foundry.domain.state import GlobalState

# Создание базовой экономики
economy = GlobalState.empty(n_agents=1000, n_firms=100)

# Структура состояния
print(f"Агентов: {economy.agents.size}")
print(f"Фирм: {economy.firms.size}")
print(f"Начальный ВВП: {economy.gdp}")
print(f"Начальная ставка налога: {economy.tax_rate}")
```

### Кастомная инициализация

```python
import jax.numpy as jnp

# Кастомные агенты
agents = AgentState(
    active=jnp.ones(1000, dtype=jnp.bool_),      # Все активны
    age=jnp.random.randint(18, 80, (1000,)),     # Случайный возраст
    skill_level=jnp.random.normal(1.0, 0.2, (1000,)),  # Навыки ~ N(1.0, 0.2)
    income=jnp.zeros(1000),                      # Начальный доход = 0
    reported_income=jnp.zeros(1000),
    savings=jnp.random.exponential(1000, (1000,)),  # Сбережения ~ Exp(1000)
    consumption=jnp.zeros(1000),
    risk_aversion=jnp.random.beta(2, 5, (1000,)),  # Риск ~ Beta(2,5)
    is_employed=jnp.zeros(1000, dtype=jnp.bool_),   # Никто не работает
    employer_id=jnp.full(1000, -1, dtype=jnp.int32)  # Нет работодателей
)

# Кастомные фирмы
firms = FirmState(
    sector_id=jnp.random.randint(0, 5, (100,)),   # 5 секторов экономики
    productivity=jnp.random.lognormal(0, 0.5, (100,)),  # Продуктивность
    capital=jnp.random.exponential(10000, (100,)),       # Капитал
    labor_count=jnp.zeros(100),                    # Нет работников
    cash=jnp.ones(100) * 50000,                    # Стартовый капитал
    inventory=jnp.zeros(100),
    debt=jnp.zeros(100),
    wage_offer=jnp.ones(100) * 50,                 # Предлагаемая зарплата
    price=jnp.ones(100) * 10                       # Цена продукции
)

# Сборка глобального состояния
economy = GlobalState(
    step=jnp.array(0),
    agents=agents,
    firms=firms,
    market=MarketState(
        avg_price=jnp.array(1.0),
        total_supply=jnp.array(0.0),
        total_demand=jnp.array(0.0),
        avg_wage=jnp.array(50.0),
        unemployment_rate=jnp.array(1.0),          # 100% безработица
        interest_rate=jnp.array(0.05)
    ),
    government_balance=jnp.array(0.0),
    tax_rate=jnp.array(0.0),
    gdp=jnp.array(0.0)
)
```

## Схемы конфигурации

### AgentType (Типы агентов)

```python
from enum import Enum

class AgentType(str, Enum):
    WORKER = "worker"              # Наёмный работник
    ENTREPRENEUR = "entrepreneur"  # Предприниматель
    RETIREE = "retiree"           # Пенсионер
```

### RegionProfile (Региональный профиль)

```python
from pydantic import BaseModel, Field

class RegionProfile(BaseModel):
    """Параметры региона для инициализации популяции агентов."""

    region_id: int
    avg_income: float = Field(..., ge=0, description="Средний доход в регионе")
    unemployment_rate: float = Field(..., ge=0, le=1.0, description="Уровень безработицы")
    tech_level: float = Field(default=1.0, ge=0.5, description="Уровень цифровизации")

    model_config = ConfigDict(frozen=True)  # Неизменяемый объект
```

### SimulationConfig (Конфигурация симуляции)

```python
class SimulationConfig(BaseModel):
    """Глобальные настройки симуляции."""

    n_agents: int = Field(..., gt=0, description="Количество агентов")
    n_steps: int = Field(default=12, gt=0, description="Горизонт планирования (месяцы)")
    seed: int = 42

# Пример использования
config = SimulationConfig(
    n_agents=10000,
    n_steps=120,     # 10 лет
    seed=12345
)

# Валидация конфигурации
try:
    validated_config = SimulationConfig(**user_input)
    print("Конфигурация валидна")
except ValidationError as e:
    print(f"Ошибки валидации: {e}")
```

## Работа с состояниями

### Обновление состояний

```python
from dataclasses import replace

# Обновление состояния агентов (функциональный подход)
new_agents = replace(
    economy.agents,
    income=economy.agents.income + wage_increase,
    consumption=economy.agents.consumption + consumption_increase
)

# Обновление глобального состояния
new_economy = replace(
    economy,
    agents=new_agents,
    step=economy.step + 1,
    gdp=compute_gdp(new_agents, economy.firms)
)
```

### Доступ к данным

```python
# Доступ к массивам агентов
employed_agents = economy.agents.income[economy.agents.is_employed]
unemployed_count = jnp.sum(~economy.agents.is_employed)

# Статистики по фирмам
profitable_firms = economy.firms.cash[economy.firms.cash > 0]
avg_productivity = jnp.mean(economy.firms.productivity)

# Макроэкономические показатели
total_gdp = economy.gdp
inflation_rate = economy.market.avg_price  # Упрощённо
```

### Сериализация и десериализация

```python
import json
from polisyos.core.canon import serialize_state, deserialize_state

# Сериализация состояния
state_dict = serialize_state(economy)
json_data = json.dumps(state_dict)

# Десериализация
loaded_dict = json.loads(json_data)
loaded_economy = deserialize_state(loaded_dict, GlobalState)
```

## Экономическая интерпретация

### Производственная функция

Модель основана на расширенной функции Кобба-Дугласа:

```
Y_i = A_i * K_i^α * L_i^(1-α)
```

где:
- `Y_i` - выпуск фирмы i
- `A_i` - производительность (`firm.productivity`)
- `K_i` - капитал (`firm.capital`)
- `L_i` - труд (`firm.labor_count`)
- `α` - эластичность по капиталу (обычно 0.3-0.4)

### Полезность агентов

Функция полезности агентов комбинирует потребление и сбережения:

```
U_a = (1-β) * log(C_a) + β * log(S_a + 1)
```

где:
- `C_a` - потребление агента a (`agent.consumption`)
- `S_a` - сбережения агента a (`agent.savings`)
- `β` - параметр intertemporal substitution

### Рынок труда

Модель рынка труда с friction:

```
w_i = f(skill_a, productivity_i, unemployment_rate)
```

где зарплата зависит от навыков агента, производительности фирмы и общего уровня безработицы.

## Валидация и проверки

### Инварианты состояния

```python
def check_economy_invariants(state: GlobalState) -> bool:
    """Проверка экономических инвариантов."""

    # Все доходы неотрицательны
    assert jnp.all(state.agents.income >= 0), "Отрицательные доходы"

    # Безработные не имеют работодателя
    unemployed = ~state.agents.is_employed
    no_employer = state.agents.employer_id == -1
    assert jnp.all(unemployed == no_employer), "Несоответствие занятости"

    # Баланс бюджета правительства
    tax_revenue = jnp.sum(state.agents.income * state.tax_rate)
    assert abs(state.government_balance - tax_revenue) < 1e-6, "Нарушение бюджетного баланса"

    return True
```

### Схема валидации

```python
from pydantic import ValidationError

def validate_simulation_config(config_dict: dict) -> SimulationConfig:
    """Валидация конфигурации симуляции."""

    try:
        config = SimulationConfig(**config_dict)

        # Дополнительные бизнес-правила
        if config.n_agents > 100000:
            raise ValueError("Слишком много агентов для симуляции")

        if config.n_steps > 1000:
            raise ValueError("Слишком длинный горизонт симуляции")

        return config

    except ValidationError as e:
        raise ValueError(f"Некорректная конфигурация: {e}") from e
```

## Примеры использования

### Создание тестовой экономики

```python
def create_test_economy(n_agents: int = 100, n_firms: int = 10) -> GlobalState:
    """Создание простой тестовой экономики для экспериментов."""

    # Агенты с нормальным распределением доходов
    agents = AgentState(
        active=jnp.ones(n_agents, dtype=jnp.bool_),
        age=jnp.random.randint(25, 65, (n_agents,)),
        skill_level=jnp.random.normal(1.0, 0.1, (n_agents,)),
        income=jnp.random.lognormal(10, 0.5, (n_agents,)),  # Логнормальный доход
        reported_income=jnp.zeros(n_agents),
        savings=jnp.random.exponential(5000, (n_agents,)),
        consumption=jnp.zeros(n_agents),
        risk_aversion=jnp.random.beta(2, 2, (n_agents,)),
        is_employed=jnp.random.binomial(1, 0.8, (n_agents,)).astype(bool),
        employer_id=jnp.where(
            jnp.random.binomial(1, 0.8, (n_agents,)).astype(bool),
            jnp.random.randint(0, n_firms, (n_agents,)),
            -1
        )
    )

    # Фирмы разных секторов
    firms = FirmState(
        sector_id=jnp.random.randint(0, 3, (n_firms,)),  # 3 сектора
        productivity=jnp.random.lognormal(0, 0.3, (n_firms,)),
        capital=jnp.random.exponential(50000, (n_firms,)),
        labor_count=jnp.random.poisson(20, (n_firms,)).astype(float),
        cash=jnp.random.exponential(100000, (n_firms,)),
        inventory=jnp.zeros(n_firms),
        debt=jnp.zeros(n_firms),
        wage_offer=jnp.random.normal(50, 10, (n_firms,)),
        price=jnp.random.normal(15, 5, (n_firms,))
    )

    # Рыночные агрегаты
    market = MarketState(
        avg_price=jnp.array(1.0),
        total_supply=jnp.sum(firms.inventory),
        total_demand=jnp.sum(agents.consumption),
        avg_wage=jnp.mean(firms.wage_offer),
        unemployment_rate=jnp.mean(~agents.is_employed).astype(float),
        interest_rate=jnp.array(0.03)
    )

    return GlobalState(
        step=jnp.array(0),
        agents=agents,
        firms=firms,
        market=market,
        government_balance=jnp.array(0.0),
        tax_rate=jnp.array(0.2),
        gdp=jnp.array(0.0)  # Будет вычислено механизмом
    )
```

### Анализ состояния экономики

```python
def analyze_economy(state: GlobalState) -> dict:
    """Анализ ключевых показателей экономики."""

    return {
        "total_population": state.agents.size,
        "employed_ratio": jnp.mean(state.agents.is_employed),
        "avg_income": jnp.mean(state.agents.income),
        "income_gini": compute_gini(state.agents.income),
        "total_firms": state.firms.size,
        "avg_firm_size": jnp.mean(state.firms.labor_count),
        "unemployment_rate": state.market.unemployment_rate,
        "gdp_per_capita": state.gdp / state.agents.size if state.gdp > 0 else 0,
        "government_balance": state.government_balance,
        "inflation_proxy": state.market.avg_price
    }

# Анализ экономики
stats = analyze_economy(economy)
for key, value in stats.items():
    print(f"{key}: {float(value):.3f}")
```

## Связь с другими модулями

- **`foundry.base`**: Использует состояния для определения механизмов
- **`foundry.compile.api`**: Компилятор работает с состояниями для генерации кода
- **`foundry.runtime`**: Runtime обновляет состояния во время исполнения
- **`agent_sim`**: Более детальная модель агентов наследует от базовых состояний
- **`plugins`**: Плагины доменов используют состояния для своих симуляций

---

Модуль `domain` предоставляет фундаментальную структуру данных для всех экономических симуляций в Policy Engine, обеспечивая типобезопасность, валидацию и совместимость между различными компонентами системы.
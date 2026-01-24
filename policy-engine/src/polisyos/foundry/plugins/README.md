# PolisyOS Foundry Plugins

## Обзор

Модуль `plugins` предоставляет модульную архитектуру плагинов для доменно-специфичных симуляций (экономика, здравоохранение, климат и т.д.). Модуль определяет базовые протоколы, реестр плагинов и утилиты для построения мульти-доменных симуляций.

## Архитектура

### 1. Core Components (Базовые компоненты)
- **`core.py`** - Протоколы плагинов, метаданные и реестр
- **`composite.py`** - Композитное состояние и исполнитель для мульти-доменных симуляций
- **`discovery.py`** - Автообнаружение плагинов
- **`api.py`** - High-level API `PolisySimulator`

### 2. Domain Plugins (Доменные плагины)
- **`economics/`** - Экономический домен с гетерогенными агентами

## Core Protocols (Базовые протоколы)

### PluginMetadata (Метаданные плагина)

```python
@dataclass(frozen=True)
class PluginMetadata:
    name: str                          # Уникальное имя плагина
    version: str                       # Версия плагина
    description: str                   # Описание функциональности
    author: str                        # Автор плагина
    capabilities: tuple[PluginCapability, ...]  # Поддерживаемые возможности
    tags: tuple[str, ...]              # Теги для категоризации
```

### PluginCapability (Возможности плагинов)

```python
class PluginCapability(str, Enum):
    AGENTS = "agents"                  # Поддержка агентов
    MECHANISMS = "mechanisms"          # Экономические механизмы
    REWARDS = "rewards"                # Функции вознаграждения
    OBJECTIVES = "objectives"          # Целевые функции
    OBSERVATIONS = "observations"      # Наблюдения состояния
    VISUALIZATION = "visualization"    # Визуализация результатов
```

### DomainPlugin Protocol (Протокол доменного плагина)

```python
class DomainPlugin(Protocol[State]):
    @property
    def metadata(self) -> PluginMetadata: ...

    def create_initial_state(
        self, config: DomainConfig, rng_key: jax.Array
    ) -> State: ...

    def get_mechanisms(self) -> Sequence[MechanismProtocol[State]]: ...

    def get_reward_function(self) -> RewardProtocol[State]: ...

    def get_objectives(self) -> dict[str, ObjectiveProtocol[State]]: ...
```

## Economics Plugin (Экономический плагин)

### Обзор

Экономический плагин предоставляет полную модель экономики с гетерогенными агентами, фирмами и рынками. Плагин реализует современные экономические механизмы и поддерживает как микро-, так и макроэкономический анализ.

### Возможности

- ✅ **Гетерогенные агенты**: Агенты с различными предпочтениями, навыками и поведением
- ✅ **Производственные фирмы**: Модель с производственной функцией Кобба-Дугласа
- ✅ **Рынки**: Труда, товаров, финансовый рынок
- ✅ **Налоговые механизмы**: Подоходный налог, субсидии, перераспределение
- ✅ **Социальная защита**: Пособия по безработице, пенсионная система
- ✅ **Макроэкономические цели**: ВВП, безработица, неравенство

### EconomicState (Экономическое состояние)

```python
@chex.dataclass(frozen=True)
class EconomicState:
    """Полное состояние экономической системы."""

    # Агенты (домохозяйства)
    agents: AgentState

    # Фирмы (предприятия)
    firms: FirmState

    # Рынки
    labor_market: LaborMarketState
    goods_market: GoodsMarketState

    # Правительство
    government: GovernmentState

    # Макроэкономика
    gdp: Float[Array, ""]
    inflation: Float[Array, ""]
    unemployment_rate: Float[Array, ""]

    # Временные метки
    step: Int[Array, ""]
    time_step: Int[Array, ""]
```

### Механизмы экономики

#### LaborMarketMechanism (Механизм рынка труда)

```python
class LaborMarketMechanism(Mechanism):
    """Модель рынка труда с поиском работы и увольнениями."""

    def apply(self, state: EconomicState, key: jax.Array) -> EconomicState:
        # Поиск работы безработными агентами
        unemployed = ~state.agents.employed
        job_offers = self._generate_job_offers(state.firms, key)

        # Сопоставление кандидатов и вакансий
        new_employments = self._match_workers_to_jobs(
            unemployed_agents=state.agents[unemployed],
            job_offers=job_offers,
            key=key
        )

        # Обновление состояния
        return self._update_labor_market(state, new_employments)
```

#### TaxationMechanism (Налоговый механизм)

```python
class TaxationMechanism(Mechanism):
    """Механизм сбора налогов и формирования бюджета."""

    tax_rate: float = 0.2              # Ставка подоходного налога
    corporate_tax_rate: float = 0.25    # Ставка корпоративного налога

    def apply(self, state: EconomicState, key: jax.Array) -> EconomicState:
        # Расчёт подоходного налога
        income_tax = state.agents.income * self.tax_rate
        total_income_tax = jnp.sum(income_tax)

        # Расчёт корпоративного налога
        profits = state.firms.revenue - state.firms.costs
        corporate_tax = jnp.maximum(profits, 0) * self.corporate_tax_rate
        total_corporate_tax = jnp.sum(corporate_tax)

        # Обновление бюджета правительства
        new_gov_balance = (
            state.government.balance +
            total_income_tax +
            total_corporate_tax
        )

        return state.replace(
            agents=state.agents.replace(
                income=state.agents.income - income_tax
            ),
            firms=state.firms.replace(
                cash=state.firms.cash - corporate_tax
            ),
            government=state.government.replace(
                balance=new_gov_balance
            )
        )
```

#### TransferMechanism (Механизм трансфертов)

```python
class TransferMechanism(Mechanism):
    """Механизм социальных трансфертов."""

    unemployment_benefit: float = 1000.0   # Пособие по безработице
    child_allowance: float = 200.0         # Детские пособия

    def apply(self, state: EconomicState, key: jax.Array) -> EconomicState:
        unemployed = ~state.agents.employed
        has_children = state.agents.children > 0

        # Расчёт пособий
        unemployment_payments = unemployed * self.unemployment_benefit
        child_payments = has_children * self.child_allowance * state.agents.children

        total_payments = unemployment_payments + child_payments
        total_cost = jnp.sum(total_payments)

        return state.replace(
            agents=state.agents.replace(
                income=state.agents.income + total_payments
            ),
            government=state.government.replace(
                balance=state.government.balance - total_cost
            )
        )
```

#### ConsumptionMechanism (Механизм потребления)

```python
class ConsumptionMechanism(Mechanism):
    """Механизм принятия решений о потреблении."""

    def apply(self, state: EconomicState, key: jax.Array) -> EconomicState:
        # Решение о потреблении на основе полезности
        optimal_consumption = self._solve_consumption_problem(
            income=state.agents.income,
            savings=state.agents.savings,
            prices=state.goods_market.prices,
            preferences=state.agents.preferences
        )

        # Обновление состояния
        new_savings = state.agents.savings + state.agents.income - optimal_consumption

        return state.replace(
            agents=state.agents.replace(
                consumption=optimal_consumption,
                savings=new_savings
            ),
            goods_market=state.goods_market.replace(
                demand=jnp.sum(optimal_consumption)
            )
        )
```

#### SavingsMechanism (Механизм сбережений)

```python
class SavingsMechanism(Mechanism):
    """Механизм принятия решений о сбережениях."""

    time_preference: float = 0.05         # Временные предпочтения
    risk_aversion: float = 2.0           # Отношение к риску

    def apply(self, state: EconomicState, key: jax.Array) -> EconomicState:
        # Оптимизация портфеля сбережений
        portfolio_allocation = self._optimize_portfolio(
            wealth=state.agents.savings,
            expected_returns=state.financial_market.expected_returns,
            risk_matrix=state.financial_market.covariance,
            risk_aversion=self.risk_aversion,
            time_horizon=state.agents.planning_horizon
        )

        return state.replace(
            agents=state.agents.replace(
                portfolio=portfolio_allocation
            )
        )
```

### Функции вознаграждения

#### EconomicReward (Экономическое вознаграждение)

```python
class EconomicReward(RewardProtocol[EconomicState]):
    """Функция вознаграждения для экономических агентов."""

    consumption_weight: float = 1.0
    savings_weight: float = 0.5
    inequality_penalty: float = 0.1

    def __call__(self, state: EconomicState) -> Float[Array, "n_agents"]:
        # Вознаграждение за потребление
        consumption_reward = self.consumption_weight * jnp.log(state.agents.consumption + 1)

        # Вознаграждение за сбережения
        savings_reward = self.savings_weight * jnp.log(state.agents.savings + 1)

        # Штраф за неравенство (для социальных целей)
        gini = compute_gini(state.agents.income)
        inequality_penalty = self.inequality_penalty * gini

        return consumption_reward + savings_reward - inequality_penalty
```

### Целевые функции

#### GDPObjective (Цель максимизации ВВП)

```python
class GDPObjective(ObjectiveProtocol[EconomicState]):
    """Максимизация валового внутреннего продукта."""

    def __call__(self, state: EconomicState) -> float:
        return float(state.gdp)

    def gradient(self, state: EconomicState) -> EconomicState:
        # Градиент по факторам производства
        return state  # Реализация зависит от модели
```

#### GiniObjective (Цель минимизации неравенства)

```python
class GiniObjective(ObjectiveProtocol[EconomicState]):
    """Минимизация коэффициента Джини."""

    def __call__(self, state: EconomicState) -> float:
        gini = compute_gini(state.agents.income)
        return -float(gini)  # Минимизация неравенства = максимизация отрицательного Gini

    def gradient(self, state: EconomicState) -> EconomicState:
        # Градиент по распределению доходов
        return state
```

#### UnemploymentObjective (Цель минимизации безработицы)

```python
class UnemploymentObjective(ObjectiveProtocol[EconomicState]):
    """Минимизация уровня безработицы."""

    target_unemployment: float = 0.05  # Целевая безработица 5%

    def __call__(self, state: EconomicState) -> float:
        unemployment = state.unemployment_rate
        deviation = abs(unemployment - self.target_unemployment)
        return -float(deviation)  # Минимизация отклонения
```

#### Social Welfare Objectives (Социальное благосостояние)

```python
class UtilitarianWelfare(ObjectiveProtocol[EconomicState]):
    """Утилитаристское социальное благосостояние."""

    def __call__(self, state: EconomicState) -> float:
        # Сумма полезностей всех агентов
        utilities = jnp.log(state.agents.consumption + 1)
        return float(jnp.sum(utilities))

class RawlsianWelfare(ObjectiveProtocol[EconomicState]):
    """Равлсианское социальное благосостояние."""

    def __call__(self, state: EconomicState) -> float:
        # Максимум минимума полезности
        utilities = jnp.log(state.agents.consumption + 1)
        return float(jnp.min(utilities))
```

## High-Level API

### PolisySimulator (Высокоуровневый симулятор)

```python
from polisyos.foundry.plugins import PolisySimulator, DomainConfig

# Создание симулятора
sim = PolisySimulator()

# Добавление экономического домена
sim.add_domain(
    "economics",
    DomainConfig(
        n_agents=1000,
        n_firms=100,
        parameters={
            "tax_rate": 0.2,
            "unemployment_benefit": 1000.0,
            "interest_rate": 0.03
        }
    )
)

# Запуск симуляции
result = sim.run(n_steps=256)

# Получение результатов
gdp_series = result.get_metric("economics", "gdp")
unemployment_series = result.get_metric("economics", "unemployment_rate")
```

### Мульти-доменные симуляции

```python
# Создание мульти-доменной симуляции
sim = PolisySimulator()

# Добавление доменов
sim.add_domain("economics", DomainConfig(n_agents=1000))
sim.add_domain("healthcare", DomainConfig(n_agents=1000))
sim.add_domain("education", DomainConfig(n_agents=1000))

# Добавление взаимодействий между доменами
sim.add_interaction(
    source_domain="healthcare",
    target_domain="economics",
    source_field="healthcare_costs",
    target_field="agents.consumption",
    transformation=lambda x: x * 0.1  # 10% от расходов на здравоохранение
)

sim.add_interaction(
    source_domain="education",
    target_domain="economics",
    source_field="education_achievement",
    target_field="agents.skill_level",
    transformation=lambda x: x * 0.05  # Прирост навыков
)

# Запуск симуляции
result = sim.run(n_steps=128)
```

## Регистр плагинов

### PluginRegistry (Реестр плагинов)

```python
from polisyos.foundry.plugins.core import get_registry

# Получение глобального реестра
registry = get_registry()

# Регистрация плагина
registry.register(EconomicsPlugin())

# Получение плагина
economics_plugin = registry.get_plugin("economics")

# Список всех плагинов
available_plugins = registry.list_plugins()
print(f"Доступные плагины: {list(available_plugins.keys())}")
```

### Автообнаружение плагинов

```python
from polisyos.foundry.plugins.discovery import auto_register_plugins

# Автоматическая регистрация всех плагинов
auto_register_plugins()

# Создание плагина из простого описания
simple_plugin = create_simple_plugin(
    name="custom_economics",
    mechanisms=[CustomTaxMechanism(), CustomLaborMechanism()],
    reward_fn=custom_reward_function
)
```

## CLI Interface (Командная строка)

```bash
# Список доступных плагинов
python -m polisyos.foundry.plugins.cli list

# Запуск симуляции
python -m polisyos.foundry.plugins.cli run \
    --domain economics \
    --n-steps 128 \
    --n-agents 1000 \
    --output results.json

# Мульти-доменная симуляция
python -m polisyos.foundry.plugins.cli run \
    --domains economics healthcare \
    --n-steps 64 \
    --config simulation_config.json
```

## Composite States (Композитные состояния)

### CompositeState (Составное состояние)

```python
from polisyos.foundry.plugins.composite import CompositeState

# Создание композитного состояния
composite = CompositeState({
    "economics": EconomicState(...),
    "healthcare": HealthcareState(...),
    "education": EducationState(...)
})

# Доступ к субсостояниям
economic_state = composite.get_state("economics")
gdp = economic_state.gdp

# Обновление субсостояния
new_economic_state = economic_state.replace(gdp=gdp * 1.05)
composite = composite.update_state("economics", new_economic_state)
```

### CrossDomainInteraction (Междоменные взаимодействия)

```python
from polisyos.foundry.plugins.composite import CrossDomainInteraction

# Определение взаимодействия
health_economy_interaction = CrossDomainInteraction(
    source_domain="healthcare",
    target_domain="economics",
    source_field="disease_prevalence",
    target_field="agents.productivity",
    transformation=lambda prevalence: 1.0 - prevalence * 0.1  # Болезни снижают продуктивность
)

# Применение взаимодействия
updated_composite = health_economy_interaction.apply(composite)
```

## Примеры использования

### Базовая экономическая симуляция

```python
from polisyos.foundry.plugins import PolisySimulator, DomainConfig

# Настройка экономической симуляции
sim = PolisySimulator()
sim.add_domain("economics", DomainConfig(
    n_agents=1000,
    n_firms=50,
    parameters={
        "tax_rate": 0.15,
        "unemployment_benefit": 800.0,
        "minimum_wage": 1200.0,
        "interest_rate": 0.025
    }
))

# Запуск и анализ
result = sim.run(n_steps=120)  # 10 лет

# Анализ результатов
print("=== Экономические показатели ===")
gdp_final = result.get_metric("economics", "gdp")[-1]
unemployment_final = result.get_metric("economics", "unemployment_rate")[-1]
gini_final = result.get_metric("economics", "income_gini")[-1]

print(f"Финальный ВВП: ${gdp_final:,.0f}")
print(f"Уровень безработицы: {unemployment_final:.1%}")
print(f"Коэффициент Джини: {gini_final:.3f}")
```

### Политика сравнения

```python
# Сравнение разных налоговых политик
policies = [
    {"name": "flat_tax", "tax_rate": 0.2, "progressive": False},
    {"name": "progressive_tax", "tax_rate": 0.25, "progressive": True},
    {"name": "high_tax", "tax_rate": 0.35, "progressive": True}
]

results = {}
for policy in policies:
    sim = PolisySimulator()
    sim.add_domain("economics", DomainConfig(
        n_agents=1000,
        parameters=policy
    ))

    result = sim.run(n_steps=60)
    results[policy["name"]] = {
        "gdp_growth": result.get_metric("economics", "gdp")[-1] /
                     result.get_metric("economics", "gdp")[0] - 1,
        "avg_unemployment": jnp.mean(result.get_metric("economics", "unemployment_rate")),
        "final_gini": result.get_metric("economics", "income_gini")[-1]
    }

# Сравнение результатов
for name, metrics in results.items():
    print(f"{name}:")
    print(".2%")
    print(".1%")
    print(".3f")
```

### Продвинутая симуляция с обучением

```python
from polisyos.foundry.plugins import PolisySimulator, DomainConfig
from polisyos.foundry.agent_sim import ActorCritic, train_actor_critic

# Создание симулятора с обучением агентов
sim = PolisySimulator()
sim.add_domain("economics", DomainConfig(
    n_agents=500,
    parameters={"enable_learning": True}
))

# Определение модели RL для агентов
model = ActorCritic(
    obs_dim=15,  # Размерность наблюдений экономики
    action_dim=3,  # Действия: потребление, сбережения, налоги
    hidden_dims=[128, 64]
)

# Обучение агентов в экономической среде
trained_model = sim.train_agents(
    model=model,
    n_episodes=100,
    episode_length=24,  # 2 года
    objective="social_welfare"  # Целевая функция
)

# Симуляция с обученными агентами
result = sim.run(n_steps=120, agent_model=trained_model)
```

## Связь с другими модулями

- **`domain`**: Использует базовые состояния экономики
- **`agent_sim`**: Интегрируется с симуляцией агентов для RL
- **`calibration`**: Калибровка параметров экономических моделей
- **`foundry.compiler`**: Компиляция политик для исполнения
- **`scientist`**: Высокоуровневый API для экспериментов

---

Модуль `plugins` предоставляет гибкую и расширяемую архитектуру для создания комплексных мульти-доменных симуляций с поддержкой машинного обучения и междисциплинарных взаимодействий.

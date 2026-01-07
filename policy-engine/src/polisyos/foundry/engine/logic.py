import jax
import jax.numpy as jnp

from polisyos.foundry.domain.state import AgentState, FirmState, MarketState

# === ПРОИЗВОДСТВО (Кобб-Дуглас) ===


def cobb_douglas_production(
    productivity: float, capital: float, labor: float, alpha: float = 0.3
) -> float:
    """
    Функция Кобба-Дугласа: Y = A * K^α * L^(1-α)
    alpha = 0.3 (стандартная эластичность капитала)
    """
    return productivity * (capital**alpha) * (labor ** (1 - alpha))


def update_firms_production(firms: FirmState, key: jax.Array) -> tuple[FirmState, jax.Array]:
    """
    Фирмы производят товары используя функцию Кобба-Дугласа.
    Возвращает: (обновленные фирмы, произведенные товары)
    """
    # Производство для каждой фирмы
    production = jax.vmap(cobb_douglas_production)(
        firms.productivity, firms.capital, firms.labor_count
    )

    # Обновляем запасы товаров (производство идет на склад)
    new_inventory = firms.inventory + production

    # Вычитаем затраты на производство (упрощенная модель)
    # Предполагаем, что затраты = 20% от производства
    production_costs = production * 0.2
    new_cash = firms.cash - production_costs

    updated_firms = firms.replace(inventory=new_inventory, cash=new_cash)

    return updated_firms, production


# === РЫНОК ТРУДА ===


def update_labor_market(
    agents: AgentState, firms: FirmState, key: jax.Array
) -> tuple[AgentState, FirmState]:
    """
    Рынок труда: простая модель случайного распределения.
    """
    n_agents = agents.size
    n_firms = firms.size

    # Случайно выбираем, кто работает (примерно половина агентов)
    employment_probs = jax.random.uniform(key, shape=(n_agents,))
    employment_threshold = 0.5  # 50% занятость
    new_is_employed = employment_probs < employment_threshold

    # Для занятых агентов случайно выбираем фирму
    firm_choices = jax.random.randint(key, shape=(n_agents,), minval=0, maxval=n_firms)
    new_employer_ids = jnp.where(new_is_employed, firm_choices, -1)

    # Подсчитываем штат каждой фирмы
    employed_mask = new_is_employed
    employed_firm_ids = jnp.where(employed_mask, new_employer_ids, 0)  # 0 как dummy
    labor_counts = jax.ops.segment_sum(jnp.ones_like(employed_firm_ids), employed_firm_ids, n_firms)

    # Обновляем зарплаты
    new_income = jnp.zeros(n_agents, dtype=jnp.float32)
    employed_firm_ids_safe = jnp.where(employed_mask, new_employer_ids, 0)
    safe_firm_ids = jnp.clip(employed_firm_ids_safe, 0, n_firms - 1)
    wage_rates = firms.wage_offer[safe_firm_ids] * agents.skill_level
    new_income = jnp.where(employed_mask, wage_rates, 0.0)

    updated_agents = agents.replace(
        employer_id=new_employer_ids, is_employed=new_is_employed, income=new_income
    )

    updated_firms = firms.replace(labor_count=labor_counts)

    return updated_agents, updated_firms


# === РЫНОК ТОВАРОВ ===


def update_goods_market(
    firms: FirmState,
    agents: AgentState,
    market: MarketState,
    produced_goods: jax.Array,
    key: jax.Array,
) -> tuple[FirmState, AgentState, MarketState]:
    """
    Рынок товаров: фирмы устанавливают цены, агенты покупают.
    """
    # 1. Фирмы устанавливают цены (на основе спроса/предложения)
    # Упрощенная модель: цена = стоимость производства * наценка
    production_cost_per_unit = 1.0  # упрощение
    markup = 1.5  # 50% наценка
    new_prices = production_cost_per_unit * markup * jnp.ones_like(firms.price)

    # 2. Агенты формируют спрос
    # Спрос = доход * propensity_to_consume (склонность к потреблению)
    propensity_to_consume = 0.8
    total_income = jnp.sum(agents.income)
    total_demand = total_income * propensity_to_consume

    # 3. Рыночное равновесие (упрощенное)
    total_supply = jnp.sum(produced_goods)

    # Если предложение > спрос -> цены падают, иначе растут
    price_adjustment = jnp.where(total_supply > total_demand, 0.95, 1.05)
    new_prices = new_prices * price_adjustment

    # 4. Агенты покупают товары
    # Упрощение: фиксированное потребление на агента
    base_consumption = 2.0  # каждый агент потребляет 2 единицы товара
    consumption_per_agent = jnp.where(agents.income > 0, base_consumption, 0.0)

    # Обновляем потребление агентов
    new_consumption = agents.consumption + consumption_per_agent

    # 5. Фирмы получают выручку
    # Предполагаем равномерное распределение продаж между фирмами
    total_revenue = jnp.sum(consumption_per_agent) * jnp.mean(new_prices)
    revenue_per_firm = total_revenue / firms.size
    new_cash = firms.cash + revenue_per_firm

    # 6. Обновляем запасы (продажи уменьшают запасы)
    total_sales = jnp.sum(consumption_per_agent)
    total_produced = jnp.sum(produced_goods)
    produced_safe = jnp.where(total_produced > 0, total_produced, 1.0)
    sales_per_firm = produced_goods / produced_safe * total_sales
    new_inventory = firms.inventory - sales_per_firm

    updated_firms = firms.replace(price=new_prices, cash=new_cash, inventory=new_inventory)

    updated_agents = agents.replace(consumption=new_consumption)

    updated_market = market.replace(total_supply=total_supply, total_demand=total_demand)

    return updated_firms, updated_agents, updated_market


# === ПОТРЕБЛЕНИЕ ===


def update_agents_consumption(
    agents: AgentState, market: MarketState, key: jax.Array
) -> AgentState:
    """
    Агенты потребляют и формируют сбережения.
    """
    # Агенты тратят часть дохода на потребление, остальное сберегают
    consumption_rate = 0.8  # 80% дохода на потребление
    consumption_expenses = agents.income * consumption_rate

    # Сбережения = доход - потребление
    new_savings = agents.savings + (agents.income - consumption_expenses)

    # Старение (простая модель)
    new_age = agents.age + 1

    return agents.replace(age=new_age, consumption=consumption_expenses, savings=new_savings)


# === АГРЕГАЦИЯ СТАТИСТИКИ ===


def aggregate_market_stats(
    agents: AgentState, firms: FirmState, market: MarketState
) -> MarketState:
    """
    Агрегируем макроэкономические показатели.
    """
    # Средняя цена
    avg_price = jnp.mean(firms.price)

    # Средняя зарплата
    employed_mask = agents.is_employed
    employed_incomes = jnp.where(employed_mask, agents.income, 0)
    employed_count = jnp.sum(employed_mask)
    avg_wage = jnp.where(employed_count > 0, jnp.sum(employed_incomes) / employed_count, 0)

    # Уровень безработицы
    unemployment_rate = 1 - (employed_count / agents.size)

    # Процентная ставка (упрощенная модель)
    # Если безработица высокая -> ставка падает, низкая -> растет
    interest_rate = 0.05 + (unemployment_rate - 0.05) * 0.1  # базовая 5%, чувствительность 10%

    return market.replace(
        avg_price=avg_price,
        avg_wage=avg_wage,
        unemployment_rate=unemployment_rate,
        interest_rate=interest_rate,
    )

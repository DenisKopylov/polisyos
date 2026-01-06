# src/orchestrator/data_loader.py

import jax.numpy as jnp

from src.domain.state import AgentState, FirmState, GlobalState, MarketState
from src.udf.engine import UDFEngine
from src.udf.schema import DataViewRequest, DataViewType
from src.utils.logger import logger


def load_initial_state(udf: UDFEngine, source_run_id: str, step: int = 0) -> GlobalState:
    """
    Загружает состояние агентов из UDF и конвертирует в JAX PyTree.
    """
    logger.info(f"📥 Loading state from RunID: {source_run_id} at Step: {step}")

    # 1. Формируем запрос к UDF (хотим всех агентов)
    # Нам нужны сырые данные, поэтому берем SNAPSHOT, но без агрегации (пока хак через metrics)
    # В реальном UDF для инициализации лучше иметь отдельный метод, но используем то, что есть.
    req = DataViewRequest(
        request_id="init_load",
        run_id=source_run_id,
        view_type=DataViewType.SNAPSHOT,
        metrics=["income", "age", "savings", "is_employed"],  # Колонки, которые нам нужны
        step_end=step,
        aggregation="mean",  # В данном контексте мы будем игнорировать агрегацию,
        # если доработаем engine, или получим "среднего агента".
        # ДЛЯ MVP: Давайте лучше сделаем прямой SQL запрос в UDFEngine для сырых данных
        # или допустим, что SNAPSHOT возвращает rows, если aggregation не задан (нужна доработка schema).
    )

    # ХАК ДЛЯ MVP: Прямой доступ к DuckDB, чтобы получить список всех агентов,
    # так как DataViewRequest пока заточен под агрегаты.
    # В будущем: добавить ViewType.RAW_DUMP
    query = f"""
        SELECT age, income, savings, is_employed
        FROM agents_snapshot
        WHERE run_id = '{source_run_id}' AND step = {step}
    """
    df = udf.db.conn.execute(query).fetchdf()

    if df.empty:
        raise ValueError(f"No data found for RunID: {source_run_id} at Step: {step}")

    n_agents = len(df)
    logger.info(f"👥 Found {n_agents} agents in DB.")

    # 2. Конвертация Pandas -> JAX
    # JAX любит типизированные массивы
    # Обратите внимание: в базе данных нет skill_level, consumption, employer_id
    # Их нужно инициализировать дефолтными значениями
    agents = AgentState(
        age=jnp.array(df["age"].values, dtype=jnp.int32),
        skill_level=jnp.ones(n_agents, dtype=jnp.float32),  # Дефолтное значение
        income=jnp.array(df["income"].values, dtype=jnp.float32),
        savings=jnp.array(df["savings"].values, dtype=jnp.float32),
        consumption=jnp.zeros(n_agents, dtype=jnp.float32),  # Дефолтное значение
        is_employed=jnp.array(df["is_employed"].values, dtype=bool),
        employer_id=jnp.full(n_agents, -1, dtype=jnp.int32),  # Дефолтное значение
    )

    # 3. Для MVP создаем пустые фирмы и рынок
    # В будущем можно тоже загружать из базы данных
    firms = FirmState(
        sector_id=jnp.zeros(10, dtype=jnp.int32),
        productivity=jnp.ones(10, dtype=jnp.float32),
        capital=jnp.ones(10, dtype=jnp.float32) * 100.0,
        labor_count=jnp.zeros(10, dtype=jnp.float32),
        cash=jnp.ones(10, dtype=jnp.float32) * 10000.0,
        inventory=jnp.zeros(10, dtype=jnp.float32),
        debt=jnp.zeros(10, dtype=jnp.float32),
        wage_offer=jnp.ones(10, dtype=jnp.float32) * 10.0,
        price=jnp.ones(10, dtype=jnp.float32),
    )

    market = MarketState(
        avg_price=1.0,
        total_supply=0.0,
        total_demand=0.0,
        avg_wage=10.0,
        unemployment_rate=0.0,
        interest_rate=0.05,
    )

    # 4. Баланс правительства (можно тоже читать из DB, но пока дадим 0)
    return GlobalState(
        agents=agents, firms=firms, market=market, government_balance=0.0, gdp=0.0, step=step
    )

import jax
import jax.numpy as jnp

from src.domain.state import GlobalState
from src.utils.logger import logger


def main():
    logger.info("🏗 Testing NEW Global State (Agents + Firms)...")

    N_AGENTS = 100
    N_FIRMS = 10

    # 1. Инициализация
    state = GlobalState.empty(n_agents=N_AGENTS, n_firms=N_FIRMS)

    # 2. Проверка размеров
    logger.info(f"Agents allocated: {state.agents.size}")
    logger.info(f"Firms allocated: {state.firms.size}")
    logger.info(f"Initial Avg Price: {state.market.avg_price}")

    assert state.agents.size == N_AGENTS
    assert state.firms.size == N_FIRMS

    # 3. Проверка назначения на работу (JAX magic)
    # Назначим первых 10 агентов на фирму #0
    new_employer_ids = state.agents.employer_id.at[:10].set(0)

    new_agents = state.agents.replace(employer_id=new_employer_ids)

    # Считаем штат фирмы #0 через сегментную сумму (как обсуждали)
    # Создаем массив единиц
    ones = jnp.ones(N_AGENTS)
    # Считаем, сколько людей работает в каждой фирме.
    # ВАЖНО: employer_id=-1 (безработные) нужно игнорировать или обрабатывать отдельно.
    # Для простоты теста считаем только тех, у кого ID >= 0

    # Фильтр: берем только занятых
    mask_employed = new_employer_ids >= 0
    safe_ids = jnp.where(mask_employed, new_employer_ids, 0)  # -1 превращаем в 0 временно
    counts = jax.ops.segment_sum(jnp.where(mask_employed, 1.0, 0.0), safe_ids, N_FIRMS)

    logger.info(f"Firm 0 employees: {counts[0]} (Expected 10.0)")

    if counts[0] == 10.0:
        logger.success("✅ New State Structure is Valid & JAX-Ready!")
    else:
        logger.error("❌ Aggregation logic failed.")


if __name__ == "__main__":
    main()

# check_domain.py
# Хак импортов для конфига (как мы делали раньше)
import jax  # noqa: E402
import jax.numpy as jnp  # noqa: E402

from src.domain.state import GlobalState  # noqa: E402
from src.utils.logger import logger  # noqa: E402


def main():
    logger.info("🚀 Starting Domain Model Check...")

    N = 1_000_000  # Тестируем на миллионе агентов

    # 1. Инициализация (на CPU это займет мгновения, т.к. JAX ленивый)
    logger.info(f"Allocating state for {N:,} agents...")
    state = GlobalState.empty(n_agents=N)

    # 2. Простой расчет (Векторизация в действии)
    # Допустим, мы хотим выдать всем грант 500 единиц

    @jax.jit
    def apply_grant(s: GlobalState, amount: float) -> GlobalState:
        # Обрати внимание: мы создаем НОВЫЙ стейт, а не меняем старый (Functional Programming)
        new_income = s.agents.income + amount

        # Обновляем структуру (replace создает копию с измененным полем)
        new_agents = s.agents.replace(income=new_income)
        return s.replace(agents=new_agents)

    logger.info("Running JIT compilation...")
    # Первый запуск - компиляция
    state_v2 = apply_grant(state, 500.0)
    # block_until_ready нужен, чтобы замерить реальное время выполнения асинхронного JAX
    state_v2.agents.income.block_until_ready()
    logger.info("Calculation complete.")

    # Проверка результатов
    sample = state_v2.agents.income[:5]
    logger.info(f"Sample incomes: {sample}")

    assert jnp.all(state_v2.agents.income == 500.0), "Grant logic failed!"
    logger.success("✅ Domain Layer is JAX-compatible!")


if __name__ == "__main__":
    main()

import time

import jax  # noqa: E402
import jax.numpy as jnp  # noqa: E402

from src.domain.state import GlobalState  # noqa: E402
from src.engine.kernel import SimulationKernel  # noqa: E402

# --- IMPORTS HACK ---
from src.utils.logger import logger  # noqa: E402


def main():
    logger.info("🚀 Starting Simulation Loop Check...")

    # 1. Setup
    N_AGENTS = 1_000_000
    N_STEPS = 12

    # Инициализация (дадим людям денег, чтобы было что считать)
    state = GlobalState.empty(N_AGENTS)
    initial_income = jnp.ones(N_AGENTS) * 1000.0
    # Пусть 95% работают
    initial_employed = jax.random.bernoulli(jax.random.PRNGKey(0), p=0.95, shape=(N_AGENTS,))

    state = state.replace(
        agents=state.agents.replace(income=initial_income, is_employed=initial_employed)
    )

    kernel = SimulationKernel()
    key = jax.random.PRNGKey(42)  # Мастер-ключ случайности

    logger.info(f"Populated world with {N_AGENTS:,} agents.")
    logger.info("Starting time loop...")

    start_time = time.time()

    # --- TIME LOOP ---
    for t in range(N_STEPS):
        # Расщепляем ключ: один для шага, один на будущее
        step_key, key = jax.random.split(key)

        # ШАГ СИМУЛЯЦИИ
        state = kernel.step(state, step_key)

        # Барьер синхронизации (нужен только для точного замера времени)
        # В реальной жизни не обязателен на каждом шаге
        state.gdp.block_until_ready()

        # Логируем макро-показатели
        # Обрати внимание: state.gdp - это DeviceArray (на GPU/CPU),
        # при печати он вытягивается в Python (медленно), но для логов ок.
        logger.info(
            f"Step {t+1:02d} | GDP: {state.gdp/1e6:.2f}M | Unempl: {state.unemployment_rate:.2%}"
        )

    total_time = time.time() - start_time
    logger.success(f"✅ Simulation finished in {total_time:.4f}s")
    logger.info(
        f"Speed: {N_STEPS / total_time:.1f} steps/sec ({N_AGENTS * N_STEPS / total_time / 1e6:.1f}M agents-steps/sec)"
    )


if __name__ == "__main__":
    main()

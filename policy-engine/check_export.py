import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import uuid

# --- IMPORTS HACK ---
import jax_bootstrap  # noqa: F401
import jax  # noqa: E402
import jax.numpy as jnp  # noqa: E402

from polisyos.foundry.domain.state import GlobalState  # noqa: E402
from polisyos.foundry.engine.kernel import SimulationKernel  # noqa: E402
from polisyos.fabric.io.db import SimulationDB  # noqa: E402
from polisyos.common.logger import logger  # noqa: E402


def main():
    run_id = str(uuid.uuid4())[:8]  # Уникальный ID запуска
    logger.info(f"🎬 Starting Full Pipeline Check. RunID: {run_id}")

    # 1. Init DB
    db = SimulationDB()

    # 2. Init World (100k агентов для быстрого теста записи, миллион писать дольше)
    n_agents = 100_000
    state = GlobalState.empty(n_agents=n_agents, n_firms=100)

    # Даем деньги и работу
    state = state.replace(
        agents=state.agents.replace(
            income=jnp.ones(n_agents) * 1000.0, is_employed=jnp.ones(n_agents, dtype=bool)
        )
    )

    kernel = SimulationKernel()
    key = jax.random.PRNGKey(42)

    macro_buffer = []

    # 3. Run Loop
    for t in range(6):  # 6 месяцев
        step_key, key = jax.random.split(key)
        state = kernel.step(state, step_key)

        # Сбор макро-данных в буфер (Python list dicts)
        # item() превращает JAX-скаляр в Python float
        macro_buffer.append(
            {
                "run_id": run_id,
                "step": state.step.item(),
                "gdp": state.gdp.item(),
                "unemployment_rate": state.market.unemployment_rate.item(),
                "inflation_rate": 0.0,
                "avg_price": state.market.avg_price.item(),
                "avg_income": float(jnp.mean(state.agents.income)),
                "government_balance": state.government_balance.item(),
                "timestamp": None,  # DuckDB сам подставит current_timestamp
            }
        )

        # Сохраняем "Снимок" популяции только на 0-м и последнем шаге (чтобы не забить диск)
        if t == 0 or t == 5:
            db.save_agents(run_id, state.step.item(), state.agents)

    # 4. Flush to Disk
    db.save_macro(macro_buffer)

    # 5. Verify Data
    logger.info("🔍 Verifying data in DuckDB...")
    count = db.conn.execute(
        "SELECT count(*) FROM agents_snapshot WHERE run_id=?", [run_id]
    ).fetchone()[0]
    avg_unempl = db.conn.execute(
        "SELECT avg(unemployment_rate) FROM macro_history WHERE run_id=?", [run_id]
    ).fetchone()[0]

    logger.success(f"✅ Export Success! Total agent records: {count:,}")
    logger.info(f"📊 Average Unemployment in DB: {avg_unempl:.2%}")

    db.close()


if __name__ == "__main__":
    main()

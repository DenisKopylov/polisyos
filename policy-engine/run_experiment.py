import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import uuid

import jax_bootstrap  # noqa: F401
import jax
import jax.numpy as jnp

from polisyos.scientist.agent.base import MockAgent
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.engine.kernel import SimulationKernel
from polisyos.fabric.io.db import SimulationDB
from polisyos.scientist.orchestrator.run_record import build_run_record, save_run_record_json
from polisyos.scientist.orchestrator.compiler import compile_policy
from polisyos.ir.data_views import AccessTier, DataViewRequest
from polisyos.fabric.udf.engine import UDFEngine

# IMPORTS
from polisyos.common.logger import logger


def main():
    RUN_ID = str(uuid.uuid4())[:8]
    logger.info(f"🎬 Starting Experiment Loop. RunID: {RUN_ID}")

    # 1. Init System
    db = SimulationDB()
    udf = UDFEngine(db)
    agent = MockAgent()  # Пока используем заглушку

    run_record = build_run_record(run_id=RUN_ID, seed=42)
    db.save_run_record(run_record)
    save_run_record_json(run_record)

    # 2. Init World
    N_AGENTS = 1_000  # Меньше агентов для скорости экспериментов
    N_FIRMS = 50  # Фирмы для реальной экономики
    state = GlobalState.empty(N_AGENTS, N_FIRMS)

    # Инициализируем агентов
    is_employed = jax.random.bernoulli(jax.random.PRNGKey(0), p=0.50, shape=(N_AGENTS,))
    state = state.replace(
        agents=state.agents.replace(
            income=jnp.ones(N_AGENTS) * 1000.0,
            is_employed=is_employed,
            skill_level=jax.random.uniform(
                jax.random.PRNGKey(1), shape=(N_AGENTS,), minval=0.5, maxval=1.5
            ),
        )
    )

    # Создаем экономический движок
    kernel = SimulationKernel()

    # Save initial state
    unemployment = jnp.mean(~state.agents.is_employed).item()
    db.save_macro(
        [
            {
                "run_id": RUN_ID,
                "step": 0,
                "gdp": state.gdp,
                "unemployment_rate": unemployment,
                "inflation_rate": 0.0,
                "avg_price": state.market.avg_price,
                "avg_income": jnp.mean(state.agents.income).item(),
                "government_balance": state.government_balance,
                "timestamp": None,
            }
        ]
    )

    # 3. THE LOOP
    key = jax.random.PRNGKey(42)
    MAX_STEPS = 5

    for t in range(1, MAX_STEPS + 1):
        logger.info(f"\n--- STEP {t} ---")

        # A. PERCEPTION (Глаза)
        # Агент запрашивает последние данные
        req = DataViewRequest(
            request_id="context",
            run_id=RUN_ID,  # <--- ПЕРЕДАЕМ ID
            view_type="panel",
            metrics=["unemployment_rate", "gdp", "inflation_rate", "avg_price"],
            step_start=max(0, t - 3),  # Смотрим на 3 шага назад
            access_tier=AccessTier.PUBLIC,
        )
        context_df = udf.query(req)
        logger.info(f"📊 Context loaded:\n{context_df.tail(1)}")

        # B. DECISION (Мозг)
        policy_ir = agent.decide(step=t, context_df=context_df)
        logger.info(
            f"💡 Agent proposed: {policy_ir.interventions[0].mechanism_type} (Rate: {policy_ir.interventions[0].parameters['rate']})"
        )

        # C. COMPILATION (Руки)
        policy_model = compile_policy(policy_ir, n_agents=N_AGENTS, n_firms=N_FIRMS)

        # D. ACTION + ECONOMIC SIMULATION (Физика + Экономика)
        step_key, key = jax.random.split(key)

        # Сначала применяем политику агента
        state, _ = policy_model(state, step_key)

        # Затем запускаем полный экономический цикл (производство + рынки)
        step_key2, key = jax.random.split(key)
        state = kernel.step(state, step_key2)

        # E. PERSISTENCE (Память)
        # Сохраняем все новые макро-показатели
        inflation_rate = 0.0  # Для простоты - можно рассчитать как изменение цен
        if t > 1:
            # Простой расчет инфляции как изменение средней цены
            prev_price = (
                context_df["avg_price"].iloc[-1] if len(context_df) > 0 else state.market.avg_price
            )
            inflation_rate = (state.market.avg_price - prev_price) / prev_price * 100

        db.save_macro(
            [
                {
                    "run_id": RUN_ID,
                    "step": t,
                    "gdp": state.gdp,
                    "unemployment_rate": state.market.unemployment_rate,
                    "inflation_rate": inflation_rate,
                    "avg_price": state.market.avg_price,
                    "avg_income": jnp.mean(state.agents.income).item(),
                    "government_balance": state.government_balance,
                    "timestamp": None,
                }
            ]
        )

        logger.info(
            f"📈 Economy: GDP={state.gdp:.0f}, Unemployment={state.market.unemployment_rate:.1%}, Inflation={inflation_rate:.1f}%, Price={state.market.avg_price:.2f}"
        )

    logger.success("✅ Experiment Cycle Completed.")

    # Final check
    res = db.conn.execute(
        f"SELECT step, gdp, unemployment_rate, inflation_rate, avg_price FROM macro_history WHERE run_id='{RUN_ID}' ORDER BY step"
    ).fetchdf()
    print("\nFinal Economic Trajectory:")
    print(res)


if __name__ == "__main__":
    main()

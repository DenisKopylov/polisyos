import jax
import jax.numpy as jnp

from src.domain.state import GlobalState  # noqa: E402
from src.orchestrator.compiler import compile_policy
from src.policy_ir.contract import PolicyRequestIR
from src.policy_ir.types import TranslatableString

# IMPORTS HACK
from src.utils.logger import logger  # noqa: E402


def main():
    logger.info("🏭 Starting Policy Compiler Check...")

    # 1. Создаем IR (как будто получили от GPT-4)
    dummy_ir = PolicyRequestIR(
        project_name=TranslatableString(en="Test Reform", ua="Тест"),
        simulation_params={"scope_years": 1, "time_frequency": "M"},
        entities=[],
        objectives=[],
        interventions=[
            {
                "id": "tax_cut_2025",
                "name": {"en": "Tax Cut", "ua": "Знижка"},
                "target_selector": "all",
                "mechanism_type": "tax_subsidy",
                "parameters": {"rate": 0.15},  # 15% субсидия
            }
        ],
    )

    # 2. Компиляция
    N_AGENTS = 100
    try:
        policy_model = compile_policy(dummy_ir, n_agents=N_AGENTS)
        logger.success("✅ Compilation successful!")
    except Exception as e:
        logger.error(f"Compilation failed: {e}")
        return

    # 3. Инспекция скомпилированного объекта
    # CompositePolicy -> steps[0] -> TaxSubsidy
    first_mech = policy_model.steps[0]
    logger.info(f"Inspecting mechanism: {type(first_mech).__name__}")
    logger.info(f"Rate parameter: {first_mech.rate}")

    assert first_mech.rate == 0.15, "Parameter mismatch! JSON value lost."

    # 4. Пробный запуск (Execution)
    state = GlobalState.empty(N_AGENTS)
    # Дадим доход 1000
    state = state.replace(agents=state.agents.replace(income=jnp.ones(N_AGENTS) * 1000.0))

    logger.info("Running compiled policy...")
    # Запускаем!
    next_state = policy_model(state, jax.random.PRNGKey(0))

    # Проверка математики: 1000 + (1000 * 0.15) = 1150
    avg_income = jnp.mean(next_state.agents.income)
    logger.info(f"Average Income After Policy: {avg_income:.2f}")

    if jnp.isclose(avg_income, 1150.0):
        logger.success("✅ Execution Correct! JSON logic applied to JAX tensors.")
    else:
        logger.error(f"❌ Math mismatch. Expected 1150.0, got {avg_income}")


if __name__ == "__main__":
    main()

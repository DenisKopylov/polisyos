import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

# check_foundry.py
import jax_bootstrap  # noqa: F401
import equinox as eqx
import jax
import jax.numpy as jnp
from loguru import logger

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.fiscal import TaxSubsidy  # noqa: E402

# IMPORTS HACK


def main():
    logger.info("🧪 Starting Differentiable Policy Check...")

    # 0. Проверим backend
    logger.info(f"✅ JAX Backend: {jax.default_backend()}")

    # 1. Setup World
    N_AGENTS = 10
    state = GlobalState.empty(n_agents=N_AGENTS, n_firms=2)
    state = state.replace(agents=state.agents.replace(income=jnp.ones(N_AGENTS) * 100.0))

    # 2. Инициализируем Политику
    # Ставка 10% (0.10)
    policy = TaxSubsidy(rate=0.10, n_agents=N_AGENTS)

    logger.info(".2%")

    # 3. Описываем Функцию Потерь (Loss Function)
    # Наша цель: Максимизировать GDP.
    # Но градиентный спуск ищет МИНИМУМ. Поэтому мы минимизируем (-GDP).

    def loss_function(policy_model, current_state):
        # Применяем политику (Шаг симуляции)
        # key нам тут не важен, так как детерминированная логика
        next_state, _ = policy_model(current_state, jax.random.PRNGKey(0))
        new_income = next_state.agents.income

        # Считаем GDP
        total_gdp = jnp.sum(new_income)

        # Возвращаем минус GDP (чтобы градиент показывал рост)
        return -total_gdp

    # 4. Вычисляем Градиент (Magic Step)
    # eqx.filter_grad говорит JAX'у: "Найди производную loss_function по параметрам внутри policy_model"
    grad_func = eqx.filter_jit(eqx.filter_grad(loss_function))

    grads = grad_func(policy, state)

    # 5. Анализ результата
    # grads теперь имеет ту же структуру, что и policy, но вместо значений там производные
    rate_grad = grads.rate

    logger.info(f"Calculated Gradient (dGDP / dRate): {rate_grad}")

    # Интерпретация:
    # Loss = -GDP.
    # Если grad = -1000, значит при росте rate на +1, Loss упадет на 1000 (GDP вырастет на 1000).
    # У нас 10 агентов с доходом 100. Исходный GDP = 1000.
    # Если rate +1.0 (100%), GDP вырастет на 1000.
    # Ожидаемый градиент для Loss: -1000.0

    if jnp.isclose(rate_grad, -1000.0):
        logger.success("✅ Gradient is CORRECT! Auto-differentiation works.")
        logger.info("🚀 We can now OPTIMIZE laws using AI.")
    else:
        logger.error(f"❌ Gradient mismatch. Expected -1000.0, got {rate_grad}")


if __name__ == "__main__":
    main()

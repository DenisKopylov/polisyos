# ruff: noqa: E402

import sys
from pathlib import Path
from typing import Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import os
import time

# На некоторых macOS окружениях (JAX+Metal) возможны ошибки runtime.
# Для воспроизводимости демо предпочитаем CPU, если пользователь явно не выбрал платформу.
os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")

import equinox as eqx
import jax
import jax.numpy as jnp
import optax

from polisyos.foundry.agents import AgentPolicy

try:
    import jax_bootstrap  # noqa: F401
except ModuleNotFoundError:
    # `jax_bootstrap` используется в некоторых окружениях (например, macOS+Metal)
    # для дополнительной инициализации JAX. Для самого демо он не обязателен.
    pass

# --- КОНФИГУРАЦИЯ ---
N_AGENTS = 10_000  # Масштаб: 10k агентов
LEARNING_RATE = 0.05  # Скорость обучения агентов
ITERATIONS = 200  # Количество шагов обучения на каждую налоговую ставку
TAX_RATES = [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
SEED = 42
RISK_PENALTY_COEF = 1.0  # Тюнинг: при 2.0 почти все всегда "честные"


def create_population(key: jax.Array, n: int) -> Tuple[jnp.ndarray, jnp.ndarray]:
    """Генерирует популяцию: Лог-нормальные доходы и Равномерный риск."""
    k1, k2 = jax.random.split(key)
    # Доходы: log-normal distribution (реалистичное распределение богатства)
    incomes = jnp.exp(jax.random.normal(k1, (n,)) * 0.5 + 3.0)
    # Риск: от 0.0 (рисковый) до 1.0 (осторожный)
    risk_aversion = jax.random.uniform(k2, (n,))
    return incomes, risk_aversion


def loss_fn(
    policy_static: AgentPolicy,
    params,
    observations: jnp.ndarray,
    incomes: jnp.ndarray,
    risk_aversion: jnp.ndarray,
    tax_rate: jnp.ndarray,
) -> jnp.ndarray:
    """
    Функция потерь: Минус Полезность (Utility).
    Utility = (Доход - Налог) - (Штраф за риск * Скрытый доход)
    """
    model = eqx.combine(params, policy_static)
    logits = model(observations)
    declared_fraction = jax.nn.sigmoid(logits).reshape(-1)

    tax_paid = incomes * declared_fraction * tax_rate
    hidden_income = incomes * (1.0 - declared_fraction)
    disposable_income = incomes - tax_paid

    # Чем выше risk_aversion, тем "дороже" для агента скрывать доход
    risk_penalty = risk_aversion * hidden_income * RISK_PENALTY_COEF

    utility = disposable_income - risk_penalty

    # Регуляризация энтропии (чтобы агенты не "застревали" слишком рано)
    probs = jnp.clip(declared_fraction, 1e-5, 1 - 1e-5)
    entropy = -(probs * jnp.log(probs) + (1 - probs) * jnp.log(1 - probs))

    # Максимизируем Utility -> Минимизируем Negative Utility
    return -jnp.mean(utility) - 0.01 * jnp.mean(entropy)


@eqx.filter_jit
def train_step(
    policy_static: AgentPolicy,
    params,
    opt_state,
    optimizer: optax.GradientTransformation,
    incomes: jnp.ndarray,
    risk_aversion: jnp.ndarray,
    tax_rate: jnp.ndarray,
):
    """Один шаг градиентного спуска (JIT-compiled)."""
    norm_incomes = jnp.log1p(incomes)
    tax_vec = jnp.full_like(incomes, tax_rate)
    observations = jnp.stack([norm_incomes, risk_aversion, tax_vec], axis=1)

    grads = jax.grad(loss_fn, argnums=1)(
        policy_static, params, observations, incomes, risk_aversion, tax_rate
    )

    updates, new_opt_state = optimizer.update(grads, opt_state, params)
    new_params = eqx.apply_updates(params, updates)
    return new_params, new_opt_state


def evaluate(
    policy_static: AgentPolicy,
    params,
    incomes: jnp.ndarray,
    risk_aversion: jnp.ndarray,
    tax_rate: jnp.ndarray,
):
    """Оценка текущего состояния экономики."""
    norm_incomes = jnp.log1p(incomes)
    tax_vec = jnp.full_like(incomes, tax_rate)
    observations = jnp.stack([norm_incomes, risk_aversion, tax_vec], axis=1)

    model = eqx.combine(params, policy_static)
    logits = model(observations)
    declared_fraction = jax.nn.sigmoid(logits).reshape(-1)

    total_tax_revenue = jnp.sum(incomes * declared_fraction * tax_rate)
    avg_compliance = jnp.mean(declared_fraction)
    # При крайних режимах (все ~1.0 или все ~0.0) корреляция может стать NaN из-за нулевой дисперсии.
    x = risk_aversion - jnp.mean(risk_aversion)
    y = declared_fraction - jnp.mean(declared_fraction)
    denom = jnp.std(x) * jnp.std(y)
    corr = jnp.where(denom > 1e-8, jnp.mean(x * y) / denom, jnp.array(0.0, dtype=jnp.float32))

    return total_tax_revenue, avg_compliance, corr


def main() -> None:
    print(f"=== ЗАПУСК LAFFER CURVE DEMO (N={N_AGENTS}) ===")
    key = jax.random.PRNGKey(SEED)

    # 1. Генерация популяции
    key, subkey = jax.random.split(key)
    incomes, risk_aversion = create_population(subkey, N_AGENTS)
    print(f"Популяция создана. Total Income: {jnp.sum(incomes):.2f}")

    # 2. Инициализация политики (MLP)
    key, subkey = jax.random.split(key)
    policy = AgentPolicy(
        subkey,
        in_dim=3,
        action_type="continuous",
        out_dim=1,
        hidden_layers=[64, 64],
    )
    params = eqx.filter(policy, eqx.is_inexact_array)
    policy_static = eqx.filter(policy, eqx.is_inexact_array, inverse=True)

    optimizer = optax.adam(LEARNING_RATE)
    initial_params = params
    opt_state = optimizer.init(initial_params)

    results: list[tuple[float, jnp.ndarray, jnp.ndarray, jnp.ndarray]] = []

    start_time = time.time()

    # 3. Цикл по налоговым ставкам (Sweep)
    print(f"\n{'TAX RATE':<10} | {'REVENUE':<15} | {'COMPLIANCE':<12} | {'RISK CORR':<10}")
    print("-" * 55)

    for tax in TAX_RATES:
        tax_rate = jnp.array(tax, dtype=jnp.float32)

        # Для "чистого" sweep: начинаем обучение с одинаковых весов на каждой ставке.
        params = initial_params
        opt_state = optimizer.init(params)

        for _ in range(ITERATIONS):
            params, opt_state = train_step(
                policy_static, params, opt_state, optimizer, incomes, risk_aversion, tax_rate
            )

        revenue, compliance, corr = evaluate(
            policy_static, params, incomes, risk_aversion, tax_rate
        )
        # Синхронизация для корректного измерения времени
        revenue.block_until_ready()

        results.append((tax, revenue, compliance, corr))
        print(f"{tax*100:5.0f}%     | {revenue:15.2f} | {compliance*100:11.1f}% | {corr:9.3f}")

    total_time = time.time() - start_time
    print("-" * 55)
    print(
        f"Симуляция завершена за {total_time:.2f} сек ({total_time/len(TAX_RATES):.2f} сек/ставка)"
    )

    # 4. Анализ Кривой Лаффера
    revenues = [r[1] for r in results]
    max_rev_idx = int(jnp.argmax(jnp.array(revenues)))
    peak_tax = results[max_rev_idx][0]

    print("\nИТОГ:")
    print(f"Пик доходов достигнут при ставке: {peak_tax*100:.0f}%")
    if 0.1 < peak_tax < 0.9:
        print("✅ Эффект Кривой Лаффера подтвержден (пик в середине).")
    else:
        print("⚠️ Кривая Лаффера не явная (возможно, штрафы слишком мягкие или жесткие).")

    print(
        f"Гетерогенность агентов (корреляция риска): {results[max_rev_idx][3]:.3f} (Ожидается > 0.2)"
    )


if __name__ == "__main__":
    main()


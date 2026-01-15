# polisyos/orchestrator/optimizer.py
from typing import List

import jax
import jax.numpy as jnp
import optax

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.base import Mechanism
from polisyos.foundry.executor import apply_patch_map
from polisyos.foundry.loss import policy_loss_fn
from polisyos.foundry.utils import gradient_health_report
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def optimize_mechanisms(
    mechanisms: List[Mechanism],
    initial_state: GlobalState,
    key: jax.Array,
    steps: int = 100,
    learning_rate: float = 0.05,
    min_balance: float = -1000.0,
    debug_mode: bool = False,
    clip_grad_norm: float | None = None,
) -> List[Mechanism]:
    """
    Запускает градиентный спуск для настройки параметров механизмов.
    """
    print(f"   [Optimizer] Starting auto-tuning for {steps} steps...")

    # Для MVP оптимизируем только rate в TaxSubsidy
    # В будущем можно расширить на все механизмы

    # Извлекаем текущие параметры
    current_rates = []
    for mech in mechanisms:
        if hasattr(mech, "rate"):
            current_rates.append(float(mech.rate))
        else:
            current_rates.append(0.0)  # Заглушка для других механизмов

    # Конвертируем в JAX массив для оптимизации
    rates_array = jnp.array(current_rates)

    # 1. Настройка оптимизатора (Adam)
    if clip_grad_norm is None:
        optimizer = optax.adam(learning_rate)
    else:
        optimizer = optax.chain(
            optax.clip_by_global_norm(clip_grad_norm),
            optax.adam(learning_rate),
        )
    opt_state = optimizer.init(rates_array)

    # 2. Функция шага (JIT-компилируемая)
    def loss_wrapper(rates_param, state_key):
        modified_mechanisms = []
        for i, mech in enumerate(mechanisms):
            if hasattr(mech, "rate"):
                new_rate = rates_param[i]
                if mech.__class__.__name__ == "TaxSubsidy":
                    from polisyos.foundry.fiscal import TaxSubsidy

                    new_mech = TaxSubsidy(rate=new_rate, n_agents=len(initial_state.agents.age))
                else:
                    new_mech = mech
            else:
                new_mech = mech
            modified_mechanisms.append(new_mech)

        curr_state = initial_state
        curr_key = state_key
        for idx, m in enumerate(modified_mechanisms):
            curr_key, step_key = jax.random.split(curr_key)
            patches, next_key = m.emit_patches(curr_state, step_key)
            curr_state = apply_patch_map(
                curr_state,
                patches,
                slot_registry=DEFAULT_SLOT_REGISTRY,
                merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
                default_node_id=f"mech_{idx}",
            )
            curr_key = next_key
        return policy_loss_fn(curr_state, min_balance)

    @jax.jit
    def step_fn(rates, opt_state, state_key):
        loss_val, grads = jax.value_and_grad(loss_wrapper)(rates, state_key)
        updates, new_opt_state = optimizer.update(grads, opt_state, rates)
        new_rates = optax.apply_updates(rates, updates)
        return new_rates, new_opt_state, loss_val

    # 3. Цикл оптимизации
    current_rates = rates_array
    for i in range(steps):
        if debug_mode:
            loss_val, grads = jax.value_and_grad(loss_wrapper)(current_rates, key)
            if clip_grad_norm is None:
                report, clipped_grads = gradient_health_report(grads, clip_norm=None)
                updates, opt_state = optimizer.update(clipped_grads, opt_state, current_rates)
            else:
                report, _ = gradient_health_report(grads, clip_norm=clip_grad_norm)
                updates, opt_state = optimizer.update(grads, opt_state, current_rates)
            current_rates = optax.apply_updates(current_rates, updates)
            if i % 20 == 0:
                print(
                    f"     Step {i}: Loss = {loss_val:.4f} | "
                    f"GradNorm = {report.grad_norm:.4f} | "
                    f"Clipped = {report.clipped}"
                )
        else:
            current_rates, opt_state, loss = step_fn(current_rates, opt_state, key)
            if i % 20 == 0:
                print(f"     Step {i}: Loss = {loss:.4f}")

    print("   [Optimizer] Tuning complete.")

    # 4. Создаем новые механизмы с оптимизированными параметрами
    optimized_rates = current_rates
    optimized_mechanisms = []
    for i, mech in enumerate(mechanisms):
        if hasattr(mech, "rate"):
            # Создаем новый механизм с оптимизированным rate
            if mech.__class__.__name__ == "TaxSubsidy":
                from polisyos.foundry.fiscal import TaxSubsidy

                new_mech = TaxSubsidy(
                    rate=float(optimized_rates[i]), n_agents=len(initial_state.agents.age)
                )
            else:
                new_mech = mech  # Для других механизмов оставляем как есть
        else:
            new_mech = mech
        optimized_mechanisms.append(new_mech)

    return optimized_mechanisms

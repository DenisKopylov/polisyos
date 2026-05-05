from __future__ import annotations

import jax.numpy as jnp
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.methods.loss import policy_loss_fn


def test_policy_loss_fn_normalizes_scale_and_remains_finite() -> None:
    state = GlobalState.empty(n_agents=3, n_firms=1).replace(
        agents=GlobalState.empty(n_agents=3, n_firms=1).agents.replace(
            income=jnp.array([1000.0, 2000.0, 3000.0], dtype=jnp.float32),
        ),
        government_balance=jnp.array(-500.0, dtype=jnp.float32),
    )

    loss = policy_loss_fn(state, min_balance=-1000.0)
    assert jnp.isfinite(loss)


def test_policy_loss_fn_fails_closed_on_non_finite_inputs() -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1).replace(
        agents=GlobalState.empty(n_agents=2, n_firms=1).agents.replace(
            income=jnp.array([1.0, jnp.nan], dtype=jnp.float32),
        ),
    )

    assert jnp.isinf(policy_loss_fn(state))

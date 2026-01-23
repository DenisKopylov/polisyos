from __future__ import annotations

from typing import Callable, Iterable

import chex
import equinox as eqx
import jax
import jax.numpy as jnp
from jaxtyping import Array, Float

from polisyos.foundry.agent_sim.state import AgentState, PolicyState


class MLP(eqx.Module):
    layers: tuple[eqx.nn.Linear, ...]
    activation: Callable[[jnp.ndarray], jnp.ndarray] = eqx.field(static=True)

    def __call__(self, x: jnp.ndarray) -> jnp.ndarray:
        if x.ndim == 1:
            return self._forward_single(x)
        if x.ndim == 2:
            return jax.vmap(self._forward_single)(x)
        raise ValueError(f"MLP expects ndim 1 or 2, got shape={x.shape!r}")

    def _forward_single(self, x: jnp.ndarray) -> jnp.ndarray:
        out = x
        for layer in self.layers[:-1]:
            out = self.activation(layer(out))
        return self.layers[-1](out) if self.layers else out


class SharedPolicy(eqx.Module):
    network: MLP

    def __init__(
        self,
        obs_dim: int,
        action_dim: int,
        hidden_dims: Iterable[int],
        *,
        key: jax.Array,
        activation: str = "relu",
    ):
        dims = [int(obs_dim)] + [int(h) for h in hidden_dims] + [int(action_dim)]
        keys = jax.random.split(key, max(len(dims) - 1, 1))
        layers = tuple(
            eqx.nn.Linear(dims[i], dims[i + 1], key=keys[i]) for i in range(len(dims) - 1)
        )
        act = jax.nn.relu if activation == "relu" else jax.nn.tanh
        self.network = MLP(layers=layers, activation=act)

    def __call__(
        self,
        observations: Float[Array, "n_agents obs_dim"],
        rng_key: chex.PRNGKey | None = None,
    ) -> Float[Array, "n_agents action_dim"]:
        del rng_key
        return self.network(observations)


def build_observations(
    agents: AgentState,
    policy: PolicyState,
    time_step: int | jnp.ndarray,
    *,
    steps_per_year: int = 12,
) -> Float[Array, "n_agents obs_dim"]:
    n_agents = agents.wealth.shape[0]
    age_years = agents.age.astype(jnp.float32) / float(steps_per_year)

    agent_features = jnp.stack(
        [
            agents.wealth,
            agents.income,
            agents.risk_aversion,
            agents.discount_factor,
            agents.skill_level,
            age_years,
        ],
        axis=-1,
    )

    time_val = jnp.asarray(time_step, dtype=jnp.float32)
    seasonal_sin = jnp.sin(2.0 * jnp.pi * time_val / 12.0)
    seasonal_cos = jnp.cos(2.0 * jnp.pi * time_val / 12.0)
    global_features = jnp.stack(
        [
            policy.tax_rate,
            policy.interest_rate,
            seasonal_sin,
            seasonal_cos,
        ],
        axis=0,
    )
    global_features = jnp.broadcast_to(global_features, (n_agents, global_features.shape[0]))

    return jnp.concatenate([agent_features, global_features], axis=-1)

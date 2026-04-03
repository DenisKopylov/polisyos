"""Train macro-policy controllers that react to global simulation observations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import equinox as eqx
import jax
import jax.numpy as jnp
import optax

from polisyos.foundry.agent_sim.actor_critic import ActorCritic, NormalizedMLP
from polisyos.foundry.agent_sim.credit_assignment import CentralizedCritic
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.state import GlobalState, PolicyState


class GovernmentPolicy(eqx.Module):
    """Map global simulation observations into bounded fiscal-policy controls."""
    network: NormalizedMLP
    output_bounds: dict[str, tuple[float, float]]

    def __init__(
        self,
        key: jax.Array,
        *,
        obs_dim: int = 12,
        hidden_dims: tuple[int, ...] = (64, 64),
        output_bounds: dict[str, tuple[float, float]] | None = None,
    ):
        if output_bounds is None:
            output_bounds = {
                "tax_rate": (0.0, 0.5),
                "transfer_rate": (0.0, 0.3),
                "interest_rate": (0.0, 0.2),
            }

        self.output_bounds = dict(output_bounds)
        n_outputs = len(self.output_bounds)
        dims = (int(obs_dim),) + tuple(int(d) for d in hidden_dims) + (int(n_outputs),)
        keys = jax.random.split(key, len(dims) - 1)
        layers = tuple(
            eqx.nn.Linear(dims[i], dims[i + 1], key=keys[i])
            for i in range(len(dims) - 1)
        )
        norms = tuple(
            eqx.nn.LayerNorm(dim, elementwise_affine=True) for dim in dims[1:-1]
        )
        self.network = NormalizedMLP(layers=layers, norms=norms, activation=jax.nn.gelu)

    def __call__(self, global_obs: jnp.ndarray) -> PolicyState:
        raw_output = self.network(global_obs)
        outputs: dict[str, jnp.ndarray] = {}
        for i, (name, (low, high)) in enumerate(self.output_bounds.items()):
            scaled = low + (high - low) * jax.nn.sigmoid(raw_output[i])
            outputs[name] = scaled

        tax_rate = outputs.get("tax_rate", jnp.array(0.0))
        transfer_rate = outputs.get("transfer_rate", jnp.array(0.0))
        interest_rate = outputs.get("interest_rate", jnp.array(0.01))

        return PolicyState(
            tax_rate=tax_rate,
            transfer_rate=transfer_rate,
            interest_rate=interest_rate,
            expected_interest_rate=interest_rate,
        )


@dataclass(frozen=True)
class GovernmentTrainingConfig:
    """Set episode length, optimizer settings, and welfare weights for government training."""
    n_episodes: int = 100
    steps_per_episode: int = 256
    learning_rate: float = 1e-3
    gamma: float = 0.99
    policy_update_frequency: int = 1
    welfare_weights: dict | None = None


def train_government_policy(
    gov_policy: GovernmentPolicy,
    agent_policy: ActorCritic,
    make_executor: Callable[[ActorCritic], PureExecutor],
    initial_state: GlobalState,
    config: GovernmentTrainingConfig,
    rng_key: jax.Array,
) -> tuple[GovernmentPolicy, dict]:
    """Optimize a government controller against simulated welfare trajectories."""
    params, static = eqx.partition(gov_policy, eqx.is_inexact_array)
    optimizer = optax.adam(config.learning_rate)
    opt_state = optimizer.init(params)

    welfare_weights = config.welfare_weights or {"gdp": 1.0, "neg_gini": 0.5}

    def welfare_reward(state: GlobalState) -> jnp.ndarray:
        total = jnp.array(0.0, dtype=jnp.float32)
        total = total + welfare_weights.get("gdp", 0.0) * state.aggregates.total_wealth
        total = total - welfare_weights.get("neg_gini", 0.0) * state.distributions.gini_wealth
        total = total + welfare_weights.get("bottom_50_share", 0.0) * state.distributions.bottom_50_share
        return total

    @jax.jit
    def episode_loss(gov_params, key):
        gov = eqx.combine(static, gov_params)
        executor = make_executor(agent_policy)

        def step_fn(carry, _):
            state, rng, cumulative = carry
            key1, key2 = jax.random.split(rng)

            global_obs = CentralizedCritic.build_global_observations(state)
            new_policy = gov(global_obs)
            state = state.replace(policy=new_policy)

            next_state, _ = executor.step(state)
            reward = welfare_reward(next_state)
            cumulative = cumulative + config.gamma ** state.time_step * reward
            return (next_state, key2, cumulative), reward

        init_carry = (initial_state, key, jnp.array(0.0, dtype=jnp.float32))
        (_, _, total_reward), _ = jax.lax.scan(
            step_fn,
            init_carry,
            None,
            length=int(config.steps_per_episode),
        )
        return -total_reward

    @jax.jit
    def update_step(gov_params, opt_state, key):
        loss, grads = jax.value_and_grad(episode_loss)(gov_params, key)
        updates, new_opt_state = optimizer.update(grads, opt_state, gov_params)
        new_params = optax.apply_updates(gov_params, updates)
        return new_params, new_opt_state, loss

    loss_history = []
    for _ in range(int(config.n_episodes)):
        rng_key, step_key = jax.random.split(rng_key)
        params, opt_state, loss = update_step(params, opt_state, step_key)
        loss_history.append(float(loss))

    trained = eqx.combine(static, params)
    metrics = {
        "loss_history": loss_history,
        "final_welfare": -loss_history[-1] if loss_history else 0.0,
    }
    return trained, metrics

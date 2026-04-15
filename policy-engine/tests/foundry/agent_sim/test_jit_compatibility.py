from __future__ import annotations

import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.analysis import BehaviorAnalyzer
from polisyos.foundry.agent_sim.distributions import DistributionConfig
from polisyos.foundry.agent_sim.executor import PureExecutor
from polisyos.foundry.agent_sim.graph_executor import GraphAwareExecutor
from polisyos.foundry.agent_sim.mechanism import Mechanism, MechanismSpec
from polisyos.foundry.agent_sim.mpc import HybridPlanner, MPCPlanner
from polisyos.foundry.agent_sim.population import (
    LifecycleConfig,
    PopulationConfig,
    batch_create_agents,
)
from polisyos.foundry.agent_sim.state import GlobalState
from polisyos.foundry.agent_sim.population_executor import PopulationAwareExecutor
from polisyos.foundry.agent_sim.temporal import build_temporal_observations
from polisyos.foundry.contracts.fidelity import FidelityLevel


class _NoOpMechanism(Mechanism):
    def __init__(self, name: str = "noop") -> None:
        self._spec = MechanismSpec(
            name=name,
            reads=frozenset(),
            writes=frozenset(),
            parameters={},
            stochastic=False,
        )

    @property
    def spec(self):
        return self._spec

    def apply(self, state, rng_key, fidelity):
        del rng_key, fidelity
        return state, {}


def test_graph_aware_executor_run_is_jit_safe(simple_state) -> None:
    executor = GraphAwareExecutor(
        [_NoOpMechanism()],
        distribution_config=DistributionConfig(update_frequency=1),
        graph_update_frequency=1,
    )

    final_state, metrics = executor.run(simple_state, 1, FidelityLevel.SURROGATE_FLUID)

    assert int(final_state.time_step) == int(simple_state.time_step) + 1
    assert "graph_density" in metrics


def test_population_aware_executor_run_is_jit_safe(simple_state) -> None:
    executor = PopulationAwareExecutor(
        [_NoOpMechanism()],
        lifecycle_config=LifecycleConfig(),
        distribution_config=DistributionConfig(update_frequency=1),
        lifecycle_frequency=1,
        graph_update_frequency=0,
    )

    final_state, metrics = executor.run(simple_state, 1, FidelityLevel.SURROGATE_FLUID)

    assert int(final_state.time_step) == int(simple_state.time_step) + 1
    assert "population/n_active" in metrics


def test_mpc_planner_preserves_eager_wrapper_and_supports_jit(simple_state) -> None:
    planner = MPCPlanner(simulator=PureExecutor([_NoOpMechanism()]), horizon=2, n_samples=2)
    candidates = jnp.zeros((3, 1), dtype=jnp.float32)

    eager_idx = planner.plan(simple_state, 0, candidates, jax.random.PRNGKey(0))
    compiled_idx = jax.jit(lambda state, actions, key: planner.plan(state, 0, actions, key))(
        simple_state,
        candidates,
        jax.random.PRNGKey(1),
    )

    assert isinstance(eager_idx, int)
    assert compiled_idx.shape == ()
    assert int(compiled_idx) in {0, 1, 2}


def test_hybrid_planner_uses_tracer_safe_mpc_path(simple_state) -> None:
    obs_dim = build_temporal_observations(simple_state, horizon=2).shape[-1]
    actor_critic = ActorCritic(obs_dim=obs_dim, action_dim=1, hidden_dims=[8], key=jax.random.PRNGKey(42))
    planner = HybridPlanner(
        actor_critic=actor_critic,
        mpc_planner=MPCPlanner(simulator=PureExecutor([_NoOpMechanism()]), horizon=2, n_samples=2),
        mpc_threshold=-1.0,
    )

    action = jax.jit(lambda state, key: planner.get_action(state, 0, key))(
        simple_state,
        jax.random.PRNGKey(7),
    )

    assert action.shape == (1,)


def test_batch_create_agents_vectorized_path_is_jit_safe() -> None:
    state = GlobalState.empty(n_agents=4, max_agents=8, seed=0)
    parent_indices = jnp.full((3,), -1, dtype=jnp.int32)

    created = jax.jit(
        lambda current_state, key: batch_create_agents(
            current_state,
            n_new=3,
            parent_indices=parent_indices,
            rng_key=key,
            config=PopulationConfig(),
            n_requested=jnp.array(3, dtype=jnp.int32),
        )
    )(state, jax.random.PRNGKey(9))

    assert int(jnp.sum(created.agents.active)) == 7
    assert int(created.population_manager.n_active) == 7


def test_mobility_matrix_vectorized_path_is_jit_safe() -> None:
    initial = GlobalState.empty(n_agents=8, seed=0)
    final = initial.replace(
        agents=initial.agents.replace(
            wealth=initial.agents.wealth + jnp.linspace(0.0, 1.0, 8, dtype=jnp.float32)
        )
    )

    matrix = jax.jit(
        lambda before, after: BehaviorAnalyzer.compute_mobility_matrix(
            before,
            after,
            n_quantiles=4,
        )
    )(initial, final)

    assert matrix.shape == (4, 4)
    assert bool(jnp.all(jnp.isfinite(matrix)))

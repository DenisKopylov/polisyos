"""The real Economics/PPO producer reaches a declared classical-Gini refusal."""

from __future__ import annotations

import equinox as eqx
import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.agent_sim.actor_critic import ActorCritic
from polisyos.foundry.agent_sim.jit_training import (
    JITTrainingConfig,
    create_jit_trainer_with_metrics,
)
from polisyos.foundry.agent_sim.metrics import MetricsCollector, standard_training_metrics
from polisyos.foundry.agent_sim.temporal_mechanisms import TemporalConsumptionMechanism
from polisyos.foundry.agent_sim.training import TrainingConfig, collect_trajectory
from polisyos.foundry.contracts.fidelity import FidelityLevel
from polisyos.foundry.plugins.composite import (
    CompositeExecutor,
    CompositeState,
    CompositeStateConfig,
)
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.economics import EconomicsPlugin
from polisyos.foundry.plugins.training_adapter import (
    EconomicsTrainingAdapter,
    _native_to_composite,
)


def _profile(monkeypatch, *, wealth=0.0, inactive_padding=False):
    monkeypatch.setattr(PluginRegistry, "_instance", None)
    registry = PluginRegistry()
    registry.register(EconomicsPlugin())
    config = CompositeStateConfig(
        domains={"economics": DomainConfig(n_agents=10, max_agents=10, time_horizon=4)},
        global_seed=31,
    )
    composite = CompositeState.create(config, registry)
    domain = composite.get_domain("economics")
    active = jnp.ones(10, dtype=jnp.bool_)
    values = jnp.full((10,), wealth, dtype=jnp.float32)
    if inactive_padding:
        active = active.at[-1].set(False)
        values = values.at[-1].set(-1e6)
    domain = domain.replace(
        agents=domain.agents.replace(
            active=active,
            wealth=values,
            income=jnp.zeros(10, dtype=jnp.float32),
            wage=jnp.full((10,), 30.0, dtype=jnp.float32),
            skill_level=jnp.full((10,), 2.0, dtype=jnp.float32),
            employed=jnp.ones(10, dtype=jnp.bool_),
        ),
        policy=domain.policy.replace(
            transfer_rate=jnp.asarray(0.0, dtype=jnp.float32),
            unemployment_benefit=jnp.asarray(0.0, dtype=jnp.float32),
            minimum_wage=jnp.asarray(0.0, dtype=jnp.float32),
            interest_rate=jnp.asarray(0.0, dtype=jnp.float32),
        ),
    )
    composite = composite.update_domain("economics", domain.update_aggregates())
    adapter = EconomicsTrainingAdapter.from_composite(
        composite, CompositeExecutor(["economics"], registry)
    )
    assert adapter is not None
    config = TrainingConfig(
        n_episodes=1, steps_per_episode=1, ppo_epochs=1, horizon=4, include_expectations=False
    )
    actor = ActorCritic(jax.random.PRNGKey(4), adapter.observation_dim(config), hidden_dims=(8, 4))
    native = adapter.to_native_state(seed=19)
    executor = adapter.make_executor(actor, config)
    return adapter, config, actor, native, executor


def test_real_policy_then_registered_tax_produces_signed_wealth_without_law_change(monkeypatch):
    with jax.enable_x64(False):
        adapter, _, _, native, executor = _profile(monkeypatch)
        seam = executor.mechanisms[0]
        key = jax.random.PRNGKey(7)
        policy_state, _ = TemporalConsumptionMechanism.apply(
            seam, native, key, FidelityLevel.HARD_DISCRETE
        )
        domain = _native_to_composite(
            policy_state,
            config=seam._bridge_config,
            n_agents=10,
            max_agents=10,
            wage_growth_rate=adapter.wage_growth_rate,
        ).get_domain("economics")
        # Replay the actual CompositeExecutor mechanism order and PRNG splits,
        # stopping before its requested distribution refresh, not before laws.
        _, bridge_key = jax.random.split(key)
        _, domain_key = jax.random.split(bridge_key)
        enabled = set(seam._bridge_config.domains["economics"].enabled_mechanisms)
        applied = []
        for mechanism in seam._bridge_executor.registry.get("economics").get_mechanisms():
            if mechanism.name not in enabled:
                continue
            domain_key, mechanism_key = jax.random.split(domain_key)
            domain = mechanism.apply(domain, rng_key=mechanism_key)
            applied.append(mechanism.name)
        assert applied == ["labor_market", "taxation", "transfers", "savings"]
        assert np.all(np.asarray(domain.agents.income) > 0)
        assert np.all(np.asarray(domain.agents.wealth) < 0)
        # All realized wages are below the first bracket ceiling: tax is 10%
        # of income; zero transfers and interest leave that debit unchanged.
        np.testing.assert_allclose(domain.agents.wealth, -0.1 * domain.agents.income)
        with pytest.raises(ValueError, match="finite nonnegative active values"):
            jax.block_until_ready(domain.update_aggregates())


@pytest.mark.parametrize("route", ["bridge", "metric_enabled_ppo"])
def test_actual_bridge_and_ppo_refuse_signed_metric_before_publication(monkeypatch, route):
    with jax.enable_x64(False):
        adapter, config, actor, native, executor = _profile(monkeypatch)
        if route == "bridge":
            invoke = lambda: executor.step(native, fidelity=FidelityLevel.HARD_DISCRETE)
        else:
            trainer = create_jit_trainer_with_metrics(
                actor,
                lambda current: adapter.make_executor(current, config),
                native,
                JITTrainingConfig(**config.common_kwargs()),
            )
            invoke = lambda: trainer(jax.random.PRNGKey(19))
        with pytest.raises(
            Exception, match="classical Gini requires finite nonnegative active values"
        ):
            jax.block_until_ready(invoke())


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
def test_signed_ppo_without_metric_is_preserved_but_real_current_metric_refuses(
    monkeypatch, compiled
):
    with jax.enable_x64(False):
        _, config, actor, native, executor = _profile(monkeypatch)
        # A genuine scan can eliminate an unrequested cached distribution.
        # Signed simulation remains supported without a requested Gini metric.
        trajectory = jax.block_until_ready(collect_trajectory(executor, native, actor, config))
        assert np.isfinite(np.asarray(trajectory.rewards)).all()
        result, _ = jax.jit(lambda state: executor.step(state, fidelity=config.fidelity))(native)
        assert np.all(np.asarray(result.agents.wealth) < 0)
        collector = MetricsCollector(standard_training_metrics(), max_history=2)
        collect = lambda state: collector.collect(state)
        if compiled:
            collect = eqx.filter_jit(collect)
        with pytest.raises(
            Exception, match="classical Gini requires finite nonnegative active values"
        ):
            jax.block_until_ready(collect(result))


@pytest.mark.parametrize("inactive_padding", [False, True])
def test_same_real_ppo_route_admits_nonnegative_active_population(monkeypatch, inactive_padding):
    with jax.enable_x64(False):
        _, config, actor, native, executor = _profile(
            monkeypatch, wealth=1000.0, inactive_padding=inactive_padding
        )
        trajectory = jax.block_until_ready(collect_trajectory(executor, native, actor, config))
        assert trajectory.rewards.shape == (1, 10)
        assert np.isfinite(np.asarray(trajectory.rewards)).all()
        np.testing.assert_array_equal(trajectory.active_mask[0], native.agents.active)
        result, _ = executor.step(native, fidelity=FidelityLevel.HARD_DISCRETE)
        assert np.all(np.asarray(result.agents.wealth)[np.asarray(result.agents.active)] >= 0)
        if inactive_padding:
            assert float(result.agents.wealth[-1]) == -1e6

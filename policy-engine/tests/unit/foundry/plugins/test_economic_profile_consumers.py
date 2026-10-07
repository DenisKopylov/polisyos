"""Actual consumer witnesses for distinct fiscal and transition-labor profiles."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry._registry import create_mechanism_from_spec
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import apply_patch_map
from polisyos.foundry.plugins.composite import (
    CompositeExecutor,
    CompositeState,
    CompositeStateConfig,
)
from polisyos.foundry.plugins.core import DomainConfig, PluginRegistry
from polisyos.foundry.plugins.economics import EconomicsPlugin, EconomicState
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _assert_full_state(left, right) -> None:
    left_values, left_tree = jax.tree_util.tree_flatten(left)
    right_values, right_tree = jax.tree_util.tree_flatten(right)
    assert left_tree == right_tree
    for actual, expected in zip(left_values, right_values, strict=True):
        np.testing.assert_array_equal(actual, expected)


def _plugin_consumer(mechanism: str, state: EconomicState):
    registry = PluginRegistry()
    registry.clear()  # The production registry is a process singleton.
    registry.register(EconomicsPlugin())
    config = CompositeStateConfig(
        domains={"economics": DomainConfig(n_agents=12, enabled_mechanisms=(mechanism,))}
    )
    composite = CompositeState(
        domain_states={"economics": state}, time_step=jnp.asarray(0), config=config
    )
    return CompositeExecutor(["economics"], registry), composite


@pytest.mark.parametrize("policy_rate", [0.0, 0.25, 0.5])
def test_registered_progressive_tax_complete_state_budget_and_step_profile(policy_rate) -> None:
    plugin = EconomicsPlugin()
    taxation = next(m for m in plugin.get_mechanisms() if m.name == "taxation")
    income = np.asarray([5000.0, 20000.0, 60000.0] * 4, dtype=np.float32)
    active = np.asarray([True, False, True] * 4)
    before = EconomicState.empty(n_agents=12, seed=41)
    before = before.replace(
        agents=before.agents.replace(
            income=jnp.asarray(income), wealth=jnp.full(12, 200000.0), active=jnp.asarray(active)
        ),
        policy=before.policy.replace(tax_rate=jnp.asarray(policy_rate)),
    )
    # Integrate the three applicable marginal brackets in supplied per-step units.
    tax = np.asarray(
        [
            0.10 * min(x, 10000) + 0.15 * max(min(x - 10000, 30000), 0) + 0.22 * max(x - 40000, 0)
            for x in income
        ],
        dtype=np.float32,
    )
    tax *= (1 + policy_rate - 0.25) * active
    expected = before.replace(agents=before.agents.replace(wealth=before.agents.wealth - tax))
    _assert_full_state(taxation.apply(before), expected)
    executor, composite = _plugin_consumer("taxation", before)
    first = executor.step(composite, jax.random.PRNGKey(9))
    current = first.get_domain("economics")
    _assert_full_state(current, expected.update_aggregates())
    second = executor.step(first, jax.random.PRNGKey(10))
    expected2 = expected.replace(
        agents=expected.agents.replace(wealth=expected.agents.wealth - tax)
    )
    _assert_full_state(second.get_domain("economics"), expected2.update_aggregates())
    assert int(second.time_step) == 2
    assert int(current.time_step) == 0  # Existing composite vs domain clock distinction.
    # Plugin household stocks lose tax; there is no government counteraccount.
    assert not hasattr(current, "government_balance")
    assert float(before.agents.wealth.sum() - current.agents.wealth.sum()) == float(tax.sum())
    # Native tax instead uses reported income, updates flow income and counteraccount.
    native = GlobalState.empty(n_agents=12, n_firms=1)
    native = native.replace(
        agents=native.agents.replace(
            active=jnp.asarray(active),
            income=jnp.asarray(income),
            reported_income=jnp.asarray(income / 2),
        )
    )
    patch, next_key = create_mechanism_from_spec("income_tax", {"rate": 0.25}, 12, 1).emit_patches(
        native, jax.random.PRNGKey(9)
    )
    result = apply_patch_map(
        native,
        patch,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        default_node_id="tax",
    )
    debit = income / 8 * active
    np.testing.assert_array_equal(result.agents.income, income - debit)
    assert float(result.government_balance) == float(debit.sum())
    assert float(result.agents.income.sum() + result.government_balance) == float(income.sum())
    np.testing.assert_array_equal(next_key, jax.random.PRNGKey(9))
    assert not np.array_equal(tax, debit)


def test_registered_transition_labor_composite_uses_supplied_seed_and_retains_distinct_clock() -> (
    None
):
    state = EconomicState.empty(n_agents=12, seed=7)
    state = state.replace(
        agents=state.agents.replace(
            employed=jnp.zeros(12, dtype=bool), wage=jnp.full(12, 40000.0), skill_level=jnp.ones(12)
        )
    )
    executor, composite = _plugin_consumer("labor_market", state)
    labor = next(m for m in EconomicsPlugin().get_mechanisms() if m.name == "labor_market")
    key = jax.random.PRNGKey(28)
    _, domain_key = jax.random.split(key)
    _, mechanism_key = jax.random.split(domain_key)
    expected = labor.apply(state, rng_key=mechanism_key).update_aggregates()
    actual = executor.step(composite, key)
    _assert_full_state(actual.get_domain("economics"), expected)
    _assert_full_state(executor.step(composite, key), actual)
    changed = executor.step(composite, jax.random.PRNGKey(29)).get_domain("economics")
    assert not np.array_equal(changed.agents.wage, expected.agents.wage)
    assert int(actual.time_step) == 1 and int(expected.time_step) == 0
    # No supplied key uses the domain clock; fixed clock replays the same draw.
    _assert_full_state(labor.apply(state), labor.apply(state))
    changed_time = labor.apply(state.replace(time_step=jnp.asarray(1)))
    assert not np.array_equal(changed_time.agents.wage, labor.apply(state).agents.wage)
    assert not hasattr(expected.agents, "employer_id")
    assert not hasattr(expected, "firms")


def test_matched_zero_employment_regime_preserves_distinct_full_state_and_rng_laws() -> None:
    from polisyos.foundry.plugins.economics.mechanisms import LaborMarketMechanism

    active = jnp.asarray([True, False, True] * 4)
    economic = EconomicState.empty(n_agents=12, seed=5)
    economic = economic.replace(
        agents=economic.agents.replace(
            active=active,
            employed=jnp.zeros(12, dtype=bool),
            wage=jnp.zeros(12),
            income=jnp.zeros(12),
        ),
        policy=economic.policy.replace(minimum_wage=jnp.asarray(0.0)),
    )
    native = GlobalState.empty(n_agents=12, n_firms=1)
    native = native.replace(
        agents=native.agents.replace(
            active=active,
            is_employed=jnp.zeros(12, dtype=bool),
            employer_id=jnp.full(12, -1),
            income=jnp.zeros(12),
        ),
        firms=native.firms.replace(wage_offer=jnp.zeros(1)),
    )
    transition = LaborMarketMechanism(job_finding_rate=0, job_separation_rate=0, wage_growth_rate=0)
    threshold = create_mechanism_from_spec("labor_market", {"employment_threshold": 0.0}, 12, 1)
    for seed in (4, 19):
        key = jax.random.PRNGKey(seed)
        patch, next_key = threshold.emit_patches(native, key)
        result = apply_patch_map(
            native,
            patch,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            default_node_id="matched-labor",
        )
        expected_native = native.replace(
            firms=native.firms.replace(labor_count=jnp.zeros(1, dtype=jnp.int32))
        )
        _assert_full_state(result, expected_native)
        expected_plugin = economic.replace(
            agents=economic.agents.replace(hours_worked=jnp.zeros(12))
        )
        plugin_result = transition.apply(economic, rng_key=key)
        _assert_full_state(plugin_result, expected_plugin)
        np.testing.assert_array_equal(plugin_result.agents.employed, result.agents.is_employed)
        np.testing.assert_array_equal(plugin_result.agents.income, result.agents.income)
        np.testing.assert_array_equal(next_key, jax.random.split(key, 3)[2])
        # Matching these two observables does not fabricate plugin employer IDs,
        # firm counts or a returned key: these remain native-only ABI fields.
        assert not hasattr(plugin_result.agents, "employer_id")
        assert not hasattr(plugin_result, "firms")
        # Same finite state, explicit law change: native threshold=1 creates jobs;
        # the zero-finding transition retains unemployment.
        divergent, _ = create_mechanism_from_spec(
            "labor_market", {"employment_threshold": 1.0}, 12, 1
        ).emit_patches(native, key)
        changed = apply_patch_map(
            native,
            divergent,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            default_node_id="distinct-labor",
        )
        np.testing.assert_array_equal(changed.agents.is_employed, active)
        assert not np.array_equal(changed.agents.is_employed, plugin_result.agents.employed)


@pytest.mark.parametrize("income,expected", [([0.25, 0.75], -0.5), ([0.25, 0.75, 0.0, 0.0], -0.25)])
def test_historical_baseline_preserves_all_entry_population_and_aliases(income, expected) -> None:
    from polisyos.foundry.methods._internal.loss import policy_loss_fn as internal_alias
    from polisyos.foundry.methods.loss import policy_loss_fn as public_alias
    from polisyos.foundry.plugins.economics.baselines import normalized_income_budget_loss

    assert internal_alias is public_alias is normalized_income_budget_loss
    state = GlobalState.empty(n_agents=len(income), n_firms=1)
    state = state.replace(
        agents=state.agents.replace(
            income=jnp.asarray(income), active=jnp.zeros(len(income), dtype=bool)
        )
    )
    assert float(jax.jit(public_alias)(state)) == pytest.approx(expected)
    # The historical ABI counts every supplied entry, regardless of active flag.
    assert float(
        public_alias(state.replace(agents=state.agents.replace(active=~state.agents.active)))
    ) == pytest.approx(expected)
    high_income = state.replace(agents=state.agents.replace(income=jnp.asarray(income) * 10000))
    gradient = jax.grad(
        lambda values: public_alias(
            high_income.replace(agents=high_income.agents.replace(income=values))
        )
    )(high_income.agents.income)
    np.testing.assert_allclose(gradient, np.zeros(len(income)), atol=1e-7, rtol=0)

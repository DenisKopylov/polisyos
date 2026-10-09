"""Finite equation profiles for live fiscal/labor kernels and economics consumers."""

from __future__ import annotations

import json
from collections.abc import Mapping

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry._registry import create_mechanism_from_spec
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import apply_patch_map
from polisyos.foundry.methods.catalog.mechanism.runtime import (
    IncomeTaxMechanismMethod,
    LaborMarketMechanismMethod,
    TaxSubsidyMechanismMethod,
)
from polisyos.foundry.methods.loss import policy_loss_fn
from polisyos.foundry.plugins.economics import EconomicsPlugin, EconomicState
from polisyos.foundry.plugins.economics.baselines import normalized_income_budget_loss
from polisyos.foundry.plugins.economics.mechanisms import (
    LaborMarketMechanism as TransitionLabor,
)
from polisyos.foundry.plugins.economics.mechanisms import (
    TaxationMechanism,
    TransferMechanism,
)
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _state() -> GlobalState:
    state = GlobalState.empty(n_agents=4, n_firms=1)
    return state.replace(
        agents=state.agents.replace(
            active=jnp.asarray([True, True, False, True]),
            income=jnp.asarray([100.0, 50.0, 25.0, 80.0]),
            reported_income=jnp.asarray([80.0, 40.0, 25.0, 40.0]),
            skill_level=jnp.asarray([1.0, 1.5, 0.5, 2.0]),
            is_employed=jnp.asarray([False, True, True, False]),
            employer_id=jnp.asarray([-1, 0, 0, -1], dtype=jnp.int32),
        ),
        firms=state.firms.replace(wage_offer=jnp.asarray([20.0])),
        government_balance=jnp.asarray(17.0),
    )


_TARGET = jnp.asarray([True, False, True, True])


def _assert_tree_equal(actual, expected) -> None:
    left, left_shape = jax.tree_util.tree_flatten(actual)
    right, right_shape = jax.tree_util.tree_flatten(expected)
    assert left_shape == right_shape
    for lhs, rhs in zip(left, right, strict=True):
        np.testing.assert_array_equal(np.asarray(lhs), np.asarray(rhs))


def _assert_full_patch(actual: Mapping, expected: Mapping) -> None:
    assert set(actual) == set(expected)
    for slot, records in expected.items():
        assert len(actual[slot]) == len(records)
        for lhs, rhs in zip(actual[slot], records, strict=True):
            assert set(lhs) == set(rhs)
            for field in rhs:
                np.testing.assert_array_equal(np.asarray(lhs[field]), np.asarray(rhs[field]))


def _apply(state: GlobalState, patch: dict) -> GlobalState:
    return apply_patch_map(
        state,
        patch,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        default_node_id="economic-profile-oracle",
    )


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize(
    "kind,method,expected_delta,expected_balance",
    [
        ("income_tax", IncomeTaxMechanismMethod, [-20.0, 0.0, 0.0, -10.0], 30.0),
        ("tax_subsidy", TaxSubsidyMechanismMethod, [25.0, 0.0, 0.0, 20.0], -45.0),
    ],
)
def test_registered_fiscal_producer_full_patch_reaches_state_consumer(
    compiled, kind, method, expected_delta, expected_balance
) -> None:
    state, key = _state(), jax.random.PRNGKey(27)
    mechanism = create_mechanism_from_spec(kind, {"rate": 0.25}, 4, 1)
    emit = lambda value, seed: mechanism.emit_patches(value, seed, target_mask=_TARGET)
    if compiled:
        emit = jax.jit(emit)
    patch, next_key = emit(state, key)
    expected_patch = {
        "agents.income": [{"delta": expected_delta}],
        "government.balance": [{"delta": expected_balance}],
    }
    _assert_full_patch(patch, expected_patch)
    np.testing.assert_array_equal(np.asarray(next_key), np.asarray(key))
    result = _apply(state, patch)
    expected = state.replace(
        agents=state.agents.replace(income=state.agents.income + jnp.asarray(expected_delta)),
        government_balance=jnp.asarray(17 + expected_balance),
    )
    _assert_tree_equal(result, expected)
    assert float(result.agents.income.sum() + result.government_balance) == float(
        state.agents.income.sum() + state.government_balance
    )
    artifact = method.pure_step(state, {"rate": 0.25, "target_mask": _TARGET, "__seed__": 27})[
        "result"
    ]
    _assert_full_patch(json.loads(json.dumps(artifact))["patches"], expected_patch)
    assert artifact["n_patch_slots"] == 2


@pytest.mark.parametrize("compiled", [False, True], ids=["eager", "jit"])
@pytest.mark.parametrize(
    "threshold,employed,employers,income_delta,count",
    [
        (0.0, [False, True, True, False], [-1, 0, 0, -1], [-100.0, 0.0, 0.0, -80.0], 1),
        (1.0, [True, True, True, True], [0, 0, 0, 0], [-80.0, 0.0, 0.0, -40.0], 3),
    ],
)
def test_registered_labor_full_patch_has_independent_extreme_probability_oracle(
    compiled, threshold, employed, employers, income_delta, count
) -> None:
    state, key = _state(), jax.random.PRNGKey(27)
    mechanism = create_mechanism_from_spec(
        "labor_market", {"employment_threshold": threshold}, 4, 1
    )
    emit = lambda value, seed: mechanism.emit_patches(value, seed, target_mask=_TARGET)
    if compiled:
        emit = jax.jit(emit)
    patch, next_key = emit(state, key)
    expected_patch = {
        "agents.employer_id": [{"value": employers}],
        "agents.is_employed": [{"value": employed}],
        "agents.income": [{"delta": income_delta}],
        "firms.labor_count": [{"value": [count]}],
    }
    _assert_full_patch(patch, expected_patch)
    np.testing.assert_array_equal(np.asarray(next_key), np.asarray(jax.random.split(key, 3)[2]))
    expected = state.replace(
        agents=state.agents.replace(
            employer_id=jnp.asarray(employers, dtype=jnp.int32),
            is_employed=jnp.asarray(employed),
            income=state.agents.income + jnp.asarray(income_delta),
        ),
        firms=state.firms.replace(labor_count=jnp.asarray([count], dtype=jnp.int32)),
    )
    _assert_tree_equal(_apply(state, patch), expected)
    artifact = LaborMarketMechanismMethod.pure_step(
        state, {"employment_threshold": threshold, "target_mask": _TARGET, "__seed__": 27}
    )["result"]
    _assert_full_patch(json.loads(json.dumps(artifact))["patches"], expected_patch)
    assert artifact["n_patch_slots"] == 4


def test_labor_seed_replay_and_perturbation_are_observable_in_state() -> None:
    state = GlobalState.empty(n_agents=64, n_firms=3)
    mechanism = create_mechanism_from_spec("labor_market", {"employment_threshold": 0.5}, 64, 3)
    first, first_key = mechanism.emit_patches(state, jax.random.PRNGKey(1))
    repeated, repeated_key = mechanism.emit_patches(state, jax.random.PRNGKey(1))
    changed, changed_key = mechanism.emit_patches(state, jax.random.PRNGKey(2))
    _assert_tree_equal(first, repeated)
    np.testing.assert_array_equal(first_key, repeated_key)
    assert not np.array_equal(first_key, changed_key)
    first_state, changed_state = _apply(state, first), _apply(state, changed)
    assert not np.array_equal(first_state.agents.employer_id, changed_state.agents.employer_id)
    for result in (first_state, changed_state):
        counts = np.bincount(
            np.asarray(result.agents.employer_id)[np.asarray(result.agents.is_employed)],
            minlength=3,
        )
        np.testing.assert_array_equal(result.firms.labor_count, counts)


def test_equal_one_period_tax_equations_require_explicit_stock_flow_conversion() -> None:
    native = _state()
    native = native.replace(agents=native.agents.replace(reported_income=native.agents.income))
    effective = native.agents.active & _TARGET
    economic = EconomicState.empty(n_agents=4, seed=8)
    economic = economic.replace(
        agents=economic.agents.replace(
            active=effective,
            income=native.agents.income,
            wealth=jnp.asarray([1000.0, 2000.0, 3000.0, 4000.0]),
        ),
        policy=economic.policy.replace(tax_rate=jnp.asarray(0.25)),
    )
    # Flat 25% bracket and the same one-period income base are an explicitly
    # matched fixture. Plugin wealth and native income still represent different slots.
    taxation = TaxationMechanism(brackets=((0.0, 0.25),))
    plugin_result = taxation.apply(economic)
    patch, key = create_mechanism_from_spec("income_tax", {"rate": 0.25}, 4, 1).emit_patches(
        native, jax.random.PRNGKey(8), target_mask=_TARGET
    )
    native_result = _apply(native, patch)
    tax = np.asarray([25.0, 0.0, 0.0, 20.0])
    np.testing.assert_array_equal(economic.agents.wealth - plugin_result.agents.wealth, tax)
    np.testing.assert_array_equal(native.agents.income - native_result.agents.income, tax)
    np.testing.assert_array_equal(plugin_result.agents.income, economic.agents.income)
    assert float(native_result.government_balance - native.government_balance) == tax.sum()
    np.testing.assert_array_equal(key, jax.random.PRNGKey(8))
    # Interpreting wealth as the flow input destroys the matched-equation result.
    wrong_units = taxation.apply(
        economic.replace(agents=economic.agents.replace(income=economic.agents.wealth))
    )
    assert not np.array_equal(economic.agents.wealth - wrong_units.agents.wealth, tax)
    assert not hasattr(plugin_result, "government_balance")


def test_real_progressive_tax_can_reach_signed_wealth_then_existing_gini_refuses() -> None:
    """The real plugin tax law feeds signed active wealth into the Gini guard."""

    economic = EconomicState.empty(n_agents=2, seed=31)
    economic = economic.replace(
        agents=economic.agents.replace(
            active=jnp.ones(2, dtype=jnp.bool_),
            income=jnp.asarray([25_000.0, 50_000.0]),
            wealth=jnp.zeros(2),
        )
    )

    taxed = TaxationMechanism().apply(economic)

    # The existing progressive brackets debit 3,250 and 7,700 respectively.
    np.testing.assert_array_equal(taxed.agents.wealth, jnp.asarray([-3_250.0, -7_700.0]))
    assert not taxed.validate()
    with pytest.raises(Exception, match="classical Gini requires finite nonnegative active values"):
        jax.block_until_ready(taxed.update_aggregates())


def test_equal_subsidy_transfer_equations_require_uniform_income_and_policy() -> None:
    native = _state().replace(agents=_state().agents.replace(income=jnp.full(4, 100.0)))
    effective = native.agents.active & _TARGET
    economic = EconomicState.empty(n_agents=4, seed=8)
    economic = economic.replace(
        agents=economic.agents.replace(
            active=effective,
            income=jnp.full(4, 100.0),
            wealth=jnp.full(4, 1000.0),
            employed=jnp.ones(4, dtype=jnp.bool_),
        ),
        policy=economic.policy.replace(
            transfer_rate=jnp.asarray(0.25), unemployment_benefit=jnp.asarray(0.0)
        ),
    ).update_aggregates()
    transferred = TransferMechanism(means_tested=False).apply(economic)
    patch, _ = create_mechanism_from_spec("tax_subsidy", {"rate": 0.25}, 4, 1).emit_patches(
        native, jax.random.PRNGKey(8), target_mask=_TARGET
    )
    result = _apply(native, patch)
    expected = np.asarray([25.0, 0.0, 0.0, 25.0])
    np.testing.assert_array_equal(transferred.agents.wealth - economic.agents.wealth, expected)
    np.testing.assert_array_equal(result.agents.income - native.agents.income, expected)
    assert float(result.government_balance - native.government_balance) == -50.0
    # The default means-tested profile has a distinct law even at identical units.
    default_result = TransferMechanism().apply(economic)
    assert not np.array_equal(default_result.agents.wealth - economic.agents.wealth, expected)


def test_plugin_factory_labor_has_transition_wage_and_seed_laws_distinct_from_threshold() -> None:
    plugin = EconomicsPlugin()
    mechanism = next(item for item in plugin.get_mechanisms() if item.name == "labor_market")
    state = EconomicState.empty(n_agents=64, seed=8)
    state = state.replace(
        agents=state.agents.replace(
            employed=jnp.zeros(64, dtype=jnp.bool_),
            wage=jnp.full(64, 40000.0),
            skill_level=jnp.ones(64),
        )
    )
    first = mechanism.apply(state, rng_key=jax.random.PRNGKey(1))
    repeated = mechanism.apply(state, rng_key=jax.random.PRNGKey(1))
    changed = mechanism.apply(state, rng_key=jax.random.PRNGKey(2))
    _assert_tree_equal(first, repeated)
    assert not np.array_equal(first.agents.wage, changed.agents.wage)
    assert not np.array_equal(first.agents.employed, changed.agents.employed)
    assert np.all(np.asarray(first.agents.wage) >= 30000.0)
    np.testing.assert_array_equal(
        first.agents.income, np.where(first.agents.employed, first.agents.wage, 0.0)
    )
    np.testing.assert_array_equal(
        first.agents.hours_worked, np.where(first.agents.employed, 40.0, 0.0)
    )
    # A zero threshold removes every active native job, whereas zero transition
    # rates retain existing jobs. Neither class name grants model equivalence.
    transition = TransitionLabor(job_finding_rate=0.0, job_separation_rate=0.0)
    employed = state.replace(agents=state.agents.replace(employed=jnp.ones(64, dtype=jnp.bool_)))
    assert np.asarray(
        transition.apply(employed, rng_key=jax.random.PRNGKey(1)).agents.employed
    ).all()
    native = GlobalState.empty(n_agents=64, n_firms=1)
    patch, _ = create_mechanism_from_spec(
        "labor_market", {"employment_threshold": 0.0}, 64, 1
    ).emit_patches(native, jax.random.PRNGKey(1))
    assert not np.asarray(_apply(native, patch).agents.is_employed).any()


@pytest.mark.parametrize(
    "income,expected",
    [
        ([0.0, 0.0], 0.0),
        ([0.25, 0.75], -0.5),
        ([1.0, 1.0], -1.0),
        ([10.0, 30.0], -1.0),
        ([-1.0, 3.0], -0.5),
        ([-2.0, -2.0], 1.0),
    ],
)
def test_named_historical_income_score_preserves_hand_calculation_and_consumer(
    income, expected
) -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1)
    state = state.replace(
        agents=state.agents.replace(income=jnp.asarray(income)),
        government_balance=jnp.asarray(-2000.0),
    )
    assert policy_loss_fn is normalized_income_budget_loss
    # Budget breach (-1000 - -2000)/1000 = 1, with weight 10.
    assert float(jax.jit(policy_loss_fn)(state)) == pytest.approx(expected + 10.0)
    safe = state.replace(government_balance=jnp.asarray(0.0))
    assert float(policy_loss_fn(safe)) == pytest.approx(expected)


def test_historical_positive_unit_income_score_is_scale_invariant_not_welfare() -> None:
    state = GlobalState.empty(n_agents=3, n_firms=1)
    for scale in (1.0, 10.0, 1e6):
        current = state.replace(
            agents=state.agents.replace(income=jnp.asarray([1.0, 2.0, 3.0]) * scale)
        )
        assert float(normalized_income_budget_loss(current)) == -1.0
    # EconomicState wealth is a stock, and is not an admitted GlobalState income input.
    with pytest.raises(AttributeError, match="government_balance"):
        normalized_income_budget_loss(EconomicState.empty(n_agents=3, seed=8))


@pytest.mark.parametrize(
    "balance,minimum,expected",
    [(-1500.0, -1000.0, 1.5), (10.0, 20.0, 1.5), (-2.0, 0.0, 39.0)],
)
def test_historical_budget_scales_have_independent_hand_oracle(balance, minimum, expected) -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1)
    state = state.replace(
        agents=state.agents.replace(income=jnp.asarray([1.0, 3.0])),
        government_balance=jnp.asarray(balance),
    )
    assert float(jax.jit(policy_loss_fn)(state, min_balance=minimum)) == pytest.approx(expected)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("slot", ["income", "balance", "minimum"])
def test_named_historical_score_nonfinite_inputs_fail_closed(invalid, slot) -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1)
    income = [1.0, invalid] if slot == "income" else [1.0, 3.0]
    state = state.replace(
        agents=state.agents.replace(income=jnp.asarray(income)),
        government_balance=jnp.asarray(invalid if slot == "balance" else 0.0),
    )
    minimum = invalid if slot == "minimum" else -1000.0
    assert float(jax.jit(policy_loss_fn)(state, min_balance=minimum)) == float("inf")


def test_named_historical_score_gradients_preserve_the_selected_normalized_law() -> None:
    state = GlobalState.empty(n_agents=2, n_firms=1)

    def loss(income):
        return policy_loss_fn(state.replace(agents=state.agents.replace(income=income)))

    gradient = jax.jit(jax.grad(loss))
    np.testing.assert_array_equal(gradient(jnp.asarray([0.25, 0.5])), [-0.5, -0.5])
    np.testing.assert_allclose(gradient(jnp.asarray([2.0, 4.0])), [0.0, 0.0], atol=1e-7)

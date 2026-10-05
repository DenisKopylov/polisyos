"""Characterize the two economic profiles and the named loss baseline."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy.testing as npt
import pytest

from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.mechanisms.fiscal import compute_tax
from polisyos.foundry.execute.mechanisms.labor import (
    LaborMarketMechanism as PatchLaborMarketMechanism,
)
from polisyos.foundry.methods._internal.loss import policy_loss_fn as internal_policy_loss_fn
from polisyos.foundry.methods.loss import policy_loss_fn as legacy_policy_loss_fn
from polisyos.foundry.plugins.economics.mechanisms import (
    LaborMarketMechanism as EconomicLaborMarketMechanism,
)
from polisyos.foundry.plugins.economics.mechanisms import (
    TaxationMechanism,
)


def _global_state(income: list[float], *, balance: float = 0.0) -> GlobalState:
    state = GlobalState.empty(n_agents=len(income), n_firms=1)
    return state.replace(
        agents=state.agents.replace(income=jnp.asarray(income, dtype=jnp.float32)),
        government_balance=jnp.asarray(balance, dtype=jnp.float32),
    )


@pytest.mark.parametrize(
    ("income", "balance", "min_balance", "expected"),
    [
        ([1000.0, 2000.0, 3000.0], 0.0, -1000.0, -1.0),
        ([10000.0, 20000.0, 30000.0], 0.0, -1000.0, -1.0),
        ([0.0, 0.0, 0.0], 0.0, -1000.0, 0.0),
        ([-100.0, -200.0, -300.0], 0.0, -1000.0, 1.0),
        ([-100.0, 0.0, 100.0], 0.0, -1000.0, 0.0),
        ([1000.0, 2000.0, 3000.0], -2000.0, -1000.0, 9.0),
    ],
)
def test_legacy_policy_loss_fn_preserves_normalized_income_budget_formula(
    income: list[float],
    balance: float,
    min_balance: float,
    expected: float,
) -> None:
    result = legacy_policy_loss_fn(_global_state(income, balance=balance), min_balance=min_balance)

    npt.assert_allclose(float(result), expected, rtol=0.0, atol=1e-5)


def test_legacy_public_and_internal_facades_preserve_identity() -> None:
    assert internal_policy_loss_fn is legacy_policy_loss_fn


def test_named_economic_baseline_owns_the_legacy_facades() -> None:
    try:
        from polisyos.foundry.plugins.economics.baselines import (
            normalized_income_budget_loss,
        )
    except ModuleNotFoundError as exc:
        pytest.fail(f"canonical economic baseline owner is missing: {exc}")

    assert internal_policy_loss_fn is normalized_income_budget_loss
    assert legacy_policy_loss_fn is normalized_income_budget_loss


def test_legacy_policy_loss_fn_is_jittable_and_differentiable() -> None:
    state = _global_state([-2.0, 4.0])
    compiled = jax.jit(legacy_policy_loss_fn)
    npt.assert_allclose(float(compiled(state)), float(legacy_policy_loss_fn(state)))

    def loss_for_income(income: jnp.ndarray) -> jnp.ndarray:
        return legacy_policy_loss_fn(state.replace(agents=state.agents.replace(income=income)))

    gradient = jax.grad(loss_for_income)(state.agents.income)
    assert gradient.shape == state.agents.income.shape
    assert bool(jnp.all(jnp.isfinite(gradient)))


def test_named_baseline_gradient_is_the_normalized_formula_not_income_maximization() -> None:
    """Analytic derivatives distinguish the retained baseline from a welfare objective."""
    state = _global_state([-2.0, 4.0])

    def loss(income):
        return legacy_policy_loss_fn(state.replace(agents=state.agents.replace(income=income)))

    # For (-2, 4), L=-(a+b)/(-a+b), so dL/da=-2/9 and dL/db=-1/9.
    npt.assert_allclose(jax.grad(loss)(state.agents.income), [-2.0 / 9.0, -1.0 / 9.0])
    npt.assert_allclose(jax.grad(loss)(jnp.array([1000.0, 2000.0])), [0.0, 0.0], atol=1e-9)


@pytest.mark.parametrize("min_balance", [float("nan"), float("inf"), -float("inf")])
def test_baseline_rejects_nonfinite_budget_threshold_under_jit(min_balance: float) -> None:
    """A supplied invalid threshold remains a refusal after compilation."""
    state = _global_state([1.0, 2.0])
    assert float(jax.jit(legacy_policy_loss_fn)(state, min_balance)) == float("inf")


@pytest.mark.parametrize(
    "state",
    [
        _global_state([1.0, jnp.nan]),
        _global_state([1.0, 2.0], balance=float("nan")),
        _global_state([1.0, float("inf")]),
    ],
)
def test_legacy_policy_loss_fn_keeps_native_numeric_guard_fail_closed(state: GlobalState) -> None:
    assert float(legacy_policy_loss_fn(state)) == float("inf")


def test_income_tax_and_economic_tax_keep_distinct_tax_bases() -> None:
    state = _global_state([100.0, 200.0])
    state = state.replace(
        agents=state.agents.replace(reported_income=jnp.asarray([10.0, 20.0], dtype=jnp.float32))
    )
    npt.assert_allclose(
        compute_tax(state, jnp.asarray(0.2, dtype=jnp.float32)),
        jnp.asarray([2.0, 4.0], dtype=jnp.float32),
    )

    from polisyos.foundry.plugins.economics.state import EconomicState

    economic = EconomicState.empty(n_agents=2, seed=0)
    economic = economic.replace(
        agents=economic.agents.replace(
            income=jnp.asarray([100.0, 200.0], dtype=jnp.float32),
            wealth=jnp.asarray([1000.0, 1000.0], dtype=jnp.float32),
        )
    )
    taxed = TaxationMechanism().apply(economic)
    npt.assert_allclose(taxed.agents.income, economic.agents.income)
    assert bool(jnp.any(taxed.agents.wealth < economic.agents.wealth))


def test_domain_plugin_fiscal_consumer_does_not_claim_patchmap_budget_equivalence() -> None:
    """The actual plugin selection preserves its wealth effects and separate ABI."""
    from polisyos.foundry.plugins.economics.plugin import EconomicsPlugin
    from polisyos.foundry.plugins.economics.state import EconomicState

    economic = EconomicState.empty(n_agents=3, seed=0)
    economic = economic.replace(
        agents=economic.agents.replace(
            active=jnp.array([True, False, True]),
            income=jnp.array([100.0, 200.0, 300.0]),
            wealth=jnp.array([1000.0, 1000.0, 1000.0]),
        )
    )
    taxation = next(item for item in EconomicsPlugin().get_mechanisms() if item.name == "taxation")
    consumed = taxation.apply(economic)
    npt.assert_allclose(consumed.agents.wealth, [990.0, 1000.0, 970.0])
    npt.assert_array_equal(consumed.agents.income, economic.agents.income)
    assert not hasattr(consumed, "government_balance")
    assert consumed.time_step == economic.time_step


def test_threshold_and_transition_labor_profiles_remain_distinct() -> None:
    patch_state = _global_state([100.0, 200.0])
    patch_state = patch_state.replace(
        agents=patch_state.agents.replace(
            is_employed=jnp.asarray([True, False]),
            employer_id=jnp.asarray([0, -1], dtype=jnp.int32),
            skill_level=jnp.ones(2, dtype=jnp.float32),
        )
    )
    patches, _ = PatchLaborMarketMechanism(employment_threshold=0.0).emit_patches(
        patch_state, jax.random.PRNGKey(0)
    )
    assert patches["agents.is_employed"][0]["value"].tolist() == [False, False]

    from polisyos.foundry.plugins.economics.state import EconomicState

    transition_state = EconomicState.empty(n_agents=2, seed=0).replace(
        agents=EconomicState.empty(n_agents=2, seed=0).agents.replace(
            employed=jnp.asarray([True, False]),
            income=jnp.asarray([100.0, 200.0], dtype=jnp.float32),
            skill_level=jnp.ones(2, dtype=jnp.float32),
        )
    )
    transitioned = EconomicLaborMarketMechanism(
        job_finding_rate=1.0,
        job_separation_rate=0.0,
        wage_growth_rate=0.0,
    ).apply(transition_state, rng_key=jax.random.PRNGKey(0))
    assert transitioned.agents.employed.tolist() == [True, True]

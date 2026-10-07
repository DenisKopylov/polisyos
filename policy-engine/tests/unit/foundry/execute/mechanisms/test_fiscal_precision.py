"""Native fiscal arithmetic keeps the source rate until the income dtype is known."""

import pickle
from decimal import Decimal

import equinox as eqx
import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry._registry import create_mechanism_from_spec
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import apply_patch_map
from polisyos.foundry.execute.mechanisms.fiscal import (
    IncomeTax,
    TaxSubsidy,
    _validate_rate,
    compute_tax,
)
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def make_state(dtype, values=(1000.0,) * 10):
    state = GlobalState.empty(n_agents=len(values), n_firms=1)
    income = jnp.asarray(values, dtype=dtype)
    return state.replace(
        agents=state.agents.replace(income=income, reported_income=income),
        government_balance=jnp.asarray(0.0, dtype=dtype),
    )


def apply(state, patch):
    return apply_patch_map(
        state,
        patch,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        default_node_id="tax",
    )


@pytest.mark.parametrize("kind", ["income_tax", "tax_subsidy"])
@pytest.mark.parametrize("compiled", [False, True])
def test_rate_is_materialized_at_income_dtype_before_native_calculation(kind, compiled):
    with jax.enable_x64(True):
        state = make_state(jnp.float64)
        mech = create_mechanism_from_spec(kind, {"rate": Decimal(".10")}, 10, 1)
        emit = jax.jit(lambda s, k: mech.emit_patches(s, k)) if compiled else mech.emit_patches
        patch, key = emit(state, jax.random.PRNGKey(17))
        sign = -1 if kind == "income_tax" else 1
        np.testing.assert_array_equal(
            patch["agents.income"][0]["delta"], np.full(10, sign * 100.0, dtype=np.float64)
        )
        assert float(patch["government.balance"][0]["delta"]) == -sign * 1000.0
        assert patch["agents.income"][0]["delta"].dtype == jnp.float64
        after = apply(state, patch)
        assert float(after.government_balance) == -sign * 1000.0
        np.testing.assert_array_equal(key, jax.random.PRNGKey(17))


@pytest.mark.parametrize("kind", ["income_tax", "tax_subsidy"])
@pytest.mark.parametrize("compiled", [False, True])
def test_float32_calculation_keeps_declared_output_dtype_with_precise_source(kind, compiled):
    with jax.enable_x64(True):
        state = make_state(jnp.float32)
        mech = create_mechanism_from_spec(kind, {"rate": Decimal(".10")}, 10, 1)
        emit = jax.jit(lambda s, k: mech.emit_patches(s, k)) if compiled else mech.emit_patches
        patch, _ = emit(state, jax.random.PRNGKey(0))
        assert patch["agents.income"][0]["delta"].dtype == jnp.float32
        assert patch["government.balance"][0]["delta"].dtype == jnp.float32
        assert float(abs(patch["government.balance"][0]["delta"])) == 1000.0
        assert apply(state, patch).agents.income.dtype == jnp.float32


@pytest.mark.parametrize("kind", ["income_tax", "tax_subsidy"])
def test_explicit_float32_parameter_keeps_its_given_precision_on_float64_income(kind):
    with jax.enable_x64(True):
        state = make_state(jnp.float64)
        cls = IncomeTax if kind == "income_tax" else TaxSubsidy
        mech = cls(rate=jnp.asarray(0.1, dtype=jnp.float32), n_agents=10)
        patch, _ = mech.emit_patches(state, jax.random.PRNGKey(0))
        assert mech.rate.dtype == jnp.float32
        assert (
            float(abs(patch["government.balance"][0]["delta"])) == float(np.float32(0.1)) * 10000.0
        )


@pytest.mark.parametrize("cls", [IncomeTax, TaxSubsidy])
@pytest.mark.parametrize("compiled", [False, True])
def test_precise_float64_rate_and_large_income_are_not_quantized_to_float32(cls, compiled):
    with jax.enable_x64(True):
        state = make_state(jnp.float64, (1e12,))
        mech = cls(rate=jnp.asarray(0.1000000001, dtype=jnp.float64), n_agents=1)
        emit = jax.jit(lambda s, k: mech.emit_patches(s, k)) if compiled else mech.emit_patches
        patch, _ = emit(state, jax.random.PRNGKey(0))
        assert float(abs(patch["agents.income"][0]["delta"][0])) == 100000000100.0
        assert float(abs(patch["government.balance"][0]["delta"])) == 100000000100.0


@pytest.mark.parametrize("cls", [IncomeTax, TaxSubsidy])
def test_large_float64_tax_amount_retains_fraction(cls):
    with jax.enable_x64(True):
        state = make_state(jnp.float64, (2**24 + 1.0,))
        mech = cls(rate=0.5, n_agents=1)
        patch, _ = mech.emit_patches(state, jax.random.PRNGKey(0))
        assert float(abs(patch["agents.income"][0]["delta"][0])) == 8388608.5


@pytest.mark.parametrize("kind", ["income_tax", "tax_subsidy"])
def test_rate_rebinding_pickle_and_gradient_use_current_public_parameter(kind):
    with jax.enable_x64(True):
        state = make_state(jnp.float64, (1000.0,))
        cls = IncomeTax if kind == "income_tax" else TaxSubsidy
        original = cls(rate=0.1000000001, n_agents=1)
        changed = eqx.tree_at(
            lambda m: m.rate, original, jnp.asarray(0.2000000001, dtype=jnp.float64)
        )
        reloaded = pickle.loads(pickle.dumps(changed))  # noqa: S301 -- Local test-owned bytes.
        patch, _ = reloaded.emit_patches(state, jax.random.PRNGKey(0))
        assert float(abs(patch["agents.income"][0]["delta"][0])) == 200.0000001
        sign = -1.0 if kind == "income_tax" else 1.0
        grad = eqx.filter_grad(
            lambda m: jnp.sum(
                m.emit_patches(state, jax.random.PRNGKey(0))[0]["agents.income"][0]["delta"]
            )
        )(changed)
        assert float(grad.rate) == sign * 1000.0
        assert grad.rate.dtype == changed.rate.dtype


@pytest.mark.parametrize("x64", [False, True])
def test_legacy_validation_helper_default_dtype_remains_float32(x64):
    with jax.enable_x64(x64):
        assert _validate_rate(0.1).dtype == jnp.float32


@pytest.mark.parametrize("dtype", [jnp.float32, jnp.float64])
def test_direct_compute_tax_uses_current_income_calculation_dtype(dtype):
    with jax.enable_x64(True):
        state = make_state(dtype)
        tax = compute_tax(state, jnp.asarray(0.1, dtype=jnp.float64))
        assert tax.dtype == dtype
        np.testing.assert_array_equal(tax, np.full(10, 100.0, dtype=np.dtype(dtype)))


@pytest.mark.parametrize("cls", [IncomeTax, TaxSubsidy])
def test_dynamic_constructor_inside_jit_retains_source_precision(cls):
    with jax.enable_x64(True):
        state = make_state(jnp.float64, (1e12,))

        def revenue(rate):
            mechanism = cls(rate=rate, n_agents=1)
            patch, _ = mechanism.emit_patches(state, jax.random.PRNGKey(0))
            return jnp.abs(patch["government.balance"][0]["delta"])

        source = jnp.asarray(0.1000000001, dtype=jnp.float64)
        assert float(jax.jit(revenue)(source)) == 100000000100.0
        assert float(jax.grad(revenue)(source)) == 1e12


@pytest.mark.parametrize("dtype", [jnp.int32, jnp.int64, jnp.bool_, jnp.float16, jnp.bfloat16])
@pytest.mark.parametrize("x64", [False, True])
@pytest.mark.parametrize("cls", [IncomeTax, TaxSubsidy])
@pytest.mark.parametrize("compiled", [False, True])
def test_existing_lower_precision_inputs_keep_minimum_float32_arithmetic(dtype, x64, cls, compiled):
    with jax.enable_x64(x64):
        state = make_state(dtype, (1.125, 3.25, 9.5, 17.75))
        mechanism = cls(rate=0.1, n_agents=4)
        emit = (
            jax.jit(lambda s, k: mechanism.emit_patches(s, k))
            if compiled
            else mechanism.emit_patches
        )
        patch, key = emit(state, jax.random.PRNGKey(0))
        sign = -1 if cls is IncomeTax else 1
        expected = np.asarray(state.agents.income, dtype=np.float32) * np.float32(0.1)
        np.testing.assert_array_equal(patch["agents.income"][0]["delta"], sign * expected)
        assert patch["agents.income"][0]["delta"].dtype == jnp.float32
        assert patch["government.balance"][0]["delta"].dtype == jnp.float32
        np.testing.assert_array_equal(key, jax.random.PRNGKey(0))

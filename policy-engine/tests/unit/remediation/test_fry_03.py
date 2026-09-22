"""FRY-03 witnesses for the canonical fiscal/labor execution owner."""

from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import apply_patch_map
from polisyos.foundry.mechanisms import fiscal as legacy_fiscal
from polisyos.foundry.mechanisms import labor as legacy_labor
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _canonical_module(module_name: str):
    """Load a relocated module with a useful test failure when it is absent."""
    try:
        return importlib.import_module(f"polisyos.foundry.execute.mechanisms.{module_name}")
    except ModuleNotFoundError as exc:
        pytest.fail(f"canonical FRY-03 owner is missing: {exc}", pytrace=False)


def _canonical_package():
    """Load the canonical execution-mechanism export package."""
    try:
        return importlib.import_module("polisyos.foundry.execute.mechanisms")
    except ModuleNotFoundError as exc:
        pytest.fail(f"canonical FRY-03 export package is missing: {exc}", pytrace=False)


def _state(*, n_agents: int = 4, n_firms: int = 2) -> GlobalState:
    """Build a small deterministic state exercising fiscal and labor fields."""
    state = GlobalState.empty(n_agents=n_agents, n_firms=n_firms)
    return state.replace(
        agents=state.agents.replace(
            active=jnp.array([True, True, False, True], dtype=jnp.bool_)[:n_agents],
            income=jnp.array([100.0, 50.0, 25.0, 80.0], dtype=jnp.float32)[:n_agents],
            reported_income=jnp.array([100.0, 50.0, 25.0, 80.0], dtype=jnp.float32)[:n_agents],
            skill_level=jnp.array([1.0, 1.5, 0.5, 2.0], dtype=jnp.float32)[:n_agents],
            is_employed=jnp.array([False, True, True, False], dtype=jnp.bool_)[:n_agents],
            employer_id=jnp.array([-1, 0, 1, -1], dtype=jnp.int32)[:n_agents],
        ),
        firms=state.firms.replace(
            wage_offer=jnp.array([20.0, 30.0], dtype=jnp.float32)[:n_firms],
        ),
    )


def _assert_patch_maps_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> None:
    """Compare patch payloads without relying on array object identity."""
    assert set(left) == set(right)
    for slot in left:
        assert len(left[slot]) == len(right[slot])
        for left_record, right_record in zip(left[slot], right[slot], strict=True):
            assert set(left_record) == set(right_record)
            for field in left_record:
                np.testing.assert_array_equal(
                    np.asarray(left_record[field]), np.asarray(right_record[field])
                )


def test_relocated_exports_are_the_same_live_fiscal_and_labor_classes() -> None:
    """The old import path remains a forwarding facade, not a copied kernel."""
    fiscal = _canonical_module("fiscal")
    labor = _canonical_module("labor")
    package = _canonical_package()

    assert fiscal.IncomeTax is legacy_fiscal.IncomeTax
    assert fiscal.TaxSubsidy is legacy_fiscal.TaxSubsidy
    assert labor.LaborMarketMechanism is legacy_labor.LaborMarketMechanism
    assert package.IncomeTax is fiscal.IncomeTax
    assert package.TaxSubsidy is fiscal.TaxSubsidy
    assert package.LaborMarketMechanism is labor.LaborMarketMechanism


def test_registry_and_spec_creation_resolve_the_canonical_kernel_owner() -> None:
    """Method descriptors and spec creation must load the new execution owner."""
    package = _canonical_package()
    from polisyos.foundry._registry import create_mechanism_from_spec, get_mechanism_descriptor

    expected = {
        "income_tax": ("polisyos.foundry.execute.mechanisms:IncomeTax", package.IncomeTax),
        "tax_subsidy": ("polisyos.foundry.execute.mechanisms:TaxSubsidy", package.TaxSubsidy),
        "labor_market": (
            "polisyos.foundry.execute.mechanisms:LaborMarketMechanism",
            package.LaborMarketMechanism,
        ),
    }
    for mechanism_type, (class_path, expected_class) in expected.items():
        descriptor = get_mechanism_descriptor(mechanism_type)
        assert descriptor.mechanism_class_path == class_path
        assert descriptor.mechanism_class is expected_class

    assert type(create_mechanism_from_spec("income_tax", {"rate": 0.2}, 4, 2)) is (
        package.IncomeTax
    )
    assert type(
        create_mechanism_from_spec(
            "labor_market", {"employment_threshold": 0.5}, 4, 2
        )
    ) is package.LaborMarketMechanism


def test_relocated_fiscal_kernels_preserve_patch_maps_and_prng_keys() -> None:
    """Equivalent fiscal relocation preserves both patch bytes and key progression."""
    fiscal = _canonical_module("fiscal")
    state = _state()
    key = jax.random.PRNGKey(17)

    for legacy_cls, canonical_cls, kwargs in (
        (legacy_fiscal.IncomeTax, fiscal.IncomeTax, {"rate": 0.2, "n_agents": 4}),
        (legacy_fiscal.TaxSubsidy, fiscal.TaxSubsidy, {"rate": 0.1, "n_agents": 4}),
    ):
        legacy_patches, legacy_key = legacy_cls(**kwargs).emit_patches(state, key)
        canonical_patches, canonical_key = canonical_cls(**kwargs).emit_patches(state, key)
        _assert_patch_maps_equal(legacy_patches, canonical_patches)
        np.testing.assert_array_equal(np.asarray(legacy_key), np.asarray(canonical_key))


def test_relocated_fiscal_kernel_preserves_active_target_masks_and_balance() -> None:
    """Income-tax relocation retains mask semantics and fiscal balance accounting."""
    fiscal = _canonical_module("fiscal")
    state = _state(n_agents=3, n_firms=1)
    patches, next_key = fiscal.IncomeTax(rate=0.2, n_agents=3).emit_patches(
        state,
        jax.random.PRNGKey(0),
        target_mask=jnp.array([True, True, False], dtype=jnp.bool_),
    )
    next_state = apply_patch_map(
        state,
        patches,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        default_node_id="fry03-income-tax",
    )

    assert next_state.agents.income.tolist() == [80.0, 40.0, 25.0]
    assert float(next_state.government_balance) == 30.0
    assert not bool(jnp.array_equal(next_key, jax.random.PRNGKey(0)))


def test_relocated_labor_kernel_preserves_employer_and_firm_counts() -> None:
    """Equivalent labor relocation preserves masked employer and count patches."""
    labor = _canonical_module("labor")
    state = _state()
    target_mask = jnp.array([True, False, True, True], dtype=jnp.bool_)
    legacy_patches, legacy_key = legacy_labor.LaborMarketMechanism(
        employment_threshold=1.0
    ).emit_patches(state, jax.random.PRNGKey(23), target_mask=target_mask)
    canonical_patches, canonical_key = labor.LaborMarketMechanism(
        employment_threshold=1.0
    ).emit_patches(state, jax.random.PRNGKey(23), target_mask=target_mask)

    _assert_patch_maps_equal(legacy_patches, canonical_patches)
    np.testing.assert_array_equal(np.asarray(legacy_key), np.asarray(canonical_key))
    assert canonical_patches["agents.employer_id"][0]["value"].shape == (4,)
    assert canonical_patches["firms.labor_count"][0]["value"].shape == (2,)


def test_canonical_fiscal_kernel_supports_jit_and_gradient() -> None:
    """The relocated numeric kernel remains differentiable on the tiny N path."""
    fiscal = _canonical_module("fiscal")
    state = _state(n_agents=3, n_firms=1)

    jit_tax = jax.jit(lambda rate: fiscal.compute_tax(state, rate))
    np.testing.assert_allclose(np.asarray(jit_tax(jnp.array(0.2))), [20.0, 10.0, 0.0])
    gradient = jax.grad(lambda rate: jnp.sum(fiscal.compute_tax(state, rate)))(jnp.array(0.2))
    assert float(gradient) == pytest.approx(150.0)

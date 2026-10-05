"""FRY-03 witnesses for the canonical fiscal/labor execution owner."""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping
from decimal import Decimal
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
    assert (
        type(create_mechanism_from_spec("labor_market", {"employment_threshold": 0.5}, 4, 2))
        is package.LaborMarketMechanism
    )


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
    assert bool(jnp.array_equal(next_key, jax.random.PRNGKey(0)))


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


@pytest.mark.parametrize(
    ("mechanism_type", "params", "expected_income", "expected_balance"),
    [
        ("income_tax", {"rate": 0.2}, [80.0, 50.0, 25.0, 64.0], 36.0),
        ("tax_subsidy", {"rate": 0.1}, [110.0, 50.0, 25.0, 88.0], -18.0),
        ("labor_market", {"employment_threshold": 0.0}, [0.0, 50.0, 25.0, 0.0], 0.0),
    ],
)
def test_registered_adapter_json_patches_require_a_native_consumer_bridge(
    mechanism_type: str,
    params: dict[str, float],
    expected_income: list[float],
    expected_balance: float,
) -> None:
    """Diagnostic JSON retains effects but is not the native PatchMap ABI."""
    from polisyos.foundry.methods.catalog.mechanism._registry_boot import (
        register_mechanism_methods,
    )
    from polisyos.foundry.methods.components.merge_engine import MergeConflictError
    from polisyos.foundry.methods.registry import registry_scope

    state = _state()
    with registry_scope() as registry:
        for method_class in register_mechanism_methods():
            registry.register(method_class)
        method = registry.get(f"mechanism.runtime.{mechanism_type}@1.0.0")
        result = method.pure_step(
            state, {**params, "target_mask": [True, False, True, True], "__seed__": 23}
        )
    # A real serialized boundary, rather than passing the producer's JAX objects.
    patches = json.loads(json.dumps(result))["result"]["patches"]
    projected_income = np.asarray(state.agents.income) + np.asarray(
        patches["agents.income"][0]["delta"]
    )
    np.testing.assert_allclose(projected_income, expected_income)
    projected_balance = float(state.government_balance) + float(
        patches.get("government.balance", [{"delta": 0.0}])[0]["delta"]
    )
    assert projected_balance == pytest.approx(expected_balance)
    # Presence of a registered method and JSON "patches" is a cheap proxy for
    # consumer compatibility: list deltas require a real materialization bridge.
    with pytest.raises(MergeConflictError, match=r"ArrayImpl.*list"):
        apply_patch_map(
            state,
            patches,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            default_node_id="economic-runtime-consumer",
        )
    if mechanism_type != "labor_market":
        before = float(jnp.sum(state.agents.income) + state.government_balance)
        after = float(np.sum(projected_income) + projected_balance)
        assert after == pytest.approx(before)
    else:
        assert patches["agents.is_employed"][0]["value"] == [False, True, True, False]
        assert patches["agents.employer_id"][0]["value"] == [-1, 0, 1, -1]
        assert patches["firms.labor_count"][0]["value"] == [1, 0]


def test_labor_masked_counts_and_key_have_independent_oracle() -> None:
    """An unselected incumbent counts, while an inactive incumbent does not."""
    labor = _canonical_module("labor")
    state = _state(n_firms=1)
    key = jax.random.PRNGKey(23)
    patches, next_key = labor.LaborMarketMechanism(employment_threshold=1.0).emit_patches(
        state, key, target_mask=jnp.array([True, False, True, True], dtype=jnp.bool_)
    )
    consumed = apply_patch_map(
        state,
        patches,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        default_node_id="masked-labor-oracle",
    )
    np.testing.assert_allclose(consumed.agents.income, [20.0, 50.0, 25.0, 40.0])
    assert consumed.agents.employer_id.tolist() == [0, 0, 1, 0]
    assert consumed.agents.is_employed.tolist() == [True, True, True, True]
    assert consumed.firms.labor_count.tolist() == [3.0]
    np.testing.assert_array_equal(next_key, jax.random.split(key, 3)[2])


@pytest.mark.parametrize(
    ("mechanism_type", "params", "expected_income", "expected_balance"),
    [
        ("income_tax", {"rate": Decimal("0.2")}, [80.0, 40.0, 25.0, 64.0], 46.0),
        ("tax_subsidy", {"rate": Decimal("0.1")}, [110.0, 55.0, 25.0, 88.0], -23.0),
        ("labor_market", {"employment_threshold": Decimal("0")}, [0.0, 0.0, 25.0, 0.0], 0.0),
    ],
)
def test_compiled_baseline_plan_persists_replayable_effects(
    tmp_path,
    mechanism_type: str,
    params: dict[str, Decimal],
    expected_income: list[float],
    expected_balance: float,
) -> None:
    """Trinity compilation and native replay must agree on consumed state effects."""
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.contracts.foundry import CompileRequest
    from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
    from polisyos.foundry.compile.api import compile as compile_foundry
    from polisyos.foundry.execute.executor import (
        apply_state_delta_and_snapshot,
        execute_program_graph,
        load_state_snapshot,
    )
    from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.governance.schedule import ScheduleSpec
    from polisyos.ir.governance.selector_expr import SelectorPredicate
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import SelectorOperator
    from polisyos.ir.trinity import TrinityBundle

    store = FileSystemCAS(tmp_path)
    registries = build_default_registry_bundle(store)
    content = load_registry_bundle_content(store, registries.bundle_ref)
    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="baseline_fixture", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="baseline_fixture",
            interventions=[
                InterventionSpec(
                    intervention_id="baseline",
                    kind=mechanism_type,
                    target=SelectorPredicate(
                        field="id", operator=SelectorOperator.EQUALS, value="all"
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params=params,
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="baseline_fixture",
            data_snapshot_ref="sha256:" + "0" * 64,
            registry_bundle_ref=str(registries.bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        policy,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=policy.schema_version),
        ),
    )
    compiled = compile_foundry(
        store, CompileRequest(policy_ref=policy_ref, registry_bundle_ref=registries.bundle_ref)
    )
    assert compiled.ok, compiled.notes
    assert compiled.exec_plan_ref is not None
    program_ref = next(item.ref for item in compiled.derived_refs if item.role == "program_graph")
    state = _state()
    delta_ids = []
    for _ in range(2):
        executed = execute_program_graph(
            store,
            program_ref=program_ref,
            exec_plan_ref=compiled.exec_plan_ref,
            base_state=state,
            mechanism_registry=content.mechanism_registry,
            slot_registry=content.slot_registry,
            merge_registry=content.merge_registry,
            seed=23,
            welfare_bound_mode="off",
        )
        assert not executed.failure_cards
        delta_ids.append(executed.state_delta_ref.artifact_id)
        _, applied = apply_state_delta_and_snapshot(
            store,
            base_state=state,
            state_delta_ref=executed.state_delta_ref,
            slot_registry=content.slot_registry,
            merge_registry=content.merge_registry,
        )
        reopened = load_state_snapshot(store, snapshot_ref=applied.state_snapshot_ref)
        np.testing.assert_allclose(reopened.agents.income, expected_income)
        assert float(reopened.government_balance) == pytest.approx(expected_balance)
        if mechanism_type == "labor_market":
            assert reopened.firms.labor_count.tolist() == [0.0, 0.0]
            assert reopened.agents.employer_id.tolist() == [-1, -1, 1, -1]
    assert delta_ids[0] == delta_ids[1]

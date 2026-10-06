"""Registered baseline kernels survive real spec/compiler/CAS execution replay."""

from __future__ import annotations

from decimal import Decimal

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteRequest,
    FoundryExecConfig,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry._registry import create_mechanism_from_spec, get_mechanism_descriptor
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import (
    apply_patch_map,
    load_state_snapshot,
    put_state_snapshot,
)
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle


@pytest.mark.parametrize(
    "kind,params",
    [
        ("income_tax", {"rate": Decimal("0.25")}),
        ("tax_subsidy", {"rate": Decimal("0.25")}),
        ("labor_market", {"employment_threshold": Decimal("0.5")}),
    ],
)
def test_live_baseline_spec_compiler_and_fresh_cas_replay_match_complete_patch_state(
    tmp_path, kind, params
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    bundle = build_default_registry_bundle(store)
    registry = load_registry_bundle_content(store, bundle.bundle_ref)
    policy = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="baseline", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="baseline",
            interventions=[
                {
                    "intervention_id": "baseline",
                    "kind": kind,
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": "==",
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": params,
                }
            ],
        ),
        model_spec=ModelSpec(
            model_id="baseline",
            data_snapshot_ref="sha256:" + "0" * 64,
            registry_bundle_ref=str(bundle.bundle_ref.artifact_id),
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
        store,
        CompileRequest(
            input_kind="trinity", policy_ref=policy_ref, registry_bundle_ref=bundle.bundle_ref
        ),
    )
    assert compiled.ok
    descriptor = get_mechanism_descriptor(kind)
    assert descriptor.mechanism_class_path.startswith("polisyos.foundry.execute.mechanisms:")
    state = GlobalState.empty(n_agents=8, n_firms=2)
    state = state.replace(
        agents=state.agents.replace(
            active=jnp.asarray([True, True, False, True] * 2),
            income=jnp.asarray([80.0, 40.0, 20.0, 100.0] * 2),
            reported_income=jnp.asarray([40.0, 20.0, 10.0, 60.0] * 2),
        ),
        firms=state.firms.replace(wage_offer=jnp.asarray([20.0, 30.0])),
        government_balance=jnp.asarray(17.0),
    )
    original_snapshot = put_state_snapshot(store, state=state, step=0)
    state_ref = StateSnapshotRef(artifact_id=original_snapshot.artifact_id)
    data_ref = store.put_json(
        DataSnapshot(data_ref=state_ref),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    binding = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_ref,
            registry_bundle_ref=bundle.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_ref,
        ),
        PutOptions(kind="foundry.input_bindings", media_type="application/json"),
    )
    request = ExecuteRequest(
        exec_plan_ref=compiled.exec_plan_ref,
        input_bindings_ref=FoundryInputBindingsRef(artifact_id=binding.artifact_id),
        registry_bundle_ref=bundle.bundle_ref,
        exec_config=FoundryExecConfig(seed=27),
    )
    # Historical baseline executor splits the request key once before this kernel.
    _, kernel_key = jax.random.split(jax.random.PRNGKey(27))
    mechanism = create_mechanism_from_spec(kind, dict(params), 8, 2)
    patch, next_key = mechanism.emit_patches(state, kernel_key, target_mask=jnp.ones(8, dtype=bool))
    expected = apply_patch_map(
        state,
        patch,
        slot_registry=registry.slot_registry,
        merge_registry=registry.merge_registry,
        default_node_id="baseline",
    )
    first = execute_foundry(store, request)
    repeated = execute_foundry(FileSystemCAS(tmp_path / "cas"), request)
    assert first.ok and repeated.ok
    reopened = FileSystemCAS(tmp_path / "cas")
    for output in [first, repeated]:
        result = SimulationResult.model_validate(
            from_canonical_bytes(reopened.get_bytes(output.simulation_result_ref))
        )
        readback = load_state_snapshot(reopened, snapshot_ref=result.state_snapshot_ref)
        actual_leaves, actual_tree = jax.tree_util.tree_flatten(readback)
        expected_leaves, expected_tree = jax.tree_util.tree_flatten(expected)
        assert actual_tree == expected_tree
        for actual, oracle in zip(actual_leaves, expected_leaves, strict=True):
            np.testing.assert_array_equal(actual, oracle)
    oracle_key = jax.random.split(kernel_key, 3)[2] if kind == "labor_market" else kernel_key
    np.testing.assert_array_equal(next_key, oracle_key)

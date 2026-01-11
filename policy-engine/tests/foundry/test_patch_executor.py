from __future__ import annotations

from decimal import Decimal

import pytest
import jax.numpy as jnp
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import Metrics, StateDelta
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compiler import compile_surface_policy
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.executor import (
    apply_state_delta_and_snapshot,
    execute_program_graph,
    load_state_snapshot,
)
from polisyos.ir.surface import PolicySemantic, PolicySurfaceIR
from polisyos.ir.types import SelectorOperator


def test_patch_executor_emits_artifacts(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    registries = load_registry_bundle_content(store, bundle.bundle_ref)

    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            interventions=[
                {
                    "intervention_id": "tax_cut",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": Decimal("0.1")},
                }
            ],
        )
    )

    artifacts = compile_surface_policy(
        store,
        policy,
        mechanism_registry=registries.mechanism_registry,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
    )

    base_state = GlobalState.empty(n_agents=4, n_firms=2)
    base_state = base_state.replace(
        agents=base_state.agents.replace(income=jnp.ones(4, dtype=jnp.float32) * 1000.0)
    )
    exec_artifacts = execute_program_graph(
        store,
        program_ref=artifacts.program_ref,
        exec_plan_ref=artifacts.exec_plan_ref,
        base_state=base_state,
        mechanism_registry=registries.mechanism_registry,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        step=0,
    )

    assert store.has(exec_artifacts.state_delta_ref.artifact_id)
    assert store.has(exec_artifacts.metrics_ref.artifact_id)

    delta_payload = from_canonical_bytes(
        store.get_bytes(exec_artifacts.state_delta_ref.artifact_id)
    )
    state_delta = StateDelta.model_validate(delta_payload)
    assert state_delta.ops
    for op in state_delta.ops:
        assert op.value_ref is not None
        assert store.has(op.value_ref.artifact_id)
        manifest = store.get_manifest(op.value_ref.artifact_id)
        assert manifest.media_type == "application/x-npy"

    metrics_payload = from_canonical_bytes(store.get_bytes(exec_artifacts.metrics_ref.artifact_id))
    metrics = Metrics.model_validate(metrics_payload)
    assert metrics.values.get("applied_nodes") == 1

    next_state, applied = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        step=0,
    )

    assert store.has(applied.state_snapshot_ref.artifact_id)
    assert float(jnp.mean(next_state.agents.income)) < float(jnp.mean(base_state.agents.income))

    loaded_bytes = store.get_bytes(applied.state_snapshot_ref.artifact_id)
    assert loaded_bytes


def test_patch_executor_respects_target_mask(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    registries = load_registry_bundle_content(store, bundle.bundle_ref)

    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            interventions=[
                {
                    "intervention_id": "tax_cut",
                    "kind": "income_tax",
                    "target": {
                        "kind": "predicate",
                        "field": "income",
                        "operator": SelectorOperator.LESS_THAN,
                        "value": "1000",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": Decimal("0.1")},
                }
            ],
        )
    )

    artifacts = compile_surface_policy(
        store,
        policy,
        mechanism_registry=registries.mechanism_registry,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        units_registry=registries.units_registry,
    )

    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    base_state = base_state.replace(
        agents=base_state.agents.replace(income=jnp.array([500.0, 2000.0], dtype=jnp.float32))
    )

    exec_artifacts = execute_program_graph(
        store,
        program_ref=artifacts.program_ref,
        exec_plan_ref=artifacts.exec_plan_ref,
        base_state=base_state,
        mechanism_registry=registries.mechanism_registry,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        selector_field_registry=registries.selector_field_registry,
        step=0,
    )

    next_state, _ = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        step=0,
    )

    assert float(next_state.agents.income[0]) == 450.0
    assert float(next_state.agents.income[1]) == 2000.0


def test_tax_subsidy_emits_patches_with_mask(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    registries = load_registry_bundle_content(store, bundle.bundle_ref)

    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            interventions=[
                {
                    "intervention_id": "subsidy",
                    "kind": "tax_subsidy",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.LESS_THAN,
                        "value": 1,
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": Decimal("0.1")},
                }
            ],
        )
    )

    artifacts = compile_surface_policy(
        store,
        policy,
        mechanism_registry=registries.mechanism_registry,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        units_registry=registries.units_registry,
    )

    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    base_state = base_state.replace(
        agents=base_state.agents.replace(income=jnp.array([1000.0, 2000.0], dtype=jnp.float32))
    )

    exec_artifacts = execute_program_graph(
        store,
        program_ref=artifacts.program_ref,
        exec_plan_ref=artifacts.exec_plan_ref,
        base_state=base_state,
        mechanism_registry=registries.mechanism_registry,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        selector_field_registry=registries.selector_field_registry,
        step=0,
    )

    next_state, _ = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        step=0,
    )

    assert float(next_state.agents.income[0]) == pytest.approx(1100.0)
    assert float(next_state.agents.income[1]) == pytest.approx(2000.0)
    assert float(next_state.government_balance) == pytest.approx(-100.0)

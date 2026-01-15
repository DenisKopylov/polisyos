import jax
import jax.numpy as jnp
import pytest
from decimal import Decimal

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compiler import compile_surface_policy
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.executor import apply_state_delta_and_snapshot, execute_program_graph
from polisyos.ir.surface import PolicySemantic, PolicySurfaceIR
from polisyos.ir.types import SelectorOperator


def test_compile_surface_policy_roundtrip_rate(tmp_path) -> None:
    """
    Surface IR smoke-test:
    PolicySurfaceIR -> foundry compile -> foundry execute -> apply patches to GlobalState.
    """

    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    registries = load_registry_bundle_content(store, bundle.bundle_ref)

    policy = PolicySurfaceIR(
        semantic=PolicySemantic(
            context_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            interventions=[
                {
                    "intervention_id": "subsidy_2025",
                    "kind": "tax_subsidy",
                    "target": {
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    "schedule": {"start_step": 0, "duration_steps": 1},
                    "params": {"rate": Decimal("0.15")},
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

    n_agents = 100
    base_state = GlobalState.empty(n_agents=n_agents, n_firms=5)
    base_state = base_state.replace(
        agents=base_state.agents.replace(income=jnp.ones(n_agents, dtype=jnp.float32) * 1000.0)
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
        seed=0,
    )

    next_state, _ = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=registries.slot_registry,
        merge_registry=registries.merge_registry,
        step=0,
    )

    avg_income = jnp.mean(next_state.agents.income)
    assert float(avg_income) == pytest.approx(1150.0, abs=1e-3)

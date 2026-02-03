from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import CompileRequest, ExecuteRequest, StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.compiler import put_policy_surface
from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.executor import put_state_snapshot
from polisyos.ir.surface import PolicySemantic, PolicySurfaceIR
from polisyos.ir.types import SelectorOperator


def test_execute_facade_smoke(tmp_path) -> None:
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

    policy_ref = put_policy_surface(
        store,
        policy,
        mechanism_registry=registries.mechanism_registry,
        units_registry=registries.units_registry,
    )
    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="surface",
            policy_ref=policy_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )
    assert compile_result.ok
    assert compile_result.exec_plan_ref is not None

    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    snapshot_ref = put_state_snapshot(store, state=base_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref.artifact_id)

    exec_result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=compile_result.exec_plan_ref,
            state_snapshot_ref=state_snapshot_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )
    assert exec_result.ok is True
    assert exec_result.simulation_result_ref is not None
    assert exec_result.simulation_result_ref.kind == "foundry.simulation_result"

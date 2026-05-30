from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteRequest,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_layer.types import SelectorOperator


def _compile_exec_plan(store: FileSystemCAS):
    registry_bundle = build_default_registry_bundle(store)
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="p8_execute", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_input_bindings",
            interventions=[
                InterventionSpec(
                    intervention_id="cut",
                    kind="income_tax",
                    target=SelectorPredicate(
                        field="id",
                        operator=SelectorOperator.EQUALS,
                        value="all",
                    ),
                    schedule=ScheduleSpec(start_step=0, duration_steps=1),
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_input_bindings",
            data_snapshot_ref="sha256:" + ("0" * 64),
            registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
        ),
    )
    trinity_ref = store.put_json(
        trinity,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity.schema_version),
        ),
    )
    compile_result = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=trinity_ref,
            registry_bundle_ref=registry_bundle.bundle_ref,
        ),
    )
    assert compile_result.ok
    assert compile_result.exec_plan_ref is not None
    return compile_result.exec_plan_ref, registry_bundle.bundle_ref


def test_execute_supports_input_bindings_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    exec_plan_ref, registry_bundle_ref = _compile_exec_plan(store)

    base_state = GlobalState.empty(n_agents=4, n_firms=2)
    state_snapshot_ref = put_state_snapshot(store, state=base_state, step=0)

    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=StateSnapshotRef(artifact_id=state_snapshot_ref.artifact_id)),
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
    )
    input_bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle_ref,
            rules=[],
            bound_state_snapshot_ref=StateSnapshotRef(artifact_id=state_snapshot_ref.artifact_id),
        ),
        PutOptions(
            kind="foundry.input_bindings",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.FoundryInputBindings", version="1.0"),
        ),
    )

    result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=input_bindings_ref.artifact_id),
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    assert result.ok
    assert result.simulation_result_ref is not None
    assert any(note == "state_source:input_bindings_ref" for note in result.notes)

from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_SIMULATION_RESULT_REF,
    INPUT_INPUT_BINDINGS_REF,
)
from polisyos.scientist.orchestration.workflows.builder import run_default_workflow


def _put_data_snapshot(
    store: FileSystemCAS, state_snapshot_ref: StateSnapshotRef
) -> DataSnapshotRef:
    snapshot = DataSnapshot(data_ref=state_snapshot_ref)
    ref = store.put_json(
        snapshot,
        PutOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
        ),
    )
    return DataSnapshotRef(artifact_id=ref.artifact_id)


def test_engine_default_workflow_p8_wires_bindings_and_pre_sim_gate(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry_bundle = build_default_registry_bundle(store)

    base_state = GlobalState.empty(n_agents=6, n_firms=2)
    snapshot_ref_payload = put_state_snapshot(store, state=base_state, step=0)
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref_payload.artifact_id)
    data_snapshot_ref = _put_data_snapshot(store, state_snapshot_ref)

    trinity_bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_p8", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_p8",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
                    kind="income_tax",
                    target={
                        "kind": "predicate",
                        "field": "id",
                        "operator": SelectorOperator.EQUALS,
                        "value": "all",
                    },
                    schedule={"start_step": 0, "duration_steps": 1},
                    params={"rate": Decimal("0.1")},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="model_p8",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
        ),
    )
    trinity_ref_payload = store.put_json(
        trinity_bundle,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.TrinityBundle", version=trinity_bundle.schema_version
            ),
        ),
    )

    state = ExperimentState(
        run_id="R_p8_default",
        inputs={
            "trinity_bundle_ref": trinity_ref_payload,
            "registry_bundle_ref": registry_bundle.bundle_ref,
            "data_snapshot_ref": data_snapshot_ref,
        },
    )

    result = run_default_workflow(state, store=store, foundry=DefaultFoundryPort())

    assert INPUT_INPUT_BINDINGS_REF in result.state.inputs
    assert result.state.inputs[INPUT_INPUT_BINDINGS_REF].kind == "foundry.input_bindings"
    assert result.state.params.get("data_plane_gate_profile") is not None

    workflow_nodes = {record.alias: record.status for record in result.report.nodes}
    assert workflow_nodes.get("bind_foundry_inputs") == "ok"
    assert workflow_nodes.get("run_data_plane_gate") == "ok"

    sim_ref = result.state.artifacts_index.get(ARTIFACT_SIMULATION_RESULT_REF)
    assert sim_ref is not None
    sim_manifest = store.get_manifest(sim_ref.artifact_id)
    roles = {item.role for item in sim_manifest.inputs}
    assert "input.input_bindings_ref" in roles

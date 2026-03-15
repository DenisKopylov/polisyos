from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    FoundryInputBindings,
    StateSnapshotRef,
)
from polisyos.runtime.replay import completeness_check


def _put_json(store: FileSystemCAS, payload, *, kind: str):
    return store.put_json(payload, PutOptions(kind=kind, media_type="application/json"))


def _base_payload(store: FileSystemCAS):
    registry_ref = _put_json(store, {"registry": {}}, kind="core.registry_bundle")
    trinity_ref = _put_json(store, {"trinity": {}}, kind="ir.trinity_bundle")
    lowered_ir_ref = _put_json(
        store,
        {"policy_fidelity_level": "hybrid", "constraint_mode": "hard_soft_v1"},
        kind="foundry.lowered_ir",
    )
    program_graph_ref = _put_json(
        store,
        {"nodes": [], "edges": [], "entrypoints": [], "lowered_ir_ref": str(lowered_ir_ref.artifact_id)},
        kind="foundry.program_graph",
    )
    state_snapshot_ref = _put_json(store, {"state": {}}, kind="foundry.state_snapshot")
    data_snapshot_ref = _put_json(
        store,
        DataSnapshot(data_ref=StateSnapshotRef(artifact_id=state_snapshot_ref.artifact_id)),
        kind="fabric.data_snapshot",
    )
    exec_plan_ref = _put_json(
        store,
        {
            "program_ref": {
                "artifact_id": str(program_graph_ref.artifact_id),
                "kind": "foundry.program_graph",
                "media_type": "application/json",
            },
            "order": [],
            "policy_fidelity_level": "hybrid",
            "constraint_mode": "hard_soft_v1",
        },
        kind="foundry.exec_plan",
    )
    simulation_result_ref = _put_json(
        store,
        {"metrics_ref": str(exec_plan_ref.artifact_id)},
        kind="foundry.simulation_result",
    )
    return {
        "schema_version": "3.1",
        "run_id": "R_replay_input_bindings",
        "seed": 1,
        "inputs": {
            "trinity_bundle_ref": str(trinity_ref.artifact_id),
            "registry_bundle_ref": str(registry_ref.artifact_id),
            "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
        },
        "artifacts": {
            "exec_plan_ref": str(exec_plan_ref.artifact_id),
            "lowered_ir_ref": str(lowered_ir_ref.artifact_id),
            "simulation_result_ref": str(simulation_result_ref.artifact_id),
        },
        "_refs": {
            "registry_ref": registry_ref,
            "data_snapshot_ref": data_snapshot_ref,
            "state_snapshot_ref": state_snapshot_ref,
            "lowered_ir_ref": lowered_ir_ref,
        },
    }


def test_replay_completeness_requires_input_bindings_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload = _base_payload(store)
    packet_ref = _put_json(store, {k: v for k, v in payload.items() if k != "_refs"}, kind="scientist.decision_packet")

    report = completeness_check(store, packet_ref.artifact_id)

    assert report.level.value == "incomplete"
    assert "missing_required_role:input.input_bindings_ref" in report.reason_codes


def test_replay_completeness_accepts_packet_with_input_bindings_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload = _base_payload(store)
    refs = payload["_refs"]
    input_bindings_ref = _put_json(
        store,
        FoundryInputBindings(
            data_snapshot_ref=refs["data_snapshot_ref"],
            registry_bundle_ref=refs["registry_ref"],
            rules=[],
            bound_state_snapshot_ref=StateSnapshotRef(
                artifact_id=refs["state_snapshot_ref"].artifact_id
            ),
        ),
        kind="foundry.input_bindings",
    )
    packet_payload = {k: v for k, v in payload.items() if k != "_refs"}
    packet_payload["inputs"]["input_bindings_ref"] = str(input_bindings_ref.artifact_id)
    packet_ref = _put_json(store, packet_payload, kind="scientist.decision_packet")

    report = completeness_check(store, packet_ref.artifact_id)

    assert report.level.value == "complete"
    assert report.ok


def test_replay_completeness_requires_lowered_ir_ref(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    payload = _base_payload(store)
    packet_payload = {k: v for k, v in payload.items() if k != "_refs"}
    packet_payload["artifacts"].pop("lowered_ir_ref", None)
    packet_ref = _put_json(store, packet_payload, kind="scientist.decision_packet")

    report = completeness_check(store, packet_ref.artifact_id)

    assert report.level.value == "incomplete"
    assert "missing_required_role:artifact.lowered_ir_ref" in report.reason_codes

from __future__ import annotations

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ExecPlanRef,
    FoundryInputBindings,
    Metrics,
    MetricsRef,
    ProgramGraphRef,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.runtime.replay import VerificationConfig, VerificationMode
from polisyos.scientist.replay_backend import replay_packet


def _put_json(store: FileSystemCAS, payload, *, kind: str):
    return store.put_json(payload, PutOptions(kind=kind, media_type="application/json"))


def _build_packet(store: FileSystemCAS):
    registry_bundle_ref = _put_json(store, {"registry": {}}, kind="core.registry_bundle")
    trinity_bundle_ref = _put_json(store, {"trinity": {}}, kind="ir.trinity_bundle")
    state_snapshot_ref = _put_json(store, {"state": {}}, kind="foundry.state_snapshot")
    data_snapshot = DataSnapshot(
        data_ref=StateSnapshotRef(artifact_id=state_snapshot_ref.artifact_id),
    )
    data_snapshot_ref = _put_json(store, data_snapshot, kind="fabric.data_snapshot")
    input_bindings = FoundryInputBindings(
        data_snapshot_ref=data_snapshot_ref,
        registry_bundle_ref=registry_bundle_ref,
        rules=[],
        bound_state_snapshot_ref=StateSnapshotRef(artifact_id=state_snapshot_ref.artifact_id),
    )
    input_bindings_ref = _put_json(store, input_bindings, kind="foundry.input_bindings")
    program_graph_ref = _put_json(store, {"nodes": []}, kind="foundry.program_graph")
    exec_plan = ExecPlan(
        program_ref=ProgramGraphRef(artifact_id=program_graph_ref.artifact_id),
        order=[],
        random_seed=123,
    )
    exec_plan_ref = _put_json(store, exec_plan, kind="foundry.exec_plan")
    metrics_ref = _put_json(
        store,
        Metrics(values={"applied_nodes": 1, "status": "ok"}),
        kind="foundry.metrics",
    )
    simulation_result = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
    )
    simulation_result_ref = _put_json(
        store,
        simulation_result,
        kind="foundry.simulation_result",
    )
    packet_payload = {
        "schema_version": "3.0",
        "run_id": "R_replay_backend",
        "seed": 123,
        "inputs": {
            "trinity_bundle_ref": str(trinity_bundle_ref.artifact_id),
            "input_bindings_ref": str(input_bindings_ref.artifact_id),
            "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
            "registry_bundle_ref": str(registry_bundle_ref.artifact_id),
        },
        "artifacts": {
            "exec_plan_ref": str(exec_plan_ref.artifact_id),
            "simulation_result_ref": str(simulation_result_ref.artifact_id),
            "metrics_ref": str(metrics_ref.artifact_id),
        },
    }
    packet_ref = _put_json(store, packet_payload, kind="scientist.decision_packet")
    return packet_ref, simulation_result_ref


def test_replay_backend_foundry_strategy_with_bit_exact(monkeypatch, tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    packet_ref, simulation_result_ref = _build_packet(store)

    def _fake_execute_foundry_replay(*, store, payload, seed):  # noqa: ANN001
        return simulation_result_ref.artifact_id

    monkeypatch.setattr(
        "polisyos.scientist.replay_backend._execute_foundry_replay",
        _fake_execute_foundry_replay,
    )

    result = replay_packet(
        store,
        packet_ref.artifact_id,
        verify=True,
        verification_config=VerificationConfig(mode=VerificationMode.BIT_EXACT),
    )

    assert result.success
    assert result.strategy.value == "foundry"
    assert result.verification is not None
    assert result.verification.passed

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
from polisyos.runtime.replay import (
    VerificationConfig,
    VerificationMode,
    completeness_check,
    verify_replay,
)


def _put_json(store: FileSystemCAS, payload, *, kind: str):
    return store.put_json(payload, PutOptions(kind=kind, media_type="application/json"))


def _build_packet_fixture(store: FileSystemCAS):
    registry_bundle_ref = _put_json(store, {"registry": {}}, kind="core.registry_bundle")
    trinity_bundle_ref = _put_json(store, {"trinity": {}}, kind="ir.trinity_bundle")
    lowered_ir_ref = _put_json(
        store,
        {"policy_fidelity_level": "hybrid", "constraint_mode": "hard_soft_v1"},
        kind="foundry.lowered_ir",
    )
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
    program_graph_ref = _put_json(
        store,
        {
            "nodes": [],
            "edges": [],
            "entrypoints": [],
            "lowered_ir_ref": str(lowered_ir_ref.artifact_id),
        },
        kind="foundry.program_graph",
    )
    exec_plan = ExecPlan(
        program_ref=ProgramGraphRef(artifact_id=program_graph_ref.artifact_id),
        order=[],
        random_seed=123,
    )
    exec_plan_ref = _put_json(store, exec_plan, kind="foundry.exec_plan")
    metrics = Metrics(values={"applied_nodes": 1, "status": "ok"})
    metrics_ref = _put_json(store, metrics, kind="foundry.metrics")
    sim_result = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics_ref.artifact_id),
        state_snapshot_ref=StateSnapshotRef(artifact_id=state_snapshot_ref.artifact_id),
    )
    simulation_result_ref = _put_json(store, sim_result, kind="foundry.simulation_result")

    packet_payload = {
        "schema_version": "3.0",
        "run_id": "R_packet_runtime_test",
        "seed": 123,
        "inputs": {
            "trinity_bundle_ref": str(trinity_bundle_ref.artifact_id),
            "input_bindings_ref": str(input_bindings_ref.artifact_id),
            "data_snapshot_ref": str(data_snapshot_ref.artifact_id),
            "registry_bundle_ref": str(registry_bundle_ref.artifact_id),
        },
        "artifacts": {
            "exec_plan_ref": str(exec_plan_ref.artifact_id),
            "lowered_ir_ref": str(lowered_ir_ref.artifact_id),
            "simulation_result_ref": str(simulation_result_ref.artifact_id),
            "metrics_ref": str(metrics_ref.artifact_id),
        },
    }
    packet_ref = _put_json(store, packet_payload, kind="scientist.decision_packet")
    return packet_ref, packet_payload, simulation_result_ref


def test_completeness_check_detects_foundry_strategy(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    packet_ref, _, _ = _build_packet_fixture(store)

    report = completeness_check(store, packet_ref.artifact_id)

    assert report.strategy.value == "foundry"
    assert report.level.value == "complete"
    assert report.ok


def test_verify_replay_bit_exact_passes_for_same_simulation_result(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    _, packet_payload, simulation_result_ref = _build_packet_fixture(store)

    result = verify_replay(
        store,
        original_payload=packet_payload,
        replay_simulation_ref=simulation_result_ref.artifact_id,
        config=VerificationConfig(mode=VerificationMode.BIT_EXACT),
    )

    assert result.passed
    assert result.mode == VerificationMode.BIT_EXACT


def test_verify_replay_ci_bounded_detects_metric_drift(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    _, packet_payload, simulation_result_ref = _build_packet_fixture(store)

    replay_metrics = Metrics(values={"applied_nodes": 100, "status": "ok"})
    replay_metrics_ref = _put_json(store, replay_metrics, kind="foundry.metrics")
    replay_sim_result = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=simulation_result_ref.artifact_id),
        metrics_ref=MetricsRef(artifact_id=replay_metrics_ref.artifact_id),
    )
    replay_sim_ref = _put_json(store, replay_sim_result, kind="foundry.simulation_result")

    result = verify_replay(
        store,
        original_payload=packet_payload,
        replay_simulation_ref=replay_sim_ref.artifact_id,
        config=VerificationConfig(mode=VerificationMode.CI_BOUNDED, relative_tolerance=0.01),
    )

    assert not result.passed
    assert result.mode == VerificationMode.CI_BOUNDED
    assert "applied_nodes" in result.details.get("mismatches", {})

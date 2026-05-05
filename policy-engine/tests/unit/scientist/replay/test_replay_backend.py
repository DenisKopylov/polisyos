from __future__ import annotations

import logging

import pytest
from polisyos.core.artifacts.manifest import ArtifactRef
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
from polisyos.core.run.context import RunContext
from polisyos.runtime.replay import VerificationConfig, VerificationMode
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeOutcome
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.replay.backend import (
    list_dead_letters,
    load_dead_letter,
    replay_dead_letter,
    replay_packet,
)


class _ArtifactStoreProxy:
    def __init__(self, store: FileSystemCAS) -> None:
        self._store = store

    def __getattr__(self, name: str):
        return getattr(self._store, name)


def _put_json(store: FileSystemCAS, payload, *, kind: str):
    return store.put_json(payload, PutOptions(kind=kind, media_type="application/json"))


def _build_packet(store: FileSystemCAS):
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
            "lowered_ir_ref": str(lowered_ir_ref.artifact_id),
            "simulation_result_ref": str(simulation_result_ref.artifact_id),
            "metrics_ref": str(metrics_ref.artifact_id),
        },
    }
    packet_ref = _put_json(store, packet_payload, kind="scientist.decision_packet")
    return packet_ref, simulation_result_ref


def _put_dead_letter(
    store: FileSystemCAS,
    *,
    run_id: str = "R_dead",
    alias: str = "agent",
    node_id: str = "test.node@1.0.0",
):
    return _put_json(
        store,
        {
            "kind": "scientist.dead_letter",
            "run_id": run_id,
            "alias": alias,
            "node_id": node_id,
            "error_type": "RuntimeError",
            "error_message": "boom",
            "attempts": 2,
            "policy": {"max_retries": 0},
            "created_at": "2026-04-11T12:00:00Z",
        },
        kind="scientist.dead_letter",
    )


def test_replay_backend_foundry_strategy_with_bit_exact(monkeypatch, tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    packet_ref, simulation_result_ref = _build_packet(store)

    def _fake_execute_foundry_replay(*, store, payload, seed):
        return simulation_result_ref.artifact_id

    monkeypatch.setattr(
        "polisyos.scientist.replay.backend._execute_foundry_replay",
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


def test_list_dead_letters_filters_by_run_and_alias(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    keep_ref = _put_dead_letter(store, run_id="R_keep", alias="agent")
    _put_dead_letter(store, run_id="R_drop", alias="search")

    records = list_dead_letters(store, run_id="R_keep", alias="agent")

    assert len(records) == 1
    assert records[0].artifact_ref.artifact_id == keep_ref.artifact_id
    assert records[0].run_id == "R_keep"


def test_load_dead_letter_returns_typed_record(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    dead_ref = _put_dead_letter(store, run_id="R_dead_record")

    record = load_dead_letter(store, dead_ref.artifact_id)

    assert record.run_id == "R_dead_record"
    assert record.alias == "agent"
    assert record.node_id == "test.node@1.0.0"
    assert record.attempts == 2


def test_replay_backend_helpers_accept_protocol_store_proxy(tmp_path) -> None:
    base_store = FileSystemCAS(tmp_path)
    store = _ArtifactStoreProxy(base_store)
    keep_ref = _put_dead_letter(base_store, run_id="R_proxy", alias="agent")

    records = list_dead_letters(store, run_id="R_proxy")
    record = load_dead_letter(store, keep_ref.artifact_id)

    assert len(records) == 1
    assert records[0].artifact_ref.artifact_id == keep_ref.artifact_id
    assert record.run_id == "R_proxy"


@pytest.mark.asyncio
async def test_replay_dead_letter_reexecutes_node(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    dead_ref = _put_dead_letter(store)
    registry_bundle = ArtifactRef(
        artifact_id="sha256:" + "d" * 64,
        kind="core.registry_bundle",
        media_type="application/json",
    )
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_dead")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("dead-letter"))
    state = ExperimentState(run_id="R_dead", params={"replayed": False})

    class _Node:
        def __init__(self) -> None:
            self.spec = type(
                "Spec",
                (),
                {"metadata": type("Metadata", (), {"component_id": "test.node@1.0.0"})()},
            )()

        def execute(self, ctx, state):
            del ctx
            return NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"replayed": True}}),
            )

    outcome = await replay_dead_letter(
        store,
        dead_ref.artifact_id,
        ctx=ctx,
        state=state,
        node=_Node(),
    )

    assert outcome.status == "ok"
    assert outcome.state.params["replayed"] is True

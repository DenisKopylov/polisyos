from __future__ import annotations

import logging
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    SchemaInfo,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.artifacts.store import PutOptions
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
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.policy_design.schema import PolicyCandidateSchema
from polisyos.scientist.replay.backend import (
    list_dead_letters,
    load_dead_letter,
    replay_dead_letter,
    replay_packet,
)
from polisyos.scientist.replay.deterministic import VerificationConfig, VerificationMode


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
    return store.put_json(
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
        PutOptions(
            kind="scientist.dead_letter",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.orchestration.engine.DeadLetter",
                version="1.0",
            ),
        ),
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
    assert record.dispatch_basis_status == "not_established"
    assert record.dispatch_basis_ref is None


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
async def test_replay_dead_letter_refuses_legacy_record_without_dispatch_basis(tmp_path) -> None:
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.scientist.replay.backend import DeadLetterError

    store = FileSystemCAS(tmp_path)
    dead_ref = _put_dead_letter(store)
    registry_bundle = build_default_registry_bundle(
        store,
        return_selected_profile=True,
    ).bundle_ref
    run = RunContext.start(store=store, registry_bundle=registry_bundle, run_id="R_dead")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("dead-letter"))
    state = ExperimentState(run_id="R_dead", params={"replayed": False})
    node_calls: list[bool] = []

    class _Node:
        def __init__(self) -> None:
            self.spec = type(
                "Spec",
                (),
                {"metadata": type("Metadata", (), {"component_id": "test.node@1.0.0"})()},
            )()

        def execute(self, ctx, state):
            del ctx
            node_calls.append(True)
            return NodeOutcome(
                status="ok",
                state=state.model_copy(update={"params": {"replayed": True}}),
            )

    with pytest.raises(DeadLetterError, match="dead_letter_dispatch_basis_not_established"):
        await replay_dead_letter(
            store,
            dead_ref.artifact_id,
            ctx=ctx,
            state=state,
            node=_Node(),
        )

    assert node_calls == []
    assert run.read_runtime_invocation_attempts() == []


@pytest.mark.asyncio
async def test_retry_producer_binds_and_replays_exact_dispatch_source(tmp_path) -> None:
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
    from polisyos.scientist.orchestration.engine.protocol import NodeSpec
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.retry import RetryPolicy
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
    from polisyos.scientist.replay.backend import DeadLetterError

    node_id = "test.source_bound@1.0.0"

    def _spec() -> NodeSpec:
        return NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(node_id),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Dispatch-source replay test",
                description="Captures the invocation value selected from WorkflowSpec.",
                tags=["test"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=[],
            state_writes=["params.observed_dispatch_tag"],
            produces=[],
        )

    class _SourceBoundNode:
        def __init__(
            self,
            *,
            bound: dict[str, object] | None = None,
            fail_tags: set[str] | None = None,
            calls: list[str] | None = None,
        ):
            self.spec = _spec()
            self.bound = dict(bound or {})
            self.fail_tags = fail_tags or set()
            self.calls = calls

        def bind(self, params: dict[str, object]) -> _SourceBoundNode:
            return _SourceBoundNode(bound=params, fail_tags=self.fail_tags, calls=self.calls)

        def execute(self, ctx, state):
            del ctx
            dispatch_tag = self.bound.get("dispatch_tag")
            if self.calls is not None:
                self.calls.append(str(dispatch_tag))
            if dispatch_tag in self.fail_tags:
                raise RuntimeError("injected dispatch failure")
            params = {**state.params, "observed_dispatch_tag": self.bound.get("dispatch_tag")}
            return NodeOutcome(status="ok", state=state.model_copy(update={"params": params}))

    store = FileSystemCAS(tmp_path).with_ambient_ownership_enforcement()
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        registry_bundle = build_default_registry_bundle(
            store,
            return_selected_profile=True,
        ).bundle_ref
        run = RunContext.start(
            store=store,
            registry_bundle=registry_bundle,
            run_id="R_dispatch_source",
        )
        ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger("dead-letter-source"),
        )
        state = ExperimentState(run_id="R_dispatch_source", params={"outer": "before"})
        producer_registry = NodeRegistry()
        producer_registry.register(_SourceBoundNode(fail_tags={"original", "other"}))
        retry = RetryPolicy(max_retries=1, backoff_base_s=0.1, jitter="none")
        workflow = WorkflowSpec(
            workflow_id="dead_letter_dispatch_source",
            error_policy="continue",
            nodes=[
                NodeInvocation(
                    alias="agent",
                    node_id=node_id,
                    params={"dispatch_tag": "original"},
                    retry=retry,
                ),
                NodeInvocation(
                    alias="other",
                    node_id=node_id,
                    params={"dispatch_tag": "other"},
                    retry=retry,
                ),
            ],
        )

        result = await AsyncWorkflowExecutor(ctx, producer_registry).execute(workflow, state)

        assert result.report.status == "fail"
        records = list_dead_letters(store, run_id="R_dispatch_source", alias="agent")
        assert len(records) == 1
        record = load_dead_letter(store, records[0].artifact_ref.artifact_id)
        assert record.dispatch_basis_status == "selected"
        assert record.artifact_ref.manifest_profile_sha256 is not None
        assert record.dispatch_basis_ref is not None
        assert record.dispatch_basis_ref.manifest_profile_sha256 is not None
        payload = load_core_json_artifact(store, record.artifact_ref.artifact_id)
        assert "params" not in payload
        manifest = store.get_manifest(record.artifact_ref.artifact_id)
        assert manifest.inputs == [
            input_ref_from_artifact_ref(record.dispatch_basis_ref, role="dispatch_basis")
        ]
        attempts = run.read_runtime_invocation_attempts()
        selected_attempt = next(
            attempt for attempt in attempts if attempt.basis_ref == record.dispatch_basis_ref
        )
        assert selected_attempt.basis.node_alias == "agent"
        assert selected_attempt.basis.component_id == node_id
        assert selected_attempt.outcome is not None
        assert selected_attempt.outcome.status == "unknown"

    replay_registry = NodeRegistry()
    replay_calls: list[str] = []
    replay_registry.register(_SourceBoundNode(calls=replay_calls))
    replay_state = state.model_copy(update={"params": {"outer": "mutated"}})
    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-b"):
        with pytest.raises(ArtifactOwnershipError):
            await replay_dead_letter(
                store,
                record.artifact_ref.artifact_id,
                ctx=ctx,
                state=replay_state,
                registry=replay_registry,
            )
    assert replay_calls == []

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):
        outcome = await replay_dead_letter(
            store,
            record.artifact_ref.artifact_id,
            ctx=ctx,
            state=replay_state,
            registry=replay_registry,
        )
        assert outcome.status == "ok"
        assert outcome.state.params["observed_dispatch_tag"] == "original"
        assert replay_calls == ["original"]
        replay_call_count = len(replay_calls)

    with tenant_scope(None, tenant_id="tenant-a", cell_id="cell-a"):

        def _copy_with_basis(basis_ref: ArtifactRef | None, status: str) -> ArtifactRef:
            payload = load_core_json_artifact(store, record.artifact_ref.artifact_id)
            payload["dispatch_basis_status"] = status
            payload["dispatch_basis_ref"] = (
                basis_ref.model_dump(mode="json") if basis_ref is not None else None
            )
            return store.put_json(
                payload,
                PutOptions(
                    kind="scientist.dead_letter",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.scientist.orchestration.engine.DeadLetter",
                        version="2.0",
                    ),
                    inputs=(
                        [input_ref_from_artifact_ref(basis_ref, role="dispatch_basis")]
                        if basis_ref is not None
                        else []
                    ),
                ),
            )

        swapped_attempt = next(
            attempt for attempt in attempts if attempt.basis.node_alias == "other"
        )
        assert swapped_attempt.outcome is not None
        assert swapped_attempt.outcome.status == "unknown"
        swapped_ref = _copy_with_basis(swapped_attempt.basis_ref, "selected")
        with pytest.raises(DeadLetterError, match="dead_letter_dispatch_basis_mismatch"):
            await replay_dead_letter(
                store,
                swapped_ref.artifact_id,
                ctx=ctx,
                state=replay_state,
                registry=replay_registry,
            )
        assert len(replay_calls) == replay_call_count

        assert selected_attempt.basis_ref.manifest_profile_sha256 is not None
        changed_profile = selected_attempt.basis_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "0" * 64}
        )
        changed_ref = _copy_with_basis(changed_profile, "selected")
        with pytest.raises(DeadLetterError, match="dead_letter_dispatch_basis_not_established"):
            await replay_dead_letter(
                store,
                changed_ref.artifact_id,
                ctx=ctx,
                state=replay_state,
                registry=replay_registry,
            )
        assert len(replay_calls) == replay_call_count

        removed_ref = _copy_with_basis(None, "not_established")
        with pytest.raises(DeadLetterError, match="dead_letter_dispatch_basis_not_established"):
            await replay_dead_letter(
                store,
                removed_ref.artifact_id,
                ctx=ctx,
                state=replay_state,
                registry=replay_registry,
            )
        assert len(replay_calls) == replay_call_count


def _candidate_schema_for_unbound_origin_test(
    candidate_id: str,
) -> PolicyCandidateSchema:
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.trinity import TrinityBundle

    bundle = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_unbound_origin_test",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(policy_id="policy_unbound_origin_test"),
        model_spec=ModelSpec(
            model_id="model_unbound_origin_test",
            data_snapshot_ref="sha256:" + "1" * 64,
        ),
    )
    return PolicyCandidateSchema.from_trinity_bundle(bundle, candidate_id=candidate_id)


@pytest.mark.asyncio
async def test_dead_letter_replay_selects_candidate_without_claiming_owner_origin(
    tmp_path: Path,
) -> None:
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.scientist.nodes.builtins.decide.build_policy_output_bundle import (
        _resolve_candidate,
    )
    from polisyos.scientist.policy_design.phase3 import _load_bound_candidate_source_state

    store = FileSystemCAS(tmp_path)
    dead_ref = _put_dead_letter(store, run_id="R_dead_unbound_origin")
    registry_bundle = build_default_registry_bundle(
        store,
        return_selected_profile=True,
    ).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_dead_unbound_origin",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("dead-letter-unbound-origin"),
    )
    candidate = _candidate_schema_for_unbound_origin_test("candidate_replay_unbound")
    state = ExperimentState(
        run_id="R_dead_unbound_origin",
        params={"policy_candidate_schema": candidate.model_dump(mode="json")},
    )

    class _CandidateConsumer:
        def __init__(self) -> None:
            self.spec = type(
                "Spec",
                (),
                {"metadata": type("Metadata", (), {"component_id": "test.node@1.0.0"})()},
            )()

        def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            basis = _load_bound_candidate_source_state(ctx, state)
            selected, selected_ref = _resolve_candidate(ctx, state)
            assert selected is not None
            assert selected_ref is None
            return NodeOutcome(
                status="ok",
                state=state.model_copy(
                    update={
                        "params": {
                            **state.params,
                            "selected_candidate_id": selected.candidate_id,
                            "owner_basis_present": basis is not None,
                        }
                    }
                ),
            )

    from polisyos.scientist.replay.backend import DeadLetterError

    consumer_calls: list[bool] = []
    consumer = _CandidateConsumer()
    original_execute = consumer.execute

    def _observe_execute(ctx: ExecutionContext, replay_state: ExperimentState) -> NodeOutcome:
        consumer_calls.append(True)
        return original_execute(ctx, replay_state)

    consumer.execute = _observe_execute
    with pytest.raises(DeadLetterError, match="dead_letter_dispatch_basis_not_established"):
        await replay_dead_letter(
            store,
            dead_ref.artifact_id,
            ctx=ctx,
            state=state,
            node=consumer,
        )

    assert consumer_calls == []
    assert run.read_runtime_invocation_attempts() == []

"""Real reopened cache consumers distinguish input presence and journal effects."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from _helpers.run_lifecycle import (
    assert_one_resumed_terminal_lifecycle,
    interrupt_before_finalize_async,
    resume_same_run,
)

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine import async_executor as async_executor_module
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.idempotency import NodeCacheEntry
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


class _PresenceNode:
    def __init__(self):
        self.calls = 0
        self.refs: list[ArtifactRef] = []
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.presence_consumer@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Presence consumer",
                description="Exact observed input presence and type",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.threshold"],
            state_writes=["params.observed"],
        )

    def execute(self, ctx, state):
        raise AssertionError("Actual async method required")

    async def execute_async(self, ctx, state):
        self.calls += 1
        observed = {
            "present": "threshold" in state.params,
            # Classify the actual JSON value crossing the artifact contract;
            # branch guard views are list/dict subclasses, not new JSON types.
            "type": type(json.loads(json.dumps(state.params["threshold"]))).__name__
            if "threshold" in state.params
            else None,
            "value": state.params.get("threshold"),
        }
        ref = ctx.store.put_json(
            observed, PutOptions(kind="scientist.presence_effect", media_type="application/json")
        )
        self.refs.append(ref)
        state.params["observed"] = observed
        return NodeOutcome(status="ok", state=state, artifacts=[ref])


class _ArtifactRefWriter:
    def __init__(self) -> None:
        self.calls = 0
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.async_artifact_ref_writer@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Async ArtifactRef writer",
                description="Cache a typed ArtifactRef state mutation",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.seed"],
            state_writes=["preflight_report_ref"],
        )

    def execute(self, ctx, state):
        raise AssertionError("Actual async method required")

    async def execute_async(self, ctx, state):
        self.calls += 1
        ref = ctx.store.put_json(
            {"writer": "async_artifact_ref"},
            PutOptions(
                kind="scientist.artifact_ref_effect",
                media_type="application/json",
            ),
        )
        state.preflight_report_ref = ref
        return NodeOutcome(status="ok", state=state, artifacts=[ref])


@pytest.mark.asyncio
async def test_async_cache_replays_typed_artifact_ref_mutation_from_cas(tmp_path):
    root = tmp_path / "artifact-ref-cache"
    store = FileSystemCAS(root)
    bundle_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    node = _ArtifactRefWriter()
    registry = NodeRegistry()
    registry.register(node)
    run_id = "R_async_artifact_ref_cache"
    workflow = WorkflowSpec(
        workflow_id="async_artifact_ref_cache",
        nodes=[NodeInvocation(alias="write_ref", node_id=node.spec.metadata.component_id)],
    )

    previous_run = None
    for ordinal in range(2):
        reopened = FileSystemCAS(root)
        run = (
            RunContext.start(reopened, bundle_ref, run_id=run_id)
            if previous_run is None
            else resume_same_run(reopened, previous_run)
        )
        ctx = ExecutionContext(
            store=reopened,
            run=run,
            logger=logging.getLogger("async-artifact-ref-cache"),
        )
        state = ExperimentState(run_id=run_id, params={"seed": 7})
        executor = AsyncWorkflowExecutor(ctx, registry)
        if ordinal == 0:
            cold_events = await interrupt_before_finalize_async(
                run,
                lambda executor=executor, workflow=workflow, state=state: executor.execute(
                    workflow, state
                ),
            )
            assert sum(event.get("event") == "NODE_CACHE_STORE" for event in cold_events) == 1
            assert node.calls == 1
            previous_run = run
            continue

        result = await executor.execute(workflow, state)
        assert result.report.status == "ok"
        ref = result.state.preflight_report_ref
        assert isinstance(ref, ArtifactRef)
        assert reopened.verify(ref).ok
        assert node.calls == 1
        events = assert_one_resumed_terminal_lifecycle(run)
        hits = [record for record in events if record.get("event") == "NODE_CACHE_HIT"]
        assert len(hits) == 1

    assert node.calls == 1


def _expected_presence(params: dict[str, Any]) -> dict[str, Any]:
    present = "threshold" in params
    value = params.get("threshold")
    return {"present": present, "type": type(value).__name__ if present else None, "value": value}


def _assert_presence_observation(observed: dict[str, Any], expected: dict[str, Any]) -> None:
    assert observed == expected, (
        "cache replay did not preserve the current input's threshold presence"
    )


@pytest.mark.asyncio
async def test_five_presence_variants_share_one_run_and_replay_only_their_native_results(tmp_path):
    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    bundle_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    node = _PresenceNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="native_presence",
        nodes=[NodeInvocation(alias="consume", node_id=node.spec.metadata.component_id)],
    )
    run_id = "R_presence_shared"
    inputs: tuple[dict[str, Any], ...] = (
        {},
        {"threshold": None},
        {"threshold": 0},
        {"threshold": False},
        {"threshold": []},
    )
    previous_run: RunContext | None = None
    cache_refs: list[ArtifactRef] = []
    idempotency_keys: list[str] = []

    for ordinal, params in enumerate(inputs, start=1):
        reopened = FileSystemCAS(root)
        run = (
            RunContext.start(reopened, bundle_ref, run_id=run_id)
            if previous_run is None
            else resume_same_run(reopened, previous_run)
        )
        ctx = ExecutionContext(
            store=reopened, run=run, logger=logging.getLogger("presence-consumer")
        )
        state = ExperimentState(run_id=run_id, params={**params, "unrelated": "same-control-value"})
        expected = _expected_presence(params)
        executor = AsyncWorkflowExecutor(ctx, registry)
        events = await interrupt_before_finalize_async(
            run,
            lambda executor=executor, workflow=workflow, state=state: executor.execute(
                workflow, state
            ),
            expected_resumes=ordinal - 1,
        )
        stores = [event for event in events if event.get("event") == "NODE_CACHE_STORE"]
        hits = [event for event in events if event.get("event") == "NODE_CACHE_HIT"]
        assert len(stores) == ordinal
        assert not hits
        assert node.calls == ordinal
        cache_ref = ArtifactRef.model_validate(stores[-1]["refs"]["outputs"][0])
        entry = NodeCacheEntry.model_validate(from_canonical_bytes(reopened.get_bytes(cache_ref)))
        assert reopened.verify(cache_ref).ok
        assert entry.run_id == run_id
        assert entry.node_id == str(node.spec.metadata.component_id)
        assert entry.idempotency_key not in idempotency_keys
        idempotency_keys.append(entry.idempotency_key)
        cache_refs.append(cache_ref)
        effect_ref = node.refs[-1]
        assert reopened.verify(effect_ref).ok
        assert json.loads(reopened.get_bytes(effect_ref)) == expected
        assert reopened.get_manifest(effect_ref).kind == "scientist.presence_effect"
        previous_run = run

    assert previous_run is not None
    assert node.calls == len(inputs)
    assert len(idempotency_keys) == len(inputs) and len(set(idempotency_keys)) == len(inputs)
    assert len({str(ref.artifact_id) for ref in cache_refs}) == len(inputs)
    assert len({str(ref.artifact_id) for ref in node.refs}) == len(inputs)
    assert all(FileSystemCAS(root).verify(ref).ok for ref in cache_refs)

    reopened = FileSystemCAS(root)
    run = resume_same_run(reopened, previous_run)
    ctx = ExecutionContext(
        store=reopened, run=run, logger=logging.getLogger("presence-consumer-replay")
    )
    final_params = inputs[-1]
    final_state = ExperimentState(
        run_id=run_id, params={**final_params, "unrelated": "final-current"}
    )
    result = await AsyncWorkflowExecutor(ctx, registry).execute(workflow, final_state)
    expected_final = _expected_presence(final_params)
    assert result.report.status == "ok"
    _assert_presence_observation(result.state.params["observed"], expected_final)
    assert result.state.params["unrelated"] == "final-current"
    assert "observed" not in final_state.params
    assert node.calls == len(inputs)
    assert reopened.verify(result.run_ref).ok
    final_effect = result.report.nodes[0].artifacts[0]
    assert reopened.verify(final_effect).ok
    assert str(final_effect.artifact_id) == str(node.refs[-1].artifact_id)
    terminal = assert_one_resumed_terminal_lifecycle(run, expected_resumes=len(inputs))
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in terminal) == len(inputs)
    assert sum(event.get("event") == "NODE_CACHE_HIT" for event in terminal) == 1


@pytest.mark.asyncio
async def test_removing_presence_discriminator_is_caught_with_markers_intact(tmp_path, monkeypatch):
    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    bundle_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    node = _PresenceNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="native_presence_negative_control",
        nodes=[NodeInvocation(alias="consume", node_id=node.spec.metadata.component_id)],
    )
    run_id = "R_presence_removed_discriminator"
    missing_state = ExperimentState(run_id=run_id, params={"unrelated": "same"})
    present_null_state = ExperimentState(
        run_id=run_id, params={"threshold": None, "unrelated": "same"}
    )
    original_compute = async_executor_module.compute_idempotency_key

    def collapse_missing_to_null(
        spec: NodeSpec, state: ExperimentState, bind_params: dict[str, Any] | None = None
    ) -> str:
        if "params.threshold" not in spec.state_reads or "threshold" in state.params:
            return original_compute(spec, state, bind_params)
        collapsed = state.model_copy(deep=True)
        collapsed.params["threshold"] = None
        return original_compute(spec, collapsed, bind_params)

    monkeypatch.setattr(async_executor_module, "compute_idempotency_key", collapse_missing_to_null)
    missing_key = async_executor_module.compute_idempotency_key(node.spec, missing_state)
    null_key = async_executor_module.compute_idempotency_key(node.spec, present_null_state)
    assert missing_key == null_key
    run = RunContext.start(store, bundle_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=store, run=run, logger=logging.getLogger("presence-negative-control")
    )
    executor = AsyncWorkflowExecutor(ctx, registry)
    first_events = await interrupt_before_finalize_async(
        run,
        lambda executor=executor, workflow=workflow, state=missing_state: executor.execute(
            workflow, state
        ),
    )
    first_stores = [event for event in first_events if event.get("event") == "NODE_CACHE_STORE"]
    assert len(first_stores) == 1
    assert not any(event.get("event") == "NODE_CACHE_HIT" for event in first_events)
    first_ref = ArtifactRef.model_validate(first_stores[0]["refs"]["outputs"][0])
    first_entry = NodeCacheEntry.model_validate(from_canonical_bytes(store.get_bytes(first_ref)))
    assert store.verify(first_ref).ok
    assert first_entry.idempotency_key == missing_key
    assert first_entry.run_id == run_id
    assert node.calls == 1
    assert json.loads(store.get_bytes(node.refs[0])) == _expected_presence({})

    reopened = FileSystemCAS(root)
    resumed = resume_same_run(reopened, run)
    resumed_ctx = ExecutionContext(
        store=reopened, run=resumed, logger=logging.getLogger("presence-negative-control-resume")
    )
    result = await AsyncWorkflowExecutor(resumed_ctx, registry).execute(
        workflow, present_null_state
    )
    assert result.report.status == "ok"
    actual = result.state.params["observed"]
    assert actual == _expected_presence({})
    assert actual != _expected_presence({"threshold": None})
    assert result.state.params["unrelated"] == "same"
    assert node.calls == 1
    terminal = assert_one_resumed_terminal_lifecycle(resumed)
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in terminal) == 1
    assert sum(event.get("event") == "NODE_CACHE_HIT" for event in terminal) == 1
    assert reopened.verify(result.run_ref).ok
    with pytest.raises(AssertionError, match="current input's threshold presence"):
        _assert_presence_observation(actual, _expected_presence({"threshold": None}))

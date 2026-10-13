from __future__ import annotations

import json
import logging
import multiprocessing

from _helpers.process_run_lifecycle import (
    _CACHED_SPEC,
    CachedCounterNode,
    produce_cached_run_then_exit_before_finalize,
)
from _helpers.run_lifecycle import (
    assert_one_resumed_terminal_lifecycle,
    interrupt_before_finalize,
    resume_same_run,
)

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.runtime.http.services.adapters.core_run import load_terminal_core_run_source
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_BROAD_CACHED_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_broad_cached_counter@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Broad Cached Counter",
    description="Test node for exact replay writes under a broad declaration",
    tags=["test"],
    capabilities=Capability.SCIENTIST_NODE,
)

_BROAD_CACHED_SPEC = NodeSpec(
    metadata=_BROAD_CACHED_METADATA,
    state_reads=["params.seed"],
    state_writes=["params"],
)

_TOP_LEVEL_REF = ArtifactRef(
    artifact_id="sha256:" + "a" * 64,
    kind="test.ref",
    media_type="application/json",
)

_TOP_LEVEL_REF_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_top_level_ref@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Top-Level Ref",
    description="Test node for scalar state replay",
    tags=["test"],
    capabilities=Capability.SCIENTIST_NODE,
)

_TOP_LEVEL_REF_SPEC = NodeSpec(
    metadata=_TOP_LEVEL_REF_METADATA,
    state_reads=["params.seed"],
    state_writes=["preflight_report_ref"],
)

_INVALID_REPLAY_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_invalid_replay@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Invalid Replay",
    description="Test node for cache replay precondition handling",
    tags=["test"],
    capabilities=Capability.SCIENTIST_NODE,
)

_INVALID_REPLAY_SPEC = NodeSpec(
    metadata=_INVALID_REPLAY_METADATA,
    state_reads=["params.seed"],
    state_writes=["params.items", "params.reexecuted"],
)

_FAIL_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_always_fail@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Always Fail",
    description="Test fail node for retry verification",
    tags=["test"],
    capabilities=Capability.SCIENTIST_NODE,
)

_FAIL_SPEC = NodeSpec(metadata=_FAIL_METADATA)

_MUTATING_FAIL_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_mutating_fail@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Mutating Fail",
    description="Test fail node that mutates before failing",
    tags=["test"],
    capabilities=Capability.SCIENTIST_NODE,
)

_MUTATING_FAIL_SPEC = NodeSpec(
    metadata=_MUTATING_FAIL_METADATA,
    state_writes=["params.leaked"],
)


class BroadCachedCounterNode:
    calls = 0

    @property
    def spec(self) -> NodeSpec:
        return _BROAD_CACHED_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        BroadCachedCounterNode.calls += 1
        new_state = state.model_copy(deep=True)
        new_state.params["cached_counter"] = BroadCachedCounterNode.calls
        return NodeOutcome(status="ok", state=new_state)


class TopLevelRefNode:
    calls = 0

    @property
    def spec(self) -> NodeSpec:
        return _TOP_LEVEL_REF_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        TopLevelRefNode.calls += 1
        new_state = state.model_copy(deep=True)
        new_state.preflight_report_ref = _TOP_LEVEL_REF
        return NodeOutcome(status="ok", state=new_state)


class InvalidReplayNode:
    calls = 0

    @property
    def spec(self) -> NodeSpec:
        return _INVALID_REPLAY_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        InvalidReplayNode.calls += 1
        new_state = state.model_copy(deep=True)
        if isinstance(new_state.params.get("items"), list):
            new_state.params["items"].pop(1)
        else:
            new_state.params["reexecuted"] = True
        return NodeOutcome(status="ok", state=new_state)


class AlwaysFailNode:
    calls = 0

    @property
    def spec(self) -> NodeSpec:
        return _FAIL_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        AlwaysFailNode.calls += 1
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(code="node.fail", message="expected failure"),
        )


class MutatingFailNode:
    @property
    def spec(self) -> NodeSpec:
        return _MUTATING_FAIL_SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        state.params["leaked"] = True
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(code="node.fail", message="expected failure"),
        )


def _build_context(
    store: FileSystemCAS,
    run_id: str,
    *,
    selected_registry_profile: bool = True,
    resume_from: ExecutionContext | None = None,
) -> tuple[ExecutionContext, NodeRegistry]:
    if resume_from is None:
        bundle = build_default_registry_bundle(
            store, return_selected_profile=selected_registry_profile
        )
        run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    else:
        assert resume_from.run.run_manifest.run_id == run_id
        run = resume_same_run(store, resume_from.run)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("idempotency_test"))
    registry = NodeRegistry()
    registry.register(CachedCounterNode())
    registry.register(BroadCachedCounterNode())
    registry.register(TopLevelRefNode())
    registry.register(InvalidReplayNode())
    registry.register(AlwaysFailNode())
    return ctx, registry


def _load_trace_events(store: FileSystemCAS, ctx: ExecutionContext) -> list[dict[str, object]]:
    trace_ref = ctx.run.run_manifest.trace_ref
    assert trace_ref is not None
    payload = store.get_bytes(trace_ref.artifact_id).decode("utf-8")
    return [json.loads(line) for line in payload.splitlines() if line.strip()]


def test_executor_cache_hit_after_restart_same_run_id(tmp_path) -> None:
    CachedCounterNode.calls = 0
    store = FileSystemCAS(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="cache_restart",
        nodes=[
            NodeInvocation(
                alias="cached",
                node_id=ComponentId.parse("scientist.node_cached_counter@1.0.0"),
            ),
        ],
    )
    initial_state = ExperimentState(run_id="R_cache_restart", params={"seed": 7})

    ctx_a, registry_a = _build_context(store, "R_cache_restart")
    cold_events = interrupt_before_finalize(
        ctx_a.run,
        lambda: WorkflowExecutor(ctx_a, registry_a).execute(workflow, initial_state),
    )
    assert CachedCounterNode.calls == 1
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in cold_events) == 1

    ctx_b, registry_b = _build_context(store, "R_cache_restart", resume_from=ctx_a)
    result_b = WorkflowExecutor(ctx_b, registry_b).execute(workflow, initial_state)
    assert result_b.report.status == "ok"
    assert CachedCounterNode.calls == 1
    assert result_b.state.params["cached_counter"] == 1

    events = assert_one_resumed_terminal_lifecycle(ctx_b.run)
    hit_events = [evt for evt in events if evt.get("event") == "NODE_CACHE_HIT"]
    assert len(hit_events) == 1


# Production mutation caught: a cache hit must replay only actual writes, not
# restore unrelated values from the historical full outcome state.
def test_executor_cache_hit_preserves_unrelated_current_state(tmp_path) -> None:
    BroadCachedCounterNode.calls = 0
    store = FileSystemCAS(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="broad_cache_replay",
        nodes=[
            NodeInvocation(
                alias="cached",
                node_id=ComponentId.parse("scientist.node_broad_cached_counter@1.0.0"),
            ),
        ],
    )

    ctx_a, registry_a = _build_context(store, "R_broad_cache_replay")
    cold_events = interrupt_before_finalize(
        ctx_a.run,
        lambda: WorkflowExecutor(ctx_a, registry_a).execute(
            workflow,
            ExperimentState(
                run_id="R_broad_cache_replay",
                params={"seed": 7, "unrelated": "old"},
            ),
        ),
    )
    assert BroadCachedCounterNode.calls == 1
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in cold_events) == 1

    ctx_b, registry_b = _build_context(store, "R_broad_cache_replay", resume_from=ctx_a)
    result_b = WorkflowExecutor(ctx_b, registry_b).execute(
        workflow,
        ExperimentState(
            run_id="R_broad_cache_replay",
            params={"seed": 7, "unrelated": "new"},
        ),
    )

    assert result_b.report.status == "ok"
    assert BroadCachedCounterNode.calls == 1
    assert result_b.state.params["unrelated"] == "new"
    assert result_b.state.params["cached_counter"] == 1
    assert_one_resumed_terminal_lifecycle(ctx_b.run)


# Production mutation caught: a cache hit must replay a declared top-level
# scalar/ref write, including when the current base still carries None.
def test_executor_cache_hit_replays_top_level_ref_write(tmp_path) -> None:
    TopLevelRefNode.calls = 0
    store = FileSystemCAS(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="top_level_ref_cache",
        nodes=[
            NodeInvocation(
                alias="ref_writer",
                node_id=ComponentId.parse("scientist.node_top_level_ref@1.0.0"),
            ),
        ],
    )

    ctx_a, registry_a = _build_context(store, "R_top_level_ref_cache")
    cold_events = interrupt_before_finalize(
        ctx_a.run,
        lambda: WorkflowExecutor(ctx_a, registry_a).execute(
            workflow,
            ExperimentState(run_id="R_top_level_ref_cache", params={"seed": 7}),
        ),
    )
    assert TopLevelRefNode.calls == 1
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in cold_events) == 1

    ctx_b, registry_b = _build_context(store, "R_top_level_ref_cache", resume_from=ctx_a)
    result_b = WorkflowExecutor(ctx_b, registry_b).execute(
        workflow,
        ExperimentState(run_id="R_top_level_ref_cache", params={"seed": 7}),
    )

    assert result_b.report.status == "ok"
    assert TopLevelRefNode.calls == 1
    assert result_b.state.preflight_report_ref == _TOP_LEVEL_REF
    assert_one_resumed_terminal_lifecycle(ctx_b.run)


def test_cache_rejects_boolean_integer_alias_in_live_mutation_journal(tmp_path) -> None:
    """A valid CAS entry must miss when its live ordered journal differs by JSON type."""
    run_id = "R_cache_mutation_type_guard"
    state = ExperimentState(run_id=run_id, params={"seed": 7})
    branch = branch_state(state, write_paths=_CACHED_SPEC.state_writes)
    branch.state.params["cached_counter"] = True
    outcome = NodeOutcome(status="ok", state=branch.state)
    cache = NodeResultCache(FileSystemCAS(tmp_path), run_id=run_id)
    key = compute_idempotency_key(spec=_CACHED_SPEC, state=state)

    cache.put(
        key,
        node_id=str(_CACHED_SPEC.metadata.component_id),
        outcome=outcome,
    )
    journal = cache._mutation_journals[key]
    assert journal.operations[0].value is True
    # This adversarial live-record mutation exposes Python's True == 1 alias.
    object.__setattr__(journal.operations[0], "value", 1)

    assert cache.get(key) is None
    assert not cache.has(key)


# Production mutation caught: an incompatible cached list target must evict
# the cache entry and re-execute, never silently report a cache-hit success.
def test_executor_reexecutes_when_cached_replay_target_is_incompatible(tmp_path) -> None:
    InvalidReplayNode.calls = 0
    store = FileSystemCAS(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="invalid_replay_target",
        nodes=[
            NodeInvocation(
                alias="invalid_replay",
                node_id=ComponentId.parse("scientist.node_invalid_replay@1.0.0"),
            ),
        ],
    )

    ctx_a, registry_a = _build_context(store, "R_invalid_replay_target")
    cold_events = interrupt_before_finalize(
        ctx_a.run,
        lambda: WorkflowExecutor(ctx_a, registry_a).execute(
            workflow,
            ExperimentState(
                run_id="R_invalid_replay_target",
                params={"seed": 7, "items": ["cached", "removed"]},
            ),
        ),
    )
    assert InvalidReplayNode.calls == 1
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in cold_events) == 1

    ctx_b, registry_b = _build_context(store, "R_invalid_replay_target", resume_from=ctx_a)
    result_b = WorkflowExecutor(ctx_b, registry_b).execute(
        workflow,
        ExperimentState(
            run_id="R_invalid_replay_target",
            params={"seed": 7, "items": {}},
        ),
    )

    assert result_b.report.status == "ok"
    assert InvalidReplayNode.calls == 2
    assert result_b.state.params["reexecuted"] is True
    assert_one_resumed_terminal_lifecycle(ctx_b.run)


def test_executor_resume_retries_failed_node_and_reuses_cached_ok_node(tmp_path) -> None:
    CachedCounterNode.calls = 0
    AlwaysFailNode.calls = 0
    store = FileSystemCAS(tmp_path)
    workflow = WorkflowSpec(
        workflow_id="cache_resume_fail",
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="cached",
                node_id=ComponentId.parse("scientist.node_cached_counter@1.0.0"),
            ),
            NodeInvocation(
                alias="failing",
                node_id=ComponentId.parse("scientist.node_always_fail@1.0.0"),
                depends_on=["cached"],
            ),
        ],
    )
    initial_state = ExperimentState(run_id="R_cache_resume", params={"seed": 42})

    ctx_a, registry_a = _build_context(store, "R_cache_resume")
    cold_events = interrupt_before_finalize(
        ctx_a.run,
        lambda: WorkflowExecutor(ctx_a, registry_a).execute(workflow, initial_state),
    )
    assert CachedCounterNode.calls == 1
    assert AlwaysFailNode.calls == 1
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in cold_events) == 1

    ctx_b, registry_b = _build_context(store, "R_cache_resume", resume_from=ctx_a)
    result_b = WorkflowExecutor(ctx_b, registry_b).execute(workflow, initial_state)
    assert result_b.report.status == "fail"
    assert CachedCounterNode.calls == 1
    assert AlwaysFailNode.calls == 2

    cached_record = next(rec for rec in result_b.report.nodes if rec.alias == "cached")
    failing_record = next(rec for rec in result_b.report.nodes if rec.alias == "failing")
    assert cached_record.status == "ok"
    assert failing_record.status == "fail"
    events = assert_one_resumed_terminal_lifecycle(ctx_b.run)
    assert any(evt.get("event") == "NODE_CACHE_HIT" for evt in events)


def test_executor_failed_node_state_is_not_committed(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    run_id = "R_failed_state_rollback"
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("rollback_test"))
    registry = NodeRegistry()
    registry.register(MutatingFailNode())
    workflow = WorkflowSpec(
        workflow_id="failed_state_rollback",
        error_policy="continue",
        nodes=[
            NodeInvocation(
                alias="mutating_fail",
                node_id=ComponentId.parse("scientist.node_mutating_fail@1.0.0"),
            ),
        ],
    )

    result = WorkflowExecutor(ctx, registry).execute(
        workflow,
        ExperimentState(run_id=run_id, params={"baseline": True}),
    )

    assert result.report.status == "fail"
    assert result.state.params == {"baseline": True}


def test_incomplete_process_run_resumes_same_cache_and_one_terminal_lifecycle(tmp_path) -> None:
    CachedCounterNode.calls = 0
    run_id = "R_process_loss_resume"
    root = tmp_path / "cas"
    process = multiprocessing.get_context("spawn").Process(
        target=produce_cached_run_then_exit_before_finalize,
        args=(str(root), run_id),
    )
    process.start()
    process.join(timeout=30)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
    assert process.exitcode == 73

    child_trace = root / "runs" / run_id / "trace.jsonl"
    child_events = [
        json.loads(line)
        for line in child_trace.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert sum(event.get("event") == "RUN_STARTED" for event in child_events) == 1
    assert sum(event.get("event") == "RUN_RESUMED" for event in child_events) == 0
    assert sum(event.get("event") == "RUN_FINALIZED" for event in child_events) == 0
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in child_events) == 1

    store = FileSystemCAS(root)
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run_dir = root / "runs" / run_id
    resumed = RunContext.resume(
        store,
        run_id=run_id,
        run_dir=run_dir,
        registry_bundle=bundle.bundle_ref,
        producer=None,
        env=None,
        access_scope=None,
    )
    ctx = ExecutionContext(
        store=store,
        run=resumed,
        logger=logging.getLogger("idempotency_resume_test"),
    )
    registry = NodeRegistry()
    registry.register(CachedCounterNode())
    workflow = WorkflowSpec(
        workflow_id="cache_resume_after_process_loss",
        nodes=[
            NodeInvocation(
                alias="cached",
                node_id=ComponentId.parse("scientist.node_cached_counter@1.0.0"),
            ),
        ],
    )
    result = WorkflowExecutor(ctx, registry).execute(
        workflow,
        ExperimentState(run_id=run_id, params={"seed": 7}),
    )
    assert result.report.status == "ok"
    assert result.state.params["cached_counter"] == 1
    assert CachedCounterNode.calls == 0
    assert resumed.run_manifest.run_id == run_id

    terminal = load_terminal_core_run_source(
        store=store,
        core_runs_root=root / "runs",
        run_id=run_id,
    )
    records = [
        json.loads(line)
        for line in terminal.trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert_one_resumed_terminal_lifecycle(resumed)
    assert sum(record.get("event") == "NODE_CACHE_HIT" for record in records) == 1
    assert terminal.manifest_ref.manifest_profile_sha256 is not None

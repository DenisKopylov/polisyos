from __future__ import annotations

import json
import logging
import multiprocessing
from copy import deepcopy

import pytest
from _helpers.process_run_lifecycle import (
    _CACHED_SPEC,
    CachedCounterNode,
    CheckpointedCacheEffectNode,
    checkpointed_cache_registry,
    checkpointed_cache_workflow,
    produce_cached_checkpoint_then_exit,
)
from _helpers.run_lifecycle import (
    interrupt_before_finalize,
    resume_same_run,
)

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.runtime.http.services.adapters.core_run import load_terminal_core_run_source
from polisyos.scientist.orchestration.engine.checkpoint import (
    resolve_latest_checkpoint,
    resume_from_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeCacheEntry,
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

_CACHE_BASE_MUTATOR_SPEC = NodeSpec(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("scientist.node_cache_base_mutator@1.0.0"),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name="Cache replay current-base mutator",
        capabilities=Capability.SCIENTIST_NODE,
    ),
    state_writes=["params", "preflight_report_ref"],
)


class CacheBaseMutator:
    """Change only a subsequent alias's base inside one actual workflow."""

    def __init__(self, updates=None, *, delete=(), reset_preflight: bool = False) -> None:
        self._updates = dict(updates or {})
        self._delete = tuple(delete)
        self._reset_preflight = reset_preflight

    @property
    def spec(self) -> NodeSpec:
        return _CACHE_BASE_MUTATOR_SPEC

    def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        for key, value in self._updates.items():
            state.params[key] = deepcopy(value)
        for key in self._delete:
            state.params.pop(key, None)
        if self._reset_preflight:
            state.preflight_report_ref = None
        return NodeOutcome(status="ok", state=state)


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


def test_executor_cache_hit_with_distinct_original_dag_aliases(tmp_path) -> None:
    CachedCounterNode.calls = 0
    store = FileSystemCAS(tmp_path)
    ctx, registry = _build_context(store, "R_cache_restart")
    workflow = WorkflowSpec(
        workflow_id="cache_restart",
        nodes=[
            NodeInvocation(
                alias="cold",
                node_id=ComponentId.parse("scientist.node_cached_counter@1.0.0"),
            ),
            NodeInvocation(
                alias="warm",
                node_id=ComponentId.parse("scientist.node_cached_counter@1.0.0"),
                depends_on=["cold"],
            ),
        ],
    )
    initial_state = ExperimentState(run_id="R_cache_restart", params={"seed": 7})
    warm_state = initial_state.model_copy(
        update={"params": {"seed": 7, "cached_counter": 1}}, deep=True
    )
    assert compute_idempotency_key(_CACHED_SPEC, initial_state) == compute_idempotency_key(
        _CACHED_SPEC, warm_state
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, initial_state)
    assert result.report.status == "ok"
    assert CachedCounterNode.calls == 1
    assert result.state.params["cached_counter"] == 1
    events = _load_trace_events(store, ctx)
    assert any(
        e.get("event") == "NODE_CACHE_STORE" and e.get("phase") == "scientist.node.cold"
        for e in events
    )
    assert any(
        e.get("event") == "NODE_CACHE_HIT" and e.get("phase") == "scientist.node.warm"
        for e in events
    )


# Production mutation caught: a cache hit must replay only actual writes, not
# restore unrelated values from the historical full outcome state.
def test_executor_cache_hit_preserves_unrelated_current_state(tmp_path) -> None:
    BroadCachedCounterNode.calls = 0
    store = FileSystemCAS(tmp_path)
    ctx, registry = _build_context(store, "R_broad_cache_replay")
    registry.register(CacheBaseMutator({"unrelated": "new", "cached_counter": 9}))
    initial = ExperimentState(run_id="R_broad_cache_replay", params={"seed": 7, "unrelated": "old"})
    warm_base = ExperimentState(
        run_id=initial.run_id,
        params={"seed": 7, "unrelated": "new", "cached_counter": 9},
    )
    assert compute_idempotency_key(_BROAD_CACHED_SPEC, initial) == compute_idempotency_key(
        _BROAD_CACHED_SPEC, warm_base
    )
    workflow = WorkflowSpec(
        workflow_id="broad_cache_replay",
        nodes=[
            NodeInvocation(
                alias="cold",
                node_id=ComponentId.parse("scientist.node_broad_cached_counter@1.0.0"),
            ),
            NodeInvocation(
                alias="mutate",
                node_id=_CACHE_BASE_MUTATOR_SPEC.metadata.component_id,
                depends_on=["cold"],
            ),
            NodeInvocation(
                alias="warm",
                node_id=ComponentId.parse("scientist.node_broad_cached_counter@1.0.0"),
                depends_on=["mutate"],
            ),
        ],
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    assert result.report.status == "ok"
    assert BroadCachedCounterNode.calls == 1
    assert result.state.params["unrelated"] == "new"
    assert result.state.params["cached_counter"] == 1
    events = _load_trace_events(store, ctx)
    assert any(
        e.get("event") == "NODE_CACHE_STORE" and e.get("phase") == "scientist.node.cold"
        for e in events
    )
    assert any(
        e.get("event") == "NODE_CACHE_HIT" and e.get("phase") == "scientist.node.warm"
        for e in events
    )


def test_cache_replays_exact_journal_without_repeating_settled_effect(tmp_path) -> None:
    """Native CAS replay preserves operations while the real effect owner stays once."""
    import hashlib
    from decimal import Decimal

    from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
    from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
    from polisyos.scientist.orchestration.engine.protocol import NodeEvent

    run_id = "R_exact_journal_effect"
    operation_id = f"{run_id}/selected-operation-7"
    effect_bytes = operation_id.encode()
    effect_digest = hashlib.sha256(effect_bytes).hexdigest()
    effect_path = tmp_path / "effect"
    ledger_path = tmp_path / "budget.json"
    calls: list[str] = []
    first_settlements = []
    original_ledger_bytes = []

    class JournalEffectNode:
        spec = _BROAD_CACHED_SPEC.model_copy(
            update={
                "metadata": _BROAD_CACHED_METADATA.model_copy(
                    update={
                        "component_id": ComponentId.parse("scientist.node_journal_effect@1.0.0")
                    }
                )
            }
        )

        def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            calls.append(operation_id)
            # Exclusive creation distinguishes a cache replay from a second physical call.
            with effect_path.open("xb") as effect:
                effect.write(effect_bytes)
            middleware = BudgetMiddleware(
                BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
                ledger=FileBudgetLedger(ledger_path),
            )
            middleware.settle_spend_safe(
                event_id=operation_id,
                key="run",
                amount=Decimal("2"),
                provider="local-test-producer",
                payload_digest=effect_digest,
            )
            state.params["y"] = 4
            del state.params["drop"]
            state.params["null"] = None
            return NodeOutcome(
                status="ok",
                state=state,
                events=[
                    NodeEvent(
                        code="test.physical_effect",
                        message="One owned effect",
                        attrs={"operation_id": operation_id},
                    )
                ],
            )

    class ObserveAndMutate(CacheBaseMutator):
        def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
            first_settlements.append(FileBudgetLedger(ledger_path).snapshot())
            original_ledger_bytes.append(ledger_path.read_bytes())
            return super().execute(ctx, state)

    store = FileSystemCAS(tmp_path / "cas")
    ctx, registry = _build_context(store, run_id)
    registry.register(JournalEffectNode())
    registry.register(
        ObserveAndMutate(
            {"y": 9, "drop": 99, "null": 88, "unwritten": "current", "unrelated": "new"},
            delete=("removed_elsewhere",),
        )
    )
    workflow = WorkflowSpec(
        workflow_id="exact_journal_effect",
        nodes=[
            NodeInvocation(alias="cold", node_id=JournalEffectNode.spec.metadata.component_id),
            NodeInvocation(
                alias="mutate",
                node_id=_CACHE_BASE_MUTATOR_SPEC.metadata.component_id,
                depends_on=["cold"],
            ),
            NodeInvocation(
                alias="warm",
                node_id=JournalEffectNode.spec.metadata.component_id,
                depends_on=["mutate"],
            ),
        ],
    )
    origin = ExperimentState(
        run_id=run_id,
        params={
            "seed": 7,
            "y": 4,
            "drop": 1,
            "null": 8,
            "unwritten": "old",
            "unrelated": "old",
            "removed_elsewhere": "old",
        },
    )
    current = ExperimentState(
        run_id=run_id,
        params={
            "seed": 7,
            "y": 9,
            "drop": 99,
            "null": 88,
            "unwritten": "current",
            "unrelated": "new",
        },
    )
    assert compute_idempotency_key(JournalEffectNode.spec, origin) == compute_idempotency_key(
        JournalEffectNode.spec, current
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, origin)
    assert result.report.status == "ok"
    assert result.state.params == {
        "seed": 7,
        "y": 4,
        "null": None,
        "unwritten": "current",
        "unrelated": "new",
    }
    assert origin.params == {
        "seed": 7,
        "y": 4,
        "drop": 1,
        "null": 8,
        "unwritten": "old",
        "unrelated": "old",
        "removed_elsewhere": "old",
    }
    assert calls == [operation_id]
    assert effect_path.read_bytes() == effect_bytes
    assert len(first_settlements) == len(original_ledger_bytes) == 1
    first_settlement = first_settlements[0]
    assert first_settlement.state.spent["run"] == Decimal("2")
    assert ledger_path.read_bytes() == original_ledger_bytes[0]
    final_settlement = FileBudgetLedger(ledger_path).snapshot()
    assert (
        final_settlement.spend_receipts[operation_id]
        == first_settlement.spend_receipts[operation_id]
    )
    assert final_settlement.state.spent["run"] == Decimal("2")
    events = _load_trace_events(store, ctx)
    assert any(
        e.get("event") == "NODE_CACHE_STORE" and e.get("phase") == "scientist.node.cold"
        for e in events
    )
    assert any(
        e.get("event") == "NODE_CACHE_HIT" and e.get("phase") == "scientist.node.warm"
        for e in events
    )


# Production mutation caught: a cache hit must replay a declared top-level
# scalar/ref write, including when the current base still carries None.
def test_executor_cache_hit_replays_top_level_ref_write(tmp_path) -> None:
    TopLevelRefNode.calls = 0
    store = FileSystemCAS(tmp_path)
    ctx, registry = _build_context(store, "R_top_level_ref_cache")
    registry.register(CacheBaseMutator(reset_preflight=True))
    initial = ExperimentState(run_id="R_top_level_ref_cache", params={"seed": 7})
    assert compute_idempotency_key(_TOP_LEVEL_REF_SPEC, initial) == compute_idempotency_key(
        _TOP_LEVEL_REF_SPEC,
        initial.model_copy(update={"preflight_report_ref": _TOP_LEVEL_REF}, deep=True),
    )
    workflow = WorkflowSpec(
        workflow_id="top_level_ref_cache",
        nodes=[
            NodeInvocation(
                alias="cold",
                node_id=ComponentId.parse("scientist.node_top_level_ref@1.0.0"),
            ),
            NodeInvocation(
                alias="mutate",
                node_id=_CACHE_BASE_MUTATOR_SPEC.metadata.component_id,
                depends_on=["cold"],
            ),
            NodeInvocation(
                alias="warm",
                node_id=ComponentId.parse("scientist.node_top_level_ref@1.0.0"),
                depends_on=["mutate"],
            ),
        ],
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    assert result.report.status == "ok"
    assert TopLevelRefNode.calls == 1
    assert result.state.preflight_report_ref == _TOP_LEVEL_REF
    events = _load_trace_events(store, ctx)
    assert any(
        e.get("event") == "NODE_CACHE_STORE" and e.get("phase") == "scientist.node.cold"
        for e in events
    )
    assert any(
        e.get("event") == "NODE_CACHE_HIT" and e.get("phase") == "scientist.node.warm"
        for e in events
    )


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
    ctx, registry = _build_context(store, "R_invalid_replay_target")
    registry.register(CacheBaseMutator({"items": {}}))
    initial = ExperimentState(
        run_id="R_invalid_replay_target", params={"seed": 7, "items": ["cached", "removed"]}
    )
    warm_base = ExperimentState(run_id=initial.run_id, params={"seed": 7, "items": {}})
    assert compute_idempotency_key(_INVALID_REPLAY_SPEC, initial) == compute_idempotency_key(
        _INVALID_REPLAY_SPEC, warm_base
    )
    workflow = WorkflowSpec(
        workflow_id="invalid_replay_target",
        nodes=[
            NodeInvocation(
                alias="cold",
                node_id=ComponentId.parse("scientist.node_invalid_replay@1.0.0"),
            ),
            NodeInvocation(
                alias="mutate",
                node_id=_CACHE_BASE_MUTATOR_SPEC.metadata.component_id,
                depends_on=["cold"],
            ),
            NodeInvocation(
                alias="warm",
                node_id=ComponentId.parse("scientist.node_invalid_replay@1.0.0"),
                depends_on=["mutate"],
            ),
        ],
    )
    result = WorkflowExecutor(ctx, registry).execute(workflow, initial)
    assert result.report.status == "ok"
    assert InvalidReplayNode.calls == 2
    assert result.state.params["items"] == {}
    assert result.state.params["reexecuted"] is True
    events = _load_trace_events(store, ctx)
    assert any(
        e.get("event") == "NODE_CACHE_BYPASS"
        and e.get("phase") == "scientist.node.warm"
        and e.get("metrics", {}).get("reason_code") == 4
        for e in events
    )
    assert not any(
        e.get("event") == "NODE_CACHE_HIT" and e.get("phase") == "scientist.node.warm"
        for e in events
    )


def test_executor_refuses_blind_resume_after_known_failure(tmp_path) -> None:
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
    with pytest.raises(ValueError, match="workflow_execution_admission_frontier_not_reconciled"):
        WorkflowExecutor(ctx_b, registry_b).execute(workflow, initial_state)
    assert CachedCounterNode.calls == 1
    assert AlwaysFailNode.calls == 1


def test_executor_cached_success_and_distinct_failed_aliases(tmp_path) -> None:
    CachedCounterNode.calls = 0
    AlwaysFailNode.calls = 0
    store = FileSystemCAS(tmp_path)
    ctx, registry = _build_context(store, "R_distinct_cache_failures")
    workflow = WorkflowSpec(
        workflow_id="cache_distinct_failures",
        error_policy="continue",
        nodes=[
            NodeInvocation(alias="cold", node_id=_CACHED_SPEC.metadata.component_id),
            NodeInvocation(
                alias="first_failure",
                node_id=_FAIL_SPEC.metadata.component_id,
                depends_on=["cold"],
            ),
            NodeInvocation(
                alias="warm",
                node_id=_CACHED_SPEC.metadata.component_id,
                depends_on=["cold"],
            ),
            NodeInvocation(
                alias="second_failure",
                node_id=_FAIL_SPEC.metadata.component_id,
                depends_on=["warm"],
            ),
        ],
    )
    result = WorkflowExecutor(ctx, registry).execute(
        workflow, ExperimentState(run_id="R_distinct_cache_failures", params={"seed": 42})
    )
    assert result.report.status == "fail"
    assert CachedCounterNode.calls == 1
    assert AlwaysFailNode.calls == 2
    assert {record.alias: record.status for record in result.report.nodes} == {
        "cold": "ok",
        "first_failure": "fail",
        "warm": "ok",
        "second_failure": "fail",
    }
    assert any(
        event.get("event") == "NODE_CACHE_HIT" and event.get("phase") == "scientist.node.warm"
        for event in _load_trace_events(store, ctx)
    )


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


def test_incomplete_process_run_resumes_same_cache_and_one_terminal_lifecycle(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3
    from decimal import Decimal

    from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger

    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    run_id = "R_process_loss_resume"
    root = tmp_path / "cas"
    database = tmp_path / "effect.sqlite3"
    ledger = tmp_path / "budget.json"
    process = multiprocessing.get_context("spawn").Process(
        target=produce_cached_checkpoint_then_exit,
        args=(str(root), run_id, str(database), str(ledger)),
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
    assert (
        sum(
            event.get("event") == "NODE_CACHE_STORE" and event.get("phase") == "scientist.node.cold"
            for event in child_events
        )
        == 1
    )

    store = FileSystemCAS(root)
    run_dir = root / "runs" / run_id
    resolved = resolve_latest_checkpoint(store, run_id, run_dir=run_dir)
    assert resolved is not None
    _, checkpoint = resolved
    assert checkpoint.metadata.completed_nodes == ["cold", "mutate"]
    assert checkpoint.metadata.execution_budget_contract == "admitted_workflow_budget_v1"
    assert all(store.verify(ref).ok for ref in checkpoint.metadata.cache_entry_refs)
    entries = [
        NodeCacheEntry.model_validate(from_canonical_bytes(store.get_bytes(ref)))
        for ref in checkpoint.metadata.cache_entry_refs
    ]
    assert checkpoint.state is not None
    restored = ExperimentState.model_validate(checkpoint.state)
    bundle_ref = restored.inputs["registry_bundle_ref"]
    cold = ExperimentState(
        run_id=run_id, inputs={"registry_bundle_ref": bundle_ref}, params={"seed": 7}
    )
    node = CheckpointedCacheEffectNode(database, ledger, value=7)
    cold_key = compute_idempotency_key(node.spec, cold)
    assert cold_key == compute_idempotency_key(node.spec, restored)
    original_entries = [
        entry for entry in entries if entry.node_id == "scientist.node_admission_probe@1.0.0"
    ]
    assert len(original_entries) == 1 and original_entries[0].idempotency_key == cold_key
    assert restored.params == {
        "seed": 7,
        "result": 7,
        "y": 9,
        "drop": 99,
        "null": 88,
        "unwritten": "current",
        "unrelated": "new",
    }
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM effects").fetchone() == (1,)
    first_settlement = FileBudgetLedger(ledger).snapshot()
    original_ledger = ledger.read_bytes()
    assert first_settlement.state.spent["run"] == Decimal("2")

    result = resume_from_checkpoint(
        store,
        run_id,
        workflow=checkpointed_cache_workflow(),
        registry=checkpointed_cache_registry(database, ledger),
        registry_bundle_ref=bundle_ref,
        run_dir=run_dir,
        require_reconciled_attempts=True,
    )
    assert result.report.status == "ok"
    assert [record.alias for record in result.report.nodes] == ["warm"]
    assert result.state.run_id == run_id
    assert result.state.params == {
        "seed": 7,
        "result": 7,
        "y": 4,
        "null": None,
        "unwritten": "current",
        "unrelated": "new",
    }
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM effects").fetchone() == (1,)
    final_settlement = FileBudgetLedger(ledger).snapshot()
    operation_id = f"{run_id}/selected-operation-7"
    assert ledger.read_bytes() == original_ledger
    assert len(first_settlement.spend_receipts) == len(final_settlement.spend_receipts) == 1
    assert (
        final_settlement.spend_receipts[operation_id]
        == first_settlement.spend_receipts[operation_id]
    )
    assert final_settlement.state.spent["run"] == Decimal("2")

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
    assert sum(record.get("event") == "RUN_STARTED" for record in records) == 1
    assert sum(record.get("event") == "RUN_RESUMED" for record in records) == 1
    assert sum(record.get("event") == "RUN_FINALIZED" for record in records) == 1
    assert sum(record.get("event") == "NODE_CACHE_HIT" for record in records) == 1
    assert any(
        record.get("event") == "NODE_CACHE_HIT" and record.get("phase") == "scientist.node.warm"
        for record in records
    )
    assert terminal.manifest_ref.manifest_profile_sha256 is not None

    from polisyos.core.artifacts.manifest import artifact_ref_identity_key

    finalized_records = [record for record in records if record.get("event") == "RUN_FINALIZED"]
    assert len(finalized_records) == 1
    finalization_inputs = finalized_records[0]["refs"]["inputs"]
    assert len(finalization_inputs) == 1
    finalization_ref = ArtifactRef.model_validate(finalization_inputs[0])
    assert terminal.workflow_finalization_ref is not None
    assert artifact_ref_identity_key(terminal.workflow_finalization_ref) == (
        artifact_ref_identity_key(finalization_ref)
    )
    assert terminal.workflow_finalization_ref.kind == "scientist.workflow_state_finalization"
    assert terminal.workflow_finalization_ref.media_type == "application/json"
    assert terminal.workflow_finalization_ref.manifest_profile_sha256 is not None
    assert (
        sum(
            artifact_ref_identity_key(ref)
            == artifact_ref_identity_key(terminal.workflow_finalization_ref)
            for ref in terminal.manifest.outputs
        )
        == 1
    )

    original_trace_bytes = terminal.trace_path.read_bytes()
    original_manifest_bytes = store.get_bytes(terminal.manifest_ref)
    original_finalization_bytes = store.get_bytes(terminal.workflow_finalization_ref)
    try:
        records_without_terminal_input = [
            json.loads(line)
            for line in original_trace_bytes.decode("utf-8").splitlines()
            if line.strip()
        ]
        finalized = next(
            record
            for record in records_without_terminal_input
            if record.get("event") == "RUN_FINALIZED"
        )
        finalized["refs"]["inputs"] = []
        terminal.trace_path.write_bytes(
            b"\n".join(
                json.dumps(record, separators=(",", ":")).encode("utf-8")
                for record in records_without_terminal_input
            )
            + b"\n"
        )
        without_finalization_input = load_terminal_core_run_source(
            store=store,
            core_runs_root=root / "runs",
            run_id=run_id,
        )
        assert without_finalization_input.workflow_finalization_ref is None
        assert artifact_ref_identity_key(without_finalization_input.manifest_ref) == (
            artifact_ref_identity_key(terminal.manifest_ref)
        )
        outputs_without_finalization = [
            artifact_ref_identity_key(ref) for ref in without_finalization_input.manifest.outputs
        ]
        original_outputs = [artifact_ref_identity_key(ref) for ref in terminal.manifest.outputs]
        assert outputs_without_finalization == original_outputs
        assert store.get_bytes(without_finalization_input.manifest_ref) == original_manifest_bytes
        assert store.get_bytes(terminal.workflow_finalization_ref) == original_finalization_bytes
    finally:
        terminal.trace_path.write_bytes(original_trace_bytes)
    assert terminal.trace_path.read_bytes() == original_trace_bytes


def test_terminal_finalization_ref_is_unique_selected_profile_and_manifest_linked(
    monkeypatch,
) -> None:
    from pathlib import Path
    from types import SimpleNamespace

    from polisyos.core.trace import RunTerminality
    from polisyos.core.trace.record import TraceRecord, TraceRefs
    from polisyos.runtime.http.services.adapters import core_run

    run_id = "R_terminal_finalization_ref_selection"
    manifest_ref = ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="core.run_manifest",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )

    def ref(
        number: int,
        *,
        kind: str = "scientist.workflow_state_finalization",
        media_type: str = "application/json",
        profile: str | None = "sha256:" + "b" * 64,
    ) -> ArtifactRef:
        return ArtifactRef(
            artifact_id=f"sha256:{number:064x}",
            kind=kind,
            media_type=media_type,
            manifest_profile_sha256=profile,
        )

    finalization = ref(2)
    prior_state = ref(3, kind="scientist.experiment_state")
    final_state = ref(4, kind="scientist.experiment_state")

    def load(*, terminal_inputs, manifest_outputs):
        records = {
            "started": TraceRecord(
                run_id=run_id,
                phase="core",
                event="RUN_STARTED",
                run_terminality=RunTerminality.NON_TERMINAL,
                tenant_id="tenant-test",
                cell_id="cell-test",
            ),
            "finalized": TraceRecord(
                run_id=run_id,
                phase="core",
                event="RUN_FINALIZED",
                run_terminality=RunTerminality.TERMINAL,
                tenant_id="tenant-test",
                cell_id="cell-test",
                refs=TraceRefs(inputs=terminal_inputs, outputs=[manifest_ref]),
            ),
        }
        manifest = SimpleNamespace(
            run_id=run_id,
            tenant_id="tenant-test",
            cell_id="cell-test",
            outputs=manifest_outputs,
        )
        monkeypatch.setattr(
            core_run,
            "_iter_strict_terminal_trace_lines",
            lambda *_args, **_kwargs: ("started", "finalized"),
        )
        monkeypatch.setattr(core_run, "_parse_trace_record", records.__getitem__)
        monkeypatch.setattr(core_run, "load_bound_terminal_manifest", lambda **_kwargs: manifest)
        return core_run.load_terminal_core_run_source(
            store=object(),
            core_runs_root=Path("/tmp/terminal-finalization-selection"),
            run_id=run_id,
        )

    selected = load(
        terminal_inputs=[finalization],
        manifest_outputs=[prior_state, final_state, finalization],
    )
    assert selected.workflow_finalization_ref == finalization

    historical_finalization = ref(5)
    resumed = load(
        terminal_inputs=[finalization],
        manifest_outputs=[
            prior_state,
            historical_finalization,
            final_state,
            finalization,
        ],
    )
    assert resumed.workflow_finalization_ref == finalization

    profileless = ref(2, profile=None)
    alternate_profile = ref(2, profile="sha256:" + "c" * 64)
    wrong_kind = ref(2, kind="scientist.experiment_state")
    wrong_media = ref(2, media_type="application/octet-stream")
    cases = [
        ([], [finalization]),
        ([finalization, finalization], [finalization]),
        ([finalization], [finalization, finalization]),
        ([finalization], [prior_state, final_state]),
        ([profileless], [finalization]),
        ([finalization], [alternate_profile]),
        ([wrong_kind], [wrong_kind]),
        ([wrong_media], [wrong_media]),
    ]
    for terminal_inputs, manifest_outputs in cases:
        result = load(terminal_inputs=terminal_inputs, manifest_outputs=manifest_outputs)
        assert result.workflow_finalization_ref is None

    from polisyos.runtime.http.services.adapters.core_run import TerminalCoreRunSource

    legacy = TerminalCoreRunSource(
        run_id="legacy-terminal",
        tenant_id=None,
        cell_id=None,
        run_dir=Path("/tmp/legacy-terminal"),
        trace_path=Path("/tmp/legacy-terminal/trace.jsonl"),
        manifest_ref=manifest_ref,
        manifest=SimpleNamespace(),
    )
    assert legacy.workflow_finalization_ref is None

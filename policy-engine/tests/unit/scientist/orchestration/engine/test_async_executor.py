"""Tests for polisyos.scientist.orchestration.engine.async_executor — AsyncWorkflowExecutor."""

from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.idempotency import NodeResultCache
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_FAKE_SHA = "sha256:" + "ab" * 32


def _make_ctx(*, metrics=None):
    store = MagicMock()
    store.put_json.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA,
        kind="test",
        media_type="application/json",
    )
    run = MagicMock()
    run.trace_path = None
    run.finalize.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA,
        kind="run",
        media_type="application/json",
    )
    return ExecutionContext(
        store=store,
        run=run,
        logger=MagicMock(),
        metrics=metrics,
    )


def _make_mock_node(*, node_id="test.node@1.0.0", state_writes=None):
    node = MagicMock()
    node.spec = MagicMock(spec=NodeSpec)
    node.spec.state_reads = []
    node.spec.state_writes = state_writes or []
    node.spec.node_id = node_id
    return node


def _cache_node_spec(
    node_id: str,
    *,
    state_reads: list[str] | None = None,
    state_writes: list[str] | None = None,
) -> NodeSpec:
    return NodeSpec(
        metadata=ComponentMetadata(
            component_id=ComponentId.parse(node_id),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="Async cache test node",
            description="Test node for async cache behavior",
            tags=["test"],
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_reads=list(state_reads or ["params.seed"]),
        state_writes=list(state_writes or ["params.result"]),
        produces=[],
    )


class _CacheTestNode:
    def __init__(self, spec: NodeSpec, *, incompatible_target: bool = False) -> None:
        self.spec = spec
        self.calls = 0
        self._incompatible_target = incompatible_target

    def execute(self, ctx, state):
        del ctx
        self.calls += 1
        if self._incompatible_target:
            items = state.params.get("items")
            if isinstance(items, list):
                items.pop()
            else:
                state.params["reexecuted"] = True
        else:
            state.params["result"] = self.calls
        return NodeOutcome(status="ok", state=state)


def _make_real_store_ctx(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    run = MagicMock()
    run.trace_path = None
    run.finalize.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA,
        kind="run",
        media_type="application/json",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("async_executor_test"),
    )
    return store, ctx


def _artifact_id_strings(store) -> set[str]:
    """Normalize immutable CAS identities without relying on RootModel hashing."""
    return {str(artifact_id) for artifact_id in store.iter_artifact_ids()}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAsyncWorkflowExecutor:
    @pytest.mark.asyncio
    async def test_simple_linear_dag(self):
        """A→B→C — same result as sync."""
        state = ExperimentState(run_id="async-test-001")

        node = _make_mock_node()
        node.execute.return_value = NodeOutcome(
            status="ok",
            state=state,
            events=[],
            artifacts=[],
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        workflow = WorkflowSpec(
            workflow_id="test_linear",
            nodes=[
                NodeInvocation(alias="step_a", node_id="test.node@1.0.0"),
                NodeInvocation(alias="step_b", node_id="test.node@1.0.0", depends_on=["step_a"]),
                NodeInvocation(alias="step_c", node_id="test.node@1.0.0", depends_on=["step_b"]),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert len(result.report.nodes) == 3
        assert all(r.status == "ok" for r in result.report.nodes)

    @pytest.mark.asyncio
    async def test_parallel_tier(self):
        """A→(B,C)→D — B and C run in parallel."""
        state = ExperimentState(run_id="async-test-002")

        call_order = []

        def _make_execute(alias):
            def _execute(ctx, st):
                call_order.append(alias)
                return NodeOutcome(status="ok", state=st, events=[], artifacts=[])

            return _execute

        def _get_node(node_id):
            alias = str(node_id).split("@")[0].split(".")[-1]
            node = _make_mock_node(node_id=str(node_id))
            node.execute.side_effect = _make_execute(alias)
            return node

        registry = MagicMock(spec=NodeRegistry)
        registry.get.side_effect = _get_node

        workflow = WorkflowSpec(
            workflow_id="test_parallel",
            nodes=[
                NodeInvocation(alias="a", node_id="test.a@1.0.0"),
                NodeInvocation(alias="b", node_id="test.b@1.0.0", depends_on=["a"]),
                NodeInvocation(alias="c", node_id="test.c@1.0.0", depends_on=["a"]),
                NodeInvocation(alias="d", node_id="test.d@1.0.0", depends_on=["b", "c"]),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert len(result.report.nodes) == 4

        # A must be first, D must be last, B and C in middle (any order)
        aliases = [r.alias for r in result.report.nodes]
        assert aliases[0] == "a"
        assert set(aliases[1:3]) == {"b", "c"}
        assert aliases[3] == "d"

    @pytest.mark.asyncio
    async def test_failed_node_blocks_downstream(self):
        """A→B→C — if B fails, C should be skipped."""
        state = ExperimentState(run_id="async-test-003")

        def _get_node(node_id):
            alias = str(node_id).split("@")[0].split(".")[-1]
            node = _make_mock_node(node_id=str(node_id))
            if alias == "b":
                node.execute.return_value = NodeOutcome(
                    status="fail",
                    state=state,
                    events=[],
                    artifacts=[],
                    error=NodeError(code="node.exception", message="b failed"),
                )
            else:
                node.execute.return_value = NodeOutcome(
                    status="ok",
                    state=state,
                    events=[],
                    artifacts=[],
                )
            return node

        registry = MagicMock(spec=NodeRegistry)
        registry.get.side_effect = _get_node

        workflow = WorkflowSpec(
            workflow_id="test_fail",
            nodes=[
                NodeInvocation(alias="a", node_id="test.a@1.0.0"),
                NodeInvocation(alias="b", node_id="test.b@1.0.0", depends_on=["a"]),
                NodeInvocation(alias="c", node_id="test.c@1.0.0", depends_on=["b"]),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "fail"
        statuses = {r.alias: r.status for r in result.report.nodes}
        assert statuses["a"] == "ok"
        assert statuses["b"] == "fail"
        assert statuses["c"] == "skip"

    @pytest.mark.asyncio
    async def test_max_parallelism_one_degrades_to_sequential(self):
        """max_parallelism=1 → nodes execute sequentially even in parallel tier."""
        state = ExperimentState(run_id="async-test-004")

        order = []

        def _get_node(node_id):
            alias = str(node_id).split("@")[0].split(".")[-1]
            node = _make_mock_node(node_id=str(node_id))

            def _execute(ctx, st):
                order.append(alias)
                return NodeOutcome(status="ok", state=st, events=[], artifacts=[])

            node.execute.side_effect = _execute
            return node

        registry = MagicMock(spec=NodeRegistry)
        registry.get.side_effect = _get_node

        workflow = WorkflowSpec(
            workflow_id="test_seq",
            nodes=[
                NodeInvocation(alias="a", node_id="test.a@1.0.0"),
                NodeInvocation(alias="b", node_id="test.b@1.0.0"),
                NodeInvocation(alias="c", node_id="test.c@1.0.0"),
            ],
        )

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry, max_parallelism=1)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert len(order) == 3

    @pytest.mark.asyncio
    async def test_metrics_tier_completed_called(self):
        """Verify record_tier_completed is called for each tier."""
        state = ExperimentState(run_id="async-test-005")

        node = _make_mock_node()
        node.execute.return_value = NodeOutcome(
            status="ok",
            state=state,
            events=[],
            artifacts=[],
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        metrics = MagicMock()
        ctx = _make_ctx(metrics=metrics)

        workflow = WorkflowSpec(
            workflow_id="test_metrics",
            nodes=[
                NodeInvocation(alias="a", node_id="test.node@1.0.0"),
                NodeInvocation(alias="b", node_id="test.node@1.0.0", depends_on=["a"]),
            ],
        )

        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert metrics.record_tier_completed.call_count == 2
        assert metrics.record_workflow_completed.call_count == 1

    @pytest.mark.asyncio
    async def test_async_executor_persists_via_async_artifact_store_adapter(self, monkeypatch):
        state = ExperimentState(run_id="async-test-persist")
        node = _make_mock_node()
        node.execute.return_value = NodeOutcome(
            status="ok",
            state=state,
            events=[],
            artifacts=[],
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node
        workflow = WorkflowSpec(
            workflow_id="test_async_persist",
            nodes=[NodeInvocation(alias="a", node_id="test.node@1.0.0")],
        )

        seen_kinds: list[str] = []
        original_put_json = AsyncArtifactStoreAdapter.put_json

        async def _tracked_put_json(self, obj, opts, canon_spec=None):
            seen_kinds.append(str(getattr(opts, "kind", "")))
            return await original_put_json(self, obj, opts, canon_spec=canon_spec)

        monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)

        ctx = _make_ctx()
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert seen_kinds[:3] == [
            "scientist.workflow_spec",
            "scientist.experiment_state",
            "scientist.workflow_report",
        ]

    @pytest.mark.asyncio
    async def test_no_metrics_no_crash(self):
        """When metrics is None, async executor should not crash."""
        state = ExperimentState(run_id="async-test-006")

        node = _make_mock_node()
        node.execute.return_value = NodeOutcome(
            status="ok",
            state=state,
            events=[],
            artifacts=[],
        )

        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node

        ctx = _make_ctx(metrics=None)
        workflow = WorkflowSpec(
            workflow_id="test_no_metrics",
            nodes=[NodeInvocation(alias="a", node_id="test.node@1.0.0")],
        )

        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)
        assert result.report.status == "ok"


class TestAsyncCacheBoundaries:
    @pytest.mark.asyncio
    async def test_cache_hit_reads_with_exhausted_compute_budget_but_miss_does_not(
        self, tmp_path
    ):
        """A permitted cache hit must not consume or require new compute budget."""
        node_id = "test.async_cache_budget@1.0.0"
        node = _CacheTestNode(_cache_node_spec(node_id))
        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node
        store, ctx = _make_real_store_ctx(tmp_path)
        executor = AsyncWorkflowExecutor(ctx, registry)
        executor._cache = NodeResultCache(store, run_id="async-cache-budget")
        invocation = NodeInvocation(alias="cached", node_id=node_id)
        workflow = WorkflowSpec(workflow_id="async_cache_budget", nodes=[invocation])

        initial = ExperimentState(run_id="async-cache-budget", params={"seed": 1})
        first, _, first_hit, _ = await executor._execute_node(
            "cached", invocation, initial, workflow
        )
        assert first.status == "ok"
        assert first_hit is False
        assert node.calls == 1

        budget = BudgetMiddleware(
            BudgetState(
                limits={
                    "read": BudgetLimit(key="read", max_usd=Decimal("1")),
                    "run": BudgetLimit(key="run", max_usd=Decimal("1")),
                },
                spent={"read": Decimal("0"), "run": Decimal("0")},
            )
        )
        executor._budget_middleware = budget
        budget.budget_state.spent["run"] = Decimal("1")
        hit, _, cache_hit, _ = await executor._execute_node(
            "cached",
            invocation,
            ExperimentState(run_id="async-cache-budget", params={"seed": 1}),
            workflow,
        )
        assert hit.status == "ok"
        assert cache_hit is True
        assert hit.state.params["result"] == 1
        assert node.calls == 1

        budget.budget_state.spent["read"] = Decimal("1")
        denied_hit, _, denied_cache_hit, _ = await executor._execute_node(
            "cached",
            invocation,
            ExperimentState(run_id="async-cache-budget", params={"seed": 1}),
            workflow,
        )
        assert denied_hit.status == "fail"
        assert denied_hit.error is not None
        assert denied_hit.error.code == "node.budget_exhausted"
        assert denied_hit.error.details["budget_key"] == "read"
        assert denied_cache_hit is False
        assert node.calls == 1

        budget.budget_state.spent["read"] = Decimal("0")
        executor._cache.clear()
        miss, _, miss_hit, _ = await executor._execute_node(
            "cached",
            invocation,
            ExperimentState(run_id="async-cache-budget", params={"seed": 1}),
            workflow,
        )
        assert miss.status == "fail"
        assert miss.error is not None
        assert miss.error.code == "node.budget_exhausted"
        assert miss_hit is False
        assert node.calls == 1

    @pytest.mark.asyncio
    async def test_cache_io_does_not_block_independent_coroutine(self, tmp_path, monkeypatch):
        """A slow local cache read must yield to unrelated event-loop work."""
        node_id = "test.async_cache_io@1.0.0"
        node = _CacheTestNode(_cache_node_spec(node_id))
        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node
        store, ctx = _make_real_store_ctx(tmp_path)
        executor = AsyncWorkflowExecutor(ctx, registry)
        executor._cache = NodeResultCache(store, run_id="async-cache-io")
        invocation = NodeInvocation(alias="cached", node_id=node_id)
        workflow = WorkflowSpec(workflow_id="async_cache_io", nodes=[invocation])

        await executor._execute_node(
            "cached",
            invocation,
            ExperimentState(run_id="async-cache-io", params={"seed": 1}),
            workflow,
        )

        original_get_bytes = store.get_bytes

        def slow_get_bytes(artifact_id):
            time.sleep(0.08)
            return original_get_bytes(artifact_id)

        monkeypatch.setattr(store, "get_bytes", slow_get_bytes)
        ticks = 0
        finished = asyncio.Event()

        async def tick() -> None:
            nonlocal ticks
            while not finished.is_set():
                ticks += 1
                await asyncio.sleep(0)

        ticker = asyncio.create_task(tick())
        try:
            hit, _, cache_hit, _ = await executor._execute_node(
                "cached",
                invocation,
                ExperimentState(run_id="async-cache-io", params={"seed": 1}),
                workflow,
            )
        finally:
            finished.set()
            await ticker

        assert hit.status == "ok"
        assert cache_hit is True
        assert node.calls == 1
        assert ticks > 0

    @pytest.mark.asyncio
    async def test_cache_put_does_not_block_and_failed_entry_is_not_published(
        self, tmp_path, monkeypatch
    ):
        """Cache publication is off-loop and the index stays atomic on write failure."""
        node_id = "test.async_cache_put@1.0.0"
        node = _CacheTestNode(_cache_node_spec(node_id))
        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node
        store, ctx = _make_real_store_ctx(tmp_path)
        executor = AsyncWorkflowExecutor(ctx, registry)
        executor._cache = NodeResultCache(store, run_id="async-cache-put")
        invocation = NodeInvocation(alias="cached", node_id=node_id)
        workflow = WorkflowSpec(workflow_id="async_cache_put", nodes=[invocation])

        original_put_json = store.put_json
        put_calls = 0
        put_phase: str | None = None
        phase_ticks = {"outcome": 0, "entry": 0}

        def slow_put_json(*args, **kwargs):
            nonlocal put_calls, put_phase
            put_calls += 1
            if put_calls == 1:
                put_phase = "outcome"
                phase_ticks["outcome"] = 0
            elif put_calls == 2:
                put_phase = "entry"
                phase_ticks["entry"] = 0
            time.sleep(0.08)
            return original_put_json(*args, **kwargs)

        monkeypatch.setattr(store, "put_json", slow_put_json)
        finished = asyncio.Event()

        async def tick() -> None:
            while not finished.is_set():
                if put_phase in phase_ticks:
                    phase_ticks[put_phase] += 1
                await asyncio.sleep(0)

        ticker = asyncio.create_task(tick())
        try:
            outcome, _, cache_hit, _ = await executor._execute_node(
                "cached",
                invocation,
                ExperimentState(run_id="async-cache-put", params={"seed": 1}),
                workflow,
            )
        finally:
            finished.set()
            await ticker

        assert outcome.status == "ok"
        assert cache_hit is False
        assert executor._cache.size == 1
        assert put_calls >= 2
        assert phase_ticks["outcome"] > 0
        assert phase_ticks["entry"] > 0

        executor._cache.clear()
        ids_before_failed_publication = _artifact_id_strings(store)
        calls = 0

        def fail_entry_put(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("entry publication interrupted")
            return original_put_json(*args, **kwargs)

        monkeypatch.setattr(store, "put_json", fail_entry_put)
        outcome, _, cache_hit, _ = await executor._execute_node(
            "cached",
            invocation,
            ExperimentState(run_id="async-cache-put", params={"seed": 2}),
            workflow,
        )
        assert outcome.status == "ok"
        assert cache_hit is False
        assert executor._cache.size == 0
        assert _artifact_id_strings(store) == ids_before_failed_publication

    @pytest.mark.asyncio
    async def test_failed_cache_entry_does_not_publish_partial_cas_artifacts(
        self, tmp_path, monkeypatch
    ):
        """A failed cache-entry write leaves neither an index entry nor an orphan CAS epoch."""
        node_id = "test.async_cache_atomicity@1.0.0"
        node = _CacheTestNode(_cache_node_spec(node_id))
        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node
        store, ctx = _make_real_store_ctx(tmp_path)
        executor = AsyncWorkflowExecutor(ctx, registry)
        executor._cache = NodeResultCache(store, run_id="async-cache-atomicity")
        invocation = NodeInvocation(alias="cached", node_id=node_id)
        workflow = WorkflowSpec(workflow_id="async_cache_atomicity", nodes=[invocation])
        ids_before_failed_publication = _artifact_id_strings(store)

        original_put_json = store.put_json
        put_calls = 0

        def fail_entry_put(*args, **kwargs):
            nonlocal put_calls
            put_calls += 1
            if put_calls == 2:
                raise OSError("entry publication interrupted")
            return original_put_json(*args, **kwargs)

        monkeypatch.setattr(store, "put_json", fail_entry_put)
        outcome, _, cache_hit, _ = await executor._execute_node(
            "cached",
            invocation,
            ExperimentState(run_id="async-cache-atomicity", params={"seed": 1}),
            workflow,
        )

        assert outcome.status == "ok"
        assert cache_hit is False
        assert put_calls == 2
        assert executor._cache.size == 0
        assert _artifact_id_strings(store) == ids_before_failed_publication

    @pytest.mark.asyncio
    async def test_incompatible_cached_replay_is_discarded_and_recomputed(self, tmp_path):
        """A stale state target must not publish cached state or fail the workflow."""
        node_id = "test.async_cache_replay@1.0.0"
        spec = _cache_node_spec(node_id, state_writes=["params.items"])
        node = _CacheTestNode(spec, incompatible_target=True)
        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node
        store, ctx = _make_real_store_ctx(tmp_path)
        executor = AsyncWorkflowExecutor(ctx, registry)
        executor._cache = NodeResultCache(store, run_id="async-cache-replay")
        invocation = NodeInvocation(alias="cached", node_id=node_id)
        workflow = WorkflowSpec(workflow_id="async_cache_replay", nodes=[invocation])

        first, _, _, _ = await executor._execute_node(
            "cached",
            invocation,
            ExperimentState(
                run_id="async-cache-replay",
                params={"seed": 1, "items": ["stale"]},
            ),
            workflow,
        )
        assert first.status == "ok"
        assert node.calls == 1

        fresh, _, cache_hit, _ = await executor._execute_node(
            "cached",
            invocation,
            ExperimentState(
                run_id="async-cache-replay",
                params={"seed": 1, "items": {}},
            ),
            workflow,
        )
        assert fresh.status == "ok"
        assert cache_hit is False
        assert fresh.state.params["items"] == {"reexecuted": True}
        assert node.calls == 2


class TestAsyncFailFastAdmission:
    @pytest.mark.asyncio
    async def test_fail_fast_rechecks_cancellation_after_semaphore_acquire(self):
        """Queued nodes skip after an earlier failure, without starting their producer."""

        class _FailFastNode:
            def __init__(self, node_id: str, *, fails: bool) -> None:
                self.spec = _cache_node_spec(node_id)
                self.fails = fails
                self.calls = 0

            def execute(self, ctx, state):
                del ctx
                self.calls += 1
                if self.fails:
                    time.sleep(0.04)
                    return NodeOutcome(
                        status="fail",
                        state=state,
                        error=NodeError(
                            code="node.expected_failure",
                            message="expected fail-fast witness",
                            details={},
                        ),
                    )
                return NodeOutcome(status="ok", state=state)

        first = _FailFastNode("test.fail_fast_first@1.0.0", fails=True)
        second = _FailFastNode("test.fail_fast_second@1.0.0", fails=False)
        third = _FailFastNode("test.fail_fast_third@1.0.0", fails=False)
        nodes = {
            first.spec.metadata.component_id.root: first,
            second.spec.metadata.component_id.root: second,
            third.spec.metadata.component_id.root: third,
        }
        registry = MagicMock(spec=NodeRegistry)
        registry.get.side_effect = lambda node_id: nodes[str(node_id)]
        workflow = WorkflowSpec(
            workflow_id="async_fail_fast_admission",
            error_policy="fail_fast",
            nodes=[
                NodeInvocation(alias="first", node_id="test.fail_fast_first@1.0.0"),
                NodeInvocation(alias="second", node_id="test.fail_fast_second@1.0.0"),
                NodeInvocation(alias="third", node_id="test.fail_fast_third@1.0.0"),
            ],
        )

        result = await AsyncWorkflowExecutor(
            _make_ctx(),
            registry,
            max_parallelism=1,
        ).execute(workflow, ExperimentState(run_id="async-fail-fast"))

        records = {record.alias: record for record in result.report.nodes}
        assert records["first"].status == "fail"
        assert records["second"].status == "skip"
        assert records["third"].status == "skip"
        assert first.calls == 1
        assert second.calls == 0
        assert third.calls == 0

    @pytest.mark.asyncio
    async def test_metric_failure_after_semaphore_acquire_releases_slot(self):
        """Telemetry failure must not strand a slot or skip queued producers."""

        class _SlowNode:
            def __init__(self, node_id: str) -> None:
                self.spec = _cache_node_spec(node_id)
                self.calls = 0

            def execute(self, ctx, state):
                del ctx
                self.calls += 1
                time.sleep(0.04)
                return NodeOutcome(status="ok", state=state)

        first = _SlowNode("test.metric_first@1.0.0")
        second = _SlowNode("test.metric_second@1.0.0")
        nodes = {
            first.spec.metadata.component_id.root: first,
            second.spec.metadata.component_id.root: second,
        }
        registry = MagicMock(spec=NodeRegistry)
        registry.get.side_effect = lambda node_id: nodes[str(node_id)]
        metrics = MagicMock()
        metrics.record_semaphore_wait.side_effect = RuntimeError("telemetry unavailable")
        workflow = WorkflowSpec(
            workflow_id="async_metric_failure",
            error_policy="continue",
            nodes=[
                NodeInvocation(alias="first", node_id="test.metric_first@1.0.0"),
                NodeInvocation(alias="second", node_id="test.metric_second@1.0.0"),
            ],
        )

        result = await AsyncWorkflowExecutor(
            _make_ctx(metrics=metrics),
            registry,
            max_parallelism=1,
        ).execute(workflow, ExperimentState(run_id="async-metric-failure"))

        assert result.report.status == "ok"
        assert {record.status for record in result.report.nodes} == {"ok"}
        assert first.calls == 1
        assert second.calls == 1
        assert metrics.record_semaphore_wait.call_count >= 1

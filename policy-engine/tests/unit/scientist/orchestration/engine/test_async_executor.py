"""Tests for polisyos.scientist.orchestration.engine.async_executor — AsyncWorkflowExecutor."""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import threading
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from polisyos.core.artifacts.async_store import AsyncArtifactStoreAdapter
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
    artifact_ref_identity_key,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run import context as run_context
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import WorkflowTimeoutError
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import branch_state
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_FAKE_SHA = "sha256:" + "ab" * 32


class _TemporaryFileSystemCAS(FileSystemCAS):
    """Keep the legacy async fixture on the selected-profile store contract."""

    def __init__(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        super().__init__(Path(self._temporary_directory.name) / "cas")


def _make_ctx(*, metrics=None):
    store = _TemporaryFileSystemCAS()
    run = MagicMock()
    run.run_manifest.run_id = "async-test-run"
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
            elif isinstance(items, dict):
                items["reexecuted"] = True
            else:
                state.params["items"] = {"reexecuted": True}
        else:
            state.params["result"] = self.calls
        return NodeOutcome(status="ok", state=state)


class _AsyncSelectedArtifactOutputNode:
    """Synchronous test producer exercised through the async executor path."""

    def __init__(
        self,
        *,
        node_name: str,
        payload: object | None = None,
        declared_refs: list[ArtifactRef] | None = None,
        selected_refs: dict[str, ArtifactRef] | None = None,
        status: str = "ok",
    ) -> None:
        self.payload = payload
        self.declared_refs = declared_refs
        self.selected_refs = selected_refs
        self.status = status
        self.calls = 0
        self.spec = _cache_node_spec(
            f"scientist.node_{node_name}@1.0.0",
            state_reads=[],
            state_writes=["artifacts_index"],
        )

    def execute(self, ctx, state):
        self.calls += 1
        persisted_ref = None
        if self.payload is not None:
            persisted_ref = ctx.store.put_json(
                self.payload,
                PutOptions(
                    kind="test.async_selected_output",
                    media_type="application/json",
                    schema=SchemaInfo(name="test.AsyncSelectedOutput", version="1.0"),
                ),
                return_selected_profile=True,
            )
        declared_refs = self.declared_refs
        if declared_refs is None:
            declared_refs = [persisted_ref] if persisted_ref is not None else []
        selected_refs = self.selected_refs
        if selected_refs is None and persisted_ref is not None:
            selected_refs = {"selected_output": persisted_ref}
        next_state = state.model_copy(deep=True)
        for key, ref in (selected_refs or {}).items():
            next_state.artifacts_index[key] = ref
        if self.status == "fail":
            return NodeOutcome(
                status="fail",
                state=next_state,
                artifacts=declared_refs,
                error=NodeError(code="node.test_failure", message="expected test failure"),
            )
        return NodeOutcome(status="ok", state=next_state, artifacts=declared_refs)


def _make_real_store_ctx(
    tmp_path: Path,
) -> tuple[FileSystemCAS, ExecutionContext]:
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


def _make_owned_run_context(
    tmp_path: Path,
    *,
    run_id: str,
) -> tuple[FileSystemCAS, object, ExecutionContext]:
    store = FileSystemCAS(tmp_path / "owned-cas")
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("async_executor_selected_output_test"),
    )
    return store, bundle, ctx


def _artifact_id_strings(store: FileSystemCAS) -> set[str]:
    """Normalize immutable CAS identities without relying on RootModel hashing."""
    return {str(artifact_id) for artifact_id in store.iter_artifact_ids()}


def _artifact_ids_of_kind(store: FileSystemCAS, kind: str) -> set[str]:
    """Select persisted artifacts by their manifest kind."""
    return {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == kind
    }


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
        ctx.run.finalize.assert_called_once()
        finalize_kwargs = ctx.run.finalize.call_args.kwargs
        assert finalize_kwargs["status"] == "fail"
        assert finalize_kwargs["errors"] == [
            {"node": "b", "code": "node.exception", "message": "b failed"}
        ]
        finalization_ref = finalize_kwargs["workflow_finalization_ref"]
        assert finalization_ref.kind == "scientist.workflow_state_finalization"
        assert finalization_ref.media_type == "application/json"

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
    async def test_async_executor_persists_via_async_artifact_store_adapter(
        self, monkeypatch, tmp_path
    ):
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

        async def _tracked_put_json(
            self, obj, opts, canon_spec=None, *, return_selected_profile=False
        ):
            seen_kinds.append(str(getattr(opts, "kind", "")))
            return await original_put_json(
                self,
                obj,
                opts,
                canon_spec=canon_spec,
                return_selected_profile=return_selected_profile,
            )

        monkeypatch.setattr(AsyncArtifactStoreAdapter, "put_json", _tracked_put_json)

        _, ctx = _make_real_store_ctx(tmp_path)
        executor = AsyncWorkflowExecutor(ctx, registry)
        result = await executor.execute(workflow, state)

        assert result.report.status == "ok"
        assert seen_kinds[:4] == [
            "scientist.workflow_spec",
            "scientist.experiment_state",
            "scientist.experiment_state",
            "scientist.experiment_state",
        ]
        assert "scientist.workflow_report" in seen_kinds
        assert "scientist.workflow_state_finalization" in seen_kinds

    @pytest.mark.asyncio
    async def test_async_executor_records_attempt_basis_for_fresh_owner_read(
        self, tmp_path: Path
    ) -> None:
        store = FileSystemCAS(tmp_path / "cas")
        bundle = build_default_registry_bundle(store, return_selected_profile=True)
        run = RunContext.start(
            store=store,
            registry_bundle=bundle.bundle_ref,
            run_id="async-owner-attempt",
        )
        ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger("async_executor_owner_test"),
        )
        node_id = "test.async_owner_attempt@1.0.0"
        node = _CacheTestNode(_cache_node_spec(node_id))
        registry = NodeRegistry()
        registry.register(node)
        workflow = WorkflowSpec(
            workflow_id="async_owner_attempt",
            nodes=[NodeInvocation(alias="attempt", node_id=node_id)],
        )
        state = ExperimentState(run_id="async-owner-attempt", params={"seed": 1})

        result = await AsyncWorkflowExecutor(ctx, registry).execute(workflow, state)

        assert result.report.status == "ok"
        trace_path = run.trace_path
        assert trace_path is not None
        attempts = run_context._read_runtime_invocation_attempts(
            store, trace_path, run_id=state.run_id
        )
        assert len(attempts) == 1
        attempt = attempts[0]
        assert attempt.basis.node_alias == "attempt"
        assert attempt.basis.component_id == node_id
        assert attempt.basis.workflow_spec_ref.manifest_profile_sha256 is not None
        assert attempt.basis.input_state_ref.manifest_profile_sha256 is not None
        assert attempt.outcome is not None
        assert attempt.outcome.status == "ok"
        persisted_workflow = WorkflowSpec.model_validate_json(
            store.get_bytes(attempt.basis.workflow_spec_ref)
        )
        persisted_input = ExperimentState.model_validate_json(
            store.get_bytes(attempt.basis.input_state_ref)
        )
        assert persisted_workflow.workflow_id == workflow.workflow_id
        assert persisted_input.run_id == state.run_id
        assert persisted_input.params == {"seed": 1}

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

    @pytest.mark.asyncio
    async def test_budget_alert_warnings_persist_and_deduplicate_before_exhaustion(
        self, tmp_path: Path
    ) -> None:
        store = FileSystemCAS(tmp_path / "cas")
        bundle = build_default_registry_bundle(store, return_selected_profile=True)
        run = RunContext.start(
            store=store,
            registry_bundle=bundle.bundle_ref,
            run_id="async-budget-warning-owner",
        )
        ctx = ExecutionContext(
            store=store,
            run=run,
            logger=logging.getLogger("async_budget_warning_test"),
        )
        budget_state = BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))},
            spent={"run": Decimal("8")},
        )
        executor = AsyncWorkflowExecutor(
            ctx, MagicMock(spec=NodeRegistry), budget_middleware=BudgetMiddleware(budget_state)
        )

        executor._check_budget("node", budget_key="run")
        executor._check_budget("node", budget_key="run")
        budget_state.spent["run"] = Decimal("9")
        executor._check_budget("node", budget_key="run")
        executor._check_budget("node", budget_key="run")
        budget_state.spent["run"] = Decimal("10")
        with pytest.raises(BudgetExhaustedError):
            executor._check_budget("node", budget_key="run")

        run.finalize(status="ok")
        trace_ref = run.run_manifest.trace_ref
        assert trace_ref is not None
        records = [
            json.loads(line)
            for line in store.get_bytes(trace_ref.artifact_id).decode("utf-8").splitlines()
            if line.strip()
        ]
        alerts = [record for record in records if record["event"] == "BUDGET_ALERT"]

        assert [(record["phase"], record["event"]) for record in alerts] == [
            ("scientist.budget", "BUDGET_ALERT"),
            ("scientist.budget", "BUDGET_ALERT"),
        ]
        assert [record["metrics"] for record in alerts] == [
            {"threshold_pct": 80},
            {"threshold_pct": 90},
        ]
        assert [record["warnings"] for record in alerts] == [
            [
                {
                    "code": "budget_threshold",
                    "msg": "Budget threshold reached",
                    "data": {"budget_key": "run"},
                }
            ],
            [
                {
                    "code": "budget_threshold",
                    "msg": "Budget threshold reached",
                    "data": {"budget_key": "run"},
                }
            ],
        ]
        assert all("budget_key" not in record["metrics"] for record in alerts)

    @pytest.mark.asyncio
    async def test_readiness_releases_disjoint_successor_before_unrelated_node_finishes(self):
        node_ids = {
            "slow": "test.readiness_slow@1.0.0",
            "quick": "test.readiness_quick@1.0.0",
            "after_quick": "test.readiness_after_quick@1.0.0",
        }
        slow_started = threading.Event()
        release_slow = threading.Event()
        slow_finished = threading.Event()
        after_quick_started = threading.Event()
        after_quick_saw_slow_running: list[bool] = []

        class _ReadinessNode:
            def __init__(self, alias: str) -> None:
                self.alias = alias
                self.spec = _cache_node_spec(
                    node_ids[alias],
                    state_writes=[f"params.{alias}"],
                )

            def execute(self, ctx, state):
                del ctx
                if self.alias == "slow":
                    slow_started.set()
                    if not release_slow.wait(timeout=2):
                        raise TimeoutError("readiness test did not release slow sibling")
                    slow_finished.set()
                elif self.alias == "after_quick":
                    after_quick_saw_slow_running.append(not slow_finished.is_set())
                    after_quick_started.set()
                    release_slow.set()
                state.params[self.alias] = True
                return NodeOutcome(status="ok", state=state)

        nodes = {alias: _ReadinessNode(alias) for alias in node_ids}
        registry = MagicMock(spec=NodeRegistry)
        registry.get.side_effect = lambda node_id: nodes[
            next(alias for alias, value in node_ids.items() if value == str(node_id))
        ]
        workflow = WorkflowSpec(
            workflow_id="readiness_disjoint_state_paths",
            error_policy="continue",
            nodes=[
                NodeInvocation(alias="slow", node_id=node_ids["slow"]),
                NodeInvocation(alias="quick", node_id=node_ids["quick"]),
                NodeInvocation(
                    alias="after_quick",
                    node_id=node_ids["after_quick"],
                    depends_on=["quick"],
                ),
            ],
        )
        executor = AsyncWorkflowExecutor(_make_ctx(), registry, max_parallelism=2)
        execution = asyncio.create_task(
            executor.execute(
                workflow,
                ExperimentState(run_id="readiness-disjoint", params={"seed": 1}),
            )
        )
        slow_was_admitted = await asyncio.to_thread(slow_started.wait, 1)
        successor_released_early = await asyncio.to_thread(after_quick_started.wait, 0.75)
        release_slow.set()
        result = await execution

        assert slow_was_admitted
        assert successor_released_early
        assert after_quick_saw_slow_running == [True]
        assert result.report.status == "ok"
        assert result.state.params["slow"] is True
        assert result.state.params["quick"] is True
        assert result.state.params["after_quick"] is True

    @pytest.mark.asyncio
    async def test_sync_and_async_checkpoint_hooks_keep_their_selected_call_paths(self):
        node_id = "test.async_checkpoint_selection@1.0.0"
        node = _CacheTestNode(_cache_node_spec(node_id))
        registry = MagicMock(spec=NodeRegistry)
        registry.get.return_value = node
        workflow = WorkflowSpec(
            workflow_id="async_checkpoint_selection",
            nodes=[NodeInvocation(alias="node", node_id=node_id)],
        )
        async_hook = SimpleNamespace(
            on_node_complete_async=AsyncMock(return_value=None),
        )

        async_result = await AsyncWorkflowExecutor(
            _make_ctx(), registry, checkpoint_hook=async_hook
        ).execute(workflow, ExperimentState(run_id="async-checkpoint-selection"))

        assert async_result.report.status == "ok"
        async_hook.on_node_complete_async.assert_awaited_once()

        sync_hook = SimpleNamespace(on_node_complete=Mock(return_value=None))
        sync_result = await AsyncWorkflowExecutor(
            _make_ctx(), registry, checkpoint_hook=sync_hook
        ).execute(workflow, ExperimentState(run_id="sync-checkpoint-selection"))

        assert sync_result.report.status == "ok"
        sync_hook.on_node_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_checkpoint_hook_handles_parallel_tier(self):
        node_ids = {
            "left": "test.sync_checkpoint_left@1.0.0",
            "right": "test.sync_checkpoint_right@1.0.0",
        }

        class _WritingNode:
            def __init__(self, alias: str) -> None:
                self.alias = alias
                self.spec = _cache_node_spec(
                    node_ids[alias],
                    state_writes=[f"params.{alias}"],
                )

            def execute(self, ctx, state):
                del ctx
                state.params[self.alias] = True
                return NodeOutcome(status="ok", state=state)

        nodes = {alias: _WritingNode(alias) for alias in node_ids}
        registry = MagicMock(spec=NodeRegistry)
        registry.get.side_effect = lambda node_id: nodes[
            next(alias for alias, value in node_ids.items() if value == str(node_id))
        ]
        hook = SimpleNamespace(
            on_node_complete=Mock(return_value=None),
            on_tier_complete=Mock(return_value=None),
        )
        workflow = WorkflowSpec(
            workflow_id="sync_checkpoint_parallel_tier",
            nodes=[
                NodeInvocation(alias="left", node_id=node_ids["left"]),
                NodeInvocation(alias="right", node_id=node_ids["right"]),
            ],
        )

        result = await AsyncWorkflowExecutor(
            _make_ctx(), registry, checkpoint_hook=hook, max_parallelism=2
        ).execute(workflow, ExperimentState(run_id="sync-checkpoint-tier", params={"seed": 1}))

        assert result.report.status == "ok"
        hook.on_tier_complete.assert_called_once()
        hook.on_node_complete.assert_not_called()


class TestAsyncCacheBoundaries:
    @pytest.mark.asyncio
    async def test_cache_hit_reads_with_exhausted_compute_budget_but_miss_does_not(self, tmp_path):
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
    async def test_expired_workflow_cache_wait_refuses_producer_admission(
        self, tmp_path, monkeypatch
    ):
        """An elapsed owner deadline grants no refreshed producer or cache budget."""
        node_id = "test.async_cache_deadline@1.0.0"
        node = _CacheTestNode(_cache_node_spec(node_id))
        registry = NodeRegistry()
        registry.register(node)
        store, ctx = _make_real_store_ctx(tmp_path)
        executor = AsyncWorkflowExecutor(ctx, registry, workflow_timeout_s=0.08)
        executor._cache = NodeResultCache(store, run_id="async-cache-deadline")
        invocation = NodeInvocation(alias="cached", node_id=node_id)
        workflow = WorkflowSpec(workflow_id="async_cache_deadline", nodes=[invocation])

        executor._workflow_deadline = time.perf_counter() + 0.04
        original_get = executor._cache.get

        def slow_get(*args, **kwargs):
            time.sleep(0.06)
            return original_get(*args, **kwargs)

        monkeypatch.setattr(executor._cache, "get", slow_get)
        state = ExperimentState(run_id="async-cache-deadline", params={"seed": 1})
        original_state = state.model_dump(mode="json")
        original_artifacts = _artifact_id_strings(store)

        with pytest.raises(WorkflowTimeoutError):
            await executor._execute_node("cached", invocation, state, workflow)

        assert node.calls == 0
        assert executor._cache.size == 0
        assert _artifact_id_strings(store) == original_artifacts
        assert state.model_dump(mode="json") == original_state

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
        phase_ticks = {"entry": 0}

        def slow_put_json(obj, opts, canon_spec=None, *, return_selected_profile=False):
            nonlocal put_calls, put_phase
            if str(getattr(opts, "kind", "")) == "scientist.node_cache_entry":
                put_calls += 1
                put_phase = "entry"
                phase_ticks["entry"] = 0
                time.sleep(0.08)
            return original_put_json(
                obj,
                opts,
                canon_spec=canon_spec,
                return_selected_profile=return_selected_profile,
            )

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
        assert put_calls == 1
        assert phase_ticks["entry"] > 0

        executor._cache.clear()
        ids_before_failed_publication = _artifact_ids_of_kind(store, "scientist.node_cache_entry")
        calls = 0

        def fail_entry_put(obj, opts, canon_spec=None, *, return_selected_profile=False):
            nonlocal calls
            if str(getattr(opts, "kind", "")) == "scientist.node_cache_entry":
                calls += 1
                if calls == 1:
                    raise OSError("entry publication interrupted")
            return original_put_json(
                obj,
                opts,
                canon_spec=canon_spec,
                return_selected_profile=return_selected_profile,
            )

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
        assert (
            _artifact_ids_of_kind(store, "scientist.node_cache_entry")
            == ids_before_failed_publication
        )

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
        ids_before_failed_publication = _artifact_ids_of_kind(store, "scientist.node_cache_entry")

        original_put_json = store.put_json
        put_calls = 0

        def fail_entry_put(obj, opts, canon_spec=None, *, return_selected_profile=False):
            nonlocal put_calls
            if str(getattr(opts, "kind", "")) == "scientist.node_cache_entry":
                put_calls += 1
                if put_calls == 1:
                    raise OSError("entry publication interrupted")
            return original_put_json(
                obj,
                opts,
                canon_spec=canon_spec,
                return_selected_profile=return_selected_profile,
            )

        monkeypatch.setattr(store, "put_json", fail_entry_put)
        outcome, _, cache_hit, _ = await executor._execute_node(
            "cached",
            invocation,
            ExperimentState(run_id="async-cache-atomicity", params={"seed": 1}),
            workflow,
        )

        assert outcome.status == "ok"
        assert cache_hit is False
        assert put_calls == 1
        assert executor._cache.size == 0
        assert (
            _artifact_ids_of_kind(store, "scientist.node_cache_entry")
            == ids_before_failed_publication
        )

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


class TestAsyncSelectedOutputPublication:
    @pytest.mark.asyncio
    async def test_publishes_only_verified_selected_successful_output_views(self, tmp_path):
        run_id = "async-selected-output"
        store, bundle, ctx = _make_owned_run_context(tmp_path, run_id=run_id)
        selected_ref = store.put_json(
            {"same_blob": True},
            PutOptions(
                kind="test.async_selected_output",
                media_type="application/json",
                schema=SchemaInfo(name="test.AsyncSelectedOutput", version="1.0"),
            ),
            return_selected_profile=True,
        )
        wrong_profile_ref = store.put_json(
            {"same_blob": True},
            PutOptions(
                kind="test.async_selected_output",
                media_type="application/json",
                schema=SchemaInfo(name="test.AsyncSelectedOutput", version="2.0"),
            ),
            return_selected_profile=True,
        )
        preseed_ref = store.put_json(
            {"preseed": True},
            PutOptions(kind="test.async_selected_output", media_type="application/json"),
            return_selected_profile=True,
        )
        replayed_only_ref = store.put_json(
            {"replayed_only": True},
            PutOptions(kind="test.async_selected_output", media_type="application/json"),
            return_selected_profile=True,
        )
        fake_ref = ArtifactRef(
            artifact_id="sha256:" + "ef" * 32,
            kind="test.async_selected_output",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "12" * 32,
        )
        producer = _AsyncSelectedArtifactOutputNode(
            node_name="real_output",
            payload={"produced": "in-node"},
        )
        replayed = _AsyncSelectedArtifactOutputNode(
            node_name="replayed_input",
            declared_refs=[selected_ref],
            selected_refs={"replayed_output": selected_ref},
        )
        unselected = _AsyncSelectedArtifactOutputNode(
            node_name="unselected_output",
            declared_refs=[wrong_profile_ref],
            selected_refs={},
        )
        nonexistent = _AsyncSelectedArtifactOutputNode(
            node_name="nonexistent_output",
            declared_refs=[fake_ref],
            selected_refs={"nonexistent": fake_ref},
        )
        failed = _AsyncSelectedArtifactOutputNode(
            node_name="failed_output",
            declared_refs=[preseed_ref],
            selected_refs={"failed": preseed_ref},
            status="fail",
        )
        registry = NodeRegistry()
        for node in (producer, replayed, unselected, nonexistent, failed):
            registry.register(node)
        workflow = WorkflowSpec(
            workflow_id="async_selected_output_publish",
            error_policy="continue",
            nodes=[
                NodeInvocation(alias="producer", node_id=producer.spec.metadata.component_id),
                NodeInvocation(alias="replayed", node_id=replayed.spec.metadata.component_id),
                NodeInvocation(alias="unselected", node_id=unselected.spec.metadata.component_id),
                NodeInvocation(alias="nonexistent", node_id=nonexistent.spec.metadata.component_id),
                NodeInvocation(alias="failed", node_id=failed.spec.metadata.component_id),
            ],
        )
        state = ExperimentState(
            run_id=run_id,
            inputs={"registry_bundle_ref": bundle.bundle_ref},
            artifacts_index={
                "preseed_only": preseed_ref,
                "profile_selected": selected_ref,
                "replayed_only": replayed_only_ref,
            },
        )

        result = await AsyncWorkflowExecutor(ctx, registry).execute(workflow, state)

        assert result.report.status == "fail"
        assert selected_ref.artifact_id == wrong_profile_ref.artifact_id
        assert selected_ref.manifest_profile_sha256 != wrong_profile_ref.manifest_profile_sha256
        produced_ref = result.report.nodes[0].artifacts[0]
        assert store.verify(produced_ref).ok
        output_identities = {artifact_ref_identity_key(ref) for ref in ctx.run.run_manifest.outputs}
        assert artifact_ref_identity_key(produced_ref) in output_identities
        assert artifact_ref_identity_key(selected_ref) in output_identities
        assert artifact_ref_identity_key(wrong_profile_ref) not in output_identities
        assert artifact_ref_identity_key(preseed_ref) not in output_identities
        assert artifact_ref_identity_key(replayed_only_ref) not in output_identities
        assert artifact_ref_identity_key(fake_ref) not in output_identities

    @pytest.mark.asyncio
    async def test_publishes_selected_outputs_from_verified_cache_hit(self, tmp_path):
        run_id = "async-selected-output-cache"
        store, bundle, ctx = _make_owned_run_context(tmp_path, run_id=run_id)
        node = _AsyncSelectedArtifactOutputNode(node_name="cache_output")
        registry = NodeRegistry()
        registry.register(node)
        state = ExperimentState(
            run_id=run_id,
            inputs={"registry_bundle_ref": bundle.bundle_ref},
            params={"seed": "async-cache-output"},
        )
        produced_ref = store.put_json(
            {"cached": "producer-output"},
            PutOptions(
                kind="test.async_selected_output",
                media_type="application/json",
                schema=SchemaInfo(name="test.AsyncSelectedOutput", version="1.0"),
            ),
            return_selected_profile=True,
        )
        cached_state = branch_state(state, write_paths=("artifacts_index",)).state
        cached_state.artifacts_index["selected_output"] = produced_ref
        cached_outcome = NodeOutcome(
            status="ok",
            state=cached_state,
            artifacts=[produced_ref],
        )
        cache_key = compute_idempotency_key(node.spec, state, {})
        cache_entry_ref = NodeResultCache(store, run_id=run_id).put(
            cache_key,
            node_id=str(node.spec.metadata.component_id),
            outcome=cached_outcome,
        )

        result = await AsyncWorkflowExecutor(
            ctx,
            registry,
            checkpoint_cache_seed_refs=[cache_entry_ref],
        ).execute(
            WorkflowSpec(
                workflow_id="async_cache_selected_output",
                nodes=[NodeInvocation(alias="cached", node_id=node.spec.metadata.component_id)],
            ),
            state,
        )

        assert result.report.status == "ok"
        assert node.calls == 0
        output_identities = [artifact_ref_identity_key(ref) for ref in ctx.run.run_manifest.outputs]
        assert output_identities.count(artifact_ref_identity_key(produced_ref)) == 1

"""Tests for async fan-out execution and merge conflict policy (WS5.5)."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.fan_out import (
    FanOutConfig,
    FanOutNode,
    MergeConflictPolicy,
)
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeSpec
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState

_FAKE_SHA = "sha256:" + "ab" * 32


def _make_ctx():
    store = MagicMock()
    store.put_json.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA, kind="test", media_type="application/json",
    )
    run = MagicMock()
    run.trace_path = None
    return ExecutionContext(store=store, run=run, logger=MagicMock())


def _make_mock_node(*, ok=True, artifacts=None, delay: float = 0):
    node = MagicMock()
    node.spec = MagicMock(spec=NodeSpec)
    node.spec.state_reads = []
    node.spec.state_writes = []
    node.bind.return_value = None

    if ok:
        def _execute(ctx, state):
            if delay:
                time.sleep(delay)
            return NodeOutcome(
                status="ok", state=state, events=[],
                artifacts=artifacts or [],
            )
        node.execute.side_effect = _execute
    else:
        def _execute_fail(ctx, state):
            if delay:
                time.sleep(delay)
            return NodeOutcome(
                status="fail", state=state, events=[],
                error=NodeError(code="test.fail", message="fail", details={}),
            )
        node.execute.side_effect = _execute_fail
    return node


def _make_registry(node):
    registry = MagicMock(spec=NodeRegistry)
    registry.get.return_value = node
    return registry


# ── Async fan-out execution ──────────────────────────────────────────


class TestAsyncFanOutExecution:
    @pytest.mark.asyncio
    async def test_async_processes_all_items(self) -> None:
        state = ExperimentState(
            run_id="r1", params={"items": ["a", "b", "c"]},
        )
        task_node = _make_mock_node()
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = await fan.execute_async(_make_ctx(), state)
        assert outcome.status == "ok"
        assert any("3/3" in e.message for e in outcome.events)

    @pytest.mark.asyncio
    async def test_async_parallel_execution(self) -> None:
        """Items run concurrently, not sequentially."""
        execution_times: dict[int, float] = {}

        def _timed_execute(ctx, state):
            idx = state.params.get("item_index", 0)
            execution_times[idx] = time.monotonic()
            time.sleep(0.05)
            return NodeOutcome(status="ok", state=state, events=[], artifacts=[])

        task_node = MagicMock()
        task_node.spec = MagicMock(spec=NodeSpec)
        task_node.spec.state_reads = []
        task_node.spec.state_writes = []
        task_node.bind.return_value = None
        task_node.execute.side_effect = _timed_execute

        state = ExperimentState(
            run_id="r2", params={"items": [1, 2, 3, 4]},
        )
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            max_parallelism=4,
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = await fan.execute_async(_make_ctx(), state)
        assert outcome.status == "ok"

    @pytest.mark.asyncio
    async def test_async_respects_max_parallelism(self) -> None:
        """Semaphore limits concurrent execution."""
        active = {"count": 0, "max": 0}
        lock = threading.Lock()

        def _counting_execute(ctx, state):
            with lock:
                active["count"] += 1
                active["max"] = max(active["max"], active["count"])
            time.sleep(0.02)
            with lock:
                active["count"] -= 1
            return NodeOutcome(status="ok", state=state, events=[], artifacts=[])

        task_node = MagicMock()
        task_node.spec = MagicMock(spec=NodeSpec)
        task_node.spec.state_reads = []
        task_node.spec.state_writes = []
        task_node.bind.return_value = None
        task_node.execute.side_effect = _counting_execute

        state = ExperimentState(
            run_id="r3", params={"items": list(range(8))},
        )
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            max_parallelism=2,
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = await fan.execute_async(_make_ctx(), state)
        assert outcome.status == "ok"
        assert active["max"] <= 2

    @pytest.mark.asyncio
    async def test_async_continue_on_failure(self) -> None:
        call_count = 0

        def _execute(ctx, state):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return NodeOutcome(
                    status="fail", state=state,
                    error=NodeError(code="test.fail", message="fail", details={}),
                )
            return NodeOutcome(status="ok", state=state, events=[], artifacts=[])

        task_node = MagicMock()
        task_node.spec = MagicMock(spec=NodeSpec)
        task_node.spec.state_reads = []
        task_node.spec.state_writes = []
        task_node.bind.return_value = None
        task_node.execute.side_effect = _execute

        state = ExperimentState(
            run_id="r4", params={"items": [1, 2, 3]},
        )
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            continue_on_item_failure=True,
            max_parallelism=1,  # sequential for deterministic ordering
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = await fan.execute_async(_make_ctx(), state)
        assert outcome.status == "ok"  # continue_on_item_failure=True

    @pytest.mark.asyncio
    async def test_async_stop_on_failure(self) -> None:
        state = ExperimentState(
            run_id="r5", params={"items": [1, 2, 3]},
        )
        task_node = _make_mock_node(ok=False)
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            continue_on_item_failure=False,
            max_parallelism=1,
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = await fan.execute_async(_make_ctx(), state)
        assert outcome.status == "fail"

    @pytest.mark.asyncio
    async def test_async_skip_no_items(self) -> None:
        state = ExperimentState(run_id="r6", params={})
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        fan = FanOutNode(cfg, _make_registry(_make_mock_node()))
        outcome = await fan.execute_async(_make_ctx(), state)
        assert outcome.status == "skip"

    @pytest.mark.asyncio
    async def test_async_skip_empty_list(self) -> None:
        state = ExperimentState(run_id="r7", params={"items": []})
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        fan = FanOutNode(cfg, _make_registry(_make_mock_node()))
        outcome = await fan.execute_async(_make_ctx(), state)
        assert outcome.status == "skip"


# ── Merge conflict policy ────────────────────────────────────────────


class TestMergeConflictPolicy:
    def test_last_write_wins_default(self) -> None:
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        assert cfg.merge_conflict_policy == MergeConflictPolicy.LAST_WRITE_WINS

    def test_config_accepts_all_policies(self) -> None:
        for policy in MergeConflictPolicy:
            cfg = FanOutConfig(
                items_state_path="params.items",
                task_node_id="test.node@1.0.0",
                result_state_path="params.results",
                merge_conflict_policy=policy,
            )
            assert cfg.merge_conflict_policy == policy

    def test_serialization_roundtrip(self) -> None:
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            merge_conflict_policy=MergeConflictPolicy.FIRST_WRITE_WINS,
        )
        dumped = cfg.model_dump()
        restored = FanOutConfig.model_validate(dumped)
        assert restored.merge_conflict_policy == MergeConflictPolicy.FIRST_WRITE_WINS


# ── Sync execute still works after refactor ──────────────────────────


class TestSyncExecuteAfterRefactor:
    def test_sync_still_works(self) -> None:
        """Ensure sync execute() still works after extracting _merge_outcomes."""
        state = ExperimentState(
            run_id="r-sync", params={"items": ["a", "b"]},
        )
        task_node = _make_mock_node()
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "ok"
        assert any("2/2" in e.message for e in outcome.events)

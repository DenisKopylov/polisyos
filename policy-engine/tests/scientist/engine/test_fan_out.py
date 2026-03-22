"""Tests for the fan-out / fan-in (map-reduce) node."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.fan_out import FanOutConfig, FanOutNode, FanOutResult
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


def _make_mock_node(*, ok=True, artifacts=None):
    node = MagicMock()
    node.spec = MagicMock(spec=NodeSpec)
    node.spec.state_reads = []
    node.spec.state_writes = []
    # bind returns None so the original node is used (not a mock wrapper)
    node.bind.return_value = None
    if ok:
        def _execute(ctx, state):
            return NodeOutcome(
                status="ok", state=state, events=[],
                artifacts=artifacts or [],
            )
        node.execute.side_effect = _execute
    else:
        def _execute_fail(ctx, state):
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


# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------

class TestFanOutConfigModel:
    def test_defaults(self) -> None:
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        assert cfg.item_param_key == "item"
        assert cfg.merge_strategy == "list_collect"
        assert cfg.max_parallelism == 4
        assert cfg.continue_on_item_failure is True

    def test_extra_forbidden(self) -> None:
        with pytest.raises(Exception):
            FanOutConfig(
                items_state_path="x", task_node_id="x@1.0.0",
                result_state_path="y", bad="field",
            )

    def test_roundtrip(self) -> None:
        cfg = FanOutConfig(
            items_state_path="params.countries",
            task_node_id="test.node@1.0.0",
            result_state_path="params.country_results",
            max_parallelism=8,
        )
        dumped = cfg.model_dump()
        restored = FanOutConfig.model_validate(dumped)
        assert restored.max_parallelism == 8


class TestFanOutResultModel:
    def test_defaults(self) -> None:
        r = FanOutResult(items_count=5, completed=4, failed=1)
        assert r.failed_items == []


# ---------------------------------------------------------------------------
# FanOutNode spec
# ---------------------------------------------------------------------------

class TestFanOutNodeSpec:
    def test_spec_reads_items_path(self) -> None:
        cfg = FanOutConfig(
            items_state_path="params.countries",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        node = FanOutNode(cfg, _make_registry(_make_mock_node()))
        assert "params.countries" in node.spec.state_reads

    def test_spec_writes_result_path(self) -> None:
        cfg = FanOutConfig(
            items_state_path="params.countries",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        node = FanOutNode(cfg, _make_registry(_make_mock_node()))
        assert "params.results" in node.spec.state_writes


# ---------------------------------------------------------------------------
# Execution: basic
# ---------------------------------------------------------------------------

class TestFanOutExecution:
    def test_processes_all_items(self) -> None:
        state = ExperimentState(
            run_id="r1",
            params={"items": ["a", "b", "c"]},
        )
        task_node = _make_mock_node()
        registry = _make_registry(task_node)
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        fan = FanOutNode(cfg, registry)
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "ok"
        # registry.get() returns task_node, so calls go through it
        resolved_node = registry.get.return_value
        assert resolved_node.execute.call_count == 3
        # Check event summary
        assert any("3/3" in e.message for e in outcome.events)

    def test_skip_on_none_items(self) -> None:
        state = ExperimentState(run_id="r2", params={})
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        fan = FanOutNode(cfg, _make_registry(_make_mock_node()))
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "skip"

    def test_skip_on_empty_list(self) -> None:
        state = ExperimentState(run_id="r3", params={"items": []})
        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
        )
        fan = FanOutNode(cfg, _make_registry(_make_mock_node()))
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "skip"

    def test_single_item(self) -> None:
        state = ExperimentState(
            run_id="r4",
            params={"items": ["only_one"]},
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
        assert task_node.execute.call_count == 1

    def test_item_injected_into_params(self) -> None:
        """Task node receives the item value in bind params."""
        state = ExperimentState(
            run_id="r5",
            params={"items": ["UA", "PL"]},
        )
        task_node = _make_mock_node()
        # Track what bind receives
        bind_calls = []
        def _bind(params):
            bind_calls.append(params)
            return task_node
        task_node.bind = _bind

        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            item_param_key="country",
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "ok"
        assert bind_calls[0]["country"] == "UA"
        assert bind_calls[1]["country"] == "PL"
        assert bind_calls[0]["item_index"] == 0
        assert bind_calls[1]["item_index"] == 1


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------

class TestFanOutFailures:
    def test_continue_on_failure(self) -> None:
        """With continue_on_item_failure=True, overall status is ok."""
        state = ExperimentState(
            run_id="r6",
            params={"items": [1, 2, 3]},
        )
        call_count = 0
        def _execute(ctx, s):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return NodeOutcome(
                    status="fail", state=s,
                    error=NodeError(code="test.fail", message="fail", details={}),
                )
            return NodeOutcome(status="ok", state=s, events=[], artifacts=[])

        task_node = _make_mock_node()
        task_node.execute.side_effect = _execute

        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            continue_on_item_failure=True,
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "ok"
        assert task_node.execute.call_count == 3  # all items processed

    def test_stop_on_failure(self) -> None:
        """With continue_on_item_failure=False, stop at first failure."""
        state = ExperimentState(
            run_id="r7",
            params={"items": [1, 2, 3]},
        )
        call_count = 0
        def _execute(ctx, s):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return NodeOutcome(
                    status="fail", state=s,
                    error=NodeError(code="test.fail", message="fail", details={}),
                )
            return NodeOutcome(status="ok", state=s, events=[], artifacts=[])

        task_node = _make_mock_node()
        task_node.execute.side_effect = _execute

        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            continue_on_item_failure=False,
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "fail"
        assert outcome.error is not None
        assert task_node.execute.call_count == 2  # stopped at item 2

    def test_exception_in_task_treated_as_failure(self) -> None:
        state = ExperimentState(
            run_id="r8",
            params={"items": ["a"]},
        )
        task_node = _make_mock_node()
        task_node.execute.side_effect = RuntimeError("boom")

        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            continue_on_item_failure=True,
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "ok"  # continue_on_item_failure=True


# ---------------------------------------------------------------------------
# Merge strategies
# ---------------------------------------------------------------------------

class TestMergeStrategies:
    def test_list_collect(self) -> None:
        state = ExperimentState(
            run_id="r9",
            params={"items": ["a", "b"]},
        )
        art = ArtifactRef(artifact_id=_FAKE_SHA, kind="test", media_type="application/json")
        task_node = _make_mock_node(artifacts=[art])

        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            merge_strategy="list_collect",
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "ok"
        assert "results" in outcome.state.params

    def test_dict_merge(self) -> None:
        state = ExperimentState(
            run_id="r10",
            params={"items": ["x", "y"]},
        )
        art = ArtifactRef(artifact_id=_FAKE_SHA, kind="test", media_type="application/json")
        task_node = _make_mock_node(artifacts=[art])

        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            merge_strategy="dict_merge",
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "ok"
        results = outcome.state.params.get("results")
        assert isinstance(results, dict)
        assert "0" in results and "1" in results

    def test_artifact_index_merge(self) -> None:
        state = ExperimentState(
            run_id="r11",
            params={"items": ["a", "b"]},
        )
        art = ArtifactRef(artifact_id=_FAKE_SHA, kind="test", media_type="application/json")
        task_node = _make_mock_node(artifacts=[art])

        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            merge_strategy="artifact_index",
        )
        fan = FanOutNode(cfg, _make_registry(task_node), alias="test_fan")
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "ok"
        assert "fan_out_test_fan_0" in outcome.state.artifacts_index
        assert "fan_out_test_fan_1" in outcome.state.artifacts_index


# ---------------------------------------------------------------------------
# Template params
# ---------------------------------------------------------------------------

class TestTemplateParams:
    def test_template_merged_with_item(self) -> None:
        state = ExperimentState(
            run_id="r12",
            params={"items": ["UA"]},
        )
        task_node = _make_mock_node()
        bind_calls = []
        def _bind(params):
            bind_calls.append(params)
            return task_node
        task_node.bind = _bind

        cfg = FanOutConfig(
            items_state_path="params.items",
            task_node_id="test.node@1.0.0",
            result_state_path="params.results",
            task_params_template={"year": 2025, "source": "wvs"},
        )
        fan = FanOutNode(cfg, _make_registry(task_node))
        outcome = fan.execute(_make_ctx(), state)
        assert outcome.status == "ok"
        assert bind_calls[0]["year"] == 2025
        assert bind_calls[0]["source"] == "wvs"
        assert bind_calls[0]["item"] == "UA"

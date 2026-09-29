"""Behavioral coverage for canonical WorkflowReport persistence."""

from __future__ import annotations

import logging
import time
from unittest.mock import MagicMock

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import (
    NodeRunRecord,
    WorkflowExecutionStatus,
    WorkflowExecutor,
    WorkflowReport,
    _WorkflowReportCanonicalizationError,
    _WorkflowReportStatusError,
)
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner.serialization import (
    deserialize_outcome,
    serialize_outcome,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_FAKE_SHA = "sha256:" + "ab" * 32
_NODE_ID = "test.canonical_report@1.0.0"
_TIMEOUT_SECONDS = 1.0


class _ReportNode:
    def __init__(self, *, timeout: bool) -> None:
        self.timeout = timeout
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(_NODE_ID),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Canonical report test node",
                description="Exercises a real workflow report write.",
                tags=["test"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=[],
            state_writes=[],
            produces=[],
        )

    def execute(self, ctx, state):
        del ctx
        if self.timeout:
            time.sleep(1.05)
            return NodeOutcome(status="ok", state=state)
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(
                code="node.expected_failure",
                message="Canonical detail control.",
                details={
                    "nested": {"attempt": 2, "enabled": True, "unset": None},
                    "reason": "control",
                },
            ),
        )


class _SlowCanonicalFailureNode(_ReportNode):
    def execute(self, ctx, state):
        del ctx
        time.sleep(0.1)
        return NodeOutcome(
            status="fail",
            state=state,
            error=NodeError(
                code="node.expected_failure",
                message="Canonical detail control.",
                details={"reason": "slow-control"},
            ),
        )


def _build_context(tmp_path) -> tuple[FileSystemCAS, ExecutionContext]:
    store = FileSystemCAS(tmp_path / "cas")
    run = MagicMock()
    run.trace_path = None
    run.finalize.return_value = ArtifactRef(
        artifact_id=_FAKE_SHA,
        kind="run",
        media_type="application/json",
    )
    return store, ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("workflow_report_canonical_persistence_test"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("executor_kind", "is_timeout"),
    [
        pytest.param("sync", True, id="sync-timeout"),
        pytest.param("async", True, id="async-timeout"),
        pytest.param("sync", False, id="sync-canonical-control"),
        pytest.param("async", False, id="async-canonical-control"),
    ],
)
async def test_workflow_executor_persists_and_reopens_canonical_report(
    tmp_path,
    executor_kind: str,
    is_timeout: bool,
) -> None:
    node = _ReportNode(timeout=is_timeout)
    registry = MagicMock(spec=NodeRegistry)
    registry.get.return_value = node
    store, ctx = _build_context(tmp_path)
    run_id = f"canonical-report-{executor_kind}-{is_timeout}"
    workflow = WorkflowSpec(
        workflow_id="canonical_report_test",
        nodes=[
            NodeInvocation(
                alias="reported",
                node_id=_NODE_ID,
                timeout_s=_TIMEOUT_SECONDS if is_timeout else None,
            )
        ],
    )
    initial_state = ExperimentState(run_id=run_id)

    if executor_kind == "sync":
        result = WorkflowExecutor(ctx, registry).execute(workflow, initial_state)
    else:
        result = await AsyncWorkflowExecutor(ctx, registry).execute(workflow, initial_state)

    assert result.report.status == "fail"
    assert result.report.nodes[0].error is not None
    if is_timeout:
        assert result.report.nodes[0].error.code == "node.timeout"
        encoded_timeout = result.report.nodes[0].error.details["timeout_seconds_binary64_hex"]
        reported_timeout = float.fromhex(encoded_timeout)
        assert 0 < reported_timeout <= _TIMEOUT_SECONDS
        if executor_kind == "sync":
            assert reported_timeout == _TIMEOUT_SECONDS
    else:
        assert result.report.nodes[0].error.details == {
            "nested": {"attempt": 2, "enabled": True, "unset": None},
            "reason": "control",
        }

    report_ref = result.state.reports_index["workflow_report"]
    assert report_ref.kind == "scientist.workflow_report"
    payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    replayed = WorkflowReport.model_validate(payload)
    assert replayed.status == "fail"
    assert replayed.nodes[0].error is not None
    assert replayed.nodes[0].error.code == result.report.nodes[0].error.code
    assert replayed.nodes[0].error.details == result.report.nodes[0].error.details


@pytest.mark.asyncio
async def test_async_semaphore_timeout_persists_exact_timeout_report(tmp_path) -> None:
    node = _SlowCanonicalFailureNode(timeout=False)
    registry = MagicMock(spec=NodeRegistry)
    registry.get.return_value = node
    store, ctx = _build_context(tmp_path)
    timeout_s = 0.02
    workflow = WorkflowSpec(
        workflow_id="canonical_report_semaphore_test",
        nodes=[
            NodeInvocation(alias="first_slow", node_id=_NODE_ID),
            NodeInvocation(alias="second_queued", node_id=_NODE_ID),
        ],
    )

    result = await AsyncWorkflowExecutor(
        ctx,
        registry,
        max_parallelism=1,
        semaphore_timeout_s=timeout_s,
    ).execute(workflow, ExperimentState(run_id="semaphore-report"))

    queued = next(record for record in result.report.nodes if record.alias == "second_queued")
    assert queued.error is not None
    assert queued.error.code == "node.semaphore_timeout"
    encoded_timeout = queued.error.details["timeout_seconds_binary64_hex"]
    assert float.fromhex(encoded_timeout) == timeout_s

    report_ref = result.state.reports_index["workflow_report"]
    payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    replayed = WorkflowReport.model_validate(payload)
    replayed_queued = next(record for record in replayed.nodes if record.alias == "second_queued")
    assert replayed_queued.error is not None
    assert replayed_queued.error.code == "node.semaphore_timeout"
    assert replayed_queued.error.details["timeout_seconds_binary64_hex"] == encoded_timeout


def test_historical_node_error_float_details_remain_replayable() -> None:
    historical = NodeOutcome(
        status="fail",
        state=ExperimentState(run_id="historical-float-timeout"),
        error=NodeError(
            code="node.timeout",
            message="Node timed out.",
            details={"timeout_s": _TIMEOUT_SECONDS},
        ),
    )
    replayed = deserialize_outcome(serialize_outcome(historical))

    assert replayed.error is not None
    assert replayed.error.code == "node.timeout"
    assert replayed.error.details["timeout_s"] == _TIMEOUT_SECONDS


def test_report_writer_rejects_float_details_with_timeout_markers_intact() -> None:
    error = NodeError(
        code="node.timeout",
        message="Node timed out.",
        details={"timeout_seconds_binary64_hex": _TIMEOUT_SECONDS.hex()},
    )
    report = WorkflowReport(
        workflow_id="canonical_report_test",
        run_id="mutated-error-details",
        error_policy="fail_fast",
        status="fail",
        nodes=[
            NodeRunRecord(
                alias="reported",
                node_id=_NODE_ID,
                status="fail",
                duration_ms=0,
                error=error,
            )
        ],
    )

    assert report._validated_payload()["nodes"][0]["error"]["code"] == "node.timeout"
    error.details["timeout_s"] = _TIMEOUT_SECONDS

    with pytest.raises(_WorkflowReportCanonicalizationError, match="not canonical") as raised:
        report._validated_payload()

    assert raised.value.node_alias == "reported"
    assert report.nodes[0].error is error


@pytest.mark.asyncio
@pytest.mark.parametrize("executor_kind", ["sync", "async"])
async def test_workflow_report_writer_rejects_unrecognized_status(
    tmp_path,
    executor_kind: str,
) -> None:
    report = WorkflowReport(
        workflow_id="canonical_report_test",
        run_id=f"unrecognized-status-{executor_kind}",
        error_policy="fail_fast",
        status="bogus",
        nodes=[],
    )
    _, ctx = _build_context(tmp_path)
    registry = MagicMock(spec=NodeRegistry)

    if executor_kind == "sync":
        with pytest.raises(_WorkflowReportStatusError, match="status"):
            WorkflowExecutor(ctx, registry)._persist_report(report)
    else:
        with pytest.raises(_WorkflowReportStatusError, match="status"):
            await AsyncWorkflowExecutor(ctx, registry)._persist_report(report)


@pytest.mark.asyncio
@pytest.mark.parametrize("executor_kind", ["sync", "async"])
@pytest.mark.parametrize(
    "status",
    [WorkflowExecutionStatus.OK.value, WorkflowExecutionStatus.FAIL.value],
)
async def test_workflow_report_writer_accepts_current_producer_statuses(
    tmp_path,
    executor_kind: str,
    status: str,
) -> None:
    report = WorkflowReport(
        workflow_id="canonical_report_test",
        run_id=f"current-status-{executor_kind}-{status}",
        error_policy="fail_fast",
        status=status,
        nodes=[],
    )
    store, ctx = _build_context(tmp_path)
    registry = MagicMock(spec=NodeRegistry)

    if executor_kind == "sync":
        report_ref = WorkflowExecutor(ctx, registry)._persist_report(report)
    else:
        report_ref = await AsyncWorkflowExecutor(ctx, registry)._persist_report(report)

    payload = from_canonical_bytes(store.get_bytes(report_ref.artifact_id))
    assert payload["status"] == status


def test_historical_workflow_report_status_remains_readable_without_write_gate() -> None:
    historical = WorkflowReport.model_validate(
        {
            "schema_version": "1.0",
            "workflow_id": "canonical_report_test",
            "run_id": "historical-state-only-result",
            "error_policy": "fail_fast",
            "status": "not_established",
            "nodes": [],
        }
    )

    assert historical.status == "not_established"

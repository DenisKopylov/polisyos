from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.errors import (
    CycleDetectedError,
    DuplicateAliasError,
    MissingDependencyError,
    WorkflowSpecError,
)
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeStatus
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.telemetry import (
    add_span_events,
    set_span_attribute,
    start_node_span,
)
from polisyos.scientist.engine.workflow_spec import ErrorPolicy, NodeInvocation, WorkflowSpec


class NodeRunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str
    node_id: str
    status: NodeStatus
    duration_ms: int = Field(ge=0)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    error: NodeError | None = None
    skip_reason: str | None = None


class WorkflowReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    workflow_id: str
    run_id: str
    error_policy: ErrorPolicy
    status: str
    nodes: list[NodeRunRecord] = Field(default_factory=list)


@dataclass(frozen=True)
class WorkflowExecutionResult:
    state: ExperimentState
    report: WorkflowReport
    run_ref: ArtifactRef | None = None


def _node_level_to_logging(level: str) -> int:
    return {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "error": logging.ERROR,
    }.get(level, logging.INFO)


def _log_node_events(logger: logging.Logger, alias: str, events: Iterable[Any]) -> None:
    for event in events:
        level = _node_level_to_logging(getattr(event, "level", "info"))
        code = getattr(event, "code", None)
        message = getattr(event, "message", "")
        attrs = getattr(event, "attrs", {})
        prefix = f"[{alias}]"
        if code:
            logger.log(level, "%s %s (%s) %s", prefix, message, code, attrs)
        else:
            logger.log(level, "%s %s %s", prefix, message, attrs)


def _bind_node_params(node: Any, params: dict[str, Any]) -> Any:
    if not params:
        return node
    binder = getattr(node, "bind", None)
    if callable(binder):
        try:
            bound = binder(params)
            return bound if bound is not None else node
        except Exception:
            return node
    return node


def _validate_required_binds(required: list[str], state: ExperimentState) -> None:
    for bind in required:
        if not _has_bind(state, bind):
            raise WorkflowSpecError(f"Missing required bind: {bind}")


def _has_bind(state: ExperimentState, bind: str) -> bool:
    parts = bind.split(".")
    current: Any = state
    for part in parts:
        if isinstance(current, BaseModel):
            if not hasattr(current, part):
                return False
            current = getattr(current, part)
        elif isinstance(current, dict):
            if part not in current:
                return False
            current = current.get(part)
        else:
            return False
    return current is not None


def _validate_aliases(nodes: list[NodeInvocation]) -> None:
    aliases = [n.alias for n in nodes]
    if len(set(aliases)) != len(aliases):
        raise DuplicateAliasError("NodeInvocation.alias must be unique within workflow")


def _validate_dependencies(invocations: dict[str, NodeInvocation]) -> None:
    for alias, inv in invocations.items():
        for dep in inv.depends_on:
            if dep not in invocations:
                raise MissingDependencyError(f"Missing dependency '{dep}' for node '{alias}'")


def _topo_sort(invocations: dict[str, NodeInvocation]) -> list[str]:
    indegree: dict[str, int] = {alias: 0 for alias in invocations}
    edges: dict[str, list[str]] = {alias: [] for alias in invocations}
    order_index = {alias: idx for idx, alias in enumerate(invocations.keys())}

    for alias, inv in invocations.items():
        for dep in inv.depends_on:
            edges[dep].append(alias)
            indegree[alias] += 1

    queue = [alias for alias, deg in indegree.items() if deg == 0]
    queue.sort(key=lambda a: order_index.get(a, 0))

    ordered: list[str] = []
    while queue:
        alias = queue.pop(0)
        ordered.append(alias)
        for nxt in edges[alias]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
        queue.sort(key=lambda a: order_index.get(a, 0))

    if len(ordered) != len(invocations):
        raise CycleDetectedError("Cycle detected in workflow graph")
    return ordered


class WorkflowExecutor:
    """Sequential workflow executor (v0)."""

    def __init__(self, ctx: ExecutionContext, registry: NodeRegistry) -> None:
        self._ctx = ctx
        self._registry = registry

    def execute(self, workflow: WorkflowSpec, state: ExperimentState) -> WorkflowExecutionResult:
        _validate_aliases(workflow.nodes)
        invocations = {inv.alias: inv for inv in workflow.nodes}
        _validate_dependencies(invocations)
        _validate_required_binds(workflow.required_binds, state)

        # Validate node availability before execution
        for inv in workflow.nodes:
            self._registry.get(inv.node_id)

        order = _topo_sort(invocations)

        initial_state = state.model_copy(deep=True)
        workflow_ref = self._persist_workflow_spec(workflow)
        self._ctx.run.add_input(workflow_ref)
        state_input_ref = self._persist_state(initial_state)
        self._ctx.run.add_input(state_input_ref)

        records: list[NodeRunRecord] = []
        failed: set[str] = set()
        blocked: set[str] = set()

        for alias in order:
            inv = invocations[alias]

            if any(dep in failed or dep in blocked for dep in inv.depends_on):
                record = NodeRunRecord(
                    alias=alias,
                    node_id=str(inv.node_id),
                    status="skip",
                    duration_ms=0,
                    skip_reason="upstream_failed",
                )
                records.append(record)
                blocked.add(alias)
                self._ctx.run.emit(
                    f"scientist.node.{alias}",
                    "NODE_SKIP",
                    metrics={"duration_ms": 0, "status_ok": 0},
                )
                continue

            node = _bind_node_params(self._registry.get(inv.node_id), inv.params)
            span_attrs = {
                "polisyos.run_id": state.run_id,
                "polisyos.workflow_id": workflow.workflow_id,
                "polisyos.node.alias": alias,
                "polisyos.node.id": str(inv.node_id),
            }

            with start_node_span(self._ctx.tracer, span_attrs) as span:
                self._ctx.run.emit(f"scientist.node.{alias}", "NODE_STARTED")
                started = time.perf_counter()
                try:
                    raw_outcome = node.execute(self._ctx, state)
                    outcome = NodeOutcome.model_validate(raw_outcome)
                except ValidationError as exc:
                    self._ctx.logger.exception("Node %s returned invalid outcome", alias)
                    outcome = NodeOutcome(
                        status="fail",
                        state=state,
                        error=NodeError(
                            code="node.invalid_outcome",
                            message="Node returned invalid outcome",
                            details={"error": str(exc)},
                        ),
                    )
                except Exception as exc:  # noqa: BLE001
                    self._ctx.logger.exception("Node %s failed", alias)
                    outcome = NodeOutcome(
                        status="fail",
                        state=state,
                        error=NodeError(
                            code="node.exception",
                            message=str(exc),
                            details={"type": exc.__class__.__name__},
                        ),
                    )

                duration_ms = int((time.perf_counter() - started) * 1000)
                state = outcome.state

                _log_node_events(self._ctx.logger, alias, outcome.events)
                add_span_events(span, outcome.events)
                set_span_attribute(span, "polisyos.node.status", outcome.status)
                set_span_attribute(span, "polisyos.node.duration_ms", duration_ms)

                status_event = {
                    "ok": "NODE_OK",
                    "skip": "NODE_SKIP",
                    "fail": "NODE_FAIL",
                }[outcome.status]
                self._ctx.run.emit(
                    f"scientist.node.{alias}",
                    status_event,
                    outputs=outcome.artifacts,
                    metrics={
                        "duration_ms": duration_ms,
                        "status_ok": 1 if outcome.status == "ok" else 0,
                    },
                )

                if outcome.status == "fail":
                    failed.add(alias)

                record = NodeRunRecord(
                    alias=alias,
                    node_id=str(inv.node_id),
                    status=outcome.status,
                    duration_ms=duration_ms,
                    artifacts=list(outcome.artifacts),
                    error=outcome.error,
                )
                records.append(record)

                if outcome.status == "fail" and workflow.error_policy == "fail_fast":
                    break

        overall_status = "fail" if failed else "ok"
        report = WorkflowReport(
            workflow_id=workflow.workflow_id,
            run_id=state.run_id,
            error_policy=workflow.error_policy,
            status=overall_status,
            nodes=records,
        )

        report_ref = self._persist_report(report)
        final_state = state.model_copy(deep=True)
        final_state.reports_index["workflow_report"] = report_ref
        final_state_ref = self._persist_state(final_state)

        self._ctx.run.add_output(final_state_ref)
        self._ctx.run.add_output(report_ref)

        errors_payload = [
            {
                "node": rec.alias,
                "code": rec.error.code,
                "message": rec.error.message,
            }
            for rec in records
            if rec.status == "fail" and rec.error is not None
        ]

        run_ref = self._ctx.run.finalize(
            status=overall_status,
            errors=errors_payload or None,
        )

        return WorkflowExecutionResult(state=final_state, report=report, run_ref=run_ref)

    def _persist_workflow_spec(self, workflow: WorkflowSpec) -> ArtifactRef:
        return self._ctx.store.put_json(
            workflow.model_dump(),
            PutOptions(
                kind="scientist.workflow_spec",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.engine.WorkflowSpec",
                    version="1.0",
                ),
            ),
        )

    def _persist_state(self, state: ExperimentState) -> ArtifactRef:
        return self._ctx.store.put_json(
            state.model_dump(),
            PutOptions(
                kind="scientist.experiment_state",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.engine.ExperimentState",
                    version="1.0",
                ),
            ),
        )

    def _persist_report(self, report: WorkflowReport) -> ArtifactRef:
        return self._ctx.store.put_json(
            report.model_dump(),
            PutOptions(
                kind="scientist.workflow_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.engine.WorkflowReport",
                    version="1.0",
                ),
            ),
        )

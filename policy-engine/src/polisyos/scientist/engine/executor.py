"""Public engine executor module API."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec, CanonViolation
from polisyos.scientist.engine.checkpoint import compute_workflow_fingerprint
from polisyos.scientist.engine.condition import ConditionSyntaxError, evaluate_condition
from polisyos.scientist.engine.errors import (
    CycleDetectedError,
    DuplicateAliasError,
    MissingDependencyError,
    NodeTimeoutError,
    RetryExhaustedError,
    WorkflowSpecError,
)
from polisyos.scientist.engine.idempotency import NodeResultCache, compute_idempotency_key
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeStatus
from polisyos.scientist.engine.retry import RetryPolicy, execute_with_retry_sync
from polisyos.scientist.engine.state_branching import branch_state, snapshot_state
from polisyos.scientist.engine.state_merge import merge_parallel_outcomes
from polisyos.scientist.engine.telemetry import (
    add_span_events,
    set_span_attribute,
    start_node_span,
)
from polisyos.scientist.engine.workflow_spec import ErrorPolicy
from polisyos.scientist.error_semantics import emit_degraded_path
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CLAIMS_REF,
    ARTIFACT_RESEARCH_DAG_REF,
)
from polisyos.scientist.research_dag.persistence import persist_research_dag
from polisyos.scientist.research_dag.projections import (
    SELECTED_RESEARCH_DAG_WORKFLOWS,
    is_research_dag_enabled,
    project_workflow_execution_to_research_dag,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from polisyos.scientist.engine.checkpoint import CheckpointHook
    from polisyos.scientist.engine.context import ExecutionContext
    from polisyos.scientist.engine.registry import NodeRegistry
    from polisyos.scientist.engine.state import ExperimentState
    from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

_CACHE_BYPASS_DISABLED = 1
_CACHE_BYPASS_KEY_ERROR = 2
_CACHE_BYPASS_STORE_ERROR = 3

_CACHE_DISABLED_NODE_IDS = frozenset(
    {
        "scientist.node_noop@1.0.0",
        "scientist.node_set_state@1.0.0",
        "scientist.node_emit_artifact@1.0.0",
        "scientist.node_enrich_knowledge@1.0.0",
        "scientist.node_enrich_knowledge@1.1.0",
    }
)
_EXECUTOR_DEGRADED_ERRORS = (
    ArithmeticError,
    AssertionError,
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)
_NODE_BIND_ERRORS = _EXECUTOR_DEGRADED_ERRORS
_NODE_EXECUTION_ERRORS = _EXECUTOR_DEGRADED_ERRORS


class NodeRunRecord(BaseModel):
    """Node run record data model."""

    model_config = ConfigDict(extra="forbid")

    alias: str
    node_id: str
    status: NodeStatus
    duration_ms: int = Field(ge=0)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    error: NodeError | None = None
    skip_reason: str | None = None


class WorkflowReport(BaseModel):
    """Workflow report data model."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    workflow_id: str
    run_id: str
    error_policy: ErrorPolicy
    status: str
    nodes: list[NodeRunRecord] = Field(default_factory=list)


@dataclass(frozen=True)
class WorkflowExecutionResult:
    """Workflow execution result data model."""

    state: ExperimentState
    report: WorkflowReport
    run_ref: ArtifactRef | None = None


class NodeBindError(RuntimeError):
    """Binding runtime parameters to a node failed."""

    def __init__(
        self,
        *,
        node_label: str,
        param_keys: tuple[str, ...],
        cause: BaseException,
    ) -> None:
        self.node_label = node_label
        self.param_keys = param_keys
        self.error_type = cause.__class__.__name__
        super().__init__(f"Node bind failed for {node_label}: {cause}")


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


_module_logger = get_logger(__name__)


def _executor_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return emit_degraded_path(
        component="engine.executor",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=_module_logger,
    )


def bind_node_params(node: Any, params: dict[str, Any]) -> Any:
    if not params:
        return node
    binder = getattr(node, "bind", None)
    if callable(binder):
        try:
            bound = binder(params)
            return bound if bound is not None else node
        except _NODE_BIND_ERRORS as exc:
            raise NodeBindError(
                node_label=str(getattr(node, "spec", node.__class__.__name__)),
                param_keys=tuple(sorted(params)),
                cause=exc,
            ) from exc
    return node


_bind_node_params = bind_node_params


def _merge_cached_outcome_state(
    *,
    alias: str,
    node: Any,
    base_state: ExperimentState,
    outcome: NodeOutcome,
) -> ExperimentState:
    """Apply cached branch-local state onto the current base state by declared writes."""
    merge_result = merge_parallel_outcomes(
        base_state,
        {alias: outcome},
        {alias: list(getattr(node.spec, "state_writes", ()))},
    )
    return merge_result.state


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


def _should_cache(node_id: str) -> bool:
    return node_id not in _CACHE_DISABLED_NODE_IDS


def _topo_sort(invocations: dict[str, NodeInvocation]) -> list[str]:
    indegree: dict[str, int] = dict.fromkeys(invocations, 0)
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

    def __init__(
        self,
        ctx: ExecutionContext,
        registry: NodeRegistry,
        *,
        checkpoint_hook: CheckpointHook | None = None,
        checkpoint_cache_seed_refs: list[ArtifactRef] | None = None,
        provenance_dag: Any | None = None,
    ) -> None:
        self._ctx = ctx
        self._registry = registry
        self._cache: NodeResultCache | None = None
        self._checkpoint_hook = checkpoint_hook
        self._checkpoint_cache_seed_refs = list(checkpoint_cache_seed_refs or [])
        self._provenance_dag = provenance_dag
        self._node_outputs: dict[str, list[ArtifactRef]] = {}

    def execute(self, workflow: WorkflowSpec, state: ExperimentState) -> WorkflowExecutionResult:
        _validate_aliases(workflow.nodes)
        invocations = {inv.alias: inv for inv in workflow.nodes}
        _validate_dependencies(invocations)
        _validate_required_binds(workflow.required_binds, state)

        # Validate node availability before execution
        for inv in workflow.nodes:
            self._registry.get(inv.node_id)

        order = _topo_sort(invocations)
        workflow_started = time.perf_counter()

        initial_state = snapshot_state(state)
        workflow_ref = self._persist_workflow_spec(workflow)
        self._ctx.run.add_input(workflow_ref)
        state_input_ref = self._persist_state(initial_state)
        self._ctx.run.add_input(state_input_ref)
        self._cache = NodeResultCache(self._ctx.store, run_id=state.run_id)
        restored_entries = self._cache.seed_from_trace(self._ctx.run.trace_path)
        restored_from_checkpoint = self._cache.seed_from_entry_refs(
            self._checkpoint_cache_seed_refs
        )
        if restored_entries:
            self._ctx.logger.info(
                "Recovered %s cached node outcomes for run_id=%s",
                restored_entries,
                state.run_id,
            )
        if restored_from_checkpoint:
            self._ctx.logger.info(
                "Recovered %s cached node outcomes from checkpoint refs for run_id=%s",
                restored_from_checkpoint,
                state.run_id,
            )

        records: list[NodeRunRecord] = []
        failed: set[str] = set()
        blocked: set[str] = set()
        condition_skipped: set[str] = set()
        completed_nodes: list[str] = []
        workflow_fingerprint = compute_workflow_fingerprint(workflow)

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

            # --- Condition evaluation ---
            if inv.condition is not None:
                try:
                    cond_result = evaluate_condition(inv.condition.expr, state)
                except ConditionSyntaxError as exc:
                    self._ctx.logger.error(
                        "Condition syntax error for node %s: %s",
                        alias,
                        exc,
                    )
                    cond_result = False

                if not cond_result:
                    if inv.condition.on_false == "fail":
                        record = NodeRunRecord(
                            alias=alias,
                            node_id=str(inv.node_id),
                            status="fail",
                            duration_ms=0,
                            error=NodeError(
                                code="node.condition_false",
                                message=f"Condition not met: {inv.condition.expr}",
                                details={"expr": inv.condition.expr, "on_false": "fail"},
                            ),
                        )
                        records.append(record)
                        failed.add(alias)
                        self._ctx.run.emit(
                            f"scientist.node.{alias}",
                            "NODE_FAIL",
                            metrics={"duration_ms": 0, "status_ok": 0},
                        )
                    else:
                        record = NodeRunRecord(
                            alias=alias,
                            node_id=str(inv.node_id),
                            status="skip",
                            duration_ms=0,
                            skip_reason="condition_false",
                        )
                        records.append(record)
                        condition_skipped.add(alias)
                        self._ctx.run.emit(
                            f"scientist.node.{alias}",
                            "NODE_SKIP",
                            metrics={"duration_ms": 0, "status_ok": 0},
                        )
                    if workflow.error_policy == "fail_fast" and alias in failed:
                        break
                    continue

            try:
                node = _bind_node_params(self._registry.get(inv.node_id), inv.params)
            except NodeBindError as exc:
                self._ctx.logger.exception("Node %s bind failed", alias)
                record = NodeRunRecord(
                    alias=alias,
                    node_id=str(inv.node_id),
                    status="fail",
                    duration_ms=0,
                    error=NodeError(
                        code="node.bind_failed",
                        message=str(exc),
                        details={
                            "node": exc.node_label,
                            "param_keys": list(exc.param_keys),
                            "type": exc.error_type,
                        },
                    ),
                )
                records.append(record)
                failed.add(alias)
                self._ctx.run.emit(
                    f"scientist.node.{alias}",
                    "NODE_FAIL",
                    metrics={"duration_ms": 0, "status_ok": 0},
                )
                if self._ctx.metrics is not None:
                    self._ctx.metrics.record_node_completed(
                        alias=alias,
                        node_id=str(inv.node_id),
                        workflow_id=workflow.workflow_id,
                        status="fail",
                        duration_ms=0,
                        cache_hit=False,
                        retry_count=0,
                    )
                if workflow.error_policy == "fail_fast":
                    break
                continue
            span_attrs = {
                "polisyos.run_id": state.run_id,
                "polisyos.workflow_id": workflow.workflow_id,
                "polisyos.node.alias": alias,
                "polisyos.node.id": str(inv.node_id),
            }

            with start_node_span(self._ctx.tracer, span_attrs) as span:
                self._ctx.run.emit(f"scientist.node.{alias}", "NODE_STARTED")
                if self._ctx.audit is not None:
                    self._ctx.audit.append(
                        run_id=state.run_id,
                        actor="engine",
                        action="NODE_STARTED",
                        metadata={"alias": alias, "node_id": str(inv.node_id)},
                    )
                if self._ctx.metrics is not None:
                    self._ctx.metrics.record_node_started(
                        alias=alias,
                        node_id=str(inv.node_id),
                        workflow_id=workflow.workflow_id,
                    )
                started = time.perf_counter()
                node_id = str(inv.node_id)
                cache_enabled = _should_cache(node_id)
                cache_key: str | None = None
                cache_hit = False
                cache_stored = False
                cache_entry_ref: ArtifactRef | None = None
                cache_bypass_reason: int | None = None
                set_span_attribute(span, "polisyos.node.cache.enabled", cache_enabled)

                if cache_enabled:
                    try:
                        cache_key = compute_idempotency_key(
                            spec=node.spec,
                            state=state,
                            bind_params=inv.params,
                        )
                        set_span_attribute(
                            span,
                            "polisyos.node.idempotency_key_prefix",
                            cache_key[:16],
                        )
                    except (CanonViolation, ValueError, TypeError) as exc:
                        cache_bypass_reason = _CACHE_BYPASS_KEY_ERROR
                        self._ctx.logger.warning(
                            "Idempotency key generation failed for node %s: %s",
                            alias,
                            exc,
                        )
                    except _EXECUTOR_DEGRADED_ERRORS as exc:
                        cache_bypass_reason = _CACHE_BYPASS_KEY_ERROR
                        _executor_degraded(
                            operation="compute_idempotency_key",
                            reason="unexpected_cache_key_failure",
                            exc=exc,
                            details={"alias": alias, "node_id": node_id},
                        )
                else:
                    cache_bypass_reason = _CACHE_BYPASS_DISABLED

                if cache_bypass_reason is not None:
                    self._ctx.run.emit(
                        f"scientist.node.{alias}",
                        "NODE_CACHE_BYPASS",
                        metrics={
                            "duration_ms": 0,
                            "cache_bypass": 1,
                            "reason_code": cache_bypass_reason,
                        },
                    )
                    set_span_attribute(
                        span,
                        "polisyos.node.cache.bypass_reason",
                        cache_bypass_reason,
                    )

                cached_outcome: NodeOutcome | None = None
                if cache_key is not None and self._cache is not None:
                    cached_outcome = self._cache.get(cache_key)
                    if cached_outcome is not None:
                        cache_hit = True
                        self._ctx.run.emit(
                            f"scientist.node.{alias}",
                            "NODE_CACHE_HIT",
                            metrics={
                                "duration_ms": int((time.perf_counter() - started) * 1000),
                                "cache_hit": 1,
                            },
                        )

                if cached_outcome is not None:
                    outcome = cached_outcome.model_copy(
                        update={
                            "state": _merge_cached_outcome_state(
                                alias=alias,
                                node=node,
                                base_state=state,
                                outcome=cached_outcome,
                            )
                        }
                    )
                else:
                    retry_policy = inv.retry or RetryPolicy()
                    branched_state = branch_state(
                        state,
                        write_paths=getattr(node.spec, "state_writes", ()),
                    )
                    node_state = branched_state.state
                    set_span_attribute(
                        span,
                        "polisyos.node.state_branch.isolated_paths",
                        ",".join(branched_state.journal.isolated_paths),
                    )
                    try:
                        raw_outcome = execute_with_retry_sync(
                            node,
                            self._ctx,
                            node_state,
                            retry_policy=retry_policy,
                            timeout_s=inv.timeout_s,
                            alias=alias,
                        )
                        outcome = NodeOutcome.model_validate(raw_outcome)
                    except NodeTimeoutError as exc:
                        self._ctx.logger.error("Node %s timed out", alias)
                        outcome = NodeOutcome(
                            status="fail",
                            state=state,
                            error=NodeError(
                                code="node.timeout",
                                message=str(exc),
                                details={"timeout_s": inv.timeout_s},
                            ),
                        )
                    except RetryExhaustedError as exc:
                        self._ctx.logger.error("Node %s exhausted retries", alias)
                        outcome = NodeOutcome(
                            status="fail",
                            state=state,
                            error=NodeError(
                                code="node.retry_exhausted",
                                message=str(exc),
                                details={"max_retries": retry_policy.max_retries},
                            ),
                        )
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
                    except _NODE_EXECUTION_ERRORS as exc:
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

                    if outcome.status == "ok" and cache_key is not None and self._cache is not None:
                        try:
                            entry_ref = self._cache.put(cache_key, node_id=node_id, outcome=outcome)
                            cache_entry_ref = entry_ref
                            cache_stored = True
                            self._ctx.run.emit(
                                f"scientist.node.{alias}",
                                "NODE_CACHE_STORE",
                                outputs=[entry_ref],
                                metrics={
                                    "duration_ms": int((time.perf_counter() - started) * 1000),
                                    "cache_store": 1,
                                },
                            )
                        except _EXECUTOR_DEGRADED_ERRORS as exc:
                            envelope = _executor_degraded(
                                operation="store_cache_entry",
                                reason="cache_bypass",
                                exc=exc,
                                details={"alias": alias, "node_id": node_id},
                            )
                            outcome.events.append(
                                NodeEvent(
                                    level="warn",
                                    message="Node result cache write bypassed",
                                    code="node.cache_bypass",
                                    attrs={
                                        "reason": str(envelope.get("reason", "cache_bypass")),
                                        "error_type": str(
                                            envelope.get("error_type", "runtime_error")
                                        ),
                                    },
                                )
                            )
                            self._ctx.run.emit(
                                f"scientist.node.{alias}",
                                "NODE_CACHE_BYPASS",
                                metrics={
                                    "duration_ms": 0,
                                    "cache_bypass": 1,
                                    "reason_code": _CACHE_BYPASS_STORE_ERROR,
                                },
                            )
                            set_span_attribute(
                                span,
                                "polisyos.node.cache.bypass_reason",
                                _CACHE_BYPASS_STORE_ERROR,
                            )

                duration_ms = int((time.perf_counter() - started) * 1000)
                if self._ctx.metrics is not None:
                    self._ctx.metrics.record_node_completed(
                        alias=alias,
                        node_id=str(inv.node_id),
                        workflow_id=workflow.workflow_id,
                        status=outcome.status,
                        duration_ms=duration_ms,
                        cache_hit=cache_hit,
                        retry_count=0,
                    )
                if outcome.status == "ok":
                    state = outcome.state

                # Record provenance
                if self._provenance_dag is not None:
                    try:
                        ended_at = datetime.now(UTC)
                        started_at_dt = datetime.fromtimestamp(
                            ended_at.timestamp() - duration_ms / 1000,
                            tz=UTC,
                        )
                        if outcome.status == "ok":
                            input_refs: list[Any] = []
                            for dep in inv.depends_on or []:
                                input_refs.extend(self._node_outputs.get(dep, []))
                            self._provenance_dag.record_node_execution(
                                alias=alias,
                                node_id=node_id,
                                started_at=started_at_dt,
                                ended_at=ended_at,
                                input_refs=input_refs,
                                output_refs=list(outcome.artifacts),
                                params=dict(inv.params) if inv.params else {},
                            )
                            self._node_outputs[alias] = list(outcome.artifacts)
                        elif outcome.status == "fail":
                            self._provenance_dag.record_node_failure(
                                alias=alias,
                                node_id=node_id,
                                error=str(outcome.error.message) if outcome.error else "Unknown",
                                traceback=(
                                    outcome.error.details.get("type", "")
                                    if outcome.error and outcome.error.details
                                    else None
                                ),
                                started_at=started_at_dt,
                                ended_at=ended_at,
                            )
                    except _EXECUTOR_DEGRADED_ERRORS as exc:
                        envelope = _executor_degraded(
                            operation="record_provenance",
                            reason="provenance_record_failed",
                            exc=exc,
                            details={"alias": alias, "node_id": node_id},
                        )
                        outcome.events.append(
                            NodeEvent(
                                level="warn",
                                message="Node provenance recording degraded",
                                code="node.provenance_degraded",
                                attrs={
                                    "reason": str(
                                        envelope.get("reason", "provenance_record_failed")
                                    ),
                                    "error_type": str(envelope.get("error_type", "runtime_error")),
                                },
                            )
                        )

                _log_node_events(self._ctx.logger, alias, outcome.events)
                add_span_events(span, outcome.events)
                set_span_attribute(span, "polisyos.node.status", outcome.status)
                set_span_attribute(span, "polisyos.node.duration_ms", duration_ms)
                set_span_attribute(span, "polisyos.node.cache.hit", cache_hit)
                set_span_attribute(span, "polisyos.node.cache.store", cache_stored)

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

                if self._ctx.audit is not None:
                    audit_action = "NODE_COMPLETED" if outcome.status == "ok" else "NODE_FAILED"
                    self._ctx.audit.append(
                        run_id=state.run_id,
                        actor="engine",
                        action=audit_action,
                        artifact_refs=list(outcome.artifacts) if outcome.artifacts else None,
                        metadata={
                            "alias": alias,
                            "node_id": node_id,
                            "status": outcome.status,
                            "duration_ms": duration_ms,
                            "cache_hit": cache_hit,
                            "error": str(outcome.error) if outcome.error else None,
                        },
                    )

                if outcome.status == "fail":
                    failed.add(alias)

                if outcome.status == "ok":
                    completed_nodes.append(alias)
                    if self._checkpoint_hook is not None:
                        checkpoint_result = self._checkpoint_hook.on_node_complete(
                            state=state,
                            alias=alias,
                            node_id=node_id,
                            completed_nodes=list(completed_nodes),
                            workflow_id=workflow.workflow_id,
                            workflow_fingerprint=workflow_fingerprint,
                            cache_entry_ref=cache_entry_ref,
                        )
                        if checkpoint_result is not None:
                            checkpoint_state = branch_state(
                                state,
                                write_paths=("last_checkpoint_ref",),
                            ).state
                            checkpoint_state.last_checkpoint_ref = checkpoint_result.checkpoint_ref
                            state = checkpoint_state
                            self._ctx.run.emit(
                                "scientist.checkpoint",
                                "CHECKPOINT_CREATED",
                                outputs=[checkpoint_result.checkpoint_ref],
                                metrics={
                                    "sequence_number": checkpoint_result.sequence_number,
                                    "duration_ms": checkpoint_result.duration_ms,
                                },
                            )
                            if self._ctx.audit is not None:
                                self._ctx.audit.append(
                                    run_id=state.run_id,
                                    actor="engine",
                                    action="CHECKPOINT_CREATED",
                                    artifact_refs=[checkpoint_result.checkpoint_ref],
                                    metadata={
                                        "sequence_number": checkpoint_result.sequence_number,
                                        "alias": alias,
                                    },
                                )

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
        if self._ctx.metrics is not None:
            self._ctx.metrics.record_workflow_completed(
                workflow_id=workflow.workflow_id,
                status=overall_status,
                duration_ms=int((time.perf_counter() - workflow_started) * 1000),
                node_count=len(records),
            )
        report = WorkflowReport(
            workflow_id=workflow.workflow_id,
            run_id=state.run_id,
            error_policy=workflow.error_policy,
            status=overall_status,
            nodes=records,
        )

        report_ref = self._persist_report(report)
        research_dag_ref: ArtifactRef | None = None
        if (
            workflow.workflow_id in SELECTED_RESEARCH_DAG_WORKFLOWS
            and is_research_dag_enabled(state.params)
        ):
            try:
                research_dag = project_workflow_execution_to_research_dag(
                    run_id=state.run_id,
                    workflow_id=workflow.workflow_id,
                    records=records,
                    state=state,
                    claim_ledger_ref=state.artifacts_index.get(ARTIFACT_CLAIMS_REF),
                )
                research_dag_ref = persist_research_dag(self._ctx.store, research_dag)
                self._ctx.run.add_output(research_dag_ref)
            except _EXECUTOR_DEGRADED_ERRORS as exc:
                _executor_degraded(
                    operation="persist_research_dag",
                    reason="research_dag_sidecar_failed",
                    exc=exc,
                    details={"workflow_id": workflow.workflow_id},
                )
                research_dag_ref = None

        final_write_paths = ["reports_index.workflow_report"]
        if research_dag_ref is not None:
            final_write_paths.append(f"artifacts_index.{ARTIFACT_RESEARCH_DAG_REF}")
        final_state = branch_state(
            state,
            write_paths=tuple(final_write_paths),
        ).state
        final_state.reports_index["workflow_report"] = report_ref
        if research_dag_ref is not None:
            final_state.artifacts_index[ARTIFACT_RESEARCH_DAG_REF] = research_dag_ref
        final_state_ref = self._persist_state(final_state)

        self._ctx.run.add_output(final_state_ref)
        self._ctx.run.add_output(report_ref)

        # Finalize and persist provenance DAG
        if self._provenance_dag is not None:
            try:
                self._provenance_dag.finalize()
                prov_json = self._provenance_dag.to_prov_json()
                prov_ref = self._ctx.store.put_json(
                    prov_json,
                    PutOptions(
                        kind="scientist.provenance.run_dag",
                        media_type="application/json",
                    ),
                )
                self._ctx.run.add_output(prov_ref)
            except _EXECUTOR_DEGRADED_ERRORS as exc:
                _executor_degraded(
                    operation="finalize_provenance",
                    reason="provenance_finalize_failed",
                    exc=exc,
                    details={"workflow_id": workflow.workflow_id},
                )

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
            canon_spec=CanonSpec(forbid_floats=False),
        )

    def _persist_state(self, state: ExperimentState) -> ArtifactRef:
        return self._ctx.store.put_json(
            state.model_dump(),
            PutOptions(
                kind="scientist.experiment_state",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.engine.ExperimentState",
                    version=state.schema_version,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
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

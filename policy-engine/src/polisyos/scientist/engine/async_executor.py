"""Async workflow executor with parallel DAG tier execution.

Uses :func:`topo_sort_tiers` to group nodes into topological levels, then
executes each tier in parallel via ``asyncio.TaskGroup`` +
``asyncio.to_thread`` (nodes remain sync — no need to rewrite 35+ nodes).

Feature-flagged via ``POLISYOS_ASYNC_EXECUTOR=1`` and opt-in through
``run_selected_workflow``.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.engine.checkpoint import compute_workflow_fingerprint
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.errors import (
    NodeTimeoutError,
    RetryExhaustedError,
    WorkflowTimeoutError,
)
from polisyos.scientist.engine.condition import ConditionSyntaxError, evaluate_condition
from polisyos.scientist.engine.executor import (
    NodeRunRecord,
    WorkflowExecutionResult,
    WorkflowReport,
    _bind_node_params,
    _log_node_events,
    _should_cache,
    _topo_sort,
    _validate_aliases,
    _validate_dependencies,
    _validate_required_binds,
)
from polisyos.scientist.engine.idempotency import NodeResultCache, compute_idempotency_key
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeStatus
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.retry import RetryPolicy, execute_with_retry_async
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_merge import merge_parallel_outcomes
from polisyos.scientist.engine.telemetry import (
    add_span_events,
    set_span_attribute,
    start_node_span,
)
from polisyos.scientist.engine.topo import topo_sort_tiers
from polisyos.scientist.engine.trace_attributes import (
    build_node_span_attributes,
    enrich_node_span_result,
)
from polisyos.scientist.engine.workflow_spec import ErrorPolicy, NodeInvocation, WorkflowSpec

if TYPE_CHECKING:
    from polisyos.scientist.engine.checkpoint import CheckpointHook
    from polisyos.scientist.provenance.run_dag import RunProvenanceDAG

_module_logger = get_logger(__name__)


class AsyncWorkflowExecutor:
    """Async workflow executor with parallel DAG branches."""

    def __init__(
        self,
        ctx: ExecutionContext,
        registry: NodeRegistry,
        *,
        checkpoint_hook: "CheckpointHook | None" = None,
        checkpoint_cache_seed_refs: list[ArtifactRef] | None = None,
        max_parallelism: int = 4,
        provenance_dag: "RunProvenanceDAG | None" = None,
        semaphore_timeout_s: float | None = None,
        workflow_timeout_s: float | None = None,
        budget_middleware: Any | None = None,
    ) -> None:
        self._ctx = ctx
        self._registry = registry
        self._cache: NodeResultCache | None = None
        self._checkpoint_hook = checkpoint_hook
        self._checkpoint_cache_seed_refs = list(checkpoint_cache_seed_refs or [])
        self._max_parallelism = max(1, max_parallelism)
        self._provenance_dag = provenance_dag
        self._semaphore_timeout_s = semaphore_timeout_s
        self._workflow_timeout_s = workflow_timeout_s
        self._budget_middleware = budget_middleware
        self._node_outputs: dict[str, list[ArtifactRef]] = {}
        self._pre_node_state_keys: dict[str, set[str]] = {}

    async def execute(
        self, workflow: WorkflowSpec, state: ExperimentState,
    ) -> WorkflowExecutionResult:
        _validate_aliases(workflow.nodes)
        invocations = {inv.alias: inv for inv in workflow.nodes}
        _validate_dependencies(invocations)
        _validate_required_binds(workflow.required_binds, state)

        for inv in workflow.nodes:
            self._registry.get(inv.node_id)

        tiers = topo_sort_tiers(invocations)
        workflow_started = time.perf_counter()

        if self._ctx.metrics is not None:
            self._ctx.metrics.record_workflow_state(
                run_id=state.run_id, workflow_id=workflow.workflow_id, state="running",
            )

        initial_state = state.model_copy(deep=True)
        workflow_ref = self._persist_workflow_spec(workflow)
        self._ctx.run.add_input(workflow_ref)
        state_input_ref = self._persist_state(initial_state)
        self._ctx.run.add_input(state_input_ref)

        self._cache = NodeResultCache(self._ctx.store, run_id=state.run_id)
        restored = self._cache.seed_from_trace(self._ctx.run.trace_path)
        restored_cp = self._cache.seed_from_entry_refs(self._checkpoint_cache_seed_refs)
        if restored:
            self._ctx.logger.info("Recovered %s cached node outcomes", restored)
        if restored_cp:
            self._ctx.logger.info("Recovered %s cached outcomes from checkpoint", restored_cp)

        records: list[NodeRunRecord] = []
        failed: set[str] = set()
        blocked: set[str] = set()
        condition_skipped: set[str] = set()
        completed_nodes: list[str] = []
        workflow_fingerprint = compute_workflow_fingerprint(workflow)
        abort = False

        async def _execute_tiers() -> None:
            nonlocal state, abort
            for tier_index, tier in enumerate(tiers):
                if abort:
                    for alias in tier:
                        records.append(NodeRunRecord(
                            alias=alias, node_id=str(invocations[alias].node_id),
                            status="skip", duration_ms=0, skip_reason="upstream_failed",
                        ))
                        blocked.add(alias)
                    continue

                runnable: list[str] = []
                for alias in tier:
                    inv = invocations[alias]
                    if any(dep in failed or dep in blocked for dep in inv.depends_on):
                        records.append(NodeRunRecord(
                            alias=alias, node_id=str(inv.node_id),
                            status="skip", duration_ms=0, skip_reason="upstream_failed",
                        ))
                        blocked.add(alias)
                        self._ctx.run.emit(
                            f"scientist.node.{alias}", "NODE_SKIP",
                            metrics={"duration_ms": 0, "status_ok": 0},
                        )
                        continue

                    if inv.condition is not None:
                        try:
                            cond_result = evaluate_condition(inv.condition.expr, state)
                        except ConditionSyntaxError as exc:
                            self._ctx.logger.error(
                                "Condition syntax error for node %s: %s", alias, exc,
                            )
                            cond_result = False

                        if not cond_result:
                            if inv.condition.on_false == "fail":
                                records.append(NodeRunRecord(
                                    alias=alias, node_id=str(inv.node_id),
                                    status="fail", duration_ms=0,
                                    error=NodeError(
                                        code="node.condition_false",
                                        message=f"Condition not met: {inv.condition.expr}",
                                        details={"expr": inv.condition.expr, "on_false": "fail"},
                                    ),
                                ))
                                failed.add(alias)
                                self._ctx.run.emit(
                                    f"scientist.node.{alias}", "NODE_FAIL",
                                    metrics={"duration_ms": 0, "status_ok": 0},
                                )
                            else:
                                records.append(NodeRunRecord(
                                    alias=alias, node_id=str(inv.node_id),
                                    status="skip", duration_ms=0,
                                    skip_reason="condition_false",
                                ))
                                condition_skipped.add(alias)
                                self._ctx.run.emit(
                                    f"scientist.node.{alias}", "NODE_SKIP",
                                    metrics={"duration_ms": 0, "status_ok": 0},
                                )
                            continue

                    runnable.append(alias)

                if failed and workflow.error_policy == "fail_fast":
                    abort = True

                if not runnable or abort:
                    continue

                # Tier savepoint for rollback on failure
                tier_savepoint = state.model_copy(deep=True)
                tier_started = time.perf_counter()

                if len(runnable) == 1:
                    alias = runnable[0]
                    record, state, node_failed = await self._run_single_node(
                        alias, invocations[alias], state, workflow,
                        workflow_fingerprint, completed_nodes,
                        tier_index=tier_index,
                    )
                    records.append(record)
                    if node_failed:
                        failed.add(alias)
                        if workflow.error_policy == "fail_fast":
                            state = tier_savepoint
                            abort = True
                    else:
                        completed_nodes.append(alias)
                else:
                    # Backpressure metrics
                    if self._ctx.metrics is not None:
                        self._ctx.metrics.record_backpressure(
                            tier_index=tier_index,
                            queued_tasks=len(runnable),
                            active_tasks=0,
                            workflow_id=workflow.workflow_id,
                        )

                    tier_records, state, tier_failed = await self._run_parallel_tier(
                        runnable, invocations, state, workflow,
                        workflow_fingerprint, completed_nodes,
                        tier_index=tier_index,
                    )
                    records.extend(tier_records)
                    for alias in tier_failed:
                        failed.add(alias)
                    for rec in tier_records:
                        if rec.status == "ok":
                            completed_nodes.append(rec.alias)
                    if tier_failed and workflow.error_policy == "fail_fast":
                        state = tier_savepoint
                        abort = True

                tier_duration_ms = int((time.perf_counter() - tier_started) * 1000)
                if self._ctx.metrics is not None:
                    self._ctx.metrics.record_tier_completed(
                        tier_index=tier_index,
                        tier_size=len(runnable),
                        duration_ms=tier_duration_ms,
                        workflow_id=workflow.workflow_id,
                    )

        # Execute tiers with optional workflow-level timeout
        if self._workflow_timeout_s is not None:
            try:
                await asyncio.wait_for(
                    _execute_tiers(), timeout=self._workflow_timeout_s,
                )
            except asyncio.TimeoutError:
                raise WorkflowTimeoutError(
                    f"Workflow {workflow.workflow_id} exceeded "
                    f"timeout of {self._workflow_timeout_s}s",
                )
        else:
            await _execute_tiers()

        overall_status = "fail" if failed else "ok"
        if self._ctx.metrics is not None:
            self._ctx.metrics.record_workflow_completed(
                workflow_id=workflow.workflow_id,
                status=overall_status,
                duration_ms=int((time.perf_counter() - workflow_started) * 1000),
                node_count=len(records),
            )
            self._ctx.metrics.record_workflow_state(
                run_id=state.run_id, workflow_id=workflow.workflow_id, state=overall_status,
            )

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

        # Finalize and persist provenance DAG
        if self._provenance_dag is not None:
            try:
                prov_graph = self._provenance_dag.finalize()
                prov_json = self._provenance_dag.to_prov_json()
                prov_ref = self._ctx.store.put_json(
                    prov_json,
                    PutOptions(
                        kind="scientist.provenance.run_dag",
                        media_type="application/json",
                    ),
                )
                self._ctx.run.add_output(prov_ref)
            except Exception:  # noqa: BLE001 — provenance must never crash pipeline
                _module_logger.debug("Provenance DAG finalization failed")

        errors_payload = [
            {"node": r.alias, "code": r.error.code, "message": r.error.message}
            for r in records if r.status == "fail" and r.error is not None
        ]
        run_ref = self._ctx.run.finalize(
            status=overall_status, errors=errors_payload or None,
        )

        return WorkflowExecutionResult(state=final_state, report=report, run_ref=run_ref)

    async def _run_single_node(
        self,
        alias: str,
        inv: NodeInvocation,
        state: ExperimentState,
        workflow: WorkflowSpec,
        workflow_fingerprint: str,
        completed_nodes: list[str],
        tier_index: int = 0,
    ) -> tuple[NodeRunRecord, ExperimentState, bool]:
        """Execute a single node (same semantics as sync executor)."""
        outcome, duration_ms, cache_hit = await self._execute_node(
            alias, inv, state, workflow, tier_index=tier_index,
        )
        state = outcome.state
        node_failed = outcome.status == "fail"

        if outcome.status == "ok" and self._checkpoint_hook is not None:
            self._handle_checkpoint(
                state, alias, str(inv.node_id),
                completed_nodes + [alias], workflow, workflow_fingerprint,
                cache_entry_ref=None,
            )

        record = NodeRunRecord(
            alias=alias, node_id=str(inv.node_id),
            status=outcome.status, duration_ms=duration_ms,
            artifacts=list(outcome.artifacts),
            error=outcome.error,
        )
        return record, state, node_failed

    async def _run_parallel_tier(
        self,
        aliases: list[str],
        invocations: dict[str, NodeInvocation],
        state: ExperimentState,
        workflow: WorkflowSpec,
        workflow_fingerprint: str,
        completed_nodes: list[str],
        tier_index: int = 0,
    ) -> tuple[list[NodeRunRecord], ExperimentState, set[str]]:
        """Execute a parallel tier using asyncio.TaskGroup."""
        semaphore = asyncio.Semaphore(self._max_parallelism)
        results: dict[str, tuple[NodeOutcome, int, bool]] = {}
        cancel_event = asyncio.Event()

        async def _run_with_sem(alias: str) -> None:
            # Check cancellation before acquiring semaphore
            if cancel_event.is_set():
                task_state = state.model_copy(deep=True)
                results[alias] = (
                    NodeOutcome(
                        status="skip", state=task_state,
                        events=[NodeEvent(
                            level="info", message="Cancelled by fail_fast",
                            code="node.cancelled", attrs={},
                        )],
                    ), 0, False,
                )
                return

            # Per-task state snapshot to prevent cross-contamination
            task_state = state.model_copy(deep=True)

            # Semaphore with optional timeout
            sem_wait_start = time.perf_counter()
            if self._semaphore_timeout_s is not None:
                try:
                    await asyncio.wait_for(
                        semaphore.acquire(), timeout=self._semaphore_timeout_s,
                    )
                except asyncio.TimeoutError:
                    results[alias] = (
                        NodeOutcome(
                            status="fail", state=task_state,
                            error=NodeError(
                                code="node.semaphore_timeout",
                                message=f"Node {alias} timed out waiting for execution slot",
                                details={"timeout_s": self._semaphore_timeout_s},
                            ),
                        ), 0, False,
                    )
                    return
            else:
                await semaphore.acquire()
            sem_wait_s = time.perf_counter() - sem_wait_start
            if self._ctx.metrics is not None and sem_wait_s > 0.001:
                self._ctx.metrics.record_semaphore_wait(
                    tier_index=tier_index, wait_seconds=sem_wait_s,
                    workflow_id=workflow.workflow_id,
                )

            try:
                outcome, duration_ms, cache_hit = await self._execute_node(
                    alias, invocations[alias], task_state, workflow,
                    tier_index=tier_index,
                )
                results[alias] = (outcome, duration_ms, cache_hit)
                # Signal cancellation on fail_fast
                if outcome.status == "fail" and workflow.error_policy == "fail_fast":
                    cancel_event.set()
            finally:
                semaphore.release()

        async with asyncio.TaskGroup() as tg:
            for alias in aliases:
                tg.create_task(_run_with_sem(alias))

        # Merge results
        ok_outcomes: dict[str, NodeOutcome] = {}
        write_specs: dict[str, list[str]] = {}
        records: list[NodeRunRecord] = []
        tier_failed: set[str] = set()

        for alias in aliases:
            outcome, duration_ms, cache_hit = results[alias]
            records.append(NodeRunRecord(
                alias=alias, node_id=str(invocations[alias].node_id),
                status=outcome.status, duration_ms=duration_ms,
                artifacts=list(outcome.artifacts), error=outcome.error,
            ))
            if outcome.status == "ok":
                ok_outcomes[alias] = outcome
                node = self._registry.get(invocations[alias].node_id)
                write_specs[alias] = list(node.spec.state_writes)
            elif outcome.status == "fail":
                tier_failed.add(alias)

        if ok_outcomes:
            merge_result = merge_parallel_outcomes(state, ok_outcomes, write_specs)
            state = merge_result.state
            if merge_result.conflicts:
                self._ctx.logger.warning(
                    "Parallel merge conflicts: %s", merge_result.conflicts,
                )

        return records, state, tier_failed

    async def _execute_node(
        self,
        alias: str,
        inv: NodeInvocation,
        state: ExperimentState,
        workflow: WorkflowSpec,
        tier_index: int = 0,
    ) -> tuple[NodeOutcome, int, bool]:
        """Execute a single node with cache, retry, timeout, metrics."""
        node = _bind_node_params(self._registry.get(inv.node_id), inv.params)
        node_id = str(inv.node_id)

        # Build structured span attributes for OTel
        span_attrs = build_node_span_attributes(
            alias=alias,
            node_id=node_id,
            workflow_id=workflow.workflow_id,
            tier_index=tier_index,
            run_id=state.run_id,
        )

        # Capture pre-node state keys for provenance mutation tracking
        if self._provenance_dag is not None:
            self._pre_node_state_keys[alias] = set(state.artifacts_index.keys())

        self._ctx.run.emit(f"scientist.node.{alias}", "NODE_STARTED")
        if self._ctx.audit is not None:
            self._ctx.audit.append(
                run_id=state.run_id, actor="engine",
                action="NODE_STARTED",
                metadata={"alias": alias, "node_id": node_id},
            )
        if self._ctx.metrics is not None:
            self._ctx.metrics.record_node_started(
                alias=alias, node_id=node_id, workflow_id=workflow.workflow_id,
            )

        started = time.perf_counter()
        cache_hit = False

        # Cache check
        cache_key: str | None = None
        if _should_cache(node_id):
            try:
                cache_key = compute_idempotency_key(
                    spec=node.spec, state=state, bind_params=inv.params,
                )
            except Exception:  # noqa: BLE001
                pass

        # Budget pre-check
        if self._budget_middleware is not None:
            try:
                self._budget_middleware.pre_check(alias)
                new_alerts = self._budget_middleware.check_thresholds()
                for level in new_alerts:
                    self._ctx.run.emit(
                        "scientist.budget", "BUDGET_ALERT",
                        metrics={"threshold_pct": level},
                    )
            except Exception as budget_exc:
                from polisyos.scientist.engine.budget import BudgetExhaustedError
                if isinstance(budget_exc, BudgetExhaustedError):
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    return NodeOutcome(
                        status="fail", state=state,
                        error=NodeError(
                            code="node.budget_exhausted",
                            message=str(budget_exc),
                            details={},
                        ),
                    ), duration_ms, False
                raise

        cached_outcome: NodeOutcome | None = None
        if cache_key and self._cache:
            cached_outcome = self._cache.get(cache_key)
            if cached_outcome:
                cache_hit = True

        if cached_outcome is not None:
            outcome = cached_outcome
        else:
            retry_policy = inv.retry or RetryPolicy()
            retry_stats: dict[str, int] = {}
            try:
                raw_outcome = await execute_with_retry_async(
                    node, self._ctx, state,
                    retry_policy=retry_policy,
                    timeout_s=inv.timeout_s,
                    alias=alias,
                    retry_stats=retry_stats,
                )
                outcome = NodeOutcome.model_validate(raw_outcome)
            except NodeTimeoutError as exc:
                self._ctx.logger.error("Node %s timed out", alias)
                outcome = NodeOutcome(
                    status="fail", state=state,
                    error=NodeError(code="node.timeout", message=str(exc),
                                    details={"timeout_s": inv.timeout_s}),
                )
            except RetryExhaustedError as exc:
                self._ctx.logger.error("Node %s exhausted retries", alias)
                outcome = NodeOutcome(
                    status="fail", state=state,
                    error=NodeError(code="node.retry_exhausted", message=str(exc),
                                    details={"max_retries": retry_policy.max_retries}),
                )
            except ValidationError as exc:
                outcome = NodeOutcome(
                    status="fail", state=state,
                    error=NodeError(code="node.invalid_outcome",
                                    message="Node returned invalid outcome",
                                    details={"error": str(exc)}),
                )
            except Exception as exc:  # noqa: BLE001
                self._ctx.logger.exception("Node %s failed", alias)
                outcome = NodeOutcome(
                    status="fail", state=state,
                    error=NodeError(code="node.exception", message=str(exc),
                                    details={"type": exc.__class__.__name__}),
                )

            # Cache store
            if outcome.status == "ok" and cache_key and self._cache:
                try:
                    self._cache.put(cache_key, node_id=node_id, outcome=outcome)
                except Exception:  # noqa: BLE001
                    pass

        duration_ms = int((time.perf_counter() - started) * 1000)

        # Enrich span with post-execution attributes
        enrich_node_span_result(
            span_attrs, status=outcome.status,
            duration_ms=duration_ms, cache_hit=cache_hit,
        )
        for key, value in span_attrs.items():
            set_span_attribute(None, key, value)  # best-effort; span from tracer

        # Record provenance
        if self._provenance_dag is not None:
            try:
                from datetime import datetime, timezone
                ended_at = datetime.now(timezone.utc)
                started_at = datetime.fromtimestamp(
                    ended_at.timestamp() - duration_ms / 1000, tz=timezone.utc,
                )
                if outcome.status == "ok":
                    # Collect input refs from upstream dependencies
                    input_refs: list[Any] = []
                    for dep in (inv.depends_on or []):
                        input_refs.extend(self._node_outputs.get(dep, []))
                    self._provenance_dag.record_node_execution(
                        alias=alias, node_id=node_id,
                        started_at=started_at, ended_at=ended_at,
                        input_refs=input_refs,
                        output_refs=list(outcome.artifacts),
                        params=dict(inv.params) if inv.params else {},
                    )
                    # Track outputs for downstream input_refs
                    self._node_outputs[alias] = list(outcome.artifacts)
                    # Record state mutations
                    pre_keys = self._pre_node_state_keys.get(alias, set())
                    post_keys = set(outcome.state.artifacts_index.keys())
                    keys_added = sorted(post_keys - pre_keys)
                    keys_modified = sorted(
                        k for k in pre_keys & post_keys
                        if outcome.state.artifacts_index.get(k)
                        != state.artifacts_index.get(k)
                    )
                    if keys_added or keys_modified:
                        self._provenance_dag.record_state_mutation(
                            alias=alias,
                            keys_added=keys_added or None,
                            keys_modified=keys_modified or None,
                        )
                elif outcome.status == "fail":
                    self._provenance_dag.record_node_failure(
                        alias=alias, node_id=node_id,
                        error=str(outcome.error.message) if outcome.error else "Unknown",
                        traceback=outcome.error.details.get("type", "") if outcome.error and outcome.error.details else None,
                        started_at=started_at, ended_at=ended_at,
                    )
            except Exception:  # noqa: BLE001 — provenance must never crash pipeline
                _module_logger.debug("Provenance recording failed for node %s", alias)

        _log_node_events(self._ctx.logger, alias, outcome.events)
        status_event = {"ok": "NODE_OK", "skip": "NODE_SKIP", "fail": "NODE_FAIL"}[outcome.status]
        self._ctx.run.emit(
            f"scientist.node.{alias}", status_event,
            outputs=outcome.artifacts,
            metrics={"duration_ms": duration_ms, "status_ok": 1 if outcome.status == "ok" else 0},
        )

        if self._ctx.audit is not None:
            audit_action = "NODE_COMPLETED" if outcome.status == "ok" else "NODE_FAILED"
            self._ctx.audit.append(
                run_id=state.run_id, actor="engine",
                action=audit_action,
                artifact_refs=list(outcome.artifacts) if outcome.artifacts else None,
                metadata={
                    "alias": alias,
                    "node_id": node_id,
                    "status": outcome.status,
                    "duration_ms": duration_ms,
                    "cache_hit": cache_hit,
                },
            )

        if self._ctx.metrics is not None:
            actual_retry_count = max(0, retry_stats.get("attempts", 1) - 1)
            self._ctx.metrics.record_node_completed(
                alias=alias, node_id=node_id,
                workflow_id=workflow.workflow_id,
                status=outcome.status, duration_ms=duration_ms,
                cache_hit=cache_hit, retry_count=actual_retry_count,
            )

        return outcome, duration_ms, cache_hit

    def _handle_checkpoint(
        self,
        state: ExperimentState,
        alias: str,
        node_id: str,
        completed_nodes: list[str],
        workflow: WorkflowSpec,
        workflow_fingerprint: str,
        cache_entry_ref: ArtifactRef | None,
    ) -> ExperimentState:
        if self._checkpoint_hook is None:
            return state
        result = self._checkpoint_hook.on_node_complete(
            state=state, alias=alias, node_id=node_id,
            completed_nodes=completed_nodes,
            workflow_id=workflow.workflow_id,
            workflow_fingerprint=workflow_fingerprint,
            cache_entry_ref=cache_entry_ref,
        )
        if result is not None:
            state = state.model_copy(
                update={"last_checkpoint_ref": result.checkpoint_ref},
            )
            if self._ctx.audit is not None:
                self._ctx.audit.append(
                    run_id=state.run_id, actor="engine",
                    action="CHECKPOINT_CREATED",
                    artifact_refs=[result.checkpoint_ref],
                    metadata={
                        "sequence_number": result.sequence_number,
                        "alias": alias,
                    },
                )
            if self._provenance_dag is not None:
                try:
                    self._provenance_dag.record_checkpoint(
                        alias=alias,
                        checkpoint_ref=result.checkpoint_ref,
                        sequence_number=result.sequence_number,
                    )
                except Exception:  # noqa: BLE001
                    _module_logger.debug("Checkpoint provenance recording failed for %s", alias)
        return state

    def _persist_workflow_spec(self, workflow: WorkflowSpec) -> ArtifactRef:
        return self._ctx.store.put_json(
            workflow.model_dump(),
            PutOptions(
                kind="scientist.workflow_spec",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.engine.WorkflowSpec", version="1.0",
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
                    name="polisyos.scientist.engine.WorkflowReport", version="1.0",
                ),
            ),
        )

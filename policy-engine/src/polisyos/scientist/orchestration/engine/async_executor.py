"""Async workflow executor with parallel DAG tier execution.

Uses :func:`topo_sort_tiers` to group nodes into topological levels, then
executes each tier in parallel via ``asyncio.TaskGroup`` +
``asyncio.to_thread`` (nodes remain sync — no need to rewrite 35+ nodes).

Feature-flagged via ``POLISYOS_ASYNC_EXECUTOR=1`` and opt-in through
``run_selected_workflow``.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from polisyos.common.async_tools import run_blocking_async
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.orchestration.engine.budget import BudgetExhaustedError
from polisyos.scientist.orchestration.engine.checkpoint import compute_workflow_fingerprint
from polisyos.scientist.orchestration.engine.condition import (
    ConditionSyntaxError,
    evaluate_condition,
)
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.errors import (
    NodeTimeoutError,
    RetryExhaustedError,
    WorkflowTimeoutError,
)
from polisyos.scientist.orchestration.engine.executor import (
    _EXECUTOR_DEGRADED_ERRORS,
    NodeBindError,
    NodeRunRecord,
    WorkflowExecutionResult,
    WorkflowReport,
    _log_node_events,
    _merge_cached_outcome_state,
    _outcome_skip_reason,
    _should_cache,
    _skip_blocker_for_engine_skip,
    _skip_blocker_for_outcome,
    _validate_aliases,
    _validate_dependencies,
    _validate_required_binds,
    bind_node_params,
)
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeError, NodeEvent, NodeOutcome
from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_async
from polisyos.scientist.orchestration.engine.state_branching import branch_state, snapshot_state
from polisyos.scientist.orchestration.engine.state_merge import (
    MergeConflict,
    MergeConflictPolicy,
    merge_parallel_outcomes,
)
from polisyos.scientist.orchestration.engine.telemetry import set_span_attribute
from polisyos.scientist.orchestration.engine.topo import topo_sort_tiers
from polisyos.scientist.orchestration.engine.trace_attributes import (
    build_node_span_attributes,
    enrich_node_span_result,
)

if TYPE_CHECKING:
    from polisyos.scientist.evidence.provenance.run_dag import RunProvenanceDAG
    from polisyos.scientist.orchestration.engine.checkpoint import (
        AsyncCheckpointHook,
        CheckpointHook,
    )
    from polisyos.scientist.orchestration.engine.compensation import RollbackCompensationHook
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_module_logger = get_logger(__name__)


def _executor_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return emit_degraded_path(
        component="engine.async_executor",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=_module_logger,
    )


class AsyncWorkflowExecutor:
    """Async workflow executor with parallel DAG branches."""

    def __init__(
        self,
        ctx: ExecutionContext,
        registry: NodeRegistry,
        *,
        checkpoint_hook: CheckpointHook | AsyncCheckpointHook | None = None,
        checkpoint_cache_seed_refs: list[ArtifactRef] | None = None,
        max_parallelism: int = 4,
        provenance_dag: RunProvenanceDAG | None = None,
        semaphore_timeout_s: float | None = None,
        workflow_timeout_s: float | None = None,
        budget_middleware: Any | None = None,
        merge_conflict_policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
        compensation_hook: RollbackCompensationHook | None = None,
    ) -> None:
        self._ctx = ctx
        self._async_store = ensure_async_artifact_store(ctx.store)
        self._registry = registry
        self._cache: NodeResultCache | None = None
        self._checkpoint_hook = checkpoint_hook
        self._checkpoint_cache_seed_refs = list(checkpoint_cache_seed_refs or [])
        self._max_parallelism = max(1, max_parallelism)
        self._provenance_dag = provenance_dag
        self._semaphore_timeout_s = semaphore_timeout_s
        self._workflow_timeout_s = workflow_timeout_s
        self._budget_middleware = budget_middleware
        self._merge_conflict_policy = merge_conflict_policy
        self._compensation_hook = compensation_hook
        self._node_outputs: dict[str, list[ArtifactRef]] = {}
        self._pre_node_state_keys: dict[str, set[str]] = {}

    async def execute(
        self,
        workflow: WorkflowSpec,
        state: ExperimentState,
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
                run_id=state.run_id,
                workflow_id=workflow.workflow_id,
                state="running",
            )

        initial_state = snapshot_state(state)
        workflow_ref = await self._persist_workflow_spec(workflow)
        self._ctx.run.add_input(workflow_ref)
        state_input_ref = await self._persist_state(initial_state)
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
                        records.append(
                            NodeRunRecord(
                                alias=alias,
                                node_id=str(invocations[alias].node_id),
                                status="skip",
                                duration_ms=0,
                                skip_reason="upstream_failed",
                                skip_blocker=_skip_blocker_for_engine_skip(
                                    alias=alias,
                                    node_id=str(invocations[alias].node_id),
                                    skip_reason="upstream_failed",
                                    missing_input="upstream_dependency",
                                    phase="dependency_resolution",
                                ),
                            )
                        )
                        blocked.add(alias)
                    continue

                runnable: list[str] = []
                for alias in tier:
                    inv = invocations[alias]
                    if any(dep in failed or dep in blocked for dep in inv.depends_on):
                        records.append(
                            NodeRunRecord(
                                alias=alias,
                                node_id=str(inv.node_id),
                                status="skip",
                                duration_ms=0,
                                skip_reason="upstream_failed",
                                skip_blocker=_skip_blocker_for_engine_skip(
                                    alias=alias,
                                    node_id=str(inv.node_id),
                                    skip_reason="upstream_failed",
                                    missing_input="upstream_dependency",
                                    phase="dependency_resolution",
                                ),
                            )
                        )
                        blocked.add(alias)
                        self._ctx.run.emit(
                            f"scientist.node.{alias}",
                            "NODE_SKIP",
                            metrics={"duration_ms": 0, "status_ok": 0},
                        )
                        continue

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
                                records.append(
                                    NodeRunRecord(
                                        alias=alias,
                                        node_id=str(inv.node_id),
                                        status="fail",
                                        duration_ms=0,
                                        error=NodeError(
                                            code="node.condition_false",
                                            message=f"Condition not met: {inv.condition.expr}",
                                            details={
                                                "expr": inv.condition.expr,
                                                "on_false": "fail",
                                            },
                                        ),
                                    )
                                )
                                failed.add(alias)
                                self._ctx.run.emit(
                                    f"scientist.node.{alias}",
                                    "NODE_FAIL",
                                    metrics={"duration_ms": 0, "status_ok": 0},
                                )
                            else:
                                records.append(
                                    NodeRunRecord(
                                        alias=alias,
                                        node_id=str(inv.node_id),
                                        status="skip",
                                        duration_ms=0,
                                        skip_reason="condition_false",
                                        skip_blocker=_skip_blocker_for_engine_skip(
                                            alias=alias,
                                            node_id=str(inv.node_id),
                                            skip_reason="condition_false",
                                            missing_input=inv.condition.expr,
                                            phase="condition_evaluation",
                                        ),
                                    )
                                )
                                condition_skipped.add(alias)
                                self._ctx.run.emit(
                                    f"scientist.node.{alias}",
                                    "NODE_SKIP",
                                    metrics={"duration_ms": 0, "status_ok": 0},
                                )
                            continue

                    runnable.append(alias)

                if failed and workflow.error_policy == "fail_fast":
                    abort = True

                if not runnable or abort:
                    continue

                # Tier savepoint for rollback on failure
                tier_savepoint = snapshot_state(state)
                tier_started = time.perf_counter()

                if len(runnable) == 1:
                    alias = runnable[0]
                    record, state, node_failed = await self._run_single_node(
                        alias,
                        invocations[alias],
                        state,
                        workflow,
                        workflow_fingerprint,
                        completed_nodes,
                        tier_index=tier_index,
                    )
                    records.append(record)
                    if node_failed:
                        failed.add(alias)
                        if workflow.error_policy == "fail_fast":
                            state = tier_savepoint
                            self._emit_rollback_compensation(
                                workflow_id=workflow.workflow_id,
                                run_id=state.run_id,
                                tier_index=tier_index,
                                failed_aliases=(alias,),
                                completed_before_tier=tuple(completed_nodes),
                                restored_state=state,
                                reason="single_node_fail_fast",
                            )
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
                        runnable,
                        invocations,
                        state,
                        workflow,
                        workflow_fingerprint,
                        completed_nodes,
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
                        self._emit_rollback_compensation(
                            workflow_id=workflow.workflow_id,
                            run_id=state.run_id,
                            tier_index=tier_index,
                            failed_aliases=tuple(sorted(tier_failed)),
                            completed_before_tier=tuple(completed_nodes),
                            restored_state=state,
                            reason="parallel_tier_fail_fast",
                        )
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
                    _execute_tiers(),
                    timeout=self._workflow_timeout_s,
                )
            except TimeoutError as exc:
                raise WorkflowTimeoutError(
                    f"Workflow {workflow.workflow_id} exceeded "
                    f"timeout of {self._workflow_timeout_s}s",
                ) from exc
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
                run_id=state.run_id,
                workflow_id=workflow.workflow_id,
                state=overall_status,
            )

        report = WorkflowReport(
            workflow_id=workflow.workflow_id,
            run_id=state.run_id,
            error_policy=workflow.error_policy,
            status=overall_status,
            nodes=records,
        )
        report_ref = await self._persist_report(report)
        final_state = branch_state(
            state,
            write_paths=("reports_index.workflow_report",),
        ).state
        final_state.reports_index["workflow_report"] = report_ref
        final_state_ref = await self._persist_state(final_state)

        self._ctx.run.add_output(final_state_ref)
        self._ctx.run.add_output(report_ref)

        # Finalize and persist provenance DAG
        if self._provenance_dag is not None:
            try:
                self._provenance_dag.finalize()
                prov_json = self._provenance_dag.to_prov_json()
                prov_ref = await self._async_store.put_json(
                    prov_json,
                    ArtifactWriteOptions(
                        kind="scientist.provenance.run_dag",
                        media_type="application/json",
                    ),
                )
                self._ctx.run.add_output(prov_ref)
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                _executor_degraded(
                    operation="finalize_provenance_dag",
                    reason="provenance_finalize_failed",
                    exc=exc,
                    details={"workflow_id": workflow.workflow_id, "run_id": state.run_id},
                )

        errors_payload = [
            {"node": r.alias, "code": r.error.code, "message": r.error.message}
            for r in records
            if r.status == "fail" and r.error is not None
        ]
        run_ref = self._ctx.run.finalize(
            status=overall_status,
            errors=errors_payload or None,
        )

        return WorkflowExecutionResult(state=final_state, report=report, run_ref=run_ref)

    def _emit_rollback_compensation(
        self,
        *,
        workflow_id: str,
        run_id: str,
        tier_index: int,
        failed_aliases: tuple[str, ...],
        completed_before_tier: tuple[str, ...],
        restored_state: ExperimentState,
        reason: str,
    ) -> None:
        if self._compensation_hook is None:
            return
        from polisyos.scientist.orchestration.engine.compensation import RollbackCompensationEvent

        try:
            self._compensation_hook.on_tier_rollback(
                event=RollbackCompensationEvent(
                    run_id=run_id,
                    workflow_id=workflow_id,
                    tier_index=tier_index,
                    failed_aliases=failed_aliases,
                    completed_before_tier=completed_before_tier,
                    reason=reason,
                ),
                restored_state=restored_state,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            _executor_degraded(
                operation="rollback_compensation",
                reason="rollback_compensation_hook_failed",
                exc=exc,
                details={
                    "workflow_id": workflow_id,
                    "run_id": run_id,
                    "tier_index": tier_index,
                    "reason": reason,
                },
            )

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
        outcome, duration_ms, _cache_hit, cache_entry_ref = await self._execute_node(
            alias,
            inv,
            state,
            workflow,
            tier_index=tier_index,
        )
        if outcome.status == "ok":
            state = outcome.state
        node_failed = outcome.status == "fail"

        if outcome.status == "ok" and self._checkpoint_hook is not None:
            state = await self._handle_checkpoint(
                state,
                alias,
                str(inv.node_id),
                [*completed_nodes, alias],
                workflow,
                workflow_fingerprint,
                cache_entry_ref=cache_entry_ref,
            )

        record = NodeRunRecord(
            alias=alias,
            node_id=str(inv.node_id),
            status=outcome.status,
            duration_ms=duration_ms,
            artifacts=list(outcome.artifacts),
            error=outcome.error,
            skip_reason=_outcome_skip_reason(outcome) if outcome.status == "skip" else None,
            skip_blocker=_skip_blocker_for_outcome(
                alias=alias,
                node_id=str(inv.node_id),
                outcome=outcome,
            ),
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
        results: dict[str, tuple[NodeOutcome, int, bool, ArtifactRef | None]] = {}
        cancel_event = asyncio.Event()

        async def _run_with_sem(alias: str) -> None:
            # Check cancellation before acquiring semaphore
            if cancel_event.is_set():
                results[alias] = (
                    NodeOutcome(
                        status="skip",
                        state=state,
                        events=[
                            NodeEvent(
                                level="info",
                                message="Cancelled by fail_fast",
                                code="node.cancelled",
                                attrs={},
                            )
                        ],
                    ),
                    0,
                    False,
                    None,
                )
                return

            # Semaphore with optional timeout
            sem_wait_start = time.perf_counter()
            if self._semaphore_timeout_s is not None:
                try:
                    await asyncio.wait_for(
                        semaphore.acquire(),
                        timeout=self._semaphore_timeout_s,
                    )
                except TimeoutError:
                    results[alias] = (
                        NodeOutcome(
                            status="fail",
                            state=state,
                            error=NodeError(
                                code="node.semaphore_timeout",
                                message=f"Node {alias} timed out waiting for execution slot",
                                details={"timeout_s": self._semaphore_timeout_s},
                            ),
                        ),
                        0,
                        False,
                        None,
                    )
                    return
            else:
                await semaphore.acquire()
            sem_wait_s = time.perf_counter() - sem_wait_start
            if self._ctx.metrics is not None and sem_wait_s > 0.001:
                self._ctx.metrics.record_semaphore_wait(
                    tier_index=tier_index,
                    wait_seconds=sem_wait_s,
                    workflow_id=workflow.workflow_id,
                )

            try:
                outcome, duration_ms, cache_hit, cache_entry_ref = await self._execute_node(
                    alias,
                    invocations[alias],
                    state,
                    workflow,
                    tier_index=tier_index,
                )
                results[alias] = (outcome, duration_ms, cache_hit, cache_entry_ref)
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
        cache_entry_refs: dict[str, ArtifactRef] = {}
        write_specs: dict[str, list[str]] = {}
        records: list[NodeRunRecord] = []
        tier_failed: set[str] = set()

        for alias in aliases:
            outcome, duration_ms, _cache_hit, cache_entry_ref = results[alias]
            records.append(
                NodeRunRecord(
                    alias=alias,
                    node_id=str(invocations[alias].node_id),
                    status=outcome.status,
                    duration_ms=duration_ms,
                    artifacts=list(outcome.artifacts),
                    error=outcome.error,
                    skip_reason=_outcome_skip_reason(outcome) if outcome.status == "skip" else None,
                    skip_blocker=_skip_blocker_for_outcome(
                        alias=alias,
                        node_id=str(invocations[alias].node_id),
                        outcome=outcome,
                    ),
                )
            )
            if outcome.status == "ok":
                ok_outcomes[alias] = outcome
                if cache_entry_ref is not None:
                    cache_entry_refs[alias] = cache_entry_ref
                node = self._registry.get(invocations[alias].node_id)
                write_specs[alias] = list(node.spec.state_writes)
            elif outcome.status == "fail":
                tier_failed.add(alias)

        if ok_outcomes:
            merge_result = merge_parallel_outcomes(
                state,
                ok_outcomes,
                write_specs,
                conflict_policy=self._merge_conflict_policy,
            )
            if merge_result.conflicts:
                conflict_ref = await self._persist_parallel_merge_conflict(
                    workflow_id=workflow.workflow_id,
                    tier_index=tier_index,
                    conflicts=merge_result.conflict_details,
                    aliases=aliases,
                )
                conflict_details: dict[str, Any] = {
                    "tier_index": tier_index,
                    "conflict_paths": [conflict.path for conflict in merge_result.conflict_details],
                    "conflict_policy": self._merge_conflict_policy.value,
                }
                if conflict_ref is not None:
                    conflict_details["merge_conflict_ref"] = str(conflict_ref.artifact_id)
                for record in records:
                    if record.status != "ok":
                        continue
                    record.status = "fail"
                    record.error = NodeError(
                        code="node.parallel_merge_conflict",
                        message="Parallel tier produced conflicting state writes",
                        details=conflict_details,
                    )
                    if conflict_ref is not None:
                        record.artifacts.append(conflict_ref)
                    tier_failed.add(record.alias)
                return records, state, tier_failed

            state = merge_result.state
            if merge_result.resolved_conflicts:
                self._ctx.logger.warning(
                    "Parallel merge resolved by policy=%s: %s",
                    self._merge_conflict_policy.value,
                    [str(conflict) for conflict in merge_result.resolved_conflicts],
                )
            if self._checkpoint_hook is not None:
                checkpoint_completed = list(completed_nodes)
                for alias in aliases:
                    if alias not in ok_outcomes:
                        continue
                    checkpoint_completed.append(alias)
                    state = await self._handle_checkpoint(
                        state,
                        alias,
                        str(invocations[alias].node_id),
                        checkpoint_completed,
                        workflow,
                        workflow_fingerprint,
                        cache_entry_ref=cache_entry_refs.get(alias),
                    )

        return records, state, tier_failed

    async def _execute_node(
        self,
        alias: str,
        inv: NodeInvocation,
        state: ExperimentState,
        workflow: WorkflowSpec,
        tier_index: int = 0,
    ) -> tuple[NodeOutcome, int, bool, ArtifactRef | None]:
        """Execute a single node with cache, retry, timeout, metrics."""
        try:
            node = bind_node_params(self._registry.get(inv.node_id), inv.params)
        except NodeBindError as exc:
            self._ctx.logger.exception("Node %s bind failed", alias)
            return (
                NodeOutcome(
                    status="fail",
                    state=state,
                    error=NodeError(
                        code="node.bind_failed",
                        message=str(exc),
                        details={
                            "node": exc.node_label,
                            "param_keys": list(exc.param_keys),
                            "type": exc.error_type,
                        },
                    ),
                ),
                0,
                False,
                None,
            )
        branch = branch_state(
            state,
            write_paths=getattr(node.spec, "state_writes", ()),
        )
        node_state = branch.state
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
                run_id=state.run_id,
                actor="engine",
                action="NODE_STARTED",
                metadata={"alias": alias, "node_id": node_id},
            )
        if self._ctx.metrics is not None:
            self._ctx.metrics.record_node_started(
                alias=alias,
                node_id=node_id,
                workflow_id=workflow.workflow_id,
            )

        started = time.perf_counter()
        cache_hit = False
        cache_entry_ref: ArtifactRef | None = None

        # Cache check
        cache_key: str | None = None
        if _should_cache(node_id):
            try:
                cache_key = compute_idempotency_key(
                    spec=node.spec,
                    state=state,
                    bind_params=inv.params,
                )
            except (AttributeError, TypeError, ValueError) as exc:
                _executor_degraded(
                    operation="compute_cache_key",
                    reason="cache_bypass",
                    exc=exc,
                    details={"alias": alias, "node_id": node_id},
                )

        # Budget pre-check
        if self._budget_middleware is not None:
            try:
                self._budget_middleware.pre_check(alias)
                new_alerts = self._budget_middleware.check_thresholds()
                for level in new_alerts:
                    self._ctx.run.emit(
                        "scientist.budget",
                        "BUDGET_ALERT",
                        metrics={"threshold_pct": level},
                    )
            except BudgetExhaustedError as budget_exc:
                duration_ms = int((time.perf_counter() - started) * 1000)
                return (
                    NodeOutcome(
                        status="fail",
                        state=state,
                        error=NodeError(
                            code="node.budget_exhausted",
                            message=str(budget_exc),
                            details={},
                        ),
                    ),
                    duration_ms,
                    False,
                    None,
                )

        cached_outcome: NodeOutcome | None = None
        retry_stats: dict[str, int] = {}
        if cache_key and self._cache:
            cached_outcome = self._cache.get(cache_key)
            if cached_outcome:
                cache_hit = True

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
            try:
                raw_outcome = await execute_with_retry_async(
                    node,
                    self._ctx,
                    node_state,
                    retry_policy=retry_policy,
                    timeout_s=inv.timeout_s,
                    alias=alias,
                    retry_stats=retry_stats,
                )
                outcome = NodeOutcome.model_validate(raw_outcome)
            except NodeTimeoutError as exc:
                self._ctx.logger.error("Node %s timed out", alias)
                outcome = NodeOutcome(
                    status="fail",
                    state=node_state,
                    error=NodeError(
                        code="node.timeout", message=str(exc), details={"timeout_s": inv.timeout_s}
                    ),
                )
            except RetryExhaustedError as exc:
                self._ctx.logger.error("Node %s exhausted retries", alias)
                outcome = NodeOutcome(
                    status="fail",
                    state=node_state,
                    error=NodeError(
                        code="node.retry_exhausted",
                        message=str(exc),
                        details={"max_retries": retry_policy.max_retries},
                    ),
                )
            except ValidationError as exc:
                outcome = NodeOutcome(
                    status="fail",
                    state=node_state,
                    error=NodeError(
                        code="node.invalid_outcome",
                        message="Node returned invalid outcome",
                        details={"error": str(exc)},
                    ),
                )
            except _EXECUTOR_DEGRADED_ERRORS as exc:
                self._ctx.logger.exception("Node %s failed", alias)
                outcome = NodeOutcome(
                    status="fail",
                    state=node_state,
                    error=NodeError(
                        code="node.exception",
                        message=str(exc),
                        details={"type": exc.__class__.__name__},
                    ),
                )

            # Cache store
            if outcome.status == "ok" and cache_key and self._cache:
                try:
                    cache_entry_ref = self._cache.put(
                        cache_key,
                        node_id=node_id,
                        outcome=outcome,
                    )
                except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
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
                                "error_type": str(envelope.get("error_type", "runtime_error")),
                            },
                        )
                    )

        duration_ms = int((time.perf_counter() - started) * 1000)

        # Enrich span with post-execution attributes
        enrich_node_span_result(
            span_attrs,
            status=outcome.status,
            duration_ms=duration_ms,
            cache_hit=cache_hit,
        )
        for key, value in span_attrs.items():
            set_span_attribute(None, key, value)  # best-effort; span from tracer

        # Record provenance
        if self._provenance_dag is not None:
            try:
                ended_at = datetime.now(UTC)
                started_at = datetime.fromtimestamp(
                    ended_at.timestamp() - duration_ms / 1000,
                    tz=UTC,
                )
                if outcome.status == "ok":
                    # Collect input refs from upstream dependencies
                    input_refs: list[Any] = []
                    for dep in inv.depends_on or []:
                        input_refs.extend(self._node_outputs.get(dep, []))
                    self._provenance_dag.record_node_execution(
                        alias=alias,
                        node_id=node_id,
                        started_at=started_at,
                        ended_at=ended_at,
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
                        k
                        for k in pre_keys & post_keys
                        if outcome.state.artifacts_index.get(k) != state.artifacts_index.get(k)
                    )
                    if keys_added or keys_modified:
                        self._provenance_dag.record_state_mutation(
                            alias=alias,
                            keys_added=keys_added or None,
                            keys_modified=keys_modified or None,
                        )
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
                        started_at=started_at,
                        ended_at=ended_at,
                    )
            except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
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
                            "reason": str(envelope.get("reason", "provenance_record_failed")),
                            "error_type": str(envelope.get("error_type", "runtime_error")),
                        },
                    )
                )

        _log_node_events(self._ctx.logger, alias, outcome.events)
        status_event = {"ok": "NODE_OK", "skip": "NODE_SKIP", "fail": "NODE_FAIL"}[outcome.status]
        self._ctx.run.emit(
            f"scientist.node.{alias}",
            status_event,
            outputs=outcome.artifacts,
            metrics={"duration_ms": duration_ms, "status_ok": 1 if outcome.status == "ok" else 0},
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
                },
            )

        if self._ctx.metrics is not None:
            actual_retry_count = max(0, retry_stats.get("attempts", 1) - 1)
            self._ctx.metrics.record_node_completed(
                alias=alias,
                node_id=node_id,
                workflow_id=workflow.workflow_id,
                status=outcome.status,
                duration_ms=duration_ms,
                cache_hit=cache_hit,
                retry_count=actual_retry_count,
            )

        return outcome, duration_ms, cache_hit, cache_entry_ref

    async def _handle_checkpoint(
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
        async_checkpoint = getattr(self._checkpoint_hook, "on_node_complete_async", None)
        if callable(async_checkpoint):
            result = await async_checkpoint(
                state=state,
                alias=alias,
                node_id=node_id,
                completed_nodes=completed_nodes,
                workflow_id=workflow.workflow_id,
                workflow_fingerprint=workflow_fingerprint,
                cache_entry_ref=cache_entry_ref,
            )
        else:
            result = await run_blocking_async(
                self._checkpoint_hook.on_node_complete,
                state=state,
                alias=alias,
                node_id=node_id,
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
                    run_id=state.run_id,
                    actor="engine",
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
                except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
                    _executor_degraded(
                        operation="record_checkpoint_provenance",
                        reason="provenance_record_failed",
                        exc=exc,
                        details={"alias": alias, "node_id": node_id},
                    )
        return state

    async def _persist_parallel_merge_conflict(
        self,
        *,
        workflow_id: str,
        tier_index: int,
        conflicts: list[MergeConflict],
        aliases: list[str],
    ) -> ArtifactRef | None:
        if not conflicts:
            return None
        payload = {
            "workflow_id": workflow_id,
            "tier_index": tier_index,
            "merge_conflict_policy": self._merge_conflict_policy.value,
            "aliases": sorted(aliases),
            "conflicts": [conflict.to_dict() for conflict in conflicts],
        }
        try:
            return await self._async_store.put_json(
                payload,
                ArtifactWriteOptions(
                    kind="scientist.parallel_merge_conflict",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.scientist.orchestration.engine.ParallelMergeConflict",
                        version="1.0",
                    ),
                ),
            )
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            _executor_degraded(
                operation="persist_parallel_merge_conflict",
                reason="artifact_persist_failed",
                exc=exc,
                details={
                    "workflow_id": workflow_id,
                    "tier_index": tier_index,
                    "conflict_count": len(conflicts),
                },
            )
            return None

    async def _persist_workflow_spec(self, workflow: WorkflowSpec) -> ArtifactRef:
        return await self._async_store.put_json(
            workflow.model_dump(),
            ArtifactWriteOptions(
                kind="scientist.workflow_spec",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.WorkflowSpec",
                    version="1.0",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

    async def _persist_state(self, state: ExperimentState) -> ArtifactRef:
        return await self._async_store.put_json(
            state.model_dump(),
            ArtifactWriteOptions(
                kind="scientist.experiment_state",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.ExperimentState",
                    version=state.schema_version,
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

    async def _persist_report(self, report: WorkflowReport) -> ArtifactRef:
        return await self._async_store.put_json(
            report.model_dump(),
            ArtifactWriteOptions(
                kind="scientist.workflow_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.WorkflowReport",
                    version="1.0",
                ),
            ),
        )

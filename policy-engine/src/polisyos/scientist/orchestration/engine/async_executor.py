"""Async workflow executor with parallel DAG tier execution.

Uses :func:`topo_sort_tiers` to group nodes into topological levels, then
executes each tier in parallel via ``asyncio.TaskGroup`` +
``asyncio.to_thread`` (nodes remain sync — no need to rewrite 35+ nodes).

Feature-flagged via ``POLISYOS_ASYNC_EXECUTOR=1`` and opt-in through
``run_selected_workflow``.
"""

from __future__ import annotations

import asyncio
import threading
import time
from copy import deepcopy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from polisyos.common.async_tools import run_blocking_async
from polisyos.common.logger import get_logger
from polisyos.core.artifacts.async_store import ensure_async_artifact_store
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ArtifactTenantContextInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.scientist.orchestration.engine.budget import BudgetExhaustedError
from polisyos.scientist.orchestration.engine.checkpoint import (
    CheckpointError,
    compute_workflow_fingerprint,
)
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
    _CACHE_BYPASS_REPLAY_INCOMPATIBLE,
    _EXECUTOR_DEGRADED_ERRORS,
    NodeBindError,
    NodeRunRecord,
    WorkflowExecutionResult,
    WorkflowExecutionStatus,
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
from polisyos.scientist.orchestration.engine.protocol import (
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
)
from polisyos.scientist.orchestration.engine.retry import RetryPolicy, execute_with_retry_async
from polisyos.scientist.orchestration.engine.state_branching import (
    StateMutation,
    StateMutationJournal,
    branch_state,
    mutation_journal_for_state,
    mutation_journal_from_operations,
    snapshot_state,
)
from polisyos.scientist.orchestration.engine.state_merge import (
    MergeConflict,
    MergeConflictPolicy,
    StateReplayIncompatible,
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
_READINESS_MISSING = object()


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
        self._cache_seed_owner: object | None = None
        self._checkpoint_hook = checkpoint_hook
        self._checkpoint_cache_seed_refs = list(checkpoint_cache_seed_refs or [])
        self._max_parallelism = max(1, max_parallelism)
        self._provenance_dag = provenance_dag
        self._semaphore_timeout_s = semaphore_timeout_s
        self._workflow_timeout_s = workflow_timeout_s
        self._workflow_deadline: float | None = None
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
        self._require_atomic_tier_checkpoint(tiers)
        seed_owner = object()
        self._cache_seed_owner = seed_owner
        self._cache = None
        workflow_started = time.perf_counter()
        self._workflow_deadline = (
            workflow_started + self._workflow_timeout_s
            if self._workflow_timeout_s is not None
            else None
        )

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

        try:
            cache, restored, restored_cp = await self._recover_cache(
                run_id=state.run_id, deadline_monotonic=self._workflow_deadline
            )
            NodeResultCache._check_deadline(self._workflow_deadline)
        except TimeoutError as exc:
            raise WorkflowTimeoutError(
                f"Workflow {workflow.workflow_id} exceeded timeout during cache recovery"
            ) from exc
        # The worker owns its cache until this uncancelled await accepts it.
        # Cancellation cannot stop already-entered backend I/O; that worker's
        # eventual private index must never become the current executor cache.
        if self._cache_seed_owner is not seed_owner:
            raise asyncio.CancelledError("cache recovery superseded")
        self._cache = cache
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
                    elif record.status == "ok":
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

                    (
                        tier_records,
                        state,
                        tier_failed,
                        tier_cache_entry_refs,
                    ) = await self._run_parallel_tier(
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
                    tier_completed = [rec.alias for rec in tier_records if rec.status == "ok"]
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
                    elif tier_completed:
                        completed_nodes.extend(tier_completed)
                        checkpoint_alias = tier_completed[-1]
                        state = await self._handle_tier_checkpoint(
                            state,
                            aliases=tier_completed,
                            alias=checkpoint_alias,
                            node_id=str(invocations[checkpoint_alias].node_id),
                            completed_nodes=completed_nodes,
                            workflow=workflow,
                            workflow_fingerprint=workflow_fingerprint,
                            cache_entry_refs_by_alias=tier_cache_entry_refs,
                        )

                tier_duration_ms = int((time.perf_counter() - tier_started) * 1000)
                if self._ctx.metrics is not None:
                    self._ctx.metrics.record_tier_completed(
                        tier_index=tier_index,
                        tier_size=len(runnable),
                        duration_ms=tier_duration_ms,
                        workflow_id=workflow.workflow_id,
                    )

        async def _execute_readiness() -> None:
            """Run the bounded, explicit-dependency readiness schedule.

            This path is intentionally narrower than the tier executor.  It
            is selected only for continuation workflows without checkpoint or
            provenance hooks, and only after declared unordered state access
            has been proven disjoint.  Every successful completion is merged
            before its successors are admitted, so a successor observes the
            committed state of its explicit predecessors.
            """
            nonlocal state
            order = list(invocations)
            pending = set(order)
            settled: set[str] = set()
            running: dict[
                str,
                asyncio.Task[tuple[NodeOutcome, int, bool, ArtifactRef | None]],
            ] = {}
            launch_baselines: dict[str, ExperimentState] = {}
            records_by_alias: dict[str, NodeRunRecord] = {}
            tier_by_alias = {
                alias: tier_index for tier_index, tier in enumerate(tiers) for alias in tier
            }
            tier_members = {tier_index: set(tier) for tier_index, tier in enumerate(tiers)}
            tier_started_at: dict[int, float] = {}
            tier_finished_at: dict[int, float] = {}

            def _skip_record(alias: str) -> NodeRunRecord:
                invocation = invocations[alias]
                return NodeRunRecord(
                    alias=alias,
                    node_id=str(invocation.node_id),
                    status="skip",
                    duration_ms=0,
                    skip_reason="upstream_failed",
                    skip_blocker=_skip_blocker_for_engine_skip(
                        alias=alias,
                        node_id=str(invocation.node_id),
                        skip_reason="upstream_failed",
                        missing_input="upstream_dependency",
                        phase="dependency_resolution",
                    ),
                )

            try:
                while pending or running:
                    progressed = False

                    # Resolve known failed branches before admitting any new
                    # work.  A skipped node remains a settled dependency, as
                    # in the existing tier executor; only failures block its
                    # descendants.
                    for alias in order:
                        if alias not in pending:
                            continue
                        if any(
                            dep in failed or dep in blocked for dep in invocations[alias].depends_on
                        ):
                            pending.remove(alias)
                            blocked.add(alias)
                            settled.add(alias)
                            records_by_alias[alias] = _skip_record(alias)
                            self._ctx.run.emit(
                                f"scientist.node.{alias}",
                                "NODE_SKIP",
                                metrics={"duration_ms": 0, "status_ok": 0},
                            )
                            progressed = True

                    ready = [
                        alias
                        for alias in order
                        if alias in pending
                        and all(dep in settled for dep in invocations[alias].depends_on)
                        and not any(
                            dep in failed or dep in blocked for dep in invocations[alias].depends_on
                        )
                    ]
                    for alias in ready:
                        if len(running) >= self._max_parallelism:
                            break
                        pending.remove(alias)
                        tier_index = tier_by_alias[alias]
                        tier_started_at.setdefault(tier_index, time.perf_counter())
                        launch_baseline, execution_input = self._readiness_launch_pair(state)
                        launch_baselines[alias] = launch_baseline
                        running[alias] = asyncio.create_task(
                            self._execute_node(
                                alias,
                                invocations[alias],
                                execution_input,
                                workflow,
                                tier_index=tier_index,
                            )
                        )
                        progressed = True

                    if running:
                        done, _ = await asyncio.wait(
                            tuple(running.values()),
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        for alias in order:
                            task = running.get(alias)
                            if task is None or task not in done:
                                continue
                            del running[alias]
                            launch_baseline = launch_baselines.pop(alias, None)
                            outcome, duration_ms, _cache_hit, _cache_entry_ref = task.result()
                            record = NodeRunRecord(
                                alias=alias,
                                node_id=str(invocations[alias].node_id),
                                status=outcome.status,
                                duration_ms=duration_ms,
                                artifacts=list(outcome.artifacts),
                                error=outcome.error,
                                skip_reason=(
                                    _outcome_skip_reason(outcome)
                                    if outcome.status == "skip"
                                    else None
                                ),
                                skip_blocker=_skip_blocker_for_outcome(
                                    alias=alias,
                                    node_id=str(invocations[alias].node_id),
                                    outcome=outcome,
                                ),
                            )
                            records_by_alias[alias] = record

                            if outcome.status == "ok":
                                node = self._registry.get(invocations[alias].node_id)
                                write_specs = list(node.spec.state_writes)
                                try:
                                    merge_outcome, merge_journal = self._prepare_readiness_outcome(
                                        outcome,
                                        launch_baseline,
                                        write_specs,
                                    )
                                except StateReplayIncompatible as exc:
                                    record.status = "fail"
                                    record.error = NodeError(
                                        code="node.readiness_state_write",
                                        message=(
                                            "Readiness completion changed state outside "
                                            "its declared write paths"
                                        ),
                                        details={
                                            "path": exc.path,
                                            "reason": exc.reason,
                                        },
                                    )
                                    failed.add(alias)
                                else:
                                    merge_result = merge_parallel_outcomes(
                                        state,
                                        {alias: merge_outcome},
                                        {alias: write_specs},
                                        conflict_policy=self._merge_conflict_policy,
                                        mutation_journals={alias: merge_journal},
                                    )
                                    if merge_result.conflicts:
                                        conflict_ref = await self._persist_parallel_merge_conflict(
                                            workflow_id=workflow.workflow_id,
                                            tier_index=tier_by_alias[alias],
                                            conflicts=merge_result.conflict_details,
                                            aliases=[alias],
                                        )
                                        record.status = "fail"
                                        record.error = NodeError(
                                            code="node.readiness_merge_conflict",
                                            message=(
                                                "Readiness completion produced a conflicting "
                                                "state write"
                                            ),
                                            details={
                                                "tier_index": tier_by_alias[alias],
                                                "conflict_paths": [
                                                    conflict.path
                                                    for conflict in merge_result.conflict_details
                                                ],
                                                "conflict_policy": self._merge_conflict_policy.value,
                                            },
                                        )
                                        if conflict_ref is not None:
                                            record.artifacts.append(conflict_ref)
                                        failed.add(alias)
                                    else:
                                        state = merge_result.state
                                        settled.add(alias)
                                        completed_nodes.append(alias)
                            elif outcome.status == "fail":
                                failed.add(alias)
                            else:
                                settled.add(alias)
                                condition_skipped.add(alias)
                            progressed = True

                    if not running and pending and not progressed:
                        # topo_sort_tiers already rejects cycles.  Reaching
                        # this branch means a future dependency state was not
                        # represented by the explicit graph, so fail closed.
                        raise RuntimeError("Readiness scheduler made no progress")

                terminal = settled | failed | blocked
                for tier_index, members in tier_members.items():
                    if not members or not members.issubset(terminal):
                        continue
                    started_at = tier_started_at.get(tier_index)
                    if started_at is None:
                        continue
                    tier_finished_at[tier_index] = time.perf_counter()
                if self._ctx.metrics is not None:
                    for tier_index, members in tier_members.items():
                        started_at = tier_started_at.get(tier_index)
                        finished_at = tier_finished_at.get(tier_index)
                        if started_at is None or finished_at is None:
                            continue
                        self._ctx.metrics.record_tier_completed(
                            tier_index=tier_index,
                            tier_size=len(members),
                            duration_ms=int((finished_at - started_at) * 1000),
                            workflow_id=workflow.workflow_id,
                        )
            finally:
                if running:
                    tasks = tuple(running.values())
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

            records.extend(records_by_alias[alias] for alias in order if alias in records_by_alias)

        # Execute tiers with optional workflow-level timeout
        execution_body = (
            _execute_readiness
            if self._can_use_readiness_schedule(workflow, invocations)
            else _execute_tiers
        )
        if self._workflow_deadline is not None:
            try:
                remaining = self._workflow_deadline - time.perf_counter()
                if remaining <= 0:
                    raise TimeoutError("workflow deadline exceeded before execution")
                await asyncio.wait_for(execution_body(), timeout=remaining)
            except TimeoutError as exc:
                raise WorkflowTimeoutError(
                    f"Workflow {workflow.workflow_id} exceeded "
                    f"timeout of {self._workflow_timeout_s}s",
                ) from exc
        else:
            await execution_body()

        overall_status = WorkflowExecutionStatus.from_failures(bool(failed)).value
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

    def _can_use_readiness_schedule(
        self,
        workflow: WorkflowSpec,
        invocations: dict[str, NodeInvocation],
    ) -> bool:
        """Return whether the conservative readiness path is applicable.

        The existing tier loop remains the authority for workflows whose
        semantics depend on a tier-wide checkpoint, rollback, condition
        evaluation, semaphore timeout, or deterministic provenance order.  A
        readiness schedule is therefore limited to a continuation workflow
        with declared state access and no checkpoint hook.  Pairwise state
        read/write checks reject an otherwise apparently independent node when
        its outcome could depend on an unordered mutable access.
        """
        if workflow.error_policy != "continue":
            return False
        if self._checkpoint_hook is not None:
            return False
        if self._semaphore_timeout_s is not None:
            return False
        if self._provenance_dag is not None:
            return False
        if self._compensation_hook is not None:
            return False
        if any(inv.condition is not None for inv in invocations.values()):
            return False

        state_access: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {}
        for alias, inv in invocations.items():
            node = self._registry.get(inv.node_id)
            spec = getattr(node, "spec", None)
            if not isinstance(spec, NodeSpec):
                return False
            reads = getattr(spec, "state_reads", None)
            writes = getattr(spec, "state_writes", None)
            if not isinstance(reads, (list, tuple)) or not isinstance(writes, (list, tuple)):
                return False
            if any(not isinstance(path, str) or not path for path in (*reads, *writes)):
                return False
            state_access[alias] = (
                tuple(tuple(part for part in path.split(".") if part) for path in reads),
                tuple(tuple(part for part in path.split(".") if part) for path in writes),
            )

        ancestors = self._readiness_ancestors(invocations)
        aliases = list(invocations)
        for index, left_alias in enumerate(aliases):
            left_reads, left_writes = state_access[left_alias]
            for right_alias in aliases[index + 1 :]:
                # An explicit transitive dependency gives the scheduler an
                # ordering edge.  All unordered state access must be proven
                # disjoint before early release is allowed.
                if right_alias in ancestors[left_alias] or left_alias in ancestors[right_alias]:
                    continue
                right_reads, right_writes = state_access[right_alias]
                if any(
                    self._readiness_paths_overlap(left, right)
                    for left in left_writes
                    for right in right_writes
                ):
                    return False
                if any(
                    self._readiness_paths_overlap(left, right)
                    for left in left_writes
                    for right in right_reads
                ) or any(
                    self._readiness_paths_overlap(left, right)
                    for left in right_writes
                    for right in left_reads
                ):
                    return False
        return True

    @staticmethod
    def _readiness_ancestors(
        invocations: dict[str, NodeInvocation],
    ) -> dict[str, set[str]]:
        """Return the transitive explicit dependency set for each alias."""
        ancestors: dict[str, set[str]] = {alias: set() for alias in invocations}
        for alias in invocations:
            stack = list(invocations[alias].depends_on)
            while stack:
                dependency = stack.pop()
                if dependency in ancestors[alias]:
                    continue
                ancestors[alias].add(dependency)
                stack.extend(invocations[dependency].depends_on)
        return ancestors

    @staticmethod
    def _readiness_paths_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
        """Return whether two declared state paths overlap by containment."""
        shortest = min(len(left), len(right))
        return left[:shortest] == right[:shortest]

    @staticmethod
    def _readiness_launch_pair(
        state: ExperimentState,
    ) -> tuple[ExperimentState, ExperimentState]:
        """Return an immutable launch baseline and a fresh execution input."""
        launch_baseline = snapshot_state(state)
        # A blank branch journal prevents inherited completion journals from
        # becoming part of a later sibling's returned snapshot.  The real node
        # path adds its own declared-write journal before executing.
        # Start that branch from a second full snapshot: branch_state() only
        # copies mutable top-level mappings eagerly, so using ``state`` here
        # would leave nested containers shared with both the committed state
        # and launch_baseline.
        execution_input = branch_state(
            snapshot_state(state),
            write_paths=(),
        ).state
        return launch_baseline, execution_input

    @classmethod
    def _prepare_readiness_outcome(
        cls,
        outcome: NodeOutcome,
        launch_baseline: ExperimentState | None,
        write_specs: list[str],
    ) -> tuple[NodeOutcome, StateMutationJournal | None]:
        """Bind one completion to its exact declared state delta.

        Journaled production branches replay only operations under declared
        paths.  Unjournaled adapters are rebased against the immutable launch
        baseline and receive a synthetic exact-path journal.  Any remaining
        state difference is an undeclared write and fails closed.
        """
        if launch_baseline is None:
            raise StateReplayIncompatible(
                "readiness",
                "launch baseline was not retained for completion",
            )

        journal = mutation_journal_for_state(outcome.state)
        merge_journal = (
            cls._readiness_merge_journal(outcome.state, write_specs)
            if journal is not None and journal.operations
            else cls._readiness_synthetic_journal(
                launch_baseline,
                outcome.state,
                write_specs,
            )
        )
        rebased = merge_parallel_outcomes(
            launch_baseline,
            {"readiness": outcome},
            {"readiness": write_specs},
            mutation_journals={"readiness": merge_journal},
        )
        if rebased.conflicts:
            raise StateReplayIncompatible(
                "state",
                "completion produced a conflicting declared write",
            )
        # Pydantic model equality includes private attributes.  A replayed
        # branch may therefore compare unequal solely because it carries a
        # different mutation journal, even when every public state field is
        # identical.  Ownership checks must compare the semantic state only.
        if cls._readiness_public_state(rebased.state) != cls._readiness_public_state(outcome.state):
            difference = cls._readiness_first_difference(rebased.state, outcome.state)
            raise StateReplayIncompatible(
                difference or "state",
                "completion changed an undeclared state path",
            )
        return outcome.model_copy(update={"state": rebased.state}), merge_journal

    @staticmethod
    def _readiness_merge_journal(
        outcome_state: ExperimentState,
        write_specs: list[str],
    ) -> StateMutationJournal | None:
        """Return a branch journal only when every operation is declared."""
        journal = mutation_journal_for_state(outcome_state)
        if journal is None or not journal.operations:
            return None

        write_parts = [
            tuple(part for part in path.split(".") if part)
            for path in write_specs
            if isinstance(path, str) and path
        ]
        if not write_parts:
            raise StateReplayIncompatible(
                journal.operations[0].path,
                "journal operation is outside declared write paths",
            )

        owned_operations = []
        for operation in journal.operations:
            operation_parts = tuple(part for part in operation.path.split(".") if part)
            if any(
                len(write_path) <= len(operation_parts)
                and write_path == operation_parts[: len(write_path)]
                for write_path in write_parts
            ):
                owned_operations.append(operation)
        if len(owned_operations) != len(journal.operations):
            undeclared = next(
                operation for operation in journal.operations if operation not in owned_operations
            )
            raise StateReplayIncompatible(
                undeclared.path,
                "journal operation is outside declared write paths",
            )
        return mutation_journal_from_operations(owned_operations)

    @classmethod
    def _readiness_synthetic_journal(
        cls,
        baseline_state: ExperimentState,
        outcome_state: ExperimentState,
        write_specs: list[str],
    ) -> StateMutationJournal | None:
        """Build exact nested-path operations for an unjournaled result."""
        operations: list[StateMutation] = []
        for path in cls._readiness_normalize_paths(write_specs):
            # Top-level mapping writes retain the established value-delta
            # handling in state_merge; nested paths get an exact journal so a
            # stale sibling mapping is never promoted to the write root.
            if len(path) < 2:
                continue
            baseline_value = cls._readiness_get_path(baseline_state, path)
            outcome_value = cls._readiness_get_path(outcome_state, path)
            if baseline_value == outcome_value:
                continue
            if outcome_value is _READINESS_MISSING:
                if baseline_value is _READINESS_MISSING:
                    continue
                operations.append(
                    StateMutation(
                        path=".".join(path),
                        operation="delete",
                        target_presence="present",
                        target_kind=cls._readiness_target_kind(baseline_value),
                    )
                )
                continue
            operations.append(
                StateMutation(
                    path=".".join(path),
                    operation="set",
                    value=deepcopy(outcome_value),
                    target_presence=(
                        "missing" if baseline_value is _READINESS_MISSING else "present"
                    ),
                    target_kind=cls._readiness_target_kind(baseline_value),
                )
            )
        if not operations:
            return None
        return mutation_journal_from_operations(operations)

    @staticmethod
    def _readiness_normalize_paths(write_specs: list[str]) -> list[tuple[str, ...]]:
        paths = sorted(
            {
                tuple(part for part in path.split(".") if part)
                for path in write_specs
                if isinstance(path, str) and path
            }
        )
        normalized: list[tuple[str, ...]] = []
        for path in paths:
            if any(
                len(existing) <= len(path) and existing == path[: len(existing)]
                for existing in normalized
            ):
                continue
            normalized.append(path)
        return normalized

    @staticmethod
    def _readiness_get_path(root: Any, path: tuple[str, ...]) -> Any:
        current = root
        for part in path:
            if isinstance(current, BaseModel):
                if not hasattr(current, part):
                    return _READINESS_MISSING
                current = getattr(current, part)
            elif isinstance(current, dict):
                if part not in current:
                    return _READINESS_MISSING
                current = current[part]
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (IndexError, TypeError, ValueError):
                    return _READINESS_MISSING
            else:
                return _READINESS_MISSING
        return current

    @staticmethod
    def _readiness_target_kind(value: Any) -> str:
        if value is _READINESS_MISSING:
            return "missing"
        if isinstance(value, dict):
            return "dict"
        if isinstance(value, list):
            return "list"
        if isinstance(value, set):
            return "set"
        if isinstance(value, BaseModel):
            return "model"
        return "scalar"

    @staticmethod
    def _readiness_first_difference(left: ExperimentState, right: ExperimentState) -> str | None:
        left_public = AsyncWorkflowExecutor._readiness_public_state(left)
        right_public = AsyncWorkflowExecutor._readiness_public_state(right)
        if left_public == right_public:
            return None
        return (
            AsyncWorkflowExecutor._readiness_difference_path(
                left_public,
                right_public,
            )
            or "state"
        )

    @staticmethod
    def _readiness_public_state(state: ExperimentState) -> dict[str, Any]:
        """Return only public semantic fields, excluding branch journals."""
        return state.model_dump(mode="python")

    @staticmethod
    def _readiness_difference_path(left: Any, right: Any, path: str = "") -> str | None:
        """Return the first public state path whose values differ."""
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right), key=str):
                child_path = f"{path}.{key}" if path else str(key)
                if key not in left or key not in right:
                    return child_path
                difference = AsyncWorkflowExecutor._readiness_difference_path(
                    left[key],
                    right[key],
                    child_path,
                )
                if difference is not None:
                    return difference
            return None
        if isinstance(left, list) and isinstance(right, list):
            for index, (left_item, right_item) in enumerate(zip(left, right)):
                difference = AsyncWorkflowExecutor._readiness_difference_path(
                    left_item,
                    right_item,
                    f"{path}.{index}" if path else str(index),
                )
                if difference is not None:
                    return difference
            if len(left) != len(right):
                return (
                    f"{path}.{min(len(left), len(right))}"
                    if path
                    else str(min(len(left), len(right)))
                )
            return None
        if left != right:
            return path or "state"
        return None

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
    ) -> tuple[list[NodeRunRecord], ExperimentState, set[str], dict[str, ArtifactRef]]:
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
                            error=NodeError.for_timeout(
                                code="node.semaphore_timeout",
                                message=f"Node {alias} timed out waiting for execution slot",
                                timeout_s=self._semaphore_timeout_s,
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

            try:
                # A fail-fast signal can arrive while this task waits for the
                # semaphore.  Recheck after admission, inside the release
                # guard, so queued producers never start after the failure.
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

                if self._ctx.metrics is not None and sem_wait_s > 0.001:
                    try:
                        self._ctx.metrics.record_semaphore_wait(
                            tier_index=tier_index,
                            wait_seconds=sem_wait_s,
                            workflow_id=workflow.workflow_id,
                        )
                    except _EXECUTOR_DEGRADED_ERRORS as exc:
                        _executor_degraded(
                            operation="record_semaphore_wait",
                            reason="metrics_degraded",
                            exc=exc,
                            details={
                                "alias": alias,
                                "tier_index": tier_index,
                                "workflow_id": workflow.workflow_id,
                            },
                        )

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
                return records, state, tier_failed, {}

            state = merge_result.state
            if merge_result.resolved_conflicts:
                self._ctx.logger.warning(
                    "Parallel merge resolved by policy=%s: %s",
                    self._merge_conflict_policy.value,
                    [str(conflict) for conflict in merge_result.resolved_conflicts],
                )
        return records, state, tier_failed, cache_entry_refs

    async def _recover_cache(
        self,
        *,
        run_id: str,
        deadline_monotonic: float | None,
    ) -> tuple[NodeResultCache, int, int]:
        """Build a private recovery index off-loop before caller admission.

        The synchronous store must support use from the shared executor, as
        required for the existing async artifact-store adapter. A backend read
        already entered cannot be preempted; deadline checks stop subsequent
        reads and index admission, while cancellation discards worker ownership.
        """
        tenant_context = self._run_tenant_context()
        trace_path = self._ctx.run.trace_path
        refs = tuple(self._checkpoint_cache_seed_refs)
        try:
            self._check_budget("cache_recovery", budget_key="read")
        except BudgetExhaustedError:
            # Preserve the native per-node budget failure path. A denied read
            # must not first consume persisted recovery bytes to build its cache.
            return (
                NodeResultCache(self._ctx.store, run_id=run_id, tenant_context=tenant_context),
                0,
                0,
            )

        def recover() -> tuple[NodeResultCache, int, int]:
            NodeResultCache._check_deadline(deadline_monotonic)
            cache = NodeResultCache(self._ctx.store, run_id=run_id, tenant_context=tenant_context)
            restored = cache.seed_from_trace(trace_path, deadline_monotonic=deadline_monotonic)
            restored_cp = cache.seed_from_entry_refs(refs, deadline_monotonic=deadline_monotonic)
            NodeResultCache._check_deadline(deadline_monotonic)
            return cache, restored, restored_cp

        return await run_blocking_async(
            recover,
            timeout_seconds=self._remaining_deadline_seconds(deadline_monotonic),
            unbounded=deadline_monotonic is None,
        )

    def _run_tenant_context(self) -> ArtifactTenantContextInfo | None:
        """Capture tenant/cell ownership from the existing run context."""
        run = self._ctx.run
        tenant_id = getattr(run, "tenant_id", None)
        cell_id = getattr(run, "cell_id", None)
        if not isinstance(tenant_id, str) or not tenant_id:
            run_manifest = getattr(run, "run_manifest", None)
            manifest_tenant_id = getattr(run_manifest, "tenant_id", None)
            manifest_cell_id = getattr(run_manifest, "cell_id", None)
            tenant_id = manifest_tenant_id if isinstance(manifest_tenant_id, str) else None
            cell_id = manifest_cell_id if isinstance(manifest_cell_id, str) else None
        elif cell_id is not None and not isinstance(cell_id, str):
            cell_id = None
        if tenant_id is None:
            return None
        return ArtifactTenantContextInfo(tenant_id=tenant_id, cell_id=cell_id)

    def _cache_deadline(
        self,
        inv: NodeInvocation,
        *,
        started_at: float | None = None,
    ) -> float | None:
        """Return one absolute deadline shared by cache and node admission."""
        started = time.perf_counter() if started_at is None else started_at
        deadlines: list[float] = []
        if inv.timeout_s is not None:
            deadlines.append(started + inv.timeout_s)
        if self._workflow_deadline is not None:
            deadlines.append(self._workflow_deadline)
        elif self._workflow_timeout_s is not None:
            deadlines.append(started + self._workflow_timeout_s)
        return min(deadlines) if deadlines else None

    @staticmethod
    def _remaining_deadline_seconds(deadline: float | None) -> float | None:
        if deadline is None:
            return None
        return max(0.001, deadline - time.perf_counter())

    def _cache_timeout_seconds(
        self,
        inv: NodeInvocation,
        *,
        started_at: float | None = None,
    ) -> float | None:
        """Return the remaining time budget for one cache I/O operation.

        Cache work is part of the node/workflow deadline.  Passing the raw
        configured timeout here would give a cache miss or publication a fresh
        full timeout after the producer had already consumed most of it.
        ``run_blocking_async`` rejects a non-positive timeout, so an expired
        deadline is represented by its smallest bounded slice and reported as
        the normal timeout/degraded path.
        """
        return self._remaining_deadline_seconds(self._cache_deadline(inv, started_at=started_at))

    def _check_budget(self, alias: str, *, budget_key: str) -> None:
        """Check one action-specific budget and emit its threshold alerts."""
        if self._budget_middleware is None:
            return
        self._budget_middleware.pre_check(alias, budget_key=budget_key)
        for level in self._budget_middleware.check_thresholds(budget_key):
            self._ctx.run.emit(
                "scientist.budget",
                "BUDGET_ALERT",
                metrics={"threshold_pct": level, "budget_key": budget_key},
            )

    async def _put_cache_entry(
        self,
        cache_key: str,
        *,
        node_id: str,
        outcome: NodeOutcome,
        timeout_seconds: float | None,
        deadline_monotonic: float | None,
    ) -> ArtifactRef:
        """Publish a cache entry off-loop and quarantine it if cancelled."""
        cache = self._cache
        if cache is None:
            raise RuntimeError("cache is not initialized")

        cancelled = threading.Event()

        def put_and_reconcile() -> ArtifactRef:
            try:
                return cache.put(
                    cache_key,
                    node_id=node_id,
                    outcome=outcome,
                    deadline_monotonic=deadline_monotonic,
                )
            finally:
                # A timeout/cancellation only cancels the awaitable; the
                # executor worker may still finish its synchronous CAS write.
                # Reconcile the in-memory publication after that worker exits
                # so a late completion cannot resurrect a cancelled cache key.
                if cancelled.is_set():
                    cache.discard(cache_key)

        put_task = asyncio.create_task(
            run_blocking_async(
                put_and_reconcile,
                timeout_seconds=timeout_seconds,
                unbounded=deadline_monotonic is None,
            )
        )
        try:
            return await asyncio.shield(put_task)
        except asyncio.CancelledError:
            cancelled.set()
            # Shield lets the synchronous writer finish before the key is
            # discarded; cancellation of the await is not cancellation of the
            # underlying worker thread.
            try:
                await asyncio.shield(put_task)
            except _EXECUTOR_DEGRADED_ERRORS:
                pass
            cache.discard(cache_key)
            raise
        except _EXECUTOR_DEGRADED_ERRORS:
            cancelled.set()
            # On a bounded wait, the underlying shared-executor call may
            # continue after run_blocking_async has returned.  Discard now and
            # again from the worker's finally block to close that race.
            cache.discard(cache_key)
            raise

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
        cache_deadline = self._cache_deadline(inv, started_at=started)
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

        cached_outcome: NodeOutcome | None = None
        retry_stats: dict[str, int] = {}
        if cache_key and self._cache:
            try:
                self._check_budget(alias, budget_key="read")
            except BudgetExhaustedError as budget_exc:
                duration_ms = int((time.perf_counter() - started) * 1000)
                return (
                    NodeOutcome(
                        status="fail",
                        state=state,
                        error=NodeError(
                            code="node.budget_exhausted",
                            message=str(budget_exc),
                            details={"budget_key": "read"},
                        ),
                    ),
                    duration_ms,
                    False,
                    None,
                )

            try:
                cached_outcome = await run_blocking_async(
                    self._cache.get,
                    cache_key,
                    deadline_monotonic=cache_deadline,
                    timeout_seconds=self._remaining_deadline_seconds(cache_deadline),
                    unbounded=cache_deadline is None,
                )
            except _EXECUTOR_DEGRADED_ERRORS as exc:
                _executor_degraded(
                    operation="load_cache_entry",
                    reason="cache_bypass",
                    exc=exc,
                    details={"alias": alias, "node_id": node_id},
                )

        if cached_outcome is not None:
            try:
                merged_cached_state = _merge_cached_outcome_state(
                    alias=alias,
                    node=node,
                    base_state=state,
                    outcome=cached_outcome,
                )
            except StateReplayIncompatible as exc:
                if self._cache is not None and cache_key is not None:
                    self._cache.discard(cache_key)
                cached_outcome = None
                self._ctx.run.emit(
                    f"scientist.node.{alias}",
                    "NODE_CACHE_BYPASS",
                    metrics={
                        "duration_ms": int((time.perf_counter() - started) * 1000),
                        "cache_bypass": 1,
                        "reason_code": _CACHE_BYPASS_REPLAY_INCOMPATIBLE,
                    },
                )
                self._ctx.logger.warning(
                    "Node %s cache replay bypassed: %s",
                    alias,
                    exc,
                )
                span_attrs["polisyos.node.cache.bypass_reason"] = _CACHE_BYPASS_REPLAY_INCOMPATIBLE
            else:
                cache_hit = True
                self._ctx.run.emit(
                    f"scientist.node.{alias}",
                    "NODE_CACHE_HIT",
                    metrics={
                        "duration_ms": int((time.perf_counter() - started) * 1000),
                        "cache_hit": 1,
                    },
                )
                outcome = cached_outcome.model_copy(update={"state": merged_cached_state})

        if cached_outcome is None:
            try:
                self._check_budget(alias, budget_key="run")
            except BudgetExhaustedError as budget_exc:
                duration_ms = int((time.perf_counter() - started) * 1000)
                return (
                    NodeOutcome(
                        status="fail",
                        state=state,
                        error=NodeError(
                            code="node.budget_exhausted",
                            message=str(budget_exc),
                            details={"budget_key": "run"},
                        ),
                    ),
                    duration_ms,
                    False,
                    None,
                )

            retry_policy = inv.retry or RetryPolicy()
            node_timeout_s = self._remaining_deadline_seconds(cache_deadline)
            try:
                raw_outcome = await execute_with_retry_async(
                    node,
                    self._ctx,
                    node_state,
                    retry_policy=retry_policy,
                    timeout_s=node_timeout_s,
                    alias=alias,
                    retry_stats=retry_stats,
                )
                outcome = NodeOutcome.model_validate(raw_outcome)
            except NodeTimeoutError as exc:
                self._ctx.logger.error("Node %s timed out", alias)
                outcome = NodeOutcome(
                    status="fail",
                    state=node_state,
                    error=NodeError.for_timeout(
                        message=str(exc),
                        timeout_s=node_timeout_s,
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
                    cache_entry_ref = await self._put_cache_entry(
                        cache_key,
                        node_id=node_id,
                        outcome=outcome,
                        timeout_seconds=self._remaining_deadline_seconds(cache_deadline),
                        deadline_monotonic=cache_deadline,
                    )
                    self._ctx.run.emit(
                        f"scientist.node.{alias}",
                        "NODE_CACHE_STORE",
                        outputs=[cache_entry_ref],
                        metrics={"cache_hit": 0},
                    )
                except _EXECUTOR_DEGRADED_ERRORS as exc:
                    self._cache.discard(cache_key)
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

    async def _handle_tier_checkpoint(
        self,
        state: ExperimentState,
        *,
        aliases: list[str],
        alias: str,
        node_id: str,
        completed_nodes: list[str],
        workflow: WorkflowSpec,
        workflow_fingerprint: str,
        cache_entry_refs_by_alias: dict[str, ArtifactRef],
    ) -> ExperimentState:
        """Publish a merged tier frontier through the available hook contract."""
        if self._checkpoint_hook is None:
            return state

        async_checkpoint = getattr(self._checkpoint_hook, "on_tier_complete_async", None)
        sync_checkpoint = getattr(self._checkpoint_hook, "on_tier_complete", None)
        if callable(async_checkpoint) or callable(sync_checkpoint):
            cache_entry_refs = [
                cache_entry_refs_by_alias[successful_alias]
                for successful_alias in aliases
                if successful_alias in cache_entry_refs_by_alias
            ]
            if callable(async_checkpoint):
                result = await async_checkpoint(
                    state=state,
                    alias=alias,
                    node_id=node_id,
                    completed_nodes=list(completed_nodes),
                    workflow_id=workflow.workflow_id,
                    workflow_fingerprint=workflow_fingerprint,
                    cache_entry_refs=list(cache_entry_refs),
                )
            else:
                result = await run_blocking_async(
                    sync_checkpoint,
                    state=state,
                    alias=alias,
                    node_id=node_id,
                    completed_nodes=list(completed_nodes),
                    workflow_id=workflow.workflow_id,
                    workflow_fingerprint=workflow_fingerprint,
                    cache_entry_refs=list(cache_entry_refs),
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
                            "aliases": list(aliases),
                            "tier_atomic": True,
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
                            operation="record_tier_checkpoint_provenance",
                            reason="provenance_record_failed",
                            exc=exc,
                            details={
                                "alias": alias,
                                "node_id": node_id,
                                "aliases": list(aliases),
                            },
                        )
            return state

        raise CheckpointError("parallel_tier_requires_atomic_checkpoint_hook")

    def _require_atomic_tier_checkpoint(self, tiers: list[list[str]]) -> None:
        """Reject a node-only hook before executing a workflow with parallel tiers."""
        if self._checkpoint_hook is None or not any(len(tier) > 1 for tier in tiers):
            return
        if callable(getattr(self._checkpoint_hook, "on_tier_complete_async", None)):
            return
        if callable(getattr(self._checkpoint_hook, "on_tier_complete", None)):
            return
        raise CheckpointError("parallel_tier_requires_atomic_checkpoint_hook")

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
            report._validated_payload(),
            ArtifactWriteOptions(
                kind="scientist.workflow_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.orchestration.engine.WorkflowReport",
                    version="1.0",
                ),
            ),
        )

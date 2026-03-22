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
from polisyos.scientist.engine.errors import NodeTimeoutError, RetryExhaustedError
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
from polisyos.scientist.engine.protocol import NodeError, NodeOutcome, NodeStatus
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
from polisyos.scientist.engine.workflow_spec import ErrorPolicy, NodeInvocation, WorkflowSpec

if TYPE_CHECKING:
    from polisyos.scientist.engine.checkpoint import CheckpointHook

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
    ) -> None:
        self._ctx = ctx
        self._registry = registry
        self._cache: NodeResultCache | None = None
        self._checkpoint_hook = checkpoint_hook
        self._checkpoint_cache_seed_refs = list(checkpoint_cache_seed_refs or [])
        self._max_parallelism = max(1, max_parallelism)

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

        for tier_index, tier in enumerate(tiers):
            if abort:
                # Block remaining tiers
                for alias in tier:
                    records.append(NodeRunRecord(
                        alias=alias, node_id=str(invocations[alias].node_id),
                        status="skip", duration_ms=0, skip_reason="upstream_failed",
                    ))
                    blocked.add(alias)
                continue

            # Check for blocked / condition-skipped nodes in this tier
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

                # Evaluate condition (if present)
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

            # Condition-failures with on_false="fail" may trigger abort
            if failed and workflow.error_policy == "fail_fast":
                abort = True

            if not runnable or abort:
                continue

            tier_started = time.perf_counter()

            if len(runnable) == 1:
                # Sequential — single node tier
                alias = runnable[0]
                record, state, node_failed = await self._run_single_node(
                    alias, invocations[alias], state, workflow,
                    workflow_fingerprint, completed_nodes,
                )
                records.append(record)
                if node_failed:
                    failed.add(alias)
                    if workflow.error_policy == "fail_fast":
                        abort = True
                else:
                    completed_nodes.append(alias)
            else:
                # Parallel tier
                tier_records, state, tier_failed = await self._run_parallel_tier(
                    runnable, invocations, state, workflow,
                    workflow_fingerprint, completed_nodes,
                )
                records.extend(tier_records)
                for alias in tier_failed:
                    failed.add(alias)
                for rec in tier_records:
                    if rec.status == "ok":
                        completed_nodes.append(rec.alias)
                if tier_failed and workflow.error_policy == "fail_fast":
                    abort = True

            tier_duration_ms = int((time.perf_counter() - tier_started) * 1000)
            if self._ctx.metrics is not None:
                self._ctx.metrics.record_tier_completed(
                    tier_index=tier_index,
                    tier_size=len(runnable),
                    duration_ms=tier_duration_ms,
                    workflow_id=workflow.workflow_id,
                )

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
        final_state = state.model_copy(deep=True)
        final_state.reports_index["workflow_report"] = report_ref
        final_state_ref = self._persist_state(final_state)

        self._ctx.run.add_output(final_state_ref)
        self._ctx.run.add_output(report_ref)

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
    ) -> tuple[NodeRunRecord, ExperimentState, bool]:
        """Execute a single node (same semantics as sync executor)."""
        outcome, duration_ms, cache_hit = await self._execute_node(
            alias, inv, state, workflow,
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
    ) -> tuple[list[NodeRunRecord], ExperimentState, set[str]]:
        """Execute a parallel tier using asyncio.TaskGroup."""
        semaphore = asyncio.Semaphore(self._max_parallelism)
        results: dict[str, tuple[NodeOutcome, int, bool]] = {}

        async def _run_with_sem(alias: str) -> None:
            async with semaphore:
                outcome, duration_ms, cache_hit = await self._execute_node(
                    alias, invocations[alias], state, workflow,
                )
                results[alias] = (outcome, duration_ms, cache_hit)

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
    ) -> tuple[NodeOutcome, int, bool]:
        """Execute a single node with cache, retry, timeout, metrics."""
        node = _bind_node_params(self._registry.get(inv.node_id), inv.params)
        node_id = str(inv.node_id)

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

        cached_outcome: NodeOutcome | None = None
        if cache_key and self._cache:
            cached_outcome = self._cache.get(cache_key)
            if cached_outcome:
                cache_hit = True

        if cached_outcome is not None:
            outcome = cached_outcome
        else:
            retry_policy = inv.retry or RetryPolicy()
            try:
                raw_outcome = await execute_with_retry_async(
                    node, self._ctx, state,
                    retry_policy=retry_policy,
                    timeout_s=inv.timeout_s,
                    alias=alias,
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
            self._ctx.metrics.record_node_completed(
                alias=alias, node_id=node_id,
                workflow_id=workflow.workflow_id,
                status=outcome.status, duration_ms=duration_ms,
                cache_hit=cache_hit, retry_count=0,
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

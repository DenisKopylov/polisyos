"""Temporal workflow runner — maps scientist workflows to Temporal activities.

Import-guarded: ``temporalio`` is an optional dependency.  If not installed,
importing this module raises ``ImportError`` with a helpful message, and the
factory in ``config.py`` never reaches this code unless the user explicitly
selects ``backend="temporal"``.

Architecture
------------
* One **Temporal workflow** per scientist run.
* Each topological tier becomes a group of **parallel activities**.
* ``ExperimentState`` is serialised between tiers via ``serialization.py``.
* W3C TraceContext is propagated through activity headers.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

try:
    from temporalio import activity, workflow
    from temporalio.client import Client as TemporalClient
    from temporalio.common import RetryPolicy as TemporalRetryPolicy
    from temporalio.service import RPCError as TemporalRPCError

    _HAS_TEMPORAL = True
except ImportError:
    _HAS_TEMPORAL = False
    TemporalRPCError = RuntimeError

from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.runner.distributed_tier import (
    build_distributed_execution_result,
    merge_and_checkpoint_tier,
    project_distributed_node_outcomes,
    seed_runner_cache,
)
from polisyos.scientist.orchestration.engine.runner.fallback_runner import (
    HealthFailureDisposition,
    _classify_health_probe_exception,
    _HealthFailureSample,
)
from polisyos.scientist.orchestration.engine.runner.protocol import RunnerHealth
from polisyos.scientist.orchestration.engine.runner.serialization import (
    deserialize_state,
    serialize_context_meta,
    serialize_state,
)
from polisyos.scientist.orchestration.engine.runner.state_merge import merge_tier_outcomes
from polisyos.scientist.orchestration.engine.state_merge import MergeConflictPolicy

_logger = logging.getLogger(__name__)
_TRACE_IMPORT_ERRORS = (ImportError, ModuleNotFoundError, AttributeError)
_TRACE_RUNTIME_ERRORS = (RuntimeError, TypeError, ValueError)
_TEMPORAL_HEALTH_ERRORS = (OSError, RuntimeError, TypeError, ValueError)
_TEMPORAL_PROBE_ERRORS = (TemporalRPCError,) + _TEMPORAL_HEALTH_ERRORS
_TEMPORAL_TRANSIENT_STATUS_NAMES = frozenset(
    {
        "ABORTED",
        "DEADLINE_EXCEEDED",
        "RESOURCE_EXHAUSTED",
        "UNAVAILABLE",
    }
)


def _temporal_probe_disposition(exc: BaseException) -> HealthFailureDisposition:
    """Classify Temporal probe failures from typed RPC status, not text."""

    if _HAS_TEMPORAL and isinstance(exc, TemporalRPCError):
        status = getattr(exc, "status", None)
        status_name = getattr(status, "name", None)
        if status_name in _TEMPORAL_TRANSIENT_STATUS_NAMES:
            return HealthFailureDisposition.ALLOW
        return HealthFailureDisposition.BLOCK
    return _classify_health_probe_exception(exc)


# ---------------------------------------------------------------------------
# Payload models (plain dicts for Temporal serialization)
# ---------------------------------------------------------------------------


@dataclass
class NodeActivityPayload:
    """Serialisable payload shipped to a Temporal activity worker."""

    node_id: str
    alias: str
    params: dict[str, Any]
    state_bytes: bytes
    trace_carrier: dict[str, str]
    timeout_s: float | None = None
    max_retries: int = 0
    context_meta: dict[str, Any] | None = None


@dataclass
class WorkflowRunPayload:
    """Top-level payload for the Temporal workflow."""

    workflow_spec_json: dict[str, Any]
    initial_state_bytes: bytes
    context_meta: dict[str, Any]
    max_parallelism: int = 4
    merge_conflict_policy: str = MergeConflictPolicy.ERROR.value


# ---------------------------------------------------------------------------
# Activity definition
# ---------------------------------------------------------------------------

if _HAS_TEMPORAL:

    @activity.defn(name="scientist_execute_node")
    async def execute_node_activity(payload_dict: dict[str, Any]) -> bytes:
        """Keep the state-only activity contract for older workflow histories."""
        from polisyos.scientist.orchestration.engine.runner._activity_worker import (
            run_node_state_in_worker,
        )

        return await run_node_state_in_worker(payload_dict)

    @activity.defn(name="scientist_execute_node_outcome_v1")
    async def execute_node_outcome_activity(payload_dict: dict[str, Any]) -> bytes:
        """Execute one node and return its typed, status-bearing outcome."""

        from polisyos.scientist.orchestration.engine.runner._activity_worker import (
            run_node_in_worker,
        )

        return await run_node_in_worker(payload_dict)

    @activity.defn(name="scientist_merge_checkpoint_tier")
    async def merge_checkpoint_tier_activity(payload_dict: dict[str, Any]) -> dict[str, Any]:
        """Merge one tier and persist checkpoints/cache metadata remotely."""
        from polisyos.scientist.orchestration.engine.runner._activity_worker import (
            run_merge_checkpoint_tier_in_worker,
        )

        return await run_merge_checkpoint_tier_in_worker(payload_dict)


# ---------------------------------------------------------------------------
# Workflow definition
# ---------------------------------------------------------------------------

if _HAS_TEMPORAL:

    @workflow.defn(name="ScientistWorkflow")
    class ScientistWorkflow:
        """Temporal workflow that executes a scientist DAG tier-by-tier."""

        @workflow.run
        async def run(self, payload_dict: dict[str, Any]) -> Any:
            """Execute the DAG, retaining typed outcomes on the versioned status path."""
            from polisyos.scientist.orchestration.engine.topo import topo_sort_tiers
            from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

            carries_node_status = workflow.patched("distributed-node-outcome-status-v1")
            spec = WorkflowSpec.model_validate(payload_dict["workflow_spec_json"])
            state_bytes: bytes = payload_dict["initial_state_bytes"]
            max_par = max(1, int(payload_dict.get("max_parallelism", 4) or 4))
            conflict_policy = MergeConflictPolicy(
                payload_dict.get("merge_conflict_policy", MergeConflictPolicy.ERROR.value)
            )
            ctx_meta: dict[str, Any] = payload_dict.get("context_meta", {})
            workflow_fingerprint = str(payload_dict.get("workflow_fingerprint") or "")
            checkpoint_meta = payload_dict.get("checkpoint_hook_meta")
            completed_nodes = list(
                checkpoint_meta.get("completed_nodes", [])
                if isinstance(checkpoint_meta, dict)
                else []
            )

            invocations = {inv.alias: inv for inv in spec.nodes}
            tiers = topo_sort_tiers(invocations)
            node_reports_by_alias: dict[str, dict[str, Any]] = {}
            node_activity = (
                execute_node_outcome_activity if carries_node_status else execute_node_activity
            )

            for tier in tiers:
                # Build activity payloads without scheduling them; chunking below enforces
                # workflow max_parallelism while keeping same-tier state input stable.
                tier_state_bytes = state_bytes
                activity_specs = []
                for alias in tier:
                    inv = invocations[alias]
                    # Inject W3C TraceContext — supplements Temporal's native
                    # context propagation (via temporalio.contrib.opentelemetry
                    # interceptor) for cases where the interceptor is not configured.
                    _carrier = _inject_trace_carrier()

                    act_payload = {
                        "node_id": str(inv.node_id),
                        "alias": alias,
                        "params": inv.params or {},
                        "state_bytes": state_bytes,
                        "trace_carrier": _carrier,
                        "timeout_s": inv.timeout_s,
                        "max_retries": inv.retry.max_retries if inv.retry else 0,
                        "context_meta": ctx_meta,
                    }
                    retry_policy = TemporalRetryPolicy(
                        maximum_attempts=1 + (inv.retry.max_retries if inv.retry else 0),
                    )
                    timeout = (
                        timedelta(seconds=inv.timeout_s) if inv.timeout_s else timedelta(minutes=10)
                    )
                    activity_specs.append((act_payload, timeout, retry_policy))

                # Execute tier in bounded chunks.  Each chunk waits with
                # return_exceptions=True so one failed sibling cannot cancel the rest.
                tier_results: dict[str, bytes] = {}
                for offset in range(0, len(activity_specs), max_par):
                    chunk = activity_specs[offset : offset + max_par]
                    tasks = [
                        workflow.execute_activity(
                            node_activity,
                            act_payload,
                            start_to_close_timeout=timeout,
                            retry_policy=retry_policy,
                        )
                        for act_payload, timeout, retry_policy in chunk
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for (act_payload, _timeout, _retry_policy), item in zip(
                        chunk, results, strict=False
                    ):
                        if not isinstance(item, BaseException):
                            tier_results[str(act_payload["alias"])] = item
                    exceptions = [item for item in results if isinstance(item, BaseException)]
                    if exceptions:
                        raise exceptions[0]

                # Merge parallel node results into unified state
                if tier_results:
                    if carries_node_status:
                        node_reports_by_alias.update(
                            project_distributed_node_outcomes(
                                workflow=spec,
                                tier_aliases=list(tier),
                                outcome_bytes_by_alias=tier_results,
                            )
                        )
                    if checkpoint_meta is not None:
                        merge_payload = {
                            "workflow_spec_json": payload_dict["workflow_spec_json"],
                            "tier_aliases": list(tier),
                            "result_bytes_by_alias": tier_results,
                            "base_state_bytes": tier_state_bytes,
                            "context_meta": ctx_meta,
                            "workflow_fingerprint": workflow_fingerprint,
                            "completed_nodes": completed_nodes,
                            "merge_conflict_policy": conflict_policy.value,
                            "checkpoint_hook_meta": checkpoint_meta,
                        }
                        if carries_node_status:
                            merge_payload["result_format"] = "node_outcome"
                        merge_result = await workflow.execute_activity(
                            merge_checkpoint_tier_activity,
                            merge_payload,
                            start_to_close_timeout=timedelta(minutes=10),
                            retry_policy=TemporalRetryPolicy(maximum_attempts=1),
                        )
                        state_bytes = merge_result["state_bytes"]
                        completed_nodes = list(
                            merge_result.get("completed_nodes") or completed_nodes
                        )
                        checkpoint_meta = merge_result.get("checkpoint_hook_meta")
                        if bool(merge_result.get("should_abort")):
                            break
                    else:
                        if carries_node_status:
                            outcome_merge = merge_tier_outcomes(
                                tier_state_bytes,
                                tier_results,
                                requested_aliases=tier,
                                conflict_policy=conflict_policy,
                            )
                            tier_failed = any(
                                outcome.status == "fail"
                                for outcome in outcome_merge.node_outcomes.values()
                            )
                            state_bytes = (
                                tier_state_bytes
                                if tier_failed and spec.error_policy == "fail_fast"
                                else outcome_merge.state_bytes
                            )
                            if tier_failed and spec.error_policy == "fail_fast":
                                break
                        else:
                            from polisyos.scientist.orchestration.engine.runner.state_merge import (
                                merge_tier_states,
                            )

                            state_bytes = merge_tier_states(
                                tier_state_bytes,
                                tier_results,
                                conflict_policy=conflict_policy,
                            )

            if carries_node_status:
                return {
                    "state_bytes": state_bytes,
                    "node_reports_by_alias": node_reports_by_alias,
                }
            return state_bytes


# ---------------------------------------------------------------------------
# Runner class
# ---------------------------------------------------------------------------


class TemporalWorkflowRunner:
    """Dispatches scientist workflows via Temporal.

    Requires ``temporalio`` to be installed.  Connection to the Temporal
    server is established lazily on first ``execute_workflow`` call.
    """

    def __init__(
        self,
        *,
        server_url: str,
        namespace: str = "default",
        task_queue: str = "scientist-nodes",
        max_parallelism: int = 4,
        merge_conflict_policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
    ) -> None:
        if not _HAS_TEMPORAL:
            raise ImportError(
                "temporalio is required for the Temporal runner backend.  "
                "Install it with: pip install temporalio"
            )
        self._server_url = server_url
        self._namespace = namespace
        self._task_queue = task_queue
        self._max_parallelism = max_parallelism
        self._merge_conflict_policy = merge_conflict_policy
        self._client: TemporalClient | None = None
        self._health_probe_id = 0
        self._health_sample: _HealthFailureSample | None = None

    def _get_health_sample(self) -> _HealthFailureSample | None:
        """Return the private authority witness for the latest Temporal probe."""
        return self._health_sample

    async def _get_client(self) -> TemporalClient:
        if self._client is None:
            self._client = await TemporalClient.connect(
                self._server_url,
                namespace=self._namespace,
            )
        return self._client

    async def health_check(self) -> RunnerHealth:
        """Probe Temporal server health."""
        import time

        self._health_probe_id += 1
        self._health_sample = None
        try:
            t0 = time.monotonic()
            client = await self._get_client()
            # Use service health check RPC
            await client.service_client.check_health()
            latency = (time.monotonic() - t0) * 1000
            health = RunnerHealth(
                backend="temporal",
                healthy=True,
                latency_ms=round(latency, 2),
                message=f"namespace={self._namespace}",
            )
            self._health_sample = _HealthFailureSample(
                health=health,
                disposition=HealthFailureDisposition.BLOCK,
                probe_id=self._health_probe_id,
            )
            return health
        except _TEMPORAL_PROBE_ERRORS as exc:
            health = RunnerHealth(
                backend="temporal",
                healthy=False,
                message=f"probe failed: {exc}",
            )
            self._health_sample = _HealthFailureSample(
                health=health,
                disposition=_temporal_probe_disposition(exc),
                probe_id=self._health_probe_id,
            )
            return health

    async def execute_workflow(
        self,
        workflow: Any,  # WorkflowSpec
        state: Any,  # ExperimentState
        ctx: Any,  # ExecutionContext
        registry: Any,  # NodeRegistry
        *,
        checkpoint_hook: Any | None = None,
        checkpoint_cache_seed_refs: Any | None = None,
        max_parallelism: int | None = None,
    ) -> Any:  # WorkflowExecutionResult
        """Start a Temporal workflow and wait for completion."""
        from polisyos.scientist.orchestration.engine.checkpoint import (
            compute_workflow_fingerprint,
            serialize_checkpoint_hook_runtime_metadata,
        )
        from polisyos.scientist.orchestration.engine.topo import topo_sort_tiers

        client = await self._get_client()
        ctx_meta = serialize_context_meta(
            ctx,
            workflow_id=workflow.workflow_id,
            runner_backend="temporal",
        )
        if ctx.metrics is not None:
            ctx.metrics.record_trace_correlation(
                runner_backend="temporal",
                workflow_id=workflow.workflow_id,
                run_id=str(ctx_meta.get("run_id") or state.run_id),
                trace_id=ctx_meta.get("trace_id"),
                span_id=ctx_meta.get("span_id"),
            )
        state_bytes = serialize_state(state)
        cache = seed_runner_cache(
            store=ctx.store,
            run_id=state.run_id,
            checkpoint_cache_seed_refs=list(checkpoint_cache_seed_refs or []),
            logger=_logger,
        )
        workflow_fingerprint = compute_workflow_fingerprint(workflow)
        checkpoint_hook_meta = serialize_checkpoint_hook_runtime_metadata(checkpoint_hook)

        if checkpoint_hook is not None and checkpoint_hook_meta is None:
            invocations = {inv.alias: inv for inv in workflow.nodes}
            tiers = topo_sort_tiers(invocations)
            completed_nodes: list[str] = []
            node_reports_by_alias: dict[str, dict[str, Any]] = {}
            effective_max_parallelism = max(
                1,
                int(max_parallelism or self._max_parallelism or 1),
            )
            for tier in tiers:
                tier_state_bytes = state_bytes
                tier_results: dict[str, bytes] = {}
                activity_specs = []
                for alias in tier:
                    inv = invocations[alias]
                    _carrier = _inject_trace_carrier()

                    act_payload = {
                        "node_id": str(inv.node_id),
                        "alias": alias,
                        "params": inv.params or {},
                        "state_bytes": tier_state_bytes,
                        "trace_carrier": _carrier,
                        "timeout_s": inv.timeout_s,
                        "max_retries": inv.retry.max_retries if inv.retry else 0,
                        "context_meta": ctx_meta,
                    }
                    retry_policy = TemporalRetryPolicy(
                        maximum_attempts=1 + (inv.retry.max_retries if inv.retry else 0),
                    )
                    timeout = (
                        timedelta(seconds=inv.timeout_s) if inv.timeout_s else timedelta(minutes=10)
                    )
                    activity_specs.append((alias, act_payload, timeout, retry_policy))

                for offset in range(0, len(activity_specs), effective_max_parallelism):
                    chunk = activity_specs[offset : offset + effective_max_parallelism]
                    tasks = [
                        execute_node_outcome_activity(act_payload)
                        for _alias, act_payload, _timeout, _retry_policy in chunk
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for (alias, _payload, _timeout, _retry_policy), item in zip(
                        chunk, results, strict=False
                    ):
                        if not isinstance(item, BaseException):
                            tier_results[alias] = item
                    exceptions = [item for item in results if isinstance(item, BaseException)]
                    if exceptions:
                        raise exceptions[0]

                tier_result = merge_and_checkpoint_tier(
                    workflow=workflow,
                    tier_aliases=tier,
                    invocations=invocations,
                    result_bytes_by_alias=tier_results,
                    base_state_bytes=tier_state_bytes,
                    registry=registry,
                    checkpoint_hook=checkpoint_hook,
                    cache=cache,
                    completed_nodes=completed_nodes,
                    workflow_fingerprint=workflow_fingerprint,
                    conflict_policy=self._merge_conflict_policy,
                    logger=_logger,
                )
                state_bytes = tier_result.state_bytes
                completed_nodes = tier_result.completed_nodes
                node_reports_by_alias.update(
                    project_distributed_node_outcomes(
                        workflow=workflow,
                        tier_aliases=list(tier),
                        outcome_bytes_by_alias=tier_results,
                    )
                )
                if tier_result.should_abort:
                    break

            run_id = getattr(state, "run_id", "unknown")
            return build_distributed_execution_result(
                workflow=workflow,
                run_id=run_id,
                state_bytes=state_bytes,
                node_reports_by_alias=node_reports_by_alias,
            )

        payload = {
            "workflow_spec_json": workflow.model_dump(),
            "initial_state_bytes": state_bytes,
            "context_meta": ctx_meta,
            "max_parallelism": max_parallelism or self._max_parallelism,
            "merge_conflict_policy": self._merge_conflict_policy.value,
            "workflow_fingerprint": workflow_fingerprint,
            "checkpoint_hook_meta": checkpoint_hook_meta,
        }

        run_id = getattr(state, "run_id", "unknown")
        workflow_result: Any = await client.execute_workflow(
            ScientistWorkflow.run,
            payload,
            id=f"scientist-{run_id}",
            task_queue=self._task_queue,
        )

        if isinstance(workflow_result, dict):
            return build_distributed_execution_result(
                workflow=workflow,
                run_id=run_id,
                state_bytes=workflow_result["state_bytes"],
                node_reports_by_alias=workflow_result.get("node_reports_by_alias", {}),
            )

        # Histories recorded before the patch marker return state-only bytes.
        from polisyos.scientist.orchestration.engine.executor import (
            WorkflowExecutionResult,
            WorkflowReport,
        )

        return WorkflowExecutionResult(
            state=deserialize_state(workflow_result),
            report=WorkflowReport(
                workflow_id=workflow.workflow_id,
                run_id=run_id,
                error_policy=workflow.error_policy,
                # Old histories contain only final state bytes. Replaying them
                # preserves state but cannot establish native node outcomes.
                status="not_established",
                nodes=[],
            ),
        )


def _inject_trace_carrier() -> dict[str, str]:
    carrier: dict[str, str] = {}
    try:
        from polisyos.core.observability import inject_headers

        inject_headers(carrier)
    except _TRACE_IMPORT_ERRORS:
        return carrier
    except _TRACE_RUNTIME_ERRORS as exc:
        emit_degraded_path(
            component="engine.runner.temporal",
            operation="inject_trace_carrier",
            reason="trace_carrier_injection_failed",
            exc=exc,
            log=_logger,
        )
        return carrier
    return carrier

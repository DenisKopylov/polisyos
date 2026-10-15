"""Ray workflow runner — dispatches scientist nodes as Ray remote tasks.

Import-guarded: ``ray`` is an optional dependency.  If not installed,
importing this module raises ``ImportError`` with a helpful message, and the
factory in ``config.py`` never reaches this code unless the user explicitly
selects ``backend="ray"``.

Architecture
------------
* Topological tiers are computed locally.
* Each node in a tier becomes a ``ray.remote`` task.
* ``ray.get()`` synchronises between tiers.
* State is shipped as bytes via ``serialization.py``.
* W3C TraceContext is propagated through task arguments.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Any

from pydantic import ValidationError

try:
    import ray

    _HAS_RAY = True
except ImportError:
    _HAS_RAY = False

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
    deserialize_outcome,
    deserialize_state,
    deserialize_worker_execution_receipt,
    serialize_context_meta,
    serialize_outcome,
    serialize_state,
    serialize_timeout_context,
    worker_dispatch_sha256,
)
from polisyos.scientist.orchestration.engine.state_merge import MergeConflictPolicy

_logger = logging.getLogger(__name__)
_TRACE_IMPORT_ERRORS = (ImportError, ModuleNotFoundError, AttributeError)
_TRACE_RUNTIME_ERRORS = (RuntimeError, TypeError, ValueError)
_RAY_PROBE_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValidationError, ValueError)
_RAY_TRANSIENT_EXCEPTION_NAMES = (
    "GetTimeoutError",
    "RayConnectionError",
    "NodeDiedError",
    "WorkerCrashedError",
    "ObjectLostError",
)


def _ray_probe_disposition(exc: BaseException) -> HealthFailureDisposition:
    """Classify Ray probe failures from typed exception classes only."""

    disposition = _classify_health_probe_exception(exc)
    if disposition is HealthFailureDisposition.ALLOW:
        return disposition
    if not _HAS_RAY:
        return HealthFailureDisposition.BLOCK
    ray_exceptions = getattr(ray, "exceptions", None)
    if ray_exceptions is None:
        return HealthFailureDisposition.BLOCK
    for exception_name in _RAY_TRANSIENT_EXCEPTION_NAMES:
        exception_type = getattr(ray_exceptions, exception_name, None)
        if isinstance(exception_type, type) and isinstance(exc, exception_type):
            return HealthFailureDisposition.ALLOW
    return HealthFailureDisposition.BLOCK


# ---------------------------------------------------------------------------
# Remote task definition
# ---------------------------------------------------------------------------

if _HAS_RAY:

    @ray.remote
    def execute_node_task(
        node_id: str,
        alias: str,
        params: dict[str, Any],
        state_bytes: bytes,
        trace_carrier: dict[str, str],
        timeout_s: float | None,
        max_retries: int,
        context_meta: dict[str, Any],
        worker_context_meta: dict[str, Any],
        worker_invocation_id: str,
        worker_dispatch_sha256: str,
    ) -> bytes:
        """Execute a single scientist node as a Ray remote task.

        Returns one source-bound staged execution receipt for host admission.
        """
        from polisyos.scientist.orchestration.engine.runner._activity_worker import (
            run_node_in_worker_sync,
        )

        payload = {
            "node_id": node_id,
            "alias": alias,
            "params": params,
            "state_bytes": state_bytes,
            "trace_carrier": trace_carrier,
            "timeout_s": timeout_s,
            "max_retries": max_retries,
            "context_meta": worker_context_meta,
            "worker_invocation_id": worker_invocation_id,
            "worker_dispatch_sha256": worker_dispatch_sha256,
        }
        return run_node_in_worker_sync(payload, parent_receipt=True)

    @ray.remote
    def merge_checkpoint_tier_task(payload: dict[str, Any]) -> dict[str, Any]:
        """Merge and checkpoint one tier as a Ray remote task."""
        from polisyos.scientist.orchestration.engine.runner._activity_worker import (
            run_merge_checkpoint_tier_in_worker_sync,
        )

        return run_merge_checkpoint_tier_in_worker_sync(payload)


# ---------------------------------------------------------------------------
# Runner class
# ---------------------------------------------------------------------------


class RayWorkflowRunner:
    """Dispatches scientist nodes as Ray remote tasks.

    Requires ``ray`` to be installed.  Initialises Ray lazily on first
    ``execute_workflow`` call.
    """

    def __init__(
        self,
        *,
        address: str = "auto",
        namespace: str = "polisyos",
        max_parallelism: int = 4,
        merge_conflict_policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
    ) -> None:
        if not _HAS_RAY:
            raise ImportError(
                "ray is required for the Ray runner backend.  Install it with: pip install ray"
            )
        self._address = address
        self._namespace = namespace
        self._max_parallelism = max_parallelism
        self._merge_conflict_policy = merge_conflict_policy
        self._initialised = False
        self._health_probe_id = 0
        self._health_sample: _HealthFailureSample | None = None

    def _get_health_sample(self) -> _HealthFailureSample | None:
        """Return the private authority witness for the latest Ray probe."""
        return self._health_sample

    def _ensure_init(self) -> None:
        if not self._initialised:
            if not ray.is_initialized():
                ray.init(
                    address=self._address,
                    namespace=self._namespace,
                    ignore_reinit_error=True,
                )
            self._initialised = True

    async def health_check(self) -> RunnerHealth:
        """Probe Ray cluster resources."""
        import time

        self._health_probe_id += 1
        self._health_sample = None
        try:
            self._ensure_init()
            t0 = time.monotonic()
            resources = ray.cluster_resources()
            latency = (time.monotonic() - t0) * 1000
            cpu_count = int(resources.get("CPU", 0))
            health = RunnerHealth(
                backend="ray",
                healthy=True,
                latency_ms=round(latency, 2),
                worker_count=cpu_count,
                message=f"cluster CPUs={cpu_count}",
            )
            self._health_sample = _HealthFailureSample(
                health=health,
                disposition=HealthFailureDisposition.BLOCK,
                probe_id=self._health_probe_id,
            )
            return health
        except _RAY_PROBE_ERRORS as exc:
            health = RunnerHealth(
                backend="ray",
                healthy=False,
                message=f"probe failed: {exc}",
            )
            self._health_sample = _HealthFailureSample(
                health=health,
                disposition=_ray_probe_disposition(exc),
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
        """Execute the workflow by dispatching nodes to Ray workers."""
        self._ensure_init()
        from polisyos.scientist.orchestration.engine.checkpoint import (
            compute_workflow_fingerprint,
            serialize_checkpoint_hook_runtime_metadata,
        )
        from polisyos.scientist.orchestration.engine.topo import topo_sort_tiers

        ctx_meta = serialize_context_meta(
            ctx,
            workflow_id=workflow.workflow_id,
            runner_backend="ray",
        )
        if ctx.metrics is not None:
            ctx.metrics.record_trace_correlation(
                runner_backend="ray",
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
        effective_max_parallelism = max(
            1,
            int(max_parallelism or self._max_parallelism or 1),
        )

        invocations = {inv.alias: inv for inv in workflow.nodes}
        tiers = topo_sort_tiers(invocations)
        workflow_fingerprint = compute_workflow_fingerprint(workflow)
        checkpoint_hook_meta = serialize_checkpoint_hook_runtime_metadata(checkpoint_hook)
        completed_nodes: list[str] = []
        node_reports_by_alias: dict[str, dict[str, Any]] = {}

        for tier in tiers:
            tier_state_bytes = state_bytes
            tier_results: dict[str, bytes] = {}
            for offset in range(0, len(tier), effective_max_parallelism):
                # Ray task workers receive a strict source-bound snapshot of the
                # live host run. The older context metadata remains available
                # only to the store-only checkpoint task below.
                worker_context_meta = serialize_timeout_context(
                    ctx,
                    expected_run_id=state.run_id,
                )
                worker_context_meta["workflow_id"] = workflow.workflow_id
                futures = []
                chunk_aliases: list[str] = []
                dispatches: dict[str, tuple[str, str, Any]] = {}
                for alias in tier[offset : offset + effective_max_parallelism]:
                    inv = invocations[alias]
                    if inv.timeout_s is not None:
                        raise ValueError("ray_parent_receipt_timeout_unsupported")
                    carrier = _inject_trace_carrier()
                    max_retries = inv.retry.max_retries if inv.retry is not None else 0
                    invocation_id = secrets.token_hex(32)
                    dispatch_digest = worker_dispatch_sha256(
                        node_id=str(inv.node_id),
                        alias=alias,
                        params=inv.params or {},
                        state_bytes=tier_state_bytes,
                        trace_carrier=carrier,
                        timeout_s=None,
                        max_retries=max_retries,
                        context_meta=worker_context_meta,
                    )
                    dispatches[alias] = (
                        invocation_id,
                        dispatch_digest,
                        ctx.run._owner_snapshot_ref,
                    )

                    task_ref = execute_node_task
                    future = task_ref.remote(
                        node_id=str(inv.node_id),
                        alias=alias,
                        params=inv.params or {},
                        state_bytes=tier_state_bytes,
                        trace_carrier=carrier,
                        timeout_s=None,
                        max_retries=max_retries,
                        context_meta=ctx_meta,
                        worker_context_meta=worker_context_meta,
                        worker_invocation_id=invocation_id,
                        worker_dispatch_sha256=dispatch_digest,
                    )
                    futures.append(future)
                    chunk_aliases.append(alias)

                # Wait for all nodes in this chunk with error classification.
                results = await asyncio.gather(
                    *[asyncio.wrap_future(f.future()) for f in futures],
                    return_exceptions=True,
                )
                # Decode and bind every returned receipt before the first parent
                # write. A snapshot update changes the owner's source ref; with
                # multiple sibling receipts, admit that one last and refuse
                # multiple independently-created snapshots as a whole chunk.
                from polisyos.scientist.orchestration.engine.retry import (
                    _admit_worker_execution_receipt,
                    _worker_node_error,
                )

                receipt_items: list[tuple[str, bytes, tuple[str, str, Any], list[Any]]] = []
                exceptions = [item for item in results if isinstance(item, BaseException)]
                for alias, item in zip(chunk_aliases, results, strict=False):
                    if isinstance(item, BaseException):
                        continue
                    try:
                        (
                            outcome_bytes,
                            _error_payload,
                            receipt_invocation_id,
                            receipt_dispatch,
                            receipt_owner_ref,
                            records,
                        ) = deserialize_worker_execution_receipt(item)
                        invocation_id, expected_dispatch, owner_ref = dispatches[alias]
                        if (
                            receipt_invocation_id != invocation_id
                            or receipt_dispatch != expected_dispatch
                            or receipt_owner_ref != owner_ref
                        ):
                            raise ValueError("ray_worker_receipt_binding_mismatch")
                        if outcome_bytes is not None:
                            outcome = deserialize_outcome(outcome_bytes)
                            if outcome.state.run_id != state.run_id:
                                raise ValueError("ray_worker_outcome_run_binding_mismatch")
                        if _error_payload is not None:
                            if not isinstance(_error_payload, dict):
                                raise ValueError("ray_worker_error_payload_invalid")
                            _worker_node_error(
                                _error_payload,
                                expected_run_id=state.run_id,
                            )
                        if outcome_bytes is None and _error_payload is None:
                            raise ValueError("ray_worker_receipt_result_missing")
                    except (TypeError, ValueError) as exc:
                        raise RuntimeError("ray_worker_receipt_invalid") from exc
                    receipt_items.append((alias, item, dispatches[alias], records))

                snapshot_receipts = [
                    entry
                    for entry in receipt_items
                    if any(record.event == "RUN_CONTEXT_SNAPSHOT" for record in entry[3])
                ]
                if len(snapshot_receipts) > 1:
                    raise RuntimeError("ray_worker_sibling_snapshot_conflict")
                if snapshot_receipts:
                    receipt_items = [
                        entry for entry in receipt_items if entry not in snapshot_receipts
                    ] + snapshot_receipts

                receipt_errors: list[BaseException] = []
                for alias, item, dispatch, _records in receipt_items:
                    invocation_id, expected_dispatch, owner_ref = dispatch
                    try:
                        outcome = _admit_worker_execution_receipt(
                            ctx,
                            item,
                            invocation_id=invocation_id,
                            expected_dispatch=expected_dispatch,
                            owner_snapshot_ref=owner_ref,
                            expected_run_id=state.run_id,
                        )
                    except Exception as exc:
                        receipt_errors.append(exc)
                        continue
                    tier_results[alias] = serialize_outcome(outcome)

                exceptions.extend(receipt_errors)
                for exc in exceptions:
                    from polisyos.scientist.orchestration.engine.runner.error_classifier import (
                        classify_remote_error,
                    )

                    category = classify_remote_error(exc)
                    _logger.error("Ray tier execution failed (%s): %s", category.value, exc)
                if exceptions:
                    raise exceptions[0]

            # Merge parallel node results into unified state
            if tier_results:
                node_reports_by_alias.update(
                    project_distributed_node_outcomes(
                        workflow=workflow,
                        tier_aliases=tier,
                        outcome_bytes_by_alias=tier_results,
                    )
                )
                if checkpoint_hook is not None and checkpoint_hook_meta is not None:
                    merge_result = await asyncio.wrap_future(
                        merge_checkpoint_tier_task.remote(
                            {
                                "workflow_spec_json": workflow.model_dump(mode="json"),
                                "tier_aliases": list(tier),
                                "result_bytes_by_alias": tier_results,
                                "base_state_bytes": tier_state_bytes,
                                "context_meta": ctx_meta,
                                "workflow_fingerprint": workflow_fingerprint,
                                "completed_nodes": completed_nodes,
                                "merge_conflict_policy": self._merge_conflict_policy.value,
                                "checkpoint_hook_meta": checkpoint_hook_meta,
                                "result_format": "node_outcome",
                                "trace_carrier": _inject_trace_carrier(),
                            }
                        ).future()
                    )
                    state_bytes = merge_result["state_bytes"]
                    completed_nodes = list(merge_result.get("completed_nodes") or completed_nodes)
                    checkpoint_hook_meta = merge_result.get("checkpoint_hook_meta")
                    should_abort = bool(merge_result.get("should_abort"))
                else:
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
                        result_format="node_outcome",
                    )
                    state_bytes = tier_result.state_bytes
                    completed_nodes = tier_result.completed_nodes
                    should_abort = tier_result.should_abort
                if should_abort:
                    break

        run_id = getattr(state, "run_id", "unknown")
        return build_distributed_execution_result(
            workflow=workflow,
            run_id=run_id,
            state_bytes=state_bytes,
            node_reports_by_alias=node_reports_by_alias,
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
            component="engine.runner.ray",
            operation="inject_trace_carrier",
            reason="trace_carrier_injection_failed",
            exc=exc,
            log=_logger,
        )
        return carrier
    return carrier

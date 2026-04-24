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
from typing import Any

from pydantic import ValidationError

try:
    import ray

    _HAS_RAY = True
except ImportError:
    _HAS_RAY = False

from polisyos.scientist.engine.runner.distributed_tier import (
    merge_and_checkpoint_tier,
    seed_runner_cache,
)
from polisyos.scientist.engine.runner.protocol import RunnerHealth
from polisyos.scientist.engine.runner.serialization import (
    deserialize_state,
    serialize_context_meta,
    serialize_state,
)
from polisyos.scientist.engine.state_merge import MergeConflictPolicy
from polisyos.scientist.error_semantics import emit_degraded_path

_logger = logging.getLogger(__name__)
_TRACE_IMPORT_ERRORS = (ImportError, ModuleNotFoundError, AttributeError)
_TRACE_RUNTIME_ERRORS = (RuntimeError, TypeError, ValueError)
_RAY_PROBE_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValidationError, ValueError)


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
        context_meta: dict[str, Any],
    ) -> bytes:
        """Execute a single scientist node as a Ray remote task.

        Returns serialised ``NodeOutcome`` bytes.
        """
        from polisyos.scientist.engine.runner._activity_worker import (
            run_node_in_worker_sync,
        )

        payload = {
            "node_id": node_id,
            "alias": alias,
            "params": params,
            "state_bytes": state_bytes,
            "trace_carrier": trace_carrier,
            "timeout_s": timeout_s,
            "context_meta": context_meta,
        }
        return run_node_in_worker_sync(payload)

    @ray.remote
    def merge_checkpoint_tier_task(payload: dict[str, Any]) -> dict[str, Any]:
        """Merge and checkpoint one tier as a Ray remote task."""
        from polisyos.scientist.engine.runner._activity_worker import (
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

        try:
            self._ensure_init()
            t0 = time.monotonic()
            resources = ray.cluster_resources()
            latency = (time.monotonic() - t0) * 1000
            cpu_count = int(resources.get("CPU", 0))
            return RunnerHealth(
                backend="ray",
                healthy=True,
                latency_ms=round(latency, 2),
                worker_count=cpu_count,
                message=f"cluster CPUs={cpu_count}",
            )
        except _RAY_PROBE_ERRORS as exc:
            return RunnerHealth(
                backend="ray",
                healthy=False,
                message=f"probe failed: {exc}",
            )

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
        from polisyos.scientist.engine.checkpoint import (
            compute_workflow_fingerprint,
            serialize_checkpoint_hook_runtime_metadata,
        )
        from polisyos.scientist.engine.topo import topo_sort_tiers

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

        for tier in tiers:
            tier_state_bytes = state_bytes
            tier_results: dict[str, bytes] = {}
            for offset in range(0, len(tier), effective_max_parallelism):
                futures = []
                chunk_aliases: list[str] = []
                for alias in tier[offset : offset + effective_max_parallelism]:
                    inv = invocations[alias]
                    carrier = _inject_trace_carrier()

                    task_ref = execute_node_task
                    if inv.timeout_s is not None:
                        task_ref = execute_node_task.options(
                            timeout=inv.timeout_s,
                        )
                    future = task_ref.remote(
                        node_id=str(inv.node_id),
                        alias=alias,
                        params=inv.params or {},
                        state_bytes=tier_state_bytes,
                        trace_carrier=carrier,
                        timeout_s=inv.timeout_s,
                        context_meta=ctx_meta,
                    )
                    futures.append(future)
                    chunk_aliases.append(alias)

                # Wait for all nodes in this chunk with error classification.
                results = await asyncio.gather(
                    *[asyncio.wrap_future(f.future()) for f in futures],
                    return_exceptions=True,
                )
                for alias, item in zip(chunk_aliases, results, strict=False):
                    if not isinstance(item, BaseException):
                        tier_results[alias] = item
                exceptions = [item for item in results if isinstance(item, BaseException)]
                for exc in exceptions:
                    from polisyos.scientist.engine.runner.error_classifier import (
                        classify_remote_error,
                    )

                    category = classify_remote_error(exc)
                    _logger.error("Ray tier execution failed (%s): %s", category.value, exc)
                if exceptions:
                    raise exceptions[0]

            # Merge parallel node results into unified state
            if tier_results:
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
                                "trace_carrier": _inject_trace_carrier(),
                            }
                        ).future()
                    )
                    state_bytes = merge_result["state_bytes"]
                    completed_nodes = list(merge_result.get("completed_nodes") or completed_nodes)
                    checkpoint_hook_meta = merge_result.get("checkpoint_hook_meta")
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
                    )
                    state_bytes = tier_result.state_bytes
                    completed_nodes = tier_result.completed_nodes

        final_state = deserialize_state(state_bytes)

        from polisyos.scientist.engine.executor import (
            WorkflowExecutionResult,
            WorkflowReport,
        )

        run_id = getattr(state, "run_id", "unknown")
        report = WorkflowReport(
            workflow_id=workflow.workflow_id,
            run_id=run_id,
            error_policy=workflow.error_policy,
            status="ok",
            nodes=[],
        )
        return WorkflowExecutionResult(state=final_state, report=report)


def _inject_trace_carrier() -> dict[str, str]:
    carrier: dict[str, str] = {}
    try:
        from polisyos.core.observability.propagation import inject_headers

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

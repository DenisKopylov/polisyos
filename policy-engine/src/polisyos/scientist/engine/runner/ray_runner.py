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
from typing import TYPE_CHECKING, Any

try:
    import ray

    _HAS_RAY = True
except ImportError:
    _HAS_RAY = False

from polisyos.scientist.engine.runner.protocol import RunnerHealth
from polisyos.scientist.engine.runner.serialization import (
    deserialize_state,
    serialize_context_meta,
    serialize_state,
)

if TYPE_CHECKING:
    from polisyos.scientist.engine.context import ExecutionContext
    from polisyos.scientist.engine.executor import WorkflowExecutionResult
    from polisyos.scientist.engine.registry import NodeRegistry
    from polisyos.scientist.engine.state import ExperimentState
    from polisyos.scientist.engine.workflow_spec import WorkflowSpec

_logger = logging.getLogger(__name__)


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
    ) -> None:
        if not _HAS_RAY:
            raise ImportError(
                "ray is required for the Ray runner backend.  "
                "Install it with: pip install ray"
            )
        self._address = address
        self._namespace = namespace
        self._max_parallelism = max_parallelism
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
        except Exception as exc:  # noqa: BLE001
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
        max_parallelism: int | None = None,
    ) -> Any:  # WorkflowExecutionResult
        """Execute the workflow by dispatching nodes to Ray workers."""
        self._ensure_init()

        from polisyos.scientist.engine.topo import topo_sort_tiers
        from polisyos.scientist.engine.workflow_spec import NodeInvocation

        ctx_meta = serialize_context_meta(ctx)
        state_bytes = serialize_state(state)

        invocations = {inv.alias: inv for inv in workflow.nodes}
        tiers = topo_sort_tiers(invocations)

        for tier in tiers:
            futures = []
            for alias in tier:
                inv = invocations[alias]
                # Inject W3C TraceContext into carrier for cross-process propagation
                carrier: dict[str, str] = {}
                try:
                    from polisyos.core.observability.propagation import inject_headers
                    inject_headers(carrier)
                except Exception:  # noqa: BLE001
                    pass

                task_ref = execute_node_task
                if inv.timeout_s is not None:
                    task_ref = execute_node_task.options(
                        timeout=inv.timeout_s,
                    )
                future = task_ref.remote(
                    node_id=str(inv.node_id),
                    alias=alias,
                    params=inv.params or {},
                    state_bytes=state_bytes,
                    trace_carrier=carrier,
                    timeout_s=inv.timeout_s,
                    context_meta=ctx_meta,
                )
                futures.append(future)

            # Wait for all nodes in this tier with error classification
            try:
                results = await asyncio.gather(
                    *[asyncio.wrap_future(f.future()) for f in futures]
                )
            except Exception as exc:  # noqa: BLE001
                from polisyos.scientist.engine.runner.error_classifier import (
                    classify_remote_error,
                    RemoteErrorCategory,
                )

                category = classify_remote_error(exc)
                _logger.error(
                    "Ray tier execution failed (%s): %s", category.value, exc
                )
                if category is RemoteErrorCategory.FATAL:
                    raise
                raise

            # Merge parallel node results into unified state
            if results:
                from polisyos.scientist.engine.runner.state_merge import merge_tier_states

                state_bytes = merge_tier_states(state_bytes, list(results))

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

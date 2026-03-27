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
from typing import TYPE_CHECKING, Any

try:
    from temporalio import activity, workflow
    from temporalio.client import Client as TemporalClient
    from temporalio.common import RetryPolicy as TemporalRetryPolicy

    _HAS_TEMPORAL = True
except ImportError:
    _HAS_TEMPORAL = False

from polisyos.scientist.engine.runner.protocol import RunnerHealth
from polisyos.scientist.engine.runner.serialization import (
    deserialize_outcome,
    deserialize_state,
    serialize_context_meta,
    serialize_outcome,
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


# ---------------------------------------------------------------------------
# Activity definition
# ---------------------------------------------------------------------------

if _HAS_TEMPORAL:

    @activity.defn(name="scientist_execute_node")
    async def execute_node_activity(payload_dict: dict[str, Any]) -> bytes:
        """Execute a single scientist node as a Temporal activity.

        Reconstructs state from bytes, executes the node in-process,
        and returns the serialised ``NodeOutcome``.
        """
        from polisyos.scientist.engine.runner._activity_worker import (
            run_node_in_worker,
        )

        return await run_node_in_worker(payload_dict)


# ---------------------------------------------------------------------------
# Workflow definition
# ---------------------------------------------------------------------------

if _HAS_TEMPORAL:

    @workflow.defn(name="ScientistWorkflow")
    class ScientistWorkflow:
        """Temporal workflow that executes a scientist DAG tier-by-tier."""

        @workflow.run
        async def run(self, payload_dict: dict[str, Any]) -> bytes:
            """Execute the full DAG and return final state bytes."""
            from polisyos.scientist.engine.topo import topo_sort_tiers
            from polisyos.scientist.engine.workflow_spec import (
                NodeInvocation,
                WorkflowSpec,
            )

            spec = WorkflowSpec.model_validate(payload_dict["workflow_spec_json"])
            state_bytes: bytes = payload_dict["initial_state_bytes"]
            max_par: int = payload_dict.get("max_parallelism", 4)
            ctx_meta: dict[str, Any] = payload_dict.get("context_meta", {})

            invocations = {inv.alias: inv for inv in spec.nodes}
            tiers = topo_sort_tiers(invocations)

            for tier in tiers:
                # Build activity payloads for each node in this tier
                tasks = []
                for alias in tier:
                    inv = invocations[alias]
                    # Inject W3C TraceContext — supplements Temporal's native
                    # context propagation (via temporalio.contrib.opentelemetry
                    # interceptor) for cases where the interceptor is not configured.
                    _carrier: dict[str, str] = {}
                    try:
                        from polisyos.core.observability.propagation import inject_headers
                        inject_headers(_carrier)
                    except Exception:  # noqa: BLE001
                        pass

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
                    timeout = timedelta(seconds=inv.timeout_s) if inv.timeout_s else timedelta(minutes=10)
                    tasks.append(
                        workflow.execute_activity(
                            execute_node_activity,
                            act_payload,
                            start_to_close_timeout=timeout,
                            retry_policy=retry_policy,
                        )
                    )

                # Execute tier in parallel (up to max_parallelism)
                # Temporal handles concurrency natively per activity
                results = await asyncio.gather(*tasks)

                # Merge parallel node results into unified state
                if results:
                    from polisyos.scientist.engine.runner.state_merge import merge_tier_states

                    state_bytes = merge_tier_states(state_bytes, list(results))

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
        self._client: TemporalClient | None = None

    async def _get_client(self) -> TemporalClient:
        if self._client is None:
            self._client = await TemporalClient.connect(
                self._server_url, namespace=self._namespace,
            )
        return self._client

    async def health_check(self) -> RunnerHealth:
        """Probe Temporal server health."""
        import time

        try:
            t0 = time.monotonic()
            client = await self._get_client()
            # Use service health check RPC
            await client.service_client.check_health()
            latency = (time.monotonic() - t0) * 1000
            return RunnerHealth(
                backend="temporal",
                healthy=True,
                latency_ms=round(latency, 2),
                message=f"namespace={self._namespace}",
            )
        except Exception as exc:  # noqa: BLE001
            return RunnerHealth(
                backend="temporal",
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
        """Start a Temporal workflow and wait for completion."""
        client = await self._get_client()
        ctx_meta = serialize_context_meta(ctx)
        state_bytes = serialize_state(state)

        payload = {
            "workflow_spec_json": workflow.model_dump(),
            "initial_state_bytes": state_bytes,
            "context_meta": ctx_meta,
            "max_parallelism": max_parallelism or self._max_parallelism,
        }

        run_id = getattr(state, "run_id", "unknown")
        result_bytes: bytes = await client.execute_workflow(
            ScientistWorkflow.run,
            payload,
            id=f"scientist-{run_id}",
            task_queue=self._task_queue,
        )

        final_state = deserialize_state(result_bytes)

        # Build a minimal WorkflowExecutionResult
        from polisyos.scientist.engine.executor import (
            WorkflowExecutionResult,
            WorkflowReport,
        )

        report = WorkflowReport(
            workflow_id=workflow.workflow_id,
            run_id=run_id,
            error_policy=workflow.error_policy,
            status="ok",
            nodes=[],
        )
        return WorkflowExecutionResult(state=final_state, report=report)

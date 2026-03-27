"""Workflow runner protocol — backend-agnostic execution interface.

Defines ``WorkflowRunnerBackend`` for dispatching full workflow execution
and ``RemoteNodeExecutor`` for dispatching individual nodes to remote workers.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from polisyos.scientist.engine.retry import RetryPolicy

# We use string annotations for heavy types to keep this module lightweight.
# Concrete implementations import the real types.

type JsonValue = str | int | float | bool | None | dict[str, Any] | list[Any]


class RunnerHealth(BaseModel):
    """Health status of a workflow runner backend."""

    model_config = ConfigDict(extra="forbid")

    backend: str
    healthy: bool
    latency_ms: float | None = None
    worker_count: int | None = None
    message: str = ""


@runtime_checkable
class WorkflowRunnerBackend(Protocol):
    """Backend that can execute a full scientist workflow.

    Implementations:
    * ``LocalWorkflowRunner`` — delegates to ``AsyncWorkflowExecutor``
    * ``TemporalWorkflowRunner`` — Temporal activities per node
    * ``RayWorkflowRunner`` — Ray remote tasks per node
    """

    async def execute_workflow(
        self,
        workflow: Any,  # WorkflowSpec
        state: Any,  # ExperimentState
        ctx: Any,  # ExecutionContext
        registry: Any,  # NodeRegistry
        *,
        checkpoint_hook: Any | None = None,  # CheckpointHook
        max_parallelism: int = 4,
    ) -> Any:  # WorkflowExecutionResult  # pragma: no cover - protocol
        ...

    async def health_check(self) -> RunnerHealth:  # pragma: no cover - protocol
        """Probe the runner backend and return its health status."""
        ...


@runtime_checkable
class RemoteNodeExecutor(Protocol):
    """Interface for executing a single node on a remote worker.

    Used by distributed runners (Temporal, Ray) to ship node execution
    across process boundaries.  The ``trace_carrier`` dict carries W3C
    TraceContext headers for distributed tracing correlation.
    """

    async def execute_node(
        self,
        node_id: str,
        alias: str,
        params: dict[str, JsonValue],
        state_bytes: bytes,
        trace_carrier: dict[str, str],
        *,
        timeout_s: float | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> Any:  # NodeOutcome  # pragma: no cover - protocol
        ...

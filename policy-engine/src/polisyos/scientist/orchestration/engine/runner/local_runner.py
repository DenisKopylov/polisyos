"""Local workflow runner — zero-overhead wrapper over AsyncWorkflowExecutor.

This is the default backend.  It delegates directly to the in-process
``AsyncWorkflowExecutor``, preserving identical semantics for checkpoint,
cache, retry, timeout, telemetry, and audit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutionResult
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner.protocol import RunnerHealth
from polisyos.scientist.orchestration.engine.runner.serialization import serialize_context_meta
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_merge import MergeConflictPolicy
from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

if TYPE_CHECKING:
    from datetime import datetime

    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.scientist.orchestration.engine.checkpoint import CheckpointHook
    from polisyos.scientist.orchestration.engine.context import ExecutionContext


class LocalWorkflowRunner:
    """Delegates to ``AsyncWorkflowExecutor``.  No distributed overhead."""

    def __init__(
        self,
        *,
        max_parallelism: int = 4,
        merge_conflict_policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
        workflow_deadline_at: datetime | None = None,
        budget_middleware: Any | None = None,
        workflow_execution_admission_ref: ArtifactRef | None = None,
        workflow_execution_admission_origin: tuple[ArtifactRef, WorkflowSpec] | None = None,
        strict_budget_attempts: bool = False,
        capture_workflow_execution_admission: bool = False,
    ) -> None:
        self._max_parallelism = max_parallelism
        self._merge_conflict_policy = merge_conflict_policy
        self._workflow_deadline_at = workflow_deadline_at
        self._budget_middleware = budget_middleware
        self._workflow_execution_admission_ref = workflow_execution_admission_ref
        self._workflow_execution_admission_origin = workflow_execution_admission_origin
        self._strict_budget_attempts = strict_budget_attempts
        self._capture_workflow_execution_admission = capture_workflow_execution_admission

    async def health_check(self) -> RunnerHealth:
        """Local runner is always healthy."""
        return RunnerHealth(backend="local", healthy=True, message="in-process")

    async def execute_workflow(
        self,
        workflow: WorkflowSpec,
        state: ExperimentState,
        ctx: ExecutionContext,
        registry: NodeRegistry,
        *,
        checkpoint_hook: CheckpointHook | None = None,
        checkpoint_cache_seed_refs: list[ArtifactRef] | None = None,
        max_parallelism: int | None = None,
    ) -> WorkflowExecutionResult:
        """Execute the workflow in-process via AsyncWorkflowExecutor."""
        effective_parallelism = max_parallelism or self._max_parallelism
        ctx_meta = serialize_context_meta(
            ctx,
            workflow_id=workflow.workflow_id,
            runner_backend="local",
        )
        if ctx.metrics is not None:
            ctx.metrics.record_trace_correlation(
                runner_backend="local",
                workflow_id=workflow.workflow_id,
                run_id=str(ctx_meta.get("run_id") or state.run_id),
                trace_id=ctx_meta.get("trace_id"),
                span_id=ctx_meta.get("span_id"),
            )
        executor = AsyncWorkflowExecutor(
            ctx,
            registry,
            checkpoint_hook=checkpoint_hook,
            checkpoint_cache_seed_refs=checkpoint_cache_seed_refs,
            max_parallelism=effective_parallelism,
            merge_conflict_policy=self._merge_conflict_policy,
            workflow_deadline_at=self._workflow_deadline_at,
            budget_middleware=self._budget_middleware,
            workflow_execution_admission_ref=self._workflow_execution_admission_ref,
            workflow_execution_admission_origin=self._workflow_execution_admission_origin,
            strict_budget_attempts=self._strict_budget_attempts,
            capture_workflow_execution_admission=self._capture_workflow_execution_admission,
        )
        return await executor.execute(workflow, state)

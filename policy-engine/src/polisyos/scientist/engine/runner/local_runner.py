"""Local workflow runner — zero-overhead wrapper over AsyncWorkflowExecutor.

This is the default backend.  It delegates directly to the in-process
``AsyncWorkflowExecutor``, preserving identical semantics for checkpoint,
cache, retry, timeout, telemetry, and audit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.executor import WorkflowExecutionResult
from polisyos.scientist.engine.registry import NodeRegistry
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import WorkflowSpec

from polisyos.scientist.engine.runner.protocol import RunnerHealth

if TYPE_CHECKING:
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.scientist.engine.checkpoint import CheckpointHook


class LocalWorkflowRunner:
    """Delegates to ``AsyncWorkflowExecutor``.  No distributed overhead."""

    def __init__(self, *, max_parallelism: int = 4) -> None:
        self._max_parallelism = max_parallelism

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
        executor = AsyncWorkflowExecutor(
            ctx,
            registry,
            checkpoint_hook=checkpoint_hook,
            checkpoint_cache_seed_refs=checkpoint_cache_seed_refs,
            max_parallelism=effective_parallelism,
        )
        return await executor.execute(workflow, state)

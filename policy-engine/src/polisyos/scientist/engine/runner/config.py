"""Runner backend configuration and factory.

Follows the same pattern as ``locks/config.py``: declarative Pydantic model
with ``from_env()`` classmethod and a ``build_workflow_runner()`` factory.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.scientist.engine.runner.protocol import WorkflowRunnerBackend


class WorkflowRunnerConfig(BaseModel):
    """Declarative workflow-runner backend configuration."""

    model_config = ConfigDict(extra="forbid")

    backend: Literal["local", "temporal", "ray"] = "local"

    # --- Temporal ---
    temporal_namespace: str | None = None
    temporal_task_queue: str | None = None
    temporal_server_url: str | None = None

    # --- Ray ---
    ray_address: str | None = None
    ray_namespace: str | None = None

    # --- Shared ---
    max_parallelism: int = Field(default=4, ge=1, le=64)

    # --- Fallback ---
    fallback_to_local: bool = True

    @classmethod
    def from_env(cls) -> WorkflowRunnerConfig:
        """Build config from environment variables."""
        max_par_raw = os.environ.get("POLISYOS_RUNNER_MAX_PARALLELISM", "4")
        return cls(
            backend=os.environ.get("POLISYOS_RUNNER_BACKEND", "local"),  # type: ignore[arg-type]
            temporal_namespace=os.environ.get("POLISYOS_TEMPORAL_NAMESPACE"),
            temporal_task_queue=os.environ.get("POLISYOS_TEMPORAL_TASK_QUEUE"),
            temporal_server_url=os.environ.get("POLISYOS_TEMPORAL_SERVER_URL"),
            ray_address=os.environ.get("POLISYOS_RAY_ADDRESS"),
            ray_namespace=os.environ.get("POLISYOS_RAY_NAMESPACE"),
            max_parallelism=int(max_par_raw),
        )


def _maybe_wrap_fallback(
    runner: WorkflowRunnerBackend,
    config: WorkflowRunnerConfig,
) -> WorkflowRunnerBackend:
    """Wrap a distributed runner with fallback-to-local if configured."""
    if not config.fallback_to_local:
        return runner
    from polisyos.scientist.engine.runner.fallback_runner import FallbackWorkflowRunner

    return FallbackWorkflowRunner(
        runner,
        max_parallelism=config.max_parallelism,
    )


def build_workflow_runner(config: WorkflowRunnerConfig) -> WorkflowRunnerBackend:
    """Construct a ``WorkflowRunnerBackend`` from declarative config."""
    if config.backend == "local":
        from polisyos.scientist.engine.runner.local_runner import LocalWorkflowRunner

        return LocalWorkflowRunner(max_parallelism=config.max_parallelism)

    if config.backend == "temporal":
        from polisyos.scientist.engine.runner.temporal_runner import TemporalWorkflowRunner

        if not config.temporal_server_url:
            raise ValueError("WorkflowRunnerConfig.temporal_server_url is required for temporal backend")
        runner = TemporalWorkflowRunner(
            server_url=config.temporal_server_url,
            namespace=config.temporal_namespace or "default",
            task_queue=config.temporal_task_queue or "scientist-nodes",
            max_parallelism=config.max_parallelism,
        )
        return _maybe_wrap_fallback(runner, config)

    if config.backend == "ray":
        from polisyos.scientist.engine.runner.ray_runner import RayWorkflowRunner

        runner = RayWorkflowRunner(
            address=config.ray_address or "auto",
            namespace=config.ray_namespace or "polisyos",
            max_parallelism=config.max_parallelism,
        )
        return _maybe_wrap_fallback(runner, config)

    raise ValueError(f"Unknown runner backend: {config.backend!r}")

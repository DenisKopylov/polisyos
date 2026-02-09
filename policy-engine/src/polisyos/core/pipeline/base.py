from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

StateT = TypeVar("StateT")


class PipelineError(RuntimeError):
    """Base exception for shared pipeline orchestration."""


class DuplicateStageError(PipelineError):
    """Raised when a stage with the same identifier already exists."""


class UnknownStageError(PipelineError):
    """Raised when a stage or dependency is missing."""


class PipelineCycleError(PipelineError):
    """Raised when the DAG contains a cycle."""


class StageExecutionError(PipelineError):
    """Raised when stage execution fails and no custom handler is provided."""

    def __init__(self, *, stage_id: str, cause: Exception) -> None:
        super().__init__(f"Stage '{stage_id}' failed: {cause}")
        self.stage_id = stage_id
        self.cause = cause


@dataclass(slots=True)
class PipelineRun(Generic[StateT]):
    """Result of a pipeline run."""

    state: StateT
    executed_stage_ids: list[str] = field(default_factory=list)
    short_circuited: bool = False

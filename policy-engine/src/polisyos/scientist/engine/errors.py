from __future__ import annotations

from polisyos.core.errors import ErrorCategory, PolicyOSError


class EngineError(PolicyOSError):
    """Base class for Scientist engine errors."""

    default_stage = "scientist.engine"
    default_category = ErrorCategory.FATAL


class WorkflowSpecError(EngineError):
    """Workflow spec validation/build errors."""

    default_stage = "scientist.engine.workflow_spec"
    default_category = ErrorCategory.VALIDATION


class UnknownNodeError(WorkflowSpecError):
    """Raised when a node_id cannot be resolved in the registry."""


class DuplicateAliasError(WorkflowSpecError):
    """Raised when NodeInvocation aliases are duplicated."""


class MissingDependencyError(WorkflowSpecError):
    """Raised when a dependency alias is missing from workflow."""


class CycleDetectedError(WorkflowSpecError):
    """Raised when a cycle is detected in the workflow graph."""


class NodeExecutionError(EngineError):
    """Raised when a node fails or returns an invalid outcome."""


class NodeTimeoutError(NodeExecutionError):
    """Node exceeded its timeout_s."""


class RetryExhaustedError(NodeExecutionError):
    """All retries exhausted, last error attached."""

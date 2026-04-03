"""Public engine errors module API."""
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


class CircuitBreakerOpenError(EngineError):
    """Raised when a circuit breaker is open and rejects a request."""

    default_stage = "scientist.engine.circuit_breaker"
    default_category = ErrorCategory.TRANSIENT


class WorkflowTimeoutError(EngineError):
    """Workflow exceeded its overall timeout."""

    default_stage = "scientist.engine.workflow"
    default_category = ErrorCategory.TRANSIENT


class StateMergeConflictError(EngineError):
    """Two parallel node results modified the same state key."""

    default_stage = "scientist.engine.runner.state_merge"
    default_category = ErrorCategory.FATAL


class DeserializationError(EngineError):
    """Failed to deserialise state or outcome from bytes."""

    default_stage = "scientist.engine.runner.serialization"
    default_category = ErrorCategory.FATAL

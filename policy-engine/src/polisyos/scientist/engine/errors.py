from __future__ import annotations


class EngineError(Exception):
    """Base class for Scientist engine errors."""


class WorkflowSpecError(EngineError):
    """Workflow spec validation/build errors."""


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

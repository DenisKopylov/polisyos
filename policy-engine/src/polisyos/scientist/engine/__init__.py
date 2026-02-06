"""Scientist workflow engine (v0)."""

from __future__ import annotations

from polisyos.scientist.engine.errors import (
    CycleDetectedError,
    DuplicateAliasError,
    EngineError,
    MissingDependencyError,
    NodeExecutionError,
    UnknownNodeError,
    WorkflowSpecError,
)
from polisyos.scientist.engine.executor import WorkflowExecutor
from polisyos.scientist.engine.idempotency import (
    IDEMPOTENCY_CONTRACT_VERSION,
    NodeCacheEntry,
    NodeResultCache,
    compute_idempotency_key,
    compute_idempotency_payload,
    extract_state_slice,
)
from polisyos.scientist.engine.protocol import (
    Node,
    NodeError,
    NodeEvent,
    NodeOutcome,
    NodeSpec,
    NodeStatus,
)
from polisyos.scientist.engine.registry import NodeRegistry, discover_nodes
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.workflow_spec import NodeInvocation, WorkflowSpec

__all__ = [
    "Node",
    "NodeSpec",
    "NodeOutcome",
    "NodeStatus",
    "NodeEvent",
    "NodeError",
    "ExperimentState",
    "WorkflowSpec",
    "NodeInvocation",
    "NodeRegistry",
    "discover_nodes",
    "WorkflowExecutor",
    "EngineError",
    "WorkflowSpecError",
    "UnknownNodeError",
    "DuplicateAliasError",
    "MissingDependencyError",
    "CycleDetectedError",
    "NodeExecutionError",
    "IDEMPOTENCY_CONTRACT_VERSION",
    "compute_idempotency_key",
    "compute_idempotency_payload",
    "extract_state_slice",
    "NodeCacheEntry",
    "NodeResultCache",
]

"""Public workflows engine base module API."""
from __future__ import annotations

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class WorkflowEngine(Protocol):
    """
    Abstract workflow engine protocol.

    LangGraph is now just one implementation, not a hard dependency.
    This enables:
    - Unit testing with mock engines
    - Future migration to Temporal.io / Prefect
    - Simple loop-based implementations for search
    """

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run workflow to completion.

        Args:
            initial_state: Initial ExperimentState dict

        Returns:
            Final ExperimentState after workflow completion
        """

    def step(self, state: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
        """
        Execute single workflow step.

        Args:
            state: Current ExperimentState dict

        Returns:
            Tuple of (new_state, is_terminal) where is_terminal
            indicates if workflow has reached an end node.
        """

    @property
    def current_phase(self) -> str:
        """Current FSM phase (INTAKE, FRAME, EXECUTE, etc.)."""

    @property
    def current_node(self) -> str | None:
        """Currently executing node name, if any."""

    def reset(self) -> None:
        """Reset engine to initial state for reuse."""


class WorkflowEngineFactory(Protocol):
    """Factory for creating workflow engines."""

    def create(self, config: Dict[str, Any] | None = None) -> WorkflowEngine:
        """Create a new workflow engine instance."""


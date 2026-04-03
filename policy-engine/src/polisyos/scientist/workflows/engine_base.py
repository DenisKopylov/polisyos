"""Engine protocols for legacy workflow adapters and lightweight loop runners."""
from __future__ import annotations

from typing import Any, Dict, Protocol, runtime_checkable


@runtime_checkable
class WorkflowEngine(Protocol):
    """Define the minimal execution API shared by legacy workflow engines.

    LangGraph is only one implementation behind this protocol; callers can use
    mock engines in tests or loop-based engines for search prototypes as long as
    `run()`, `step()`, `current_phase`, and `current_node` are honored.
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
    """Construct protocol-compatible workflow engines from runtime config."""

    def create(self, config: Dict[str, Any] | None = None) -> WorkflowEngine:
        """Create a new workflow engine instance."""

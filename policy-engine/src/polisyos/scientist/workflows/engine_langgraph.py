from __future__ import annotations

from typing import Any, Dict

from langgraph.graph.graph import CompiledGraph

from polisyos.scientist.kernel.fsm import Phase


class LangGraphEngine:
    """
    LangGraph adapter implementing WorkflowEngine protocol.

    Wraps existing workflow.py build_workflow() with protocol-compliant interface.
    """

    def __init__(self, compiled_graph: CompiledGraph):
        self._graph = compiled_graph
        self._current_phase: str = Phase.INTAKE.value
        self._current_node: str | None = None
        self._last_state: Dict[str, Any] | None = None

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Run workflow to completion."""
        result = self._graph.invoke(initial_state)
        self._last_state = result
        self._current_phase = result.get("phase", Phase.DECIDE.value)
        self._current_node = None
        return result

    def step(self, state: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
        """
        Execute single step.

        Note: LangGraph's compiled graph doesn't natively support single-step
        execution. We use stream() to get incremental updates.
        """
        events = list(self._graph.stream(state))
        if not events:
            return state, True

        last_event = events[-1]
        if isinstance(last_event, dict):
            for node_name, node_state in last_event.items():
                self._current_node = node_name
                if isinstance(node_state, dict):
                    self._last_state = {**state, **node_state}
                    self._current_phase = self._last_state.get("phase", self._current_phase)

        last_state = self._last_state or state
        is_terminal = (
            self._current_node in {"pack_decision", "__end__"}
            or last_state.get("pruned", False)
        )
        return last_state, is_terminal

    @property
    def current_phase(self) -> str:
        return self._current_phase

    @property
    def current_node(self) -> str | None:
        return self._current_node

    def reset(self) -> None:
        """Reset engine state."""
        self._current_phase = Phase.INTAKE.value
        self._current_node = None
        self._last_state = None

    @classmethod
    def from_existing_workflow(cls) -> "LangGraphEngine":
        """Legacy adapter entrypoint removed."""
        raise RuntimeError(
            "LangGraph legacy workflow was removed. Use polisyos.scientist.run_experiment() engine DAG."
        )


class LangGraphEngineFactory:
    """Factory for LangGraph engines."""

    def __init__(self, build_func=None):
        self._build_func = build_func

    def create(self, config: Dict[str, Any] | None = None) -> LangGraphEngine:
        if self._build_func:
            graph = self._build_func()
        else:
            raise RuntimeError(
                "LangGraph legacy workflow was removed. Use scientist.workflows.default engine DAG."
            )
        return LangGraphEngine(graph)

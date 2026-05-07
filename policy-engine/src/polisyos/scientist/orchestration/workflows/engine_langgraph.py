"""LangGraph-backed adapter that satisfies the legacy `WorkflowEngine` protocol."""

from __future__ import annotations

from typing import Any

from langgraph.graph.graph import CompiledGraph

from polisyos.scientist.orchestration.kernel.fsm import Phase


class LangGraphEngine:
    """Wrap a compiled LangGraph DAG behind the `WorkflowEngine` interface.

    This adapter exists for legacy integrations that still expect a stateful
    engine object. New production Scientist runs should prefer the engine DAG in
    `polisyos.scientist.orchestration.workflows.builder`.
    """

    def __init__(self, compiled_graph: CompiledGraph):
        self._graph = compiled_graph
        self._current_phase: str = Phase.INTAKE.value
        self._current_node: str | None = None
        self._last_state: dict[str, Any] | None = None

    def run(self, initial_state: dict[str, Any]) -> dict[str, Any]:
        """Invoke the compiled graph once and return the final merged state."""
        result = self._graph.invoke(initial_state)
        self._last_state = result
        self._current_phase = result.get("phase", Phase.DECIDE.value)
        self._current_node = None
        return result

    def step(self, state: dict[str, Any]) -> tuple[dict[str, Any], bool]:
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
        is_terminal = self._current_node in {"pack_decision", "__end__"} or last_state.get(
            "pruned", False
        )
        return last_state, is_terminal

    @property
    def current_phase(self) -> str:
        return self._current_phase

    @property
    def current_node(self) -> str | None:
        return self._current_node

    def reset(self) -> None:
        """Reset cached phase/node pointers so the adapter can be reused."""
        self._current_phase = Phase.INTAKE.value
        self._current_node = None
        self._last_state = None

    @classmethod
    def from_existing_workflow(cls) -> LangGraphEngine:
        """Reject the removed legacy builder path and point callers to engine DAGs."""
        raise RuntimeError(
            "LangGraph legacy workflow was removed. Use polisyos.scientist.run_experiment() engine DAG."
        )


class LangGraphEngineFactory:
    """Create `LangGraphEngine` wrappers from a supplied graph builder callback."""

    def __init__(self, build_func=None):
        self._build_func = build_func

    def create(self, config: dict[str, Any] | None = None) -> LangGraphEngine:
        if self._build_func:
            graph = self._build_func()
        else:
            raise RuntimeError(
                "LangGraph legacy workflow was removed. Use scientist.workflows.default engine DAG."
            )
        return LangGraphEngine(graph)

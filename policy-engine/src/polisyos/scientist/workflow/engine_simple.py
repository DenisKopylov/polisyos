from __future__ import annotations

from typing import Any, Callable, Dict, List

from polisyos.scientist.kernel.fsm import Phase


class SimpleLoopEngine:
    """
    Minimal workflow engine for search iterations.

    Executes a sequence of node functions without LangGraph overhead.
    Useful for:
    - Unit testing search loop mechanics
    - Rapid iteration during development
    - Surrogate evaluations in CheapStage
    """

    def __init__(
        self,
        nodes: List[tuple[str, Callable[[Dict[str, Any]], Dict[str, Any]]]],
        terminal_node: str = "pack_decision",
    ):
        self._nodes = nodes
        self._node_map = {name: fn for name, fn in nodes}
        self._terminal_node = terminal_node
        self._current_idx = 0
        self._current_phase = Phase.INTAKE.value

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Run all nodes sequentially."""
        state = initial_state
        for name, fn in self._nodes:
            state = fn(state)
            if state.get("pruned") or name == self._terminal_node:
                break
        return state

    def step(self, state: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
        """Execute single node."""
        if self._current_idx >= len(self._nodes):
            return state, True

        name, fn = self._nodes[self._current_idx]
        new_state = fn(state)
        self._current_idx += 1

        is_terminal = (
            name == self._terminal_node
            or new_state.get("pruned", False)
            or self._current_idx >= len(self._nodes)
        )
        return new_state, is_terminal

    @property
    def current_phase(self) -> str:
        return self._current_phase

    @property
    def current_node(self) -> str | None:
        if 0 <= self._current_idx < len(self._nodes):
            return self._nodes[self._current_idx][0]
        return None

    def reset(self) -> None:
        self._current_idx = 0
        self._current_phase = Phase.INTAKE.value

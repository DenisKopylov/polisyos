"""Topological ordering of tool calls based on declared dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["ToolDependencyGraph"]


@dataclass
class ToolDependencyGraph:
    """Defines prerequisite relationships between tools.

    ``edges`` maps a tool name to the list of tool names that must execute
    before it.  Tools absent from the mapping have no prerequisites.
    """

    edges: dict[str, list[str]] = field(default_factory=dict)

    def execution_order(self, requested: list[str]) -> list[str]:
        """Return *requested* tools sorted in a valid execution order.

        Tools whose prerequisites are not in *requested* are placed last
        (their dependencies are assumed already satisfied from previous
        iterations).
        """
        request_set = set(requested)
        in_degree: dict[str, int] = {name: 0 for name in requested}
        adj: dict[str, list[str]] = {name: [] for name in requested}

        for name in requested:
            for dep in self.edges.get(name, []):
                if dep in request_set:
                    in_degree[name] += 1
                    adj[dep].append(name)

        # Kahn's algorithm
        queue = [n for n in requested if in_degree[n] == 0]
        result: list[str] = []
        while queue:
            node = queue.pop(0)
            result.append(node)
            for successor in adj[node]:
                in_degree[successor] -= 1
                if in_degree[successor] == 0:
                    queue.append(successor)

        remaining = [n for n in requested if n not in set(result)]
        if remaining:
            cycle_nodes = ", ".join(dict.fromkeys(remaining))
            raise ValueError(f"cyclic tool dependencies detected: {cycle_nodes}")
        return result

    def can_execute(self, tool_name: str, completed: set[str]) -> bool:
        """Return ``True`` if all prerequisites for *tool_name* are met."""
        for dep in self.edges.get(tool_name, []):
            if dep not in completed:
                return False
        return True

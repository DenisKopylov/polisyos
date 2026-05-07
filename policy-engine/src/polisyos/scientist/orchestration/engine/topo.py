"""Tiered topological sort for parallel DAG execution.

Groups nodes into levels (tiers) using Kahn's algorithm. Nodes in the same
tier have no mutual dependencies and can potentially execute in parallel,
subject to write-safety checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.scientist.orchestration.engine.errors import CycleDetectedError

if TYPE_CHECKING:
    from polisyos.scientist.orchestration.engine.registry import NodeRegistry
    from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation


def topo_sort_tiers(invocations: dict[str, NodeInvocation]) -> list[list[str]]:
    """Kahn's algorithm, grouping by topological levels.

    Returns ``list[list[str]]`` — each inner list is a parallel tier of
    node aliases.
    """
    indegree: dict[str, int] = dict.fromkeys(invocations, 0)
    forward: dict[str, list[str]] = {alias: [] for alias in invocations}
    order_index = {alias: idx for idx, alias in enumerate(invocations.keys())}

    for alias, inv in invocations.items():
        for dep in inv.depends_on:
            forward[dep].append(alias)
            indegree[alias] += 1

    current_tier = sorted(
        [a for a, deg in indegree.items() if deg == 0],
        key=lambda a: order_index.get(a, 0),
    )

    tiers: list[list[str]] = []
    visited = 0

    while current_tier:
        tiers.append(list(current_tier))
        visited += len(current_tier)
        next_tier: list[str] = []
        for alias in current_tier:
            for nxt in forward[alias]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    next_tier.append(nxt)
        next_tier.sort(key=lambda a: order_index.get(a, 0))
        current_tier = next_tier

    if visited != len(invocations):
        raise CycleDetectedError("Cycle detected in workflow graph")

    return tiers


def validate_tier_write_safety(
    tier_aliases: list[str],
    registry: NodeRegistry,
    invocations: dict[str, NodeInvocation],
) -> tuple[bool, list[str]]:
    """Check that ``state_writes`` of nodes in a tier don't overlap.

    Returns ``(is_safe, conflict_keys)``.
    """
    if len(tier_aliases) <= 1:
        return True, []

    seen_writes: dict[str, str] = {}  # write_key -> alias that declared it
    conflicts: list[str] = []

    for alias in tier_aliases:
        inv = invocations[alias]
        node = registry.get(inv.node_id)
        for write_key in node.spec.state_writes:
            if write_key in seen_writes:
                conflicts.append(
                    f"{write_key} (written by both {seen_writes[write_key]} and {alias})"
                )
            else:
                seen_writes[write_key] = alias

    return len(conflicts) == 0, conflicts

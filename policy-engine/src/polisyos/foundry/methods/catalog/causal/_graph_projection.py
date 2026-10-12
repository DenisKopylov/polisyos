"""Public causal graph projection module API."""

from __future__ import annotations

from polisyos.ir.analytics.causal_graph import CausalGraphModel, project_graph_to_dag


def pag_to_dag_projection(
    graph: CausalGraphModel,
) -> tuple[CausalGraphModel, list[str]]:
    """Compatibility alias for the canonical graph-profile DAG projection."""
    return project_graph_to_dag(graph)


__all__ = ["pag_to_dag_projection"]

from __future__ import annotations

from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType


def pag_to_dag_projection(
    graph: CausalGraphModel,
) -> tuple[CausalGraphModel, list[str]]:
    """
    Project PAG/CPDAG uncertainty into a DAG approximation for DAG-only consumers.

    - X <-> Y becomes U_n -> X and U_n -> Y.
    - Uncertain endpoints (circle) are oriented as tail->arrow and flagged in metadata.
    """
    if graph.graph_type is GraphType.DAG and all(
        edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW for edge in graph.edges
    ):
        return graph, []

    new_edges = []
    latent_vars: list[str] = []
    used_nodes = set(graph.nodes)
    projection_stats = {
        "bidirected_replaced": 0,
        "uncertain_oriented": 0,
    }

    def _next_latent_name() -> str:
        index = 0
        while True:
            candidate = f"U_{index}"
            index += 1
            if candidate not in used_nodes:
                used_nodes.add(candidate)
                return candidate

    for edge in graph.edges:
        if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW:
            latent_name = _next_latent_name()
            latent_vars.append(latent_name)
            projection_stats["bidirected_replaced"] += 1
            edge_label = f"{edge.src}<->{edge.dst}"
            base_meta = dict(edge.metadata)
            new_edges.append(
                edge.model_copy(
                    update={
                        "src": latent_name,
                        "dst": edge.src,
                        "mark_src": EdgeMark.TAIL,
                        "mark_dst": EdgeMark.ARROW,
                        "metadata": {
                            **base_meta,
                            "latent_proxy": True,
                            "original_bidirected": edge_label,
                        },
                    }
                )
            )
            new_edges.append(
                edge.model_copy(
                    update={
                        "src": latent_name,
                        "dst": edge.dst,
                        "mark_src": EdgeMark.TAIL,
                        "mark_dst": EdgeMark.ARROW,
                        "metadata": {
                            **base_meta,
                            "latent_proxy": True,
                            "original_bidirected": edge_label,
                        },
                    }
                )
            )
            continue

        is_fully_oriented = edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW
        if is_fully_oriented:
            new_edges.append(edge)
            continue

        projection_stats["uncertain_oriented"] += 1
        new_edges.append(
            edge.model_copy(
                update={
                    "mark_src": EdgeMark.TAIL,
                    "mark_dst": EdgeMark.ARROW,
                    "metadata": {
                        **dict(edge.metadata),
                        "orientation_uncertain": True,
                    },
                }
            )
        )

    graph_metadata = {
        **dict(graph.metadata),
        "pag_projection": {
            "performed": True,
            "latent_vars": list(latent_vars),
            **projection_stats,
        },
    }
    projected = graph.model_copy(
        update={
            "graph_type": GraphType.DAG,
            "nodes": list(graph.nodes) + latent_vars,
            "edges": new_edges,
            "metadata": graph_metadata,
        }
    )
    return projected, latent_vars


__all__ = ["pag_to_dag_projection"]

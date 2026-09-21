"""Public causal graph projection module API."""

from __future__ import annotations

from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark, GraphType


def pag_to_dag_projection(
    graph: CausalGraphModel,
) -> tuple[CausalGraphModel, list[str]]:
    """
    Project the supported part of a PAG/CPDAG into a DAG for DAG-only consumers.

    - X <-> Y becomes U_n -> X and U_n -> Y.
    - A stored X <- Y edge is canonicalized to Y -> X without changing its marks.
    - Unresolved endpoints are rejected instead of being assigned an arbitrary DAG
      direction. Callers must retain the partial graph or use a partial-graph consumer.
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
        "reversed_normalized": 0,
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

        if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.TAIL:
            projection_stats["reversed_normalized"] += 1
            new_edges.append(
                edge.model_copy(
                    update={
                        "src": edge.dst,
                        "dst": edge.src,
                        "mark_src": EdgeMark.TAIL,
                        "mark_dst": EdgeMark.ARROW,
                        "metadata": {
                            **dict(edge.metadata),
                            "orientation_normalized": True,
                            "original_src": edge.src,
                            "original_dst": edge.dst,
                            "original_marks": [edge.mark_src.value, edge.mark_dst.value],
                        },
                    }
                )
            )
            continue

        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW:
            new_edges.append(edge)
            continue

        raise ValueError(
            "cannot project unresolved partial orientation into a DAG: "
            f"{edge.src!r} {edge.mark_src.value}-{edge.mark_dst.value} {edge.dst!r}; "
            "retain the PAG/CPDAG or use a partial-graph consumer"
        )

    graph_metadata = {
        **dict(graph.metadata),
        "pag_projection": {
            "performed": True,
            "latent_vars": list(latent_vars),
            **projection_stats,
        },
    }
    projected = CausalGraphModel(
        schema_version=graph.schema_version,
        graph_type=GraphType.DAG,
        nodes=list(graph.nodes) + latent_vars,
        edges=new_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=None,
        metadata=graph_metadata,
    )
    return projected, latent_vars


__all__ = ["pag_to_dag_projection"]

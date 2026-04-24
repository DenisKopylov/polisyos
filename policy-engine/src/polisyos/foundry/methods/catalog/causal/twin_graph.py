"""Twin-network graph builder for counterfactual Layer-3 reasoning.

Twin graphs are derived representational views over a validated base causal
graph. They are intentionally NOT a new GraphType in the core IR.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict

from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType


class TwinGraphMetadata(BaseModel):
    """Metadata for a derived twin graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    factual_world_prefix: str = "__0"
    counterfactual_world_prefix: str = "__1"
    shared_exogenous: list[str]
    world_count: int = 2
    source_graph_hash: str


def _source_graph_hash(graph: CausalGraphModel) -> str:
    payload = graph.model_dump(mode="json")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _infer_shared_exogenous(graph: CausalGraphModel) -> list[str]:
    node_set = set(graph.nodes)
    candidates: Any = (
        graph.metadata.get("shared_exogenous")
        or graph.metadata.get("exogenous_nodes")
        or graph.metadata.get("exogenous_vars")
    )
    if isinstance(candidates, Iterable) and not isinstance(candidates, (str, bytes)):
        exogenous = [str(v) for v in candidates if str(v) in node_set]
        if exogenous:
            return sorted(set(exogenous))
    # Conservative fallback: explicit U_ prefix only.
    return sorted(n for n in graph.nodes if n.startswith("U_"))


def _world_node(node: str, suffix: str, shared_exogenous: set[str]) -> str:
    if node in shared_exogenous:
        return node
    return f"{node}{suffix}"


def _validate_twin(
    graph: CausalGraphModel,
    *,
    shared_exogenous: set[str],
    factual_suffix: str,
    counterfactual_suffix: str,
) -> None:
    node_set = set(graph.nodes)
    for exo in shared_exogenous:
        if exo not in node_set:
            raise ValueError(f"Shared exogenous '{exo}' is absent from twin graph nodes")
        if f"{exo}{factual_suffix}" in node_set or f"{exo}{counterfactual_suffix}" in node_set:
            raise ValueError(
                f"Shared exogenous '{exo}' must not be world-suffixed in the twin graph"
            )

    for node in graph.nodes:
        if node in shared_exogenous:
            continue
        if node.endswith(factual_suffix):
            counterpart = f"{node[: -len(factual_suffix)]}{counterfactual_suffix}"
            if counterpart not in node_set:
                raise ValueError(f"Missing counterfactual counterpart for '{node}'")
        if node.endswith(counterfactual_suffix):
            counterpart = f"{node[: -len(counterfactual_suffix)]}{factual_suffix}"
            if counterpart not in node_set:
                raise ValueError(f"Missing factual counterpart for '{node}'")


def build_twin_graph(graph: CausalGraphModel) -> tuple[CausalGraphModel, TwinGraphMetadata]:
    """Build a derived twin graph from a base validated graph."""
    shared_exogenous = _infer_shared_exogenous(graph)
    shared_exogenous_set = set(shared_exogenous)
    factual_suffix = "__0"
    counterfactual_suffix = "__1"

    twin_nodes: list[str] = []
    for node in graph.nodes:
        if node in shared_exogenous_set:
            twin_nodes.append(node)
        else:
            twin_nodes.append(f"{node}{factual_suffix}")
            twin_nodes.append(f"{node}{counterfactual_suffix}")

    seen_edges: set[tuple[Any, ...]] = set()
    twin_edges: list[CausalEdge] = []
    for suffix in (factual_suffix, counterfactual_suffix):
        for edge in graph.edges:
            src = _world_node(edge.src, suffix, shared_exogenous_set)
            dst = _world_node(edge.dst, suffix, shared_exogenous_set)
            key = (
                src,
                dst,
                edge.mark_src,
                edge.mark_dst,
                edge.lag,
                tuple(edge.sources),
                edge.data_confidence,
                edge.literature_confidence,
                edge.llm_confidence,
                edge.expert_confidence,
                edge.simulation_confidence,
                edge.combined_confidence,
                edge.unsupported_by_evidence,
                tuple(edge.evidence_refs),
                edge.p_value,
                tuple(sorted(edge.metadata.items())),
            )
            if key in seen_edges:
                continue
            seen_edges.add(key)
            twin_edges.append(edge.model_copy(update={"src": src, "dst": dst}))

    meta = TwinGraphMetadata(
        shared_exogenous=shared_exogenous,
        source_graph_hash=_source_graph_hash(graph),
    )

    twin_graph = CausalGraphModel(
        schema_version=graph.schema_version,
        graph_type=GraphType.ADMG,
        nodes=twin_nodes,
        edges=twin_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata={
            **dict(graph.metadata),
            "derived_view": "twin_network",
            "twin_metadata": meta.model_dump(mode="json"),
        },
    )
    _validate_twin(
        twin_graph,
        shared_exogenous=shared_exogenous_set,
        factual_suffix=meta.factual_world_prefix,
        counterfactual_suffix=meta.counterfactual_world_prefix,
    )
    return twin_graph, meta


def _extract_world_subgraph(
    graph: CausalGraphModel,
    meta: TwinGraphMetadata,
    *,
    suffix: str,
) -> CausalGraphModel:
    shared_exogenous = set(meta.shared_exogenous)
    renamed: dict[str, str] = {}
    ordered_nodes: list[str] = []
    for node in graph.nodes:
        if node in shared_exogenous:
            renamed[node] = node
            if node not in ordered_nodes:
                ordered_nodes.append(node)
            continue
        if node.endswith(suffix):
            base = node[: -len(suffix)]
            renamed[node] = base
            if base not in ordered_nodes:
                ordered_nodes.append(base)

    world_edges: list[CausalEdge] = []
    for edge in graph.edges:
        if edge.src not in renamed or edge.dst not in renamed:
            continue
        world_edges.append(
            edge.model_copy(update={"src": renamed[edge.src], "dst": renamed[edge.dst]})
        )

    return CausalGraphModel(
        schema_version=graph.schema_version,
        graph_type=GraphType.ADMG,
        nodes=ordered_nodes,
        edges=world_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata={
            **dict(graph.metadata),
            "derived_view": "twin_subgraph",
            "world_suffix": suffix,
            "source_graph_hash": meta.source_graph_hash,
        },
    )


def to_factual_subgraph(graph: CausalGraphModel, meta: TwinGraphMetadata) -> CausalGraphModel:
    """Extract the factual (world 0) projection from a twin graph."""
    return _extract_world_subgraph(graph, meta, suffix=meta.factual_world_prefix)


def to_counterfactual_subgraph(
    graph: CausalGraphModel,
    meta: TwinGraphMetadata,
) -> CausalGraphModel:
    """Extract the counterfactual (world 1) projection from a twin graph."""
    return _extract_world_subgraph(graph, meta, suffix=meta.counterfactual_world_prefix)


__all__ = [
    "TwinGraphMetadata",
    "build_twin_graph",
    "to_counterfactual_subgraph",
    "to_factual_subgraph",
]

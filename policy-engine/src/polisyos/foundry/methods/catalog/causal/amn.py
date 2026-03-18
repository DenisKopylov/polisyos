"""AMN (Ancestral Multi-world Network) derived graph builder."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from itertools import combinations
from typing import Any

from pydantic import BaseModel, ConfigDict

from polisyos.foundry.methods.catalog.causal.admg_ops import m_separation
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, EdgeMark, GraphType


class AMNMetadata(BaseModel):
    """Metadata describing a derived AMN view over a base graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    worlds: list[str]
    world_partition: dict[str, list[str]]
    counterfactual_interventions: dict[str, dict[str, float]]
    bridge_edges: list[tuple[str, str]]


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
    return sorted(n for n in graph.nodes if n.startswith("U_"))


def _world_node(node: str, world: str, shared_exogenous: set[str]) -> str:
    if node in shared_exogenous:
        return node
    return f"{node}__{world}"


def build_amn(
    graph: CausalGraphModel,
    interventions: dict[str, dict[str, float]],
) -> tuple[CausalGraphModel, AMNMetadata]:
    """Build a derived AMN graph and metadata for multi-world counterfactuals."""
    if interventions:
        worlds = sorted(interventions)
    else:
        worlds = ["w0"]
        interventions = {"w0": {}}

    shared_exogenous = set(_infer_shared_exogenous(graph))
    amn_nodes: list[str] = []
    world_partition: dict[str, list[str]] = {}
    for world in worlds:
        world_nodes: list[str] = []
        for node in graph.nodes:
            if node in shared_exogenous:
                if node not in amn_nodes:
                    amn_nodes.append(node)
                continue
            world_node = f"{node}__{world}"
            amn_nodes.append(world_node)
            world_nodes.append(world_node)
        world_partition[world] = world_nodes

    seen: set[tuple[Any, ...]] = set()
    amn_edges: list[CausalEdge] = []
    for world in worlds:
        for edge in graph.edges:
            src = _world_node(edge.src, world, shared_exogenous)
            dst = _world_node(edge.dst, world, shared_exogenous)
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
            if key in seen:
                continue
            seen.add(key)
            amn_edges.append(edge.model_copy(update={"src": src, "dst": dst}))

    bridge_edges: list[tuple[str, str]] = []
    intervened_vars: set[str] = set()
    amn_node_set = set(amn_nodes)
    for world_data in interventions.values():
        intervened_vars.update(world_data.keys())

    for variable in sorted(intervened_vars):
        candidate_nodes = [
            f"{variable}__{world}"
            for world in worlds
            if f"{variable}__{world}" in amn_node_set
        ]
        for left, right in combinations(candidate_nodes, 2):
            bridge_edges.append((left, right))
            amn_edges.append(
                CausalEdge(
                    src=left,
                    dst=right,
                    mark_src=EdgeMark.ARROW,
                    mark_dst=EdgeMark.ARROW,
                )
            )

    meta = AMNMetadata(
        worlds=worlds,
        world_partition=world_partition,
        counterfactual_interventions={k: dict(v) for k, v in interventions.items()},
        bridge_edges=bridge_edges,
    )

    amn_graph = CausalGraphModel(
        schema_version=graph.schema_version,
        graph_type=GraphType.ADMG,
        nodes=amn_nodes,
        edges=amn_edges,
        discovery_method=graph.discovery_method,
        skg_version_id=graph.skg_version_id,
        pag_identification_policy=graph.pag_identification_policy,
        id_confidence_under_pag=graph.id_confidence_under_pag,
        metadata={
            **dict(graph.metadata),
            "derived_view": "amn",
            "source_graph_hash": _source_graph_hash(graph),
            "amn_metadata": meta.model_dump(mode="json"),
        },
    )
    return amn_graph, meta


def amn_d_separation(
    graph: CausalGraphModel,
    meta: AMNMetadata,
    x_set: frozenset[str],
    y_set: frozenset[str],
    z_set: frozenset[str],
) -> bool:
    """Cross-world d-separation check on an AMN graph.

    The AMN is an ADMG (may contain bidirected bridge edges), so the actual
    oracle is m-separation.
    """
    _ = meta
    node_set = set(graph.nodes)
    missing = (x_set | y_set | z_set) - node_set
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Unknown AMN nodes in separation query: {missing_list}")
    return m_separation(graph, x_set, y_set, z_set)


__all__ = [
    "AMNMetadata",
    "build_amn",
    "amn_d_separation",
]

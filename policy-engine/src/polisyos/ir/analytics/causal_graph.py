"""Public analytics causal graph module API."""

from __future__ import annotations

import json
from enum import Enum
from functools import cached_property
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import CausalGraphModelRef


class GraphType(str, Enum):
    """Graph type public type."""

    DAG = "dag"
    CPDAG = "cpdag"
    PAG = "pag"
    MGRAPH = "mgraph"  # M-graph: includes R_X indicator and X_star proxy nodes
    ADMG = "admg"  # Acyclic Directed Mixed Graph (bidirected edges only, no R-nodes)


class PAGIdentificationPolicy(str, Enum):
    """PAG identification policy data model."""

    CONSERVATIVE = "conservative"
    OPTIMISTIC = "optimistic"
    PROBABILISTIC = "probabilistic"


class EdgeMark(str, Enum):
    """Edge mark public type."""

    TAIL = "tail"
    ARROW = "arrow"
    CIRCLE = "circle"


class EdgeSource(str, Enum):
    """Edge source public type."""

    DATA = "data"
    LITERATURE = "literature"
    LLM_PRIOR = "llm_prior"
    EXPERT = "expert"
    SIMULATION = "simulation"


class CausalEdge(BaseModel):
    """Causal edge public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    SOURCE_WEIGHTS: ClassVar[dict[EdgeSource, float]] = {
        EdgeSource.LITERATURE: 0.5,
        EdgeSource.DATA: 0.4,
        EdgeSource.EXPERT: 0.1,
        EdgeSource.LLM_PRIOR: 0.05,
        EdgeSource.SIMULATION: 0.1,
    }

    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    mark_src: EdgeMark = EdgeMark.TAIL
    mark_dst: EdgeMark = EdgeMark.ARROW
    lag: int | None = Field(default=None, ge=0)

    sources: list[EdgeSource] = Field(default_factory=list)
    data_confidence: float | None = None
    literature_confidence: float | None = None
    llm_confidence: float | None = None
    expert_confidence: float | None = None
    simulation_confidence: float | None = None
    combined_confidence: float | None = None

    unsupported_by_evidence: bool = False

    evidence_refs: list[str] = Field(default_factory=list)
    p_value: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_fields(self) -> CausalEdge:
        for name in (
            "data_confidence",
            "literature_confidence",
            "llm_confidence",
            "expert_confidence",
            "simulation_confidence",
            "combined_confidence",
            "p_value",
        ):
            value = getattr(self, name)
            if value is None:
                continue
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be in [0,1], got {value}")
        return self

    @staticmethod
    def _clamp_probability(value: float | None) -> float:
        if value is None:
            return 0.0
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return float(value)

    def _confidence_for_source(self, source: EdgeSource) -> float:
        if source is EdgeSource.DATA:
            return self._clamp_probability(self.data_confidence)
        if source is EdgeSource.LITERATURE:
            return self._clamp_probability(self.literature_confidence)
        if source is EdgeSource.LLM_PRIOR:
            return self._clamp_probability(self.llm_confidence)
        if source is EdgeSource.EXPERT:
            return self._clamp_probability(self.expert_confidence)
        if source is EdgeSource.SIMULATION:
            return self._clamp_probability(self.simulation_confidence)
        return 0.0

    def compute_combined_confidence(self) -> float:
        product_of_failures = 1.0
        for source in self.sources:
            conf = self._confidence_for_source(source)
            weight = self.SOURCE_WEIGHTS.get(source, 0.05)
            product_of_failures *= (1.0 - conf) ** weight
        combined = 1.0 - product_of_failures
        return self._clamp_probability(combined)


class CausalGraphModel(BaseModel):
    """DAG / CPDAG / PAG / MGRAPH / ADMG causal graph IR contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    graph_type: GraphType
    nodes: list[str]
    edges: list[CausalEdge]
    discovery_method: str = ""
    skg_version_id: int | None = None
    pag_identification_policy: PAGIdentificationPolicy = PAGIdentificationPolicy.CONSERVATIVE
    id_confidence_under_pag: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_graph(self) -> CausalGraphModel:
        if not self.nodes:
            raise ValueError("nodes must be non-empty")
        if any(not node for node in self.nodes):
            raise ValueError("nodes must not contain empty names")
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError("nodes must be unique")

        node_set = set(self.nodes)
        for edge in self.edges:
            if edge.src not in node_set:
                raise ValueError(f"Edge src '{edge.src}' not in nodes")
            if edge.dst not in node_set:
                raise ValueError(f"Edge dst '{edge.dst}' not in nodes")
            if edge.src == edge.dst:
                raise ValueError("self-loops are not allowed in CausalGraphModel")

        if self.graph_type is GraphType.DAG:
            for edge in self.edges:
                if edge.mark_src is not EdgeMark.TAIL or edge.mark_dst is not EdgeMark.ARROW:
                    raise ValueError(
                        "DAG requires oriented edges with mark_src=tail, mark_dst=arrow"
                    )
            # Time-unrolled DAGs (e.g., PCMCI) may contain lagged reciprocal edges
            # that are acyclic in time. Cycle check is applied to contemporaneous edges.
            if _has_directed_cycle(nodes=self.nodes, edges=self.edges, include_lagged=False):
                raise ValueError("DAG must be acyclic")
        elif self.graph_type is GraphType.CPDAG:
            for edge in self.edges:
                if edge.mark_src is EdgeMark.CIRCLE or edge.mark_dst is EdgeMark.CIRCLE:
                    raise ValueError("CPDAG does not allow circle endpoints")
        elif self.graph_type is GraphType.MGRAPH:
            _validate_mgraph_structure(self.nodes, self.edges)

        if self.id_confidence_under_pag is not None:
            if not (0.0 <= self.id_confidence_under_pag <= 1.0):
                raise ValueError("id_confidence_under_pag must be in [0,1]")
            if self.pag_identification_policy is not PAGIdentificationPolicy.PROBABILISTIC:
                raise ValueError(
                    "id_confidence_under_pag is only allowed when "
                    "pag_identification_policy=probabilistic"
                )
        return self

    @staticmethod
    def _dot_escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def to_dot(self) -> str:
        """
        Convert graph to DOT digraph for DoWhy.

        Requires a fully oriented DAG (tail->arrow edges only).
        """
        if self.graph_type is not GraphType.DAG:
            raise ValueError("to_dot() is only supported for DAG graphs")
        lines: list[str] = ["digraph {"]
        for node in self.nodes:
            lines.append(f'  "{self._dot_escape(node)}";')
        for edge in self.edges:
            if edge.mark_src is not EdgeMark.TAIL or edge.mark_dst is not EdgeMark.ARROW:
                raise ValueError("to_dot() requires fully oriented edges (tail->arrow)")
            lines.append(f'  "{self._dot_escape(edge.src)}" -> "{self._dot_escape(edge.dst)}";')
        lines.append("}")
        return "\n".join(lines)

    def to_rustworkx(self) -> tuple[Any, dict[str, int]]:
        import rustworkx as rx

        graph = rx.PyDiGraph()
        node_map: dict[str, int] = {}
        for node in self.nodes:
            idx = graph.add_node(node)
            node_map[node] = idx
        for edge in self.edges:
            graph.add_edge(
                node_map[edge.src],
                node_map[edge.dst],
                edge.model_dump(mode="json", exclude={"src", "dst"}),
            )
        return graph, node_map

    def to_networkx(self) -> Any:
        import networkx as nx

        graph = nx.DiGraph()
        graph.add_nodes_from(self.nodes)
        for edge in self.edges:
            graph.add_edge(
                edge.src,
                edge.dst,
                **edge.model_dump(mode="json", exclude={"src", "dst"}),
            )
        return graph

    @cached_property
    def kuzu_node_rows(self) -> tuple[dict[str, str], ...]:
        """Prepared node rows reused by Kuzu emitters."""
        return tuple({"name": node} for node in self.nodes)

    @cached_property
    def kuzu_edge_rows(self) -> tuple[dict[str, Any], ...]:
        """Prepared edge rows reused by Kuzu emitters and CSV exporters."""
        graph_type = self.graph_type.value
        return tuple(_serialize_kuzu_edge_row(edge, graph_type=graph_type) for edge in self.edges)

    def to_kuzu(self, kuzu_conn: Any) -> None:
        for row in self.kuzu_node_rows:
            kuzu_conn.execute("MERGE (v:CausalVar {name: $name})", row)

        for row in self.kuzu_edge_rows:
            kuzu_conn.execute(
                (
                    "MATCH (s:CausalVar {name: $src}), (d:CausalVar {name: $dst}) "
                    "MERGE (s)-[r:CausalEdge]->(d) "
                    "SET r.mark_src = $mark_src, "
                    "r.mark_dst = $mark_dst, "
                    "r.lag = $lag, "
                    "r.combined_confidence = $combined_confidence, "
                    "r.graph_type = $graph_type, "
                    "r.sources = $sources, "
                    "r.evidence_refs = $evidence_refs, "
                    "r.metadata_json = $metadata_json"
                ),
                row,
            )


def _serialize_kuzu_edge_row(edge: CausalEdge, *, graph_type: str) -> dict[str, Any]:
    return {
        "src": edge.src,
        "dst": edge.dst,
        "mark_src": edge.mark_src.value,
        "mark_dst": edge.mark_dst.value,
        "lag": edge.lag,
        "combined_confidence": edge.combined_confidence,
        "graph_type": graph_type,
        "sources": json.dumps([source.value for source in edge.sources]),
        "evidence_refs": json.dumps(edge.evidence_refs),
        "metadata_json": json.dumps(edge.metadata, sort_keys=True),
    }


def _validate_mgraph_structure(nodes: list[str], edges: list[CausalEdge]) -> None:
    """Validate the naming contract for an M-graph.

    For every node named "R_X" in nodes:
      - The substantive variable "X" must also be in nodes.
      - The proxy variable "X_star" must also be in nodes.
    For every node named "X_star" in nodes:
      - An edge R_X → X_star (TAIL→ARROW) must exist.
    Raises ValueError with a descriptive message on violation.
    """
    node_set = set(nodes)
    directed = {
        (e.src, e.dst) for e in edges if e.mark_src.value == "tail" and e.mark_dst.value == "arrow"
    }

    for node in nodes:
        if node.startswith("R_"):
            target = node[2:]  # "R_X" → "X"
            if target not in node_set:
                raise ValueError(
                    f"M-graph node '{node}' has no corresponding substantive variable '{target}'"
                )
            proxy = f"{target}_star"
            if proxy not in node_set:
                raise ValueError(
                    f"M-graph node '{node}' has no corresponding proxy variable '{proxy}'"
                )
        elif node.endswith("_star"):
            target = node[:-5]  # "X_star" → "X"
            r_node = f"R_{target}"
            if r_node not in node_set:
                raise ValueError(f"M-graph proxy '{node}' has no corresponding R-node '{r_node}'")
            # Edge R_X → X_star must exist
            if (r_node, node) not in directed:
                raise ValueError(f"M-graph requires directed edge '{r_node}' → '{node}'")


def _has_directed_cycle(
    *,
    nodes: list[str],
    edges: list[CausalEdge],
    include_lagged: bool = True,
) -> bool:
    indegree: dict[str, int] = dict.fromkeys(nodes, 0)
    adjacency: dict[str, list[str]] = {node: [] for node in nodes}
    for edge in edges:
        if not include_lagged and edge.lag not in (None, 0):
            continue
        adjacency[edge.src].append(edge.dst)
        indegree[edge.dst] += 1

    queue = [node for node, deg in indegree.items() if deg == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for nxt in adjacency[node]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return visited != len(nodes)


def persist_causal_graph_model(
    store: ArtifactStore,
    graph: CausalGraphModel,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_graph_model",
    schema_version: str = "1.0",
) -> CausalGraphModelRef:
    """Persist causal graph model helper."""
    ref = put_json_artifact(
        store,
        graph.model_dump(mode="json"),
        kind="ir.causal_graph_model",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalGraphModelRef.model_validate(ref)


def load_causal_graph_model(
    store: ArtifactStore,
    ref: CausalGraphModelRef,
) -> CausalGraphModel:
    """Load causal graph model."""
    payload = get_json_artifact(store, ref.artifact_id)
    return CausalGraphModel.model_validate(payload)


__all__ = [
    "CausalEdge",
    "CausalGraphModel",
    "EdgeMark",
    "EdgeSource",
    "GraphType",
    "PAGIdentificationPolicy",
    "load_causal_graph_model",
    "persist_causal_graph_model",
]

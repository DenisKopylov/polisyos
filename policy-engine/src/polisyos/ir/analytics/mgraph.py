"""mgraph — IR types for Missing Data Graphs (M-graphs).

An M-graph extends a causal DAG with:
  - R_X nodes: missingness indicators (R_X=1 ↔ X is observed)
  - X_star nodes: observed proxies (X* = X when R_X=1, else NaN)

These types are pure IR contracts (no algorithm logic).  The
recoverability algorithms live in
``foundry/methods/catalog/causal/recoverability_engine.py``.

References
----------
Mohan, K. & Pearl, J. (2021). "Graphical Models for Processing Missing
    Data." Journal of the American Statistical Association.
Mohan, K., Pearl, J. & Tian, J. (2013). "Missing Data as a Causal and
    Probabilistic Problem." UAI 2013.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, model_validator

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_graph import CausalGraphModel


class MissingnessKind(str, Enum):
    """Missingness mechanism classification."""

    MCAR = "mcar"  # Missing Completely at Random: R_X ⊥⊥ (X, V\X)
    MAR = "mar"  # Missing at Random: R_X ⊥⊥ X | observed vars
    MNAR = "mnar"  # Missing Not at Random: R_X depends on X itself


class RNode(BaseModel):
    """Missingness indicator node R_X in an M-graph.

    Represents the binary variable R_X where R_X=1 means X is observed
    and R_X=0 means X is missing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_variable: str
    """The substantive variable X whose missingness R_X indicates."""

    missingness_kind: MissingnessKind
    """MCAR / MAR / MNAR classification for this missingness mechanism."""

    description: str = ""


class ProxyNode(BaseModel):
    """Observed proxy variable X_star in an M-graph.

    X_star = X when R_X = 1, else NaN.  X_star is what we actually observe
    in the data; X is the latent full-data variable.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_variable: str
    """The substantive variable X this proxy represents."""

    proxy_name: str
    """Node name in the graph (e.g. 'X_star')."""


class MGraphMetadata(BaseModel):
    """Semantic metadata for a CausalGraphModel with graph_type=MGRAPH.

    Stored in ``graph.metadata["mgraph"]`` as a serialised dict to avoid
    modifying the versioned CausalGraphModel schema.

    Use ``extract_mgraph_metadata()`` to deserialise and
    ``build_mgraph()`` to construct a well-formed M-graph.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"

    r_nodes: tuple[RNode, ...] = ()
    """One RNode per variable with potential missingness."""

    proxy_nodes: tuple[ProxyNode, ...] = ()
    """One ProxyNode per variable with potential missingness."""

    substantive_vars: tuple[str, ...] = ()
    """Full-data variables V (excludes R_* and *_star nodes)."""

    fully_observed_vars: tuple[str, ...] = ()
    """Subset of substantive_vars that have no R-node (always observed)."""

    @model_validator(mode="after")
    def _validate_consistency(self) -> MGraphMetadata:
        r_targets = {rn.target_variable for rn in self.r_nodes}
        p_targets = {pn.target_variable for pn in self.proxy_nodes}
        if r_targets != p_targets:
            raise ValueError(
                "r_nodes and proxy_nodes must cover the same set of variables; "
                f"r_nodes covers {sorted(r_targets)}, "
                f"proxy_nodes covers {sorted(p_targets)}"
            )
        subst_set = set(self.substantive_vars)
        for v in r_targets:
            if v not in subst_set:
                raise ValueError(f"R-node target '{v}' not listed in substantive_vars")
        for v in self.fully_observed_vars:
            if v not in subst_set:
                raise ValueError(f"fully_observed_var '{v}' not listed in substantive_vars")
        return self


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_mgraph_metadata(graph: CausalGraphModel) -> MGraphMetadata:
    """Extract MGraphMetadata from ``graph.metadata["mgraph"]``.

    Raises ValueError if the key is absent or the graph_type is not MGRAPH.
    """
    from polisyos.ir.analytics.causal_graph import GraphType

    if graph.graph_type is not GraphType.MGRAPH:
        raise ValueError(
            f"extract_mgraph_metadata requires graph_type=MGRAPH, got {graph.graph_type}"
        )
    raw = graph.metadata.get("mgraph")
    if raw is None:
        raise ValueError(
            "graph.metadata['mgraph'] is absent; "
            "use build_mgraph() to construct a properly annotated M-graph"
        )
    if isinstance(raw, str):
        raw = json.loads(raw)
    return MGraphMetadata.model_validate(raw)


def build_mgraph(
    *,
    substantive_vars: list[str] | None = None,
    directed_edges: list[tuple[str, str]] | None = None,
    bidirected_edges: list[tuple[str, str]] | None = None,
    missingness_map: dict[str, MissingnessKind] | None = None,
    fully_observed: list[str] | None = None,
    missingness_edges: list[tuple[str, str]] | None = None,
    base_graph: CausalGraphModel | None = None,
    missing_variables: dict[str, MissingnessKind] | None = None,
    discovery_method: str = "manual",
) -> CausalGraphModel:
    """Construct a well-formed CausalGraphModel with graph_type=MGRAPH.

    For each variable X in *missingness_map*:
      - Adds nodes ``"R_X"`` (indicator) and ``"X_star"`` (proxy).
      - Adds directed edge ``R_X → X_star`` (proxy mechanism).
      - MNAR only: adds directed edge ``X → R_X``.

    Stores :class:`MGraphMetadata` in ``graph.metadata["mgraph"]``.

    Parameters
    ----------
    substantive_vars:
        Full-data variable names V (no R_* or *_star). Optional when
        ``base_graph`` is provided.
    directed_edges:
        Directed edges among substantive variables. Legacy call sites may also
        include explicit missingness edges such as ``("Z", "R_X")``.
    bidirected_edges:
        Bidirected (confounding) edges: [(u, v), ...].  Optional.
    missingness_map:
        Maps each variable with potential missingness to its mechanism.
        Variables not listed are treated as fully observed.
    missingness_edges:
        Explicit edges into missingness indicators, e.g. ``("Z", "R_X")`` for
        MAR or ``("Y", "R_X")`` for outcome-driven missingness.
    base_graph:
        Legacy convenience input. When provided, substantive variables and
        substantive edges are derived from this graph unless overridden.
    missing_variables:
        Legacy alias for ``missingness_map``.
    fully_observed:
        Explicit list of always-observed variables.  Defaults to
        ``substantive_vars`` minus ``missingness_map.keys()``.
    discovery_method:
        Passed through to CausalGraphModel.discovery_method.
    """
    from polisyos.ir.analytics.causal_graph import (
        CausalEdge,
        CausalGraphModel,
        EdgeMark,
        GraphType,
    )

    missingness_map = dict(missingness_map or missing_variables or {})
    directed_edges = list(directed_edges or [])
    bidirected_edges = list(bidirected_edges or [])
    missingness_edges = list(missingness_edges or [])

    if base_graph is not None:
        if substantive_vars is None:
            substantive_vars = [
                node
                for node in base_graph.nodes
                if not node.startswith("R_") and not node.endswith("_star")
            ]
        if discovery_method == "manual" and getattr(base_graph, "discovery_method", None):
            discovery_method = base_graph.discovery_method

        from polisyos.ir.analytics.causal_graph import EdgeMark

        for edge in base_graph.edges:
            if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW:
                bidirected_edges.append((edge.src, edge.dst))
            else:
                directed_edges.append((edge.src, edge.dst))

    if substantive_vars is None:
        raise ValueError("build_mgraph requires substantive_vars unless base_graph is provided")

    subst_set = set(substantive_vars)

    # Validate inputs
    for v in missingness_map:
        if v not in subst_set:
            raise ValueError(f"missingness_map key '{v}' not in substantive_vars")

    substantive_directed: list[tuple[str, str]] = []
    for src, dst in directed_edges:
        if src in subst_set and dst in subst_set:
            substantive_directed.append((src, dst))
            continue
        missingness_edges.append((src, dst))

    normalised_missingness_edges: list[tuple[str, str]] = []
    for src, dst in missingness_edges:
        if not dst.startswith("R_"):
            raise ValueError(f"missingness edge must target an R-node, got ({src!r}, {dst!r})")
        target_var = dst[2:]
        if target_var not in subst_set:
            raise ValueError(
                f"missingness edge target '{dst}' refers to unknown substantive variable '{target_var}'"
            )
        normalised_missingness_edges.append((src, dst))

    # Stable de-duplication preserves deterministic node/edge ordering.
    substantive_directed = list(dict.fromkeys(substantive_directed))
    bidirected_edges = list(dict.fromkeys(bidirected_edges))
    normalised_missingness_edges = list(dict.fromkeys(normalised_missingness_edges))

    # Build full node list
    all_nodes: list[str] = list(substantive_vars)
    r_nodes: list[RNode] = []
    proxy_nodes: list[ProxyNode] = []
    for v, kind in missingness_map.items():
        r_name = f"R_{v}"
        proxy_name = f"{v}_star"
        all_nodes.append(r_name)
        all_nodes.append(proxy_name)
        r_nodes.append(RNode(target_variable=v, missingness_kind=kind))
        proxy_nodes.append(ProxyNode(target_variable=v, proxy_name=proxy_name))

    # Build edges list
    all_edges: list[CausalEdge] = []

    # Directed edges among substantive vars
    for src, dst in substantive_directed:
        all_edges.append(CausalEdge(src=src, dst=dst))

    # Bidirected (confounding) edges
    for u, v in bidirected_edges:
        all_edges.append(CausalEdge(src=u, dst=v, mark_src=EdgeMark.ARROW, mark_dst=EdgeMark.ARROW))

    # Missingness mechanism edges
    for v, kind in missingness_map.items():
        r_name = f"R_{v}"
        proxy_name = f"{v}_star"
        # R_X → X_star (proxy observation mechanism)
        all_edges.append(CausalEdge(src=r_name, dst=proxy_name))
        # MNAR: X → R_X (missingness depends on X itself)
        if kind is MissingnessKind.MNAR:
            all_edges.append(CausalEdge(src=v, dst=r_name))

    for src, dst in normalised_missingness_edges:
        all_edges.append(CausalEdge(src=src, dst=dst))

    # Build fully_observed list
    if fully_observed is None:
        fully_observed = [v for v in substantive_vars if v not in missingness_map]

    # Build MGraphMetadata
    meta = MGraphMetadata(
        r_nodes=tuple(r_nodes),
        proxy_nodes=tuple(proxy_nodes),
        substantive_vars=tuple(substantive_vars),
        fully_observed_vars=tuple(fully_observed),
    )

    return CausalGraphModel(
        graph_type=GraphType.MGRAPH,
        nodes=all_nodes,
        edges=all_edges,
        discovery_method=discovery_method,
        metadata={"mgraph": meta.model_dump(mode="json")},
    )


__all__ = [
    "MGraphMetadata",
    "MissingnessKind",
    "ProxyNode",
    "RNode",
    "build_mgraph",
    "extract_mgraph_metadata",
]

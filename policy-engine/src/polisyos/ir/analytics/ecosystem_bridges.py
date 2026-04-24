"""Bridge contracts for external causal-tooling ecosystems."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.causal_graph import CausalGraphModel, EdgeMark


class CausalBridgeTarget(str, Enum):
    """External causal ecosystem targets supported by the bridge layer."""

    DOWHY = "dowhy"
    ECONML = "econml"
    CAUSALNEX = "causalnex"
    PGMPY = "pgmpy"
    TIGRAMITE_PCMCI = "tigramite_pcmci"


class DoWhyGraphBridge(BaseModel):
    """DoWhy-ready graph bridge using DOT plus explicit role hints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: CausalBridgeTarget = CausalBridgeTarget.DOWHY
    graph_dot: str
    treatment: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    common_causes: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)
    effect_modifiers: list[str] = Field(default_factory=list)


class EconMLDesignBridge(BaseModel):
    """EconML-ready design contract derived from an IR causal graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: CausalBridgeTarget = CausalBridgeTarget.ECONML
    treatment: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    features: list[str] = Field(default_factory=list)
    effect_modifiers: list[str] = Field(default_factory=list)
    confounders: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)


class CausalNexGraphBridge(BaseModel):
    """CausalNex edge-list exchange with optional confidence weights."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: CausalBridgeTarget = CausalBridgeTarget.CAUSALNEX
    nodes: list[str]
    directed_edges: list[tuple[str, str]]
    weighted_confidence: dict[str, float] = Field(default_factory=dict)


class PgmpyGraphBridge(BaseModel):
    """pgmpy/adjacency exchange covering directed and latent confounding edges."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: CausalBridgeTarget = CausalBridgeTarget.PGMPY
    nodes: list[str]
    directed_edges: list[tuple[str, str]]
    latent_bidirected_edges: list[tuple[str, str]] = Field(default_factory=list)


class TigramiteEdge(BaseModel):
    """One Tigramite/PCMCI lagged edge."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    lag: int = Field(ge=0)


class TigramitePCMCIBridge(BaseModel):
    """Tigramite PCMCI bridge preserving lagged-edge semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: CausalBridgeTarget = CausalBridgeTarget.TIGRAMITE_PCMCI
    variables: list[str]
    max_lag: int = Field(ge=0)
    lagged_edges: list[TigramiteEdge] = Field(default_factory=list)


def _oriented_directed_edges(graph: CausalGraphModel) -> list[tuple[str, str]]:
    return [
        (edge.src, edge.dst)
        for edge in graph.edges
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW
    ]


def _bidirected_edges(graph: CausalGraphModel) -> list[tuple[str, str]]:
    return [
        tuple(sorted((edge.src, edge.dst)))
        for edge in graph.edges
        if edge.mark_src is EdgeMark.ARROW and edge.mark_dst is EdgeMark.ARROW
    ]


def to_dowhy_graph_bridge(
    graph: CausalGraphModel,
    *,
    treatment: str,
    outcome: str,
    common_causes: list[str] | None = None,
    instruments: list[str] | None = None,
    effect_modifiers: list[str] | None = None,
) -> DoWhyGraphBridge:
    """Build a DoWhy bridge contract from an oriented IR DAG."""

    return DoWhyGraphBridge(
        graph_dot=graph.to_dot(),
        treatment=treatment,
        outcome=outcome,
        common_causes=common_causes or [],
        instruments=instruments or [],
        effect_modifiers=effect_modifiers or [],
    )


def to_econml_design_bridge(
    graph: CausalGraphModel,
    *,
    treatment: str,
    outcome: str,
    effect_modifiers: list[str] | None = None,
    instruments: list[str] | None = None,
) -> EconMLDesignBridge:
    """Build an EconML design contract from a causal graph skeleton."""

    excluded = {treatment, outcome, *(effect_modifiers or ()), *(instruments or ())}
    features = [node for node in graph.nodes if node not in excluded]
    return EconMLDesignBridge(
        treatment=treatment,
        outcome=outcome,
        features=features,
        effect_modifiers=effect_modifiers or [],
        confounders=features,
        instruments=instruments or [],
    )


def to_causalnex_graph_bridge(graph: CausalGraphModel) -> CausalNexGraphBridge:
    """Export directed edges and confidence weights for CausalNex-like consumers."""

    directed_edges = _oriented_directed_edges(graph)
    weights = {
        f"{edge.src}->{edge.dst}": edge.combined_confidence
        for edge in graph.edges
        if edge.combined_confidence is not None
        and edge.mark_src is EdgeMark.TAIL
        and edge.mark_dst is EdgeMark.ARROW
    }
    return CausalNexGraphBridge(
        nodes=list(graph.nodes),
        directed_edges=directed_edges,
        weighted_confidence=weights,
    )


def to_pgmpy_graph_bridge(graph: CausalGraphModel) -> PgmpyGraphBridge:
    """Export directed and latent-bidirected edges for pgmpy-like tooling."""

    return PgmpyGraphBridge(
        nodes=list(graph.nodes),
        directed_edges=_oriented_directed_edges(graph),
        latent_bidirected_edges=sorted(set(_bidirected_edges(graph))),
    )


def to_tigramite_pcmci_bridge(
    graph: CausalGraphModel,
    *,
    max_lag: int | None = None,
) -> TigramitePCMCIBridge:
    """Export lagged edges in a Tigramite/PCMCI-friendly format."""

    lagged_edges = [
        TigramiteEdge(src=edge.src, dst=edge.dst, lag=edge.lag or 0)
        for edge in graph.edges
        if edge.mark_src is EdgeMark.TAIL and edge.mark_dst is EdgeMark.ARROW
    ]
    computed_max_lag = max((edge.lag for edge in lagged_edges), default=0)
    return TigramitePCMCIBridge(
        variables=list(graph.nodes),
        max_lag=computed_max_lag if max_lag is None else max_lag,
        lagged_edges=lagged_edges,
    )


__all__ = [
    "CausalBridgeTarget",
    "CausalNexGraphBridge",
    "DoWhyGraphBridge",
    "EconMLDesignBridge",
    "PgmpyGraphBridge",
    "TigramiteEdge",
    "TigramitePCMCIBridge",
    "to_causalnex_graph_bridge",
    "to_dowhy_graph_bridge",
    "to_econml_design_bridge",
    "to_pgmpy_graph_bridge",
    "to_tigramite_pcmci_bridge",
]

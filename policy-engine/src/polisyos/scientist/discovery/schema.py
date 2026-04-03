"""Typed discovery contracts for graph-hypothesis search."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.scientist import GraphHypothesisRef
from polisyos.ir.analytics.causal_discovery import (
    AlgebraicConstraintReport,
    CausalDiscoveryReport,
    LatentDiscoveryBundle,
)
from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel
from polisyos.ir.refs import CausalDiscoveryReportRef

GRAPH_HYPOTHESIS_SCHEMA_NAME = "polisyos.scientist.discovery.GraphHypothesis"
GRAPH_HYPOTHESIS_SCHEMA_VERSION = "1.0"


class DiscoveryAlgorithmFamily(str, Enum):
    """High-level causal-discovery families used by the portfolio runner."""

    CONSTRAINT_BASED = "constraint_based"
    SCORE_BASED = "score_based"
    FUNCTIONAL = "functional"
    TIME_SERIES = "time_series"


class DiscoveryMethod(str, Enum):
    """Concrete discovery methods supported by Phase C portfolio."""

    PC = "pc"
    FCI = "fci"
    GES = "ges"
    DAGMA = "dagma"
    ANM = "anm"
    PAIRWISE_HEURISTIC = "pairwise_heuristic"
    PCMCI_PLUS = "pcmci+"


class ComputeFootprint(BaseModel):
    """Minimal execution footprint for one graph hypothesis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_seconds: float = Field(default=0.0, ge=0.0)
    timeout_seconds: float | None = Field(default=None, ge=0.0)
    n_samples: int | None = Field(default=None, ge=0)
    n_variables: int | None = Field(default=None, ge=0)
    n_bootstrap: int = Field(default=0, ge=0)
    random_seed: int | None = None
    backend: str | None = None
    method_params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphHypothesis(BaseModel):
    """Layer-C candidate schema reused across portfolio, stability, and judging."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(
        default=GRAPH_HYPOTHESIS_SCHEMA_VERSION,
        pattern=r"^\d+\.\d+$",
    )
    hypothesis_id: str = Field(min_length=1)
    algorithm_family: DiscoveryAlgorithmFamily
    method: DiscoveryMethod
    graph: CausalGraphModel
    resolved_graph: CausalGraphModel | None = None
    edge_confidence: dict[str, float] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    compute_footprint: ComputeFootprint = Field(default_factory=ComputeFootprint)
    failure_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    algebraic_constraints: AlgebraicConstraintReport | None = None
    latent_discovery: LatentDiscoveryBundle | None = None
    source_discovery_report_ref: CausalDiscoveryReportRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_edge_confidence(self) -> "GraphHypothesis":
        for key, value in self.edge_confidence.items():
            if not key:
                raise ValueError("edge_confidence keys must be non-empty")
            if not (0.0 <= float(value) <= 1.0):
                raise ValueError(f"edge_confidence[{key!r}] must be in [0,1], got {value}")
        return self


def edge_key_for_edge(edge: CausalEdge) -> str:
    """Return the normalized edge key used by scientist discovery."""

    key = f"{edge.src}->{edge.dst}"
    if edge.lag not in (None, 0):
        return f"{key}@lag={edge.lag}"
    return key


def orientation_key_for_edge(edge: CausalEdge) -> str:
    """Return a mark-aware edge descriptor for orientation-frequency accounting."""

    base = f"{edge.src}|{edge.mark_src.value}>{edge.mark_dst.value}|{edge.dst}"
    if edge.lag not in (None, 0):
        return f"{base}@lag={edge.lag}"
    return base


def skeleton_key_for_edge(edge: CausalEdge) -> str:
    """Return the skeleton key, ignoring orientation but preserving lag."""

    src, dst = sorted((edge.src, edge.dst))
    base = f"{src}--{dst}"
    if edge.lag not in (None, 0):
        return f"{base}@lag={edge.lag}"
    return base


def infer_algorithm_family(method: DiscoveryMethod | str) -> DiscoveryAlgorithmFamily:
    """Map a concrete method to its portfolio family."""

    normalized = DiscoveryMethod(method)
    if normalized in {DiscoveryMethod.PC, DiscoveryMethod.FCI}:
        return DiscoveryAlgorithmFamily.CONSTRAINT_BASED
    if normalized in {DiscoveryMethod.GES, DiscoveryMethod.DAGMA}:
        return DiscoveryAlgorithmFamily.SCORE_BASED
    if normalized in {DiscoveryMethod.ANM, DiscoveryMethod.PAIRWISE_HEURISTIC}:
        return DiscoveryAlgorithmFamily.FUNCTIONAL
    return DiscoveryAlgorithmFamily.TIME_SERIES


def default_method_assumptions(method: DiscoveryMethod | str) -> list[str]:
    """Return conservative, method-specific assumptions for surfaced provenance."""

    normalized = DiscoveryMethod(method)
    assumptions: dict[DiscoveryMethod, list[str]] = {
        DiscoveryMethod.PC: [
            "causal_sufficiency unless contradicted by later discovery evidence",
            "faithfulness / Markov assumptions for conditional-independence testing",
        ],
        DiscoveryMethod.FCI: [
            "faithfulness / Markov assumptions for conditional-independence testing",
            "latent confounders may exist; output preserves partial ancestral uncertainty",
        ],
        DiscoveryMethod.GES: [
            "score-equivalent DAG search with no latent-confounder handling in the base search",
            "faithfulness / score consistency assumptions",
        ],
        DiscoveryMethod.DAGMA: [
            "continuous optimization over DAG structure with acyclicity constraint",
            "no latent-confounder handling in the base score-based search",
        ],
        DiscoveryMethod.ANM: [
            "pairwise additive-noise orientation is used as a heuristic structural signal",
            "orientation quality depends on non-Gaussianity / nonlinear asymmetry being informative",
        ],
        DiscoveryMethod.PAIRWISE_HEURISTIC: [
            "pairwise orientation is heuristic and intended as a low-cost functional baseline",
            "edge orientation quality depends on directional asymmetry surviving the chosen residual proxy",
        ],
        DiscoveryMethod.PCMCI_PLUS: [
            "lag-limited time-series discovery under the configured maximum lag",
            "stationarity / stable temporal mechanism assumptions of the chosen conditional-independence test",
        ],
    }
    return list(assumptions[normalized])


def bootstrap_confidence_for_edge(
    report: CausalDiscoveryReport,
    edge: CausalEdge,
) -> float | None:
    """Resolve bootstrap stability for an edge across foundry report key variants."""

    stability = dict(report.bootstrap_stability)
    for key in (
        edge_key_for_edge(edge),
        orientation_key_for_edge(edge),
        f"{edge.src}->{edge.dst}@lag={edge.lag}",
    ):
        if key in stability:
            return float(stability[key])
    return None


def edge_confidence_for_edge(
    report: CausalDiscoveryReport,
    edge: CausalEdge,
    *,
    shared_bootstrap_stability: dict[str, float] | None = None,
) -> float:
    """Resolve edge confidence using the agreed fallback order."""

    normalized_key = edge_key_for_edge(edge)
    if shared_bootstrap_stability and normalized_key in shared_bootstrap_stability:
        return float(shared_bootstrap_stability[normalized_key])
    if edge.combined_confidence is not None:
        return float(edge.combined_confidence)
    if edge.data_confidence is not None:
        return float(edge.data_confidence)
    return 0.5


def graph_hypothesis_from_report(
    report: CausalDiscoveryReport,
    *,
    hypothesis_id: str,
    compute_footprint: ComputeFootprint | None = None,
    shared_bootstrap_stability: dict[str, float] | None = None,
    metadata: dict[str, Any] | None = None,
) -> GraphHypothesis:
    """Normalize a foundry discovery report into the scientist graph contract."""

    method = DiscoveryMethod(report.method)
    warnings = list(report.warnings)
    failure_markers = (
        "timeout",
        "failed",
        "modulenotfounderror",
        "unsupported",
        "executor_failed",
        "algorithm_failed",
    )
    failure_reasons = [
        warning
        for warning in warnings
        if any(marker in warning.lower() for marker in failure_markers)
    ]
    edge_confidence = {
        edge_key_for_edge(edge): edge_confidence_for_edge(
            report,
            edge,
            shared_bootstrap_stability=shared_bootstrap_stability,
        )
        for edge in report.graph.edges
    }
    return GraphHypothesis(
        hypothesis_id=hypothesis_id,
        algorithm_family=infer_algorithm_family(method),
        method=method,
        graph=report.graph,
        resolved_graph=report.resolved_graph,
        edge_confidence=edge_confidence,
        assumptions=default_method_assumptions(method),
        compute_footprint=compute_footprint or ComputeFootprint(),
        failure_reasons=failure_reasons,
        warnings=warnings,
        algebraic_constraints=report.algebraic_constraints,
        latent_discovery=report.latent_discovery,
        metadata={
            "discovery_report_metadata": dict(report.metadata),
            **(metadata or {}),
        },
    )


def persist_graph_hypothesis(
    store: FileSystemCAS,
    hypothesis: GraphHypothesis,
    *,
    inputs: list[InputRef] | None = None,
) -> GraphHypothesisRef:
    """Persist a single graph hypothesis and return its typed artifact reference."""
    ref = store.put_json(
        hypothesis,
        PutOptions(
            kind="scientist.graph_hypothesis",
            media_type="application/json",
            schema=SchemaInfo(
                name=GRAPH_HYPOTHESIS_SCHEMA_NAME,
                version=hypothesis.schema_version,
            ),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return GraphHypothesisRef.model_validate(ref.model_dump(mode="json"))


def load_graph_hypothesis(
    store: FileSystemCAS,
    ref: GraphHypothesisRef,
) -> GraphHypothesis:
    """Load graph hypothesis."""
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return GraphHypothesis.model_validate(payload)


__all__ = [
    "ComputeFootprint",
    "DiscoveryAlgorithmFamily",
    "DiscoveryMethod",
    "GRAPH_HYPOTHESIS_SCHEMA_NAME",
    "GRAPH_HYPOTHESIS_SCHEMA_VERSION",
    "GraphHypothesis",
    "bootstrap_confidence_for_edge",
    "default_method_assumptions",
    "edge_confidence_for_edge",
    "edge_key_for_edge",
    "graph_hypothesis_from_report",
    "infer_algorithm_family",
    "load_graph_hypothesis",
    "orientation_key_for_edge",
    "persist_graph_hypothesis",
    "skeleton_key_for_edge",
]

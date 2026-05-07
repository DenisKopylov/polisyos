"""Contract models for interference identification and topology planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep
from polisyos.ir.analytics.interference import ExposureMappingType


class InterferenceAugmentedGraph(BaseModel):
    """Graph augmentation used by the interference identification layer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    original_graph: CausalGraphModel
    augmented_graph: CausalGraphModel
    exposure_nodes: tuple[str, ...] = ()
    cluster_partition: tuple[tuple[str, ...], ...] = ()
    interference_type: Literal["none", "partial", "network", "bipartite", "spatial"] = "network"
    exposure_mapping: ExposureMappingType = ExposureMappingType.FRACTIONAL
    cross_unit_edges: tuple[tuple[str, str], ...] = ()
    node_to_cluster: dict[str, str] = Field(default_factory=dict)
    cluster_var: str | None = None


class InterferenceIdentificationResult(BaseModel):
    """Result of graph-based interference identification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    treatment: str
    outcome: str
    status: Literal["identified", "non_identified", "input_invalid"]
    interference_detected: bool
    sutva_violated: bool
    identification_method: str = "graph_based_interference_id"
    augmented_graph: InterferenceAugmentedGraph
    proof_steps: tuple[IRProofStep, ...] = ()
    trace: tuple[str, ...] = ()
    base_identification_status: str | None = None
    estimand_ast: dict[str, Any] | None = None
    required_distributions: tuple[dict[str, Any], ...] = ()
    negative_certificate: dict[str, Any] | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _SimplicialSupportGate:
    supported: bool
    assumptions: tuple[str, ...]
    failures: tuple[str, ...]


@dataclass(frozen=True)
class _TopologyCertificatePlan:
    supported_query_family: str
    fallback_mode: Literal["pairwise", "clustered", "unsupported"]
    exposure_assumptions: tuple[str, ...]
    reduction_error_bound: float | None
    mode_requested: Literal["pairwise", "clustered", "complex"]
    mode_used: Literal["pairwise", "clustered", "complex", "unsupported"]
    fallback_triggered: bool
    fallback_reason_codes: tuple[str, ...]
    estimability_checks: dict[str, Literal["pass", "fail", "not_applicable"]]


@dataclass(frozen=True)
class _ReductionErrorBoundPlan:
    reduction_error_bound: float | None
    assumptions: tuple[str, ...] = ()


__all__ = [
    "InterferenceAugmentedGraph",
    "InterferenceIdentificationResult",
    "_ReductionErrorBoundPlan",
    "_SimplicialSupportGate",
    "_TopologyCertificatePlan",
]

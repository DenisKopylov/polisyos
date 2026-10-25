"""Contract models for interference identification and topology planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.analytics.evidence_bundle import ProofStep as IRProofStep
from polisyos.ir.analytics.interference import ExposureMappingType


class InterferenceAugmentedGraph(BaseModel):
    """Original and candidate graph state retained for interference diagnostics."""

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

    schema_version: Literal["1.0", "1.1"] = "1.0"
    treatment: str
    outcome: str
    status: Literal[
        "identified",
        "non_identified",
        "input_invalid",
        "oracle_needed",
        "pag_ambiguous",
        "not_recoverable",
    ]
    interference_detected: bool | None
    sutva_violated: bool | None
    identification_method: str = "graph_based_interference_id"
    augmented_graph: InterferenceAugmentedGraph
    proof_steps: tuple[IRProofStep, ...] = ()
    trace: tuple[str, ...] = ()
    base_identification_status: str | None = None
    estimand_ast: dict[str, Any] | None = None
    required_distributions: tuple[dict[str, Any], ...] = ()
    negative_certificate: dict[str, Any] | None = None
    warnings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_status_schema_version(self) -> InterferenceIdentificationResult:
        """Keep the legacy status set at 1.0 and gate expanded outcomes to 1.1."""
        expanded_statuses = {"oracle_needed", "pag_ambiguous", "not_recoverable"}
        if self.status in expanded_statuses and self.schema_version != "1.1":
            raise ValueError(f"status {self.status!r} requires schema_version='1.1'")
        if self.schema_version == "1.0" and (
            self.interference_detected is None or self.sutva_violated is None
        ):
            raise ValueError("schema_version='1.0' requires boolean topology indicators")
        return self


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

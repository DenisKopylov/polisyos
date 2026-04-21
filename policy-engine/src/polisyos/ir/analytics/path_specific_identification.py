"""Typed proof-kernel artifacts for path-specific identification decisions.

The contracts in this module are intentionally estimator-agnostic. They record:

- the normalized path policy being analyzed;
- district-local compilation diagnostics;
- the main witness when exact identification fails;
- the fallback mode chosen by the proof backend.

This is the path-specific analogue of the proximal/recoverability certificate
surfaces: a compact machine-readable object that can be embedded into
``IdentificationResult.metadata`` / ``NegativeCertificate.quantitative_diagnostics``.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.estimand import DistributionRef, EstimandAST
from polisyos.ir.analytics.mediation_effects import PathSpecificQuery
from polisyos.ir.analytics.partial_identification import BoundsBundle


class PathSpecificDecisionMode(str, Enum):
    """Outcome of the path-specific proof-kernel decision procedure."""

    EXACT_IDENTIFIED = "exact_identified"
    EXACT_WITH_EXPERIMENTS = "exact_with_experiments"
    TEMPLATE_PROXIMAL = "template_proximal"
    BOUNDED = "bounded"
    BLOCKED_WITH_WITNESS = "blocked_with_witness"


class PathSpecificWitnessKind(str, Enum):
    """Main structural blocker or diagnostic emitted by the backend."""

    EDGE_INCONSISTENCY = "edge_inconsistency"
    RECANTING_WITNESS = "recanting_witness"
    RECANTING_DISTRICT = "recanting_district"
    TOTAL_EFFECT_NOT_IDENTIFIED = "total_effect_not_identified"
    UNSUPPORTED_CONDITIONING = "unsupported_conditioning"
    WIDTH_BUDGET_EXCEEDED = "width_budget_exceeded"
    UNSUPPORTED_GRAPH_SEMANTICS = "unsupported_graph_semantics"


class PathSpecificDistrictLabel(str, Enum):
    """Treatment label seen by one district in the compiled local plan."""

    ACTIVE = "active"
    FROZEN = "frozen"
    NATURAL = "natural"
    MIXED = "mixed"


class PathSpecificWitness(BaseModel):
    """Smallest known machine-readable witness for a failed exact-ID path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: PathSpecificWitnessKind
    detail: str
    variables: tuple[str, ...] = ()
    district: tuple[str, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


class PathSpecificDistrictFactor(BaseModel):
    """One district-local factor in the compiled path-specific plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    district: tuple[str, ...]
    label: PathSpecificDistrictLabel
    parents: tuple[str, ...] = ()
    frontier_assignments: tuple[tuple[str, str, Literal["active", "frozen"]], ...] = ()
    local_width_bound: int = 1


class PathSpecificCompilationPlan(BaseModel):
    """District-local compilation diagnostics for a path-specific query."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path_policy_hash: str
    relevant_nodes: tuple[str, ...]
    ancestral_nodes: tuple[str, ...]
    treatment_frontier: tuple[tuple[str, str, Literal["active", "frozen"]], ...] = ()
    district_partition: tuple[tuple[str, ...], ...] = ()
    district_factors: tuple[PathSpecificDistrictFactor, ...] = ()
    intrinsic_width_bound: int = 1
    compiled_estimand_ast: EstimandAST | None = None
    required_distributions: tuple[DistributionRef, ...] = ()


class PathSpecificIdentificationReport(BaseModel):
    """Full decision payload emitted by the path-specific proof backend."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    theorem_family: str = "path_specific_id_scale_v1"
    mode: PathSpecificDecisionMode
    treatment: str
    outcome: str
    semantic_query: PathSpecificQuery
    compilation_plan: PathSpecificCompilationPlan | None = None
    witnesses: tuple[PathSpecificWitness, ...] = ()
    required_distributions: tuple[DistributionRef, ...] = ()
    bounds_bundle: BoundsBundle | None = None
    proof_trace: tuple[str, ...] = ()
    fallback_trace: tuple[str, ...] = ()
    constructive_message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "PathSpecificCompilationPlan",
    "PathSpecificDecisionMode",
    "PathSpecificDistrictFactor",
    "PathSpecificDistrictLabel",
    "PathSpecificIdentificationReport",
    "PathSpecificWitness",
    "PathSpecificWitnessKind",
]

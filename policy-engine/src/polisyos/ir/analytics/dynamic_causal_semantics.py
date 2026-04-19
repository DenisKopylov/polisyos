"""Typed dynamic causal semantics attachments for proof-kernel artifacts.

These models are intentionally small and proof-oriented. They let the public
``ProofBundle`` carry the minimum machine-checkable structure needed to explain
why a cyclic or continuous-time query was accepted, blocked, or kept at the
research boundary.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DynamicSemanticsFamily(str, Enum):
    """Semantic family used to interpret a dynamic or cyclic causal query."""

    IOSCM = "ioSCM"
    SIMPLE_SCM = "simple_SCM"
    LOCAL_INDEPENDENCE_GRAPH = "local_independence_graph"
    ADMG = "admg"


class GraphicalOracleKind(str, Enum):
    """Graphical Markov criterion used by a dynamic proof path."""

    D = "d"
    SIGMA = "sigma"
    MU = "mu"
    DELTA = "delta"


class InterventionKind(str, Enum):
    """Intervention kinds currently distinguished by the proof kernel."""

    NODE_DO = "node_do"
    MECHANISM_SWAP = "mechanism_swap"
    INTENSITY_INTERVENTION = "intensity_intervention"


class DynamicReductionStatus(str, Enum):
    """How far the engine reduced the dynamic query to a certified backend."""

    VALIDATED_REDUCTION = "validated_reduction"
    HEURISTIC_ONLY = "heuristic_only"
    BLOCKED = "blocked"


class WellPosednessStatus(str, Enum):
    """Status of the well-posedness witness for a cyclic or dynamic fragment."""

    PROVED = "proved"
    REFUTED = "refuted"
    HEURISTIC_BLOCKED = "heuristic_blocked"


class InterventionScope(BaseModel):
    """Admissible intervention summary for a dynamic proof path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: InterventionKind
    targets: tuple[str, ...] = ()
    admissible: bool = True
    admissibility_theorem: str | None = None


class WellPosednessWitness(BaseModel):
    """Machine-checkable summary of the semantics well-posedness check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: WellPosednessStatus
    family: str
    method: str
    confidence: str
    lipschitz_constant: float | None = None
    warning: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class SeparationClaim(BaseModel):
    """Statement of a graphical separation query used in the proof path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    x_set: tuple[str, ...] = ()
    y_set: tuple[str, ...] = ()
    z_set: tuple[str, ...] = ()
    holds: bool
    criterion: GraphicalOracleKind


class GraphicalMarkovCertificate(BaseModel):
    """Constructive graphical-causal certificate for dynamic semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    certificate_type: str = "graphical_markov"
    semantics_family: DynamicSemanticsFamily
    graphical_oracle: GraphicalOracleKind
    theorem_family: str
    source_graph_ref: str | None = None
    latent_projection_ref: str | None = None
    intervention_spec: InterventionScope | None = None
    separation_claim: SeparationClaim | None = None
    transformation_trace: tuple[str, ...] = ()
    required_distributions: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class DynamicScopeStatement(BaseModel):
    """Declared supported and excluded dynamic-semantics families."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    covered_families: tuple[str, ...] = ()
    excluded_families: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class LocalIndependenceAttachment(BaseModel):
    """Continuous-time attachment for local-independence-based semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graphical_oracle: GraphicalOracleKind
    causal_validity_rule: str | None = None
    eliminable_processes: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


class DynamicSemanticsAttachment(BaseModel):
    """Top-level proof attachment for cyclic and continuous-time semantics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    semantics_family: DynamicSemanticsFamily
    reduction_status: DynamicReductionStatus = DynamicReductionStatus.HEURISTIC_ONLY
    markov_criterion_certificate: GraphicalMarkovCertificate | None = None
    well_posedness_witness: WellPosednessWitness | None = None
    intervention_scope: InterventionScope | None = None
    continuous_time_attachment: LocalIndependenceAttachment | None = None
    scope_statement: DynamicScopeStatement | None = None


__all__ = [
    "DynamicReductionStatus",
    "DynamicScopeStatement",
    "DynamicSemanticsAttachment",
    "DynamicSemanticsFamily",
    "GraphicalMarkovCertificate",
    "GraphicalOracleKind",
    "InterventionKind",
    "InterventionScope",
    "LocalIndependenceAttachment",
    "SeparationClaim",
    "WellPosednessStatus",
    "WellPosednessWitness",
]

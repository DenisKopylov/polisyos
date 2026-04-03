"""Public analytics causal discovery module API."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.causal_graph import CausalGraphModel
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import ArtifactRefModel, CausalDiscoveryReportRef

_ALGEBRAIC_IMPLIED_CONSTRAINTS_KIND = "ir.algebraic_implied_constraints"
_ALGEBRAIC_IMPLIED_CONSTRAINTS_SCHEMA_NAME = "ir.algebraic_implied_constraints"
_ALGEBRAIC_VIOLATED_CONSTRAINTS_KIND = "ir.algebraic_violated_constraints"
_ALGEBRAIC_VIOLATED_CONSTRAINTS_SCHEMA_NAME = "ir.algebraic_violated_constraints"


class AlgebraicConstraintFamily(str, Enum):
    """Algebraic constraint family public type."""
    CI = "ci"
    TETRAD = "tetrad"
    OVERCOMPLETE = "overcomplete"


class AlgebraicBlockSpec(BaseModel):
    """Algebraic block spec data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    block_id: str = Field(min_length=1)
    family: AlgebraicConstraintFamily
    variables: tuple[str, ...]
    quadruples: tuple[tuple[str, str, str, str], ...] = ()
    expected_rank: int | None = Field(default=None, ge=1)
    max_residual_energy: float | None = Field(default=None, ge=0.0)

    def model_post_init(self, __context: Any) -> None:
        del __context
        if len(self.variables) != len(set(self.variables)):
            raise ValueError("variables must be unique within an algebraic block")
        if self.family is AlgebraicConstraintFamily.TETRAD:
            if len(self.variables) < 4:
                raise ValueError("tetrad blocks require at least 4 variables")
            if self.expected_rank is not None:
                raise ValueError("expected_rank is only valid for overcomplete blocks")
            if self.max_residual_energy is not None:
                raise ValueError(
                    "max_residual_energy is only valid for overcomplete blocks"
                )
            for quadruple in self.quadruples:
                if len(set(quadruple)) != 4:
                    raise ValueError("each tetrad quadruple must contain 4 unique variables")
                if not set(quadruple).issubset(set(self.variables)):
                    raise ValueError(
                        "tetrad quadruples must only reference variables declared in the block"
                    )
        elif self.family is AlgebraicConstraintFamily.OVERCOMPLETE:
            if self.expected_rank is None:
                raise ValueError("overcomplete blocks require expected_rank")
            if len(self.variables) <= self.expected_rank:
                raise ValueError(
                    "overcomplete blocks require more variables than expected_rank"
                )
            if self.quadruples:
                raise ValueError("quadruples are only valid for tetrad blocks")
        else:
            raise ValueError(
                "AlgebraicBlockSpec only supports explicit tetrad and overcomplete blocks"
            )


class ImpliedConstraintSpec(BaseModel):
    """Implied constraint spec data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str = Field(min_length=1)
    family: AlgebraicConstraintFamily
    statement: str = Field(min_length=1)
    variables: tuple[str, ...]
    conditioning_set: tuple[str, ...] = ()
    source_block_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConstraintEvaluationResult(BaseModel):
    """Constraint evaluation result data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str = Field(min_length=1)
    family: AlgebraicConstraintFamily
    status: Literal["passed", "violated", "skipped", "error", "unsupported"]
    statistic: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    adjusted_p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    severity: Literal["info", "warning", "blocker"] = "info"
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlgebraicConstraintReport(BaseModel):
    """Algebraic constraint report data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    implied_constraints_ref: ArtifactRefModel | None = None
    violated_constraints_ref: ArtifactRefModel | None = None
    severity: Literal["info", "warning", "blocker"] = "info"
    suggested_repairs: list[str] = Field(default_factory=list)
    families_run: list[AlgebraicConstraintFamily] = Field(default_factory=list)
    n_implied_constraints: int = Field(default=0, ge=0)
    n_violated_constraints: int = Field(default=0, ge=0)
    tested_by_family: dict[str, int] = Field(default_factory=dict)
    violated_by_family: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    implied_constraints_preview: list[ImpliedConstraintSpec] = Field(default_factory=list)
    violated_constraints_preview: list[ConstraintEvaluationResult] = Field(default_factory=list)


class LatentTrustLevel(str, Enum):
    """Latent trust level public type."""
    RESEARCH = "research"
    CONDITIONAL = "conditional"
    VALIDATED = "validated"


class LatentAssumptionCard(BaseModel):
    """Latent assumption card public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    assumption_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence_basis: list[str] = Field(default_factory=list)
    falsification_hook: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LatentDiscoveryBundle(BaseModel):
    """Latent discovery bundle data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposed_latent_nodes: list[str] = Field(default_factory=list)
    inducing_environments: list[str] = Field(default_factory=list)
    identification_conditions: list[str] = Field(default_factory=list)
    falsification_tests: list[str] = Field(default_factory=list)
    trust_level: LatentTrustLevel = LatentTrustLevel.RESEARCH
    assumption_cards: list[LatentAssumptionCard] = Field(default_factory=list)
    readiness_cap: Literal["proof_only"] = "proof_only"
    human_gate_required: bool = True
    promotion_allowed: bool = False
    no_promotion_reasons: list[str] = Field(default_factory=list)
    not_for_decision_support: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CausalDiscoveryReport(BaseModel):
    """Output of a causal-discovery run, including optional latent diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    method: str
    graph: CausalGraphModel
    resolved_graph: CausalGraphModel | None = None
    bootstrap_stability: dict[str, float] = Field(default_factory=dict)
    n_bootstrap: int = Field(default=0, ge=0)
    significance_level: float = Field(default=0.05, ge=0.0, le=1.0)
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    warnings: list[str] = Field(default_factory=list)
    algebraic_constraints: AlgebraicConstraintReport | None = None
    latent_discovery: LatentDiscoveryBundle | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataType(str, Enum):
    """Data type public type."""
    CROSS_SECTIONAL = "cross_sectional"
    TIME_SERIES = "time_series"


class DimensionRegime(str, Enum):
    """Dimension regime public type."""
    LOW_DIM = "low_dim"   # n_vars <= 20
    MED_DIM = "med_dim"   # 21 <= n_vars <= 50
    HIGH_DIM = "high_dim"  # n_vars > 50


class DataCharacteristics(BaseModel):
    """Data characteristics public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_type: DataType
    n_samples: int
    n_variables: int
    dimension_regime: DimensionRegime
    estimated_density: float
    has_mixed_types: bool
    suspected_latent_confounders: bool
    is_stationary: bool | None = None
    max_lag: int | None = None


class EdgeAgreement(BaseModel):
    """Edge agreement public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_key: str
    presence_score: float
    orientation_confidence: float
    mark_src: str
    mark_dst: str
    contributing_algorithms: list[str]


class DiscoveryPipelineReport(BaseModel):
    """Discovery pipeline report data model."""
    model_config = ConfigDict(extra="forbid", frozen=True)

    unified_pag: CausalGraphModel
    individual_results: list[CausalDiscoveryReport]
    algorithm_weights: dict[str, float]
    edge_agreements: list[EdgeAgreement]
    skeleton_agreement: dict[str, float] = Field(default_factory=dict)
    temporal_dag: CausalGraphModel | None = None
    pag_validity_violations: list[str] = Field(default_factory=list)
    data_characteristics: DataCharacteristics
    n_algorithms_run: int
    warnings: list[str] = Field(default_factory=list)
    computation_time_seconds: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


def persist_causal_discovery_report(
    store: ArtifactStore,
    report: CausalDiscoveryReport,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_discovery_report",
    schema_version: str = "1.0",
) -> CausalDiscoveryReportRef:
    """Persist causal discovery report helper."""
    persisted_report = _materialize_algebraic_constraint_payloads(
        store,
        report,
        inputs=inputs,
    )
    ref = put_json_artifact(
        store,
        persisted_report.model_dump(mode="json"),
        kind="ir.causal_discovery_report",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalDiscoveryReportRef.model_validate(ref)


def load_causal_discovery_report(
    store: ArtifactStore,
    ref: CausalDiscoveryReportRef,
) -> CausalDiscoveryReport:
    """Load causal discovery report."""
    payload = get_json_artifact(store, ref.artifact_id)
    report = CausalDiscoveryReport.model_validate(payload)
    return _hydrate_algebraic_constraint_payloads(store, report)


def _materialize_algebraic_constraint_payloads(
    store: ArtifactStore,
    report: CausalDiscoveryReport,
    *,
    inputs: list[InputRef] | None,
) -> CausalDiscoveryReport:
    algebraic = report.algebraic_constraints
    if algebraic is None:
        return report

    updated = algebraic
    if algebraic.implied_constraints_ref is None and algebraic.implied_constraints_preview:
        ref = put_json_artifact(
            store,
            [item.model_dump(mode="json") for item in algebraic.implied_constraints_preview],
            kind=_ALGEBRAIC_IMPLIED_CONSTRAINTS_KIND,
            schema_name=_ALGEBRAIC_IMPLIED_CONSTRAINTS_SCHEMA_NAME,
            schema_version="1.0",
            inputs=inputs,
            canon_spec=CanonSpec(forbid_floats=False),
        )
        updated = updated.model_copy(
            update={
                "implied_constraints_ref": ArtifactRefModel.model_validate(ref),
                "implied_constraints_preview": [],
            }
        )

    if updated.violated_constraints_ref is None and updated.violated_constraints_preview:
        ref = put_json_artifact(
            store,
            [item.model_dump(mode="json") for item in updated.violated_constraints_preview],
            kind=_ALGEBRAIC_VIOLATED_CONSTRAINTS_KIND,
            schema_name=_ALGEBRAIC_VIOLATED_CONSTRAINTS_SCHEMA_NAME,
            schema_version="1.0",
            inputs=inputs,
            canon_spec=CanonSpec(forbid_floats=False),
        )
        updated = updated.model_copy(
            update={
                "violated_constraints_ref": ArtifactRefModel.model_validate(ref),
                "violated_constraints_preview": [],
            }
        )

    if updated == algebraic:
        return report
    return report.model_copy(update={"algebraic_constraints": updated})


def _hydrate_algebraic_constraint_payloads(
    store: ArtifactStore,
    report: CausalDiscoveryReport,
) -> CausalDiscoveryReport:
    algebraic = report.algebraic_constraints
    if algebraic is None:
        return report

    updates: dict[str, Any] = {}
    if algebraic.implied_constraints_ref is not None and not algebraic.implied_constraints_preview:
        payload = get_json_artifact(store, algebraic.implied_constraints_ref.artifact_id)
        updates["implied_constraints_preview"] = [
            ImpliedConstraintSpec.model_validate(item) for item in payload
        ]

    if algebraic.violated_constraints_ref is not None and not algebraic.violated_constraints_preview:
        payload = get_json_artifact(store, algebraic.violated_constraints_ref.artifact_id)
        updates["violated_constraints_preview"] = [
            ConstraintEvaluationResult.model_validate(item) for item in payload
        ]

    if not updates:
        return report
    return report.model_copy(
        update={"algebraic_constraints": algebraic.model_copy(update=updates)}
    )


__all__ = [
    "AlgebraicBlockSpec",
    "AlgebraicConstraintFamily",
    "AlgebraicConstraintReport",
    "CausalDiscoveryReport",
    "ConstraintEvaluationResult",
    "DataType",
    "DimensionRegime",
    "DataCharacteristics",
    "EdgeAgreement",
    "ImpliedConstraintSpec",
    "DiscoveryPipelineReport",
    "persist_causal_discovery_report",
    "LatentAssumptionCard",
    "LatentDiscoveryBundle",
    "LatentTrustLevel",
    "load_causal_discovery_report",
]

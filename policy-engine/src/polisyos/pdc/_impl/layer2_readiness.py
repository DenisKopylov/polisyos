"""Layer 2 S0 readiness contracts for the universal policy designer."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ID_PATTERN = r"^[a-z][a-z0-9_.-]*$"

LAYER2_READINESS_SCHEMA_VERSION = "policyos.policy_design_case.layer2_readiness.v1"
CANONICAL_DESIGN_RECORD_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer2_s9_projection_lowering.v1"
)

Audience = Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]
AuthorityPosture = Literal["shadow", "advisory", "governed", "production"]
EpistemicRegime = Literal["risk", "uncertainty", "ambiguity", "ignorance", "contested_model"]
SourceAuthority = Literal[
    "deterministic_producer",
    "governed_config",
    "human_governance",
    "llm_candidate",
    "llm_critic",
    "llm_drafter",
]
FirewallDisposition = Literal["not_applicable", "pass", "warn", "limit", "block"]
CellMaturity = Literal["fail_closed", "predictive"]
EvidenceKind = Literal[
    "measurement",
    "derivation",
    "proxy",
    "transport",
    "bounds",
    "simulation",
    "elicitation",
    "incomparable_meet",
]
type DecisionGrade = Literal[
    "unsupported",
    "descriptive_only",
    "advisory_admissible",
    "decision_admissible",
]


class Layer2ReadinessModel(BaseModel):
    """Strict frozen base for Layer 2 readiness contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class EvidenceBasis(Layer2ReadinessModel):
    """Producer evidence used by the GY authority lattice."""

    producer_roots: list[Any] = Field(default_factory=list, max_length=80)
    method_refs: list[str] = Field(default_factory=list, max_length=80)
    calibration_refs: list[Any] = Field(default_factory=list, max_length=80)
    counterexamples_closed: list[Any] = Field(default_factory=list, max_length=80)


class AuthorityBoundary(Layer2ReadinessModel):
    """Purpose-scoped authority boundary carried by Layer 2 records."""

    boundary_id: str | None = Field(default=None, pattern=ID_PATTERN)
    authoritative_for: list[str] = Field(..., min_length=1, max_length=20)
    may_not_use_for: list[str] = Field(..., min_length=1, max_length=20)
    source_authority: SourceAuthority
    posture: AuthorityPosture
    rule_version_refs: list[str] = Field(..., min_length=1, max_length=20)
    evidence_kind: EvidenceKind | None = None
    decision_grade: DecisionGrade | None = None
    evidence_basis: EvidenceBasis | None = None
    known_limits: list[str] = Field(default_factory=list, max_length=80)

    @model_validator(mode="after")
    def _validate_llm_firewall(self) -> AuthorityBoundary:
        if self.source_authority.startswith("llm_") and self.posture != "shadow":
            raise ValueError(f"{self.source_authority} cannot carry {self.posture} authority")
        if (
            self.evidence_kind == "simulation"
            and _decision_grade_rank(self.decision_grade)
            >= _decision_grade_rank("advisory_admissible")
            and not (self.evidence_basis and self.evidence_basis.calibration_refs)
        ):
            raise ValueError(
                "uncalibrated simulation cannot carry advisory_admissible or stronger authority"
            )
        return self

    def meet(
        self,
        other: AuthorityBoundary,
        *,
        boundary_id: str | None = None,
    ) -> AuthorityBoundary:
        """Return the weakest purpose-scoped boundary shared by two upstream ports."""

        authoritative_for = sorted(set(self.authoritative_for) & set(other.authoritative_for))
        may_not_use_for = sorted(set(self.may_not_use_for) | set(other.may_not_use_for))
        evidence_kind = _meet_evidence_kind(self.evidence_kind, other.evidence_kind)
        decision_grade = _meet_decision_grade(self.decision_grade, other.decision_grade)
        return AuthorityBoundary(
            boundary_id=boundary_id,
            authoritative_for=authoritative_for or ["none"],
            may_not_use_for=may_not_use_for or ["unspecified"],
            source_authority=_meet_source_authority(self.source_authority, other.source_authority),
            posture=_meet_posture(self.posture, other.posture),
            rule_version_refs=sorted(set(self.rule_version_refs) | set(other.rule_version_refs)),
            evidence_kind=evidence_kind,
            decision_grade=decision_grade,
            evidence_basis=_merge_evidence_basis(self.evidence_basis, other.evidence_basis),
            known_limits=sorted(set(self.known_limits) | set(other.known_limits)),
        )

    def permits_at_most(self, other: AuthorityBoundary) -> bool:
        """Return whether this boundary is no stronger than ``other``."""

        if not set(self.authoritative_for) <= set(other.authoritative_for):
            return False
        if not set(other.may_not_use_for) <= set(self.may_not_use_for):
            return False
        return _decision_grade_rank(self.decision_grade) <= _decision_grade_rank(
            other.decision_grade
        )

    def with_partial_evidence_downgrade(
        self,
        *,
        limitation: str,
        may_not_use_for: list[str] | tuple[str, ...],
        decision_grade_cap: DecisionGrade = "advisory_admissible",
        boundary_id: str | None = None,
    ) -> AuthorityBoundary:
        """Return this boundary capped for partial-but-grounded evidence.

        Args:
            limitation: Human-visible limitation explaining the bounded evidence.
            may_not_use_for: Purpose deny-list entries added by the downgrade.
            decision_grade_cap: Maximum decision grade allowed after downgrade.
            boundary_id: Optional replacement boundary identifier.

        Returns:
            A boundary with a capped grade, merged limitations, and merged deny-list.
        """

        if not limitation.strip():
            raise ValueError("partial evidence downgrade requires a visible limitation")
        safe_cap: DecisionGrade = (
            decision_grade_cap
            if _decision_grade_rank(decision_grade_cap)
            < _decision_grade_rank("decision_admissible")
            else "advisory_admissible"
        )
        capped_grade = _meet_decision_grade(self.decision_grade, safe_cap)
        return self.model_copy(
            update={
                "boundary_id": boundary_id if boundary_id is not None else self.boundary_id,
                "decision_grade": capped_grade,
                "may_not_use_for": sorted(
                    set(self.may_not_use_for) | {str(value) for value in may_not_use_for}
                ),
                "known_limits": sorted(set(self.known_limits) | {limitation}),
            }
        )


_DECISION_GRADE_RANK: dict[str | None, int] = {
    None: 0,
    "unsupported": 0,
    "descriptive_only": 1,
    "advisory_admissible": 2,
    "decision_admissible": 3,
}
_POSTURE_RANK: dict[str, int] = {"shadow": 0, "advisory": 1, "governed": 2, "production": 3}
_SOURCE_AUTHORITY_RANK: dict[str, int] = {
    "llm_candidate": 0,
    "llm_critic": 0,
    "llm_drafter": 0,
    "human_governance": 1,
    "governed_config": 2,
    "deterministic_producer": 3,
}


def _decision_grade_rank(value: DecisionGrade | None) -> int:
    return _DECISION_GRADE_RANK.get(value, 0)


def _meet_decision_grade(left: DecisionGrade | None, right: DecisionGrade | None) -> DecisionGrade:
    rank = min(_decision_grade_rank(left), _decision_grade_rank(right))
    for grade, grade_rank in _DECISION_GRADE_RANK.items():
        if grade is not None and grade_rank == rank:
            return grade
    return "unsupported"


def _meet_evidence_kind(left: EvidenceKind | None, right: EvidenceKind | None) -> EvidenceKind:
    if left is None or right is None:
        return "elicitation"
    if left == right:
        return left
    if "incomparable_meet" in {left, right}:
        return "incomparable_meet"
    if "elicitation" in {left, right}:
        return "elicitation"
    if left == "measurement":
        return right
    if right == "measurement":
        return left
    if left == "derivation" and right in {"proxy", "transport", "bounds", "simulation"}:
        return right
    if right == "derivation" and left in {"proxy", "transport", "bounds", "simulation"}:
        return left
    comparable_pairs = {frozenset(("proxy", "transport"))}
    if frozenset((left, right)) in comparable_pairs:
        return "incomparable_meet"
    if {left, right} <= {"bounds", "simulation"}:
        return "incomparable_meet"
    return "incomparable_meet"


def _meet_posture(left: AuthorityPosture, right: AuthorityPosture) -> AuthorityPosture:
    rank = min(_POSTURE_RANK[left], _POSTURE_RANK[right])
    for posture, posture_rank in _POSTURE_RANK.items():
        if posture_rank == rank:
            return posture  # type: ignore[return-value]
    return "shadow"


def _meet_source_authority(left: SourceAuthority, right: SourceAuthority) -> SourceAuthority:
    rank = min(_SOURCE_AUTHORITY_RANK[left], _SOURCE_AUTHORITY_RANK[right])
    for source, source_rank in _SOURCE_AUTHORITY_RANK.items():
        if source_rank == rank:
            return source  # type: ignore[return-value]
    return "llm_candidate"


def _merge_evidence_basis(
    left: EvidenceBasis | None,
    right: EvidenceBasis | None,
) -> EvidenceBasis | None:
    if left is None and right is None:
        return None
    left = left or EvidenceBasis()
    right = right or EvidenceBasis()
    return EvidenceBasis(
        producer_roots=[*left.producer_roots, *right.producer_roots],
        method_refs=sorted(set(left.method_refs) | set(right.method_refs)),
        calibration_refs=[*left.calibration_refs, *right.calibration_refs],
        counterexamples_closed=[*left.counterexamples_closed, *right.counterexamples_closed],
    )


class ValueOfInformationEstimate(Layer2ReadinessModel):
    """Shared value-of-information currency consumed by downstream slices."""

    estimate_id: str = Field(..., pattern=ID_PATTERN)
    purpose: str = Field(..., min_length=1, max_length=200)
    budget_dimensions: list[str] = Field(..., min_length=1, max_length=10)
    used_by_sites: list[str] = Field(..., min_length=1, max_length=20)
    owner: str = Field(..., min_length=1, max_length=100)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class GovernanceDecisionClass(Layer2ReadinessModel):
    """Registry entry for a governance decision class."""

    decision_class_id: str = Field(..., pattern=ID_PATTERN)
    label: str = Field(..., min_length=1, max_length=120)
    required_role: str = Field(..., min_length=1, max_length=120)
    default_posture: AuthorityPosture
    high_stakes: bool
    authority_boundary: AuthorityBoundary


class AxisPositionDeclaration(Layer2ReadinessModel):
    """A declared position on a universal designer cluster axis."""

    cluster: str = Field(..., min_length=1, max_length=80)
    axis: str = Field(..., min_length=1, max_length=120)
    position: str = Field(..., min_length=1, max_length=200)
    evidence_refs: list[str] = Field(default_factory=list, max_length=40)
    authority_purpose: str = Field(..., min_length=1, max_length=200)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)

    @property
    def cell_ref(self) -> str:
        """Return the `CLUSTER.axis` reference."""

        return f"{self.cluster}.{self.axis}"


class AxisFirewallStatus(Layer2ReadinessModel):
    """Fail-closed or predictive firewall status for one axis."""

    cell_ref: str = Field(..., min_length=3, max_length=200)
    status: FirewallDisposition
    pattern_ids: list[str] = Field(default_factory=list, max_length=10)
    reason: str = Field(..., min_length=1, max_length=500)
    maturity: CellMaturity | None = None
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class CertifiedOperationEnvelope(Layer2ReadinessModel):
    """Certified operation envelope attached to a design record."""

    envelope_id: str = Field(..., pattern=ID_PATTERN)
    domains: list[str] = Field(..., min_length=1, max_length=20)
    posture_scopes: list[AuthorityPosture] = Field(..., min_length=1, max_length=4)
    epistemic_regime_scopes: list[EpistemicRegime] = Field(default_factory=list, max_length=20)
    actor_scopes: list[str] = Field(..., min_length=1, max_length=20)
    method_scopes: list[str] = Field(..., min_length=1, max_length=20)
    certified_for: list[str] = Field(..., min_length=1, max_length=20)
    not_certified_for: list[str] = Field(..., min_length=1, max_length=40)
    cluster_authority_dimension_refs: list[str] = Field(default_factory=list, max_length=40)
    rule_version_ref: str = Field(..., min_length=1, max_length=300)


class DesignRecordV0(Layer2ReadinessModel):
    """Minimal narrow-waist design record carried from S2 onward."""

    schema_version: str = LAYER2_READINESS_SCHEMA_VERSION
    record_id: str = Field(..., pattern=ID_PATTERN)
    candidate_ref: str = Field(..., min_length=1, max_length=300)
    candidate_source: SourceAuthority
    projection_status: AuthorityPosture
    authority_boundary: AuthorityBoundary
    axis_positions: list[AxisPositionDeclaration] = Field(default_factory=list, max_length=40)
    firewall_status: list[AxisFirewallStatus] = Field(default_factory=list, max_length=40)
    envelope: CertifiedOperationEnvelope
    ledger_refs: list[str] = Field(default_factory=list, max_length=40)
    projection_audiences: list[Audience] = Field(..., min_length=1, max_length=4)

    @model_validator(mode="after")
    def _validate_v0_authority(self) -> DesignRecordV0:
        if self.candidate_source.startswith("llm_") and self.projection_status != "shadow":
            raise ValueError(
                f"{self.candidate_source} cannot carry {self.projection_status} authority"
            )
        if self.projection_status == "production":
            raise ValueError("DesignRecordV0 cannot carry production authority")
        return self


class CanonicalDesignRecord(Layer2ReadinessModel):
    """Replayable S9 narrow waist for faithful projections and governed lowering."""

    schema_version: str = CANONICAL_DESIGN_RECORD_SCHEMA_VERSION
    record_id: str = Field(..., pattern=ID_PATTERN)
    record_ref: str = Field(..., min_length=1, max_length=300)
    source_design_record_ref: str = Field(..., min_length=1, max_length=300)
    source_design_record_digest: str = Field(..., min_length=1, max_length=300)
    source_revision_ref: str = Field(..., min_length=1, max_length=300)
    canonical_design_record_revision_ref: str = Field(..., min_length=1, max_length=300)
    recursive_design_graph_refs: list[str] = Field(..., min_length=1, max_length=80)
    claim_bound_evidence_portfolio_refs: list[str] = Field(
        ...,
        min_length=1,
        max_length=80,
    )
    pareto_tradeoff_value_choice_refs: list[str] = Field(..., min_length=1, max_length=80)
    axis_position_refs: list[str] = Field(..., min_length=1, max_length=80)
    firewall_status_refs: list[str] = Field(..., min_length=1, max_length=80)
    certified_envelope_ref: str = Field(..., min_length=1, max_length=300)
    search_ledger_refs: list[str] = Field(..., min_length=1, max_length=80)
    counterexample_refinement_refs: list[str] = Field(default_factory=list, max_length=80)
    assurance_case_refs: list[str] = Field(..., min_length=1, max_length=80)
    limitation_refs: list[str] = Field(..., min_length=1, max_length=80)
    abstention_refs: list[str] = Field(default_factory=list, max_length=80)
    lowering_artifact_refs: list[str] = Field(default_factory=list, max_length=80)
    projection_audiences: list[Audience] = Field(..., min_length=1, max_length=4)
    projection_status: AuthorityPosture
    authority_boundary: AuthorityBoundary
    rule_version_ref: str = Field(..., min_length=1, max_length=300)

    @model_validator(mode="after")
    def _validate_canonical_authority(self) -> CanonicalDesignRecord:
        if self.projection_status == "production":
            raise ValueError("CanonicalDesignRecord cannot carry production authority")
        if self.authority_boundary.posture == "production":
            raise ValueError("CanonicalDesignRecord cannot carry production authority")
        return self


class MinimalSeedManifest(Layer2ReadinessModel):
    """S0 manifest of algebra generators and launch budgets."""

    schema_version: str = LAYER2_READINESS_SCHEMA_VERSION
    manifest_id: str = Field(..., pattern=ID_PATTERN)
    facet_primitives: list[str] = Field(..., min_length=1, max_length=40)
    instrument_modality_primitives: list[str] = Field(..., min_length=1, max_length=40)
    projection_primitives: list[str] = Field(..., min_length=1, max_length=40)
    launch_firewalls: list[str] = Field(..., min_length=1, max_length=20)
    budgets: dict[str, str] = Field(..., min_length=1, max_length=20)
    principal_set_explore_exploit: str = Field(..., min_length=1, max_length=200)
    owned_by: str = Field(..., min_length=1, max_length=100)
    rule_version_refs: list[str] = Field(..., min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_launch_firewalls(self) -> MinimalSeedManifest:
        required = {"P15", "P25"}
        if not required <= set(self.launch_firewalls):
            raise ValueError("launch_firewalls must include P15 and P25")
        return self

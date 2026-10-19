"""Runtime API contracts for run explorer, debug, evidence, and artifact-inspection endpoints."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationInfo,
    field_validator,
    model_validator,
)

from polisyos.ir import governance, observation

from ..artifacts.manifest import ArtifactRef, InputRef, artifact_ref_identity_key
from ..trace import RunTerminality
from .decision_validity import DecisionValidityStatus
from .execution_plan import (
    EvaluatorVerdict,
    IterationLifecycleState,
    StopReason,
)
from .feedback import (
    DecisionCompareReport,
    DecisionMonitoringContract,
    DecisionMonitoringReport,
    DecisionReissuePlan,
)
from .foundry import EquilibriumMultiplicityReport, SimulationResult
from .policy_design_case_projection import PolicyDesignCaseProjection

PolicyLayerLevel = governance.PolicyLayerLevel
NormativeOutcomeChannel = governance.NormativeOutcomeChannel
IdentificationMode = observation.IdentificationMode

SourceKind = Literal["core_run"]
NodeStatus = Literal["ok", "skip", "fail", "unknown"]
AgentPipelineCostOrigin = Literal["reported", "estimated", "reuse", "unknown"]
AgentPipelineSettlementStatus = Literal["pending", "committed", "unknown", "unmanaged"]
PreviewMode = Literal["json", "text", "binary"]
CanonReadStatus = Literal[
    "not_applicable",
    "not_evaluated",
    "declared_bytes_conformant",
    "profile_absent_unqualified_candidate",
    "declared_unknown_candidate",
]
VerificationStatus = Literal["verified", "pending", "disputed", "untraced"]
LineageFreshness = Literal["current", "stale", "unknown"]
DisputeStatus = Literal["none", "disputed", "under_review", "resolved"]
QuantityClass = Literal["decision", "telemetry", "layout", "debug"]
ComparabilityStatus = Literal["compatible", "warning", "blocked"]
CompareCandidateRelation = Literal["baseline", "previous", "selected", "recommended"]
CompareResponseStatus = Literal["computed", "client_computable"]
DeltaSignificance = Literal["improved", "worsened", "mixed", "uncertain", "not_comparable"]
OperatorProjectionAuthority = Literal["runtime_authority", "projection_only"]
OperatorProjectionState = Literal[
    "draft",
    "projection_only",
    "redacted",
    "stale",
    "contested",
    "projected",
    "blocked",
    "readiness_closed",
    "approved",
    "rejected",
    "published_blocked",
    "publishable",
]
DeltaDominance = Literal["a", "b", "none", "mixed", "unknown"]
CounterfactualMode = Literal["actual", "actual_vs_scenario", "scenario_only"]
ScenarioStatus = Literal["draft", "computed", "stale", "failed"]
ScenarioLifecycleStatus = Literal["generated", "draft", "saved", "promoted"]
ScenarioAssumptionStatus = Literal[
    "operator_assumption",
    "model_assumption",
    "observed_evidence",
    "disputed",
]
ScenarioInterventionOperator = Literal["set", "add", "multiply", "remove"]
ScenarioConstraintSeverity = Literal["error", "warning"]
ScenarioSurfaceSupport = Literal[
    "run_metrics",
    "quantities",
    "lineage",
    "charts",
    "whatif",
]
BureaucraticGenre = Literal[
    "postanova_kmu",
    "zakonoproekt",
    "expert_vysnovok",
    "analitichna_zapyska",
]
BureaucraticBlockKind = Literal[
    "header",
    "requisites",
    "preamble",
    "legal_basis",
    "section",
    "article",
    "clause",
    "subclause",
    "paragraph",
    "list",
    "table",
    "quantity",
    "annex",
    "signature",
    "appendix",
]
BureaucraticEpistemicKind = Literal[
    "evidence_filled",
    "model_generated",
    "operator_filled",
    "imported",
]
BureaucraticDocumentStatus = Literal["draft", "signed_external", "archived"]
BureaucraticExportFormat = Literal["html", "pdf", "docx"]
EpochPerturbationClass = Literal[
    "incident",
    "appeal",
    "correction",
    "retraction",
    "legal_change",
    "discovered_bias",
]
TemporalSurfaceSupport = Literal[
    "run_details",
    "run_timeline",
    "run_lineage",
    "run_quantities",
    "run_fabric_decision_data",
    "run_compare",
    "run_agents",
    "run_evidence_context",
    "run_workflow",
    "run_nodes",
    "artifact_content",
    "epoch_staleness",
]
TemporalEventKind = Literal[
    "run_start",
    "run_finish",
    "trace_event",
    "policy_change",
    "late_evidence",
    "correction",
    "snapshot",
    "now",
]
LineageSummaryKind = Literal[
    "source",
    "transform",
    "model",
    "agent",
    "result",
    "artifact",
    "dataset",
    "method",
    "unknown",
]
FabricImpactSubjectKind = Literal["lineage", "source_contract", "run", "decision_data"]
UniversalPolicyGrammarStatus = Literal["compiled", "blocked", "candidate_unverified"]
UniversalPolicyGrammarSourceClassification = Literal[
    "deterministic_producer",
    "human_author",
    "mixed",
    "llm_candidate",
    "llm_critic",
    "llm_drafter",
]
UniversalPolicyAuthorityPurpose = Literal[
    "compilation_facets",
    "legal_authority",
    "data_authority",
    "method_authority",
    "closeout_authority",
    "publication_authority",
    "projection_diagnostic",
]
UniversalPolicyFacetName = Literal[
    "instrument_type",
    "targeting_type",
    "delivery_channel",
    "funding_channel",
    "authority_type",
    "outcome_channel",
    "risk_facet",
    "method_need",
    "population_predicate",
    "geography_predicate",
    "time_predicate",
]
UniversalPolicyInstrumentType = Literal[
    "transfer",
    "subsidy",
    "tax",
    "regulation",
    "service",
    "procurement",
    "infrastructure",
    "information",
    "credit",
    "insurance",
    "price_control",
    "coordination",
]
UniversalPolicyTargetingType = Literal[
    "universal",
    "means_tested",
    "categorical",
    "geographic",
    "sectoral",
    "risk_based",
    "entitlement",
    "discretionary",
]
UniversalPolicyDeliveryChannel = Literal[
    "direct_payment",
    "tax_expenditure",
    "public_service",
    "procurement",
    "credit_registry",
    "regulatory_enforcement",
    "grant_program",
    "voucher",
    "information_campaign",
    "infrastructure_project",
]
UniversalPolicyFundingChannel = Literal[
    "budget_appropriation",
    "earmarked_tax",
    "donor_grant",
    "concessional_credit",
    "user_fee",
    "cross_subsidy",
    "regulatory_mandate",
    "unfunded_mandate",
]
UniversalPolicyRiskFacet = Literal[
    "budget_feasibility",
    "legal_exception",
    "equity_harm",
    "privacy_pii",
    "transportability",
    "strategic_gaming",
    "stale_source",
    "forged_citation",
    "source_contradiction",
    "ambiguous_human_review",
    "method_assumption",
    "fairness_threshold_reversal",
]
UniversalPopulationPredicate = Literal[
    "all_residents",
    "households",
    "children",
    "firms",
    "msmes",
    "low_income_renters",
    "workers",
    "patients",
    "students",
    "sector_members",
]
UniversalGeographyPredicate = Literal[
    "national",
    "state_or_region",
    "municipal",
    "rural",
    "urban",
    "displacement_affected",
    "custom_administrative_area",
]
UniversalTimePredicate = Literal[
    "single_period",
    "annual",
    "multi_year",
    "phased_rollout",
    "event_triggered",
    "retroactive",
    "open_ended",
]
UniversalPolicyCapabilityRealityLabel = Literal[
    "implemented",
    "contract_only",
    "producer_missing",
    "artifact_missing",
    "bridge_missing",
    "consumer_missing",
    "verification_missing",
    "implemented_but_not_orchestrated",
    "surface_missing",
    "surface_out_of_scope",
    "semantic_test_missing",
]

_AUTHORITY_PROTECTED_PURPOSES = frozenset(
    {
        "legal_authority",
        "data_authority",
        "method_authority",
        "closeout_authority",
        "publication_authority",
    }
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ApiMeta(BaseModel):
    """Api meta public type."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    generated_at: datetime = Field(default_factory=_utc_now)
    source_kinds: list[SourceKind] = Field(default_factory=list)


class AuthMeResponse(BaseModel):
    """Authenticated principal payload returned by the runtime ``/auth/me`` endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    user_id: str
    display_name: str
    tenant_id: str
    principal_type: Literal["anonymous", "service", "user"] = "user"
    cell_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    mfa_verified: bool = False
    feature_overrides: dict[str, bool] = Field(default_factory=dict)


class RuntimeApiProblemContext(BaseModel):
    """Sanitized request and exception context carried by a runtime problem."""

    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: str | None = None
    tenant: str | None = None
    run_id: str | None = None
    artifact_id: str | None = None
    dependency: str | None = None
    retry_state: str | None = None
    stage: str | None = None
    category: str | None = None


class RuntimeApiProblem(BaseModel):
    """Runtime API problem with a closed envelope and namespaced diagnostics."""

    model_config = ConfigDict(extra="forbid", strict=True)

    type: str = Field(default="about:blank")
    title: str
    status: int = Field(default=500, ge=100, le=599)
    detail: str
    code: str
    instance: str | None = None
    request_id: str | None = None
    # Backward-compatible fields for existing clients.
    error: str | None = None
    status_code: int = Field(default=500, ge=100, le=599)
    context: RuntimeApiProblemContext | None = None
    extensions: dict[str, JsonValue] | None = None

    @field_validator("extensions")
    @classmethod
    def validate_diagnostic_extensions(
        cls,
        value: dict[str, JsonValue] | None,
    ) -> dict[str, JsonValue] | None:
        """Reject extension values that cannot be serialized as finite JSON."""
        if value is None:
            return None
        try:
            json.dumps(value, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("runtime_api_problem_extensions_must_be_json") from exc
        return value


class RuntimeApiError(RuntimeApiProblem):
    """Backward-compatible alias for runtime API error payloads."""


class UnitRef(BaseModel):
    """Machine-readable unit identity plus a human display label."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    system: str = Field(default="ucum", min_length=1)
    display: str | None = None


class UniversalAuthorityProfile(BaseModel):
    """Authority profile consumed by the universal policy grammar compiler.

    The profile is intentionally separate from evidence authority. It may
    authorize deterministic compilation of facets, but LLM-sourced profiles may
    never authorize legal, data, method, closeout, or publication slots.
    """

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    authority_type: PolicyLayerLevel
    source_classification: UniversalPolicyGrammarSourceClassification = "deterministic_producer"
    authoritative_for: tuple[UniversalPolicyAuthorityPurpose, ...] = ("compilation_facets",)
    may_not_use_for: tuple[UniversalPolicyAuthorityPurpose, ...] = ()
    rule_version_ref: str = "policyos.policy_grammar.authority_profile.v1"

    @model_validator(mode="after")
    def _validate_llm_authority_boundary(self) -> UniversalAuthorityProfile:
        if self.source_classification.startswith("llm_"):
            illegal = sorted(set(self.authoritative_for) & _AUTHORITY_PROTECTED_PURPOSES)
            if illegal:
                raise ValueError(
                    f"{self.source_classification} cannot be authoritative_for: "
                    + ", ".join(illegal)
                )
        return self


class UniversalPolicyGrammarAuthorityEnvelope(BaseModel):
    """Authority envelope attached to a compiled universal policy design case."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1)
    authority_type: PolicyLayerLevel
    source_classification: UniversalPolicyGrammarSourceClassification
    authoritative_for: tuple[UniversalPolicyAuthorityPurpose, ...]
    may_not_use_for: tuple[UniversalPolicyAuthorityPurpose, ...]
    rule_version_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_llm_authority_boundary(self) -> UniversalPolicyGrammarAuthorityEnvelope:
        if self.source_classification.startswith("llm_"):
            illegal = sorted(set(self.authoritative_for) & _AUTHORITY_PROTECTED_PURPOSES)
            if illegal:
                raise ValueError(
                    f"{self.source_classification} cannot authorize protected purposes: "
                    + ", ".join(illegal)
                )
        return self


class UniversalPolicyFacetBase(BaseModel):
    """Common semantic grounding carried by every universal policy grammar facet."""

    model_config = ConfigDict(extra="forbid")

    facet_name: UniversalPolicyFacetName
    concept_spine_refs: tuple[str, ...] = Field(min_length=1)
    source_vocabulary_refs: tuple[str, ...] = Field(min_length=1)
    derivation_rule_ref: str = Field(min_length=1)


class UniversalPolicyInstrumentTypeFacet(UniversalPolicyFacetBase):
    """Controlled policy instrument facet."""

    facet_name: Literal["instrument_type"] = "instrument_type"
    value: UniversalPolicyInstrumentType


class UniversalPolicyTargetingTypeFacet(UniversalPolicyFacetBase):
    """Controlled policy targeting facet."""

    facet_name: Literal["targeting_type"] = "targeting_type"
    value: UniversalPolicyTargetingType


class UniversalPolicyDeliveryChannelFacet(UniversalPolicyFacetBase):
    """Controlled delivery-channel facet."""

    facet_name: Literal["delivery_channel"] = "delivery_channel"
    value: UniversalPolicyDeliveryChannel


class UniversalPolicyFundingChannelFacet(UniversalPolicyFacetBase):
    """Controlled funding-channel facet."""

    facet_name: Literal["funding_channel"] = "funding_channel"
    value: UniversalPolicyFundingChannel


class UniversalPolicyAuthorityTypeFacet(UniversalPolicyFacetBase):
    """Authority-layer facet reusing the IR governance policy-layer enum."""

    facet_name: Literal["authority_type"] = "authority_type"
    value: PolicyLayerLevel


class UniversalPolicyOutcomeChannelFacet(UniversalPolicyFacetBase):
    """Outcome-channel facet reusing the IR normative outcome enum."""

    facet_name: Literal["outcome_channel"] = "outcome_channel"
    value: NormativeOutcomeChannel


class UniversalPolicyRiskFacetRecord(UniversalPolicyFacetBase):
    """Controlled risk facet reconciled with deterministic critic/challenge vocabularies."""

    facet_name: Literal["risk_facet"] = "risk_facet"
    value: UniversalPolicyRiskFacet


class UniversalPolicyMethodNeedFacet(UniversalPolicyFacetBase):
    """Method-need facet reusing the IR observation identification-mode enum."""

    facet_name: Literal["method_need"] = "method_need"
    value: IdentificationMode


class UniversalPolicyPopulationPredicateFacet(UniversalPolicyFacetBase):
    """Controlled population predicate facet grounded in the concept spine."""

    facet_name: Literal["population_predicate"] = "population_predicate"
    value: UniversalPopulationPredicate


class UniversalPolicyGeographyPredicateFacet(UniversalPolicyFacetBase):
    """Controlled geography predicate facet grounded in the concept spine."""

    facet_name: Literal["geography_predicate"] = "geography_predicate"
    value: UniversalGeographyPredicate


class UniversalPolicyTimePredicateFacet(UniversalPolicyFacetBase):
    """Controlled time predicate facet grounded in temporal policy semantics."""

    facet_name: Literal["time_predicate"] = "time_predicate"
    value: UniversalTimePredicate


class UniversalPolicyFacets(BaseModel):
    """Facet set emitted by the W6.A universal policy grammar compiler."""

    model_config = ConfigDict(extra="forbid")

    instrument_type: UniversalPolicyInstrumentTypeFacet
    targeting_type: UniversalPolicyTargetingTypeFacet
    delivery_channel: UniversalPolicyDeliveryChannelFacet
    funding_channel: UniversalPolicyFundingChannelFacet
    authority_type: UniversalPolicyAuthorityTypeFacet
    outcome_channel: UniversalPolicyOutcomeChannelFacet
    risk_facet: UniversalPolicyRiskFacetRecord
    method_need: UniversalPolicyMethodNeedFacet
    population_predicate: UniversalPolicyPopulationPredicateFacet
    geography_predicate: UniversalPolicyGeographyPredicateFacet
    time_predicate: UniversalPolicyTimePredicateFacet

    def iter_facets(self) -> tuple[UniversalPolicyFacetBase, ...]:
        """Return all facets in stable compiler order."""
        return (
            self.instrument_type,
            self.targeting_type,
            self.delivery_channel,
            self.funding_channel,
            self.authority_type,
            self.outcome_channel,
            self.risk_facet,
            self.method_need,
            self.population_predicate,
            self.geography_predicate,
            self.time_predicate,
        )


class UniversalPolicyGrammarBlocker(BaseModel):
    """Typed blocker preventing grammar output from masquerading as authority."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    severity: Literal["blocked", "warning"] = "blocked"
    message: str = Field(min_length=1)
    facet_name: UniversalPolicyFacetName | None = None
    pattern_refs: tuple[str, ...] = Field(default=())
    missing_capability_label: UniversalPolicyCapabilityRealityLabel | None = None


class UniversalPolicyDesignCaseAuditSurface(BaseModel):
    """Machine/audit surface for inspecting compiled grammar output."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    status: UniversalPolicyGrammarStatus
    authoritative_for: tuple[UniversalPolicyAuthorityPurpose, ...]
    may_not_use_for: tuple[UniversalPolicyAuthorityPurpose, ...]
    facet_names: tuple[UniversalPolicyFacetName, ...] = Field(default=())
    blocker_codes: tuple[str, ...] = Field(default=())
    consumer_components: tuple[str, ...] = Field(default=())
    capability_reality_label: UniversalPolicyCapabilityRealityLabel


class UniversalPolicyDesignCase(BaseModel):
    """Compilation-only universal policy design case produced by W6.A."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.universal_policy_design_case.v1"] = (
        "policyos.universal_policy_design_case.v1"
    )
    case_id: str = Field(min_length=1)
    intent_id: str = Field(min_length=1)
    status: UniversalPolicyGrammarStatus
    authority_profile: UniversalAuthorityProfile
    authority_envelope: UniversalPolicyGrammarAuthorityEnvelope
    concept_spine_ref: str = Field(min_length=1)
    jurisdiction_spine_ref: str = Field(min_length=1)
    facets: UniversalPolicyFacets | None = None
    blockers: tuple[UniversalPolicyGrammarBlocker, ...] = Field(default=())
    downstream_consumer_components: tuple[str, ...] = Field(
        default=("obligation_graph", "claim_decomposition", "requirement_compilers")
    )
    audit_surface: UniversalPolicyDesignCaseAuditSurface
    capability_reality_label: UniversalPolicyCapabilityRealityLabel
    reuse_classification: Literal[
        "wire_existing",
        "extend_existing",
        "consolidate_existing",
        "build_new",
    ]
    reuse_evidence: tuple[str, ...] = Field(default=())
    produced_by: str = "polisyos.policy_grammar.compiler.PolicyGrammarCompiler"
    persisted_artifact_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _validate_compilation_state(self) -> UniversalPolicyDesignCase:
        if self.status == "compiled" and self.facets is None:
            raise ValueError("compiled universal policy design case requires facets")
        if self.status == "blocked" and not self.blockers:
            raise ValueError("blocked universal policy design case requires blockers")
        return self


class TemporalRef(BaseModel):
    """Bitemporal and snapshot scope carried by a decision-bearing value."""

    model_config = ConfigDict(extra="forbid")

    valid_at: datetime | None = None
    tx_at: datetime | None = None
    snapshot_id: str | None = None
    branch: str | None = None
    scenario_id: str | None = None


class TemporalScope(BaseModel):
    """Canonical bitemporal cursor used by runtime API and dashboard cache keys."""

    model_config = ConfigDict(extra="forbid")

    valid_at: datetime | None = None
    tx_at: datetime | None = None
    branch: str | None = None
    snapshot_id: str | None = None
    scenario_id: str | None = None


EpochProjectionStatus = Literal[
    "current",
    "stale",
    "revalidation_required",
    "contested",
    "not_established",
]
EpochPredicateProvenance = Literal[
    "recomputed",
    "independently_reconciled",
    "consumer_asserted",
    "institutionally_supplied",
    "not_established",
]


class EpochCertificateStalenessView(BaseModel):
    """One immutable certificate rendered against the requested semantic epoch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    certificate_ref: ArtifactRef
    authority_purpose: str = Field(min_length=1)
    bound_epoch_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    current_epoch_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    status: EpochProjectionStatus
    stale_reasons: tuple[str, ...] = ()
    trigger_event_refs: tuple[ArtifactRef, ...] = ()
    input_certificate_refs: tuple[ArtifactRef, ...] = ()
    recipe_ref: ArtifactRef
    native_coordinate_refs: tuple[str, ...] = ()
    rule_schema_profile_refs: tuple[str, ...] = ()
    revalidation_requirements: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _status_matches_epoch_relationship(self) -> EpochCertificateStalenessView:
        if self.status == "current":
            if self.current_epoch_ref is None or self.bound_epoch_ref != self.current_epoch_ref:
                raise ValueError("current certificate requires the requested epoch")
            if self.stale_reasons or self.revalidation_requirements:
                raise ValueError("current certificate cannot carry stale obligations")
        elif self.status in {"stale", "revalidation_required", "contested"}:
            if not self.stale_reasons:
                raise ValueError("non-current certificate requires a stale reason")
        return self


class EpochDerivedRecomputeView(BaseModel):
    """Owner-emitted recompute state, or an explicit engineering nonreceipt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["not_established", "pending", "running", "completed", "failed"]
    predicate_provenance: EpochPredicateProvenance
    evidence_ref: ArtifactRef | None = None
    evidence_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def _owner_evidence_controls_status(self) -> EpochDerivedRecomputeView:
        evidence = self.evidence_ref is not None and self.evidence_content_hash is not None
        if self.status == "not_established":
            if evidence or self.predicate_provenance != "not_established":
                raise ValueError("not-established recompute cannot carry positive owner evidence")
        elif not evidence or self.predicate_provenance not in {
            "recomputed",
            "independently_reconciled",
        }:
            raise ValueError("recompute status requires content-bound owner evidence")
        return self


class EpochDependencyStalenessView(BaseModel):
    """One revised input and the exact dependent target reached from it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_ref: ArtifactRef
    target_ref: ArtifactRef
    relation: str = Field(min_length=1)
    authority_purpose: str = Field(min_length=1)
    disposition: Literal[
        "unchanged",
        "annotation_only",
        "invalidate",
        "reissue",
        "supersede",
        "withdraw",
        "contested",
        "review_required",
    ]
    source_classes: tuple[EpochPerturbationClass, ...] = ()
    advisory_event_refs: tuple[ArtifactRef, ...] = ()
    owner_evidence_refs: tuple[ArtifactRef, ...] = ()
    recompute: EpochDerivedRecomputeView


class EpochPerturbationView(BaseModel):
    """Cause identity kept separate from advisory and adjudicated consequence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_class: EpochPerturbationClass
    event_ref: ArtifactRef
    target_ref: ArtifactRef
    scope: Literal["instance", "dependency_descendants"]
    observed_at: datetime
    advisory_posture: Literal["annotation_only", "review_required"]
    adjudicated_disposition: Literal[
        "annotation_only",
        "invalidate",
        "reissue",
        "supersede",
        "withdraw",
        "contested",
        "review_required",
    ]
    source_evidence_refs: tuple[ArtifactRef, ...] = ()
    owner_evidence_refs: tuple[ArtifactRef, ...] = ()

    @model_validator(mode="after")
    def _appeal_is_instance_scoped(self) -> EpochPerturbationView:
        if self.source_class == "appeal" and self.scope != "instance":
            raise ValueError("appeal projection requires instance scope")
        return self


class EpochBoundaryLineageView(BaseModel):
    """Visible immutable boundary between predecessor and successor epochs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    previous_epoch_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    current_epoch_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    transition_ref: ArtifactRef | None = None
    trigger_event_refs: tuple[ArtifactRef, ...] = ()
    predecessor_packet_ref: ArtifactRef | None = None
    successor_packet_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _boundary_is_real(self) -> EpochBoundaryLineageView:
        if self.previous_epoch_ref == self.current_epoch_ref:
            raise ValueError("epoch boundary requires distinct epochs")
        return self


class EpochOpenWorldRiskComponentView(BaseModel):
    """One non-numeric OpenWorldRisk component."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    component_id: str = Field(min_length=1)
    component_kind: Literal["model", "obligation", "calibration", "novel"]
    status: Literal["within_scope", "outside_scope", "not_established"]
    limitation_code: str = Field(min_length=1)
    evidence_ref: ArtifactRef | None = None
    predicate_provenance: Literal["independently_reconciled", "not_established"]


class EpochOpenWorldRiskView(BaseModel):
    """Actual vector posture and its fail-closed promotion consequence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["established", "limited", "not_established"]
    limitation_code: str = Field(min_length=1)
    vector_artifact_ref: ArtifactRef | None = None
    components: tuple[EpochOpenWorldRiskComponentView, ...] = ()
    promotion_frozen: bool

    @model_validator(mode="after")
    def _freeze_is_derived(self) -> EpochOpenWorldRiskView:
        expected = self.status != "established"
        if self.promotion_frozen != expected:
            raise ValueError("OpenWorldRisk promotion freeze must be derived from vector status")
        if self.status == "established" and any(
            row.status != "within_scope" for row in self.components
        ):
            raise ValueError("established OpenWorldRisk requires every component within scope")
        return self


class InstitutionalAuthorityAbsenceView(BaseModel):
    """A deliberate institutional non-appointment, not an engineering ticket."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    absence_class: Literal["institutional"] = "institutional"
    title: Literal["Authority not appointed"] = "Authority not appointed"
    role: Literal["epoch_predicate_policy_signer", "epoch_transition_signer"]
    authority_purpose: str = Field(min_length=1)
    capability_state: Literal["absent/unallocated"] = "absent/unallocated"
    observed_result: Literal["not_established"] = "not_established"
    refusal_code: Literal[
        "policy_admission_missing",
        "epoch_transition_signer_not_established",
    ]
    predicate_provenance: Literal["not_established"] = "not_established"
    consequence: str = Field(min_length=1)
    closure_condition: str = Field(min_length=1)
    inspectable_capabilities: tuple[str, ...] = ()
    source_refs: tuple[ArtifactRef, ...] = ()
    appointment_is_closure_precondition: Literal[False] = False

    @model_validator(mode="after")
    def _role_matches_refusal(self) -> InstitutionalAuthorityAbsenceView:
        expected = {
            "epoch_predicate_policy_signer": "policy_admission_missing",
            "epoch_transition_signer": "epoch_transition_signer_not_established",
        }[self.role]
        if self.refusal_code != expected:
            raise ValueError("institutional authority role/refusal mismatch")
        return self


class EngineeringCapabilityAbsenceView(BaseModel):
    """Assignable producer/read-bridge work with a named code owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    absence_class: Literal["engineering"] = "engineering"
    title: Literal["Engineering capability not wired"] = "Engineering capability not wired"
    capability: Literal["epoch_inheritance_recompute_status"] = "epoch_inheritance_recompute_status"
    missing_labels: tuple[Literal["producer_missing"], Literal["bridge_missing"]] = (
        "producer_missing",
        "bridge_missing",
    )
    candidate_owner_module: Literal["polisyos.runtime.quality.derived_observations"] = (
        "polisyos.runtime.quality.derived_observations"
    )
    candidate_owner_path: Literal["src/polisyos/runtime/quality/derived_observations.py"] = (
        "src/polisyos/runtime/quality/derived_observations.py"
    )
    missing_output: str = Field(min_length=1)
    consequence: str = Field(min_length=1)
    closure_condition: str = Field(min_length=1)
    institutional_dependency: Literal[False] = False


class EpochProjectionDenominatorView(BaseModel):
    """Evidence for the dependency/target set rather than a self-attested count."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    predicate_provenance: EpochPredicateProvenance
    denominator_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    source_count: int = Field(default=0, ge=0)
    target_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _positive_denominator_requires_owner_evidence(self) -> EpochProjectionDenominatorView:
        established = self.predicate_provenance in {
            "recomputed",
            "independently_reconciled",
        }
        if established != (self.denominator_ref is not None):
            raise ValueError("denominator evidence/provenance mismatch")
        return self


class EpochStalenessProjectionView(BaseModel):
    """Strict replay-bound owner projection for epoch, validity, and staleness chrome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["polisyos.runtime.epoch-staleness.v1"] = (
        "polisyos.runtime.epoch-staleness.v1"
    )
    run_id: str = Field(min_length=1)
    decision_packet_ref: ArtifactRef | None = None
    temporal_scope: TemporalScope
    requested_query_context_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    owner_as_of: datetime | None = None
    owner_time_reason: (
        Literal[
            "owner_time_not_established",
            "epoch_scope_unresolved",
        ]
        | None
    ) = None
    observed_at: datetime
    status: EpochProjectionStatus
    current_epoch_ref: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    scoped_epoch_refs: tuple[str, ...] = ()
    decision_validity_status: DecisionValidityStatus | None = None
    revalidation_required: bool
    denominator: EpochProjectionDenominatorView
    certificates: tuple[EpochCertificateStalenessView, ...] = ()
    dependencies: tuple[EpochDependencyStalenessView, ...] = ()
    perturbations: tuple[EpochPerturbationView, ...] = ()
    lineage: tuple[EpochBoundaryLineageView, ...] = ()
    open_world_risk: EpochOpenWorldRiskView
    institutional_absences: tuple[InstitutionalAuthorityAbsenceView, ...] = ()
    engineering_absences: tuple[EngineeringCapabilityAbsenceView, ...] = ()
    limitations: tuple[str, ...] = ()
    predicate_provenance: EpochPredicateProvenance
    fixture_only: bool = False
    projection_semantic_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _semantic_state_is_bound(self) -> EpochStalenessProjectionView:
        if (self.owner_as_of is None) == (self.owner_time_reason is None):
            raise ValueError("owner as_of requires exactly one value or typed reason")
        if self.revalidation_required != (
            self.status == "revalidation_required"
            or any(row.status == "revalidation_required" for row in self.certificates)
        ):
            raise ValueError("revalidation_required must be derived from projection state")
        if self.status == "current" and (
            self.current_epoch_ref is None
            or self.institutional_absences
            or self.predicate_provenance not in {"recomputed", "independently_reconciled"}
        ):
            raise ValueError("current epoch requires reconciled owner evidence")
        if self.projection_semantic_hash != epoch_staleness_semantic_hash(self):
            raise ValueError("epoch staleness projection semantic hash mismatch")
        return self


class EpochStalenessProjectionResponse(BaseModel):
    """HTTP response whose request metadata is outside the stable semantic identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: ApiMeta
    projection: EpochStalenessProjectionView


def epoch_staleness_semantic_hash(
    projection: EpochStalenessProjectionView,
) -> str:
    """Hash owner semantics while excluding server read time and the hash itself."""

    payload = projection.model_dump(
        mode="json",
        exclude={"observed_at", "projection_semantic_hash"},
    )
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    framed = b"polisyos.runtime.epoch-staleness.semantic.v1\x00" + encoded
    return "sha256:" + hashlib.sha256(framed).hexdigest()


class TemporalRange(BaseModel):
    """Inclusive range in which a temporal cursor can be used."""

    model_config = ConfigDict(extra="forbid")

    earliest: datetime | None = None
    latest: datetime | None = None


class TemporalGapRange(BaseModel):
    """Typed unavailable interval for a temporal surface."""

    model_config = ConfigDict(extra="forbid")

    start: datetime | None = None
    end: datetime | None = None
    reason_code: str
    label: str | None = None


class TemporalEventPoint(BaseModel):
    """Known event point used by scrubber snapping and capability diagnostics."""

    model_config = ConfigDict(extra="forbid")

    id: str
    timestamp: datetime
    kind: TemporalEventKind = "trace_event"
    label: str
    valid_at: datetime | None = None
    tx_at: datetime | None = None
    observed: bool = True


class TemporalSurfaceCapability(BaseModel):
    """Support declaration for one time-sensitive runtime surface."""

    model_config = ConfigDict(extra="forbid")

    surface: TemporalSurfaceSupport
    supported: bool
    resolution: str = "event"
    reason_code: str | None = None
    valid_range: TemporalRange | None = None
    tx_range: TemporalRange | None = None
    nearest_event_points: list[TemporalEventPoint] = Field(default_factory=list)
    gaps: list[TemporalGapRange] = Field(default_factory=list)


class TemporalIndexEvidence(BaseModel):
    """Index and slow-query evidence for temporal world lookups."""

    model_config = ConfigDict(extra="forbid")

    table: str
    adapter: str = "duckdb"
    index_name: str
    columns: list[str] = Field(default_factory=list)
    status: Literal["implemented", "recommended", "missing", "not_applicable"] = "implemented"
    slow_query_gate_ms: int = Field(default=500, ge=1)
    evidence_ref: str | None = None


class TemporalCapabilitiesView(BaseModel):
    """Temporal capability manifest for one run or the runtime as a whole."""

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    default_scope: TemporalScope | None = None
    valid_range: TemporalRange = Field(default_factory=TemporalRange)
    tx_range: TemporalRange = Field(default_factory=TemporalRange)
    resolution: str = "event"
    surfaces: list[TemporalSurfaceCapability] = Field(default_factory=list)
    event_points: list[TemporalEventPoint] = Field(default_factory=list)
    nearest_event_points: list[TemporalEventPoint] = Field(default_factory=list)
    supported_tables: list[str] = Field(default_factory=list)
    unsupported_surfaces: list[TemporalSurfaceSupport] = Field(default_factory=list)
    branch_support: bool = False
    snapshot_support: bool = False
    scenario_branch_support: Literal["explicit_only", "unsupported"] = "unsupported"
    graph_temporal_scope: Literal["full", "partial", "unsupported"] = "unsupported"
    slow_query_evidence: list[TemporalIndexEvidence] = Field(default_factory=list)


class TemporalCapabilitiesResponse(BaseModel):
    """Response envelope for temporal capabilities and gaps."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    capabilities: TemporalCapabilitiesView


class FabricSourceScorecardsResponse(BaseModel):
    """Response envelope for generated Fabric source scorecards."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    schema_version: str = "fabric.source_scorecard.v1"
    generated_at: datetime | None = None
    count: int = Field(default=0, ge=0)
    scorecards: dict[str, dict[str, Any]] = Field(default_factory=dict)


class FabricQualityTrustBatchRequest(BaseModel):
    """Run-scoped batch request for Fabric quality/trust metadata."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    decision_data_ids: list[str] = Field(default_factory=list, max_length=100)
    temporal_scope: TemporalScope | None = None


class FabricQualityBatchResponse(BaseModel):
    """Batch response for Fabric quality refs without client-side N+1 fetches."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    quality_refs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)


class FabricTrustBatchResponse(BaseModel):
    """Batch response for Fabric trust-envelope refs without client-side N+1 fetches."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    trust_refs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)


class FabricReplayRunResponse(BaseModel):
    """Run-scoped replay metadata extracted from Fabric decision-data envelopes."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    replay_refs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)


class FabricImpactAnalysisRequest(BaseModel):
    """Request body for Fabric-backed impact analysis."""

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    lineage_ids: list[str] = Field(default_factory=list, max_length=100)
    source_contract_ids: list[str] = Field(default_factory=list, max_length=100)
    temporal_scope: TemporalScope | None = None
    max_depth: int = Field(default=2, ge=1, le=8)


class FabricImpactRecord(BaseModel):
    """One origin/impact row for a Fabric lineage or source-contract subject."""

    model_config = ConfigDict(extra="forbid")

    subject_id: str
    subject_kind: FabricImpactSubjectKind
    lineage_status: VerificationStatus = "untraced"
    quality_status: str | None = None
    replay_status: str | None = None
    downstream_refs: list[str] = Field(default_factory=list)
    upstream_refs: list[str] = Field(default_factory=list)
    affected_decision_data_ids: list[str] = Field(default_factory=list)
    source_contract_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class FabricImpactAnalysisResponse(BaseModel):
    """Response envelope for Fabric impact analysis."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    impacts: list[FabricImpactRecord] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class VerificationMetadata(BaseModel):
    """Audit metadata used by Trust View without changing the underlying truth."""

    model_config = ConfigDict(extra="forbid")

    hash: str | None = None
    verification_status: VerificationStatus = "untraced"
    verified_by: str | None = None
    verified_at: datetime | None = None
    verification_method: str | None = None
    freshness: LineageFreshness = "unknown"
    dispute_status: DisputeStatus = "none"
    temporal_scope: TemporalScope | None = None


class TrustMetadataRef(BaseModel):
    """Selected runtime object and its Trust View metadata payload."""

    model_config = ConfigDict(extra="forbid")

    subject_id: str = Field(min_length=1)
    subject_kind: Literal["quantity", "authored_text", "artifact", "lineage", "chart"] = "lineage"
    trust_metadata: VerificationMetadata


class LineageCompactSummaryItem(BaseModel):
    """One compact lineage crumb suitable for inline and hover surfaces."""

    model_config = ConfigDict(extra="forbid")

    kind: LineageSummaryKind = "unknown"
    label: str
    id: str | None = None


class LineageRef(BaseModel):
    """Typed lineage reference embedded inside `QuantityValue` envelopes."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    hash: str | None = None
    status: VerificationStatus = "untraced"
    freshness: LineageFreshness = "unknown"
    summary: dict[str, str] = Field(default_factory=dict)
    compact_summary: list[LineageCompactSummaryItem] = Field(default_factory=list)
    reason_code: str | None = None
    tracking_issue: str | None = None
    trust_metadata: VerificationMetadata | None = None
    artifact_ref: ArtifactRef | None = None
    artifact_ref_provenance: Literal["run_output_ref", "reader_materialized"] | None = None
    source_run_id: str | None = None

    @model_validator(mode="after")
    def _validate_untraced_contract(self) -> LineageRef:
        if self.id == "untraced" and self.status != "untraced":
            raise ValueError('lineage id "untraced" requires status="untraced"')
        if self.status == "untraced":
            if not self.reason_code:
                raise ValueError("untraced lineage requires reason_code")
            if not self.tracking_issue:
                raise ValueError("untraced lineage requires tracking_issue")
        if self.artifact_ref is None and self.artifact_ref_provenance is not None:
            raise ValueError("lineage provenance requires an artifact_ref")
        if self.artifact_ref is not None and self.artifact_ref.manifest_profile_sha256 is None:
            raise ValueError("lineage artifact_ref must select a manifest profile")
        if self.source_run_id is not None and self.artifact_ref is None:
            raise ValueError("source_run_id requires a selected artifact profile")
        if self.source_run_id is not None and self.artifact_ref_provenance is None:
            raise ValueError("source_run_id requires selected profile provenance")
        if self.artifact_ref_provenance == "run_output_ref" and self.source_run_id is None:
            raise ValueError("run_output_ref provenance requires source_run_id")
        return self


class QuantityUncertainty(BaseModel):
    """Uncertainty envelope for a decision-bearing quantity."""

    model_config = ConfigDict(extra="forbid")

    ci_80: tuple[float, float] | None = None
    ci_95: tuple[float, float] | None = None
    quantiles: dict[str, float] = Field(default_factory=dict)
    method: Literal["bootstrap", "bayesian", "analytic", "simulation", "none"] | str | None = None
    identifiability: Literal["identified", "estimated", "assumed", "unknown"] = "unknown"
    disputed: bool = False


class QuantityValue(BaseModel):
    """Canonical envelope for every numeric value that can influence a decision."""

    model_config = ConfigDict(extra="forbid")

    point: float | None = None
    unit: UnitRef
    metric_id: str | None = None
    lineage: LineageRef
    uncertainty: QuantityUncertainty | None = None
    time: TemporalRef | None = None
    quantity_class: QuantityClass = "decision"
    label: str | None = None


class LineageGraphNode(BaseModel):
    """Runtime lineage graph node projected from artifact or Fabric provenance."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str = "unknown"
    label: str
    media_type: str | None = None
    manifest_profile_sha256: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageGraphEdge(BaseModel):
    """Runtime lineage graph edge projected from artifact or Fabric provenance."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    target_id: str
    relation: str
    source_manifest_profile_sha256: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    target_manifest_profile_sha256: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineageExportLinks(BaseModel):
    """Stable export links for external lineage interoperability formats."""

    model_config = ConfigDict(extra="forbid")

    openlineage: str
    prov: str


class LineageGraphView(BaseModel):
    """Compact plus full runtime lineage graph view."""

    model_config = ConfigDict(extra="forbid")

    id: str
    status: VerificationStatus = "untraced"
    hash: str | None = None
    freshness: LineageFreshness = "unknown"
    compact_summary: list[LineageCompactSummaryItem] = Field(default_factory=list)
    nodes: list[LineageGraphNode] = Field(default_factory=list)
    edges: list[LineageGraphEdge] = Field(default_factory=list)
    root_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    selected_artifact_ref: ArtifactRef | None = None
    profile_binding_status: Literal["verified", "not_established"] | None = None
    artifact_ref_provenance: Literal["run_output_ref", "reader_materialized"] | None = None
    source_run_id: str | None = None
    exports: LineageExportLinks
    metadata: dict[str, Any] = Field(default_factory=dict)
    trust_metadata: VerificationMetadata | None = None

    @model_validator(mode="after")
    def _validate_profile_binding_surface(self) -> LineageGraphView:
        if self.profile_binding_status == "verified" and self.selected_artifact_ref is None:
            raise ValueError("verified profile binding requires selected_artifact_ref")
        if self.source_run_id is not None and self.selected_artifact_ref is None:
            raise ValueError("source_run_id requires a selected artifact profile")
        if self.source_run_id is not None and self.profile_binding_status != "verified":
            raise ValueError("source_run_id requires verified profile binding")
        if self.source_run_id is not None and self.artifact_ref_provenance is None:
            raise ValueError("source_run_id requires selected profile provenance")
        if self.profile_binding_status == "verified" and self.artifact_ref_provenance is None:
            raise ValueError("verified profile binding requires selected profile provenance")
        if self.profile_binding_status == "not_established" and self.trust_metadata is not None:
            raise ValueError("unestablished profile binding cannot carry trust metadata")
        if self.artifact_ref_provenance is not None and self.selected_artifact_ref is None:
            raise ValueError("profile provenance requires selected_artifact_ref")
        if self.artifact_ref_provenance == "run_output_ref" and self.source_run_id is None:
            raise ValueError("run_output_ref provenance requires source_run_id")
        return self


class LineageBatchRequest(BaseModel):
    """Batch lineage lookup request used to avoid client-side N+1 fetches."""

    model_config = ConfigDict(extra="forbid")

    lineage_ids: list[str] = Field(default_factory=list, min_length=1, max_length=100)
    run_id: str | None = Field(default=None, min_length=1)
    selected_artifact_refs: list[ArtifactRef | None] | None = None

    @model_validator(mode="after")
    def _validate_selected_profile_alignment(self) -> LineageBatchRequest:
        if self.selected_artifact_refs is None:
            if self.run_id is not None:
                raise ValueError("run_id requires aligned selected_artifact_refs")
            return self
        if len(self.selected_artifact_refs) != len(self.lineage_ids):
            raise ValueError("selected_artifact_refs must align with lineage_ids")
        if any(
            ref is not None and ref.manifest_profile_sha256 is None
            for ref in self.selected_artifact_refs
        ):
            raise ValueError("selected_artifact_refs must select manifest profiles")
        return self


class LineageResponse(BaseModel):
    """Response envelope returned by one runtime lineage lookup."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    lineage: LineageGraphView


class LineageBatchResolution(BaseModel):
    """Map one requested lineage selector and profile to its resolved response."""

    model_config = ConfigDict(extra="forbid")

    requested_lineage_id: str
    resolved_lineage_id: str


class LineageBatchResponse(BaseModel):
    """Response envelope returned by runtime lineage batch lookup."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    lineages: list[LineageGraphView] = Field(default_factory=list)
    # Missing/null is a legacy response. Consumers may then match exact IDs only.
    lineage_resolutions: list[LineageBatchResolution] | None = None


class LineageExportResponse(BaseModel):
    """Response envelope returned by runtime lineage export endpoints."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    lineage_id: str
    format: Literal["openlineage", "prov"]
    payload: dict[str, Any]


class QuantityCoverageEntry(BaseModel):
    """One numeric field discovered by the quantity coverage inventory."""

    model_config = ConfigDict(extra="forbid")

    path: str
    quantity_class: QuantityClass
    status: VerificationStatus
    lineage_id: str | None = None
    metric_id: str | None = None
    reason_code: str | None = None
    tracking_issue: str | None = None


class QuantityCoverageSummary(BaseModel):
    """Class-aware coverage counts for quantity law migration."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(default=0, ge=0)
    decision: int = Field(default=0, ge=0)
    telemetry: int = Field(default=0, ge=0)
    layout: int = Field(default=0, ge=0)
    debug: int = Field(default=0, ge=0)
    traced: int = Field(default=0, ge=0)
    untraced: int = Field(default=0, ge=0)


class RunQuantitiesResponse(BaseModel):
    """Response envelope returned by the run quantity inventory endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    source_kind: SourceKind
    temporal_scope: TemporalScope | None = None
    quantities: list[QuantityValue] = Field(default_factory=list)
    coverage: QuantityCoverageSummary = Field(default_factory=QuantityCoverageSummary)
    entries: list[QuantityCoverageEntry] = Field(default_factory=list)


class ComparisonFrame(BaseModel):
    """Canonical scope that makes two run payloads comparable."""

    model_config = ConfigDict(extra="forbid")

    run_a: str
    run_b: str
    metric_set: list[str] = Field(default_factory=list)
    population: str | None = None
    unit_policy: Literal["canonical", "source", "mixed"] = "canonical"
    temporal_scope: TemporalScope | None = None
    scenario_scope: dict[str, Any] = Field(default_factory=dict)
    assumption_set: list[str] = Field(default_factory=list)


class ComparabilityReport(BaseModel):
    """Pre-flight report that prevents misleading run comparisons."""

    model_config = ConfigDict(extra="forbid")

    status: ComparabilityStatus
    warnings: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)


class LineageDelta(BaseModel):
    """Compact provenance drift summary for one compared metric."""

    model_config = ConfigDict(extra="forbid")

    source_changed: bool = False
    model_changed: bool = False
    hash_changed: bool = False
    freshness_changed: bool = False
    verification_changed: str | None = None
    notes: list[str] = Field(default_factory=list)


class DeltaDistribution(BaseModel):
    """Distributional summary of a metric delta."""

    model_config = ConfigDict(extra="forbid")

    quantiles: dict[str, float] = Field(default_factory=dict)
    mean_shift: float | None = None
    median_shift: float | None = None
    ci_overlap: bool | None = None


class DeltaQuantity(BaseModel):
    """One decision-bearing metric comparison with quantity-law envelopes."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str
    label: str
    a: QuantityValue | None = None
    b: QuantityValue | None = None
    delta_absolute: QuantityValue | None = None
    delta_relative: QuantityValue | None = None
    delta_distribution: DeltaDistribution = Field(default_factory=DeltaDistribution)
    significance: DeltaSignificance = "uncertain"
    dominance: DeltaDominance = "unknown"
    decision_salience: float = Field(default=0.0, ge=0.0, le=1.0)
    lineage_delta: LineageDelta = Field(default_factory=LineageDelta)


class CompareCandidate(BaseModel):
    """One candidate run suggested as a meaningful comparator."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    label: str | None = None
    relation: CompareCandidateRelation = "recommended"
    status: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    comparability: ComparabilityReport


class CompareRunResponse(BaseModel):
    """Response envelope for the best-in-class policy diff endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    status: CompareResponseStatus = "computed"
    temporal_scope: TemporalScope | None = None
    comparison_frame: ComparisonFrame
    comparability: ComparabilityReport
    deltas: list[DeltaQuantity] = Field(default_factory=list)


class CompareCandidatesResponse(BaseModel):
    """Response envelope for compare-candidate discovery."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    candidates: list[CompareCandidate] = Field(default_factory=list)


class ScenarioConstraint(BaseModel):
    """One explicit constraint that bounds a scenario intervention."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str
    field: str | None = None
    severity: ScenarioConstraintSeverity = "warning"
    operator: str | None = None
    value: QuantityValue | None = None
    message: str | None = None


class ScenarioAssumption(BaseModel):
    """Named scenario assumption with provenance."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    label: str
    status: ScenarioAssumptionStatus
    lineage: LineageRef
    description: str | None = None


class ScenarioIntervention(BaseModel):
    """One operator-visible policy intervention inside a scenario manifest."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    operator: ScenarioInterventionOperator
    value: QuantityValue
    baseline_value: QuantityValue | None = None
    constraint_ids: list[str] = Field(default_factory=list)


class ScenarioRef(BaseModel):
    """Stable reference carried by every counterfactual value."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    status: ScenarioStatus
    baseline_run_id: str = Field(min_length=1)
    temporal_scope: TemporalScope | None = None
    lineage: LineageRef
    assumption_ids: list[str] = Field(min_length=1)
    manifest_hash: str | None = None


class ScenarioManifest(BaseModel):
    """Manifest that makes a counterfactual named, reproducible and auditable."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    baseline_run_id: str = Field(min_length=1)
    status: ScenarioStatus
    lifecycle_status: ScenarioLifecycleStatus = "generated"
    revision: int = Field(default=1, ge=1)
    manifest_hash: str = ""
    temporal_scope: TemporalScope | None = None
    policy_question: str = Field(min_length=1)
    author: str = Field(min_length=1)
    affected_population: str | None = None
    temporal_window: TemporalRange | None = None
    model_family: str = Field(min_length=1)
    model_version: str | None = None
    model_lineage: LineageRef
    baseline_lineage: LineageRef | None = None
    baseline_hash: str | None = None
    computed_at: datetime | None = None
    saved_at: datetime | None = None
    promoted_at: datetime | None = None
    validity_window: TemporalRange | None = None
    known_limitations: list[str] = Field(default_factory=list)
    stale_reasons: list[str] = Field(default_factory=list)
    interventions: list[ScenarioIntervention] = Field(min_length=1)
    assumptions: list[ScenarioAssumption] = Field(min_length=1)
    constraints: list[ScenarioConstraint] = Field(default_factory=list)
    phase4_gate_verdict: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_scenario_manifest(self) -> ScenarioManifest:
        assumption_ids = {assumption.id for assumption in self.assumptions}
        constraint_ids = {constraint.id for constraint in self.constraints}
        for intervention in self.interventions:
            unknown_constraints = [
                constraint_id
                for constraint_id in intervention.constraint_ids
                if constraint_id not in constraint_ids
            ]
            if unknown_constraints:
                raise ValueError(
                    "intervention references unknown constraints: "
                    + ",".join(sorted(unknown_constraints))
                )
        if not assumption_ids:
            raise ValueError("scenario manifest requires at least one assumption")
        return self


class CounterfactualMetric(BaseModel):
    """Actual, scenario and delta values for one metric."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str = Field(min_length=1)
    label: str
    actual: QuantityValue
    counterfactual: QuantityValue
    delta: QuantityValue
    scenario_ref: ScenarioRef
    assumption_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_counterfactual_metric(self) -> CounterfactualMetric:
        if not set(self.assumption_ids).issubset(set(self.scenario_ref.assumption_ids)):
            raise ValueError("counterfactual metric references assumptions outside ScenarioRef")
        for field_name in ("counterfactual", "delta"):
            quantity = getattr(self, field_name)
            if quantity.time is None or quantity.time.scenario_id != self.scenario_ref.id:
                raise ValueError(
                    f"{field_name} quantity must carry time.scenario_id={self.scenario_ref.id}"
                )
        return self


class ScenarioCapability(BaseModel):
    """Support declaration for one counterfactual runtime surface or metric."""

    model_config = ConfigDict(extra="forbid")

    surface: ScenarioSurfaceSupport
    supported: bool
    reason_code: str | None = None
    metric_id: str | None = None
    supported_modes: list[CounterfactualMode] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class ScenarioCreateRequest(BaseModel):
    """Request body for saving a scenario draft under a baseline run."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    policy_question: str = Field(min_length=1)
    author: str = Field(default="operator", min_length=1)
    interventions: list[ScenarioIntervention] = Field(min_length=1)
    assumptions: list[ScenarioAssumption] = Field(min_length=1)
    constraints: list[ScenarioConstraint] = Field(default_factory=list)
    affected_population: str | None = None
    model_family: str = Field(default="operator-specified", min_length=1)
    model_version: str | None = None
    known_limitations: list[str] = Field(default_factory=list)
    regime_shift_forecast_bundle_ref: str | None = None


class ScenarioListResponse(BaseModel):
    """Response envelope for scenarios available on a run."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    scenarios: list[ScenarioManifest] = Field(default_factory=list)


class ScenarioManifestResponse(BaseModel):
    """Response envelope for one scenario manifest."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    scenario: ScenarioManifest


class ScenarioCapabilitiesResponse(BaseModel):
    """Response envelope for scenario support and unsupported surfaces."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str | None = None
    scenario_id: str | None = None
    temporal_scope: TemporalScope | None = None
    capabilities: list[ScenarioCapability] = Field(default_factory=list)


class CounterfactualMetricsResponse(BaseModel):
    """Response envelope for normalized actual + scenario metrics."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    scenario: ScenarioManifest
    metrics: dict[str, CounterfactualMetric] = Field(default_factory=dict)


class BureaucraticTemplateRef(BaseModel):
    """Versioned jurisdictional template identity used by bureaucratic renderers."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    genre: BureaucraticGenre
    jurisdiction: str = Field(default="ua", min_length=1)
    locale: str = Field(default="uk-UA", min_length=1)
    legal_review_status: Literal["pending_external_review", "approved", "rejected"] = (
        "pending_external_review"
    )


class BureaucraticAuthorship(BaseModel):
    """Authorship, agent and review attribution for one document block."""

    model_config = ConfigDict(extra="forbid")

    author: str = "PolicyOS"
    author_role: str = "system"
    agent_version: str | None = None
    timestamp: datetime | None = None
    reviewed_by_human: bool = False


class BureaucraticBlock(BaseModel):
    """Canonical document AST block independent of HTML/PDF/DOCX renderers."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    kind: BureaucraticBlockKind
    title: str | None = None
    text: str | None = None
    level: int = Field(default=1, ge=1, le=6)
    number: str | None = None
    items: list[str] = Field(default_factory=list)
    quantity: QuantityValue | None = None
    epistemic_origin: BureaucraticEpistemicKind
    authorship: BureaucraticAuthorship = Field(default_factory=BureaucraticAuthorship)
    provenance: list[LineageCompactSummaryItem] = Field(default_factory=list)
    raw_source_refs: list[str] = Field(default_factory=list)
    children: list[BureaucraticBlock] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BureaucraticEpistemicSummary(BaseModel):
    """Document-level block-origin proportions shown in the epistemic legend."""

    model_config = ConfigDict(extra="forbid")

    evidence_filled: float = Field(default=0.0, ge=0.0, le=1.0)
    model_generated: float = Field(default=0.0, ge=0.0, le=1.0)
    operator_filled: float = Field(default=0.0, ge=0.0, le=1.0)
    imported: float = Field(default=0.0, ge=0.0, le=1.0)


class BureaucraticDocument(BaseModel):
    """Machine-checkable bureaucratic document AST rendered from a decision packet."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    packet_id: str = Field(min_length=1)
    genre: BureaucraticGenre
    jurisdiction: str = Field(default="ua", min_length=1)
    template: BureaucraticTemplateRef
    status: BureaucraticDocumentStatus = "draft"
    title: str
    language: str = "uk"
    watermark: str
    render_timestamp: datetime = Field(default_factory=_utc_now)
    packet_hash: str
    temporal_scope: TemporalScope | None = None
    trust_view: bool = False
    blocks: list[BureaucraticBlock] = Field(default_factory=list)
    annexes: list[BureaucraticBlock] = Field(default_factory=list)
    epistemic_summary: BureaucraticEpistemicSummary = Field(
        default_factory=BureaucraticEpistemicSummary
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class BureaucraticRenderRequest(BaseModel):
    """Request body for rendering one packet into a jurisdictional document AST."""

    model_config = ConfigDict(extra="forbid")

    genre: BureaucraticGenre
    jurisdiction: str = Field(default="ua", min_length=1)
    template_version: str | None = None
    manifest_profile_sha256: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
        description="Optional exact manifest profile for the source artifact.",
    )
    temporal_scope: TemporalScope | None = None
    trust_view: bool = False


class BureaucraticRenderResponse(BaseModel):
    """Response envelope for bureaucratic document AST rendering."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    document: BureaucraticDocument


class BureaucraticExportResponse(BaseModel):
    """Deterministic export packet for HTML/PDF/DOCX generation."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    document_id: str
    packet_id: str
    format: BureaucraticExportFormat
    content_type: str
    filename: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CursorPage(BaseModel):
    """Cursor page public type."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=50, ge=1, le=200)
    cursor: str | None = None
    next_cursor: str | None = None
    count: int = Field(default=0, ge=0)
    total: int | None = Field(default=None, ge=0)


class RunRecordV1(BaseModel):
    """Run record V 1 public type."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    tenant_id: str | None = None
    cell_id: str | None = None
    execution_profile: str | None = None
    control_job_id: str | None = None
    has_trace: bool = False


class RunSummary(RunRecordV1):
    """List-view projection of a run with artifact counts, warnings, and decision status."""

    run_terminality: RunTerminality
    root_artifact_count: int = Field(default=0, ge=0)
    has_workflow_report: bool = False
    warnings: list[str] = Field(default_factory=list)
    decision_validity_status: DecisionValidityStatus | None = None
    decision_validity_checked_at: datetime | None = None
    decision_review_required: bool = False
    decision_superseded_by_ref: ArtifactRef | None = None


class RunOperatorProjectionStateLabel(BaseModel):
    """Projection lifecycle label with explicit authority semantics."""

    model_config = ConfigDict(extra="forbid")

    state: OperatorProjectionState
    label: str
    authority: OperatorProjectionAuthority


class RunOperatorDiagnostic(BaseModel):
    """Typed operator root-cause projection attached to run details."""

    model_config = ConfigDict(extra="forbid")

    authoritative_runtime_state: str
    projection_source: str
    owner: str
    phase: str
    first_blocking_cause: str
    upstream_missing_input: str | None = None
    downstream_impact: str
    authority_refs: dict[str, str] = Field(default_factory=dict)
    blocker_overridable: bool = False
    evidence_refs: list[str] = Field(default_factory=list)
    next_diagnostic_command: str
    projection_labels: list[RunOperatorProjectionStateLabel] = Field(default_factory=list)


class RunN5InteractionSample(BaseModel):
    """One shared-seed derived interaction value in a candidate N5 artifact."""

    model_config = ConfigDict(extra="forbid")

    seed: int
    value: float

    @field_validator("seed", mode="before")
    @classmethod
    def _strict_seed(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("run_n5_interaction_seed_not_integer")
        return value

    @field_validator("value", mode="before")
    @classmethod
    def _finite_value(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("run_n5_interaction_value_not_real")
        if not math.isfinite(float(value)):
            raise ValueError("run_n5_interaction_value_non_finite")
        return value


class RunN5InteractionSamplingSummary(BaseModel):
    """Recomputable shared-seed mean and sample SE for one interaction step."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["estimated", "standard_error_not_estimated"]
    replicate_count: int = Field(ge=1)
    seeds: tuple[int, ...] = Field(min_length=1)
    samples: tuple[RunN5InteractionSample, ...] = Field(min_length=1)
    mean: float
    standard_error: float | None

    @model_validator(mode="after")
    def _recompute_summary(self) -> RunN5InteractionSamplingSummary:
        if (
            self.replicate_count != len(self.seeds)
            or self.replicate_count != len(self.samples)
            or len(set(self.seeds)) != len(self.seeds)
            or tuple(sample.seed for sample in self.samples) != self.seeds
        ):
            raise ValueError("run_n5_interaction_seed_denominator_mismatch")
        values = [sample.value for sample in self.samples]
        expected_mean = sum(values) / len(values)
        if not math.isfinite(self.mean) or not math.isclose(
            self.mean, expected_mean, rel_tol=1e-12, abs_tol=1e-12
        ):
            raise ValueError("run_n5_interaction_mean_recomputation_mismatch")
        expected_status = "standard_error_not_estimated" if len(values) == 1 else "estimated"
        if self.status != expected_status:
            raise ValueError("run_n5_interaction_sampling_status_mismatch")
        if len(values) == 1:
            if self.standard_error is not None:
                raise ValueError("run_n5_interaction_single_draw_se_must_be_unestimated")
        else:
            expected_se = math.sqrt(
                sum((value - expected_mean) ** 2 for value in values)
                / (len(values) - 1)
                / len(values)
            )
            if self.standard_error is None or not math.isclose(
                self.standard_error, expected_se, rel_tol=1e-12, abs_tol=1e-12
            ):
                raise ValueError("run_n5_interaction_se_recomputation_mismatch")
        return self


class RunN5InteractionTerm(BaseModel):
    """One pairwise interaction mean and its paired replicate vector."""

    model_config = ConfigDict(extra="forbid")

    atom_ids: tuple[str, str]
    outcome: str = Field(min_length=1)
    by_step: dict[int, float]
    replication_sampling_by_step: dict[int, RunN5InteractionSamplingSummary] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def _bind_sampling_to_means(self) -> RunN5InteractionTerm:
        if set(self.replication_sampling_by_step) - set(self.by_step):
            raise ValueError("run_n5_interaction_sample_step_without_mean")
        for step, summary in self.replication_sampling_by_step.items():
            if not math.isclose(self.by_step[step], summary.mean, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("run_n5_interaction_sample_mean_mismatch")
        return self


class RunN5InteractionEvidence(BaseModel):
    """Candidate-only interaction evidence with legacy epochs explicitly limited."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "policyos.runtime.joint_simulation_horizon.v1",
        "policyos.runtime.joint_simulation_horizon.v2",
        "policyos.runtime.joint_simulation_horizon.v3",
        "policyos.runtime.joint_simulation_horizon.v4",
    ]
    numeric_interaction: Literal["none", "additive", "non_additive", "unsupported"]
    numeric_interaction_basis: Literal[
        "finite_checked_model_point_estimate_only", "not_established"
    ]
    interaction_sampling_status: Literal[
        "estimated", "standard_error_not_estimated", "not_established"
    ]
    interaction_terms: tuple[RunN5InteractionTerm, ...] = ()
    higher_order_residuals: dict[str, dict[int, float]] = Field(default_factory=dict)
    higher_order_residual_sampling: dict[str, dict[int, RunN5InteractionSamplingSummary]] = Field(
        default_factory=dict
    )
    checked_interaction_orders: tuple[int, ...] = ()
    authority_purpose: Literal["candidate_checked_model_only"] = "candidate_checked_model_only"
    publication_authority: Literal[False] = False

    @model_validator(mode="after")
    def _verify_interaction_evidence_epoch(self) -> RunN5InteractionEvidence:
        current = self.schema_version == "policyos.runtime.joint_simulation_horizon.v4"
        if not current:
            if (
                self.numeric_interaction != "unsupported"
                or self.numeric_interaction_basis != "not_established"
                or self.interaction_sampling_status != "not_established"
                or any(term.replication_sampling_by_step for term in self.interaction_terms)
                or self.higher_order_residual_sampling
            ):
                raise ValueError("run_n5_legacy_interaction_uncertainty_laundered")
            return self
        if (self.interaction_sampling_status == "estimated") != (
            self.numeric_interaction_basis == "finite_checked_model_point_estimate_only"
        ):
            raise ValueError("run_n5_interaction_basis_status_mismatch")
        if (
            self.interaction_sampling_status != "estimated"
            and self.numeric_interaction != "unsupported"
        ):
            raise ValueError("run_n5_unestimated_interaction_classification_not_limited")
        if self.interaction_sampling_status != "not_established":
            for term in self.interaction_terms:
                if set(term.by_step) != set(term.replication_sampling_by_step):
                    raise ValueError("run_n5_interaction_summary_step_missing")
            for outcome, by_step in self.higher_order_residuals.items():
                if set(by_step) != set(self.higher_order_residual_sampling.get(outcome, {})):
                    raise ValueError("run_n5_residual_summary_step_missing")
        return self


def _validate_run_n5_interaction_scope(
    evidence: RunN5InteractionEvidence | None,
    *,
    atom_ids: tuple[str, ...],
    selected_outcomes: tuple[str, ...],
    executed_steps: tuple[int, ...],
    replication_seeds: tuple[int, ...],
) -> None:
    """Bind current interaction records to the selected, source-derived N5 basis."""

    if (
        evidence is None
        or evidence.schema_version != "policyos.runtime.joint_simulation_horizon.v4"
    ):
        return
    if (
        not atom_ids
        or not selected_outcomes
        or not executed_steps
        or not replication_seeds
        or len(set(atom_ids)) != len(atom_ids)
        or len(set(selected_outcomes)) != len(selected_outcomes)
        or len(set(executed_steps)) != len(executed_steps)
        or len(set(replication_seeds)) != len(replication_seeds)
        or any(not value for value in (*atom_ids, *selected_outcomes))
    ):
        raise ValueError("run_n5_interaction_scope_parent_context_missing_or_invalid")

    expected_pairs = {frozenset(pair) for pair in itertools.combinations(atom_ids, 2)}
    expected_steps = set(executed_steps)
    expected_outcomes = set(selected_outcomes)
    actual_term_keys: set[tuple[frozenset[str], str]] = set()
    sampling_established = evidence.interaction_sampling_status != "not_established"
    for term in evidence.interaction_terms:
        pair = frozenset(term.atom_ids)
        term_key = (pair, term.outcome)
        if (
            len(pair) != 2
            or pair not in expected_pairs
            or term.outcome not in expected_outcomes
            or term_key in actual_term_keys
        ):
            raise ValueError("run_n5_interaction_scope_foreign_or_duplicate_pair")
        actual_term_keys.add(term_key)
        mean_steps = set(term.by_step)
        summary_steps = set(term.replication_sampling_by_step)
        if mean_steps != expected_steps:
            raise ValueError("run_n5_interaction_scope_pair_step_basis_incomplete")
        if not summary_steps.issubset(expected_steps) or not summary_steps.issubset(mean_steps):
            raise ValueError("run_n5_interaction_scope_foreign_step")
        for summary in term.replication_sampling_by_step.values():
            if summary.seeds != replication_seeds:
                raise ValueError("run_n5_interaction_scope_seed_basis_mismatch")
        if sampling_established and summary_steps != expected_steps:
            raise ValueError("run_n5_interaction_scope_pair_step_basis_incomplete")
        if summary_steps and summary_steps != expected_steps:
            raise ValueError("run_n5_interaction_scope_pair_step_basis_incomplete")

    expected_term_keys = {
        (frozenset(pair), outcome)
        for pair in itertools.combinations(atom_ids, 2)
        for outcome in selected_outcomes
    }
    if actual_term_keys != expected_term_keys:
        raise ValueError("run_n5_interaction_scope_pair_set_incomplete")

    residual_outcomes = set(evidence.higher_order_residuals)
    residual_sampling_outcomes = set(evidence.higher_order_residual_sampling)
    expected_residual_outcomes = expected_outcomes if len(atom_ids) >= 3 else set()
    if (
        not residual_outcomes.issubset(expected_residual_outcomes)
        or not residual_sampling_outcomes.issubset(expected_residual_outcomes)
        or not residual_sampling_outcomes.issubset(residual_outcomes)
    ):
        raise ValueError("run_n5_interaction_scope_foreign_residual_outcome")
    for outcome, by_step in evidence.higher_order_residuals.items():
        mean_steps = set(by_step)
        summary_steps = set(evidence.higher_order_residual_sampling.get(outcome, {}))
        if mean_steps != expected_steps:
            raise ValueError("run_n5_interaction_scope_residual_step_basis_incomplete")
        if not summary_steps.issubset(expected_steps) or not summary_steps.issubset(mean_steps):
            raise ValueError("run_n5_interaction_scope_foreign_residual_step")
        for summary in evidence.higher_order_residual_sampling.get(outcome, {}).values():
            if summary.seeds != replication_seeds:
                raise ValueError("run_n5_interaction_scope_residual_seed_basis_mismatch")
        if sampling_established and summary_steps != expected_steps:
            raise ValueError("run_n5_interaction_scope_residual_step_basis_incomplete")
        if summary_steps and summary_steps != expected_steps:
            raise ValueError("run_n5_interaction_scope_residual_step_basis_incomplete")
    if residual_outcomes != expected_residual_outcomes:
        raise ValueError("run_n5_interaction_scope_residual_basis_incomplete")

    expected_orders = (1, 2, 3) if len(atom_ids) == 3 else (1, 2) if len(atom_ids) >= 2 else (1,)
    checked_orders = evidence.checked_interaction_orders
    if (
        tuple(sorted(set(checked_orders))) != checked_orders
        or not set(checked_orders).issubset(expected_orders)
        or checked_orders != expected_orders
    ):
        raise ValueError("run_n5_interaction_scope_checked_orders_mismatch")


class RunCandidateSimulationN8ChildSourceBinding(BaseModel):
    """One selected parent atom bound to its persisted child N5 source input."""

    model_config = ConfigDict(extra="forbid")

    child_node_ref: str = Field(min_length=1)
    child_design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    n5_input_ref: ArtifactRef
    n5_result_ref: ArtifactRef
    profile_config_ref: str = Field(min_length=1)
    profile_selection_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_intervention_id: str = Field(min_length=1)
    source_atom_id: str = Field(pattern=r"^atom_[a-f0-9]{16}$")
    source_atom_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_problem_frame_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    parent_atom_id: str = Field(pattern=r"^atom_[a-f0-9]{16}$")
    parent_atom_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_child_source_refs(self) -> RunCandidateSimulationN8ChildSourceBinding:
        expected = (
            (
                self.n4_source_ref,
                {
                    "runtime.generation_source_handoff",
                    "runtime.quality.n4_candidate_scenario_source",
                },
            ),
            (self.context_job_ref, {"runtime.quality.cycle_substrate_context_job"}),
            (self.n5_input_ref, {"runtime.quality.candidate_simulation_n5_input"}),
            (self.n5_result_ref, {"polisyos.runtime.joint_simulation_result"}),
        )
        if any(
            ref.kind not in kinds or ref.media_type != "application/json" for ref, kinds in expected
        ):
            raise ValueError("run_n8_joint_child_source_ref_invalid")
        return self


class RunCandidateSimulationN5Observation(BaseModel):
    """One typed N5 observation projected from a persisted recursive run."""

    model_config = ConfigDict(extra="forbid")

    node_ref: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    design_problem_basis_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    cycle_index: int | None = Field(default=None, ge=0)
    candidate_id: str | None = Field(default=None, min_length=1)
    atom_ids: tuple[str, ...] = ()
    selected_outcomes: tuple[str, ...] = ()
    executed_steps: tuple[int, ...] = ()
    replication_seeds: tuple[int, ...] = ()
    status: Literal["joint_simulated", "simulation_pending_n5", "simulation_blocked"]
    simulation_ref: str | None = None
    simulation_result_ref: ArtifactRef | None = None
    n4_source_ref: ArtifactRef | None = None
    context_job_ref: ArtifactRef | None = None
    n5_input_ref: ArtifactRef | None = None
    profile_config_ref: str | None = Field(default=None, min_length=1)
    profile_selection_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    lineage_status: Literal["resolved", "not_established"] | None = None
    lineage_limitation_code: str | None = Field(default=None, min_length=1)
    currentness_status: Literal["not_established"] = "not_established"
    world_model_record_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    k_world_ref_before: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    k_world_ref_after: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    authority_blockers: tuple[str, ...] = ()
    n5_interaction_evidence: RunN5InteractionEvidence | None = None
    n8_numeric_interaction: Literal["none", "additive", "non_additive", "unsupported"] | None = None
    n8_numeric_interaction_basis: (
        Literal["finite_checked_model_point_estimate_only", "not_established"] | None
    ) = None
    n8_interaction_sampling_status: (
        Literal["estimated", "standard_error_not_estimated", "not_established"] | None
    ) = None
    n8_status: (
        Literal["value_ready", "value_conditional", "value_blocked", "value_pending_n8"] | None
    ) = None
    n8_authority_blockers: tuple[str, ...] = ()
    n8_joint_request_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    n8_joint_world_model_record_ref: str | None = Field(default=None, min_length=1)
    n8_joint_outcome_units: dict[str, str] = Field(default_factory=dict)
    n8_joint_parent_atom_ids: tuple[str, ...] = ()
    n8_joint_parent_atom_content_hashes: tuple[str, ...] = ()
    n8_parent_child_refs: tuple[str, ...] = ()
    n8_parent_child_source_bindings: tuple[RunCandidateSimulationN8ChildSourceBinding, ...] = ()
    n8_joint_scope_status: Literal["resolved", "not_established"] | None = None
    n8_joint_scope_limitation_code: str | None = Field(default=None, min_length=1)
    n8_joint_value_limitation_code: Literal["joint_interaction_rule_not_established"] | None = None
    n8_candidate_joint_selection_status: Literal["resolved", "not_established"] | None = None
    n8_candidate_joint_selection_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    n8_candidate_parent_atom_ids: tuple[
        Annotated[str, Field(pattern=r"^atom_[a-f0-9]{16}$")], ...
    ] = ()
    n8_candidate_parent_atom_content_hashes: tuple[str, ...] = ()
    n8_candidate_parent_intervention_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    n8_candidate_parent_child_refs: tuple[str, ...] = ()
    n8_candidate_joint_selection_limitation_code: (
        Literal["parent_joint_candidate_source_selection_not_established"] | None
    ) = None
    n8_candidate_member_basis: (
        Literal["hypothetical_all_unique_n4_source_members", "not_established"] | None
    ) = None
    n8_source_candidate_relationship: Literal["alternatives", "not_established"] | None = None
    n8_policy_composition_status: Literal["not_established"] | None = None
    n8_policy_composition_limitation_code: (
        Literal[
            "n4_source_candidates_are_alternatives_not_authored_compound_design",
            "legacy_selection_receipt_has_no_composition_basis",
            "parent_joint_candidate_source_selection_not_established",
        ]
        | None
    ) = None
    n8_child_to_parent_refinement_status: Literal["not_established"] | None = None
    n8_child_to_parent_refinement_limitation_code: (
        Literal[
            "child_to_parent_refinement_rule_not_established",
            "legacy_selection_receipt_has_no_refinement_basis",
            "parent_joint_candidate_source_selection_not_established",
        ]
        | None
    ) = None

    @field_validator("executed_steps", "replication_seeds", mode="before")
    @classmethod
    def _strict_interaction_scope_ints(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)) or any(
            isinstance(item, bool) or not isinstance(item, int) for item in value
        ):
            raise ValueError("run_n5_interaction_scope_integer_basis_invalid")
        return value

    @model_validator(mode="after")
    def _verify_n4_n5_lineage_projection(self) -> RunCandidateSimulationN5Observation:
        _validate_run_n5_interaction_scope(
            self.n5_interaction_evidence,
            atom_ids=self.atom_ids,
            selected_outcomes=self.selected_outcomes,
            executed_steps=self.executed_steps,
            replication_seeds=self.replication_seeds,
        )
        refs = (self.n4_source_ref, self.context_job_ref, self.n5_input_ref)
        if any(ref is not None for ref in refs):
            source, context, n5_input = refs
            if (
                source is None
                or source.kind
                not in {
                    "runtime.generation_source_handoff",
                    "runtime.quality.n4_candidate_scenario_source",
                }
                or source.media_type != "application/json"
                or context is None
                or context.kind != "runtime.quality.cycle_substrate_context_job"
                or context.media_type != "application/json"
                or n5_input is None
                or n5_input.kind != "runtime.quality.candidate_simulation_n5_input"
                or n5_input.media_type != "application/json"
                or self.profile_config_ref is None
                or self.profile_selection_ref is None
                or self.lineage_status is None
            ):
                raise ValueError("run_n5_lineage_projection_incomplete")
        if self.lineage_status == "resolved" and self.lineage_limitation_code is not None:
            raise ValueError("run_n5_lineage_resolved_with_limitation")
        if self.lineage_status == "not_established" and self.lineage_limitation_code is None:
            raise ValueError("run_n5_lineage_limitation_missing")
        n8_fields = (
            self.n8_numeric_interaction,
            self.n8_numeric_interaction_basis,
            self.n8_interaction_sampling_status,
        )
        if any(value is not None for value in n8_fields):
            if self.n5_interaction_evidence is None or any(value is None for value in n8_fields):
                raise ValueError("run_n5_n8_interaction_qualification_missing")
            if n8_fields != (
                self.n5_interaction_evidence.numeric_interaction,
                self.n5_interaction_evidence.numeric_interaction_basis,
                self.n5_interaction_evidence.interaction_sampling_status,
            ):
                raise ValueError("run_n5_n8_interaction_qualification_mismatch")
        if self.n8_status == "value_conditional":
            if self.n5_interaction_evidence is None or any(value is None for value in n8_fields):
                raise ValueError("run_n5_n8_conditional_interaction_missing")
            if self.n8_numeric_interaction == "unsupported" and (
                "interaction_numeric_classification_unsupported" not in self.n8_authority_blockers
            ):
                raise ValueError("run_n5_n8_unsupported_interaction_not_limited")
            if self.n8_interaction_sampling_status != "estimated" and not set(
                self.n8_authority_blockers
            ).intersection(
                {
                    "interaction_sampling_not_established",
                    "standard_error_not_estimated",
                    "legacy_interaction_not_established",
                }
            ):
                raise ValueError("run_n5_n8_unestimated_interaction_not_limited")
        joint_fields_present = any(
            (
                self.n8_joint_request_content_hash is not None,
                self.n8_joint_world_model_record_ref is not None,
                bool(self.n8_joint_outcome_units),
                bool(self.n8_joint_parent_atom_ids),
                bool(self.n8_joint_parent_atom_content_hashes),
                bool(self.n8_parent_child_refs),
                bool(self.n8_parent_child_source_bindings),
                self.n8_joint_scope_status is not None,
                self.n8_joint_scope_limitation_code is not None,
                self.n8_joint_value_limitation_code is not None,
            )
        )
        if self.n8_joint_scope_status is None:
            if joint_fields_present:
                raise ValueError("run_n8_joint_scope_status_missing")
        elif self.n8_status != "value_pending_n8":
            raise ValueError("run_n8_joint_scope_must_remain_pending")
        elif self.n8_joint_scope_status == "not_established":
            if (
                self.n8_joint_scope_limitation_code is None
                or self.n8_joint_value_limitation_code is not None
                or self.n8_joint_scope_limitation_code not in self.n8_authority_blockers
            ):
                raise ValueError("run_n8_joint_scope_limitation_missing")
        elif (
            self.n8_joint_scope_limitation_code is not None
            or self.n8_joint_value_limitation_code != "joint_interaction_rule_not_established"
            or "joint_interaction_rule_not_established" not in self.n8_authority_blockers
            or self.n8_joint_request_content_hash is None
            or self.n8_joint_world_model_record_ref is None
            or self.world_model_record_content_hash is None
            or not self.n8_joint_outcome_units
            or set(self.n8_joint_outcome_units) != set(self.selected_outcomes)
            or any(not unit.strip() for unit in self.n8_joint_outcome_units.values())
            or len(self.n8_joint_parent_atom_content_hashes) != len(self.atom_ids)
            or len(set(self.n8_joint_parent_atom_content_hashes))
            != len(self.n8_joint_parent_atom_content_hashes)
            or len(self.n8_joint_parent_atom_ids) != len(self.atom_ids)
            or len(set(self.n8_joint_parent_atom_ids)) != len(self.n8_joint_parent_atom_ids)
            or not self.n8_parent_child_refs
            or tuple(row.child_node_ref for row in self.n8_parent_child_source_bindings)
            != self.n8_parent_child_refs
            or {row.parent_atom_id for row in self.n8_parent_child_source_bindings}
            != set(self.n8_joint_parent_atom_ids)
            or {row.source_atom_id for row in self.n8_parent_child_source_bindings}
            != set(self.n8_joint_parent_atom_ids)
            or {row.source_intervention_id for row in self.n8_parent_child_source_bindings}
            != set(self.atom_ids)
            or {row.parent_atom_content_hash for row in self.n8_parent_child_source_bindings}
            != set(self.n8_joint_parent_atom_content_hashes)
            or {row.source_atom_content_hash for row in self.n8_parent_child_source_bindings}
            != set(self.n8_joint_parent_atom_content_hashes)
            or any(
                row.source_problem_frame_ref != self.design_problem_ref
                for row in self.n8_parent_child_source_bindings
            )
            or len(self.n8_parent_child_refs) != len(set(self.n8_parent_child_refs))
            or len(self.n8_parent_child_source_bindings) != len(self.atom_ids)
            or self.n5_interaction_evidence is None
            or self.n5_interaction_evidence.schema_version
            != "policyos.runtime.joint_simulation_horizon.v4"
            or any(value is None for value in n8_fields)
            or n8_fields
            != (
                self.n5_interaction_evidence.numeric_interaction,
                self.n5_interaction_evidence.numeric_interaction_basis,
                self.n5_interaction_evidence.interaction_sampling_status,
            )
        ):
            raise ValueError("run_n8_joint_scope_binding_incomplete")
        candidate_selection_fields_present = any(
            (
                self.n8_candidate_joint_selection_status is not None,
                self.n8_candidate_joint_selection_content_hash is not None,
                bool(self.n8_candidate_parent_atom_ids),
                bool(self.n8_candidate_parent_atom_content_hashes),
                bool(self.n8_candidate_parent_intervention_ids),
                bool(self.n8_candidate_parent_child_refs),
                self.n8_candidate_joint_selection_limitation_code is not None,
                self.n8_candidate_member_basis is not None,
                self.n8_source_candidate_relationship is not None,
                self.n8_policy_composition_status is not None,
                self.n8_policy_composition_limitation_code is not None,
                self.n8_child_to_parent_refinement_status is not None,
                self.n8_child_to_parent_refinement_limitation_code is not None,
            )
        )
        if self.n8_candidate_joint_selection_status is None:
            if candidate_selection_fields_present:
                raise ValueError("run_n8_candidate_joint_selection_status_missing")
        elif self.n8_candidate_joint_selection_status == "not_established":
            if (
                self.n8_candidate_joint_selection_limitation_code
                != "parent_joint_candidate_source_selection_not_established"
                or self.n8_candidate_joint_selection_content_hash is not None
                or self.n8_candidate_parent_atom_ids
                or self.n8_candidate_parent_atom_content_hashes
                or self.n8_candidate_parent_intervention_ids
                or self.n8_candidate_parent_child_refs
                or self.n8_candidate_member_basis != "not_established"
                or self.n8_source_candidate_relationship != "not_established"
                or self.n8_policy_composition_status != "not_established"
                or self.n8_policy_composition_limitation_code
                != "parent_joint_candidate_source_selection_not_established"
                or self.n8_child_to_parent_refinement_status != "not_established"
                or self.n8_child_to_parent_refinement_limitation_code
                != "parent_joint_candidate_source_selection_not_established"
            ):
                raise ValueError("run_n8_candidate_joint_selection_limitation_missing")
        elif (
            self.n8_candidate_joint_selection_content_hash is None
            or self.n8_candidate_joint_selection_limitation_code is not None
            or not self.n8_candidate_parent_atom_ids
            or len(self.n8_candidate_parent_atom_ids) != len(self.atom_ids)
            or len(set(self.n8_candidate_parent_atom_ids)) != len(self.n8_candidate_parent_atom_ids)
            or len(self.n8_candidate_parent_atom_content_hashes) != len(self.atom_ids)
            or len(set(self.n8_candidate_parent_atom_content_hashes))
            != len(self.n8_candidate_parent_atom_content_hashes)
            or self.n8_candidate_parent_intervention_ids != self.atom_ids
            or len(self.n8_candidate_parent_child_refs) != len(self.atom_ids)
            or len(set(self.n8_candidate_parent_child_refs))
            != len(self.n8_candidate_parent_child_refs)
            or self.n8_joint_scope_status != "not_established"
            or self.n8_status != "value_pending_n8"
            or self.n8_candidate_member_basis is None
            or self.n8_source_candidate_relationship is None
            or self.n8_policy_composition_status != "not_established"
            or self.n8_policy_composition_limitation_code is None
            or self.n8_child_to_parent_refinement_status != "not_established"
            or self.n8_child_to_parent_refinement_limitation_code is None
            or (
                self.n8_candidate_member_basis == "hypothetical_all_unique_n4_source_members"
                and (
                    self.n8_source_candidate_relationship != "alternatives"
                    or self.n8_policy_composition_limitation_code
                    != "n4_source_candidates_are_alternatives_not_authored_compound_design"
                    or self.n8_child_to_parent_refinement_limitation_code
                    != "child_to_parent_refinement_rule_not_established"
                )
            )
            or (
                self.n8_candidate_member_basis == "not_established"
                and (
                    self.n8_source_candidate_relationship != "not_established"
                    or self.n8_policy_composition_limitation_code
                    != "legacy_selection_receipt_has_no_composition_basis"
                    or self.n8_child_to_parent_refinement_limitation_code
                    != "legacy_selection_receipt_has_no_refinement_basis"
                )
            )
        ):
            raise ValueError("run_n8_candidate_joint_selection_binding_incomplete")
        return self


class RunRecursiveCycleBranchFailure(BaseModel):
    """Exact producer failure carried by a bounded partial recursive run."""

    model_config = ConfigDict(extra="forbid")

    failed_branch_ref: str = Field(min_length=1)
    origin_node_ref: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    exception_type: str = Field(min_length=1)
    error_code: str | None = Field(default=None, min_length=1)
    error_message: str


class RunRecursiveCycleCheckpoint(BaseModel):
    """Read-only checkpoint from an incomplete persisted recursive traversal."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "policyos.runtime.recursive_cycle_checkpoint.v1",
        "policyos.runtime.recursive_cycle_checkpoint.v2",
    ] = "policyos.runtime.recursive_cycle_checkpoint.v1"
    status: Literal["partial"] = "partial"
    publication_authority: Literal[False] = False
    budget_stop_node_ref: str | None = Field(default=None, min_length=1)
    pending_frontier: tuple[str, ...] = ()
    completed_design_refs: tuple[str, ...] = ()
    root_n9_status: Literal["not_run"] = "not_run"
    leaf_terminal_kinds: dict[str, str] = Field(default_factory=dict)
    failed_branches: tuple[RunRecursiveCycleBranchFailure, ...] = ()

    @model_validator(mode="after")
    def _verify_checkpoint_shape(self) -> RunRecursiveCycleCheckpoint:
        if self.schema_version.endswith(".v1"):
            if self.budget_stop_node_ref is None or self.failed_branches:
                raise ValueError("recursive_cycle_budget_checkpoint_shape_invalid")
        elif self.budget_stop_node_ref is not None or not self.failed_branches:
            raise ValueError("recursive_cycle_failure_checkpoint_shape_invalid")
        return self


class RunCandidateSimulationChildProfileBinding(BaseModel):
    """Historical child profile/context binding with currentness left unestablished."""

    model_config = ConfigDict(extra="forbid")

    node_ref: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    root_n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    context_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    profile_id: str = Field(min_length=1)
    profile_config_ref: str = Field(min_length=1)
    profile_selection_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    model_declaration_ref: ArtifactRef | None = None
    ncm_ref: ArtifactRef | None = None
    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    historical_binding_status: Literal["resolved", "not_established"]
    limitation_code: str | None = Field(default=None, min_length=1)
    currentness_status: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _verify_profile_binding_refs(self) -> RunCandidateSimulationChildProfileBinding:
        expected_node_ref = "design-problem://" + self.design_problem_ref.removeprefix("sha256:")
        if (
            self.node_ref != expected_node_ref
            or self.root_n4_source_ref.kind != "runtime.generation_source_handoff"
            or self.root_n4_source_ref.media_type != "application/json"
            or self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
            or (self.historical_binding_status == "resolved" and self.limitation_code is not None)
            or (
                self.historical_binding_status == "not_established" and self.limitation_code is None
            )
        ):
            raise ValueError("run_candidate_simulation_child_profile_binding_invalid")
        return self


class RunCandidateSimulationCurrentOccurrence(BaseModel):
    """One current candidate occurrence after append-only N6 continuation."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    cycle_index: int = Field(ge=0)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    front: Literal["decision", "research", "quarantine", "portfolio"]
    certified_by_n9: bool


class RunCandidateSimulationContinuationFronts(BaseModel):
    """Current N6 fronts recomputed after the N9 continuation outcome."""

    model_config = ConfigDict(extra="forbid")

    decision_candidate_ids: tuple[str, ...]
    research_candidate_ids: tuple[str, ...]
    quarantine_candidate_ids: tuple[str, ...]
    portfolio_candidate_ids: tuple[str, ...]


class RunCandidateSimulationAcquisitionContinuationProjection(BaseModel):
    """Typed candidate-only projection of the exact N9 continuation."""

    model_config = ConfigDict(extra="forbid")

    source_generation_run_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    continued_generation_run_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_cycle_index: int = Field(ge=0)
    continued_cycle_index: int = Field(ge=0)
    previous_n4_source_ref: ArtifactRef | None = None
    previous_n5_input_ref: ArtifactRef | None = None
    selected_n4_source_ref: ArtifactRef
    selected_n5_input_ref: ArtifactRef
    previous_profile_selection_ref: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    previous_profile_content_hash: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    selected_profile_selection_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    selected_profile_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    selected_target_world_slot: str = Field(min_length=1)
    previous_selected_target_baseline_hash: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    selected_target_baseline_hash: str | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    source_currentness_status: Literal["current", "stale", "not_established"]
    source_currentness_reason: str = Field(min_length=1)
    continuation_currentness_status: Literal["current", "stale", "not_established"]
    continuation_currentness_reason: str = Field(min_length=1)
    n9_status: Literal["promotion_pending_n9", "certified_current_valid", "not_promoted"]
    n9_reason: str = Field(min_length=1)
    n9_certified_candidate_ids: tuple[str, ...] = ()
    current_candidate_occurrences: tuple[RunCandidateSimulationCurrentOccurrence, ...]
    current_fronts: RunCandidateSimulationContinuationFronts
    currentness_status: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_observation_only"] = "candidate_observation_only"
    publication_authority: Literal[False] = False

    @model_validator(mode="after")
    def _bind_n9_current_front(self) -> RunCandidateSimulationAcquisitionContinuationProjection:
        current_ids = {row.candidate_id for row in self.current_candidate_occurrences}
        front_ids = (
            *self.current_fronts.decision_candidate_ids,
            *self.current_fronts.research_candidate_ids,
            *self.current_fronts.quarantine_candidate_ids,
            *self.current_fronts.portfolio_candidate_ids,
        )
        if (
            len(front_ids) != len(set(front_ids))
            or set(front_ids) != current_ids
            or len(current_ids) != len(self.current_candidate_occurrences)
            or not set(self.n9_certified_candidate_ids).issubset(current_ids)
            or any(
                row.candidate_id not in getattr(self.current_fronts, f"{row.front}_candidate_ids")
                or row.certified_by_n9 != (row.candidate_id in self.n9_certified_candidate_ids)
                for row in self.current_candidate_occurrences
            )
            or self.continued_cycle_index != self.source_cycle_index + 1
            or self.selected_n4_source_ref.kind != "runtime.quality.n4_candidate_scenario_source"
            or self.selected_n5_input_ref.kind != "runtime.quality.candidate_simulation_n5_input"
            or (self.previous_n4_source_ref is None) != (self.previous_n5_input_ref is None)
            or (self.previous_profile_selection_ref is None)
            != (self.previous_profile_content_hash is None)
            or (
                self.previous_n4_source_ref is not None
                and self.previous_n4_source_ref.kind
                != "runtime.quality.n4_candidate_scenario_source"
            )
            or (
                self.previous_n5_input_ref is not None
                and self.previous_n5_input_ref.kind
                != "runtime.quality.candidate_simulation_n5_input"
            )
            or (
                self.previous_selected_target_baseline_hash is not None
                and self.selected_target_baseline_hash is not None
                and self.previous_selected_target_baseline_hash
                == self.selected_target_baseline_hash
            )
            or (self.n9_status != "certified_current_valid" and self.n9_certified_candidate_ids)
            or (
                self.continuation_currentness_status != "current"
                and self.n9_status == "certified_current_valid"
            )
        ):
            raise ValueError("run_candidate_simulation_continuation_projection_invalid")
        return self


class RunCandidateSimulationAcquisitionHistoryEntry(BaseModel):
    """Persisted acquisition action facts projected as candidate history only."""

    model_config = ConfigDict(extra="forbid")

    route_receipt_ref: ArtifactRef
    reentry_receipt_ref: ArtifactRef | None = None
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_generation: int = Field(ge=1)
    terminal_outcome: Literal["reentry_completed", "quarantined_no_growth"]
    old_candidate_id: str | None = Field(default=None, min_length=1)
    new_candidate_id: str | None = Field(default=None, min_length=1)
    new_candidate_source_ref: ArtifactRef | None = None
    origin_source_ref: ArtifactRef | None = None
    expected_origin_source_ref: ArtifactRef | None = None
    schema_version: (
        Literal["policyos.runtime.run_candidate_simulation_acquisition_history.v2"] | None
    ) = None
    reentry_receipt_schema_version: (
        Literal[
            "policyos.runtime.acquisition_overlay_reentry.v1",
            "policyos.runtime.acquisition_overlay_reentry.v2",
            "policyos.runtime.acquisition_overlay_reentry.v3",
        ]
        | None
    ) = None
    continuation_join_status: (
        Literal["not_applicable", "legacy_occurrence_unbound", "v3_occurrence_joined"] | None
    ) = None
    origin_source_binding_status: (
        Literal["not_supplied", "observed_only", "verified_same_candidate_root"] | None
    ) = None
    continuation: RunCandidateSimulationAcquisitionContinuationProjection | None = None
    currentness_status: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_observation_only"] = "candidate_observation_only"
    publication_authority: Literal[False] = False

    @model_validator(mode="after")
    def _verify_history_refs(self) -> RunCandidateSimulationAcquisitionHistoryEntry:
        if (
            self.route_receipt_ref.kind != "runtime_quality.acquisition_route_loop_receipt"
            or self.route_receipt_ref.media_type != "application/json"
            or (
                self.reentry_receipt_ref is not None
                and (
                    self.reentry_receipt_ref.kind
                    != "runtime_quality.acquisition_overlay_reentry_receipt"
                    or self.reentry_receipt_ref.media_type != "application/json"
                )
            )
            or (
                self.new_candidate_source_ref is not None
                and (
                    self.new_candidate_source_ref.kind
                    != "runtime.quality.n4_candidate_scenario_source"
                    or self.new_candidate_source_ref.media_type != "application/json"
                )
            )
            or (
                self.origin_source_ref is not None
                and (
                    self.origin_source_ref.kind != "runtime.quality.n4_candidate_scenario_source"
                    or self.origin_source_ref.media_type != "application/json"
                )
            )
            or (
                self.expected_origin_source_ref is not None
                and (
                    self.expected_origin_source_ref.kind
                    != "runtime.quality.n4_candidate_scenario_source"
                    or self.expected_origin_source_ref.media_type != "application/json"
                )
            )
        ):
            raise ValueError("candidate_acquisition_history_ref_invalid")
        reentry_fields = (
            self.reentry_receipt_ref,
            self.old_candidate_id,
            self.new_candidate_id,
            self.new_candidate_source_ref,
        )
        same_candidate = (
            self.old_candidate_id is not None and self.old_candidate_id == self.new_candidate_id
        )
        metadata_values = (
            self.schema_version,
            self.reentry_receipt_schema_version,
            self.continuation_join_status,
            self.origin_source_binding_status,
        )
        metadata_present = any(value is not None for value in metadata_values)
        if metadata_present and (
            self.schema_version
            != "policyos.runtime.run_candidate_simulation_acquisition_history.v2"
            or self.continuation_join_status is None
            or self.origin_source_binding_status is None
        ):
            raise ValueError("candidate_acquisition_lineage_metadata_incomplete")
        # Older projections may omit all version/join metadata. They remain
        # readable as limited observations, but cannot carry a producer-verified
        # root claim.
        if not metadata_present and self.expected_origin_source_ref is not None:
            raise ValueError("candidate_acquisition_expected_origin_without_metadata")
        if self.terminal_outcome == "quarantined_no_growth":
            if (
                any(
                    value is not None
                    for value in (*reentry_fields, self.expected_origin_source_ref)
                )
                or self.continuation is not None
                or self.reentry_receipt_schema_version is not None
                or (
                    metadata_present
                    and (
                        self.continuation_join_status != "not_applicable"
                        or self.origin_source_binding_status
                        != (
                            "observed_only"
                            if self.origin_source_ref is not None
                            else "not_supplied"
                        )
                    )
                )
                or (
                    not metadata_present
                    and (
                        self.continuation_join_status is not None
                        or self.origin_source_binding_status is not None
                    )
                )
            ):
                raise ValueError("candidate_acquisition_quarantine_lineage_status_invalid")
            return self
        if metadata_present:
            expected_join = (
                "v3_occurrence_joined"
                if self.reentry_receipt_schema_version
                == "policyos.runtime.acquisition_overlay_reentry.v3"
                else "legacy_occurrence_unbound"
            )
            if (
                self.reentry_receipt_schema_version is None
                or self.continuation_join_status != expected_join
                or (
                    self.reentry_receipt_schema_version
                    == "policyos.runtime.acquisition_overlay_reentry.v3"
                )
                != (self.continuation is not None)
            ):
                raise ValueError("candidate_acquisition_receipt_join_status_invalid")
            expected_origin_status = (
                "verified_same_candidate_root"
                if same_candidate
                else ("observed_only" if self.origin_source_ref is not None else "not_supplied")
            )
            if self.origin_source_binding_status != expected_origin_status:
                raise ValueError("candidate_acquisition_origin_status_invalid")
        if self.terminal_outcome == "reentry_completed" and any(
            value is None for value in reentry_fields
        ):
            raise ValueError("candidate_acquisition_reentry_binding_incomplete")
        if self.terminal_outcome == "quarantined_no_growth" and self.continuation is not None:
            raise ValueError("candidate_acquisition_quarantine_has_continuation")
        if self.terminal_outcome == "quarantined_no_growth" and any(
            value is not None for value in (*reentry_fields, self.expected_origin_source_ref)
        ):
            raise ValueError("candidate_acquisition_quarantine_claims_reentry")
        if self.terminal_outcome == "reentry_completed":
            if (
                metadata_present
                and same_candidate
                and (
                    self.origin_source_ref is None
                    or self.expected_origin_source_ref is None
                    or artifact_ref_identity_key(self.origin_source_ref)
                    != artifact_ref_identity_key(self.expected_origin_source_ref)
                )
            ):
                raise ValueError("candidate_acquisition_same_candidate_origin_binding_invalid")
            if not same_candidate and self.expected_origin_source_ref is not None:
                raise ValueError("candidate_acquisition_expected_origin_without_same_candidate")
        continuation = self.continuation
        if continuation is not None:
            if self.new_candidate_source_ref is None or artifact_ref_identity_key(
                self.new_candidate_source_ref
            ) != artifact_ref_identity_key(continuation.selected_n4_source_ref):
                raise ValueError("candidate_acquisition_continuation_source_binding_invalid")
            if self.new_candidate_id is None or not any(
                occurrence.candidate_id == self.new_candidate_id
                and occurrence.cycle_index == continuation.continued_cycle_index
                for occurrence in continuation.current_candidate_occurrences
            ):
                raise ValueError("candidate_acquisition_continuation_candidate_missing")
        if (
            continuation is not None
            and self.old_candidate_id == self.new_candidate_id
            and (
                self.old_candidate_id is None
                or continuation.previous_n4_source_ref is None
                or continuation.previous_n5_input_ref is None
                or continuation.previous_profile_selection_ref is None
                or continuation.previous_profile_content_hash is None
                or continuation.previous_profile_selection_ref
                != continuation.selected_profile_selection_ref
                or continuation.previous_selected_target_baseline_hash is None
                or continuation.selected_target_baseline_hash is None
                or continuation.previous_selected_target_baseline_hash
                == continuation.selected_target_baseline_hash
                or artifact_ref_identity_key(continuation.previous_n4_source_ref)
                == artifact_ref_identity_key(continuation.selected_n4_source_ref)
                or artifact_ref_identity_key(continuation.previous_n5_input_ref)
                == artifact_ref_identity_key(continuation.selected_n5_input_ref)
            )
        ):
            raise ValueError("candidate_acquisition_same_candidate_continuation_binding_invalid")
        return self


class RunCandidateSimulationProjection(BaseModel):
    """Source-bound candidate observations exposed for display, never authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.runtime.run_candidate_simulation_projection.v1"] = (
        "policyos.runtime.run_candidate_simulation_projection.v1"
    )
    run_id: str = Field(min_length=1)
    artifact_status: Literal["resolved", "not_established"]
    authority_purpose: Literal["candidate_observation_only"] = "candidate_observation_only"
    publication_authority: Literal[False] = False
    source_ref: ArtifactRef | None = None
    source_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    n4_recursive_source_ref: ArtifactRef | None = None
    n4_recursive_source_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    n4_recursive_source_status: Literal["resolved", "not_established"] | None = None
    n4_recursive_source_limitation_code: str | None = Field(default=None, min_length=1)
    n4_recursive_source_result_status: (
        Literal[
            "generated",
            "generation_unavailable",
            "preflight_rejected",
        ]
        | None
    ) = None
    n4_recursive_source_currentness_status: Literal["not_established"] = "not_established"
    n4_recursive_source_context_job_ref: ArtifactRef | None = None
    n4_recursive_source_profile_config_ref: str | None = Field(default=None, min_length=1)
    n4_recursive_source_profile_selection_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    n4_child_profile_status: (
        Literal[
            "not_attempted",
            "resolved",
            "not_established",
        ]
        | None
    ) = None
    n4_child_profile_limitation_code: str | None = Field(default=None, min_length=1)
    n4_child_profile_bindings: tuple[RunCandidateSimulationChildProfileBinding, ...] = ()
    limitation_code: (
        Literal[
            "compiled_cycle_artifact_ambiguous",
            "compiled_cycle_artifact_ref_invalid",
            "compiled_cycle_artifact_integrity_not_established",
            "compiled_cycle_artifact_content_invalid",
            "n5_observation_not_emitted",
            "n5_result_reference_not_established",
            "n5_interaction_scope_not_established",
        ]
        | None
    ) = None
    n5_observations: tuple[RunCandidateSimulationN5Observation, ...] = ()
    recursive_cycle_checkpoint: RunRecursiveCycleCheckpoint | None = None
    acquisition_history: tuple[RunCandidateSimulationAcquisitionHistoryEntry, ...] = ()
    acquisition_history_limitation_code: (
        Literal[
            "acquisition_n4_source_not_established",
            "acquisition_action_history_not_observed",
            "acquisition_action_history_incomplete",
            "acquisition_action_history_integrity_not_established",
            "acquisition_reentry_source_not_established",
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def _verify_candidate_projection_source(self) -> RunCandidateSimulationProjection:
        if self.artifact_status == "resolved":
            if (
                self.source_ref is None
                or self.source_ref.kind != "runtime.compiled_recursive_generation_cycle"
                or self.source_content_hash is None
                or self.limitation_code
                in {
                    "compiled_cycle_artifact_ambiguous",
                    "compiled_cycle_artifact_ref_invalid",
                    "compiled_cycle_artifact_integrity_not_established",
                    "compiled_cycle_artifact_content_invalid",
                }
            ):
                raise ValueError("candidate_projection_resolved_source_missing")
            if self.n4_recursive_source_status == "resolved" and (
                self.n4_recursive_source_ref is None
                or self.n4_recursive_source_content_hash is None
                or self.n4_recursive_source_result_status is None
                or self.n4_recursive_source_context_job_ref is None
                or self.n4_recursive_source_profile_config_ref is None
                or self.n4_recursive_source_profile_selection_ref is None
                or self.n4_recursive_source_limitation_code is not None
            ):
                raise ValueError("candidate_projection_n4_source_resolved_binding_missing")
            if self.n4_recursive_source_status == "not_established" and (
                self.n4_recursive_source_content_hash is not None
                or self.n4_recursive_source_limitation_code is None
            ):
                raise ValueError("candidate_projection_n4_source_refusal_not_fail_closed")
            if self.n4_child_profile_status == "resolved" and (
                self.n4_child_profile_limitation_code is not None
                or not self.n4_child_profile_bindings
                or any(
                    row.historical_binding_status != "resolved"
                    for row in self.n4_child_profile_bindings
                )
            ):
                raise ValueError("candidate_projection_child_profile_resolved_with_limitation")
            if self.n4_child_profile_status == "not_established" and (
                self.n4_child_profile_limitation_code is None
            ):
                raise ValueError("candidate_projection_child_profile_limitation_missing")
            if self.n4_child_profile_status in {None, "not_attempted"} and (
                self.n4_child_profile_limitation_code is not None
            ):
                raise ValueError("candidate_projection_unexpected_child_profile_limitation")
            if (
                self.limitation_code
                in {
                    "n5_result_reference_not_established",
                    "n5_interaction_scope_not_established",
                }
                and self.n5_observations
            ):
                raise ValueError("candidate_projection_unverified_n5_observation_present")
            if self.limitation_code == "n5_observation_not_emitted" and self.n5_observations:
                raise ValueError("candidate_projection_empty_n5_observation_mismatch")
            if self.acquisition_history and self.acquisition_history_limitation_code is not None:
                raise ValueError("candidate_projection_acquisition_history_mixed_refusal")
            return self
        if (
            self.source_content_hash is not None
            or self.n4_recursive_source_content_hash is not None
            or self.n4_recursive_source_status is not None
            or self.n4_child_profile_status is not None
            or self.n4_child_profile_bindings
            or self.n5_observations
            or self.recursive_cycle_checkpoint is not None
            or self.acquisition_history
            or self.acquisition_history_limitation_code is not None
            or self.limitation_code
            not in {
                "compiled_cycle_artifact_ambiguous",
                "compiled_cycle_artifact_ref_invalid",
                "compiled_cycle_artifact_integrity_not_established",
                "compiled_cycle_artifact_content_invalid",
            }
        ):
            raise ValueError("candidate_projection_refusal_not_fail_closed")
        return self


class RunGenericCycleSimulationChildProfileBinding(BaseModel):
    """Historical profile row joined to one persisted N4-derived child."""

    model_config = ConfigDict(extra="forbid")

    node_ref: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_ref: ArtifactRef
    source_result_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_atom_refs: tuple[str, ...] = Field(min_length=1)
    semantic_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    context_job_ref: ArtifactRef
    profile_ref: ArtifactRef
    profile_id: str = Field(min_length=1)
    profile_selection_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    historical_binding_status: Literal["resolved", "not_established"]
    limitation_code: str | None = Field(default=None, min_length=1)
    currentness_status: Literal["not_established"] = "not_established"

    @model_validator(mode="after")
    def _verify_generic_binding(self) -> RunGenericCycleSimulationChildProfileBinding:
        expected_node_ref = "design-problem://" + self.design_problem_ref.removeprefix("sha256:")
        if (
            self.node_ref != expected_node_ref
            or self.source_ref.kind != "runtime.generation_source_handoff"
            or self.source_ref.media_type != "application/json"
            or self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
            or self.profile_ref.kind != "runtime.quality.generic_cycle_simulation_profile"
            or self.profile_ref.media_type != "application/json"
            or not self.source_atom_refs
            or len(self.source_atom_refs) != len(set(self.source_atom_refs))
            or tuple(self.source_atom_refs) != tuple(sorted(self.source_atom_refs))
            or (self.historical_binding_status == "resolved" and self.limitation_code is not None)
            or (
                self.historical_binding_status == "not_established" and self.limitation_code is None
            )
        ):
            raise ValueError("run_generic_child_profile_binding_invalid")
        return self


class RunGenericCycleSimulationN5Horizon(BaseModel):
    """Publicly readable valid-time horizon from one verified N5 result."""

    model_config = ConfigDict(extra="forbid")
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    step: int = Field(ge=1)
    valid_time_role: str = Field(min_length=1, strict=True)
    transaction_time_role: str = Field(min_length=1, strict=True)
    scenario_branch_policy: str = Field(min_length=1, strict=True)

    @field_validator("start", "end", "step", mode="before")
    @classmethod
    def _strict_horizon_ints(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("run_generic_n5_result_horizon_integer_invalid")
        return value

    @model_validator(mode="after")
    def _verify_horizon_grid(self) -> RunGenericCycleSimulationN5Horizon:
        if self.end < self.start or (self.end - self.start) % self.step:
            raise ValueError("run_generic_n5_result_horizon_grid_invalid")
        return self


class RunGenericCycleSimulationN5TrajectoryPoint(BaseModel):
    """One finite outcome/effect row surfaced from a verified N5 trajectory."""

    model_config = ConfigDict(extra="forbid")
    step: int = Field(ge=0)
    outcomes: dict[str, float]
    effects: dict[str, float]

    @field_validator("step", mode="before")
    @classmethod
    def _strict_step(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("run_generic_n5_result_step_not_integer")
        return value

    @field_validator("outcomes", "effects", mode="before")
    @classmethod
    def _finite_numeric_map(cls, value: object) -> object:
        if not isinstance(value, Mapping) or not value:
            raise ValueError("run_generic_n5_result_numeric_map_missing")
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError("run_generic_n5_result_numeric_map_key_invalid")
            if isinstance(item, bool) or not isinstance(item, int | float):
                raise ValueError("run_generic_n5_result_numeric_map_value_not_real")
            if not math.isfinite(float(item)):
                raise ValueError("run_generic_n5_result_numeric_map_value_non_finite")
        return value


class RunGenericCycleSimulationN5Trajectory(BaseModel):
    """One verified individual, pairwise, or joint numerical trajectory."""

    model_config = ConfigDict(extra="forbid")
    run_level: Literal["individual", "pairwise", "joint"]
    atom_ids: tuple[str, ...] = Field(min_length=1)
    points: tuple[RunGenericCycleSimulationN5TrajectoryPoint, ...] = Field(min_length=1)

    @field_validator("atom_ids", mode="before")
    @classmethod
    def _strict_trajectory_atom_ids(cls, value: object) -> object:
        if not isinstance(value, list | tuple) or any(
            not isinstance(atom_id, str) or not atom_id for atom_id in value
        ):
            raise ValueError("run_generic_n5_result_trajectory_atom_ids_invalid")
        return value

    @model_validator(mode="after")
    def _verify_trajectory_scope(self) -> RunGenericCycleSimulationN5Trajectory:
        steps = tuple(point.step for point in self.points)
        if (
            not all(self.atom_ids)
            or len(self.atom_ids) != len(set(self.atom_ids))
            or len(steps) != len(set(steps))
            or steps != tuple(sorted(steps))
            or (self.run_level == "individual" and len(self.atom_ids) != 1)
            or (self.run_level == "pairwise" and len(self.atom_ids) != 2)
        ):
            raise ValueError("run_generic_n5_result_trajectory_scope_invalid")
        return self


class RunGenericCycleSimulationN5ResultBody(BaseModel):
    """Typed candidate-only body read from the selected, verified N5 CAS view."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["policyos.runtime.run_generic_cycle_simulation_n5_result_body.v1"] = (
        "policyos.runtime.run_generic_cycle_simulation_n5_result_body.v1"
    )
    artifact_ref: ArtifactRef
    artifact_schema_name: Literal["policyos.runtime.n5.joint_simulation_result"]
    artifact_schema_version: Literal["1.0.0", "2.0.0", "3.0.0", "4.0.0"]
    result_schema_version: Literal[
        "policyos.runtime.joint_simulation_horizon.v1",
        "policyos.runtime.joint_simulation_horizon.v2",
        "policyos.runtime.joint_simulation_horizon.v3",
        "policyos.runtime.joint_simulation_horizon.v4",
    ]
    selected_manifest_profile_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$", strict=True)
    world_model_record_ref: str = Field(min_length=1, strict=True)
    world_model_record_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    atom_ids: tuple[str, ...] = Field(min_length=1)
    selected_outcomes: tuple[str, ...] = Field(min_length=1)
    horizon: RunGenericCycleSimulationN5Horizon
    trajectories: tuple[RunGenericCycleSimulationN5Trajectory, ...] = Field(min_length=1)
    uncertainty_kind: Literal["K_sim"] = "K_sim"
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    candidate_status: Literal["candidate_unverified"] = "candidate_unverified"
    currentness_status: Literal["not_established"] = "not_established"
    publication_authority: Literal[False] = False

    @field_validator("atom_ids", "selected_outcomes", mode="before")
    @classmethod
    def _strict_result_basis_strings(cls, value: object) -> object:
        if not isinstance(value, list | tuple) or any(
            not isinstance(item, str) or not item for item in value
        ):
            raise ValueError("run_generic_n5_result_body_string_basis_invalid")
        return value

    @model_validator(mode="after")
    def _verify_result_body_binding(self) -> RunGenericCycleSimulationN5ResultBody:
        result_schema_by_artifact_version = {
            "1.0.0": "policyos.runtime.joint_simulation_horizon.v1",
            "2.0.0": "policyos.runtime.joint_simulation_horizon.v2",
            "3.0.0": "policyos.runtime.joint_simulation_horizon.v3",
            "4.0.0": "policyos.runtime.joint_simulation_horizon.v4",
        }
        if (
            self.artifact_ref.kind != "polisyos.runtime.joint_simulation_result"
            or self.artifact_ref.media_type != "application/json"
            or self.artifact_ref.manifest_profile_sha256 != self.selected_manifest_profile_sha256
            or result_schema_by_artifact_version[self.artifact_schema_version]
            != self.result_schema_version
            or not all(self.atom_ids)
            or len(self.atom_ids) != len(set(self.atom_ids))
            or not all(self.selected_outcomes)
            or len(self.selected_outcomes) != len(set(self.selected_outcomes))
        ):
            raise ValueError("run_generic_n5_result_body_manifest_binding_invalid")
        horizon_steps = set(range(self.horizon.start, self.horizon.end + 1, self.horizon.step))
        trajectory_scopes: set[tuple[str, frozenset[str]]] = set()
        for trajectory in self.trajectories:
            atom_scope = frozenset(trajectory.atom_ids)
            scope = (trajectory.run_level, atom_scope)
            if (
                atom_scope - set(self.atom_ids)
                or scope in trajectory_scopes
                or (trajectory.run_level == "joint" and trajectory.atom_ids != self.atom_ids)
            ):
                raise ValueError("run_generic_n5_result_body_foreign_or_duplicate_scope")
            trajectory_scopes.add(scope)
            for point in trajectory.points:
                if (
                    point.step not in horizon_steps
                    or not set(self.selected_outcomes).issubset(point.outcomes)
                    or not set(self.selected_outcomes).issubset(point.effects)
                ):
                    raise ValueError("run_generic_n5_result_body_selected_basis_incomplete")
        return self


class RunGenericCycleSimulationN5Observation(BaseModel):
    """One historical, candidate-only N5 observation and its persisted lineage."""

    model_config = ConfigDict(extra="forbid")

    node_ref: str = Field(min_length=1)
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cycle_index: int = Field(ge=0)
    candidate_id: str = Field(min_length=1)
    status: Literal["joint_simulated", "simulation_pending_n5", "simulation_blocked"]
    simulation_result_ref: ArtifactRef | None = None
    simulation_result_body: RunGenericCycleSimulationN5ResultBody | None = None
    simulation_result_body_status: (
        Literal["not_applicable", "resolved", "not_established"] | None
    ) = None
    simulation_result_body_limitation_code: (
        Literal[
            "generic_n5_result_body_request_binding_not_established",
            "generic_n5_result_body_selected_manifest_view_not_established",
            "generic_n5_result_body_execution_not_successful",
            "generic_n5_result_body_content_refused",
        ]
        | None
    ) = None
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    profile_ref: ArtifactRef
    child_profile_family_ref: ArtifactRef | None = None
    child_profile_set_ref: ArtifactRef | None = None
    n5_input_ref: ArtifactRef
    n5_execution_ref: ArtifactRef | None = None
    n5_request_binding_status: Literal["resolved", "not_established"] = "not_established"
    n5_request_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    profile_selection_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    atom_ids: tuple[str, ...] = ()
    selected_outcomes: tuple[str, ...] = ()
    executed_steps: tuple[int, ...] = ()
    replication_seeds: tuple[int, ...] = ()
    world_model_record_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    authority_blockers: tuple[str, ...] = ()
    n8_status: Literal["value_ready", "value_conditional", "value_blocked", "value_pending_n8"]
    n8_lineage_status: Literal["resolved", "not_established"]
    n8_value_ref: str | None = None
    n8_authority_blockers: tuple[str, ...] = ()
    n8_limitation_code: str | None = Field(default=None, min_length=1)
    n5_interaction_evidence: RunN5InteractionEvidence | None = None
    n8_numeric_interaction: Literal["none", "additive", "non_additive", "unsupported"] | None = None
    n8_numeric_interaction_basis: (
        Literal["finite_checked_model_point_estimate_only", "not_established"] | None
    ) = None
    n8_interaction_sampling_status: (
        Literal["estimated", "standard_error_not_estimated", "not_established"] | None
    ) = None
    currentness_status: Literal["not_established"] = "not_established"
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    publication_authority: Literal[False] = False

    @field_validator("executed_steps", "replication_seeds", mode="before")
    @classmethod
    def _strict_interaction_scope_ints(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)) or any(
            isinstance(item, bool) or not isinstance(item, int) for item in value
        ):
            raise ValueError("run_generic_n5_interaction_scope_integer_basis_invalid")
        return value

    @model_validator(mode="after")
    def _verify_generic_n5_lineage(self) -> RunGenericCycleSimulationN5Observation:
        _validate_run_n5_interaction_scope(
            self.n5_interaction_evidence,
            atom_ids=self.atom_ids,
            selected_outcomes=self.selected_outcomes,
            executed_steps=self.executed_steps,
            replication_seeds=self.replication_seeds,
        )
        typed_refs = (
            (self.n4_source_ref, "runtime.generation_source_handoff"),
            (self.context_job_ref, "runtime.quality.cycle_substrate_context_job"),
            (self.profile_ref, "runtime.quality.generic_cycle_simulation_profile"),
            (self.n5_input_ref, "runtime.quality.generic_cycle_simulation_n5_input"),
        )
        if any(
            ref.kind != kind or ref.media_type != "application/json" for ref, kind in typed_refs
        ):
            raise ValueError("run_generic_n5_ref_kind_invalid")
        for ref, kind in (
            (
                self.child_profile_family_ref,
                "runtime.quality.generic_cycle_simulation_child_profile_family",
            ),
            (self.child_profile_set_ref, "runtime.quality.recursive_n4_child_profile_set"),
            (self.n5_execution_ref, "runtime.quality.generic_cycle_simulation_n5_execution"),
            (self.simulation_result_ref, "polisyos.runtime.joint_simulation_result"),
        ):
            if ref is not None and (ref.kind != kind or ref.media_type != "application/json"):
                raise ValueError("run_generic_n5_optional_ref_kind_invalid")
        if (self.child_profile_family_ref is None) != (self.child_profile_set_ref is None):
            raise ValueError("run_generic_n5_child_family_set_pair_invalid")
        if self.simulation_result_ref is None:
            if (
                self.simulation_result_body is not None
                or self.simulation_result_body_status not in (None, "not_applicable")
                or self.simulation_result_body_limitation_code is not None
            ):
                raise ValueError("run_generic_n5_result_body_without_result_ref")
        elif self.simulation_result_body is None:
            if (
                self.simulation_result_body_status != "not_established"
                or self.simulation_result_body_limitation_code is None
            ):
                raise ValueError("run_generic_n5_result_body_unavailable_reason_missing")
        else:
            body = self.simulation_result_body
            if (
                self.status != "joint_simulated"
                or self.simulation_result_body_status != "resolved"
                or body.artifact_ref != self.simulation_result_ref
                or body.world_model_record_content_hash != self.world_model_record_content_hash
                or body.atom_ids != self.atom_ids
                or body.selected_outcomes != self.selected_outcomes
                or self.simulation_result_body_limitation_code is not None
            ):
                raise ValueError("run_generic_n5_result_body_parent_binding_invalid")
        if self.status == "joint_simulated" and (
            self.simulation_result_ref is None or self.n5_execution_ref is None
        ):
            raise ValueError("run_generic_n5_success_result_missing")
        if (self.n5_request_binding_status == "resolved") != (
            self.n5_request_content_hash is not None
        ):
            raise ValueError("run_generic_n5_request_binding_shape_invalid")
        if self.n8_lineage_status == "resolved" and (self.n5_request_binding_status != "resolved"):
            raise ValueError("run_generic_n8_request_binding_not_established")
        if self.n8_status == "value_conditional":
            if any(
                value is None
                for value in (
                    self.n5_interaction_evidence,
                    self.n8_numeric_interaction,
                    self.n8_numeric_interaction_basis,
                    self.n8_interaction_sampling_status,
                )
            ):
                raise ValueError("run_generic_n8_interaction_qualification_missing")
            if (
                self.n8_numeric_interaction != self.n5_interaction_evidence.numeric_interaction
                or (
                    self.n8_numeric_interaction_basis
                    != self.n5_interaction_evidence.numeric_interaction_basis
                )
                or (
                    self.n8_interaction_sampling_status
                    != self.n5_interaction_evidence.interaction_sampling_status
                )
            ):
                raise ValueError("run_generic_n8_interaction_qualification_mismatch")
            if self.n8_numeric_interaction == "unsupported" and (
                "interaction_numeric_classification_unsupported" not in self.n8_authority_blockers
            ):
                raise ValueError("run_generic_n8_unsupported_interaction_not_limited")
            if self.n8_interaction_sampling_status != "estimated" and not set(
                self.n8_authority_blockers
            ).intersection(
                {
                    "interaction_sampling_not_established",
                    "standard_error_not_estimated",
                    "legacy_interaction_not_established",
                }
            ):
                raise ValueError("run_generic_n8_unestimated_interaction_not_limited")
            if self.n8_lineage_status == "resolved" and (
                self.simulation_result_ref is None
                or self.n8_value_ref != str(self.simulation_result_ref.artifact_id)
                or self.n8_limitation_code is not None
            ):
                raise ValueError("run_generic_n8_conditional_binding_invalid")
            if self.n8_lineage_status == "not_established" and (
                self.n8_limitation_code is None or self.n8_value_ref is not None
            ):
                raise ValueError("run_generic_n8_conditional_limitation_missing")
        elif self.n8_lineage_status == "resolved":
            raise ValueError("run_generic_n8_nonconditional_resolved_invalid")
        if (self.n8_lineage_status == "not_established") != (self.n8_limitation_code is not None):
            raise ValueError("run_generic_n8_limitation_shape_invalid")
        return self


class RunGenericCycleSimulationProjection(BaseModel):
    """Persisted generic simulation lineage exposed as candidate-only history."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "policyos.runtime.run_generic_cycle_simulation_projection.v1",
        "policyos.runtime.run_generic_cycle_simulation_projection.v2",
    ] = "policyos.runtime.run_generic_cycle_simulation_projection.v1"
    run_id: str = Field(min_length=1)
    artifact_status: Literal["resolved", "not_established"]
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    publication_authority: Literal[False] = False
    currentness_status: Literal["not_established"] = "not_established"
    source_ref: ArtifactRef | None = None
    source_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    n4_source_ref: ArtifactRef | None = None
    n4_source_status: Literal["resolved", "not_established"] | None = None
    n4_source_limitation_code: str | None = Field(default=None, min_length=1)
    parent_context_job_ref: ArtifactRef | None = None
    parent_profile_ref: ArtifactRef | None = None
    parent_profile_id: str | None = Field(default=None, min_length=1)
    child_profile_family_ref: ArtifactRef | None = None
    child_profile_set_ref: ArtifactRef | None = None
    credal_source_attempt_ref: ArtifactRef | None = None
    credal_source_status: Literal["not_established"] | None = None
    credal_source_limitation_code: (
        Literal[
            "candidate_source_authority_not_established",
            "candidate_source_attempt_replay_not_established",
        ]
        | None
    ) = None
    child_profile_status: Literal["not_attempted", "resolved", "not_established"]
    child_profile_limitation_code: str | None = Field(default=None, min_length=1)
    child_profile_bindings: tuple[RunGenericCycleSimulationChildProfileBinding, ...] = ()
    n5_observations: tuple[RunGenericCycleSimulationN5Observation, ...] = ()
    n5_limitation_code: str | None = Field(default=None, min_length=1)
    recursive_cycle_checkpoint: RunRecursiveCycleCheckpoint | None = None
    limitation_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _verify_generic_projection(self) -> RunGenericCycleSimulationProjection:
        has_credal_attempt_projection = (
            self.credal_source_attempt_ref is not None
            or self.credal_source_status is not None
            or self.credal_source_limitation_code is not None
        )
        if has_credal_attempt_projection:
            if (
                self.schema_version != "policyos.runtime.run_generic_cycle_simulation_projection.v2"
                or self.credal_source_status != "not_established"
                or self.credal_source_limitation_code is None
                or self.child_profile_status != "not_established"
                or self.n5_observations
                or (
                    self.credal_source_attempt_ref is not None
                    and (
                        self.credal_source_attempt_ref.kind
                        != "runtime.quality.candidate_credal_source_attempt"
                        or self.credal_source_attempt_ref.media_type != "application/json"
                    )
                )
            ):
                raise ValueError("run_generic_projection_credal_source_attempt_invalid")
        elif self.schema_version != "policyos.runtime.run_generic_cycle_simulation_projection.v1":
            raise ValueError("run_generic_projection_schema_extension_without_attempt")
        if self.artifact_status == "resolved":
            if self.source_ref is None or self.source_content_hash is None:
                raise ValueError("run_generic_projection_compiled_source_missing")
            if self.n4_source_status == "resolved" and (
                self.n4_source_ref is None
                or self.n4_source_limitation_code is not None
                or self.parent_context_job_ref is None
                or self.parent_profile_ref is None
                or self.parent_profile_id is None
            ):
                raise ValueError("run_generic_projection_n4_binding_missing")
            if self.child_profile_status == "resolved" and (
                self.child_profile_family_ref is None
                or self.child_profile_set_ref is None
                or self.child_profile_limitation_code is not None
                or not self.child_profile_bindings
                or any(
                    row.historical_binding_status != "resolved"
                    for row in self.child_profile_bindings
                )
            ):
                raise ValueError("run_generic_projection_child_binding_missing")
            if self.child_profile_status == "not_established" and (
                self.child_profile_limitation_code is None
            ):
                raise ValueError("run_generic_projection_child_limitation_missing")
            return self
        if (
            self.source_content_hash is not None
            or self.n4_source_status is not None
            or self.child_profile_bindings
            or self.n5_observations
            or self.limitation_code is None
        ):
            raise ValueError("run_generic_projection_refusal_shape_invalid")
        return self


class RunDetails(RunRecordV1):
    """Run details public type."""

    manifest_ref: ArtifactRef | None = None
    trace_ref: ArtifactRef | None = None
    capability_manifest_ref: ArtifactRef | None = None
    root_artifacts: list[ArtifactRef] = Field(default_factory=list)
    root_input_artifacts: list[ArtifactRef] = Field(default_factory=list)
    has_workflow_report: bool = False
    workflow_report_ref: ArtifactRef | None = None
    warnings: list[str] = Field(default_factory=list)
    decision_validity_status: DecisionValidityStatus | None = None
    decision_validity_checked_at: datetime | None = None
    decision_review_required: bool = False
    decision_superseded_by_ref: ArtifactRef | None = None
    operator_diagnostic: RunOperatorDiagnostic | None = None
    policy_design_case_projection: PolicyDesignCaseProjection | None = None
    candidate_simulation: RunCandidateSimulationProjection | None = None
    generic_cycle_simulation: RunGenericCycleSimulationProjection | None = None


class RunTimelineEvent(BaseModel):
    """One timestamped event emitted into the runtime timeline for a run."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    timestamp: datetime
    phase: str
    event: str
    span_id: str | None = None
    parent_span_id: str | None = None
    input_artifact_ids: list[str] = Field(default_factory=list)
    output_artifact_ids: list[str] = Field(default_factory=list)
    input_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    output_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    metrics: dict[str, int | float] = Field(default_factory=dict)
    warning_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)


class RunTimelineSummary(BaseModel):
    """Aggregate counters and latency totals derived from a run's timeline events."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    total_events: int = Field(default=0, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    node_status_counts: dict[str, int] = Field(default_factory=dict)
    phase_counts: dict[str, int] = Field(default_factory=dict)
    cache_hits: int = Field(default=0, ge=0)
    cache_stores: int = Field(default=0, ge=0)
    cache_bypasses: int = Field(default=0, ge=0)


class RunTimelineView(BaseModel):
    """Timeline payload returned by runtime endpoints, including summary and ordered events."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    summary: RunTimelineSummary
    events: list[RunTimelineEvent] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RunNodeRecord(BaseModel):
    """Per-node execution summary used by node listings and debug surfaces."""

    model_config = ConfigDict(extra="forbid")

    alias: str
    node_id: str | None = None
    status: NodeStatus = "unknown"
    duration_ms: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] = Field(default_factory=dict)
    skip_reason: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    input_artifact_ids: list[str] = Field(default_factory=list)
    output_artifact_ids: list[str] = Field(default_factory=list)
    input_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    output_artifact_refs: list[ArtifactRef] = Field(default_factory=list)


class NodeDebugView(BaseModel):
    """Detailed node-debug payload with timeline slices, cache activity, and notes."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    alias: str
    record: RunNodeRecord
    timeline_events: list[RunTimelineEvent] = Field(default_factory=list)
    cache_hits: int = Field(default=0, ge=0)
    cache_stores: int = Field(default=0, ge=0)
    cache_bypasses: int = Field(default=0, ge=0)
    notes: list[str] = Field(default_factory=list)


class SimulationResultCandidateView(BaseModel):
    """Candidate-only simulation result bound to one persisted run node.

    This projection is intentionally not an authority envelope.  It exposes a
    content-addressed ``SimulationResult`` for debugging a later node failure
    only after the run state, workflow node, expected artifact manifest, and
    CAS bytes have been reconciled.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    node_alias: str
    node_id: str | None = None
    artifact_ref: ArtifactRef
    simulation_result: SimulationResult
    projection_class: Literal["candidate_reference_only"] = "candidate_reference_only"
    authority_status: Literal["non_authority"] = "non_authority"
    integrity_status: Literal["verified"] = "verified"
    notes: list[str] = Field(default_factory=list)


class GovernanceDebugView(BaseModel):
    """Detailed governance payload exposing verdicts, report refs, and contract warnings."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    verdict: str | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)
    issue_summary: dict[str, int] | None = None
    notes: list[str] = Field(default_factory=list)
    report_ref: ArtifactRef | None = None
    report_kind: str | None = None
    report_schema_version: str | None = None
    links: dict[str, ArtifactRef | None] | None = None
    legal_executed: bool | None = None
    transport_summary: dict[str, Any] | None = None
    validation_trace: dict[str, Any] | None = None
    contract_warnings: list[str] = Field(default_factory=list)
    decision_validity: dict[str, Any] | None = None
    normative_summary: dict[str, Any] | None = None
    normative_arbitration_result_ref: ArtifactRef | None = None
    fallback_from_decision_packet: bool = False


class RunErrorView(BaseModel):
    """Normalized error record assembled from manifests, traces, reports, or runtime faults."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["manifest", "workflow_report", "trace", "runtime"]
    code: str
    message: str
    node_alias: str | None = None
    timestamp: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AgentPipelineCostEvent(BaseModel):
    """One persisted provider settlement or authenticated reuse event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    origin_event_id: str | None = Field(default=None, min_length=1)
    cost_origin: AgentPipelineCostOrigin
    amount: Decimal | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    settlement_status: AgentPipelineSettlementStatus
    durability: Literal["ledger", "memory", "none"] | None = None
    receipts: tuple[str, ...] = ()
    payload_digest: str | None = Field(default=None, min_length=1)
    model: str | None = None
    provider: str | None = None
    control_job_attempt: int | None = Field(default=None, ge=1, strict=True)
    pre_admission_attempt_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")

    @model_validator(mode="before")
    @classmethod
    def _derive_compatibility_cost(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        normalized = dict(value)
        if "amount" not in normalized:
            normalized["amount"] = normalized.get("cost_usd")
        if "cost_usd" not in normalized:
            raw_amount = normalized.get("amount")
            if raw_amount is not None:
                try:
                    normalized["cost_usd"] = float(Decimal(str(raw_amount)))
                except InvalidOperation, ValueError, TypeError, OverflowError:
                    normalized["cost_usd"] = None
        return normalized

    @model_validator(mode="after")
    def _verify_cost_event_semantics(self) -> AgentPipelineCostEvent:
        if self.amount is not None and (not self.amount.is_finite() or self.amount < 0):
            raise ValueError("producer_cost_amount_must_be_finite_and_nonnegative")
        if (
            self.amount is not None
            and self.cost_usd is not None
            and (Decimal(str(self.cost_usd)) != self.amount)
        ):
            raise ValueError("producer_cost_compatibility_projection_mismatch")
        if self.cost_origin == "unknown" and (self.amount is not None or self.cost_usd is not None):
            raise ValueError("unknown_cost_origin_cannot_carry_amount")
        if self.cost_origin in {"reported", "estimated"} and (
            self.amount is None or self.cost_usd is None
        ):
            raise ValueError("known_cost_origin_requires_amount")
        if self.cost_origin == "reuse" and (
            self.amount != Decimal(0) or self.cost_usd != 0.0 or self.origin_event_id is None
        ):
            raise ValueError("reuse_cost_requires_exact_zero_and_origin_event")
        if self.settlement_status == "committed" and (
            self.durability is None or self.durability == "none" or self.amount is None
        ):
            raise ValueError("committed_cost_event_lacks_durable_known_outcome")
        if self.control_job_attempt is not None and self.pre_admission_attempt_id is not None:
            raise ValueError("producer_attempt_attribution_is_ambiguous")
        if (
            self.control_job_attempt is not None or self.pre_admission_attempt_id is not None
        ) and self.durability != "ledger":
            raise ValueError("producer_attempt_attribution_requires_durable_ledger")
        return self


class AgentPipelineUnattributedCostScalar(BaseModel):
    """A legacy monetary scalar whose lease attribution is not established."""

    model_config = ConfigDict(extra="forbid")

    source_kind: Literal[
        "step_summary",
        "attempt_summary",
        "pipeline_summary",
        "performance_summary_llm",
        "performance_summary_variant_row",
    ]
    source_field: Literal["cost_usd", "reported_cost_usd", "estimated_cost_usd"]
    claimed_value_usd: float
    scope: Literal["not_established"] = "not_established"
    attempt: int | None = Field(default=None, ge=1, strict=True)
    agent: str | None = None
    model: str | None = None
    model_variant_id: str | None = None
    source_index: int | None = Field(default=None, ge=0, strict=True)

    @field_validator("claimed_value_usd", mode="before")
    @classmethod
    def _claimed_scalar_must_be_finite_nonnegative_number(cls, value: object) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise ValueError("unattributed_cost_scalar_must_be_numeric")
        try:
            amount = float(value)
        except (OverflowError, ValueError) as exc:
            raise ValueError("unattributed_cost_scalar_must_be_finite_nonnegative") from exc
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("unattributed_cost_scalar_must_be_finite_nonnegative")
        return amount


_AGENT_PIPELINE_COST_SCALAR_FIELDS = (
    "cost_usd",
    "reported_cost_usd",
    "estimated_cost_usd",
)
_AGENT_PIPELINE_OWNER_CONTEXT_KEY = "verified_control_job_attempt"


def _owner_attempt_from_validation_context(context: object) -> int | None:
    if not isinstance(context, Mapping):
        return None
    value = context.get(_AGENT_PIPELINE_OWNER_CONTEXT_KEY)
    if type(value) is not int or value < 1:
        return None
    return value


def _current_agent_pipeline_cost_events(
    events: list[AgentPipelineCostEvent], owner_attempt: int | None
) -> list[AgentPipelineCostEvent]:
    if owner_attempt is None:
        return []
    return [
        event
        for event in events
        if event.durability == "ledger"
        and event.control_job_attempt == owner_attempt
        and event.pre_admission_attempt_id is None
    ]


def _capture_unattributed_cost_scalars(
    value: Mapping[str, Any],
    *,
    source_kind: Literal["step_summary", "attempt_summary", "pipeline_summary"],
    projected_values: Mapping[str, Any] | None = None,
) -> list[object]:
    existing = value.get("unattributed_cost_scalars")
    rows: list[object] = list(existing) if isinstance(existing, (list, tuple)) else []
    for source_field in _AGENT_PIPELINE_COST_SCALAR_FIELDS:
        claimed_value = value.get(source_field)
        if claimed_value is None:
            continue
        if (
            projected_values is not None
            and not isinstance(claimed_value, bool)
            and claimed_value == projected_values.get(source_field)
        ):
            continue
        rows.append(
            {
                "source_kind": source_kind,
                "source_field": source_field,
                "claimed_value_usd": claimed_value,
                "scope": "not_established",
                "attempt": value.get("attempt"),
                "agent": value.get("agent"),
                "model": value.get("model"),
                "model_variant_id": value.get("model_variant_id"),
            }
        )
    return rows


def _remove_reconciled_summary_scalar_claims(
    rows: list[object],
    *,
    source_kind: Literal["step_summary", "attempt_summary", "pipeline_summary"],
    projection: Mapping[str, Any],
) -> list[object]:
    retained: list[object] = []
    for raw in rows:
        row = AgentPipelineUnattributedCostScalar.model_validate(raw)
        if (
            row.source_kind == source_kind
            and row.claimed_value_usd == projection.get(row.source_field)
            and projection.get(row.source_field) is not None
        ):
            continue
        retained.append(row)
    return retained


def _remove_reconciled_child_step_scalar_claims(
    rows: list[object],
    *,
    steps: list[AgentPipelineStep],
    owner_attempt: int | None,
) -> list[object]:
    """Remove captured step claims only when every possible source child reconciles."""
    if owner_attempt is None:
        return rows

    retained: list[object] = []
    identity_fields = ("attempt", "agent", "model", "model_variant_id")
    for raw in rows:
        row = AgentPipelineUnattributedCostScalar.model_validate(raw)
        if row.source_kind != "step_summary":
            retained.append(row)
            continue

        # Missing labels are not identity. Treat them as wildcards so an old or
        # partially captured row cannot be cleared by a similarly named sibling.
        possible_sources = [
            step
            for step in steps
            if all(
                getattr(row, field) is None or getattr(row, field) == getattr(step, field)
                for field in identity_fields
            )
        ]
        if not possible_sources:
            retained.append(row)
            continue

        reconciles_every_possible_source = all(
            (
                projected := _agent_pipeline_cost_projection(step.cost_events, owner_attempt).get(
                    row.source_field
                )
            )
            is not None
            and projected == row.claimed_value_usd
            for step in possible_sources
        )
        if not reconciles_every_possible_source:
            retained.append(row)
    return retained


def _deduplicate_unattributed_cost_scalars(
    rows: list[object],
) -> list[AgentPipelineUnattributedCostScalar]:
    unique: dict[tuple[object, ...], AgentPipelineUnattributedCostScalar] = {}
    for raw in rows:
        row = AgentPipelineUnattributedCostScalar.model_validate(raw)
        key = (
            row.source_kind,
            row.source_field,
            row.claimed_value_usd,
            row.scope,
            row.attempt,
            row.agent,
            row.model,
            row.model_variant_id,
            row.source_index,
        )
        unique.setdefault(key, row)
    return list(unique.values())


def _performance_summary_without_unattributed_cost_scalars(
    value: object,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not isinstance(value, Mapping):
        return None, []
    normalized = dict(value)
    rows: list[dict[str, Any]] = []
    llm = normalized.get("llm")
    if isinstance(llm, Mapping):
        llm_row = dict(llm)
        claimed_value = llm_row.get("cost_usd")
        if claimed_value is not None:
            rows.append(
                {
                    "source_kind": "performance_summary_llm",
                    "source_field": "cost_usd",
                    "claimed_value_usd": claimed_value,
                    "scope": "not_established",
                }
            )
        llm_row["cost_usd"] = None
        normalized["llm"] = llm_row
    variant_rows = normalized.get("variant_rows")
    if isinstance(variant_rows, (list, tuple)):
        sanitized_rows: list[object] = []
        for index, raw_row in enumerate(variant_rows):
            if not isinstance(raw_row, Mapping):
                sanitized_rows.append(raw_row)
                continue
            row = dict(raw_row)
            claimed_value = row.get("cost_usd")
            if claimed_value is not None:
                rows.append(
                    {
                        "source_kind": "performance_summary_variant_row",
                        "source_field": "cost_usd",
                        "claimed_value_usd": claimed_value,
                        "scope": "not_established",
                        "model": row.get("model"),
                        "model_variant_id": row.get("model_variant_id"),
                        "source_index": index,
                    }
                )
            row["cost_usd"] = None
            sanitized_rows.append(row)
        normalized["variant_rows"] = sanitized_rows
    return normalized, rows


def _agent_pipeline_cost_projection(
    events: list[AgentPipelineCostEvent], owner_attempt: int | None
) -> dict[str, Any]:
    """Derive current-attempt totals only with an explicit root owner context."""
    current_attempt_events = _current_agent_pipeline_cost_events(events, owner_attempt)
    if not current_attempt_events:
        return {
            "cost_usd": None,
            "reported_cost_usd": None,
            "estimated_cost_usd": None,
            "cost_origin": None,
            "cost_origin_counts": {},
            "settlement_status_counts": {},
            "settlement_event_ids": (),
        }
    cost_origin_counts: dict[str, int] = {}
    settlement_status_counts: dict[str, int] = {}
    reported_cost_usd = 0.0
    estimated_cost_usd = 0.0
    cost_is_unknown = False
    total_cost_usd = 0.0
    for event in current_attempt_events:
        cost_origin_counts[event.cost_origin] = cost_origin_counts.get(event.cost_origin, 0) + 1
        settlement_status_counts[event.settlement_status] = (
            settlement_status_counts.get(event.settlement_status, 0) + 1
        )
        if event.cost_origin == "reported" and event.cost_usd is not None:
            reported_cost_usd += event.cost_usd
        if event.cost_origin == "estimated" and event.cost_usd is not None:
            estimated_cost_usd += event.cost_usd
        if (
            event.cost_origin == "unknown"
            or event.settlement_status in {"pending", "unknown"}
            or event.cost_usd is None
        ):
            cost_is_unknown = True
        elif event.cost_origin in {"reported", "estimated", "reuse"}:
            total_cost_usd += event.cost_usd
    origins = set(cost_origin_counts)
    return {
        "cost_usd": None if cost_is_unknown else total_cost_usd,
        "reported_cost_usd": reported_cost_usd,
        "estimated_cost_usd": estimated_cost_usd,
        "cost_origin": next(iter(origins)) if len(origins) == 1 else None,
        "cost_origin_counts": cost_origin_counts,
        "settlement_status_counts": settlement_status_counts,
        "settlement_event_ids": tuple(event.event_id for event in current_attempt_events),
    }


def _cost_events_from_pipeline_steps(steps: object) -> list[AgentPipelineCostEvent]:
    """Read already validated per-call events from step payloads."""
    events: list[AgentPipelineCostEvent] = []
    if not isinstance(steps, (list, tuple)):
        return events
    for raw_step in steps:
        if isinstance(raw_step, AgentPipelineStep):
            events.extend(raw_step.cost_events)
            continue
        if isinstance(raw_step, Mapping):
            raw_events = raw_step.get("cost_events")
            if isinstance(raw_events, (list, tuple)):
                events.extend(AgentPipelineCostEvent.model_validate(row) for row in raw_events)
    return events


class AgentPipelineStep(BaseModel):
    """Agent pipeline step public type."""

    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(default=1, ge=1)
    agent: str
    action: str
    status: Literal["ok", "warn", "fail", "info"] = "info"
    timestamp: datetime | None = None
    summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    details_cost_scope: Literal["not_established"] = Field(
        default="not_established",
        description=(
            "Opaque diagnostic details are not reconciled to the verified ControlJob lease "
            "attempt or included in current cost totals."
        ),
    )
    prompt: str | None = None
    response: str | None = None
    model: str | None = None
    provider: str | None = None
    model_variant_id: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    reported_cost_usd: float | None = Field(default=None, ge=0.0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    cost_origin: AgentPipelineCostOrigin | None = None
    cost_origin_counts: dict[AgentPipelineCostOrigin, int] = Field(default_factory=dict)
    settlement_status_counts: dict[AgentPipelineSettlementStatus, int] = Field(default_factory=dict)
    settlement_event_ids: tuple[str, ...] = ()
    cost_events: list[AgentPipelineCostEvent] = Field(default_factory=list)
    unattributed_cost_scalars: list[AgentPipelineUnattributedCostScalar] = Field(
        default_factory=list
    )
    token_usage: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _derive_cost_summary_from_events(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, Mapping):
            return value
        raw_events = value.get("cost_events")
        events = (
            [AgentPipelineCostEvent.model_validate(row) for row in raw_events]
            if isinstance(raw_events, (list, tuple))
            else []
        )
        normalized = dict(value)
        projection = _agent_pipeline_cost_projection(
            events, _owner_attempt_from_validation_context(info.context)
        )
        normalized.update(projection)
        scalar_rows = _capture_unattributed_cost_scalars(
            value,
            source_kind="step_summary",
            projected_values=projection,
        )
        owner_attempt = _owner_attempt_from_validation_context(info.context)
        if owner_attempt is not None:
            scalar_rows = _remove_reconciled_summary_scalar_claims(
                scalar_rows,
                source_kind="step_summary",
                projection=projection,
            )
        normalized["unattributed_cost_scalars"] = scalar_rows
        return normalized


class AgentPipelineAttempt(BaseModel):
    """Agent pipeline attempt public type."""

    model_config = ConfigDict(extra="forbid")

    attempt: int = Field(ge=1)
    status: str = "unknown"
    verdict: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    reported_cost_usd: float | None = Field(default=None, ge=0.0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    cost_origin_counts: dict[AgentPipelineCostOrigin, int] = Field(default_factory=dict)
    settlement_status_counts: dict[AgentPipelineSettlementStatus, int] = Field(default_factory=dict)
    steps: list[AgentPipelineStep] = Field(default_factory=list)
    unattributed_cost_scalars: list[AgentPipelineUnattributedCostScalar] = Field(
        default_factory=list
    )
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _derive_cost_summary_from_steps(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, Mapping):
            return value
        events = _cost_events_from_pipeline_steps(value.get("steps"))
        normalized = dict(value)
        projection = _agent_pipeline_cost_projection(
            events, _owner_attempt_from_validation_context(info.context)
        )
        normalized.update(projection)
        normalized["unattributed_cost_scalars"] = _capture_unattributed_cost_scalars(
            value,
            source_kind="attempt_summary",
            projected_values=projection,
        )
        normalized.pop("cost_origin", None)
        normalized.pop("settlement_event_ids", None)
        return normalized

    @model_validator(mode="after")
    def _reconcile_cost_projection_and_unattributed_scalars(
        self, info: ValidationInfo
    ) -> AgentPipelineAttempt:
        events = _cost_events_from_pipeline_steps(self.steps)
        projection = _agent_pipeline_cost_projection(
            events, _owner_attempt_from_validation_context(info.context)
        )
        self.cost_usd = projection["cost_usd"]
        self.reported_cost_usd = projection["reported_cost_usd"]
        self.estimated_cost_usd = projection["estimated_cost_usd"]
        self.cost_origin_counts = projection["cost_origin_counts"]
        self.settlement_status_counts = projection["settlement_status_counts"]
        owner_attempt = _owner_attempt_from_validation_context(info.context)
        summary_scalars: list[object] = list(self.unattributed_cost_scalars)
        if owner_attempt is not None:
            summary_scalars = _remove_reconciled_summary_scalar_claims(
                summary_scalars,
                source_kind="attempt_summary",
                projection=projection,
            )
            summary_scalars = _remove_reconciled_child_step_scalar_claims(
                summary_scalars,
                steps=self.steps,
                owner_attempt=owner_attempt,
            )
        self.unattributed_cost_scalars = _deduplicate_unattributed_cost_scalars(
            [
                *summary_scalars,
                *(row for step in self.steps for row in step.unattributed_cost_scalars),
            ]
        )
        return self


class RetrievalPhaseTelemetry(BaseModel):
    """Retrieval phase telemetry public type."""

    model_config = ConfigDict(extra="forbid")

    phase: str
    lane: str | None = None
    duration_ms: int = Field(default=0, ge=0)
    candidates_total: int = Field(default=0, ge=0)
    candidates_selected: int = Field(default=0, ge=0)
    docs_fetched: int = Field(default=0, ge=0)


class RetrievalTelemetryView(BaseModel):
    """Retrieval telemetry summary for agent pipelines, including lane and phase counters."""

    model_config = ConfigDict(extra="forbid")

    mode: str = "hybrid"
    lane_used: str = "fastlane"
    metadata_docs_fetched: int = Field(default=0, ge=0)
    local_index_size_bytes: int = Field(default=0, ge=0)
    local_index_docs_total: int = Field(default=0, ge=0)
    candidates_filtered: int = Field(default=0, ge=0)
    candidates_promoted: int = Field(default=0, ge=0)
    phases: list[RetrievalPhaseTelemetry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PreflightDiagnosticView(BaseModel):
    """API view of one preflight diagnostic surfaced to runtime clients."""

    model_config = ConfigDict(extra="forbid")

    code: str
    severity: str = "error"
    message: str
    path: list[str] = Field(default_factory=list)
    replanning_hints: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class PreflightReportView(BaseModel):
    """API view of preflight readiness, diagnostics, and the persisted report reference."""

    model_config = ConfigDict(extra="forbid")

    ready_to_run: bool = False
    diagnostics: list[PreflightDiagnosticView] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    report_ref: ArtifactRef | None = None


class EvaluatorScoresView(BaseModel):
    """Normalized evaluator score breakdown exposed by runtime agent-pipeline views."""

    model_config = ConfigDict(extra="forbid")

    kpi_score: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty_score: float = Field(default=0.0, ge=0.0, le=1.0)
    constraints_score: float = Field(default=0.0, ge=0.0, le=1.0)
    data_quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    budget_score: float = Field(default=0.0, ge=0.0, le=1.0)
    total_score: float = Field(default=0.0, ge=0.0, le=1.0)


class EvaluatorReportView(BaseModel):
    """API view of evaluator verdicts, scores, reasons, and replanning hints."""

    model_config = ConfigDict(extra="forbid")

    verdict: EvaluatorVerdict | None = None
    scores: EvaluatorScoresView = Field(default_factory=EvaluatorScoresView)
    reasons: list[str] = Field(default_factory=list)
    replanning_hints: list[str] = Field(default_factory=list)
    diagnostics: list[PreflightDiagnosticView] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    report_ref: ArtifactRef | None = None


class IterationLifecycleView(BaseModel):
    """Current iteration state with stop reason and latest evaluator verdict."""

    model_config = ConfigDict(extra="forbid")

    iteration: int = Field(default=1, ge=1)
    state: IterationLifecycleState = "plan_created"
    stop_reason: StopReason | None = None
    last_verdict: EvaluatorVerdict | None = None
    state_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class ReproducibilityView(BaseModel):
    """Hashes, seeds, and missing refs used to assess whether a run can be replayed."""

    model_config = ConfigDict(extra="forbid")

    seed: int = Field(default=0, ge=0)
    seed_source: str | None = None
    determinism_tier: str | None = None
    plan_hash: str | None = None
    registry_hash: str | None = None
    method_catalog_hash: str | None = None
    data_snapshot_hash: str | None = None
    input_bindings_hash: str | None = None
    readiness: str | None = None
    why_partial: list[str] = Field(default_factory=list)
    missing_refs: list[str] = Field(default_factory=list)
    suggested_next_step: str | None = None
    manifest_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class RunEvidenceNeedView(BaseModel):
    """One evidence need derived from the execution plan for retrieval and promotion flows."""

    model_config = ConfigDict(extra="forbid")

    need_id: str
    metric: str
    geography: str | None = None
    time_start: str | None = None
    time_end: str | None = None
    granularity: str = "annual"
    quality_min: float = Field(default=0.6, ge=0.0, le=1.0)
    purpose: str = "policy_drafting"
    matched_plan_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RunEvidencePlanView(BaseModel):
    """Fetch plan describing how a connector/profile can satisfy a run evidence need."""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    metric_id: str
    connector_id: str
    dataset_id: str
    profile_id: str | None = None
    source_lane: str = "fastlane"
    quality_min: float = Field(default=0.6, ge=0.0, le=1.0)
    filters: dict[str, list[str]] = Field(default_factory=dict)
    date_start: str | None = None
    date_end: str | None = None
    granularity: str | None = None
    fallback_count: int = Field(default=0, ge=0)
    matched_need_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RunEvidencePromotionView(BaseModel):
    """Candidate evidence promotion surfaced while reviewing retrieved data options."""

    model_config = ConfigDict(extra="forbid")

    promotion_id: str
    metric_id: str
    connector_id: str
    dataset_id: str
    profile_id: str | None = None
    source_lane: str = "explorelane"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = "pending"
    created_at: datetime | None = None
    signals: list[str] = Field(default_factory=list)
    matched_plan_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunEvidenceContextView(BaseModel):
    """Joined evidence context linking plans, snapshots, promotions, and related artifacts."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    execution_plan_ref: ArtifactRef | None = None
    evidence_bundle_ref: ArtifactRef | None = None
    fabric_retrieval_trace_ref: ArtifactRef | None = None
    data_snapshot_ref: ArtifactRef | None = None
    data_view_request_ref: ArtifactRef | None = None
    data_view_request_profile_status: Literal[
        "caller_selected_profile", "worker_default_limited", "not_requested", "not_established"
    ] = Field(
        default="not_established",
        description=(
            "Profile-selection provenance only; does not establish source authority or currentness."
        ),
    )
    input_bindings_ref: ArtifactRef | None = None
    materialization_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    production_data_evidence_context: dict[str, Any] = Field(default_factory=dict)
    related_artifacts: list[ArtifactRef] = Field(default_factory=list)
    data_needs: list[RunEvidenceNeedView] = Field(default_factory=list)
    fetch_plans: list[RunEvidencePlanView] = Field(default_factory=list)
    promotion_candidates: list[RunEvidencePromotionView] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AgentPipelineView(BaseModel):
    """Composite runtime view of agent attempts, retrieval, evaluation, and iteration state."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    owner_control_job_attempt: int | None = Field(
        default=None,
        ge=1,
        strict=True,
        description=(
            "Verified ControlJob lease attempt bound to this run; null means the owner attempt "
            "was not established."
        ),
    )
    total_attempts: int = Field(default=0, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    reported_cost_usd: float | None = Field(default=None, ge=0.0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    cost_origin_counts: dict[AgentPipelineCostOrigin, int] = Field(default_factory=dict)
    settlement_status_counts: dict[AgentPipelineSettlementStatus, int] = Field(default_factory=dict)
    latest_verdict: str | None = None
    attempts: list[AgentPipelineAttempt] = Field(default_factory=list)
    unattributed_cost_events: list[AgentPipelineCostEvent] = Field(default_factory=list)
    unattributed_cost_scalars: list[AgentPipelineUnattributedCostScalar] = Field(
        default_factory=list
    )
    decision_packet_ref: ArtifactRef | None = None
    reflexion_terminal_ref: ArtifactRef | None = None
    retrieval: RetrievalTelemetryView | None = None
    execution_plan_ref: ArtifactRef | None = None
    method_catalog_snapshot_ref: ArtifactRef | None = None
    preflight: PreflightReportView | None = None
    evaluator: EvaluatorReportView | None = None
    iteration_lifecycle: IterationLifecycleView | None = None
    reproducibility: ReproducibilityView | None = None
    performance_summary: dict[str, Any] | None = None
    source: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _derive_cost_summary_from_attempts(cls, value: object, info: ValidationInfo) -> object:
        if not isinstance(value, Mapping):
            return value
        events: list[AgentPipelineCostEvent] = []
        raw_attempts = value.get("attempts")
        if isinstance(raw_attempts, (list, tuple)):
            for raw_attempt in raw_attempts:
                if isinstance(raw_attempt, AgentPipelineAttempt):
                    events.extend(event for step in raw_attempt.steps for event in step.cost_events)
                elif isinstance(raw_attempt, Mapping):
                    events.extend(_cost_events_from_pipeline_steps(raw_attempt.get("steps")))
        normalized = dict(value)
        projection = _agent_pipeline_cost_projection(
            events, _owner_attempt_from_validation_context(info.context)
        )
        normalized.update(projection)
        normalized["unattributed_cost_scalars"] = _capture_unattributed_cost_scalars(
            value,
            source_kind="pipeline_summary",
            projected_values=projection,
        )
        normalized.pop("cost_origin", None)
        normalized.pop("settlement_event_ids", None)
        performance_summary, performance_scalars = (
            _performance_summary_without_unattributed_cost_scalars(
                normalized.get("performance_summary")
            )
        )
        normalized["performance_summary"] = performance_summary
        normalized["unattributed_cost_scalars"] = [
            *normalized.get("unattributed_cost_scalars", []),
            *performance_scalars,
        ]
        return normalized

    @classmethod
    def _from_verified_owner_context(
        cls,
        *,
        owner_control_job_attempt: int | None,
        **values: Any,
    ) -> AgentPipelineView:
        """Validate a pipeline with the owner selector reconciled by its route."""
        values["owner_control_job_attempt"] = owner_control_job_attempt
        return cls.model_validate(
            values,
            context={_AGENT_PIPELINE_OWNER_CONTEXT_KEY: owner_control_job_attempt},
        )

    @model_validator(mode="after")
    def _reconcile_cost_projection_and_unattributed_sources(
        self, info: ValidationInfo
    ) -> AgentPipelineView:
        owner_attempt = _owner_attempt_from_validation_context(info.context)
        if owner_attempt is None:
            self.owner_control_job_attempt = None
        elif self.owner_control_job_attempt != owner_attempt:
            raise ValueError("agent_pipeline_owner_context_mismatch")

        context = {_AGENT_PIPELINE_OWNER_CONTEXT_KEY: owner_attempt}
        self.attempts = [
            AgentPipelineAttempt.model_validate(attempt.model_dump(mode="python"), context=context)
            for attempt in self.attempts
        ]
        if owner_attempt is not None:
            for attempt in self.attempts:
                for step in attempt.steps:
                    for event in step.cost_events:
                        if (
                            event.durability == "ledger"
                            and event.control_job_attempt != owner_attempt
                        ):
                            raise ValueError("agent_pipeline_event_owner_attempt_mismatch")
        events = _cost_events_from_pipeline_steps(
            [step for attempt in self.attempts for step in attempt.steps]
        )
        projection = _agent_pipeline_cost_projection(events, owner_attempt)
        self.cost_usd = projection["cost_usd"]
        self.reported_cost_usd = projection["reported_cost_usd"]
        self.estimated_cost_usd = projection["estimated_cost_usd"]
        self.cost_origin_counts = projection["cost_origin_counts"]
        self.settlement_status_counts = projection["settlement_status_counts"]
        summary_scalars: list[object] = list(self.unattributed_cost_scalars)
        if owner_attempt is not None:
            summary_scalars = _remove_reconciled_summary_scalar_claims(
                summary_scalars,
                source_kind="pipeline_summary",
                projection=projection,
            )
        self.unattributed_cost_scalars = _deduplicate_unattributed_cost_scalars(
            [
                *summary_scalars,
                *(row for attempt in self.attempts for row in attempt.unattributed_cost_scalars),
            ]
        )
        if any(event.control_job_attempt is not None for event in self.unattributed_cost_events):
            raise ValueError("unattributed_cost_event_claims_control_job_attempt")
        event_ids = [event.event_id for event in self.unattributed_cost_events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("duplicate_unattributed_cost_event")
        return self


class RunWorkflowNodeView(BaseModel):
    """Workflow graph node annotated with runtime status, duration, and artifact IO."""

    model_config = ConfigDict(extra="forbid")

    alias: str
    node_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    depth: int = Field(default=0, ge=0)
    status: NodeStatus = "unknown"
    duration_ms: int = Field(default=0, ge=0)
    skip_reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    input_artifact_ids: list[str] = Field(default_factory=list)
    output_artifact_ids: list[str] = Field(default_factory=list)
    input_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    output_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    heat: float = Field(default=0.0, ge=0.0)


class RunWorkflowEdgeView(BaseModel):
    """Run workflow edge view data model."""

    model_config = ConfigDict(extra="forbid")

    from_alias: str
    to_alias: str


class RunWorkflowSummary(BaseModel):
    """Summary statistics for the workflow graph executed by a run."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str | None = None
    error_policy: str | None = None
    status: str | None = None
    node_count: int = Field(default=0, ge=0)
    edge_count: int = Field(default=0, ge=0)
    ok_count: int = Field(default=0, ge=0)
    skip_count: int = Field(default=0, ge=0)
    fail_count: int = Field(default=0, ge=0)
    max_depth: int = Field(default=0, ge=0)
    critical_path_duration_ms: int | None = Field(default=None, ge=0)


class RunWorkflowView(BaseModel):
    """Workflow graph payload returned by runtime explorer endpoints."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    summary: RunWorkflowSummary
    nodes: list[RunWorkflowNodeView] = Field(default_factory=list)
    edges: list[RunWorkflowEdgeView] = Field(default_factory=list)
    workflow_spec_ref: ArtifactRef | None = None
    workflow_report_ref: ArtifactRef | None = None
    notes: list[str] = Field(default_factory=list)


class ArtifactManifestView(BaseModel):
    """Metadata returned when a client inspects a stored artifact manifest."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    manifest_profile_sha256: str | None = None
    kind: str
    media_type: str
    byte_size: int = Field(ge=0)
    created_at: datetime
    schema_name: str | None = None
    schema_version: str | None = None
    producer_component: str | None = None
    producer_version: str | None = None
    inputs: list[InputRef] = Field(default_factory=list)
    integrity_sha256: str


class DecisionPacketOutlineEntry(BaseModel):
    """Typed outline entry surfaced for decision-packet previews."""

    model_config = ConfigDict(extra="forbid")

    section_id: str
    title: str
    section_type: str | None = None


class DecisionPacketEffectSize(BaseModel):
    """Structured uncertainty payload used by typed decision-packet previews."""

    model_config = ConfigDict(extra="forbid")

    point: float | None = None
    ci_80: tuple[float, float] | None = None
    ci_95: tuple[float, float] | None = None
    quantiles: dict[str, float] | None = None
    identifiability: Literal["identified", "estimated", "assumed"] | None = None
    disputed: bool | None = None
    method: str | None = None


class DecisionPacketMetricSignificance(BaseModel):
    """Typed metric-significance entry embedded in decision-packet previews."""

    model_config = ConfigDict(extra="forbid")

    baseline_model_id: str | None = None
    candidate_model_id: str | None = None
    metric_direction: str | None = None
    baseline_value: float | None = None
    candidate_value: float | None = None
    delta_value: float | None = None
    test_id: str | None = None
    test_label: str | None = None
    p_value: float | None = None
    p_adj: float | None = None
    alpha: float | None = None
    significant: bool | None = None
    effect_size: DecisionPacketEffectSize | None = None
    assumption_warnings: list[str] = Field(default_factory=list)
    calibration_warnings: list[str] = Field(default_factory=list)


class DecisionPacketMetricComparisonRow(BaseModel):
    """Typed metric-comparison row embedded in decision-packet previews."""

    model_config = ConfigDict(extra="forbid")

    metric_id: str
    metric_direction: str | None = None
    baseline_model_id: str | None = None
    candidate_model_id: str | None = None
    baseline_value: float | None = None
    candidate_value: float | None = None
    delta_value: float | None = None
    family_id: str | None = None
    family_scope: str | None = None
    sample_size_effective: int | None = None
    resampling_method: str | None = None
    test_id: str | None = None
    test_label: str | None = None
    statistic: float | None = None
    effect_size: DecisionPacketEffectSize | None = None
    p_value: float | None = None
    p_adj: float | None = None
    alpha: float | None = None
    significant: bool | None = None
    assumption_warnings: list[str] = Field(default_factory=list)
    calibration_warnings: list[str] = Field(default_factory=list)


class DecisionPacketAuthoredBlock(BaseModel):
    """Typed authored-text block embedded in decision-packet previews."""

    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    content: str
    author: Literal["citation", "human", "drafter", "formalizer", "critic"] | None = None
    author_agent_version: str | None = None
    sources: list[dict[str, str]] = Field(default_factory=list)
    timestamp: str | None = None
    confidence: float | None = None
    reviewed_by_human: bool | None = None


class DecisionPacketPreview(BaseModel):
    """Typed additive sidecar for decision-packet artifact previews."""

    model_config = ConfigDict(extra="allow")

    document_outline: list[DecisionPacketOutlineEntry] = Field(default_factory=list)
    metric_significance_by_metric: dict[str, DecisionPacketMetricSignificance] = Field(
        default_factory=dict
    )
    metric_validation_comparison_rows: list[DecisionPacketMetricComparisonRow] = Field(
        default_factory=list
    )
    blocks: list[DecisionPacketAuthoredBlock] = Field(default_factory=list)
    narrative_blocks: list[DecisionPacketAuthoredBlock] = Field(default_factory=list)
    evidence_summary_blocks: list[DecisionPacketAuthoredBlock] = Field(default_factory=list)


class PredictiveCoverageScenarioPreview(BaseModel):
    """One scenario's recomputed predictive interval counts for inspection."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    metric_name: str
    interval_requested_count: int = Field(ge=0)
    interval_available_count: int = Field(ge=0)
    interval_evaluated_count: int = Field(ge=0)
    interval_hit_count: int = Field(ge=0)
    nominal_confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    interval_type: str | None = None
    observed_hit_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class PredictiveCoverageDiagnosticPreview(BaseModel):
    """Limited, reader-materialized interval diagnostic; never an S10 grade."""

    model_config = ConfigDict(extra="forbid")

    source_artifact_id: str
    source_manifest_profile_sha256: str
    source_schema_version: Literal["1.0"]
    metric: Literal["predictive_interval_coverage"]
    measurement_status: Literal["measured", "not_measured", "invalid_source"]
    reason_code: Literal[
        "none",
        "no_evaluated_intervals",
        "predictive_scope_not_established",
        "unsupported_report_scope",
        "malformed_report_shape",
        "malformed_interval_counts",
        "stored_hit_rate_mismatch",
    ]
    assessment: Literal["limited"]
    source_materialization: Literal["reader_materialized"]
    canon_read_status: CanonReadStatus = "not_evaluated"
    producer_attestation_status: Literal["not_established"]
    s10_metric_mapping_status: Literal["not_established"]
    s10_threshold_status: Literal["not_established"]
    issuer_status: Literal["not_established"]
    effective_time_status: Literal["not_established"]
    counterfactual_credibility_status: Literal["not_established"]
    causal_effect_status: Literal["not_established"]
    may_not_use_for: list[
        Literal["promotion", "publication", "policy_selection", "causal_effect_claim"]
    ]
    scenarios: list[PredictiveCoverageScenarioPreview]


class ArtifactContentPreview(BaseModel):
    """Artifact content preview public type."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    manifest_profile_sha256: str | None = None
    kind: str
    media_type: str
    mode: PreviewMode
    canon_read_status: CanonReadStatus = "not_evaluated"
    size_bytes: int = Field(ge=0)
    max_bytes: int = Field(ge=1)
    truncated: bool = False
    preview: Any = None
    decision_packet_preview: DecisionPacketPreview | None = None
    predictive_coverage_diagnostic: PredictiveCoverageDiagnosticPreview | None = None


class ArtifactLineageNode(BaseModel):
    """One node in the artifact-lineage graph with status, size, role, and depth."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    manifest_profile_sha256: str | None = None
    role: str | None = None
    kind: str | None = None
    media_type: str | None = None
    status: str
    byte_size: int = Field(default=0, ge=0)
    depth: int = Field(default=0, ge=0)


class ArtifactLineageEdge(BaseModel):
    """Artifact lineage edge public type."""

    model_config = ConfigDict(extra="forbid")

    parent_artifact_id: str
    parent_manifest_profile_sha256: str | None = None
    child_artifact_id: str
    child_manifest_profile_sha256: str | None = None
    role: str


class ArtifactLineageView(BaseModel):
    """Artifact lineage graph plus completeness and corruption indicators."""

    model_config = ConfigDict(extra="forbid")

    root_artifact_ids: list[str] = Field(default_factory=list)
    root_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    total_nodes: int = Field(default=0, ge=0)
    total_edges: int = Field(default=0, ge=0)
    total_size_bytes: int = Field(default=0, ge=0)
    is_complete: bool = False
    missing_artifact_ids: list[str] = Field(default_factory=list)
    corrupted_artifact_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    nodes: list[ArtifactLineageNode] = Field(default_factory=list)
    edges: list[ArtifactLineageEdge] = Field(default_factory=list)


class ArtifactSchemaView(BaseModel):
    """Schema metadata exposed for an artifact's serialized payload."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    manifest_profile_sha256: str | None = None
    kind: str
    media_type: str
    canon_read_status: CanonReadStatus = "not_evaluated"
    schema_name: str | None = None
    schema_version: str | None = None
    top_level_keys: list[str] = Field(default_factory=list)


class ArtifactBatchRequest(BaseModel):
    """Batch artifact lookup request used to avoid client-side N+1 fetches."""

    model_config = ConfigDict(extra="forbid")

    artifact_ids: list[str] = Field(default_factory=list, min_length=1, max_length=100)


class RunsBatchRequest(BaseModel):
    """Batch run lookup request used to avoid client-side N+1 fetches."""

    model_config = ConfigDict(extra="forbid")

    run_ids: list[str] = Field(default_factory=list, min_length=1, max_length=100)


class RunFeedbackView(BaseModel):
    """Runtime view of monitoring, compare, and reissue artifacts attached to a run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    decision_packet_ref: ArtifactRef | None = None
    feedback_loop: dict[str, Any] | None = None
    monitoring_contract: DecisionMonitoringContract | None = None
    monitoring_report: DecisionMonitoringReport | None = None
    compare_report: DecisionCompareReport | None = None
    reissue_plan: DecisionReissuePlan | None = None
    decision_validity: dict[str, Any] | None = None
    notes: list[str] = Field(default_factory=list)


class RunEquilibriaView(BaseModel):
    """Runtime view of a Foundry equilibrium multiplicity report."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    source_kind: SourceKind
    report_ref: ArtifactRef | None = None
    report: EquilibriumMultiplicityReport | None = None
    notes: list[str] = Field(default_factory=list)


class RunCompareView(BaseModel):
    """Side-by-side comparison payload for two runtime runs."""

    model_config = ConfigDict(extra="forbid")

    left_run_id: str
    right_run_id: str
    report: DecisionCompareReport


class RunsListResponse(BaseModel):
    """Paginated response envelope returned by the runs listing endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    page: CursorPage
    runs: list[RunSummary] = Field(default_factory=list)


class RunDetailsResponse(BaseModel):
    """Response envelope returned when a client requests one run's detailed record."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    run: RunDetails


class RunTimelineResponse(BaseModel):
    """Response envelope returned by the run timeline endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    temporal_scope: TemporalScope | None = None
    timeline: RunTimelineView


class RunNodesResponse(BaseModel):
    """Response envelope returned by the run nodes endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    source_kind: SourceKind
    nodes: list[RunNodeRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RunLineageResponse(BaseModel):
    """Response envelope returned by the run artifact-lineage endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    temporal_scope: TemporalScope | None = None
    lineage: ArtifactLineageView


class RunEvidenceContextResponse(BaseModel):
    """Response envelope returned by the run evidence-context endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    context: RunEvidenceContextView


class NodeDebugResponse(BaseModel):
    """Response envelope returned by the node debug endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    debug: NodeDebugView


class SimulationResultCandidateResponse(BaseModel):
    """Response envelope for the candidate-only simulation-result debug route."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    debug: SimulationResultCandidateView


class GovernanceDebugResponse(BaseModel):
    """Response envelope returned by the governance debug endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    debug: GovernanceDebugView


class RunErrorsResponse(BaseModel):
    """Response envelope returned by the run errors endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    errors: list[RunErrorView] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AgentPipelineResponse(BaseModel):
    """Response envelope returned by the agent-pipeline endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    pipeline: AgentPipelineView


class RunWorkflowResponse(BaseModel):
    """Response envelope returned by the workflow graph endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    workflow: RunWorkflowView


class ArtifactManifestResponse(BaseModel):
    """Response envelope returned by the artifact manifest endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    artifact: ArtifactManifestView


class ArtifactContentResponse(BaseModel):
    """Response envelope returned by the artifact preview/content endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    artifact: ArtifactContentPreview


class ArtifactLineageResponse(BaseModel):
    """Response envelope returned by the artifact lineage endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    lineage: ArtifactLineageView


class ArtifactSchemaResponse(BaseModel):
    """Response envelope returned by the artifact schema endpoint."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    meta: ApiMeta
    schema_view: ArtifactSchemaView = Field(alias="schema")


class ArtifactBatchResponse(BaseModel):
    """Response envelope returned by the artifact batch endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    artifacts: list[ArtifactManifestView] = Field(default_factory=list)


class MobilityEstimateRequest(BaseModel):
    """Request payload for runtime mobility estimation endpoints."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal[
        "complete_case",
        "attrition_adjusted",
        "sequential_attrition_adjusted",
        "refreshment_anchored",
    ] = "attrition_adjusted"
    n_classes: int = Field(default=5, ge=2)
    origin_classes: list[int] = Field(default_factory=list)
    destination_classes: list[int | None] = Field(default_factory=list)
    retention_indicators: list[int] | None = None
    retention_indicators_by_wave: list[list[int]] | None = None
    attrition_features: list[list[float]] | None = None
    attrition_features_by_wave: list[list[list[float]]] | None = None
    sample_weights: list[float] | None = None
    retention_probabilities: list[float] | None = None
    retention_probabilities_by_wave: list[list[float]] | None = None
    destination_marginals: list[float] | None = None
    refreshment_destination_classes: list[int] | None = None
    refreshment_weights: list[float] | None = None
    feature_names: list[str] = Field(default_factory=list)
    estimator: Literal["ipcw", "aipw"] = "aipw"
    positivity_floor: float = Field(default=0.05, ge=0.0, le=0.49)
    compute_bounds: bool = True
    monotone: bool = True
    panel_length: int | None = Field(default=None, ge=2)
    waves_used: list[int] = Field(default_factory=list)
    persist_artifact: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class MobilityBoundsRequest(BaseModel):
    """Request payload for runtime mobility bounds endpoints."""

    model_config = ConfigDict(extra="forbid")

    observed_joint_matrix: list[list[float]]
    row_marginals: list[float]
    column_marginals: list[float] | None = None
    headline_metric: str = "upward_rate"
    persist_artifact: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class MobilityEstimateResponse(BaseModel):
    """Response envelope returned after estimating a mobility report."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    report: dict[str, Any]
    mobility_report_ref: ArtifactRef | None = None
    bounds_bundle_ref: ArtifactRef | None = None


class MobilityBoundsResponse(BaseModel):
    """Response envelope returned for direct or report-linked mobility bounds."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    bounds: dict[str, Any]
    bounds_bundle_ref: ArtifactRef | None = None
    mobility_report_ref: ArtifactRef | None = None
    cell_bounds: dict[str, list[float]] = Field(default_factory=dict)
    summary_bounds: dict[str, list[float]] = Field(default_factory=dict)


class MobilityReportResponse(BaseModel):
    """Response envelope returned when loading one persisted mobility report."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    report: dict[str, Any]
    mobility_report_ref: ArtifactRef


class MobilityDiagnosticsResponse(BaseModel):
    """Response envelope returned when loading mobility diagnostics only."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    diagnostics: dict[str, Any]
    mobility_report_ref: ArtifactRef


class RunsBatchResponse(BaseModel):
    """Response envelope returned by the run batch endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    runs: list[RunDetails] = Field(default_factory=list)


class RunFeedbackResponse(BaseModel):
    """Response envelope returned by the run feedback endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    feedback: RunFeedbackView


class RunEquilibriaResponse(BaseModel):
    """Response envelope returned by the run equilibria endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    equilibria: RunEquilibriaView


class RunCompareResponse(BaseModel):
    """Response envelope returned by the run comparison endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    compare: RunCompareView


class FeedbackActionResponse(BaseModel):
    """Outcome payload returned after evaluating feedback or reissuing a decision."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    run_id: str
    action: Literal["evaluate_feedback", "reissue"]
    status: Literal["completed", "accepted"] = "completed"
    monitoring_report_ref: ArtifactRef | None = None
    compare_report_ref: ArtifactRef | None = None
    reissue_plan_ref: ArtifactRef | None = None
    reissued_run_id: str | None = None
    message: str


__all__ = [
    "AgentPipelineAttempt",
    "AgentPipelineCostEvent",
    "AgentPipelineResponse",
    "AgentPipelineStep",
    "AgentPipelineUnattributedCostScalar",
    "AgentPipelineView",
    "ApiMeta",
    "ArtifactContentPreview",
    "ArtifactContentResponse",
    "ArtifactLineageEdge",
    "ArtifactLineageNode",
    "ArtifactLineageResponse",
    "ArtifactLineageView",
    "ArtifactManifestResponse",
    "ArtifactManifestView",
    "ArtifactSchemaResponse",
    "ArtifactSchemaView",
    "AuthMeResponse",
    "BureaucraticAuthorship",
    "BureaucraticBlock",
    "BureaucraticBlockKind",
    "BureaucraticDocument",
    "BureaucraticDocumentStatus",
    "BureaucraticEpistemicKind",
    "BureaucraticEpistemicSummary",
    "BureaucraticExportFormat",
    "BureaucraticExportResponse",
    "BureaucraticGenre",
    "BureaucraticRenderRequest",
    "BureaucraticRenderResponse",
    "BureaucraticTemplateRef",
    "CanonReadStatus",
    "ComparabilityReport",
    "ComparabilityStatus",
    "CompareCandidate",
    "CompareCandidatesResponse",
    "CompareResponseStatus",
    "CompareRunResponse",
    "ComparisonFrame",
    "CounterfactualMetric",
    "CounterfactualMetricsResponse",
    "CounterfactualMode",
    "CursorPage",
    "DecisionCompareReport",
    "DecisionMonitoringContract",
    "DecisionMonitoringReport",
    "DecisionPacketAuthoredBlock",
    "DecisionPacketEffectSize",
    "DecisionPacketMetricComparisonRow",
    "DecisionPacketMetricSignificance",
    "DecisionPacketOutlineEntry",
    "DecisionPacketPreview",
    "DecisionReissuePlan",
    "DeltaDistribution",
    "DeltaDominance",
    "DeltaQuantity",
    "DeltaSignificance",
    "DisputeStatus",
    "EngineeringCapabilityAbsenceView",
    "EpochBoundaryLineageView",
    "EpochCertificateStalenessView",
    "EpochDependencyStalenessView",
    "EpochDerivedRecomputeView",
    "EpochOpenWorldRiskComponentView",
    "EpochOpenWorldRiskView",
    "EpochPerturbationClass",
    "EpochPerturbationView",
    "EpochPredicateProvenance",
    "EpochProjectionDenominatorView",
    "EpochProjectionStatus",
    "EpochStalenessProjectionResponse",
    "EpochStalenessProjectionView",
    "EvaluatorReportView",
    "EvaluatorScoresView",
    "FabricImpactAnalysisRequest",
    "FabricImpactAnalysisResponse",
    "FabricImpactRecord",
    "FabricImpactSubjectKind",
    "FabricQualityBatchResponse",
    "FabricQualityTrustBatchRequest",
    "FabricReplayRunResponse",
    "FabricSourceScorecardsResponse",
    "FabricTrustBatchResponse",
    "FeedbackActionResponse",
    "GovernanceDebugResponse",
    "GovernanceDebugView",
    "InstitutionalAuthorityAbsenceView",
    "IterationLifecycleView",
    "LineageBatchRequest",
    "LineageBatchResolution",
    "LineageBatchResponse",
    "LineageCompactSummaryItem",
    "LineageDelta",
    "LineageExportLinks",
    "LineageExportResponse",
    "LineageFreshness",
    "LineageGraphEdge",
    "LineageGraphNode",
    "LineageGraphView",
    "LineageRef",
    "LineageResponse",
    "LineageSummaryKind",
    "MobilityBoundsRequest",
    "MobilityBoundsResponse",
    "MobilityDiagnosticsResponse",
    "MobilityEstimateRequest",
    "MobilityEstimateResponse",
    "MobilityReportResponse",
    "NodeDebugResponse",
    "NodeDebugView",
    "NodeStatus",
    "PredictiveCoverageDiagnosticPreview",
    "PredictiveCoverageScenarioPreview",
    "PreflightDiagnosticView",
    "PreflightReportView",
    "PreviewMode",
    "QuantityClass",
    "QuantityCoverageEntry",
    "QuantityCoverageSummary",
    "QuantityUncertainty",
    "QuantityValue",
    "ReproducibilityView",
    "RetrievalPhaseTelemetry",
    "RetrievalTelemetryView",
    "RunCandidateSimulationAcquisitionHistoryEntry",
    "RunCandidateSimulationChildProfileBinding",
    "RunCandidateSimulationN5Observation",
    "RunCandidateSimulationProjection",
    "RunCompareResponse",
    "RunCompareView",
    "RunDetails",
    "RunDetailsResponse",
    "RunEquilibriaResponse",
    "RunEquilibriaView",
    "RunErrorView",
    "RunErrorsResponse",
    "RunEvidenceContextResponse",
    "RunEvidenceContextView",
    "RunEvidenceNeedView",
    "RunEvidencePlanView",
    "RunEvidencePromotionView",
    "RunFeedbackResponse",
    "RunFeedbackView",
    "RunGenericCycleSimulationChildProfileBinding",
    "RunGenericCycleSimulationN5Observation",
    "RunGenericCycleSimulationProjection",
    "RunLineageResponse",
    "RunNodeRecord",
    "RunNodesResponse",
    "RunOperatorDiagnostic",
    "RunOperatorProjectionStateLabel",
    "RunQuantitiesResponse",
    "RunRecordV1",
    "RunRecursiveCycleBranchFailure",
    "RunRecursiveCycleCheckpoint",
    "RunSummary",
    "RunTimelineEvent",
    "RunTimelineResponse",
    "RunTimelineSummary",
    "RunTimelineView",
    "RunWorkflowEdgeView",
    "RunWorkflowNodeView",
    "RunWorkflowResponse",
    "RunWorkflowSummary",
    "RunWorkflowView",
    "RunsListResponse",
    "RuntimeApiError",
    "RuntimeApiProblem",
    "RuntimeApiProblemContext",
    "ScenarioAssumption",
    "ScenarioAssumptionStatus",
    "ScenarioCapabilitiesResponse",
    "ScenarioCapability",
    "ScenarioConstraint",
    "ScenarioConstraintSeverity",
    "ScenarioCreateRequest",
    "ScenarioIntervention",
    "ScenarioInterventionOperator",
    "ScenarioLifecycleStatus",
    "ScenarioListResponse",
    "ScenarioManifest",
    "ScenarioManifestResponse",
    "ScenarioRef",
    "ScenarioStatus",
    "ScenarioSurfaceSupport",
    "SimulationResultCandidateResponse",
    "SimulationResultCandidateView",
    "SourceKind",
    "TemporalCapabilitiesResponse",
    "TemporalCapabilitiesView",
    "TemporalEventKind",
    "TemporalEventPoint",
    "TemporalGapRange",
    "TemporalIndexEvidence",
    "TemporalRange",
    "TemporalRef",
    "TemporalScope",
    "TemporalSurfaceCapability",
    "TemporalSurfaceSupport",
    "TrustMetadataRef",
    "UnitRef",
    "UniversalAuthorityProfile",
    "UniversalPolicyDesignCase",
    "UniversalPolicyDesignCaseAuditSurface",
    "UniversalPolicyFacets",
    "UniversalPolicyGrammarAuthorityEnvelope",
    "UniversalPolicyGrammarBlocker",
    "VerificationMetadata",
    "VerificationStatus",
    "epoch_staleness_semantic_hash",
]

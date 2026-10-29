"""Runtime API contracts for run explorer, debug, evidence, and artifact-inspection endpoints."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Generic, Literal, TypeVar, get_args, get_origin

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    PrivateAttr,
    TypeAdapter,
    ValidationInfo,
    field_validator,
    model_validator,
)

from polisyos.ir.governance import NormativeOutcomeChannel, PolicyLayerLevel
from polisyos.ir.observation import IdentificationMode

from ..artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    artifact_ref_identity_key,
)
from ..trace import RunTerminality
from .bounded_liveness import BoundedLivenessResolution
from .decision_packet_hte import (
    DecisionPacketLegacyHTEFeaturePreview,
    DecisionPacketLegacyHTEPreview,
)
from .decision_validity import DecisionValidityStatus, SourceCurrentUseProjection
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
from .owned_attempt_anchor import (
    OwnedAttemptAnchorProjectionAssociation,
    OwnedAttemptAnchorRef,
    OwnedAttemptAnchorRefusalAssociation,
    OwnedHTERequestContextV1,
)
from .policy_design_case_projection import PolicyDesignCaseProjection

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
    def _validate_llm_authority_boundary(
        self,
    ) -> UniversalPolicyGrammarAuthorityEnvelope:
        if self.source_classification.startswith("llm_"):
            illegal = sorted(set(self.authoritative_for) & _AUTHORITY_PROTECTED_PURPOSES)
            if illegal:
                raise ValueError(
                    f"{self.source_classification} cannot authorize protected purposes: "
                    + ", ".join(illegal)
                )
        return self


FacetNameT = TypeVar("FacetNameT", bound=UniversalPolicyFacetName)


class UniversalPolicyFacetBase(BaseModel, Generic[FacetNameT]):
    """Common semantic grounding carried by every universal policy grammar facet."""

    model_config = ConfigDict(extra="forbid")

    facet_name: FacetNameT
    concept_spine_refs: tuple[str, ...] = Field(min_length=1)
    source_vocabulary_refs: tuple[str, ...] = Field(min_length=1)
    derivation_rule_ref: str = Field(min_length=1)


class UniversalPolicyInstrumentTypeFacet(UniversalPolicyFacetBase[Literal["instrument_type"]]):
    """Controlled policy instrument facet."""

    facet_name: Literal["instrument_type"] = "instrument_type"
    value: UniversalPolicyInstrumentType


class UniversalPolicyTargetingTypeFacet(UniversalPolicyFacetBase[Literal["targeting_type"]]):
    """Controlled policy targeting facet."""

    facet_name: Literal["targeting_type"] = "targeting_type"
    value: UniversalPolicyTargetingType


class UniversalPolicyDeliveryChannelFacet(UniversalPolicyFacetBase[Literal["delivery_channel"]]):
    """Controlled delivery-channel facet."""

    facet_name: Literal["delivery_channel"] = "delivery_channel"
    value: UniversalPolicyDeliveryChannel


class UniversalPolicyFundingChannelFacet(UniversalPolicyFacetBase[Literal["funding_channel"]]):
    """Controlled funding-channel facet."""

    facet_name: Literal["funding_channel"] = "funding_channel"
    value: UniversalPolicyFundingChannel


class UniversalPolicyAuthorityTypeFacet(UniversalPolicyFacetBase[Literal["authority_type"]]):
    """Authority-layer facet reusing the IR governance policy-layer enum."""

    facet_name: Literal["authority_type"] = "authority_type"
    value: PolicyLayerLevel


class UniversalPolicyOutcomeChannelFacet(UniversalPolicyFacetBase[Literal["outcome_channel"]]):
    """Outcome-channel facet reusing the IR normative outcome enum."""

    facet_name: Literal["outcome_channel"] = "outcome_channel"
    value: NormativeOutcomeChannel


class UniversalPolicyRiskFacetRecord(UniversalPolicyFacetBase[Literal["risk_facet"]]):
    """Controlled risk facet reconciled with deterministic critic/challenge vocabularies."""

    facet_name: Literal["risk_facet"] = "risk_facet"
    value: UniversalPolicyRiskFacet


class UniversalPolicyMethodNeedFacet(UniversalPolicyFacetBase[Literal["method_need"]]):
    """Method-need facet reusing the IR observation identification-mode enum."""

    facet_name: Literal["method_need"] = "method_need"
    value: IdentificationMode


class UniversalPolicyPopulationPredicateFacet(
    UniversalPolicyFacetBase[Literal["population_predicate"]]
):
    """Controlled population predicate facet grounded in the concept spine."""

    facet_name: Literal["population_predicate"] = "population_predicate"
    value: UniversalPopulationPredicate


class UniversalPolicyGeographyPredicateFacet(
    UniversalPolicyFacetBase[Literal["geography_predicate"]]
):
    """Controlled geography predicate facet grounded in the concept spine."""

    facet_name: Literal["geography_predicate"] = "geography_predicate"
    value: UniversalGeographyPredicate


class UniversalPolicyTimePredicateFacet(UniversalPolicyFacetBase[Literal["time_predicate"]]):
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
    def _positive_denominator_requires_owner_evidence(
        self,
    ) -> EpochProjectionDenominatorView:
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
    n8_candidate_value_ref: str | None = Field(default=None, exclude_if=lambda value: value is None)
    n8_candidate_decision_grade: Literal["low"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
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
        elif self.n8_status not in {"value_pending_n8", "value_conditional"}:
            raise ValueError("run_n8_joint_scope_must_remain_candidate_only")
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
        if (
            self.n8_candidate_value_ref is not None or self.n8_candidate_decision_grade is not None
        ) and (
            self.n8_status != "value_conditional"
            or self.n8_candidate_decision_grade != "low"
            or self.simulation_result_ref is None
            or self.n8_candidate_value_ref != str(self.simulation_result_ref.artifact_id)
            or self.n8_joint_scope_status != "not_established"
            or not {
                "n5_execution_request_provenance_not_established",
                "n4_source_candidates_are_alternatives_not_authored_compound_design",
                "child_to_parent_refinement_rule_not_established",
            }.issubset(self.n8_authority_blockers)
        ):
            raise ValueError("run_n8_joint_candidate_conditional_binding_invalid")
        if (
            self.n8_status == "value_conditional"
            and self.n8_joint_scope_status is not None
            and (self.n8_candidate_value_ref is None or self.n8_candidate_decision_grade is None)
        ):
            raise ValueError("run_n8_joint_candidate_conditional_value_missing")
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
            or self.n8_status not in {"value_pending_n8", "value_conditional"}
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
    def _bind_n9_current_front(
        self,
    ) -> RunCandidateSimulationAcquisitionContinuationProjection:
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


class RunCandidateSimulationRetainedEvaluation(BaseModel):
    """Original evaluation occurrence retained under a verified Runtime decision.

    These refs describe the prior execution. They never claim that execution
    consumed the newly admitted acquisition source.
    """

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    candidate_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    world_model_record_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evaluation_job_id: str = Field(min_length=1)
    evaluation_run_id: str = Field(min_length=1)
    generation_run_id: str = Field(min_length=1)
    cycle_index: int = Field(ge=0)
    n4_source_ref: ArtifactRef
    context_job_ref: ArtifactRef
    n5_input_ref: ArtifactRef
    n5_execution_ref: ArtifactRef
    n5_result_ref: ArtifactRef
    basis_ref: ArtifactRef

    @model_validator(mode="after")
    def _verify_selected_refs(self) -> RunCandidateSimulationRetainedEvaluation:
        for ref, kind in (
            (self.n4_source_ref, "runtime.quality.n4_candidate_scenario_source"),
            (self.context_job_ref, "runtime.quality.cycle_substrate_context_job"),
            (self.n5_input_ref, "runtime.quality.candidate_simulation_n5_input"),
            (self.n5_execution_ref, "runtime.quality.candidate_simulation_execution"),
            (self.n5_result_ref, "polisyos.runtime.joint_simulation_result"),
            (self.basis_ref, "runtime_quality.acquisition_evaluation_basis"),
        ):
            if (
                ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("candidate_acquisition_retained_evaluation_ref_invalid")
        return self


class RunCandidateSimulationAcquisitionHistoryEntryV3(BaseModel):
    """Verified source admission with an unchanged, separate evaluation occurrence.

    Runtime resolves the entire source/decision/frontier/fold join before this
    display DTO is constructed. DTO validation alone is not that verification.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["policyos.runtime.run_candidate_simulation_acquisition_history.v3"]
    route_receipt_ref: ArtifactRef
    route_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    action_generation: int = Field(ge=1)
    terminal_outcome: Literal["source_admitted_evaluation_retained"]
    admitted_source_ref: ArtifactRef
    growth_receipt_ref: ArtifactRef
    evaluation_decision_ref: ArtifactRef
    current_continuation_ref: ArtifactRef
    retained_evaluation: RunCandidateSimulationRetainedEvaluation
    source_admission_status: Literal["admitted"] = "admitted"
    evaluation_disposition: Literal["retained_prior"] = "retained_prior"
    reentry_receipt_ref: None = None
    old_candidate_id: None = None
    new_candidate_id: None = None
    new_candidate_source_ref: None = None
    origin_source_ref: None = None
    expected_origin_source_ref: None = None
    reentry_receipt_schema_version: None = None
    continuation_join_status: None = None
    origin_source_binding_status: None = None
    continuation: None = None
    currentness_status: Literal["not_established"] = "not_established"
    authority_purpose: Literal["candidate_observation_only"] = "candidate_observation_only"
    publication_authority: Literal[False] = False

    @model_validator(mode="after")
    def _verify_retention_refs(self) -> RunCandidateSimulationAcquisitionHistoryEntryV3:
        for ref, kind in (
            (self.route_receipt_ref, "runtime_quality.acquisition_route_loop_receipt"),
            (self.growth_receipt_ref, "runtime_quality.acquisition_world_growth_receipt"),
            (self.evaluation_decision_ref, "runtime_quality.acquisition_evaluation_decision"),
            (self.current_continuation_ref, "runtime_quality.acquisition_retained_continuation"),
        ):
            if (
                ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("candidate_acquisition_retention_ref_invalid")
        if self.admitted_source_ref.manifest_profile_sha256 is None:
            raise ValueError("candidate_acquisition_admitted_source_profile_missing")
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
    acquisition_history: tuple[
        RunCandidateSimulationAcquisitionHistoryEntry
        | RunCandidateSimulationAcquisitionHistoryEntryV3,
        ...,
    ] = ()
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
    n5_owner_join_status: (
        Literal["resolved", "unavailable", "invalid", "mismatch", "not_established"] | None
    ) = Field(default=None, exclude_if=lambda value: value is None)
    n5_owner_join_limitation_code: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
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
            (
                self.child_profile_set_ref,
                "runtime.quality.recursive_n4_child_profile_set",
            ),
            (
                self.n5_execution_ref,
                "runtime.quality.generic_cycle_simulation_n5_execution",
            ),
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
        if self.status == "joint_simulated" and self.simulation_result_ref is None:
            raise ValueError("run_generic_n5_success_result_missing")
        if (
            self.status == "joint_simulated"
            and self.n5_execution_ref is None
            and self.n5_owner_join_status not in {"unavailable", "not_established"}
        ):
            raise ValueError("run_generic_n5_success_owner_missing_without_limitation")
        if self.n5_owner_join_status == "resolved":
            if (
                self.n5_owner_join_limitation_code is not None
                or self.n5_request_binding_status != "resolved"
                or self.n5_execution_ref is None
            ):
                raise ValueError("run_generic_n5_owner_join_resolved_invalid")
        elif self.n5_owner_join_status is not None:
            if not self.n5_owner_join_limitation_code:
                raise ValueError("run_generic_n5_owner_join_limitation_missing")
            if self.n5_owner_join_status in {"invalid", "mismatch"} and (
                self.status != "simulation_blocked" or self.n8_status != "value_blocked"
            ):
                raise ValueError("run_generic_n5_owner_conflict_not_refused")
        elif self.n5_owner_join_limitation_code is not None:
            raise ValueError("run_generic_n5_owner_join_status_missing")
        if (self.n5_request_binding_status == "resolved") != (
            self.n5_request_content_hash is not None
        ):
            raise ValueError("run_generic_n5_request_binding_shape_invalid")
        if self.n8_lineage_status == "resolved" and (self.n5_request_binding_status != "resolved"):
            raise ValueError("run_generic_n8_request_binding_not_established")
        if self.n8_status == "value_conditional":
            if (
                self.n5_interaction_evidence is None
                or self.n8_numeric_interaction is None
                or self.n8_numeric_interaction_basis is None
                or self.n8_interaction_sampling_status is None
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


RunN6CycleSearchTerminalKind = Literal[
    "a_spec_gap",
    "tool_failure",
    "composition_invalid",
    "recursive_blocked",
    "search_ceiling_repair_required",
    "human_decision_required",
    "acquisition_required",
    "budget_exhausted",
    "frontier_stable",
    "grounded_admissible",
    "grounded_partial_admissible",
    "grounded_abstention",
]
RunN6CycleRefinementDecision = Literal[
    "refine",
    "acquire",
    "reframe",
    "decompose",
    "human_decision",
    "abstain",
    "block_candidate",
    "stop",
]
RunN6CycleSearchIterationStatus = Literal[
    "blocked",
    "blocked_no_retry",
    "governance_required",
    "acquisition_required",
    "abstained",
    "stopped",
    "refined_shadow",
]
RunN6CycleGroundingStatus = Literal[
    "current_valid",
    "grounded_shadow",
    "grounding_gap",
    "grounding_failed",
    "grounding_unavailable",
]
RunN6CycleValueStatus = Literal[
    "value_pending_n8",
    "value_ready",
    "value_conditional",
    "value_blocked",
]
RunN6CycleValueDecisionGrade = Literal["blocked", "low", "medium", "high"]
RunN6CycleVoiAction = Literal["advance", "stop", "escalate", "blocked"]
RunN6CycleRunTerminalStatus = Literal["completed", "blocked"]


class RunGenericCycleSimulationN6CycleHistoryEntry(BaseModel):
    """One exact N6 cycle state carried by the persisted candidate projection."""

    model_config = ConfigDict(extra="forbid")

    node_ref: str = Field(min_length=1)
    cycle_index: int = Field(ge=0)
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    design_problem_basis_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    selected_candidate_ref: str = Field(min_length=1)
    selected_candidate_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    generation_cycle_run_terminal_status: RunN6CycleRunTerminalStatus
    terminal_kind: RunN6CycleSearchTerminalKind
    refinement_decision: RunN6CycleRefinementDecision
    search_iteration_status: RunN6CycleSearchIterationStatus
    grounding_status: RunN6CycleGroundingStatus
    grounding_current_valid: bool
    value_status: RunN6CycleValueStatus
    value_decision_grade: RunN6CycleValueDecisionGrade | None = None
    value_authority_blockers: tuple[str, ...] = ()
    value_ref: str | None = None
    voi_next_action: RunN6CycleVoiAction


class RunGenericCycleSimulationProjection(BaseModel):
    """Persisted generic simulation lineage exposed as candidate-only history."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "policyos.runtime.run_generic_cycle_simulation_projection.v1",
        "policyos.runtime.run_generic_cycle_simulation_projection.v2",
        "policyos.runtime.run_generic_cycle_simulation_projection.v3",
        "policyos.runtime.run_generic_cycle_simulation_projection.v4",
        "policyos.runtime.run_generic_cycle_simulation_projection.v5",
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
    joint_parent_observations: tuple[RunCandidateSimulationN5Observation, ...] = Field(
        default=(), exclude_if=lambda value: not value
    )
    joint_parent_status: Literal["resolved", "not_established"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    joint_parent_limitation_code: str | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    n5_limitation_code: str | None = Field(default=None, min_length=1)
    recursive_cycle_checkpoint: RunRecursiveCycleCheckpoint | None = None
    n6_cycle_history_status: Literal["resolved", "not_established"] | None = None
    n6_cycle_history_limitation_code: Literal["n6_cycle_history_not_emitted"] | None = None
    n6_cycle_history: tuple[RunGenericCycleSimulationN6CycleHistoryEntry, ...] = ()
    limitation_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _verify_generic_projection(self) -> RunGenericCycleSimulationProjection:
        has_credal_attempt_projection = (
            self.credal_source_attempt_ref is not None
            or self.credal_source_status is not None
            or self.credal_source_limitation_code is not None
        )
        has_n6_cycle_history_extension = (
            self.n6_cycle_history_status is not None
            or self.n6_cycle_history_limitation_code is not None
            or bool(self.n6_cycle_history)
        )
        if self.n6_cycle_history_status == "resolved":
            if not self.n6_cycle_history or self.n6_cycle_history_limitation_code is not None:
                raise ValueError("run_generic_projection_n6_history_resolved_without_rows")
            history_keys = tuple((row.node_ref, row.cycle_index) for row in self.n6_cycle_history)
            if len(history_keys) != len(set(history_keys)):
                raise ValueError("run_generic_projection_n6_history_duplicate_cycle")
        elif self.n6_cycle_history_status == "not_established":
            if self.n6_cycle_history or self.n6_cycle_history_limitation_code != (
                "n6_cycle_history_not_emitted"
            ):
                raise ValueError("run_generic_projection_n6_history_refusal_not_fail_closed")
        elif self.n6_cycle_history or self.n6_cycle_history_limitation_code is not None:
            raise ValueError("run_generic_projection_n6_history_status_missing")

        has_joint_parent_extension = self.joint_parent_status is not None
        has_owner_join_extension = any(
            row.n5_owner_join_status is not None for row in self.n5_observations
        )
        has_v5_extension = has_joint_parent_extension or has_owner_join_extension
        if has_v5_extension and self.schema_version != (
            "policyos.runtime.run_generic_cycle_simulation_projection.v5"
        ):
            raise ValueError("run_generic_projection_v5_schema_invalid")
        if has_joint_parent_extension:
            if has_credal_attempt_projection:
                raise ValueError("run_generic_projection_parent_credal_conflict")
            if self.joint_parent_status == "resolved":
                if (
                    len(self.joint_parent_observations) != 1
                    or self.joint_parent_limitation_code is not None
                    or self.joint_parent_observations[0].status != "joint_simulated"
                    or self.joint_parent_observations[0].simulation_result_ref is None
                    or self.joint_parent_observations[0].simulation_ref is None
                    or self.joint_parent_observations[0].n5_interaction_evidence is None
                    or self.joint_parent_observations[0].n8_candidate_joint_selection_status
                    != "resolved"
                    or self.joint_parent_observations[0].n8_status
                    not in {"value_pending_n8", "value_conditional"}
                    or self.joint_parent_observations[0].n8_joint_scope_status != "not_established"
                ):
                    raise ValueError("run_generic_projection_parent_binding_invalid")
            elif self.joint_parent_observations or not self.joint_parent_limitation_code:
                raise ValueError("run_generic_projection_parent_limitation_missing")
        elif self.joint_parent_observations or self.joint_parent_limitation_code is not None:
            raise ValueError("run_generic_projection_parent_status_missing")
        if has_credal_attempt_projection:
            expected_schema = (
                "policyos.runtime.run_generic_cycle_simulation_projection.v4"
                if has_n6_cycle_history_extension
                else "policyos.runtime.run_generic_cycle_simulation_projection.v2"
            )
            if (
                self.schema_version != expected_schema
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
        else:
            expected_schema = (
                "policyos.runtime.run_generic_cycle_simulation_projection.v3"
                if has_n6_cycle_history_extension
                else "policyos.runtime.run_generic_cycle_simulation_projection.v1"
            )
            if not has_v5_extension and self.schema_version != expected_schema:
                raise ValueError("run_generic_projection_schema_extension_invalid")
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
            or self.joint_parent_status is not None
            or self.joint_parent_observations
            or self.joint_parent_limitation_code is not None
            or self.n6_cycle_history_status is not None
            or self.n6_cycle_history_limitation_code is not None
            or self.n6_cycle_history
            or self.limitation_code is None
        ):
            raise ValueError("run_generic_projection_refusal_shape_invalid")
        return self


class MethodExecutionPosteriorSummaryRef(BaseModel):
    """Point to one bounded posterior summary produced by a direct method run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    point_role: str = Field(min_length=1, max_length=96)
    ref: ArtifactRef

    @model_validator(mode="after")
    def _require_selected_profile(self) -> MethodExecutionPosteriorSummaryRef:
        if self.ref.manifest_profile_sha256 is None:
            raise ValueError("method_execution_posterior_summary_profile_missing")
        return self


class ObservationalInputResourcePolicy(BaseModel):
    """Pin bounded input reads and the selected estimator parameter profile."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[
        "polisyos.runtime.observational_input_resource_policy.v1",
        "polisyos.runtime.observational_input_resource_policy.v2",
        "polisyos.runtime.observational_input_resource_policy.v3",
        "polisyos.runtime.observational_input_resource_policy.v4",
        "polisyos.runtime.observational_input_resource_policy.v5",
    ] = "polisyos.runtime.observational_input_resource_policy.v1"
    revision: Literal["r1", "r2", "r3", "r4", "r5"] = "r1"
    max_manifest_bytes: int = Field(default=65_536, gt=0, le=1_048_576)
    max_bytes: int = Field(default=8_388_608, gt=0, le=134_217_728)
    max_depth: int = Field(default=64, gt=0, le=256)
    max_elements: int = Field(default=200_000, gt=0, le=5_000_000)
    method_contract_target: (
        Literal["polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"] | None
    ) = None
    required_estimator_n_jobs: Literal[1] | None = None
    method_execution_wait_policy: BoundedLivenessResolution | None = None
    method_fqn: (
        Literal[
            "causal.hte.causal_forest@2.0.0",
            "causal.hte.double_ml@2.0.0",
            "causal.hte.meta_learner@2.0.0",
            "causal.hte.forest_dr@2.0.0",
        ]
        | None
    ) = None
    method_profile_id: (
        Literal[
            "econml.causal_forest_dml.native_mean@2.0",
            "econml.dml.point_only@2.0",
            "econml.meta_learner.point_only@2.0",
            "econml.forest_dr.native_mean@2.0",
        ]
        | None
    ) = None
    execution_scope: (
        Literal[
            "estimator_n_jobs_one",
            "producer_scoped_joblib_parallelism_one",
        ]
        | None
    ) = None
    max_jobs: Literal[1] | None = None

    @field_validator("required_estimator_n_jobs", mode="before")
    @classmethod
    def _reject_boolean_required_estimator_n_jobs(cls, value: object) -> object:
        if type(value) is bool:
            raise ValueError(
                "observational_input_resource_policy_required_estimator_n_jobs_must_be_integer"
            )
        return value

    @model_validator(mode="after")
    def _require_coherent_profile_revision(self) -> ObservationalInputResourcePolicy:
        if self.revision == "r1":
            if (
                self.schema_version != "polisyos.runtime.observational_input_resource_policy.v1"
                or self.method_contract_target is not None
                or self.required_estimator_n_jobs is not None
                or self.method_execution_wait_policy is not None
                or self.method_fqn is not None
                or self.method_profile_id is not None
                or self.execution_scope is not None
                or self.max_jobs is not None
            ):
                raise ValueError("observational_input_resource_policy_r1_shape_invalid")
            return self
        if self.revision == "r2":
            if (
                self.schema_version != "polisyos.runtime.observational_input_resource_policy.v2"
                or self.method_contract_target
                != "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
                or self.required_estimator_n_jobs != 1
                or self.method_execution_wait_policy is not None
                or self.method_fqn is not None
                or self.method_profile_id is not None
                or self.execution_scope is not None
                or self.max_jobs is not None
            ):
                raise ValueError("observational_input_resource_policy_r2_shape_invalid")
            return self
        wait_policy = self.method_execution_wait_policy
        common_wait = (
            wait_policy is not None
            and wait_policy.producer_key == "runtime.observational_method_execution"
            and wait_policy.retry_ceiling == 0
            and wait_policy.escalation == "runtime_escalation"
        )
        if self.revision == "r3":
            if (
                self.schema_version != "polisyos.runtime.observational_input_resource_policy.v3"
                or self.method_contract_target
                != "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
                or self.required_estimator_n_jobs != 1
                or not common_wait
                or self.method_fqn is not None
                or self.method_profile_id is not None
                or self.execution_scope is not None
                or self.max_jobs is not None
            ):
                raise ValueError("observational_input_resource_policy_r3_shape_invalid")
            return self
        profile_by_method = {
            "causal.hte.causal_forest@2.0.0": (
                "econml.causal_forest_dml.native_mean@2.0",
                "estimator_n_jobs_one",
                1,
            ),
            "causal.hte.double_ml@2.0.0": (
                "econml.dml.point_only@2.0",
                "producer_scoped_joblib_parallelism_one",
                None,
            ),
            "causal.hte.meta_learner@2.0.0": (
                "econml.meta_learner.point_only@2.0",
                "producer_scoped_joblib_parallelism_one",
                None,
            ),
            "causal.hte.forest_dr@2.0.0": (
                "econml.forest_dr.native_mean@2.0",
                "estimator_n_jobs_one",
                1,
            ),
        }
        expected_profile = profile_by_method.get(self.method_fqn or "")
        if self.revision == "r4":
            if (
                self.schema_version != "polisyos.runtime.observational_input_resource_policy.v4"
                or self.method_contract_target
                != "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
                or not common_wait
                or expected_profile is None
                or self.method_profile_id != expected_profile[0]
                or self.execution_scope != expected_profile[1]
                or self.required_estimator_n_jobs != expected_profile[2]
                or self.max_jobs != 1
            ):
                raise ValueError("observational_input_resource_policy_r4_shape_invalid")
            return self

        required_estimator_jobs_by_method = {
            "causal.hte.causal_forest@2.0.0": 1,
            "causal.hte.double_ml@2.0.0": None,
            "causal.hte.meta_learner@2.0.0": None,
            "causal.hte.forest_dr@2.0.0": 1,
        }
        expected_method_profile_id = expected_profile[0] if expected_profile is not None else None
        if (
            self.schema_version != "polisyos.runtime.observational_input_resource_policy.v5"
            or self.method_contract_target
            != "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
            or not common_wait
            or expected_profile is None
            or self.method_profile_id != expected_method_profile_id
            or self.execution_scope != "producer_scoped_joblib_parallelism_one"
            or self.required_estimator_n_jobs
            != required_estimator_jobs_by_method.get(self.method_fqn or "")
            or self.max_jobs != 1
        ):
            raise ValueError("observational_input_resource_policy_r5_shape_invalid")
        return self

    def digest(self) -> str:
        """Return the unprefixed SHA-256 of the complete versioned budget."""
        payload = self.model_dump(mode="json")
        if self.revision in {"r1", "r2"}:
            # Preserve the exact canonical identity of historical persisted intents.
            payload.pop("method_execution_wait_policy")
        if self.revision == "r1":
            payload.pop("method_contract_target")
            payload.pop("required_estimator_n_jobs")
        if self.revision not in {"r4", "r5"}:
            # These method-scoped fields are absent from the canonical v1-v3 bytes.
            payload.pop("method_fqn")
            payload.pop("method_profile_id")
            payload.pop("execution_scope")
            payload.pop("max_jobs")
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


_ObservationalRunLimitation = Literal[
    "candidate_input_not_external_truth",
    "scientific_validity_not_established",
    "units_and_context_not_established",
    "source_access_revalidation_not_established",
]
_ContentAdmittedObservationalLimitation = Literal[
    "candidate_input_not_external_truth",
    "scientific_validity_not_established",
    "units_and_context_not_established",
    "source_access_revalidation_not_established",
    "legacy_hte_json_v1_source_normalized",
]

_OBSERVATIONAL_RUN_BASE_LIMITATIONS: tuple[_ObservationalRunLimitation, ...] = (
    "candidate_input_not_external_truth",
    "scientific_validity_not_established",
    "units_and_context_not_established",
)

_OBSERVATIONAL_HTE_SUCCESSOR_METHODS = frozenset(
    {
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    }
)
_OBSERVATIONAL_HTE_LEGACY_METHODS = frozenset(
    {"causal.hte.forest_dr@1.0.0", "causal.hte.forest_dr@1.1.0"}
)


def _literal_json_schema_values(annotation: Any) -> tuple[str, ...]:
    """Return string arms from a literal annotation, including optional unions."""
    if get_origin(annotation) is Literal:
        return tuple(value for value in get_args(annotation) if isinstance(value, str))
    return tuple(
        value
        for argument in get_args(annotation)
        for value in _literal_json_schema_values(argument)
    )


def _append_expected_limitations_json_schema(
    schema: dict[str, Any],
    *,
    model: type[BaseModel],
    protocol_field: str,
    status_field: str,
    limitations_field: str,
    expected_limitations: Callable[[str, str | None], tuple[str, ...]],
) -> None:
    """Project each runtime protocol/status caveat tuple into its wire schema."""
    protocol_values = _literal_json_schema_values(model.model_fields[protocol_field].annotation)
    status_field_info = model.model_fields[status_field]
    statuses: list[str | None] = []
    if status_field_info.default is None and not status_field_info.is_required():
        statuses.append(None)
    statuses.extend(_literal_json_schema_values(status_field_info.annotation))

    conditions: list[dict[str, Any]] = []
    for protocol in protocol_values:
        for status in statuses:
            if status is None:
                status_condition: dict[str, Any] = {
                    "anyOf": [
                        {"not": {"required": [status_field]}},
                        {
                            "properties": {status_field: {"type": "null"}},
                            "required": [status_field],
                        },
                    ]
                }
            else:
                status_condition = {
                    "properties": {status_field: {"const": status}},
                    "required": [status_field],
                }
            limitations = expected_limitations(protocol, status)
            conditions.append(
                {
                    "if": {
                        "allOf": [
                            {
                                "properties": {protocol_field: {"const": protocol}},
                                "required": [protocol_field],
                            },
                            status_condition,
                        ]
                    },
                    "then": {
                        "properties": {
                            limitations_field: {
                                "minItems": len(limitations),
                                "maxItems": len(limitations),
                                "prefixItems": [{"const": value} for value in limitations],
                                "items": False,
                            }
                        }
                    },
                }
            )
    schema["allOf"] = [*schema.get("allOf", []), *conditions]


def _observational_intent_manifest_identity(schema_version: str) -> tuple[str, str, str]:
    """Resolve one exact semantic intent version to its CAS manifest identity."""
    identities = {
        "polisyos.runtime.observational_run_intent.v1": (
            "runtime.observational_run_intent",
            "polisyos.runtime.ObservationalRunIntent",
            "1.0",
        ),
        "polisyos.runtime.observational_run_intent.v2": (
            "runtime.observational_run_intent",
            "polisyos.runtime.ObservationalRunIntent",
            "2.0",
        ),
        "polisyos.runtime.observational_run_intent.v3": (
            "runtime.observational_run_intent",
            "polisyos.runtime.ObservationalRunIntent",
            "3.0",
        ),
        "polisyos.runtime.content_admitted_observational_run_intent.v1": (
            "runtime.content_admitted_observational_run_intent",
            "polisyos.runtime.ContentAdmittedObservationalRunIntent",
            "1.0",
        ),
        "polisyos.runtime.content_admitted_observational_run_intent.v2": (
            "runtime.content_admitted_observational_run_intent",
            "polisyos.runtime.ContentAdmittedObservationalRunIntent",
            "2.0",
        ),
        "polisyos.runtime.content_admitted_observational_run_intent.v3": (
            "runtime.content_admitted_observational_run_intent",
            "polisyos.runtime.ContentAdmittedObservationalRunIntent",
            "3.0",
        ),
    }
    try:
        return identities[schema_version]
    except KeyError as exc:
        raise ValueError("observational_intent_semantic_schema_version_unsupported") from exc


class ObservationalRunIntent(BaseModel):
    """Persist submitted and resolved pins before a direct observational run is queued."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra=lambda schema: _append_expected_limitations_json_schema(
            schema,
            model=ObservationalRunIntent,
            protocol_field="protocol",
            status_field="source_access_revalidation_status",
            limitations_field="limitations",
            expected_limitations=lambda protocol, status: _expected_observational_limitations(
                protocol,
                source_access_revalidation_status=status,
            ),
        ),
    )

    schema_version: Literal[
        "polisyos.runtime.observational_run_intent.v1",
        "polisyos.runtime.observational_run_intent.v2",
        "polisyos.runtime.observational_run_intent.v3",
    ] = "polisyos.runtime.observational_run_intent.v1"
    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    requested_source_ref: ArtifactRef
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"]
    method_fqn: str = Field(min_length=1, max_length=256)
    method_version: str = Field(min_length=1, max_length=64)
    owned_hte_request_context: OwnedHTERequestContextV1 | None = None
    search_binding_admission: SearchUncertaintyTaskAdmissionSnapshot | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    search_binding_tenant_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        exclude_if=lambda value: value is None,
    )
    search_binding_cell_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        exclude_if=lambda value: value is None,
    )
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_build_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_build_digest_scope: Literal["class_source_only"] = "class_source_only"
    submitted_params_present: bool
    submitted_params: dict[str, JsonValue] = Field(default_factory=dict)
    resolved_params: dict[str, JsonValue]
    seed: int = Field(default=0, strict=True, ge=0, le=4_294_967_295)
    seed_policy_revision: Literal["server_seed_zero_v1"] = "server_seed_zero_v1"
    resource_policy: ObservationalInputResourcePolicy
    # Optional only for immutable pre-R3 history; current R3 admissions require
    # a selected CAS artifact carrying the exact policy body and profile.
    resource_policy_ref: ArtifactRef | None = None
    contract_target_id: Literal["foundry.causal.hte_observational_data.v1"] | None = None
    contract_target_fqn: (
        Literal["polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"] | None
    ) = None
    resource_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_governance: ArtifactGovernanceInfo
    source_tenant_context: ArtifactTenantContextInfo | None = None
    purpose: Literal["candidate_method_execution"] = "candidate_method_execution"
    source_access_revalidation_status: Literal["not_established"] | None = None
    limitations: tuple[_ObservationalRunLimitation, ...] = Field(
        default=_OBSERVATIONAL_RUN_BASE_LIMITATIONS,
        min_length=3,
        max_length=4,
    )
    created_at: datetime = Field(default_factory=_utc_now)

    def selection_digest(self) -> str:
        """Return a stable digest over every persisted accepted request pin."""
        payload = self.model_dump(mode="json")
        if self.schema_version == "polisyos.runtime.observational_run_intent.v1":
            # Keep pre-v2 content identity stable: the added optional field is
            # absent from every historical v1 canonical representation.
            payload.pop("owned_hte_request_context", None)
        if self.resource_policy_ref is None:
            # Preserve the historical canonical digest for intents that predate
            # the selected policy artifact and exact target tuple.
            payload.pop("resource_policy_ref", None)
            payload.pop("contract_target_id", None)
            payload.pop("contract_target_fqn", None)
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @model_validator(mode="after")
    def _require_pinned_source_and_policy(self) -> ObservationalRunIntent:
        _method_base, separator, fqn_version = self.method_fqn.rpartition("@")
        if (
            self.requested_source_ref.manifest_profile_sha256 is None
            or not separator
            or fqn_version != self.method_version
            or self.method_fqn
            not in _OBSERVATIONAL_HTE_LEGACY_METHODS | _OBSERVATIONAL_HTE_SUCCESSOR_METHODS
        ):
            raise ValueError("observational_run_intent_method_identity_invalid")
        is_successor = self.method_fqn in _OBSERVATIONAL_HTE_SUCCESSOR_METHODS
        request_context = self.owned_hte_request_context
        search_binding_ref = (
            request_context.search_uncertainty_task_binding_ref
            if request_context is not None
            else None
        )
        search_binding_present = search_binding_ref is not None
        if search_binding_present != (self.search_binding_tenant_id is not None):
            raise ValueError("observational_run_intent_search_tenant_scope_mismatch")
        if not search_binding_present and self.search_binding_cell_id is not None:
            raise ValueError("observational_run_intent_search_cell_without_binding")
        if self.schema_version == "polisyos.runtime.observational_run_intent.v3":
            snapshot = self.search_binding_admission
            if (
                not is_successor
                or not search_binding_present
                or type(snapshot) is not SearchUncertaintyTaskAdmissionSnapshot
                or self.search_binding_tenant_id is None
                or artifact_ref_identity_key(snapshot.binding_ref)
                != artifact_ref_identity_key(search_binding_ref)
                or snapshot.tenant_id != self.search_binding_tenant_id
                or snapshot.cell_id != self.search_binding_cell_id
                or snapshot.selected_method_fqn != self.method_fqn
                or snapshot.selected_method_abi_version != self.method_version
                or snapshot.selected_method_abi_digest != self.method_abi_digest
                or snapshot.selected_method_params != self.resolved_params
                or snapshot.selected_method_seed != self.seed
                or snapshot.selected_inference_profile_id != self.resource_policy.method_profile_id
                or artifact_ref_identity_key(snapshot.selected_method_input_ref)
                != artifact_ref_identity_key(self.requested_source_ref)
                or snapshot.selected_method_input_content_sha256
                != self.requested_source_ref.artifact_id.hex
            ):
                raise ValueError("observational_run_intent_search_snapshot_mismatch")
            params_bytes = json.dumps(
                self.resolved_params,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            if hashlib.sha256(params_bytes).hexdigest() != snapshot.selected_method_params_sha256:
                raise ValueError("observational_run_intent_search_snapshot_params_mismatch")
        elif self.search_binding_admission is not None:
            raise ValueError("observational_run_intent_search_snapshot_version_mismatch")
        if is_successor:
            if (
                self.schema_version
                not in {
                    "polisyos.runtime.observational_run_intent.v2",
                    "polisyos.runtime.observational_run_intent.v3",
                }
                or type(request_context) is not OwnedHTERequestContextV1
                or request_context.request_estimand_status != "declared"
                or request_context.request_target_scope_status != "declared"
                or request_context.outcome_variable_status != "declared"
                or request_context.treatment_variable_status != "declared"
                or request_context.contrast_status != "declared"
                or request_context.request_alpha_status != "declared"
                or request_context.requested_alpha is None
                or request_context.requested_guarantee_status not in {"declared", "not_established"}
                or (request_context.requested_guarantee_status == "declared")
                != (request_context.requested_guarantee is not None)
                or self.resolved_params.get("alpha") != request_context.requested_alpha
            ):
                raise ValueError("observational_run_intent_hte_successor_context_invalid")
        elif (
            self.schema_version != "polisyos.runtime.observational_run_intent.v1"
            or request_context is not None
            or self.search_binding_tenant_id is not None
            or self.search_binding_cell_id is not None
        ):
            raise ValueError("observational_run_intent_legacy_context_must_be_absent")
        if self.resource_policy_digest != self.resource_policy.digest():
            raise ValueError("observational_run_intent_resource_policy_digest_mismatch")
        if self.resource_policy_ref is not None and (
            self.resource_policy_ref.kind != "runtime.observational_input_resource_policy"
            or self.resource_policy_ref.media_type != "application/json"
            or self.resource_policy_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("observational_run_intent_resource_policy_ref_invalid")
        if self.resource_policy.revision in {"r3", "r4", "r5"} and (
            self.resource_policy_ref is None
            or self.contract_target_id != "foundry.causal.hte_observational_data.v1"
            or self.contract_target_fqn
            != "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        ):
            raise ValueError("observational_run_intent_r3_selected_contract_required")
        if self.resource_policy_ref is None and (
            self.contract_target_id is not None or self.contract_target_fqn is not None
        ):
            raise ValueError("observational_run_intent_target_without_policy_ref")
        if self.limitations != _expected_observational_limitations(
            self.protocol,
            source_access_revalidation_status=self.source_access_revalidation_status,
        ):
            raise ValueError("observational_run_intent_limitations_invalid")
        if any(name.startswith("__") for name in self.submitted_params) or any(
            name.startswith("__") for name in self.resolved_params
        ):
            raise ValueError("observational_run_intent_reserved_runtime_parameter")
        if not self.submitted_params_present and self.submitted_params:
            raise ValueError("observational_run_intent_submitted_params_presence_mismatch")
        if self.method_fqn == "causal.hte.forest_dr@1.1.0":
            if (
                self.resource_policy.revision not in {"r2", "r3"}
                or self.resource_policy.method_contract_target
                != "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
                or self.resource_policy.required_estimator_n_jobs != 1
                or type(self.resolved_params.get("n_jobs")) is not int
                or self.resolved_params.get("n_jobs") != 1
            ):
                raise ValueError("observational_run_intent_method_resource_profile_invalid")
        elif self.method_fqn in _OBSERVATIONAL_HTE_SUCCESSOR_METHODS:
            if (
                self.resource_policy.revision not in {"r4", "r5"}
                or self.resource_policy.method_contract_target
                != "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
                or self.resource_policy.method_execution_wait_policy is None
                or self.resource_policy.method_fqn != self.method_fqn
            ):
                raise ValueError("observational_run_intent_successor_resource_profile_invalid")
        elif self.method_version != "1.0.0":
            raise ValueError("observational_run_intent_historical_profile_version_invalid")
        elif (
            self.method_fqn == "causal.hte.forest_dr@1.0.0"
            and self.resource_policy.required_estimator_n_jobs is not None
        ):
            raise ValueError("observational_run_intent_method_resource_profile_invalid")
        return self

    def artifact_payload(self) -> dict[str, JsonValue]:
        """Serialize the immutable intent while preserving historical v1 bytes."""
        payload = self.model_dump(mode="json")
        if self.schema_version == "polisyos.runtime.observational_run_intent.v1":
            payload.pop("owned_hte_request_context", None)
        return payload


def _expected_observational_normalization(source_protocol: str) -> str:
    """Return the only source normalization allowed for an admitted protocol."""
    if source_protocol == "method_input_envelope_v1":
        return "canonical_passthrough"
    if source_protocol == "legacy_hte_json_v1":
        return "legacy_to_method_input_envelope_v1"
    raise ValueError("observational_source_protocol_invalid")


def _expected_observational_limitations(
    source_protocol: str,
    *,
    source_access_revalidation_status: str | None = None,
) -> tuple[_ObservationalRunLimitation, ...]:
    """Return immutable caveats, preserving old history and recording current access limits."""
    if source_protocol not in {"method_input_envelope_v1", "legacy_hte_json_v1"}:
        raise ValueError("observational_source_protocol_invalid")
    limitations: list[_ObservationalRunLimitation] = list(_OBSERVATIONAL_RUN_BASE_LIMITATIONS)
    if source_access_revalidation_status == "not_established":
        limitations.append("source_access_revalidation_not_established")
    elif source_access_revalidation_status is not None:
        raise ValueError("observational_source_access_status_invalid")
    return tuple(limitations)


def _expected_content_admitted_limitations(
    source_protocol: str,
    *,
    source_access_revalidation_status: str | None = None,
) -> tuple[_ContentAdmittedObservationalLimitation, ...]:
    """Return requested caveats plus producer-proven normalization caveats."""
    limitations: list[_ContentAdmittedObservationalLimitation] = list(
        _expected_observational_limitations(
            source_protocol,
            source_access_revalidation_status=source_access_revalidation_status,
        )
    )
    if source_protocol == "legacy_hte_json_v1":
        limitations.append("legacy_hte_json_v1_source_normalized")
    return tuple(limitations)


class SearchUncertaintyTaskAdmissionSnapshot(BaseModel):
    """Freeze the Search owner's recomputed binding admission before dispatch."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    binding_ref: ArtifactRef
    binding_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ticket_id: str = Field(min_length=1, max_length=128)
    ticket_generation: int = Field(ge=1, strict=True)
    owner_revision: int = Field(ge=1, strict=True)
    projection_revision: int = Field(ge=1, strict=True)
    projection_ref: ArtifactRef
    task_admission_ref: ArtifactRef
    task_epoch_ref: ArtifactRef
    owner_context_ref: ArtifactRef
    basis_ref: ArtifactRef
    dependency_inventory_ref: ArtifactRef
    dependency_inventory_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_projection_ref: ArtifactRef
    selected_method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    selected_method_abi_version: Literal["2.0.0"]
    selected_method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_method_params: dict[str, JsonValue]
    selected_method_params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_method_seed: int = Field(ge=0, le=4_294_967_295, strict=True)
    selected_inference_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    selected_method_input_ref: ArtifactRef
    selected_method_input_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tenant_id: str = Field(min_length=1, max_length=128)
    cell_id: str | None = Field(default=None, min_length=1, max_length=128)
    resolved_at: datetime
    resolution_status: Literal["current"] = "current"
    closure_status: Literal["recomputed"] = "recomputed"

    @model_validator(mode="after")
    def _require_recomputed_binding_identity(
        self,
    ) -> SearchUncertaintyTaskAdmissionSnapshot:
        """Bind the current Search proof to exact refs, owner values, and input bytes."""
        expected_refs = (
            (self.binding_ref, "scientist.search.uncertainty_task_binding"),
            (self.projection_ref, "scientist.search.uncertainty_ticket_projection"),
            (self.task_admission_ref, "scientist.search.uncertainty_task_admission"),
            (self.task_epoch_ref, "scientist.search.uncertainty_task_epoch"),
            (self.owner_context_ref, "scientist.search.uncertainty_owner_task_context"),
            (self.basis_ref, "scientist.search.uncertainty_basis"),
            (
                self.dependency_inventory_ref,
                "scientist.search.uncertainty_input_inventory",
            ),
            (
                self.source_projection_ref,
                "scientist.search.uncertainty_ticket_projection",
            ),
        )
        for ref, expected_kind in expected_refs:
            if (
                ref.kind != expected_kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("search_task_admission_snapshot_ref_invalid")
        if self.selected_method_input_ref.manifest_profile_sha256 is None:
            raise ValueError("search_task_admission_snapshot_input_profile_missing")
        if (
            self.binding_ref.artifact_id.hex != self.binding_content_sha256
            or self.selected_method_input_ref.artifact_id.hex
            != self.selected_method_input_content_sha256
        ):
            raise ValueError("search_task_admission_snapshot_content_digest_mismatch")
        params_bytes = json.dumps(
            self.selected_method_params,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if hashlib.sha256(params_bytes).hexdigest() != self.selected_method_params_sha256:
            raise ValueError("search_task_admission_snapshot_params_digest_mismatch")
        if self.resolved_at.tzinfo is None or self.resolved_at.utcoffset() is None:
            raise ValueError("search_task_admission_snapshot_resolution_time_must_be_aware")
        return self


ObservationalRunIntent.model_rebuild()


class ContentAdmittedObservationalRunIntent(BaseModel):
    """Bind worker-admitted bounded content to the prequeued method and source pins."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra=lambda schema: _append_expected_limitations_json_schema(
            schema,
            model=ContentAdmittedObservationalRunIntent,
            protocol_field="source_protocol",
            status_field="source_access_revalidation_status",
            limitations_field="limitations",
            expected_limitations=lambda protocol, status: _expected_content_admitted_limitations(
                protocol,
                source_access_revalidation_status=status,
            ),
        ),
    )

    schema_version: Literal[
        "polisyos.runtime.content_admitted_observational_run_intent.v1",
        "polisyos.runtime.content_admitted_observational_run_intent.v2",
        "polisyos.runtime.content_admitted_observational_run_intent.v3",
    ] = "polisyos.runtime.content_admitted_observational_run_intent.v1"
    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    attempt: int = Field(ge=1, strict=True)
    requested_intent_ref: ArtifactRef
    requested_source_ref: ArtifactRef
    source_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resource_policy_ref: ArtifactRef
    submitted_input_ref: ArtifactRef
    effective_input_ref: ArtifactRef
    contract_target_id: Literal["foundry.causal.hte_observational_data.v1"] | None = None
    contract_target: Literal[
        "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
    ]
    selection_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_access_revalidation_status: Literal["not_established"] | None = None
    method_fqn: Literal[
        "causal.hte.forest_dr@1.0.0",
        "causal.hte.forest_dr@1.1.0",
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    owned_hte_request_context: OwnedHTERequestContextV1 | None = None
    search_binding_admission: SearchUncertaintyTaskAdmissionSnapshot | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    search_binding_tenant_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        exclude_if=lambda value: value is None,
    )
    search_binding_cell_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        exclude_if=lambda value: value is None,
    )
    source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"]
    normalization: Literal[
        "canonical_passthrough",
        "legacy_to_method_input_envelope_v1",
    ]
    limitations: tuple[
        Literal[
            "candidate_input_not_external_truth",
            "scientific_validity_not_established",
            "units_and_context_not_established",
            "source_access_revalidation_not_established",
            "legacy_hte_json_v1_source_normalized",
        ],
        ...,
    ] = Field(min_length=3, max_length=5)
    source_governance: ArtifactGovernanceInfo
    source_tenant_context: ArtifactTenantContextInfo | None = None
    observed_manifest_bytes: int = Field(ge=0, strict=True)
    observed_manifest_selection_bytes: int = Field(ge=0, strict=True)
    observed_manifest_verification_bytes: int = Field(ge=0, strict=True)
    observed_payload_bytes: int = Field(ge=0, strict=True)
    observed_source_bytes: int = Field(ge=0, strict=True)
    payload_integrity_verified: Literal[True]
    observed_bytes: int = Field(ge=0, strict=True)
    observed_depth: int = Field(ge=0, strict=True)
    observed_elements: int = Field(ge=0, strict=True)
    resource_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    admitted_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def _require_selected_input_views(self) -> ContentAdmittedObservationalRunIntent:
        is_successor = self.method_fqn in _OBSERVATIONAL_HTE_SUCCESSOR_METHODS
        request_context = self.owned_hte_request_context
        search_binding_ref = (
            request_context.search_uncertainty_task_binding_ref
            if request_context is not None
            else None
        )
        if search_binding_ref is None:
            if any(
                value is not None
                for value in (
                    self.search_binding_admission,
                    self.search_binding_tenant_id,
                    self.search_binding_cell_id,
                )
            ):
                raise ValueError("content_admitted_search_snapshot_without_binding")
        elif (
            type(self.search_binding_admission) is not SearchUncertaintyTaskAdmissionSnapshot
            or artifact_ref_identity_key(self.search_binding_admission.binding_ref)
            != artifact_ref_identity_key(search_binding_ref)
            or self.search_binding_tenant_id is None
            or self.search_binding_admission.tenant_id != self.search_binding_tenant_id
            or self.search_binding_admission.cell_id != self.search_binding_cell_id
            or self.search_binding_admission.selected_method_fqn != self.method_fqn
            or self.search_binding_admission.selected_method_input_ref != self.effective_input_ref
        ):
            raise ValueError("content_admitted_search_snapshot_selection_mismatch")
        if (
            self.schema_version == "polisyos.runtime.content_admitted_observational_run_intent.v3"
            and (search_binding_ref is None or self.search_binding_admission is None)
        ):
            raise ValueError("content_admitted_search_snapshot_required_for_v3")
        if is_successor:
            if (
                self.schema_version
                not in {
                    "polisyos.runtime.content_admitted_observational_run_intent.v2",
                    "polisyos.runtime.content_admitted_observational_run_intent.v3",
                }
                or type(request_context) is not OwnedHTERequestContextV1
                or request_context.request_estimand_status != "declared"
                or request_context.request_target_scope_status != "declared"
                or request_context.outcome_variable_status != "declared"
                or request_context.treatment_variable_status != "declared"
                or request_context.contrast_status != "declared"
                or request_context.request_alpha_status != "declared"
                or request_context.requested_guarantee_status not in {"declared", "not_established"}
            ):
                raise ValueError("content_admitted_hte_successor_context_invalid")
        elif (
            self.schema_version != "polisyos.runtime.content_admitted_observational_run_intent.v1"
            or request_context is not None
            or self.search_binding_admission is not None
            or self.search_binding_tenant_id is not None
            or self.search_binding_cell_id is not None
        ):
            raise ValueError("content_admitted_legacy_context_must_be_absent")
        refs = (
            self.requested_intent_ref,
            self.requested_source_ref,
            self.resource_policy_ref,
            self.submitted_input_ref,
            self.effective_input_ref,
        )
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("content_admitted_observational_intent_profile_missing")
        expected_source_kind = (
            "ir.observation_method_input"
            if self.source_protocol == "method_input_envelope_v1"
            else "ir.observational_data"
        )
        if (
            self.requested_intent_ref.kind != "runtime.observational_run_intent"
            or self.requested_intent_ref.media_type != "application/json"
            or self.requested_source_ref.kind != expected_source_kind
            or self.requested_source_ref.media_type != "application/json"
            or self.resource_policy_ref.kind != "runtime.observational_input_resource_policy"
            or self.resource_policy_ref.media_type != "application/json"
            or self.submitted_input_ref != self.requested_source_ref
        ):
            raise ValueError("content_admitted_observational_submitted_source_mismatch")
        if (
            self.effective_input_ref.kind != "ir.observation_method_input"
            or self.effective_input_ref.media_type != "application/json"
        ):
            raise ValueError("content_admitted_observational_effective_input_invalid")
        if (
            self.contract_target_id is not None
            and self.contract_target_id != "foundry.causal.hte_observational_data.v1"
        ) or self.contract_target != (
            "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        ):
            raise ValueError("content_admitted_observational_target_invalid")
        if self.selection_digest is not None and len(self.selection_digest) != 64:
            raise ValueError("content_admitted_observational_selection_digest_invalid")
        if self.normalization != _expected_observational_normalization(self.source_protocol):
            raise ValueError("content_admitted_observational_protocol_normalization_mismatch")
        if self.limitations != _expected_content_admitted_limitations(
            self.source_protocol,
            source_access_revalidation_status=self.source_access_revalidation_status,
        ):
            raise ValueError("content_admitted_observational_limitations_invalid")
        if (
            self.observed_manifest_bytes != self.observed_manifest_selection_bytes
            or self.observed_source_bytes
            != self.observed_manifest_selection_bytes
            + self.observed_manifest_verification_bytes
            + self.observed_payload_bytes
            or self.observed_payload_bytes != self.observed_bytes
        ):
            raise ValueError("content_admitted_observational_read_usage_mismatch")
        if (
            self.source_protocol == "method_input_envelope_v1"
            and self.effective_input_ref != self.submitted_input_ref
        ):
            raise ValueError("content_admitted_observational_passthrough_mismatch")
        return self

    def artifact_payload(self) -> dict[str, JsonValue]:
        """Serialize the admitted intent while omitting successor fields from v1 bytes."""
        payload = self.model_dump(mode="json")
        if self.schema_version == "polisyos.runtime.content_admitted_observational_run_intent.v1":
            payload.pop("owned_hte_request_context", None)
        return payload


class CompletedExAnteCandidateSource(BaseModel):
    """Lookup keys for a completed candidate source, never an authority claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_run_id: str = Field(min_length=1, max_length=128, strict=True)
    candidate_ref: ArtifactRef

    @model_validator(mode="after")
    def _validate_source_selector(self) -> CompletedExAnteCandidateSource:
        if (
            self.candidate_ref.kind != "scientist.policy_design.candidate"
            or self.candidate_ref.media_type != "application/json"
            or self.candidate_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("completed_candidate_source_selected_ref_invalid")
        return self


class CompletedExAnteComparisonRequest(BaseModel):
    """An explicit bounded set of selected-source lookup keys."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sources: tuple[CompletedExAnteCandidateSource, ...] = Field(min_length=2, max_length=20)


class CompletedExAnteCandidateObservation(BaseModel):
    """One owner-recomputed candidate score; no feasibility claim is made."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: CompletedExAnteCandidateSource
    candidate_hash: str = Field(strict=True, pattern=r"^sha256:[0-9a-f]{64}$")
    minimized_score: float = Field(strict=True, allow_inf_nan=False)
    maximizing_coordinate: float = Field(strict=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def _validate_coordinate(self) -> CompletedExAnteCandidateObservation:
        if self.maximizing_coordinate != -self.minimized_score:
            raise ValueError("candidate_coordinate_does_not_match_score")
        return self


class CompletedExAnteCandidateRanking(BaseModel):
    """One candidate-only comparison at a scoped live owner read."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["complete", "verification_missing", "invalid"]
    authority_status: Literal["candidate_only"] = "candidate_only"
    revalidation_required: Literal[True] = True
    comparison_contract_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    observations: tuple[CompletedExAnteCandidateObservation, ...] = Field(default=(), max_length=20)
    frontier_candidate_hashes: tuple[str, ...] = Field(default=(), max_length=20)
    limitations: tuple[str, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def _validate_candidate_only_shape(self) -> CompletedExAnteCandidateRanking:
        if self.status == "complete":
            if (
                len(self.observations) < 2
                or not self.comparison_contract_sha256
                or not self.frontier_candidate_hashes
                or self.limitations
            ):
                raise ValueError("completed_candidate_rank_requires_recomputed_sources")
            ids = [item.candidate_hash for item in self.observations]
            if (
                len(ids) != len(set(ids))
                or len(self.frontier_candidate_hashes) != len(set(self.frontier_candidate_hashes))
                or not set(self.frontier_candidate_hashes) <= set(ids)
            ):
                raise ValueError("completed_candidate_rank_identity_mismatch")
        elif (
            self.comparison_contract_sha256 is not None
            or self.observations
            or self.frontier_candidate_hashes
            or not self.limitations
        ):
            raise ValueError("limited_candidate_rank_requires_reason_only")
        return self


class MethodMetricCandidateScore(BaseModel):
    """Current candidate-only score replayed from one completed Runtime source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["selected", "verification_missing", "invalid"]
    authority_status: Literal["candidate_only"] = "candidate_only"
    revalidation_required: Literal[True] = True
    candidate_ref: ArtifactRef | None = None
    source_vector_ref: ArtifactRef | None = None
    minimized_score: float | None = Field(default=None, strict=True, allow_inf_nan=False)
    maximizing_coordinate: float | None = Field(default=None, strict=True, allow_inf_nan=False)
    comparison_contract_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=32)

    @model_validator(mode="after")
    def _require_candidate_score_shape(self) -> MethodMetricCandidateScore:
        if self.status == "selected":
            if (
                self.candidate_ref is None
                or self.candidate_ref.kind != "scientist.policy_design.candidate"
                or self.candidate_ref.media_type != "application/json"
                or self.candidate_ref.manifest_profile_sha256 is None
                or self.source_vector_ref is None
                or self.source_vector_ref.kind != "scientist.policy_evaluation_vector"
                or self.source_vector_ref.media_type != "application/json"
                or self.source_vector_ref.manifest_profile_sha256 is None
                or self.minimized_score is None
                or not math.isfinite(self.minimized_score)
                or self.maximizing_coordinate != -self.minimized_score
                or not self.comparison_contract_sha256
                or self.limitations
            ):
                raise ValueError("selected_method_metric_candidate_score_requires_source")
        elif (
            self.candidate_ref is not None
            or self.source_vector_ref is not None
            or self.minimized_score is not None
            or self.maximizing_coordinate is not None
            or self.comparison_contract_sha256 is not None
            or not self.limitations
        ):
            raise ValueError("limited_method_metric_candidate_score_requires_reason_only")
        return self


class MethodMetricProjectionResponse(BaseModel):
    """Bounded API projection of owner-selected method metric rows."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: ApiMeta
    run_id: str = Field(min_length=1, max_length=128)
    status: Literal["selected", "verification_missing", "invalid"]
    vector_ref: ArtifactRef | None = None
    observations: tuple[JsonValue, ...] = Field(default_factory=tuple, max_length=8192)
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=32)
    candidate_score: MethodMetricCandidateScore | None = None

    @model_validator(mode="after")
    def _require_projection_shape(self) -> MethodMetricProjectionResponse:
        if self.vector_ref is not None and (
            self.vector_ref.kind != "scientist.policy_evaluation_vector"
            or self.vector_ref.media_type != "application/json"
            or self.vector_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("method_metric_projection_response_vector_invalid")
        if self.status == "selected":
            if self.vector_ref is None:
                raise ValueError("method_metric_projection_response_vector_required")
        elif self.vector_ref is not None or self.observations:
            raise ValueError("method_metric_projection_response_limited_shape_invalid")
        if (
            self.candidate_score is not None
            and self.candidate_score.status == "selected"
            and (
                self.status != "selected"
                or self.candidate_score.source_vector_ref != self.vector_ref
            )
        ):
            raise ValueError("candidate_score_requires_current_method_projection")
        return self


class CompletedExAnteCandidateComparisonResponse(BaseModel):
    """Fresh scoped comparison; absence means no comparison was requested."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    meta: ApiMeta
    run_id: str = Field(min_length=1, max_length=128)
    candidate_comparison: CompletedExAnteCandidateRanking | None = None


class MethodMetricProjectionSelection(BaseModel):
    """Identify an AD01 vector and the verifier implementation that admitted it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    vector_ref: ArtifactRef
    verifier_revision: str = Field(min_length=1, max_length=96)
    verifier_implementation_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _require_selected_vector(self) -> MethodMetricProjectionSelection:
        if (
            self.vector_ref.kind != "scientist.policy_evaluation_vector"
            or self.vector_ref.media_type != "application/json"
            or self.vector_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("method_metric_projection_vector_view_invalid")
        return self


class MethodExecutionCandidateOutcome(BaseModel):
    """Scalar-only candidate summary captured from the producer's typed report."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    method: Literal["forest_dr"] = "forest_dr"
    status: Literal["success", "input_invalid", "assumption_failed", "numerical_failure"]
    estimand: str = Field(min_length=1, max_length=256)
    point_estimate: float | None = None
    confidence_interval: tuple[float, float] | None = None
    confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    standard_error: float | None = Field(default=None, ge=0.0)
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    sample_size: int = Field(ge=0, strict=True)
    n_treated: int = Field(ge=0, strict=True)
    n_control: int = Field(ge=0, strict=True)
    candidate_only: Literal[True] = True
    limitations: tuple[
        Literal[
            "causal_identification_not_established",
            "scientific_validity_not_established",
        ],
        ...,
    ] = (
        "causal_identification_not_established",
        "scientific_validity_not_established",
    )

    @classmethod
    def from_json_payload(cls, payload: object) -> MethodExecutionCandidateOutcome:
        """Validate a bounded decoded JSON summary with strict wire semantics.

        The caller still owns selected-profile, integrity, provenance and read-limit
        admission. JSON arrays are valid wire values for the DTO's tuple fields;
        this does not relax strict Python validation or the candidate-only limits.

        Args:
            payload: The complete JSON mapping returned by a bounded reader.

        Returns:
            A new immutable candidate summary under the unchanged DTO contract.

        Raises:
            ValueError: If the value is not JSON wire data or violates the contract.
        """
        return _validate_strict_json_wire_payload(
            payload,
            TypeAdapter(cls),
            invalid_code="method_execution_candidate_outcome_wire_payload_invalid",
        )

    @model_validator(mode="after")
    def _require_candidate_report_shape(self) -> MethodExecutionCandidateOutcome:
        if self.status == "success" and (
            self.point_estimate is None or self.confidence_interval is None
        ):
            raise ValueError("method_execution_candidate_success_summary_incomplete")
        if self.confidence_interval is not None:
            low, high = self.confidence_interval
            if not math.isfinite(low) or not math.isfinite(high) or low > high:
                raise ValueError("method_execution_candidate_interval_invalid")
        if self.point_estimate is not None and not math.isfinite(self.point_estimate):
            raise ValueError("method_execution_candidate_estimate_non_finite")
        for name, value in (
            ("confidence_level", self.confidence_level),
            ("standard_error", self.standard_error),
            ("p_value", self.p_value),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"method_execution_candidate_{name}_non_finite")
        if self.n_treated + self.n_control > self.sample_size:
            raise ValueError("method_execution_candidate_counts_exceed_sample")
        if self.limitations != (
            "causal_identification_not_established",
            "scientific_validity_not_established",
        ):
            raise ValueError("method_execution_candidate_limitations_invalid")
        return self


class DirectMethodExecutionHTETargetRelation(BaseModel):
    """Bounded target relation copied from the validated HTE outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    requested_scope_status: Literal["declared", "not_established"]
    requested_scope: str | None = Field(default=None, min_length=1, max_length=256)
    requested_guarantee_status: Literal["declared", "not_established"]
    requested_guarantee: (
        Literal[
            "candidate_point",
            "backend_conditional_interval",
            "population_sampling_coverage",
        ]
        | None
    )
    computed_scope_status: Literal["recomputed", "not_established"]
    computed_scope: Literal["selected_evaluation_rows"] | None
    computed_guarantee_status: Literal["computed", "not_established"]
    computed_guarantee: Literal["candidate_point", "backend_conditional_interval"] | None
    source_content_status: Literal["content_bound", "not_established"]
    row_order_status: Literal["recomputed", "not_established"]
    contrast_status: Literal["recomputed", "not_established"]
    estimand_status: Literal["recomputed", "not_established"]
    alpha_status: Literal["recomputed", "not_applicable", "not_established"]
    profile_status: Literal["qualified", "point_only", "not_established"]
    scope_disposition: Literal["satisfied", "requested_claim_not_satisfied", "not_established"]
    guarantee_disposition: Literal["satisfied", "requested_claim_not_satisfied", "not_established"]
    overall_disposition: Literal["satisfied", "requested_claim_not_satisfied", "not_established"]

    @model_validator(mode="after")
    def _require_status_value_pairs(self) -> DirectMethodExecutionHTETargetRelation:
        if (self.requested_scope_status == "declared") != (self.requested_scope is not None):
            raise ValueError("direct_method_hte_requested_scope_status_mismatch")
        if (self.requested_guarantee_status == "declared") != (
            self.requested_guarantee is not None
        ):
            raise ValueError("direct_method_hte_requested_guarantee_status_mismatch")
        if (self.computed_scope_status == "recomputed") != (
            self.computed_scope == "selected_evaluation_rows"
        ):
            raise ValueError("direct_method_hte_computed_scope_status_mismatch")
        if (self.computed_guarantee_status == "computed") != (self.computed_guarantee is not None):
            raise ValueError("direct_method_hte_computed_guarantee_status_mismatch")
        if self.estimand_status != "not_established":
            raise ValueError("direct_method_hte_source_variable_identity_not_established")

        scope_evidence_ready = (
            self.computed_scope_status == "recomputed"
            and self.source_content_status == "content_bound"
            and self.row_order_status == "recomputed"
        )
        if (
            self.requested_scope_status == "declared"
            and self.computed_scope_status == "recomputed"
            and self.requested_scope == "population"
            and self.computed_scope == "selected_evaluation_rows"
        ):
            # This direct typed scope conflict is decisive even when unrelated
            # source-variable or row-identity joins remain unknown.
            expected_scope = "requested_claim_not_satisfied"
        elif self.requested_scope_status != "declared" or not scope_evidence_ready:
            expected_scope = "not_established"
        elif self.requested_scope == self.computed_scope:
            expected_scope = "satisfied"
        else:
            expected_scope = "not_established"

        guarantee_evidence_ready = (
            self.computed_guarantee_status == "computed"
            and self.alpha_status in {"recomputed", "not_applicable"}
            and self.profile_status in {"qualified", "point_only"}
        )
        if (
            self.requested_guarantee_status == "declared"
            and self.computed_guarantee_status == "computed"
            and self.requested_guarantee != self.computed_guarantee
        ):
            expected_guarantee = "requested_claim_not_satisfied"
        elif self.requested_guarantee_status != "declared" or not guarantee_evidence_ready:
            expected_guarantee = "not_established"
        elif self.requested_guarantee == self.computed_guarantee:
            expected_guarantee = "satisfied"
        else:
            expected_guarantee = "not_established"

        expected_overall = (
            "requested_claim_not_satisfied"
            if "requested_claim_not_satisfied" in {expected_scope, expected_guarantee}
            else "not_established"
            if (
                "not_established" in {expected_scope, expected_guarantee}
                or self.contrast_status != "recomputed"
                or self.estimand_status != "recomputed"
                or self.source_content_status != "content_bound"
                or self.row_order_status != "recomputed"
            )
            else "satisfied"
        )
        if (
            self.scope_disposition != expected_scope
            or self.guarantee_disposition != expected_guarantee
            or self.overall_disposition != expected_overall
        ):
            raise ValueError("direct_method_hte_target_relation_disposition_mismatch")
        return self


class DirectMethodExecutionHTEResourceEvidence(BaseModel):
    """Bounded owner-policy and method-specific execution evidence for one HTE result."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    owner_policy_ref: ArtifactRef
    owner_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    owner_policy_schema_version: Literal[
        "polisyos.runtime.observational_input_resource_policy.v4",
        "polisyos.runtime.observational_input_resource_policy.v5",
    ]
    owner_policy_revision: Literal["r4", "r5"]
    owner_policy_method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    owner_policy_method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    owner_policy_execution_scope: Literal[
        "estimator_n_jobs_one",
        "producer_scoped_joblib_parallelism_one",
    ]
    owner_policy_max_jobs: Literal[1]
    owner_policy_required_estimator_n_jobs: Literal[1] | None
    owner_policy_manifest_schema_version: Literal["1.0"] = "1.0"
    execution_status: Literal["not_started", "returned", "raised"]
    estimator_observation_status: Literal["recomputed", "not_applicable", "not_established"]
    estimator_before_class_fqn: str | None = Field(default=None, min_length=1, max_length=256)
    estimator_before_n_jobs: int | None = Field(default=None, strict=True)
    estimator_before_params_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    estimator_after_class_fqn: str | None = Field(default=None, min_length=1, max_length=256)
    estimator_after_n_jobs: int | None = Field(default=None, strict=True)
    estimator_after_params_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    joblib_observation_status: Literal["recomputed", "not_applicable", "not_established"]
    joblib_profile_id: Literal["joblib.parallel_config.current_thread@1.0"] | None
    joblib_profile_revision: Literal["1.0"] | None
    joblib_implementation: Literal["joblib.parallel_config"] | None
    joblib_implementation_version: str | None = Field(default=None, min_length=1, max_length=96)
    joblib_scope: Literal["current_thread_joblib"] | None
    joblib_max_jobs: Literal[1] | None
    joblib_started: bool = False
    joblib_finished: bool = False
    joblib_exit_status: Literal["not_started", "returned", "raised"] = "not_started"
    joblib_entry_effective_jobs: int | None = Field(default=None, strict=True)
    joblib_entry_backend_fqn: str | None = Field(default=None, min_length=1, max_length=256)
    joblib_entry_config_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    joblib_entry_implementation_version: str | None = Field(
        default=None, min_length=1, max_length=96
    )
    joblib_exit_effective_jobs: int | None = Field(default=None, strict=True)
    joblib_exit_backend_fqn: str | None = Field(default=None, min_length=1, max_length=256)
    joblib_exit_config_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    joblib_exit_implementation_version: str | None = Field(
        default=None, min_length=1, max_length=96
    )
    physical_thread_limit_status: Literal["not_established"] = "not_established"
    physical_thread_limit: None = None

    @model_validator(mode="after")
    def _require_coherent_resource_evidence(
        self,
    ) -> DirectMethodExecutionHTEResourceEvidence:
        historical_method_profile = {
            "causal.hte.causal_forest@2.0.0": (
                "econml.causal_forest_dml.native_mean@2.0",
                "estimator_n_jobs_one",
                1,
            ),
            "causal.hte.double_ml@2.0.0": (
                "econml.dml.point_only@2.0",
                "producer_scoped_joblib_parallelism_one",
                None,
            ),
            "causal.hte.meta_learner@2.0.0": (
                "econml.meta_learner.point_only@2.0",
                "producer_scoped_joblib_parallelism_one",
                None,
            ),
            "causal.hte.forest_dr@2.0.0": (
                "econml.forest_dr.native_mean@2.0",
                "estimator_n_jobs_one",
                1,
            ),
        }
        method_profile = {
            "causal.hte.causal_forest@2.0.0": (
                "econml.causal_forest_dml.native_mean@2.0",
                1,
            ),
            "causal.hte.double_ml@2.0.0": (
                "econml.dml.point_only@2.0",
                None,
            ),
            "causal.hte.meta_learner@2.0.0": (
                "econml.meta_learner.point_only@2.0",
                None,
            ),
            "causal.hte.forest_dr@2.0.0": (
                "econml.forest_dr.native_mean@2.0",
                1,
            ),
        }
        if (
            self.owner_policy_ref.kind != "runtime.observational_input_resource_policy"
            or self.owner_policy_ref.media_type != "application/json"
            or self.owner_policy_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("direct_method_hte_resource_policy_ref_invalid")
        expected = method_profile[self.owner_policy_method_fqn]
        if self.owner_policy_max_jobs != 1:
            raise ValueError("direct_method_hte_resource_policy_method_tuple_invalid")
        if self.owner_policy_revision == "r4":
            historical_expected = historical_method_profile[self.owner_policy_method_fqn]
            if (
                self.owner_policy_schema_version
                != "polisyos.runtime.observational_input_resource_policy.v4"
                or self.owner_policy_method_profile_id != historical_expected[0]
                or self.owner_policy_execution_scope != historical_expected[1]
                or self.owner_policy_required_estimator_n_jobs != historical_expected[2]
            ):
                raise ValueError("direct_method_hte_resource_policy_method_tuple_invalid")
        elif (
            self.owner_policy_schema_version
            != "polisyos.runtime.observational_input_resource_policy.v5"
            or self.owner_policy_method_profile_id != expected[0]
            or self.owner_policy_execution_scope != "producer_scoped_joblib_parallelism_one"
            or self.owner_policy_required_estimator_n_jobs != expected[1]
        ):
            raise ValueError("direct_method_hte_resource_policy_method_tuple_invalid")
        estimator_before = (
            self.estimator_before_class_fqn,
            self.estimator_before_n_jobs,
            self.estimator_before_params_sha256,
        )
        estimator_after = (
            self.estimator_after_class_fqn,
            self.estimator_after_n_jobs,
            self.estimator_after_params_sha256,
        )
        joblib_entry = (
            self.joblib_profile_id,
            self.joblib_profile_revision,
            self.joblib_implementation,
            self.joblib_scope,
            self.joblib_max_jobs,
            self.joblib_entry_effective_jobs,
            self.joblib_entry_backend_fqn,
            self.joblib_entry_config_sha256,
            self.joblib_entry_implementation_version,
        )
        joblib_exit = (
            self.joblib_exit_effective_jobs,
            self.joblib_exit_backend_fqn,
            self.joblib_exit_config_sha256,
            self.joblib_exit_implementation_version,
        )
        if self.owner_policy_revision == "r4" and any(
            value is not None and value < 1
            for value in (
                self.joblib_entry_effective_jobs,
                self.joblib_exit_effective_jobs,
            )
        ):
            raise ValueError("direct_method_hte_joblib_execution_observation_invalid")
        estimator_required = self.owner_policy_required_estimator_n_jobs == 1
        estimator_observed = estimator_before + estimator_after
        if self.owner_policy_revision == "r5":
            if estimator_required:
                if self.estimator_observation_status == "recomputed":
                    if any(item is None for item in estimator_observed):
                        raise ValueError("direct_method_hte_estimator_observation_incomplete")
                elif self.estimator_observation_status != "not_established":
                    raise ValueError("direct_method_hte_estimator_observation_status_invalid")
            elif self.estimator_observation_status != "not_applicable" or any(
                item is not None for item in estimator_observed
            ):
                raise ValueError("direct_method_hte_joblib_estimator_observation_present")

            joblib_required = (
                self.owner_policy_execution_scope == "producer_scoped_joblib_parallelism_one"
            )
            if not joblib_required:
                if (
                    self.joblib_observation_status != "not_applicable"
                    or self.joblib_started
                    or self.joblib_finished
                    or self.joblib_exit_status != "not_started"
                    or any(item is not None for item in joblib_entry + joblib_exit)
                ):
                    raise ValueError("direct_method_hte_estimator_joblib_observation_invalid")
            elif self.execution_status == "not_started":
                if (
                    self.joblib_observation_status != "not_established"
                    or self.joblib_started
                    or self.joblib_finished
                    or self.joblib_exit_status != "not_started"
                    or any(item is not None for item in joblib_entry + joblib_exit)
                ):
                    raise ValueError("direct_method_hte_unstarted_joblib_observation_invalid")
            elif self.joblib_observation_status == "recomputed":
                if (
                    not self.joblib_started
                    or not self.joblib_finished
                    or self.joblib_exit_status != self.execution_status
                    or any(item is None for item in joblib_entry + joblib_exit)
                    or self.joblib_profile_id != "joblib.parallel_config.current_thread@1.0"
                    or self.joblib_profile_revision != "1.0"
                    or self.joblib_implementation != "joblib.parallel_config"
                    or self.joblib_scope != "current_thread_joblib"
                    or self.joblib_max_jobs != 1
                ):
                    raise ValueError("direct_method_hte_joblib_execution_observation_invalid")
            elif self.joblib_observation_status == "not_established":
                if not self.joblib_started and (
                    self.joblib_finished
                    or self.joblib_exit_status != "not_started"
                    or any(item is not None for item in joblib_entry + joblib_exit)
                ):
                    raise ValueError("direct_method_hte_joblib_observation_status_invalid")
                if self.joblib_finished == (self.joblib_exit_status == "not_started"):
                    raise ValueError("direct_method_hte_joblib_exit_observation_invalid")
            else:
                raise ValueError("direct_method_hte_joblib_observation_status_invalid")
            return self

        if estimator_required:
            if self.execution_status == "returned":
                complete_bounded_observation = (
                    self.estimator_observation_status == "recomputed"
                    and all(item is not None for item in estimator_observed)
                    and self.estimator_before_n_jobs == 1
                    and self.estimator_after_n_jobs == 1
                    and self.estimator_before_class_fqn == self.estimator_after_class_fqn
                    and self.estimator_before_params_sha256 == self.estimator_after_params_sha256
                )
                returned_refusal_unavailable_observation = (
                    self.estimator_observation_status == "not_established"
                    and all(item is None for item in estimator_observed)
                    and self.joblib_observation_status == "recomputed"
                    and self.joblib_started
                )
                if not (complete_bounded_observation or returned_refusal_unavailable_observation):
                    raise ValueError("direct_method_hte_returned_estimator_resource_invalid")
            elif self.execution_status == "not_started":
                if self.estimator_observation_status != "not_established" or any(
                    item is not None for item in estimator_observed
                ):
                    raise ValueError("direct_method_hte_unstarted_estimator_observation_invalid")
            elif self.estimator_observation_status == "recomputed":
                # Raised executions preserve measurements and drift; they cannot
                # qualify as completed bounded execution.
                if any(item is None for item in estimator_observed):
                    raise ValueError("direct_method_hte_raised_estimator_resource_invalid")
            elif self.estimator_observation_status != "not_established" or any(
                item is not None for item in estimator_observed
            ):
                raise ValueError("direct_method_hte_raised_estimator_observation_invalid")
        elif self.estimator_observation_status != "not_applicable" or any(
            item is not None for item in estimator_observed
        ):
            raise ValueError("direct_method_hte_joblib_estimator_observation_present")

        joblib_required = (
            self.owner_policy_execution_scope == "producer_scoped_joblib_parallelism_one"
        )
        if not joblib_required:
            if (
                self.joblib_observation_status != "not_applicable"
                or self.joblib_started
                or self.joblib_finished
                or self.joblib_exit_status != "not_started"
                or any(item is not None for item in joblib_entry + joblib_exit)
            ):
                raise ValueError("direct_method_hte_estimator_joblib_observation_invalid")
        elif self.execution_status == "not_started":
            if (
                self.joblib_observation_status != "not_established"
                or self.joblib_started
                or self.joblib_finished
                or self.joblib_exit_status != "not_started"
                or any(item is not None for item in joblib_entry + joblib_exit)
            ):
                raise ValueError("direct_method_hte_unstarted_joblib_observation_invalid")
        else:
            expected_exit = self.execution_status
            if (
                self.joblib_observation_status != "recomputed"
                or not self.joblib_started
                or not self.joblib_finished
                or self.joblib_exit_status != expected_exit
                or any(item is None for item in joblib_entry + joblib_exit)
                or self.joblib_profile_id != "joblib.parallel_config.current_thread@1.0"
                or self.joblib_profile_revision != "1.0"
                or self.joblib_implementation != "joblib.parallel_config"
                or self.joblib_scope != "current_thread_joblib"
                or self.joblib_max_jobs != 1
                or (
                    self.execution_status == "returned"
                    and (
                        self.joblib_entry_effective_jobs != 1
                        or self.joblib_exit_effective_jobs != 1
                        or self.joblib_implementation_version
                        != self.joblib_entry_implementation_version
                        or self.joblib_entry_backend_fqn != self.joblib_exit_backend_fqn
                        or self.joblib_entry_config_sha256 != self.joblib_exit_config_sha256
                        or self.joblib_entry_implementation_version
                        != self.joblib_exit_implementation_version
                    )
                )
            ):
                raise ValueError("direct_method_hte_joblib_execution_observation_invalid")
        return self


class DirectMethodExecutionHTESummary(BaseModel):
    """Scalar-only projection copied from a validated persisted HTE outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    kind: Literal["point_estimate", "interval_estimate", "refusal"]
    method_fqn: Literal[
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_profile_id: Literal[
        "econml.causal_forest_dml.native_mean@2.0",
        "econml.dml.point_only@2.0",
        "econml.meta_learner.point_only@2.0",
        "econml.forest_dr.native_mean@2.0",
    ]
    resolved_params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    owned_attempt_anchor_ref: OwnedAttemptAnchorRef
    hte_outcome_ref: ArtifactRef
    point_result_ref: ArtifactRef | None = None
    hte_result_ref: ArtifactRef | None = None
    inference_basis_ref: ArtifactRef | None = None
    refusal_diagnostic_ref: ArtifactRef | None = None
    search_uncertainty_task_binding_ref: ArtifactRef | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    materialization_binding_ref: ArtifactRef | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    method_result_ref: ArtifactRef
    method_evidence_ref: ArtifactRef
    source_data_ref: ArtifactRef | None = None
    selected_rows_status: Literal["recomputed", "not_established"]
    n_selected_rows: int | None = Field(default=None, ge=1, strict=True)
    selected_rows_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_row_order_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_x_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    computed_estimand_status: Literal["recomputed", "not_established"]
    computed_estimand: Literal["mean_effect_over_selected_x"] | None = None
    computed_target_scope_status: Literal["recomputed", "not_established"]
    computed_target_scope: Literal["selected_evaluation_rows"] | None = None
    measure_unit_status: Literal["established", "not_established"]
    measure_unit: str | None = Field(default=None, min_length=1, max_length=128)
    request_estimand_status: Literal["declared", "not_established"]
    request_estimand: str | None = Field(default=None, min_length=1, max_length=256)
    request_target_scope_status: Literal["declared", "not_established"]
    request_target_scope: str | None = Field(default=None, min_length=1, max_length=256)
    outcome_variable_status: Literal["declared", "not_established"]
    outcome_variable_id: str | None = Field(default=None, min_length=1, max_length=256)
    treatment_variable_status: Literal["declared", "not_established"]
    treatment_variable_id: str | None = Field(default=None, min_length=1, max_length=256)
    request_contrast_status: Literal["declared", "not_established"]
    control_value: float | None = None
    treated_value: float | None = None
    request_alpha_status: Literal["declared", "not_established"]
    requested_alpha: float | None = Field(default=None, gt=0.0, lt=1.0)
    requested_guarantee_status: Literal["declared", "not_established"]
    requested_guarantee: (
        Literal[
            "candidate_point",
            "backend_conditional_interval",
            "population_sampling_coverage",
        ]
        | None
    )
    computed_guarantee_status: Literal["computed", "not_established"]
    computed_guarantee: Literal["candidate_point", "backend_conditional_interval"] | None
    target_relation: DirectMethodExecutionHTETargetRelation
    inference_status: (
        Literal[
            "not_requested",
            "unavailable",
            "unsupported",
            "not_qualified",
            "failed",
            "native_ate_inference_validated",
        ]
        | None
    )
    inference_reason: (
        Literal[
            "inference_not_requested",
            "native_inference_unavailable",
            "native_inference_invalid",
            "method_profile_not_qualified",
            "selection_uses_outcomes",
            "contrast_not_established",
            "request_alpha_not_established",
        ]
        | None
    )
    point_estimate: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    confidence_level: float | None = Field(default=None, gt=0.0, lt=1.0)
    refusal_stage: Literal["prepare", "fit", "infer", "origin_verification"] | None = None
    refusal_reason: (
        Literal[
            "invalid_point_estimate",
            "method_execution_failed",
            "required_input_unavailable",
            "invalid_selected_input",
            "method_profile_unavailable",
            "runtime_origin_not_verified",
        ]
        | None
    )
    refusal_diagnostic_code: (
        Literal[
            "hte_input_invalid",
            "empty_selected_input",
            "econml_unavailable",
            "joblib_unavailable",
            "resource_profile_invalid",
            "dml_profile_invalid",
            "meta_profile_invalid",
            "hte_execution_failed",
            "hte_fit_failed",
            "hte_point_estimate_invalid",
            "contrast_not_established",
            "runtime_origin_not_verified",
        ]
        | None
    )
    resource_evidence: DirectMethodExecutionHTEResourceEvidence
    limitations: tuple[str, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def _require_scalar_summary_shape(self) -> DirectMethodExecutionHTESummary:
        ref_specs = (
            (self.hte_outcome_ref, "ir.hte_outcome"),
            (self.method_result_ref, "scientist.method_result.causal.hte"),
            (self.method_evidence_ref, "scientist.method_evidence"),
        )
        for ref, expected_kind in ref_specs:
            if (
                ref.kind != expected_kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("direct_method_hte_summary_required_ref_invalid")
        for ref, expected_kind in (
            (self.point_result_ref, "ir.hte_point_result"),
            (self.hte_result_ref, "ir.hte_result"),
            (self.inference_basis_ref, "ir.ate_inference_basis"),
            (self.refusal_diagnostic_ref, "ir.hte_refusal_diagnostic"),
        ):
            if ref is not None and (
                ref.kind != expected_kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("direct_method_hte_summary_optional_ref_invalid")
        if self.search_uncertainty_task_binding_ref is not None and (
            self.search_uncertainty_task_binding_ref.kind
            != "scientist.search.uncertainty_task_binding"
            or self.search_uncertainty_task_binding_ref.media_type != "application/json"
            or self.search_uncertainty_task_binding_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("direct_method_hte_summary_search_binding_ref_invalid")
        if self.materialization_binding_ref is not None and (
            self.materialization_binding_ref.kind
            != "foundry.hte.physical_source_materialization_binding"
            or self.materialization_binding_ref.media_type != "application/json"
            or self.materialization_binding_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("direct_method_hte_summary_materialization_binding_ref_invalid")
        if (
            self.resource_evidence.owner_policy_revision == "r5"
            and self.materialization_binding_ref is None
        ):
            raise ValueError("direct_method_hte_r5_materialization_binding_required")
        if self.hte_result_ref is not None and (
            self.point_result_ref is not None or self.inference_basis_ref is None
        ):
            raise ValueError("direct_method_hte_summary_interval_refs_incomplete")
        if self.inference_basis_ref is not None and (
            self.point_result_ref is None and self.hte_result_ref is None
        ):
            raise ValueError("direct_method_hte_summary_basis_without_result")
        if (
            self.source_data_ref is not None
            and self.source_data_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("direct_method_hte_summary_source_profile_missing")
        if self.source_data_ref is None:
            raise ValueError("direct_method_hte_summary_source_ref_missing")
        requested_pairs = (
            (self.request_estimand_status == "declared", self.request_estimand),
            (self.request_target_scope_status == "declared", self.request_target_scope),
            (self.outcome_variable_status == "declared", self.outcome_variable_id),
            (self.treatment_variable_status == "declared", self.treatment_variable_id),
            (self.request_contrast_status == "declared", self.control_value),
            (self.request_contrast_status == "declared", self.treated_value),
            (self.request_alpha_status == "declared", self.requested_alpha),
            (self.requested_guarantee_status == "declared", self.requested_guarantee),
            (
                self.computed_target_scope_status == "recomputed",
                self.computed_target_scope,
            ),
            (self.computed_estimand_status == "recomputed", self.computed_estimand),
            (self.computed_guarantee_status == "computed", self.computed_guarantee),
            (self.selected_rows_status == "recomputed", self.n_selected_rows),
            (self.selected_rows_status == "recomputed", self.selected_rows_sha256),
            (self.selected_rows_status == "recomputed", self.selected_row_order_sha256),
            (self.selected_rows_status == "recomputed", self.selected_x_sha256),
            (self.measure_unit_status == "established", self.measure_unit),
        )
        if any((status is True) != (value is not None) for status, value in requested_pairs):
            raise ValueError("direct_method_hte_summary_status_value_mismatch")
        for name, value in (
            ("point_estimate", self.point_estimate),
            ("lower_bound", self.lower_bound),
            ("upper_bound", self.upper_bound),
            ("confidence_level", self.confidence_level),
            ("control_value", self.control_value),
            ("treated_value", self.treated_value),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"direct_method_hte_summary_{name}_non_finite")
        if self.kind == "point_estimate":
            if (
                self.point_estimate is None
                or self.lower_bound is not None
                or self.upper_bound is not None
                or self.confidence_level is not None
                or self.point_result_ref is None
                or self.hte_result_ref is not None
                or self.computed_guarantee != "candidate_point"
                or self.computed_estimand_status != "recomputed"
                or self.computed_estimand != "mean_effect_over_selected_x"
                or self.computed_target_scope_status != "recomputed"
                or self.computed_target_scope != "selected_evaluation_rows"
                or self.selected_rows_status != "recomputed"
                or self.source_data_ref is None
                or self.inference_status
                not in {
                    "not_requested",
                    "unavailable",
                    "unsupported",
                    "not_qualified",
                    "failed",
                }
                or self.inference_reason is None
                or self.refusal_diagnostic_ref is not None
            ):
                raise ValueError("direct_method_hte_point_summary_invalid")
            if self.inference_basis_ref is not None and (
                self.inference_status != "failed"
                or self.inference_reason != "native_inference_invalid"
            ):
                raise ValueError("direct_method_hte_point_basis_disposition_invalid")
        elif self.kind == "interval_estimate":
            if (
                self.point_estimate is None
                or self.lower_bound is None
                or self.upper_bound is None
                or self.confidence_level is None
                or self.point_result_ref is not None
                or self.hte_result_ref is None
                or self.inference_basis_ref is None
                or self.method_profile_id
                not in {
                    "econml.causal_forest_dml.native_mean@2.0",
                    "econml.forest_dr.native_mean@2.0",
                }
                or self.computed_guarantee != "backend_conditional_interval"
                or self.computed_estimand_status != "recomputed"
                or self.computed_estimand != "mean_effect_over_selected_x"
                or self.computed_target_scope_status != "recomputed"
                or self.computed_target_scope != "selected_evaluation_rows"
                or self.selected_rows_status != "recomputed"
                or self.source_data_ref is None
                or self.inference_status != "native_ate_inference_validated"
                or self.inference_reason is not None
                or self.requested_alpha is None
                or self.refusal_diagnostic_ref is not None
                or self.target_relation.profile_status != "qualified"
                or self.target_relation.alpha_status != "recomputed"
                or not math.isclose(
                    1.0 - self.confidence_level,
                    self.requested_alpha,
                    rel_tol=0.0,
                    abs_tol=1.0e-12,
                )
            ):
                raise ValueError("direct_method_hte_interval_summary_invalid")
        elif any(
            value is not None
            for value in (
                self.point_estimate,
                self.lower_bound,
                self.upper_bound,
                self.confidence_level,
                self.point_result_ref,
                self.hte_result_ref,
                self.inference_basis_ref,
                self.inference_status,
                self.inference_reason,
            )
        ):
            raise ValueError("direct_method_hte_refusal_carries_numeric_estimate")
        if self.kind == "refusal" and (
            self.computed_estimand_status != "not_established"
            or self.computed_target_scope_status != "not_established"
            or self.computed_guarantee_status != "not_established"
            or self.selected_rows_status != "not_established"
            or self.refusal_diagnostic_ref is None
            or self.target_relation.overall_disposition != "not_established"
        ):
            raise ValueError("direct_method_hte_refusal_claims_computed_quantity")
        if self.kind == "refusal":
            if (
                self.refusal_stage is None
                or self.refusal_reason is None
                or self.refusal_diagnostic_code is None
                or self.refusal_diagnostic_ref is None
            ):
                raise ValueError("direct_method_hte_refusal_detail_missing")
        elif any(
            value is not None
            for value in (
                self.refusal_stage,
                self.refusal_reason,
                self.refusal_diagnostic_code,
            )
        ):
            raise ValueError("direct_method_hte_success_carries_refusal_details")
        if (
            self.kind == "interval_estimate"
            and self.lower_bound is not None
            and (self.upper_bound is None or self.lower_bound > self.upper_bound)
        ):
            raise ValueError("direct_method_hte_interval_order_invalid")
        if self.kind == "refusal" and any(
            ref is not None
            for ref in (
                self.point_result_ref,
                self.hte_result_ref,
                self.inference_basis_ref,
            )
        ):
            raise ValueError("direct_method_hte_refusal_carries_result_refs")
        if self.kind != "refusal" and self.resource_evidence.execution_status != "returned":
            raise ValueError("direct_method_hte_numeric_result_without_returned_resource")
        if self.kind != "refusal" and self.resource_evidence.owner_policy_revision == "r5":
            evidence = self.resource_evidence
            expected_estimator_status = (
                "recomputed"
                if evidence.owner_policy_required_estimator_n_jobs == 1
                else "not_applicable"
            )
            if (
                evidence.estimator_observation_status != expected_estimator_status
                or evidence.joblib_observation_status != "recomputed"
            ):
                raise ValueError("direct_method_hte_numeric_resource_observation_not_established")
            if evidence.owner_policy_required_estimator_n_jobs == 1 and (
                evidence.estimator_before_n_jobs != 1
                or evidence.estimator_after_n_jobs != 1
                or evidence.estimator_before_class_fqn != evidence.estimator_after_class_fqn
                or evidence.estimator_before_params_sha256 != evidence.estimator_after_params_sha256
            ):
                raise ValueError("direct_method_hte_numeric_estimator_policy_not_qualified")
            if (
                evidence.joblib_exit_status != "returned"
                or evidence.joblib_entry_effective_jobs != 1
                or evidence.joblib_exit_effective_jobs != 1
                or evidence.joblib_entry_backend_fqn != evidence.joblib_exit_backend_fqn
                or evidence.joblib_entry_config_sha256 != evidence.joblib_exit_config_sha256
                or evidence.joblib_entry_implementation_version
                != evidence.joblib_exit_implementation_version
                or evidence.joblib_implementation_version
                != evidence.joblib_entry_implementation_version
            ):
                raise ValueError("direct_method_hte_numeric_joblib_policy_not_qualified")
        if self.target_relation.requested_scope_status != self.request_target_scope_status or (
            self.target_relation.requested_scope != self.request_target_scope
            or self.target_relation.requested_guarantee_status != self.requested_guarantee_status
            or self.target_relation.requested_guarantee != self.requested_guarantee
            or self.target_relation.computed_scope_status != self.computed_target_scope_status
            or self.target_relation.computed_scope != self.computed_target_scope
            or self.target_relation.computed_guarantee_status != self.computed_guarantee_status
            or self.target_relation.computed_guarantee != self.computed_guarantee
        ):
            raise ValueError("direct_method_hte_summary_target_relation_mismatch")
        if self.resource_evidence.owner_policy_method_fqn != self.method_fqn or (
            self.resource_evidence.owner_policy_method_profile_id != self.method_profile_id
            or self.resource_evidence.owner_policy_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("direct_method_hte_summary_resource_identity_mismatch")
        if (
            self.method_profile_id
            in {
                "econml.dml.point_only@2.0",
                "econml.meta_learner.point_only@2.0",
            }
            and self.kind == "point_estimate"
            and self.target_relation.profile_status != "point_only"
        ):
            raise ValueError("direct_method_hte_point_only_profile_relation_invalid")
        return self


@dataclass(frozen=True, slots=True)
class CompletedMethodHTESource:
    """Owner-resolved HTE summary bound to one completed Runtime event.

    The selected summary is the worker-admitted projection. Its accompanying
    association binds that summary to the exact completed owner event and
    profiled artifact manifests; it does not grant publication or causal
    authority.
    """

    source_run_id: str
    source_job_id: str
    source_attempt: int
    completed_event_id: int
    completed_event_payload_sha256: str
    summary: DirectMethodExecutionHTESummary
    association: OwnedAttemptAnchorProjectionAssociation


class RuntimeSearchHTECompletionDeliveryV1(BaseModel):
    """Bind one Search receiver delivery to an immutable Runtime completion event.

    The durable outbox envelope is a retry key, not an assessment or authority
    record. Search must resolve the exact completed event through Runtime and
    content-verify its selected HTE artifacts before advancing its own owner CAS.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["1.0"] = "1.0"
    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    attempt: int = Field(ge=1, strict=True)
    completed_event_id: int = Field(ge=1, strict=True)
    completed_event_payload_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    search_uncertainty_task_binding_ref: ArtifactRef

    @model_validator(mode="after")
    def _require_profiled_search_binding(self) -> RuntimeSearchHTECompletionDeliveryV1:
        """Require the exact profile-qualified Search binding selected by Runtime."""
        ref = self.search_uncertainty_task_binding_ref
        if (
            ref.kind != "scientist.search.uncertainty_task_binding"
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
        ):
            raise ValueError("runtime_search_hte_completion_binding_ref_invalid")
        return self


class DirectMethodExecutionSelection(BaseModel):
    """Persist the immutable input, runtime pins, and outputs of direct method work."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selection_kind: Literal["direct_method"] = "direct_method"
    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    attempt: int = Field(ge=1, strict=True)
    requested_source_ref: ArtifactRef
    observational_run_intent_ref: ArtifactRef
    content_admitted_intent_ref: ArtifactRef
    resource_policy_ref: ArtifactRef
    submitted_input_ref: ArtifactRef
    effective_input_ref: ArtifactRef
    method_result_ref: ArtifactRef
    method_evidence_ref: ArtifactRef
    owned_attempt_anchor_ref: OwnedAttemptAnchorRef | None = None
    hte_outcome_ref: ArtifactRef | None = None
    point_result_ref: ArtifactRef | None = None
    hte_result_ref: ArtifactRef | None = None
    inference_basis_ref: ArtifactRef | None = None
    refusal_diagnostic_ref: ArtifactRef | None = None
    invocation_basis_ref: ArtifactRef | None = None
    hte: DirectMethodExecutionHTESummary | None = None
    contract_target_id: Literal["foundry.causal.hte_observational_data.v1"] | None = None
    contract_target: Literal[
        "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
    ]
    selection_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_access_revalidation_status: Literal["not_established"] | None = None
    method_fqn: Literal[
        "causal.hte.forest_dr@1.0.0",
        "causal.hte.forest_dr@1.1.0",
        "causal.hte.causal_forest@2.0.0",
        "causal.hte.double_ml@2.0.0",
        "causal.hte.meta_learner@2.0.0",
        "causal.hte.forest_dr@2.0.0",
    ]
    method_version: Literal["1.0.0", "1.1.0", "2.0.0"]
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_build_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_build_digest_scope: Literal["class_source_only"]
    resource_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"]
    normalization: Literal[
        "canonical_passthrough",
        "legacy_to_method_input_envelope_v1",
    ]
    limitations: tuple[
        Literal[
            "candidate_input_not_external_truth",
            "scientific_validity_not_established",
            "units_and_context_not_established",
            "source_access_revalidation_not_established",
            "legacy_hte_json_v1_source_normalized",
        ],
        ...,
    ]
    method_dispatch_binding_status: Literal["recomputed", "not_established"]
    owned_hte_request_context: OwnedHTERequestContextV1 | None = None
    candidate_outcome: MethodExecutionCandidateOutcome | None = None
    posterior_summary_refs: tuple[MethodExecutionPosteriorSummaryRef, ...] = Field(default=())

    @model_validator(mode="after")
    def _require_selected_views(self) -> DirectMethodExecutionSelection:
        is_successor = self.method_fqn in _OBSERVATIONAL_HTE_SUCCESSOR_METHODS
        if is_successor:
            context = self.owned_hte_request_context
            if (
                self.method_version != "2.0.0"
                or type(context) is not OwnedHTERequestContextV1
                or context.request_estimand_status != "declared"
                or context.request_target_scope_status != "declared"
                or context.outcome_variable_status != "declared"
                or context.treatment_variable_status != "declared"
                or context.contrast_status != "declared"
                or context.request_alpha_status != "declared"
                or context.requested_guarantee_status not in {"declared", "not_established"}
                or self.owned_attempt_anchor_ref is None
                or self.hte_outcome_ref is None
                or self.candidate_outcome is not None
                or self.hte is None
                or self.invocation_basis_ref is not None
            ):
                raise ValueError("direct_method_execution_hte_successor_selection_invalid")
            if self.hte is not None:
                if self.hte.kind == "interval_estimate" and (
                    self.hte_result_ref is None
                    or self.point_result_ref is not None
                    or self.inference_basis_ref is None
                ):
                    raise ValueError("direct_method_execution_hte_interval_refs_incomplete")
                if self.hte.kind == "point_estimate" and (
                    self.point_result_ref is None or self.hte_result_ref is not None
                ):
                    raise ValueError("direct_method_execution_hte_point_refs_invalid")
                if self.hte.kind == "refusal" and any(
                    ref is not None
                    for ref in (
                        self.point_result_ref,
                        self.hte_result_ref,
                        self.inference_basis_ref,
                    )
                ):
                    raise ValueError("direct_method_execution_hte_refusal_refs_invalid")
            if self.hte_outcome_ref.kind != "ir.hte_outcome" or (
                self.hte_outcome_ref.media_type != "application/json"
                or self.hte_outcome_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("direct_method_execution_hte_outcome_ref_invalid")
            if self.point_result_ref is not None and (
                self.point_result_ref.kind != "ir.hte_point_result"
                or self.point_result_ref.media_type != "application/json"
                or self.point_result_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("direct_method_execution_point_result_ref_invalid")
            if self.hte_result_ref is not None and (
                self.hte_result_ref.kind != "ir.hte_result"
                or self.hte_result_ref.media_type != "application/json"
                or self.hte_result_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("direct_method_execution_hte_result_ref_invalid")
            if self.inference_basis_ref is not None and (
                self.inference_basis_ref.kind != "ir.ate_inference_basis"
                or self.inference_basis_ref.media_type != "application/json"
                or self.inference_basis_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("direct_method_execution_inference_basis_ref_invalid")
            if self.refusal_diagnostic_ref is not None and (
                self.refusal_diagnostic_ref.kind != "ir.hte_refusal_diagnostic"
                or self.refusal_diagnostic_ref.media_type != "application/json"
                or self.refusal_diagnostic_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("direct_method_execution_refusal_diagnostic_ref_invalid")
            if self.invocation_basis_ref is not None and (
                self.invocation_basis_ref.manifest_profile_sha256 is None
            ):
                raise ValueError("direct_method_execution_invocation_basis_ref_invalid")
            if (
                self.hte.owned_attempt_anchor_ref != self.owned_attempt_anchor_ref
                or self.hte.hte_outcome_ref != self.hte_outcome_ref
                or self.hte.point_result_ref != self.point_result_ref
                or self.hte.hte_result_ref != self.hte_result_ref
                or self.hte.inference_basis_ref != self.inference_basis_ref
                or self.hte.refusal_diagnostic_ref != self.refusal_diagnostic_ref
                or self.hte.method_fqn != self.method_fqn
                or self.hte.method_abi_digest != self.method_abi_digest
                or self.hte.method_result_ref != self.method_result_ref
                or self.hte.method_evidence_ref != self.method_evidence_ref
                or self.hte.source_data_ref != self.effective_input_ref
                or self.hte.resource_evidence.owner_policy_ref != self.resource_policy_ref
                or self.hte.resource_evidence.owner_policy_digest != self.resource_policy_digest
            ):
                raise ValueError("direct_method_execution_hte_summary_selection_mismatch")
            if (
                self.hte.request_estimand_status != context.request_estimand_status
                or self.hte.request_estimand != context.request_estimand
                or self.hte.request_target_scope_status != context.request_target_scope_status
                or self.hte.request_target_scope != context.request_target_scope
                or self.hte.outcome_variable_status != context.outcome_variable_status
                or self.hte.outcome_variable_id != context.outcome_variable_id
                or self.hte.treatment_variable_status != context.treatment_variable_status
                or self.hte.treatment_variable_id != context.treatment_variable_id
                or self.hte.request_contrast_status != context.contrast_status
                or self.hte.control_value != context.control_value
                or self.hte.treated_value != context.treated_value
                or self.hte.request_alpha_status != context.request_alpha_status
                or self.hte.requested_alpha != context.requested_alpha
                or self.hte.requested_guarantee_status != context.requested_guarantee_status
                or self.hte.requested_guarantee != context.requested_guarantee
                or (self.hte.search_uncertainty_task_binding_ref is None)
                != (context.search_uncertainty_task_binding_ref is None)
                or (
                    self.hte.search_uncertainty_task_binding_ref is not None
                    and context.search_uncertainty_task_binding_ref is not None
                    and artifact_ref_identity_key(self.hte.search_uncertainty_task_binding_ref)
                    != artifact_ref_identity_key(context.search_uncertainty_task_binding_ref)
                )
            ):
                raise ValueError("direct_method_execution_hte_summary_request_context_mismatch")
        elif (
            self.method_fqn != f"causal.hte.forest_dr@{self.method_version}"
            or self.owned_hte_request_context is not None
            or self.hte is not None
            or any(
                ref is not None
                for ref in (
                    self.owned_attempt_anchor_ref,
                    self.hte_outcome_ref,
                    self.point_result_ref,
                    self.hte_result_ref,
                    self.inference_basis_ref,
                    self.refusal_diagnostic_ref,
                    self.invocation_basis_ref,
                )
            )
        ):
            raise ValueError("direct_method_execution_method_version_mismatch")
        if (
            not is_successor
            and self.candidate_outcome is not None
            and self.candidate_outcome.method != "forest_dr"
        ):
            raise ValueError("direct_method_execution_candidate_outcome_method_invalid")
        if self.selection_digest is not None and len(self.selection_digest) != 64:
            raise ValueError("direct_method_execution_selection_digest_invalid")
        if self.limitations != _expected_content_admitted_limitations(
            self.source_protocol,
            source_access_revalidation_status=self.source_access_revalidation_status,
        ):
            raise ValueError("direct_method_execution_limitations_invalid")
        refs = (
            self.requested_source_ref,
            self.observational_run_intent_ref,
            self.content_admitted_intent_ref,
            self.resource_policy_ref,
            self.submitted_input_ref,
            self.effective_input_ref,
            self.method_result_ref,
            self.method_evidence_ref,
            *(
                ref
                for ref in (
                    self.hte_outcome_ref,
                    self.point_result_ref,
                    self.hte_result_ref,
                    self.inference_basis_ref,
                    self.refusal_diagnostic_ref,
                    self.invocation_basis_ref,
                )
                if ref is not None
            ),
        )
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("direct_method_execution_selected_profile_missing")
        expected_source_kind = (
            "ir.observation_method_input"
            if self.source_protocol == "method_input_envelope_v1"
            else "ir.observational_data"
        )
        if (
            self.requested_source_ref.kind != expected_source_kind
            or self.requested_source_ref.media_type != "application/json"
            or self.submitted_input_ref != self.requested_source_ref
            or self.effective_input_ref.kind != "ir.observation_method_input"
            or self.effective_input_ref.media_type != "application/json"
            or self.observational_run_intent_ref.kind != "runtime.observational_run_intent"
            or self.observational_run_intent_ref.media_type != "application/json"
            or self.content_admitted_intent_ref.kind
            != "runtime.content_admitted_observational_run_intent"
            or self.content_admitted_intent_ref.media_type != "application/json"
            or self.resource_policy_ref.kind != "runtime.observational_input_resource_policy"
            or self.resource_policy_ref.media_type != "application/json"
            or self.contract_target_id != "foundry.causal.hte_observational_data.v1"
            or self.contract_target
            != "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
        ):
            raise ValueError("direct_method_execution_input_selection_invalid")
        if self.normalization != _expected_observational_normalization(self.source_protocol):
            raise ValueError("direct_method_execution_protocol_normalization_mismatch")
        if (
            self.source_protocol == "method_input_envelope_v1"
            and self.effective_input_ref != self.submitted_input_ref
        ):
            raise ValueError("direct_method_execution_passthrough_mismatch")
        if (
            self.method_result_ref.kind != "scientist.method_result.causal.hte"
            or self.method_result_ref.media_type != "application/json"
            or self.method_evidence_ref.kind != "scientist.method_evidence"
            or self.method_evidence_ref.media_type != "application/json"
        ):
            raise ValueError("direct_method_execution_output_view_invalid")
        return self


class DirectMethodExecutionRequestSummary(BaseModel):
    """Privacy-bounded immutable request summary for one accepted direct method job."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    requested_source_ref: ArtifactRef
    requested_intent_ref: ArtifactRef
    resource_policy_ref: ArtifactRef
    source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"]
    method_fqn: str = Field(min_length=1, max_length=256)
    method_version: str = Field(min_length=1, max_length=64)
    owned_hte_request_context: OwnedHTERequestContextV1 | None = None
    method_abi_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_build_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    method_build_digest_scope: Literal["class_source_only"]
    resource_policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolved_params_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    seed: int = Field(ge=0, le=4_294_967_295, strict=True)
    seed_policy_revision: Literal["server_seed_zero_v1"]
    required_estimator_n_jobs: int | None = Field(default=None, ge=1, strict=True)
    max_manifest_bytes: int = Field(ge=1, strict=True)
    max_bytes: int = Field(ge=1, strict=True)
    max_depth: int = Field(ge=1, strict=True)
    max_elements: int = Field(ge=1, strict=True)
    requested_at: datetime

    @model_validator(mode="after")
    def _require_selected_request_refs(self) -> DirectMethodExecutionRequestSummary:
        if (
            self.requested_source_ref.manifest_profile_sha256 is None
            or self.requested_intent_ref.kind != "runtime.observational_run_intent"
            or self.requested_intent_ref.media_type != "application/json"
            or self.requested_intent_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("direct_method_execution_request_summary_refs_invalid")
        if (
            self.resource_policy_ref.kind != "runtime.observational_input_resource_policy"
            or self.resource_policy_ref.media_type != "application/json"
            or self.resource_policy_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("direct_method_execution_request_policy_ref_invalid")
        is_successor = self.method_fqn in _OBSERVATIONAL_HTE_SUCCESSOR_METHODS
        if is_successor:
            context = self.owned_hte_request_context
            if (
                self.method_version != "2.0.0"
                or type(context) is not OwnedHTERequestContextV1
                or context.request_estimand_status != "declared"
                or context.request_target_scope_status != "declared"
                or context.outcome_variable_status != "declared"
                or context.treatment_variable_status != "declared"
                or context.contrast_status != "declared"
                or context.request_alpha_status != "declared"
                or context.requested_guarantee_status not in {"declared", "not_established"}
            ):
                raise ValueError("direct_method_execution_request_hte_context_invalid")
        elif (
            self.method_fqn != f"causal.hte.forest_dr@{self.method_version}"
            or self.owned_hte_request_context is not None
        ):
            raise ValueError("direct_method_execution_request_method_version_mismatch")
        return self


class DirectMethodExecutionTimeRoles(BaseModel):
    """Keep request, admission, execution, owner verification, and read times distinct."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    admitted_at: datetime | None = None
    execution_started_at: datetime | None = None
    execution_finished_at: datetime | None = None
    source_observation_epoch: datetime | None = None
    owner_verified_at: datetime | None = None
    reader_at: datetime


class DirectMethodExecutionRunProjection(BaseModel):
    """Audience-bounded current projection of one persisted direct method run."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal[
        "withheld",
        "absent",
        "legacy_unbound",
        "accepted_pending",
        "selected",
        "input_refused",
        "execution_failed",
        "unavailable",
    ]
    request: DirectMethodExecutionRequestSummary | None = None
    selection: DirectMethodExecutionSelection | None = None
    input_refusal: OwnedAttemptAnchorRefusalAssociation | None = None
    time_roles: DirectMethodExecutionTimeRoles | None = None
    refusal_code: Literal["observational_input_refused"] | None = None
    limitations: tuple[
        Literal[
            "selected_view_permission_required",
            "owned_run_cell_scope_required",
            "no_direct_method_request",
            "legacy_selection_unbound",
            "candidate_execution_pending",
            "execution_outcome_not_established",
            "selection_persistence_not_established",
            "input_refused_before_dispatch",
            "candidate_input_not_external_truth",
            "causal_identification_not_established",
            "scientific_validity_not_established",
            "units_and_context_not_established",
            "source_access_revalidation_not_established",
            "legacy_hte_json_v1_source_normalized",
        ],
        ...,
    ] = Field(default_factory=tuple, max_length=32)
    candidate_only: Literal[True] = True

    @model_validator(mode="after")
    def _require_projection_status_shape(self) -> DirectMethodExecutionRunProjection:
        if self.status == "withheld":
            if (
                self.request is not None
                or self.selection is not None
                or self.input_refusal is not None
                or self.time_roles is not None
            ):
                raise ValueError("direct_method_execution_withheld_projection_leaks_selection")
            if self.limitations not in {
                ("selected_view_permission_required",),
                ("owned_run_cell_scope_required",),
            }:
                raise ValueError("direct_method_execution_withheld_reason_invalid")
        elif self.status in {"absent", "legacy_unbound"}:
            if (
                self.request is not None
                or self.selection is not None
                or self.input_refusal is not None
                or self.refusal_code is not None
            ):
                raise ValueError("direct_method_execution_empty_status_has_selection")
            if self.time_roles is not None:
                raise ValueError("direct_method_execution_empty_status_has_times")
            expected_limitations = {
                "absent": ("no_direct_method_request",),
                "legacy_unbound": ("legacy_selection_unbound",),
            }[self.status]
            if self.limitations != expected_limitations:
                raise ValueError("direct_method_execution_empty_status_reason_invalid")
        elif self.status == "unavailable":
            if (
                self.selection is not None
                or self.input_refusal is not None
                or self.refusal_code is not None
            ):
                raise ValueError("direct_method_execution_unavailable_has_selection")
            if (self.request is None) != (self.time_roles is None):
                raise ValueError("direct_method_execution_unavailable_request_times_mismatch")
            if self.limitations not in {
                ("execution_outcome_not_established",),
                ("selection_persistence_not_established",),
            }:
                raise ValueError("direct_method_execution_unavailable_reason_invalid")
        elif self.status == "selected":
            successor_selection = (
                self.selection is not None
                and self.selection.method_fqn in _OBSERVATIONAL_HTE_SUCCESSOR_METHODS
            )
            if (
                self.request is None
                or self.selection is None
                or self.input_refusal is not None
                or (self.selection.candidate_outcome is None and not successor_selection)
                or self.time_roles is None
                or self.time_roles.admitted_at is None
                or self.time_roles.execution_started_at is None
                or self.time_roles.execution_finished_at is None
                or self.time_roles.owner_verified_at is None
                or self.refusal_code is not None
                or self.request.requested_source_ref != self.selection.requested_source_ref
                or self.request.method_fqn != self.selection.method_fqn
                or self.request.method_version != self.selection.method_version
                or self.request.owned_hte_request_context
                != self.selection.owned_hte_request_context
                or self.limitations != self.selection.limitations
            ):
                raise ValueError("direct_method_execution_selected_projection_incomplete")
        else:
            if self.request is None or self.selection is not None or self.time_roles is None:
                raise ValueError("direct_method_execution_request_projection_incomplete")
            if (self.status == "input_refused") != (
                self.refusal_code == "observational_input_refused"
            ):
                raise ValueError("direct_method_execution_refusal_status_invalid")
            if (self.status == "input_refused") != (self.input_refusal is not None):
                raise ValueError("direct_method_execution_refusal_association_missing")
            if self.input_refusal is not None and (
                self.input_refusal.status != "input_refusal_reconciled"
                or self.input_refusal.job_id == ""
            ):
                raise ValueError("direct_method_execution_refusal_association_invalid")
            expected_limitations = (
                ("candidate_execution_pending",)
                if self.status == "accepted_pending"
                else (
                    ("input_refused_before_dispatch",)
                    if self.status == "input_refused"
                    else ("execution_outcome_not_established",)
                )
            )
            if self.limitations != expected_limitations:
                raise ValueError("direct_method_execution_request_status_reason_invalid")
        return self


class GraphMethodExecutionSelection(BaseModel):
    """Persist one graph result's exact method bundle and optional AD01 projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selection_kind: Literal["graph_method"] = "graph_method"
    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    attempt: int = Field(ge=1, strict=True)
    method_result_ref: None = None
    source_experiment_state_ref: ArtifactRef
    simulation_result_ref: ArtifactRef
    method_execution_bundle_ref: ArtifactRef
    method_metric_binding_set_ref: ArtifactRef
    source_candidate_ref: ArtifactRef | None = None
    metric_verification_status: Literal["verified", "verification_missing"]
    method_metric_projection: MethodMetricProjectionSelection | None = None
    metric_projection_wait_policy: BoundedLivenessResolution | None = None

    @model_validator(mode="after")
    def _require_exact_graph_source(self) -> GraphMethodExecutionSelection:
        refs = (
            self.source_experiment_state_ref,
            self.simulation_result_ref,
            self.method_execution_bundle_ref,
            self.method_metric_binding_set_ref,
        )
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise ValueError("graph_method_execution_selected_profile_missing")
        if (
            self.source_experiment_state_ref.kind != "scientist.experiment_state"
            or self.source_experiment_state_ref.media_type != "application/json"
            or self.simulation_result_ref.kind != "foundry.simulation_result"
            or self.method_execution_bundle_ref.kind != "foundry.method_execution_bundle"
            or self.method_metric_binding_set_ref.kind != "foundry.method_metric_binding_set"
            or any(ref.media_type != "application/json" for ref in refs[1:])
        ):
            raise ValueError("graph_method_execution_source_tuple_invalid")
        if self.source_candidate_ref is not None and (
            self.source_candidate_ref.kind != "scientist.policy_design.candidate"
            or self.source_candidate_ref.media_type != "application/json"
            or self.source_candidate_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("graph_method_execution_source_candidate_invalid")
        if (self.metric_verification_status == "verified") != (
            self.method_metric_projection is not None
        ) or (self.metric_verification_status == "verified") != (
            self.source_candidate_ref is not None
        ):
            raise ValueError("graph_method_execution_projection_status_mismatch")
        if self.metric_projection_wait_policy is not None and (
            self.metric_projection_wait_policy.producer_key != "runtime.method_metric_projection"
            or self.metric_projection_wait_policy.retry_ceiling != 0
            or self.metric_projection_wait_policy.escalation != "runtime_escalation"
        ):
            raise ValueError("graph_method_execution_wait_policy_invalid")
        return self


MethodExecutionSelection = Annotated[
    DirectMethodExecutionSelection | GraphMethodExecutionSelection,
    Field(discriminator="selection_kind"),
]


def _is_json_wire_value(value: object) -> bool:
    """Return whether a decoded value consists only of JSON wire primitives."""
    if value is None or type(value) in (bool, int, str):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(_is_json_wire_value(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and _is_json_wire_value(item) for key, item in value.items())
    return False


_StrictJsonWirePayloadT = TypeVar("_StrictJsonWirePayloadT")


def _validate_strict_json_wire_payload(
    payload: object,
    adapter: TypeAdapter[_StrictJsonWirePayloadT],
    *,
    invalid_code: str,
) -> _StrictJsonWirePayloadT:
    """Strictly validate one persisted JSON object using JSON wire semantics.

    Owner stores decode persisted JSON before typed admission. This boundary
    preserves JSON arrays as tuple-compatible wire values while refusing
    non-JSON Python objects, non-string keys, and non-finite numbers before
    serialization. The adapter still applies strict model validation.
    """
    if type(payload) is not dict or not _is_json_wire_value(payload):
        raise ValueError(invalid_code)
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return adapter.validate_json(serialized, strict=True)


def _validate_method_execution_selection_wire_payload(
    payload: object,
) -> MethodExecutionSelection:
    """Strictly decode one JSON-shaped persisted method selection.

    Persisted rows and lifecycle events are decoded JSON objects, so strict
    Python validation would reject JSON arrays for tuple fields. The shared
    wire admission helper preserves Pydantic's strict JSON semantics, including
    extra-field refusal, without accepting Python model objects, tuples, or
    custom JSON coercions.
    """
    return _validate_strict_json_wire_payload(
        payload,
        TypeAdapter(MethodExecutionSelection),
        invalid_code="method_execution_selection_wire_payload_invalid",
    )


class MethodExecutionProducerEmissionDiagnostic(BaseModel):
    """One bounded actual ExecuteResult output inventory, without authority claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    emission_index: int = Field(ge=0)
    execute_result_status: Literal["ok", "failed", "not_established"]
    output_ref_status: Literal["complete", "partial", "none"]
    simulation_result_ref: ArtifactRef | None = None
    method_execution_bundle_refs: tuple[ArtifactRef, ...] = Field(
        default_factory=tuple,
        max_length=8,
    )
    method_metric_binding_set_refs: tuple[ArtifactRef, ...] = Field(
        default_factory=tuple,
        max_length=8,
    )

    @model_validator(mode="after")
    def validate_selected_output_refs(
        self,
    ) -> MethodExecutionProducerEmissionDiagnostic:
        """Require every exposed reference to be selected and kind-correct."""
        expected = (
            (self.simulation_result_ref, "foundry.simulation_result"),
            *(
                (ref, "foundry.method_execution_bundle")
                for ref in self.method_execution_bundle_refs
            ),
            *(
                (ref, "foundry.method_metric_binding_set")
                for ref in self.method_metric_binding_set_refs
            ),
        )
        for ref, kind in expected:
            if ref is None:
                continue
            if (
                ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("method_execution_producer_diagnostic_ref_invalid")
        output_ref_count = (
            int(self.simulation_result_ref is not None)
            + len(self.method_execution_bundle_refs)
            + len(self.method_metric_binding_set_refs)
        )
        complete = (
            self.simulation_result_ref is not None
            and len(self.method_execution_bundle_refs) == 1
            and len(self.method_metric_binding_set_refs) == 1
        )
        if (
            (self.output_ref_status == "complete" and not complete)
            or (self.output_ref_status == "partial" and output_ref_count == 0)
            or (self.output_ref_status == "none" and output_ref_count != 0)
        ):
            raise ValueError("method_execution_producer_diagnostic_status_mismatch")
        return self


class MethodExecutionProducerDiagnostic(BaseModel):
    """Candidate-only per-attempt inventory of actual Foundry method emissions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    attempt: int = Field(ge=1)
    authority_status: Literal["candidate_only"] = "candidate_only"
    emissions: tuple[MethodExecutionProducerEmissionDiagnostic, ...] = Field(
        default_factory=tuple,
        max_length=16,
    )
    inventory_truncated: bool = False
    limitations: tuple[
        Literal[
            "producer_diagnostic_only",
            "workflow_authority_not_established",
            "scientific_validity_not_established",
        ],
        ...,
    ] = (
        "producer_diagnostic_only",
        "workflow_authority_not_established",
        "scientific_validity_not_established",
    )

    @model_validator(mode="after")
    def validate_emission_order(self) -> MethodExecutionProducerDiagnostic:
        """Keep the bounded inventory stable and unambiguous."""
        if tuple(item.emission_index for item in self.emissions) != tuple(
            range(len(self.emissions))
        ):
            raise ValueError("method_execution_producer_diagnostic_order_invalid")
        return self


class RunConditionalTransportCandidateProjection(BaseModel):
    """Audience-safe candidate summary derived from a verified persisted result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_scope: Literal["candidate_only"]
    candidate_disposition: Literal["not_run", "completed", "partial", "unsupported", "error"]
    requested_profile_id: str = Field(min_length=1, max_length=160)
    requested_profile_revision: str = Field(min_length=1, max_length=80)
    selection_identity: str = Field(min_length=1, max_length=240)
    reason_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{1,95}$")
    proposal_count: int = Field(ge=0)
    member_evaluation_count: int = Field(ge=0)
    completed_valid_member_count: int = Field(ge=0)
    identified_member_fraction: float | None = Field(default=None, ge=0, le=1)
    identified_member_fraction_basis: Literal["selected_completed_valid_members"]
    source_currentness: Literal["unknown"]
    interpretation_limit: Literal[
        "selected_family_member_outcomes_do_not_establish_whole_pag_class_probability_calibration_legal_applicability_or_protected_eligibility"
    ]

    @model_validator(mode="after")
    def validate_candidate_counts_and_fraction(self) -> RunConditionalTransportCandidateProjection:
        """Keep the denominator explicit and fraction semantics truthful."""
        if self.completed_valid_member_count > self.member_evaluation_count:
            raise ValueError("conditional_transport_candidate_valid_count_exceeds_evaluated")
        if self.completed_valid_member_count == 0:
            if self.identified_member_fraction is not None:
                raise ValueError("conditional_transport_candidate_fraction_requires_denominator")
        elif self.identified_member_fraction is None:
            raise ValueError("conditional_transport_candidate_fraction_missing")
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
    method_execution_producer_diagnostic: MethodExecutionProducerDiagnostic | None = None
    method_execution_selection: DirectMethodExecutionRunProjection | None = None
    conditional_transport_candidate: RunConditionalTransportCandidateProjection | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


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


class ExAnteSourceUseDebugView(BaseModel):
    """Fresh, bounded SQL source-use outcome for one profiled execution.

    This says only whether the internally admitted materialization remains
    available for its registered use at the owner read point. It is not legal,
    scientific, or external-database-currentness authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["current", "withdrawn", "unknown"]
    method_replay_status: Literal["verified", "verification_missing", "invalid"]
    source_basis_ref: ArtifactRef | None = None
    method_execution_bundle_ref: ArtifactRef | None = None
    input_capture_ref: ArtifactRef | None = None
    recomputed_mean_change: float | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    owner_current_use: SourceCurrentUseProjection | None = None
    limitations: tuple[str, ...] = Field(default_factory=tuple, max_length=16)
    projection_class: Literal["candidate_reference_only"] = "candidate_reference_only"
    authority_status: Literal["non_authority"] = "non_authority"

    @model_validator(mode="after")
    def _bind_owner_outcome(self) -> ExAnteSourceUseDebugView:
        if self.status in {"current", "withdrawn"}:
            refs = (self.source_basis_ref, self.method_execution_bundle_ref, self.input_capture_ref)
            if (
                self.method_replay_status != "verified"
                or self.owner_current_use is None
                or self.owner_current_use.status != self.status
                or self.owner_current_use.selection_checked
                or self.owner_current_use.basis_digest is None
                or self.owner_current_use.committed_root is None
                or self.owner_current_use.generation < 1
                or self.limitations
                or any(ref is None or ref.manifest_profile_sha256 is None for ref in refs)
            ):
                raise ValueError("debug_source_use_requires_verified_replay_and_owner")
        elif not self.limitations:
            raise ValueError("debug_source_use_unknown_requires_limitation")
        if self.status == "current":
            if self.recomputed_mean_change is None or not math.isfinite(
                self.recomputed_mean_change
            ):
                raise ValueError("debug_current_source_use_requires_recomputed_mean_change")
        elif self.recomputed_mean_change is not None:
            raise ValueError("debug_noncurrent_source_use_cannot_authorize_score")
        return self


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
    exante_source_use: ExAnteSourceUseDebugView | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
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
_AGENT_PIPELINE_RESPONSE_REPORT_CONTEXT_KEY = "agent_pipeline_response_report"


def _is_agent_pipeline_response_report_context(context: object) -> bool:
    return (
        isinstance(context, Mapping)
        and context.get(_AGENT_PIPELINE_RESPONSE_REPORT_CONTEXT_KEY) is True
    )


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
        if _is_agent_pipeline_response_report_context(info.context):
            return dict(value)
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
        normalized = dict(value)
        if _is_agent_pipeline_response_report_context(info.context):
            normalized.pop("cost_origin", None)
            normalized.pop("settlement_event_ids", None)
            return normalized
        events = _cost_events_from_pipeline_steps(value.get("steps"))
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
        if _is_agent_pipeline_response_report_context(info.context):
            return self
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
        "caller_selected_profile",
        "worker_default_limited",
        "not_requested",
        "not_established",
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


def _agent_pipeline_verified_event_basis_sha256(
    events: list[AgentPipelineCostEvent], owner_attempt: int
) -> str:
    """Bind private owner admission to the complete typed event basis."""
    payload = {
        "owner_control_job_attempt": owner_attempt,
        "cost_events": [event.model_dump(mode="json") for event in events],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AgentPipelineView(BaseModel):
    """Composite runtime view of agent attempts, retrieval, evaluation, and iteration state."""

    model_config = ConfigDict(extra="forbid")

    _verified_owner_control_job_attempt: int | None = PrivateAttr(default=None)
    _verified_cost_event_basis_sha256: str | None = PrivateAttr(default=None)
    _response_report_observations: bool = PrivateAttr(default=False)

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
        if _is_agent_pipeline_response_report_context(info.context):
            normalized = dict(value)
            normalized.pop("cost_origin", None)
            normalized.pop("settlement_event_ids", None)
            performance_summary, performance_scalars = (
                _performance_summary_without_unattributed_cost_scalars(
                    normalized.get("performance_summary")
                )
            )
            normalized["performance_summary"] = performance_summary
            scalar_claims = normalized.get("unattributed_cost_scalars")
            if isinstance(scalar_claims, (list, tuple)):
                normalized["unattributed_cost_scalars"] = [
                    *scalar_claims,
                    *performance_scalars,
                ]
            return normalized
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
    def _from_response_report(cls, values: Mapping[str, object]) -> AgentPipelineView:
        """Parse endpoint fields as read observations without owner admission."""
        return cls.model_validate(
            values,
            context={_AGENT_PIPELINE_RESPONSE_REPORT_CONTEXT_KEY: True},
        )

    @classmethod
    def _from_verified_owner_context(
        cls,
        *,
        owner_control_job_attempt: int | None,
        **values: object,
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
        if (
            _is_agent_pipeline_response_report_context(info.context)
            or self._response_report_observations
        ):
            if any(
                event.control_job_attempt is not None for event in self.unattributed_cost_events
            ):
                raise ValueError("unattributed_cost_event_claims_control_job_attempt")
            event_ids = [event.event_id for event in self.unattributed_cost_events]
            if len(event_ids) != len(set(event_ids)):
                raise ValueError("duplicate_unattributed_cost_event")
            return self
        context_owner_attempt = _owner_attempt_from_validation_context(info.context)
        prior_owner_attempt = getattr(self, "_verified_owner_control_job_attempt", None)
        if context_owner_attempt is None and prior_owner_attempt is not None:
            if self.owner_control_job_attempt != prior_owner_attempt:
                raise ValueError("agent_pipeline_owner_context_mismatch")
            prior_events = _cost_events_from_pipeline_steps(
                [step for attempt in self.attempts for step in attempt.steps]
            )
            prior_basis = _agent_pipeline_verified_event_basis_sha256(
                prior_events, prior_owner_attempt
            )
            if getattr(self, "_verified_cost_event_basis_sha256", None) != prior_basis:
                raise ValueError("agent_pipeline_verified_owner_cost_event_basis_changed")
            owner_attempt = prior_owner_attempt
        else:
            owner_attempt = context_owner_attempt
            if owner_attempt is None:
                self.owner_control_job_attempt = None
            elif self.owner_control_job_attempt != owner_attempt or (
                prior_owner_attempt is not None and prior_owner_attempt != owner_attempt
            ):
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

    def model_post_init(self, context: object) -> None:
        """Remember route-verified ownership only on the admitted typed instance."""
        if _is_agent_pipeline_response_report_context(context):
            self._response_report_observations = True
            return
        owner_attempt = _owner_attempt_from_validation_context(context)
        if owner_attempt is None:
            return
        events = _cost_events_from_pipeline_steps(
            [step for attempt in self.attempts for step in attempt.steps]
        )
        self._verified_owner_control_job_attempt = owner_attempt
        self._verified_cost_event_basis_sha256 = _agent_pipeline_verified_event_basis_sha256(
            events, owner_attempt
        )


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
    hte: DirectMethodExecutionHTESummary | None = None
    hte_projection_status: Literal["absent", "typed", "legacy_limited", "invalid"] = "absent"
    hte_legacy_limited: DecisionPacketLegacyHTEPreview | None = None

    @model_validator(mode="after")
    def _require_hte_projection_shape(self) -> DecisionPacketPreview:
        if self.hte_projection_status == "typed":
            if self.hte is None or self.hte_legacy_limited is not None:
                raise ValueError("decision_packet_hte_typed_projection_invalid")
        elif self.hte_projection_status == "legacy_limited":
            if self.hte is not None or self.hte_legacy_limited is None:
                raise ValueError("decision_packet_hte_legacy_projection_invalid")
        elif self.hte is not None or self.hte_legacy_limited is not None:
            raise ValueError("decision_packet_hte_nonprojected_value_present")
        return self


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
    """Response/report envelope returned by the agent-pipeline endpoint."""

    model_config = ConfigDict(extra="forbid")

    meta: ApiMeta
    pipeline: AgentPipelineView

    @model_validator(mode="before")
    @classmethod
    def _parse_pipeline_report_observations(cls, value: object) -> object:
        """Preserve endpoint report fields without creating verified owner context."""
        if not isinstance(value, Mapping):
            return value
        raw_pipeline = value.get("pipeline")
        if not isinstance(raw_pipeline, Mapping):
            return value
        normalized = dict(value)
        normalized["pipeline"] = AgentPipelineView._from_response_report(raw_pipeline)
        return normalized


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
    "CompletedExAnteCandidateComparisonResponse",
    "CompletedExAnteCandidateObservation",
    "CompletedExAnteCandidateRanking",
    "CompletedExAnteCandidateSource",
    "CompletedExAnteComparisonRequest",
    "CompletedMethodHTESource",
    "ContentAdmittedObservationalRunIntent",
    "CounterfactualMetric",
    "CounterfactualMetricsResponse",
    "CounterfactualMode",
    "CursorPage",
    "DecisionCompareReport",
    "DecisionMonitoringContract",
    "DecisionMonitoringReport",
    "DecisionPacketAuthoredBlock",
    "DecisionPacketEffectSize",
    "DecisionPacketLegacyHTEFeaturePreview",
    "DecisionPacketLegacyHTEPreview",
    "DecisionPacketMetricComparisonRow",
    "DecisionPacketMetricSignificance",
    "DecisionPacketOutlineEntry",
    "DecisionPacketPreview",
    "DecisionReissuePlan",
    "DeltaDistribution",
    "DeltaDominance",
    "DeltaQuantity",
    "DeltaSignificance",
    "DirectMethodExecutionHTEResourceEvidence",
    "DirectMethodExecutionHTESummary",
    "DirectMethodExecutionHTETargetRelation",
    "DirectMethodExecutionRequestSummary",
    "DirectMethodExecutionRunProjection",
    "DirectMethodExecutionSelection",
    "DirectMethodExecutionTimeRoles",
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
    "GraphMethodExecutionSelection",
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
    "MethodExecutionCandidateOutcome",
    "MethodExecutionPosteriorSummaryRef",
    "MethodExecutionProducerDiagnostic",
    "MethodExecutionProducerEmissionDiagnostic",
    "MethodExecutionSelection",
    "MethodMetricCandidateScore",
    "MethodMetricProjectionResponse",
    "MethodMetricProjectionSelection",
    "MobilityBoundsRequest",
    "MobilityBoundsResponse",
    "MobilityDiagnosticsResponse",
    "MobilityEstimateRequest",
    "MobilityEstimateResponse",
    "MobilityReportResponse",
    "NodeDebugResponse",
    "NodeDebugView",
    "NodeStatus",
    "ObservationalInputResourcePolicy",
    "ObservationalRunIntent",
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

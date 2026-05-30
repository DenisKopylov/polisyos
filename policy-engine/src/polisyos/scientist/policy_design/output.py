"""Typed policy-output artifacts and bundle builder."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.ic_verification import ICVerificationCertificateRef
from polisyos.core.contracts.scientist import (
    ChampionPolicyDossierRef,
    ConstraintSatisfactionReportRef,
    DecisionReadinessContractRef,
    GovernanceAccountabilityArtifactRef,
    GovernanceGatePacketRef,
    ImplementationPlanRef,
    PolicyArtifactBundleRef,
    PolicyBriefRef,
    PolicyFrontierReportRef,
    RejectedAlternativesSummaryRef,
    ReplayableAuditBundleRef,
    StressTestReportRef,
    SubgroupImpactReportRef,
    TransportabilityReportRef,
    UncertaintyReportRef,
)
from polisyos.ir.analytics.cross_graph import CrossGraphEvidenceProfile, TransportStatus
from polisyos.ir.analytics.distributional import (
    DistributionalReport,
    ImpactDirection,
)
from polisyos.ir.registry.refs import (
    FiscalFeedbackLinkRef,
    IncentiveCompatibilityCertificateRef,
    MechanismWelfareLossBoundRef,
    OptimizationAmbiguityCertificateRef,
    WelfareBundleRef,
)
from polisyos.scientist.evidence.claims.export import blocked_claim_summary, claim_ledger_summary
from polisyos.scientist.evidence.claims.ledger import load_claim_ledger, persist_claim_ledger
from polisyos.scientist.evidence.claims.projections import project_policy_artifact_bundle_claims
from polisyos.scientist.methods.doe.stress_report import StressTestReport
from polisyos.scientist.governance.calibration_validation import CalibrationValidationBundle
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.phase3 import (
    Phase3CertificateStatus,
    phase3_gate_reference_blockers,
)
from polisyos.scientist.policy_design.schema import (
    MonitoringSignalSpec,
    PolicyCandidateSchema,
    RolloutStep,
)
from polisyos.scientist.methods.search.artifact_minimality import (
    ArtifactFunction,
    ArtifactMinimalityMixin,
    artifact_functions_field,
)
from polisyos.scientist.methods.search.judge_stack import JudgeVerdict, PolicyPromotionResult
from polisyos.scientist.methods.search.pareto_registry import ParetoRegistrySnapshot
from polisyos.scientist.methods.search.readiness import DecisionReadiness, DecisionReadinessContract
from polisyos.scientist.methods.search.uncertainty import UncertaintyEnvelope


class TradeoffRow(BaseModel):
    """Tradeoff row public type."""

    model_config = ConfigDict(extra="forbid")

    axis: str = Field(min_length=1)
    champion_value: str = Field(min_length=1)
    comparator_value: str | None = None
    rationale: str = Field(min_length=1)


class PolicyRiskNote(BaseModel):
    """Policy risk note public type."""

    model_config = ConfigDict(extra="forbid")

    risk_id: str = Field(default_factory=lambda: f"risk_{uuid4().hex[:10]}")
    title: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    description: str = Field(min_length=1)
    impacted_groups: list[str] = Field(default_factory=list)
    surfaced_assumptions: list[str] = Field(default_factory=list)


class RecommendedAction(BaseModel):
    """Recommended action public type."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(default_factory=lambda: f"action_{uuid4().hex[:10]}")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: str = Field(default="medium", min_length=1)


class PolicyBrief(ArtifactMinimalityMixin):
    """Policy brief public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    brief_id: str = Field(default_factory=lambda: f"brief_{uuid4().hex[:12]}")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
        )
    )
    title: str = Field(min_length=1)
    audience: str = Field(default="decision_maker", min_length=1)
    executive_summary: str = Field(min_length=1)
    readiness_level: str = Field(min_length=1)
    surfaced_assumptions: list[str] = Field(default_factory=list)
    uncertainty_highlights: list[str] = Field(default_factory=list)
    subgroup_harms: list[str] = Field(default_factory=list)
    hard_constraint_notes: list[str] = Field(default_factory=list)
    tradeoffs: list[TradeoffRow] = Field(default_factory=list)
    risks: list[PolicyRiskNote] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConstraintSatisfactionEntry(BaseModel):
    """One feasibility row showing how a single policy constraint was evaluated."""

    model_config = ConfigDict(extra="forbid")

    constraint_name: str = Field(min_length=1)
    status: str = Field(min_length=1)
    observed_value: float | None = None
    threshold: float | None = None
    margin: float | None = None
    source: str | None = None


class SubgroupImpactEntry(BaseModel):
    """Distributional impact row for one subgroup touched by a candidate policy."""

    model_config = ConfigDict(extra="forbid")

    subgroup_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    direction: str = Field(min_length=1)
    net_impact: float = 0.0
    vulnerable: bool = False


class PolicyFrontierEntry(BaseModel):
    """One candidate on the shared policy frontier, including objectives and constraint status."""

    model_config = ConfigDict(extra="forbid")

    candidate_hash: str = Field(min_length=1)
    candidate_id: str | None = None
    policy_family: str | None = None
    view_membership: list[str] = Field(default_factory=list)
    primary_objectives: dict[str, float] = Field(default_factory=dict)
    constraint_statuses: dict[str, str] = Field(default_factory=dict)
    readiness_level: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyFrontierReport(ArtifactMinimalityMixin):
    """Frontier snapshot used to compare candidate families and preserve cross-run search context."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    loop_id: str = Field(min_length=1)
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.ROUTING,
            ArtifactFunction.CROSS_RUN_LEARNING,
        )
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    global_frontier: list[PolicyFrontierEntry] = Field(default_factory=list)
    view_membership: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChampionPolicyDossier(ArtifactMinimalityMixin):
    """Champion policy dossier public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    dossier_id: str = Field(default_factory=lambda: f"dossier_{uuid4().hex[:12]}")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    candidate_id: str = Field(min_length=1)
    candidate_hash: str = Field(min_length=1)
    readiness_level: str = Field(min_length=1)
    executive_summary: str = Field(min_length=1)
    objective_summary: dict[str, float] = Field(default_factory=dict)
    constraint_summary: list[ConstraintSatisfactionEntry] = Field(default_factory=list)
    subgroup_harms: list[str] = Field(default_factory=list)
    surfaced_assumptions: list[str] = Field(default_factory=list)
    uncertainty_summary: dict[str, float] = Field(default_factory=dict)
    transport_summary: dict[str, Any] = Field(default_factory=dict)
    governance_summary: dict[str, Any] = Field(default_factory=dict)
    stress_summary: dict[str, Any] = Field(default_factory=dict)
    calibration_validation_summary: dict[str, Any] = Field(default_factory=dict)
    accountability_summary: dict[str, Any] = Field(default_factory=dict)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConstraintSatisfactionReport(ArtifactMinimalityMixin):
    """Candidate-level feasibility report showing which constraints still block rollout."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    candidate_id: str = Field(min_length=1)
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
        )
    )
    feasible: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    constraints: list[ConstraintSatisfactionEntry] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubgroupImpactReport(ArtifactMinimalityMixin):
    """Candidate-level equity summary covering harmed groups, beneficiaries, and inequality shift."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    candidate_id: str = Field(min_length=1)
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
        )
    )
    harmed_subgroups: list[SubgroupImpactEntry] = Field(default_factory=list)
    benefiting_subgroups: list[SubgroupImpactEntry] = Field(default_factory=list)
    inequality_delta: float | None = None
    notes: list[str] = Field(default_factory=list)


class UncertaintyReport(ArtifactMinimalityMixin):
    """Readiness-oriented summary of the uncertainty channels still binding a candidate."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    candidate_id: str = Field(min_length=1)
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.ROUTING,
            ArtifactFunction.PROMOTION_GATING,
        )
    )
    readiness_level: str = Field(min_length=1)
    uncertainties: dict[str, float] = Field(default_factory=dict)
    summary_notes: list[str] = Field(default_factory=list)
    binding_types: list[str] = Field(default_factory=list)


class TransportabilityReport(ArtifactMinimalityMixin):
    """Assessment of whether supporting evidence transfers to the target deployment context."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    candidate_id: str = Field(min_length=1)
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
        )
    )
    evidence_depth: str = Field(min_length=1)
    transport_status: str = Field(min_length=1)
    unsupported_needs: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)


class GovernanceGatePacket(ArtifactMinimalityMixin):
    """Governance gate packet public type."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    candidate_id: str = Field(min_length=1)
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    judge_composite_decision: str = Field(min_length=1)
    readiness_level: str = Field(min_length=1)
    governance_issues: list[str] = Field(default_factory=list)
    critical_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    translator_compliance_passed: bool | None = None
    translator_compliance_failures: list[str] = Field(default_factory=list)
    defer_to_human: bool = False
    phase3_gate: Phase3CertificateStatus = Field(default_factory=Phase3CertificateStatus.missing)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImplementationPlan(ArtifactMinimalityMixin):
    """Rollout plan that turns a candidate into ordered steps, monitors, and fallback actions."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    candidate_id: str = Field(min_length=1)
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
        )
    )
    rollout_steps: list[RolloutStep] = Field(default_factory=list)
    monitoring_plan: list[MonitoringSignalSpec] = Field(default_factory=list)
    fallback_variant_ids: list[str] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)


class RejectedAlternativeEntry(BaseModel):
    """Near-frontier policy alternative annotated with why it lost to the selected candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_hash: str = Field(min_length=1)
    candidate_id: str | None = None
    policy_family: str | None = None
    reason: str = Field(min_length=1)
    near_frontier: bool = False


class RejectedAlternativesSummary(ArtifactMinimalityMixin):
    """Search-memory summary of rejected alternatives and their dominant failure modes."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    loop_id: str = Field(min_length=1)
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.CROSS_RUN_LEARNING,
        )
    )
    alternatives: list[RejectedAlternativeEntry] = Field(default_factory=list)
    dominant_rejection_reasons: list[str] = Field(default_factory=list)


class ReplayableAuditBundle(ArtifactMinimalityMixin):
    """Replay package that pins runtime inputs, outputs, and reports needed for later audit."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    run_id: str = Field(min_length=1)
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    candidate_ref: ArtifactRef | None = None
    evaluation_ref: ArtifactRef | None = None
    readiness_ref: ArtifactRef | None = None
    workflow_id: str | None = None
    execution_profile: str | None = None
    runtime_input_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    runtime_artifacts_index: dict[str, ArtifactRef] = Field(default_factory=dict)
    runtime_reports_index: dict[str, ArtifactRef] = Field(default_factory=dict)
    runtime_params_snapshot: dict[str, Any] = Field(default_factory=dict)
    upstream_audit_refs: list[ArtifactRef] = Field(default_factory=list)
    actionable_side_information_refs: list[ArtifactRef] = Field(default_factory=list)
    artifact_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    trace_notes: list[str] = Field(default_factory=list)


class PolicyArtifactBundle(ArtifactMinimalityMixin):
    """Top-level bundle stitching together frontier, governance, rollout, and replay artifacts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    bundle_id: str = Field(default_factory=lambda: f"policy_bundle_{uuid4().hex[:12]}")
    artifact_functions: set[ArtifactFunction] = Field(
        default_factory=lambda: artifact_functions_field(
            ArtifactFunction.PROMOTION_GATING,
            ArtifactFunction.REPLAY_AUDIT,
        )
    )
    candidate_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    policy_frontier_report_ref: PolicyFrontierReportRef
    champion_policy_dossier_ref: ChampionPolicyDossierRef
    policy_brief_ref: PolicyBriefRef
    constraint_satisfaction_report_ref: ConstraintSatisfactionReportRef
    subgroup_impact_report_ref: SubgroupImpactReportRef
    uncertainty_report_ref: UncertaintyReportRef
    transportability_report_ref: TransportabilityReportRef
    governance_gate_packet_ref: GovernanceGatePacketRef
    implementation_plan_ref: ImplementationPlanRef
    rejected_alternatives_summary_ref: RejectedAlternativesSummaryRef
    replayable_audit_bundle_ref: ReplayableAuditBundleRef
    decision_readiness_contract_ref: DecisionReadinessContractRef | None = None
    claims_ref: ArtifactRef | None = None
    stress_test_report_ref: StressTestReportRef | None = None
    governance_accountability_artifact_ref: GovernanceAccountabilityArtifactRef | None = None
    phase3_gate: Phase3CertificateStatus = Field(default_factory=Phase3CertificateStatus.missing)
    welfare_bundle_ref: WelfareBundleRef | None = None
    ambiguity_certificate_ref: OptimizationAmbiguityCertificateRef | None = None
    semantic_ic_certificate_ref: ICVerificationCertificateRef | None = None
    mechanism_ic_certificate_ref: IncentiveCompatibilityCertificateRef | None = None
    mechanism_welfare_loss_bound_ref: MechanismWelfareLossBoundRef | None = None
    fiscal_feedback_ref: FiscalFeedbackLinkRef | None = None
    audit_refs: list[ArtifactRef] = Field(default_factory=list)
    actionable_side_information_refs: list[ArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyArtifactBuildInput(BaseModel):
    """Policy artifact build input public type."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    loop_id: str = Field(default="policy_mode", min_length=1)
    run_id: str = Field(default="policy_mode", min_length=1)
    candidate: PolicyCandidateSchema
    candidate_hash: str = Field(min_length=1)
    candidate_ref: ArtifactRef | None = None
    evaluation_vector: PolicyEvaluationVector | None = None
    evaluation_ref: ArtifactRef | None = None
    pareto_snapshot: ParetoRegistrySnapshot | None = None
    promotion_result: PolicyPromotionResult | None = None
    judge_verdict: JudgeVerdict | None = None
    readiness_contract: DecisionReadinessContract | None = None
    readiness_ref: ArtifactRef | None = None
    claims_ref: ArtifactRef | None = None
    distributional_report: DistributionalReport | None = None
    cross_graph_profile: CrossGraphEvidenceProfile | None = None
    uncertainty_envelope: UncertaintyEnvelope | None = None
    stress_test_report: StressTestReport | None = None
    stress_test_report_ref: ArtifactRef | None = None
    calibration_validation_bundle: CalibrationValidationBundle | None = None
    calibration_validation_bundle_ref: ArtifactRef | None = None
    policy_brief: PolicyBrief | None = None
    translator_compliance: Any | None = None
    phase3_gate: Phase3CertificateStatus | None = None
    constraint_findings: list[str] = Field(default_factory=list)
    mutation_hints: list[str] = Field(default_factory=list)
    audit_refs: list[ArtifactRef] = Field(default_factory=list)
    actionable_side_information_refs: list[ArtifactRef] = Field(default_factory=list)
    runtime_input_refs: dict[str, ArtifactRef] = Field(default_factory=dict)
    runtime_artifacts_index: dict[str, ArtifactRef] = Field(default_factory=dict)
    runtime_reports_index: dict[str, ArtifactRef] = Field(default_factory=dict)
    runtime_params_snapshot: dict[str, Any] = Field(default_factory=dict)
    execution_profile: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyArtifactBuilder:
    """Build and persist the 12-artifact policy output bundle."""

    def build(
        self,
        store: FileSystemCAS,
        source: PolicyArtifactBuildInput,
    ) -> PolicyArtifactBundleRef:
        self._validate_contract_bound_source(store, source)
        upstream_audit_refs = _dedupe_artifact_refs(source.audit_refs)
        actionable_side_information_refs = _dedupe_artifact_refs(
            source.actionable_side_information_refs
        )
        phase3_gate = source.phase3_gate or (
            source.readiness_contract.phase3_gate
            if source.readiness_contract is not None
            else Phase3CertificateStatus.missing()
        )
        frontier_report = self._build_frontier_report(source)
        frontier_ref = persist_policy_frontier_report(
            store,
            frontier_report,
            inputs=_bundle_inputs(source),
        )

        constraint_report = self._build_constraint_report(source)
        constraint_ref = persist_constraint_satisfaction_report(
            store,
            constraint_report,
            inputs=_bundle_inputs(source),
        )

        subgroup_report = self._build_subgroup_report(source)
        subgroup_ref = persist_subgroup_impact_report(
            store,
            subgroup_report,
            inputs=_bundle_inputs(source),
        )

        uncertainty_report = self._build_uncertainty_report(source)
        uncertainty_ref = persist_uncertainty_report(
            store,
            uncertainty_report,
            inputs=_bundle_inputs(source),
        )

        transport_report = self._build_transportability_report(source)
        transport_ref = persist_transportability_report(
            store,
            transport_report,
            inputs=_bundle_inputs(source),
        )

        gate_packet = self._build_governance_gate_packet(source)
        gate_ref = persist_governance_gate_packet(
            store,
            gate_packet,
            inputs=_bundle_inputs(source),
        )

        implementation_plan = self._build_implementation_plan(source)
        implementation_ref = persist_implementation_plan(
            store,
            implementation_plan,
            inputs=_bundle_inputs(source),
        )

        rejected_summary = self._build_rejected_alternatives(source)
        rejected_ref = persist_rejected_alternatives_summary(
            store,
            rejected_summary,
            inputs=_bundle_inputs(source),
        )

        dossier = self._build_dossier(
            source=source,
            constraint_report=constraint_report,
            subgroup_report=subgroup_report,
            uncertainty_report=uncertainty_report,
            transport_report=transport_report,
            gate_packet=gate_packet,
            implementation_plan=implementation_plan,
        )
        dossier_ref = persist_champion_policy_dossier(
            store,
            dossier,
            inputs=_bundle_inputs(source),
        )

        brief = source.policy_brief
        if brief is None:
            brief = _brief_from_dossier(dossier)
        brief_ref = persist_policy_brief(
            store,
            brief,
            inputs=_bundle_inputs(source),
        )

        base_refs = {
            "policy_frontier_report_ref": frontier_ref,
            "champion_policy_dossier_ref": dossier_ref,
            "policy_brief_ref": brief_ref,
            "constraint_satisfaction_report_ref": constraint_ref,
            "subgroup_impact_report_ref": subgroup_ref,
            "uncertainty_report_ref": uncertainty_ref,
            "transportability_report_ref": transport_ref,
            "governance_gate_packet_ref": gate_ref,
            "implementation_plan_ref": implementation_ref,
            "rejected_alternatives_summary_ref": rejected_ref,
        }
        claims_ref = source.claims_ref or self._persist_claim_ledger(
            store=store,
            source=source,
            refs=base_refs,
            phase3_gate=phase3_gate,
        )
        claim_summary_metadata = _claim_summary_metadata(store, claims_ref)

        audit_bundle = self._build_replayable_audit_bundle(
            source=source,
            refs={**base_refs, "claims_ref": claims_ref},
            upstream_audit_refs=upstream_audit_refs,
            actionable_side_information_refs=actionable_side_information_refs,
        )
        audit_ref = persist_replayable_audit_bundle(
            store,
            audit_bundle,
            inputs=_bundle_inputs(source),
        )

        bundle = PolicyArtifactBundle(
            candidate_id=source.candidate.candidate_id,
            policy_frontier_report_ref=frontier_ref,
            champion_policy_dossier_ref=dossier_ref,
            policy_brief_ref=brief_ref,
            constraint_satisfaction_report_ref=constraint_ref,
            subgroup_impact_report_ref=subgroup_ref,
            uncertainty_report_ref=uncertainty_ref,
            transportability_report_ref=transport_ref,
            governance_gate_packet_ref=gate_ref,
            implementation_plan_ref=implementation_ref,
            rejected_alternatives_summary_ref=rejected_ref,
            replayable_audit_bundle_ref=audit_ref,
            decision_readiness_contract_ref=_maybe_validate_ref(
                source.readiness_ref,
                DecisionReadinessContractRef,
            ),
            claims_ref=claims_ref,
            stress_test_report_ref=_maybe_validate_ref(
                source.stress_test_report_ref,
                StressTestReportRef,
            ),
            governance_accountability_artifact_ref=_maybe_validate_ref(
                (
                    None
                    if source.calibration_validation_bundle is None
                    else source.calibration_validation_bundle.governance_accountability_ref
                ),
                GovernanceAccountabilityArtifactRef,
            ),
            phase3_gate=phase3_gate,
            welfare_bundle_ref=_maybe_validate_ref(
                phase3_gate.welfare_bundle_ref,
                WelfareBundleRef,
            ),
            ambiguity_certificate_ref=_maybe_validate_ref(
                phase3_gate.ambiguity_certificate_ref,
                OptimizationAmbiguityCertificateRef,
            ),
            semantic_ic_certificate_ref=_maybe_validate_ref(
                phase3_gate.semantic_ic_certificate_ref,
                ICVerificationCertificateRef,
            ),
            mechanism_ic_certificate_ref=_maybe_validate_ref(
                phase3_gate.mechanism_ic_certificate_ref,
                IncentiveCompatibilityCertificateRef,
            ),
            mechanism_welfare_loss_bound_ref=_maybe_validate_ref(
                phase3_gate.mechanism_welfare_loss_bound_ref,
                MechanismWelfareLossBoundRef,
            ),
            fiscal_feedback_ref=_maybe_validate_ref(
                phase3_gate.fiscal_feedback_ref,
                FiscalFeedbackLinkRef,
            ),
            audit_refs=upstream_audit_refs,
            actionable_side_information_refs=actionable_side_information_refs,
            metadata={
                "candidate_hash": source.candidate_hash,
                "judge_composite_decision": (
                    source.judge_verdict.composite_decision if source.judge_verdict else None
                ),
                "claims_ref": str(claims_ref.artifact_id),
                **claim_summary_metadata,
            },
        )
        return persist_policy_artifact_bundle(
            store,
            bundle,
            inputs=_bundle_inputs(source),
        )

    def _persist_claim_ledger(
        self,
        *,
        store: FileSystemCAS,
        source: PolicyArtifactBuildInput,
        refs: dict[str, ArtifactRef],
        phase3_gate: Phase3CertificateStatus,
    ) -> ArtifactRef:
        readiness_level = (
            source.readiness_contract.readiness_level
            if source.readiness_contract is not None
            else DecisionReadiness.RESEARCH_ARTIFACT
        )
        projection_payload = {
            "candidate_id": source.candidate.candidate_id,
            "decision_readiness_contract_ref": (
                None if source.readiness_ref is None else source.readiness_ref.model_dump(mode="json")
            ),
            "phase3_gate": phase3_gate.model_dump(mode="json"),
            **{key: ref.model_dump(mode="json") for key, ref in refs.items()},
        }
        source_refs = _dedupe_artifact_refs(
            [
                *refs.values(),
                *source.audit_refs,
                *source.actionable_side_information_refs,
            ]
        )
        ledger = project_policy_artifact_bundle_claims(
            projection_payload,
            run_id=source.run_id,
            source_artifact_refs=source_refs,
            readiness_level=readiness_level,
        )
        return persist_claim_ledger(store, ledger, inputs=_bundle_inputs(source))

    def _validate_contract_bound_source(
        self,
        store: FileSystemCAS,
        source: PolicyArtifactBuildInput,
    ) -> None:
        promoted = bool(
            source.promotion_result is not None
            and source.promotion_result.promotion_decision.promoted
        )
        readiness = source.readiness_contract
        if promoted and readiness is None:
            raise ValueError(
                "Promoted policy bundles require a DecisionReadinessContract before assembly."
            )
        if promoted and source.readiness_ref is None:
            raise ValueError(
                "Promoted policy bundles require a persisted DecisionReadinessContract ref."
            )
        if source.evaluation_vector is None and promoted:
            raise ValueError(
                "Promoted policy bundles require a PolicyEvaluationVector for audit completeness."
            )
        phase3_gate = source.phase3_gate or (
            source.readiness_contract.phase3_gate if source.readiness_contract is not None else None
        )
        if phase3_gate is None or not phase3_gate.gate_passed:
            blocking = [] if phase3_gate is None else list(phase3_gate.blocking_reasons)
            raise ValueError(
                "Policy artifact bundles require a complete Phase 3 certificate package before assembly."
                + ("" if not blocking else f" Blocking reasons: {', '.join(blocking)}")
            )
        phase3_ref_blockers = phase3_gate_reference_blockers(store, phase3_gate)
        if phase3_ref_blockers:
            raise ValueError(
                "Policy artifact bundles require loadable Phase 3 certificate refs before assembly."
                + f" Blocking reasons: {', '.join(phase3_ref_blockers)}"
            )
        brief_required = self._brief_required(readiness)
        if brief_required and source.policy_brief is None:
            raise ValueError(
                "Readiness EXTERNAL_BRIEFING and above requires an explicit PolicyBrief."
            )
        if brief_required and source.translator_compliance is None:
            raise ValueError(
                "Readiness EXTERNAL_BRIEFING and above requires TranslatorCompliance output."
            )
        if (
            brief_required
            and source.translator_compliance is not None
            and not bool(getattr(source.translator_compliance, "passed", False))
        ):
            raise ValueError("PolicyBrief failed TranslatorCompliancePass and cannot be bundled.")

    def _brief_required(
        self,
        readiness: DecisionReadinessContract | None,
    ) -> bool:
        if readiness is None:
            return False
        ordered_levels = [
            DecisionReadiness.RESEARCH_ARTIFACT,
            DecisionReadiness.ANALYST_ADVISORY,
            DecisionReadiness.EXTERNAL_BRIEFING,
            DecisionReadiness.SIMULATION_READY,
            DecisionReadiness.RECOMMENDATION_READY,
            DecisionReadiness.DEPLOYMENT_READY,
        ]
        return ordered_levels.index(readiness.readiness_level) >= ordered_levels.index(
            DecisionReadiness.EXTERNAL_BRIEFING
        )

    def _build_frontier_report(self, source: PolicyArtifactBuildInput) -> PolicyFrontierReport:
        snapshot = source.pareto_snapshot
        if snapshot is None:
            return PolicyFrontierReport(loop_id=source.loop_id)
        global_hashes = snapshot.frontiers.get("global_feasible", [])
        entries: list[PolicyFrontierEntry] = []
        for candidate_hash in global_hashes:
            entry = snapshot.entries.get(candidate_hash)
            if entry is None:
                continue
            readiness_level = None
            if candidate_hash == source.candidate_hash and source.readiness_contract is not None:
                readiness_level = source.readiness_contract.readiness_level.value
            entries.append(
                PolicyFrontierEntry(
                    candidate_hash=entry.candidate_hash,
                    candidate_id=entry.candidate_id,
                    policy_family=entry.policy_family,
                    view_membership=list(entry.view_membership),
                    primary_objectives={
                        name: channel.value for name, channel in entry.evaluation.primary.items()
                    },
                    constraint_statuses={
                        name: status.value
                        for name, status in entry.evaluation.constraint_statuses.items()
                    },
                    readiness_level=readiness_level,
                    metadata=dict(entry.metadata),
                )
            )
        return PolicyFrontierReport(
            loop_id=snapshot.loop_id,
            global_frontier=entries,
            view_membership={key: list(value) for key, value in snapshot.frontiers.items()},
            metadata={"hypervolume_by_view": dict(snapshot.hypervolume_by_view)},
        )

    def _build_constraint_report(
        self,
        source: PolicyArtifactBuildInput,
    ) -> ConstraintSatisfactionReport:
        evaluation = source.evaluation_vector
        if evaluation is None:
            return ConstraintSatisfactionReport(
                candidate_id=source.candidate.candidate_id,
                feasible=False,
                findings=["policy_evaluation_missing"],
                metadata={"not_assessed": True},
            )
        entries = [
            ConstraintSatisfactionEntry(
                constraint_name=name,
                status=(channel.status.value if channel.status is not None else "not_assessed"),
                observed_value=channel.value,
                threshold=channel.threshold,
                margin=channel.margin,
                source=channel.source,
            )
            for name, channel in evaluation.hard_constraints.items()
        ]
        return ConstraintSatisfactionReport(
            candidate_id=source.candidate.candidate_id,
            feasible=evaluation.feasible,
            blocking_reasons=list(evaluation.blocking_reasons),
            constraints=entries,
            findings=list(source.constraint_findings),
            metadata={"policy_family": source.metadata.get("policy_family")},
        )

    def _build_subgroup_report(
        self,
        source: PolicyArtifactBuildInput,
    ) -> SubgroupImpactReport:
        report = source.distributional_report
        if report is None:
            return SubgroupImpactReport(
                candidate_id=source.candidate.candidate_id,
                notes=["distributional_report_missing"],
            )
        harmed: list[SubgroupImpactEntry] = []
        benefiting: list[SubgroupImpactEntry] = []
        for breakdown in report.breakdowns:
            for cohort in breakdown.cohorts:
                entry = SubgroupImpactEntry(
                    subgroup_id=cohort.cohort_id,
                    label=cohort.cohort_label,
                    direction=cohort.impact_direction.value,
                    net_impact=float(next(iter(cohort.metric_deltas.values()), 0.0)),
                    vulnerable=bool(cohort.is_vulnerable),
                )
                if cohort.impact_direction is ImpactDirection.NEGATIVE:
                    harmed.append(entry)
                else:
                    benefiting.append(entry)
        inequality_delta = None
        if report.overall_gini_before is not None and report.overall_gini_after is not None:
            inequality_delta = float(report.overall_gini_after - report.overall_gini_before)
        return SubgroupImpactReport(
            candidate_id=source.candidate.candidate_id,
            harmed_subgroups=harmed,
            benefiting_subgroups=benefiting,
            inequality_delta=inequality_delta,
        )

    def _build_uncertainty_report(
        self,
        source: PolicyArtifactBuildInput,
    ) -> UncertaintyReport:
        envelope = source.uncertainty_envelope
        readiness_level = (
            source.readiness_contract.readiness_level.value
            if source.readiness_contract is not None
            else "research_artifact"
        )
        if envelope is None:
            return UncertaintyReport(
                candidate_id=source.candidate.candidate_id,
                readiness_level=readiness_level,
                summary_notes=["uncertainty_envelope_missing"],
            )
        uncertainties = {
            uncertainty_type.value: estimate.level
            for uncertainty_type, estimate in envelope.uncertainties.items()
        }
        binding_types = [
            uncertainty_type.value
            for uncertainty_type, estimate in envelope.uncertainties.items()
            if estimate.level >= 0.5
        ]
        return UncertaintyReport(
            candidate_id=source.candidate.candidate_id,
            readiness_level=readiness_level,
            uncertainties=uncertainties,
            binding_types=binding_types,
            summary_notes=[f"{key}={value:.3f}" for key, value in sorted(uncertainties.items())],
        )

    def _build_transportability_report(
        self,
        source: PolicyArtifactBuildInput,
    ) -> TransportabilityReport:
        profile = source.cross_graph_profile
        if profile is None:
            return TransportabilityReport(
                candidate_id=source.candidate.candidate_id,
                evidence_depth=str(
                    source.candidate.metadata.get("evidence_depth") or "single_study"
                ),
                transport_status="not_assessed",
                caveats=[
                    assumption.description for assumption in source.candidate.transport_assumptions
                ],
            )
        statuses = {assessment.transport_status for assessment in profile.needs}
        if TransportStatus.UNSUPPORTED in statuses:
            status = TransportStatus.UNSUPPORTED.value
        elif TransportStatus.BOUNDED_NON_IDENTIFIED in statuses:
            status = TransportStatus.BOUNDED_NON_IDENTIFIED.value
        elif TransportStatus.PARTIALLY_IDENTIFIED in statuses:
            status = TransportStatus.PARTIALLY_IDENTIFIED.value
        elif TransportStatus.IDENTIFIED in statuses:
            status = TransportStatus.IDENTIFIED.value
        else:
            status = "not_assessed"
        unsupported = [
            assessment.need.need_id
            for assessment in profile.needs
            if assessment.transport_status
            in {
                TransportStatus.UNSUPPORTED,
                TransportStatus.BOUNDED_NON_IDENTIFIED,
                TransportStatus.PARTIALLY_IDENTIFIED,
            }
        ]
        caveats = [assumption.description for assumption in source.candidate.transport_assumptions]
        for assumption in source.candidate.transport_assumptions:
            caveats.extend(assumption.caveats)
        for source_name, source_status in profile.source_statuses.items():
            if getattr(source_status, "status", None) == "available":
                continue
            status_value = getattr(getattr(source_status, "status", None), "value", None) or str(
                getattr(source_status, "status", "unknown")
            )
            caveats.append(f"Evidence channel unavailable: {source_name} ({status_value}).")
        return TransportabilityReport(
            candidate_id=source.candidate.candidate_id,
            evidence_depth=str(source.candidate.metadata.get("evidence_depth") or "single_study"),
            transport_status=status,
            unsupported_needs=unsupported,
            caveats=_dedupe_text(caveats),
        )

    def _build_governance_gate_packet(
        self,
        source: PolicyArtifactBuildInput,
    ) -> GovernanceGatePacket:
        verdict = source.judge_verdict
        readiness_level = (
            source.readiness_contract.readiness_level.value
            if source.readiness_contract is not None
            else "research_artifact"
        )
        compliance_passed = None
        compliance_failures: list[str] = []
        if source.translator_compliance is not None:
            compliance_passed = bool(getattr(source.translator_compliance, "passed", False))
            compliance_failures = [
                str(getattr(item, "code", item))
                for item in getattr(source.translator_compliance, "findings", [])
            ]
        phase3_gate = source.phase3_gate or (
            source.readiness_contract.phase3_gate
            if source.readiness_contract is not None
            else Phase3CertificateStatus.missing()
        )
        critical_failures = [
            card.description for card in (verdict.blocking_failures if verdict is not None else [])
        ]
        if not phase3_gate.gate_passed:
            critical_failures.extend(phase3_gate.blocking_reasons)
        return GovernanceGatePacket(
            candidate_id=source.candidate.candidate_id,
            judge_composite_decision=(
                verdict.composite_decision if verdict is not None else "not_assessed"
            ),
            readiness_level=readiness_level,
            governance_issues=list(source.constraint_findings),
            critical_failures=_dedupe_text(critical_failures),
            warnings=[
                card.description for card in (verdict.warnings if verdict is not None else [])
            ],
            translator_compliance_passed=compliance_passed,
            translator_compliance_failures=compliance_failures,
            defer_to_human=(
                verdict.composite_decision == "defer_to_human" if verdict is not None else False
            ),
            phase3_gate=phase3_gate,
            metadata={"mutation_hints": list(source.mutation_hints)},
        )

    def _build_implementation_plan(
        self,
        source: PolicyArtifactBuildInput,
    ) -> ImplementationPlan:
        actions = [
            RecommendedAction(
                title="Monitor rollout gates",
                description="Track monitoring signals and rollback triggers during deployment.",
                priority="high",
            )
        ]
        if source.candidate.expected_harm_envelope.rollback_triggers:
            actions.append(
                RecommendedAction(
                    title="Prepare rollback path",
                    description=(
                        "Rollback triggers: "
                        + ", ".join(source.candidate.expected_harm_envelope.rollback_triggers)
                    ),
                    priority="high",
                )
            )
        return ImplementationPlan(
            candidate_id=source.candidate.candidate_id,
            rollout_steps=list(source.candidate.rollout_plan),
            monitoring_plan=list(source.candidate.monitoring_plan),
            fallback_variant_ids=[
                variant.variant_id for variant in source.candidate.fallback_variants
            ],
            recommended_actions=actions,
        )

    def _build_rejected_alternatives(
        self,
        source: PolicyArtifactBuildInput,
    ) -> RejectedAlternativesSummary:
        snapshot = source.pareto_snapshot
        if snapshot is None:
            return RejectedAlternativesSummary(loop_id=source.loop_id)
        frontier = set(snapshot.frontiers.get("global_feasible", []))
        alternatives: list[RejectedAlternativeEntry] = []
        reasons: list[str] = []
        for candidate_hash, entry in snapshot.entries.items():
            if candidate_hash == source.candidate_hash:
                continue
            if candidate_hash in frontier:
                continue
            near_frontier = (
                source.evaluation_vector is not None
                and self._reporting_distance_from_selected(
                    entry.evaluation,
                    source.evaluation_vector,
                )
                <= 5.0
            )
            reason = (
                "infeasible"
                if not entry.evaluation.feasible
                else "dominated_near_frontier"
                if near_frontier
                else "dominated"
            )
            reasons.append(reason)
            alternatives.append(
                RejectedAlternativeEntry(
                    candidate_hash=candidate_hash,
                    candidate_id=entry.candidate_id,
                    policy_family=entry.policy_family,
                    reason=reason,
                    near_frontier=reason == "dominated_near_frontier",
                )
            )
        return RejectedAlternativesSummary(
            loop_id=source.loop_id,
            alternatives=alternatives[:20],
            dominant_rejection_reasons=sorted(set(reasons)),
        )

    def _reporting_distance_from_selected(
        self,
        candidate_evaluation,
        selected_evaluation,
    ) -> float:
        candidate_axes = candidate_evaluation.frontier_objectives("global_feasible")
        selected_axes = selected_evaluation.frontier_objectives("global_feasible")
        shared_axes = sorted(set(candidate_axes) & set(selected_axes))
        if not shared_axes:
            return float("inf")
        gap = sum(
            abs(float(selected_axes[axis]) - float(candidate_axes[axis])) for axis in shared_axes
        )
        return gap / max(len(shared_axes), 1)

    def _build_dossier(
        self,
        *,
        source: PolicyArtifactBuildInput,
        constraint_report: ConstraintSatisfactionReport,
        subgroup_report: SubgroupImpactReport,
        uncertainty_report: UncertaintyReport,
        transport_report: TransportabilityReport,
        gate_packet: GovernanceGatePacket,
        implementation_plan: ImplementationPlan,
    ) -> ChampionPolicyDossier:
        evaluation = source.evaluation_vector
        objective_summary = {
            name: channel.value
            for name, channel in (evaluation.primary.items() if evaluation else [])
        }
        recommended_actions = list(implementation_plan.recommended_actions)
        if gate_packet.defer_to_human:
            recommended_actions.append(
                RecommendedAction(
                    title="Human review required",
                    description="Escalate to a human reviewer before any external deployment.",
                    priority="high",
                )
            )
        readiness_level = (
            source.readiness_contract.readiness_level.value
            if source.readiness_contract is not None
            else "research_artifact"
        )
        return ChampionPolicyDossier(
            candidate_id=source.candidate.candidate_id,
            candidate_hash=source.candidate_hash,
            readiness_level=readiness_level,
            executive_summary=(
                f"Candidate {source.candidate.candidate_id} is assessed at {readiness_level} "
                f"with {len(constraint_report.blocking_reasons)} blocking reasons."
            ),
            objective_summary=objective_summary,
            constraint_summary=list(constraint_report.constraints),
            subgroup_harms=[item.label for item in subgroup_report.harmed_subgroups],
            surfaced_assumptions=(
                list(source.readiness_contract.assumptions_must_be_surfaced)
                if source.readiness_contract is not None
                else []
            ),
            uncertainty_summary=dict(uncertainty_report.uncertainties),
            transport_summary=transport_report.model_dump(mode="json"),
            governance_summary=gate_packet.model_dump(mode="json"),
            stress_summary=(
                source.stress_test_report.model_dump(mode="json")
                if source.stress_test_report is not None
                else {}
            ),
            calibration_validation_summary=(
                source.calibration_validation_bundle.readout_summary()
                if source.calibration_validation_bundle is not None
                else {}
            ),
            accountability_summary=(
                dict(source.calibration_validation_bundle.governance_accountability_summary)
                if source.calibration_validation_bundle is not None
                else {}
            ),
            recommended_actions=recommended_actions,
            metadata={
                "candidate_metadata": dict(source.candidate.metadata),
                "calibration_validation_bundle_ref": (
                    None
                    if source.calibration_validation_bundle_ref is None
                    else str(source.calibration_validation_bundle_ref.artifact_id)
                ),
                "governance_accountability_artifact_ref": (
                    None
                    if source.calibration_validation_bundle is None
                    or source.calibration_validation_bundle.governance_accountability_ref is None
                    else str(
                        source.calibration_validation_bundle.governance_accountability_ref.artifact_id
                    )
                ),
            },
        )

    def _build_replayable_audit_bundle(
        self,
        *,
        source: PolicyArtifactBuildInput,
        refs: dict[str, ArtifactRef],
        upstream_audit_refs: list[ArtifactRef],
        actionable_side_information_refs: list[ArtifactRef],
    ) -> ReplayableAuditBundle:
        trace_notes = list(source.constraint_findings)
        trace_notes.extend(source.mutation_hints)
        if source.stress_test_report is not None:
            trace_notes.append(
                f"stress_vulnerabilities={len(source.stress_test_report.vulnerabilities)}"
            )
        return ReplayableAuditBundle(
            run_id=source.run_id,
            candidate_ref=source.candidate_ref,
            evaluation_ref=source.evaluation_ref,
            readiness_ref=source.readiness_ref,
            workflow_id=str(source.metadata.get("workflow_id") or "") or None,
            execution_profile=source.execution_profile,
            runtime_input_refs=dict(source.runtime_input_refs),
            runtime_artifacts_index=dict(source.runtime_artifacts_index),
            runtime_reports_index=dict(source.runtime_reports_index),
            runtime_params_snapshot=dict(source.runtime_params_snapshot),
            upstream_audit_refs=upstream_audit_refs,
            actionable_side_information_refs=actionable_side_information_refs,
            artifact_refs=refs,
            trace_notes=_dedupe_text(trace_notes),
        )


def persist_policy_frontier_report(
    store: FileSystemCAS,
    payload: PolicyFrontierReport,
    *,
    inputs: list[InputRef] | None = None,
) -> PolicyFrontierReportRef:
    """Persist the policy frontier snapshot and return its typed artifact reference."""
    return _persist_model(
        store,
        payload,
        kind="scientist.policy_frontier_report",
        schema_name="polisyos.scientist.policy_design.PolicyFrontierReport",
        ref_cls=PolicyFrontierReportRef,
        inputs=inputs,
    )


def persist_champion_policy_dossier(
    store: FileSystemCAS,
    payload: ChampionPolicyDossier,
    *,
    inputs: list[InputRef] | None = None,
) -> ChampionPolicyDossierRef:
    """Persist the champion dossier used for promotion and downstream briefing flows."""
    return _persist_model(
        store,
        payload,
        kind="scientist.champion_policy_dossier",
        schema_name="polisyos.scientist.policy_design.ChampionPolicyDossier",
        ref_cls=ChampionPolicyDossierRef,
        inputs=inputs,
    )


def persist_policy_brief(
    store: FileSystemCAS,
    payload: PolicyBrief,
    *,
    inputs: list[InputRef] | None = None,
) -> PolicyBriefRef:
    """Persist the reader-facing policy brief assembled for external or analyst consumption."""
    return _persist_model(
        store,
        payload,
        kind="scientist.policy_brief",
        schema_name="polisyos.scientist.policy_design.PolicyBrief",
        ref_cls=PolicyBriefRef,
        inputs=inputs,
    )


def persist_constraint_satisfaction_report(
    store: FileSystemCAS,
    payload: ConstraintSatisfactionReport,
    *,
    inputs: list[InputRef] | None = None,
) -> ConstraintSatisfactionReportRef:
    """Persist the candidate feasibility report and return its typed artifact reference."""
    return _persist_model(
        store,
        payload,
        kind="scientist.constraint_satisfaction_report",
        schema_name="polisyos.scientist.policy_design.ConstraintSatisfactionReport",
        ref_cls=ConstraintSatisfactionReportRef,
        inputs=inputs,
    )


def persist_subgroup_impact_report(
    store: FileSystemCAS,
    payload: SubgroupImpactReport,
    *,
    inputs: list[InputRef] | None = None,
) -> SubgroupImpactReportRef:
    """Persist the subgroup-impact review used by equity and governance gates."""
    return _persist_model(
        store,
        payload,
        kind="scientist.subgroup_impact_report",
        schema_name="polisyos.scientist.policy_design.SubgroupImpactReport",
        ref_cls=SubgroupImpactReportRef,
        inputs=inputs,
    )


def persist_uncertainty_report(
    store: FileSystemCAS,
    payload: UncertaintyReport,
    *,
    inputs: list[InputRef] | None = None,
) -> UncertaintyReportRef:
    """Persist the uncertainty summary that feeds readiness and promotion decisions."""
    return _persist_model(
        store,
        payload,
        kind="scientist.uncertainty_report",
        schema_name="polisyos.scientist.policy_design.UncertaintyReport",
        ref_cls=UncertaintyReportRef,
        inputs=inputs,
    )


def persist_transportability_report(
    store: FileSystemCAS,
    payload: TransportabilityReport,
    *,
    inputs: list[InputRef] | None = None,
) -> TransportabilityReportRef:
    """Persist the transportability assessment for the candidate's supporting evidence."""
    return _persist_model(
        store,
        payload,
        kind="scientist.transportability_report",
        schema_name="polisyos.scientist.policy_design.TransportabilityReport",
        ref_cls=TransportabilityReportRef,
        inputs=inputs,
    )


def persist_governance_gate_packet(
    store: FileSystemCAS,
    payload: GovernanceGatePacket,
    *,
    inputs: list[InputRef] | None = None,
) -> GovernanceGatePacketRef:
    """Persist the governance packet that captures readiness, warnings, and escalation needs."""
    return _persist_model(
        store,
        payload,
        kind="scientist.governance_gate_packet",
        schema_name="polisyos.scientist.policy_design.GovernanceGatePacket",
        ref_cls=GovernanceGatePacketRef,
        inputs=inputs,
    )


def persist_implementation_plan(
    store: FileSystemCAS,
    payload: ImplementationPlan,
    *,
    inputs: list[InputRef] | None = None,
) -> ImplementationPlanRef:
    """Persist the rollout and monitoring plan for the selected policy candidate."""
    return _persist_model(
        store,
        payload,
        kind="scientist.implementation_plan",
        schema_name="polisyos.scientist.policy_design.ImplementationPlan",
        ref_cls=ImplementationPlanRef,
        inputs=inputs,
    )


def persist_rejected_alternatives_summary(
    store: FileSystemCAS,
    payload: RejectedAlternativesSummary,
    *,
    inputs: list[InputRef] | None = None,
) -> RejectedAlternativesSummaryRef:
    """Persist the rejected-alternatives summary used for learning across future search loops."""
    return _persist_model(
        store,
        payload,
        kind="scientist.rejected_alternatives_summary",
        schema_name="polisyos.scientist.policy_design.RejectedAlternativesSummary",
        ref_cls=RejectedAlternativesSummaryRef,
        inputs=inputs,
    )


def persist_replayable_audit_bundle(
    store: FileSystemCAS,
    payload: ReplayableAuditBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> ReplayableAuditBundleRef:
    """Persist the replayable audit bundle that rehydrates a policy decision end to end."""
    return _persist_model(
        store,
        payload,
        kind="scientist.replayable_audit_bundle",
        schema_name="polisyos.scientist.policy_design.ReplayableAuditBundle",
        ref_cls=ReplayableAuditBundleRef,
        inputs=inputs,
    )


def persist_policy_artifact_bundle(
    store: FileSystemCAS,
    payload: PolicyArtifactBundle,
    *,
    inputs: list[InputRef] | None = None,
) -> PolicyArtifactBundleRef:
    """Persist the final policy artifact bundle that ties all promotion outputs together."""
    return _persist_model(
        store,
        payload,
        kind="scientist.policy_artifact_bundle",
        schema_name="polisyos.scientist.policy_design.PolicyArtifactBundle",
        ref_cls=PolicyArtifactBundleRef,
        inputs=inputs,
    )


def load_policy_frontier_report(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> PolicyFrontierReport:
    """Load policy frontier report."""
    return _load_model(store, ref, PolicyFrontierReport)


def load_champion_policy_dossier(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> ChampionPolicyDossier:
    """Load champion policy dossier."""
    return _load_model(store, ref, ChampionPolicyDossier)


def load_policy_brief(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> PolicyBrief:
    """Load policy brief."""
    return _load_model(store, ref, PolicyBrief)


def load_constraint_satisfaction_report(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> ConstraintSatisfactionReport:
    """Load constraint satisfaction report."""
    return _load_model(store, ref, ConstraintSatisfactionReport)


def load_subgroup_impact_report(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> SubgroupImpactReport:
    """Load subgroup impact report."""
    return _load_model(store, ref, SubgroupImpactReport)


def load_uncertainty_report(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> UncertaintyReport:
    """Load uncertainty report."""
    return _load_model(store, ref, UncertaintyReport)


def load_transportability_report(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> TransportabilityReport:
    """Load transportability report."""
    return _load_model(store, ref, TransportabilityReport)


def load_governance_gate_packet(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> GovernanceGatePacket:
    """Load governance gate packet."""
    return _load_model(store, ref, GovernanceGatePacket)


def load_implementation_plan(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> ImplementationPlan:
    """Load implementation plan."""
    return _load_model(store, ref, ImplementationPlan)


def load_rejected_alternatives_summary(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> RejectedAlternativesSummary:
    """Load rejected alternatives summary."""
    return _load_model(store, ref, RejectedAlternativesSummary)


def load_replayable_audit_bundle(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> ReplayableAuditBundle:
    """Load replayable audit bundle."""
    return _load_model(store, ref, ReplayableAuditBundle)


def load_policy_artifact_bundle(
    store: FileSystemCAS,
    ref: ArtifactRef,
) -> PolicyArtifactBundle:
    """Load policy artifact bundle."""
    return _load_model(store, ref, PolicyArtifactBundle)


def _persist_model(
    store: FileSystemCAS,
    payload: BaseModel,
    *,
    kind: str,
    schema_name: str,
    ref_cls: type[ArtifactRef],
    inputs: list[InputRef] | None,
) -> ArtifactRef:
    ref = store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=str(payload.schema_version)),
            inputs=list(inputs or []),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ref_cls.model_validate(ref.model_dump())


def _load_model(store: FileSystemCAS, ref: ArtifactRef, model_cls: type[BaseModel]) -> Any:
    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return model_cls.model_validate(payload)


def _bundle_inputs(source: PolicyArtifactBuildInput) -> list[InputRef]:
    inputs: list[InputRef] = []
    if source.candidate_ref is not None:
        inputs.append(InputRef(artifact_id=source.candidate_ref.artifact_id, role="candidate"))
    if source.evaluation_ref is not None:
        inputs.append(InputRef(artifact_id=source.evaluation_ref.artifact_id, role="evaluation"))
    if source.readiness_ref is not None:
        inputs.append(InputRef(artifact_id=source.readiness_ref.artifact_id, role="readiness"))
    if source.stress_test_report_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=source.stress_test_report_ref.artifact_id,
                role="stress_test_report",
            )
        )
    if source.calibration_validation_bundle_ref is not None:
        inputs.append(
            InputRef(
                artifact_id=source.calibration_validation_bundle_ref.artifact_id,
                role="calibration_validation_bundle",
            )
        )
    if (
        source.calibration_validation_bundle is not None
        and source.calibration_validation_bundle.governance_accountability_ref is not None
    ):
        inputs.append(
            InputRef(
                artifact_id=source.calibration_validation_bundle.governance_accountability_ref.artifact_id,
                role="governance_accountability_artifact",
            )
        )
    for index, ref in enumerate(_dedupe_artifact_refs(source.audit_refs)):
        inputs.append(
            InputRef(
                artifact_id=ref.artifact_id,
                role=f"upstream_audit_ref_{index}",
            )
        )
    for index, ref in enumerate(_dedupe_artifact_refs(source.actionable_side_information_refs)):
        inputs.append(
            InputRef(
                artifact_id=ref.artifact_id,
                role=f"actionable_side_information_ref_{index}",
            )
        )
    return inputs


def _brief_from_dossier(dossier: ChampionPolicyDossier) -> PolicyBrief:
    risks = [
        PolicyRiskNote(
            title="Subgroup harm",
            severity="warning",
            description=harm,
            impacted_groups=[harm],
        )
        for harm in dossier.subgroup_harms
    ]
    tradeoffs = [
        TradeoffRow(
            axis=name,
            champion_value=f"{value:.4f}",
            rationale=f"Technical dossier objective {name} = {value:.4f}.",
        )
        for name, value in sorted(dossier.objective_summary.items())
    ]
    hard_constraint_notes = [
        item.constraint_name for item in dossier.constraint_summary if item.status != "feasible"
    ]
    uncertainty_highlights = [
        f"{name}: {value:.3f}" for name, value in sorted(dossier.uncertainty_summary.items())
    ]
    return PolicyBrief(
        title=f"Policy brief for {dossier.candidate_id}",
        executive_summary=dossier.executive_summary,
        readiness_level=dossier.readiness_level,
        surfaced_assumptions=list(dossier.surfaced_assumptions),
        uncertainty_highlights=uncertainty_highlights,
        subgroup_harms=list(dossier.subgroup_harms),
        hard_constraint_notes=hard_constraint_notes,
        tradeoffs=tradeoffs,
        risks=risks,
        recommended_actions=list(dossier.recommended_actions),
        metadata={
            "generated_by": "deterministic_policy_brief",
            "synthesized_from_dossier": True,
            "contract_bound_source": False,
        },
    )


def _dedupe_text(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _dedupe_artifact_refs(items: list[ArtifactRef]) -> list[ArtifactRef]:
    output: list[ArtifactRef] = []
    seen: set[str] = set()
    for item in items:
        artifact_id = str(item.artifact_id)
        if artifact_id in seen:
            continue
        seen.add(artifact_id)
        output.append(item)
    return output


def _claim_summary_metadata(store: FileSystemCAS, claims_ref: ArtifactRef) -> dict[str, Any]:
    try:
        ledger = load_claim_ledger(store, claims_ref)
    except (OSError, RuntimeError, TypeError, ValueError):
        return {
            "claim_ledger_summary": {
                "lifecycle_status": "legacy_missing",
                "load_status": "unavailable",
            },
            "blocked_claim_summary": {
                "lifecycle_status": "legacy_missing",
                "blocked_count": 0,
                "blocked_claims": [],
                "superseded_claim_ids": [],
            },
        }
    return {
        "claim_ledger_summary": claim_ledger_summary(ledger),
        "blocked_claim_summary": blocked_claim_summary(ledger),
    }


def _maybe_validate_ref(ref: ArtifactRef | None, ref_cls: type[ArtifactRef]) -> ArtifactRef | None:
    if ref is None:
        return None
    return ref_cls.model_validate(ref.model_dump())


__all__ = [
    "ChampionPolicyDossier",
    "ConstraintSatisfactionEntry",
    "ConstraintSatisfactionReport",
    "GovernanceGatePacket",
    "ImplementationPlan",
    "PolicyArtifactBuildInput",
    "PolicyArtifactBuilder",
    "PolicyArtifactBundle",
    "PolicyBrief",
    "PolicyFrontierEntry",
    "PolicyFrontierReport",
    "PolicyRiskNote",
    "RecommendedAction",
    "RejectedAlternativeEntry",
    "RejectedAlternativesSummary",
    "ReplayableAuditBundle",
    "SubgroupImpactEntry",
    "SubgroupImpactReport",
    "TradeoffRow",
    "TransportabilityReport",
    "UncertaintyReport",
    "load_champion_policy_dossier",
    "load_constraint_satisfaction_report",
    "load_governance_gate_packet",
    "load_implementation_plan",
    "load_policy_artifact_bundle",
    "load_policy_brief",
    "load_policy_frontier_report",
    "load_rejected_alternatives_summary",
    "load_replayable_audit_bundle",
    "load_subgroup_impact_report",
    "load_transportability_report",
    "load_uncertainty_report",
    "persist_champion_policy_dossier",
    "persist_constraint_satisfaction_report",
    "persist_governance_gate_packet",
    "persist_implementation_plan",
    "persist_policy_artifact_bundle",
    "persist_policy_brief",
    "persist_policy_frontier_report",
    "persist_rejected_alternatives_summary",
    "persist_replayable_audit_bundle",
    "persist_subgroup_impact_report",
    "persist_transportability_report",
    "persist_uncertainty_report",
]

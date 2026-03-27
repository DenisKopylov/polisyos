"""
Typed references for Scientist layer artifacts.

These provide type-safe references to CAS-stored artifacts,
enabling static analysis and IDE support while maintaining
the content-addressable architecture.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..artifacts.manifest import ArtifactRef


@runtime_checkable
class FailureCardLike(Protocol):
    """Minimal FailureCard surface required to build FailureCardRef."""

    content_hash: str
    attempt_number: int
    error_code: str
    source_step: Any
    can_retry: bool


class ScientistArtifactRef(ArtifactRef):
    """Base class for Scientist artifact references.

    Accepts legacy fields (cas_hash/ref_type/artifact_type) for backward compatibility.
    """

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "artifact_id" not in data and data.get("cas_hash"):
            data = dict(data)
            data["artifact_id"] = data["cas_hash"]
        if "kind" not in data:
            legacy_type = data.get("ref_type") or data.get("artifact_type")
            if legacy_type:
                data = dict(data)
                data["kind"] = f"scientist.{legacy_type}"
        if "media_type" not in data:
            data = dict(data)
            data["media_type"] = "application/json"
        return data


class ExperimentStateRef(ScientistArtifactRef):
    kind: Literal["scientist.experiment_state"] = "scientist.experiment_state"
    media_type: Literal["application/json"] = "application/json"


class DecisionPacketRef(ScientistArtifactRef):
    kind: Literal["scientist.decision_packet"] = "scientist.decision_packet"
    media_type: Literal["application/json"] = "application/json"


class GovernanceReportRef(ScientistArtifactRef):
    kind: Literal["scientist.governance_report"] = "scientist.governance_report"
    media_type: Literal["application/json"] = "application/json"


class FailureCardRef(ScientistArtifactRef):
    """
    Typed reference to a FailureCard artifact in CAS.

    Used in state schemas to reference failure history without
    embedding full FailureCard objects in workflow state.
    """

    kind: Literal["scientist.failure_card"] = "scientist.failure_card"
    media_type: Literal["application/json"] = "application/json"

    # Denormalized fields for quick filtering without CAS lookup
    attempt_number: int = Field(ge=1, description="Which retry attempt this represents")
    error_code: str = Field(description="Error code for quick categorization")
    source_step: str = Field(description="Origin of the failure")
    can_retry: bool = Field(description="Whether this failure allowed retry")

    @classmethod
    def from_card(cls, card: FailureCardLike) -> "FailureCardRef":
        """Create a reference from a FailureCard instance."""
        source_step = getattr(card.source_step, "value", card.source_step)
        return cls(
            artifact_id=card.content_hash,
            attempt_number=card.attempt_number,
            error_code=card.error_code,
            source_step=str(source_step),
            can_retry=card.can_retry,
        )


class TrinityIRRef(ScientistArtifactRef):
    """Reference to a canonical Trinity IR artifact."""

    kind: Literal["scientist.policy_ir"] = "scientist.policy_ir"
    media_type: Literal["application/json"] = "application/json"

    version: int = Field(ge=1, description="Revision number of this IR")
    status: str = Field(description="Current status: draft, validated, rejected")


class CritiqueRef(ScientistArtifactRef):
    """Reference to a Critic evaluation artifact."""

    kind: Literal["scientist.critique"] = "scientist.critique"
    media_type: Literal["application/json"] = "application/json"

    verdict: str = Field(description="Critic's verdict: approve, revise, reject")
    ir_ref: str = Field(description="CAS hash of the evaluated IR")


class TimelineRef(ScientistArtifactRef):
    """
    Reference to a stored RunTimeline artifact.

    Note: In Scientist contracts we use CAS-addressed references (artifact_id).
    """

    kind: Literal["scientist.run_timeline"] = "scientist.run_timeline"
    media_type: Literal["application/json"] = "application/json"

    # Denormalized for quick filtering
    run_id: str = Field(description="Associated run id")
    event_count: int = Field(ge=0, description="Number of timeline events")
    total_duration_ms: int = Field(ge=0, description="Total run duration, ms")


class DecisionCardRef(ScientistArtifactRef):
    """Reference to a stored DecisionCard artifact."""

    kind: Literal["scientist.decision_card"] = "scientist.decision_card"
    media_type: Literal["application/json"] = "application/json"

    run_id: str = Field(description="Associated run id")
    verdict: str = Field(description="Decision verdict")
    generated_at: str = Field(description="Card generation timestamp (ISO 8601)")


class CheckpointRef(ScientistArtifactRef):
    """Reference to a stored Scientist checkpoint artifact."""

    kind: Literal["scientist.checkpoint"] = "scientist.checkpoint"
    media_type: Literal["application/json"] = "application/json"

    run_id: str = Field(description="Associated run id")
    sequence_number: int = Field(ge=0, description="Checkpoint sequence number")
    node_alias: str = Field(description="Last completed node alias")


class SensitivityResultRef(ScientistArtifactRef):
    """Reference to a stored sensitivity analysis result artifact."""

    kind: Literal["scientist.sensitivity_result"] = "scientist.sensitivity_result"
    media_type: Literal["application/json"] = "application/json"


class StressTestReportRef(ScientistArtifactRef):
    """Reference to a stored stress-test report artifact."""

    kind: Literal["scientist.stress_test_report"] = "scientist.stress_test_report"
    media_type: Literal["application/json"] = "application/json"


class PlatformMetaEvaluationReportRef(ScientistArtifactRef):
    """Reference to a stored platform meta-evaluation report artifact."""

    kind: Literal["scientist.platform_meta_evaluation_report"] = (
        "scientist.platform_meta_evaluation_report"
    )
    media_type: Literal["application/json"] = "application/json"


class GraphHypothesisRef(ScientistArtifactRef):
    kind: Literal["scientist.graph_hypothesis"] = "scientist.graph_hypothesis"
    media_type: Literal["application/json"] = "application/json"


class BootstrapStabilityReportRef(ScientistArtifactRef):
    kind: Literal["scientist.bootstrap_stability_report"] = (
        "scientist.bootstrap_stability_report"
    )
    media_type: Literal["application/json"] = "application/json"


class DownstreamUtilityReportRef(ScientistArtifactRef):
    kind: Literal["scientist.downstream_utility_report"] = (
        "scientist.downstream_utility_report"
    )
    media_type: Literal["application/json"] = "application/json"


class EdgeConfidenceMatrixRef(ScientistArtifactRef):
    kind: Literal["scientist.edge_confidence_matrix"] = "scientist.edge_confidence_matrix"
    media_type: Literal["application/json"] = "application/json"


class GraphPriorBundleRef(ScientistArtifactRef):
    kind: Literal["scientist.graph_prior_bundle"] = "scientist.graph_prior_bundle"
    media_type: Literal["application/json"] = "application/json"


class PriorKnowledgeBundleRef(ScientistArtifactRef):
    kind: Literal["scientist.prior_knowledge_bundle"] = "scientist.prior_knowledge_bundle"
    media_type: Literal["application/json"] = "application/json"


class DiscoveryTaskProfileRef(ScientistArtifactRef):
    kind: Literal["scientist.discovery_task_profile"] = "scientist.discovery_task_profile"
    media_type: Literal["application/json"] = "application/json"


class GraphHypothesisSetRef(ScientistArtifactRef):
    kind: Literal["scientist.graph_hypothesis_set"] = "scientist.graph_hypothesis_set"
    media_type: Literal["application/json"] = "application/json"


class RefutationReportRef(ScientistArtifactRef):
    kind: Literal["scientist.discovery_refutation_report"] = (
        "scientist.discovery_refutation_report"
    )
    media_type: Literal["application/json"] = "application/json"


class ReproducibilityReportRef(ScientistArtifactRef):
    kind: Literal["scientist.discovery_reproducibility_report"] = (
        "scientist.discovery_reproducibility_report"
    )
    media_type: Literal["application/json"] = "application/json"


class ActiveDisambiguationPlanRef(ScientistArtifactRef):
    kind: Literal["scientist.active_disambiguation_plan"] = (
        "scientist.active_disambiguation_plan"
    )
    media_type: Literal["application/json"] = "application/json"


class DiscoveryAuditBundleRef(ScientistArtifactRef):
    kind: Literal["scientist.discovery_audit_bundle"] = "scientist.discovery_audit_bundle"
    media_type: Literal["application/json"] = "application/json"


class DiscoveryArtifactBundleRef(ScientistArtifactRef):
    kind: Literal["scientist.discovery_artifact_bundle"] = (
        "scientist.discovery_artifact_bundle"
    )
    media_type: Literal["application/json"] = "application/json"


class DecisionReadinessContractRef(ScientistArtifactRef):
    kind: Literal["scientist.decision_readiness_contract"] = (
        "scientist.decision_readiness_contract"
    )
    media_type: Literal["application/json"] = "application/json"


class PolicyFrontierReportRef(ScientistArtifactRef):
    kind: Literal["scientist.policy_frontier_report"] = "scientist.policy_frontier_report"
    media_type: Literal["application/json"] = "application/json"


class ChampionPolicyDossierRef(ScientistArtifactRef):
    kind: Literal["scientist.champion_policy_dossier"] = (
        "scientist.champion_policy_dossier"
    )
    media_type: Literal["application/json"] = "application/json"


class PolicyBriefRef(ScientistArtifactRef):
    kind: Literal["scientist.policy_brief"] = "scientist.policy_brief"
    media_type: Literal["application/json"] = "application/json"


class ConstraintSatisfactionReportRef(ScientistArtifactRef):
    kind: Literal["scientist.constraint_satisfaction_report"] = (
        "scientist.constraint_satisfaction_report"
    )
    media_type: Literal["application/json"] = "application/json"


class SubgroupImpactReportRef(ScientistArtifactRef):
    kind: Literal["scientist.subgroup_impact_report"] = "scientist.subgroup_impact_report"
    media_type: Literal["application/json"] = "application/json"


class UncertaintyReportRef(ScientistArtifactRef):
    kind: Literal["scientist.uncertainty_report"] = "scientist.uncertainty_report"
    media_type: Literal["application/json"] = "application/json"


class TransportabilityReportRef(ScientistArtifactRef):
    kind: Literal["scientist.transportability_report"] = "scientist.transportability_report"
    media_type: Literal["application/json"] = "application/json"


class GovernanceGatePacketRef(ScientistArtifactRef):
    kind: Literal["scientist.governance_gate_packet"] = "scientist.governance_gate_packet"
    media_type: Literal["application/json"] = "application/json"


class ImplementationPlanRef(ScientistArtifactRef):
    kind: Literal["scientist.implementation_plan"] = "scientist.implementation_plan"
    media_type: Literal["application/json"] = "application/json"


class RejectedAlternativesSummaryRef(ScientistArtifactRef):
    kind: Literal["scientist.rejected_alternatives_summary"] = (
        "scientist.rejected_alternatives_summary"
    )
    media_type: Literal["application/json"] = "application/json"


class ReplayableAuditBundleRef(ScientistArtifactRef):
    kind: Literal["scientist.replayable_audit_bundle"] = "scientist.replayable_audit_bundle"
    media_type: Literal["application/json"] = "application/json"


class PolicyArtifactBundleRef(ScientistArtifactRef):
    kind: Literal["scientist.policy_artifact_bundle"] = "scientist.policy_artifact_bundle"
    media_type: Literal["application/json"] = "application/json"


class DecisionMonitoringContractRef(ScientistArtifactRef):
    kind: Literal["scientist.decision_monitoring_contract"] = (
        "scientist.decision_monitoring_contract"
    )
    media_type: Literal["application/json"] = "application/json"


class DecisionMonitoringReportRef(ScientistArtifactRef):
    kind: Literal["scientist.decision_monitoring_report"] = (
        "scientist.decision_monitoring_report"
    )
    media_type: Literal["application/json"] = "application/json"


class DecisionCompareReportRef(ScientistArtifactRef):
    kind: Literal["scientist.decision_compare_report"] = "scientist.decision_compare_report"
    media_type: Literal["application/json"] = "application/json"


class DecisionReissuePlanRef(ScientistArtifactRef):
    kind: Literal["scientist.decision_reissue_plan"] = "scientist.decision_reissue_plan"
    media_type: Literal["application/json"] = "application/json"


class PolicyRequestFrameRef(ScientistArtifactRef):
    kind: Literal["scientist.policy_request_frame"] = "scientist.policy_request_frame"
    media_type: Literal["application/json"] = "application/json"


class LegalCandidatePackRef(ScientistArtifactRef):
    kind: Literal["scientist.legal_candidate_pack"] = "scientist.legal_candidate_pack"
    media_type: Literal["application/json"] = "application/json"


class LegalSourcePackRef(ScientistArtifactRef):
    kind: Literal["scientist.legal_source_pack"] = "scientist.legal_source_pack"
    media_type: Literal["application/json"] = "application/json"


class SourceVerificationReportRef(ScientistArtifactRef):
    kind: Literal["scientist.source_verification_report"] = (
        "scientist.source_verification_report"
    )
    media_type: Literal["application/json"] = "application/json"


class PolicyOptionSetRef(ScientistArtifactRef):
    kind: Literal["scientist.policy_option_set"] = "scientist.policy_option_set"
    media_type: Literal["application/json"] = "application/json"


class VerifiedPolicyReportRef(ScientistArtifactRef):
    kind: Literal["scientist.verified_policy_report"] = "scientist.verified_policy_report"
    media_type: Literal["application/json"] = "application/json"


__all__ = [
    "ScientistArtifactRef",
    "ExperimentStateRef",
    "DecisionPacketRef",
    "GovernanceReportRef",
    "FailureCardLike",
    "FailureCardRef",
    "TrinityIRRef",
    "CritiqueRef",
    "TimelineRef",
    "DecisionCardRef",
    "CheckpointRef",
    "SensitivityResultRef",
    "StressTestReportRef",
    "PlatformMetaEvaluationReportRef",
    "GraphHypothesisRef",
    "BootstrapStabilityReportRef",
    "DownstreamUtilityReportRef",
    "EdgeConfidenceMatrixRef",
    "GraphPriorBundleRef",
    "PriorKnowledgeBundleRef",
    "DiscoveryTaskProfileRef",
    "GraphHypothesisSetRef",
    "RefutationReportRef",
    "ReproducibilityReportRef",
    "ActiveDisambiguationPlanRef",
    "DiscoveryAuditBundleRef",
    "DiscoveryArtifactBundleRef",
    "DecisionReadinessContractRef",
    "PolicyFrontierReportRef",
    "ChampionPolicyDossierRef",
    "PolicyBriefRef",
    "ConstraintSatisfactionReportRef",
    "SubgroupImpactReportRef",
    "UncertaintyReportRef",
    "TransportabilityReportRef",
    "GovernanceGatePacketRef",
    "ImplementationPlanRef",
    "RejectedAlternativesSummaryRef",
    "ReplayableAuditBundleRef",
    "PolicyArtifactBundleRef",
    "DecisionMonitoringContractRef",
    "DecisionMonitoringReportRef",
    "DecisionCompareReportRef",
    "DecisionReissuePlanRef",
    "PolicyRequestFrameRef",
    "LegalCandidatePackRef",
    "LegalSourcePackRef",
    "SourceVerificationReportRef",
    "PolicyOptionSetRef",
    "VerifiedPolicyReportRef",
]

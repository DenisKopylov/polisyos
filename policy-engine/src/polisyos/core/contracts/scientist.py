"""
Typed references for Scientist layer artifacts.

These provide type-safe references to CAS-stored artifacts,
enabling static analysis and IDE support while maintaining
the content-addressable architecture.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import ConfigDict, Field, model_validator

from ..artifacts.ids import ArtifactID
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
    """Artifact reference for persisted Scientist workflow state across steps and retries."""
    kind: str = "scientist.experiment_state"
    media_type: str = "application/json"


class DecisionPacketRef(ScientistArtifactRef):
    """Artifact reference for the decision packet emitted when a Scientist run concludes."""
    kind: str = "scientist.decision_packet"
    media_type: str = "application/json"


class GovernanceReportRef(ScientistArtifactRef):
    """Artifact reference for aggregated governance-pass findings attached to a run."""
    kind: str = "scientist.governance_report"
    media_type: str = "application/json"


class FailureCardRef(ScientistArtifactRef):
    """
    Typed reference to a FailureCard artifact in CAS.

    Used in state schemas to reference failure history without
    embedding full FailureCard objects in workflow state.
    """

    kind: str = "scientist.failure_card"
    media_type: str = "application/json"

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
            artifact_id=ArtifactID.model_validate(card.content_hash),
            attempt_number=card.attempt_number,
            error_code=card.error_code,
            source_step=str(source_step),
            can_retry=card.can_retry,
        )


class TrinityIRRef(ScientistArtifactRef):
    """Reference to a canonical Trinity IR artifact."""

    kind: str = "scientist.policy_ir"
    media_type: str = "application/json"

    version: int = Field(ge=1, description="Revision number of this IR")
    status: str = Field(description="Current status: draft, validated, rejected")


class CritiqueRef(ScientistArtifactRef):
    """Reference to a Critic evaluation artifact."""

    kind: str = "scientist.critique"
    media_type: str = "application/json"

    verdict: str = Field(description="Critic's verdict: approve, revise, reject")
    ir_ref: str = Field(description="CAS hash of the evaluated IR")


class TimelineRef(ScientistArtifactRef):
    """
    Reference to a stored RunTimeline artifact.

    Note: In Scientist contracts we use CAS-addressed references (artifact_id).
    """

    kind: str = "scientist.run_timeline"
    media_type: str = "application/json"

    # Denormalized for quick filtering
    run_id: str = Field(description="Associated run id")
    event_count: int = Field(ge=0, description="Number of timeline events")
    total_duration_ms: int = Field(ge=0, description="Total run duration, ms")


class DecisionCardRef(ScientistArtifactRef):
    """Reference to a stored DecisionCard artifact."""

    kind: str = "scientist.decision_card"
    media_type: str = "application/json"

    run_id: str = Field(description="Associated run id")
    verdict: str = Field(description="Decision verdict")
    generated_at: str = Field(description="Card generation timestamp (ISO 8601)")


class CheckpointRef(ScientistArtifactRef):
    """Reference to a stored Scientist checkpoint artifact."""

    kind: str = "scientist.checkpoint"
    media_type: str = "application/json"

    run_id: str = Field(description="Associated run id")
    sequence_number: int = Field(ge=0, description="Checkpoint sequence number")
    node_alias: str = Field(description="Last completed node alias")


class SensitivityResultRef(ScientistArtifactRef):
    """Reference to a stored sensitivity analysis result artifact."""

    kind: str = "scientist.sensitivity_result"
    media_type: str = "application/json"


class StressTestReportRef(ScientistArtifactRef):
    """Reference to a stored stress-test report artifact."""

    kind: str = "scientist.stress_test_report"
    media_type: str = "application/json"


class CalibrationValidationBundleRef(ScientistArtifactRef):
    """Reference to a stored calibration-validation bundle artifact."""

    kind: str = (
        "scientist.calibration_validation_bundle"
    )
    media_type: str = "application/json"


class GovernanceAccountabilityArtifactRef(ScientistArtifactRef):
    """Reference to a stored governance accountability artifact."""

    kind: str = (
        "scientist.governance_accountability_artifact"
    )
    media_type: str = "application/json"


class PlatformMetaEvaluationReportRef(ScientistArtifactRef):
    """Reference to a stored platform meta-evaluation report artifact."""

    kind: str = (
        "scientist.platform_meta_evaluation_report"
    )
    media_type: str = "application/json"


class GraphHypothesisRef(ScientistArtifactRef):
    """Artifact reference for one discovered causal-graph hypothesis."""
    kind: str = "scientist.graph_hypothesis"
    media_type: str = "application/json"


class BootstrapStabilityReportRef(ScientistArtifactRef):
    """Artifact reference for bootstrap stability diagnostics on graph structure."""
    kind: str = (
        "scientist.bootstrap_stability_report"
    )
    media_type: str = "application/json"


class DownstreamUtilityReportRef(ScientistArtifactRef):
    """Artifact reference for a report estimating downstream usefulness of a candidate output."""
    kind: str = (
        "scientist.downstream_utility_report"
    )
    media_type: str = "application/json"


class EdgeConfidenceMatrixRef(ScientistArtifactRef):
    """Artifact reference for edge-level confidence scores produced during discovery."""
    kind: str = "scientist.edge_confidence_matrix"
    media_type: str = "application/json"


class GraphPriorBundleRef(ScientistArtifactRef):
    """Artifact reference for priors injected into graph discovery or scoring."""
    kind: str = "scientist.graph_prior_bundle"
    media_type: str = "application/json"


class PriorKnowledgeBundleRef(ScientistArtifactRef):
    """Artifact reference for curated prior knowledge supplied to Scientist workflows."""
    kind: str = "scientist.prior_knowledge_bundle"
    media_type: str = "application/json"


class DiscoveryTaskProfileRef(ScientistArtifactRef):
    """Artifact reference for the profile that parameterizes a discovery workflow."""
    kind: str = "scientist.discovery_task_profile"
    media_type: str = "application/json"


class GraphHypothesisSetRef(ScientistArtifactRef):
    """Artifact reference for the set of competing graph hypotheses under review."""
    kind: str = "scientist.graph_hypothesis_set"
    media_type: str = "application/json"


class RefutationReportRef(ScientistArtifactRef):
    """Artifact reference for a report documenting refuted discovery hypotheses."""
    kind: str = (
        "scientist.discovery_refutation_report"
    )
    media_type: str = "application/json"


class ReproducibilityReportRef(ScientistArtifactRef):
    """Artifact reference for a discovery reproducibility assessment across reruns."""
    kind: str = (
        "scientist.discovery_reproducibility_report"
    )
    media_type: str = "application/json"


class ActiveDisambiguationPlanRef(ScientistArtifactRef):
    """Artifact reference for a follow-up plan that resolves discovery ambiguities."""
    kind: str = (
        "scientist.active_disambiguation_plan"
    )
    media_type: str = "application/json"


class DiscoveryAuditBundleRef(ScientistArtifactRef):
    """Artifact reference for the audit bundle emitted by discovery workflows."""
    kind: str = "scientist.discovery_audit_bundle"
    media_type: str = "application/json"


class DiscoveryArtifactBundleRef(ScientistArtifactRef):
    """Artifact reference for the bundle of artifacts produced during discovery."""
    kind: str = (
        "scientist.discovery_artifact_bundle"
    )
    media_type: str = "application/json"


class DecisionReadinessContractRef(ScientistArtifactRef):
    """Artifact reference for criteria that must hold before a policy decision is issued."""
    kind: str = (
        "scientist.decision_readiness_contract"
    )
    media_type: str = "application/json"


class PolicyFrontierReportRef(ScientistArtifactRef):
    """Artifact reference for the frontier report comparing policy trade-offs."""
    kind: str = "scientist.policy_frontier_report"
    media_type: str = "application/json"


class ChampionPolicyDossierRef(ScientistArtifactRef):
    """Artifact reference for the dossier describing the current champion policy option."""
    kind: str = (
        "scientist.champion_policy_dossier"
    )
    media_type: str = "application/json"


class PolicyBriefRef(ScientistArtifactRef):
    """Artifact reference for the narrative brief summarizing the recommended policy."""
    kind: str = "scientist.policy_brief"
    media_type: str = "application/json"


class ConstraintSatisfactionReportRef(ScientistArtifactRef):
    """Artifact reference for the report scoring how well an option satisfies constraints."""
    kind: str = (
        "scientist.constraint_satisfaction_report"
    )
    media_type: str = "application/json"


class SubgroupImpactReportRef(ScientistArtifactRef):
    """Artifact reference for subgroup-level impact analysis of a policy candidate."""
    kind: str = "scientist.subgroup_impact_report"
    media_type: str = "application/json"


class UncertaintyReportRef(ScientistArtifactRef):
    """Artifact reference for uncertainty bounds or decompositions on a candidate policy."""
    kind: str = "scientist.uncertainty_report"
    media_type: str = "application/json"


class TransportabilityReportRef(ScientistArtifactRef):
    """Artifact reference for a transportability assessment across populations or settings."""
    kind: str = "scientist.transportability_report"
    media_type: str = "application/json"


class GovernanceGatePacketRef(ScientistArtifactRef):
    """Artifact reference for the packet submitted to governance gates before approval."""
    kind: str = "scientist.governance_gate_packet"
    media_type: str = "application/json"


class ImplementationPlanRef(ScientistArtifactRef):
    """Artifact reference for the operational rollout plan of the selected policy."""
    kind: str = "scientist.implementation_plan"
    media_type: str = "application/json"


class RejectedAlternativesSummaryRef(ScientistArtifactRef):
    """Artifact reference for the summary explaining why alternative options were rejected."""
    kind: str = (
        "scientist.rejected_alternatives_summary"
    )
    media_type: str = "application/json"


class ReplayableAuditBundleRef(ScientistArtifactRef):
    """Artifact reference for the replay-friendly audit bundle of a decision workflow."""
    kind: str = "scientist.replayable_audit_bundle"
    media_type: str = "application/json"


class PolicyArtifactBundleRef(ScientistArtifactRef):
    """Artifact reference for the bundle of final artifacts backing a policy recommendation."""
    kind: str = "scientist.policy_artifact_bundle"
    media_type: str = "application/json"


class DecisionMonitoringContractRef(ScientistArtifactRef):
    """Artifact reference for post-deployment metrics, triggers, and review obligations."""
    kind: str = (
        "scientist.decision_monitoring_contract"
    )
    media_type: str = "application/json"


class DecisionMonitoringReportRef(ScientistArtifactRef):
    """Artifact reference for observed-vs-expected monitoring results after rollout."""
    kind: str = (
        "scientist.decision_monitoring_report"
    )
    media_type: str = "application/json"


class DecisionCompareReportRef(ScientistArtifactRef):
    """Artifact reference for a comparison between two decisions or policy versions."""
    kind: str = "scientist.decision_compare_report"
    media_type: str = "application/json"


class DecisionReissuePlanRef(ScientistArtifactRef):
    """Artifact reference for the plan to reissue or revise a prior decision."""
    kind: str = "scientist.decision_reissue_plan"
    media_type: str = "application/json"


class PolicyRequestFrameRef(ScientistArtifactRef):
    """Artifact reference for the structured intake frame of a new policy request."""
    kind: str = "scientist.policy_request_frame"
    media_type: str = "application/json"


class LegalCandidatePackRef(ScientistArtifactRef):
    """Artifact reference for assembled candidate legal sources during verification."""
    kind: str = "scientist.legal_candidate_pack"
    media_type: str = "application/json"


class LegalSourcePackRef(ScientistArtifactRef):
    """Artifact reference for the curated legal-source pack used for verification."""
    kind: str = "scientist.legal_source_pack"
    media_type: str = "application/json"


class SourceVerificationReportRef(ScientistArtifactRef):
    """Artifact reference for source-quality and legal verification diagnostics."""
    kind: str = (
        "scientist.source_verification_report"
    )
    media_type: str = "application/json"


class PolicyOptionSetRef(ScientistArtifactRef):
    """Artifact reference for the set of policy options under governance comparison."""
    kind: str = "scientist.policy_option_set"
    media_type: str = "application/json"


class VerifiedPolicyReportRef(ScientistArtifactRef):
    """Artifact reference for the final report of a policy option that passed verification."""
    kind: str = "scientist.verified_policy_report"
    media_type: str = "application/json"


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
    "CalibrationValidationBundleRef",
    "GovernanceAccountabilityArtifactRef",
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

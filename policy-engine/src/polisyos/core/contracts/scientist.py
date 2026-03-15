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
    "DecisionMonitoringContractRef",
    "DecisionMonitoringReportRef",
    "DecisionCompareReportRef",
    "DecisionReissuePlanRef",
]

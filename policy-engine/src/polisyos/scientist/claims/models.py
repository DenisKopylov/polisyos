"""Typed claim contracts for Scientist decision artifacts."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.search.readiness import DecisionReadiness


class ClaimType(str, Enum):
    """Decision-bearing claim families tracked by the claim spine."""

    FACTUAL = "factual"
    CAUSAL = "causal"
    LEGAL = "legal"
    NORMATIVE = "normative"
    FORECAST = "forecast"
    DISTRIBUTIONAL = "distributional"
    WELFARE = "welfare"
    IMPLEMENTATION = "implementation"
    SOURCE_QUALITY = "source_quality"


class ClaimSupportStatus(str, Enum):
    """How well available evidence supports a claim."""

    UNSUPPORTED = "unsupported"
    WEAKLY_SUPPORTED = "weakly_supported"
    SUPPORTED = "supported"
    CONTESTED = "contested"
    REFUTED = "refuted"
    NOT_EVALUABLE = "not_evaluable"


class ClaimPublishability(str, Enum):
    """Whether a claim may leave the current runtime boundary."""

    DRAFT = "draft"
    INTERNAL_ONLY = "internal_only"
    REVIEW_REQUIRED = "review_required"
    PUBLISHABLE = "publishable"
    BLOCKED = "blocked"


class ClaimRecord(BaseModel):
    """One typed claim plus its support, counterevidence, and release state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    claim_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    claim_type: ClaimType
    text: str = Field(min_length=1)
    normalized_subject: str | None = None
    support_status: ClaimSupportStatus
    publishability: ClaimPublishability
    readiness_level: DecisionReadiness
    evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    counterevidence_refs: list[ArtifactRef] = Field(default_factory=list)
    uncertainty_profile_ref: ArtifactRef | None = None
    provenance_ref: ArtifactRef | None = None
    source_attribution: list[str] = Field(default_factory=list)
    reviewer_refs: list[ArtifactRef] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_publishability(self) -> ClaimRecord:
        if self.publishability is ClaimPublishability.PUBLISHABLE:
            if self.support_status is not ClaimSupportStatus.SUPPORTED:
                raise ValueError("publishable claims must be supported")
            if self.counterevidence_refs:
                raise ValueError("publishable claims cannot carry unresolved counterevidence")
            if self.blocked_reasons:
                raise ValueError("publishable claims cannot carry blocked_reasons")
            if (
                self.claim_type
                in {
                    ClaimType.CAUSAL,
                    ClaimType.LEGAL,
                    ClaimType.FORECAST,
                    ClaimType.DISTRIBUTIONAL,
                    ClaimType.WELFARE,
                }
                and not self.evidence_refs
            ):
                raise ValueError("publishable high-stakes claims require evidence_refs")
        if self.support_status is ClaimSupportStatus.REFUTED and (
            self.publishability is ClaimPublishability.PUBLISHABLE
        ):
            raise ValueError("refuted claims cannot be publishable")
        return self


class ClaimLedger(BaseModel):
    """CAS-persisted sidecar containing all projected claims for one run/artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    claims: list[ClaimRecord] = Field(default_factory=list)
    decision_readiness_ref: ArtifactRef | None = None
    source_artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    created_by_node_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_claim_ids(self) -> ClaimLedger:
        claim_ids = [claim.claim_id for claim in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("ClaimLedger claim_id values must be unique")
        if any(claim.run_id != self.run_id for claim in self.claims):
            raise ValueError("ClaimLedger claims must share the ledger run_id")
        return self


class ClaimReadinessAssessment(BaseModel):
    """Machine-readable claim readiness decision used by validators and gates."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    support_status: ClaimSupportStatus
    publishability: ClaimPublishability
    readiness_level: DecisionReadiness
    blocking_reasons: list[str] = Field(default_factory=list)
    review_required_reasons: list[str] = Field(default_factory=list)


class ClaimValidationResult(BaseModel):
    """Validation result for claim-spine publication gates."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    status: Literal["ok", "warning", "blocked", "legacy_missing", "disabled"]
    violations: list[str] = Field(default_factory=list)
    claim_ledger_status: Literal["present", "legacy_missing", "disabled"] = "present"
    workflow_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ClaimLedger",
    "ClaimPublishability",
    "ClaimReadinessAssessment",
    "ClaimRecord",
    "ClaimSupportStatus",
    "ClaimType",
    "ClaimValidationResult",
]

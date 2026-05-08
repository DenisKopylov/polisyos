"""Public analytics normative arbitration module API."""

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import NormativeArbitrationResultRef

if TYPE_CHECKING:
    from polisyos.ir.governance.problem_frame import NormativeArbitrationPolicy
else:
    from polisyos.ir.governance.problem_frame import NormativeArbitrationPolicy


class ArbitrationOption(str, Enum):
    """Arbitration option public type."""

    BASELINE = "baseline"
    PROPOSAL = "proposal"
    INDETERMINATE = "indeterminate"


class NormativeModelCompleteness(str, Enum):
    """Normative model completeness public type."""

    COMPLETE = "complete"
    PARTIAL = "partial"


class NormativeAuditStatus(str, Enum):
    """Normative audit status public type."""

    SATISFIED = "satisfied"
    VIOLATED = "violated"
    UNEVALUATED = "unevaluated"


class OptionOutcomeMatrix(BaseModel):
    """Option outcome matrix data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    option: ArbitrationOption
    binding_values: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_binding_values(self) -> OptionOutcomeMatrix:
        for key, value in self.binding_values.items():
            if not math.isfinite(value):
                raise ValueError(f"binding_values.{key} must be finite")
        return self


class StakeholderUtilitySummary(BaseModel):
    """Stakeholder utility summary data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    stakeholder_id: str
    baseline_utility: float = 0.0
    proposal_utility: float = 0.0
    delta_utility: float = 0.0
    welfare_weight: float = Field(default=1.0, ge=0.0)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_numbers(self) -> StakeholderUtilitySummary:
        for value in (
            self.baseline_utility,
            self.proposal_utility,
            self.delta_utility,
            self.welfare_weight,
        ):
            if not math.isfinite(value):
                raise ValueError("stakeholder utility summary values must be finite")
        return self


class RightsAuditEntry(BaseModel):
    """Rights audit entry data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    right_id: str
    stakeholder_id: str
    binding_ref: str | None = None
    status: NormativeAuditStatus
    compare_to: str
    operator: str
    threshold: float | int | str | bool | None = None
    observed_value: float | int | str | bool | None = None
    notes: list[str] = Field(default_factory=list)


class HardConstraintAuditEntry(BaseModel):
    """Hard constraint audit entry data model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str
    status: NormativeAuditStatus
    operator: str | None = None
    threshold: float | int | str | bool | None = None
    proposal_value: float | int | str | bool | None = None
    baseline_value: float | int | str | bool | None = None
    notes: list[str] = Field(default_factory=list)


class PolicyOutcome(BaseModel):
    """Policy outcome public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: NormativeArbitrationPolicy
    selected_option: ArbitrationOption
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str
    metrics: dict[str, float | int | str | bool | None] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class ResidualDissent(BaseModel):
    """Residual dissent public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: NormativeArbitrationPolicy
    preferred_option: ArbitrationOption
    rationale: str


class NormativeProvenance(BaseModel):
    """Normative provenance public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trinity_bundle_ref: str | None = None
    distributional_report_ref: str | None = None
    legal_report_ref: str | None = None
    metrics_ref: str | None = None
    simulation_result_ref: str | None = None
    uncertainty_refs: list[str] = Field(default_factory=list)


class TradeoffCertificate(BaseModel):
    """Tradeoff certificate public type."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_policy: NormativeArbitrationPolicy
    selected_option: ArbitrationOption
    winners: list[str] = Field(default_factory=list)
    losers: list[str] = Field(default_factory=list)
    residual_dissent: list[ResidualDissent] = Field(default_factory=list)
    rights_violations: list[str] = Field(default_factory=list)
    hard_constraint_violations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class NormativeArbitrationResult(BaseModel):
    """Normative arbitration result data model."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={
            "title": "NormativeArbitrationResult",
            "description": "Formal value-conflict arbitration output for proposal vs baseline.",
        },
    )

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    comparison_mode: str = "proposal_vs_baseline"
    model_completeness: NormativeModelCompleteness = NormativeModelCompleteness.PARTIAL
    option_matrix: list[OptionOutcomeMatrix] = Field(default_factory=list, min_length=2)
    per_stakeholder_utility: list[StakeholderUtilitySummary] = Field(default_factory=list)
    rights_audit: list[RightsAuditEntry] = Field(default_factory=list)
    hard_constraint_audit: list[HardConstraintAuditEntry] = Field(default_factory=list)
    policy_outcomes: list[PolicyOutcome] = Field(default_factory=list, min_length=1)
    selected_policy: NormativeArbitrationPolicy
    selected_option: ArbitrationOption
    winners: list[str] = Field(default_factory=list)
    losers: list[str] = Field(default_factory=list)
    residual_dissent: list[ResidualDissent] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    tradeoff_certificate: TradeoffCertificate
    provenance: NormativeProvenance = Field(default_factory=NormativeProvenance)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_selected_policy(self) -> NormativeArbitrationResult:
        policy_ids = {item.policy for item in self.policy_outcomes}
        if self.selected_policy not in policy_ids:
            raise ValueError("selected_policy must be present in policy_outcomes")
        option_ids = {item.option for item in self.option_matrix}
        if (
            ArbitrationOption.BASELINE not in option_ids
            or ArbitrationOption.PROPOSAL not in option_ids
        ):
            raise ValueError("option_matrix must include baseline and proposal entries")
        return self


def persist_normative_arbitration_result(
    store: ArtifactStore,
    result: NormativeArbitrationResult,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.normative_arbitration_result",
    schema_version: str = "1.0",
) -> NormativeArbitrationResultRef:
    """Persist normative arbitration result helper."""
    ref = put_json_artifact(
        store,
        result.model_dump(mode="json"),
        kind="ir.normative_arbitration_result",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return NormativeArbitrationResultRef.model_validate(ref)


def load_normative_arbitration_result(
    store: ArtifactStore,
    ref: NormativeArbitrationResultRef,
) -> NormativeArbitrationResult:
    """Load normative arbitration result."""
    payload = get_json_artifact(store, ref.artifact_id)
    return NormativeArbitrationResult.model_validate(payload)


__all__ = [
    "ArbitrationOption",
    "HardConstraintAuditEntry",
    "NormativeArbitrationResult",
    "NormativeAuditStatus",
    "NormativeModelCompleteness",
    "NormativeProvenance",
    "OptionOutcomeMatrix",
    "PolicyOutcome",
    "ResidualDissent",
    "RightsAuditEntry",
    "StakeholderUtilitySummary",
    "TradeoffCertificate",
    "load_normative_arbitration_result",
    "persist_normative_arbitration_result",
]

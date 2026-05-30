"""Shared VOI decision/report contracts for Scientist compute scheduling."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef

NEGATIVE_VALUE_ACTIONS: frozenset[str] = frozenset({"defer", "reject", "stop_search"})
MANDATORY_GATE_SAFE_ACTIONS: frozenset[str] = frozenset(
    {
        "defer",
        "reject",
        "stop_search",
        "request_human_review",
        "run_required_gate",
        "blocked_by_mandatory_gate",
    }
)


class VOIDecisionType(str, Enum):
    """Decision families covered by the Wave 2.3 VOI scheduler surface."""

    CANDIDATE_EVALUATION = "candidate_evaluation"
    SOURCE_VERIFICATION = "source_verification"
    HUMAN_ESCALATION = "human_escalation"
    ADVERSARIAL_CHALLENGE = "adversarial_challenge"
    STOP_SEARCH = "stop_search"


class VOIDecisionRecord(BaseModel):
    """Auditable value-of-information explanation for one compute/review choice."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    decision_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    decision_type: VOIDecisionType
    recommended_action: str = Field(min_length=1)
    expected_value: float
    expected_cost: float = Field(ge=0.0)
    expected_risk_reduction: float = Field(ge=0.0)
    mandatory_gate_overrides: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)
    input_refs: list[ArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("decision_id", "run_id", "recommended_action", "explanation")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("VOI decision text fields cannot be blank")
        return value

    @field_validator("mandatory_gate_overrides")
    @classmethod
    def _non_blank_gate_overrides(cls, value: list[str]) -> list[str]:
        if any(not str(item).strip() for item in value):
            raise ValueError("mandatory_gate_overrides cannot contain blank values")
        return list(dict.fromkeys(str(item) for item in value))

    @model_validator(mode="after")
    def _validate_decision_safety(self) -> VOIDecisionRecord:
        action = _action_key(self.recommended_action)
        if self.expected_value < 0.0 and action not in NEGATIVE_VALUE_ACTIONS:
            raise ValueError(
                "negative expected value must produce defer, reject, or stop_search"
            )
        if self.mandatory_gate_overrides and action not in MANDATORY_GATE_SAFE_ACTIONS:
            raise ValueError("VOI cannot waive or advance through mandatory gates")
        return self


class VOIRunReport(BaseModel):
    """Persisted run-level VOI ledger for major Scientist runs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    decisions: list[VOIDecisionRecord] = Field(default_factory=list)
    total_expected_cost: float = Field(ge=0.0)
    calibration_status: str = Field(min_length=1)
    shadow_baseline_ref: ArtifactRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("run_id", "calibration_status")
    @classmethod
    def _non_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("VOI report text fields cannot be blank")
        return value

    @model_validator(mode="after")
    def _validate_report(self) -> VOIRunReport:
        decision_ids = [decision.decision_id for decision in self.decisions]
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("VOI report decision_id values must be unique")
        if any(decision.run_id != self.run_id for decision in self.decisions):
            raise ValueError("VOI report decisions must share report run_id")
        expected_min_cost = sum(decision.expected_cost for decision in self.decisions)
        if self.total_expected_cost + 1e-9 < expected_min_cost:
            raise ValueError("VOI report total_expected_cost cannot be below decision costs")
        return self


def stable_voi_decision_id(
    *,
    run_id: str,
    decision_type: VOIDecisionType | str,
    subject_id: str,
    sequence: int = 0,
) -> str:
    """Build deterministic ids for repeatable VOI fixtures and shadow reports."""

    digest = hashlib.sha256(
        json.dumps(
            {
                "run_id": run_id,
                "decision_type": str(VOIDecisionType(decision_type).value),
                "subject_id": subject_id,
                "sequence": sequence,
            },
            ensure_ascii=True,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"voi_decision_{digest}"


def acquisition_voi_metadata(
    *,
    requirement_gap_id: str,
    acquisition_strategy: str,
    requirement_family: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build metadata for VOI rankings over compiled requirement gaps."""

    metadata: dict[str, Any] = {
        "requirement_gap_id": _required_text(requirement_gap_id),
        "acquisition_strategy": _required_text(acquisition_strategy),
        "ranking_subject": "compiled_requirement_gap",
    }
    family = _optional_text(requirement_family)
    if family:
        metadata["requirement_family"] = family
    if extra:
        metadata.update(dict(extra))
    return metadata


def validate_mandatory_gate_policy(report: VOIRunReport) -> list[str]:
    """Return violations for VOI decisions that try to waive mandatory gates."""

    violations: list[str] = []
    for decision in report.decisions:
        action = _action_key(decision.recommended_action)
        if decision.mandatory_gate_overrides and action not in MANDATORY_GATE_SAFE_ACTIONS:
            violations.append(f"mandatory_gate_waived:{decision.decision_id}")
    return violations


def _action_key(action: str) -> str:
    return str(action).strip().lower().replace("-", "_").replace(" ", "_")


def _required_text(value: object) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError("required VOI metadata text cannot be blank")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "MANDATORY_GATE_SAFE_ACTIONS",
    "NEGATIVE_VALUE_ACTIONS",
    "VOIDecisionRecord",
    "VOIDecisionType",
    "VOIRunReport",
    "acquisition_voi_metadata",
    "stable_voi_decision_id",
    "validate_mandatory_gate_policy",
]

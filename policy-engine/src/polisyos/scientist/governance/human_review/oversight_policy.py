"""Human-oversight release policy and packet/readiness validators."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.governance.human_review.decisions import human_review_status
from polisyos.scientist.governance.human_review.models import (
    HumanReviewDecision,
    HumanReviewPacket,
    HumanReviewStatus,
    ReviewRiskTier,
)
from polisyos.scientist.governance.report import GovernanceReport

HUMAN_REVIEW_REQUIREMENT_FLAG = (
    "scientist.best_in_class.wave1.phase1_6.require_human_review_for_publication"
)
HUMAN_REVIEW_PACKET_REF_KEY = "human_review_packet_ref"
HUMAN_REVIEW_DECISION_REF_KEY = "human_review_decision_ref"

__all__ = [
    "HUMAN_REVIEW_DECISION_REF_KEY",
    "HUMAN_REVIEW_PACKET_REF_KEY",
    "HUMAN_REVIEW_REQUIREMENT_FLAG",
    "HumanReviewRequirement",
    "HumanReviewValidationResult",
    "apply_human_review_to_governance_report",
    "evaluate_human_review_requirement",
    "human_review_section",
    "is_human_review_required_for_publication",
    "validate_human_reviewed_readiness",
]


class HumanReviewRequirement(BaseModel):
    """Policy decision describing whether human review is required."""

    model_config = ConfigDict(extra="forbid")

    required: bool
    risk_tier: ReviewRiskTier = ReviewRiskTier.MEDIUM
    reasons: list[str] = Field(default_factory=list)
    required_reviewer_count: int = Field(default=1, ge=1, le=4)
    reviewer_independence_required: bool = False
    separation_of_duty_required: bool = False
    minimum_time_spent_seconds: int = Field(default=0, ge=0)
    require_change_request_or_dissent: bool = False


class HumanReviewValidationResult(BaseModel):
    """Fail-closed validation result for publication paths."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    status: Literal["ok", "warning", "blocked"]
    violations: list[str] = Field(default_factory=list)
    human_review_status: HumanReviewStatus = HumanReviewStatus.LEGACY_MISSING
    metadata: dict[str, Any] = Field(default_factory=dict)


def evaluate_human_review_requirement(
    *,
    params: Mapping[str, Any] | None = None,
    governance_report: GovernanceReport | Mapping[str, Any] | None = None,
    packet_payload: Mapping[str, Any] | None = None,
) -> HumanReviewRequirement:
    """Evaluate whether a release path should require human oversight."""

    resolved_params = params or {}
    reasons: list[str] = []
    risk_tier = _risk_tier(resolved_params, packet_payload)
    if _feature_enabled(resolved_params, HUMAN_REVIEW_REQUIREMENT_FLAG, default=False):
        reasons.append("feature_flag_required")
    if _truthy(resolved_params.get("require_human_review_for_publication"), default=False):
        reasons.append("explicit_param_required")
    if _truthy(resolved_params.get("public_sector"), default=False) and risk_tier in {
        ReviewRiskTier.HIGH,
        ReviewRiskTier.PUBLIC_SECTOR_HIGH,
    }:
        reasons.append("high_risk_public_sector")
        risk_tier = ReviewRiskTier.PUBLIC_SECTOR_HIGH
    if _governance_verdict(governance_report) == "human_gate":
        reasons.append("governance_human_gate")
    if _contains_human_gate_issue(governance_report):
        reasons.append("governance_human_gate_issue")
    if _truthy(resolved_params.get("affects_fundamental_rights"), default=False):
        reasons.append("fundamental_rights_impacted")
    required_reviewer_count = 2 if risk_tier is ReviewRiskTier.PUBLIC_SECTOR_HIGH else 1
    if _truthy(resolved_params.get("two_person_review"), default=False):
        required_reviewer_count = max(required_reviewer_count, 2)
        reasons.append("two_person_review_requested")
    high_risk_independence = risk_tier in {
        ReviewRiskTier.HIGH,
        ReviewRiskTier.PUBLIC_SECTOR_HIGH,
    }
    return HumanReviewRequirement(
        required=bool(reasons),
        risk_tier=risk_tier,
        reasons=sorted(set(reasons)),
        required_reviewer_count=required_reviewer_count,
        reviewer_independence_required=high_risk_independence
        or required_reviewer_count > 1,
        separation_of_duty_required=high_risk_independence,
        minimum_time_spent_seconds=300 if high_risk_independence else 0,
        require_change_request_or_dissent=high_risk_independence,
    )


def is_human_review_required_for_publication(
    params: Mapping[str, Any] | None = None,
) -> bool:
    """Return whether publication should fail closed without review evidence."""

    return evaluate_human_review_requirement(params=params).required


def validate_human_reviewed_readiness(
    payload: Mapping[str, Any],
    *,
    review_packet_ref: ArtifactRef | str | None = None,
    review_decision_ref: ArtifactRef | str | None = None,
    decisions: list[HumanReviewDecision] | None = None,
    packet: HumanReviewPacket | None = None,
    requirement: HumanReviewRequirement | None = None,
) -> HumanReviewValidationResult:
    """Reject readiness claims that say `human_reviewed` without review refs."""

    violations: list[str] = []
    claims_human_reviewed = _payload_claims_human_reviewed(payload)
    has_review_ref = review_packet_ref is not None or review_decision_ref is not None
    status = (
        human_review_status(
            decisions or [],
            packet=packet,
            required_reviewer_count=(
                max(
                    requirement.required_reviewer_count if requirement is not None else 1,
                    packet.required_reviewer_count if packet is not None else 1,
                )
            ),
        )
        if decisions is not None
        else HumanReviewStatus.LEGACY_MISSING
    )
    if claims_human_reviewed and not has_review_ref:
        violations.append("human_reviewed_readiness_without_review_ref")
    if requirement is not None and requirement.required:
        if review_packet_ref is None:
            violations.append("missing_human_review_packet_ref")
        if review_decision_ref is None:
            violations.append("missing_human_review_decision_ref")
        elif decisions is not None and status not in {
            HumanReviewStatus.APPROVED,
            HumanReviewStatus.OVERRIDDEN,
        }:
            violations.append(f"human_review_not_release_approved:{status.value}")
    blocked = bool(violations)
    return HumanReviewValidationResult(
        passed=not blocked,
        status="blocked" if blocked else "ok",
        violations=sorted(set(violations)),
        human_review_status=status,
        metadata={
            "claims_human_reviewed": claims_human_reviewed,
            "has_review_ref": has_review_ref,
            "requirement": None
            if requirement is None
            else requirement.model_dump(mode="json"),
        },
    )


def human_review_section(
    *,
    requirement: HumanReviewRequirement,
    review_packet_ref: ArtifactRef | str | None = None,
    review_decision_ref: ArtifactRef | str | None = None,
    decisions: list[HumanReviewDecision] | None = None,
    packet: HumanReviewPacket | None = None,
) -> dict[str, Any]:
    """Build a decision-packet/governance-safe human-review section."""

    status = (
        human_review_status(
            decisions or [],
            packet=packet,
            required_reviewer_count=max(
                requirement.required_reviewer_count,
                packet.required_reviewer_count if packet is not None else 1,
            ),
        )
        if decisions is not None
        else HumanReviewStatus.LEGACY_MISSING
        if requirement.required
        else HumanReviewStatus.NOT_REQUIRED
    )
    return {
        "required": requirement.required,
        "status": status.value,
        "risk_tier": requirement.risk_tier.value,
        "required_reviewer_count": requirement.required_reviewer_count,
        "reasons": list(requirement.reasons),
        "review_packet_ref": _ref_text(review_packet_ref),
        "review_decision_ref": _ref_text(review_decision_ref),
    }


def apply_human_review_to_governance_report(
    report: GovernanceReport,
    *,
    review_packet_ref: ArtifactRef | None = None,
    review_decision_ref: ArtifactRef | None = None,
    decisions: list[HumanReviewDecision] | None = None,
    packet: HumanReviewPacket | None = None,
) -> GovernanceReport:
    """Attach human-review refs and status to a governance report."""

    summary = human_review_section(
        requirement=HumanReviewRequirement(required=review_packet_ref is not None),
        review_packet_ref=review_packet_ref,
        review_decision_ref=review_decision_ref,
        decisions=decisions,
        packet=packet,
    )
    notes = [*report.notes, f"human_review_status:{summary['status']}"]
    return report.model_copy(
        update={
            "links": report.links.model_copy(
                update={
                    "human_review_packet_ref": review_packet_ref,
                    "human_review_decision_ref": review_decision_ref,
                }
            ),
            "notes": sorted(set(notes)),
        }
    )


def _risk_tier(
    params: Mapping[str, Any],
    packet_payload: Mapping[str, Any] | None,
) -> ReviewRiskTier:
    raw = str(params.get("risk_tier") or params.get("review_risk_tier") or "").strip()
    if raw:
        return ReviewRiskTier(raw)
    if _truthy(params.get("public_sector"), default=False) and _truthy(
        params.get("high_risk"),
        default=False,
    ):
        return ReviewRiskTier.PUBLIC_SECTOR_HIGH
    if _truthy(params.get("high_risk"), default=False):
        return ReviewRiskTier.HIGH
    if isinstance(packet_payload, Mapping):
        section = packet_payload.get("human_review")
        if isinstance(section, Mapping) and section.get("risk_tier"):
            return ReviewRiskTier(str(section["risk_tier"]))
    return ReviewRiskTier.MEDIUM


def _payload_claims_human_reviewed(payload: Mapping[str, Any]) -> bool:
    stack: list[Any] = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            for key, child in value.items():
                key_text = str(key).lower()
                if key_text == "human_reviewed" and _truthy(child, default=False):
                    return True
                if "readiness" in key_text and str(child).lower() == "human_reviewed":
                    return True
                stack.append(child)
        elif isinstance(value, list):
            stack.extend(value)
        elif isinstance(value, str) and value.lower() == "human_reviewed":
            return True
    return False


def _governance_verdict(report: GovernanceReport | Mapping[str, Any] | None) -> str | None:
    if report is None:
        return None
    if isinstance(report, GovernanceReport):
        return report.verdict
    verdict = report.get("verdict")
    return str(verdict) if verdict is not None else None


def _contains_human_gate_issue(report: GovernanceReport | Mapping[str, Any] | None) -> bool:
    if report is None:
        return False
    issues = report.issues if isinstance(report, GovernanceReport) else report.get("issues", [])
    if not isinstance(issues, list):
        return False
    for issue in issues:
        if not isinstance(issue, Mapping):
            continue
        severity = str(issue.get("severity") or issue.get("level") or "").lower()
        code = str(issue.get("code") or "").lower()
        if severity == "human_gate" or "human_review" in code:
            return True
    return False


def _feature_enabled(params: Mapping[str, Any], flag_name: str, *, default: bool) -> bool:
    for key in (flag_name, flag_name.replace(".", "_")):
        if key in params:
            return _truthy(params[key], default=default)
    env_key = re.sub(r"[^A-Za-z0-9]+", "_", flag_name).upper()
    if env_key in os.environ:
        return _truthy(os.environ[env_key], default=default)
    return default


def _truthy(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    token = str(value).strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return default


def _ref_text(ref: ArtifactRef | str | None) -> str | None:
    if ref is None:
        return None
    if isinstance(ref, ArtifactRef):
        return str(ref.artifact_id)
    return str(ref)

"""Publication validators for the Scientist claim spine."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evidence.claims.models import (
    ClaimLedger,
    ClaimPublishability,
    ClaimValidationResult,
)
from polisyos.scientist.evidence.claims.projections import has_decision_bearing_content

CLAIM_SPINE_FLAG = "scientist.best_in_class.wave1.phase1_1.claim_spine"
FAIL_ON_NAKED_CLAIMS_FLAG = "scientist.best_in_class.wave1.phase1_1.fail_on_naked_claims"
CLAIMS_REF_KEY = "claims_ref"
SELECTED_FAIL_CLOSED_WORKFLOWS: frozenset[str] = frozenset(
    {
        "scientist_policy_design",
        "scientist_policy_verified",
        "scientist_causal_full",
    }
)
STATE_DECISION_BEARING_ARTIFACT_KEYS: tuple[str, ...] = (
    "policy_output_bundle_ref",
    "verified_policy_report_ref",
    "source_verification_report_ref",
    "policy_recommendation_ref",
    "causal_report_ref",
    "causal_validity_bundle_ref",
    "distributional_report_ref",
    "welfare_bundle_ref",
)


def is_feature_enabled(
    params: Mapping[str, Any] | None,
    flag_name: str,
    *,
    default: bool,
) -> bool:
    """Resolve a feature flag from params or environment."""

    if params is not None:
        for key in (flag_name, _flag_param_key(flag_name)):
            if key in params:
                return _truthy(params[key], default=default)
    env_key = _flag_env_key(flag_name)
    if env_key in os.environ:
        return _truthy(os.environ[env_key], default=default)
    return default


def is_claim_spine_enabled(params: Mapping[str, Any] | None = None) -> bool:
    """Return whether additive claim-ledger sidecars should be produced."""

    return is_feature_enabled(params, CLAIM_SPINE_FLAG, default=True)


def is_fail_on_naked_claims_enabled(params: Mapping[str, Any] | None = None) -> bool:
    """Return whether selected workflows should fail closed on missing claims_ref."""

    return is_feature_enabled(params, FAIL_ON_NAKED_CLAIMS_FLAG, default=False)


def validate_claim_ledger_for_publication(ledger: ClaimLedger) -> ClaimValidationResult:
    """Reject ledgers that contain blocked claims or unresolved review requirements."""

    violations: list[str] = []
    for claim in ledger.claims:
        if claim.publishability is ClaimPublishability.BLOCKED:
            violations.append(f"blocked_claim:{claim.claim_id}")
        elif claim.publishability is ClaimPublishability.REVIEW_REQUIRED:
            violations.append(f"review_required_claim:{claim.claim_id}")
    return ClaimValidationResult(
        passed=not violations,
        status="ok" if not violations else "blocked",
        violations=violations,
        claim_ledger_status="present",
        metadata={"claim_count": len(ledger.claims)},
    )


def validate_naked_decision_claims(
    payload: Mapping[str, Any],
    *,
    claims_ref: ArtifactRef | str | None,
    workflow_id: str | None,
    fail_on_naked_claims: bool,
) -> ClaimValidationResult:
    """Detect decision-bearing payloads that lack a claim projection."""

    has_claims = claims_ref is not None
    decision_bearing = has_decision_bearing_content(payload)
    selected_workflow = _is_selected_fail_closed_workflow(workflow_id)
    violations: list[str] = []
    if decision_bearing and not has_claims:
        violations.append("missing_claims_ref_for_decision_bearing_payload")
    blocked = bool(violations and fail_on_naked_claims and selected_workflow)
    return ClaimValidationResult(
        passed=not blocked,
        status="blocked" if blocked else "warning" if violations else "ok",
        violations=violations,
        claim_ledger_status="present" if has_claims else "legacy_missing",
        workflow_id=workflow_id,
        metadata={
            "decision_bearing": decision_bearing,
            "fail_on_naked_claims": fail_on_naked_claims,
            "selected_fail_closed_workflow": selected_workflow,
        },
    )


def validate_state_claim_projection(
    *,
    workflow_id: str | None,
    artifacts_index: Mapping[str, ArtifactRef],
    fail_on_naked_claims: bool,
) -> ClaimValidationResult:
    """Validate claim projection coverage from a workflow state's artifact index."""

    has_claims = CLAIMS_REF_KEY in artifacts_index
    decision_bearing_keys = [
        key for key in STATE_DECISION_BEARING_ARTIFACT_KEYS if key in artifacts_index
    ]
    selected_workflow = _is_selected_fail_closed_workflow(workflow_id)
    violations = (
        ["missing_claims_ref_for_decision_bearing_state"]
        if decision_bearing_keys and not has_claims
        else []
    )
    blocked = bool(violations and fail_on_naked_claims and selected_workflow)
    return ClaimValidationResult(
        passed=not blocked,
        status="blocked" if blocked else "warning" if violations else "ok",
        violations=violations,
        claim_ledger_status="present" if has_claims else "legacy_missing",
        workflow_id=workflow_id,
        metadata={
            "decision_bearing_artifact_keys": decision_bearing_keys,
            "fail_on_naked_claims": fail_on_naked_claims,
            "selected_fail_closed_workflow": selected_workflow,
        },
    )


def legacy_claim_ledger_status(claims_ref: ArtifactRef | str | None) -> str:
    """Return the packet rendering status for old artifacts without claims_ref."""

    return "available" if claims_ref is not None else "legacy_missing"


def _is_selected_fail_closed_workflow(workflow_id: str | None) -> bool:
    return str(workflow_id or "").strip().lower() in SELECTED_FAIL_CLOSED_WORKFLOWS


def _flag_param_key(flag_name: str) -> str:
    return flag_name.replace(".", "_")


def _flag_env_key(flag_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", flag_name).upper()


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


__all__ = [
    "CLAIMS_REF_KEY",
    "CLAIM_SPINE_FLAG",
    "FAIL_ON_NAKED_CLAIMS_FLAG",
    "SELECTED_FAIL_CLOSED_WORKFLOWS",
    "STATE_DECISION_BEARING_ARTIFACT_KEYS",
    "is_claim_spine_enabled",
    "is_fail_on_naked_claims_enabled",
    "is_feature_enabled",
    "legacy_claim_ledger_status",
    "validate_claim_ledger_for_publication",
    "validate_naked_decision_claims",
    "validate_state_claim_projection",
]

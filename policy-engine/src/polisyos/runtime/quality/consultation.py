"""Structured judgement and consultation records for Policy Design Cases."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

JUDGEMENT_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.structured_expert_judgement.v1"
)
CONSULTATION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.consultation_record.v1"
)
HUMAN_OVERSIGHT_SCHEMA_VERSION = "policyos.runtime.policy_design_case.human_oversight.v1"
LEGITIMACY_VALIDATION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.legitimacy_validation.v1"
)
JUDGEMENT_NOT_DATA = "judgement_not_data"

_SEVERITY_ORDER = {
    "none": 0,
    "low": 1,
    "medium": 2,
    "moderate": 2,
    "high": 3,
    "critical": 4,
}
_UNRESOLVED_STATUSES = {"open", "unresolved", "partially_resolved"}


def build_structured_expert_judgement_record(
    *,
    judgement_id: str,
    claim_ids: Sequence[str],
    elicitation_method: str,
    expert_provenance: Mapping[str, Any],
    conflicts: Sequence[Mapping[str, Any]],
    uncertainty: Mapping[str, Any],
    classification: str = JUDGEMENT_NOT_DATA,
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a first-class expert judgement record."""

    return {
        "schema_version": JUDGEMENT_SCHEMA_VERSION,
        "generated_at": _utc(generated_at).isoformat(),
        "judgement_id": judgement_id,
        "claim_ids": [str(claim_id) for claim_id in claim_ids],
        "elicitation_method": elicitation_method,
        "expert_provenance": dict(expert_provenance),
        "conflicts": [dict(conflict) for conflict in conflicts],
        "uncertainty": dict(uncertainty),
        "classification": classification,
        "evidence_classification": classification,
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }


def validate_structured_expert_judgement_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate that expert judgement is explicit judgement, not observed data."""

    issues: list[dict[str, Any]] = []
    if record.get("schema_version") != JUDGEMENT_SCHEMA_VERSION:
        issues.append(
            _issue(
                "expert_judgement_schema_version_invalid",
                "schema_version",
                "Structured expert judgement records must use the current schema.",
            )
        )
    for field in ("judgement_id", "elicitation_method"):
        if not _text(record.get(field)):
            issues.append(
                _issue(
                    "expert_judgement_required_field_missing",
                    field,
                    f"Structured expert judgement must include {field}.",
                )
            )
    if not _mapping(record.get("expert_provenance")):
        issues.append(
            _issue(
                "expert_judgement_provenance_missing",
                "expert_provenance",
                "Structured expert judgement must include expert provenance.",
            )
        )
    if not isinstance(record.get("conflicts"), list):
        issues.append(
            _issue(
                "expert_judgement_conflicts_missing",
                "conflicts",
                "Structured expert judgement must explicitly record conflicts.",
            )
        )
    if not _mapping(record.get("uncertainty")):
        issues.append(
            _issue(
                "expert_judgement_uncertainty_missing",
                "uncertainty",
                "Structured expert judgement must include uncertainty.",
            )
        )
    classification = _judgement_classification(record)
    if classification != JUDGEMENT_NOT_DATA:
        issues.append(
            _issue(
                "expert_judgement_classification_invalid",
                "classification",
                "Expert judgement must be classified as judgement_not_data.",
                value=classification,
            )
        )
    return {
        "schema_version": LEGITIMACY_VALIDATION_SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "summary": {"issue_count": len(issues)},
        "issues": issues,
    }


def build_consultation_record(
    *,
    consultation_id: str,
    stakeholder_map: Mapping[str, Any],
    consultation_plan: Mapping[str, Any],
    public_comments: Sequence[Mapping[str, Any]],
    objection_records: Sequence[Mapping[str, Any]],
    response_to_comment_reasoning: Sequence[Mapping[str, Any]],
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a first-class consultation record."""

    return {
        "schema_version": CONSULTATION_SCHEMA_VERSION,
        "generated_at": _utc(generated_at).isoformat(),
        "consultation_id": consultation_id,
        "stakeholder_map": dict(stakeholder_map),
        "consultation_plan": dict(consultation_plan),
        "public_comments": [dict(comment) for comment in public_comments],
        "objection_records": [dict(objection) for objection in objection_records],
        "response_to_comment_reasoning": [
            dict(response) for response in response_to_comment_reasoning
        ],
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }


def validate_consultation_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate consultation, response-to-comment, and legitimacy blockers."""

    issues: list[dict[str, Any]] = []
    if record.get("schema_version") != CONSULTATION_SCHEMA_VERSION:
        issues.append(
            _issue(
                "consultation_schema_version_invalid",
                "schema_version",
                "Consultation records must use the current schema.",
            )
        )
    for field in ("consultation_id",):
        if not _text(record.get(field)):
            issues.append(
                _issue(
                    "consultation_required_field_missing",
                    field,
                    f"Consultation record must include {field}.",
                )
            )
    if not _stakeholders(record.get("stakeholder_map")):
        issues.append(
            _issue(
                "consultation_stakeholder_map_missing",
                "stakeholder_map",
                "Consultation record must include a stakeholder map.",
            )
        )
    if not _mapping(record.get("consultation_plan")):
        issues.append(
            _issue(
                "consultation_plan_missing",
                "consultation_plan",
                "Consultation record must include a consultation plan.",
            )
        )
    public_comments = _list_of_mappings(record.get("public_comments"))
    if not public_comments:
        issues.append(
            _issue(
                "consultation_public_comment_missing",
                "public_comments",
                "Consultation record must include public comment records.",
            )
        )
    objections = _list_of_mappings(record.get("objection_records"))
    responses = _list_of_mappings(record.get("response_to_comment_reasoning"))
    response_ids = _response_objection_ids(responses)
    unresolved = [
        objection
        for objection in objections
        if _is_unresolved_objection(objection)
    ]
    for objection in unresolved:
        severity = _severity(objection.get("severity"))
        objection_id = _text(objection.get("objection_id"))
        if severity >= _SEVERITY_ORDER["high"] and objection_id not in response_ids:
            issues.append(
                _issue(
                    "consultation_unresolved_objection_legitimacy_blocker",
                    "response_to_comment_reasoning",
                    "High-severity unresolved objections require response-to-comment reasoning.",
                    value=objection_id,
                    claim_id=_text(objection.get("claim_id")),
                )
            )
    return {
        "schema_version": LEGITIMACY_VALIDATION_SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "summary": {
            "issue_count": len(issues),
            "public_comment_count": len(public_comments),
            "objection_count": len(objections),
            "unresolved_objection_count": len(unresolved),
            "max_unresolved_objection_severity": _max_objection_severity(unresolved),
        },
        "issues": issues,
    }


def validate_policy_design_case_legitimacy_records(
    case: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate Phase 27.1 governance, judgement, and consultation case records."""

    issues: list[dict[str, Any]] = []
    final_claims = _final_claims(case)
    if final_claims:
        issues.extend(_human_oversight_issues(case))
    judgement_records = _records(
        case,
        "structured_expert_judgements",
        "structured_judgement_records",
        "expert_judgements",
    )
    if final_claims and not judgement_records and not _record_family_blocked(
        case,
        "structured_expert_judgement",
        "structured_judgement",
        "expert_judgement",
    ):
        issues.append(
            _issue(
                "policy_design_structured_judgement_missing",
                "structured_expert_judgements",
                (
                    "Final major claims require structured expert judgement records "
                    "or explicit runtime blockers."
                ),
            )
        )
    for record in judgement_records:
        issues.extend(_judgement_case_issues(record, final_claims))
    consultation_records = _records(
        case,
        "consultations",
        "consultation_records",
        "stakeholder_consultations",
    )
    if final_claims and not consultation_records and not _record_family_blocked(
        case,
        "consultation",
        "stakeholder_consultation",
    ):
        issues.append(
            _issue(
                "policy_design_consultation_record_missing",
                "consultations",
                (
                    "Final major claims require stakeholder consultation records "
                    "or explicit runtime blockers."
                ),
            )
        )
    for record in consultation_records:
        issues.extend(_consultation_case_issues(record, final_claims))
    return {
        "schema_version": LEGITIMACY_VALIDATION_SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "summary": {"issue_count": len(issues)},
        "issues": issues,
    }


def _human_oversight_issues(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    record = _mapping(
        case.get("human_oversight")
        or case.get("human_oversight_effectiveness")
        or case.get("oversight_effectiveness")
    )
    if not record:
        if _record_family_blocked(case, "human_oversight", "reviewer_oversight"):
            return []
        return [
            _issue(
                "policy_design_human_oversight_missing",
                "human_oversight",
                "Final major claims require human oversight effectiveness records.",
            )
        ]
    issues = _human_oversight_shape_issues(record)
    if not _human_oversight_effective(record):
        issues.append(
            _issue(
                "policy_design_human_oversight_ineffective",
                "human_oversight",
                "Nominal approval cannot close out without effective independent oversight.",
                evidence_ref=_text(record.get("oversight_ref") or record.get("evidence_ref")),
            )
        )
    return _dedupe_issues(issues)


def _human_oversight_shape_issues(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if record.get("schema_version") != HUMAN_OVERSIGHT_SCHEMA_VERSION:
        issues.append(
            _issue(
                "policy_design_human_oversight_schema_version_invalid",
                "human_oversight.schema_version",
                "Human oversight records must use the current schema.",
            )
        )
    for field in ("authority_profile", "status"):
        if not _text(record.get(field)):
            issues.append(_human_oversight_required_field_issue(field))
    for field in ("review_count", "reviewer_count"):
        if _positive_int(record.get(field)) is None:
            issues.append(_human_oversight_required_field_issue(field))
    if not (
        _text_values(record.get("reviewer_identities"))
        or _text_values(record.get("reviewer_roles"))
        or _text(record.get("reviewer_identity"))
        or _text(record.get("reviewer_role"))
    ):
        issues.append(_human_oversight_required_field_issue("reviewer_identity_or_role"))
    if not isinstance(record.get("conflicts"), list):
        issues.append(_human_oversight_required_field_issue("conflicts"))
    for field in (
        "reviewer_independence_rate",
        "separation_of_duty_attestation_rate",
        "approve_without_change_rate",
    ):
        value = _float_or_none(record.get(field))
        if value is None or value < 0.0 or value > 1.0:
            issues.append(_human_oversight_required_field_issue(field))
    if not _mapping(record.get("producer_independence")):
        issues.append(_human_oversight_required_field_issue("producer_independence"))
    if not (
        _mapping(record.get("exposure_order_controls"))
        or _text_values(record.get("exposure_order"))
        or _text_values(record.get("exposure_order_refs"))
    ):
        issues.append(_human_oversight_required_field_issue("exposure_order"))
    if _positive_int(
        record.get("time_spent_seconds")
        or record.get("average_time_spent_seconds")
        or record.get("minimum_time_spent_seconds")
    ) is None:
        issues.append(_human_oversight_required_field_issue("time_spent_seconds"))
    if not (
        isinstance(record.get("dissent_records"), list)
        or "dissent_count" in record
    ):
        issues.append(_human_oversight_required_field_issue("dissent_records"))
    if not (
        isinstance(record.get("change_requests"), list)
        or "change_request_count" in record
    ):
        issues.append(_human_oversight_required_field_issue("change_requests"))
    if not (
        isinstance(record.get("override_decisions"), list)
        or "override_count" in record
    ):
        issues.append(_human_oversight_required_field_issue("override_decisions"))
    if not _text(record.get("rubber_stamp_risk")):
        issues.append(_human_oversight_required_field_issue("rubber_stamp_risk"))
    if "effective_oversight" not in record:
        issues.append(_human_oversight_required_field_issue("effective_oversight"))
    if not (
        _text(record.get("voi_escalation_ref"))
        or _mapping(record.get("voi_escalation"))
        or _text(record.get("value_of_information_ref"))
    ):
        issues.append(_human_oversight_required_field_issue("voi_escalation_ref"))
    if not _text(record.get("oversight_ref") or record.get("evidence_ref")):
        issues.append(_human_oversight_required_field_issue("evidence_ref"))
    if not _text(record.get("runtime_event_ref")):
        issues.append(_human_oversight_required_field_issue("runtime_event_ref"))
    return issues


def _human_oversight_required_field_issue(field: str) -> dict[str, Any]:
    return _issue(
        "policy_design_human_oversight_required_field_missing",
        f"human_oversight.{field}",
        f"Human oversight records must include {field}.",
    )


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float) and value.is_integer():
        parsed = int(value)
    elif isinstance(value, str) and value.strip():
        try:
            parsed = int(value)
        except ValueError:
            return None
    else:
        return None
    return parsed if parsed > 0 else None


def _human_oversight_effective(record: Mapping[str, Any]) -> bool:
    if record.get("effective_oversight") is not True:
        return False
    if _text(record.get("rubber_stamp_risk")) == "high":
        return False
    independence = _float_or_none(record.get("reviewer_independence_rate"))
    if independence is not None and independence < 0.8:
        return False
    separation = _float_or_none(record.get("separation_of_duty_attestation_rate"))
    if separation is not None and separation < 0.8:
        return False
    approve_without_change = _float_or_none(record.get("approve_without_change_rate"))
    return approve_without_change is None or approve_without_change < 0.95


def _judgement_case_issues(
    record: Mapping[str, Any],
    final_claims: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    validation = validate_structured_expert_judgement_record(record)
    classification = _judgement_classification(record)
    judgement_id = _text(
        record.get("judgement_id")
        or record.get("record_id")
        or record.get("evidence_id")
    )
    for validation_issue in validation["issues"]:
        if validation_issue.get("code") == "expert_judgement_classification_invalid":
            continue
        issues.append(
            _issue(
                f"policy_design_{validation_issue.get('code')}",
                str(validation_issue.get("field") or "structured_expert_judgements"),
                str(
                    validation_issue.get("message")
                    or "Structured expert judgement record is invalid."
                ),
                evidence_ref=_text(record.get("evidence_ref") or record.get("cas_ref")),
                value=validation_issue.get("value"),
            )
        )
    if any(
        issue.get("code") == "expert_judgement_classification_invalid"
        for issue in validation["issues"]
    ):
        issues.append(
            _issue(
                "policy_design_expert_judgement_masquerades_as_observed_data",
                "structured_expert_judgements.classification",
                (
                    "Expert judgement must be labelled judgement_not_data and "
                    "cannot masquerade as observed data."
                ),
                evidence_ref=_text(record.get("evidence_ref") or record.get("cas_ref")),
                value=classification,
            )
        )
    if judgement_id is not None and classification != JUDGEMENT_NOT_DATA:
        for claim in final_claims:
            source_refs = set(_text_values(claim.get("source_data_refs"))) | set(
                _text_values(claim.get("data_refs"))
            )
            if judgement_id in source_refs:
                issues.append(
                    _issue(
                        "policy_design_expert_judgement_masquerades_as_observed_data",
                        "final_major_claims.source_data_refs",
                        "Final claims cannot cite expert judgement as observed source data.",
                        evidence_ref=_text(record.get("evidence_ref") or record.get("cas_ref")),
                        claim_id=_text(claim.get("claim_id")),
                        value=judgement_id,
                    )
                )
    return _dedupe_issues(issues)


def _consultation_case_issues(
    record: Mapping[str, Any],
    final_claims: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    validation = validate_consultation_record(record)
    for validation_issue in validation["issues"]:
        issues.append(
            _issue(
                f"policy_design_{validation_issue.get('code')}",
                str(validation_issue.get("field") or "consultations"),
                str(validation_issue.get("message") or "Consultation record is invalid."),
                evidence_ref=_text(record.get("evidence_ref") or record.get("cas_ref")),
                value=validation_issue.get("value"),
                claim_id=_text(validation_issue.get("claim_id")),
            )
        )
    claims_by_id = {
        claim_id: claim
        for claim in final_claims
        if (claim_id := _text(claim.get("claim_id"))) is not None
    }
    responses = _response_objection_ids(
        _list_of_mappings(record.get("response_to_comment_reasoning"))
    )
    for objection in _list_of_mappings(record.get("objection_records")):
        if not _is_unresolved_objection(objection):
            continue
        if _severity(objection.get("severity")) < _SEVERITY_ORDER["high"]:
            continue
        objection_id = _text(objection.get("objection_id"))
        claim_id = _text(objection.get("claim_id"))
        claim = claims_by_id.get(claim_id or "")
        visible = (
            objection_id is not None
            and claim is not None
            and objection_id
            in {
                *list(_text_values(claim.get("objection_refs"))),
                *list(_text_values(claim.get("unresolved_objection_refs"))),
                *list(_text_values(claim.get("consultation_objection_refs"))),
            }
        )
        response_present = objection_id is not None and objection_id in responses
        hidden = _text(objection.get("visibility")) == "hidden"
        if hidden or not visible or not response_present:
            issues.append(
                _issue(
                    "policy_design_unresolved_objection_hidden_from_final_claim",
                    "final_major_claims.objection_refs",
                    (
                        "High-severity unresolved stakeholder objections must remain "
                        "visible in final claims with response-to-comment reasoning."
                    ),
                    evidence_ref=_text(record.get("evidence_ref") or record.get("cas_ref")),
                    claim_id=claim_id,
                    value=objection_id,
                )
            )
    return _dedupe_issues(issues)


def _issue(
    code: str,
    field: str,
    message: str,
    *,
    evidence_ref: str | None = None,
    value: object | None = None,
    claim_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "field": field,
        "message": message,
    }
    if evidence_ref:
        payload["evidence_ref"] = evidence_ref
    if value is not None:
        payload["value"] = value
    if claim_id:
        payload["claim_id"] = claim_id
    return payload


def _records(case: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for key in keys:
        value = case.get(key)
        if isinstance(value, Mapping):
            rows.append(value)
        elif isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    return rows


def _record_family_blocked(case: Mapping[str, Any], *families: str) -> bool:
    wanted = {_text(family) for family in families}
    wanted.discard(None)
    blockers = _records(
        case,
        "record_family_blockers",
        "governance_legitimacy_blockers",
        "structured_judgement_consultation_blockers",
        "human_oversight_blockers",
        "consultation_blockers",
        "expert_judgement_blockers",
    )
    active_statuses = {"active", "accepted", "blocked", "fail", "open", "unresolved"}
    for blocker in blockers:
        status = _text(blocker.get("status") or blocker.get("blocker_status")) or "active"
        if status not in active_statuses:
            continue
        blocker_family = _text(
            blocker.get("record_family")
            or blocker.get("family_id")
            or blocker.get("blocked_record_family")
        )
        code = _text(blocker.get("code") or blocker.get("blocker_code")) or ""
        if not (
            blocker_family in wanted
            or any(family is not None and family in code for family in wanted)
        ):
            continue
        if _text(blocker.get("evidence_ref") or blocker.get("cas_ref")) and _text(
            blocker.get("runtime_event_ref")
        ):
            return True
    return False


def _final_claims(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    claims = case.get("final_major_claims") or case.get("major_claims") or ()
    if not isinstance(claims, list):
        return ()
    return tuple(
        claim
        for claim in claims
        if isinstance(claim, Mapping)
        and bool(claim.get("major") is not False)
    )


def _judgement_classification(record: Mapping[str, Any]) -> str:
    return _text(
        record.get("classification")
        or record.get("evidence_classification")
        or record.get("record_classification")
    ) or ""


def _stakeholders(value: object) -> list[Mapping[str, Any]]:
    mapping = _mapping(value)
    stakeholders = mapping.get("stakeholders")
    return _list_of_mappings(stakeholders)


def _response_objection_ids(responses: Sequence[Mapping[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for response in responses:
        for key in ("objection_id", "responds_to_objection_id"):
            value = _text(response.get(key))
            if value:
                ids.add(value)
        ids.update(_text_values(response.get("objection_ids")))
    return ids


def _is_unresolved_objection(objection: Mapping[str, Any]) -> bool:
    return _text(objection.get("status") or "unresolved") in _UNRESOLVED_STATUSES


def _max_objection_severity(objections: Sequence[Mapping[str, Any]]) -> str:
    if not objections:
        return "none"
    reverse = {value: key for key, value in _SEVERITY_ORDER.items() if key != "moderate"}
    max_value = max(_severity(objection.get("severity")) for objection in objections)
    return reverse.get(max_value, "none")


def _severity(value: object) -> int:
    return _SEVERITY_ORDER.get(_text(value) or "none", 0)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list_of_mappings(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(item for item in (_text(item) for item in value) if item)
    text = _text(value)
    return (text,) if text else ()


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().casefold()
    return text or None


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _dedupe_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[object, object, object]] = set()
    deduped: list[dict[str, Any]] = []
    for issue in issues:
        key = (issue.get("code"), issue.get("field"), issue.get("value"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(issue))
    return deduped


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "CONSULTATION_SCHEMA_VERSION",
    "HUMAN_OVERSIGHT_SCHEMA_VERSION",
    "JUDGEMENT_NOT_DATA",
    "JUDGEMENT_SCHEMA_VERSION",
    "build_consultation_record",
    "build_structured_expert_judgement_record",
    "validate_consultation_record",
    "validate_policy_design_case_legitimacy_records",
    "validate_structured_expert_judgement_record",
]

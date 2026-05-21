"""Policy Design Case lifecycle, ex-post outcome, and calibration contracts."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from polisyos.runtime.quality.ddm_monitoring import (
    ImplementationMonitoringEvaluationError,
    validate_implementation_monitoring_evaluation_record,
)
from polisyos.scientist.orchestration.memory.contamination import (
    MemoryContaminationPolicy,
    detect_memory_contamination,
)

CASE_LIFECYCLE_SCHEMA_VERSION = "policyos.runtime.policy_design_case.case_lifecycle.v1"
CASE_LIFECYCLE_CONTRACT_ID = "policy_design_case.case_lifecycle.v1"
EX_POST_LEARNING_SCHEMA_VERSION = "policyos.runtime.policy_design_case.ex_post_learning.v1"
EX_POST_LEARNING_CONTRACT_ID = "policy_design_case.ex_post_learning.v1"

GOVERNED_LIFECYCLE_PROFILES = frozenset({"governed", "production"})
ALLOWED_LIFECYCLE_EVENTS = frozenset(
    {
        "draft",
        "ready_for_review",
        "approved",
        "published",
        "amended",
        "superseded",
        "withdrawn",
        "recalled",
        "retracted",
        "stale",
        "contested",
        "ex_post_under_review",
        "confirmed",
        "refuted",
        "inconclusive",
        "reissue",
    }
)
RESOLUTION_LIFECYCLE_EVENTS = frozenset(
    {
        "amended",
        "superseded",
        "withdrawn",
        "recalled",
        "retracted",
        "confirmed",
        "refuted",
        "inconclusive",
        "reissue",
    }
)
REASSESSMENT_STATUSES = frozenset(
    {"confirmed", "refuted", "superseded", "inconclusive", "accepted_data_deficit"}
)
_SHA256_REF_RE = re.compile(r"^(?:sha256:|cas://sha256/)[0-9a-f]{64}$", re.IGNORECASE)


@dataclass(frozen=True)
class PolicyDesignLifecycleError(ValueError):
    """Fail-closed lifecycle/ex-post/calibration contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class PolicyDesignLifecycleIssue:
    """Scorecard-readable lifecycle validation issue."""

    code: str
    message: str
    field: str
    evidence_ref: str | None = None
    affected_claim: str | None = None
    next_action: str = (
        "Emit Phase 27.2 lifecycle, DDM monitoring, ex-post, and calibration "
        "records from runtime quality before publication closeout."
    )

    def as_gate_fields(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "evidence_ref": self.evidence_ref,
            "affected_claim": self.affected_claim,
            "next_action": self.next_action,
        }


def build_case_lifecycle_record(
    *,
    ledger_id: str,
    case_id: str,
    current_state: str,
    events: Iterable[Mapping[str, Any]],
    continuous_governance_reports: Mapping[str, str],
    resolution_event_refs: Iterable[str] = (),
    evidence_ref: str,
    runtime_event_ref: str,
) -> dict[str, Any]:
    """Build an append-only lifecycle ledger for a governed Policy Design Case."""

    payload = {
        "schema_version": CASE_LIFECYCLE_SCHEMA_VERSION,
        "contract_id": CASE_LIFECYCLE_CONTRACT_ID,
        "ledger_id": ledger_id,
        "case_id": case_id,
        "current_state": current_state,
        "events": [dict(event) for event in events],
        "continuous_governance_reports": dict(continuous_governance_reports),
        "resolution_event_refs": list(resolution_event_refs),
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }
    return validate_case_lifecycle_record(payload)


def validate_case_lifecycle_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate append-only lifecycle semantics for published/governed cases."""

    if not isinstance(record, Mapping):
        raise PolicyDesignLifecycleError(
            "policy_design_case_lifecycle_missing",
            "Policy Design Case lifecycle record must be a mapping.",
            "case_lifecycle",
        )
    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_case_lifecycle_schema_version_missing",
    )
    if schema_version != CASE_LIFECYCLE_SCHEMA_VERSION:
        raise PolicyDesignLifecycleError(
            "policy_design_case_lifecycle_schema_version_invalid",
            "Case lifecycle record must use the Phase 27.2 schema.",
            "schema_version",
        )
    normalized["schema_version"] = CASE_LIFECYCLE_SCHEMA_VERSION
    normalized["contract_id"] = _text(record.get("contract_id")) or CASE_LIFECYCLE_CONTRACT_ID
    normalized["ledger_id"] = _required_text(
        record.get("ledger_id") or record.get("record_id") or record.get("id"),
        "ledger_id",
        "policy_design_case_lifecycle_id_missing",
    )
    normalized["case_id"] = _required_text(
        record.get("case_id"),
        "case_id",
        "policy_design_case_lifecycle_case_id_missing",
    )
    current_state = _required_text(
        record.get("current_state") or record.get("state"),
        "current_state",
        "policy_design_case_lifecycle_state_missing",
    )
    normalized["current_state"] = current_state
    events = [_validate_lifecycle_event(event) for event in _mapping_rows(record.get("events"))]
    if not events:
        raise PolicyDesignLifecycleError(
            "policy_design_case_lifecycle_event_missing",
            "Case lifecycle ledger must include append-only lifecycle events.",
            "events",
        )
    normalized["events"] = events
    reports = _continuous_governance_reports(record.get("continuous_governance_reports"))
    normalized["continuous_governance_reports"] = reports
    resolution_refs = _text_values(record.get("resolution_event_refs"))
    normalized["resolution_event_refs"] = resolution_refs
    _reject_historical_rewrite(record, events)
    if _state_is_stale(current_state, events) and not _has_stale_resolution(
        events,
        resolution_refs,
    ):
        raise PolicyDesignLifecycleError(
            "policy_design_published_case_stale",
            (
                "Published Policy Design Case is stale without reissue, supersession, "
                "withdrawal, or ex-post reassessment resolution."
            ),
            "case_lifecycle.current_state",
        )
    _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_case_lifecycle_runtime_ref_missing",
    )
    _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_case_lifecycle_runtime_event_missing",
    )
    return normalized


def build_ex_post_learning_record(
    *,
    record_id: str,
    case_id: str,
    claim_prediction_links: Iterable[Mapping[str, Any]],
    calibration: Mapping[str, Any],
    memory_contamination_check: Mapping[str, Any],
    learning_records: Iterable[Mapping[str, Any]],
    evidence_ref: str,
    runtime_event_ref: str,
) -> dict[str, Any]:
    """Build ex-post learning evidence without rewriting publication authority."""

    payload = {
        "schema_version": EX_POST_LEARNING_SCHEMA_VERSION,
        "contract_id": EX_POST_LEARNING_CONTRACT_ID,
        "record_id": record_id,
        "case_id": case_id,
        "claim_prediction_links": [dict(link) for link in claim_prediction_links],
        "calibration": dict(calibration),
        "memory_contamination_check": dict(memory_contamination_check),
        "learning_records": [dict(record) for record in learning_records],
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }
    return validate_ex_post_learning_record(payload)


def validate_ex_post_learning_record(
    record: Mapping[str, Any],
    *,
    required_claim_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate ex-post outcome links, calibration, and clean reusable learning."""

    if not isinstance(record, Mapping):
        raise PolicyDesignLifecycleError(
            "policy_design_ex_post_learning_missing",
            "Ex-post learning record must be a mapping.",
            "ex_post_learning",
        )
    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_ex_post_learning_schema_version_missing",
    )
    if schema_version != EX_POST_LEARNING_SCHEMA_VERSION:
        raise PolicyDesignLifecycleError(
            "policy_design_ex_post_learning_schema_version_invalid",
            "Ex-post learning record must use the Phase 27.2 schema.",
            "schema_version",
        )
    normalized["schema_version"] = EX_POST_LEARNING_SCHEMA_VERSION
    normalized["contract_id"] = _text(record.get("contract_id")) or EX_POST_LEARNING_CONTRACT_ID
    normalized["record_id"] = _required_text(
        record.get("record_id") or record.get("id"),
        "record_id",
        "policy_design_ex_post_learning_id_missing",
    )
    normalized["case_id"] = _required_text(
        record.get("case_id"),
        "case_id",
        "policy_design_ex_post_learning_case_id_missing",
    )
    links = [
        _validate_prediction_outcome_link(link)
        for link in _mapping_rows(
            record.get("claim_prediction_links") or record.get("outcome_links")
        )
    ]
    if not links:
        raise PolicyDesignLifecycleError(
            "policy_design_ex_post_outcome_link_missing",
            "Ex-post learning must link claim predictions to observed outcomes.",
            "claim_prediction_links",
        )
    missing_claims = set(_text_values(required_claim_ids)).difference(
        {str(link["claim_id"]) for link in links}
    )
    if missing_claims:
        raise PolicyDesignLifecycleError(
            "policy_design_ex_post_outcome_link_missing",
            "Ex-post learning omits outcome links for claims: " + ", ".join(sorted(missing_claims)),
            "claim_prediction_links",
        )
    normalized["claim_prediction_links"] = links
    normalized["calibration"] = _validate_calibration(record.get("calibration"))
    normalized["learning_records"] = _validate_learning_records(
        record.get("learning_records")
    )
    normalized["memory_contamination_check"] = _validate_memory_contamination_check(
        record.get("memory_contamination_check"),
        learning_records=normalized["learning_records"],
    )
    _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_ex_post_learning_runtime_ref_missing",
    )
    _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_ex_post_learning_runtime_event_missing",
    )
    return normalized


def validate_policy_design_lifecycle_records(
    case: Mapping[str, Any],
    *,
    canary_kind: str = "production",
) -> list[PolicyDesignLifecycleIssue]:
    """Return scorecard issues for Phase 27.2 lifecycle/DDM/ex-post records."""

    if not isinstance(case, Mapping):
        return []
    if not _phase27_in_scope(case, canary_kind=canary_kind):
        return []
    issues: list[PolicyDesignLifecycleIssue] = []
    claim_ids = _major_claim_ids(case)

    monitoring_record = _first_mapping(
        case.get("implementation_monitoring_evaluation"),
        case.get("implementation_monitoring_and_evaluation"),
        case.get("implementation_monitoring_record"),
        case.get("implementation_monitoring_records"),
    )
    if monitoring_record is None:
        issues.append(
            PolicyDesignLifecycleIssue(
                code="policy_design_implementation_monitoring_record_missing",
                message=(
                    "Governed and production Policy Design Cases require implementation "
                    "contract, monitoring plan, and evaluation design records before "
                    "publication authority."
                ),
                field="implementation_monitoring_evaluation",
            )
        )
    else:
        try:
            validate_implementation_monitoring_evaluation_record(
                monitoring_record,
                required_claim_ids=claim_ids,
            )
        except ImplementationMonitoringEvaluationError as exc:
            issues.append(_issue_from_error(exc))

    lifecycle_record = _first_mapping(
        case.get("case_lifecycle"),
        case.get("lifecycle"),
        case.get("lifecycle_ledger"),
    )
    if lifecycle_record is None:
        issues.append(
            PolicyDesignLifecycleIssue(
                code="policy_design_case_lifecycle_missing",
                message=(
                    "Published or governed Policy Design Case requires an append-only "
                    "lifecycle ledger."
                ),
                field="case_lifecycle",
            )
        )
    else:
        try:
            validate_case_lifecycle_record(lifecycle_record)
        except PolicyDesignLifecycleError as exc:
            issues.append(_issue_from_error(exc))

    ex_post_record = _first_mapping(
        case.get("ex_post_learning"),
        case.get("ex_post_outcomes"),
        case.get("lifecycle_ex_post_and_calibration"),
    )
    if ex_post_record is None:
        issues.append(
            PolicyDesignLifecycleIssue(
                code="policy_design_ex_post_learning_missing",
                message=(
                    "Governed and production Policy Design Cases require ex-post "
                    "outcome reassessment, calibration, and contamination-control records."
                ),
                field="ex_post_learning",
            )
        )
    else:
        try:
            validate_ex_post_learning_record(
                ex_post_record,
                required_claim_ids=claim_ids,
            )
        except PolicyDesignLifecycleError as exc:
            issues.append(_issue_from_error(exc))

    issues.extend(_claim_future_prior_issues(case))
    return issues


def _validate_lifecycle_event(event: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(event)
    normalized["event_id"] = _required_text(
        event.get("event_id") or event.get("id"),
        "events.event_id",
        "policy_design_case_lifecycle_event_missing",
    )
    event_type = _required_text(
        event.get("event_type") or event.get("lifecycle_event"),
        "events.event_type",
        "policy_design_case_lifecycle_event_type_missing",
    )
    if event_type not in ALLOWED_LIFECYCLE_EVENTS:
        raise PolicyDesignLifecycleError(
            "policy_design_case_lifecycle_event_type_invalid",
            "Lifecycle event type is not recognized.",
            "events.event_type",
        )
    normalized["event_type"] = event_type
    _required_text(
        event.get("previous_state"),
        "events.previous_state",
        "policy_design_case_lifecycle_transition_missing",
    )
    _required_text(
        event.get("new_state"),
        "events.new_state",
        "policy_design_case_lifecycle_transition_missing",
    )
    if not _text_values(event.get("evidence_refs")):
        raise PolicyDesignLifecycleError(
            "policy_design_case_lifecycle_evidence_missing",
            "Lifecycle events must reference transition evidence.",
            "events.evidence_refs",
        )
    _required_text(
        event.get("runtime_event_ref"),
        "events.runtime_event_ref",
        "policy_design_case_lifecycle_runtime_event_missing",
    )
    return normalized


def _continuous_governance_reports(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise PolicyDesignLifecycleError(
            "policy_design_continuous_governance_report_missing",
            (
                "Case lifecycle must link continuous governance validity, reissue, "
                "supersession, and withdrawal reports."
            ),
            "continuous_governance_reports",
        )
    aliases = {
        "reissue": ("reissue", "reissued", "continuous_governance_reissue_report_ref"),
        "supersede": ("supersede", "superseded", "continuous_governance_supersede_report_ref"),
        "withdraw": ("withdraw", "withdrawn", "continuous_governance_withdraw_report_ref"),
        "validity": ("validity", "validity_report", "continuous_governance_stale_report_ref"),
    }
    normalized: dict[str, str] = {}
    for key, candidates in aliases.items():
        ref = None
        for candidate in candidates:
            candidate_ref = _text(value.get(candidate))
            if candidate_ref:
                ref = candidate_ref
                break
        if ref is None:
            raise PolicyDesignLifecycleError(
                "policy_design_continuous_governance_report_missing",
                f"Continuous governance report ref is missing: {key}.",
                f"continuous_governance_reports.{key}",
            )
        if not _runtime_artifact_ref(ref):
            raise PolicyDesignLifecycleError(
                "policy_design_continuous_governance_report_ref_invalid",
                f"Continuous governance report ref is not runtime authority: {key}.",
                f"continuous_governance_reports.{key}",
            )
        normalized[key] = ref
    return normalized


def _reject_historical_rewrite(
    record: Mapping[str, Any],
    events: Iterable[Mapping[str, Any]],
) -> None:
    if bool(record.get("historical_authority_rewritten")) or bool(
        record.get("rewrites_historical_authority")
    ):
        raise PolicyDesignLifecycleError(
            "policy_design_lifecycle_historical_rewrite",
            "Lifecycle records must append evidence without rewriting publication authority.",
            "case_lifecycle.historical_authority_rewritten",
        )
    for event in events:
        if bool(event.get("rewrites_historical_authority")):
            raise PolicyDesignLifecycleError(
                "policy_design_lifecycle_historical_rewrite",
                "Lifecycle events must not rewrite historical authority.",
                "case_lifecycle.events.rewrites_historical_authority",
            )


def _state_is_stale(current_state: str, events: Iterable[Mapping[str, Any]]) -> bool:
    if current_state == "stale":
        return True
    return any(
        _text(event.get("event_type")) == "stale"
        or _text(event.get("new_state")) == "stale"
        for event in events
    )


def _has_stale_resolution(
    events: Iterable[Mapping[str, Any]],
    resolution_refs: Iterable[str],
) -> bool:
    refs = set(resolution_refs)
    ordered_events = list(events)
    stale_indexes = [
        index
        for index, event in enumerate(ordered_events)
        if _text(event.get("event_type")) == "stale"
        or _text(event.get("new_state")) == "stale"
    ]
    last_stale_index = max(stale_indexes, default=-1)
    for index, event in enumerate(ordered_events):
        if index <= last_stale_index:
            continue
        event_id = _text(event.get("event_id"))
        event_type = _text(event.get("event_type"))
        if event_type in RESOLUTION_LIFECYCLE_EVENTS and (
            not refs or (event_id is not None and event_id in refs)
        ):
            return True
    return False


def _validate_prediction_outcome_link(link: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(link)
    normalized["link_id"] = _required_text(
        link.get("link_id") or link.get("id"),
        "claim_prediction_links.link_id",
        "policy_design_ex_post_outcome_link_missing",
    )
    normalized["claim_id"] = _required_text(
        link.get("claim_id"),
        "claim_prediction_links.claim_id",
        "policy_design_ex_post_outcome_link_missing",
    )
    for field, code in (
        ("prediction_ref", "policy_design_claim_prediction_ref_missing"),
        ("observed_outcome_ref", "policy_design_observed_outcome_ref_missing"),
        ("reassessment_ref", "policy_design_reassessment_ref_missing"),
        ("future_method_prior_ref", "policy_design_future_prior_ref_missing"),
        ("future_uncertainty_prior_ref", "policy_design_future_prior_ref_missing"),
    ):
        _required_text(link.get(field), f"claim_prediction_links.{field}", code)
    status = _required_text(
        link.get("reassessment_status"),
        "claim_prediction_links.reassessment_status",
        "policy_design_reassessment_status_missing",
    )
    if status not in REASSESSMENT_STATUSES:
        raise PolicyDesignLifecycleError(
            "policy_design_reassessment_status_invalid",
            (
                "Reassessment status must be confirmation, refutation, supersession, "
                "inconclusive, or accepted data deficit."
            ),
            "claim_prediction_links.reassessment_status",
        )
    normalized["reassessment_status"] = status
    return normalized


def _validate_calibration(value: object) -> dict[str, Any]:
    record = _required_mapping(
        value,
        "calibration",
        "policy_design_calibration_evidence_missing",
        "Ex-post learning requires calibration, backtesting, leaderboard, and track-record refs.",
    )
    for field in (
        "calibration_report_refs",
        "backtesting_report_refs",
        "calibration_leaderboard_ref",
        "track_record_ref",
    ):
        if not _surface_present(record.get(field)):
            raise PolicyDesignLifecycleError(
                "policy_design_calibration_evidence_missing",
                f"Calibration evidence is missing {field}.",
                f"calibration.{field}",
            )
    return dict(record)


def _validate_learning_records(value: object) -> list[dict[str, Any]]:
    records = _mapping_rows(value)
    if not records:
        raise PolicyDesignLifecycleError(
            "policy_design_learning_record_missing",
            "Ex-post learning requires scoped reusable learning records.",
            "learning_records",
        )
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        for field in (
            "learning_id",
            "scope",
            "applicability",
            "revocation_conditions",
            "memory_contamination_controls",
        ):
            if not _surface_present(record.get(field)):
                raise PolicyDesignLifecycleError(
                    "policy_design_learning_record_missing",
                    f"Learning record is missing {field}.",
                    f"learning_records[{index}].{field}",
                )
        normalized.append(dict(record))
    return normalized


def _validate_memory_contamination_check(
    value: object,
    *,
    learning_records: list[dict[str, Any]],
) -> dict[str, Any]:
    record = _required_mapping(
        value,
        "memory_contamination_check",
        "policy_design_memory_contamination_check_missing",
        "Ex-post learning requires a memory-contamination check.",
    )
    status = _required_text(
        record.get("status"),
        "memory_contamination_check.status",
        "policy_design_memory_contamination_check_missing",
    )
    explicit_findings = _mapping_rows(record.get("findings"))
    policy = _memory_policy(record.get("policy"))
    detected_findings = [
        finding.model_dump(mode="json")
        for finding in detect_memory_contamination(learning_records, policy=policy)
    ]
    blocking_findings = [
        finding
        for finding in [*explicit_findings, *detected_findings]
        if _text(finding.get("severity")) != "warning"
    ]
    if status != "clean" or blocking_findings:
        raise PolicyDesignLifecycleError(
            "policy_design_learning_contamination_detected",
            "Ex-post learning is contaminated or lacks a clean memory-contamination check.",
            "memory_contamination_check.findings",
        )
    _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "memory_contamination_check.evidence_ref",
        "policy_design_memory_contamination_check_missing",
    )
    _required_text(
        record.get("runtime_event_ref"),
        "memory_contamination_check.runtime_event_ref",
        "policy_design_memory_contamination_check_missing",
    )
    return dict(record)


def _memory_policy(value: object) -> MemoryContaminationPolicy:
    if not isinstance(value, Mapping):
        return MemoryContaminationPolicy()
    return MemoryContaminationPolicy(
        hidden_ref_ids=set(_text_values(value.get("hidden_ref_ids"))),
        hidden_suite_ids=set(_text_values(value.get("hidden_suite_ids"))),
        canary_tokens=set(_text_values(value.get("canary_tokens"))),
    )


def _claim_future_prior_issues(case: Mapping[str, Any]) -> list[PolicyDesignLifecycleIssue]:
    issues: list[PolicyDesignLifecycleIssue] = []
    for claim in _major_claim_rows(case):
        claim_id = _text(claim.get("claim_id"))
        if claim_id is None:
            continue
        for field, code, message in (
            (
                "prediction_refs",
                "policy_design_claim_prediction_ref_missing",
                "Major claims need explicit prediction refs before ex-post reassessment.",
            ),
            (
                "observed_outcome_refs",
                "policy_design_observed_outcome_ref_missing",
                "Major claims need observed outcome refs after implementation monitoring.",
            ),
            (
                "reassessment_refs",
                "policy_design_reassessment_ref_missing",
                "Major claims need reassessment status refs.",
            ),
            (
                "future_prior_refs",
                "policy_design_future_prior_ref_missing",
                "Major claims need future method/uncertainty prior refs.",
            ),
        ):
            if not _surface_present(claim.get(field)):
                issues.append(
                    PolicyDesignLifecycleIssue(
                        code=code,
                        message=message,
                        field=f"final_major_claims.{field}",
                        affected_claim=claim_id,
                    )
                )
    return issues


def _phase27_in_scope(case: Mapping[str, Any], *, canary_kind: str) -> bool:
    profile = _effective_profile(case) or canary_kind.casefold()
    if profile in GOVERNED_LIFECYCLE_PROFILES:
        return True
    lifecycle = _first_mapping(case.get("case_lifecycle"), case.get("lifecycle"))
    if lifecycle is not None:
        state = _text(lifecycle.get("current_state") or lifecycle.get("state"))
        return state in {"published", "stale", "superseded", "withdrawn", "retracted"}
    return False


def _effective_profile(case: Mapping[str, Any]) -> str | None:
    authority_profile = case.get("authority_profile")
    if isinstance(authority_profile, Mapping):
        for key in (
            "effective_execution_profile",
            "requested_authority_level",
            "authority_profile",
        ):
            text = _text(authority_profile.get(key))
            if text is not None:
                return text.casefold()
    text = _text(case.get("effective_execution_profile"))
    return None if text is None else text.casefold()


def _major_claim_ids(case: Mapping[str, Any]) -> list[str]:
    return [
        claim_id
        for claim_id in (_text(claim.get("claim_id")) for claim in _major_claim_rows(case))
        if claim_id is not None
    ]


def _major_claim_rows(case: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = _mapping_rows(case.get("final_major_claims") or case.get("major_claims"))
    return [row for row in rows if row.get("major") is not False]


def _issue_from_error(
    error: PolicyDesignLifecycleError | ImplementationMonitoringEvaluationError,
) -> PolicyDesignLifecycleIssue:
    return PolicyDesignLifecycleIssue(
        code=error.code,
        message=str(error),
        field=error.field or "policy_design_case",
    )


def _first_mapping(*candidates: object) -> Mapping[str, Any] | None:
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return candidate
        if isinstance(candidate, list | tuple):
            for item in candidate:
                if isinstance(item, Mapping):
                    return item
    return None


def _required_mapping(
    value: object,
    field: str,
    code: str,
    message: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise PolicyDesignLifecycleError(code, message, field)
    return value


def _mapping_rows(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, list | tuple):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _surface_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, Iterable):
        return any(_surface_present(item) for item in value)
    return True


def _required_text(value: object, field: str, code: str) -> str:
    text = _text(value)
    if text is None:
        raise PolicyDesignLifecycleError(
            code,
            f"Required lifecycle text is missing: {field}.",
            field,
        )
    return text


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_values(value: object) -> list[str]:
    if isinstance(value, str):
        text = _text(value)
        return [] if text is None else [text]
    if isinstance(value, Mapping):
        return [
            text
            for text in (_text(item) for item in value.values())
            if text is not None
        ]
    if isinstance(value, Iterable):
        return [text for text in (_text(item) for item in value) if text is not None]
    return []


def _runtime_artifact_ref(value: object) -> bool:
    text = _text(value)
    if text is None:
        return False
    return bool(_SHA256_REF_RE.fullmatch(text)) or text.startswith("artifact://")


__all__ = [
    "ALLOWED_LIFECYCLE_EVENTS",
    "CASE_LIFECYCLE_CONTRACT_ID",
    "CASE_LIFECYCLE_SCHEMA_VERSION",
    "EX_POST_LEARNING_CONTRACT_ID",
    "EX_POST_LEARNING_SCHEMA_VERSION",
    "PolicyDesignLifecycleError",
    "PolicyDesignLifecycleIssue",
    "build_case_lifecycle_record",
    "build_ex_post_learning_record",
    "validate_case_lifecycle_record",
    "validate_ex_post_learning_record",
    "validate_policy_design_lifecycle_records",
]

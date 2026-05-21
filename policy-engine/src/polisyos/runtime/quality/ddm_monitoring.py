"""Policy Design Case implementation, monitoring, evaluation, and DDM bridge."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

IMPLEMENTATION_MONITORING_EVALUATION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.implementation_monitoring_evaluation.v1"
)
IMPLEMENTATION_MONITORING_EVALUATION_CONTRACT_ID = (
    "policy_design_case.implementation_monitoring_evaluation.v1"
)

DDM_EVENT_GROUPS: dict[str, str] = {
    "shift_events": "ml.problem_15_7.shift_risk.v1",
    "degradation_events": "ml.problem_15_7.degradation.v1",
    "readiness_events": "ml.problem_15_7.readiness_state.v1",
    "incident_events": "ml.problem_15_7.incident_payload.v1",
    "root_cause_events": "ml.problem_15_7.root_cause_bundle.v1",
}


@dataclass(frozen=True)
class ImplementationMonitoringEvaluationError(ValueError):
    """Fail-closed implementation monitoring/evaluation contract violation."""

    code: str
    message: str
    field: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


def build_implementation_monitoring_evaluation_record(
    *,
    record_id: str,
    case_id: str,
    claim_ids: Iterable[str],
    implementation_contract: Mapping[str, Any],
    monitoring_plan: Mapping[str, Any],
    evaluation_design: Mapping[str, Any],
    ddm_events: Mapping[str, Any],
    publication_authority_ref: str,
    created_before_publication_authority: bool,
    evidence_ref: str,
    runtime_event_ref: str,
) -> dict[str, Any]:
    """Build a runtime-owned monitoring/evaluation record for a Policy Design Case."""

    payload = {
        "schema_version": IMPLEMENTATION_MONITORING_EVALUATION_SCHEMA_VERSION,
        "contract_id": IMPLEMENTATION_MONITORING_EVALUATION_CONTRACT_ID,
        "record_id": record_id,
        "case_id": case_id,
        "claim_ids": list(claim_ids),
        "implementation_contract": dict(implementation_contract),
        "monitoring_plan": dict(monitoring_plan),
        "evaluation_design": dict(evaluation_design),
        "publication_order": {
            "publication_authority_ref": publication_authority_ref,
            "created_before_publication_authority": created_before_publication_authority,
        },
        "ddm_monitoring": _ddm_event_groups(ddm_events),
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }
    return validate_implementation_monitoring_evaluation_record(payload)


def validate_implementation_monitoring_evaluation_record(
    record: Mapping[str, Any],
    *,
    required_claim_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate the implementation/monitoring/evaluation record used by closeout."""

    if not isinstance(record, Mapping):
        raise ImplementationMonitoringEvaluationError(
            "policy_design_implementation_monitoring_record_missing",
            "Implementation monitoring/evaluation record must be a mapping.",
        )
    normalized = dict(record)
    schema_version = _required_text(
        record.get("schema_version"),
        "schema_version",
        "policy_design_implementation_monitoring_schema_version_missing",
    )
    if schema_version != IMPLEMENTATION_MONITORING_EVALUATION_SCHEMA_VERSION:
        raise ImplementationMonitoringEvaluationError(
            "policy_design_implementation_monitoring_schema_version_invalid",
            "Implementation monitoring/evaluation record must use the Phase 27.2 schema.",
            "schema_version",
        )
    normalized["schema_version"] = IMPLEMENTATION_MONITORING_EVALUATION_SCHEMA_VERSION
    normalized["contract_id"] = (
        _text(record.get("contract_id")) or IMPLEMENTATION_MONITORING_EVALUATION_CONTRACT_ID
    )
    normalized["record_id"] = _required_text(
        record.get("record_id") or record.get("id"),
        "record_id",
        "policy_design_implementation_monitoring_record_id_missing",
    )
    normalized["case_id"] = _required_text(
        record.get("case_id"),
        "case_id",
        "policy_design_implementation_monitoring_case_id_missing",
    )
    claim_ids = _text_values(record.get("claim_ids") or record.get("affected_claim_ids"))
    if not claim_ids:
        raise ImplementationMonitoringEvaluationError(
            "policy_design_implementation_monitoring_claim_ref_missing",
            "Implementation monitoring/evaluation record must bind at least one claim.",
            "claim_ids",
        )
    required_claims = set(_text_values(required_claim_ids))
    if required_claims and required_claims.difference(claim_ids):
        raise ImplementationMonitoringEvaluationError(
            "policy_design_implementation_monitoring_claim_ref_missing",
            "Implementation monitoring/evaluation record does not cover all required claims.",
            "claim_ids",
        )
    normalized["claim_ids"] = claim_ids

    normalized["implementation_contract"] = _implementation_contract(
        record.get("implementation_contract")
    )
    normalized["monitoring_plan"] = _monitoring_plan(record.get("monitoring_plan"))
    normalized["evaluation_design"] = _evaluation_design(record.get("evaluation_design"))
    normalized["publication_order"] = _publication_order(record.get("publication_order"))
    normalized["ddm_monitoring"] = _validate_ddm_monitoring(
        record.get("ddm_monitoring") or record.get("ddm_events"),
        claim_ids=claim_ids,
    )
    _required_text(
        record.get("evidence_ref") or record.get("cas_ref"),
        "evidence_ref",
        "policy_design_implementation_monitoring_runtime_ref_missing",
    )
    _required_text(
        record.get("runtime_event_ref"),
        "runtime_event_ref",
        "policy_design_implementation_monitoring_runtime_event_missing",
    )
    return normalized


def _implementation_contract(value: object) -> dict[str, Any]:
    record = _required_mapping(
        value,
        "implementation_contract",
        "policy_design_implementation_contract_missing",
        "Implementation contract is required before publication authority.",
    )
    for field in (
        "contract_id",
        "intervention_ref",
        "responsible_owner",
        "start_date",
        "affected_claim_ids",
    ):
        _require_surface(
            record.get(field),
            f"implementation_contract.{field}",
            "policy_design_implementation_contract_missing",
        )
    return dict(record)


def _monitoring_plan(value: object) -> dict[str, Any]:
    record = _required_mapping(
        value,
        "monitoring_plan",
        "policy_design_monitoring_plan_missing",
        "Monitoring plan is required before publication authority.",
    )
    for field in (
        "plan_id",
        "indicators",
        "observation_windows",
        "review_cadence",
        "trigger_thresholds",
        "responsible_owners",
    ):
        _require_surface(
            record.get(field),
            f"monitoring_plan.{field}",
            "policy_design_monitoring_plan_missing",
        )
    return dict(record)


def _evaluation_design(value: object) -> dict[str, Any]:
    record = _required_mapping(
        value,
        "evaluation_design",
        "policy_design_evaluation_design_missing",
        "Evaluation design is required before publication authority.",
    )
    for field in (
        "design_id",
        "design_type",
        "estimand",
        "outcome_metrics",
        "comparison_strategy",
        "observation_windows",
    ):
        _require_surface(
            record.get(field),
            f"evaluation_design.{field}",
            "policy_design_evaluation_design_missing",
        )
    return dict(record)


def _publication_order(value: object) -> dict[str, Any]:
    record = _required_mapping(
        value,
        "publication_order",
        "policy_design_implementation_publication_order_invalid",
        "Implementation monitoring/evaluation record must carry publication ordering.",
    )
    if record.get("created_before_publication_authority") is not True:
        raise ImplementationMonitoringEvaluationError(
            "policy_design_implementation_publication_order_invalid",
            (
                "Implementation contract, monitoring plan, and evaluation design must "
                "be created before publication authority."
            ),
            "publication_order.created_before_publication_authority",
        )
    _required_text(
        record.get("publication_authority_ref"),
        "publication_order.publication_authority_ref",
        "policy_design_implementation_publication_order_invalid",
    )
    return dict(record)


def _validate_ddm_monitoring(
    value: object,
    *,
    claim_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    monitoring = _required_mapping(
        value,
        "ddm_monitoring",
        "policy_design_ddm_evidence_missing",
        (
            "Monitoring record must carry DDM shift, degradation, readiness, "
            "incident, and root-cause evidence."
        ),
    )
    normalized: dict[str, list[dict[str, Any]]] = {}
    for group, expected_type in DDM_EVENT_GROUPS.items():
        rows = _mapping_rows(monitoring.get(group))
        if not rows:
            raise ImplementationMonitoringEvaluationError(
                "policy_design_ddm_evidence_missing",
                f"DDM monitoring evidence is missing {group}.",
                f"ddm_monitoring.{group}",
            )
        normalized[group] = [
            _validate_ddm_event(
                row,
                expected_event_type=expected_type,
                claim_ids=claim_ids,
                field=f"ddm_monitoring.{group}",
            )
            for row in rows
        ]
    _validate_incident_root_cause_links(normalized)
    return normalized


def _validate_ddm_event(
    event: Mapping[str, Any],
    *,
    expected_event_type: str,
    claim_ids: list[str],
    field: str,
) -> dict[str, Any]:
    normalized = dict(event)
    event_type = _required_text(
        event.get("event_type"),
        f"{field}.event_type",
        "policy_design_ddm_evidence_missing",
    )
    if event_type != expected_event_type:
        raise ImplementationMonitoringEvaluationError(
            "policy_design_ddm_event_type_invalid",
            f"Expected {expected_event_type}, got {event_type}.",
            f"{field}.event_type",
        )
    normalized["event_id"] = _required_text(
        event.get("event_id"),
        f"{field}.event_id",
        "policy_design_ddm_evidence_missing",
    )
    affected_claim_ids = _text_values(event.get("affected_claim_ids"))
    if not affected_claim_ids or set(affected_claim_ids).isdisjoint(claim_ids):
        raise ImplementationMonitoringEvaluationError(
            "policy_design_ddm_claim_link_missing",
            "DDM events must reference affected Policy Design Case claims.",
            f"{field}.affected_claim_ids",
        )
    normalized["affected_claim_ids"] = affected_claim_ids
    if not _text_values(event.get("affected_evidence_line_refs")):
        raise ImplementationMonitoringEvaluationError(
            "policy_design_ddm_evidence_line_link_missing",
            "DDM events must reference affected evidence lines.",
            f"{field}.affected_evidence_line_refs",
        )
    if not (
        _text(event.get("downstream_status"))
        or _text(event.get("publication_status"))
        or _text(event.get("readiness_status"))
    ):
        raise ImplementationMonitoringEvaluationError(
            "policy_design_ddm_downstream_status_missing",
            "DDM events must name downstream readiness or publication status.",
            f"{field}.downstream_status",
        )
    _required_text(
        event.get("evidence_ref") or event.get("cas_ref"),
        f"{field}.evidence_ref",
        "policy_design_ddm_runtime_ref_missing",
    )
    _required_text(
        event.get("runtime_event_ref"),
        f"{field}.runtime_event_ref",
        "policy_design_ddm_runtime_event_missing",
    )
    return normalized


def _validate_incident_root_cause_links(
    monitoring: Mapping[str, list[dict[str, Any]]],
) -> None:
    root_cause_ids = {
        event["event_id"] for event in monitoring.get("root_cause_events", [])
    }
    for incident in monitoring.get("incident_events", []):
        refs = set(_text_values(incident.get("root_cause_event_ids")))
        if not refs or refs.isdisjoint(root_cause_ids):
            raise ImplementationMonitoringEvaluationError(
                "policy_design_ddm_root_cause_missing",
                "DDM incident events must link to root-cause evidence.",
                "ddm_monitoring.incident_events.root_cause_event_ids",
            )


def _ddm_event_groups(value: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        group: [dict(row) for row in _mapping_rows(value.get(group))]
        for group in DDM_EVENT_GROUPS
    }


def _required_mapping(
    value: object,
    field: str,
    code: str,
    message: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise ImplementationMonitoringEvaluationError(code, message, field)
    return value


def _mapping_rows(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, list | tuple):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _require_surface(value: object, field: str, code: str) -> None:
    if not _surface_present(value):
        raise ImplementationMonitoringEvaluationError(
            code,
            f"Required implementation monitoring/evaluation surface is missing: {field}.",
            field,
        )


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
        raise ImplementationMonitoringEvaluationError(
            code,
            f"Required implementation monitoring/evaluation text is missing: {field}.",
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


__all__ = [
    "DDM_EVENT_GROUPS",
    "IMPLEMENTATION_MONITORING_EVALUATION_CONTRACT_ID",
    "IMPLEMENTATION_MONITORING_EVALUATION_SCHEMA_VERSION",
    "ImplementationMonitoringEvaluationError",
    "build_implementation_monitoring_evaluation_record",
    "validate_implementation_monitoring_evaluation_record",
]

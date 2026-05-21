"""Policy Design Case records for observability and orchestration static audits."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

DORMANT_CAPABILITY_INVENTORY_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.dormant_capability_inventory.v1"
)
SKIP_CAUSALITY_LEDGER_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.skip_causality_ledger.v1"
)
FRESHNESS_POLICY_TIME_SEMANTICS_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.freshness_policy_time_semantics.v1"
)

DORMANT_CAPABILITY_INVENTORY_RECORD_KEY = "dormant_capability_inventory"
SKIP_CAUSALITY_LEDGER_RECORD_KEY = "skip_causality_ledger"
FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY = "freshness_policy_time_semantics"

REQUIRED_DORMANT_CAPABILITY_IDS = frozenset(
    {
        "lex_legal_kg",
        "fabric_dataset_catalog_graph",
        "foundry_method_catalog_expectations",
        "scientist_workflow_nodes",
    }
)
REQUIRED_FRESHNESS_EVIDENCE_KINDS = frozenset(
    {
        "legal",
        "data",
        "benchmark",
        "decision",
    }
)
STALE_FRESHNESS_STATUSES = frozenset(
    {
        "expired",
        "fail",
        "failed",
        "missing",
        "outdated",
        "stale",
    }
)
PASSING_FRESHNESS_STATUSES = frozenset(
    {
        "current",
        "fresh",
        "pass",
        "passed",
        "valid",
    }
)
PASSING_RECORD_STATUSES = frozenset({"pass", "passed", "ok", "accepted", "approved"})
DEFAULT_OBSERVABILITY_STATIC_AUDIT_NEXT_ACTION = (
    "Emit Phase 28.3 dormant-capability, skip-causality, and "
    "freshness/policy-time records inside the runtime-owned Policy Design Case."
)


@dataclass(frozen=True)
class PolicyDesignObservabilityStaticAuditIssue:
    """Scorecard-readable issue for Phase 28.3 static audit records."""

    code: str
    message: str
    field: str
    evidence_ref: str | None = None
    affected_claim: str | None = None
    next_action: str = DEFAULT_OBSERVABILITY_STATIC_AUDIT_NEXT_ACTION

    def as_gate_fields(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "evidence_ref": self.evidence_ref,
            "affected_claim": self.affected_claim,
            "next_action": self.next_action,
        }


def build_dormant_capability_inventory_record(
    *,
    record_id: str,
    capabilities: Iterable[Mapping[str, Any]],
    evidence_ref: str,
    runtime_event_ref: str,
    next_diagnostic_command: str,
    status: str = "pass",
) -> dict[str, Any]:
    """Build the PDD-017 dormant capability inventory record."""

    payload = {
        "schema_version": DORMANT_CAPABILITY_INVENTORY_SCHEMA_VERSION,
        "record_id": record_id,
        "record_family": "capability_mode_and_fallback_selection.v1",
        "status": status,
        "capabilities": [dict(row) for row in capabilities],
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
        "next_diagnostic_command": next_diagnostic_command,
    }
    issues = _dormant_capability_inventory_issues(payload)
    if issues:
        issue = issues[0]
        raise ValueError(f"{issue.code}: {issue.message}")
    return payload


def build_skip_causality_ledger_record(
    *,
    record_id: str,
    skipped_nodes: Iterable[Mapping[str, Any]],
    projection_preserves_reason_fields: bool,
    evidence_ref: str,
    runtime_event_ref: str,
    next_diagnostic_command: str,
    status: str = "pass",
) -> dict[str, Any]:
    """Build the PDD-018 skip-causality preservation ledger."""

    payload = {
        "schema_version": SKIP_CAUSALITY_LEDGER_SCHEMA_VERSION,
        "record_id": record_id,
        "record_family": "capability_mode_and_fallback_selection.v1",
        "status": status,
        "projection_preserves_reason_fields": projection_preserves_reason_fields,
        "skipped_nodes": [dict(row) for row in skipped_nodes],
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
        "next_diagnostic_command": next_diagnostic_command,
    }
    issues = _skip_causality_ledger_issues(payload)
    if issues:
        issue = issues[0]
        raise ValueError(f"{issue.code}: {issue.message}")
    return payload


def build_freshness_policy_time_semantics_record(
    *,
    record_id: str,
    policy_time: str,
    evidence_time_bindings: Iterable[Mapping[str, Any]],
    continuous_governance_triggers: Iterable[Mapping[str, Any]],
    final_artifact_date_assumptions: Iterable[Mapping[str, Any]],
    evidence_ref: str,
    runtime_event_ref: str,
    next_diagnostic_command: str,
    status: str = "pass",
) -> dict[str, Any]:
    """Build the PDD-045 freshness and policy-time semantics record."""

    payload = {
        "schema_version": FRESHNESS_POLICY_TIME_SEMANTICS_SCHEMA_VERSION,
        "record_id": record_id,
        "record_family": "numeric_time_and_geography_semantics.v1",
        "status": status,
        "policy_time": policy_time,
        "evidence_time_bindings": [dict(row) for row in evidence_time_bindings],
        "continuous_governance_triggers": [
            dict(row) for row in continuous_governance_triggers
        ],
        "final_artifact_date_assumptions": [
            dict(row) for row in final_artifact_date_assumptions
        ],
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
        "next_diagnostic_command": next_diagnostic_command,
    }
    issues = _freshness_policy_time_semantics_issues(payload)
    if issues:
        issue = issues[0]
        raise ValueError(f"{issue.code}: {issue.message}")
    return payload


def validate_observability_orchestration_static_audit_records(
    case: Mapping[str, Any],
) -> tuple[PolicyDesignObservabilityStaticAuditIssue, ...]:
    """Validate Phase 28.3 observability/orchestration records embedded in a PDC."""

    issues: list[PolicyDesignObservabilityStaticAuditIssue] = []
    dormant = case.get(DORMANT_CAPABILITY_INVENTORY_RECORD_KEY)
    if not isinstance(dormant, Mapping):
        issues.append(
            _issue(
                code="policy_design_dormant_capability_inventory_missing",
                message=(
                    "Policy Design Case is missing the PDD-017 dormant capability "
                    "integration inventory."
                ),
                field=DORMANT_CAPABILITY_INVENTORY_RECORD_KEY,
            )
        )
    else:
        issues.extend(_dormant_capability_inventory_issues(dormant))

    skip_ledger = case.get(SKIP_CAUSALITY_LEDGER_RECORD_KEY)
    if not isinstance(skip_ledger, Mapping):
        issues.append(
            _issue(
                code="policy_design_skip_causality_ledger_missing",
                message=(
                    "Policy Design Case is missing the PDD-018 skip-causality "
                    "preservation ledger."
                ),
                field=SKIP_CAUSALITY_LEDGER_RECORD_KEY,
            )
        )
    else:
        issues.extend(_skip_causality_ledger_issues(skip_ledger))

    freshness = case.get(FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY)
    if not isinstance(freshness, Mapping):
        issues.append(
            _issue(
                code="policy_design_freshness_policy_time_semantics_missing",
                message=(
                    "Policy Design Case is missing the PDD-045 freshness and "
                    "policy-time semantics record."
                ),
                field=FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY,
            )
        )
    else:
        issues.extend(_freshness_policy_time_semantics_issues(freshness))
    return tuple(issues)


def _dormant_capability_inventory_issues(
    record: Mapping[str, Any],
) -> list[PolicyDesignObservabilityStaticAuditIssue]:
    issues: list[PolicyDesignObservabilityStaticAuditIssue] = []
    evidence_ref = _text(record.get("evidence_ref") or record.get("cas_ref"))
    issues.extend(
        _record_shell_issues(
            record,
            key=DORMANT_CAPABILITY_INVENTORY_RECORD_KEY,
            expected_schema=DORMANT_CAPABILITY_INVENTORY_SCHEMA_VERSION,
            schema_code="policy_design_dormant_capability_inventory_schema_invalid",
            missing_code="policy_design_dormant_capability_inventory_incomplete",
            evidence_ref=evidence_ref,
        )
    )
    rows = _mapping_rows(record.get("capabilities"))
    if not rows:
        issues.append(
            _issue(
                code="policy_design_dormant_capability_inventory_incomplete",
                message="Dormant capability inventory must list audited capabilities.",
                field=f"{DORMANT_CAPABILITY_INVENTORY_RECORD_KEY}.capabilities",
                evidence_ref=evidence_ref,
            )
        )
        return issues

    seen = {_text(row.get("capability")) for row in rows}
    missing_capabilities = sorted(
        REQUIRED_DORMANT_CAPABILITY_IDS - {value for value in seen if value}
    )
    if missing_capabilities:
        issues.append(
            _issue(
                code="policy_design_dormant_capability_inventory_incomplete",
                message=(
                    "Dormant capability inventory is missing required subsystem "
                    f"rows: {', '.join(missing_capabilities)}."
                ),
                field=f"{DORMANT_CAPABILITY_INVENTORY_RECORD_KEY}.capabilities",
                evidence_ref=evidence_ref,
            )
        )
    required_fields = (
        "capability",
        "available",
        "invoked",
        "input_contract",
        "output_artifact",
        "consumer",
        "current_break_point",
    )
    for index, row in enumerate(rows):
        missing = [
            field
            for field in required_fields
            if row.get(field) in (None, "", [], {})
        ]
        if missing:
            issues.append(
                _issue(
                    code="policy_design_dormant_capability_inventory_incomplete",
                    message=(
                        "Dormant capability row must state availability, invocation, "
                        "contracts, artifacts, consumers, and the current break point."
                    ),
                    field=(
                        f"{DORMANT_CAPABILITY_INVENTORY_RECORD_KEY}."
                        f"capabilities[{index}].{missing[0]}"
                    ),
                    evidence_ref=evidence_ref,
                )
            )
    return issues


def _skip_causality_ledger_issues(
    record: Mapping[str, Any],
) -> list[PolicyDesignObservabilityStaticAuditIssue]:
    issues: list[PolicyDesignObservabilityStaticAuditIssue] = []
    evidence_ref = _text(record.get("evidence_ref") or record.get("cas_ref"))
    issues.extend(
        _record_shell_issues(
            record,
            key=SKIP_CAUSALITY_LEDGER_RECORD_KEY,
            expected_schema=SKIP_CAUSALITY_LEDGER_SCHEMA_VERSION,
            schema_code="policy_design_skip_causality_ledger_schema_invalid",
            missing_code="policy_design_skip_causality_explanation_missing",
            evidence_ref=evidence_ref,
        )
    )
    if record.get("projection_preserves_reason_fields") is not True:
        issues.append(
            _issue(
                code="policy_design_skip_causality_projection_loss",
                message=(
                    "Skip-causality ledger must prove event projection preserves "
                    "node reason fields."
                ),
                field=f"{SKIP_CAUSALITY_LEDGER_RECORD_KEY}.projection_preserves_reason_fields",
                evidence_ref=evidence_ref,
            )
        )
    skipped_nodes = _mapping_rows(record.get("skipped_nodes"))
    if not skipped_nodes and record.get("no_skips_attested") is not True:
        issues.append(
            _issue(
                code="policy_design_skip_causality_explanation_missing",
                message=(
                    "Skip-causality ledger must either list skipped serious nodes "
                    "or attest that no serious nodes were skipped."
                ),
                field=f"{SKIP_CAUSALITY_LEDGER_RECORD_KEY}.skipped_nodes",
                evidence_ref=evidence_ref,
            )
        )
        return issues

    required_fields = (
        "node_id",
        "reason_code",
        "missing_input",
        "prerequisite_status",
        "downstream_impact",
        "profile_policy",
        "raw_node_outcome_ref",
        "progress_event_ref",
        "node_event_ref",
    )
    for index, row in enumerate(skipped_nodes):
        missing = [
            field
            for field in required_fields
            if row.get(field) in (None, "", [], {})
        ]
        if missing:
            issues.append(
                _issue(
                    code="policy_design_skip_causality_explanation_missing",
                    message=(
                        "Every skipped serious node must preserve reason code, "
                        "missing input, prerequisites, downstream impact, profile "
                        "policy, and raw/progress/node event refs."
                    ),
                    field=(
                        f"{SKIP_CAUSALITY_LEDGER_RECORD_KEY}."
                        f"skipped_nodes[{index}].{missing[0]}"
                    ),
                    evidence_ref=evidence_ref,
                )
            )
    return issues


def _freshness_policy_time_semantics_issues(
    record: Mapping[str, Any],
) -> list[PolicyDesignObservabilityStaticAuditIssue]:
    issues: list[PolicyDesignObservabilityStaticAuditIssue] = []
    evidence_ref = _text(record.get("evidence_ref") or record.get("cas_ref"))
    issues.extend(
        _record_shell_issues(
            record,
            key=FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY,
            expected_schema=FRESHNESS_POLICY_TIME_SEMANTICS_SCHEMA_VERSION,
            schema_code="policy_design_freshness_policy_time_semantics_schema_invalid",
            missing_code="policy_design_policy_time_metadata_missing",
            evidence_ref=evidence_ref,
        )
    )
    record_policy_time = _text(record.get("policy_time"))
    if record_policy_time is None:
        issues.append(
            _issue(
                code="policy_design_policy_time_metadata_missing",
                message="Freshness semantics record must include normalized policy time.",
                field=f"{FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY}.policy_time",
                evidence_ref=evidence_ref,
            )
        )
    bindings = _mapping_rows(record.get("evidence_time_bindings"))
    if not bindings:
        issues.append(
            _issue(
                code="policy_design_policy_time_metadata_missing",
                message=(
                    "Freshness semantics record must bind legal, data, benchmark, "
                    "and decision evidence to policy time."
                ),
                field=f"{FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY}.evidence_time_bindings",
                evidence_ref=evidence_ref,
            )
        )
        return issues

    seen_kinds = {_text(row.get("evidence_kind")) for row in bindings}
    missing_kinds = sorted(
        REQUIRED_FRESHNESS_EVIDENCE_KINDS - {value for value in seen_kinds if value}
    )
    if missing_kinds:
        issues.append(
            _issue(
                code="policy_design_policy_time_metadata_missing",
                message=(
                    "Freshness semantics record is missing required evidence kinds: "
                    f"{', '.join(missing_kinds)}."
                ),
                field=f"{FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY}.evidence_time_bindings",
                evidence_ref=evidence_ref,
            )
        )
    for index, row in enumerate(bindings):
        issues.extend(
            _freshness_binding_issues(
                row,
                index=index,
                record_policy_time=record_policy_time,
                evidence_ref=evidence_ref,
            )
        )
    if not _mapping_rows(record.get("continuous_governance_triggers")):
        issues.append(
            _issue(
                code="policy_design_policy_time_metadata_missing",
                message=(
                    "Freshness semantics record must include stale/reissue/withdrawal "
                    "continuous-governance triggers."
                ),
                field=(
                    f"{FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY}."
                    "continuous_governance_triggers"
                ),
                evidence_ref=evidence_ref,
            )
        )
    if not _mapping_rows(record.get("final_artifact_date_assumptions")):
        issues.append(
            _issue(
                code="policy_design_policy_time_metadata_missing",
                message=(
                    "Freshness semantics record must expose final artifact date "
                    "assumptions."
                ),
                field=(
                    f"{FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY}."
                    "final_artifact_date_assumptions"
                ),
                evidence_ref=evidence_ref,
            )
        )
    return issues


def _freshness_binding_issues(
    row: Mapping[str, Any],
    *,
    index: int,
    record_policy_time: str | None,
    evidence_ref: str | None,
) -> list[PolicyDesignObservabilityStaticAuditIssue]:
    issues: list[PolicyDesignObservabilityStaticAuditIssue] = []
    prefix = f"{FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY}.evidence_time_bindings[{index}]"
    row_policy_time = _text(row.get("policy_time"))
    policy_time = row_policy_time or record_policy_time
    evidence_as_of = _text(
        row.get("evidence_as_of")
        or row.get("as_of")
        or row.get("updated_at")
        or row.get("generated_at")
        or row.get("published_at")
    )
    missing = []
    for field, value in (
        ("evidence_kind", _text(row.get("evidence_kind"))),
        ("policy_time", row_policy_time),
        ("evidence_as_of", evidence_as_of),
        ("freshness_status", _text(row.get("freshness_status") or row.get("status"))),
        ("acceptable_recency_window_days", _recency_window_days(row)),
        ("evidence_ref", _text(row.get("evidence_ref") or row.get("cas_ref"))),
    ):
        if value in (None, "", [], {}):
            missing.append(field)
    if missing:
        issues.append(
            _issue(
                code="policy_design_policy_time_metadata_missing",
                message=(
                    "Every freshness binding must include evidence kind, policy time, "
                    "evidence as-of time, recency window, freshness status, and "
                    "runtime evidence ref."
                ),
                field=f"{prefix}.{missing[0]}",
                evidence_ref=evidence_ref,
            )
        )
    status = _text(row.get("freshness_status") or row.get("status"))
    normalized_status = status.casefold().replace("-", "_") if status else ""
    if normalized_status in STALE_FRESHNESS_STATUSES:
        issues.append(
            _issue(
                code="policy_design_freshness_policy_time_stale",
                message="Freshness binding is stale for its policy-time semantics.",
                field=f"{prefix}.freshness_status",
                evidence_ref=_text(row.get("evidence_ref") or row.get("cas_ref"))
                or evidence_ref,
            )
        )
    elif status and normalized_status not in PASSING_FRESHNESS_STATUSES:
        issues.append(
            _issue(
                code="policy_design_freshness_policy_time_status_invalid",
                message="Freshness binding must use a passing freshness status.",
                field=f"{prefix}.freshness_status",
                evidence_ref=_text(row.get("evidence_ref") or row.get("cas_ref"))
                or evidence_ref,
            )
        )
    if policy_time and evidence_as_of:
        age_issue = _freshness_age_issue(
            policy_time=policy_time,
            evidence_as_of=evidence_as_of,
            window_days=_recency_window_days(row),
            field_prefix=prefix,
            evidence_ref=_text(row.get("evidence_ref") or row.get("cas_ref"))
            or evidence_ref,
        )
        if age_issue is not None:
            issues.append(age_issue)
    return issues


def _record_shell_issues(
    record: Mapping[str, Any],
    *,
    key: str,
    expected_schema: str,
    schema_code: str,
    missing_code: str,
    evidence_ref: str | None,
) -> list[PolicyDesignObservabilityStaticAuditIssue]:
    issues: list[PolicyDesignObservabilityStaticAuditIssue] = []
    if _text(record.get("schema_version")) != expected_schema:
        issues.append(
            _issue(
                code=schema_code,
                message=f"{key} must use schema {expected_schema}.",
                field=f"{key}.schema_version",
                evidence_ref=evidence_ref,
            )
        )
    status = _status(record.get("status"))
    if status not in PASSING_RECORD_STATUSES:
        issues.append(
            _issue(
                code=f"policy_design_{key}_status_not_pass",
                message=f"{key} must have a passing status for serious closeout.",
                field=f"{key}.status",
                evidence_ref=evidence_ref,
            )
        )
    for field in (
        "record_id",
        "evidence_ref",
        "runtime_event_ref",
        "next_diagnostic_command",
    ):
        value = record.get(field)
        if field == "evidence_ref" and value is None:
            value = record.get("cas_ref")
        if _text(value) is None:
            issues.append(
                _issue(
                    code=missing_code,
                    message=(
                        f"{key} must include record identity, runtime refs, and "
                        "the next diagnostic command."
                    ),
                    field=f"{key}.{field}",
                    evidence_ref=evidence_ref,
                )
            )
    return issues


def _freshness_age_issue(
    *,
    policy_time: str,
    evidence_as_of: str,
    window_days: int | None,
    field_prefix: str,
    evidence_ref: str | None,
) -> PolicyDesignObservabilityStaticAuditIssue | None:
    if window_days is None:
        return None
    policy_date = _parse_datetime(policy_time)
    evidence_date = _parse_datetime(evidence_as_of)
    if policy_date is None or evidence_date is None:
        return _issue(
            code="policy_design_policy_time_metadata_missing",
            message="Freshness binding has unparseable policy or evidence time.",
            field=f"{field_prefix}.policy_time",
            evidence_ref=evidence_ref,
        )
    age_days = (policy_date - evidence_date).days
    if age_days > window_days:
        return _issue(
            code="policy_design_freshness_policy_time_stale",
            message=(
                "Evidence is older than the accepted recency window for the "
                "normalized policy time."
            ),
            field=f"{field_prefix}.acceptable_recency_window_days",
            evidence_ref=evidence_ref,
        )
    return None


def _recency_window_days(row: Mapping[str, Any]) -> int | None:
    value = row.get("acceptable_recency_window_days") or row.get("freshness_window_days")
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    text = _text(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Iterable) and not isinstance(value, str | bytes):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _parse_datetime(value: str) -> datetime | None:
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        try:
            parsed = datetime.strptime(candidate, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _status(value: object) -> str:
    text = _text(value)
    return text.casefold().replace("-", "_") if text else ""


def _issue(
    *,
    code: str,
    message: str,
    field: str,
    evidence_ref: str | None = None,
    affected_claim: str | None = None,
    next_action: str | None = None,
) -> PolicyDesignObservabilityStaticAuditIssue:
    return PolicyDesignObservabilityStaticAuditIssue(
        code=code,
        message=message,
        field=field,
        evidence_ref=evidence_ref,
        affected_claim=affected_claim,
        next_action=next_action or DEFAULT_OBSERVABILITY_STATIC_AUDIT_NEXT_ACTION,
    )


__all__ = [
    "DORMANT_CAPABILITY_INVENTORY_RECORD_KEY",
    "DORMANT_CAPABILITY_INVENTORY_SCHEMA_VERSION",
    "FRESHNESS_POLICY_TIME_SEMANTICS_RECORD_KEY",
    "FRESHNESS_POLICY_TIME_SEMANTICS_SCHEMA_VERSION",
    "SKIP_CAUSALITY_LEDGER_RECORD_KEY",
    "SKIP_CAUSALITY_LEDGER_SCHEMA_VERSION",
    "PolicyDesignObservabilityStaticAuditIssue",
    "build_dormant_capability_inventory_record",
    "build_freshness_policy_time_semantics_record",
    "build_skip_causality_ledger_record",
    "validate_observability_orchestration_static_audit_records",
]

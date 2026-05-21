"""External, plugin, dependency, and client-surface Policy Design Case checks."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.external_plugin_dependency_client_surface.v1"
)
EXTERNAL_CLIENT_SURFACE_RECORD_FAMILY = "publication_trust_and_external_governance.v1"
EXTERNAL_CLIENT_SURFACE_VALIDATION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.external_plugin_dependency_client_surface.validation.v1"
)
EXTERNAL_CLIENT_SURFACE_PDDS = (
    "PDD-073",
    "PDD-085",
    "PDD-102",
    "PDD-089",
    "PDD-091",
    "PDD-092",
    "PDD-093",
    "PDD-094",
)

_PASS_STATUSES = {"pass", "passed", "ok", "accepted", "approved", "active"}
_BLOCKED_DEPENDENCY_STATUSES = {
    "blocked",
    "brownout",
    "expired",
    "fail",
    "failed",
    "incompatible",
    "revoked",
    "stale",
    "unknown",
    "withdrawn",
}
_CLIENT_AUTHORITY_STATES = {
    "queued",
    "optimistic",
    "pending",
    "client_accepted",
    "offline",
}
_SERVER_AUTHORITY_STATES = {"server_accepted", "accepted", "signed", "persisted", "final"}

_SURFACE_REQUIRED_FIELDS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "connector_acquisition": (
        "policy_design_connector_acquisition_governance_missing",
        (
            "connector_id",
            "owner",
            "acquisition_ledger_ref",
            "fetch_safety_ref",
            "source_version_ref",
            "freshness_strategy_ref",
            "sla_ref",
            "quality_contract_ref",
            "data_classification",
            "license_ref",
            "replay_ref",
            "refusal_policy_ref",
        ),
        "PDD-073 connector acquisition governance is incomplete.",
    ),
    "plugin_capability_isolation": (
        "policy_design_plugin_capability_isolation_missing",
        (
            "plugin_id",
            "component_index_ref",
            "source_provenance_ref",
            "abi_compatibility_ref",
            "dependency_compatibility_ref",
            "duplicate_check_ref",
            "allowlist_ref",
            "owner",
            "capability_scope",
            "isolation_ref",
        ),
        "PDD-085 plugin discovery, ABI, ownership, or capability isolation is incomplete.",
    ),
    "external_dependency_contracts": (
        "policy_design_external_dependency_rights_missing",
        (
            "dependency_id",
            "provider",
            "contract_ref",
            "terms_ref",
            "license_ref",
            "use_rights_ref",
            "retention_policy_ref",
            "export_rights_ref",
            "jurisdiction_ref",
            "outage_plan_ref",
            "withdrawal_replay_rights_ref",
            "correction_replay_rights_ref",
            "risk_status",
        ),
        "PDD-102 external dependency rights and provider risk evidence is incomplete.",
    ),
    "external_evidence_provenance": (
        "policy_design_external_evidence_provenance_missing",
        (
            "source_id",
            "claim_ids",
            "provider_source_ref",
            "provenance_ref",
            "replay_ref",
            "freshness_ref",
            "rights_ref",
            "support_handoff_ref",
        ),
        "External evidence provenance cannot be tied to final claims.",
    ),
    "offline_mutation_authority": (
        "policy_design_offline_mutation_authority_missing",
        (
            "mutation_id",
            "authority_state",
            "queued_state_separated",
            "idempotency_key_ref",
            "auth_freshness_ref",
            "attempt_ref",
            "conflict_resolution_ref",
            "rollback_ref",
        ),
        "PDD-089 offline or optimistic mutation authority evidence is incomplete.",
    ),
    "collaboration_attribution": (
        "policy_design_collaboration_attribution_missing",
        (
            "collaboration_id",
            "participant_identity_ref",
            "attribution_ref",
            "lock_ttl_ref",
            "staleness_check_ref",
            "persisted_review_packet_ref",
            "ephemeral_state_not_authority",
        ),
        "PDD-091 collaboration locks, presence, or attribution evidence is incomplete.",
    ),
    "assistant_composer_provenance": (
        "policy_design_authoring_provenance_missing",
        (
            "composer_id",
            "sanitized_original_prompt_ref",
            "request_hash",
            "locale_ref",
            "defaults_ref",
            "model_profile_ref",
            "flag_refs",
            "draft_state_ref",
            "retention_deletion_ref",
            "compliance_redaction_ref",
        ),
        "PDD-092 assistant/composer authoring provenance is incomplete.",
    ),
    "bureaucratic_rendering_export": (
        "policy_design_bureaucratic_rendering_export_missing",
        (
            "export_id",
            "template_review_ref",
            "template_version_ref",
            "jurisdiction",
            "semantic_section_mapping_ref",
            "export_parity_ref",
            "disclaimer_ref",
            "redaction_ref",
            "official_use_limitation_ref",
            "draft_limitation_ref",
            "official_form_authority",
        ),
        "PDD-093 bureaucratic rendering/export authority evidence is incomplete.",
    ),
    "client_persistence_privacy": (
        "policy_design_client_persistence_privacy_missing",
        (
            "inventory_ref",
            "sensitive_redaction_test_ref",
            "deletion_minimization_ref",
            "service_worker_cache_policy_ref",
            "local_evidence_retention_ref",
            "generated_export_control_ref",
            "server_client_gap_report_ref",
            "public_export_control_ref",
            "sensitive_local_state_allowed",
        ),
        "PDD-094 client persistence, privacy, or local evidence retention is incomplete.",
    ),
}


def validate_external_client_surface_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the composite Phase 28.5 external/client surface record."""

    issues: list[dict[str, str]] = []
    if record.get("schema_version") != EXTERNAL_CLIENT_SURFACE_SCHEMA_VERSION:
        issues.append(
            _issue(
                "policy_design_external_client_surface_schema_version_invalid",
                "External/client surface record must use the current schema version.",
                "schema_version",
            )
        )
    if record.get("record_family") != EXTERNAL_CLIENT_SURFACE_RECORD_FAMILY:
        issues.append(
            _issue(
                "policy_design_external_client_surface_record_family_invalid",
                "External/client surface record must bind to publication trust governance.",
                "record_family",
            )
        )
    if _status(record.get("status")) not in _PASS_STATUSES:
        issues.append(
            _issue(
                "policy_design_external_client_surface_not_passing",
                "External/client surface record must have a passing status.",
                "status",
            )
        )
    for field in ("record_id", "run_id"):
        if not _present(record.get(field)):
            issues.append(
                _issue(
                    "policy_design_external_client_surface_identity_missing",
                    "External/client surface record must include case-bound record identity.",
                    field,
                )
            )
    if not _runtime_artifact_ref(record.get("evidence_ref") or record.get("cas_ref")):
        issues.append(
            _issue(
                "policy_design_external_client_surface_runtime_ref_missing",
                "External/client surface record must include a runtime evidence artifact ref.",
                "evidence_ref",
            )
        )
    if not _runtime_event_ref(record.get("runtime_event_ref")):
        issues.append(
            _issue(
                "policy_design_external_client_surface_runtime_ref_missing",
                "External/client surface record must include a runtime event ref.",
                "runtime_event_ref",
            )
        )

    for field, (code, required_fields, message) in _SURFACE_REQUIRED_FIELDS.items():
        rows = _surface_rows(record.get(field))
        if not rows:
            issues.append(_issue(code, message, field))
            continue
        for index, row in enumerate(rows, start=1):
            issues.extend(
                _required_row_field_issues(
                    row,
                    field=field,
                    index=index,
                    required_fields=required_fields,
                    code=code,
                    message=message,
                )
            )

    issues.extend(_plugin_isolation_risk_issues(record))
    issues.extend(_dependency_risk_issues(record))
    issues.extend(_offline_mutation_authority_issues(record))
    issues.extend(_client_persistence_privacy_issues(record))

    return {
        "schema_version": EXTERNAL_CLIENT_SURFACE_VALIDATION_SCHEMA_VERSION,
        "status": "fail" if issues else "pass",
        "summary": {
            "issue_count": len(issues),
            "pdd_count": len(EXTERNAL_CLIENT_SURFACE_PDDS),
            "surface_count": len(_SURFACE_REQUIRED_FIELDS),
        },
        "issues": issues,
    }


def _required_row_field_issues(
    row: Mapping[str, Any],
    *,
    field: str,
    index: int,
    required_fields: Sequence[str],
    code: str,
    message: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for child_field in required_fields:
        value = row.get(child_field)
        if not _present(value):
            issues.append(_issue(code, message, f"{field}[{index}].{child_field}"))
    return issues


def _plugin_isolation_risk_issues(record: Mapping[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for index, row in enumerate(_surface_rows(record.get("plugin_capability_isolation")), start=1):
        if row.get("development_scan_used") is True and row.get("dev_scan_approved") is not True:
            issues.append(
                _issue(
                    "policy_design_plugin_capability_isolation_missing",
                    "Development-scan plugins require explicit production approval.",
                    f"plugin_capability_isolation[{index}].dev_scan_approved",
                )
            )
        if row.get("capability_escalation") is True:
            issues.append(
                _issue(
                    "policy_design_plugin_capability_escalation_blocked",
                    "Plugin capability escalation cannot satisfy production closeout.",
                    f"plugin_capability_isolation[{index}].capability_escalation",
                )
            )
    return issues


def _dependency_risk_issues(record: Mapping[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for index, row in enumerate(
        _surface_rows(record.get("external_dependency_contracts")),
        start=1,
    ):
        risk_status = _status(row.get("risk_status"))
        if risk_status in _BLOCKED_DEPENDENCY_STATUSES or risk_status not in _PASS_STATUSES:
            issues.append(
                _issue(
                    "policy_design_external_dependency_provider_risk_blocked",
                    "External dependency provider/source rights or risk status blocks closeout.",
                    f"external_dependency_contracts[{index}].risk_status",
                )
            )
    return issues


def _offline_mutation_authority_issues(record: Mapping[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for index, row in enumerate(_surface_rows(record.get("offline_mutation_authority")), start=1):
        state = _status(row.get("authority_state"))
        if row.get("queued_state_separated") is not True:
            issues.append(
                _issue(
                    "policy_design_offline_mutation_authority_missing",
                    "Queued or optimistic client state must be separated from authority.",
                    f"offline_mutation_authority[{index}].queued_state_separated",
                )
            )
        if state in _CLIENT_AUTHORITY_STATES and row.get("presented_as_authoritative") is True:
            issues.append(
                _issue(
                    "policy_design_offline_mutation_authority_missing",
                    "Queued or optimistic client mutation cannot be presented as final authority.",
                    f"offline_mutation_authority[{index}].presented_as_authoritative",
                )
            )
        if state in _SERVER_AUTHORITY_STATES:
            for child_field in ("server_acceptance_ref", "approval_packet_ref"):
                if not _present(row.get(child_field)):
                    issues.append(
                        _issue(
                            "policy_design_offline_mutation_authority_missing",
                            "Server-accepted authority requires signed persisted "
                            "approval evidence.",
                            f"offline_mutation_authority[{index}].{child_field}",
                        )
                    )
        elif state in _CLIENT_AUTHORITY_STATES and not _present(
            row.get("pending_authority_blocker_ref")
        ):
            issues.append(
                _issue(
                    "policy_design_offline_mutation_authority_missing",
                    "Client-pending mutation requires an explicit pending-authority blocker.",
                    f"offline_mutation_authority[{index}].pending_authority_blocker_ref",
                )
            )
    return issues


def _client_persistence_privacy_issues(record: Mapping[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for index, row in enumerate(_surface_rows(record.get("client_persistence_privacy")), start=1):
        if row.get("sensitive_local_state_allowed") is True:
            issues.append(
                _issue(
                    "policy_design_client_persistence_privacy_missing",
                    "Sensitive policy evidence cannot remain in client-local state.",
                    f"client_persistence_privacy[{index}].sensitive_local_state_allowed",
                )
            )
    return issues


def _surface_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple | set | dict):
        return bool(value)
    return True


def _status(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_")


def _runtime_artifact_ref(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return text.startswith(("sha256:", "cas://"))


def _runtime_event_ref(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return text.startswith(("event://", "sha256:", "cas://"))


def _issue(code: str, message: str, field: str) -> dict[str, str]:
    return {"code": code, "message": message, "field": field}

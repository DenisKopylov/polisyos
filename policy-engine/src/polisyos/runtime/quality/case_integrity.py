"""Integrity threat-model records for Policy Design Case evidence graphs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from polisyos.runtime.quality.policy_design_case import (
    policy_design_case_record_family_coverage_scorecard_gates,
)

EVIDENCE_GRAPH_THREAT_MODEL_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.evidence_graph_threat_model.v1"
)
EVIDENCE_GRAPH_THREAT_MODEL_RECORD_FAMILY = "integrity_self_fmea_and_maturity.v1"
EVIDENCE_GRAPH_THREAT_MODEL_RECORD_KEY = "evidence_graph_threat_model"
EVIDENCE_GRAPH_THREATS = (
    "prompt_injection",
    "poisoned_datasets",
    "stale_indexes",
    "malicious_tenants",
    "forged_provenance",
    "compromised_plugins",
    "local_client_leakage",
    "insider_mutation",
)

_PASS_STATUSES = frozenset({"pass", "passed", "ok", "accepted", "approved"})
_MITIGATED_STATUSES = _PASS_STATUSES | frozenset(
    {"bounded", "controlled", "mitigated", "monitored"}
)
_UNBOUNDED_RESIDUAL_RISK = frozenset(
    {"critical", "high", "open", "unbounded", "unknown", "unmitigated"}
)


@dataclass(frozen=True)
class PolicyDesignCaseIntegrityIssue:
    """One scorecard-readable integrity validation issue."""

    code: str
    message: str
    field: str
    evidence_ref: str | None = None
    threat_id: str | None = None

    def as_gate_fields(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "evidence_ref": self.evidence_ref,
            "threat_id": self.threat_id,
        }


def validate_evidence_graph_threat_model_record(
    record: Mapping[str, Any] | None,
) -> list[PolicyDesignCaseIntegrityIssue]:
    """Validate Phase 29.1 adversarial evidence-graph threat records."""

    if not isinstance(record, Mapping):
        return [
            _issue(
                "policy_design_evidence_graph_threat_model_record_missing",
                "Production Policy Design Cases require evidence-graph threat model records.",
                EVIDENCE_GRAPH_THREAT_MODEL_RECORD_KEY,
            )
        ]

    evidence_ref = _text(record.get("evidence_ref") or record.get("cas_ref"))
    issues: list[PolicyDesignCaseIntegrityIssue] = []
    if record.get("schema_version") != EVIDENCE_GRAPH_THREAT_MODEL_SCHEMA_VERSION:
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_schema_invalid",
                "Evidence-graph threat model record must use the Phase 29.1 schema.",
                "schema_version",
                evidence_ref,
            )
        )
    if record.get("record_family") != EVIDENCE_GRAPH_THREAT_MODEL_RECORD_FAMILY:
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_family_invalid",
                "Evidence-graph threat model must bind to integrity self-FMEA and maturity.",
                "record_family",
                evidence_ref,
            )
        )
    if _status(record.get("status")) not in _PASS_STATUSES:
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_status_not_pass",
                "Evidence-graph threat model record must be passing for serious closeout.",
                "status",
                evidence_ref,
            )
        )
    for field in ("record_id", "case_id", "run_id", "job_id", "tenant_id"):
        if not _text(record.get(field)):
            issues.append(
                _issue(
                    "policy_design_evidence_graph_threat_model_identity_missing",
                    "Evidence-graph threat model record must include case-bound identity.",
                    field,
                    evidence_ref,
                )
            )
    if not _runtime_artifact_ref(record.get("evidence_ref") or record.get("cas_ref")):
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_runtime_ref_missing",
                "Evidence-graph threat model record must carry a runtime artifact ref.",
                "evidence_ref",
                evidence_ref,
            )
        )
    if not _runtime_event_ref(record.get("runtime_event_ref")):
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_runtime_event_missing",
                "Evidence-graph threat model record must carry a runtime event ref.",
                "runtime_event_ref",
                evidence_ref,
            )
        )

    rows = _threat_rows(record)
    if not rows:
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_records_missing",
                "Evidence-graph threat model must list threat_records.",
                "threat_records",
                evidence_ref,
            )
        )
        return issues

    rows_by_threat: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        threat_id = _threat_id(row)
        if not threat_id:
            issues.append(
                _issue(
                    "policy_design_evidence_graph_threat_model_threat_id_missing",
                    "Every evidence-graph threat record must identify its threat.",
                    "threat_records.threat_id",
                    evidence_ref,
                )
            )
            continue
        if threat_id not in EVIDENCE_GRAPH_THREATS:
            issues.append(
                _issue(
                    "policy_design_evidence_graph_threat_model_threat_unknown",
                    "Evidence-graph threat record references an out-of-scope threat.",
                    f"threat_records.{threat_id}",
                    evidence_ref,
                    threat_id=threat_id,
                )
            )
            continue
        if threat_id in rows_by_threat:
            issues.append(
                _issue(
                    "policy_design_evidence_graph_threat_model_threat_duplicate",
                    "Evidence-graph threat records must be unique by threat_id.",
                    f"threat_records.{threat_id}",
                    evidence_ref,
                    threat_id=threat_id,
                )
            )
        rows_by_threat[threat_id] = row
        issues.extend(_threat_record_issues(row, threat_id=threat_id, evidence_ref=evidence_ref))

    for threat_id in EVIDENCE_GRAPH_THREATS:
        if threat_id not in rows_by_threat:
            issues.append(
                _issue(
                    "policy_design_evidence_graph_threat_model_threat_missing",
                    "Evidence-graph threat model must cover every Phase 29.1 threat.",
                    f"threat_records.{threat_id}",
                    evidence_ref,
                    threat_id=threat_id,
                )
            )
    return issues


def policy_design_case_integrity_record_family_scorecard_gates(
    case: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return Phase 29 integrity gates for concrete runtime PDC records."""

    return policy_design_case_record_family_coverage_scorecard_gates(
        case,
        phase="policy_design_case_integrity",
        gate_name="policy_design_case.integrity_record_family_coverage",
    )


def _threat_record_issues(
    row: Mapping[str, Any],
    *,
    threat_id: str,
    evidence_ref: str | None,
) -> list[PolicyDesignCaseIntegrityIssue]:
    issues: list[PolicyDesignCaseIntegrityIssue] = []
    if _status(row.get("status")) not in _MITIGATED_STATUSES:
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_threat_not_mitigated",
                "Evidence-graph threat records must be mitigated or explicitly bounded.",
                f"threat_records.{threat_id}.status",
                evidence_ref,
                threat_id=threat_id,
            )
        )
    if not _team_owner(row.get("owner")):
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_owner_missing",
                "Evidence-graph threat records must name a team owner.",
                f"threat_records.{threat_id}.owner",
                evidence_ref,
                threat_id=threat_id,
            )
        )
    for field, code, message in (
        (
            "affected_surfaces",
            "policy_design_evidence_graph_threat_model_surface_missing",
            "Evidence-graph threat records must name affected surfaces.",
        ),
        (
            "attack_paths",
            "policy_design_evidence_graph_threat_model_attack_path_missing",
            "Evidence-graph threat records must name attack paths.",
        ),
        (
            "detection_refs",
            "policy_design_evidence_graph_threat_model_detection_missing",
            "Evidence-graph threat records must include detection evidence refs.",
        ),
        (
            "mitigation_refs",
            "policy_design_evidence_graph_threat_model_mitigation_missing",
            "Evidence-graph threat records must include mitigation evidence refs.",
        ),
    ):
        if not _text_values(row.get(field)):
            issues.append(
                _issue(
                    code,
                    message,
                    f"threat_records.{threat_id}.{field}",
                    evidence_ref,
                    threat_id=threat_id,
                )
            )
    if not _text(row.get("blocker_policy_ref")):
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_blocker_policy_missing",
                "Evidence-graph threat records must define blocker policy refs.",
                f"threat_records.{threat_id}.blocker_policy_ref",
                evidence_ref,
                threat_id=threat_id,
            )
        )
    if _status(row.get("residual_risk")) in _UNBOUNDED_RESIDUAL_RISK:
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_residual_risk_unbounded",
                "Evidence-graph threat residual risk must be bounded for serious closeout.",
                f"threat_records.{threat_id}.residual_risk",
                evidence_ref,
                threat_id=threat_id,
            )
        )
    if not _runtime_artifact_ref(row.get("evidence_ref") or row.get("cas_ref")):
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_threat_runtime_ref_missing",
                "Every evidence-graph threat record must carry runtime evidence.",
                f"threat_records.{threat_id}.evidence_ref",
                evidence_ref,
                threat_id=threat_id,
            )
        )
    if not _runtime_event_ref(row.get("runtime_event_ref")):
        issues.append(
            _issue(
                "policy_design_evidence_graph_threat_model_threat_runtime_event_missing",
                "Every evidence-graph threat record must carry a runtime event ref.",
                f"threat_records.{threat_id}.runtime_event_ref",
                evidence_ref,
                threat_id=threat_id,
            )
        )
    return issues


def _threat_rows(record: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    for key in ("threat_records", "threats", "records"):
        rows = _mapping_rows(record.get(key))
        if rows:
            return rows
    return ()


def _threat_id(row: Mapping[str, Any]) -> str:
    return _status(row.get("threat_id") or row.get("threat") or row.get("id"))


def _issue(
    code: str,
    message: str,
    field: str,
    evidence_ref: str | None = None,
    *,
    threat_id: str | None = None,
) -> PolicyDesignCaseIntegrityIssue:
    return PolicyDesignCaseIntegrityIssue(
        code=code,
        message=message,
        field=field,
        evidence_ref=evidence_ref,
        threat_id=threat_id,
    )


def _mapping_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list | tuple):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _runtime_artifact_ref(value: object) -> bool:
    text = _text(value)
    return bool(text and text.startswith(("sha256:", "cas://")))


def _runtime_event_ref(value: object) -> bool:
    text = _text(value)
    return bool(text and text.startswith(("event://", "sha256:", "cas://")))


def _status(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_")


def _team_owner(value: object) -> bool:
    text = _text(value)
    return bool(text and text.startswith("team-"))


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if not isinstance(value, list | tuple | set):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


__all__ = [
    "EVIDENCE_GRAPH_THREATS",
    "EVIDENCE_GRAPH_THREAT_MODEL_RECORD_FAMILY",
    "EVIDENCE_GRAPH_THREAT_MODEL_RECORD_KEY",
    "EVIDENCE_GRAPH_THREAT_MODEL_SCHEMA_VERSION",
    "PolicyDesignCaseIntegrityIssue",
    "policy_design_case_integrity_record_family_scorecard_gates",
    "validate_evidence_graph_threat_model_record",
]

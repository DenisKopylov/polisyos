"""Pass 1B tenant, CAS, approval, and governance hardening records."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from polisyos.runtime.quality.policy_design_case import (
    policy_design_case_record_family_coverage_scorecard_gates,
)

PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.pass1b_tenant_cas_approval_governance.v1"
)
PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_CONTRACT_ID = (
    "policy_design_case.pass1b_tenant_cas_approval_governance.v1"
)
PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_RECORD_KEY = (
    "pass1b_tenant_cas_approval_governance"
)
PASS1B_HARDENING_SCORECARD_GATE = "policy_design_case.pass1b_hardening"
PASS1B_HARDENING_READINESS_CHECK = "policy_design_case.pass1b_hardening"
PASS1B_HARDENING_NEXT_ACTION = (
    "Emit the Phase 28.1 tenant/CAS/approval/governance hardening record from "
    "runtime quality before governed or production publication closeout."
)

PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_PDDS = (
    "PDD-022",
    "PDD-023",
    "PDD-024",
    "PDD-025",
    "PDD-028",
    "PDD-029",
    "PDD-030",
    "PDD-033",
    "PDD-058",
    "PDD-095",
    "PDD-096",
)

PASS1B_PDD_REQUIRED_SURFACES: dict[str, tuple[str, ...]] = {
    "PDD-022": ("tenant_identity",),
    "PDD-023": ("cas_ownership",),
    "PDD-024": ("artifact_tenant_mapping",),
    "PDD-025": ("cas_manifest_governance",),
    "PDD-028": ("approval_authority",),
    "PDD-029": ("override_signature",),
    "PDD-030": ("decision_lifecycle", "recall_retraction"),
    "PDD-033": ("privacy_security_authority",),
    "PDD-058": ("human_review_authority", "override_signature"),
    "PDD-095": ("privileged_action_authority",),
    "PDD-096": ("signing_public_trust", "public_trust"),
}

PASS1B_REQUIRED_CASE_BINDING_FIELDS: dict[str, tuple[str, ...]] = {
    "tenant_identity": (
        "record_ref",
        "tenant_id",
        "cell_id",
        "runtime_event_ref",
    ),
    "cas_ownership": (
        "record_ref",
        "owner_index_ref",
        "tenant_id",
        "read_scope_enforced",
        "runtime_event_ref",
    ),
    "artifact_tenant_mapping": (
        "record_ref",
        "descendant_map_ref",
        "api_decision_ref",
        "runtime_event_ref",
    ),
    "cas_manifest_governance": (
        "record_ref",
        "producer_metadata_ref",
        "governance_metadata_ref",
        "retention_class",
        "encryption_metadata_ref",
        "runtime_event_ref",
    ),
    "approval_authority": (
        "record_ref",
        "approval_packet_ref",
        "scorecard_digest_ref",
        "projection_policy",
        "runtime_event_ref",
    ),
    "override_signature": (
        "record_ref",
        "override_packet_ref",
        "reviewer_identity_ref",
        "signature_ref",
        "signature_class",
        "non_overridable_blockers_enforced",
        "runtime_event_ref",
    ),
    "decision_lifecycle": (
        "record_ref",
        "decision_packet_ref",
        "published_artifact_ref",
        "validity_lifecycle_ref",
        "continuous_governance_ref",
        "runtime_event_ref",
    ),
    "privacy_security_authority": (
        "record_ref",
        "privacy_compliance_report_ref",
        "security_assurance_report_ref",
        "runtime_enforcement_log_refs",
        "canonical_metadata_ref",
        "runtime_event_ref",
    ),
    "human_review_authority": (
        "record_ref",
        "human_oversight_ref",
        "reviewer_identity_refs",
        "separation_of_duty_ref",
        "rubber_stamp_risk",
        "effective_oversight",
        "runtime_event_ref",
    ),
    "privileged_action_authority": (
        "record_ref",
        "privileged_action_ledger_ref",
        "dual_control_ref",
        "before_after_hash_refs",
        "tamper_evident_attribution_ref",
        "runtime_event_ref",
    ),
    "signing_public_trust": (
        "record_ref",
        "signing_authority_matrix_ref",
        "key_lifecycle_refs",
        "release_attestation_ref",
        "public_packet_signature_ref",
        "trust_status",
        "runtime_event_ref",
    ),
    "recall_retraction": (
        "record_ref",
        "recall_authority_ref",
        "retraction_authority_ref",
        "contestability_hook_ref",
        "runtime_event_ref",
    ),
    "public_trust": (
        "record_ref",
        "public_export_ref",
        "external_audit_archive_ref",
        "standalone_verifier_ref",
        "public_contestability_ref",
        "runtime_event_ref",
    ),
}

_OVERRIDE_SIGNATURE_AUTHORITY_CLASSES = frozenset(
    {"external_signature", "internal_reviewer_attestation"}
)
_VALID_PUBLIC_TRUST_STATUSES = frozenset({"valid", "verified", "trusted"})
_PASSING_STATUS_VALUES = frozenset(
    {"pass", "passed", "ok", "accepted", "approved", "verified", "implemented"}
)
_BLOCKING_STATUS_VALUES = frozenset({"blocked", "fail", "failed", "missing", "revoked"})
_LOCAL_REF_PREFIXES = ("/", "./", "../", "~", "file://", "repo://", "tests/", "tmp/")


@dataclass(frozen=True)
class PolicyDesignPass1BHardeningIssue:
    """One scorecard-readable Phase 28.1 hardening issue."""

    code: str
    message: str
    field: str
    evidence_ref: str | None = None
    pdd_id: str | None = None
    surface: str | None = None
    next_action: str = PASS1B_HARDENING_NEXT_ACTION

    def as_gate_fields(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "evidence_ref": self.evidence_ref,
            "pdd_id": self.pdd_id,
            "surface": self.surface,
            "next_action": self.next_action,
        }


class PolicyDesignPass1BHardeningError(ValueError):
    """Fail-closed Phase 28.1 hardening contract violation."""

    def __init__(self, issue: PolicyDesignPass1BHardeningIssue) -> None:
        self.issue = issue
        super().__init__(f"{issue.code}: {issue.message}")


def build_pass1b_tenant_cas_approval_governance_record(
    *,
    record_id: str,
    case_id: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    cell_id: str | None,
    case_bindings: Mapping[str, Mapping[str, Any]],
    pdd_bindings: Iterable[Mapping[str, Any]],
    evidence_ref: str,
    runtime_event_ref: str,
) -> dict[str, Any]:
    """Build the Phase 28.1 case-bound Pass 1B hardening record."""

    payload = {
        "schema_version": PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_SCHEMA_VERSION,
        "contract_id": PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_CONTRACT_ID,
        "record_id": record_id,
        "case_id": case_id,
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "cell_id": cell_id,
        "status": "pass",
        "record_family": "pass1b_tenant_cas_approval_governance.v1",
        "hardening_group": "tenant_cas_approval_governance",
        "pdd_bindings": [dict(row) for row in pdd_bindings],
        "case_bindings": {
            str(surface): dict(binding)
            for surface, binding in case_bindings.items()
        },
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }
    return validate_pass1b_tenant_cas_approval_governance_record(payload)


def validate_pass1b_tenant_cas_approval_governance_record(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and normalize a Phase 28.1 Pass 1B hardening record."""

    issues = pass1b_tenant_cas_approval_governance_issues(record)
    if issues:
        raise PolicyDesignPass1BHardeningError(issues[0])
    normalized = dict(record)
    normalized["schema_version"] = PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_SCHEMA_VERSION
    normalized["contract_id"] = (
        _text(record.get("contract_id"))
        or PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_CONTRACT_ID
    )
    normalized["status"] = _text(record.get("status")) or "pass"
    normalized["record_family"] = (
        _text(record.get("record_family"))
        or "pass1b_tenant_cas_approval_governance.v1"
    )
    normalized["hardening_group"] = (
        _text(record.get("hardening_group")) or "tenant_cas_approval_governance"
    )
    normalized["pdd_bindings"] = [
        dict(row) for row in _mapping_rows(record.get("pdd_bindings"))
    ]
    normalized["case_bindings"] = {
        str(surface): dict(binding)
        for surface, binding in _mapping(record.get("case_bindings")).items()
        if isinstance(binding, Mapping)
    }
    return normalized


def pass1b_tenant_cas_approval_governance_issues(
    record: object,
) -> tuple[PolicyDesignPass1BHardeningIssue, ...]:
    """Return deterministic Phase 28.1 hardening issues without raising."""

    if not isinstance(record, Mapping):
        return (
            PolicyDesignPass1BHardeningIssue(
                code="policy_design_pass1b_hardening_record_missing",
                message=(
                    "Production Policy Design Case requires the Phase 28.1 "
                    "tenant/CAS/approval/governance hardening record."
                ),
                field=PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_RECORD_KEY,
            ),
        )
    issues: list[PolicyDesignPass1BHardeningIssue] = []
    if record.get("schema_version") != PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_SCHEMA_VERSION:
        issues.append(
            _issue(
                "policy_design_pass1b_hardening_schema_version_invalid",
                "Phase 28.1 hardening record must use the current schema.",
                "schema_version",
                record=record,
            )
        )
    for field in (
        "record_id",
        "case_id",
        "run_id",
        "job_id",
        "tenant_id",
        "evidence_ref",
        "runtime_event_ref",
    ):
        if not _text(record.get(field)):
            issues.append(
                _issue(
                    "policy_design_pass1b_hardening_required_field_missing",
                    f"Phase 28.1 hardening record is missing {field}.",
                    field,
                    record=record,
                )
            )
    if not _runtime_event_ref(record.get("runtime_event_ref")):
        issues.append(
            _issue(
                "policy_design_pass1b_hardening_runtime_event_missing",
                "Phase 28.1 hardening record must be linked to a runtime event.",
                "runtime_event_ref",
                record=record,
            )
        )
    status = (_text(record.get("status")) or "").casefold().replace("-", "_")
    if status not in _PASSING_STATUS_VALUES:
        issues.append(
            _issue(
                "policy_design_pass1b_hardening_status_not_pass",
                "Phase 28.1 hardening record must be passing for serious closeout.",
                "status",
                record=record,
            )
        )
    case_bindings = _mapping(record.get("case_bindings"))
    pdd_bindings = _mapping_rows(record.get("pdd_bindings"))
    issues.extend(_case_binding_issues(case_bindings, record=record))
    issues.extend(_pdd_binding_issues(pdd_bindings, case_bindings, record=record))
    return tuple(issues)


def policy_design_pass1b_hardening_scorecard_gates(
    case: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return scorecard gates for the Phase 28.1 case-bound hardening record."""

    record = case.get(PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_RECORD_KEY)
    gates = policy_design_case_record_family_coverage_scorecard_gates(
        case,
        phase="policy_design_pass1b_hardening",
        gate_name="policy_design_case.pass1b_record_family_coverage",
    )
    for issue in pass1b_tenant_cas_approval_governance_issues(record):
        gate_fields = issue.as_gate_fields()
        gates.append(
            {
                "name": "policy_design_pass1b_hardening",
                "stage": "ops",
                "code": str(gate_fields["code"]),
                "status": "fail",
                "layer": "assurance_case",
                "phase": "policy_design_pass1b_hardening",
                "message": str(gate_fields["message"]),
                "evidence_ref": (
                    str(gate_fields["evidence_ref"])
                    if gate_fields["evidence_ref"] is not None
                    else "quality_evidence/policy_design_case.json"
                ),
                "next_action": str(gate_fields["next_action"]),
                "missing_input": str(gate_fields["field"]),
                "pdd_id": gate_fields["pdd_id"],
                "surface": gate_fields["surface"],
                "blocking": True,
            }
        )
    return gates


def _case_binding_issues(
    case_bindings: Mapping[str, Any],
    *,
    record: Mapping[str, Any],
) -> list[PolicyDesignPass1BHardeningIssue]:
    issues: list[PolicyDesignPass1BHardeningIssue] = []
    for surface, required_fields in PASS1B_REQUIRED_CASE_BINDING_FIELDS.items():
        binding = case_bindings.get(surface)
        if not isinstance(binding, Mapping):
            issues.append(
                _issue(
                    f"policy_design_pass1b_{surface}_missing",
                    f"Phase 28.1 hardening record is missing {surface}.",
                    f"case_bindings.{surface}",
                    record=record,
                    surface=surface,
                )
            )
            continue
        for field in required_fields:
            if not _binding_field_present(binding.get(field)):
                issues.append(
                    _issue(
                        _missing_field_code(surface, field),
                        f"Phase 28.1 {surface} binding is missing {field}.",
                        f"case_bindings.{surface}.{field}",
                        record=record,
                        surface=surface,
                    )
                )
        issues.extend(_surface_semantic_issues(surface, binding, record=record))
    return issues


def _pdd_binding_issues(
    pdd_bindings: tuple[Mapping[str, Any], ...],
    case_bindings: Mapping[str, Any],
    *,
    record: Mapping[str, Any],
) -> list[PolicyDesignPass1BHardeningIssue]:
    issues: list[PolicyDesignPass1BHardeningIssue] = []
    by_pdd: dict[str, list[Mapping[str, Any]]] = {}
    for row in pdd_bindings:
        pdd_id = _text(row.get("pdd_id"))
        if pdd_id:
            by_pdd.setdefault(pdd_id, []).append(row)
    for pdd_id, required_surfaces in PASS1B_PDD_REQUIRED_SURFACES.items():
        rows = by_pdd.get(pdd_id, [])
        if not rows:
            issues.append(
                _issue(
                    "policy_design_pass1b_pdd_binding_missing",
                    f"Phase 28.1 hardening record is missing {pdd_id}.",
                    "pdd_bindings",
                    record=record,
                    pdd_id=pdd_id,
                )
            )
            continue
        row_surfaces = {surface for row in rows for surface in _row_surfaces(row)}
        missing_surfaces = [
            surface
            for surface in required_surfaces
            if surface not in case_bindings or surface not in row_surfaces
        ]
        if missing_surfaces:
            issues.append(
                _issue(
                    "policy_design_pass1b_pdd_binding_incomplete",
                    (
                        f"Phase 28.1 {pdd_id} is not bound to required case "
                        f"surfaces: {', '.join(missing_surfaces)}."
                    ),
                    "pdd_bindings",
                    record=record,
                    pdd_id=pdd_id,
                    surface=",".join(missing_surfaces),
                )
            )
        for row in rows:
            issues.extend(_pdd_row_issues(row, record=record, pdd_id=pdd_id))
    extra_pdds = sorted(set(by_pdd) - set(PASS1B_PDD_REQUIRED_SURFACES))
    for pdd_id in extra_pdds:
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_binding_unknown",
                f"Phase 28.1 hardening record references an unknown PDD: {pdd_id}.",
                "pdd_bindings",
                record=record,
                pdd_id=pdd_id,
            )
        )
    return issues


def _pdd_row_issues(
    row: Mapping[str, Any],
    *,
    record: Mapping[str, Any],
    pdd_id: str,
) -> list[PolicyDesignPass1BHardeningIssue]:
    issues: list[PolicyDesignPass1BHardeningIssue] = []
    for field in ("surface", "record_ref", "evidence_ref", "runtime_event_ref", "owner", "status"):
        if not _text(row.get(field)):
            issues.append(
                _issue(
                    "policy_design_pass1b_pdd_binding_field_missing",
                    f"Phase 28.1 {pdd_id} binding is missing {field}.",
                    f"pdd_bindings.{pdd_id}.{field}",
                    record=record,
                    pdd_id=pdd_id,
                )
            )
    if _text(row.get("runtime_event_ref")) and not _runtime_event_ref(row.get("runtime_event_ref")):
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_binding_runtime_event_invalid",
                f"Phase 28.1 {pdd_id} binding runtime event is not authority evidence.",
                f"pdd_bindings.{pdd_id}.runtime_event_ref",
                record=record,
                pdd_id=pdd_id,
            )
        )
    owner = _text(row.get("owner"))
    if owner and not owner.startswith("team-"):
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_binding_owner_invalid",
                f"Phase 28.1 {pdd_id} binding must name a team owner.",
                f"pdd_bindings.{pdd_id}.owner",
                record=record,
                pdd_id=pdd_id,
            )
        )
    status = (_text(row.get("status")) or "").casefold().replace("-", "_")
    if status not in _PASSING_STATUS_VALUES:
        issues.append(
            _issue(
                "policy_design_pass1b_pdd_binding_not_pass",
                f"Phase 28.1 {pdd_id} binding must be passing or represented by a blocker.",
                f"pdd_bindings.{pdd_id}.status",
                record=record,
                pdd_id=pdd_id,
            )
        )
    return issues


def _surface_semantic_issues(
    surface: str,
    binding: Mapping[str, Any],
    *,
    record: Mapping[str, Any],
) -> list[PolicyDesignPass1BHardeningIssue]:
    issues: list[PolicyDesignPass1BHardeningIssue] = []
    status = (_text(binding.get("status")) or "pass").casefold()
    if status in _BLOCKING_STATUS_VALUES:
        issues.append(
            _issue(
                f"policy_design_pass1b_{surface}_blocked",
                f"Phase 28.1 {surface} binding is not passing.",
                f"case_bindings.{surface}.status",
                record=record,
                surface=surface,
            )
        )
    if surface == "cas_ownership" and binding.get("read_scope_enforced") is not True:
        issues.append(
            _issue(
                "policy_design_pass1b_cas_ownership_scope_not_enforced",
                "CAS ownership binding must prove read scope enforcement.",
                "case_bindings.cas_ownership.read_scope_enforced",
                record=record,
                surface=surface,
            )
        )
    if surface == "override_signature":
        signature_class = (_text(binding.get("signature_class")) or "").casefold()
        if signature_class not in _OVERRIDE_SIGNATURE_AUTHORITY_CLASSES:
            issues.append(
                _issue(
                    "policy_design_pass1b_override_signature_not_external_or_attested",
                    (
                        "Production overrides must be external signatures or "
                        "internal reviewer attestations, not digest-only proofs."
                    ),
                    "case_bindings.override_signature.signature_class",
                    record=record,
                    surface=surface,
                )
            )
        if binding.get("non_overridable_blockers_enforced") is not True:
            issues.append(
                _issue(
                    "policy_design_pass1b_override_non_overridable_blockers_missing",
                    "Override binding must prove non-overridable blockers remain blocked.",
                    "case_bindings.override_signature.non_overridable_blockers_enforced",
                    record=record,
                    surface=surface,
                )
            )
    if surface == "human_review_authority":
        if binding.get("effective_oversight") is not True:
            issues.append(
                _issue(
                    "policy_design_pass1b_human_review_ineffective",
                    "Human review binding must prove effective oversight.",
                    "case_bindings.human_review_authority.effective_oversight",
                    record=record,
                    surface=surface,
                )
            )
        if (_text(binding.get("rubber_stamp_risk")) or "").casefold() == "high":
            issues.append(
                _issue(
                    "policy_design_pass1b_human_review_rubber_stamp_risk",
                    "Human review binding cannot carry high rubber-stamp risk.",
                    "case_bindings.human_review_authority.rubber_stamp_risk",
                    record=record,
                    surface=surface,
                )
            )
    if surface == "signing_public_trust":
        trust_status = (_text(binding.get("trust_status")) or "").casefold()
        if trust_status not in _VALID_PUBLIC_TRUST_STATUSES:
            issues.append(
                _issue(
                    "policy_design_pass1b_public_trust_signature_invalid",
                    (
                        "Public trust binding must prove a valid signing and key "
                        "lifecycle chain."
                    ),
                    "case_bindings.signing_public_trust.trust_status",
                    record=record,
                    surface=surface,
                )
            )
    if surface == "recall_retraction" and not _binding_field_present(
        binding.get("contestability_hook_ref")
    ):
        issues.append(
            _issue(
                "policy_design_pass1b_recall_retraction_authority_missing",
                "Recall/retraction binding must include contestability hooks.",
                "case_bindings.recall_retraction.contestability_hook_ref",
                record=record,
                surface=surface,
            )
        )
    if surface == "public_trust" and not _binding_field_present(
        binding.get("public_contestability_ref")
    ):
        issues.append(
            _issue(
                "policy_design_pass1b_public_trust_contestability_missing",
                "Public trust binding must include public contestability evidence.",
                "case_bindings.public_trust.public_contestability_ref",
                record=record,
                surface=surface,
            )
        )
    return issues


def _missing_field_code(surface: str, field: str) -> str:
    if surface == "recall_retraction" and field in {
        "recall_authority_ref",
        "retraction_authority_ref",
        "contestability_hook_ref",
    }:
        return "policy_design_pass1b_recall_retraction_authority_missing"
    if surface == "public_trust" and field == "public_contestability_ref":
        return "policy_design_pass1b_public_trust_contestability_missing"
    if surface == "signing_public_trust" and field in {
        "key_lifecycle_refs",
        "public_packet_signature_ref",
        "trust_status",
    }:
        return "policy_design_pass1b_public_trust_signature_invalid"
    return f"policy_design_pass1b_{surface}_{field}_missing"


def _row_surfaces(row: Mapping[str, Any]) -> tuple[str, ...]:
    surface = _text(row.get("surface"))
    surfaces = list(_text_values(row.get("surfaces")))
    if surface:
        surfaces.append(surface)
    return tuple(dict.fromkeys(surfaces))


def _issue(
    code: str,
    message: str,
    field: str,
    *,
    record: Mapping[str, Any],
    pdd_id: str | None = None,
    surface: str | None = None,
) -> PolicyDesignPass1BHardeningIssue:
    return PolicyDesignPass1BHardeningIssue(
        code=code,
        message=message,
        field=field,
        evidence_ref=_text(record.get("evidence_ref")),
        pdd_id=pdd_id,
        surface=surface,
    )


def _binding_field_present(value: object) -> bool:
    if isinstance(value, bool):
        return value is True
    if isinstance(value, (list, tuple, set)):
        return any(_binding_field_present(item) for item in value)
    text = _text(value)
    if text is None:
        return False
    return not _local_ref(text)


def _runtime_event_ref(value: object) -> bool:
    text = _text(value)
    if text is None or _local_ref(text):
        return False
    return text.startswith(("event://", "sha256:", "cas://sha256/"))


def _local_ref(value: str) -> bool:
    return value.startswith(_LOCAL_REF_PREFIXES)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if isinstance(value, list):
        return tuple(item for item in value if isinstance(item, Mapping))
    return ()


def _text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = _text(value)
        return (text,) if text else ()
    if isinstance(value, Mapping):
        values: list[str] = []
        for item in value.values():
            values.extend(_text_values(item))
        return tuple(values)
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        values: list[str] = []
        for item in value:
            values.extend(_text_values(item))
        return tuple(values)
    return ()


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


__all__ = [
    "PASS1B_HARDENING_READINESS_CHECK",
    "PASS1B_HARDENING_SCORECARD_GATE",
    "PASS1B_PDD_REQUIRED_SURFACES",
    "PASS1B_REQUIRED_CASE_BINDING_FIELDS",
    "PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_CONTRACT_ID",
    "PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_PDDS",
    "PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_RECORD_KEY",
    "PASS1B_TENANT_CAS_APPROVAL_GOVERNANCE_SCHEMA_VERSION",
    "PolicyDesignPass1BHardeningError",
    "PolicyDesignPass1BHardeningIssue",
    "build_pass1b_tenant_cas_approval_governance_record",
    "pass1b_tenant_cas_approval_governance_issues",
    "policy_design_pass1b_hardening_scorecard_gates",
    "validate_pass1b_tenant_cas_approval_governance_record",
]

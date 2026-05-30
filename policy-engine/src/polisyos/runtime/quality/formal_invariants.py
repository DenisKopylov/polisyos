"""Formal invariant registry and lightweight model checks for Policy Design Case.

ADR-0165 makes closeout-critical invariant specs machine-readable. This module
keeps the first pass intentionally small: a TOML registry plus finite-state
checks for the authority paths that can otherwise produce false closeout.
"""

from __future__ import annotations

import json
import tomllib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

from polisyos.runtime.quality.authority import (
    AuthorityRole,
    EvidenceClass,
    ProvenanceKind,
)
from polisyos.runtime.quality.phase_barriers import PhaseBarrierStatus
from polisyos.runtime.quality.run_state import VALID_TRANSITIONS, RunState

REPO_ROOT = Path(__file__).resolve().parents[4]
FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH = Path(
    "architecture/policy_design_case/formal_invariant_specs.toml"
)
FORMAL_INVARIANT_REGISTRY_PATH = REPO_ROOT / FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH

SCHEMA_VERSION = "policyos.policy_design_case.formal_invariant_specs.v1"
TOOL_NAME = "runtime.quality.policy-design-formal-invariants"

REQUIRED_CLOSEOUT_INVARIANT_IDS = frozenset(
    {
        "authority_ordering",
        "phase_barriers",
        "same_input_closure",
        "cas_event_reconciliation",
        "terminal_readiness",
    }
)
REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS = frozenset(
    {
        "bounded_liveness_producer_pipeline",
        "bounded_liveness_retry_lease",
        "bounded_liveness_escalation_authority",
        "bounded_liveness_reissue_flow",
    }
)

REQUIRED_FIELDS = frozenset(
    {
        "spec_id",
        "family",
        "owner",
        "source_adrs",
        "statement",
        "protected_authority_property",
        "implementation_scopes",
        "accepted_check_type",
        "model_property",
        "minimum_evidence_artifacts",
        "revisit_triggers",
        "retirement_rule",
        "criticality",
        "status",
        "negative_tests",
    }
)
REQUIRED_STRING_FIELDS = frozenset(
    {
        "spec_id",
        "family",
        "owner",
        "statement",
        "protected_authority_property",
        "accepted_check_type",
        "model_property",
        "retirement_rule",
        "criticality",
        "status",
    }
)
REQUIRED_LIST_FIELDS = frozenset(
    {
        "source_adrs",
        "implementation_scopes",
        "minimum_evidence_artifacts",
        "revisit_triggers",
        "negative_tests",
    }
)
AUTHORITY_CRITICALITIES = frozenset({"substrate_critical", "policy_case_critical"})
ACCEPTED_CHECK_TYPES = frozenset(
    {
        "finite_state_model_check",
        "property_based_model_check",
        "runtime_trace_conformance",
        "state_machine_model_check",
        "static_contract_check",
    }
)
ACTIVE_STATUSES = frozenset({"active", "blocked"})
UNIT_TEST_ONLY_CHECKS = frozenset({"unit_test_only", "unit_test"})

_AUTHORITY_ROLES = tuple(AuthorityRole.__args__)  # type: ignore[attr-defined]
_EVIDENCE_CLASSES = tuple(EvidenceClass.__args__)  # type: ignore[attr-defined]
_PROVENANCE_KINDS = tuple(ProvenanceKind.__args__)  # type: ignore[attr-defined]
_PROJECTION_ROLES = frozenset(
    {
        "approval_input",
        "diagnostic_only",
        "not_authoritative",
        "packaging_only",
        "projection_only",
        "readiness_input",
        "scorecard_input",
    }
)
_AUTHORITY_ROLES_ALLOWED = frozenset({"producer_authority", "runtime_blocker"})
_SERIOUS_AUTHORITY_PROVENANCE = frozenset({"runtime_emitted", "runtime_blocker"})
_PROJECTION_PROVENANCE = frozenset(
    {"bundle_overlay", "bundle_packaged", "runtime_projection"}
)
_C40_PRODUCER_STATES = (
    "requested",
    "preflighted",
    "waiting_on_spine",
    "waiting_on_peer",
    "emitted_context_only",
    "emitted_binding",
    "blocked",
    "timed_out",
    "degraded",
    "rerun_required",
    "abandoned",
)
_LIVENESS_ONGOING_STATES = frozenset(
    {"pending", "requested", "running", "retrying", "leased", "acquired", "preflighted"}
)
_LIVENESS_WAIT_STATES = frozenset({"waiting_on_spine", "waiting_on_peer"})
_LIVENESS_SATISFIED_STATES = frozenset({"satisfied", "emitted_context_only", "emitted_binding"})
_LIVENESS_ESCALATION_STATES = frozenset(
    {
        "escalated",
        "failed",
        "cancelled",
        "blocked",
        "timed_out",
        "degraded",
        "rerun_required",
        "abandoned",
    }
)
_REISSUE_TERMINAL_STATUSES = frozenset(
    {
        "completed",
        "resolved",
        "reissued",
        "superseded",
        "withdrawn",
        "confirmed",
        "refuted",
        "inconclusive",
        "closed",
        "none",
    }
)


@dataclass(frozen=True)
class FormalInvariantIssue:
    """One formal invariant registry or model-check finding."""

    code: str
    spec_id: str
    field: str
    message: str
    value: object | None = None
    severity: str = "error"

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "severity": self.severity,
            "spec_id": self.spec_id,
            "field": self.field,
            "message": self.message,
        }
        if self.value is not None:
            payload["value"] = self.value
        return payload


@dataclass(frozen=True)
class FormalInvariantValidationResult:
    """Validation result shared by runtime and repo-quality checks."""

    status: str
    specs: tuple[dict[str, Any], ...]
    issues: tuple[FormalInvariantIssue, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": {
                "spec_count": len(self.specs),
                "issue_count": len(self.issues),
            },
            "issues": [issue.as_dict() for issue in self.issues],
        }


class FormalInvariantRegistryError(ValueError):
    """Raised when strict formal invariant registry loading finds errors."""

    def __init__(self, result: FormalInvariantValidationResult) -> None:
        self.result = result
        codes = sorted({issue.code for issue in result.issues})
        super().__init__("Formal invariant registry is invalid: " + ", ".join(codes))


def load_formal_invariant_specs(
    *,
    repo_root: Path | str = REPO_ROOT,
    registry_path: Path | str = FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH,
    strict: bool = True,
) -> tuple[dict[str, Any], ...]:
    """Load formal invariant specs from TOML, optionally failing on validation."""

    repo_root_path = Path(repo_root).resolve()
    registry_file = _resolve(repo_root_path, Path(registry_path))
    payload = _load_toml(registry_file)
    result = validate_formal_invariant_specs_payload(payload, repo_root=repo_root_path)
    if strict and result.issues:
        raise FormalInvariantRegistryError(result)
    invalid_ids = {issue.spec_id for issue in result.issues}
    return tuple(row for row in result.specs if row.get("spec_id") not in invalid_ids)


def validate_formal_invariant_specs_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | str = REPO_ROOT,
) -> FormalInvariantValidationResult:
    """Validate a parsed formal invariant registry payload."""

    repo_root_path = Path(repo_root).resolve()
    issues: list[FormalInvariantIssue] = []
    raw_specs = payload.get("specs")
    specs: list[dict[str, Any]] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            FormalInvariantIssue(
                code="formal_invariant_schema_version_invalid",
                spec_id="registry",
                field="schema_version",
                message=f"Formal invariant registry must use {SCHEMA_VERSION}.",
                value=payload.get("schema_version"),
            )
        )

    if not isinstance(raw_specs, list) or not raw_specs:
        issues.append(
            FormalInvariantIssue(
                code="formal_invariant_registry_missing_rows",
                spec_id="registry",
                field="specs",
                message="Formal invariant registry must define at least one [[specs]] row.",
            )
        )
        return FormalInvariantValidationResult("fail", specs=(), issues=tuple(issues))

    seen: set[str] = set()
    for index, raw_row in enumerate(raw_specs, start=1):
        if not isinstance(raw_row, Mapping):
            issues.append(
                FormalInvariantIssue(
                    code="formal_invariant_row_invalid",
                    spec_id=f"specs[{index}]",
                    field="specs",
                    message="Every formal invariant row must be a TOML table.",
                )
            )
            continue
        row = dict(raw_row)
        specs.append(row)
        spec_id = _row_label(row, index)
        if spec_id in seen:
            issues.append(
                FormalInvariantIssue(
                    code="formal_invariant_spec_id_duplicate",
                    spec_id=spec_id,
                    field="spec_id",
                    message="Formal invariant spec ids must be unique.",
                    value=spec_id,
                )
            )
        seen.add(spec_id)
        issues.extend(_field_shape_issues(row, index=index, repo_root=repo_root_path))

    for required_id in sorted(REQUIRED_CLOSEOUT_INVARIANT_IDS - seen):
        issues.append(
            FormalInvariantIssue(
                code="formal_invariant_required_spec_missing",
                spec_id=required_id,
                field="spec_id",
                message="Phase 29.4 closeout invariant is missing from the registry.",
                value=required_id,
            )
        )
    for required_id in sorted(REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS - seen):
        issues.append(
            FormalInvariantIssue(
                code="formal_invariant_required_temporal_liveness_spec_missing",
                spec_id=required_id,
                field="spec_id",
                message="W10.A temporal/liveness invariant is missing from the registry.",
                value=required_id,
            )
        )

    return FormalInvariantValidationResult(
        "fail" if issues else "pass",
        specs=tuple(specs),
        issues=tuple(issues),
    )


def build_formal_invariant_spec_report(
    *,
    repo_root: Path | str = REPO_ROOT,
    registry_path: Path | str = FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH,
) -> dict[str, Any]:
    """Build a machine-readable formal invariant coverage and model-check report."""

    repo_root_path = Path(repo_root).resolve()
    registry_file = _resolve(repo_root_path, Path(registry_path))
    payload = _load_toml(registry_file)
    validation = validate_formal_invariant_specs_payload(
        payload,
        repo_root=repo_root_path,
    )
    model_checks = model_check_formal_invariant_specs(validation.specs)
    covered = {
        str(row.get("spec_id"))
        for row in validation.specs
        if str(row.get("spec_id")) in REQUIRED_CLOSEOUT_INVARIANT_IDS
    }
    temporal_covered = {
        str(row.get("spec_id"))
        for row in validation.specs
        if str(row.get("spec_id")) in REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS
    }
    required_count = len(REQUIRED_CLOSEOUT_INVARIANT_IDS)
    covered_count = len(covered)
    temporal_required_count = len(REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS)
    temporal_covered_count = len(temporal_covered)
    status = (
        "pass"
        if validation.status == "pass" and model_checks["status"] == "pass"
        else "fail"
    )
    issues = [issue.as_dict() for issue in validation.issues]
    for check in model_checks["checks"]:
        if check["status"] == "pass":
            continue
        issues.append(
            {
                "code": "formal_invariant_model_check_failed",
                "severity": "error",
                "spec_id": check["spec_id"],
                "field": "model_property",
                "message": "Formal invariant model check produced counterexamples.",
                "value": check["counterexamples"],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": status,
        "repo_root": str(repo_root_path),
        "source": {"registry_path": _rel(registry_file, repo_root_path)},
        "summary": {
            "spec_count": len(validation.specs),
            "required_spec_count": required_count,
            "covered_required_spec_count": covered_count,
            "required_coverage_pct": _pct(covered_count, required_count),
            "temporal_liveness_required_spec_count": temporal_required_count,
            "temporal_liveness_covered_required_spec_count": temporal_covered_count,
            "temporal_liveness_coverage_pct": _pct(
                temporal_covered_count,
                temporal_required_count,
            ),
            "issue_count": len(issues),
        },
        "required_closeout_invariants": sorted(REQUIRED_CLOSEOUT_INVARIANT_IDS),
        "required_temporal_liveness_invariants": sorted(
            REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS
        ),
        "model_checks": model_checks,
        "specs": list(validation.specs),
        "issues": issues,
    }


def model_check_formal_invariant_specs(
    specs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Run finite-state model checks for every spec row with a model property."""

    checks: list[dict[str, Any]] = []
    for row in specs:
        spec_id = str(row.get("spec_id") or "unknown").strip() or "unknown"
        model_property = str(row.get("model_property") or "").strip()
        if not model_property:
            checks.append(
                {
                    "spec_id": spec_id,
                    "model_property": model_property,
                    "status": "fail",
                    "checked_states": 0,
                    "counterexamples": [
                        {"code": "formal_invariant_model_property_missing"}
                    ],
                }
            )
            continue
        checker = _MODEL_CHECKERS.get(model_property)
        if checker is None:
            checks.append(
                {
                    "spec_id": spec_id,
                    "model_property": model_property,
                    "status": "fail",
                    "checked_states": 0,
                    "counterexamples": [
                        {"code": "formal_invariant_model_property_unknown"}
                    ],
                }
            )
            continue
        checked_states, counterexamples = checker()
        checks.append(
            {
                "spec_id": spec_id,
                "model_property": model_property,
                "status": "pass" if not counterexamples else "fail",
                "checked_states": checked_states,
                "counterexamples": counterexamples,
            }
        )
    return {
        "status": "pass" if all(check["status"] == "pass" for check in checks) else "fail",
        "checks": checks,
    }


def dump_formal_invariant_report_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def check_bounded_liveness_deadline_consistency(
    trace: Mapping[str, Any],
) -> dict[str, Any]:
    """Check W10.A bounded-liveness deadline consistency over runtime traces.

    Args:
        trace: Runtime quality trace containing producer pipeline, retry/lease,
            escalation, or reissue records.

    Returns:
        JSON-serializable invariant report. Escalations are runtime governance
        evidence only; they are never treated as domain authority.
    """

    issues: list[dict[str, Any]] = []
    checked = {
        "producer_pipeline": 0,
        "retry_lease": 0,
        "escalation": 0,
        "reissue": 0,
    }
    for index, record in enumerate(_producer_liveness_records(trace)):
        checked["producer_pipeline"] += 1
        issues.extend(_producer_liveness_issues(record, index=index))
    for index, record in enumerate(_retry_lease_records(trace)):
        checked["retry_lease"] += 1
        issues.extend(_retry_lease_liveness_issues(record, index=index))
    for index, record in enumerate(_escalation_records(trace)):
        checked["escalation"] += 1
        issues.extend(_escalation_liveness_issues(record, index=index))
    for index, record in enumerate(_reissue_records(trace)):
        checked["reissue"] += 1
        issues.extend(_reissue_liveness_issues(record, index=index))

    return {
        "schema_version": (
            "policyos.runtime.quality.bounded_liveness_deadline_consistency.v1"
        ),
        "tool": TOOL_NAME,
        "status": "fail" if issues else "pass",
        "summary": {
            "checked_record_count": sum(checked.values()),
            "producer_pipeline_record_count": checked["producer_pipeline"],
            "retry_lease_record_count": checked["retry_lease"],
            "escalation_record_count": checked["escalation"],
            "reissue_record_count": checked["reissue"],
            "issue_count": len(issues),
        },
        "issues": issues,
    }


def render_formal_invariant_report_text(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"{TOOL_NAME}: {payload['status']}",
        (
            "specs={spec_count} required={covered_required_spec_count}/"
            "{required_spec_count} coverage={required_coverage_pct}% issues={issue_count}"
        ).format(**summary),
    ]
    for check in payload.get("model_checks", {}).get("checks", []):
        if not isinstance(check, Mapping):
            continue
        lines.append(
            "[{status}] {spec_id}: {model_property} states={checked_states}".format(
                status=check.get("status", "unknown"),
                spec_id=check.get("spec_id", "unknown"),
                model_property=check.get("model_property", ""),
                checked_states=check.get("checked_states", 0),
            )
        )
    for issue in payload.get("issues", []):
        if not isinstance(issue, Mapping):
            continue
        lines.append(
            "[{severity}] {spec_id}.{field}: {code}: {message}".format(
                severity=issue.get("severity", "error"),
                spec_id=issue.get("spec_id", "unknown"),
                field=issue.get("field", "unknown"),
                code=issue.get("code", "unknown"),
                message=issue.get("message", ""),
            )
        )
    return "\n".join(lines) + "\n"


def _field_shape_issues(
    row: Mapping[str, Any],
    *,
    index: int,
    repo_root: Path,
) -> list[FormalInvariantIssue]:
    issues: list[FormalInvariantIssue] = []
    spec_id = _row_label(row, index)
    for field in sorted(REQUIRED_FIELDS - set(row)):
        issues.append(
            FormalInvariantIssue(
                code="formal_invariant_field_missing",
                spec_id=spec_id,
                field=field,
                message=f"Required formal invariant field `{field}` is missing.",
            )
        )
    for field in sorted(REQUIRED_STRING_FIELDS):
        if field not in row:
            continue
        if not _non_empty_string(row.get(field)):
            issues.append(
                FormalInvariantIssue(
                    code="formal_invariant_string_field_invalid",
                    spec_id=spec_id,
                    field=field,
                    message=f"Field `{field}` must be a non-empty string.",
                    value=row.get(field),
                )
            )
    for field in sorted(REQUIRED_LIST_FIELDS):
        if field not in row:
            continue
        value = row.get(field)
        if not isinstance(value, list):
            issues.append(
                FormalInvariantIssue(
                    code="formal_invariant_list_field_invalid",
                    spec_id=spec_id,
                    field=field,
                    message=f"Field `{field}` must be a list of non-empty strings.",
                    value=value,
                )
            )
            continue
        if not value:
            issues.append(
                FormalInvariantIssue(
                    code="formal_invariant_list_field_empty",
                    spec_id=spec_id,
                    field=field,
                    message=f"Field `{field}` must contain at least one value.",
                )
            )
            continue
        if not all(_non_empty_string(item) for item in value):
            issues.append(
                FormalInvariantIssue(
                    code="formal_invariant_list_field_invalid",
                    spec_id=spec_id,
                    field=field,
                    message=f"Field `{field}` must contain only non-empty strings.",
                    value=value,
                )
            )
    issues.extend(_semantic_issues(row, spec_id=spec_id, repo_root=repo_root))
    return issues


def _semantic_issues(
    row: Mapping[str, Any],
    *,
    spec_id: str,
    repo_root: Path,
) -> list[FormalInvariantIssue]:
    issues: list[FormalInvariantIssue] = []
    check_type = _text(row.get("accepted_check_type")).casefold()
    criticality = _text(row.get("criticality")).casefold()
    status = _text(row.get("status")).casefold()
    model_property = _text(row.get("model_property"))

    if check_type and check_type not in ACCEPTED_CHECK_TYPES | UNIT_TEST_ONLY_CHECKS:
        issues.append(
            FormalInvariantIssue(
                code="formal_invariant_check_type_unknown",
                spec_id=spec_id,
                field="accepted_check_type",
                message="Accepted check type is not recognized.",
                value=check_type,
            )
        )
    if criticality in AUTHORITY_CRITICALITIES and check_type in UNIT_TEST_ONLY_CHECKS:
        issues.append(
            FormalInvariantIssue(
                code="formal_invariant_check_type_insufficient",
                spec_id=spec_id,
                field="accepted_check_type",
                message=(
                    "Authority-critical invariants cannot be satisfied by unit tests alone."
                ),
                value=check_type,
            )
        )
    if check_type in {
        "finite_state_model_check",
        "property_based_model_check",
        "state_machine_model_check",
    } and model_property not in _MODEL_CHECKERS:
        issues.append(
            FormalInvariantIssue(
                code="formal_invariant_model_property_unknown",
                spec_id=spec_id,
                field="model_property",
                message="Model-checked specs must reference a known model property.",
                value=model_property,
            )
        )
    if criticality and criticality not in AUTHORITY_CRITICALITIES | {"local"}:
        issues.append(
            FormalInvariantIssue(
                code="formal_invariant_criticality_unknown",
                spec_id=spec_id,
                field="criticality",
                message="Formal invariant criticality is not recognized.",
                value=criticality,
            )
        )
    if status and status not in ACTIVE_STATUSES:
        issues.append(
            FormalInvariantIssue(
                code="formal_invariant_status_unknown",
                spec_id=spec_id,
                field="status",
                message="Formal invariant status is not recognized.",
                value=status,
            )
        )
    for field in ("implementation_scopes", "negative_tests"):
        for value in _string_list(row.get(field)):
            path_text = value.split("::", 1)[0]
            if path_text and not _resolve(repo_root, Path(path_text)).exists():
                issues.append(
                    FormalInvariantIssue(
                        code="formal_invariant_path_missing",
                        spec_id=spec_id,
                        field=field,
                        message="Referenced implementation or test path does not exist.",
                        value=value,
                    )
                )
    return issues


def _check_authority_ordering() -> tuple[int, list[dict[str, object]]]:
    counterexamples: list[dict[str, object]] = []
    checked = 0
    for evidence_class, authority_role, provenance_kind in product(
        _EVIDENCE_CLASSES,
        _AUTHORITY_ROLES,
        _PROVENANCE_KINDS,
    ):
        checked += 1
        satisfies = _can_satisfy_serious_authority(
            evidence_class=evidence_class,
            authority_role=authority_role,
            provenance_kind=provenance_kind,
        )
        if authority_role in _PROJECTION_ROLES and satisfies:
            counterexamples.append(
                {
                    "evidence_class": evidence_class,
                    "authority_role": authority_role,
                    "provenance_kind": provenance_kind,
                    "violation": "projection_role_satisfied_authority",
                }
            )
        if provenance_kind in _PROJECTION_PROVENANCE and satisfies:
            counterexamples.append(
                {
                    "evidence_class": evidence_class,
                    "authority_role": authority_role,
                    "provenance_kind": provenance_kind,
                    "violation": "projection_provenance_satisfied_authority",
                }
            )
        if evidence_class != "authority_bearing" and satisfies:
            counterexamples.append(
                {
                    "evidence_class": evidence_class,
                    "authority_role": authority_role,
                    "provenance_kind": provenance_kind,
                    "violation": "non_authority_evidence_satisfied_authority",
                }
            )
    return checked, counterexamples


def _check_phase_barriers() -> tuple[int, list[dict[str, object]]]:
    counterexamples: list[dict[str, object]] = []
    checked = 0
    status_values = ("missing", *(status.value for status in PhaseBarrierStatus))
    for target, required_count in (
        ("ready_for_scorecard", 6),
        ("final_artifact", 5),
        ("public_artifact", 3),
    ):
        for statuses in product(status_values, repeat=required_count):
            checked += 1
            all_passed = all(status == "pass" for status in statuses)
            allowed = _phase_barrier_upgrade_allowed(statuses)
            if allowed != all_passed:
                counterexamples.append(
                    {
                        "target": target,
                        "statuses": list(statuses),
                        "allowed": allowed,
                        "expected": all_passed,
                    }
                )
    return checked, counterexamples


def _check_same_input_closure() -> tuple[int, list[dict[str, object]]]:
    counterexamples: list[dict[str, object]] = []
    checked = 0
    statuses = ("closed", "not_closed", "mismatched", "blocked")
    for left_status, right_status, same_identity, left_sha, right_sha in product(
        statuses,
        statuses,
        (True, False),
        (True, False),
        (True, False),
    ):
        checked += 1
        allowed = _same_input_closure_allowed(
            left_status=left_status,
            right_status=right_status,
            same_identity=same_identity,
            left_sha=left_sha,
            right_sha=right_sha,
        )
        expected = (
            left_status == "closed"
            and right_status == "closed"
            and same_identity
            and left_sha
            and right_sha
        )
        if allowed != expected:
            counterexamples.append(
                {
                    "left_status": left_status,
                    "right_status": right_status,
                    "same_identity": same_identity,
                    "left_sha": left_sha,
                    "right_sha": right_sha,
                    "allowed": allowed,
                    "expected": expected,
                }
            )
    return checked, counterexamples


def _check_cas_event_reconciliation() -> tuple[int, list[dict[str, object]]]:
    counterexamples: list[dict[str, object]] = []
    checked = 0
    for (
        cas_present,
        event_present,
        payload_ref_matches,
        payload_hash_matches,
        identity_matches,
        event_collision,
    ) in product((True, False), repeat=6):
        checked += 1
        allowed = _cas_event_reconciliation_allowed(
            cas_present=cas_present,
            event_present=event_present,
            payload_ref_matches=payload_ref_matches,
            payload_hash_matches=payload_hash_matches,
            identity_matches=identity_matches,
            event_collision=event_collision,
        )
        expected = (
            cas_present
            and event_present
            and payload_ref_matches
            and payload_hash_matches
            and identity_matches
            and not event_collision
        )
        if allowed != expected:
            counterexamples.append(
                {
                    "cas_present": cas_present,
                    "event_present": event_present,
                    "payload_ref_matches": payload_ref_matches,
                    "payload_hash_matches": payload_hash_matches,
                    "identity_matches": identity_matches,
                    "event_collision": event_collision,
                    "allowed": allowed,
                    "expected": expected,
                }
            )
    return checked, counterexamples


def _check_terminal_readiness() -> tuple[int, list[dict[str, object]]]:
    counterexamples: list[dict[str, object]] = []
    checked = 0
    targets = (RunState.APPROVED, RunState.REJECTED, RunState.PUBLISHED_BLOCKED)
    readiness_decisions = (
        None,
        "accepted",
        "approved",
        "rejected",
        "blocked",
        "publication_blocked",
    )
    publication_policies = (None, "allowed", "blocked", "not_public_exportable")
    for state, target, verified, readiness, policy in product(
        tuple(RunState),
        targets,
        (True, False),
        readiness_decisions,
        publication_policies,
    ):
        checked += 1
        allowed = _terminal_transition_allowed(
            state=state,
            target=target,
            scorecard_identity_verified=verified,
            readiness_decision=readiness,
            publication_policy=policy,
        )
        expected = (
            state is RunState.READINESS_CLOSED
            and target in VALID_TRANSITIONS[RunState.READINESS_CLOSED]
            and verified
            and _terminal_readiness_matches(target, readiness, policy)
        )
        if allowed != expected:
            counterexamples.append(
                {
                    "state": state.value,
                    "target": target.value,
                    "scorecard_identity_verified": verified,
                    "readiness_decision": readiness,
                    "publication_policy": policy,
                    "allowed": allowed,
                    "expected": expected,
                }
            )
    return checked, counterexamples


def _check_bounded_liveness_producer_pipeline() -> tuple[int, list[dict[str, object]]]:
    counterexamples: list[dict[str, object]] = []
    checked = 0
    for state, elapsed_past_deadline, has_escalation, satisfies_authority in product(
        _C40_PRODUCER_STATES,
        (True, False),
        (True, False),
        (True, False),
    ):
        checked += 1
        deadline = 10.0
        elapsed = 11.0 if elapsed_past_deadline else 9.0
        record = _producer_model_check_record(
            state=state,
            elapsed_s=elapsed,
            deadline_s=deadline,
            has_escalation=has_escalation,
            satisfies_authority=satisfies_authority,
        )
        issues = _producer_liveness_issues(record, index=0)
        failed = bool(issues)
        expected_failed = (
            (
                state in _LIVENESS_WAIT_STATES | _LIVENESS_ONGOING_STATES
                and elapsed_past_deadline
                and not has_escalation
            )
            or (state in _LIVENESS_SATISFIED_STATES and elapsed_past_deadline)
            or (state in _LIVENESS_ESCALATION_STATES and satisfies_authority)
        )
        if failed != expected_failed:
            counterexamples.append(
                {
                    "state": state,
                    "elapsed_past_deadline": elapsed_past_deadline,
                    "has_escalation": has_escalation,
                    "satisfies_authority": satisfies_authority,
                    "issue_codes": [issue["code"] for issue in issues],
                    "expected_failed": expected_failed,
                }
            )
    return checked, counterexamples


def _check_bounded_liveness_retry_lease() -> tuple[int, list[dict[str, object]]]:
    counterexamples: list[dict[str, object]] = []
    checked = 0
    for state, attempts_above_ceiling, lease_expired, has_escalation in product(
        ("running", "retrying", "satisfied", "escalated"),
        (True, False),
        (True, False),
        (True, False),
    ):
        checked += 1
        retry_ceiling = 2
        attempts = 3 if attempts_above_ceiling else 2
        observed_at = 11.0 if lease_expired else 9.0
        record: dict[str, object] = {
            "producer_key": "scientist.node.fixture",
            "state": state,
            "attempts": attempts,
            "retry_ceiling": retry_ceiling,
            "lease_expires_at_s": 10.0,
            "observed_at_s": observed_at,
            "deadline_s": 10.0,
            "elapsed_s": observed_at,
        }
        if has_escalation or state == "escalated":
            record["escalation_ref"] = "event://runtime-escalation/retry-fixture"
        issues = _retry_lease_liveness_issues(record, index=0)
        failed = bool(issues)
        expected_failed = attempts_above_ceiling or (
            state in _LIVENESS_ONGOING_STATES
            and lease_expired
            and not has_escalation
        )
        if failed != expected_failed:
            counterexamples.append(
                {
                    "state": state,
                    "attempts_above_ceiling": attempts_above_ceiling,
                    "lease_expired": lease_expired,
                    "has_escalation": has_escalation,
                    "issue_codes": [issue["code"] for issue in issues],
                    "expected_failed": expected_failed,
                }
            )
    return checked, counterexamples


def _check_bounded_liveness_escalation_authority() -> tuple[int, list[dict[str, object]]]:
    counterexamples: list[dict[str, object]] = []
    checked = 0
    for state, satisfies_authority, escalation_required, has_escalation in product(
        ("running", "escalated", "timed_out", "blocked"),
        (True, False),
        (True, False),
        (True, False),
    ):
        checked += 1
        record: dict[str, object] = {
            "producer_key": "fabric",
            "state": state,
            "satisfies_authority": satisfies_authority,
            "escalation_required": escalation_required,
        }
        if has_escalation or state in _LIVENESS_ESCALATION_STATES:
            record["escalation_ref"] = "event://runtime-escalation/fabric"
        issues = _escalation_liveness_issues(record, index=0)
        failed = bool(issues)
        expected_failed = (
            (state in _LIVENESS_ESCALATION_STATES and satisfies_authority)
            or (escalation_required and not _has_escalation_signal(record))
        )
        if failed != expected_failed:
            counterexamples.append(
                {
                    "state": state,
                    "satisfies_authority": satisfies_authority,
                    "escalation_required": escalation_required,
                    "has_escalation": has_escalation,
                    "issue_codes": [issue["code"] for issue in issues],
                    "expected_failed": expected_failed,
                }
            )
    return checked, counterexamples


def _check_bounded_liveness_reissue_flow() -> tuple[int, list[dict[str, object]]]:
    counterexamples: list[dict[str, object]] = []
    checked = 0
    for status, elapsed_past_deadline, has_resolution, has_escalation in product(
        ("partial_reissue", "review_required", "resolved"),
        (True, False),
        (True, False),
        (True, False),
    ):
        checked += 1
        record: dict[str, object] = {
            "case_id": "case-1",
            "claim_id": "claim-1",
            "status": status,
            "elapsed_s": 121.0 if elapsed_past_deadline else 119.0,
            "deadline_s": 120.0,
        }
        if has_resolution:
            record["resolution_ref"] = "cas://sha256/" + "a" * 64
        if has_escalation:
            record["escalation_ref"] = "event://runtime-escalation/reissue"
        issues = _reissue_liveness_issues(record, index=0)
        failed = bool(issues)
        terminal = status in _REISSUE_TERMINAL_STATUSES or has_resolution
        expected_failed = elapsed_past_deadline and not terminal and not has_escalation
        if failed != expected_failed:
            counterexamples.append(
                {
                    "status": status,
                    "elapsed_past_deadline": elapsed_past_deadline,
                    "has_resolution": has_resolution,
                    "has_escalation": has_escalation,
                    "issue_codes": [issue["code"] for issue in issues],
                    "expected_failed": expected_failed,
                }
            )
    return checked, counterexamples


def _can_satisfy_serious_authority(
    *,
    evidence_class: str,
    authority_role: str,
    provenance_kind: str,
) -> bool:
    return (
        evidence_class == "authority_bearing"
        and authority_role in _AUTHORITY_ROLES_ALLOWED
        and provenance_kind in _SERIOUS_AUTHORITY_PROVENANCE
    )


def _phase_barrier_upgrade_allowed(statuses: Sequence[str]) -> bool:
    return all(status == "pass" for status in statuses)


def _same_input_closure_allowed(
    *,
    left_status: str,
    right_status: str,
    same_identity: bool,
    left_sha: bool,
    right_sha: bool,
) -> bool:
    return (
        left_status == "closed"
        and right_status == "closed"
        and same_identity
        and left_sha
        and right_sha
    )


def _cas_event_reconciliation_allowed(
    *,
    cas_present: bool,
    event_present: bool,
    payload_ref_matches: bool,
    payload_hash_matches: bool,
    identity_matches: bool,
    event_collision: bool,
) -> bool:
    return (
        cas_present
        and event_present
        and payload_ref_matches
        and payload_hash_matches
        and identity_matches
        and not event_collision
    )


def _terminal_transition_allowed(
    *,
    state: RunState,
    target: RunState,
    scorecard_identity_verified: bool,
    readiness_decision: str | None,
    publication_policy: str | None,
) -> bool:
    return (
        state is RunState.READINESS_CLOSED
        and target in VALID_TRANSITIONS[state]
        and scorecard_identity_verified
        and _terminal_readiness_matches(target, readiness_decision, publication_policy)
    )


def _terminal_readiness_matches(
    target: RunState,
    readiness_decision: str | None,
    publication_policy: str | None,
) -> bool:
    readiness = (readiness_decision or "").strip().casefold()
    policy = (publication_policy or "").strip().casefold()
    if target is RunState.APPROVED:
        return readiness in {"accepted", "approved"}
    if target is RunState.REJECTED:
        return readiness == "rejected"
    if target is RunState.PUBLISHED_BLOCKED:
        return readiness in {
            "blocked",
            "publication_blocked",
            "publish_blocked",
        } or policy in {"blocked", "not_public_exportable", "publish_blocked"}
    return False


def _producer_liveness_records(trace: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    rows.extend(_mapping_rows(trace.get("producer_handshake_records")))
    producer_pipeline = trace.get("producer_pipeline")
    if isinstance(producer_pipeline, Mapping):
        rows.extend(_mapping_rows(producer_pipeline.get("producer_handshake_records")))
        ledger = producer_pipeline.get("producer_handshake_ledger")
        if isinstance(ledger, Mapping):
            rows.extend(_mapping_rows(ledger.get("records")))
    ledger = trace.get("producer_handshake_ledger")
    if isinstance(ledger, Mapping):
        rows.extend(_mapping_rows(ledger.get("records")))
    return tuple(rows)


def _retry_lease_records(trace: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    rows.extend(_mapping_rows(trace.get("retry_lease_records")))
    rows.extend(_mapping_rows(trace.get("retry_records")))
    retry = trace.get("retry")
    if isinstance(retry, Mapping):
        rows.extend(_mapping_rows(retry.get("records")))
    lease = trace.get("lease")
    if isinstance(lease, Mapping):
        rows.extend(_mapping_rows(lease.get("records")))
    return tuple(rows)


def _escalation_records(trace: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    rows.extend(_mapping_rows(trace.get("escalation_records")))
    rows.extend(_mapping_rows(trace.get("liveness_blockers")))
    producer_pipeline = trace.get("producer_pipeline")
    if isinstance(producer_pipeline, Mapping):
        rows.extend(_mapping_rows(producer_pipeline.get("liveness_blockers")))
    return tuple(rows)


def _reissue_records(trace: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    rows.extend(_mapping_rows(trace.get("reissue_flows")))
    rows.extend(_mapping_rows(trace.get("reissue_records")))
    lifecycle = trace.get("lifecycle_reissue_report")
    if isinstance(lifecycle, Mapping):
        rows.extend(_mapping_rows(lifecycle.get("claim_revision_states")))
    return tuple(rows)


def _producer_liveness_issues(
    record: Mapping[str, Any],
    *,
    index: int,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    state = _state(record)
    producer_key = _producer_key(record)
    deadline_s = _effective_deadline_s(record)
    elapsed_s = _elapsed_s(record)
    field = f"producer_pipeline[{index}]"
    if state in _LIVENESS_ONGOING_STATES | _LIVENESS_WAIT_STATES and deadline_s is None:
        issues.append(
            _liveness_issue(
                "bounded_liveness_deadline_missing",
                "Closeout-sensitive producer wait has no governed finite deadline.",
                field,
                producer_key=producer_key,
                state=state,
            )
        )
    if (
        state in _LIVENESS_ONGOING_STATES | _LIVENESS_WAIT_STATES
        and deadline_s is not None
        and elapsed_s is not None
        and elapsed_s > deadline_s
        and not _has_escalation_signal(record)
    ):
        issues.append(
            _liveness_issue(
                "bounded_liveness_wait_exceeded_without_escalation",
                "Producer wait exceeded its governed deadline without runtime escalation.",
                field,
                producer_key=producer_key,
                state=state,
                deadline_s=deadline_s,
                elapsed_s=elapsed_s,
            )
        )
    if (
        state in _LIVENESS_SATISFIED_STATES
        and deadline_s is not None
        and elapsed_s is not None
        and elapsed_s > deadline_s
    ):
        issues.append(
            _liveness_issue(
                "bounded_liveness_satisfied_after_deadline",
                "Producer completion after the governed deadline cannot satisfy liveness.",
                field,
                producer_key=producer_key,
                state=state,
                deadline_s=deadline_s,
                elapsed_s=elapsed_s,
            )
        )
    if state in _LIVENESS_ESCALATION_STATES and _satisfies_authority(record):
        issues.append(
            _liveness_issue(
                "bounded_liveness_escalation_cannot_satisfy_authority",
                "Runtime escalation is governance evidence and cannot satisfy domain authority.",
                field,
                producer_key=producer_key,
                state=state,
            )
        )
    return issues


def _retry_lease_liveness_issues(
    record: Mapping[str, Any],
    *,
    index: int,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    state = _state(record)
    producer_key = _producer_key(record)
    field = f"retry_lease[{index}]"
    attempts = _int_or_none(
        record.get("attempts") or record.get("attempt_count") or record.get("retry_attempts")
    )
    retry_ceiling = _int_or_none(
        record.get("retry_ceiling")
        or record.get("max_retries")
        or _nested(record, ("liveness", "retry_ceiling"))
    )
    if attempts is not None and retry_ceiling is not None and attempts > retry_ceiling:
        issues.append(
            _liveness_issue(
                "bounded_liveness_retry_ceiling_exceeded",
                "Retry attempts exceeded the governed bounded-liveness retry ceiling.",
                field,
                producer_key=producer_key,
                state=state,
                attempts=attempts,
                retry_ceiling=retry_ceiling,
            )
        )
    observed_at = _float_or_none(record.get("observed_at_s") or record.get("now_s"))
    lease_expires_at = _float_or_none(
        record.get("lease_expires_at_s") or record.get("lease_deadline_s")
    )
    if (
        observed_at is not None
        and lease_expires_at is not None
        and observed_at > lease_expires_at
        and state in _LIVENESS_ONGOING_STATES
        and not _has_escalation_signal(record)
    ):
        issues.append(
            _liveness_issue(
                "bounded_liveness_lease_expired_without_escalation",
                "Lease expired while the retry/lease state remained live without escalation.",
                field,
                producer_key=producer_key,
                state=state,
                observed_at_s=observed_at,
                lease_expires_at_s=lease_expires_at,
            )
        )
    deadline_s = _effective_deadline_s(record)
    elapsed_s = _elapsed_s(record)
    if (
        deadline_s is not None
        and elapsed_s is not None
        and elapsed_s > deadline_s
        and state in _LIVENESS_ONGOING_STATES
        and not _has_escalation_signal(record)
    ):
        issues.append(
            _liveness_issue(
                "bounded_liveness_retry_deadline_exceeded_without_escalation",
                "Retry/lease state exceeded its governed deadline without escalation.",
                field,
                producer_key=producer_key,
                state=state,
                deadline_s=deadline_s,
                elapsed_s=elapsed_s,
            )
        )
    return issues


def _escalation_liveness_issues(
    record: Mapping[str, Any],
    *,
    index: int,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    state = _state(record)
    producer_key = _producer_key(record)
    field = f"escalation[{index}]"
    if state in _LIVENESS_ESCALATION_STATES and _satisfies_authority(record):
        issues.append(
            _liveness_issue(
                "bounded_liveness_escalation_cannot_satisfy_authority",
                "Escalated liveness state cannot satisfy producer/domain authority.",
                field,
                producer_key=producer_key,
                state=state,
            )
        )
    if bool(record.get("escalation_required")) and not _has_escalation_signal(record):
        issues.append(
            _liveness_issue(
                "bounded_liveness_required_escalation_missing",
                "A deadline breach marked escalation_required without an escalation artifact.",
                field,
                producer_key=producer_key,
                state=state,
            )
        )
    return issues


def _reissue_liveness_issues(
    record: Mapping[str, Any],
    *,
    index: int,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    state = _state(record)
    producer_key = _producer_key(record)
    field = f"reissue[{index}]"
    deadline_s = _effective_deadline_s(record)
    elapsed_s = _elapsed_s(record)
    terminal = state in _REISSUE_TERMINAL_STATUSES or bool(_text(record.get("resolution_ref")))
    if not terminal and deadline_s is None:
        issues.append(
            _liveness_issue(
                "bounded_liveness_reissue_deadline_missing",
                "Reissue flow has no governed finite deadline.",
                field,
                producer_key=producer_key,
                state=state,
            )
        )
    if (
        not terminal
        and deadline_s is not None
        and elapsed_s is not None
        and elapsed_s > deadline_s
        and not _has_escalation_signal(record)
    ):
        issues.append(
            _liveness_issue(
                "bounded_liveness_reissue_deadline_exceeded_without_escalation",
                "Reissue flow exceeded its governed deadline without escalation.",
                field,
                producer_key=producer_key,
                state=state,
                deadline_s=deadline_s,
                elapsed_s=elapsed_s,
            )
        )
    if bool(record.get("historical_authority_rewritten")):
        issues.append(
            _liveness_issue(
                "bounded_liveness_late_reissue_rewrites_authority",
                "Late reissue evidence must append revision state, not rewrite authority.",
                field,
                producer_key=producer_key,
                state=state,
            )
        )
    return issues


def _producer_model_check_record(
    *,
    state: str,
    elapsed_s: float,
    deadline_s: float,
    has_escalation: bool,
    satisfies_authority: bool,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "producer_component": "scholar",
        "state": state,
        "elapsed_s": elapsed_s,
        "liveness": {"deadline_s": deadline_s, "retry_ceiling": 1},
        "wait_conditions": [],
        "blockers": [],
        "satisfies_authority": satisfies_authority,
    }
    if state == "waiting_on_peer":
        record["wait_conditions"] = [
            {
                "peer_producer": "fabric",
                "artifact_family": "source_contract",
                "required_fields": ["source_ref"],
                "deadline_s": deadline_s,
            }
        ]
    if has_escalation or state in _LIVENESS_ESCALATION_STATES:
        record["escalation_ref"] = "event://runtime-escalation/scholar"
    return record


def _mapping_rows(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, Mapping):
        return (value,)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _state(record: Mapping[str, Any]) -> str:
    return (
        _text(record.get("state"))
        or _text(record.get("status"))
        or _text(record.get("liveness_state"))
        or "unknown"
    ).casefold()


def _producer_key(record: Mapping[str, Any]) -> str:
    return (
        _text(record.get("producer_key"))
        or _text(record.get("producer_component"))
        or _text(record.get("case_id"))
        or "unknown"
    )


def _effective_deadline_s(record: Mapping[str, Any]) -> float | None:
    for value in (
        _nested(record, ("liveness", "deadline_s")),
        record.get("deadline_s"),
        record.get("deadline_seconds"),
    ):
        parsed = _float_or_none(value)
        if parsed is not None:
            return parsed
    wait_deadlines = [
        parsed
        for row in _mapping_rows(record.get("wait_conditions"))
        if (parsed := _float_or_none(row.get("deadline_s"))) is not None
    ]
    if wait_deadlines:
        return min(wait_deadlines)
    return None


def _elapsed_s(record: Mapping[str, Any]) -> float | None:
    for value in (record.get("elapsed_s"), record.get("duration_s"), record.get("age_s")):
        parsed = _float_or_none(value)
        if parsed is not None:
            return parsed
    started_at = _float_or_none(record.get("started_at_s") or record.get("acquired_at_s"))
    observed_at = _float_or_none(record.get("observed_at_s") or record.get("now_s"))
    if started_at is not None and observed_at is not None:
        return observed_at - started_at
    return None


def _has_escalation_signal(record: Mapping[str, Any]) -> bool:
    state = _state(record)
    return (
        state in _LIVENESS_ESCALATION_STATES
        or bool(_text(record.get("escalation_ref")))
        or bool(_text(record.get("runtime_escalation_ref")))
        or bool(_mapping_rows(record.get("blockers")))
        or bool(_mapping_rows(record.get("liveness_blockers")))
    )


def _satisfies_authority(record: Mapping[str, Any]) -> bool:
    return any(
        bool(record.get(field))
        for field in (
            "satisfies_authority",
            "satisfies_evidence",
            "authority_satisfied",
            "closeout_satisfied",
            "domain_authority_satisfied",
        )
    )


def _liveness_issue(
    code: str,
    message: str,
    field: str,
    *,
    producer_key: str,
    state: str,
    **extra: object,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": "error",
        "spec_id": "bounded_liveness_deadline_consistency",
        "field": field,
        "producer_key": producer_key,
        "state": state,
        "message": message,
        "capability_label": "implemented_but_not_orchestrated",
    }
    payload.update(extra)
    return payload


def _float_or_none(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _nested(record: Mapping[str, Any], path: Sequence[str]) -> object:
    cursor: object = record
    for key in path:
        if not isinstance(cursor, Mapping):
            return None
        cursor = cursor.get(key)
    return cursor


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _row_label(row: Mapping[str, Any], index: int) -> str:
    value = row.get("spec_id")
    if _non_empty_string(value):
        return str(value).strip()
    return f"specs[{index}]"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if _non_empty_string(item)]


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text(value: object) -> str:
    return str(value or "").strip()


def _pct(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else round((numerator / denominator) * 100, 3)


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


_MODEL_CHECKERS: Mapping[str, Callable[[], tuple[int, list[dict[str, object]]]]] = {
    "authority_ordering_projection_never_satisfies_serious_authority": (
        _check_authority_ordering
    ),
    "phase_barrier_authority_upgrade_requires_passed_barriers": _check_phase_barriers,
    "same_input_closure_requires_closed_matching_identity": _check_same_input_closure,
    "cas_event_reconciliation_is_bijective_for_runtime_authority": (
        _check_cas_event_reconciliation
    ),
    "terminal_readiness_requires_closed_scorecard_and_readiness": (
        _check_terminal_readiness
    ),
    "bounded_liveness_producer_pipeline_deadline_consistency": (
        _check_bounded_liveness_producer_pipeline
    ),
    "bounded_liveness_retry_lease_deadline_consistency": (
        _check_bounded_liveness_retry_lease
    ),
    "bounded_liveness_escalation_does_not_satisfy_authority": (
        _check_bounded_liveness_escalation_authority
    ),
    "bounded_liveness_reissue_deadline_consistency": (
        _check_bounded_liveness_reissue_flow
    ),
}

__all__ = [
    "FORMAL_INVARIANT_REGISTRY_PATH",
    "FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH",
    "REQUIRED_CLOSEOUT_INVARIANT_IDS",
    "REQUIRED_TEMPORAL_LIVENESS_INVARIANT_IDS",
    "SCHEMA_VERSION",
    "TOOL_NAME",
    "FormalInvariantIssue",
    "FormalInvariantRegistryError",
    "FormalInvariantValidationResult",
    "build_formal_invariant_spec_report",
    "check_bounded_liveness_deadline_consistency",
    "dump_formal_invariant_report_json",
    "load_formal_invariant_specs",
    "model_check_formal_invariant_specs",
    "render_formal_invariant_report_text",
    "validate_formal_invariant_specs_payload",
]

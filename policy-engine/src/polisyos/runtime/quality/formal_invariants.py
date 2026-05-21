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
    required_count = len(REQUIRED_CLOSEOUT_INVARIANT_IDS)
    covered_count = len(covered)
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
            "issue_count": len(issues),
        },
        "required_closeout_invariants": sorted(REQUIRED_CLOSEOUT_INVARIANT_IDS),
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
}

__all__ = [
    "FORMAL_INVARIANT_REGISTRY_PATH",
    "FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH",
    "REQUIRED_CLOSEOUT_INVARIANT_IDS",
    "SCHEMA_VERSION",
    "TOOL_NAME",
    "FormalInvariantIssue",
    "FormalInvariantRegistryError",
    "FormalInvariantValidationResult",
    "build_formal_invariant_spec_report",
    "dump_formal_invariant_report_json",
    "load_formal_invariant_specs",
    "model_check_formal_invariant_specs",
    "render_formal_invariant_report_text",
    "validate_formal_invariant_specs_payload",
]

"""Policy Design Case record-family maturity profile."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from polisyos.runtime.quality.policy_design_case import (
    POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES,
    policy_design_case_record_family_coverage_scorecard_gates,
)

CASE_MATURITY_PROFILE_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.case_maturity_profile.v1"
)
CASE_MATURITY_PROFILE_RECORD_KEY = "case_maturity_profile"
CASE_MATURITY_PROFILE_RECORD_FAMILY = "integrity_self_fmea_and_maturity.v1"
CASE_MATURITY_PROFILE_SCORECARD_GATE = "policy_design_case.record_family_maturity"
CASE_MATURITY_PROFILE_NEXT_ACTION = (
    "Emit the Phase 29.3 case maturity profile with per-family runtime evidence "
    "refs before serious closeout."
)


class RecordFamilyMaturity(StrEnum):
    """Ordered maturity levels for Policy Design Case record families."""

    MISSING = "missing"
    STUB = "stub"
    PARTIAL = "partial"
    ARGUMENT_COMPLETE = "argument_complete"
    EVIDENCE_COMPLETE = "evidence_complete"
    INDEPENDENTLY_CHALLENGED = "independently_challenged"
    EXTERNALLY_AUDITABLE = "externally_auditable"
    VALIDATED_EX_POST = "validated_ex_post"


RECORD_FAMILY_MATURITY_LEVELS = tuple(item.value for item in RecordFamilyMaturity)
_MATURITY_INDEX = {level: index for index, level in enumerate(RECORD_FAMILY_MATURITY_LEVELS)}
_REQUIRED_REFS_BY_MATURITY = {
    RecordFamilyMaturity.PARTIAL.value: ("record_refs",),
    RecordFamilyMaturity.ARGUMENT_COMPLETE.value: ("record_refs", "argument_refs"),
    RecordFamilyMaturity.EVIDENCE_COMPLETE.value: (
        "record_refs",
        "argument_refs",
        "evidence_refs",
    ),
    RecordFamilyMaturity.INDEPENDENTLY_CHALLENGED.value: (
        "record_refs",
        "argument_refs",
        "evidence_refs",
        "challenge_refs",
    ),
    RecordFamilyMaturity.EXTERNALLY_AUDITABLE.value: (
        "record_refs",
        "argument_refs",
        "evidence_refs",
        "challenge_refs",
        "audit_refs",
    ),
    RecordFamilyMaturity.VALIDATED_EX_POST.value: (
        "record_refs",
        "argument_refs",
        "evidence_refs",
        "challenge_refs",
        "audit_refs",
        "ex_post_refs",
    ),
}
_PASSING_STATUSES = frozenset({"pass", "passed", "ok", "accepted", "approved"})


@dataclass(frozen=True)
class CaseMaturityIssue:
    """One deterministic maturity-profile validation issue."""

    code: str
    family_id: str
    field: str
    message: str
    value: object | None = None
    severity: str = "error"

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "code": self.code,
            "severity": self.severity,
            "family_id": self.family_id,
            "field": self.field,
            "message": self.message,
        }
        if self.value is not None:
            payload["value"] = self.value
        return payload


@dataclass(frozen=True)
class CaseMaturityValidationResult:
    """Validation result shared by scorecard gates and tests."""

    status: str
    record_family_maturities: tuple[dict[str, Any], ...]
    issues: tuple[CaseMaturityIssue, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "summary": {
                "record_family_count": len(self.record_family_maturities),
                "issue_count": len(self.issues),
                "required_family_count": len(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES),
                "maturity_levels": list(RECORD_FAMILY_MATURITY_LEVELS),
                "maturity_distribution": dict(
                    Counter(
                        str(row.get("maturity"))
                        for row in self.record_family_maturities
                        if _non_empty_string(row.get("maturity"))
                    )
                ),
            },
            "record_family_maturities": list(self.record_family_maturities),
            "issues": [issue.as_dict() for issue in self.issues],
        }


def build_case_maturity_profile(
    *,
    record_id: str,
    case_id: str,
    run_id: str,
    job_id: str,
    tenant_id: str,
    family_maturities: Mapping[str, Mapping[str, Any]] | None = None,
    evidence_ref: str,
    runtime_event_ref: str,
    owner: str = "team-quality-closeout",
    status: str = "pass",
) -> dict[str, Any]:
    """Build a case-bound maturity profile for every minimum record family."""

    maturity_by_family = family_maturities or {}
    rows: list[dict[str, Any]] = []
    for family_id in POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES:
        row = dict(maturity_by_family.get(family_id, {}))
        row["family_id"] = family_id
        row.setdefault("maturity", RecordFamilyMaturity.MISSING.value)
        for field in (
            "record_refs",
            "argument_refs",
            "evidence_refs",
            "challenge_refs",
            "audit_refs",
            "ex_post_refs",
            "assurance_deficit_refs",
        ):
            row.setdefault(field, [])
        rows.append(row)

    return {
        "schema_version": CASE_MATURITY_PROFILE_SCHEMA_VERSION,
        "record_family": CASE_MATURITY_PROFILE_RECORD_FAMILY,
        "record_id": record_id,
        "case_id": case_id,
        "run_id": run_id,
        "job_id": job_id,
        "tenant_id": tenant_id,
        "owner": owner,
        "status": status,
        "maturity_levels": list(RECORD_FAMILY_MATURITY_LEVELS),
        "maturity_distribution": dict(Counter(row["maturity"] for row in rows)),
        "record_family_maturities": rows,
        "evidence_ref": evidence_ref,
        "runtime_event_ref": runtime_event_ref,
    }


def validate_case_maturity_profile(
    record: Mapping[str, Any] | None,
) -> CaseMaturityValidationResult:
    """Validate a Phase 29.3 record-family maturity profile."""

    if not isinstance(record, Mapping):
        issue = CaseMaturityIssue(
            code="policy_design_case_maturity_profile_missing",
            family_id=CASE_MATURITY_PROFILE_RECORD_KEY,
            field=CASE_MATURITY_PROFILE_RECORD_KEY,
            message="Policy Design Case requires a Phase 29.3 maturity profile.",
        )
        return CaseMaturityValidationResult(
            status="fail",
            record_family_maturities=(),
            issues=(issue,),
        )

    issues: list[CaseMaturityIssue] = []
    if record.get("schema_version") != CASE_MATURITY_PROFILE_SCHEMA_VERSION:
        issues.append(
            _issue(
                "policy_design_case_maturity_schema_invalid",
                CASE_MATURITY_PROFILE_RECORD_KEY,
                "schema_version",
                "Case maturity profile must use the current schema version.",
                value=record.get("schema_version"),
            )
        )
    if record.get("record_family") != CASE_MATURITY_PROFILE_RECORD_FAMILY:
        issues.append(
            _issue(
                "policy_design_case_maturity_record_family_invalid",
                CASE_MATURITY_PROFILE_RECORD_KEY,
                "record_family",
                "Case maturity profile must belong to the integrity/self-FMEA family.",
                value=record.get("record_family"),
            )
        )
    for field in ("record_id", "case_id", "run_id", "job_id", "tenant_id", "owner"):
        if not _non_empty_string(record.get(field)):
            issues.append(
                _issue(
                    "policy_design_case_maturity_identity_missing",
                    CASE_MATURITY_PROFILE_RECORD_KEY,
                    field,
                    "Case maturity profile must include case-bound identity.",
                )
            )
    if _status(record.get("status")) not in _PASSING_STATUSES:
        issues.append(
            _issue(
                "policy_design_case_maturity_status_not_pass",
                CASE_MATURITY_PROFILE_RECORD_KEY,
                "status",
                "Case maturity profile must be passing for serious closeout.",
                value=record.get("status"),
            )
        )
    if not _runtime_ref(record.get("evidence_ref")):
        issues.append(
            _issue(
                "policy_design_case_maturity_runtime_ref_missing",
                CASE_MATURITY_PROFILE_RECORD_KEY,
                "evidence_ref",
                "Case maturity profile must include runtime evidence.",
                value=record.get("evidence_ref"),
            )
        )
    if not _runtime_ref(record.get("runtime_event_ref")):
        issues.append(
            _issue(
                "policy_design_case_maturity_runtime_event_missing",
                CASE_MATURITY_PROFILE_RECORD_KEY,
                "runtime_event_ref",
                "Case maturity profile must include a runtime event.",
                value=record.get("runtime_event_ref"),
            )
        )

    levels = _string_list(record.get("maturity_levels"))
    if tuple(levels) != RECORD_FAMILY_MATURITY_LEVELS:
        issues.append(
            _issue(
                "policy_design_case_maturity_levels_invalid",
                CASE_MATURITY_PROFILE_RECORD_KEY,
                "maturity_levels",
                "Case maturity profile must expose the ordered Phase 29.3 levels.",
                value=levels,
            )
        )

    rows = record.get("record_family_maturities")
    if not isinstance(rows, list) or not rows:
        issues.append(
            _issue(
                "policy_design_case_maturity_rows_missing",
                CASE_MATURITY_PROFILE_RECORD_KEY,
                "record_family_maturities",
                "Case maturity profile must include per-family maturity rows.",
            )
        )
        return CaseMaturityValidationResult(
            status="fail",
            record_family_maturities=(),
            issues=tuple(issues),
        )

    normalized_rows: list[dict[str, Any]] = []
    seen: dict[str, int] = {}
    for index, raw_row in enumerate(rows, start=1):
        if not isinstance(raw_row, Mapping):
            issues.append(
                _issue(
                    "policy_design_case_maturity_row_invalid",
                    f"record_family_maturities[{index}]",
                    "record_family_maturities",
                    "Every maturity profile row must be an object.",
                )
            )
            continue
        row = dict(raw_row)
        normalized_rows.append(row)
        family_id = _row_family_id(row, index)
        if family_id in seen:
            issues.append(
                _issue(
                    "policy_design_case_maturity_family_duplicate",
                    family_id,
                    "family_id",
                    "Maturity profile family IDs must be unique.",
                    value=family_id,
                )
            )
        seen[family_id] = index
        issues.extend(_row_issues(row, index=index))

    expected = set(POLICY_DESIGN_CASE_MINIMUM_RECORD_FAMILIES)
    actual = {
        str(row.get("family_id")).strip()
        for row in normalized_rows
        if _non_empty_string(row.get("family_id"))
    }
    for family_id in sorted(expected - actual):
        issues.append(
            _issue(
                "policy_design_case_maturity_family_missing",
                family_id,
                "family_id",
                "Every minimum record family must have a maturity row.",
                value=family_id,
            )
        )
    for family_id in sorted(actual - expected):
        issues.append(
            _issue(
                "policy_design_case_maturity_family_unknown",
                family_id,
                "family_id",
                "Maturity profile row must reference a minimum record family.",
                value=family_id,
            )
        )

    return CaseMaturityValidationResult(
        status="fail" if issues else "pass",
        record_family_maturities=tuple(normalized_rows),
        issues=tuple(issues),
    )


def policy_design_case_maturity_scorecard_gates(
    case: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return blocking scorecard gates for the Phase 29.3 maturity profile."""

    record = case.get(CASE_MATURITY_PROFILE_RECORD_KEY)
    result = validate_case_maturity_profile(record if isinstance(record, Mapping) else None)
    gates = policy_design_case_record_family_coverage_scorecard_gates(
        case,
        phase="policy_design_case_maturity_profile",
        gate_name="policy_design_case.maturity_record_family_coverage",
    )
    gates.extend(
        [
            {
                "name": CASE_MATURITY_PROFILE_SCORECARD_GATE,
                "stage": "ops",
                "code": issue.code,
                "status": "fail",
                "layer": "assurance_case",
                "phase": "policy_design_case_maturity_profile",
                "message": issue.message,
                "evidence_ref": "quality_evidence/policy_design_case.json",
                "next_action": CASE_MATURITY_PROFILE_NEXT_ACTION,
                "missing_input": issue.field,
                "family_id": issue.family_id,
                "blocking": True,
            }
            for issue in result.issues
        ]
    )
    return gates


def _row_issues(row: Mapping[str, Any], *, index: int) -> list[CaseMaturityIssue]:
    family_id = _row_family_id(row, index)
    issues: list[CaseMaturityIssue] = []
    if not _non_empty_string(row.get("family_id")):
        issues.append(
            _issue(
                "policy_design_case_maturity_family_id_missing",
                family_id,
                "family_id",
                "Every maturity row must name a record family.",
            )
        )

    maturity = row.get("maturity")
    if not isinstance(maturity, str) or maturity not in _MATURITY_INDEX:
        issues.append(
            _issue(
                "policy_design_case_maturity_level_invalid",
                family_id,
                "maturity",
                "Maturity level must be one of the Phase 29.3 levels.",
                value=maturity,
            )
        )
        return issues

    required_fields = _REQUIRED_REFS_BY_MATURITY.get(maturity, ())
    for field in required_fields:
        refs = _string_list(row.get(field))
        if not refs:
            issues.append(
                _issue(
                    f"policy_design_case_maturity_{field}_missing",
                    family_id,
                    field,
                    f"Maturity `{maturity}` cannot be claimed without `{field}`.",
                    value=row.get(field),
                )
            )
            continue
        invalid_refs = [ref for ref in refs if not _runtime_ref(ref)]
        if invalid_refs:
            issues.append(
                _issue(
                    f"policy_design_case_maturity_{field}_invalid",
                    family_id,
                    field,
                    f"Maturity `{maturity}` requires runtime evidence refs in `{field}`.",
                    value=invalid_refs,
                )
            )
    return issues


def _issue(
    code: str,
    family_id: str,
    field: str,
    message: str,
    *,
    value: object | None = None,
) -> CaseMaturityIssue:
    return CaseMaturityIssue(
        code=code,
        family_id=family_id,
        field=field,
        message=message,
        value=value,
    )


def _row_family_id(row: Mapping[str, Any], index: int) -> str:
    value = row.get("family_id")
    if _non_empty_string(value):
        return str(value).strip()
    return f"record_family_maturities[{index}]"


def _non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _status(value: object) -> str:
    return str(value or "").strip().casefold().replace("-", "_")


def _runtime_ref(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text or len(text) > 512 or any(char in text for char in "\r\n\t"):
        return False
    if text.startswith("sha256:"):
        return _hex64(text.removeprefix("sha256:"))
    if text.startswith("cas://sha256/"):
        return _hex64(text.removeprefix("cas://sha256/"))
    return text.startswith(("artifact://", "event://"))


def _hex64(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdefABCDEF" for char in value)


__all__ = [
    "CASE_MATURITY_PROFILE_RECORD_FAMILY",
    "CASE_MATURITY_PROFILE_RECORD_KEY",
    "CASE_MATURITY_PROFILE_SCHEMA_VERSION",
    "CASE_MATURITY_PROFILE_SCORECARD_GATE",
    "RECORD_FAMILY_MATURITY_LEVELS",
    "CaseMaturityIssue",
    "CaseMaturityValidationResult",
    "RecordFamilyMaturity",
    "build_case_maturity_profile",
    "policy_design_case_maturity_scorecard_gates",
    "validate_case_maturity_profile",
]

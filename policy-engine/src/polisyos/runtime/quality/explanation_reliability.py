"""BERL warrant reliability bridge for Policy Design Case claim warrants."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any

_REQUIRES_BERL_KEYS = (
    "requires_explanation_reliability",
    "explanation_reliability_required",
    "explanation_reliability_affects_reviewer_trust",
    "explanation_trust_affects_reviewer_trust",
    "reviewer_trust_depends_on_explanation",
    "explanation_trust_affects_acceptance",
    "automated_claim_acceptance_depends_on_explanation",
    "explanation_reliability_affects_claim_acceptance",
    "explanation_reliability_affects_automated_acceptance",
    "explanation_reliability_affects_user_facing_confidence",
    "explanation_trust_affects_user_facing_confidence",
    "user_facing_confidence_depends_on_explanation",
)

_BERL_REF_KEYS = (
    "berl_reliability_refs",
    "berl_reliability_ref",
    "explanation_reliability_refs",
    "explanation_reliability_ref",
    "berl_explanation_bundle_refs",
    "berl_explanation_bundle_ref",
    "explanation_bundle_refs",
    "explanation_bundle_ref",
)

_RELIABILITY_RECORD_KEYS = (
    "warrant_reliability_records",
    "warrant_reliability",
    "berl_warrant_reliability_records",
    "berl_reliability_records",
    "explanation_reliability_records",
)

_RELIABILITY_RECORD_ID_KEYS = (
    "reliability_id",
    "berl_reliability_id",
    "record_id",
    "id",
    "evidence_ref",
    "cas_ref",
    "artifact_ref",
    "explanation_bundle_ref",
    "validation_result_ref",
    "empirical_bound_ref",
    "local_infidelity_diagnostic_ref",
)

_THRESHOLD_KEYS = (
    "validation_thresholds",
    "thresholds",
    "berl_validation_thresholds",
)

_VALIDATION_KEYS = (
    "validation",
    "validation_result",
    "berl_validation",
    "threshold_decision",
)


@dataclass(frozen=True)
class WarrantReliabilityIssue:
    """One fail-closed BERL warrant reliability issue."""

    code: str
    field: str
    message: str
    evidence_ref: str | None = None


@dataclass(frozen=True)
class WarrantReliabilityEvaluation:
    """Normalized BERL reliability records and their validation issues."""

    records: tuple[dict[str, Any], ...]
    issues: tuple[WarrantReliabilityIssue, ...]


def warrant_requires_berl_reliability(warrant: Mapping[str, Any]) -> bool:
    """Return whether BERL evidence is mandatory for this warrant."""

    return any(_truthy(warrant.get(key)) for key in _REQUIRES_BERL_KEYS)


def warrant_berl_reliability_refs(warrant: Mapping[str, Any]) -> tuple[str, ...]:
    """Collect explicit BERL reliability refs from a warrant record."""

    values: list[str] = []
    for key in _BERL_REF_KEYS:
        values.extend(_text_values(warrant.get(key)))
    return tuple(dict.fromkeys(values))


def evaluate_warrant_berl_reliability(
    case: Mapping[str, Any],
    warrant: Mapping[str, Any],
    *,
    claim_id: str | None = None,
) -> WarrantReliabilityEvaluation:
    """Validate BERL reliability records linked to a warrant."""

    refs = set(warrant_berl_reliability_refs(warrant))
    rows = _matching_reliability_rows(case, warrant, refs=refs, claim_id=claim_id)
    records: list[dict[str, Any]] = []
    issues: list[WarrantReliabilityIssue] = []
    if refs and not rows:
        issues.append(
            WarrantReliabilityIssue(
                code="policy_design_warrant_berl_reliability_record_missing",
                field="warrants.berl_reliability_refs",
                message="BERL warrant reliability refs must resolve to reliability records.",
                evidence_ref=_first_text(*refs),
            )
        )
    for row in rows:
        normalized, row_issues = _normalize_reliability_record(row, warrant=warrant)
        records.append(normalized)
        issues.extend(row_issues)
    return WarrantReliabilityEvaluation(tuple(records), tuple(issues))


def build_berl_warrant_reliability_record(
    *,
    reliability_id: str,
    claim_id: str,
    explanation_bundle_ref: str,
    validation_thresholds: Mapping[str, Any],
    explanation_bundle: Mapping[str, Any] | None = None,
    evidence_ref: str | None = None,
    warrant_id: str | None = None,
    runtime_event_ref: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a BERL warrant reliability record without requiring argument refs."""

    record: dict[str, Any] = {
        "schema_version": "policyos.runtime.policy_design_case.berl_warrant_reliability.v1",
        "record_type": "berl_warrant_reliability",
        "reliability_id": str(reliability_id),
        "claim_id": str(claim_id),
        "explanation_bundle_ref": str(explanation_bundle_ref),
        "validation_thresholds": dict(validation_thresholds),
    }
    if evidence_ref is not None:
        record["evidence_ref"] = str(evidence_ref)
    if warrant_id is not None:
        record["warrant_id"] = str(warrant_id)
    if runtime_event_ref is not None:
        record["runtime_event_ref"] = str(runtime_event_ref)
    if explanation_bundle is not None:
        record["explanation_bundle"] = dict(explanation_bundle)
        normalized, issues = _normalize_reliability_record(record, warrant={})
        record.update(
            {
                key: value
                for key, value in normalized.items()
                if key
                in {
                    "threshold_decision",
                    "empirical_bounds",
                    "local_infidelity_diagnostics",
                    "explanation_bundle",
                }
            }
        )
        if issues:
            record["validation_issues"] = [
                {
                    "code": issue.code,
                    "field": issue.field,
                    "message": issue.message,
                    "evidence_ref": issue.evidence_ref,
                }
                for issue in issues
            ]
    if metadata:
        record["metadata"] = dict(metadata)
    return record


def _matching_reliability_rows(
    case: Mapping[str, Any],
    warrant: Mapping[str, Any],
    *,
    refs: set[str],
    claim_id: str | None,
) -> tuple[Mapping[str, Any], ...]:
    rows = _reliability_rows(case, warrant)
    warrant_id = _first_text(
        warrant.get("warrant_id"),
        warrant.get("record_id"),
        warrant.get("id"),
        warrant.get("evidence_ref"),
        warrant.get("cas_ref"),
    )
    matched: list[Mapping[str, Any]] = []
    for row in rows:
        row_ids = set(_reliability_record_id_values(row))
        if refs and refs.isdisjoint(row_ids):
            continue
        if refs or _row_matches_warrant(row, warrant_id=warrant_id, claim_id=claim_id):
            matched.append(row)
    return tuple(matched)


def _reliability_rows(
    case: Mapping[str, Any],
    warrant: Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    rows: list[Mapping[str, Any]] = []
    for source in (case, warrant):
        for key in _RELIABILITY_RECORD_KEYS:
            value = source.get(key)
            if isinstance(value, Mapping):
                rows.append(value)
            elif isinstance(value, list):
                rows.extend(item for item in value if isinstance(item, Mapping))
    return tuple(rows)


def _reliability_record_id_values(row: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in _RELIABILITY_RECORD_ID_KEYS:
        values.extend(_text_values(row.get(key)))
    return tuple(dict.fromkeys(values))


def _row_matches_warrant(
    row: Mapping[str, Any],
    *,
    warrant_id: str | None,
    claim_id: str | None,
) -> bool:
    if warrant_id is not None and warrant_id in set(
        _text_values(row.get("warrant_refs"))
        + _text_values(row.get("warrant_ref"))
        + _text_values(row.get("warrant_id"))
    ):
        return True
    return claim_id is not None and claim_id in set(
        _text_values(row.get("claim_ids"))
        + _text_values(row.get("claim_id"))
        + _text_values(row.get("major_claim_id"))
    )


def _normalize_reliability_record(
    row: Mapping[str, Any],
    *,
    warrant: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[WarrantReliabilityIssue, ...]]:
    record_id = _first_text(*[row.get(key) for key in _RELIABILITY_RECORD_ID_KEYS])
    evidence_ref = _first_text(row.get("evidence_ref"), row.get("cas_ref"), row.get("artifact_ref"))
    thresholds = _thresholds_payload(row)
    normalized: dict[str, Any] = {
        "record_id": record_id,
        "claim_id": _first_text(row.get("claim_id"), warrant.get("claim_id")),
        "warrant_id": _first_text(row.get("warrant_id"), warrant.get("warrant_id")),
        "evidence_ref": evidence_ref,
        "explanation_bundle_ref": _first_text(
            row.get("explanation_bundle_ref"),
            row.get("berl_explanation_bundle_ref"),
            row.get("bundle_ref"),
        ),
        "validation_thresholds": thresholds or None,
        "empirical_bounds": _explicit_sequence(
            row.get("empirical_bounds") or row.get("empirical_reliability_bounds")
        ),
        "local_infidelity_diagnostics": _explicit_sequence(
            row.get("local_infidelity_diagnostics")
            or row.get("infidelity_diagnostics")
        ),
    }
    issues: list[WarrantReliabilityIssue] = []
    bundle_payload = _as_mapping(
        row.get("explanation_bundle") or row.get("berl_explanation_bundle")
    )
    if bundle_payload is not None:
        bundle_record, bundle_issues = _validate_bundle_record(
            bundle_payload,
            thresholds=thresholds,
            evidence_ref=evidence_ref,
        )
        normalized.update(bundle_record)
        issues.extend(bundle_issues)
    else:
        validation = _first_mapping(row, _VALIDATION_KEYS)
        normalized["threshold_decision"] = dict(validation) if validation else None
        if _validation_failed_thresholds(validation):
            issues.append(
                WarrantReliabilityIssue(
                    code="policy_design_warrant_berl_threshold_failed",
                    field="warrant_reliability_records.validation_thresholds",
                    message="BERL warrant reliability thresholds did not pass.",
                    evidence_ref=evidence_ref,
                )
            )

    _required_reliability_record_issues(normalized, evidence_ref=evidence_ref, issues=issues)
    return {key: value for key, value in normalized.items() if value is not None}, tuple(issues)


def _required_reliability_record_issues(
    normalized: Mapping[str, Any],
    *,
    evidence_ref: str | None,
    issues: list[WarrantReliabilityIssue],
) -> None:
    required: tuple[tuple[str, str, str, str], ...] = (
        (
            "explanation_bundle_ref",
            "policy_design_warrant_berl_bundle_ref_missing",
            "warrant_reliability_records.explanation_bundle_ref",
            "BERL warrant reliability records must cite the explanation bundle.",
        ),
        (
            "validation_thresholds",
            "policy_design_warrant_berl_validation_thresholds_missing",
            "warrant_reliability_records.validation_thresholds",
            "BERL warrant reliability records must include validation thresholds.",
        ),
        (
            "threshold_decision",
            "policy_design_warrant_berl_threshold_decision_missing",
            "warrant_reliability_records.threshold_decision",
            "BERL warrant reliability records must include a threshold decision.",
        ),
        (
            "empirical_bounds",
            "policy_design_warrant_berl_empirical_bounds_missing",
            "warrant_reliability_records.empirical_bounds",
            "BERL warrant reliability records must include empirical reliability bounds.",
        ),
        (
            "local_infidelity_diagnostics",
            "policy_design_warrant_berl_local_infidelity_missing",
            "warrant_reliability_records.local_infidelity_diagnostics",
            "BERL warrant reliability records must include local infidelity diagnostics.",
        ),
    )
    for key, code, field, message in required:
        if _has_required_payload(normalized.get(key)):
            continue
        issues.append(
            WarrantReliabilityIssue(
                code=code,
                field=field,
                message=message,
                evidence_ref=evidence_ref,
            )
        )


def _has_required_payload(value: object) -> bool:
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, list | tuple | set):
        return bool(value)
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def _validate_bundle_record(
    bundle_payload: Mapping[str, Any],
    *,
    thresholds: dict[str, Any],
    evidence_ref: str | None,
) -> tuple[dict[str, Any], tuple[WarrantReliabilityIssue, ...]]:
    try:
        from polisyos.berl.contracts.explanation_bundle import ExplanationBundle
        from polisyos.berl.contracts.validation_rules import (
            ValidationThresholds,
            validate_explanation_bundle,
        )

        bundle = ExplanationBundle.model_validate(bundle_payload)
        validation = validate_explanation_bundle(
            bundle,
            thresholds=_validation_thresholds(ValidationThresholds, thresholds),
        )
    except (ImportError, TypeError, ValueError) as exc:
        return (
            {"threshold_decision": {"status": "fail", "violations": [str(exc)]}},
            (
                WarrantReliabilityIssue(
                    code="policy_design_warrant_berl_bundle_invalid",
                    field="warrant_reliability_records.explanation_bundle",
                    message="BERL explanation bundle could not be validated.",
                    evidence_ref=evidence_ref,
                ),
            ),
        )

    empirical_bounds = _empirical_bounds_from_bundle(bundle)
    local_infidelity = _local_infidelity_from_bundle(bundle)
    threshold_decision = {
        "status": "pass" if validation.passed else "fail",
        "display_policy": validation.display_policy,
        "faithfulness_claim": validation.faithfulness_claim,
        "violations": list(validation.violations),
        "warnings": list(validation.warnings),
    }
    issues: list[WarrantReliabilityIssue] = []
    if not validation.passed:
        code = (
            "policy_design_warrant_berl_threshold_failed"
            if _threshold_violations(validation.violations)
            else "policy_design_warrant_berl_validation_failed"
        )
        issues.append(
            WarrantReliabilityIssue(
                code=code,
                field="warrant_reliability_records.validation_thresholds",
                message=(
                    "BERL warrant reliability thresholds did not pass: "
                    + ", ".join(validation.violations or ("unknown",))
                ),
                evidence_ref=evidence_ref,
            )
        )
    return (
        {
            "explanation_bundle": {
                "bundle_id": bundle.bundle_id,
                "schema_version": bundle.schema_version,
                "display_policy": bundle.display_policy,
                "faithfulness_claim": bundle.faithfulness_claim,
            },
            "threshold_decision": threshold_decision,
            "empirical_bounds": empirical_bounds,
            "local_infidelity_diagnostics": local_infidelity,
        },
        tuple(issues),
    )


def _validation_thresholds(
    thresholds_cls: type[object],
    thresholds: Mapping[str, Any],
) -> object | None:
    if not thresholds:
        return None
    allowed = {field.name for field in fields(thresholds_cls)}
    payload = {key: value for key, value in thresholds.items() if key in allowed}
    return thresholds_cls(**payload) if payload else None


def _thresholds_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = _first_mapping(row, _THRESHOLD_KEYS)
    return dict(payload) if payload else {}


def _first_mapping(
    row: Mapping[str, Any],
    keys: tuple[str, ...],
) -> Mapping[str, Any] | None:
    for key in keys:
        payload = _as_mapping(row.get(key))
        if payload is not None:
            return payload
    return None


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _empirical_bounds_from_bundle(bundle: object) -> list[dict[str, Any]]:
    bounds: list[dict[str, Any]] = []
    for method in getattr(bundle, "methods", ()):
        infidelity = getattr(method, "infidelity", None)
        if infidelity is None:
            continue
        bounds.append(
            {
                "method_id": getattr(method, "method_id", None),
                "bound_type": infidelity.bound_type,
                "upper_bound": infidelity.upper_bound,
                "confidence": infidelity.confidence,
            }
        )
    return bounds


def _local_infidelity_from_bundle(bundle: object) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for method in getattr(bundle, "methods", ()):
        infidelity = getattr(method, "infidelity", None)
        if infidelity is None:
            continue
        diagnostics.append(
            {
                "method_id": getattr(method, "method_id", None),
                "loss": infidelity.loss,
                "point_estimate": infidelity.point_estimate,
                "upper_bound": infidelity.upper_bound,
                "confidence": infidelity.confidence,
                "n_eval_perturbations": infidelity.n_eval_perturbations,
                "residual_cap": infidelity.residual_cap,
                "evaluation_split": infidelity.evaluation_split,
            }
        )
    return diagnostics


def _validation_failed_thresholds(validation: Mapping[str, Any] | None) -> bool:
    if validation is None:
        return False
    status = _normalized_text(
        validation.get("status"),
        validation.get("gate_status"),
        validation.get("threshold_status"),
    )
    decision = _normalized_text(validation.get("decision"), validation.get("threshold_decision"))
    violations = tuple(_text_values(validation.get("violations")))
    return (
        status in {"fail", "failed", "blocked", "reject", "rejected"}
        or decision in {"fail", "failed", "blocked", "reject", "rejected"}
        or _threshold_violations(violations)
    )


def _threshold_violations(violations: tuple[str, ...]) -> bool:
    return any(
        "threshold" in violation
        or "tolerance" in violation
        or "infidelity_upper_bound" in violation
        for violation in violations
    )


def _explicit_sequence(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Mapping):
        return [dict(value)]
    return []


def _truthy(value: object) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "required", "in_scope"}
    return False


def _first_text(*values: object) -> str | None:
    for value in values:
        text_values = _text_values(value)
        if text_values:
            return text_values[0]
    return None


def _normalized_text(*values: object) -> str | None:
    text = _first_text(*values)
    return text.casefold().replace("-", "_") if text is not None else None


def _text_values(value: object) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, Mapping):
        values: list[str] = []
        for key in ("ref", "id", "value", "evidence_ref", "cas_ref", "artifact_ref"):
            values.extend(_text_values(value.get(key)))
        return values
    if isinstance(value, list | tuple | set):
        values = []
        for item in value:
            values.extend(_text_values(item))
        return values
    return []


__all__ = [
    "WarrantReliabilityEvaluation",
    "WarrantReliabilityIssue",
    "build_berl_warrant_reliability_record",
    "evaluate_warrant_berl_reliability",
    "warrant_berl_reliability_refs",
    "warrant_requires_berl_reliability",
]

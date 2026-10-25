"""BERL warrant reliability bridge for Policy Design Case claim warrants."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Any, Literal, TypedDict

if TYPE_CHECKING:
    from polisyos.berl import ValidationThresholds
    from polisyos.berl.contracts.explanation_bundle import ExplanationBundle
    from polisyos.core.artifacts import ArtifactStore

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
    artifact_store: ArtifactStore | None = None,
) -> WarrantReliabilityEvaluation:
    """Validate BERL reliability records linked to a warrant.

    Args:
        case: Candidate Policy Design Case evidence.
        warrant: Warrant whose reliability records are selected.
        claim_id: Optional claim identity used to narrow candidate rows.
        artifact_store: Optional Core CAS store used to resolve selected bundle refs.
            A supplied reference requires this store and is never rescued by inline bytes.
    """

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
        normalized, row_issues = _normalize_reliability_record(
            row,
            warrant=warrant,
            claim_id=claim_id,
            artifact_store=artifact_store,
        )
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
    expected_explanation_subject: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a BERL warrant reliability candidate record.

    Inline bundle values can provide candidate diagnostics at construction time. Runtime
    admission must independently resolve ``explanation_bundle_ref`` through its CAS store.

    Args:
        reliability_id: Stable identity for this reliability record.
        claim_id: Claim associated with the record.
        explanation_bundle_ref: Selected typed CAS reference serialized as JSON.
        validation_thresholds: BERL thresholds to apply to the resolved bundle.
        explanation_bundle: Optional candidate payload for preliminary diagnostics only.
        evidence_ref: Optional upstream evidence reference.
        warrant_id: Optional warrant associated with the record.
        runtime_event_ref: Optional runtime event reference.
        metadata: Optional non-authoritative descriptive metadata.
        expected_explanation_subject: Optional caller-provided subject to bind at admission.
    """

    record: dict[str, Any] = {
        "schema_version": "policyos.runtime.policy_design_case.berl_warrant_reliability.v2",
        "record_type": "berl_warrant_reliability",
        "reliability_id": str(reliability_id),
        "claim_id": str(claim_id),
        "explanation_bundle_ref": str(explanation_bundle_ref),
        "validation_thresholds": dict(validation_thresholds),
        "subject_context_resolution": {
            "status": "not_established",
            "predicate_class": "not_established",
            "source": "no_typed_claim_run_subject_resolver",
            "reason": "Record construction cannot reconcile a producer-owned claim/run subject.",
        },
    }
    if evidence_ref is not None:
        record["evidence_ref"] = str(evidence_ref)
    if warrant_id is not None:
        record["warrant_id"] = str(warrant_id)
    if runtime_event_ref is not None:
        record["runtime_event_ref"] = str(runtime_event_ref)
    if explanation_bundle is not None:
        record["explanation_bundle"] = dict(explanation_bundle)
        candidate_record, issues = _validate_bundle_record(
            record["explanation_bundle"],
            thresholds=dict(validation_thresholds),
            evidence_ref=evidence_ref or str(explanation_bundle_ref),
        )
        record["candidate_diagnostics"] = {
            "source": "inline_builder_payload",
            **candidate_record,
        }
        record["candidate_diagnostics_status"] = _decision_status(candidate_record)
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
    record["threshold_decision"] = {
        "status": "fail",
        "violations": ["policy_design_warrant_berl_subject_context_not_established"],
        "candidate_status": record.get("candidate_diagnostics_status", "not_evaluated"),
    }
    if metadata:
        record["metadata"] = dict(metadata)
    if expected_explanation_subject is not None:
        record["expected_explanation_subject"] = dict(expected_explanation_subject)
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
    claim_id: str | None,
    artifact_store: ArtifactStore | None,
) -> tuple[dict[str, Any], tuple[WarrantReliabilityIssue, ...]]:
    record_id = _first_text(*[row.get(key) for key in _RELIABILITY_RECORD_ID_KEYS])
    evidence_ref = _first_text(row.get("evidence_ref"), row.get("cas_ref"), row.get("artifact_ref"))
    thresholds = _thresholds_payload(row)
    normalized: dict[str, Any] = {
        "schema_version": "policyos.runtime.policy_design_case.berl_warrant_reliability.v2",
        "record_id": record_id,
        "claim_id": _first_text(row.get("claim_id"), warrant.get("claim_id")),
        "warrant_id": _first_text(row.get("warrant_id"), warrant.get("warrant_id")),
        "evidence_ref": evidence_ref,
        "explanation_bundle_ref": _bundle_ref_display_value(row),
        "validation_thresholds": thresholds or None,
        "empirical_bounds": _explicit_sequence(
            row.get("empirical_bounds") or row.get("empirical_reliability_bounds")
        ),
        "local_infidelity_diagnostics": _explicit_sequence(
            row.get("local_infidelity_diagnostics") or row.get("infidelity_diagnostics")
        ),
        "subject_context_resolution": {
            "status": "not_established",
            "predicate_class": "not_established",
            "source": "no_typed_claim_run_subject_resolver",
            "reason": (
                "The selected bundle has not been joined to a producer-owned claim/run subject."
            ),
        },
    }
    issues: list[WarrantReliabilityIssue] = []
    bundle_payload, selected_ref, resolution_code, method_identity_projection = (
        _load_selected_bundle_payload(row, artifact_store=artifact_store)
    )
    if selected_ref is not None:
        normalized["explanation_bundle_ref"] = selected_ref
    if resolution_code is not None:
        if resolution_code == "policy_design_warrant_berl_bundle_ref_missing":
            # An inline payload remains visible only as a candidate diagnostic. It cannot
            # establish selected CAS bytes or a claim/run subject.
            candidate_payload = _as_mapping(
                row.get("explanation_bundle") or row.get("berl_explanation_bundle")
            )
            if candidate_payload is not None:
                candidate_record, candidate_issues = _validate_bundle_record(
                    candidate_payload,
                    thresholds=thresholds,
                    evidence_ref=evidence_ref,
                )
                normalized["candidate_diagnostics"] = {
                    "source": "inline_record_payload",
                    **candidate_record,
                }
                normalized["candidate_diagnostics_status"] = _decision_status(candidate_record)
                normalized.update(_candidate_summary_fields(candidate_record))
                issues.extend(candidate_issues)
            normalized["threshold_decision"] = {
                "status": "fail",
                "violations": [resolution_code],
                "candidate_status": normalized.get("candidate_diagnostics_status", "not_evaluated"),
            }
        else:
            normalized["threshold_decision"] = {
                "status": "fail",
                "violations": [resolution_code],
            }
            issues.append(
                WarrantReliabilityIssue(
                    code=resolution_code,
                    field="warrant_reliability_records.explanation_bundle_ref",
                    message=(
                        "The selected BERL store read failed; object absence is not established."
                        if resolution_code
                        == "policy_design_warrant_berl_bundle_store_read_unavailable"
                        else "The selected BERL explanation artifact could not be resolved."
                    ),
                    evidence_ref=selected_ref or evidence_ref,
                )
            )
    else:
        candidate_record, candidate_issues = _validate_bundle_record(
            bundle_payload or {},
            thresholds=thresholds,
            evidence_ref=selected_ref or evidence_ref,
        )
        normalized["candidate_diagnostics"] = {
            "source": "selected_cas_bundle",
            **candidate_record,
        }
        normalized["candidate_diagnostics_status"] = _decision_status(candidate_record)
        normalized.update(_candidate_summary_fields(candidate_record))
        selected_explanation = _as_mapping(normalized.get("explanation_bundle"))
        if method_identity_projection is not None and selected_explanation is not None:
            normalized["explanation_bundle"] = {
                **dict(selected_explanation),
                "methods": method_identity_projection,
            }
        issues.extend(candidate_issues)

        subject_context = _candidate_subject_context_resolution(
            row,
            warrant,
            claim_id=claim_id,
            record_id=record_id,
            selected_ref=selected_ref,
            bundle_payload=bundle_payload or {},
        )
        normalized["subject_context_resolution"] = subject_context
        candidate_decision = _as_mapping(candidate_record.get("threshold_decision")) or {}
        candidate_violations = candidate_decision.get("violations")
        violations = list(candidate_violations if isinstance(candidate_violations, list) else [])
        violations.append("policy_design_warrant_berl_subject_context_not_established")
        linkage = _as_mapping(subject_context.get("claim_warrant_linkage")) or {}
        if linkage.get("status") == "mismatch":
            violations.append("policy_design_warrant_berl_subject_context_link_mismatch")
            issues.append(
                WarrantReliabilityIssue(
                    code="policy_design_warrant_berl_subject_context_link_mismatch",
                    field="warrant_reliability_records.claim_warrant_linkage",
                    message=(
                        "The record's claim or warrant identifiers conflict with "
                        "the selected claim/warrant references."
                    ),
                    evidence_ref=selected_ref or evidence_ref,
                )
            )
        assertions = _as_mapping(subject_context.get("candidate_assertions")) or {}
        if assertions.get("status") in {"mismatch", "conflicting"}:
            violations.append("policy_design_warrant_berl_bundle_subject_mismatch")
            issues.append(
                WarrantReliabilityIssue(
                    code="policy_design_warrant_berl_bundle_subject_mismatch",
                    field="warrant_reliability_records.expected_explanation_subject",
                    message=(
                        "A caller-provided candidate subject conflicts with the selected "
                        "bundle; the assertion is not an authority source."
                    ),
                    evidence_ref=selected_ref or evidence_ref,
                )
            )
        normalized["threshold_decision"] = {
            **{
                key: value
                for key, value in candidate_decision.items()
                if key not in {"status", "violations"}
            },
            "status": "fail",
            "candidate_status": _decision_status(candidate_record),
            "violations": list(dict.fromkeys(violations)),
        }
        issues.append(
            WarrantReliabilityIssue(
                code="policy_design_warrant_berl_subject_context_not_established",
                field="warrant_reliability_records.subject_context_resolution",
                message=(
                    "A selected BERL bundle is candidate evidence until a typed claim/run "
                    "subject is independently resolved and joined."
                ),
                evidence_ref=selected_ref or evidence_ref,
            )
        )

    _required_reliability_record_issues(normalized, evidence_ref=evidence_ref, issues=issues)
    return {key: value for key, value in normalized.items() if value is not None}, tuple(issues)


def _candidate_summary_fields(candidate_record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: candidate_record[key]
        for key in (
            "explanation_bundle",
            "empirical_bounds",
            "local_infidelity_diagnostics",
        )
        if key in candidate_record
    }


def _decision_status(candidate_record: Mapping[str, Any]) -> str:
    decision = _as_mapping(candidate_record.get("threshold_decision")) or {}
    status = _first_text(decision.get("status"))
    return status or "not_evaluated"


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


_BUNDLE_REF_KEYS = (
    "explanation_bundle_ref",
    "berl_explanation_bundle_ref",
    "bundle_ref",
)
_EXPECTED_BUNDLE_SUBJECT_KEYS = frozenset({"prediction_id", "model_hash", "feature_schema_version"})


def _bundle_ref_display_value(row: Mapping[str, Any]) -> object | None:
    """Keep the exact selected ref representation visible in normalized output."""

    supplied = [(key, row[key]) for key in _BUNDLE_REF_KEYS if key in row]
    if len(supplied) != 1:
        return None
    value = supplied[0][1]
    if isinstance(value, str):
        return value
    model_dump = getattr(value, "model_dump_json", None)
    if callable(model_dump):
        try:
            return model_dump()
        except (TypeError, ValueError):
            return None
    return dict(value) if isinstance(value, Mapping) else value


_METHOD_IDENTITY_FIELDS = (
    "method_id",
    "requested_method_id",
    "effective_method_id",
    "fallback",
    "fallback_reason",
    "scope",
)


class _MethodIdentityProjection(TypedDict):
    method_id: str
    requested_method_id: str | None
    effective_method_id: str | None
    fallback: bool | None
    fallback_reason: str | None
    scope: Literal["local", "global", "local_bin", "diagnostic"] | None
    field_presence: dict[str, bool]


def _method_identity_projection(
    bundle: ExplanationBundle,
) -> list[_MethodIdentityProjection]:
    """Project every method identity from the typed selected-CAS bundle."""
    rows: list[_MethodIdentityProjection] = []
    for method in bundle.methods:
        present = method.model_fields_set
        rows.append(
            {
                "method_id": method.method_id,
                "requested_method_id": (
                    method.requested_method_id if "requested_method_id" in present else None
                ),
                "effective_method_id": (
                    method.effective_method_id if "effective_method_id" in present else None
                ),
                "fallback": method.fallback if "fallback" in present else None,
                "fallback_reason": (
                    method.fallback_reason if "fallback_reason" in present else None
                ),
                "scope": method.scope if "scope" in present else None,
                "field_presence": {field: field in present for field in _METHOD_IDENTITY_FIELDS},
            }
        )
    return rows


def _load_selected_bundle_payload(
    row: Mapping[str, Any],
    *,
    artifact_store: ArtifactStore | None,
) -> tuple[dict[str, Any] | None, str | None, str | None, list[_MethodIdentityProjection] | None]:
    """Resolve the exact persisted BERL ref; embedded copies never rescue a supplied ref."""

    supplied = [(key, row[key]) for key in _BUNDLE_REF_KEYS if key in row]
    if not supplied:
        return None, None, "policy_design_warrant_berl_bundle_ref_missing", None
    if len(supplied) != 1:
        return None, None, "policy_design_warrant_berl_bundle_ref_invalid", None

    from polisyos.ir import ExplanationBundleRef

    raw_ref = supplied[0][1]
    try:
        if isinstance(raw_ref, str):
            selected_ref = ExplanationBundleRef.model_validate_json(raw_ref)
        elif isinstance(raw_ref, Mapping):
            selected_ref = ExplanationBundleRef.model_validate(raw_ref)
        else:
            model_dump = getattr(raw_ref, "model_dump", None)
            if not callable(model_dump):
                raise TypeError("typed BERL bundle reference required")
            selected_ref = ExplanationBundleRef.model_validate(model_dump(mode="python"))
    except (TypeError, ValueError):
        return None, None, "policy_design_warrant_berl_bundle_ref_invalid", None

    selected_ref_text = selected_ref.model_dump_json()
    if artifact_store is None:
        return (
            None,
            selected_ref_text,
            "policy_design_warrant_berl_bundle_store_unavailable",
            None,
        )
    try:
        from polisyos.berl import (
            ExplanationBundleStoreReadError,
            load_explanation_bundle,
        )
    except (AttributeError, ImportError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return (
            None,
            selected_ref_text,
            "policy_design_warrant_berl_bundle_store_read_unavailable",
            None,
        )
    try:
        bundle = load_explanation_bundle(artifact_store, selected_ref)
    except ExplanationBundleStoreReadError:
        return (
            None,
            selected_ref_text,
            "policy_design_warrant_berl_bundle_store_read_unavailable",
            None,
        )
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return None, selected_ref_text, "policy_design_warrant_berl_bundle_unresolved", None
    return (
        bundle.model_dump(mode="json"),
        selected_ref_text,
        None,
        _method_identity_projection(bundle),
    )


def _candidate_subject_context_resolution(
    row: Mapping[str, Any],
    warrant: Mapping[str, Any],
    *,
    claim_id: str | None,
    record_id: str | None,
    selected_ref: str | None,
    bundle_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Describe candidate joins while refusing caller claims as subject authority."""

    actual_subject = _bundle_subject_values(bundle_payload)
    record_assertion_status, record_assertion = _subject_assertion(row)
    warrant_assertion_status, warrant_assertion = _subject_assertion(warrant)
    assertions = [
        assertion for assertion in (record_assertion, warrant_assertion) if assertion is not None
    ]
    assertion_conflict = len(assertions) > 1 and any(
        assertion != assertions[0] for assertion in assertions[1:]
    )
    assertion_mismatch = any(assertion != actual_subject for assertion in assertions)
    if assertion_conflict:
        assertion_status = "conflicting"
    elif assertion_mismatch:
        assertion_status = "mismatch"
    elif assertions:
        assertion_status = "matched"
    elif "malformed" in {record_assertion_status, warrant_assertion_status}:
        assertion_status = "malformed"
    else:
        assertion_status = "absent"

    expected_warrant_id = _first_text(
        warrant.get("warrant_id"), warrant.get("record_id"), warrant.get("id")
    )
    row_warrant_id = _first_text(row.get("warrant_id"))
    record_claim_id = _first_text(row.get("claim_id"), row.get("major_claim_id"))
    warrant_claim_id = _first_text(warrant.get("claim_id"), warrant.get("major_claim_id"))
    refs = set(warrant_berl_reliability_refs(warrant))
    record_ref_linked = record_id is not None and record_id in refs

    claim_mismatch = any(
        value is not None and claim_id is not None and value != claim_id
        for value in (record_claim_id, warrant_claim_id)
    ) or (
        record_claim_id is not None
        and warrant_claim_id is not None
        and record_claim_id != warrant_claim_id
    )
    warrant_mismatch = (
        row_warrant_id is not None
        and expected_warrant_id is not None
        and row_warrant_id != expected_warrant_id
    )
    if claim_mismatch or warrant_mismatch:
        linkage_status = "mismatch"
    elif (
        claim_id is not None
        and record_claim_id == claim_id
        and record_ref_linked
        and (warrant_claim_id is None or warrant_claim_id == claim_id)
    ):
        linkage_status = "matched"
    else:
        linkage_status = "not_established"

    return {
        "status": (
            "contested"
            if assertion_status in {"mismatch", "conflicting"} or linkage_status == "mismatch"
            else "not_established"
        ),
        "predicate_class": "not_established",
        "source": "no_typed_claim_run_subject_resolver",
        "selected_ref": selected_ref,
        "selected_bundle_subject": actual_subject,
        "candidate_assertions": {
            "status": assertion_status,
            "record_status": record_assertion_status,
            "record_value": record_assertion,
            "warrant_status": warrant_assertion_status,
            "warrant_value": warrant_assertion,
        },
        "claim_warrant_linkage": {
            "status": linkage_status,
            "expected_claim_id": claim_id,
            "record_claim_id": record_claim_id,
            "warrant_claim_id": warrant_claim_id,
            "record_id": record_id,
            "record_id_in_warrant_refs": record_ref_linked,
            "row_warrant_id": row_warrant_id,
            "warrant_id": expected_warrant_id,
        },
        "gate_predicate": {
            "selected_cas_content": "recomputed",
            "identifier_joins": "recomputed",
            "identifier_authority": "consumer_asserted",
            "claim_run_model_prediction_relation": "not_established",
        },
    }


def _subject_assertion(
    source: Mapping[str, Any],
) -> tuple[str, dict[str, str] | None]:
    value = source.get("expected_explanation_subject")
    if value is None:
        return "absent", None
    if not isinstance(value, Mapping) or set(value) != _EXPECTED_BUNDLE_SUBJECT_KEYS:
        return "malformed", None
    subject: dict[str, str] = {}
    for key in _EXPECTED_BUNDLE_SUBJECT_KEYS:
        field_value = value.get(key)
        if not isinstance(field_value, str) or not field_value.strip():
            return "malformed", None
        subject[key] = field_value
    return "supplied", subject


def _bundle_subject_values(payload: Mapping[str, Any]) -> dict[str, Any]:
    model = _as_mapping(payload.get("model")) or {}
    prediction = _as_mapping(payload.get("prediction")) or {}
    feature_context = _as_mapping(payload.get("feature_context")) or {}
    return {
        "prediction_id": prediction.get("prediction_id"),
        "model_hash": model.get("model_hash"),
        "feature_schema_version": feature_context.get("feature_schema_version"),
    }


def _validate_bundle_record(
    bundle_payload: Mapping[str, Any],
    *,
    thresholds: dict[str, Any],
    evidence_ref: str | None,
) -> tuple[dict[str, Any], tuple[WarrantReliabilityIssue, ...]]:
    try:
        from polisyos.berl import (
            ValidationThresholds,
            validate_persisted_explanation_bundle_payload,
        )

        active_thresholds = _validation_thresholds(ValidationThresholds, thresholds)
        bundle, validation = validate_persisted_explanation_bundle_payload(
            bundle_payload,
            thresholds=active_thresholds,
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

    if bundle is None:
        violations = validation.violations or ("explanation_bundle_invalid",)
        return (
            {
                "threshold_decision": {
                    "status": "fail",
                    "display_policy": validation.display_policy,
                    "violations": list(violations),
                    "warnings": list(validation.warnings),
                }
            },
            (
                WarrantReliabilityIssue(
                    code="policy_design_warrant_berl_bundle_invalid",
                    field="warrant_reliability_records.explanation_bundle",
                    message="BERL explanation bundle could not be validated: "
                    + ", ".join(violations),
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
    thresholds_cls: type[ValidationThresholds],
    thresholds: Mapping[str, Any],
) -> ValidationThresholds | None:
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

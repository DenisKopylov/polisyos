"""Verification helpers for cross-backend numerical equivalence certificates."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from polisyos.foundry.methods.backends.runtime_fingerprint import (
    compose_observed_tolerance_budgets,
    meet_determinism_tiers,
    validate_observed_tolerance_budget_metrics,
)
from polisyos.foundry.methods.backends.protocol import MethodResult
from polisyos.foundry.methods.equivalence.canonicalize import (
    canonicalize_method_result,
)
from polisyos.foundry.methods.equivalence.compare import compare_field_values
from polisyos.foundry.methods.equivalence.protocol import (
    CrossBackendEquivalenceCertificate,
    EQUIVALENCE_COMPARATOR_VERSION,
    EquivalenceRuntimeEnvelope,
    EquivalenceVerificationReport,
    EquivalenceVerdict,
    FieldComparison,
)
from polisyos.foundry.methods.equivalence.store import (
    verify_persisted_equivalence_certificate,
)


def runtime_envelope_from_results(
    *,
    source_result: MethodResult,
    target_result: MethodResult,
) -> EquivalenceRuntimeEnvelope:
    """Build an observed runtime envelope from a concrete result pair."""

    source_runtime = _runtime_fingerprint_payload(source_result)
    target_runtime = _runtime_fingerprint_payload(target_result)
    return EquivalenceRuntimeEnvelope(
        source_backend=source_result.reproducibility.backend,
        target_backend=target_result.reproducibility.backend,
        source_runtime_fingerprint=_runtime_fingerprint_value(source_result),
        target_runtime_fingerprint=_runtime_fingerprint_value(target_result),
        source_execution_device=_optional_string(
            source_runtime.get("execution_device") if source_runtime else None
        ),
        target_execution_device=_optional_string(
            target_runtime.get("execution_device") if target_runtime else None
        ),
        source_determinism_tier=source_result.reproducibility.determinism_tier,
        target_determinism_tier=target_result.reproducibility.determinism_tier,
        source_library_versions=dict(source_result.reproducibility.library_versions),
        target_library_versions=dict(target_result.reproducibility.library_versions),
        source_route_key=_mapping_payload(
            source_runtime.get("route_key") if source_runtime else None
        ),
        target_route_key=_mapping_payload(
            target_runtime.get("route_key") if target_runtime else None
        ),
    )


def verify_backend_equivalence(
    *,
    result: MethodResult,
    counterpart: MethodResult,
    certificate: CrossBackendEquivalenceCertificate,
    method_fqn: str | None = None,
    now: datetime | None = None,
    certificate_ref: Any | None = None,
    artifact_store: Any | None = None,
    signature_verifier: Any | None = None,
    strict_identity: bool | None = None,
    require_signed_certificate: bool = False,
    expected_comparator_version: str | None = EQUIVALENCE_COMPARATOR_VERSION,
) -> EquivalenceVerificationReport:
    """Apply one certificate to a pair of backend results."""

    notes = _applicability_issues(
        result=result,
        counterpart=counterpart,
        certificate=certificate,
        method_fqn=method_fqn,
        now=now,
        certificate_ref=certificate_ref,
        artifact_store=artifact_store,
        signature_verifier=signature_verifier,
        strict_identity=strict_identity,
        require_signed_certificate=require_signed_certificate,
        expected_comparator_version=expected_comparator_version,
    )
    if notes:
        return EquivalenceVerificationReport(
            certificate_id=certificate.certificate_id,
            verdict=EquivalenceVerdict.UNKNOWN,
            applicable=False,
            notes=tuple(notes),
        )

    left_tree = canonicalize_method_result(result)
    right_tree = canonicalize_method_result(counterpart)
    field_reports: list[FieldComparison] = []
    for spec in certificate.field_specs:
        if spec.path not in left_tree or spec.path not in right_tree:
            field_reports.append(
                FieldComparison(
                    path=spec.path,
                    comparator=spec.comparator,
                    requirement=spec.requirement,
                    strict_ok=False,
                    relaxed_ok=False,
                    missing=True,
                    message="field path missing from one or both results",
                )
            )
            continue
        field_reports.append(
            compare_field_values(
                spec=spec,
                lhs=left_tree[spec.path],
                rhs=right_tree[spec.path],
            )
        )
    verdict = _aggregate_verdict(tuple(field_reports))
    runtime_budget_validation = _validate_runtime_budget_from_field_reports(
        result=result,
        counterpart=counterpart,
        field_reports=tuple(field_reports),
    )
    return EquivalenceVerificationReport(
        certificate_id=certificate.certificate_id,
        verdict=verdict,
        applicable=True,
        field_reports=tuple(field_reports),
        runtime_budget_validation=runtime_budget_validation,
    )


def assess_certificate_applicability(
    *,
    result: MethodResult,
    certificate: CrossBackendEquivalenceCertificate,
    target_backend: Any | None = None,
    method_fqn: str | None = None,
    now: datetime | None = None,
    certificate_ref: Any | None = None,
    artifact_store: Any | None = None,
    signature_verifier: Any | None = None,
    strict_identity: bool | None = None,
    require_signed_certificate: bool = False,
    expected_comparator_version: str | None = EQUIVALENCE_COMPARATOR_VERSION,
) -> EquivalenceVerificationReport:
    """Validate whether one certificate is applicable to a single executed result."""

    notes = _single_result_applicability_issues(
        result=result,
        certificate=certificate,
        target_backend=target_backend,
        method_fqn=method_fqn,
        now=now,
        certificate_ref=certificate_ref,
        artifact_store=artifact_store,
        signature_verifier=signature_verifier,
        strict_identity=strict_identity,
        require_signed_certificate=require_signed_certificate,
        expected_comparator_version=expected_comparator_version,
    )
    if notes:
        return EquivalenceVerificationReport(
            certificate_id=certificate.certificate_id,
            verdict=EquivalenceVerdict.UNKNOWN,
            applicable=False,
            notes=tuple(notes),
        )
    return EquivalenceVerificationReport(
        certificate_id=certificate.certificate_id,
        verdict=certificate.global_verdict or EquivalenceVerdict.PASS_STRICT,
        applicable=True,
    )


def attach_equivalence_ref(
    result: MethodResult,
    certificate_uri: str,
    verdict: EquivalenceVerdict,
    *,
    report: EquivalenceVerificationReport | None = None,
    attestation_ref: str | None = None,
) -> MethodResult:
    """Attach a certificate reference plus a compact verification summary."""

    summary: dict[str, Any] = {
        "certificate_ref": str(certificate_uri),
        "verdict": verdict.value,
    }
    if report is not None:
        summary["certificate_id"] = report.certificate_id
        summary["applicable"] = report.applicable
        summary["failed_required_paths"] = list(report.failed_required_paths)
        if report.runtime_budget_validation:
            summary["runtime_budget_validation"] = dict(report.runtime_budget_validation)
        if report.notes:
            summary["notes"] = list(report.notes)
    if attestation_ref is not None:
        summary["attestation_ref"] = str(attestation_ref)

    return replace(
        result,
        cross_backend_equivalence_ref=str(certificate_uri),
        artifacts={
            **dict(result.artifacts),
            "cross_backend_equivalence": summary,
        },
    )


def _aggregate_verdict(
    field_reports: tuple[FieldComparison, ...]
) -> EquivalenceVerdict:
    required = [report for report in field_reports if report.requirement.affects_verdict]
    if any(not report.relaxed_ok for report in required):
        return EquivalenceVerdict.FAIL
    if any(not report.strict_ok for report in required):
        return EquivalenceVerdict.PASS_RELAXED
    return EquivalenceVerdict.PASS_STRICT


def _validate_runtime_budget_from_field_reports(
    *,
    result: MethodResult,
    counterpart: MethodResult,
    field_reports: tuple[FieldComparison, ...],
) -> dict[str, Any]:
    numeric_reports = tuple(
        report
        for report in field_reports
        if not report.missing
        and report.max_abs_error is not None
        and report.max_rel_error is not None
    )
    if not numeric_reports:
        return {}

    pair_budget = compose_observed_tolerance_budgets(
        [
            dict(result.reproducibility.observed_tolerance_budget or {}),
            dict(counterpart.reproducibility.observed_tolerance_budget or {}),
        ],
        determinism_tiers=[
            result.reproducibility.determinism_tier,
            counterpart.reproducibility.determinism_tier,
        ],
        composition_kind="concat",
    )
    metrics = {
        "max_abs_error": max(float(report.max_abs_error) for report in numeric_reports),
        "max_rel_error": max(float(report.max_rel_error) for report in numeric_reports),
    }
    current_tier = meet_determinism_tiers(
        [
            result.reproducibility.determinism_tier,
            counterpart.reproducibility.determinism_tier,
        ]
    )
    return validate_observed_tolerance_budget_metrics(
        metrics=metrics,
        budget=pair_budget,
        current_tier=current_tier,
    )


def _applicability_issues(
    *,
    result: MethodResult,
    counterpart: MethodResult,
    certificate: CrossBackendEquivalenceCertificate,
    method_fqn: str | None,
    now: datetime | None,
    certificate_ref: Any | None,
    artifact_store: Any | None,
    signature_verifier: Any | None,
    strict_identity: bool | None,
    require_signed_certificate: bool,
    expected_comparator_version: str | None,
) -> tuple[str, ...]:
    issues: list[str] = []
    observed = runtime_envelope_from_results(
        source_result=result,
        target_result=counterpart,
    )
    expected = certificate.runtime_envelope

    if (
        expected_comparator_version is not None
        and certificate.comparator_version != expected_comparator_version
    ):
        issues.append(
            "comparator version mismatch: "
            f"expected {expected_comparator_version}, got {certificate.comparator_version}"
        )
    if method_fqn is not None and method_fqn != certificate.method_fqn:
        issues.append(
            f"method_fqn mismatch: expected {certificate.method_fqn}, got {method_fqn}"
        )
    if observed.source_backend != expected.source_backend:
        issues.append(
            "source backend mismatch: "
            f"expected {expected.source_backend.value}, got {observed.source_backend.value}"
        )
    if observed.target_backend != expected.target_backend:
        issues.append(
            "target backend mismatch: "
            f"expected {expected.target_backend.value}, got {observed.target_backend.value}"
        )
    if (
        expected.source_runtime_fingerprint
        and observed.source_runtime_fingerprint != expected.source_runtime_fingerprint
    ):
        issues.append("source runtime fingerprint mismatch")
    if (
        expected.target_runtime_fingerprint
        and observed.target_runtime_fingerprint != expected.target_runtime_fingerprint
    ):
        issues.append("target runtime fingerprint mismatch")
    if (
        expected.source_execution_device is not None
        and observed.source_execution_device != expected.source_execution_device
    ):
        issues.append("source execution device mismatch")
    if (
        expected.target_execution_device is not None
        and observed.target_execution_device != expected.target_execution_device
    ):
        issues.append("target execution device mismatch")
    if (
        expected.source_determinism_tier is not None
        and observed.source_determinism_tier != expected.source_determinism_tier
    ):
        issues.append("source determinism tier mismatch")
    if (
        expected.target_determinism_tier is not None
        and observed.target_determinism_tier != expected.target_determinism_tier
    ):
        issues.append("target determinism tier mismatch")
    issues.extend(
        _library_version_mismatches(
            side="source",
            expected_versions=expected.source_library_versions,
            observed_versions=observed.source_library_versions,
        )
    )
    issues.extend(
        _library_version_mismatches(
            side="target",
            expected_versions=expected.target_library_versions,
            observed_versions=observed.target_library_versions,
        )
    )
    issues.extend(
        _mapping_mismatches(
            side="source route_key",
            expected_mapping=expected.source_route_key,
            observed_mapping=observed.source_route_key,
        )
    )
    issues.extend(
        _mapping_mismatches(
            side="target route_key",
            expected_mapping=expected.target_route_key,
            observed_mapping=observed.target_route_key,
        )
    )

    check_time = now or datetime.now(UTC)
    expires_at = _parse_timestamp(certificate.expires_at)
    if expires_at is not None and expires_at < check_time.astimezone(UTC):
        issues.append("certificate expired")
    if require_signed_certificate:
        if artifact_store is None or certificate_ref is None or signature_verifier is None:
            issues.append("certificate signature could not be verified")
        else:
            verification = verify_persisted_equivalence_certificate(
                store=artifact_store,
                ref=certificate_ref,
                verifier=signature_verifier,
                strict_identity=strict_identity,
            )
            if not verification.ok:
                issues.append(
                    "certificate signature verification failed: "
                    f"{verification.status.value}"
                )
    return tuple(issues)


def _single_result_applicability_issues(
    *,
    result: MethodResult,
    certificate: CrossBackendEquivalenceCertificate,
    target_backend: Any | None,
    method_fqn: str | None,
    now: datetime | None,
    certificate_ref: Any | None,
    artifact_store: Any | None,
    signature_verifier: Any | None,
    strict_identity: bool | None,
    require_signed_certificate: bool,
    expected_comparator_version: str | None,
) -> tuple[str, ...]:
    issues: list[str] = []
    observed = runtime_envelope_from_results(
        source_result=result,
        target_result=result,
    )
    expected = certificate.runtime_envelope

    if (
        expected_comparator_version is not None
        and certificate.comparator_version != expected_comparator_version
    ):
        issues.append(
            "comparator version mismatch: "
            f"expected {expected_comparator_version}, got {certificate.comparator_version}"
        )
    if method_fqn is not None and method_fqn != certificate.method_fqn:
        issues.append(
            f"method_fqn mismatch: expected {certificate.method_fqn}, got {method_fqn}"
        )
    if observed.source_backend != expected.source_backend:
        issues.append(
            "source backend mismatch: "
            f"expected {expected.source_backend.value}, got {observed.source_backend.value}"
        )
    if target_backend is not None and target_backend != expected.target_backend:
        issues.append(
            "target backend mismatch: "
            f"expected {expected.target_backend.value}, got {target_backend.value}"
        )
    if (
        expected.source_runtime_fingerprint
        and observed.source_runtime_fingerprint != expected.source_runtime_fingerprint
    ):
        issues.append("source runtime fingerprint mismatch")
    if (
        expected.source_execution_device is not None
        and observed.source_execution_device != expected.source_execution_device
    ):
        issues.append("source execution device mismatch")
    if (
        expected.source_determinism_tier is not None
        and observed.source_determinism_tier != expected.source_determinism_tier
    ):
        issues.append("source determinism tier mismatch")
    issues.extend(
        _library_version_mismatches(
            side="source",
            expected_versions=expected.source_library_versions,
            observed_versions=observed.source_library_versions,
        )
    )
    issues.extend(
        _mapping_mismatches(
            side="source route_key",
            expected_mapping=expected.source_route_key,
            observed_mapping=observed.source_route_key,
        )
    )

    check_time = now or datetime.now(UTC)
    expires_at = _parse_timestamp(certificate.expires_at)
    if expires_at is not None and expires_at < check_time.astimezone(UTC):
        issues.append("certificate expired")
    if require_signed_certificate:
        if artifact_store is None or certificate_ref is None or signature_verifier is None:
            issues.append("certificate signature could not be verified")
        else:
            verification = verify_persisted_equivalence_certificate(
                store=artifact_store,
                ref=certificate_ref,
                verifier=signature_verifier,
                strict_identity=strict_identity,
            )
            if not verification.ok:
                issues.append(
                    "certificate signature verification failed: "
                    f"{verification.status.value}"
                )
    return tuple(issues)


def _library_version_mismatches(
    *,
    side: str,
    expected_versions: Mapping[str, str],
    observed_versions: Mapping[str, str],
) -> tuple[str, ...]:
    issues: list[str] = []
    for package, expected_version in expected_versions.items():
        observed_version = observed_versions.get(package)
        if observed_version != expected_version:
            issues.append(
                f"{side} library version mismatch for {package}: "
                f"expected {expected_version}, got {observed_version}"
            )
    return tuple(issues)


def _mapping_mismatches(
    *,
    side: str,
    expected_mapping: Mapping[str, Any],
    observed_mapping: Mapping[str, Any],
) -> tuple[str, ...]:
    issues: list[str] = []
    for key, expected_value in expected_mapping.items():
        observed_value = observed_mapping.get(key)
        if observed_value != expected_value:
            issues.append(
                f"{side} mismatch for {key}: expected {expected_value}, got {observed_value}"
            )
    return tuple(issues)


def _runtime_fingerprint_payload(result: MethodResult) -> Mapping[str, Any] | None:
    payload = result.artifacts.get("backend_runtime_fingerprint")
    return payload if isinstance(payload, Mapping) else None


def _runtime_fingerprint_value(result: MethodResult) -> str | None:
    payload = _runtime_fingerprint_payload(result)
    if payload is not None and payload.get("fingerprint"):
        return str(payload["fingerprint"])
    return result.reproducibility.fingerprint


def _mapping_payload(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


__all__ = [
    "assess_certificate_applicability",
    "attach_equivalence_ref",
    "runtime_envelope_from_results",
    "verify_backend_equivalence",
]

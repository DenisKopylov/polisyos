"""Exact implementation-conformance checks for typed IC semantics."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from polisyos.core.contracts.ic_verification import (
    ICImplementationConformanceReport,
    ICImplementationConformanceReportRef,
    ICImplementationConformanceRequest,
    ICImplementationConformanceResult,
    IncentiveCompatibilityCertificate,
)
from polisyos.ir.artifacts import ArtifactStore, get_json_artifact, put_json_artifact
from polisyos.ir.governance.mechanism_semantics import (
    MechanismSemanticFragment,
    MechanismSemanticsSpec,
)

_CONFORMANCE_SCHEMA_NAME = (
    "polisyos.core.contracts.ic_verification.ICImplementationConformanceReport"
)


def _load_semantics(
    store: ArtifactStore,
    artifact_ref: Any,
) -> tuple[MechanismSemanticsSpec, str]:
    payload = get_json_artifact(store, artifact_ref.artifact_id)
    return MechanismSemanticsSpec.model_validate(payload), str(artifact_ref.artifact_id)


def _route_backend(
    authored: MechanismSemanticsSpec,
    request: ICImplementationConformanceRequest,
) -> str:
    if request.backend_hint != "auto":
        return request.backend_hint
    if authored.fragment is MechanismSemanticFragment.ENVELOPE_1D:
        return "envelope_1d"
    if authored.fragment is MechanismSemanticFragment.CYCMON_GRID:
        return "cycmon_lp"
    return "finite_exact"


def _conformance_report(
    *,
    backend: str,
    verdict: str,
    authored_digest: str,
    implementation_digest: str,
    notes: tuple[str, ...] = (),
    mismatch_witness: dict[str, Any] | None = None,
) -> ICImplementationConformanceReport:
    return ICImplementationConformanceReport(
        backend=backend,
        verdict=verdict,
        authored_digest=authored_digest,
        implementation_digest=implementation_digest,
        notes=notes,
        mismatch_witness=mismatch_witness or {},
    )


def _compare_finite(
    authored: MechanismSemanticsSpec,
    implementation: MechanismSemanticsSpec,
    *,
    authored_digest: str,
    implementation_digest: str,
) -> ICImplementationConformanceReport:
    if implementation.fragment is not MechanismSemanticFragment.FINITE_DIRECT:
        return _conformance_report(
            backend="finite_exact",
            verdict="mismatch",
            authored_digest=authored_digest,
            implementation_digest=implementation_digest,
            notes=("implementation fragment does not match authored finite_direct semantics",),
            mismatch_witness={
                "kind": "fragment_mismatch",
                "authored": authored.fragment.value,
                "implementation": implementation.fragment.value,
            },
        )
    authored_outcomes = {
        outcome.outcome_id: dict(outcome.allocation_by_player)
        for outcome in authored.finite_outcomes
    }
    implementation_outcomes = {
        outcome.outcome_id: dict(outcome.allocation_by_player)
        for outcome in implementation.finite_outcomes
    }
    if authored_outcomes != implementation_outcomes:
        return _conformance_report(
            backend="finite_exact",
            verdict="mismatch",
            authored_digest=authored_digest,
            implementation_digest=implementation_digest,
            notes=(
                "finite outcome codomain differs between authored and implementation semantics",
            ),
            mismatch_witness={
                "kind": "outcome_mismatch",
                "authored": authored_outcomes,
                "implementation": implementation_outcomes,
            },
        )
    authored_rule = {
        tuple(sorted(entry.report_profile.items())): {
            "outcome_id": entry.outcome_id,
            "payments_by_player": dict(entry.payments_by_player),
        }
        for entry in authored.allocation_rule
    }
    implementation_rule = {
        tuple(sorted(entry.report_profile.items())): {
            "outcome_id": entry.outcome_id,
            "payments_by_player": dict(entry.payments_by_player),
        }
        for entry in implementation.allocation_rule
    }
    if authored_rule != implementation_rule:
        for profile_key, authored_entry in authored_rule.items():
            if implementation_rule.get(profile_key) != authored_entry:
                return _conformance_report(
                    backend="finite_exact",
                    verdict="mismatch",
                    authored_digest=authored_digest,
                    implementation_digest=implementation_digest,
                    notes=(
                        "finite allocation or payment semantics differ on at least one report profile",
                    ),
                    mismatch_witness={
                        "kind": "allocation_mismatch",
                        "report_profile": dict(profile_key),
                        "authored": authored_entry,
                        "implementation": implementation_rule.get(profile_key),
                    },
                )
        extra_profile = next(iter(set(implementation_rule) - set(authored_rule)))
        return _conformance_report(
            backend="finite_exact",
            verdict="mismatch",
            authored_digest=authored_digest,
            implementation_digest=implementation_digest,
            notes=("implementation semantics contain an unexpected report profile",),
            mismatch_witness={
                "kind": "allocation_mismatch",
                "report_profile": dict(extra_profile),
                "authored": None,
                "implementation": implementation_rule[extra_profile],
            },
        )
    return _conformance_report(
        backend="finite_exact",
        verdict="conformant",
        authored_digest=authored_digest,
        implementation_digest=implementation_digest,
    )


def _compare_envelope(
    authored: MechanismSemanticsSpec,
    implementation: MechanismSemanticsSpec,
    *,
    authored_digest: str,
    implementation_digest: str,
) -> ICImplementationConformanceReport:
    if (
        implementation.fragment is not MechanismSemanticFragment.ENVELOPE_1D
        or authored.envelope_1d is None
        or implementation.envelope_1d is None
    ):
        return _conformance_report(
            backend="envelope_1d",
            verdict="mismatch",
            authored_digest=authored_digest,
            implementation_digest=implementation_digest,
            notes=("implementation fragment does not match authored envelope_1d semantics",),
            mismatch_witness={
                "kind": "fragment_mismatch",
                "authored": authored.fragment.value,
                "implementation": implementation.fragment.value,
            },
        )
    authored_points = {point.type_label: point for point in authored.envelope_1d.points}
    implementation_points = {point.type_label: point for point in implementation.envelope_1d.points}
    if set(authored_points) != set(implementation_points):
        return _conformance_report(
            backend="envelope_1d",
            verdict="mismatch",
            authored_digest=authored_digest,
            implementation_digest=implementation_digest,
            notes=("implementation envelope grid does not match authored type labels",),
            mismatch_witness={
                "kind": "type_grid_mismatch",
                "authored": sorted(authored_points),
                "implementation": sorted(implementation_points),
            },
        )
    notes: list[str] = []
    for label, authored_point in authored_points.items():
        implementation_point = implementation_points[label]
        authored_payload = {
            "type_value": authored_point.type_value,
            "allocation": authored_point.allocation,
        }
        implementation_payload = {
            "type_value": implementation_point.type_value,
            "allocation": implementation_point.allocation,
        }
        if authored_payload != implementation_payload:
            return _conformance_report(
                backend="envelope_1d",
                verdict="mismatch",
                authored_digest=authored_digest,
                implementation_digest=implementation_digest,
                notes=("implementation envelope semantics disagree on a type point",),
                mismatch_witness={
                    "kind": "allocation_mismatch",
                    "type_label": label,
                    "authored": authored_payload,
                    "implementation": implementation_payload,
                },
            )
        if authored_point.payment is not None:
            if implementation_point.payment != authored_point.payment:
                return _conformance_report(
                    backend="envelope_1d",
                    verdict="mismatch",
                    authored_digest=authored_digest,
                    implementation_digest=implementation_digest,
                    notes=(
                        "implementation payment rule disagrees with authored envelope semantics",
                    ),
                    mismatch_witness={
                        "kind": "payment_mismatch",
                        "type_label": label,
                        "authored": authored_point.payment,
                        "implementation": implementation_point.payment,
                    },
                )
        else:
            notes.append("payment_rule_not_compared")
    return _conformance_report(
        backend="envelope_1d",
        verdict="conformant",
        authored_digest=authored_digest,
        implementation_digest=implementation_digest,
        notes=tuple(sorted(set(notes))),
    )


def _compare_cycmon(
    authored: MechanismSemanticsSpec,
    implementation: MechanismSemanticsSpec,
    *,
    authored_digest: str,
    implementation_digest: str,
) -> ICImplementationConformanceReport:
    if (
        implementation.fragment is not MechanismSemanticFragment.CYCMON_GRID
        or authored.cycmon_grid is None
        or implementation.cycmon_grid is None
    ):
        return _conformance_report(
            backend="cycmon_lp",
            verdict="mismatch",
            authored_digest=authored_digest,
            implementation_digest=implementation_digest,
            notes=("implementation fragment does not match authored cycmon_grid semantics",),
            mismatch_witness={
                "kind": "fragment_mismatch",
                "authored": authored.fragment.value,
                "implementation": implementation.fragment.value,
            },
        )
    authored_types = {point.type_label: point for point in authored.cycmon_grid.type_points}
    implementation_types = {
        point.type_label: point for point in implementation.cycmon_grid.type_points
    }
    authored_alloc = {point.type_label: point for point in authored.cycmon_grid.allocation_points}
    implementation_alloc = {
        point.type_label: point for point in implementation.cycmon_grid.allocation_points
    }
    if set(authored_types) != set(implementation_types):
        return _conformance_report(
            backend="cycmon_lp",
            verdict="mismatch",
            authored_digest=authored_digest,
            implementation_digest=implementation_digest,
            notes=("implementation cycmon grid does not match authored type labels",),
            mismatch_witness={
                "kind": "type_grid_mismatch",
                "authored": sorted(authored_types),
                "implementation": sorted(implementation_types),
            },
        )
    notes: list[str] = []
    for label in authored_types:
        if authored_types[label].coords != implementation_types[label].coords:
            return _conformance_report(
                backend="cycmon_lp",
                verdict="mismatch",
                authored_digest=authored_digest,
                implementation_digest=implementation_digest,
                notes=("implementation type coordinates disagree with authored cycmon semantics",),
                mismatch_witness={
                    "kind": "type_point_mismatch",
                    "type_label": label,
                    "authored": list(authored_types[label].coords),
                    "implementation": list(implementation_types[label].coords),
                },
            )
        if authored_alloc[label].allocation != implementation_alloc[label].allocation:
            return _conformance_report(
                backend="cycmon_lp",
                verdict="mismatch",
                authored_digest=authored_digest,
                implementation_digest=implementation_digest,
                notes=(
                    "implementation allocation vectors disagree with authored cycmon semantics",
                ),
                mismatch_witness={
                    "kind": "allocation_mismatch",
                    "type_label": label,
                    "authored": list(authored_alloc[label].allocation),
                    "implementation": list(implementation_alloc[label].allocation),
                },
            )
        if authored_alloc[label].payment is not None:
            if authored_alloc[label].payment != implementation_alloc[label].payment:
                return _conformance_report(
                    backend="cycmon_lp",
                    verdict="mismatch",
                    authored_digest=authored_digest,
                    implementation_digest=implementation_digest,
                    notes=("implementation payment rule disagrees with authored cycmon semantics",),
                    mismatch_witness={
                        "kind": "payment_mismatch",
                        "type_label": label,
                        "authored": authored_alloc[label].payment,
                        "implementation": implementation_alloc[label].payment,
                    },
                )
        else:
            notes.append("payment_rule_not_compared")
    return _conformance_report(
        backend="cycmon_lp",
        verdict="conformant",
        authored_digest=authored_digest,
        implementation_digest=implementation_digest,
        notes=tuple(sorted(set(notes))),
    )


def evaluate_ic_implementation_conformance(
    store: ArtifactStore,
    request: ICImplementationConformanceRequest,
) -> ICImplementationConformanceReport:
    authored, authored_digest = _load_semantics(store, request.authored_semantics_ref)
    implementation, implementation_digest = _load_semantics(
        store, request.implementation_semantics_ref
    )
    backend = _route_backend(authored, request)
    if backend == "finite_exact":
        return _compare_finite(
            authored,
            implementation,
            authored_digest=authored_digest,
            implementation_digest=implementation_digest,
        )
    if backend == "envelope_1d":
        return _compare_envelope(
            authored,
            implementation,
            authored_digest=authored_digest,
            implementation_digest=implementation_digest,
        )
    if backend == "cycmon_lp":
        return _compare_cycmon(
            authored,
            implementation,
            authored_digest=authored_digest,
            implementation_digest=implementation_digest,
        )
    return _conformance_report(
        backend=backend,
        verdict="unsupported_fragment",
        authored_digest=authored_digest,
        implementation_digest=implementation_digest,
        notes=(f"backend '{backend}' is not implemented in this workspace",),
    )


def persist_ic_conformance_report(
    store: ArtifactStore,
    report: ICImplementationConformanceReport,
) -> ICImplementationConformanceReportRef:
    ref = put_json_artifact(
        store,
        report.model_dump(mode="json"),
        kind="scientist.ic_conformance_report",
        schema_name=_CONFORMANCE_SCHEMA_NAME,
        schema_version=report.schema_version,
    )
    return ICImplementationConformanceReportRef.model_validate(ref)


def load_ic_conformance_report(
    store: ArtifactStore,
    ref: ICImplementationConformanceReportRef,
) -> ICImplementationConformanceReport:
    payload = get_json_artifact(store, ref.artifact_id)
    return ICImplementationConformanceReport.model_validate(payload)


def verify_ic_implementation_conformance(
    store: ArtifactStore,
    request: ICImplementationConformanceRequest,
) -> ICImplementationConformanceResult:
    try:
        report = evaluate_ic_implementation_conformance(store, request)
    except (KeyError, OSError, RuntimeError, TypeError, ValidationError, ValueError) as exc:
        report = ICImplementationConformanceReport(
            backend=request.backend_hint if request.backend_hint != "auto" else "auto",
            verdict="semantic_validation_failure",
            authored_digest=str(request.authored_semantics_ref.artifact_id),
            implementation_digest=str(request.implementation_semantics_ref.artifact_id),
            notes=(str(exc),),
        )
    report_ref = persist_ic_conformance_report(store, report)
    return ICImplementationConformanceResult(
        ok=report.verdict == "conformant",
        verdict=report.verdict,
        report_ref=report_ref,
        notes=list(report.notes),
    )


def promote_ic_certificate_to_runtime(
    certificate: IncentiveCompatibilityCertificate,
    conformance_ref: ICImplementationConformanceReportRef,
) -> IncentiveCompatibilityCertificate:
    """Relabel a semantic certificate as runtime-scoped after exact conformance."""

    return certificate.model_copy(
        update={
            "scope": "runtime",
            "implementation_conformance_ref": conformance_ref,
        }
    )


__all__ = [
    "evaluate_ic_implementation_conformance",
    "load_ic_conformance_report",
    "persist_ic_conformance_report",
    "promote_ic_certificate_to_runtime",
    "verify_ic_implementation_conformance",
]

"""Public backtesting abstraction suite module API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.analytics.abm_bridge import ABMAlignmentReport
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
)
from polisyos.scientist.methods.backtesting.adversarial import (
    ABSTRACTION_LEAKAGE_SUITE_ID,
    ChallengeCase,
    ChallengeSuiteResult,
    build_challenge_case_result,
    build_challenge_suite_result,
)
from polisyos.scientist.methods.doe.stress_report import VulnerabilityType

_MACRO_CERTIFICATE_TYPES = frozenset(
    (
        AbstractionPreservationType.EXACT,
        AbstractionPreservationType.APPROXIMATE,
        AbstractionPreservationType.POLICY_VALUE_ONLY,
    )
)


def run_abstraction_challenge_suite(
    *,
    candidate_ref: ArtifactRef,
    loop_id: str,
    run_id: str,
    params: Mapping[str, Any],
    strategic_summary: Mapping[str, Any] | None,
    abstraction_certificate: AbstractionCertificate | None,
    abstraction_map_ref: ArtifactRef | None,
    abm_alignment_report: ABMAlignmentReport | None,
) -> tuple[ChallengeSuiteResult | None, tuple[str, ...]]:
    """Run abstraction challenge suite."""
    del run_id

    preservation_type = _resolve_preservation_type(params, abstraction_certificate)
    heuristic_warning = _has_heuristic_warning(params, abm_alignment_report)
    macro_shortcut_used = _uses_macro_shortcut(strategic_summary)

    if (
        abstraction_certificate is None
        and abstraction_map_ref is None
        and preservation_type is None
        and not heuristic_warning
        and not macro_shortcut_used
    ):
        return None, ("phase_d4_abstraction_suite_skipped_no_inputs",)

    warnings: list[str] = []
    if abstraction_certificate is None and preservation_type is None:
        warnings.append("phase_d4_abstraction_suite_audit_only")

    macro_shortcut_has_certificate = _has_macro_safe_certificate(
        abstraction_certificate,
        abstraction_map_ref,
    )
    case_results = []
    if preservation_type is AbstractionPreservationType.EXACT:
        case_results.append(
            build_challenge_case_result(
                case=ChallengeCase(
                    case_id="exact_certificate_path",
                    challenge_family="abstraction_leakage",
                    expected_outcome="preservation_type_exact",
                    severity="high",
                ),
                passed=abstraction_certificate is not None and abstraction_map_ref is not None,
                summary=(
                    "Exact abstraction certificate and map are available for macro use."
                    if abstraction_certificate is not None and abstraction_map_ref is not None
                    else "Exact abstraction path is marked exact but required certificate/map evidence is missing."
                ),
            )
        )
    elif preservation_type is AbstractionPreservationType.INVALID:
        case_results.append(
            build_challenge_case_result(
                case=ChallengeCase(
                    case_id="invalid_certificate_blocks_macro",
                    challenge_family="abstraction_leakage",
                    expected_outcome="invalid_without_macro_shortcut",
                    severity="critical",
                ),
                passed=not macro_shortcut_used,
                summary=(
                    "Invalid abstraction certificate prevented macro shortcut usage."
                    if not macro_shortcut_used
                    else "Macro shortcut remained active despite an invalid abstraction certificate."
                ),
            )
        )
    elif (
        preservation_type
        in {
            AbstractionPreservationType.APPROXIMATE,
            AbstractionPreservationType.POLICY_VALUE_ONLY,
        }
        and abstraction_certificate is not None
    ):
        bounded_summary = (
            "Bounded abstraction certificate carries preserved queries and error bounds."
            if macro_shortcut_has_certificate
            else "Bounded abstraction path is missing map evidence, queries, or error bounds."
        )
        case_results.append(
            build_challenge_case_result(
                case=ChallengeCase(
                    case_id="bounded_certificate_path",
                    challenge_family="abstraction_leakage",
                    expected_outcome="bounded_certificate_with_query_scope",
                    severity="high",
                ),
                passed=macro_shortcut_has_certificate,
                summary=bounded_summary,
            )
        )
    else:
        case_results.append(
            build_challenge_case_result(
                case=ChallengeCase(
                    case_id="heuristic_path_requires_disclaimer",
                    challenge_family="abstraction_leakage",
                    expected_outcome="heuristic_disclaimer_without_certificate",
                    severity="high",
                ),
                passed=heuristic_warning and not macro_shortcut_used,
                summary=(
                    "Heuristic abstraction path published the expected disclaimer and avoided macro shortcuts."
                    if heuristic_warning and not macro_shortcut_used
                    else "Heuristic abstraction path is missing its disclaimer or leaked into macro shortcut usage."
                ),
            )
        )

    case_results.append(
        build_challenge_case_result(
            case=ChallengeCase(
                case_id="macro_shortcut_requires_supported_certificate",
                challenge_family="abstraction_leakage",
                expected_outcome="macro_only_with_supported_certificate",
                severity="critical",
            ),
            passed=(not macro_shortcut_used or macro_shortcut_has_certificate),
            summary=(
                "Macro shortcut usage is backed by a supported abstraction certificate."
                if not macro_shortcut_used or macro_shortcut_has_certificate
                else "Macro shortcut usage was observed without a supported abstraction certificate."
            ),
        )
    )

    result = build_challenge_suite_result(
        suite_id=ABSTRACTION_LEAKAGE_SUITE_ID,
        suite_version="1.0",
        candidate_ref=candidate_ref,
        loop_id=loop_id,
        challenge_family="abstraction_leakage",
        case_results=case_results,
        primary_failure_rate_name="abstraction_leakage_rate",
        vulnerability_type=VulnerabilityType.TEMPORAL,
        metadata={
            "suite_origin": "abstraction_certificate"
            if abstraction_certificate is not None
            else "heuristic_audit",
            "preservation_type": None if preservation_type is None else preservation_type.value,
        },
        warnings=warnings,
    )
    return result, tuple(warnings)


def _resolve_preservation_type(
    params: Mapping[str, Any],
    abstraction_certificate: AbstractionCertificate | None,
) -> AbstractionPreservationType | None:
    if abstraction_certificate is not None:
        return abstraction_certificate.preservation_type
    raw = str(params.get("abstraction_preservation_type") or "").strip().lower()
    if not raw:
        return None
    try:
        return AbstractionPreservationType(raw)
    except Exception:
        return None


def _has_heuristic_warning(
    params: Mapping[str, Any],
    abm_alignment_report: ABMAlignmentReport | None,
) -> bool:
    warning_sets = []
    if abm_alignment_report is not None:
        warning_sets.append(tuple(abm_alignment_report.warnings))
    raw = params.get("abm_alignment_warnings")
    if isinstance(raw, (list, tuple)):
        warning_sets.append(tuple(str(item) for item in raw))
    return any(
        "heuristic_aggregation_without_abstraction_certificate" in warnings
        for warnings in warning_sets
    )


def _uses_macro_shortcut(strategic_summary: Mapping[str, Any] | None) -> bool:
    if strategic_summary is None:
        return False
    fallback_mode = str(
        strategic_summary.get("fallback_mode")
        or (strategic_summary.get("closure_summary") or {}).get("mode")
        or ""
    ).strip()
    return fallback_mode == "macro_abstracted"


def _has_macro_safe_certificate(
    abstraction_certificate: AbstractionCertificate | None,
    abstraction_map_ref: ArtifactRef | None,
) -> bool:
    if abstraction_certificate is None or abstraction_map_ref is None:
        return False
    if abstraction_certificate.preservation_type not in _MACRO_CERTIFICATE_TYPES:
        return False
    if abstraction_certificate.preservation_type is AbstractionPreservationType.EXACT:
        return bool(abstraction_certificate.preserved_queries)
    return abstraction_certificate.error_bound is not None and bool(
        abstraction_certificate.preserved_queries
    )


__all__ = ["run_abstraction_challenge_suite"]

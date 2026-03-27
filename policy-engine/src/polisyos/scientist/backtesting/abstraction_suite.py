from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.ir.analytics.abm_bridge import ABMAlignmentReport
from polisyos.ir.analytics.abstraction import (
    AbstractionCertificate,
    AbstractionPreservationType,
)
from polisyos.scientist.backtesting.adversarial import (
    ABSTRACTION_LEAKAGE_SUITE_ID,
    ChallengeCase,
    ChallengeSuiteResult,
    build_challenge_case_result,
    build_challenge_suite_result,
)
from polisyos.scientist.doe.stress_report import VulnerabilityType


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
                case_id="macro_shortcut_requires_exact_certificate",
                challenge_family="abstraction_leakage",
                expected_outcome="macro_only_with_exact_certificate",
                severity="critical",
            ),
            passed=(
                not macro_shortcut_used
                or preservation_type is AbstractionPreservationType.EXACT
            ),
            summary=(
                "Macro shortcut usage is backed by an exact abstraction certificate."
                if not macro_shortcut_used
                or preservation_type is AbstractionPreservationType.EXACT
                else "Macro shortcut usage was observed without an exact abstraction certificate."
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


__all__ = ["run_abstraction_challenge_suite"]

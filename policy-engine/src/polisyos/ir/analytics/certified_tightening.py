"""Finite certified search over proof-carrying bounds candidates."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

from polisyos.ir.analytics.dual_certificate import (
    CertifiedBoundsCertificateBundle,
    StratifiedLPDualCertificateBundle,
    coerce_bounds_certificate_bundle,
    validate_bounds_certificate_bundle,
)
from polisyos.ir.analytics.partial_identification import (
    BestInClassClaim,
    BoundMethod,
    BoundSoundnessLevel,
    BoundTighteningLogEntry,
    PartialIdentificationResult,
    TighteningStatus,
    TighteningStopReason,
)


_DEFAULT_CLASS_NAME = "finite_sharp_lp_candidates_v1"


def _default_soundness(result: PartialIdentificationResult) -> BoundSoundnessLevel | None:
    if result.bounds_type == "sharp_lp":
        return BoundSoundnessLevel.HEURISTIC
    if result.bounds_type == "relaxed_polynomial":
        return BoundSoundnessLevel.HEURISTIC
    if result.bounds_type == "manski":
        return BoundSoundnessLevel.ASSUMPTION_ONLY
    return None


def _find_payload(
    result: PartialIdentificationResult,
    certificate_candidates: Sequence[tuple[PartialIdentificationResult, dict[str, Any]]],
) -> dict[str, Any] | None:
    for candidate_result, payload in certificate_candidates:
        if candidate_result == result:
            return payload
    return None


def _validate_payload(payload: dict[str, Any]) -> tuple[CertifiedBoundsCertificateBundle | None, str]:
    try:
        bundle = coerce_bounds_certificate_bundle(payload)
    except Exception as exc:
        return None, f"certificate_payload_invalid:{exc.__class__.__name__}"
    validation = validate_bounds_certificate_bundle(bundle)
    if not validation.ok:
        return None, "dual_certificate_validation_failed"
    return bundle, ""


def _baseline_result(results: Sequence[PartialIdentificationResult]) -> PartialIdentificationResult | None:
    manski = next((result for result in results if result.method is BoundMethod.MANSKI), None)
    if manski is not None:
        return manski
    if not results:
        return None
    return min(results, key=lambda item: item.bound_width)


def _strict_tightening(
    candidate: PartialIdentificationResult,
    baseline: PartialIdentificationResult,
    *,
    epsilon: float,
) -> bool:
    within = (
        candidate.lower_bound >= baseline.lower_bound - epsilon
        and candidate.upper_bound <= baseline.upper_bound + epsilon
    )
    strict = (
        candidate.lower_bound > baseline.lower_bound + epsilon
        or candidate.upper_bound < baseline.upper_bound - epsilon
    )
    return bool(within and strict)


def _candidate_sort_key(candidate: PartialIdentificationResult) -> tuple[float, float, float, str]:
    return (
        float(candidate.bound_width),
        -float(candidate.lower_bound),
        float(candidate.upper_bound),
        candidate.method.value,
    )


def _class_spec_hash(
    *,
    class_name: str,
    results: Sequence[PartialIdentificationResult],
    class_spec: dict[str, Any] | None = None,
) -> str:
    payload = {
        "class_name": class_name,
        "class_spec": dict(class_spec or {}),
        "candidate_count": len(results),
        "candidates": [
            {
                "method": result.method.value,
                "bounds_type": result.bounds_type,
                "assumptions_used": list(result.assumptions_used),
                "discretization_method": result.discretization_method,
                "n_bins_final": result.n_bins_final,
            }
            for result in results
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def build_certified_tightening_claim(
    results: Sequence[PartialIdentificationResult],
    certificate_candidates: Sequence[tuple[PartialIdentificationResult, dict[str, Any]]],
    *,
    class_name: str = _DEFAULT_CLASS_NAME,
    epsilon: float = 1e-12,
    class_spec: dict[str, Any] | None = None,
    extra_log_entries: Sequence[BoundTighteningLogEntry] = (),
    budget_exhausted: bool = False,
    all_tighteners_infeasible: bool = False,
    generated_tightener_count: int = 0,
    generated_tightener_certified_count: int = 0,
) -> tuple[BestInClassClaim, list[dict[str, Any]], dict[str, Any] | None]:
    """Evaluate a finite certified search class over existing bounds candidates.

    Returns a best-in-class claim, per-result annotations aligned with `results`,
    and the selected certificate payload when the search finds a certified
    improvement.
    """

    if not results:
        return (
            BestInClassClaim(
                class_name=class_name,
                status=TighteningStatus.NOT_RUN,
                stop_reason=TighteningStopReason.NOT_RUN,
                proof_note="No bounds candidates were available for certified tightening.",
            ),
            [],
            None,
        )

    baseline = _baseline_result(results)
    if baseline is None:
        return (
            BestInClassClaim(
                class_name=class_name,
                status=TighteningStatus.NOT_RUN,
                stop_reason=TighteningStopReason.NOT_RUN,
                proof_note="No baseline candidate was available for certified tightening.",
            ),
            [],
            None,
        )

    annotations: list[dict[str, Any]] = []
    log: list[BoundTighteningLogEntry] = []
    certified_candidates: list[tuple[PartialIdentificationResult, dict[str, Any], dict[str, Any]]] = []
    improving_candidates: list[tuple[PartialIdentificationResult, dict[str, Any], dict[str, Any]]] = []
    uncertified_search_class_count = 0
    class_spec_hash = _class_spec_hash(
        class_name=class_name,
        results=results,
        class_spec=class_spec,
    )

    for result in results:
        annotation: dict[str, Any] = {
            "certificate_kind": None,
            "soundness_level": _default_soundness(result),
            "solver_metadata": {},
        }
        reason = ""
        status = "uncertified"
        payload = _find_payload(result, certificate_candidates)
        if payload is not None:
            validated_bundle, validation_reason = _validate_payload(payload)
            if validated_bundle is not None:
                annotation = {
                    "certificate_kind": (
                        "stratified_lp_primal_dual"
                        if isinstance(validated_bundle, StratifiedLPDualCertificateBundle)
                        else validated_bundle.lower_cert.certificate_kind
                    ),
                    "soundness_level": BoundSoundnessLevel.CERTIFIED,
                    "solver_metadata": {
                        "certificate_family": validated_bundle.certificate_family,
                        **(
                            {
                                "n_strata": len(validated_bundle.strata),
                                "max_duality_gap": max(
                                    max(
                                        float(stratum.certificate.lower_cert.duality_gap),
                                        float(stratum.certificate.upper_cert.duality_gap),
                                    )
                                    for stratum in validated_bundle.strata
                                ),
                            }
                            if isinstance(validated_bundle, StratifiedLPDualCertificateBundle)
                            else {
                                "lower_solver_status": validated_bundle.lower_cert.solver_status,
                                "upper_solver_status": validated_bundle.upper_cert.solver_status,
                                "max_duality_gap": max(
                                    float(validated_bundle.lower_cert.duality_gap),
                                    float(validated_bundle.upper_cert.duality_gap),
                                ),
                            }
                        ),
                    },
                }
                certified_candidates.append((result, payload, annotation))
                if _strict_tightening(result, baseline, epsilon=epsilon):
                    status = "certified_improvement"
                    improving_candidates.append((result, payload, annotation))
                    reason = "strict_subset_of_baseline"
                else:
                    status = "certified_no_improvement"
                    reason = "certified_candidate_does_not_tighten_baseline"
            else:
                reason = validation_reason
                if result.bounds_type == "sharp_lp":
                    uncertified_search_class_count += 1
        elif result.bounds_type == "sharp_lp":
            reason = "missing_machine_checkable_certificate"
            uncertified_search_class_count += 1
        else:
            reason = "result_not_in_certified_search_class"

        if result == baseline:
            status = "baseline"
            if not reason:
                reason = "baseline_candidate"

        annotations.append(annotation)
        log.append(
            BoundTighteningLogEntry(
                method=result.method,
                lower_bound=result.lower_bound,
                upper_bound=result.upper_bound,
                bound_width=result.bound_width,
                status=status,
                reason=reason,
                certificate_kind=annotation["certificate_kind"],
                soundness_level=annotation["soundness_level"],
                metadata=dict(annotation["solver_metadata"]),
            )
        )

    if extra_log_entries:
        log.extend(extra_log_entries)

    shared_metadata = {
        "n_results": len(results),
        "n_certified_candidates": len(certified_candidates),
        "n_improving_candidates": len(improving_candidates),
        "n_uncertified_search_class_candidates": uncertified_search_class_count,
        "n_generated_tighteners": int(generated_tightener_count),
        "n_generated_tighteners_certified": int(generated_tightener_certified_count),
        "n_extra_log_entries": len(extra_log_entries),
        "budget_exhausted": bool(budget_exhausted),
        "all_tighteners_infeasible": bool(all_tighteners_infeasible),
    }

    if improving_candidates:
        selected_result, selected_payload, _ = min(
            improving_candidates,
            key=lambda item: _candidate_sort_key(item[0]),
        )
        width_reduction = float(max(0.0, baseline.bound_width - selected_result.bound_width))
        claim = BestInClassClaim(
            class_name=class_name,
            class_spec_hash=class_spec_hash,
            status=TighteningStatus.IMPROVED,
            baseline_method=baseline.method,
            baseline_lower_bound=baseline.lower_bound,
            baseline_upper_bound=baseline.upper_bound,
            selected_method=selected_result.method,
            lower_bound=selected_result.lower_bound,
            upper_bound=selected_result.upper_bound,
            certified_width_reduction=width_reduction,
            proof_note=(
                "Certified finite search found a strict subset of the baseline interval "
                "with a validated primal/dual witness."
            ),
            log=log,
            metadata={
                **shared_metadata,
                "best_in_class_complete": uncertified_search_class_count == 0,
            },
        )
        return claim, annotations, selected_payload

    if (
        all_tighteners_infeasible
        and generated_tightener_count > 0
        and generated_tightener_certified_count == 0
    ):
        claim = BestInClassClaim(
            class_name=class_name,
            class_spec_hash=class_spec_hash,
            status=TighteningStatus.BLOCKED,
            stop_reason=TighteningStopReason.MODEL_INFEASIBLE_UNDER_ALL_TIGHTENERS,
            baseline_method=baseline.method,
            baseline_lower_bound=baseline.lower_bound,
            baseline_upper_bound=baseline.upper_bound,
            selected_method=baseline.method,
            lower_bound=baseline.lower_bound,
            upper_bound=baseline.upper_bound,
            certified_width_reduction=0.0,
            proof_note=(
                "Every generated tightening candidate in the finite search class was "
                "provably infeasible under the current data and assumptions."
            ),
            log=log,
            metadata={
                **shared_metadata,
                "best_in_class_complete": uncertified_search_class_count == 0,
            },
        )
        return claim, annotations, None

    if budget_exhausted:
        claim = BestInClassClaim(
            class_name=class_name,
            class_spec_hash=class_spec_hash,
            status=TighteningStatus.INCOMPLETE,
            stop_reason=TighteningStopReason.BUDGET_EXCEEDED,
            baseline_method=baseline.method,
            baseline_lower_bound=baseline.lower_bound,
            baseline_upper_bound=baseline.upper_bound,
            selected_method=baseline.method,
            lower_bound=baseline.lower_bound,
            upper_bound=baseline.upper_bound,
            certified_width_reduction=0.0,
            proof_note=(
                "The finite search class was truncated by an explicit evaluation budget, "
                "so no best-in-class non-improvement proof can be issued."
            ),
            log=log,
            metadata={
                **shared_metadata,
                "best_in_class_complete": False,
            },
        )
        return claim, annotations, None

    if certified_candidates and uncertified_search_class_count == 0:
        claim = BestInClassClaim(
            class_name=class_name,
            class_spec_hash=class_spec_hash,
            status=TighteningStatus.EXHAUSTED_NO_IMPROVEMENT,
            stop_reason=TighteningStopReason.EXHAUSTED_CLASS_NO_IMPROVEMENT,
            baseline_method=baseline.method,
            baseline_lower_bound=baseline.lower_bound,
            baseline_upper_bound=baseline.upper_bound,
            selected_method=baseline.method,
            lower_bound=baseline.lower_bound,
            upper_bound=baseline.upper_bound,
            certified_width_reduction=0.0,
            proof_note=(
                "The certified search class was exhausted: every validated sharp-LP candidate "
                "was no tighter than the baseline interval."
            ),
            log=log,
            metadata={
                **shared_metadata,
                "best_in_class_complete": True,
            },
        )
        return claim, annotations, None

    if certified_candidates:
        claim = BestInClassClaim(
            class_name=class_name,
            class_spec_hash=class_spec_hash,
            status=TighteningStatus.INCOMPLETE,
            stop_reason=TighteningStopReason.CLASS_NOT_CERTIFIABLE_WITH_BACKEND,
            baseline_method=baseline.method,
            baseline_lower_bound=baseline.lower_bound,
            baseline_upper_bound=baseline.upper_bound,
            selected_method=baseline.method,
            lower_bound=baseline.lower_bound,
            upper_bound=baseline.upper_bound,
            certified_width_reduction=0.0,
            proof_note=(
                "At least one sharp-LP candidate lacked a machine-checkable witness, "
                "so no best-in-class non-improvement proof can be issued."
            ),
            log=log,
            metadata={
                **shared_metadata,
                "best_in_class_complete": False,
            },
        )
        return claim, annotations, None

    claim = BestInClassClaim(
        class_name=class_name,
        class_spec_hash=class_spec_hash,
        status=TighteningStatus.BLOCKED,
        stop_reason=TighteningStopReason.CLASS_NOT_CERTIFIABLE_WITH_BACKEND,
        baseline_method=baseline.method,
        baseline_lower_bound=baseline.lower_bound,
        baseline_upper_bound=baseline.upper_bound,
        selected_method=baseline.method,
        lower_bound=baseline.lower_bound,
        upper_bound=baseline.upper_bound,
        certified_width_reduction=0.0,
        proof_note=(
            "No candidate in the finite search class carried a machine-checkable certificate, "
            "so best-in-class optimality could not be established."
        ),
        log=log,
        metadata={
            **shared_metadata,
            "best_in_class_complete": False,
        },
    )
    return claim, annotations, None


__all__ = ["build_certified_tightening_claim"]

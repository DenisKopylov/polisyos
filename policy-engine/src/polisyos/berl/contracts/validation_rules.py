"""Fail-closed product gates for BERL ExplanationBundle artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.berl.contracts.explanation_bundle import ExplanationBundle


@dataclass(frozen=True, slots=True)
class ValidationThresholds:
    """Release and UI thresholds for explanation display."""

    max_p95_infidelity_upper_bound: float = 0.05
    min_median_top_k_agreement: float = 0.5
    max_sign_conflict_rate: float = 0.2
    max_perturbation_ood_rate: float = 0.05


@dataclass(frozen=True, slots=True)
class ExplanationValidationResult:
    """Validation verdict for one ExplanationBundle."""

    passed: bool
    faithfulness_claim: str
    display_policy: str
    violations: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


def validate_explanation_bundle(
    bundle: ExplanationBundle,
    *,
    thresholds: ValidationThresholds | None = None,
) -> ExplanationValidationResult:
    """Validate whether a bundle may be shown as an analyst-facing explanation."""

    active_thresholds = thresholds or ValidationThresholds()
    violations: list[str] = []
    warnings: list[str] = []

    if not bundle.methods:
        violations.append("no_explanation_methods")

    bounded_methods = [method for method in bundle.methods if method.infidelity is not None]
    if bundle.faithfulness_claim == "bounded" and len(bounded_methods) != len(bundle.methods):
        violations.append("method_missing_infidelity_bound")

    if bundle.faithfulness_claim == "unbounded":
        warnings.append("faithfulness_claim_unbounded")

    for method in bundle.methods:
        if not method.params and not method.assumptions:
            violations.append(f"method_lacks_declared_assumptions:{method.method_id}")
        if method.infidelity is not None and method.infidelity.evaluation_split != "heldout":
            violations.append(f"infidelity_not_heldout:{method.method_id}")

    upper_bounds = tuple(
        method.infidelity.upper_bound
        for method in bundle.methods
        if method.infidelity is not None
    )
    if upper_bounds:
        p95 = _quantile(upper_bounds, 0.95)
        if p95 > active_thresholds.max_p95_infidelity_upper_bound:
            violations.append("p95_infidelity_upper_bound_exceeds_tolerance")

    if bundle.disagreement is None and len(bundle.methods) > 1:
        violations.append("missing_disagreement_report")
    if bundle.disagreement is not None:
        agreement = bundle.disagreement.top_k_jaccard_median
        if agreement is not None and agreement < active_thresholds.min_median_top_k_agreement:
            violations.append("median_top_k_method_agreement_below_threshold")
        conflict_rate = _sign_conflict_rate(bundle)
        if conflict_rate > active_thresholds.max_sign_conflict_rate:
            violations.append("sign_conflict_rate_exceeds_threshold")
        if _top_feature_is_non_identifiable(bundle):
            violations.append("top_feature_inside_non_identifiable_redundancy_cluster")

    support = bundle.validity.support_check
    if support.ood_rate_eval_perturbations > active_thresholds.max_perturbation_ood_rate:
        violations.append("perturbation_ood_rate_exceeds_threshold")
    if support.constraint_violation_rate > 0.0:
        violations.append("perturbation_constraint_violation")

    passed = not violations and bundle.faithfulness_claim == "bounded"
    display_policy = "analyst_display" if passed else "diagnostic_only"
    return ExplanationValidationResult(
        passed=passed,
        faithfulness_claim="bounded" if passed else "unbounded",
        display_policy=display_policy,
        violations=tuple(dict.fromkeys(violations)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def summarize_explanation_response(
    bundle: ExplanationBundle,
    *,
    thresholds: ValidationThresholds | None = None,
) -> dict[str, object]:
    """Return the API summary shape used by the explanation endpoint."""

    validation = validate_explanation_bundle(bundle, thresholds=thresholds)
    max_bound = max(
        (
            method.infidelity.upper_bound
            for method in bundle.methods
            if method.infidelity is not None
        ),
        default=None,
    )
    confidence = min(
        (
            method.infidelity.confidence
            for method in bundle.methods
            if method.infidelity is not None
        ),
        default=None,
    )
    primary_driver_level = "group" if bundle.redundancy.clusters else "feature"
    return {
        "bundle_id": bundle.bundle_id,
        "status": "complete" if bundle.methods else "empty",
        "summary": {
            "faithfulness_claim": validation.faithfulness_claim,
            "max_infidelity_upper_bound": max_bound,
            "confidence": confidence,
            "primary_driver_level": primary_driver_level,
            "warnings": list(validation.violations + validation.warnings),
        },
    }


def _sign_conflict_rate(bundle: ExplanationBundle) -> float:
    if bundle.disagreement is None:
        return 0.0
    features = {
        attribution.feature
        for method in bundle.methods
        for attribution in method.attributions
    }
    if not features:
        return 0.0
    return len(bundle.disagreement.sign_conflict_features) / len(features)


def _top_feature_is_non_identifiable(bundle: ExplanationBundle) -> bool:
    if bundle.disagreement is None:
        return False
    if "feature_level_non_identifiable" not in bundle.disagreement.flags:
        return False
    top_feature = _top_feature(bundle)
    if top_feature is None:
        return False
    for cluster in bundle.redundancy.clusters:
        if top_feature in cluster.features and cluster.reporting_policy == "group_first":
            return True
    return False


def _top_feature(bundle: ExplanationBundle) -> str | None:
    values: dict[str, float] = {}
    for method in bundle.methods:
        for attribution in method.attributions:
            current = abs(values.get(attribution.feature, 0.0))
            if abs(attribution.value) > current:
                values[attribution.feature] = attribution.value
    if not values:
        return None
    return max(values.items(), key=lambda item: abs(item[1]))[0]


def _quantile(values: tuple[float, ...], quantile: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be in [0, 1]")
    ordered = tuple(sorted(values))
    if len(ordered) == 1:
        return ordered[0]
    position = quantile * (len(ordered) - 1)
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return ordered[lower_index] * (1.0 - fraction) + ordered[upper_index] * fraction

"""Display gating rules for analyst-facing BERL UI surfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING

from polisyos.berl.contracts.validation_rules import ValidationThresholds

if TYPE_CHECKING:
    from polisyos.berl.contracts.explanation_bundle import ExplanationBundle


def can_show_bare_bar_chart(
    bundle: ExplanationBundle,
    *,
    thresholds: ValidationThresholds | None = None,
) -> bool:
    """Return true only when the plan's bare-bar-chart UI rules are satisfied."""

    active_thresholds = thresholds or ValidationThresholds()
    if not bundle.methods or any(method.infidelity is None for method in bundle.methods):
        return False
    if not bundle.prediction.output_scale:
        return False
    if not bundle.assumptions.perturbation_distribution.name:
        return False
    if not bundle.assumptions.feature_dependence_policy.primary:
        return False
    if bundle.disagreement is not None:
        agreement = bundle.disagreement.top_k_jaccard_median
        if agreement is not None and agreement < active_thresholds.min_median_top_k_agreement:
            return False
        if "feature_level_non_identifiable" in bundle.disagreement.flags:
            return False
    return True


def explanation_limitation_message(bundle: ExplanationBundle) -> str | None:
    """Return the standard limitation message when a bare chart is unsafe."""

    if can_show_bare_bar_chart(bundle):
        return None
    if bundle.redundancy.clusters:
        return (
            "Explanation available with limitations. The model is sensitive to a feature "
            "group, but the individual feature split is ambiguous."
        )
    return "Explanation available with limitations."

"""SensitivityReport — aggregated sensitivity analysis result.

Combines SensitivityResult (E-value, RV, Rosenbaum gamma) with optional
BoundsReport and NegativeCertificate when robustness thresholds are breached.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.partial_identification import BoundsReport
from polisyos.ir.analytics.sensitivity import SensitivityResult


class SensitivityReport(BaseModel):
    """Aggregated sensitivity and robustness analysis for a causal estimate.

    Produced after estimation completes and connects:
    - sensitivity_result: E-value / Robustness Value / Rosenbaum gamma
    - bounds_report: partial identification bounds (optional, when BOUNDS_ONLY strategy)
    - threshold_breaches: which metrics fell below the robustness threshold
    - overall_robustness_assessment: coarse categorisation for UI / downstream gating
    - actionable_recommendations: list of concrete next steps for the analyst

    When ``is_robust=False`` in ``sensitivity_result`` and threshold breaches are
    present, a ``NegativeCertificate`` may be attached to guide further data collection.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    run_id: str = ""
    estimand_type: str = "ate"

    sensitivity_result: SensitivityResult
    """Core sensitivity metrics: E-value, Robustness Value, Rosenbaum gamma."""

    bounds_report: BoundsReport | None = None
    """Partial identification bounds, if a BOUNDS_ONLY strategy was used."""

    threshold_breaches: dict[str, float] = Field(default_factory=dict)
    """Metrics that fell below their robustness thresholds.
    Keys are metric names (e.g. 'e_value', 'rosenbaum_gamma');
    values are the observed metric values.
    """

    negative_certificate: dict[str, Any] | None = None
    """Serialized NegativeCertificate when threshold breaches are severe.
    Stored as dict to avoid circular imports; use
    ``NegativeCertificate.model_validate(d)`` to reconstruct.
    """

    overall_robustness_assessment: str = ""
    """Coarse assessment: 'robust' | 'marginal' | 'fragile' | 'not_applicable'."""

    actionable_recommendations: list[str] = Field(default_factory=list)
    """Concrete next steps for the analyst based on the sensitivity analysis."""

    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_assessment(self) -> "SensitivityReport":
        sr = self.sensitivity_result

        # Determine assessment
        if sr.is_robust and not self.threshold_breaches:
            assessment = "robust"
        elif not sr.is_robust and self.threshold_breaches:
            assessment = "fragile"
        elif not sr.is_robust or self.threshold_breaches:
            assessment = "marginal"
        else:
            assessment = "robust"

        object.__setattr__(self, "overall_robustness_assessment", assessment)

        # Build actionable recommendations
        recs: list[str] = []
        if sr.e_value is not None and sr.e_value < 1.5:
            recs.append(
                "E-value < 1.5: a weak unmeasured confounder could explain away the effect. "
                "Consider collecting data on potential confounders."
            )
        if sr.rosenbaum_gamma is not None and sr.rosenbaum_gamma < 1.25:
            recs.append(
                "Rosenbaum gamma < 1.25: the result is sensitive to small deviations in "
                "treatment assignment odds. Consider a randomised experiment."
            )
        if sr.robustness_value is not None and sr.robustness_value < 0.05:
            recs.append(
                "Robustness value < 0.05: a confounder explaining less than 5% of residual "
                "variance could overturn the result. Investigate covariate balance."
            )
        if self.bounds_report is not None and not self.bounds_report.is_informative:
            recs.append(
                "Partial identification bounds are wide (uninformative). "
                "Collect additional data or impose stronger assumptions to narrow the bounds."
            )
        if recs:
            object.__setattr__(self, "actionable_recommendations", recs)

        return self


__all__ = ["SensitivityReport"]

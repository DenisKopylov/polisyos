"""DOD-135: Partial identification with Manski bounds."""

from __future__ import annotations

from enum import Enum
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BoundMethod(str, Enum):
    MANSKI = "manski_bounds"
    IV_BOUNDS = "iv_bounds"
    MONOTONE_TREATMENT = "monotone_treatment"
    LP_BALKE_PEARL = "lp_balke_pearl"
    IMBENS_MANSKI_CI = "imbens_manski_ci"
    MTR_BOUNDS = "mtr_bounds"
    """Monotone Treatment Response LP bounds (Manski 1997)."""
    MIV_BOUNDS = "miv_bounds"
    """Monotone Instrumental Variable bounds (Manski & Pepper 2000)."""
    MTS_BOUNDS = "mts_bounds"
    """Monotone Treatment Selection LP bounds."""
    GENERAL_LP_BOUNDS = "general_lp_bounds"
    """Generalised Balke-Pearl LP for multi-valued T/Y, binary Z (Balke & Pearl 1997 §4)."""
    COPULA_BOUNDS = "copula_bounds"
    """Fan & Park (2010) sharp bounds on the distribution of Y(1)−Y(0)."""
    TAN_BOUNDS = "tan_bounds"
    """Tan (2006, JASA) sensitivity sweep under Marginal Sensitivity Model."""
    INTERSECTION_BOUNDS = "intersection_bounds"
    """Chernozhukov, Lee & Rosen (2013) intersection of multiple identified sets."""
    ROSENBAUM_SHARP = "rosenbaum_sharp"
    """Sharp per-γ p-value bounds for matched pairs (Rosenbaum 2002)."""


class PartialIdentificationResult(BaseModel):
    """Result of partial identification analysis (e.g., Manski bounds on ATE)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    method: BoundMethod
    lower_bound: float
    upper_bound: float
    bound_width: float = 0.0
    is_informative: bool = True
    confidence: float = Field(ge=0.0, le=1.0)
    assumptions_used: list[str] = Field(default_factory=list)
    assumptions_violated: list[str] = Field(default_factory=list)
    informativeness_threshold: float = 0.5
    display_label: str = ""
    """Human-readable label for UI display, e.g. 'Manski Worst-Case Bounds'."""
    chart_type: str = "interval"
    """Visualization hint: 'interval' | 'density' | 'scatter'."""

    @model_validator(mode="after")
    def _compute_derived(self) -> "PartialIdentificationResult":
        width = self.upper_bound - self.lower_bound
        informative = width < self.informativeness_threshold
        object.__setattr__(self, "bound_width", width)
        object.__setattr__(self, "is_informative", informative)
        return self

    def to_ui_dict(self) -> dict:
        """Return a JSON-serializable dict for frontend rendering."""
        return {
            "lower": self.lower_bound,
            "upper": self.upper_bound,
            "width": self.bound_width,
            "method": self.method.value,
            "is_informative": self.is_informative,
            "confidence": self.confidence,
            "display_label": self.display_label or self.method.value,
            "chart_type": self.chart_type,
        }


class BoundsReport(BaseModel):
    """Aggregated result from running multiple partial identification methods.

    Computes the tightest method (argmin bound_width) and the consensus interval
    (intersection of all bound intervals).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    run_id: str = ""
    estimand_type: str = "ate"
    results: list[PartialIdentificationResult]
    """One PartialIdentificationResult per bounds method that was run."""
    tightest_method: BoundMethod | None = None
    """Method with the smallest bound_width."""
    tightest_lower: float | None = None
    tightest_upper: float | None = None
    consensus_lower: float | None = None
    """max(all lower_bounds) — tightest lower bound across all methods."""
    consensus_upper: float | None = None
    """min(all upper_bounds) — tightest upper bound across all methods."""
    assumptions_used: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    is_informative: bool = False
    """True when the tightest bound_width < informative_threshold * (y_max - y_min)."""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _compute_derived(self) -> "BoundsReport":
        if not self.results:
            return self
        # Tightest: argmin bound_width
        tightest = min(self.results, key=lambda r: r.bound_width)
        object.__setattr__(self, "tightest_method", tightest.method)
        object.__setattr__(self, "tightest_lower", tightest.lower_bound)
        object.__setattr__(self, "tightest_upper", tightest.upper_bound)
        # Consensus: intersection of all intervals
        object.__setattr__(self, "consensus_lower", max(r.lower_bound for r in self.results))
        object.__setattr__(self, "consensus_upper", min(r.upper_bound for r in self.results))
        # Informative: tightest_lower != tightest_upper (some information gained)
        object.__setattr__(self, "is_informative", tightest.is_informative)
        return self

    def to_ui_dict(self) -> dict:
        """Return a JSON-serializable dict for frontend rendering."""
        return {
            "estimand_type": self.estimand_type,
            "tightest_method": self.tightest_method.value if self.tightest_method else None,
            "tightest_lower": self.tightest_lower,
            "tightest_upper": self.tightest_upper,
            "consensus_lower": self.consensus_lower,
            "consensus_upper": self.consensus_upper,
            "is_informative": self.is_informative,
            "n_methods": len(self.results),
            "warnings": self.warnings,
        }


class SensitivitySweepResult(BaseModel):
    """Bounds expressed as a function of a sensitivity parameter (γ or λ).

    Captures the entire sensitivity sweep so the UI can render a sensitivity
    curve rather than just a single critical value.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    parameter_name: str
    """Name of the sensitivity parameter, e.g. 'gamma' or 'lambda'."""
    parameter_values: tuple[float, ...]
    lower_bounds: tuple[float, ...]
    upper_bounds: tuple[float, ...]
    critical_value: float | None = None
    """Parameter value at which the bounds first exclude the null (0)."""
    method: BoundMethod = BoundMethod.ROSENBAUM_SHARP
    display_label: str = ""

    @model_validator(mode="after")
    def _validate_lengths(self) -> "SensitivitySweepResult":
        n = len(self.parameter_values)
        if len(self.lower_bounds) != n or len(self.upper_bounds) != n:
            raise ValueError(
                "parameter_values, lower_bounds, and upper_bounds must have equal length"
            )
        return self


def compute_manski_bounds(
    outcome_conditioned: np.ndarray,
    treatment_probs: np.ndarray,
    outcome_support: tuple[float, float] = (0.0, 1.0),
) -> PartialIdentificationResult:
    """Classic Manski (1990) worst-case bounds for ATE.

    Parameters
    ----------
    outcome_conditioned : (2,) array
        [E[Y|X=0], E[Y|X=1]] — conditional expectations.
    treatment_probs : (2,) array
        [P(X=0), P(X=1)] — marginal treatment probabilities.
    outcome_support : tuple
        (y_min, y_max) — support of the outcome variable.

    Returns
    -------
    PartialIdentificationResult with Manski bounds on ATE.
    """
    y_min, y_max = outcome_support
    e_y0, e_y1 = float(outcome_conditioned[0]), float(outcome_conditioned[1])
    p0, p1 = float(treatment_probs[0]), float(treatment_probs[1])

    # Manski bounds: ATE in [lower, upper]
    # Lower = p1*E[Y|X=1] + (1-p1)*y_min - p0*E[Y|X=0] - (1-p0)*y_max
    # Upper = p1*E[Y|X=1] + (1-p1)*y_max - p0*E[Y|X=0] - (1-p0)*y_min
    lower = (p1 * e_y1 + (1 - p1) * y_min) - (p0 * e_y0 + (1 - p0) * y_max)
    upper = (p1 * e_y1 + (1 - p1) * y_max) - (p0 * e_y0 + (1 - p0) * y_min)

    width = upper - lower
    confidence = max(0.0, min(1.0, 1.0 - width / (y_max - y_min) if y_max != y_min else 0.0))

    return PartialIdentificationResult(
        method=BoundMethod.MANSKI,
        lower_bound=lower,
        upper_bound=upper,
        confidence=confidence,
        assumptions_used=["no_assumptions_on_selection"],
        assumptions_violated=[],
    )


__all__ = [
    "BoundMethod",
    "BoundsReport",
    "PartialIdentificationResult",
    "SensitivitySweepResult",
    "compute_manski_bounds",
]

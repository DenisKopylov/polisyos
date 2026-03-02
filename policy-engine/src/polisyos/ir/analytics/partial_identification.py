"""DOD-135: Partial identification with Manski bounds."""

from __future__ import annotations

from enum import Enum

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator


class BoundMethod(str, Enum):
    MANSKI = "manski_bounds"
    IV_BOUNDS = "iv_bounds"
    MONOTONE_TREATMENT = "monotone_treatment"


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

    @model_validator(mode="after")
    def _compute_derived(self) -> "PartialIdentificationResult":
        width = self.upper_bound - self.lower_bound
        informative = width < self.informativeness_threshold
        object.__setattr__(self, "bound_width", width)
        object.__setattr__(self, "is_informative", informative)
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
    "PartialIdentificationResult",
    "compute_manski_bounds",
]

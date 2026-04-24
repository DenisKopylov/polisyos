"""Public sensitivity registry boot module API."""

from __future__ import annotations

from collections.abc import Sequence

from .screening import (
    FASTEstimator,
    MorrisSensitivityEstimator,
    PAWNEstimator,
)
from .sobol import SobolFirstOrderEstimator
from .specification import SpecificationCurveEstimator


def register_sensitivity_methods() -> Sequence[type]:
    """Register sensitivity methods."""
    return (
        SobolFirstOrderEstimator,
        MorrisSensitivityEstimator,
        FASTEstimator,
        PAWNEstimator,
        SpecificationCurveEstimator,
    )


__all__ = ["register_sensitivity_methods"]

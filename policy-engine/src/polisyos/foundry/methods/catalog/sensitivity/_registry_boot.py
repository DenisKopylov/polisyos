"""Public sensitivity registry boot module API."""

from __future__ import annotations

from collections.abc import Sequence

from .dependent_copula import DependentCopulaSensitivityEstimator
from .distributional import (
    DistributionalSensitivityEstimator,
    QOSAPinballSensitivityEstimator,
)
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
        DependentCopulaSensitivityEstimator,
        MorrisSensitivityEstimator,
        FASTEstimator,
        PAWNEstimator,
        SpecificationCurveEstimator,
        QOSAPinballSensitivityEstimator,
        DistributionalSensitivityEstimator,
    )


__all__ = ["register_sensitivity_methods"]

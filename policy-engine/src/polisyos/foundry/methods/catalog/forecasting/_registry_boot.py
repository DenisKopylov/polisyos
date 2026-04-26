"""Public forecasting registry boot module API."""

from __future__ import annotations

from collections.abc import Sequence

from .advanced import (
    ProphetEstimator,
    STLDecompositionEstimator,
    VECForecastEstimator,
)
from .hybrid import GuardedNeuralForecastEstimator
from .regime_shift import RegimeShiftForecastEstimator
from .univariate import (
    BottomUpReconciliationEstimator,
    ExponentialSmoothingEstimator,
    ForecastEnsembleEstimator,
    GeneralLinearReconciliationEstimator,
    ThetaMethodEstimator,
)


def register_forecasting_methods() -> Sequence[type]:
    """Register forecasting methods."""
    return (
        ExponentialSmoothingEstimator,
        ThetaMethodEstimator,
        ForecastEnsembleEstimator,
        BottomUpReconciliationEstimator,
        GeneralLinearReconciliationEstimator,
        STLDecompositionEstimator,
        VECForecastEstimator,
        ProphetEstimator,
        GuardedNeuralForecastEstimator,
        RegimeShiftForecastEstimator,
    )


__all__ = ["register_forecasting_methods"]

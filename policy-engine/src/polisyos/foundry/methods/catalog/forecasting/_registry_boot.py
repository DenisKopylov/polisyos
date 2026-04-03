"""Public forecasting registry boot module API."""
from __future__ import annotations

from typing import Sequence

from .advanced import (
    ProphetEstimator,
    STLDecompositionEstimator,
    VECForecastEstimator,
)
from .univariate import (
    BottomUpReconciliationEstimator,
    ExponentialSmoothingEstimator,
    ForecastEnsembleEstimator,
    ThetaMethodEstimator,
)


def register_forecasting_methods() -> Sequence[type]:
    """Register forecasting methods."""
    return (
        ExponentialSmoothingEstimator,
        ThetaMethodEstimator,
        ForecastEnsembleEstimator,
        BottomUpReconciliationEstimator,
        STLDecompositionEstimator,
        VECForecastEstimator,
        ProphetEstimator,
    )


__all__ = ["register_forecasting_methods"]

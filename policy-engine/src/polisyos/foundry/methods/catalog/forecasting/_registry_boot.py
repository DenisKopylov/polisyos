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

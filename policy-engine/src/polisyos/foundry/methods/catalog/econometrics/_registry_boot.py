from __future__ import annotations

from typing import Sequence

from .advanced import (
    ChangePointEstimator,
    EventStudyEstimator,
    GARCHEstimator,
    LocalProjectionsEstimator,
    QuantileRegressionEstimator,
)
from .diagnostics import (
    CointegrationTestEstimator,
    ForecastBacktestEstimator,
    HausmanTestEstimator,
    SarganHansenEstimator,
    WeakIVTestEstimator,
)
from .expansion import (
    BayesianVAREstimator,
    SpatialAutoregressiveEstimator,
    SyntheticDiDEstimator,
    VECMEstimator,
)
from .iv import GMMEstimator, InstrumentalVariablesEstimator, TwoStageLeastSquaresEstimator
from .panel import FixedEffectsEstimator, PanelDataEstimator, RandomEffectsEstimator
from .timeseries import ARIMAEstimator, TimeSeriesEstimator, VAREstimator


def register_econometric_methods() -> Sequence[type]:
    return (
        FixedEffectsEstimator,
        RandomEffectsEstimator,
        PanelDataEstimator,
        TwoStageLeastSquaresEstimator,
        GMMEstimator,
        InstrumentalVariablesEstimator,
        ARIMAEstimator,
        VAREstimator,
        TimeSeriesEstimator,
        QuantileRegressionEstimator,
        EventStudyEstimator,
        LocalProjectionsEstimator,
        GARCHEstimator,
        ChangePointEstimator,
        VECMEstimator,
        BayesianVAREstimator,
        SyntheticDiDEstimator,
        SpatialAutoregressiveEstimator,
        HausmanTestEstimator,
        WeakIVTestEstimator,
        SarganHansenEstimator,
        CointegrationTestEstimator,
        ForecastBacktestEstimator,
    )


__all__ = ["register_econometric_methods"]

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_econometric_methods
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
from .protocols import (
    EconometricDiagnosticResult,
    EconometricEstimator,
    EconometricResult,
    PanelData,
    TimeSeriesData,
)
from .timeseries import ARIMAEstimator, TimeSeriesEstimator, VAREstimator


def ensure_econometric_methods_registered(registry: MethodRegistry | None = None) -> None:
    reg = registry or MethodRegistry.get_instance()
    for method_class in register_econometric_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "EconometricDiagnosticResult",
    "EconometricEstimator",
    "EconometricResult",
    "PanelData",
    "TimeSeriesData",
    "FixedEffectsEstimator",
    "PanelDataEstimator",
    "RandomEffectsEstimator",
    "TwoStageLeastSquaresEstimator",
    "GMMEstimator",
    "InstrumentalVariablesEstimator",
    "ARIMAEstimator",
    "VAREstimator",
    "TimeSeriesEstimator",
    "QuantileRegressionEstimator",
    "EventStudyEstimator",
    "LocalProjectionsEstimator",
    "GARCHEstimator",
    "ChangePointEstimator",
    "VECMEstimator",
    "BayesianVAREstimator",
    "SyntheticDiDEstimator",
    "SpatialAutoregressiveEstimator",
    "HausmanTestEstimator",
    "WeakIVTestEstimator",
    "SarganHansenEstimator",
    "CointegrationTestEstimator",
    "ForecastBacktestEstimator",
    "register_econometric_methods",
    "ensure_econometric_methods_registered",
]

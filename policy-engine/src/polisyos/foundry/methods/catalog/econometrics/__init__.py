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
from .count_data import (
    NegativeBinomialEstimator,
    PoissonRegressionEstimator,
    ZeroInflatedPoissonEstimator,
)
from .discrete_choice import (
    BLPEstimator,
    LogitEstimator,
    MixedLogitEstimator,
    MultinomialLogitEstimator,
    ProbitEstimator,
)
from .high_dimensional import (
    PostDoubleSelectionEstimator,
    PostLASSOEstimator,
)
from .iv import GMMEstimator, TwoStageLeastSquaresEstimator
from .panel import FixedEffectsEstimator, RandomEffectsEstimator
from .protocols import (
    EconometricDiagnosticResult,
    EconometricEstimator,
    EconometricResult,
    PanelData,
    TimeSeriesData,
)
from .selection import (
    HeckmanSelectionEstimator,
    TobitEstimator,
    TruncatedRegressionEstimator,
)
from .semiparametric import (
    KernelRegressionEstimator,
    RobinsonEstimator,
)
from .timeseries import ARIMAEstimator, VAREstimator


def ensure_econometric_methods_registered(registry: MethodRegistry | None = None) -> None:
    reg = registry if registry is not None else MethodRegistry.get_instance()
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
    "RandomEffectsEstimator",
    "TwoStageLeastSquaresEstimator",
    "GMMEstimator",
    "ARIMAEstimator",
    "VAREstimator",
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
    "LogitEstimator",
    "ProbitEstimator",
    "MultinomialLogitEstimator",
    "MixedLogitEstimator",
    "BLPEstimator",
    "HeckmanSelectionEstimator",
    "TobitEstimator",
    "TruncatedRegressionEstimator",
    "PoissonRegressionEstimator",
    "NegativeBinomialEstimator",
    "ZeroInflatedPoissonEstimator",
    "RobinsonEstimator",
    "KernelRegressionEstimator",
    "PostLASSOEstimator",
    "PostDoubleSelectionEstimator",
    "register_econometric_methods",
    "ensure_econometric_methods_registered",
]

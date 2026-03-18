from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_forecasting_methods
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


def ensure_forecasting_methods_registered(registry: MethodRegistry | None = None) -> None:
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_forecasting_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "BottomUpReconciliationEstimator",
    "ExponentialSmoothingEstimator",
    "ForecastEnsembleEstimator",
    "ProphetEstimator",
    "STLDecompositionEstimator",
    "ThetaMethodEstimator",
    "VECForecastEstimator",
    "ensure_forecasting_methods_registered",
    "register_forecasting_methods",
]

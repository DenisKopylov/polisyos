"""Expose forecasting methods and register them into the Foundry catalog."""

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_forecasting_methods
from .advanced import (
    ProphetEstimator,
    STLDecompositionEstimator,
    VECForecastEstimator,
)
from .benchmarking import (
    ForecastBenchmarkRegime,
    ForecastBenchmarkResult,
    ForecastRecommendationCell,
    ForecastResearchStrategy,
    RegimeShiftCalibrationBenchmarkResult,
    lookup_phase0_forecasting_recommendation,
    phase0_forecasting_recommendation_matrix,
    run_phase0_forecasting_benchmark,
    run_regime_shift_calibration_benchmark,
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


def ensure_forecasting_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Populate `registry` with baseline and advanced forecasting methods."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_forecasting_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "BottomUpReconciliationEstimator",
    "ExponentialSmoothingEstimator",
    "ForecastBenchmarkRegime",
    "ForecastBenchmarkResult",
    "ForecastEnsembleEstimator",
    "ForecastRecommendationCell",
    "ForecastResearchStrategy",
    "GeneralLinearReconciliationEstimator",
    "GuardedNeuralForecastEstimator",
    "ProphetEstimator",
    "RegimeShiftCalibrationBenchmarkResult",
    "RegimeShiftForecastEstimator",
    "STLDecompositionEstimator",
    "ThetaMethodEstimator",
    "VECForecastEstimator",
    "ensure_forecasting_methods_registered",
    "lookup_phase0_forecasting_recommendation",
    "phase0_forecasting_recommendation_matrix",
    "register_forecasting_methods",
    "run_phase0_forecasting_benchmark",
    "run_regime_shift_calibration_benchmark",
]

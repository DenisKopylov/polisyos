"""Expose panel, IV, discrete-choice, and semiparametric econometric methods."""

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_econometric_methods
from .advanced import (
    ChangePointEstimator,
    EventStudyEstimator,
    GARCHEstimator,
    LocalProjectionsEstimator,
    NonstationaryGARCHEstimator,
    QuantileRegressionEstimator,
)
from .count_data import (
    NegativeBinomialEstimator,
    PoissonRegressionEstimator,
    ZeroInflatedPoissonEstimator,
)
from .diagnostics import (
    CointegrationTestEstimator,
    ForecastBacktestEstimator,
    HausmanTestEstimator,
    SarganHansenEstimator,
    WeakIVTestEstimator,
)
from .discrete_choice import (
    BLPEstimator,
    LogitEstimator,
    MixedLogitEstimator,
    MultinomialLogitEstimator,
    ProbitEstimator,
)
from .dynamic_panel import DifferenceGMMEstimator, SystemGMMEstimator
from .expansion import (
    BayesianVAREstimator,
    SpatialAutoregressiveEstimator,
    SyntheticDiDEstimator,
    VECMEstimator,
)
from .high_dimensional import (
    PostDoubleSelectionEstimator,
    PostLASSOEstimator,
)
from .high_dimensional_iv import HighDimensionalPostSelectionIVEstimator
from .iv import GMMEstimator, TwoStageLeastSquaresEstimator
from .panel import FixedEffectsEstimator, RandomEffectsEstimator
from .protocols import (
    ConfidenceSetSegment,
    CoverageGuaranteeTier,
    CrossSectionalDependenceDiagnostic,
    EconometricDiagnosticResult,
    EconometricEstimator,
    EconometricResult,
    IdentificationDiagnostic,
    IntervalDisagreementDiagnostic,
    NonstationaryVolatilitySummary,
    OrthogonalityNuisanceDiagnostic,
    PanelData,
    PostSelectionCoverageDiagnostic,
    PostSelectionInterval,
    SparsityComplexityDiagnostic,
    ThresholdRegressionData,
    ThresholdStateField,
    TimeSeriesData,
    VolatilityBreak,
    VolatilityBreakDetectionMethod,
    VolatilityCoverageSummary,
    VolatilityLossFamily,
    VolatilityRegimeSegment,
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
from .thresholds import (
    StateDependentFRDEstimator,
    StateDependentFRKDEstimator,
    StateDependentKinkEstimator,
    StateDependentThresholdEstimator,
)
from .timeseries import ARIMAEstimator, VAREstimator


def ensure_econometric_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Register built-in econometric methods into `registry` or the global singleton."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_econometric_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "ARIMAEstimator",
    "BLPEstimator",
    "BayesianVAREstimator",
    "ChangePointEstimator",
    "CointegrationTestEstimator",
    "ConfidenceSetSegment",
    "CoverageGuaranteeTier",
    "CrossSectionalDependenceDiagnostic",
    "DifferenceGMMEstimator",
    "EconometricDiagnosticResult",
    "EconometricEstimator",
    "EconometricResult",
    "EventStudyEstimator",
    "FixedEffectsEstimator",
    "ForecastBacktestEstimator",
    "GARCHEstimator",
    "GMMEstimator",
    "HausmanTestEstimator",
    "HeckmanSelectionEstimator",
    "HighDimensionalPostSelectionIVEstimator",
    "IdentificationDiagnostic",
    "IntervalDisagreementDiagnostic",
    "KernelRegressionEstimator",
    "LocalProjectionsEstimator",
    "LogitEstimator",
    "MixedLogitEstimator",
    "MultinomialLogitEstimator",
    "NegativeBinomialEstimator",
    "NonstationaryGARCHEstimator",
    "NonstationaryVolatilitySummary",
    "OrthogonalityNuisanceDiagnostic",
    "PanelData",
    "PoissonRegressionEstimator",
    "PostDoubleSelectionEstimator",
    "PostLASSOEstimator",
    "PostSelectionCoverageDiagnostic",
    "PostSelectionInterval",
    "ProbitEstimator",
    "QuantileRegressionEstimator",
    "RandomEffectsEstimator",
    "RobinsonEstimator",
    "SarganHansenEstimator",
    "SparsityComplexityDiagnostic",
    "SpatialAutoregressiveEstimator",
    "StateDependentFRDEstimator",
    "StateDependentFRKDEstimator",
    "StateDependentKinkEstimator",
    "StateDependentThresholdEstimator",
    "SyntheticDiDEstimator",
    "SystemGMMEstimator",
    "ThresholdRegressionData",
    "ThresholdStateField",
    "TimeSeriesData",
    "TobitEstimator",
    "TruncatedRegressionEstimator",
    "TwoStageLeastSquaresEstimator",
    "VAREstimator",
    "VECMEstimator",
    "VolatilityBreak",
    "VolatilityBreakDetectionMethod",
    "VolatilityCoverageSummary",
    "VolatilityLossFamily",
    "VolatilityRegimeSegment",
    "WeakIVTestEstimator",
    "ZeroInflatedPoissonEstimator",
    "ensure_econometric_methods_registered",
    "register_econometric_methods",
]

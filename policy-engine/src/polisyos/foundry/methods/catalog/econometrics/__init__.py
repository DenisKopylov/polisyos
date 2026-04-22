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
from .diagnostics import (
    CointegrationTestEstimator,
    ForecastBacktestEstimator,
    HausmanTestEstimator,
    SarganHansenEstimator,
    WeakIVTestEstimator,
)
from .dynamic_panel import DifferenceGMMEstimator, SystemGMMEstimator
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
from .high_dimensional_iv import HighDimensionalPostSelectionIVEstimator
from .iv import GMMEstimator, TwoStageLeastSquaresEstimator
from .panel import FixedEffectsEstimator, RandomEffectsEstimator
from .protocols import (
    ConfidenceSetSegment,
    CrossSectionalDependenceDiagnostic,
    CoverageGuaranteeTier,
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
    "ConfidenceSetSegment",
    "CrossSectionalDependenceDiagnostic",
    "CoverageGuaranteeTier",
    "EconometricDiagnosticResult",
    "EconometricEstimator",
    "EconometricResult",
    "IdentificationDiagnostic",
    "IntervalDisagreementDiagnostic",
    "NonstationaryVolatilitySummary",
    "OrthogonalityNuisanceDiagnostic",
    "PanelData",
    "PostSelectionCoverageDiagnostic",
    "PostSelectionInterval",
    "SparsityComplexityDiagnostic",
    "ThresholdRegressionData",
    "ThresholdStateField",
    "TimeSeriesData",
    "VolatilityBreak",
    "VolatilityBreakDetectionMethod",
    "VolatilityCoverageSummary",
    "VolatilityLossFamily",
    "VolatilityRegimeSegment",
    "FixedEffectsEstimator",
    "RandomEffectsEstimator",
    "DifferenceGMMEstimator",
    "SystemGMMEstimator",
    "TwoStageLeastSquaresEstimator",
    "GMMEstimator",
    "HighDimensionalPostSelectionIVEstimator",
    "ARIMAEstimator",
    "VAREstimator",
    "QuantileRegressionEstimator",
    "EventStudyEstimator",
    "LocalProjectionsEstimator",
    "GARCHEstimator",
    "NonstationaryGARCHEstimator",
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
    "StateDependentFRDEstimator",
    "StateDependentFRKDEstimator",
    "StateDependentThresholdEstimator",
    "StateDependentKinkEstimator",
    "register_econometric_methods",
    "ensure_econometric_methods_registered",
]

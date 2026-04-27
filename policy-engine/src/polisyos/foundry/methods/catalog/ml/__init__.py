"""Expose tabular ML, uncertainty, embedding, and survival-analysis methods."""

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_ml_methods
from .advanced import GaussianProcessEstimator, NeuralODEEstimator, QuantileForestEstimator
from .clustering import KMeansEstimator
from .decomposition import PCAEstimator
from .frontier import (
    FTTransformerEstimator,
    GraphNeuralNetworkEstimator,
    MaskedAutoencoderEmbeddingEstimator,
    TabNetEstimator,
)
from .protocols import (
    CalibrationSupportDiagnostic,
    ClusteringResult,
    ConditionalCoverageDiagnostic,
    ConformalMethodSpec,
    CoverageEstimate,
    EmbeddingResult,
    ERTDiagnostic,
    GraphCoverageDiagnostic,
    GroupCoverageEstimate,
    PredictionIntervalResult,
    PredictionResult,
    PredictionResultConsumerInput,
    PredictionSetResult,
    ScoreTailDiagnostic,
    ShiftDiagnostic,
    SurvivalData,
    SurvivalResult,
    TabularData,
)
from .regression import ElasticNetEstimator, GradientBoostingEstimator, RandomForestEstimator
from .shift_diagnostics import (
    ShiftDiagnosticEstimator,
    ShiftDiagnosticInput,
    build_shift_diagnostic_report,
    build_shift_reference_comparison_reports,
)
from .survival import SurvivalAnalysisEstimator
from .transformers import TabularTransformerEstimator
from .uncertainty import (
    ConformalPredictionEstimator,
    GraphAwareConformalizer,
    MondrianAPSRAPSConformalizer,
    MondrianCQRConformalizer,
    NormalizedResidualMondrianConformalizer,
    WeightedConformalQuantile,
    evaluate_conformal_acceptance_gate,
    update_conditional_coverage_diagnostic_with_outcomes,
)


def ensure_ml_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Register built-in ML methods into `registry` or the global singleton."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_ml_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "CalibrationSupportDiagnostic",
    "ClusteringResult",
    "ConditionalCoverageDiagnostic",
    "ConformalPredictionEstimator",
    "ConformalMethodSpec",
    "CoverageEstimate",
    "ElasticNetEstimator",
    "EmbeddingResult",
    "ERTDiagnostic",
    "FTTransformerEstimator",
    "GaussianProcessEstimator",
    "GradientBoostingEstimator",
    "GraphCoverageDiagnostic",
    "GraphAwareConformalizer",
    "GraphNeuralNetworkEstimator",
    "GroupCoverageEstimate",
    "KMeansEstimator",
    "MaskedAutoencoderEmbeddingEstimator",
    "MondrianAPSRAPSConformalizer",
    "MondrianCQRConformalizer",
    "NormalizedResidualMondrianConformalizer",
    "NeuralODEEstimator",
    "PCAEstimator",
    "PredictionIntervalResult",
    "PredictionResult",
    "PredictionResultConsumerInput",
    "PredictionSetResult",
    "QuantileForestEstimator",
    "RandomForestEstimator",
    "ScoreTailDiagnostic",
    "ShiftDiagnostic",
    "ShiftDiagnosticEstimator",
    "ShiftDiagnosticInput",
    "SurvivalAnalysisEstimator",
    "SurvivalData",
    "SurvivalResult",
    "TabNetEstimator",
    "TabularData",
    "TabularTransformerEstimator",
    "WeightedConformalQuantile",
    "build_shift_diagnostic_report",
    "build_shift_reference_comparison_reports",
    "ensure_ml_methods_registered",
    "evaluate_conformal_acceptance_gate",
    "register_ml_methods",
    "update_conditional_coverage_diagnostic_with_outcomes",
]

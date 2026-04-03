"""Expose tabular ML, uncertainty, embedding, and survival-analysis methods."""
from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_ml_methods
from .advanced import GaussianProcessEstimator, NeuralODEEstimator, QuantileForestEstimator
from .clustering import KMeansEstimator
from .decomposition import PCAEstimator
from .protocols import (
    ClusteringResult,
    EmbeddingResult,
    PredictionIntervalResult,
    PredictionResult,
    SurvivalData,
    SurvivalResult,
    TabularData,
)
from .regression import ElasticNetEstimator, GradientBoostingEstimator, RandomForestEstimator
from .survival import SurvivalAnalysisEstimator
from .transformers import TabularTransformerEstimator
from .uncertainty import ConformalPredictionEstimator


def ensure_ml_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Register built-in ML methods into `registry` or the global singleton."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_ml_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "ClusteringResult",
    "ConformalPredictionEstimator",
    "ElasticNetEstimator",
    "EmbeddingResult",
    "GaussianProcessEstimator",
    "GradientBoostingEstimator",
    "KMeansEstimator",
    "NeuralODEEstimator",
    "PCAEstimator",
    "PredictionIntervalResult",
    "PredictionResult",
    "QuantileForestEstimator",
    "RandomForestEstimator",
    "SurvivalAnalysisEstimator",
    "SurvivalData",
    "SurvivalResult",
    "TabularData",
    "TabularTransformerEstimator",
    "ensure_ml_methods_registered",
    "register_ml_methods",
]

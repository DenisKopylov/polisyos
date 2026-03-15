from __future__ import annotations

from typing import Sequence

from .advanced import GaussianProcessEstimator, NeuralODEEstimator, QuantileForestEstimator
from .clustering import KMeansEstimator
from .decomposition import PCAEstimator
from .regression import (
    ElasticNetEstimator,
    GradientBoostingEstimator,
    RandomForestEstimator,
)
from .survival import SurvivalAnalysisEstimator
from .transformers import TabularTransformerEstimator
from .uncertainty import ConformalPredictionEstimator


def register_ml_methods() -> Sequence[type]:
    return (
        ElasticNetEstimator,
        RandomForestEstimator,
        GradientBoostingEstimator,
        GaussianProcessEstimator,
        QuantileForestEstimator,
        NeuralODEEstimator,
        TabularTransformerEstimator,
        ConformalPredictionEstimator,
        SurvivalAnalysisEstimator,
        PCAEstimator,
        KMeansEstimator,
    )


__all__ = ["register_ml_methods"]

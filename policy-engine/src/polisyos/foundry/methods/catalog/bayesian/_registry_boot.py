from __future__ import annotations

from typing import Sequence

from .advanced import (
    BayesianGaussianMixtureEstimator,
    BayesianHMCRegressionEstimator,
    BayesianHierarchicalRegressionEstimator,
    BayesianNUTSRegressionEstimator,
    DirichletProcessMixtureEstimator,
)
from .gp import GaussianProcessRegressionEstimator, SparseGPRegressionEstimator
from .regression import BayesianLinearRegressionEstimator
from .timeseries import BayesianAutoregressionEstimator
from .variational import BBVIEstimator, MeanFieldVIEstimator


def register_bayesian_methods() -> Sequence[type]:
    return (
        BayesianLinearRegressionEstimator,
        BayesianAutoregressionEstimator,
        BayesianHierarchicalRegressionEstimator,
        BayesianHMCRegressionEstimator,
        BayesianNUTSRegressionEstimator,
        BayesianGaussianMixtureEstimator,
        DirichletProcessMixtureEstimator,
        # Phase SOTA additions
        GaussianProcessRegressionEstimator,
        SparseGPRegressionEstimator,
        MeanFieldVIEstimator,
        BBVIEstimator,
    )


__all__ = ["register_bayesian_methods"]

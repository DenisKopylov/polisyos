"""Expose posterior-inference and Bayesian regression/mixture methods."""
from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from .advanced import (
    BayesianGaussianMixtureEstimator,
    BayesianHMCRegressionEstimator,
    BayesianHierarchicalRegressionEstimator,
    BayesianNUTSRegressionEstimator,
    DirichletProcessMixtureEstimator,
)
from ._registry_boot import register_bayesian_methods
from .frontier import (
    AffineNormalizingFlowPosteriorAdapter,
    BayesianBARTRegressorEstimator,
    ExpectationPropagationGaussianEstimator,
    FactorGraphBeliefPropagationEstimator,
    SimulationBasedNLEEstimator,
    SimulationBasedNPEEstimator,
    SimulationBasedNREEstimator,
    SVGDRegressionEstimator,
)
from .protocols import PosteriorResult, TruthfulnessEvidence, TruthfulnessTier
from .regression import BayesianLinearRegressionEstimator
from .timeseries import BayesianAutoregressionEstimator


def ensure_bayesian_methods_registered(registry: MethodRegistry | None = None) -> None:
    """Register built-in Bayesian methods into `registry` or the global singleton."""
    reg = registry if registry is not None else MethodRegistry.get_instance()
    for method_class in register_bayesian_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "AffineNormalizingFlowPosteriorAdapter",
    "BayesianAutoregressionEstimator",
    "BayesianBARTRegressorEstimator",
    "BayesianGaussianMixtureEstimator",
    "BayesianHMCRegressionEstimator",
    "BayesianHierarchicalRegressionEstimator",
    "BayesianNUTSRegressionEstimator",
    "BayesianLinearRegressionEstimator",
    "DirichletProcessMixtureEstimator",
    "ExpectationPropagationGaussianEstimator",
    "FactorGraphBeliefPropagationEstimator",
    "PosteriorResult",
    "SimulationBasedNLEEstimator",
    "SimulationBasedNPEEstimator",
    "SimulationBasedNREEstimator",
    "SVGDRegressionEstimator",
    "TruthfulnessEvidence",
    "TruthfulnessTier",
    "ensure_bayesian_methods_registered",
    "register_bayesian_methods",
]

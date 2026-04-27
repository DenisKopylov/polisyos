"""Expose posterior-inference and Bayesian regression/mixture methods."""

from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_bayesian_methods
from .advanced import (
    BayesianGaussianMixtureEstimator,
    BayesianHierarchicalRegressionEstimator,
    BayesianHMCRegressionEstimator,
    BayesianNUTSRegressionEstimator,
    DirichletProcessMixtureEstimator,
)
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
from .pmd_hmc import (
    PmdHmcBenchmarkCase,
    assess_pmd_hmc_multimodality,
    build_pmd_hmc_benchmark_suite,
    run_pmd_hmc_benchmark,
)
from .protocols import (
    MultimodalityState,
    MultimodalityStatus,
    PosteriorModeSummary,
    PosteriorResult,
    PriorSensitivityReport,
    SimulatorDiagnosticArtifact,
    TruthfulnessEvidence,
    TruthfulnessTier,
    canonical_simulator_diagnostic_artifact,
)
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
    "BayesianLinearRegressionEstimator",
    "BayesianNUTSRegressionEstimator",
    "DirichletProcessMixtureEstimator",
    "ExpectationPropagationGaussianEstimator",
    "FactorGraphBeliefPropagationEstimator",
    "MultimodalityState",
    "MultimodalityStatus",
    "PmdHmcBenchmarkCase",
    "PosteriorResult",
    "PosteriorModeSummary",
    "PriorSensitivityReport",
    "SVGDRegressionEstimator",
    "SimulatorDiagnosticArtifact",
    "SimulationBasedNLEEstimator",
    "SimulationBasedNPEEstimator",
    "SimulationBasedNREEstimator",
    "TruthfulnessEvidence",
    "TruthfulnessTier",
    "canonical_simulator_diagnostic_artifact",
    "assess_pmd_hmc_multimodality",
    "build_pmd_hmc_benchmark_suite",
    "run_pmd_hmc_benchmark",
    "ensure_bayesian_methods_registered",
    "register_bayesian_methods",
]

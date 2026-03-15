from __future__ import annotations

from polisyos.foundry.methods.exceptions import MethodAlreadyRegisteredError
from polisyos.foundry.methods.registry import MethodRegistry

from ._registry_boot import register_bayesian_methods
from .protocols import PosteriorResult
from .regression import BayesianLinearRegressionEstimator
from .timeseries import BayesianAutoregressionEstimator


def ensure_bayesian_methods_registered(registry: MethodRegistry | None = None) -> None:
    reg = registry or MethodRegistry.get_instance()
    for method_class in register_bayesian_methods():
        try:
            reg.register(method_class)
        except MethodAlreadyRegisteredError:
            continue


__all__ = [
    "BayesianAutoregressionEstimator",
    "BayesianLinearRegressionEstimator",
    "PosteriorResult",
    "ensure_bayesian_methods_registered",
    "register_bayesian_methods",
]

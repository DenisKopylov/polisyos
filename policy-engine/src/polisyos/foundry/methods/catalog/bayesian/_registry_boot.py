from __future__ import annotations

from typing import Sequence

from .regression import BayesianLinearRegressionEstimator
from .timeseries import BayesianAutoregressionEstimator


def register_bayesian_methods() -> Sequence[type]:
    return (
        BayesianLinearRegressionEstimator,
        BayesianAutoregressionEstimator,
    )


__all__ = ["register_bayesian_methods"]

from __future__ import annotations

from typing import Sequence

from .diagnostics import (
    CalibrationDiagnosticEstimator,
    CrossValidationEstimator,
    WalkForwardEstimator,
)
from .scoring import ProbabilisticScoringEstimator


def register_validation_methods() -> Sequence[type]:
    return (
        ProbabilisticScoringEstimator,
        CrossValidationEstimator,
        WalkForwardEstimator,
        CalibrationDiagnosticEstimator,
    )


__all__ = ["register_validation_methods"]

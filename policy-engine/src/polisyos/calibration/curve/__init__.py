"""Public types and interval-coverage curve API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CalibrationPoint:
    """One point on the calibration curve."""

    nominal_level: float
    empirical_coverage: float
    n_observations: int


@dataclass(frozen=True)
class CalibrationResult:
    """Full calibration curve with miscalibration metrics."""

    points: list[CalibrationPoint]
    ece: float | None
    max_ce: float | None
    is_well_calibrated: bool
    evaluation_status: Literal["evaluated", "incomplete", "not_evaluated"] = "evaluated"
    n_comparisons: int = 0


# Import after the public models to break the implementation/type cycle.
from polisyos.calibration.curve._compute import compute_calibration_curve  # noqa: E402

# Preserve the historical callable FQN for serialized references.
compute_calibration_curve.__module__ = __name__

__all__ = ["CalibrationPoint", "CalibrationResult", "compute_calibration_curve"]

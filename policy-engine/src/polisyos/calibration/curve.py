"""Calibration curve analysis for prediction intervals."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


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
    ece: float
    max_ce: float
    is_well_calibrated: bool


def compute_calibration_curve(
    y_true: list[float],
    intervals: list[list[tuple[float, float]]],
    *,
    levels: list[float] | None = None,
    tolerance: float = 0.05,
) -> CalibrationResult:
    """Compute calibration curve from prediction intervals at multiple levels."""
    if levels is None:
        n = len(intervals)
        levels = [round(0.1 + 0.8 * i / max(n - 1, 1), 2) for i in range(n)]

    arr_true = np.asarray(y_true, dtype=float)
    points: list[CalibrationPoint] = []

    for level, interval_set in zip(levels, intervals, strict=False):
        if not interval_set or len(interval_set) != len(arr_true):
            continue
        covered = 0
        for index, (lower, upper) in enumerate(interval_set):
            if lower <= arr_true[index] <= upper:
                covered += 1
        empirical_coverage = covered / len(arr_true) if len(arr_true) > 0 else 0.0
        points.append(
            CalibrationPoint(
                nominal_level=level,
                empirical_coverage=empirical_coverage,
                n_observations=len(arr_true),
            )
        )

    if not points:
        return CalibrationResult(points=[], ece=0.0, max_ce=0.0, is_well_calibrated=True)

    deviations = [abs(point.empirical_coverage - point.nominal_level) for point in points]
    ece = float(np.mean(deviations))
    max_ce = float(max(deviations))

    return CalibrationResult(
        points=points,
        ece=ece,
        max_ce=max_ce,
        is_well_calibrated=max_ce <= tolerance,
    )


__all__ = [
    "CalibrationPoint",
    "CalibrationResult",
    "compute_calibration_curve",
]

"""Calibration curve analysis for prediction intervals."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class CalibrationPoint:
    """One point on the calibration curve."""

    nominal_level: float
    empirical_coverage: float
    n_observations: int


@dataclass(frozen=True)
class CalibrationResult:
    """Full calibration curve with miscalibration metric."""

    points: list[CalibrationPoint]
    ece: float  # Expected Calibration Error
    max_ce: float  # Maximum Calibration Error
    is_well_calibrated: bool


def compute_calibration_curve(
    y_true: list[float],
    intervals: list[list[tuple[float, float]]],
    *,
    levels: list[float] | None = None,
    tolerance: float = 0.05,
) -> CalibrationResult:
    """Compute calibration curve from prediction intervals at multiple levels.

    Parameters
    ----------
    y_true:
        Ground-truth values.
    intervals:
        List of interval sets, one per confidence level.
        Each is a list of (lower, upper) tuples aligned with y_true.
    levels:
        Nominal confidence levels corresponding to each interval set.
        Defaults to evenly spaced from 0.1 to 0.9.
    tolerance:
        Max acceptable deviation for "well-calibrated" assessment.
    """
    if levels is None:
        n = len(intervals)
        levels = [round(0.1 + 0.8 * i / max(n - 1, 1), 2) for i in range(n)]

    arr_true = np.asarray(y_true, dtype=float)
    points: list[CalibrationPoint] = []

    for level, interval_set in zip(levels, intervals):
        if not interval_set or len(interval_set) != len(arr_true):
            continue
        covered = 0
        for i, (lo, hi) in enumerate(interval_set):
            if lo <= arr_true[i] <= hi:
                covered += 1
        emp = covered / len(arr_true) if len(arr_true) > 0 else 0.0
        points.append(CalibrationPoint(
            nominal_level=level,
            empirical_coverage=emp,
            n_observations=len(arr_true),
        ))

    if not points:
        return CalibrationResult(points=[], ece=0.0, max_ce=0.0, is_well_calibrated=True)

    deviations = [abs(p.empirical_coverage - p.nominal_level) for p in points]
    ece = float(np.mean(deviations))
    max_ce = float(max(deviations))

    return CalibrationResult(
        points=points,
        ece=ece,
        max_ce=max_ce,
        is_well_calibrated=max_ce <= tolerance,
    )

from __future__ import annotations

import numpy as np
import pytest
from polisyos.foundry.calibration.robust_set_selector import (
    gaussian_parametric_radius,
    select_robust_set_size,
)
from polisyos.ir.analytics.uncertainty import (
    RobustSetAdequacyStatus,
    RobustSetCalibrationMethod,
    RobustSetCalibrationStatus,
    RobustSetFamily,
    RobustSetSpec,
)


def _quadratic_loss(solution: np.ndarray, theta: np.ndarray) -> float:
    return float(0.5 * np.sum((solution - theta) ** 2))


def _solve_nominal(center: np.ndarray) -> np.ndarray:
    return np.asarray(center, dtype=float)


def _solve_box_robust(spec: RobustSetSpec) -> np.ndarray:
    center = np.asarray(spec.center, dtype=float)
    scale_diag = np.asarray(spec.scale_diag, dtype=float)
    return np.maximum(center - spec.size_parameter * scale_diag, 0.0)


def _solve_ellipsoid_robust(spec: RobustSetSpec) -> np.ndarray:
    center = np.asarray(spec.center, dtype=float)
    return center / (1.0 + float(spec.size_parameter))


def test_coverage_monotonicity_for_box_selector() -> None:
    rng = np.random.default_rng(123)
    theta_samples = rng.normal(loc=1.0, scale=0.2, size=(120, 4))

    report = select_robust_set_size(
        theta_samples,
        coverage_target=0.8,
        inflation_budget=None,
        family=RobustSetFamily.BOX,
        solve_nominal=_solve_nominal,
        solve_robust=_solve_box_robust,
        loss_fn=_quadratic_loss,
        seed=5,
    )

    coverages = [point.coverage_emp for point in report.empirical_frontier]

    assert report.status in {
        RobustSetCalibrationStatus.OK,
        RobustSetCalibrationStatus.INFEASIBLE_TARGET_PAIR,
    }
    assert coverages == sorted(coverages)


def test_selector_returns_infeasible_target_pair_when_budget_too_small() -> None:
    rng = np.random.default_rng(321)
    theta_samples = rng.normal(loc=1.5, scale=0.25, size=(150, 3))

    report = select_robust_set_size(
        theta_samples,
        coverage_target=0.9,
        inflation_budget=0.0,
        family=RobustSetFamily.BOX,
        solve_nominal=_solve_nominal,
        solve_robust=_solve_box_robust,
        loss_fn=_quadratic_loss,
        seed=11,
    )

    assert report.status is RobustSetCalibrationStatus.INFEASIBLE_TARGET_PAIR
    assert report.adequacy_status is RobustSetAdequacyStatus.OVERCONSERVATIVE
    assert report.selected_size is None


def test_selector_reports_undercoverage_when_grid_never_reaches_target() -> None:
    rng = np.random.default_rng(12)
    theta_samples = rng.normal(loc=0.0, scale=1.0, size=(160, 2))

    report = select_robust_set_size(
        theta_samples,
        coverage_target=0.95,
        inflation_budget=None,
        family=RobustSetFamily.BOX,
        solve_nominal=_solve_nominal,
        solve_robust=_solve_box_robust,
        loss_fn=_quadratic_loss,
        seed=13,
        rho_factors=(0.01, 0.02),
    )

    assert report.status is RobustSetCalibrationStatus.INFEASIBLE_TARGET_PAIR
    assert report.adequacy_status is RobustSetAdequacyStatus.UNDERCOVERAGE


def test_ellipsoid_selector_handles_small_n_with_shrinkage_covariance() -> None:
    rng = np.random.default_rng(77)
    theta_samples = rng.normal(loc=0.5, scale=0.3, size=(9, 10))

    report = select_robust_set_size(
        theta_samples,
        coverage_target=0.75,
        inflation_budget=None,
        family=RobustSetFamily.ELLIPSOID,
        solve_nominal=_solve_nominal,
        solve_robust=_solve_ellipsoid_robust,
        loss_fn=_quadratic_loss,
        seed=19,
    )

    assert report.status is not RobustSetCalibrationStatus.INSUFFICIENT_DATA
    assert report.metadata["shrinkage_applied"] is True


def test_gaussian_parametric_box_radius_matches_formula() -> None:
    radius = gaussian_parametric_radius(
        family=RobustSetFamily.BOX,
        dimension=1,
        coverage_target=0.95,
    )

    assert radius == pytest.approx(1.95996398454)


def test_gaussian_parametric_selector_records_assumption() -> None:
    rng = np.random.default_rng(101)
    theta_samples = rng.normal(loc=1.0, scale=0.1, size=(180, 3))

    report = select_robust_set_size(
        theta_samples,
        coverage_target=0.8,
        inflation_budget=None,
        family=RobustSetFamily.BOX,
        solve_nominal=_solve_nominal,
        solve_robust=_solve_box_robust,
        loss_fn=_quadratic_loss,
        calibration_method=RobustSetCalibrationMethod.GAUSSIAN_PARAMETRIC,
        seed=17,
    )

    assert "gaussian_parametric_radius" in report.assumptions

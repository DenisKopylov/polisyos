"""Behavioral controls for the native sharp-RD CCT robust-bias profile."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import rdd
from polisyos.foundry.methods.catalog.causal.protocols import RDDObservationalData
from polisyos.ir.analytics.causal import EstimationStatus


def _data() -> RDDObservationalData:
    x = np.linspace(-1.0, 1.0, 600)
    y = 1.0 + 0.4 * x + np.where(x < 0.0, 2.0 * x**2, 3.0 + 6.0 * x**2)
    return RDDObservationalData(running_variable=x, outcome=y, cutoff=0.0)


def _params(**overrides: object) -> dict[str, object]:
    return {
        "bias_correction": True,
        "bandwidth": 0.45,
        "bias_bandwidth": 0.65,
        "polynomial_order": 1,
        "bias_polynomial_order": 2,
        "kernel": "triangular",
        "vce": "hc0",
        "masspoints": "off",
        "bandwidth_selector": "fixed",
        "design": "sharp",
        "confidence_level": 0.95,
        "manipulation_test": False,
        **overrides,
    }


def test_rbc_removes_known_leading_curvature_bias() -> None:
    data = _data()
    corrected = rdd.RegressionDiscontinuity.pure_step(data, _params())["report"]
    conventional = rdd.RegressionDiscontinuity.pure_step(data, _params(bias_correction=False))[
        "report"
    ]
    assert corrected.status is EstimationStatus.SUCCESS
    assert corrected.point_estimate == pytest.approx(3.0, abs=1e-11)
    assert abs(conventional.point_estimate - 3.0) > 0.03
    assert corrected.method_params["tau_us"] == pytest.approx(conventional.point_estimate)
    assert corrected.method_params["bias"] == pytest.approx(
        conventional.point_estimate - corrected.point_estimate
    )


@pytest.mark.parametrize("level", [0.8, 0.95, 0.99])
def test_rbc_interval_uses_robust_se_and_requested_level(level: float) -> None:
    from statistics import NormalDist

    data = _data()
    data = data.model_copy(
        update={"outcome": data.outcome + 0.15 * np.sin(71 * data.running_variable)}
    )
    report = rdd.RegressionDiscontinuity.pure_step(data, _params(confidence_level=level))["report"]
    assert report.status is EstimationStatus.SUCCESS
    assert report.standard_error > 0.0
    z = NormalDist().inv_cdf((1.0 + level) / 2.0)
    assert report.confidence_interval == pytest.approx(
        (
            report.point_estimate - z * report.standard_error,
            report.point_estimate + z * report.standard_error,
        ),
        rel=1e-11,
    )
    assert report.method_params["confidence_procedure"] == "cct_rbc_normal_two_sided"


@pytest.mark.parametrize(
    "settings",
    [
        {"bandwidth": 0.0},
        {"bandwidth": float("nan")},
        {"bandwidth": float("inf")},
        {"bias_bandwidth": -1.0},
        {"bias_bandwidth": None},
        {"bias_polynomial_order": 1},
        {"bias_polynomial_order": True},
        {"vce": "nn"},
        {"masspoints": "adjust"},
        {"bandwidth_selector": "mserd"},
        {"confidence_level": 0.0},
        {"confidence_level": 1.0},
        {"confidence_level": float("nan")},
        {"confidence_level": float("inf")},
    ],
)
def test_unsupported_rbc_settings_do_not_emit_inference(settings: dict[str, object]) -> None:
    report = rdd.RegressionDiscontinuity.pure_step(_data(), _params(**settings))["report"]
    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None
    assert report.confidence_interval is None


def test_fuzzy_design_without_treatment_input_is_typed_limited() -> None:
    report = rdd.RegressionDiscontinuity.pure_step(_data(), _params(design="fuzzy"))["report"]
    assert report.status is EstimationStatus.ASSUMPTION_FAILED
    assert report.point_estimate is None
    assert "treatment" in report.status_reason


def test_rbc_row_permutation_and_recomputed_input_binding() -> None:
    data = _data()
    before = rdd.RegressionDiscontinuity.pure_step(data, _params())["report"]
    perm = np.random.default_rng(123).permutation(data.sample_size)
    permuted = RDDObservationalData(
        running_variable=data.running_variable[perm], outcome=data.outcome[perm], cutoff=data.cutoff
    )
    after = rdd.RegressionDiscontinuity.pure_step(permuted, _params())["report"]
    assert before.status is after.status is EstimationStatus.SUCCESS
    assert after.point_estimate == pytest.approx(before.point_estimate, abs=1e-11)
    assert after.standard_error == pytest.approx(before.standard_error, abs=1e-11)
    assert after.method_params["input_sha256"] != before.method_params["input_sha256"]


def test_registered_rbc_survives_cas_and_fresh_typed_reader(tmp_path: Path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.causal import ensure_causal_methods_registered
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.ir.analytics.causal import (
        load_causal_effect_report,
        persist_causal_effect_report,
    )

    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    try:
        ensure_causal_methods_registered()
        method = MethodRegistry.get_instance().get(
            "causal.inference.regression_discontinuity@1.0.0"
        )
        data = _data()
        data = data.model_copy(
            update={"outcome": data.outcome + 0.15 * np.sin(71 * data.running_variable)}
        )
        result = MethodDispatcher.get_instance().dispatch(
            method_class=method, signature=method.signature, state=data, params=_params(), seed=73
        )
        report = result.output["report"]
        artifact = persist_causal_effect_report(FileSystemCAS(tmp_path), report)
        loaded = load_causal_effect_report(FileSystemCAS(tmp_path), artifact)
        assert loaded is not report
        assert loaded.status is EstimationStatus.SUCCESS
        assert loaded.point_estimate == report.point_estimate
        assert loaded.standard_error == report.method_params["se_rb"]
        assert loaded.confidence_interval == report.confidence_interval
        assert loaded.method_params == report.method_params
        assert loaded.to_uncertainty_envelope().confidence_level == pytest.approx(0.95)
    finally:
        MethodRegistry.reset_instance()
        MethodDispatcher.reset_instance()


def test_rbc_never_materializes_a_diagonal_weight_matrix(monkeypatch: pytest.MonkeyPatch) -> None:
    original_solve = np.linalg.solve
    shapes: list[tuple[int, ...]] = []

    def record_solve(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        shapes.append(a.shape)
        return original_solve(a, b)

    def reject_diagonal(*args: object, **kwargs: object) -> np.ndarray:
        raise AssertionError("RBC must use vector weights, not an n-by-n diagonal")

    monkeypatch.setattr(np.linalg, "solve", record_solve)
    monkeypatch.setattr(np, "diag", reject_diagonal)
    report = rdd.RegressionDiscontinuity.pure_step(_data(), _params())["report"]
    assert report.status is EstimationStatus.SUCCESS
    assert shapes == [(2, 2), (3, 3), (2, 2), (3, 3)]


def test_deleted_correction_can_keep_rbc_markers_but_loses_known_jump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = rdd._fit_rbc_polynomial

    def removed(*args: object, **kwargs: object) -> tuple[float, float, float, float, int, int]:
        us, _, variance_us, _, n_h, n_b = original(*args, **kwargs)
        return us, us, variance_us, variance_us, n_h, n_b

    monkeypatch.setattr(rdd, "_fit_rbc_polynomial", removed)
    report = rdd.RegressionDiscontinuity.pure_step(_data(), _params())["report"]
    assert report.status is EstimationStatus.SUCCESS
    assert report.method_params["bias_correction"] is True
    assert report.method_params["profile"] == "sharp_cct_rbc_hc0_fixed"
    assert abs(report.point_estimate - 3.0) > 0.03


def test_input_cutoff_change_changes_target_and_content_binding() -> None:
    data = _data()
    original = rdd.RegressionDiscontinuity.pure_step(data, _params())["report"]
    shifted = rdd.RegressionDiscontinuity.pure_step(
        data.model_copy(update={"cutoff": 0.3}), _params()
    )["report"]
    assert shifted.status is EstimationStatus.SUCCESS
    assert shifted.method_params["cutoff"] == 0.3
    assert shifted.method_params["input_sha256"] != original.method_params["input_sha256"]
    assert abs(shifted.point_estimate - original.point_estimate) > 0.5


def test_first_rbc_profile_refuses_mass_points_and_sparse_bias_support() -> None:
    data = _data()
    tied = data.running_variable.copy()
    tied[1] = tied[0]
    for sample, params in [
        (data.model_copy(update={"running_variable": tied}), _params()),
        (data, _params(bias_bandwidth=0.002)),
    ]:
        report = rdd.RegressionDiscontinuity.pure_step(sample, params)["report"]
        assert report.status is EstimationStatus.NUMERICAL_FAILURE
        assert report.point_estimate is None


@pytest.mark.parametrize("kernel", ["uniform", "triangular", "epanechnikov"])
@pytest.mark.parametrize("order", [1, 2])
def test_conventional_profile_matches_diagonal_oracle_and_permutation(
    kernel: str, order: int
) -> None:
    data = _data()
    y = data.outcome + 0.15 * np.sin(71 * data.running_variable)
    x = data.running_variable
    for side in ["left", "right"]:
        select = (x < 0.0) if side == "left" else (x >= 0.0)
        z = x[select]
        v = y[select]
        u = np.abs(z / 0.7)
        if kernel == "uniform":
            weights = (u <= 1).astype(float)
        elif kernel == "triangular":
            weights = np.maximum(1 - u, 0)
        else:
            weights = np.where(u <= 1, 0.75 * (1 - u**2), 0.0)
        keep = weights > 0
        z, v, weights = z[keep], v[keep], weights[keep]
        design = np.vander(z, order + 1, increasing=True)
        diagonal = np.diag(weights)
        inverse = np.linalg.inv(design.T @ diagonal @ design)
        beta = inverse @ design.T @ diagonal @ v
        residual = v - design @ beta
        covariance = float(residual @ diagonal @ residual / (len(z) - order - 1)) * inverse
        expected = (beta[0], np.sqrt(covariance[0, 0]), float(len(z)))
        actual = rdd._fit_local_polynomial(
            x, y, cutoff_side=side, poly_order=order, kernel=kernel, bandwidth=0.7
        )
        assert actual == pytest.approx(expected, rel=1e-10, abs=1e-10)
        perm = np.random.default_rng(321).permutation(len(x))
        shuffled = rdd._fit_local_polynomial(
            x[perm], y[perm], cutoff_side=side, poly_order=order, kernel=kernel, bandwidth=0.7
        )
        assert shuffled == pytest.approx(expected, rel=1e-10, abs=1e-10)

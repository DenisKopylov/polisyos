"""Independent fixed-bandwidth kernel-HC0 and legacy RDD compatibility controls."""

from __future__ import annotations

from statistics import NormalDist
from typing import Any

import numpy as np
import pytest

from polisyos.foundry.methods.catalog.causal import rdd
from polisyos.foundry.methods.catalog.causal.protocols import RDDObservationalData
from polisyos.ir.analytics.causal import EstimationStatus


def _data(*, scale: float = 1.0, cutoff: float = 0.0) -> RDDObservationalData:
    coordinate = np.linspace(-0.99, 0.99, 120)
    outcome = (
        1.0
        + 0.3 * coordinate
        + 3.0 * (coordinate >= 0.0)
        + 0.2 * np.sin(31.0 * coordinate)
        + 0.1 * coordinate**2
    )
    return RDDObservationalData(
        running_variable=cutoff + coordinate * scale, outcome=outcome, cutoff=cutoff
    )


def _weights(coordinate: np.ndarray, kernel: str) -> np.ndarray:
    absolute = np.abs(coordinate)
    if kernel == "uniform":
        return (absolute <= 1.0).astype(float)
    if kernel == "epanechnikov":
        return np.where(absolute <= 1.0, 0.75 * (1.0 - absolute**2), 0.0)
    return np.maximum(1.0 - absolute, 0.0)


def _reference_side(
    data: RDDObservationalData, *, side: str, kernel: str, order: int, bandwidth: float
) -> tuple[float, float, float, np.ndarray, np.ndarray]:
    centered = data.running_variable - data.cutoff
    selected = centered >= 0.0 if side == "right" else centered < 0.0
    coordinate = centered[selected] / bandwidth
    outcome = data.outcome[selected]
    weight = _weights(coordinate, kernel)
    keep = weight > 0.0
    coordinate, outcome, weight = coordinate[keep], outcome[keep], weight[keep]
    design = np.vander(coordinate, order + 1, increasing=True)
    # Test-only small Gram inverse is independent of the production economy-SVD solve.
    inverse = np.linalg.inv(design.T @ (weight[:, None] * design))
    linear_map = inverse @ (design.T * weight)
    coefficients = linear_map @ outcome
    residual = outcome - design @ coefficients
    sensitivity = linear_map[0]
    hc0_se = float(np.sqrt(np.sum((sensitivity * residual) ** 2)))
    legacy_se = float(
        np.sqrt(np.sum(weight * residual**2) / (len(outcome) - order - 1) * inverse[0, 0])
    )
    return float(coefficients[0]), hc0_se, legacy_se, sensitivity, keep


def _report(data: RDDObservationalData, **parameters: Any):
    return rdd.KernelHC0RegressionDiscontinuity.pure_step(
        data, {"bandwidth": 0.7, "manipulation_test": False, **parameters}
    )["report"]


@pytest.mark.parametrize("kernel", ["triangular", "epanechnikov", "uniform"])
@pytest.mark.parametrize("order", [1, 2])
def test_kernel_hc0_matches_independent_sandwich_and_preserves_legacy(
    kernel: str, order: int
) -> None:
    data = _data()
    expected = [
        _reference_side(data, side=side, kernel=kernel, order=order, bandwidth=0.7)
        for side in ("left", "right")
    ]
    current = _report(data, kernel=kernel, polynomial_order=order)
    legacy = rdd.RegressionDiscontinuity.pure_step(
        data,
        {"bandwidth": 0.7, "kernel": kernel, "polynomial_order": order, "manipulation_test": False},
    )["report"]
    assert current.status is legacy.status is EstimationStatus.SUCCESS
    assert current.point_estimate == pytest.approx(expected[1][0] - expected[0][0], abs=3e-11)
    assert current.standard_error == pytest.approx(
        np.hypot(expected[0][1], expected[1][1]), rel=3e-10, abs=3e-12
    )
    assert legacy.standard_error == pytest.approx(
        np.hypot(expected[0][2], expected[1][2]), rel=3e-10, abs=3e-12
    )
    assert current.standard_error != pytest.approx(legacy.standard_error, rel=1e-3)
    assert current.method_params["variance_profile"] == "kernel_hc0"
    assert current.method_params["estimator_version"] == "1.1.0"
    assert legacy.method_params["variance_profile"] == "weighted_residual_homoskedastic"
    assert legacy.method_params["estimator_version"] == "1.0.0"
    assert current.method_params["bias_correction"] is False
    assert current.to_uncertainty_envelope().gate_eligible is False


@pytest.mark.parametrize("scale", [1e-140, 1e-8, 1.0, 1e140])
@pytest.mark.parametrize("order", [1, 2])
def test_kernel_hc0_unit_and_permutation_invariance(scale: float, order: int) -> None:
    data = _data(scale=scale)
    original = _report(_data(), polynomial_order=order)
    current = _report(data, bandwidth=0.7 * scale, polynomial_order=order)
    permutation = np.random.default_rng(716).permutation(data.sample_size)
    shuffled = _report(
        RDDObservationalData(
            running_variable=data.running_variable[permutation],
            outcome=data.outcome[permutation],
            cutoff=data.cutoff,
        ),
        bandwidth=0.7 * scale,
        polynomial_order=order,
    )
    for report in (current, shuffled):
        assert report.status is EstimationStatus.SUCCESS
        assert report.point_estimate == pytest.approx(original.point_estimate, abs=3e-11)
        assert report.standard_error == pytest.approx(original.standard_error, rel=3e-10)
        assert report.diagnostics[0].statistic == original.diagnostics[0].statistic
    assert shuffled.method_params["input_sha256"] != current.method_params["input_sha256"]


def test_translation_and_cutoff_are_preserved() -> None:
    original = _report(_data())
    translated = _report(_data(scale=10.0, cutoff=2.0), bandwidth=7.0)
    assert translated.point_estimate == pytest.approx(original.point_estimate, abs=3e-11)
    assert translated.standard_error == pytest.approx(original.standard_error, rel=3e-10)
    assert translated.method_params["cutoff"] == 2.0


def test_known_diagonal_noise_covariance_uses_squared_localization_weights() -> None:
    """A linear estimator's exact known-noise variance is not sigma2 inverse-Gram."""
    data = _data()
    expected_point, _, _, sensitivity, keep = _reference_side(
        data, side="right", kernel="triangular", order=1, bandwidth=0.7
    )
    centered = data.running_variable - data.cutoff
    side_indices = np.flatnonzero(centered >= 0.0)[keep]
    # The independent weights arise from the exact finite-design linear map;
    # each actual output is measured with a different unit response vector.
    actual_sensitivity = []
    for index in side_indices:
        unit_response = np.zeros(data.sample_size)
        unit_response[index] = 1.0
        point, _, _ = rdd._fit_local_polynomial(
            centered,
            unit_response,
            cutoff_side="right",
            poly_order=1,
            kernel="triangular",
            bandwidth=0.7,
            variance_profile="kernel_hc0",
        )
        actual_sensitivity.append(point)
    actual_sensitivity = np.asarray(actual_sensitivity)
    known_variance = np.linspace(0.04, 0.25, len(sensitivity))
    assert actual_sensitivity == pytest.approx(sensitivity, rel=3e-10, abs=3e-12)
    assert float(np.sum(actual_sensitivity**2 * known_variance)) == pytest.approx(
        float(np.sum(sensitivity**2 * known_variance)), rel=3e-10
    )
    assert float(actual_sensitivity @ data.outcome[side_indices]) == pytest.approx(
        expected_point, abs=3e-11
    )
    # Exact homoskedastic diagonal noise still requires W squared between B factors.
    coordinate = centered[side_indices] / 0.7
    design = np.column_stack((np.ones_like(coordinate), coordinate))
    weights = _weights(coordinate, "triangular")
    inverse = np.linalg.inv(design.T @ (weights[:, None] * design))
    exact = float(np.sum(sensitivity**2))
    assert exact != pytest.approx(float(inverse[0, 0]), rel=1e-3)


def test_kernel_covariance_removal_is_detected_with_unchanged_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _data()
    expected = _report(data)
    original = rdd._fit_local_polynomial

    def legacy_covariance(*args: Any, **kwargs: Any):
        return original(*args, **{**kwargs, "variance_profile": "weighted_residual_homoskedastic"})

    monkeypatch.setattr(rdd, "_fit_local_polynomial", legacy_covariance)
    mutant = _report(data)
    assert mutant.method_params["variance_profile"] == expected.method_params["variance_profile"]
    assert mutant.point_estimate == pytest.approx(expected.point_estimate, abs=3e-11)
    with pytest.raises(AssertionError):
        assert mutant.standard_error == pytest.approx(expected.standard_error, rel=3e-10)


@pytest.mark.parametrize(
    "change",
    [
        {"bandwidth": None},
        {"bandwidth_selector": "mserd"},
        {"vce": "cluster"},
        {"cluster": "unit"},
        {"masspoints": "adjust"},
        {"variance_profile": "weighted_residual_homoskedastic"},
    ],
)
def test_new_profile_cannot_silently_use_legacy_or_unsupported_inference(
    change: dict[str, Any],
) -> None:
    report = _report(_data(), **change)
    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None


@pytest.mark.parametrize("level", [0.8, 0.95, 0.99, np.nextafter(1.0, 0.0)])
def test_conventional_normal_interval_uses_representable_lower_tail(level: float) -> None:
    report = _report(_data(), confidence_level=float(level))
    assert report.status is EstimationStatus.SUCCESS
    assert report.confidence_interval[0] < report.point_estimate < report.confidence_interval[1]
    assert np.isfinite(report.confidence_interval).all()
    expected = float(NormalDist().inv_cdf((1.0 - level) / 2.0))
    assert report.confidence_interval == pytest.approx(
        (
            report.point_estimate + expected * report.standard_error,
            report.point_estimate - expected * report.standard_error,
        ),
        abs=3e-12,
    )


@pytest.mark.parametrize("level", [0.0, 1.0, np.nan, np.inf, np.nextafter(0.0, 1.0)])
def test_invalid_or_unrepresentable_level_is_refused_before_fit(
    level: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_fit(*args: Any, **kwargs: Any):
        raise AssertionError("invalid level must be rejected before numerical fitting")

    monkeypatch.setattr(rdd, "_fit_local_polynomial", no_fit)
    report = _report(_data(), confidence_level=float(level))
    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.confidence_interval is None


def test_positive_se_with_unrepresentable_interval_is_not_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unrepresentable_fit(*args: Any, **kwargs: Any):
        return 1e308 if kwargs["cutoff_side"] == "right" else 0.0, 1e307, 30.0

    monkeypatch.setattr(rdd, "_fit_local_polynomial", unrepresentable_fit)
    report = _report(_data(), confidence_level=float(np.nextafter(1.0, 0.0)))
    assert report.status is EstimationStatus.NUMERICAL_FAILURE
    assert report.point_estimate == 1e308
    assert report.standard_error == pytest.approx(np.hypot(1e307, 1e307))
    assert report.confidence_interval is None
    assert report.confidence_level is None
    assert report.to_uncertainty_envelope().gate_eligible is False
    assert "representable" in report.status_reason


def test_exact_rational_triangular_noise_oracle_distinguishes_inverse_gram() -> None:
    """Twelve fixed points have per-side known-noise variance exactly127/286."""
    from fractions import Fraction

    positive = np.arange(1, 13, dtype=float) / 13.0
    coordinate = np.concatenate((-positive, positive))
    rational_weights = [Fraction((13 - index) * (13 - 2 * index), 286) for index in range(1, 13)]
    exact_known_noise = sum(weight**2 for weight in rational_weights)
    assert exact_known_noise == Fraction(127, 286)
    side_variances = []
    legacy_variances = []
    for side, indices in (("left", range(12)), ("right", range(12, 24))):
        sensitivities = []
        unit_legacy_estimates = []
        for index in indices:
            outcome = np.zeros(24)
            outcome[index] = 1.0
            point, _, count = rdd._fit_local_polynomial(
                coordinate,
                outcome,
                cutoff_side=side,
                poly_order=1,
                kernel="triangular",
                bandwidth=1.0,
                variance_profile="kernel_hc0",
            )
            assert count == 12.0
            sensitivities.append(point)
            _, legacy_se, _ = rdd._fit_local_polynomial(
                coordinate,
                outcome,
                cutoff_side=side,
                poly_order=1,
                kernel="triangular",
                bandwidth=1.0,
                variance_profile="weighted_residual_homoskedastic",
            )
            unit_legacy_estimates.append(legacy_se**2)
        assert sensitivities == pytest.approx(
            [float(weight) for weight in rational_weights], abs=3e-14
        )
        side_variances.append(sum(value**2 for value in sensitivities))
        # For independent unit-variance errors the expectation of this
        # quadratic residual estimator is the sum over unit-response estimates.
        legacy_variances.append(sum(unit_legacy_estimates))
        assert legacy_variances[-1] == pytest.approx(float(Fraction(63, 220)), abs=3e-14)
        assert side_variances[-1] == pytest.approx(float(exact_known_noise), abs=3e-14)
    assert sum(side_variances) == pytest.approx(float(Fraction(127, 143)), abs=6e-14)
    # Expected legacy estimated variance is not the true localization-noise variance.
    legacy_expected_variance = Fraction(63, 220)
    assert float(legacy_expected_variance) != pytest.approx(float(exact_known_noise), rel=1e-3)
    assert legacy_variances[1] / side_variances[1] == pytest.approx(
        float(legacy_expected_variance / exact_known_noise), abs=3e-14
    )


def test_versioned_registry_profiles_survive_actual_persistence(tmp_path) -> None:
    """Both selected estimators keep their exact whole report under fresh CAS readback."""
    from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.causal import ensure_causal_methods_registered
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.foundry.methods.selection.resolution import ResolutionPolicy
    from polisyos.ir.analytics.causal import load_causal_effect_report, persist_causal_effect_report

    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    try:
        ensure_causal_methods_registered()
        data = _data(cutoff=0.2)
        saved = []
        assert (
            MethodRegistry.get_instance().get(
                "causal.inference.regression_discontinuity", policy=ResolutionPolicy.LATEST
            )
            is rdd.RegressionDiscontinuity
        )
        for method_name, version, variance in (
            ("regression_discontinuity", "1.0.0", "weighted_residual_homoskedastic"),
            ("regression_discontinuity_kernel_hc0", "1.1.0", "kernel_hc0"),
        ):
            method = MethodRegistry.get_instance().get(f"causal.inference.{method_name}@{version}")
            defaults = {
                parameter.name: parameter.default for parameter in method.signature.parameters
            }
            assert defaults["variance_profile"] == variance
            result = MethodDispatcher.get_instance().dispatch(
                method_class=method,
                signature=method.signature,
                state=data,
                params={"bandwidth": 0.7, "manipulation_test": False},
                seed=11,
            )
            report = result.output["report"]
            assert report.status is EstimationStatus.SUCCESS
            writer = _ensure_ir_artifact_store(FileSystemCAS(tmp_path))
            ref = persist_causal_effect_report(writer, report)
            reader = _ensure_ir_artifact_store(FileSystemCAS(tmp_path))
            assert reader is not writer
            loaded = load_causal_effect_report(reader, ref)
            assert loaded.model_dump(mode="json") == report.model_dump(mode="json")
            assert loaded.method_params["variance_profile"] == variance
            assert loaded.method_params["estimator_version"] == version
            assert loaded.method_params["cutoff"] == 0.2
            assert loaded.to_uncertainty_envelope().gate_eligible is False
            saved.append(loaded)
        assert saved[0].point_estimate == pytest.approx(saved[1].point_estimate)
        assert saved[0].standard_error != pytest.approx(saved[1].standard_error, rel=1e-3)
    finally:
        MethodRegistry.reset_instance()
        MethodDispatcher.reset_instance()

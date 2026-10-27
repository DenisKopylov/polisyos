"""Independent finite-sample witnesses for the bounded native sharp-RD profile.

The oracle below deliberately does not call or transcribe ``_fit_rbc_polynomial``.
It obtains each corrected estimator weight by perturbing one outcome through an
independently formulated weighted least-squares estimator (weighted ``lstsq``),
then applies the HC0 sandwich directly to those numerical sensitivities.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.foundry.methods.catalog.causal import rdd
from polisyos.foundry.methods.catalog.causal.protocols import RDDObservationalData
from polisyos.ir.analytics.causal import EstimationStatus

H = 0.45
B = 0.70
TRUE_JUMP = 2.0
SEED = 20_261_027
COVERAGE_SEED = 2_026_102_803
REPLICATIONS = 400
# Prospective fixed criterion: three binomial standard errors about 95% give
# [0.9173, 0.9827] at n=400; round outward to avoid false precision.
# Do not change the seed or band after observing this deciding run.
COVERAGE_ACCEPTANCE = (0.915, 0.985)


def _params(**overrides: object) -> dict[str, object]:
    return {
        "bias_correction": True,
        "bandwidth": H,
        "bias_bandwidth": B,
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


def _fixed_design() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return unique forcing values, curved mean, and nonconstant noise SD."""
    x = np.r_[np.linspace(-0.995, -0.005, 200), np.linspace(0.005, 0.995, 200)]
    mean = 1.0 + 0.3 * x + np.where(x < 0, 1.5 * x**2, TRUE_JUMP + 5.0 * x**2)
    noise_sd = 0.15 + 0.25 * np.abs(x) + 0.10 * (x >= 0)
    return x, mean, noise_sd


def _weighted_fit(design: np.ndarray, weights: np.ndarray, y: np.ndarray) -> np.ndarray:
    root_weight = np.sqrt(weights)
    return np.linalg.lstsq(root_weight[:, None] * design, root_weight * y, rcond=None)[0]


def _oracle_side(
    x: np.ndarray, y: np.ndarray, *, right: bool, h: float, b: float
) -> tuple[float, float]:
    """Calculate a corrected intercept and HC0 variance independently.

    In CCT notation for p=1, q=2 and derivative order zero, the corrected
    functional is ``alpha[0] - L * gamma[2]``. ``alpha`` is the h-window
    local-linear WLS coefficient, ``gamma`` the b-window local-quadratic WLS
    coefficient, and ``L`` is the local-linear response to ``(x/h)^2`` times
    ``(h/b)^2``. Numerical unit perturbations construct the complete corrected
    functional, including covariance, rather than importing production weights.
    """
    side = x >= 0 if right else x < 0
    xs, ys = x[side], y[side]
    wh = np.maximum(1.0 - np.abs(xs / h), 0.0)
    wb = np.maximum(1.0 - np.abs(xs / b), 0.0)
    keep = (wh > 0) | (wb > 0)
    xs, ys, wh, wb = xs[keep], ys[keep], wh[keep], wb[keep]
    hp = np.column_stack((np.ones_like(xs), xs / h))
    bq = np.column_stack((np.ones_like(xs), xs / b, (xs / b) ** 2))
    alpha = _weighted_fit(hp, wh, ys)
    gamma = _weighted_fit(bq, wb, ys)
    leading = _weighted_fit(hp, wh, (xs / h) ** 2)[0] * (h / b) ** 2

    def functional(values: np.ndarray) -> float:
        return float(_weighted_fit(hp, wh, values)[0] - leading * _weighted_fit(bq, wb, values)[2])

    sensitivities = np.array(
        [functional(np.eye(1, len(ys), index, dtype=float)[0]) for index in range(len(ys))]
    )
    corrected = float(alpha[0] - leading * gamma[2])
    residual_q = ys - bq @ gamma
    variance = float(np.sum((sensitivities * residual_q) ** 2))
    return corrected, variance


def _oracle(x: np.ndarray, y: np.ndarray, *, h: float = H, b: float = B) -> tuple[float, float]:
    left, left_variance = _oracle_side(x, y, right=False, h=h, b=b)
    right, right_variance = _oracle_side(x, y, right=True, h=h, b=b)
    return right - left, float(np.sqrt(left_variance + right_variance))


def _sample(seed: int = SEED) -> RDDObservationalData:
    x, mean, noise_sd = _fixed_design()
    y = mean + np.random.default_rng(seed).normal(0.0, noise_sd)
    return RDDObservationalData(running_variable=x, outcome=y, cutoff=0.0)


@pytest.mark.parametrize(("h", "b"), [(0.45, 0.70), (0.70, 0.45)], ids=["h_lt_b", "h_gt_b"])
def test_independent_sensitivity_oracle_matches_corrected_point_and_hc0_se(
    h: float, b: float
) -> None:
    data = _sample()
    expected_point, expected_se = _oracle(data.running_variable, data.outcome, h=h, b=b)
    params = _params(bandwidth=h, bias_bandwidth=b)
    report = rdd.RegressionDiscontinuity.pure_step(data, params)["report"]
    conventional = rdd.RegressionDiscontinuity.pure_step(
        data, _params(bandwidth=h, bias_bandwidth=b, bias_correction=False)
    )["report"]

    assert report.status is conventional.status is EstimationStatus.SUCCESS
    assert report.method_params["profile"] == "sharp_cct_rbc_hc0_fixed"
    assert report.point_estimate == pytest.approx(expected_point, rel=2e-11, abs=2e-11)
    assert report.standard_error == pytest.approx(expected_se, rel=2e-11, abs=2e-11)
    assert abs(report.point_estimate - conventional.point_estimate) > 0.04
    assert report.method_params["h"] == [h, h]
    assert report.method_params["b"] == [b, b]
    print(
        f"oracle point={expected_point:.12f} se={expected_se:.12f}; "
        f"runtime point={report.point_estimate:.12f} se={report.standard_error:.12f}; "
        f"conventional point={conventional.point_estimate:.12f}"
    )


def test_zero_curvature_produces_zero_correction_and_known_jump() -> None:
    x, _, _ = _fixed_design()
    # Exact piecewise linear means have no p+1 derivative on either side.
    y = 1.0 + 0.3 * x + np.where(x < 0.0, 0.0, TRUE_JUMP + 0.4 * x)
    data = RDDObservationalData(running_variable=x, outcome=y, cutoff=0.0)
    expected_point, expected_se = _oracle(x, y)
    corrected = rdd.RegressionDiscontinuity.pure_step(data, _params())["report"]
    conventional = rdd.RegressionDiscontinuity.pure_step(data, _params(bias_correction=False))[
        "report"
    ]
    assert corrected.status is conventional.status is EstimationStatus.SUCCESS
    assert corrected.point_estimate == pytest.approx(TRUE_JUMP, abs=2e-11)
    assert corrected.point_estimate == pytest.approx(expected_point, abs=2e-11)
    assert corrected.standard_error == pytest.approx(expected_se, abs=2e-11)
    assert corrected.point_estimate == pytest.approx(conventional.point_estimate, abs=2e-11)
    assert corrected.method_params["bias"] == pytest.approx(0.0, abs=2e-11)


def test_oracle_checked_profile_survives_dispatch_cas_and_fresh_reader(tmp_path: Path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.causal import ensure_causal_methods_registered
    from polisyos.foundry.methods.registry import MethodRegistry
    from polisyos.ir.analytics.causal import load_causal_effect_report, persist_causal_effect_report

    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    try:
        ensure_causal_methods_registered()
        method = MethodRegistry.get_instance().get(
            "causal.inference.regression_discontinuity@1.0.0"
        )
        data = _sample()
        expected_point, expected_se = _oracle(data.running_variable, data.outcome)
        result = MethodDispatcher.get_instance().dispatch(
            method_class=method, signature=method.signature, state=data, params=_params(), seed=SEED
        )
        writer = _ensure_ir_artifact_store(FileSystemCAS(tmp_path))
        artifact = persist_causal_effect_report(writer, result.output["report"])
        reader = _ensure_ir_artifact_store(FileSystemCAS(tmp_path))
        assert reader is not writer
        loaded = load_causal_effect_report(reader, artifact)
        assert loaded.point_estimate == pytest.approx(expected_point, rel=2e-11)
        assert loaded.standard_error == pytest.approx(expected_se, rel=2e-11)
        assert loaded.method_params["profile"] == "sharp_cct_rbc_hc0_fixed"
        assert loaded.method_params["h"] == [H, H]
        assert loaded.method_params["b"] == [B, B]
        assert loaded.method_params["p"] == 1
        assert loaded.method_params["q"] == 2
        assert (
            loaded.method_params["input_sha256"]
            == result.output["report"].method_params["input_sha256"]
        )
    finally:
        MethodRegistry.reset_instance()
        MethodDispatcher.reset_instance()


def test_predeclared_heteroskedastic_finite_design_coverage() -> None:
    x, mean, noise_sd = _fixed_design()
    rng = np.random.default_rng(COVERAGE_SEED)
    covered = 0
    accepted = 0
    for _ in range(REPLICATIONS):
        data = RDDObservationalData(
            running_variable=x, outcome=mean + rng.normal(0.0, noise_sd), cutoff=0.0
        )
        report = rdd.RegressionDiscontinuity.pure_step(data, _params())["report"]
        assert report.status is EstimationStatus.SUCCESS
        accepted += 1
        covered += int(report.confidence_interval[0] <= TRUE_JUMP <= report.confidence_interval[1])
    coverage = covered / accepted
    assert accepted == REPLICATIONS  # no filtering of failed fits
    assert COVERAGE_ACCEPTANCE[0] <= coverage <= COVERAGE_ACCEPTANCE[1]
    print(
        f"coverage seed={COVERAGE_SEED} covered={covered} accepted={accepted} "
        f"failed={REPLICATIONS - accepted} rate={coverage:.6f} "
        f"acceptance={COVERAGE_ACCEPTANCE}"
    )


def test_point_and_covariance_removals_are_executed_and_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _sample()
    expected_point, expected_se = _oracle(data.running_variable, data.outcome)
    original = rdd._fit_rbc_polynomial

    def point_removed(
        *args: object, **kwargs: object
    ) -> tuple[float, float, float, float, int, int]:
        conventional, _, variance_us, variance_rb, n_h, n_b = original(*args, **kwargs)
        return conventional, conventional, variance_us, variance_rb, n_h, n_b

    monkeypatch.setattr(rdd, "_fit_rbc_polynomial", point_removed)
    point_mutant = rdd.RegressionDiscontinuity.pure_step(data, _params())["report"]
    assert point_mutant.method_params["profile"] == "sharp_cct_rbc_hc0_fixed"
    with pytest.raises(AssertionError, match="point mutant escaped"):
        assert point_mutant.point_estimate == pytest.approx(expected_point, rel=2e-11), (
            "point mutant escaped independent oracle"
        )

    def covariance_removed(
        *args: object, **kwargs: object
    ) -> tuple[float, float, float, float, int, int]:
        conventional, corrected, variance_us, _, n_h, n_b = original(*args, **kwargs)
        return conventional, corrected, variance_us, variance_us, n_h, n_b

    monkeypatch.setattr(rdd, "_fit_rbc_polynomial", covariance_removed)
    covariance_mutant = rdd.RegressionDiscontinuity.pure_step(data, _params())["report"]
    assert covariance_mutant.method_params["profile"] == "sharp_cct_rbc_hc0_fixed"
    with pytest.raises(AssertionError, match="variance mutant escaped"):
        assert covariance_mutant.standard_error == pytest.approx(expected_se, rel=2e-11), (
            "variance mutant escaped independent oracle"
        )
    print(
        f"point-removal runtime={point_mutant.point_estimate:.12f} "
        f"oracle={expected_point:.12f}; variance-removal "
        f"runtime_se={covariance_mutant.standard_error:.12f} oracle_se={expected_se:.12f}"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"bandwidth": -0.1},
        {"bias_bandwidth": 0.0},
        {"polynomial_order": 3},
        {"bias_polynomial_order": 1},
        {"kernel": "gaussian"},
        {"design": "fuzzy"},
        {"bandwidth_selector": "mserd"},
    ],
)
def test_bounded_profile_refuses_unsupported_assumptions(change: dict[str, object]) -> None:
    report = rdd.RegressionDiscontinuity.pure_step(_sample(), _params(**change))["report"]
    assert report.status in {EstimationStatus.INPUT_INVALID, EstimationStatus.ASSUMPTION_FAILED}
    assert report.point_estimate is None


def test_oracle_profile_is_permutation_invariant_but_input_content_bound() -> None:
    data = _sample()
    before = rdd.RegressionDiscontinuity.pure_step(data, _params())["report"]
    order = np.random.default_rng(81).permutation(data.sample_size)
    shuffled_data = RDDObservationalData(
        running_variable=data.running_variable[order], outcome=data.outcome[order], cutoff=0.0
    )
    shuffled = rdd.RegressionDiscontinuity.pure_step(shuffled_data, _params())["report"]
    changed = rdd.RegressionDiscontinuity.pure_step(
        data.model_copy(update={"outcome": data.outcome + 1e-5}), _params()
    )["report"]
    assert shuffled.point_estimate == pytest.approx(before.point_estimate, abs=2e-12)
    assert shuffled.standard_error == pytest.approx(before.standard_error, abs=2e-12)
    assert shuffled.method_params["input_sha256"] != before.method_params["input_sha256"]
    assert changed.method_params["input_sha256"] != before.method_params["input_sha256"]

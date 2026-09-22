"""Regression witnesses for the bounded CAU-03 RDD repair."""

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.base import ComplexityClass
from polisyos.foundry.methods.catalog.causal import rdd as rdd_module
from polisyos.foundry.methods.catalog.causal.rdd import RegressionDiscontinuity
from polisyos.foundry.methods.catalog.causal.protocols import RDDObservationalData
from polisyos.ir.analytics.causal import EstimationStatus


def _report(output: dict[str, object]):
    return output["report"]


def _curved_rdd(*, n: int = 400) -> RDDObservationalData:
    running = np.linspace(-1.0, 1.0, n)
    outcome = (
        1.5
        + 0.4 * running
        + 0.7 * running**2
        + 2.5 * (running >= 0.0).astype(float)
        + 0.05 * np.sin(9.0 * running)
    )
    return RDDObservationalData(outcome=outcome, running_variable=running, cutoff=0.0)


def _reference_kernel_weights(distance: np.ndarray, kernel: str) -> np.ndarray:
    absolute = np.abs(distance)
    if kernel == "uniform":
        return (absolute <= 1.0).astype(float)
    if kernel == "epanechnikov":
        return np.where(absolute <= 1.0, 0.75 * (1.0 - absolute**2), 0.0)
    return np.where(absolute <= 1.0, 1.0 - absolute, 0.0)


def _reference_fit(
    x_centered: np.ndarray,
    outcome: np.ndarray,
    *,
    cutoff_side: str,
    poly_order: int,
    kernel: str,
    bandwidth: float,
) -> tuple[float, float, float]:
    mask = x_centered >= 0.0 if cutoff_side == "right" else x_centered < 0.0
    x_side = x_centered[mask]
    y_side = outcome[mask]
    weights = _reference_kernel_weights(x_side / bandwidth, kernel)
    valid = weights > 0.0
    x_side = x_side[valid]
    y_side = y_side[valid]
    weights = weights[valid]
    design = np.column_stack([x_side**order for order in range(poly_order + 1)])
    gram = design.T @ (weights[:, None] * design)
    rhs = design.T @ (weights * y_side)
    gram_pinv = np.linalg.pinv(gram)
    beta = gram_pinv @ rhs
    residual = y_side - design @ beta
    dof = max(x_side.size - design.shape[1], 1)
    sigma2 = float(np.sum(weights * residual**2) / dof)
    covariance = sigma2 * gram_pinv
    return float(beta[0]), float(np.sqrt(max(covariance[0, 0], 0.0))), float(x_side.size)


@pytest.mark.parametrize("kernel", ["triangular", "epanechnikov", "uniform"])
@pytest.mark.parametrize("poly_order", [1, 2])
def test_cau_03_vector_weighted_fit_matches_independent_reference(
    kernel: str,
    poly_order: int,
) -> None:
    """Supported kernel/order profiles preserve point, SE, and effective count."""

    data = _curved_rdd()
    x_centered = data.running_variable - data.cutoff
    for side in ("left", "right"):
        expected = _reference_fit(
            x_centered,
            data.outcome,
            cutoff_side=side,
            poly_order=poly_order,
            kernel=kernel,
            bandwidth=0.8,
        )
        actual = rdd_module._fit_local_polynomial(
            x_centered,
            data.outcome,
            cutoff_side=side,
            poly_order=poly_order,
            kernel=kernel,
            bandwidth=0.8,
        )
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_cau_03_fit_does_not_materialize_diagonal_or_repeat_factorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 400-point side uses vector weighting and one factorization of its small Gram matrix."""

    data = _curved_rdd(n=800)
    x_centered = data.running_variable - data.cutoff
    reference = _reference_fit(
        x_centered,
        data.outcome,
        cutoff_side="right",
        poly_order=1,
        kernel="triangular",
        bandwidth=0.8,
    )
    original_pinv = rdd_module.np.linalg.pinv
    pinv_calls: list[tuple[int, ...]] = []

    def recording_pinv(matrix: np.ndarray, *args: object, **kwargs: object) -> np.ndarray:
        pinv_calls.append(matrix.shape)
        return original_pinv(matrix, *args, **kwargs)

    def reject_diagonal(*args: object, **kwargs: object) -> np.ndarray:
        raise AssertionError("RDD WLS must not materialize an n-by-n diagonal matrix")

    monkeypatch.setattr(rdd_module.np.linalg, "pinv", recording_pinv)
    monkeypatch.setattr(rdd_module.np, "diag", reject_diagonal)

    actual = rdd_module._fit_local_polynomial(
        x_centered,
        data.outcome,
        cutoff_side="right",
        poly_order=1,
        kernel="triangular",
        bandwidth=0.8,
    )

    assert actual == pytest.approx(reference, rel=1e-12, abs=1e-12)
    assert pinv_calls == [(2, 2)]


def test_cau_03_signature_reports_linear_wls_complexity() -> None:
    """The method metadata no longer advertises the removed quadratic weight matrix."""

    assert RegressionDiscontinuity.signature.complexity is ComplexityClass.O_N


def test_cau_03_signature_default_does_not_claim_rbc() -> None:
    """The declared default is the supported uncorrected inference profile."""

    defaults = {
        parameter.name: parameter.default
        for parameter in RegressionDiscontinuity.signature.parameters
    }

    assert defaults["bias_correction"] is False


def test_cau_03_omitted_bias_correction_is_explicitly_uncorrected() -> None:
    """Omitting the flag is exactly the supported uncorrected profile."""

    data = _curved_rdd(n=200)
    omitted = _report(
        RegressionDiscontinuity.pure_step(
            data,
            {"bandwidth": 0.8, "kernel": "triangular", "manipulation_test": False},
        )
    )
    explicit = _report(
        RegressionDiscontinuity.pure_step(
            data,
            {
                "bandwidth": 0.8,
                "kernel": "triangular",
                "manipulation_test": False,
                "bias_correction": False,
            },
        )
    )

    assert omitted.status is explicit.status is EstimationStatus.SUCCESS
    assert omitted.point_estimate == pytest.approx(explicit.point_estimate)
    assert omitted.standard_error == pytest.approx(explicit.standard_error)
    assert omitted.confidence_interval == pytest.approx(explicit.confidence_interval)
    assert omitted.method_params["bias_correction"] is False
    assert explicit.method_params["bias_correction"] is False


def test_cau_03_true_bias_correction_fails_closed_without_an_estimate() -> None:
    """A requested RBC profile cannot be relabelled as ordinary local-polynomial output."""

    report = _report(
        RegressionDiscontinuity.pure_step(
            _curved_rdd(n=200),
            {"bandwidth": 0.8, "bias_correction": True},
        )
    )

    assert report.status is EstimationStatus.ASSUMPTION_FAILED
    assert report.point_estimate is None
    assert report.confidence_interval is None
    assert report.metadata["capability"] == "unsupported_rbc"
    assert "rdrobust" in (report.status_reason or "")


@pytest.mark.parametrize("malformed", ["false", 1, None])
def test_cau_03_malformed_bias_correction_flag_fails_closed(malformed: object) -> None:
    """Only actual booleans select the RDD inference profile."""

    report = _report(
        RegressionDiscontinuity.pure_step(
            _curved_rdd(n=200),
            {"bandwidth": 0.8, "bias_correction": malformed},
        )
    )

    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None
    assert report.status_reason == "bias_correction must be a boolean"


def test_cau_03_nonpositive_bandwidth_remains_input_invalid() -> None:
    """The WLS rewrite does not weaken the existing bandwidth guard."""

    report = _report(
        RegressionDiscontinuity.pure_step(
            _curved_rdd(n=200),
            {"bandwidth": 0.0, "bias_correction": False},
        )
    )

    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None
    assert report.status_reason == "invalid bandwidth=0.0"


def test_cau_03_unknown_kernel_fails_closed() -> None:
    """An unsupported kernel cannot silently select triangular weights."""

    report = _report(
        RegressionDiscontinuity.pure_step(
            _curved_rdd(n=200),
            {"bandwidth": 0.8, "kernel": "quartic", "bias_correction": False},
        )
    )

    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None
    assert report.status_reason == (
        "kernel must be one of: triangular, epanechnikov, uniform"
    )


@pytest.mark.parametrize("polynomial_order", [1.5, "2", True, 0, -1, 3, 99])
def test_cau_03_unsupported_polynomial_order_fails_closed(
    polynomial_order: object,
) -> None:
    """Only the characterized linear and quadratic profiles are supported."""

    report = _report(
        RegressionDiscontinuity.pure_step(
            _curved_rdd(n=200),
            {
                "bandwidth": 0.8,
                "polynomial_order": polynomial_order,
                "bias_correction": False,
            },
        )
    )

    assert report.status is EstimationStatus.INPUT_INVALID
    assert report.point_estimate is None
    assert report.status_reason == "polynomial_order must be an integer in {1, 2}"


def test_cau_03_insufficient_weighted_support_remains_non_success() -> None:
    """A narrow bandwidth cannot silently return a low-support estimate."""

    report = _report(
        RegressionDiscontinuity.pure_step(
            _curved_rdd(n=80),
            {"bandwidth": 0.02, "bias_correction": False},
        )
    )

    assert report.status is EstimationStatus.NUMERICAL_FAILURE
    assert report.point_estimate is None
    assert "insufficient weighted observations" in (report.status_reason or "")


def test_cau_03_rank_deficient_local_design_fails_closed() -> None:
    """Repeated running-variable values cannot produce a pseudo-inverse estimate."""

    running = np.concatenate([np.full(20, -0.25), np.full(20, 0.25)])
    outcome = np.concatenate([np.linspace(0.0, 1.0, 20), np.linspace(2.0, 3.0, 20)])
    report = _report(
        RegressionDiscontinuity.pure_step(
            RDDObservationalData(outcome=outcome, running_variable=running, cutoff=0.0),
            {
                "bandwidth": 0.8,
                "polynomial_order": 2,
                "bias_correction": False,
                "manipulation_test": False,
            },
        )
    )

    assert report.status is EstimationStatus.NUMERICAL_FAILURE
    assert report.point_estimate is None
    assert "rank deficient design" in (report.status_reason or "")

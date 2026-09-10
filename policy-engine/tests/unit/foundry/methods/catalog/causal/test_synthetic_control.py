from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.causal import (
    PanelObservationalData,
    ensure_causal_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.analytics.causal import EstimationStatus


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def test_synthetic_control_perfect_donor_match_att_estimate():
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("causal.inference.synthetic_control@2.0.0")

    t0 = 6
    true_att = 5.0
    donor_1 = np.array([10, 11, 12, 13, 14, 15, 16, 17, 18, 19], dtype=float)
    donor_2 = np.array([5, 5, 5, 5, 5, 5, 5, 5, 5, 5], dtype=float)
    treated = donor_1.copy()
    treated[t0:] += true_att

    data = PanelObservationalData(
        outcome=np.vstack([treated, donor_1, donor_2]),
        treatment=np.array([1, 0, 0]),
        time_treatment=t0,
    )

    dispatcher = MethodDispatcher.get_instance()
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={"n_placebo_runs": "all"},
        seed=42,
    )

    report = result.output["report"]
    weights = np.asarray(result.output["weights"])
    assert report.status == EstimationStatus.SUCCESS
    assert abs(report.point_estimate - true_att) < 1.0
    assert abs(weights[0] - 1.0) < 1e-2
    assert result.reproducibility.determinism_tier == DeterminismTier.STATISTICAL


def test_synthetic_control_fails_with_multiple_treated_units():
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("causal.inference.synthetic_control@2.0.0")
    data = PanelObservationalData(
        outcome=np.arange(20, dtype=float).reshape(4, 5),
        treatment=np.array([1, 1, 0, 0]),
        time_treatment=2,
    )
    dispatcher = MethodDispatcher.get_instance()
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={},
        seed=0,
    )
    report = result.output["report"]
    assert report.status == EstimationStatus.INPUT_INVALID
    envelope = result.output["envelope"]
    assert envelope is not None
    assert envelope.gate_eligible is False


def test_augmented_synthetic_control_mode_returns_augmented_flag():
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    method_cls = registry.get("causal.inference.synthetic_control@2.0.0")

    t0 = 5
    donor_1 = np.array([2, 2, 2, 2, 2, 2, 2, 2], dtype=float)
    donor_2 = np.array([1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.4], dtype=float)
    treated = 0.7 * donor_1 + 0.3 * donor_2
    treated[t0:] += 2.5

    data = PanelObservationalData(
        outcome=np.vstack([treated, donor_1, donor_2]),
        treatment=np.array([1, 0, 0]),
        time_treatment=t0,
    )

    dispatcher = MethodDispatcher.get_instance()
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=data,
        params={"estimation_mode": "augmented", "ridge_alpha": 0.5},
        seed=13,
    )

    report = result.output["report"]
    assert report.status == EstimationStatus.SUCCESS
    assert result.output["augmented"] is True
    assert np.isfinite(report.point_estimate)


def _scm_exact_two_donor_weight(y, donors, weight=0.0, covariates=None, covariate_donors=None):
    from fractions import Fraction

    numerator = Fraction(0)
    denominator = Fraction(0)
    blocks = [(y, donors, Fraction(1))]
    if weight:
        blocks.append((covariates, covariate_donors, Fraction.from_float(weight)))
    for target, controls, multiplier in blocks:
        for index, value in enumerate(target):
            difference = Fraction.from_float(float(controls[0, index])) - Fraction.from_float(
                float(controls[1, index])
            )
            residual = Fraction.from_float(float(value)) - Fraction.from_float(
                float(controls[1, index])
            )
            numerator += multiplier * difference * residual / len(target)
            denominator += multiplier * difference * difference / len(target)
    return float(max(Fraction(0), min(Fraction(1), numerator / denominator)))


def _scm_solve(y, donors, **extra):
    from polisyos.foundry.methods.catalog.causal.synthetic_control import _fit_scm_weights

    return _fit_scm_weights(
        y,
        donors,
        method="SLSQP",
        max_iter=1000,
        tolerance=1e-8,
        covariates_weight=extra.pop("covariates_weight", 0.0),
        **extra,
    )


def test_scm_solver_closes_recorded_unit_conditioning():
    # Exact pre-period values are independently source-bound in the retained
    # c3/recorded-growth/scm-scale-diagnostic.json receipt. This test claims
    # numerical computation only; full current source replay is a separate gate.
    y = np.asarray([502382.0, 854809.55, 259912734.0, 277545069.12, 292339519.94])
    donors = np.asarray(
        [
            [212667132.51, 180245284.56, 177622255.65, 172733290.49, 120162943.9],
            [74276475.43, 69770048.87, 62158198.82, 61685776.92, 57018801.65],
        ]
    )
    weights, accepted, reason = _scm_solve(y, donors)
    assert accepted, reason
    expected = _scm_exact_two_donor_weight(y, donors)
    assert weights[0] == pytest.approx(expected, abs=1e-8)
    assert weights[1] == pytest.approx(1.0 - expected, abs=1e-8)


@pytest.mark.parametrize("exponent", [0, 10, 20, 30])
def test_scm_solver_preserves_exact_match_across_declared_unit_changes(exponent):
    donors = np.ldexp(np.asarray([np.arange(10.0, 16.0), np.full(6, 5.0)]), exponent)
    weights, accepted, reason = _scm_solve(donors[0], donors)
    assert accepted, reason
    assert weights == pytest.approx([1.0, 0.0], abs=1e-8)


@pytest.mark.parametrize("exponent", [0, 20])
def test_scm_solver_preserves_relative_covariate_objective_weight(exponent):
    y = np.ldexp(np.asarray([2.0, 3.0, 5.0, 7.0]), exponent)
    donors = np.ldexp(np.asarray([[1.0, 2.0, 4.0, 6.0], [4.0, 5.0, 7.0, 9.0]]), exponent)
    covariates = np.ldexp(np.asarray([20.0, 30.0]), exponent)
    covariate_donors = np.ldexp(np.asarray([[10.0, 10.0], [90.0, 100.0]]), exponent)
    expected = _scm_exact_two_donor_weight(y, donors, 0.2, covariates, covariate_donors)
    weights, accepted, reason = _scm_solve(
        y, donors, covariates_weight=0.2, x_treated=covariates, x_donors=covariate_donors
    )
    assert accepted, reason
    assert weights[0] == pytest.approx(expected, abs=1e-8)


@pytest.mark.parametrize(
    ("has_treated", "has_donors"),
    [
        (False, False),
        (False, True),
        (True, False),
    ],
)
def test_scm_solver_refuses_incomplete_requested_covariate_objective(has_treated, has_donors):
    donors = np.asarray([np.arange(10.0, 16.0), np.full(6, 5.0)])
    weights, accepted, reason = _scm_solve(
        donors[0],
        donors,
        covariates_weight=1.0,
        x_treated=np.asarray([10.0]) if has_treated else None,
        x_donors=np.asarray([[10.0], [5.0]]) if has_donors else None,
    )
    assert not accepted
    assert not weights.size
    assert "covariate objective block" in reason


@pytest.mark.parametrize(
    ("claimed_weights", "reason_fragment"),
    [
        ([0.5, 0.5], "optimality"),
        ([-0.1, 1.1], "simplex"),
        ([0.25, 0.25], "simplex"),
        ([1.0], "vector"),
        ([float("nan"), 1.0], ""),
    ],
)
def test_scm_solver_refuses_unverified_optimizer_outputs(
    monkeypatch, claimed_weights, reason_fragment
):
    from types import SimpleNamespace

    import scipy.optimize

    monkeypatch.setattr(
        scipy.optimize,
        "minimize",
        lambda *a, **k: SimpleNamespace(
            success=True,
            message="Optimization terminated successfully",
            x=np.asarray(claimed_weights),
        ),
    )
    donors = np.asarray([np.arange(10.0, 16.0), np.full(6, 5.0)])
    weights, accepted, reason = _scm_solve(donors[0], donors)
    assert not accepted
    assert not weights.size
    assert reason and reason_fragment in reason


def test_scm_solver_checks_solution_even_when_optimizer_status_disagrees(monkeypatch):
    from types import SimpleNamespace

    import scipy.optimize

    monkeypatch.setattr(
        scipy.optimize,
        "minimize",
        lambda *a, **k: SimpleNamespace(
            success=False, message="iteration limit", x=np.asarray([1.0, 0.0])
        ),
    )
    donors = np.asarray([np.arange(10.0, 16.0), np.full(6, 5.0)])
    weights, accepted, reason = _scm_solve(donors[0], donors)
    assert accepted, reason
    assert weights.tolist() == [1.0, 0.0]


def test_scm_current_registration_refuses_retired_epoch():
    ensure_causal_methods_registered()
    registry = MethodRegistry.get_instance()
    current = registry.get("causal.inference.synthetic_control@2.0.0")
    assert current.signature.version == "2.0.0"
    assert registry.get_signature("causal.inference.synthetic_control@1.0.0") is None

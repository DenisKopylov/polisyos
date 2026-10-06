"""Reject real-law projections before dtype conversion or evaluator execution."""

from __future__ import annotations

import warnings
from fractions import Fraction

import numpy as np
import pytest

from polisyos.foundry.uncertainty import (
    admit_empirical_weights,
    admit_unit_uniform,
    empirical_cdf,
)
from polisyos.foundry.uncertainty.sampling_admission import (
    BoundedIIDMeanPlan,
    admit_float32_range,
    frozen_bernstein_budget,
)


@pytest.mark.parametrize(
    "values",
    [
        np.array([0.5 + 0.1j, 0.5 - 0.1j]),
        np.array([0.5 + 0j, 0.5 + 0j]),
        np.array([0.5 + 0.1j, 0.5 - 0.1j], dtype=object),
        np.array(["0.5", "0.5"]),
    ],
)
@pytest.mark.parametrize("inlet", ["weights", "cdf", "uniform", "range", "pilot"])
def test_non_real_numeric_domains_refuse_before_projection(values, inlet):
    plan = BoundedIIDMeanPlan(metric_id="y", pilot_samples=2)
    call = {
        "weights": lambda: admit_empirical_weights(values, 2),
        "cdf": lambda: empirical_cdf(values),
        "uniform": lambda: admit_unit_uniform(values),
        "range": lambda: admit_float32_range(values),
        "pilot": lambda: frozen_bernstein_budget(values, plan),
    }[inlet]
    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        with pytest.raises(ValueError, match="real numeric"):
            call()
    assert not observed


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int64, object])
def test_supported_real_arrays_preserve_finite_dyadic_law(dtype):
    weights = np.array([1, 1, 2], dtype=dtype)
    probabilities = admit_empirical_weights(weights, 3)
    assert np.array_equal(probabilities, [0.25, 0.25, 0.5])
    assert np.array_equal(empirical_cdf(probabilities), [0.25, 0.5, 1])
    coordinates = [0, 0] if dtype is np.int64 else [0, 0.5]
    assert np.array_equal(admit_unit_uniform(np.array(coordinates, dtype=dtype)), coordinates)


def test_iid_mean_budget_retains_independent_analytic_oracle():
    plan = BoundedIIDMeanPlan(metric_id="y")
    variance_bound, main_count = frozen_bernstein_budget(np.zeros(256), plan)
    assert variance_bound == pytest.approx(0.0995612812, abs=1e-9)
    assert main_count == 408


@pytest.mark.parametrize("representation", ["longdouble", "fraction"])
@pytest.mark.parametrize("inlet", ["weights", "cdf", "uniform", "range", "pilot"])
def test_nonzero_real_support_cannot_be_admitted_as_zero(representation, inlet):
    tiny = np.longdouble("1e-400") if representation == "longdouble" else Fraction(1, 10**400)
    if tiny == 0:
        pytest.skip("platform longdouble does not represent this positive fixture")
    values = np.array([tiny, 1], dtype=np.longdouble if representation == "longdouble" else object)
    plan = BoundedIIDMeanPlan(metric_id="y", pilot_samples=2)
    call = {
        "weights": lambda: admit_empirical_weights(values, 2),
        "cdf": lambda: empirical_cdf(values),
        "uniform": lambda: admit_unit_uniform(values),
        "range": lambda: admit_float32_range(values),
        "pilot": lambda: frozen_bernstein_budget(values, plan),
    }[inlet]
    assert values[0] > 0 and float(values[0]) == 0
    with pytest.raises(ValueError, match="nonzero sampling support"):
        call()

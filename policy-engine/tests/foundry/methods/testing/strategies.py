"""
Reusable Hypothesis strategies for Foundry method property-based tests.

All strategies produce valid, non-degenerate inputs that any well-implemented
Foundry method should be able to process without raising an exception.

Usage
-----
::

    from tests.foundry.methods.testing.strategies import (
        panel_data_strategy,
        iv_data_strategy,
        rdd_data_strategy,
        optimization_lp_strategy,
        bayesian_regression_strategy,
    )

    @given(data=panel_data_strategy())
    def test_my_method(data):
        result = MyMethod.pure_step(data, {})
        assert result is not None
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    from hypothesis import assume
    from hypothesis import strategies as st
    from hypothesis.extra.numpy import arrays, floating_dtypes

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

    # Provide no-op stubs so module-level @st.composite decorators don't fail at import
    class _StStub:
        @staticmethod
        def composite(f):  # type: ignore[misc]
            return f

        @staticmethod
        def integers(**_kw):  # type: ignore[misc]
            return None

        @staticmethod
        def floats(**_kw):  # type: ignore[misc]
            return None

        @staticmethod
        def booleans():  # type: ignore[misc]
            return None

        @staticmethod
        def one_of(*_):  # type: ignore[misc]
            return None

        @staticmethod
        def just(_):  # type: ignore[misc]
            return None

    st = _StStub()  # type: ignore[assignment]
    assume = lambda _: None  # type: ignore[assignment]
    arrays = None  # type: ignore[assignment]
    floating_dtypes = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_OBS = 20
_MAX_OBS = 200
_MIN_PERIODS = 4
_MAX_PERIODS = 20
_MIN_UNITS = 4
_MAX_UNITS = 30
_MIN_COVS = 2
_MAX_COVS = 8

# ---------------------------------------------------------------------------
# Scalar helpers
# ---------------------------------------------------------------------------


def _n_obs_st(min_val: int = _MIN_OBS, max_val: int = _MAX_OBS) -> st.SearchStrategy[int]:
    return st.integers(min_value=min_val, max_value=max_val)


def _n_periods_st(
    min_val: int = _MIN_PERIODS, max_val: int = _MAX_PERIODS
) -> st.SearchStrategy[int]:
    return st.integers(min_value=min_val, max_value=max_val)


def _finite_floats(
    min_value: float = -100.0,
    max_value: float = 100.0,
) -> st.SearchStrategy[float]:
    return st.floats(
        min_value=min_value,
        max_value=max_value,
        allow_nan=False,
        allow_infinity=False,
    )


def _finite_array(
    shape: tuple[int, ...],
    min_value: float = -100.0,
    max_value: float = 100.0,
) -> st.SearchStrategy[np.ndarray]:
    return arrays(
        dtype=np.float64,
        shape=shape,
        elements=st.floats(
            min_value=min_value,
            max_value=max_value,
            allow_nan=False,
            allow_infinity=False,
        ),
    )


# ---------------------------------------------------------------------------
# Panel / DiD data
# ---------------------------------------------------------------------------


@st.composite
def panel_data_strategy(
    draw: Any,
    min_units: int = _MIN_UNITS,
    max_units: int = _MAX_UNITS,
    min_periods: int = _MIN_PERIODS,
    max_periods: int = _MAX_PERIODS,
    min_treated_frac: float = 0.2,
    max_treated_frac: float = 0.7,
) -> dict[str, Any]:
    """
    Generate a valid panel dataset suitable for DiD / staggered methods.

    Returns a dict with keys:
    - outcome: float64 array (n_units, n_periods)
    - treatment: int array (n_units,)  — 0/1
    - time_treatment: int — period at which treatment starts
    - n_units: int
    - n_periods: int
    """
    n_units = draw(st.integers(min_value=min_units, max_value=max_units))
    n_periods = draw(st.integers(min_value=min_periods, max_value=max_periods))
    outcome = draw(_finite_array((n_units, n_periods)))
    time_treatment = draw(st.integers(min_value=2, max_value=n_periods - 1))
    n_treated = draw(
        st.integers(
            min_value=max(1, int(n_units * min_treated_frac)),
            max_value=max(1, int(n_units * max_treated_frac)),
        )
    )
    treatment = np.zeros(n_units, dtype=int)
    treatment[:n_treated] = 1
    return {
        "outcome": outcome,
        "treatment": treatment,
        "time_treatment": time_treatment,
        "n_units": n_units,
        "n_periods": n_periods,
    }


# ---------------------------------------------------------------------------
# IV (instrumental variable) data
# ---------------------------------------------------------------------------


@st.composite
def iv_data_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate valid IV data: outcome, treatment, instrument, covariates.

    Returns dict with keys: outcome, treatment, instrument, covariates.
    """
    n_obs = draw(_n_obs_st())
    n_covs = draw(st.integers(min_value=1, max_value=_MAX_COVS))
    instrument = draw(_finite_array((n_obs,), min_value=0.0, max_value=1.0))
    noise_treat = draw(_finite_array((n_obs,), min_value=-0.5, max_value=0.5))
    treatment = (instrument * 0.7 + noise_treat).clip(0.0, 1.0)
    beta_true = draw(_finite_floats(-3.0, 3.0))
    noise_out = draw(_finite_array((n_obs,), min_value=-1.0, max_value=1.0))
    outcome = treatment * beta_true + noise_out
    covariates = draw(_finite_array((n_obs, n_covs)))
    return {
        "outcome": outcome,
        "treatment": treatment,
        "instrument": instrument,
        "covariates": covariates,
        "n_obs": n_obs,
        "beta_true": beta_true,
    }


# ---------------------------------------------------------------------------
# RDD (Regression Discontinuity) data
# ---------------------------------------------------------------------------


@st.composite
def rdd_data_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate valid RDD data with a known discontinuity.

    Returns dict with keys: outcome, running_variable, covariates, cutoff, effect_true.
    """
    n_obs = draw(_n_obs_st())
    n_covs = draw(st.integers(min_value=1, max_value=4))
    cutoff = draw(_finite_floats(-1.0, 1.0))
    effect_true = draw(_finite_floats(-5.0, 5.0))
    running_variable = draw(_finite_array((n_obs,), min_value=-3.0, max_value=3.0))
    noise = draw(_finite_array((n_obs,), min_value=-0.5, max_value=0.5))
    treatment_indicator = (running_variable >= cutoff).astype(float)
    outcome = running_variable * 0.5 + treatment_indicator * effect_true + noise
    covariates = draw(_finite_array((n_obs, n_covs)))
    return {
        "outcome": outcome,
        "running_variable": running_variable,
        "covariates": covariates,
        "cutoff": cutoff,
        "effect_true": effect_true,
        "n_obs": n_obs,
    }


# ---------------------------------------------------------------------------
# LP / Optimization data
# ---------------------------------------------------------------------------


@st.composite
def lp_data_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate a feasible small LP: minimise c·x s.t. Ax ≤ b, x ≥ 0.

    Returns dict with keys: c, A_ub, b_ub, n_vars, n_constraints.
    """
    n_vars = draw(st.integers(min_value=2, max_value=8))
    n_constraints = draw(st.integers(min_value=2, max_value=6))
    c = draw(_finite_array((n_vars,), min_value=0.0, max_value=10.0))
    # Build A_ub with non-negative entries to ensure feasibility at x=0
    A_ub = draw(_finite_array((n_constraints, n_vars), min_value=0.0, max_value=5.0))
    b_ub = draw(_finite_array((n_constraints,), min_value=5.0, max_value=50.0))
    assume(np.all(b_ub > 0))
    return {
        "c": c,
        "A_ub": A_ub,
        "b_ub": b_ub,
        "n_vars": n_vars,
        "n_constraints": n_constraints,
    }


# ---------------------------------------------------------------------------
# Bayesian regression data
# ---------------------------------------------------------------------------


@st.composite
def bayesian_regression_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate valid Bayesian regression inputs: X, y, priors.

    Returns dict with keys: X, y, n_obs, n_features, beta_true.
    """
    n_obs = draw(st.integers(min_value=30, max_value=150))
    n_features = draw(st.integers(min_value=1, max_value=5))
    beta_true = draw(_finite_array((n_features,), min_value=-3.0, max_value=3.0))
    X = draw(_finite_array((n_obs, n_features)))
    noise = draw(_finite_array((n_obs,), min_value=-1.0, max_value=1.0))
    y = X @ beta_true + noise
    return {
        "X": X,
        "y": y,
        "n_obs": n_obs,
        "n_features": n_features,
        "beta_true": beta_true,
    }


# ---------------------------------------------------------------------------
# Time-series data
# ---------------------------------------------------------------------------


@st.composite
def timeseries_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate a stationary time series (AR(1) process).

    Returns dict with keys: endog, n_obs.
    """
    n_obs = draw(st.integers(min_value=50, max_value=300))
    ar_coef = draw(st.floats(min_value=-0.8, max_value=0.8, allow_nan=False))
    innovations = draw(_finite_array((n_obs,), min_value=-1.0, max_value=1.0))
    endog = np.zeros(n_obs)
    for t in range(1, n_obs):
        endog[t] = ar_coef * endog[t - 1] + innovations[t]
    return {
        "endog": endog,
        "n_obs": n_obs,
        "ar_coef": ar_coef,
    }


# ---------------------------------------------------------------------------
# Cross-section / OLS data
# ---------------------------------------------------------------------------


@st.composite
def cross_section_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate cross-section OLS data.

    Returns dict with keys: outcome, covariates, n_obs, n_features.
    """
    n_obs = draw(_n_obs_st())
    n_features = draw(st.integers(min_value=1, max_value=_MAX_COVS))
    beta_true = draw(_finite_array((n_features,), min_value=-5.0, max_value=5.0))
    X = draw(_finite_array((n_obs, n_features)))
    noise = draw(_finite_array((n_obs,), min_value=-1.0, max_value=1.0))
    outcome = X @ beta_true + noise
    return {
        "outcome": outcome,
        "covariates": X,
        "n_obs": n_obs,
        "n_features": n_features,
        "beta_true": beta_true,
    }


# ---------------------------------------------------------------------------
# Spatial data
# ---------------------------------------------------------------------------


@st.composite
def spatial_data_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate spatial point data with 2D coordinates and outcome.

    Returns dict with keys: lon, lat, outcome, covariates, n_obs.
    """
    n_obs = draw(st.integers(min_value=30, max_value=150))
    n_covs = draw(st.integers(min_value=1, max_value=4))
    lon = draw(_finite_array((n_obs,), min_value=-180.0, max_value=180.0))
    lat = draw(_finite_array((n_obs,), min_value=-90.0, max_value=90.0))
    covariates = draw(_finite_array((n_obs, n_covs)))
    # Outcome has mild spatial dependence on lat
    outcome = lat * 0.1 + draw(_finite_array((n_obs,), min_value=-5.0, max_value=5.0))
    return {
        "lon": lon,
        "lat": lat,
        "outcome": outcome,
        "covariates": covariates,
        "n_obs": n_obs,
    }


# ---------------------------------------------------------------------------
# Count data
# ---------------------------------------------------------------------------


@st.composite
def count_data_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate count (non-negative integer) outcome data for Poisson / NegBin.

    Returns dict with keys: outcome, covariates, n_obs, offset (optional).
    """
    n_obs = draw(st.integers(min_value=50, max_value=200))
    n_covs = draw(st.integers(min_value=1, max_value=4))
    X = draw(_finite_array((n_obs, n_covs), min_value=-2.0, max_value=2.0))
    # Poisson rate: lambda = exp(X @ beta)
    beta = draw(_finite_array((n_covs,), min_value=-1.0, max_value=1.0))
    lam = np.exp(np.clip(X @ beta, -5.0, 5.0))
    # Deterministic count for reproducibility in property tests
    outcome = np.round(lam).astype(np.int64)
    return {
        "outcome": outcome,
        "covariates": X,
        "n_obs": n_obs,
        "exposure": np.ones(n_obs),
    }


# ---------------------------------------------------------------------------
# Discrete choice data
# ---------------------------------------------------------------------------


@st.composite
def discrete_choice_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate discrete choice (logit) data.

    Returns dict with keys: choice, attributes, n_obs, n_alternatives, n_attributes.
    """
    n_obs = draw(st.integers(min_value=50, max_value=200))
    n_alt = draw(st.integers(min_value=2, max_value=4))
    n_attr = draw(st.integers(min_value=1, max_value=3))
    attributes = draw(_finite_array((n_obs, n_alt, n_attr), min_value=-3.0, max_value=3.0))
    # Deterministic choice based on max utility (first attribute)
    choice = np.argmax(attributes[:, :, 0], axis=1).astype(np.int64)
    return {
        "choice": choice,
        "attributes": attributes,
        "n_obs": n_obs,
        "n_alternatives": n_alt,
        "n_attributes": n_attr,
    }


# ---------------------------------------------------------------------------
# Survey data
# ---------------------------------------------------------------------------


@st.composite
def survey_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate survey sample data with design weights and stratification.

    Returns dict with keys: outcome, weights, strata_id, cluster_id, n_obs.
    """
    n_strata = draw(st.integers(min_value=2, max_value=5))
    n_per_stratum = draw(st.integers(min_value=10, max_value=40))
    n_obs = n_strata * n_per_stratum
    outcome = draw(_finite_array((n_obs,), min_value=0.0, max_value=100.0))
    # Weights: positive, sum to n_strata (calibration target)
    weights_raw = draw(_finite_array((n_obs,), min_value=0.5, max_value=3.0))
    assume(np.all(weights_raw > 0))
    strata_id = np.repeat(np.arange(n_strata), n_per_stratum).astype(np.int64)
    cluster_id = np.repeat(np.arange(n_obs // 2), 2)[:n_obs].astype(np.int64)
    return {
        "outcome": outcome,
        "weights": weights_raw,
        "strata_id": strata_id,
        "cluster_id": cluster_id,
        "n_obs": n_obs,
        "n_strata": n_strata,
    }


# ---------------------------------------------------------------------------
# Distributional (inequality / poverty) data
# ---------------------------------------------------------------------------


@st.composite
def distribution_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate income/welfare distribution data.

    Returns dict with keys: income, weights, poverty_line, n_obs.
    """
    n_obs = draw(st.integers(min_value=50, max_value=300))
    # Income: log-normal approximation, strictly positive
    log_income = draw(_finite_array((n_obs,), min_value=0.0, max_value=5.0))
    income = np.exp(log_income)
    assume(np.all(income > 0))
    weights = draw(_finite_array((n_obs,), min_value=0.1, max_value=5.0))
    assume(np.all(weights > 0))
    poverty_line = draw(st.floats(min_value=1.0, max_value=10.0, allow_nan=False))
    return {
        "income": income,
        "weights": weights,
        "poverty_line": poverty_line,
        "n_obs": n_obs,
    }


# ---------------------------------------------------------------------------
# Sensitivity analysis data
# ---------------------------------------------------------------------------


@st.composite
def sensitivity_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate parameter space for global sensitivity analysis.

    Returns dict with keys: X (n_obs, n_params), param_names, n_obs, n_params.
    """
    n_params = draw(st.integers(min_value=2, max_value=6))
    n_obs = draw(st.integers(min_value=50, max_value=500))
    # X in [0, 1] (normalised parameter space)
    X = draw(_finite_array((n_obs, n_params), min_value=0.0, max_value=1.0))
    # Simple model: linear function of params for testing
    Y = np.sum(X, axis=1)
    return {
        "X": X,
        "Y": Y,
        "n_obs": n_obs,
        "n_params": n_params,
        "param_names": [f"x{i}" for i in range(n_params)],
    }


# ---------------------------------------------------------------------------
# Simulation / SIR compartmental data
# ---------------------------------------------------------------------------


@st.composite
def simulation_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate initial conditions for a simple SIR compartmental simulation.

    Returns dict with keys: S0, I0, R0, beta, gamma, n_steps.
    """
    population = draw(st.integers(min_value=100, max_value=10_000))
    I0 = draw(st.integers(min_value=1, max_value=max(1, population // 10)))
    S0 = population - I0
    R0_count = 0
    beta = draw(st.floats(min_value=0.05, max_value=0.5, allow_nan=False))
    gamma = draw(st.floats(min_value=0.01, max_value=0.3, allow_nan=False))
    n_steps = draw(st.integers(min_value=10, max_value=200))
    return {
        "S0": float(S0),
        "I0": float(I0),
        "R0": float(R0_count),
        "N": float(population),
        "beta": beta,
        "gamma": gamma,
        "n_steps": n_steps,
    }


# ---------------------------------------------------------------------------
# ML / supervised learning data
# ---------------------------------------------------------------------------


@st.composite
def ml_regression_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate supervised regression data for ML methods.

    Returns dict with keys: features, target, n_obs, n_features.
    """
    n_obs = draw(st.integers(min_value=40, max_value=200))
    n_features = draw(st.integers(min_value=2, max_value=10))
    X = draw(_finite_array((n_obs, n_features), min_value=-3.0, max_value=3.0))
    beta = draw(_finite_array((n_features,), min_value=-2.0, max_value=2.0))
    noise = draw(_finite_array((n_obs,), min_value=-0.5, max_value=0.5))
    y = X @ beta + noise
    return {
        "features": X,
        "target": y,
        "n_obs": n_obs,
        "n_features": n_features,
    }


# ---------------------------------------------------------------------------
# Microsimulation data
# ---------------------------------------------------------------------------


@st.composite
def microsim_strategy(draw: Any) -> dict[str, Any]:
    """
    Generate micro-level population data for tax-benefit / microsim methods.

    Returns dict with keys: income, age, employment_status, household_size, n_agents.
    """
    n_agents = draw(st.integers(min_value=50, max_value=300))
    income = draw(_finite_array((n_agents,), min_value=0.0, max_value=100_000.0))
    assume(np.all(income >= 0))
    age = draw(
        arrays(
            dtype=np.int64,
            shape=(n_agents,),
            elements=st.integers(min_value=18, max_value=80),
        )
    )
    employment_status = draw(
        arrays(
            dtype=np.int64,
            shape=(n_agents,),
            elements=st.integers(min_value=0, max_value=2),  # 0=unemployed, 1=employed, 2=retired
        )
    )
    household_size = draw(
        arrays(
            dtype=np.int64,
            shape=(n_agents,),
            elements=st.integers(min_value=1, max_value=6),
        )
    )
    return {
        "income": income,
        "age": age,
        "employment_status": employment_status,
        "household_size": household_size,
        "n_agents": n_agents,
    }

from __future__ import annotations

import numpy as np
import pytest

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.econometrics import (
    PanelData,
    TimeSeriesData,
    ensure_econometric_methods_registered,
)
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def _reset_globals():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()


def _make_panel_data() -> PanelData:
    rng = np.random.default_rng(11)
    n_entities = 20
    n_periods = 6
    n_obs = n_entities * n_periods
    entity_ids = np.repeat(np.arange(n_entities), n_periods)
    time_ids = np.tile(np.arange(n_periods), n_entities)
    x0 = rng.normal(size=n_obs)
    x1 = rng.normal(size=n_obs)
    x2 = rng.normal(size=n_obs)
    y = (
        1.0
        + 0.7 * x0
        - 0.25 * x1
        + entity_ids.astype(float) * 0.05
        + rng.normal(
            scale=0.2,
            size=n_obs,
        )
    )
    instruments = np.column_stack(
        [
            x2 + rng.normal(scale=0.1, size=n_obs),
            x1 + rng.normal(scale=0.1, size=n_obs),
        ]
    )
    return PanelData(
        dependent=y,
        exog=np.column_stack([x0, x1, x2]),
        entity_ids=entity_ids,
        time_ids=time_ids,
        instrument_ids=instruments,
        feature_names=["x0", "x1", "x2"],
    )


def _make_time_series() -> TimeSeriesData:
    rng = np.random.default_rng(12)
    n_obs = 180
    noise = rng.normal(scale=0.4, size=n_obs)
    signal = np.zeros(n_obs, dtype=float)
    for idx in range(1, n_obs):
        signal[idx] = 0.65 * signal[idx - 1] + noise[idx]
    return TimeSeriesData(
        endog=signal,
        exog=np.column_stack([rng.normal(size=n_obs), rng.normal(size=n_obs)]),
    )


def _make_nonstationary_panel_data() -> PanelData:
    rng = np.random.default_rng(21)
    n_entities = 6
    n_periods = 40
    entity_ids = np.repeat(np.arange(n_entities), n_periods)
    time_ids = np.tile(np.arange(n_periods), n_entities)
    group_labels = ["managed_float"] * 3 + ["clean_float"] * 3

    dependent: list[float] = []
    exog_rows: list[list[float]] = []
    for entity_idx in range(n_entities):
        base_scale = 0.18 if entity_idx < 3 else 0.28
        stress = np.concatenate([np.zeros(20), np.ones(20)])
        reserve_pressure = rng.normal(scale=0.4, size=n_periods)
        shocks = np.concatenate(
            [
                rng.normal(scale=base_scale, size=20),
                rng.normal(scale=base_scale * 1.9, size=20),
            ]
        )
        series = np.zeros(n_periods, dtype=float)
        for t in range(1, n_periods):
            series[t] = 0.25 * series[t - 1] + shocks[t]
        dependent.extend(series.tolist())
        exog_rows.extend(np.column_stack([stress, reserve_pressure]).tolist())

    return PanelData(
        dependent=np.asarray(dependent, dtype=float),
        exog=np.asarray(exog_rows, dtype=float),
        entity_ids=entity_ids,
        time_ids=time_ids,
        feature_names=["stress_window", "reserve_pressure"],
        metadata={"group_labels": group_labels, "target_id": "fx_policy_risk"},
    )


@pytest.mark.parametrize(
    ("fqn", "params", "required_packages"),
    [
        ("econometrics.regression.quantile_regression@1.0.0", {"quantile": 0.5}, ("statsmodels",)),
        ("econometrics.timeseries.local_projections@1.0.0", {"max_horizon": 3}, ("statsmodels",)),
        ("econometrics.timeseries.garch@1.0.0", {"p": 1, "q": 1}, ("arch",)),
        (
            "econometrics.panel.nonstationary_garch@1.0.0",
            {"p": 1, "q": 1, "max_breaks": 1, "min_segment_length": 12},
            ("arch", "ruptures"),
        ),
        ("econometrics.timeseries.change_point@1.0.0", {"penalty": 4.0}, ("ruptures",)),
    ],
)
def test_advanced_estimators_run(
    fqn: str,
    params: dict[str, float],
    required_packages: tuple[str, ...],
) -> None:
    for package in required_packages:
        pytest.importorskip(package)

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    if "quantile_regression" in fqn:
        state = _make_panel_data()
    elif "nonstationary_garch" in fqn:
        state = _make_nonstationary_panel_data()
    else:
        state = _make_time_series()

    method_cls = registry.get(fqn)
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=state,
        params=params,
        seed=17,
    )

    assert result.output["result"].method_name
    if "nonstationary_garch" in fqn:
        assert result.output["result"].nonstationary_volatility is not None
        assert result.output["forecasting_uncertainty_bundle"] is not None
        assert "policy_risk_benchmark" in result.output["result"].diagnostics
        assert result.output["result"].nonstationary_volatility.coverage is not None
        assert (
            "scenario_benchmarks"
            in result.output["result"].nonstationary_volatility.coverage.metadata
        )


def test_event_study_runs() -> None:
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()

    rng = np.random.default_rng(13)
    outcome = np.vstack(
        [np.linspace(1.0, 3.0, 8) + rng.normal(scale=0.1, size=8) for _ in range(8)]
    )
    outcome[4:, 4:] += 0.6
    state = {
        "outcome": outcome,
        "treatment": np.array([0, 0, 0, 0, 1, 1, 1, 1]),
        "time_treatment": 4,
        "treatment_timing": np.array([-1, -1, -1, -1, 4, 4, 4, 4]),
    }

    method_cls = registry.get("econometrics.panel.event_study@1.0.0")
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=state,
        params={"pre_window": 2, "post_window": 2},
        seed=19,
    )

    assert result.output["result"].method_name == "event_study"
    assert result.output["uncertainty_envelope"] is not None


@pytest.mark.parametrize(
    ("fqn", "params", "required_packages"),
    [
        ("econometrics.diagnostics.hausman_test@1.0.0", {}, ("linearmodels", "scipy")),
        ("econometrics.diagnostics.weak_iv_test@1.0.0", {"n_endogenous": 1}, ("statsmodels",)),
        ("econometrics.diagnostics.sargan_hansen@1.0.0", {"n_endogenous": 1}, ("linearmodels",)),
    ],
)
def test_econometric_diagnostics_run(
    fqn: str,
    params: dict[str, float],
    required_packages: tuple[str, ...],
) -> None:
    for package in required_packages:
        pytest.importorskip(package)

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    method_cls = registry.get(fqn)
    result = dispatcher.dispatch(
        method_class=method_cls,
        signature=method_cls.signature,
        state=_make_panel_data(),
        params=params,
        seed=23,
    )

    assert result.output["result"].test_name


def test_cointegration_and_forecast_backtest_run() -> None:
    pytest.importorskip("statsmodels")

    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()
    dispatcher = MethodDispatcher.get_instance()
    base = _make_time_series()

    cointegration_cls = registry.get("econometrics.diagnostics.cointegration_test@1.0.0")
    coint_state = TimeSeriesData(
        endog=np.column_stack(
            [
                np.asarray(base.endog, dtype=float),
                np.asarray(base.endog, dtype=float)
                + np.random.default_rng(14).normal(scale=0.1, size=base.n_obs),
            ]
        )
    )
    coint_result = dispatcher.dispatch(
        method_class=cointegration_cls,
        signature=cointegration_cls.signature,
        state=coint_state,
        params={},
        seed=29,
    )
    assert coint_result.output["result"].test_name == "cointegration_test"

    backtest_cls = registry.get("econometrics.diagnostics.forecast_backtest@1.0.0")
    backtest_result = dispatcher.dispatch(
        method_class=backtest_cls,
        signature=backtest_cls.signature,
        state=base,
        params={"holdout": 12},
        seed=31,
    )
    assert backtest_result.output["result"].overall_rmse >= 0.0

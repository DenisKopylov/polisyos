from __future__ import annotations

from polisyos.foundry.methods.econometrics import ensure_econometric_methods_registered
from polisyos.foundry.methods.registry import MethodRegistry


def test_register_econometric_methods_queryable() -> None:
    MethodRegistry.reset_instance()
    ensure_econometric_methods_registered()
    registry = MethodRegistry.get_instance()

    signatures = [sig for sig in registry.query() if sig.namespace.startswith("econometrics.")]
    names = {sig.name for sig in signatures}

    assert names == {
        "hausman_test",
        "weak_iv_test",
        "sargan_hansen",
        "cointegration_test",
        "forecast_backtest",
        "fixed_effects",
        "random_effects",
        "panel_data",
        "event_study",
        "two_stage_least_squares",
        "gmm",
        "instrumental_variables",
        "arima",
        "var",
        "time_series",
        "quantile_regression",
        "local_projections",
        "garch",
        "change_point",
        "vecm",
        "bayesian_var",
        "synthetic_did",
        "spatial_autoregressive",
    }

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
        "difference_gmm",
        "system_gmm",
        "event_study",
        "two_stage_least_squares",
        "gmm",
        "arima",
        "var",
        "quantile_regression",
        "local_projections",
        "garch",
        "nonstationary_garch",
        "change_point",
        "vecm",
        "bayesian_var",
        "synthetic_did",
        "spatial_autoregressive",
        # Phase 2 additions
        "logit",
        "probit",
        "multinomial_logit",
        "mixed_logit",
        "blp",
        "heckman",
        "tobit",
        "truncated",
        "poisson",
        "negative_binomial",
        "zero_inflated_poisson",
        "robinson",
        "kernel_regression",
        "post_lasso",
        "post_double_selection",
        "high_dimensional_post_selection",
        "state_dependent_threshold",
        "state_dependent_kink",
        "state_dependent_frd",
        "state_dependent_frkd",
        # Phase 2 factor/decomposition additions
        "dynamic_factor_model",
        "principal_components",
        # Phase 4 mobility additions
        "latent_mobility",
    }

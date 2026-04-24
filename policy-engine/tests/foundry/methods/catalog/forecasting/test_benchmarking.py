from __future__ import annotations

from polisyos.foundry.methods.catalog.forecasting.benchmarking import (
    ForecastBenchmarkRegime,
    ForecastResearchStrategy,
    lookup_phase0_forecasting_recommendation,
    run_phase0_forecasting_benchmark,
)


def test_phase0_forecasting_recommendation_lookup_returns_research_matrix_cell() -> None:
    cell = lookup_phase0_forecasting_recommendation(
        "forecasting.advanced.prophet@1.0.0",
        ForecastBenchmarkRegime.STABLE_MEDIUM,
        1,
    )

    assert cell.strategies == (ForecastResearchStrategy.BAYESIAN_PLUS_CONFORMAL,)


def test_phase0_forecasting_benchmark_smoke_covers_all_seven_methods() -> None:
    results = run_phase0_forecasting_benchmark(
        regimes=(ForecastBenchmarkRegime.STABLE_SMALL,),
        horizons=(1, 4),
        n_trials=1,
        base_seed=2026,
    )

    by_method = {result.method_fqn: result for result in results}

    assert len(by_method) == 7
    assert by_method["forecasting.decomposition.stl@1.0.0"].status == "attached_output_only"
    assert (
        by_method["forecasting.univariate.exponential_smoothing@1.0.0"].current_calibration_method
        == "conformal"
    )
    assert (
        by_method["forecasting.reconciliation.bottom_up@1.0.0"].current_calibration_method
        == "coherent_bootstrap"
    )
    assert by_method["forecasting.advanced.prophet@1.0.0"].research_recommendation_by_horizon[
        1
    ] == ("conformal",)

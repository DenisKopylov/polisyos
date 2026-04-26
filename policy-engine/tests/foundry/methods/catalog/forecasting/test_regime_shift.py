from __future__ import annotations

import numpy as np
import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.catalog.forecasting.benchmarking import (
    run_regime_shift_calibration_benchmark,
)
from polisyos.ir.analytics.regime_shift_forecast import RegimeShiftForecastBundle
from polisyos.ir.artifacts import get_json_artifact


def test_regime_shift_forecaster_emits_hybrid_bundle_with_assignment_and_break_refs(
    isolated_registry,
    tmp_path,
) -> None:
    method = isolated_registry.get("forecasting.regime_shift.hybrid@1.0.0")
    store = FileSystemCAS(tmp_path / "cas")
    series = np.concatenate(
        [
            np.full(30, 10.0),
            np.full(30, 18.0),
        ]
    )

    result = method.pure_step(
        {"series": series},
        {"horizon": 6, "min_dwell": 8, "artifact_store": store},
    )

    bundle = result["regime_shift_forecast_bundle"]
    assert isinstance(bundle, RegimeShiftForecastBundle)
    assert result["forecasting_uncertainty_bundle"] is bundle
    assert result["result"]["breakpoints"] == [30]
    assert result["result"]["benchmark_status"] == "green"
    assert bundle.regime_model_family.value == "hybrid"
    assert bundle.shift_type_assessment.value == "structural"
    assert bundle.assignment_posterior_ref.kind == "ir.regime_assignment_posterior"
    assert bundle.break_posterior_ref is not None
    assert bundle.break_posterior_ref.kind == "ir.break_posterior"
    assert bundle.duration_summary_ref is not None
    assert bundle.benchmark_status.value == "green"
    assert bundle.regime_status.value == "calibrated"

    assignment = get_json_artifact(store, bundle.assignment_posterior_ref.artifact_id)
    assert assignment["posterior_type"] == "hard_assignment_proxy"
    assert set(assignment["states"]) == {"regime_0", "regime_1"}


def test_regime_shift_forecaster_blocks_long_horizon_when_shift_is_still_drifting(
    isolated_registry,
) -> None:
    method = isolated_registry.get("forecasting.regime_shift.hybrid@1.0.0")
    series = np.concatenate([np.full(24, 10.0), np.full(4, 50.0)])

    with pytest.raises(ValueError, match="beyond horizon 12"):
        method.pure_step(
            {"series": series},
            {"horizon": 13, "min_dwell": 4, "break_window": 6},
        )


def test_regime_shift_forecaster_is_registered(isolated_registry) -> None:
    method = isolated_registry.get("forecasting.regime_shift.hybrid@1.0.0")

    assert method.metadata.truthfulness_scope == "marginal_coverage"
    assert method.signature.output_slots


def test_regime_shift_factorial_benchmark_records_acceptance_cell() -> None:
    results = run_regime_shift_calibration_benchmark(
        series_lengths=(64,),
        regime_counts=(2,),
        min_dwells=(8,),
        separations=(2.0,),
        recurring_modes=(False,),
        shift_types=("level",),
        horizon=4,
        n_trials=1,
        base_seed=123,
    )

    assert len(results) == 1
    cell = results[0]
    assert cell.status == "evaluated"
    assert cell.method_fqn == "forecasting.regime_shift.hybrid@1.0.0"
    assert cell.true_breakpoints == (32,)
    assert cell.detected_breakpoints
    assert cell.benchmark_status == "green"
    assert cell.identifiability_status == "identified"
    assert cell.accepted is True

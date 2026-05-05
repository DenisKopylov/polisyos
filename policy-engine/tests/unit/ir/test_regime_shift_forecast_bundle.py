from __future__ import annotations

from datetime import UTC, datetime

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.forecasting_uncertainty import (
    FanChartSpec,
    ForecastCalibrationMethod,
    ForecastCoverageDiagnostic,
    ForecastIntervalSemantics,
    HorizonDiagnosticState,
    HorizonInterval,
    HorizonPolicyRule,
    HorizonPolicySpec,
    HorizonQuantileSet,
)
from polisyos.ir.analytics.regime_shift_forecast import (
    ForecastShiftTypeAssessment,
    RegimeBenchmarkStatus,
    RegimeForecastCalibrationStatus,
    RegimeIdentifiabilityStatus,
    RegimeModelFamily,
    RegimeShiftForecastBundle,
    load_regime_shift_forecast_bundle,
    persist_regime_shift_forecast_bundle,
)
from polisyos.ir.refs import ArtifactRefModel
from polisyos.ir.schema_catalog import get_ir_type
from pydantic import ValidationError


def _now() -> datetime:
    return datetime.now(UTC)


def _ref(hex_digit: str = "a", *, kind: str = "ir.test_artifact") -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=f"sha256:{hex_digit * 64}",
        kind=kind,
        media_type="application/json",
    )


_MISSING = object()


def _sample_bundle(
    *,
    horizon: int = 3,
    regime_model_family: RegimeModelFamily = RegimeModelFamily.HYBRID,
    identifiability_status: RegimeIdentifiabilityStatus = (RegimeIdentifiabilityStatus.IDENTIFIED),
    regime_status: RegimeForecastCalibrationStatus = (RegimeForecastCalibrationStatus.CALIBRATED),
    benchmark_status: RegimeBenchmarkStatus = RegimeBenchmarkStatus.GREEN,
    break_count_ref: ArtifactRefModel | None | object = _MISSING,
    break_ref: ArtifactRefModel | None | object = _MISSING,
    run_length_ref: ArtifactRefModel | None = None,
    duration_ref: ArtifactRefModel | None = None,
) -> RegimeShiftForecastBundle:
    generated_at = _now()
    resolved_break_count_ref = _ref("2") if break_count_ref is _MISSING else break_count_ref
    resolved_break_ref = _ref("3") if break_ref is _MISSING else break_ref
    return RegimeShiftForecastBundle(
        method_fqn="forecasting.regime.hybrid@1.0.0",
        target_id="tax_receipts",
        generated_at=generated_at,
        prediction_interval=(
            HorizonInterval(
                horizon=horizon,
                point=10.0,
                lower=8.0,
                upper=12.0,
                coverage_target=0.9,
                constructor=ForecastCalibrationMethod.BAYESIAN_PLUS_CONFORMAL,
                sample_count=40,
            ),
        ),
        fan_chart=FanChartSpec(
            quantile_levels=(0.05, 0.50, 0.95),
            horizons=(
                HorizonQuantileSet(
                    horizon=horizon,
                    quantiles={"0.05": 8.0, "0.5": 10.0, "0.95": 12.0},
                ),
            ),
        ),
        coverage_diagnostic=ForecastCoverageDiagnostic(
            nominal_coverage=0.9,
            empirical_coverage_by_horizon={horizon: 0.91},
            coverage_gap_by_horizon={horizon: 0.01},
            mean_interval_width_by_horizon={horizon: 4.0},
            conditional_coverage_pvalue_by_horizon={horizon: 0.32},
            independence_pvalue_by_horizon={horizon: 0.29},
            wis_by_horizon={horizon: 1.7},
            sample_count_by_horizon={horizon: 40},
            regime_flags=("regime_conditional_coverage_checked",),
            calibration_window=40,
            last_recalibrated_at=generated_at,
        ),
        horizon_policy=HorizonPolicySpec(
            default_method=ForecastCalibrationMethod.BAYESIAN_PLUS_CONFORMAL,
            rules=(
                HorizonPolicyRule(
                    horizon_start=horizon,
                    horizon_end=horizon,
                    diagnostic_state=HorizonDiagnosticState.GREEN,
                    allowed_methods=(ForecastCalibrationMethod.BAYESIAN_PLUS_CONFORMAL,),
                    gate_eligible=True,
                    regime="hybrid_regime_shift",
                ),
            ),
            gate_eligible=True,
            summary="Regime-conditional coverage gate",
        ),
        interval_semantics=ForecastIntervalSemantics.CONFORMALIZED_PREDICTION_INTERVAL,
        calibration_method=ForecastCalibrationMethod.BAYESIAN_PLUS_CONFORMAL,
        nominal_coverage=0.9,
        sample_size_assumption="minimum dwell time exceeds lag order by regime",
        regime_assumption="hybrid recurring regimes and one-off structural breaks",
        regime_model_family=regime_model_family,
        identifiability_status=identifiability_status,
        regime_status=regime_status,
        regime_count_posterior_ref=_ref("1"),
        break_count_posterior_ref=resolved_break_count_ref,
        assignment_posterior_ref=_ref("4"),
        break_posterior_ref=resolved_break_ref,
        run_length_posterior_ref=run_length_ref,
        permutation_invariant_regime_map_ref=_ref("5"),
        regime_parameter_summary_ref=_ref("6"),
        duration_summary_ref=duration_ref,
        transition_summary_ref=_ref("7"),
        predictive_mixture_ref=_ref("8"),
        regime_conditional_forecasts_ref=_ref("9"),
        calibration_slice_ref=_ref("a"),
        break_recovery_curve_ref=_ref("b"),
        shift_type_assessment=ForecastShiftTypeAssessment.STRUCTURAL,
        shift_type_assessment_ref=_ref("c"),
        identifiability_diagnostics_ref=_ref("d"),
        benchmark_status=benchmark_status,
    )


def test_regime_shift_forecast_bundle_creation() -> None:
    bundle = _sample_bundle()

    assert bundle.regime_model_family is RegimeModelFamily.HYBRID
    assert bundle.identifiability_status is RegimeIdentifiabilityStatus.IDENTIFIED
    assert bundle.regime_status is RegimeForecastCalibrationStatus.CALIBRATED
    assert bundle.benchmark_status is RegimeBenchmarkStatus.GREEN
    assert bundle.shift_type_assessment is ForecastShiftTypeAssessment.STRUCTURAL
    assert bundle.permutation_invariant_regime_map_ref.kind == "ir.test_artifact"


def test_long_horizon_requires_calibrated_regime_status() -> None:
    with pytest.raises(ValidationError, match="beyond horizon 12"):
        _sample_bundle(
            horizon=13,
            regime_status=RegimeForecastCalibrationStatus.UNKNOWN,
        )


def test_calibrated_status_requires_green_benchmark() -> None:
    with pytest.raises(ValidationError, match="green benchmark"):
        _sample_bundle(
            regime_status=RegimeForecastCalibrationStatus.CALIBRATED,
            benchmark_status=RegimeBenchmarkStatus.YELLOW,
        )


def test_changepoint_family_requires_break_uncertainty_refs() -> None:
    with pytest.raises(ValidationError, match="break_count_posterior_ref"):
        _sample_bundle(
            regime_model_family=RegimeModelFamily.CHANGEPOINT,
            break_count_ref=None,
            break_ref=_ref("e"),
        )

    with pytest.raises(ValidationError, match="break_posterior_ref"):
        _sample_bundle(
            regime_model_family=RegimeModelFamily.CHANGEPOINT,
            break_count_ref=_ref("e"),
            break_ref=None,
            run_length_ref=None,
        )


def test_hidden_semi_markov_requires_duration_summary() -> None:
    with pytest.raises(ValidationError, match="duration_summary_ref"):
        _sample_bundle(
            regime_model_family=RegimeModelFamily.HIDDEN_SEMI_MARKOV,
            break_count_ref=None,
            break_ref=None,
            duration_ref=None,
        )


def test_regime_shift_forecast_bundle_cas_roundtrip(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = _sample_bundle()

    ref = persist_regime_shift_forecast_bundle(store, bundle)
    loaded = load_regime_shift_forecast_bundle(store, ref)

    assert ref.kind == "ir.regime_shift_forecast_bundle"
    assert loaded == bundle


def test_regime_shift_forecast_bundle_registered_in_abi_catalog() -> None:
    entry = get_ir_type("RegimeShiftForecastBundle")

    assert entry.abi_key == "regime_shift_forecast_bundle"
    assert entry.abi_schema_file == "regime_shift_forecast_bundle.schema.json"
    assert entry.abi_priority == "p1"

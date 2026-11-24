"""Behavioral regression tests for the BKT-03 honest bias/statistics contract."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import polisyos.scientist.methods.backtesting.orchestrator as orchestrator_module
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.ir_adapter import build_ir_artifact_store
from polisyos.ir.analytics.backtest import BacktestReport, BiasDirection
from polisyos.ir.artifacts import get_json_artifact
from polisyos.scientist.methods.backtesting.orchestrator import BacktestOrchestrator
from polisyos.scientist.methods.backtesting.plan import (
    HistoricalValidationPlan,
    PredictionSource,
)


def _run_provided_report(
    tmp_path: Path,
    *,
    predictions: list[float],
    truths: list[float],
) -> BacktestReport:
    """Run one complete provided-prediction backtest for a regression fixture."""
    history_path = tmp_path / "history.json"
    history_path.write_text('{"metric": [0.0, 0.0, 0.0]}', encoding="utf-8")
    plan = HistoricalValidationPlan(
        plan_id="bkt-03-regression",
        historical_data_path=str(history_path),
        ground_truth_outcomes={"metric": truths},
        target_metrics=["metric"],
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"metric": predictions},
    )
    return BacktestOrchestrator(cas_root=str(tmp_path / ".polisyos")).run([plan])


@pytest.mark.parametrize(
    "predictions",
    [
        [1e16, 1.0, -1e16],
        [1e16, -1e16, 1.0],
        [-1e16, 1.0, 1e16],
    ],
    ids=["positive-middle", "positive-last", "negative-first"],
)
def test_cancellation_permutations_preserve_signed_bias_after_cas_readback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    predictions: list[float],
) -> None:
    """Provided residual permutations retain their source-bound positive mean."""
    from fractions import Fraction
    from math import fsum

    def _unavailable(_module_name: str) -> object:
        raise ModuleNotFoundError("controlled scipy.stats importer denial")

    monkeypatch.setattr(orchestrator_module, "import_module", _unavailable)
    report = _run_provided_report(
        tmp_path,
        predictions=predictions,
        truths=[0.0, 0.0, 0.0],
    )
    assert report.cas_artifact_id is not None
    store = build_ir_artifact_store(tmp_path / ".polisyos")
    stored_report = BacktestReport.model_validate(
        get_json_artifact(_ensure_ir_artifact_store(store), report.cas_artifact_id)
    )

    expected_mean = float(Fraction(1, 3))
    expected_mae = fsum(abs(value) for value in predictions) / len(predictions)
    for observed in (report, stored_report):
        assert observed.n_metrics_evaluated == 3
        assert observed.scenarios[0].compared_count == 3
        assert observed.scenarios[0].mae == pytest.approx(expected_mae)
        assert observed.overall_mae == pytest.approx(expected_mae)
        diagnostic = observed.metric_diagnostics[0]
        assert diagnostic.mean_residual == pytest.approx(expected_mean, abs=1e-15)
        assert diagnostic.magnitude == pytest.approx(expected_mean, abs=1e-15)
        assert diagnostic.residual_sign == "positive"
        assert diagnostic.direction_status == "not_established"
        assert diagnostic.status == "unavailable"
        assert diagnostic.reason == "scipy_ttest_1samp_error:ModuleNotFoundError"
        assert observed.overall_bias_direction is BiasDirection.UNKNOWN
        assert len(observed.detected_biases) == 1
        bias = observed.detected_biases[0]
        assert bias.direction is BiasDirection.UNKNOWN
        assert bias.magnitude == pytest.approx(expected_mean, abs=1e-15)
        assert bias.p_value is None
        assert observed.degraded is True
        assert observed.trust_eligible is False
        assert observed.trust_score is None
        assert observed.trust_grade is None


def test_constant_nonzero_residual_keeps_descriptive_bias_without_significance(
    tmp_path: Path,
) -> None:
    """A constant residual must remain visible when variance blocks a test."""
    report = _run_provided_report(
        tmp_path,
        predictions=[10.0, 10.0, 10.0],
        truths=[0.0, 0.0, 0.0],
    )

    assert report.overall_mae == pytest.approx(10.0)
    assert report.detected_biases
    bias = report.detected_biases[0]
    assert bias.affected_metrics == ["metric"]
    assert bias.magnitude == pytest.approx(10.0)
    assert bias.p_value is None
    assert bias.statistical_test != "one-sample t-test H0(mean_error=0)"
    assert bias.metadata["test_status"] == "not_computable"
    assert bias.metadata["test_reason"] == "zero_variance"
    assert report.overall_bias_direction is BiasDirection.UNKNOWN
    assert bias.direction is BiasDirection.UNKNOWN
    assert report.metric_diagnostics[0].residual_sign == "positive"
    assert report.metric_diagnostics[0].direction_status == "not_established"
    assert report.degraded is True
    assert report.degraded_reasons
    assert report.trust_eligible is False
    assert report.trust_score is None
    assert report.trust_grade is None


def test_small_nonzero_residual_keeps_descriptive_bias_and_degrades_trust(
    tmp_path: Path,
) -> None:
    """A nonzero small sample is descriptive, not evidence of no bias."""
    report = _run_provided_report(
        tmp_path,
        predictions=[0.5, 1.5],
        truths=[0.0, 0.0],
    )

    assert report.overall_mae == pytest.approx(1.0)
    assert report.detected_biases
    bias = report.detected_biases[0]
    assert bias.affected_metrics == ["metric"]
    assert bias.magnitude == pytest.approx(1.0)
    assert bias.p_value is None
    assert bias.metadata["test_status"] == "not_computable"
    assert bias.metadata["test_reason"] == "insufficient_observations"
    assert any("insufficient_observations" in reason for reason in report.degraded_reasons)
    assert report.degraded is True
    assert report.trust_eligible is False
    assert report.trust_score is None
    assert report.trust_grade is None


def test_zero_residual_is_a_separate_no_bias_control(tmp_path: Path) -> None:
    """A truly zero residual remains distinct from an untestable bias."""
    report = _run_provided_report(
        tmp_path,
        predictions=[0.0, 0.0, 0.0],
        truths=[0.0, 0.0, 0.0],
    )

    assert report.overall_mae == pytest.approx(0.0)
    assert report.detected_biases == []
    assert report.overall_bias_direction is BiasDirection.NEUTRAL
    assert report.metric_diagnostics[0].residual_sign == "zero"
    assert report.metric_diagnostics[0].direction_status == "not_applicable"


def test_symmetric_tiny_residual_is_scale_consistent_in_fresh_reports(
    tmp_path: Path,
) -> None:
    """A registered meter-to-centimeter scale preserves the tiny symmetric result."""
    pytest.importorskip("scipy.stats")

    from decimal import Decimal

    from polisyos.fabric.connectors.types.fixed_units import resolve_fixed_unit_factor
    from polisyos.scientist.governance.backtest_matrix import (
        verify_backtest_diagnostic_projection,
    )

    errors_m = [-1e-14, 0.0, 1e-14]
    meter_to_cm = resolve_fixed_unit_factor("m", "cm")
    assert meter_to_cm.multiplier == "100"
    assert meter_to_cm.transform_ref == "fabric://units/fixed-multiplicative/v1"
    assert meter_to_cm.definition_content_sha256
    errors_cm = [
        float(Decimal(str(value)) * Decimal(meter_to_cm.multiplier)) for value in errors_m
    ]
    assert errors_cm == [-1e-12, 0.0, 1e-12]
    persisted: dict[str, BacktestReport] = {}

    for unit_name, predictions in (("meter", errors_m), ("centimeter", errors_cm)):
        case_root = tmp_path / unit_name
        case_root.mkdir()
        report = _run_provided_report(
            case_root,
            predictions=predictions,
            truths=[0.0, 0.0, 0.0],
        )
        assert report.cas_artifact_id is not None
        store = build_ir_artifact_store(case_root / ".polisyos")
        fresh_report = BacktestReport.model_validate(
            get_json_artifact(_ensure_ir_artifact_store(store), report.cas_artifact_id)
        )
        fresh_projection = verify_backtest_diagnostic_projection(fresh_report)

        assert fresh_projection.status == "computed"
        assert fresh_projection.recomputed is True
        for observed in (report, fresh_report):
            diagnostic = observed.metric_diagnostics[0]
            assert observed.overall_bias_direction is BiasDirection.UNKNOWN
            assert observed.degraded is True
            assert observed.trust_eligible is False
            assert observed.trust_score is None
            assert observed.trust_grade is None
            assert observed.detected_biases == []
            assert diagnostic.status == "available"
            assert diagnostic.method_id == "scipy.stats.ttest_1samp"
            assert diagnostic.backend_id == "scipy"
            assert diagnostic.backend_version
            assert diagnostic.statistic == 0.0
            assert diagnostic.p_value == 1.0
            assert diagnostic.mean_residual == 0.0
            assert diagnostic.magnitude == 0.0
            assert diagnostic.residual_sign == "zero"
            assert diagnostic.direction_status == "not_established"
            assert diagnostic.unresolved_assumptions == [
                "residual_independence",
                "multiplicity_policy",
                "population_scope",
                "metric_direction",
            ]

        projected = fresh_projection.metric_diagnostics
        assert projected is not None and len(projected) == 1
        assert projected[0]["status"] == "available"
        assert projected[0]["method_id"] == "scipy.stats.ttest_1samp"
        assert projected[0]["p_value"] == 1.0
        persisted[unit_name] = fresh_report

    meter = persisted["meter"]
    centimeter = persisted["centimeter"]
    assert centimeter.overall_mae == pytest.approx(meter.overall_mae * 100.0, rel=1e-12, abs=0.0)
    assert centimeter.overall_rmse == pytest.approx(
        meter.overall_rmse * 100.0, rel=1e-12, abs=0.0
    )
    meter_diagnostic = meter.metric_diagnostics[0]
    centimeter_diagnostic = centimeter.metric_diagnostics[0]
    assert centimeter_diagnostic.status == meter_diagnostic.status
    assert centimeter_diagnostic.method_id == meter_diagnostic.method_id
    assert centimeter_diagnostic.statistic == meter_diagnostic.statistic
    assert centimeter_diagnostic.p_value == meter_diagnostic.p_value

    exact_zero_root = tmp_path / "exact-zero"
    exact_zero_root.mkdir()
    exact_zero = _run_provided_report(
        exact_zero_root,
        predictions=[0.0, 0.0, 0.0],
        truths=[0.0, 0.0, 0.0],
    )
    assert exact_zero.cas_artifact_id is not None
    exact_zero_store = build_ir_artifact_store(exact_zero_root / ".polisyos")
    exact_zero_fresh = BacktestReport.model_validate(
        get_json_artifact(_ensure_ir_artifact_store(exact_zero_store), exact_zero.cas_artifact_id)
    )
    assert exact_zero.overall_mae == exact_zero_fresh.overall_mae == 0.0
    assert exact_zero.overall_rmse == exact_zero_fresh.overall_rmse == 0.0
    assert exact_zero_fresh.metric_diagnostics[0].status == "exact_zero"
    assert exact_zero_fresh.metric_diagnostics[0].method_id is None
    assert exact_zero_fresh.metric_diagnostics[0].p_value is None
    assert exact_zero_fresh.metric_diagnostics[0].direction_status == "not_applicable"
    exact_zero_projection = verify_backtest_diagnostic_projection(exact_zero_fresh)
    assert exact_zero_projection.status == "computed"
    assert exact_zero_projection.recomputed is True
    assert exact_zero_projection.metric_diagnostics is not None
    assert exact_zero_projection.metric_diagnostics[0]["status"] == "exact_zero"


def test_small_sample_ttest_matches_scipy_reference() -> None:
    """The small-n reference is Student's t, not a normal approximation."""
    scipy_stats = pytest.importorskip("scipy.stats")
    errors = np.asarray([0.5, 1.5, 2.5], dtype=float)

    expected = float(scipy_stats.ttest_1samp(errors, popmean=0.0).pvalue)
    observed = BacktestOrchestrator._two_sided_ttest_pvalue(errors)

    assert observed == pytest.approx(expected, rel=1e-10, abs=1e-10)
    assert observed == pytest.approx(0.121690, abs=1e-6)


def test_tiny_nonconstant_ttest_matches_ordinary_scale_scipy_reference() -> None:
    """A tiny but distinct cohort is normalized without changing its t statistic."""
    scipy = pytest.importorskip("scipy")
    scipy_stats = pytest.importorskip("scipy.stats")
    tiny_errors = np.asarray([1e-200, 2e-200, 3e-200], dtype=float)
    ordinary_errors = np.asarray([1.0, 2.0, 3.0], dtype=float)
    with np.errstate(under="ignore"):
        assert float(np.std(tiny_errors, ddof=1)) == 0.0

    expected = scipy_stats.ttest_1samp(
        ordinary_errors,
        popmean=0.0,
        alternative="two-sided",
    )
    observed = BacktestOrchestrator._two_sided_ttest(tiny_errors)

    assert observed.status == "available"
    assert observed.method_id == "scipy.stats.ttest_1samp"
    assert observed.backend_id == "scipy"
    assert observed.backend_version == scipy.__version__
    assert observed.statistic is not None and observed.statistic != 0.0
    assert observed.statistic == pytest.approx(float(expected.statistic), rel=1e-10, abs=1e-10)
    assert observed.p_value == pytest.approx(float(expected.pvalue), rel=1e-10, abs=1e-10)


def test_cancellation_scipy_mismatch_is_unavailable_after_cas_readback(
    tmp_path: Path,
) -> None:
    """A real SciPy result that loses the source mean cannot enter the report."""
    from fractions import Fraction

    scipy_stats = pytest.importorskip("scipy.stats")
    predictions = [1e16, 1.0, -1e16]
    raw = scipy_stats.ttest_1samp(
        np.asarray(predictions, dtype=float),
        popmean=0.0,
        alternative="two-sided",
    )
    assert float(raw.statistic) == 0.0
    assert float(raw.pvalue) == 1.0

    report = _run_provided_report(
        tmp_path,
        predictions=predictions,
        truths=[0.0, 0.0, 0.0],
    )
    assert report.cas_artifact_id is not None
    store = build_ir_artifact_store(tmp_path / ".polisyos")
    stored_report = BacktestReport.model_validate(
        get_json_artifact(_ensure_ir_artifact_store(store), report.cas_artifact_id)
    )
    expected_mean = float(Fraction(1, 3))
    for observed in (report, stored_report):
        diagnostic = observed.metric_diagnostics[0]
        assert diagnostic.mean_residual == pytest.approx(expected_mean, abs=1e-15)
        assert diagnostic.magnitude == pytest.approx(expected_mean, abs=1e-15)
        assert diagnostic.residual_sign == "positive"
        assert diagnostic.direction_status == "not_established"
        assert diagnostic.status == "unavailable"
        assert diagnostic.reason == "scipy_ttest_1samp_numeric_range"
        assert diagnostic.method_id is None
        assert diagnostic.backend_id is None
        assert diagnostic.backend_version is None
        assert diagnostic.statistic is None
        assert diagnostic.p_value is None
        assert len(observed.detected_biases) == 1
        bias = observed.detected_biases[0]
        assert bias.direction is BiasDirection.UNKNOWN
        assert bias.magnitude == pytest.approx(expected_mean, abs=1e-15)
        assert bias.p_value is None
        assert observed.trust_eligible is False


def test_ttest_refuses_unrepresentable_finite_statistic_with_typed_reason() -> None:
    """Finite source values cannot justify a statistic outside binary64 range."""
    from fractions import Fraction

    errors = np.asarray([1e308, 1e-30, -1e308], dtype=float)
    exact_mean = sum(Fraction.from_float(float(value)) for value in errors) / len(errors)
    assert float(exact_mean) > 0.0

    observed = BacktestOrchestrator._two_sided_ttest(errors)

    assert observed.status == "unavailable"
    assert observed.reason == "scipy_ttest_1samp_numeric_range"
    assert observed.method_id is None
    assert observed.backend_id is None
    assert observed.backend_version is None
    assert observed.statistic is None
    assert observed.p_value is None


def test_scipy_unavailability_preserves_metrics_and_withholds_trust(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """An unavailable test backend is explicit and cannot produce positive trust."""

    def _unavailable(_module_name: str) -> object:
        raise ModuleNotFoundError("simulated scipy.stats unavailability")

    monkeypatch.setattr(orchestrator_module, "import_module", _unavailable)
    report = _run_provided_report(
        tmp_path,
        predictions=[0.5, 1.5, 2.5],
        truths=[0.0, 0.0, 0.0],
    )

    scenario = report.scenarios[0]
    assert scenario.compared_count == 3
    assert scenario.mae == pytest.approx(1.5)
    assert report.overall_mae == pytest.approx(1.5)
    assert report.degraded is True
    assert report.degraded_reasons
    assert report.trust_eligible is False
    assert report.trust_score is None
    assert report.trust_grade is None
    assert report.detected_biases
    bias = report.detected_biases[0]
    assert bias.magnitude == pytest.approx(1.5)
    assert bias.p_value is None
    assert "t-test" not in bias.statistical_test.lower()
    diagnostic = report.metric_diagnostics[0]
    assert diagnostic.status == "unavailable"
    assert diagnostic.method_id is None
    assert diagnostic.backend_id is None
    assert diagnostic.backend_version is None
    assert diagnostic.p_value is None
    assert diagnostic.reason == "scipy_ttest_1samp_error:ModuleNotFoundError"


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        ("missing_method", "scipy_ttest_1samp_missing"),
        ("nan_p_value", "scipy_ttest_1samp_invalid_result"),
        ("negative_p_value", "scipy_ttest_1samp_invalid_result"),
        ("above_one_p_value", "scipy_ttest_1samp_invalid_result"),
        ("nonfinite_statistic", "scipy_ttest_1samp_invalid_statistic"),
        ("backend_exception", "scipy_ttest_1samp_error:RuntimeError"),
    ],
    ids=[
        "method-missing",
        "p-nan",
        "p-below-zero",
        "p-above-one",
        "statistic-nonfinite",
        "backend-raises",
    ],
)
def test_invalid_scipy_execution_persists_source_bound_residual_only_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure: str,
    reason: str,
) -> None:
    """Invalid SciPy outcomes retain real residuals and cannot acquire significance."""
    from types import SimpleNamespace
    from polisyos.scientist.governance.backtest_matrix import (
        verify_backtest_diagnostic_projection,
    )

    imports: list[str] = []
    calls: list[str] = []

    def _ttest_1samp(
        _values: np.ndarray,
        *,
        popmean: float,
        alternative: str,
    ) -> object:
        assert popmean == 0.0
        assert alternative == "two-sided"
        calls.append("ttest_1samp")
        if failure == "backend_exception":
            raise RuntimeError("controlled SciPy execution failure")
        if failure == "nan_p_value":
            p_value = float("nan")
        elif failure == "negative_p_value":
            p_value = -0.01
        elif failure == "above_one_p_value":
            p_value = 1.01
        else:
            p_value = 0.25
        statistic = float("inf") if failure == "nonfinite_statistic" else 1.5
        return SimpleNamespace(statistic=statistic, pvalue=p_value)

    def _controlled_import(module_name: str) -> object:
        imports.append(module_name)
        if module_name == "scipy":
            return SimpleNamespace(__version__="controlled-version")
        if module_name != "scipy.stats":
            pytest.fail(f"unexpected import after invalid result: {module_name}")
        if failure == "missing_method":
            return SimpleNamespace()
        return SimpleNamespace(ttest_1samp=_ttest_1samp)

    monkeypatch.setattr(orchestrator_module, "import_module", _controlled_import)
    report = _run_provided_report(
        tmp_path,
        predictions=[0.5, 1.5, 2.5],
        truths=[0.0, 0.0, 0.0],
    )

    assert report.cas_artifact_id is not None
    store = build_ir_artifact_store(tmp_path / ".polisyos")
    stored_report = BacktestReport.model_validate(
        get_json_artifact(_ensure_ir_artifact_store(store), report.cas_artifact_id)
    )
    fresh_projection = verify_backtest_diagnostic_projection(stored_report)

    expected_imports = ["scipy.stats", "scipy.stats"]
    if failure == "nonfinite_statistic":
        expected_imports = ["scipy.stats", "scipy", "scipy.stats", "scipy"]
    assert imports == expected_imports
    assert calls == ([] if failure == "missing_method" else ["ttest_1samp", "ttest_1samp"])
    assert fresh_projection.status == "unavailable"
    assert fresh_projection.recomputed is False
    assert fresh_projection.reason == "scipy_ttest_1samp_fresh_backend_unavailable"
    assert fresh_projection.metric_diagnostics is not None
    fresh_diagnostic = fresh_projection.metric_diagnostics[0]
    assert fresh_diagnostic["status"] == "unavailable"
    assert fresh_diagnostic["reason"] == "scipy_ttest_1samp_fresh_backend_unavailable"
    assert fresh_diagnostic["mean_residual"] == pytest.approx(1.5)
    assert fresh_diagnostic["magnitude"] == pytest.approx(1.5)
    assert fresh_diagnostic["p_value"] is None
    for observed in (report, stored_report):
        assert observed.scenarios[0].compared_count == 3
        assert observed.scenarios[0].mae == pytest.approx(1.5)
        assert observed.overall_mae == pytest.approx(1.5)
        assert observed.degraded is True
        assert observed.overall_bias_direction is BiasDirection.UNKNOWN
        assert observed.trust_eligible is False
        assert observed.trust_score is None
        assert observed.trust_grade is None

        diagnostic = observed.metric_diagnostics[0]
        assert diagnostic.status == "unavailable"
        assert diagnostic.reason == reason
        assert diagnostic.n == 3
        assert diagnostic.mean_residual == pytest.approx(1.5)
        assert diagnostic.magnitude == pytest.approx(1.5)
        assert diagnostic.residual_sign == "positive"
        assert diagnostic.direction_status == "not_established"
        assert diagnostic.method_id is None
        assert diagnostic.backend_id is None
        assert diagnostic.backend_version is None
        assert diagnostic.statistic is None
        assert diagnostic.p_value is None
        assert diagnostic.unresolved_assumptions == [
            "residual_independence",
            "multiplicity_policy",
            "population_scope",
            "metric_direction",
        ]

        assert len(observed.detected_biases) == 1
        bias = observed.detected_biases[0]
        assert bias.direction is BiasDirection.UNKNOWN
        assert bias.magnitude == pytest.approx(1.5)
        assert bias.p_value is None


@pytest.mark.parametrize(
    ("predictions", "truths", "reason"),
    [
        ([0.99, 1.0, 1.01], [1.0, 1.0, 1.0], "scipy_ttest_1samp_error:ModuleNotFoundError"),
        ([0.99, 1.01], [1.0, 1.0], "insufficient_observations"),
        (
            [0.99, 1.0, 1.0100000000003],
            [1.0, 1.0, 1.0],
            "scipy_ttest_1samp_error:ModuleNotFoundError",
        ),
        ([1e-14, 1e-14, 1e-14], [0.0, 0.0, 0.0], "zero_variance"),
        (
            [-1e-14, 0.0, 1e-14],
            [0.0, 0.0, 0.0],
            "scipy_ttest_1samp_error:ModuleNotFoundError",
        ),
        ([1e-14], [0.0], "insufficient_observations"),
    ],
    ids=[
        "balanced-unavailable-backend",
        "balanced-insufficient-n",
        "near-zero-mean-unavailable-backend",
        "tiny-constant-nonzero",
        "tiny-balanced-nonzero",
        "tiny-single-nonzero",
    ],
)
def test_untestable_nonzero_errors_withhold_trust_after_cas_readback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    predictions: list[float],
    truths: list[float],
    reason: str,
) -> None:
    """Mean cancellation and numerical tolerances cannot stand in for a test."""

    def _unavailable(_module_name: str) -> object:
        raise ModuleNotFoundError("controlled scipy.stats importer denial")

    monkeypatch.setattr(orchestrator_module, "import_module", _unavailable)
    report = _run_provided_report(tmp_path, predictions=predictions, truths=truths)
    assert report.cas_artifact_id is not None
    store = build_ir_artifact_store(tmp_path / ".polisyos")
    stored_report = BacktestReport.model_validate(
        get_json_artifact(_ensure_ir_artifact_store(store), report.cas_artifact_id)
    )

    errors = np.asarray(predictions) - np.asarray(truths)
    assert np.any(errors != 0.0)
    assert abs(float(np.mean(errors))) < 1e-12
    test_result = BacktestOrchestrator._two_sided_ttest(errors)
    assert test_result.p_value is None
    assert test_result.reason == reason
    for observed in (report, stored_report):
        assert observed.n_metrics_evaluated == len(errors)
        assert observed.overall_mae == pytest.approx(float(np.mean(np.abs(errors))))
        assert observed.overall_mae > 0.0
        assert observed.degraded is True
        assert any(reason in item for item in observed.degraded_reasons)
        assert observed.trust_eligible is False
        assert observed.trust_score is None
        assert observed.trust_grade is None


def test_bias_magnitude_preserves_absolute_signed_mean_not_mae(tmp_path: Path) -> None:
    """The B172 bias magnitude is the absolute signed mean residual."""
    predictions = [-1.0, 3.0, 3.0]
    truths = [0.0, 0.0, 0.0]
    report = _run_provided_report(tmp_path, predictions=predictions, truths=truths)
    errors = np.asarray(predictions) - np.asarray(truths)
    expected = abs(float(np.mean(errors)))

    assert report.overall_mae == pytest.approx(float(np.mean(np.abs(errors))))
    assert report.overall_mae > expected
    assert report.detected_biases[0].magnitude == pytest.approx(expected)
    assert report.metric_diagnostics[0].magnitude == pytest.approx(expected)


def test_balanced_nonzero_errors_use_real_scipy_before_trust(
    tmp_path: Path,
) -> None:
    """Available Student's t evidence differs from merely zero mean error."""
    scipy_stats = pytest.importorskip("scipy.stats")
    predictions = [0.99, 1.0, 1.01]
    truths = [1.0, 1.0, 1.0]
    errors = np.asarray(predictions) - np.asarray(truths)
    expected = float(scipy_stats.ttest_1samp(errors, popmean=0.0).pvalue)
    test_result = BacktestOrchestrator._two_sided_ttest(errors)

    assert test_result.p_value == pytest.approx(expected)
    assert test_result.p_value == pytest.approx(1.0)
    assert test_result.status == "available"
    assert test_result.test_name == "one-sample t-test H0(mean_error=0)"
    report = _run_provided_report(tmp_path, predictions=predictions, truths=truths)
    assert report.overall_mae > 0.0
    assert report.degraded is True and report.trust_eligible is False
    assert report.trust_score is None and report.trust_grade is None
    assert report.overall_bias_direction is BiasDirection.UNKNOWN
    diagnostic = report.metric_diagnostics[0]
    assert diagnostic.status == "available" and diagnostic.method_id == "scipy.stats.ttest_1samp"
    assert diagnostic.p_value == pytest.approx(1.0)
    assert diagnostic.residual_sign == "zero" and diagnostic.direction_status == "not_established"
    assert report.detected_biases == []
    assert diagnostic.magnitude == pytest.approx(abs(float(np.mean(errors))))
    assert "metric_direction_not_established:metric" in report.degraded_reasons


@pytest.mark.parametrize("truths", [[1.0], [1.0, 1.0, 1.0]])
def test_exact_zero_error_control_does_not_claim_backend_availability(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    truths: list[float],
) -> None:
    """Exactly equal observations need no significance claim to retain zero error."""

    def _unavailable(_module_name: str) -> object:
        raise ModuleNotFoundError("controlled scipy.stats importer denial")

    monkeypatch.setattr(orchestrator_module, "import_module", _unavailable)
    errors = np.zeros(len(truths), dtype=float)
    assert BacktestOrchestrator._two_sided_ttest(errors).p_value is None
    assert BacktestOrchestrator._two_sided_ttest(errors).status == "not_computable"
    report = _run_provided_report(tmp_path, predictions=truths, truths=truths)
    assert report.overall_mae == 0.0
    assert report.overall_rmse == 0.0
    assert report.detected_biases == []
    assert report.metric_diagnostics[0].status == "exact_zero"
    assert report.metric_diagnostics[0].method_id is None
    assert report.degraded is True
    assert "backtest_source_not_established" in report.degraded_reasons
    assert report.trust_eligible is False
    assert report.trust_score is None and report.trust_grade is None


def test_s1_report_retains_method_identity_for_nonsignificant_result(tmp_path: Path) -> None:
    pytest.importorskip("scipy.stats")
    report = _run_provided_report(
        tmp_path,
        predictions=[100.0, 100.0, 100.0],
        truths=[99.5, 98.5, 97.5],
    )
    diagnostic = next(item for item in report.metric_diagnostics if item.metric_name == "metric")
    assert diagnostic.status == "available"
    assert diagnostic.method_id == "scipy.stats.ttest_1samp"
    assert diagnostic.backend_id == "scipy" and diagnostic.backend_version
    assert diagnostic.n == 3 and diagnostic.statistic is not None
    assert diagnostic.p_value == pytest.approx(0.121690, abs=1e-6)
    assert (
        diagnostic.residual_sign == "positive" and diagnostic.direction_status == "not_established"
    )
    assert "metric_direction" in diagnostic.unresolved_assumptions
    assert {"residual_independence", "multiplicity_policy"} <= set(
        diagnostic.unresolved_assumptions
    )

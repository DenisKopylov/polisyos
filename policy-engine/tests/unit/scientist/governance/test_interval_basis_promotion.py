"""Actual C5b replay/CAS interval completeness; approval inputs are fixtures."""

from __future__ import annotations

import json
import runpy
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.analytics.interference import InterferenceCertificate
from polisyos.ir.observation.bundles import BacktestPlanBundle, ContractCompatibilityTarget
from polisyos.ir.observation.contract_compilers import SpecificationCurveInput
from polisyos.ir.registry.refs import BacktestReportRef
from polisyos.scientist.governance.backtest_matrix import BacktestKind, BacktestMatrixRunner
from polisyos.scientist.governance.calibration_leaderboard import CalibrationLeaderboard
from polisyos.scientist.governance.calibration_validation import (
    CalibrationValidationRunner,
    CalibrationValidationRunnerInput,
    load_calibration_validation_bundle,
)
from polisyos.scientist.methods.backtesting.plan import HistoricalValidationPlan, PredictionSource


def _bundle(tmp_path, kind, intervals):
    path = tmp_path / (kind.value + ".json")
    path.write_text(json.dumps({"m": [0.0, 0.0, 0.0]}))
    plan = HistoricalValidationPlan(
        plan_id=kind.value,
        historical_data_path=str(path),
        prediction_source=PredictionSource.PROVIDED,
        predicted_outcomes={"m": [0.0, 0.0, 0.0]},
        ground_truth_outcomes={"m": [0.0, 0.0, 0.0]},
        prediction_intervals=None if intervals is None else {"m": intervals},
    )
    return BacktestPlanBundle(
        contract_target=ContractCompatibilityTarget(
            contract_id=kind.value, contract_fqn="test.plan"
        ),
        required_fields=["m"],
        plans=[plan.model_dump(mode="json")],
    )


@pytest.mark.parametrize("profile", ["complete", "partial", "point_only"])
def test_actual_validation_matrix_leaderboard_and_fresh_cas_consume_interval_basis(
    tmp_path, profile
):
    fixture = runpy.run_path(str(Path(__file__).with_name("test_calibration_validation.py")))
    store = FileSystemCAS(tmp_path / "cas")
    candidate = store.put_json(
        {"synthetic_candidate": True},
        PutOptions(kind="test.candidate", media_type="application/json"),
    )
    intervals = {"complete": [(-1.0, 1.0)] * 3, "partial": [(-1.0, 1.0)], "point_only": None}[
        profile
    ]
    result = CalibrationValidationRunner(store).run(
        CalibrationValidationRunnerInput(
            run_id="interval-" + profile,
            candidate_ref=candidate,
            governance_report=fixture["_governance_report"](),
            calibration_fit_score=0.9,
            backtest_plan_bundles={
                kind: _bundle(tmp_path, kind, intervals) for kind in BacktestKind
            },
            specification_curve_input=SpecificationCurveInput(
                specification_ids=["a", "b"], estimates=[0.3, 0.31], standard_errors=[0.1, 0.1]
            ),
            downstream_utility_report=fixture["_utility_report"](),
            network_interference_report=fixture["_interference_report"](),
            interference_certificate=InterferenceCertificate(
                supported_query_family="spillover",
                fallback_mode="pairwise",
                reduction_error_bound=0.05,
            ),
            strategic_summary={
                "fallback_mode": "exact_equilibrium",
                "multiplicity_note": "disclosed",
            },
            baseline_metrics={"policy_value": 100.0},
        )
    )
    fresh = load_calibration_validation_bundle(FileSystemCAS(tmp_path / "cas"), result.bundle_ref)
    report = load_backtest_report(store, fresh.backtest_report_ref)
    assert len(report.scenarios) == 5
    assert sum(s.interval_requested_count for s in report.scenarios) == (
        0 if profile == "point_only" else 15
    )
    expected_evaluated = {"complete": 15, "partial": 5, "point_only": 0}[profile]
    assert sum(s.interval_evaluated_count for s in report.scenarios) == expected_evaluated
    eligible = fresh.leaderboard_entry.metrics.eligible_for_promotion
    assert eligible is (profile != "partial")  # fixture policy outcome, no institutional authority
    if profile == "partial":
        assert fresh.backtest_matrix.composite_score is None
        assert all(s.rmse == 0.0 for s in report.scenarios)
        assert all(s.coverage_probability == 1.0 for s in report.scenarios)
        assert "backtest_interval_basis_limited" in fresh.leaderboard_entry.metrics.gap_flags
        forged = fresh.backtest_matrix.model_copy(deep=True)
        forged.composite_score = 1.0
        forged.gap_flags = []
        for item in forged.kind_results:
            item.status, item.score, item.gap_flag = "ok", 1.0, None
        # Consumers resolve original CAS rows instead of accepting these retained positive markers.
        entry = CalibrationLeaderboard(store).build_entry(
            run_id="forged",
            candidate_ref=candidate,
            governance_report=fixture["_governance_report"](),
            calibration_fit_score=0.9,
            backtest_matrix=forged,
            stress_scenarios=fresh.stress_scenarios,
        )
        assert not entry.metrics.eligible_for_promotion
        assert "backtest_interval_basis_limited" in entry.metrics.gap_flags


@pytest.mark.parametrize("profile", ["wrong_kind", "wrong_schema", "missing", "corrupt"])
def test_leaderboard_resolves_report_profile_and_bytes_before_accepting_shape(tmp_path, profile):
    fixture = runpy.run_path(str(Path(__file__).with_name("test_calibration_leaderboard.py")))
    store = FileSystemCAS(tmp_path / "cas")
    matrix = BacktestMatrixRunner(store).run(
        {kind: _bundle(tmp_path, kind, None) for kind in BacktestKind}
    )
    report = load_backtest_report(store, matrix.backtest_report_ref)
    if profile == "missing":
        matrix.backtest_report_ref = BacktestReportRef(artifact_id="sha256:" + "0" * 64)
    elif profile == "corrupt":
        # Corrupt the actual stored blob, leaving the typed ref and positive matrix markers.
        store._paths(matrix.backtest_report_ref.artifact_id)[0].write_bytes(b"{}")
    else:
        payload = report.model_dump(mode="json")
        payload["metadata"]["profile_negative"] = profile
        wrong = store.put_json(
            payload,
            PutOptions(
                kind="test.other_report" if profile == "wrong_kind" else "ir.backtest_report",
                media_type="application/json",
                schema=SchemaInfo(
                    name="ir.backtest_report",
                    version="9.9" if profile == "wrong_schema" else "1.0",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        # A correctly shaped report is insufficient when its actual CAS profile differs.
        matrix.backtest_report_ref = BacktestReportRef(artifact_id=wrong.artifact_id)
    entry = CalibrationLeaderboard(store).build_entry(
        run_id="profile-negative",
        candidate_ref=None,
        governance_report=fixture["_governance_report"](),
        calibration_fit_score=0.9,
        backtest_matrix=matrix,
        stress_scenarios=fixture["_stress_result"](),
    )
    assert not entry.metrics.eligible_for_promotion
    assert "backtest_interval_basis_unresolved" in entry.metrics.gap_flags

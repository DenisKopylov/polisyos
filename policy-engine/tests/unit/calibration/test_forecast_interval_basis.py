"""Content-bound predictive fixture evidence is separate from Runtime authority."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from polisyos.calibration.forecast_bridge import (
    load_empirical_calibration_evidence,
    persist_empirical_calibration_evidence,
    produce_empirical_calibration_evidence,
)
from polisyos.core.artifacts import FileSystemCAS
from polisyos.ir.analytics.backtest import persist_backtest_report
from polisyos.ir.artifacts import InputRef


@pytest.mark.parametrize("marker", ["missing", "fake_complete", "limited"])
def test_actual_forecast_evidence_does_not_admit_conditional_partial_pairs(tmp_path, marker):
    fixture = runpy.run_path(str(Path(__file__).parents[1] / "remediation/test_frc_02_bridge.py"))
    store, _, report, refs = fixture["_persist_report"](
        tmp_path, label=marker, observations=(True, None, None), threshold=0.5
    )
    scenario = report.scenarios[0]
    if marker != "missing":
        scenario.metadata["interval_admission"] = {
            "status": "evaluated" if marker == "fake_complete" else "limited",
            "requested_count": 3,
            "evaluated_count": 3,
        }
    ref = persist_backtest_report(
        store,
        report,
        inputs=[
            InputRef(artifact_id=value["artifact_id"], role=role) for role, value in refs.items()
        ],
    )
    evidence = produce_empirical_calibration_evidence(store, ref, context=fixture["_context"](refs))
    assert evidence.context_bound  # fixture content/role reconciliation, no current EvalSafety
    assert evidence.recomputed_denominator == 1
    assert evidence.recomputed_pass_rate == 1.0
    assert "interval_basis_limited" in evidence.failure_codes
    assert not evidence.usable_for_calibration and not evidence.floor_passed
    with pytest.raises(ValueError, match="blocked"):
        persist_empirical_calibration_evidence(store, evidence)


def test_complete_predictive_bridge_pending_is_not_refused_by_generic_degraded_flag(tmp_path):
    fixture = runpy.run_path(str(Path(__file__).parents[1] / "remediation/test_frc_02_bridge.py"))
    store, _, report, refs = fixture["_persist_report"](
        tmp_path, label="complete-predictive", observations=(True, True, True), threshold=0.5
    )
    report.degraded, report.trust_eligible = True, False
    report.degraded_reasons = ["predictive_only_bridge_pending"]
    ref = persist_backtest_report(
        store,
        report,
        inputs=[
            InputRef(artifact_id=value["artifact_id"], role=role) for role, value in refs.items()
        ],
    )
    evidence = produce_empirical_calibration_evidence(store, ref, context=fixture["_context"](refs))
    assert evidence.usable_for_calibration and evidence.floor_passed
    assert evidence.recomputed_denominator == 3
    eref = persist_empirical_calibration_evidence(store, evidence)
    fresh = load_empirical_calibration_evidence(FileSystemCAS(store.root), eref)
    assert fresh.usable_for_calibration
    assert fresh.authority_scope == "predictive_only"
    assert "s10_authority" in fresh.may_not_use_for

"""A-owned status/reason packet; FAIL on unpatched current A source is expected.

Run from policy-engine. Apply after review alongside the attached patch; this
replaces the unconditional insufficient-history assertion for a missing ref.
"""
from pathlib import Path
from types import SimpleNamespace
import runpy

from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.quality.generation_cycle import RealValueOwnerGateway, _build_s10_forecast_inputs
from polisyos.scientist.methods.backtesting.forecast_owner import ForecastOwner
from polisyos.calibration import load_empirical_calibration_evidence


def _inputs(*, method_result, selected_method_fqn):
    return dict(
        candidate=SimpleNamespace(candidate_id="reason-candidate"),
        problem=SimpleNamespace(design_problem_id="reason-problem", outcome_of_interest=SimpleNamespace(target_variable="metric")),
        world_record=SimpleNamespace(world_model_record_id="reason-world", content_hash="sha256:" + "a" * 64, valid_time_scope="2026-Q1", region_or_jurisdiction="UA"),
        method_result=method_result, selected_method_fqn=selected_method_fqn,
    )


def test_missing_ref_tier_and_s6_share_named_missing_ref_reason():
    result = _build_s10_forecast_inputs(
        **_inputs(method_result=SimpleNamespace(output={}), selected_method_fqn="forecasting.univariate.exponential_smoothing@1.0.0"),
        forecast_tier="observable_calibrated", calibration_status="limit",
        policy_context_ref="policy-context://reason-world", expected_policy_context_ref="policy-context://reason-world",
        false_clear_counts={}, calibration_evidence={},
    )
    assert result["forecast_calibration_record"] is None
    support = result["forecast_support"]
    assert support.forecast_tier == "blocked"
    assert support.s6_limitation_refs == ["s10://calibration/fail-closed/empirical_evidence_ref_missing"]
    assert "empirical_evidence_ref_missing" in support.forecast_authority_disposition_reason


def test_resolved_limited_evidence_keeps_floor_failure_reason(tmp_path: Path):
    helper = runpy.run_path("tests/unit/scientist/methods/backtesting/test_forecast_owner.py")
    store = FileSystemCAS(tmp_path / "cas")
    request, profile = helper["_configured"](store, [1000.,1000.,1000.,1000.])
    result = ForecastOwner(store, empirical_profile_ref=profile).run(request)
    fresh = FileSystemCAS(tmp_path / "cas")
    fields = result.to_s10_input_fields(fresh)
    inputs = RealValueOwnerGateway(repo_root=fresh.root, empirical_evidence_resolver=lambda ref: load_empirical_calibration_evidence(fresh, ref)).produce_forecast_inputs(
        **_inputs(method_result=SimpleNamespace(output=fields, temporal_roles=request.temporal_roles), selected_method_fqn=request.method_fqn)
    )
    record = inputs["forecast_calibration_record"]
    assert record is not None and record.calibration_status == "limit"
    support = inputs["forecast_support"]
    assert support.s6_limitation_refs == ["s10://calibration/calibration_floor_not_met"]
    assert "calibration_floor_not_met" in support.forecast_authority_disposition_reason

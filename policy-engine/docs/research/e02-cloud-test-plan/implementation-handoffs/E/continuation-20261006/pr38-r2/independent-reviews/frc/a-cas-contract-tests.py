"""A-owned FRC01 replacement packet: real ETS/CAS input, explicit refusals.

Apply as tests/unit/runtime/quality/test_frc_source_cas_contract.py after owner
review. Run from policy-engine. The fixture covers generic predictive wiring;
profile admission, independent issuer verification and HTTP default are separate.
"""

import runpy
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from polisyos.calibration import load_empirical_calibration_evidence
from polisyos.core.artifacts import FileSystemCAS
from polisyos.runtime.quality.generation_cycle import (
    RealValueOwnerGateway,
    _resolve_s10_empirical_evidence,
)
from polisyos.scientist.methods.backtesting.forecast_owner import ForecastOwner

if TYPE_CHECKING:
    from pathlib import Path


def _actual_inputs(tmp_path: Path) -> tuple[object, ...]:
    helper = runpy.run_path("tests/unit/scientist/methods/backtesting/test_forecast_owner.py")
    store = FileSystemCAS(tmp_path / "cas")
    request, profile = helper["_configured"](store, [31.0, 32.0, 33.0, 34.0])
    result = ForecastOwner(store, empirical_profile_ref=profile).run(request)
    fresh = FileSystemCAS(tmp_path / "cas")
    fields = result.to_s10_input_fields(fresh)
    return fresh, request, result, fields


def test_actual_ets_cas_fresh_resolver_preserves_six_roles_and_predictive_denials(
    tmp_path: Path,
) -> None:
    fresh, request, result, fields = _actual_inputs(tmp_path)
    evidence = load_empirical_calibration_evidence(fresh, result.empirical_evidence_ref)
    resolved, error = _resolve_s10_empirical_evidence(
        raw_ref=fields["empirical_calibration_evidence_ref"],
        resolver=lambda ref: load_empirical_calibration_evidence(fresh, ref),
        selected_method_fqn=request.method_fqn,
        expected_rule_version_ref=fields["expected_rule_version_ref"],
        expected_temporal_roles=fields["temporal_roles"],
    )
    if not (error is None and resolved is not None):
        raise AssertionError
    gateway = RealValueOwnerGateway(
        repo_root=fresh.root,
        empirical_evidence_resolver=lambda ref: load_empirical_calibration_evidence(fresh, ref),
    )
    inputs = gateway.produce_forecast_inputs(
        candidate=SimpleNamespace(candidate_id="frc-cas-candidate"),
        problem=SimpleNamespace(
            design_problem_id="frc-cas-problem",
            outcome_of_interest=SimpleNamespace(target_variable="metric"),
        ),
        world_record=SimpleNamespace(
            world_model_record_id="frc-cas-world",
            content_hash="sha256:" + "a" * 64,
            valid_time_scope="2026-Q1",
            region_or_jurisdiction="UA",
        ),
        method_result=SimpleNamespace(output=fields, temporal_roles=request.temporal_roles),
        selected_method_fqn=request.method_fqn,
    )
    record = inputs["forecast_calibration_record"]
    if not (record is not None):
        raise AssertionError
    if not (record.denominator == 4 and record.numerator == 4):
        raise AssertionError
    if not (
        str(record.empirical_evidence_ref.artifact_id)
        == str(result.empirical_evidence_ref.artifact_id)
    ):
        raise AssertionError
    for role, value in request.temporal_roles.model_dump().items():
        if not (getattr(record, role) == value == getattr(evidence, role)):
            raise AssertionError
    if not (len(set(request.temporal_roles.model_dump().values())) == 6):
        raise AssertionError
    if not (
        {"causal_effect_authority", "treatment_assignment_authority", "s10_authority"}.issubset(
            set(record.may_not_use_for)
        )
    ):
        raise AssertionError
    if not (fields["verifier_provenance"] == "not_established"):
        raise AssertionError


@pytest.mark.parametrize("defect", ["missing_ref", "wrong_kind", "bad_time", "wrong_rule"])
def test_actual_resolver_refuses_missing_fake_or_temporally_unbound_inputs(
    tmp_path: Path, defect: str
) -> None:
    fresh, request, result, _fields = _actual_inputs(tmp_path)
    raw_ref = result.empirical_evidence_ref
    expected_time = request.temporal_roles
    rule = request.calibration_rule.rule_id
    if defect == "missing_ref":
        raw_ref = None
    elif defect == "wrong_kind":
        raw_ref = result.backtest_report_ref
    elif defect == "bad_time":
        expected_time = request.temporal_roles.model_copy(
            update={"observation_time": datetime(2025, 1, 1, tzinfo=UTC)}
        )
    else:
        rule = "wrong-rule"
    resolved, error = _resolve_s10_empirical_evidence(
        raw_ref=raw_ref,
        resolver=lambda ref: load_empirical_calibration_evidence(fresh, ref),
        selected_method_fqn=request.method_fqn,
        expected_rule_version_ref=rule,
        expected_temporal_roles=expected_time,
    )
    if not (resolved is None and error is not None):
        raise AssertionError

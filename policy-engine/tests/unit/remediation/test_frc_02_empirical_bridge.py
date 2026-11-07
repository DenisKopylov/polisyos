"""Actual ForecastOwner → forecast_bridge evidence boundary witness.

This test keeps the producer, persisted report, and recomputing bridge on the
same CAS.  It intentionally does not manufacture the missing semantic-role
artifacts that would be needed to persist calibration evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import polisyos.calibration.forecast_bridge as forecast_bridge
from polisyos.calibration.forecast_bridge import (
    REFERENCE_SOURCE_INPUT_ROLES,
    persist_empirical_calibration_evidence,
    produce_empirical_calibration_evidence,
)
from polisyos.core.artifacts import FileSystemCAS, resolve_manifest_by_profile
from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.ir.analytics.backtest import (
    load_backtest_report,
    persist_backtest_report,
)
from polisyos.ir.artifacts import InputRef
from polisyos.scientist.methods.backtesting.forecast_owner import ForecastOwner
from tests.unit.remediation.test_frc_02_owner import _request, _rule, _source
from tests.unit.remediation.test_frc_02_s10 import (
    _context,
    _persist_report,
)

_OWNER_SOURCE_ROLE_MAP = {
    "scope_binding": ("candidate_source", "model_spec", "policy_spec", "calibration_rule"),
    "calibration_threshold": ("calibration_rule",),
    "observed_outcome": ("observed_source",),
    "prediction": ("uncertainty_bundle",),
    "evaluation_design": ("training_slice",),
    "credible_evaluation": ("candidate_source",),
    "source_lineage": ("candidate_source", "observed_source"),
    "method_lineage": ("method_artifact", "calibration_rule"),
}


def test_real_forecast_owner_bridge_recomputes_holdout_but_refuses_unbound_persistence(
    tmp_path: Path,
) -> None:
    """Same forecast intervals cannot hide different held-out outcomes."""

    store = FileSystemCAS(tmp_path / "cas")
    rule_ref = _rule(store)
    training = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0]
    owner = ForecastOwner(store)
    in_profile = owner.run(
        _request(
            _source(store, training=training, holdout=[20.0, 21.0, 22.0]),
            rule_ref,
            report_id="frc-owner-bridge-in-profile",
            train_end=len(training),
            horizon=3,
        )
    )
    out_of_profile = owner.run(
        _request(
            _source(store, training=training, holdout=[1000.0, 1001.0, 1002.0]),
            rule_ref,
            report_id="frc-owner-bridge-out-of-profile",
            train_end=len(training),
            horizon=3,
        )
    )

    assert in_profile.point_forecast == out_of_profile.point_forecast
    assert in_profile.predictive_intervals == out_of_profile.predictive_intervals
    assert in_profile.coverage_denominator == out_of_profile.coverage_denominator == 3
    assert in_profile.coverage_numerator != out_of_profile.coverage_numerator
    assert in_profile.empirical_suitability != out_of_profile.empirical_suitability
    assert in_profile.authority_scope == out_of_profile.authority_scope == "predictive_only"
    assert in_profile.bridge_status == out_of_profile.bridge_status == "bridge_pending"

    reports = tuple(
        load_backtest_report(_ensure_ir_artifact_store(store), result.backtest_report_ref)
        for result in (in_profile, out_of_profile)
    )
    assert tuple(report.report_id for report in reports) == (
        in_profile.report_id,
        out_of_profile.report_id,
    )
    assert reports[0].metadata["temporal_roles"] == in_profile.temporal_roles.model_dump(
        mode="json"
    )
    evidence = tuple(
        produce_empirical_calibration_evidence(store, result.backtest_report_ref)
        for result in (in_profile, out_of_profile)
    )
    for result, report_evidence in zip((in_profile, out_of_profile), evidence, strict=True):
        assert report_evidence.recomputed_numerator == result.coverage_numerator
        assert report_evidence.recomputed_denominator == result.coverage_denominator
        assert report_evidence.empirical_observations_available is False
        assert report_evidence.context_bound is False
        assert report_evidence.usable_for_calibration is False
        assert report_evidence.floor_passed is False
        assert "backtest_source_not_established" in report_evidence.failure_codes
        assert "explicit_context_missing" in report_evidence.failure_codes
        assert "s10_authority" in report_evidence.may_not_use_for

    before_ids = {str(artifact_id) for artifact_id in store.iter_artifact_ids()}
    for report_evidence in evidence:
        with pytest.raises(ValueError, match="blocked empirical calibration evidence"):
            persist_empirical_calibration_evidence(store, report_evidence)
    assert {str(artifact_id) for artifact_id in store.iter_artifact_ids()} == before_ids


@pytest.mark.parametrize(
    "role",
    [
        pytest.param("prediction_time", id="prediction_time"),
        pytest.param("observation_time", id="observation_time"),
        pytest.param("policy_effective_time", id="policy_effective_time"),
        pytest.param("data_valid_time", id="data_valid_time"),
        pytest.param("calibration_window_start", id="calibration_window_start"),
        pytest.param("calibration_window_end", id="calibration_window_end"),
    ],
)
def test_bridge_rejects_temporal_roles_that_disagree_with_persisted_report(
    tmp_path: Path,
    role: str,
) -> None:
    """A well-ordered caller time tuple cannot rebind another report period."""

    store, report_ref, refs = _persist_report(
        tmp_path,
        label="report-time-binding",
        observations=(True, True),
        threshold=0.5,
    )
    report = load_backtest_report(_ensure_ir_artifact_store(store), report_ref)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    report_temporal_roles = {
        "data_valid_time": start.isoformat(),
        "calibration_window_start": (start + timedelta(days=1)).isoformat(),
        "calibration_window_end": (start + timedelta(days=2)).isoformat(),
        "policy_effective_time": (start + timedelta(days=3)).isoformat(),
        "prediction_time": (start + timedelta(days=4)).isoformat(),
        "observation_time": (start + timedelta(days=5)).isoformat(),
    }
    report = report.model_copy(
        update={
            "metadata": {
                **report.metadata,
                "temporal_roles": report_temporal_roles,
            }
        }
    )
    report_with_times_ref = persist_backtest_report(
        _ensure_ir_artifact_store(store),
        report,
        inputs=[
            InputRef(
                artifact_id=ref["artifact_id"],
                role=role,
                manifest_profile_sha256=ref.get("manifest_profile_sha256"),
            )
            for role, ref in refs.items()
        ],
    )

    shifted_roles = {
        name: datetime.fromisoformat(value) for name, value in report_temporal_roles.items()
    }
    shifted_roles[role] += timedelta(seconds=1)
    context = _context(
        refs,
        threshold=0.5,
        temporal_updates=shifted_roles,
    )

    evidence = produce_empirical_calibration_evidence(
        store,
        report_with_times_ref,
        context=context,
    )

    assert "temporal_roles_report_mismatch" in evidence.failure_codes
    assert evidence.context_bound is False
    assert evidence.usable_for_calibration is False
    assert evidence.floor_passed is False


def test_bridge_refuses_context_when_report_does_not_bind_temporal_roles(
    tmp_path: Path,
) -> None:
    """Ordered caller timestamps alone cannot establish report time binding."""

    store, report_ref, refs = _persist_report(
        tmp_path,
        label="missing-report-time-binding",
        observations=(True, True),
        threshold=0.5,
    )
    report = load_backtest_report(_ensure_ir_artifact_store(store), report_ref)
    metadata = dict(report.metadata)
    metadata.pop("temporal_roles")
    report_without_times_ref = persist_backtest_report(
        _ensure_ir_artifact_store(store),
        report.model_copy(update={"metadata": metadata}),
        inputs=[
            InputRef(
                artifact_id=ref["artifact_id"],
                role=role,
                manifest_profile_sha256=ref.get("manifest_profile_sha256"),
            )
            for role, ref in refs.items()
        ],
    )
    evidence = produce_empirical_calibration_evidence(
        store,
        report_without_times_ref,
        context=_context(refs, threshold=0.5),
    )

    assert "report_temporal_roles_unresolved" in evidence.failure_codes
    assert evidence.context_bound is False
    assert evidence.usable_for_calibration is False
    assert evidence.floor_passed is False


def test_real_forecast_owner_cas_bridge_reopen_reaches_limited_s10_candidate(
    tmp_path: Path,
) -> None:
    """Supplemental refs compose without replacing owner edges or granting credibility."""

    from types import SimpleNamespace

    from polisyos.calibration.forecast_bridge import load_empirical_calibration_evidence
    from polisyos.runtime.http.services.predictive_calibration import (
        _build_empirical_context,
        _persist_evidence_role_refs,
    )
    from tests.unit.remediation.test_frc_02_owner import _spec
    from tests.unit.remediation.test_frc_02_s10 import (
        RULE_VERSION_REF,
        _method_result,
        _produce_forecast_inputs,
    )

    store = FileSystemCAS(tmp_path / "owner-bridge-s10-cas")
    rule_ref = _rule(store)
    model_ref = _spec(store, kind="ir.model_spec", spec_id="owner-bridge-model")
    policy_ref = _spec(store, kind="ir.policy_spec", spec_id="owner-bridge-policy")
    report_id = "frc-owner-bridge-s10-consumer"
    threshold = 0.01
    model_id = str(model_ref.artifact_id)
    policy_id = str(policy_ref.artifact_id)
    request = _request(
        _source(store, training=[float(value) for value in range(10, 20)], holdout=[20, 21, 22]),
        rule_ref,
        report_id=report_id,
        model_spec_ref=model_id,
        policy_spec_ref=policy_id,
        train_end=10,
        horizon=3,
    )

    owner_result = ForecastOwner(store).run(request)
    ir_store = _ensure_ir_artifact_store(store)
    preliminary_report = load_backtest_report(ir_store, owner_result.backtest_report_ref)
    candidate_source_ref = _spec(
        store,
        kind="ir.candidate_scenario_source",
        spec_id="owner-bridge-candidate-source",
    )
    context_refs = _persist_evidence_role_refs(
        store=store,
        report_id=report_id,
        threshold=threshold,
        model_spec_ref=model_ref,
        policy_spec_ref=policy_ref,
        candidate_source_ref=candidate_source_ref,
        observed_source_ref=owner_result.observed_source_ref,
        training_slice_ref=owner_result.training_slice_ref,
        uncertainty_bundle_ref=owner_result.uncertainty_bundle_ref,
        method_artifact_ref=owner_result.method_artifact_ref,
        calibration_rule_ref=owner_result.calibration_rule_ref,
    )
    assert REFERENCE_SOURCE_INPUT_ROLES == _OWNER_SOURCE_ROLE_MAP
    owner_manifest = ir_store.get_manifest(owner_result.backtest_report_ref)
    report_inputs = [
        InputRef.model_validate(item.model_dump(mode="python")) for item in owner_manifest.inputs
    ]
    report_inputs.append(
        InputRef(
            artifact_id=candidate_source_ref.artifact_id,
            role="candidate_source",
            manifest_profile_sha256=candidate_source_ref.manifest_profile_sha256,
        )
    )
    report_inputs.extend(
        InputRef(
            artifact_id=ref.artifact_id,
            role=role,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )
        for role, ref in context_refs.items()
    )
    selected_report_ref = persist_backtest_report(
        ir_store,
        preliminary_report,
        inputs=report_inputs,
    )
    selected_report_manifest = ir_store.get_manifest(selected_report_ref)
    for role, source_roles in _OWNER_SOURCE_ROLE_MAP.items():
        selected_role = context_refs[role]
        assert selected_role.manifest_profile_sha256 is not None
        role_manifest = resolve_manifest_by_profile(
            ir_store,
            selected_role.artifact_id,
            selected_role.manifest_profile_sha256,
        )
        actual_source_edges = tuple(
            (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            for item in role_manifest.inputs
        )
        expected_source_edges = tuple(
            (str(item.artifact_id), item.role, item.manifest_profile_sha256)
            for item in selected_report_manifest.inputs
            if item.role in source_roles
        )
        assert len(expected_source_edges) == len(source_roles)
        assert sorted(actual_source_edges) == sorted(expected_source_edges)
    report = load_backtest_report(ir_store, selected_report_ref)
    manifest_payload = ir_store.get_manifest(selected_report_ref).model_dump(mode="json")
    report_edges = {
        (
            str(item["artifact_id"]),
            str(item["role"]),
            item.get("manifest_profile_sha256"),
        )
        for item in manifest_payload["inputs"]
    }
    assert {
        "observed_source",
        "observed_data",
        "calibration_rule",
        "training_slice",
        "method_artifact",
        "uncertainty_bundle",
        "calibration_diagnostics",
        "model_spec",
        "policy_spec",
        "candidate_source",
    } <= {role for _artifact_id, role, _profile in report_edges}
    assert {
        (str(ref.artifact_id), role, ref.manifest_profile_sha256)
        for role, ref in context_refs.items()
    } <= report_edges
    assert all(profile is not None for _artifact_id, _role, profile in report_edges)

    context = _build_empirical_context(
        context_refs,
        model_spec_ref=owner_result.model_spec_ref,
        policy_spec_ref=owner_result.policy_spec_ref,
        threshold=threshold,
        temporal_roles=request.temporal_roles,
    )
    evidence = produce_empirical_calibration_evidence(
        store,
        selected_report_ref,
        context=context,
    )
    assert evidence.report_ref == selected_report_ref
    assert evidence.context_bound is True
    assert evidence.empirical_observations_available is False
    assert evidence.usable_for_calibration is False
    assert evidence.floor_passed is False
    assert (
        forecast_bridge._reconcile_backtest_rows(store, selected_report_ref, report) == "recomputed"
    )
    assert evidence.failure_codes == ("backtest_source_not_established",)
    evidence_ref = persist_empirical_calibration_evidence(store, evidence)
    assert evidence_ref.manifest_profile_sha256 is not None
    reopened = load_empirical_calibration_evidence(store, evidence_ref)
    assert reopened == evidence

    # These references are test-authored caller inputs. The role name and
    # same-report content binding do not establish an external issuer fact.
    from polisyos.ir.artifacts import get_json_artifact

    credible_payload = get_json_artifact(
        _ensure_ir_artifact_store(store),
        context_refs["credible_evaluation"].artifact_id,
    )
    assert "issuer" not in credible_payload
    assert "signature" not in credible_payload

    temporal_roles = SimpleNamespace(
        **{
            role: getattr(request.temporal_roles, role)
            for role in (
                "data_valid_time",
                "calibration_window_start",
                "calibration_window_end",
                "policy_effective_time",
                "prediction_time",
                "observation_time",
            )
        }
    )
    method_result = _method_result(
        evidence_ref=evidence_ref,
        temporal_roles=temporal_roles,
        report=report,
        expected_rule_version_ref=RULE_VERSION_REF,
    )
    candidate_projection = _produce_forecast_inputs(
        store=store,
        evidence_ref=evidence_ref,
        method_result=method_result,
    )
    record = candidate_projection["forecast_calibration_record"]
    assert record is None
    support = candidate_projection["forecast_support"]
    assert support.forecast_tier == "blocked"
    assert "backtest_source_not_established" in support.forecast_authority_disposition_reason
    assert (
        "s10://calibration/fail-closed/backtest_source_not_established"
        in support.s6_limitation_refs
    )

    # Keep every selected owner and semantic-role edge, but reverse the actual
    # report rows relative to the selected forecast/observed time positions.
    # Row-only coverage arithmetic remains unchanged, showing why edge
    # identity alone does not establish the report's empirical observations.
    original_scenario = report.scenarios[0]
    original_rows = original_scenario.outcome_comparisons
    reordered_rows = list(reversed(original_rows))
    assert [row.y_true for row in reordered_rows] != [row.y_true for row in original_rows]
    forged_report = report.model_copy(
        update={
            "scenarios": [
                original_scenario.model_copy(update={"outcome_comparisons": reordered_rows})
            ]
        }
    )
    forged_ref = persist_backtest_report(ir_store, forged_report, inputs=report_inputs)
    assert {
        (str(edge.artifact_id), edge.role, edge.manifest_profile_sha256)
        for edge in ir_store.get_manifest(forged_ref).inputs
    } == report_edges
    forged = produce_empirical_calibration_evidence(store, forged_ref, context=context)
    assert forged.context_bound is True
    assert forged.recomputed_numerator == evidence.recomputed_numerator
    assert forged.recomputed_denominator == evidence.recomputed_denominator
    assert forged.recomputed_pass_rate == evidence.recomputed_pass_rate
    assert forged.empirical_observations_available is False
    assert forged.floor_passed is False
    assert forged.usable_for_calibration is False
    assert forged.failure_codes == (
        "backtest_source_not_established",
        "backtest_row_source_mismatch",
    )
    forged_evidence_ref = persist_empirical_calibration_evidence(store, forged)
    assert load_empirical_calibration_evidence(store, forged_evidence_ref) == forged
    forged_projection = _produce_forecast_inputs(
        store=store,
        evidence_ref=forged_evidence_ref,
        method_result=_method_result(
            evidence_ref=forged_evidence_ref,
            temporal_roles=temporal_roles,
            report=forged_report,
            expected_rule_version_ref=RULE_VERSION_REF,
        ),
    )
    assert forged_projection["forecast_calibration_record"] is None
    forged_support = forged_projection["forecast_support"]
    assert forged_support.forecast_tier == "blocked"
    assert "backtest_source_not_established" in forged_support.forecast_authority_disposition_reason

"""Actual ForecastOwner → forecast_bridge evidence boundary witness.

This test keeps the producer, persisted report, and recomputing bridge on the
same CAS.  It intentionally does not manufacture the missing semantic-role
artifacts that would be needed to persist calibration evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from polisyos.calibration.forecast_bridge import (
    persist_empirical_calibration_evidence,
    produce_empirical_calibration_evidence,
)
from polisyos.core.artifacts import FileSystemCAS
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
        assert report_evidence.empirical_observations_available is True
        assert report_evidence.context_bound is False
        assert report_evidence.usable_for_calibration is False
        assert report_evidence.floor_passed is False
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
        inputs=[InputRef(artifact_id=ref["artifact_id"], role=role) for role, ref in refs.items()],
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
        inputs=[InputRef(artifact_id=ref["artifact_id"], role=role) for role, ref in refs.items()],
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

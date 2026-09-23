"""Focused witnesses for the real FRC-02 predictive owner slice.

These tests deliberately exercise the owner through its CAS boundary.  The
owner is predictive evidence only: it must never be mistaken for a causal
effect-confidence interval or an S10 promotion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.ir.artifacts import InputRef
from polisyos.scientist.methods.backtesting.forecast_owner import (
    CalibrationRuleBinding,
    ForecastOwner,
    ForecastOwnerRequest,
    ForecastTemporalRoles,
    TrainHoldoutSplit,
)

METHOD_FQN = "forecasting.univariate.exponential_smoothing@1.0.0"
ESTIMAND = "predictive_interval_coverage"


def _put_json(store: FileSystemCAS, payload: object, *, kind: str) -> ArtifactRef:
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
    )


def _source(
    store: FileSystemCAS,
    *,
    holdout: list[float],
) -> DataSnapshotRef:
    values = [float(index) for index in range(1, 31)] + holdout
    data_ref = _put_json(
        store,
        {"metric": values},
        kind="test.forecast.observed_data",
    )
    snapshot = DataSnapshot(
        data_ref=ArtifactRef.model_validate(data_ref),
        stats={"rows": len(values), "source": "test_frc_02_owner"},
    )
    snapshot_ref = _put_json(
        store,
        snapshot.model_dump(mode="json"),
        kind="fabric.data_snapshot",
    )
    return DataSnapshotRef.model_validate(snapshot_ref)


def _rule(store: FileSystemCAS, *, rule_id: str = "residual-conformal.v1") -> ArtifactRef:
    return _put_json(
        store,
        {
            "rule_id": rule_id,
            "rule_version": "1.0.0",
            "estimand": ESTIMAND,
            "method": "rolling_origin_residual_conformal",
            "nominal_coverage": 0.90,
        },
        kind="test.forecast.calibration_rule",
    )


def _temporal_roles() -> ForecastTemporalRoles:
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    return ForecastTemporalRoles(
        data_valid_time=origin,
        calibration_window_start=origin + timedelta(days=1),
        calibration_window_end=origin + timedelta(days=2),
        policy_effective_time=origin + timedelta(days=3),
        prediction_time=origin + timedelta(days=4),
        observation_time=origin + timedelta(days=5),
    )


def _request(
    source_ref: DataSnapshotRef,
    rule_ref: ArtifactRef,
    *,
    report_id: str,
    manifest_inputs: tuple[InputRef, ...] = (),
) -> ForecastOwnerRequest:
    return ForecastOwnerRequest(
        observed_source_ref=source_ref,
        split=TrainHoldoutSplit(
            train_start=0,
            train_end=30,
            holdout_start=30,
            holdout_end=34,
            horizon=4,
        ),
        target_metric="metric",
        method_fqn=METHOD_FQN,
        method_params={"horizon": 4, "alpha": 0.3, "beta": 0.1},
        report_id=report_id,
        estimand=ESTIMAND,
        calibration_rule=CalibrationRuleBinding(
            rule_id="residual-conformal.v1",
            artifact_ref={
                "artifact_id": str(rule_ref.artifact_id),
                "kind": rule_ref.kind,
                "media_type": rule_ref.media_type,
            },
        ),
        temporal_roles=_temporal_roles(),
        manifest_inputs=manifest_inputs,
    )


def test_real_ets_owner_persists_content_bound_predictive_evidence(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)

    result = ForecastOwner(store).run(
        _request(source_ref, rule_ref, report_id="frc-owner-ets-green")
    )

    assert result.method_fqn == METHOD_FQN
    assert result.estimand == ESTIMAND
    assert result.authority_scope == "predictive_only"
    assert result.bridge_status == "bridge_pending"
    assert result.denominator == 4
    assert 0.0 <= result.empirical_coverage <= 1.0
    assert result.nominal_coverage == pytest.approx(0.90)
    assert result.observed_source_ref.artifact_id == source_ref.artifact_id
    assert result.training_slice_ref.kind == "ir.forecast_training_slice"
    assert result.method_artifact_ref.kind == "foundry.method_artifact"
    assert result.uncertainty_bundle_ref.kind == "ir.forecasting_uncertainty_bundle"
    assert result.calibration_diagnostics_ref.kind == "ir.calibration_diagnostics_report"
    assert result.backtest_report_ref.kind == "ir.backtest_report"


def test_same_ets_shape_uses_held_out_observations_for_suitability(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    rule_ref = _rule(store)
    in_profile = ForecastOwner(store).run(
        _request(
            _source(store, holdout=[31.0, 32.0, 33.0, 34.0]),
            rule_ref,
            report_id="frc-owner-ets-in-profile",
        )
    )
    out_of_profile = ForecastOwner(store).run(
        _request(
            _source(store, holdout=[1000.0, 1001.0, 1002.0, 1003.0]),
            rule_ref,
            report_id="frc-owner-ets-out-of-profile",
        )
    )

    assert in_profile.method_fqn == out_of_profile.method_fqn
    assert in_profile.empirical_coverage != out_of_profile.empirical_coverage
    assert in_profile.empirical_suitability != out_of_profile.empirical_suitability


def test_owner_rejects_incomplete_model_policy_pair_and_duplicate_inputs(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    duplicate = InputRef(
        artifact_id=str(source_ref.artifact_id),
        role="observed_source",
    )

    with pytest.raises(ValueError, match="model/policy"):
        payload = _request(source_ref, rule_ref, report_id="frc-owner-partial").model_dump(
            mode="python"
        )
        payload["model_spec_ref"] = str(source_ref.artifact_id)
        ForecastOwnerRequest.model_validate(payload)

    with pytest.raises(ValueError, match="duplicate"):
        _request(
            source_ref,
            rule_ref,
            report_id="frc-owner-duplicate-input",
            manifest_inputs=(duplicate, duplicate),
        )


def test_owner_rejects_naive_or_collapsed_temporal_roles(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    source_ref = _source(store, holdout=[31.0, 32.0, 33.0, 34.0])
    rule_ref = _rule(store)
    roles = _temporal_roles().model_dump(mode="python")
    roles["observation_time"] = datetime(2026, 1, 1)

    with pytest.raises(ValueError, match="timezone|distinct"):
        payload = _request(source_ref, rule_ref, report_id="frc-owner-naive").model_dump(
            mode="python"
        )
        payload["temporal_roles"] = roles
        ForecastOwnerRequest.model_validate(payload)

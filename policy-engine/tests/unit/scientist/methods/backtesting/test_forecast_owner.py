"""Actual ETS producer, separate empirical artifact and fresh CAS replay."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from polisyos.calibration.forecast_bridge import (
    EmpiricalCalibrationEvidence,
    ForecastCalibrationProfile,
    ForecastCandidateReceipt,
    ForecastCandidateReceiptRef,
    load_empirical_calibration_evidence,
    load_forecast_candidate_receipt,
    persist_forecast_candidate_receipt,
)
from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.artifacts import get_json_artifact, normalize_artifact_ref, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.methods.backtesting.forecast_owner import (
    ForecastOwner,
    ForecastOwnerRequest,
    persist_forecast_owner_request,
)


def _configured(store: FileSystemCAS, holdout: list[float]):
    def put(payload: object, kind: str):
        return store.put_json(
            payload,
            PutOptions(kind=kind, media_type="application/json"),
            canon_spec=CanonSpec(forbid_floats=False),
        )

    data = put({"metric": [float(i) for i in range(1, 31)] + holdout}, "test.observed")
    source = put(DataSnapshot(data_ref=data).model_dump(mode="json"), "fabric.data_snapshot")
    rule = put(
        {
            "schema_version": "1.0",
            "rule_id": "rolling-origin-residual-conformal.v1",
            "rule_version": "1.0",
            "estimand": "predictive_interval_coverage",
            "algorithm": "rolling_origin_residual_conformal",
            "nominal_coverage": 0.9,
        },
        "ir.forecast_calibration_rule",
    )
    model = put({"spec_id": "model-ets"}, "ir.model_spec")
    policy = put({"spec_id": "policy-ets"}, "ir.policy_spec")
    origin = datetime(2026, 1, 1, tzinfo=UTC)
    request = ForecastOwnerRequest(
        observed_source_ref=DataSnapshotRef(artifact_id=source.artifact_id),
        split={
            "train_start": 0,
            "train_end": 30,
            "holdout_start": 30,
            "holdout_end": 30 + len(holdout),
            "horizon": len(holdout),
        },
        target_metric="metric",
        method_params={"horizon": len(holdout)},
        report_id="configured-ets-report",
        calibration_rule={
            "rule_id": "rolling-origin-residual-conformal.v1",
            "artifact_ref": normalize_artifact_ref(rule),
        },
        temporal_roles=dict(
            zip(
                (
                    "data_valid_time",
                    "calibration_window_start",
                    "calibration_window_end",
                    "policy_effective_time",
                    "prediction_time",
                    "observation_time",
                ),
                (origin + timedelta(days=i) for i in range(6)),
                strict=True,
            )
        ),
        model_spec_ref=model.artifact_id,
        policy_spec_ref=policy.artifact_id,
        seed=17,
    )
    request_ref = persist_forecast_owner_request(store, request)
    profile = ForecastCalibrationProfile(
        profile_id="linear-ets",
        profile_version="1.0",
        request_ref=request_ref,
        calibration_threshold=0.8,
    )
    profile_ref = ArtifactRefModel.model_validate(
        put_json_artifact(
            store,
            profile.model_dump(mode="json"),
            kind="ir.forecast_calibration_profile",
            schema_name="polisyos.calibration.forecast_calibration_profile",
            schema_version="1.0",
            inputs=[{"artifact_id": str(request_ref.artifact_id), "role": "forecast_request"}],
            canon_spec=CanonSpec(forbid_floats=False),
        )
    )
    return request, profile_ref


def test_configured_ets_emits_separate_evidence_and_candidate_receipt(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    request, profile_ref = _configured(store, [31.0, 32.0, 33.0, 34.0])
    result = ForecastOwner(store, empirical_profile_ref=profile_ref).run(request)
    assert result.empirical_evidence_ref is not None
    assert result.candidate_receipt_ref is not None
    fresh = FileSystemCAS(tmp_path / "cas")
    receipt = load_forecast_candidate_receipt(fresh, result.candidate_receipt_ref)
    evidence = load_empirical_calibration_evidence(fresh, receipt.empirical_evidence_ref)
    report = load_backtest_report(fresh, evidence.report_ref)
    comparisons = report.scenarios[0].outcome_comparisons
    independent_hits = sum(row.ci_lower <= row.y_true <= row.ci_upper for row in comparisons)
    assert evidence.recomputed_numerator == independent_hits
    assert evidence.recomputed_denominator == len(comparisons) == 4
    assert evidence.recomputed_pass_rate == independent_hits / len(comparisons)
    assert receipt.verifier_provenance == "not_established"
    assert receipt.authority_scope == "predictive_only"
    assert result.bridge_status == "bridge_pending"
    assert report.trust_eligible is False
    assert evidence.prediction_time == request.temporal_roles.prediction_time


def test_same_forecasts_changed_holdout_changes_persisted_evidence(tmp_path: Path):
    results = []
    evidence = []
    for index, holdout in enumerate(([31.0, 32.0, 33.0, 34.0], [1000.0, 1000.0, 1000.0, 1000.0])):
        store = FileSystemCAS(tmp_path / str(index))
        request, profile = _configured(store, holdout)
        result = ForecastOwner(store, empirical_profile_ref=profile).run(request)
        results.append(result)
        evidence.append(load_empirical_calibration_evidence(store, result.empirical_evidence_ref))
    assert results[0].point_forecast == results[1].point_forecast
    assert evidence[0].recomputed_numerator == 4
    assert evidence[1].recomputed_numerator == 0
    assert evidence[0].floor_passed is True
    assert evidence[1].floor_passed is False
    assert results[0].empirical_evidence_ref != results[1].empirical_evidence_ref


def test_configured_request_mismatch_refuses_before_method_callback(tmp_path: Path, monkeypatch):
    store = FileSystemCAS(tmp_path / "cas")
    request, profile = _configured(store, [31.0, 32.0, 33.0, 34.0])
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    def forbidden(*args, **kwargs):
        raise AssertionError("numerical method must not be called")

    monkeypatch.setattr(MethodDispatcher, "dispatch", forbidden)
    with pytest.raises(ValueError, match="differs from the configured"):
        ForecastOwner(store, empirical_profile_ref=profile).run(
            request.model_copy(update={"seed": 18})
        )


def test_content_valid_forged_receipt_cannot_switch_source_request(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    request, profile = _configured(store, [31.0, 32.0, 33.0, 34.0])
    result = ForecastOwner(store, empirical_profile_ref=profile).run(request)
    _, wrong_profile = _configured(store, [1000.0, 1000.0, 1000.0, 1000.0])
    wrong_request = get_json_artifact(store, wrong_profile.artifact_id)["request_ref"]
    receipt = ForecastCandidateReceipt(
        profile_ref=wrong_profile,
        request_ref=wrong_request,
        empirical_evidence_ref=result.empirical_evidence_ref,
    )
    with pytest.raises(ValueError, match="observed source/ordered row"):
        persist_forecast_candidate_receipt(store, receipt)


def test_content_valid_false_counts_are_rejected_on_fresh_consumer_read(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    request, profile = _configured(store, [31.0, 32.0, 33.0, 34.0])
    result = ForecastOwner(store, empirical_profile_ref=profile).run(request)
    evidence = load_empirical_calibration_evidence(store, result.empirical_evidence_ref)
    false_payload = evidence.model_dump(mode="json")
    false_payload.update(
        recomputed_numerator=0,
        recomputed_pass_rate=0.0,
        within_ci_numerator=0,
        persisted_numerator=0,
        floor_passed=False,
        usable_for_calibration=False,
        failure_codes=["calibration_floor_not_met"],
    )
    # The payload is schema-valid and its CAS bytes/hash are correct.
    EmpiricalCalibrationEvidence.model_validate(false_payload)
    manifest = store.get_manifest(result.empirical_evidence_ref.artifact_id)
    false_ref = put_json_artifact(
        store,
        false_payload,
        kind="ir.empirical_calibration_evidence",
        schema_name="polisyos.calibration.empirical_calibration_evidence",
        schema_version="1.1",
        inputs=manifest.inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    receipt = load_forecast_candidate_receipt(store, result.candidate_receipt_ref)
    false_receipt = ForecastCandidateReceipt.model_validate(
        {
            **receipt.model_dump(mode="json"),
            "empirical_evidence_ref": false_ref,
        }
    )
    false_receipt_ref = put_json_artifact(
        store,
        false_receipt.model_dump(mode="json"),
        kind="ir.forecast_candidate_receipt",
        schema_name="polisyos.calibration.forecast_candidate_receipt",
        schema_version="1.0",
        inputs=[
            {"artifact_id": str(profile.artifact_id), "role": "forecast_profile"},
            {"artifact_id": str(receipt.request_ref.artifact_id), "role": "forecast_request"},
            {"artifact_id": false_ref["artifact_id"], "role": "empirical_evidence"},
        ],
        canon_spec=CanonSpec(forbid_floats=False),
    )
    fresh = FileSystemCAS(tmp_path / "cas")
    with pytest.raises(ValueError, match="reproduced|reconciled|payload"):
        load_forecast_candidate_receipt(
            fresh,
            ForecastCandidateReceiptRef.model_validate(false_receipt_ref),
        )

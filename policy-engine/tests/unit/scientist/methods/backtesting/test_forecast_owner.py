"""Actual ETS producer, separate empirical artifact and fresh CAS replay."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.calibration.forecast_bridge import (
    EmpiricalCalibrationEvidence,
    ForecastCandidateReceipt,
    ForecastCandidateReceiptRef,
    load_empirical_calibration_evidence,
    load_forecast_candidate_receipt,
    persist_forecast_candidate_receipt,
)
from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
from polisyos.core.contracts.fabric import DataSnapshotRef
from polisyos.ir.analytics.backtest import load_backtest_report
from polisyos.ir.analytics.forecasting_uncertainty import load_forecasting_uncertainty_bundle
from polisyos.ir.artifacts import get_json_artifact, put_json_artifact
from polisyos.scientist.methods.backtesting.forecast_owner import ForecastOwner
from tests._helpers.forecast import configured_forecast_request as _configured


def test_configured_ets_emits_separate_evidence_and_candidate_receipt(tmp_path: Path):
    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
    request, profile_ref = _configured(store, [31.0, 32.0, 33.0, 34.0])
    result = ForecastOwner(store, empirical_profile_ref=profile_ref).run(request)
    assert result.empirical_evidence_ref is not None
    assert result.candidate_receipt_ref is not None
    fresh = core_artifacts.FileSystemCAS(tmp_path / "cas")
    receipt = load_forecast_candidate_receipt(fresh, result.candidate_receipt_ref)
    evidence = load_empirical_calibration_evidence(fresh, receipt.empirical_evidence_ref)
    report = load_backtest_report(fresh, evidence.report_ref)
    # Independent oracle: a perfect linear training series has Holt point and
    # rolling-origin residual bounds 31,32,33,34. Read source and interval CAS
    # separately; BacktestReport comparisons are not this oracle's input.
    source = get_json_artifact(fresh, request.observed_source_ref.artifact_id)
    rows = get_json_artifact(fresh, source["data_ref"]["artifact_id"])["metric"][30:34]
    bundle = load_forecasting_uncertainty_bundle(fresh, result.uncertainty_bundle_ref)
    bounds = [(float(item.lower), float(item.upper)) for item in bundle.prediction_interval]
    assert bounds == pytest.approx([(31.0, 31.0), (32.0, 32.0), (33.0, 33.0), (34.0, 34.0)])
    independent_hits = sum(lo <= y <= hi for y, (lo, hi) in zip(rows, bounds, strict=True))
    assert evidence.recomputed_numerator == independent_hits
    assert evidence.recomputed_denominator == len(rows) == 4
    assert evidence.recomputed_pass_rate == independent_hits / len(rows)
    assert result.measurement_binding.unit_id == "count"
    assert result.measurement_binding.scale == "source_native"
    assert bundle.metadata["measurement_binding"] == result.measurement_binding.model_dump(
        mode="json"
    )
    assert receipt.verifier_provenance == "not_established"
    assert receipt.authority_scope == "predictive_only"
    assert result.bridge_status == "bridge_pending"
    assert report.trust_eligible is False
    assert evidence.prediction_time == request.temporal_roles.prediction_time


@pytest.mark.parametrize(
    "defect",
    [
        "missing_schema",
        "wrong_kind",
        "wrong_profile",
        "malformed_schema",
        "missing_unit",
        "wrong_unit",
        "wrong_target",
        "unsupported_scale",
        "legacy_request",
    ],
)
def test_measurement_admission_precedes_any_method_callback(tmp_path: Path, monkeypatch, defect):
    """Present refs/metric names cannot replace resolved schema and unit identity."""

    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
    request, _ = _configured(store, [31.0, 32.0, 33.0, 34.0])
    source = get_json_artifact(store, request.observed_source_ref.artifact_id)
    schema = get_json_artifact(store, source["data_schema_ref"]["artifact_id"])
    kind, schema_name = "fabric.data_schema", "polisyos.fabric.DataSchema"
    if defect == "missing_schema":
        source.pop("data_schema_ref")
    elif defect == "wrong_kind":
        kind = "fake.data_schema"
    elif defect == "wrong_profile":
        schema_name = "fake.DataSchema"
        # CAS identity is byte-based; change a valid schema metadata field so
        # this writes a new wrong-profile manifest rather than reusing v1.
        schema["description"] = "wrong manifest profile fixture"
    elif defect == "malformed_schema":
        schema["fields"] = "not-fields"
    elif defect == "missing_unit":
        schema["fields"][0].pop("unit")
    elif defect == "wrong_unit":
        request = request.model_copy(update={"target_unit": "percent"})
    elif defect == "wrong_target":
        request = request.model_copy(update={"target_metric": "other_metric"})
    elif defect == "unsupported_scale":
        request = request.model_copy(update={"target_scale": "percent_to_ratio"})
    elif defect == "legacy_request":
        request = request.model_copy(update={"schema_version": "1.0"})
    if defect in {"wrong_kind", "wrong_profile", "malformed_schema", "missing_unit"}:
        source["data_schema_ref"] = put_json_artifact(
            store,
            schema,
            kind=kind,
            schema_name=schema_name,
            schema_version="1.0",
            canon_spec=core_canon.CanonSpec(forbid_floats=False),
        )
    source_ref = put_json_artifact(
        store,
        source,
        kind="fabric.data_snapshot",
        schema_name="polisyos.fabric.DataSnapshot",
        schema_version="1.0",
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    request = request.model_copy(
        update={"observed_source_ref": DataSnapshotRef(artifact_id=source_ref["artifact_id"])}
    )
    callback_count = 0

    def counted(*args, **kwargs):
        nonlocal callback_count
        callback_count += 1
        raise AssertionError("preflight must precede numerical callback")

    monkeypatch.setattr(MethodDispatcher, "dispatch", counted)
    with pytest.raises((ValueError, TypeError)):
        ForecastOwner(store).run(request)
    assert callback_count == 0


def test_adapter_returns_fresh_resolved_a_fields_without_verifier_authority(tmp_path: Path):
    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
    request, profile = _configured(store, [31.0, 32.0, 33.0, 34.0])
    result = ForecastOwner(store, empirical_profile_ref=profile).run(request)
    fields = result.to_s10_input_fields(core_artifacts.FileSystemCAS(tmp_path / "cas"))
    assert fields["empirical_calibration_evidence_ref"] == result.empirical_evidence_ref
    assert fields["forecast_candidate_receipt_ref"] == result.candidate_receipt_ref
    assert fields["expected_rule_version_ref"] == request.calibration_rule.rule_id
    assert fields["temporal_roles"] == request.temporal_roles
    assert fields["verifier_provenance"] == "not_established"
    assert fields["authority_scope"] == "predictive_only"
    with pytest.raises(ValueError, match="temporal roles"):
        result.model_copy(
            update={
                "temporal_roles": request.temporal_roles.model_copy(
                    update={"observation_time": datetime(2026, 2, 1, tzinfo=UTC)}
                )
            }
        ).to_s10_input_fields(store)


@pytest.mark.parametrize(
    "field, value", [("target_unit", "percent"), ("target_scale", "percent_to_ratio")]
)
def test_fresh_receipt_reader_refuses_integrity_valid_measurement_forgery(
    tmp_path: Path, field, value
):
    """CAS-correct refs do not establish request/source measurement agreement."""

    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
    request, profile_ref = _configured(store, [31.0, 32.0, 33.0, 34.0])
    result = ForecastOwner(store, empirical_profile_ref=profile_ref).run(request)
    forged_request = request.model_dump(mode="json")
    forged_request[field] = value
    request_ref = put_json_artifact(
        store,
        forged_request,
        kind="ir.forecast_owner_request",
        schema_name="polisyos.calibration.forecast_owner_request",
        schema_version="2.0",
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    profile = get_json_artifact(store, profile_ref.artifact_id)
    profile["request_ref"] = request_ref
    forged_profile_ref = put_json_artifact(
        store,
        profile,
        kind="ir.forecast_calibration_profile",
        schema_name="polisyos.calibration.forecast_calibration_profile",
        schema_version="1.0",
        inputs=[{"artifact_id": request_ref["artifact_id"], "role": "forecast_request"}],
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    receipt = load_forecast_candidate_receipt(store, result.candidate_receipt_ref).model_dump(
        mode="json"
    )
    receipt.update(profile_ref=forged_profile_ref, request_ref=request_ref)
    forged_receipt_ref = put_json_artifact(
        store,
        receipt,
        kind="ir.forecast_candidate_receipt",
        schema_name="polisyos.calibration.forecast_candidate_receipt",
        schema_version="1.0",
        inputs=[
            {"artifact_id": forged_profile_ref["artifact_id"], "role": "forecast_profile"},
            {"artifact_id": request_ref["artifact_id"], "role": "forecast_request"},
            {
                "artifact_id": str(result.empirical_evidence_ref.artifact_id),
                "role": "empirical_evidence",
            },
        ],
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    with pytest.raises(ValueError, match="unit|scale"):
        load_forecast_candidate_receipt(
            core_artifacts.FileSystemCAS(tmp_path / "cas"),
            ForecastCandidateReceiptRef.model_validate(forged_receipt_ref),
        )


def test_same_forecasts_changed_holdout_changes_persisted_evidence(tmp_path: Path):
    results = []
    evidence = []
    for index, holdout in enumerate(([31.0, 32.0, 33.0, 34.0], [1000.0, 1000.0, 1000.0, 1000.0])):
        store = core_artifacts.FileSystemCAS(tmp_path / str(index))
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
    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
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
    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
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
    store = core_artifacts.FileSystemCAS(tmp_path / "cas")
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
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
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
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    fresh = core_artifacts.FileSystemCAS(tmp_path / "cas")
    with pytest.raises(ValueError, match="reproduced|reconciled|payload"):
        load_forecast_candidate_receipt(
            fresh,
            ForecastCandidateReceiptRef.model_validate(false_receipt_ref),
        )

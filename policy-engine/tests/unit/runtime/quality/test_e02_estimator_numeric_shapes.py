"""Numeric shape refusals at the Foundry value and S10 diagnostic boundaries."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle


def _report(
    *,
    point_estimate: Any,
    confidence_interval: Any = (-0.25, 0.25),
) -> SimpleNamespace:
    """Build estimator-shaped output without claiming observed calibration."""

    return SimpleNamespace(
        point_estimate=point_estimate,
        confidence_interval=confidence_interval,
        standard_error=0.2,
        confidence_level=0.95,
        diagnostics=(),
        sample_size=100,
        n_treated=50,
        n_control=50,
        pre_periods=4,
        post_periods=4,
        method="e02_numeric_shape_test",
    )


def _project_foundry_value(*, point_estimate: Any, confidence_interval: Any) -> Any:
    transport = generation_cycle.ValueTransportReceipt(
        status="direct",
        world_model_record_id="world_model_record_e02_numeric_shapes",
        world_model_record_content_hash="sha256:" + "a" * 64,
        transport_result_ref="sha256:" + "b" * 64,
        transport_status="identified",
        transport_mode="direct",
        identification_engine="e02-numeric-shape-test",
    )
    calibration = generation_cycle.ValueCalibrationReceipt(
        status="pass",
        forecast_tier="direct",
        calibration_record_ref="calibration://e02/numeric-shapes",
        uncertainty_interval_refs=("interval://e02/numeric-shapes/95",),
    )
    return generation_cycle._value_outer_set_from_foundry_result(
        method_result=SimpleNamespace(
            output={
                "report": _report(
                    point_estimate=point_estimate,
                    confidence_interval=confidence_interval,
                )
            }
        ),
        transport_receipt=transport,
        calibration_receipt=calibration,
        world_record=SimpleNamespace(
            content_hash="sha256:" + "a" * 64,
            valid_time_scope="2026-Q3",
        ),
        data_trust=generation_cycle.DataTrust(
            tier="e02_numeric_shape_test",
            trust_cap=0.8,
            trust_multiplier=0.8,
            min_coverage=0.0,
            max_coverage=1.0,
            promotion_floor=0.0,
            authority_ref="repo://e02/numeric-shapes",
        ),
    )


def _s10_consumer_result(
    *,
    report: object,
    evidence: dict[str, Any],
) -> tuple[dict[str, Any], Any]:
    candidate = SimpleNamespace(candidate_id="candidate_e02_numeric_shapes")
    problem = SimpleNamespace(
        design_problem_id="problem_e02_numeric_shapes",
        outcome_of_interest=SimpleNamespace(target_variable="test_outcome"),
    )
    world = SimpleNamespace(
        world_model_record_id="world_model_record_e02_numeric_shapes",
        content_hash="sha256:" + "c" * 64,
        valid_time_scope="2026-Q3",
        region_or_jurisdiction="UA-30",
    )
    context_ref = "policy-context://e02/numeric-shapes"
    inputs = generation_cycle._build_s10_forecast_inputs(
        candidate=candidate,
        problem=problem,
        world_record=world,
        method_result=SimpleNamespace(output={"report": report}),
        selected_method_fqn="causal.inference.did.standard@1.0.0",
        forecast_tier="observable_calibrated",
        calibration_status="pass",
        policy_context_ref=context_ref,
        expected_policy_context_ref=context_ref,
        false_clear_counts=evidence["false_clear_counts"],
        calibration_evidence=evidence,
    )
    receipt = generation_cycle._value_calibration_receipt(
        inputs=inputs,
        world_record=world,
    )
    return inputs, receipt


@pytest.mark.parametrize(
    ("point_estimate", "point_value_status"),
    [
        pytest.param(None, "missing", id="missing-point"),
        pytest.param(True, "invalid", id="bool-point"),
        pytest.param(float("nan"), "invalid", id="nan-point"),
        pytest.param(float("inf"), "invalid", id="positive-infinity-point"),
        pytest.param(-float("inf"), "invalid", id="negative-infinity-point"),
    ],
)
def test_s10_shape_diagnostic_keeps_relative_width_unknown_for_invalid_point(
    point_estimate: Any,
    point_value_status: str,
) -> None:
    evidence = generation_cycle._s10_calibration_evidence_from_report(
        _report(point_estimate=point_estimate)
    )

    shape = evidence["estimator_shape_diagnostics"]
    assert shape["finite_point"] is False
    assert shape["point_value_status"] == point_value_status
    assert shape["relative_interval_width"] is None
    assert evidence["ci_width"] == 0.5
    assert evidence["calibration_status"] == "limit"
    assert evidence["denominator"] == 0
    assert evidence["pass_rate"] is None


def test_s10_zero_point_uses_scale_floor_without_promoting_calibration() -> None:
    evidence = generation_cycle._s10_calibration_evidence_from_report(
        _report(point_estimate=0.0)
    )

    shape = evidence["estimator_shape_diagnostics"]
    assert shape["finite_point"] is True
    assert shape["point_value_status"] == "known"
    assert shape["relative_interval_width"] == 0.5
    assert evidence["calibration_status"] == "limit"
    assert evidence["denominator"] == 0
    assert evidence["pass_rate"] is None


def test_s10_missing_interval_keeps_width_and_relative_width_unknown() -> None:
    evidence = generation_cycle._s10_calibration_evidence_from_report(
        _report(point_estimate=0.0, confidence_interval=None)
    )

    shape = evidence["estimator_shape_diagnostics"]
    assert shape["finite_interval"] is False
    assert shape["point_value_status"] == "known"
    assert shape["relative_interval_width"] is None
    assert evidence["ci_width"] is None


@pytest.mark.parametrize(
    "point_estimate",
    [None, 0.0, True, float("nan"), float("inf")],
)
def test_s10_report_shape_and_diagnostics_cannot_clear_value_calibration(
    point_estimate: Any,
) -> None:
    report = _report(point_estimate=point_estimate)
    evidence = generation_cycle._s10_calibration_evidence_from_report(report)
    inputs, receipt = _s10_consumer_result(
        report=report,
        evidence=evidence,
    )

    assert inputs["forecast_support"].forecast_tier == "blocked"
    assert inputs["forecast_calibration_record"] is None
    assert receipt.status == "blocked"


def test_s10_cas_readback_preserves_unknown_vs_zero_diagnostics_and_limitation(
    tmp_path: Path,
) -> None:
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.core.artifacts.manifest import SchemaInfo
    from polisyos.core.artifacts.store import PutOptions

    store_root = tmp_path / "e02-estimator-candidate-cas"
    store = FileSystemCAS(store_root)
    cases: dict[str, dict[str, Any]] = {}
    for label, point_estimate in (("unknown", None), ("zero", 0.0)):
        report = _report(point_estimate=point_estimate)
        evidence = generation_cycle._s10_calibration_evidence_from_report(report)
        report_payload = {
            "point_estimate": point_estimate,
            "confidence_interval": [-0.25, 0.25],
            "standard_error": 0.2,
            "confidence_level": 0.95,
            "diagnostics": [],
            "sample_size": 100,
            "n_treated": 50,
            "n_control": 50,
            "pre_periods": 4,
            "post_periods": 4,
            "method": "e02_numeric_shape_test",
        }
        candidate_payload = {
            "report": report_payload,
            "estimator_calibration_evidence": evidence,
        }
        candidate_bytes = json.dumps(
            candidate_payload,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        ref = store.put_bytes(
            candidate_bytes,
            PutOptions(
                kind="test.json",
                media_type="application/json",
                schema=SchemaInfo(name="tests.E02EstimatorCandidate", version="1.0"),
            ),
        )

        assert store.verify(ref.artifact_id).ok is True
        read_store = FileSystemCAS(store_root)
        loaded_bytes = read_store.get_bytes(ref.artifact_id)
        loaded = json.loads(loaded_bytes.decode("utf-8"))
        loaded_report = SimpleNamespace(**loaded["report"])
        recomputed_evidence = generation_cycle._s10_calibration_evidence_from_report(
            loaded_report
        )
        inputs, receipt = _s10_consumer_result(
            report=loaded_report,
            evidence=recomputed_evidence,
        )
        cases[label] = {
            "stored_evidence": loaded["estimator_calibration_evidence"],
            "evidence": recomputed_evidence,
            "support": inputs["forecast_support"],
            "calibration": inputs["forecast_calibration_record"],
            "receipt": receipt,
        }

    unknown = cases["unknown"]
    zero = cases["zero"]
    assert unknown["stored_evidence"]["estimator_shape_diagnostics"][
        "relative_interval_width"
    ] is None
    assert unknown["evidence"]["estimator_shape_diagnostics"][
        "relative_interval_width"
    ] is None
    assert zero["stored_evidence"]["estimator_shape_diagnostics"][
        "relative_interval_width"
    ] == 0.5
    assert zero["evidence"]["estimator_shape_diagnostics"][
        "relative_interval_width"
    ] == 0.5
    for case in (unknown, zero):
        assert case["support"].forecast_tier == "blocked"
        assert "s10://calibration/fail-closed/insufficient-history" in (
            case["support"].s6_limitation_refs
        )
        assert case["calibration"] is None
        assert case["receipt"].status == "blocked"


def test_foundry_projection_preserves_an_explicit_zero_point() -> None:
    value_set = _project_foundry_value(
        point_estimate=0.0,
        confidence_interval=(-0.25, 0.25),
    )

    assert value_set.identification_status == "point"
    assert value_set.lower == (0.0,)
    assert value_set.upper == (0.0,)


def test_foundry_projection_keeps_missing_point_refusal() -> None:
    with pytest.raises(
        ValueError,
        match="foundry_method_refused_value:uncertainty_missing",
    ):
        _project_foundry_value(
            point_estimate=None,
            confidence_interval=(-0.25, 0.25),
        )


@pytest.mark.parametrize(
    "point_estimate",
    [True, float("nan"), float("inf"), -float("inf")],
)
def test_foundry_projection_typed_refuses_invalid_point(point_estimate: Any) -> None:
    with pytest.raises(ValueError, match="foundry_method_refused_value:point_invalid"):
        _project_foundry_value(
            point_estimate=point_estimate,
            confidence_interval=(-0.25, 0.25),
        )


@pytest.mark.parametrize(
    "confidence_interval",
    [
        (0.0,),
        (True, 1.0),
        (float("nan"), 1.0),
        (0.0, float("inf")),
        (1.0, 0.0),
        ("0.0", 1.0),
    ],
)
def test_foundry_projection_typed_refuses_invalid_interval(
    confidence_interval: Any,
) -> None:
    with pytest.raises(
        ValueError,
        match="foundry_method_refused_value:uncertainty_invalid",
    ):
        _project_foundry_value(
            point_estimate=0.5,
            confidence_interval=confidence_interval,
        )

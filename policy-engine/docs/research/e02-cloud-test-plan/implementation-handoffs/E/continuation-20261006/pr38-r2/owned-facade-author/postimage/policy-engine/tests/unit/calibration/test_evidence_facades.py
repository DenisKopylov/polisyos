"""Scientist uses the canonical public evidence and sampling entrypoints."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import numpy as np
import pytest
from polisyos import calibration
from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.foundry import uncertainty

if TYPE_CHECKING:
    from pathlib import Path


def test_foundry_report_reader_is_canonical_and_refuses_funnel_kind(tmp_path: Path) -> None:
    owner = importlib.import_module("polisyos.foundry.calibration.report")
    node = importlib.import_module(
        "polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty"
    )
    if uncertainty.load_foundry_calibration_report is not owner.load_calibration_report:
        raise AssertionError
    if node.load_foundry_calibration_report is not owner.load_calibration_report:
        raise AssertionError
    if "load_foundry_calibration_report" not in uncertainty.__all__:
        raise AssertionError
    if not ("load_foundry_calibration_report" not in calibration.__all__):
        raise AssertionError
    with pytest.raises(AttributeError):
        _ = calibration.load_foundry_calibration_report
    store = FileSystemCAS(tmp_path / "foundry-report-cas")
    wrong = store.put_json(
        {"report_present": True},
        PutOptions(kind="funnel.calibration_report", media_type="application/json"),
    )
    with pytest.raises(ValueError, match="manifest kind/schema"):
        uncertainty.load_foundry_calibration_report(store, wrong)


def test_forecast_exports_preserve_canonical_types_and_refuse_authority(tmp_path: Path) -> None:
    owner = importlib.import_module("polisyos.calibration.forecast_bridge")
    # Required by the real ForecastOwner caller, independent of the export table.
    for name in (
        "PREDICTIVE_AUTHORITY_DENIALS",
        "REFERENCE_PROFILES",
        "EmpiricalCalibrationContext",
        "EmpiricalCalibrationEvidenceRef",
        "EvidenceArtifactRef",
        "ForecastCalibrationProfile",
        "ForecastCandidateReceipt",
        "ForecastCandidateReceiptRef",
        "ForecastMeasurementBinding",
        "load_empirical_calibration_evidence",
        "load_forecast_calibration_profile",
        "load_forecast_candidate_receipt",
        "persist_empirical_calibration_evidence",
        "persist_forecast_candidate_receipt",
        "produce_empirical_calibration_evidence",
        "resolve_forecast_measurement_binding",
    ):
        if getattr(calibration, name) is not getattr(owner, name):
            raise AssertionError
    with pytest.raises(AttributeError):
        _ = calibration.nonexistent_evidence_authority
    if "ForecastCalibrationProfile" not in dir(calibration):
        raise AssertionError
    store = FileSystemCAS(tmp_path / "cas")

    def ref(kind: str) -> dict[str, object]:
        stored = store.put_json(
            {"test_identity": kind}, PutOptions(kind=kind, media_type="application/json")
        )
        return {
            "artifact_id": str(stored.artifact_id),
            "kind": kind,
            "media_type": "application/json",
        }

    receipt = calibration.ForecastCandidateReceipt(
        profile_ref=ref("ir.forecast_calibration_profile"),
        request_ref=ref("ir.forecast_owner_request"),
        empirical_evidence_ref=ref("ir.empirical_calibration_evidence"),
    )
    if not (receipt.verifier_provenance == "not_established"):
        raise AssertionError
    forged = receipt.model_dump(mode="json") | {"verifier_provenance": "verified"}
    with pytest.raises(ValueError, match="verifier_provenance"):
        calibration.ForecastCandidateReceipt.model_validate(forged)


def test_public_sampling_entrypoint_recomputes_terminal_denominator() -> None:
    owner = importlib.import_module("polisyos.foundry.uncertainty.sampling_admission")
    for name in (
        "BoundedIndicatorResponse",
        "reconcile_draw_outcomes",
        "sampling_content_digest",
        "verify_mean_certificate",
    ):
        if getattr(uncertainty, name) is not getattr(owner, name):
            raise AssertionError
    response = uncertainty.BoundedIndicatorResponse("x", "y", 0.25)
    if not (response(x=0.0) == {"y": 1.0}):
        raise AssertionError
    if not (response(x=0.5) == {"y": 0.0}):
        raise AssertionError
    receipt = {
        "requested_draw_count": 1,
        "attempted_draw_count": 1,
        "unattempted_draw_count": 0,
        "successful_draw_count": 1,
        "outcome_denominator_complete": True,
        "draw_records": [
            {
                "draw_index": 0,
                "sampled_input_sha256": uncertainty.sampling_content_digest({"x": 0.0}),
                "successful_outputs": ["y"],
                "failed_outputs": [],
            }
        ],
        "failure_records": [],
    }
    if not (uncertainty.reconcile_draw_outcomes(receipt, ["y"]) == set()):
        raise AssertionError
    forged = dict(receipt, requested_draw_count=2)
    with pytest.raises(ValueError, match="denominator"):
        uncertainty.reconcile_draw_outcomes(forged, ["y"])


def test_public_finite_law_admission_preserves_atoms_and_domain() -> None:
    owner = importlib.import_module("polisyos.foundry.uncertainty.sampling_admission")
    for name in ("admit_empirical_weights", "admit_unit_uniform", "empirical_cdf"):
        if getattr(uncertainty, name) is not getattr(owner, name):
            raise AssertionError
    probabilities = uncertainty.admit_empirical_weights([1, 1, 2], 3)
    cumulative = uncertainty.empirical_cdf(probabilities)
    np.testing.assert_array_equal(cumulative, [0.25, 0.5, 1.0])
    uniforms = uncertainty.admit_unit_uniform([0, 0.25, 0.5, np.nextafter(1.0, 0.0)])
    np.testing.assert_array_equal(np.searchsorted(cumulative, uniforms, side="right"), [0, 1, 2, 2])
    with pytest.raises(ValueError, match="collapses"):
        uncertainty.admit_empirical_weights([0.5, 1e-20, 0.5], 3)
    with pytest.raises(ValueError, match=r"\[0, 1\)"):
        uncertainty.admit_unit_uniform([1.0])

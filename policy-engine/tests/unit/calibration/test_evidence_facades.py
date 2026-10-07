"""Scientist uses the canonical public evidence and sampling entrypoints."""

from __future__ import annotations

import importlib
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from polisyos import calibration
from polisyos.core import canon as core_canon
from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.foundry import uncertainty
from polisyos.ir.analytics import (
    load_posterior_summary_envelope,
    read_posterior_summary_profile,
)


def test_public_posterior_summary_is_the_canonical_producer_and_return_type() -> None:
    owner = importlib.import_module("polisyos.foundry.calibration.uncertainty_adapter")
    assert (
        uncertainty.summarize_bayesian_calibration_posterior
        is owner.summarize_bayesian_calibration_posterior
    )
    assert (
        uncertainty.BayesianCalibrationPosteriorSummary is owner.BayesianCalibrationPosteriorSummary
    )
    result = uncertainty.summarize_bayesian_calibration_posterior({"x": [0.0] * 99 + [100.0]})
    assert isinstance(result, uncertainty.BayesianCalibrationPosteriorSummary)
    assert result.posterior_means == {"x": 1.0}
    assert result.credible_intervals == {"x": (0.0, 0.0)}
    with pytest.raises(ValueError, match="non-bool"):
        uncertainty.summarize_bayesian_calibration_posterior({"x": [False, 1.0]})
    with pytest.raises(AttributeError):
        _ = uncertainty.nonexistent_posterior_authority


def test_public_posterior_summary_reopens_exact_cas_and_refuses_wrong_kind(tmp_path: Path) -> None:
    result = uncertainty.summarize_bayesian_calibration_posterior({"x": [0.0] * 99 + [100.0]})
    raw = result.parameter_envelopes["x"].model_dump(mode="python", round_trip=True)
    store = FileSystemCAS(tmp_path / "posterior-summary")
    ref = store.put_json(
        raw,
        PutOptions(
            kind="ir.uncertainty_envelope",
            media_type="application/json",
            schema=SchemaInfo(name="ir.uncertainty_envelope", version="1.1"),
        ),
        canon_spec=core_canon.CanonSpec(forbid_floats=False),
    )
    fresh = load_posterior_summary_envelope(FileSystemCAS(tmp_path / "posterior-summary"), ref)
    profile = read_posterior_summary_profile(fresh)
    assert profile.posterior_mean == 1.0
    assert fresh.point_estimate == 0.0
    assert fresh.confidence_interval == (0.0, 0.0)
    assert fresh.distribution_payload.samples == (0.0,) * 99 + (100.0,)
    assert not fresh.gate_eligible
    wrong = ref.model_copy(update={"kind": "funnel.calibration_report"})
    with pytest.raises(ValueError, match="CAS kind/schema/content"):
        load_posterior_summary_envelope(FileSystemCAS(tmp_path / "posterior-summary"), wrong)


def test_foundry_report_reader_is_canonical_and_refuses_funnel_kind(tmp_path: Path) -> None:
    owner = importlib.import_module("polisyos.foundry.calibration.report")
    node = importlib.import_module(
        "polisyos.scientist.nodes.builtins.simulate.propagate_uncertainty"
    )
    assert uncertainty.load_foundry_calibration_report is owner.load_calibration_report
    assert node.load_foundry_calibration_report is owner.load_calibration_report
    assert "load_foundry_calibration_report" in uncertainty.__all__
    assert "load_foundry_calibration_report" not in calibration.__all__
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
        assert getattr(calibration, name) is getattr(owner, name)
    with pytest.raises(AttributeError):
        _ = calibration.nonexistent_evidence_authority
    assert "ForecastCalibrationProfile" in dir(calibration)
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
    assert receipt.verifier_provenance == "not_established"
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
        assert getattr(uncertainty, name) is getattr(owner, name)
    response = uncertainty.BoundedIndicatorResponse("x", "y", 0.25)
    assert response(x=0.0) == {"y": 1.0}
    assert response(x=0.5) == {"y": 0.0}
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
    assert uncertainty.reconcile_draw_outcomes(receipt, ["y"]) == set()
    forged = dict(receipt, requested_draw_count=2)
    with pytest.raises(ValueError, match="denominator"):
        uncertainty.reconcile_draw_outcomes(forged, ["y"])


def test_public_finite_law_admission_preserves_atoms_and_domain() -> None:
    owner = importlib.import_module("polisyos.foundry.uncertainty.sampling_admission")
    for name in ("admit_empirical_weights", "admit_unit_uniform", "empirical_cdf"):
        assert getattr(uncertainty, name) is getattr(owner, name)
    probabilities = uncertainty.admit_empirical_weights([1, 1, 2], 3)
    cumulative = uncertainty.empirical_cdf(probabilities)
    np.testing.assert_array_equal(cumulative, [0.25, 0.5, 1.0])
    uniforms = uncertainty.admit_unit_uniform([0, 0.25, 0.5, np.nextafter(1.0, 0.0)])
    np.testing.assert_array_equal(np.searchsorted(cumulative, uniforms, side="right"), [0, 1, 2, 2])
    # Exact ratios place this positive atom between two distinct finite-U cuts.
    half, tiny = Fraction(1, 2), Fraction.from_float(1e-20)
    total = 2 * half + tiny
    before_half = float(np.nextafter(0.5, 0.0))
    after_half = float(np.nextafter(0.5, np.inf))
    assert Fraction.from_float(before_half) < half / total < half
    assert half < (half + tiny) / total < Fraction.from_float(after_half)
    tiny_weights = uncertainty.admit_empirical_weights([0.5, 1e-20, 0.5], 3)
    tiny_cumulative = uncertainty.empirical_cdf(tiny_weights)
    np.testing.assert_array_equal(tiny_cumulative, [0.5, after_half, 1.0])
    tiny_uniforms = uncertainty.admit_unit_uniform([before_half, 0.5, after_half])
    np.testing.assert_array_equal(
        np.searchsorted(tiny_cumulative, tiny_uniforms, side="right"), [0, 1, 2]
    )
    # With two tiny atoms, the first two upward-rounded cuts coincide at 0.5.
    assert (half + tiny) / (2 * half + 2 * tiny) == half
    with pytest.raises(ValueError, match="no finite-U bucket"):
        uncertainty.admit_empirical_weights([0.5, 1e-20, 1e-20, 0.5], 4)
    with pytest.raises(ValueError, match=r"\[0, 1\)"):
        uncertainty.admit_unit_uniform([1.0])

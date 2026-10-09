"""Numerical causal success does not mint identification admission."""

from __future__ import annotations

import pickle

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir import CausalEffectReport as PublicCausalEffectReport
from polisyos.ir.analytics.causal import (
    CausalEffectReport,
    CausalMethod,
    EstimationStatus,
    load_causal_effect_report,
    persist_causal_effect_report,
)
from polisyos.ir.analytics.uncertainty import (
    IntervalSemantics,
    load_uncertainty_envelope,
    persist_uncertainty_envelope,
)


def _report(method: CausalMethod, inference_method: str = "asymptotic") -> CausalEffectReport:
    return CausalEffectReport(
        method=method,
        estimand="E[Y(1)-Y(0)|target]",
        identified_estimand="producer-supplied expression",
        graph_ref="sha256:" + "a" * 64,
        point_estimate=2.0,
        confidence_interval=(1.8, 2.2),
        confidence_level=0.95,
        standard_error=0.1,
        inference_method=inference_method,
        sample_size=200,
        n_treated=100,
        n_control=100,
        pre_periods=2,
        post_periods=2,
        metadata={
            "parallel_trends_identified": True,
            "gate_eligible": True,
            "identification_admission": {
                "proof_status": "identified",
                "predicate_provenance": "recomputed",
                "verifier_role": "system_verifier",
                "proof_ref": "sha256:" + "b" * 64,
            },
        },
    )


@pytest.mark.parametrize("method", list(CausalMethod))
def test_all_report_families_preserve_success_statistics_as_nongating_candidates(method) -> None:
    report = _report(method)
    before = report.model_dump(mode="json")
    envelope = report.to_uncertainty_envelope()
    assert report.model_dump(mode="json") == before
    assert report.status is EstimationStatus.SUCCESS
    assert envelope is not None
    assert envelope.point_estimate == report.point_estimate
    assert envelope.confidence_interval == report.confidence_interval
    assert envelope.confidence_level == report.confidence_level
    assert envelope.interval_semantics is IntervalSemantics.CONFIDENCE_INTERVAL
    assert envelope.is_heuristic_ci is False
    assert envelope.gate_eligible is False
    assert envelope.metadata["gate_eligibility_reason"] == (
        "causal_identification_admission_not_established"
    )


def test_canonical_class_pickle_and_fresh_cas_reader_preserve_candidate_semantics(tmp_path) -> None:
    assert PublicCausalEffectReport is CausalEffectReport
    assert pickle.loads(pickle.dumps(CausalEffectReport)) is CausalEffectReport  # noqa: S301 - own class bytes
    report = _report(CausalMethod.DOWHY_BACKDOOR, "bayesian_posterior")
    writer = FileSystemCAS(tmp_path)
    ref = persist_causal_effect_report(_ensure_ir_artifact_store(writer), report)
    reader = FileSystemCAS(tmp_path)
    reopened = load_causal_effect_report(_ensure_ir_artifact_store(reader), ref)
    assert type(reopened) is CausalEffectReport
    assert reopened.model_dump(mode="json") == report.model_dump(mode="json")
    envelope = reopened.to_uncertainty_envelope()
    assert envelope is not None
    envelope_ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(writer), envelope)
    reopened_envelope = load_uncertainty_envelope(
        _ensure_ir_artifact_store(FileSystemCAS(tmp_path)), envelope_ref
    )
    assert reopened_envelope.confidence_interval == report.confidence_interval
    assert reopened_envelope.interval_semantics is IntervalSemantics.CREDIBLE_INTERVAL
    assert reopened_envelope.gate_eligible is False

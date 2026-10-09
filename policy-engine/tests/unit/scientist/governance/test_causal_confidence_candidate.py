"""Causal-purpose confidence intake requires an accepted identification owner."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store as _ensure_ir_artifact_store
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import ExecPlanRef, MetricsRef, SimulationResult
from polisyos.core.governance.passes.base import IssueSeverity, PassContext
from polisyos.core.governance.profiles import ValidationProfile
from polisyos.foundry.methods.catalog.causal.did import StandardDifferenceInDifferences
from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
from polisyos.ir.analytics.causal import EstimationStatus
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope, persist_uncertainty_envelope
from polisyos.scientist.governance.passes.confidence_pass import ConfidencePass


def _envelope(source: str) -> UncertaintyEnvelope:
    return UncertaintyEnvelope(
        point_estimate=10.0,
        confidence_interval=(9.9, 10.1),
        source=source,
        gate_eligible=True,
        metadata={
            "proof_status": "identified",
            "identification_verified": True,
            "verifier_role": "system_verifier",
            "identification_proof_ref": "sha256:" + "f" * 64,
        },
    )


def _context(store, state, *, min_ratio: float = 0.5) -> PassContext:
    profile = ValidationProfile.strict()
    profile = replace(
        profile, thresholds={**profile.thresholds, "uncertainty_min_gate_eligible_ratio": min_ratio}
    )
    return PassContext(
        ir=None,
        state={"_store": store, **state},
        registry_bundle=None,
        profile=profile,
        run_id="causal-candidate",
    )


def _candidate_blockers(issues):
    return [
        issue
        for issue in issues
        if issue.severity is IssueSeverity.BLOCKER
        and issue.code == "CONFIDENCE_GATE_ELIGIBILITY_LOW"
        and issue.path == ["artifacts_index", "causal_envelope_ref"]
    ]


@pytest.mark.parametrize("source", ["causal", "ensemble"])
@pytest.mark.parametrize("location", ["artifacts_index", "top_level"])
@pytest.mark.parametrize("min_ratio", [0.0, 0.5, 1.0])
def test_fake_or_relabelled_causal_ref_cannot_pass_any_gate_ratio(
    tmp_path, source, location, min_ratio
) -> None:
    writer = FileSystemCAS(tmp_path)
    ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(writer), _envelope(source))
    state = (
        {"artifacts_index": {"causal_envelope_ref": ref}}
        if location == "artifacts_index"
        else {"causal_envelope_ref": ref}
    )
    issues = ConfidencePass().validate(
        _context(FileSystemCAS(tmp_path), state, min_ratio=min_ratio)
    )
    assert len(_candidate_blockers(issues)) == 1


def test_healthy_simulation_metrics_cannot_dilute_causal_candidate(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    causal_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store), _envelope("ensemble")
    )
    simulation_ref = _simulation(store, metric_count=8)
    issues = ConfidencePass().validate(
        _context(
            store,
            {
                "artifacts_index": {
                    "simulation_result_ref": simulation_ref,
                    "causal_envelope_ref": causal_ref,
                }
            },
        )
    )
    assert len(_candidate_blockers(issues)) == 1


@pytest.mark.parametrize("missing_store", [False, True])
def test_unresolved_causal_input_remains_candidate_without_store_or_bytes(
    tmp_path, missing_store
) -> None:
    store = None if missing_store else FileSystemCAS(tmp_path)
    issues = ConfidencePass().validate(
        _context(store, {"causal_envelope_ref": "sha256:" + "c" * 64}, min_ratio=0.0)
    )
    assert len(_candidate_blockers(issues)) == 1


def _simulation(store: FileSystemCAS, metric_count: int = 1):
    plan = store.put_json(
        {"order": []}, PutOptions(kind="foundry.exec_plan", media_type="application/json")
    )
    metrics = store.put_json(
        {"values": {}}, PutOptions(kind="foundry.metrics", media_type="application/json")
    )
    envelope_ref = persist_uncertainty_envelope(
        _ensure_ir_artifact_store(store), _envelope("ensemble")
    )
    result = SimulationResult(
        exec_plan_ref=ExecPlanRef(artifact_id=plan.artifact_id),
        metrics_ref=MetricsRef(artifact_id=metrics.artifact_id),
        uncertainty_envelopes={f"metric-{i}": envelope_ref for i in range(metric_count)},
    )
    return store.put_json(
        result, PutOptions(kind="foundry.simulation_result", media_type="application/json")
    )


@pytest.mark.parametrize("min_ratio", [0.0, 0.5, 1.0])
def test_supported_noncausal_confidence_profile_remains_eligible(tmp_path, min_ratio) -> None:
    store = FileSystemCAS(tmp_path)
    ref = _simulation(store)
    issues = ConfidencePass().validate(
        _context(store, {"artifacts_index": {"simulation_result_ref": ref}}, min_ratio=min_ratio)
    )
    assert not any(issue.severity is IssueSeverity.BLOCKER for issue in issues)


def test_native_known_dgp_success_interval_is_candidate_at_actual_confidence_consumer(
    tmp_path,
) -> None:
    # Exact parallel-trend panel with population ATT=3. This numerical DGP
    # witness supplies no real-data identification appointment or verifier.
    base = np.tile(np.arange(10, dtype=float), (8, 1))
    treatment = np.array([1, 1, 1, 0, 0, 0, 0, 0])
    base[:3, 5:] += 3.0
    data = PanelObservationalData(outcome=base, treatment=treatment, time_treatment=5)
    output = StandardDifferenceInDifferences.pure_step(data, {})
    report = output["report"]
    assert report.status is EstimationStatus.SUCCESS
    assert report.point_estimate == pytest.approx(3.0)
    assert report.confidence_interval is not None
    envelope = output["envelope"]
    assert envelope.gate_eligible is False
    assert envelope.confidence_interval == pytest.approx(
        report.confidence_interval, rel=0, abs=1e-12
    )
    writer = FileSystemCAS(tmp_path)
    ref = persist_uncertainty_envelope(_ensure_ir_artifact_store(writer), envelope)
    issues = ConfidencePass().validate(
        _context(FileSystemCAS(tmp_path), {"causal_envelope_ref": ref}, min_ratio=0.0)
    )
    assert len(_candidate_blockers(issues)) == 1

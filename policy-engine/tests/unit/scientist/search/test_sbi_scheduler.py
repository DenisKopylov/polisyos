from __future__ import annotations

import pytest

from polisyos.ir.analytics.simulation_proof_bridge import (
    SimulationCertificationStatus,
    SimulationProofBridge,
)
from polisyos.ir.registry.refs import (
    ArtifactRefModel,
    EvidenceBundleRef,
    InterfaceMappingRef,
    ProofBundleRef,
    SimulationCalibrationReceiptRef,
)
from polisyos.scientist.methods.search import ProofAwareSBIScheduler as FacadeScheduler
from polisyos.scientist.methods.search import build_cp_basis_design_plan
from polisyos.scientist.methods.search.sbi_scheduler import (
    CPBASISConfig,
    ProofAwareSBIScheduler,
    ProofGateReceipt,
    ProofGateStatus,
    SBICalibrationSummary,
    SBIDesignCandidate,
    SBIInferenceFamily,
    proof_gate_from_bridge,
)


def _artifact_id(char: str) -> str:
    return f"sha256:{char * 64}"


def _ref(kind: str = "foundry.simulation_result", char: str = "a") -> ArtifactRefModel:
    return ArtifactRefModel(
        artifact_id=_artifact_id(char),
        kind=kind,
        media_type="application/json",
    )


def _candidate(
    candidate_id: str,
    *,
    eig: float,
    cost: float,
    status: ProofGateStatus = ProofGateStatus.IDENTIFIED,
    debt: float = 0.0,
    timeout: float = 0.0,
    family: SBIInferenceFamily = SBIInferenceFamily.NPE,
) -> SBIDesignCandidate:
    return SBIDesignCandidate(
        candidate_id=candidate_id,
        expected_information_gain=eig,
        estimated_cost_usd=cost,
        timeout_risk=timeout,
        calibration_debt=debt,
        proof_gate=ProofGateReceipt(status=status),
        posterior_family=family,
    )


def test_cp_basis_selects_best_proof_weighted_information_per_cost() -> None:
    scheduler = ProofAwareSBIScheduler()
    plan = scheduler.plan(
        [
            _candidate("identified_expensive", eig=10.0, cost=10.0),
            _candidate("bounded_cheap", eig=8.0, cost=2.0, status=ProofGateStatus.BOUNDED),
        ],
        remaining_budget_usd=20.0,
    )

    assert plan.selected_candidate_id == "bounded_cheap"
    assert plan.selected_foundry_method_id == "bayesian.sbi.npe"
    assert plan.ranked_scores[0].proof_status is ProofGateStatus.BOUNDED
    assert plan.unspecified_assumptions == {
        "cost_model": "unspecified",
        "noise_model": "unspecified",
        "allowed_adaptive_designs": "unspecified",
    }


def test_cp_basis_blocks_proof_gate_blocked_candidates_even_with_high_eig() -> None:
    plan = build_cp_basis_design_plan(
        [
            _candidate("blocked", eig=10_000.0, cost=1.0, status=ProofGateStatus.BLOCKED),
            _candidate("identified", eig=1.0, cost=1.0),
        ]
    )

    assert plan.selected_candidate_id == "identified"
    assert plan.blocked_candidate_ids == ("blocked",)
    blocked = next(score for score in plan.ranked_scores if score.candidate_id == "blocked")
    assert blocked.recommended_action == "reject"
    assert blocked.acquisition_score == 0.0


def test_cp_basis_penalizes_calibration_debt_and_timeout_risk() -> None:
    config = CPBASISConfig(lambda_timeout=2.0, lambda_calibration=3.0)
    scheduler = ProofAwareSBIScheduler(config)
    plan = scheduler.plan(
        [
            _candidate("clean", eig=6.0, cost=1.0),
            _candidate("uncalibrated", eig=6.0, cost=1.0, debt=2.0, timeout=0.5),
        ]
    )

    clean, uncalibrated = plan.ranked_scores
    assert clean.candidate_id == "clean"
    assert clean.acquisition_score > uncalibrated.acquisition_score
    assert uncalibrated.denominator == 8.0


def test_cp_basis_defers_when_remaining_budget_is_insufficient() -> None:
    plan = build_cp_basis_design_plan(
        [_candidate("too_expensive", eig=5.0, cost=10.0)],
        remaining_budget_usd=1.0,
    )

    assert plan.selected_candidate_id is None
    assert plan.deferred_candidate_ids == ("too_expensive",)
    assert plan.ranked_scores[0].recommended_action == "defer"


def test_calibration_summary_tracks_required_sbi_diagnostics() -> None:
    failed = SBICalibrationSummary.from_diagnostics(
        sbc_rank_ks_pvalue=0.01,
        expected_coverage_error=0.2,
        tarp_ks_pvalue=None,
        previous_debt=0.5,
    )
    passed = SBICalibrationSummary.from_diagnostics(
        sbc_rank_ks_pvalue=0.3,
        expected_coverage_error=0.02,
        tarp_ks_pvalue=0.4,
        previous_debt=1.0,
    )

    assert failed.accepted is False
    assert failed.calibration_debt == 1.5
    assert failed.degradation_reasons == (
        "sbc_rank_ks_failed",
        "expected_coverage_failed",
        "tarp_missing",
    )
    assert passed.accepted is True
    assert passed.calibration_debt == 0.75


def test_proof_gate_from_bridge_maps_current_unverified_scenario_and_refs() -> None:
    bridge = SimulationProofBridge(
        run_id="R1",
        simulation_result_ref=_ref(char="1"),
        evidence_bundle_ref=EvidenceBundleRef(artifact_id=_artifact_id("2")),
        proof_bundle_ref=ProofBundleRef(artifact_id=_artifact_id("3")),
        calibration_receipt_ref=SimulationCalibrationReceiptRef(artifact_id=_artifact_id("4")),
        interface_mapping_ref=InterfaceMappingRef(artifact_id=_artifact_id("5")),
        certification_status=SimulationCertificationStatus.SCENARIO,
        proof_status="identified",
        calibration_status="unverified",
        composability_status="reusable",
    )

    gate = proof_gate_from_bridge(bridge)

    assert gate.status is ProofGateStatus.SCENARIO
    assert gate.effective_validity_multiplier == 0.25
    assert gate.proof_bundle_ref is not None
    assert str(gate.proof_bundle_ref.artifact_id) == _artifact_id("3")
    assert gate.metadata["calibration_status"] == "unverified"


def test_proof_gate_from_bridge_revalidates_model_construct_bypass() -> None:
    forged = SimulationProofBridge.model_construct(
        run_id="R_forged",
        simulation_result_ref=_ref(char="1"),
        evidence_bundle_ref=EvidenceBundleRef(artifact_id=_artifact_id("2")),
        proof_bundle_ref=ProofBundleRef(artifact_id=_artifact_id("3")),
        calibration_receipt_ref=SimulationCalibrationReceiptRef(artifact_id=_artifact_id("4")),
        interface_mapping_ref=InterfaceMappingRef(artifact_id=_artifact_id("5")),
        certification_status=SimulationCertificationStatus.IDENTIFIED,
        proof_status="identified",
        calibration_status="accepted",
        composability_status="reusable",
    )

    with pytest.raises(ValueError, match="producer/verifier"):
        proof_gate_from_bridge(forged)


def test_search_facade_lazy_exports_cp_basis_scheduler() -> None:
    assert FacadeScheduler is ProofAwareSBIScheduler

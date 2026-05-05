from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.claims.models import ClaimPublishability, ClaimType
from polisyos.scientist.claims.projections import (
    has_decision_bearing_content,
    project_causal_effect_claims,
    project_causal_validity_bundle_claims,
    project_decision_packet_claims,
    project_frontier_runtime_claims,
    project_governance_report_claims,
    project_policy_artifact_bundle_claims,
)
from polisyos.scientist.claims.validators import (
    legacy_claim_ledger_status,
    validate_naked_decision_claims,
    validate_state_claim_projection,
)
from polisyos.scientist.search.readiness import DecisionReadiness


def _ref(suffix: str = "1", *, kind: str = "scientist.evidence") -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind=kind,
        media_type="application/json",
    )


def test_decision_packet_projection_creates_claims_ref_ready_ledger() -> None:
    payload = {
        "policy_summary": "Policy with 1 intervention(s)",
        "governance": {"verdict": "approve", "issues": []},
        "causal": {
            "status": "success",
            "estimand": "ATE(treatment -> outcome)",
            "point_estimate": 0.2,
            "refutation_robust": True,
            "decision_readiness_level": "analyst_advisory",
        },
    }

    ledger = project_decision_packet_claims(
        payload,
        run_id="run_packet",
        source_artifact_refs=[_ref(kind="scientist.causal_effect_report")],
    )

    assert has_decision_bearing_content(payload)
    assert {claim.claim_type for claim in ledger.claims} >= {
        ClaimType.CAUSAL,
        ClaimType.IMPLEMENTATION,
    }
    assert all(claim.evidence_refs for claim in ledger.claims)


def test_policy_bundle_projection_tracks_candidate_and_phase_gate() -> None:
    ledger = project_policy_artifact_bundle_claims(
        {
            "candidate_id": "candidate_1",
            "phase3_gate": {"gate_passed": False},
            "decision_readiness_contract_ref": _ref("2").model_dump(mode="json"),
        },
        run_id="run_policy",
        source_artifact_refs=[_ref("1")],
        readiness_level=DecisionReadiness.ANALYST_ADVISORY,
    )

    assert len(ledger.claims) == 3
    assert any(
        claim.publishability is ClaimPublishability.REVIEW_REQUIRED for claim in ledger.claims
    )


def test_causal_effect_projection_marks_failed_refutations_as_review_required() -> None:
    ledger = project_causal_effect_claims(
        {
            "status": "success",
            "estimand": "ATE",
            "point_estimate": 1.0,
            "refutation_results": [{"passed": False}],
        },
        run_id="run_causal",
        source_artifact_refs=[_ref("1")],
        readiness_level=DecisionReadiness.ANALYST_ADVISORY,
    )

    assert ledger.claims[0].claim_type is ClaimType.CAUSAL
    assert ledger.claims[0].publishability is ClaimPublishability.REVIEW_REQUIRED


def test_governance_projection_tracks_verdict_and_issue_claims() -> None:
    ledger = project_governance_report_claims(
        {
            "verdict": "human_gate",
            "issues": [{"message": "Legal basis requires expert review."}],
        },
        run_id="run_governance",
        source_artifact_refs=[_ref("1")],
    )

    assert {claim.claim_type for claim in ledger.claims} >= {
        ClaimType.IMPLEMENTATION,
        ClaimType.LEGAL,
    }
    assert any(
        claim.publishability is ClaimPublishability.REVIEW_REQUIRED for claim in ledger.claims
    )


def test_causal_validity_projection_preserves_failed_checks_as_counterevidence() -> None:
    ledger = project_causal_validity_bundle_claims(
        {"checks": {"transportability": {"status": "failed"}}},
        run_id="run_validity",
        source_artifact_refs=[_ref("1")],
        readiness_level=DecisionReadiness.ANALYST_ADVISORY,
    )

    assert ledger.claims[0].claim_type is ClaimType.CAUSAL
    assert ledger.claims[0].counterevidence_refs
    assert ledger.claims[0].publishability is ClaimPublishability.REVIEW_REQUIRED
    assert ledger.metadata["failed_checks"] == ["transportability"]


def test_frontier_runtime_projection_tracks_capability_status_claims() -> None:
    ledger = project_frontier_runtime_claims(
        {"capabilities": [{"capability_id": "deep_research", "status": "gated"}]},
        run_id="run_frontier",
        source_artifact_refs=[_ref("1")],
    )

    assert len(ledger.claims) == 1
    assert ledger.claims[0].claim_type is ClaimType.SOURCE_QUALITY
    assert ledger.claims[0].normalized_subject == "deep_research"


def test_naked_decision_claim_validator_blocks_selected_workflow_when_flag_enabled() -> None:
    result = validate_naked_decision_claims(
        {"policy_answer": {"executive_summary": "Adopt the policy."}},
        claims_ref=None,
        workflow_id="scientist_policy_design",
        fail_on_naked_claims=True,
    )

    assert result.passed is False
    assert result.status == "blocked"
    assert result.claim_ledger_status == "legacy_missing"
    assert legacy_claim_ledger_status(None) == "legacy_missing"


def test_state_claim_projection_validator_blocks_decision_artifact_without_claims_ref() -> None:
    result = validate_state_claim_projection(
        workflow_id="scientist_policy_design",
        artifacts_index={"policy_output_bundle_ref": _ref("1")},
        fail_on_naked_claims=True,
    )

    assert result.passed is False
    assert result.violations == ["missing_claims_ref_for_decision_bearing_state"]

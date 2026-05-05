from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.claims.models import (
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.evidence.claim_support import build_source_verification_voi_decisions
from polisyos.scientist.search.readiness import DecisionReadiness


def _ref(suffix: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="scientist.source",
        media_type="application/json",
    )


def _claim(claim_id: str, support_status: ClaimSupportStatus) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        run_id="run_voi",
        claim_type=ClaimType.FACTUAL,
        text=f"Claim {claim_id}",
        support_status=support_status,
        publishability=ClaimPublishability.INTERNAL_ONLY,
        readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        evidence_refs=[] if support_status is ClaimSupportStatus.UNSUPPORTED else [_ref("1")],
        counterevidence_refs=[_ref("2")] if support_status is ClaimSupportStatus.CONTESTED else [],
    )


def test_source_verification_voi_prioritizes_contested_and_unsupported_claims() -> None:
    decisions = build_source_verification_voi_decisions(
        [
            _claim("supported", ClaimSupportStatus.SUPPORTED),
            _claim("unsupported", ClaimSupportStatus.UNSUPPORTED),
            _claim("contested", ClaimSupportStatus.CONTESTED),
        ],
        run_id="run_voi",
        expected_verification_cost=0.1,
    )

    assert decisions[0].metadata["claim_id"] == "unsupported"
    assert decisions[0].recommended_action == "verify_sources"
    assert decisions[1].metadata["claim_id"] == "contested"
    assert decisions[1].expected_risk_reduction > decisions[2].expected_risk_reduction


def test_negative_source_verification_value_defers() -> None:
    decisions = build_source_verification_voi_decisions(
        [_claim("supported", ClaimSupportStatus.SUPPORTED)],
        run_id="run_voi",
        expected_verification_cost=10.0,
    )

    assert decisions[0].recommended_action == "defer"
    assert decisions[0].expected_value < 0.0


def test_supported_claim_with_zero_marginal_voi_defers() -> None:
    decisions = build_source_verification_voi_decisions(
        [_claim("supported", ClaimSupportStatus.SUPPORTED)],
        run_id="run_voi",
        expected_verification_cost=0.05,
    )

    assert decisions[0].recommended_action == "defer"
    assert decisions[0].expected_value == 0.0

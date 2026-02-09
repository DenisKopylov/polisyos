from __future__ import annotations

from decimal import Decimal

from polisyos.fabric.claims.conflicts.uncertainty_adapter import (
    envelope_from_conflict_resolution,
)
from polisyos.ir.analytics.uncertainty import IntervalSemantics, UncertaintySource
from polisyos.ir.world.conflict import ConflictResolutionCandidate, ConflictSetResolution


def _resolution(confidence: str = "0.85") -> ConflictSetResolution:
    return ConflictSetResolution(
        winner_claim_id="claim.a",
        policy_id="policy.default",
        confidence=Decimal(confidence),
        rationale="test rationale",
        resolution_artifact_id="sha256:" + "a" * 64,
    )


def test_conflict_uncertainty_with_two_candidates() -> None:
    resolution = _resolution()
    candidates = [
        ConflictResolutionCandidate(claim_id="claim.a", score_total="0.85"),
        ConflictResolutionCandidate(claim_id="claim.b", score_total="0.60"),
    ]
    env = envelope_from_conflict_resolution(resolution, candidates)
    assert env is not None
    assert env.point_estimate == 0.85
    assert env.ci_lower == 0.6
    assert env.ci_upper == 0.85
    assert env.source == UncertaintySource.CONFLICT_RESOLUTION
    assert env.interval_semantics == IntervalSemantics.DETERMINISTIC_BOUNDS
    assert env.gate_eligible is True


def test_conflict_uncertainty_single_candidate_is_heuristic() -> None:
    resolution = _resolution()
    candidates = [ConflictResolutionCandidate(claim_id="claim.a", score_total="0.85")]
    env = envelope_from_conflict_resolution(resolution, candidates)
    assert env is not None
    assert env.interval_semantics == IntervalSemantics.HEURISTIC_RANGE
    assert env.is_heuristic_ci is True
    assert env.gate_eligible is False


def test_conflict_uncertainty_none_without_candidates() -> None:
    resolution = _resolution()
    assert envelope_from_conflict_resolution(resolution, candidates=None) is None

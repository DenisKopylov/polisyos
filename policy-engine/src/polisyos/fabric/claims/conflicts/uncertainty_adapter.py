from __future__ import annotations

from decimal import Decimal

from polisyos.ir.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.world.conflict import (
    ConflictResolutionCandidate,
    ConflictSetResolution,
)


def _as_score(value: str) -> float:
    return float(Decimal(value))


def envelope_from_conflict_resolution(
    resolution: ConflictSetResolution,
    candidates: list[ConflictResolutionCandidate] | None = None,
) -> UncertaintyEnvelope | None:
    point = float(resolution.confidence)

    if not candidates:
        return None

    scores = [_as_score(candidate.score_total) for candidate in candidates]
    members_count = len(scores)
    winner_score = max(scores)

    if members_count >= 2:
        second_best = max(scores[1:])
        ci_lower = min(second_best, point)
        ci_upper = max(winner_score, point)
        interval_semantics = IntervalSemantics.DETERMINISTIC_BOUNDS
        is_heuristic = False
        gate_eligible = True
    else:
        ci_lower = point
        ci_upper = point
        interval_semantics = IntervalSemantics.HEURISTIC_RANGE
        is_heuristic = True
        gate_eligible = False

    metadata: dict[str, object] = {
        "winner_claim_id": resolution.winner_claim_id,
        "policy_id": resolution.policy_id,
        "rationale": resolution.rationale,
        "members_count": members_count,
        "winner_score": winner_score,
    }
    if members_count >= 2:
        metadata["second_best_score"] = second_best
        metadata["score_spread"] = winner_score - second_best
    else:
        metadata["single_candidate"] = True

    return UncertaintyEnvelope(
        point_estimate=point,
        confidence_interval=(ci_lower, ci_upper),
        confidence_level=None,
        distribution_family=DistributionFamily.UNKNOWN,
        source=UncertaintySource.CONFLICT_RESOLUTION,
        propagation_method=PropagationMethod.NONE,
        interval_semantics=interval_semantics,
        sample_size=members_count,
        is_heuristic_ci=is_heuristic,
        gate_eligible=gate_eligible,
        metadata=metadata,
    )


__all__ = ["envelope_from_conflict_resolution"]

"""Cross-method attribution disagreement metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class AttributionVector:
    """A method-specific attribution vector on one declared output scale."""

    method_id: str
    values: Mapping[str, float]
    confidence_intervals: Mapping[str, tuple[float, float]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MethodDisagreementSummary:
    """Bound-aware, rank-aware summary of cross-method disagreement."""

    methods_compared: tuple[str, ...]
    top_k: int
    magnitude_l1_median: float
    top_k_jaccard_median: float
    kendall_tau_median: float
    sign_conflict_features: tuple[str, ...]
    bound_aware_conflict_features: tuple[str, ...]
    pairwise_l1: Mapping[tuple[str, str], float]
    pairwise_top_k_jaccard: Mapping[tuple[str, str], float]
    pairwise_kendall_tau: Mapping[tuple[str, str], float]
    flags: tuple[str, ...]


def compare_attribution_vectors(
    vectors: Sequence[AttributionVector],
    *,
    top_k: int,
    agreement_floor: float = 0.5,
) -> MethodDisagreementSummary:
    """Compare explanation methods on normalized magnitude, rank, sign, and bounds."""

    if len(vectors) < 2:
        raise ValueError("at least two attribution vectors are required")
    if top_k <= 0:
        raise ValueError("top_k must be positive")

    pairwise_l1: dict[tuple[str, str], float] = {}
    pairwise_jaccard: dict[tuple[str, str], float] = {}
    pairwise_tau: dict[tuple[str, str], float] = {}
    for left, right in combinations(vectors, 2):
        key = (left.method_id, right.method_id)
        pairwise_l1[key] = magnitude_disagreement_l1(left.values, right.values)
        pairwise_jaccard[key] = top_k_jaccard(left.values, right.values, top_k=top_k)
        pairwise_tau[key] = kendall_tau(left.values, right.values)

    sign_conflicts = sign_conflict_features(vectors)
    bound_conflicts = bound_aware_conflict_features(vectors)
    top_k_median = _median(tuple(pairwise_jaccard.values()))
    flags: list[str] = []
    if top_k_median < agreement_floor:
        flags.append("methods_disagree_on_rank_order")
    if sign_conflicts:
        flags.append("methods_disagree_on_sign")
    if bound_conflicts:
        flags.append("bound_intervals_do_not_overlap")

    return MethodDisagreementSummary(
        methods_compared=tuple(vector.method_id for vector in vectors),
        top_k=top_k,
        magnitude_l1_median=_median(tuple(pairwise_l1.values())),
        top_k_jaccard_median=top_k_median,
        kendall_tau_median=_median(tuple(pairwise_tau.values())),
        sign_conflict_features=sign_conflicts,
        bound_aware_conflict_features=bound_conflicts,
        pairwise_l1=pairwise_l1,
        pairwise_top_k_jaccard=pairwise_jaccard,
        pairwise_kendall_tau=pairwise_tau,
        flags=tuple(flags),
    )


def magnitude_disagreement_l1(
    left: Mapping[str, float],
    right: Mapping[str, float],
    *,
    epsilon: float = 1.0e-12,
) -> float:
    """Return normalized L1 attribution disagreement."""

    features = sorted(set(left) | set(right))
    left_norm = _normalize_l1(left)
    right_norm = _normalize_l1(right)
    numerator = sum(
        abs(left_norm.get(feature, 0.0) - right_norm.get(feature, 0.0))
        for feature in features
    )
    denominator = (
        sum(abs(left_norm.get(feature, 0.0)) for feature in features)
        + sum(abs(right_norm.get(feature, 0.0)) for feature in features)
        + epsilon
    )
    return numerator / denominator


def top_k_jaccard(
    left: Mapping[str, float],
    right: Mapping[str, float],
    *,
    top_k: int,
) -> float:
    """Return Jaccard agreement between absolute top-k feature sets."""

    left_top = _top_k_features(left, top_k=top_k)
    right_top = _top_k_features(right, top_k=top_k)
    union = left_top | right_top
    if not union:
        return 1.0
    return len(left_top & right_top) / len(union)


def kendall_tau(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    """Return a simple Kendall tau over the union of feature names."""

    features = sorted(set(left) | set(right))
    concordant = 0
    discordant = 0
    for feature_a, feature_b in combinations(features, 2):
        left_order = _sign(left.get(feature_a, 0.0) - left.get(feature_b, 0.0))
        right_order = _sign(right.get(feature_a, 0.0) - right.get(feature_b, 0.0))
        product = left_order * right_order
        if product > 0:
            concordant += 1
        elif product < 0:
            discordant += 1
    total = concordant + discordant
    if total == 0:
        return 0.0
    return (concordant - discordant) / total


def sign_conflict_features(vectors: Sequence[AttributionVector]) -> tuple[str, ...]:
    """Return features that receive both positive and negative non-zero signs."""

    features = sorted({feature for vector in vectors for feature in vector.values})
    conflicts: list[str] = []
    for feature in features:
        signs = {_sign(vector.values.get(feature, 0.0)) for vector in vectors}
        signs.discard(0)
        if len(signs) > 1:
            conflicts.append(feature)
    return tuple(conflicts)


def bound_aware_conflict_features(vectors: Sequence[AttributionVector]) -> tuple[str, ...]:
    """Return features whose method confidence intervals do not overlap."""

    features = sorted(
        {
            feature
            for vector in vectors
            for feature in vector.confidence_intervals
        }
    )
    conflicts: set[str] = set()
    for feature in features:
        intervals = [
            vector.confidence_intervals[feature]
            for vector in vectors
            if feature in vector.confidence_intervals
        ]
        for left, right in combinations(intervals, 2):
            if left[1] < right[0] or right[1] < left[0]:
                conflicts.add(feature)
    return tuple(sorted(conflicts))


def _normalize_l1(values: Mapping[str, float]) -> dict[str, float]:
    total = sum(abs(_finite(value)) for value in values.values())
    if total == 0.0:
        return dict.fromkeys(values, 0.0)
    return {feature: _finite(value) / total for feature, value in values.items()}


def _top_k_features(values: Mapping[str, float], *, top_k: int) -> set[str]:
    ranked = sorted(values.items(), key=lambda item: (-abs(_finite(item[1])), item[0]))
    return {feature for feature, value in ranked[:top_k] if _finite(value) != 0.0}


def _sign(value: float) -> int:
    finite = _finite(value)
    if finite > 0.0:
        return 1
    if finite < 0.0:
        return -1
    return 0


def _finite(value: float) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("attribution values must be finite")
    return result


def _median(values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    ordered = tuple(sorted(values))
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0

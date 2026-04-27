"""Redundancy-aware feature grouping and ambiguity intervals."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence


@dataclass(frozen=True, slots=True)
class RedundancyEvidence:
    """Evidence used to group dependent or duplicate features."""

    max_abs_corr: float = 0.0
    max_predictability_r2: float = 0.0
    domain_rule: str | None = None


@dataclass(frozen=True, slots=True)
class RedundancyCluster:
    """A feature cluster that should be reported before feature-level allocation."""

    cluster_id: str
    features: tuple[str, ...]
    evidence: RedundancyEvidence
    reporting_policy: str = "group_first"


@dataclass(frozen=True, slots=True)
class FeatureInterval:
    """Min/max attribution interval for one feature across ambiguity samples."""

    feature: str
    lower: float
    upper: float


@dataclass(slots=True)
class _UnionFind:
    parent: dict[str, str] = field(default_factory=dict)

    def add(self, item: str) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: str) -> str:
        self.add(item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            next_item = self.parent[item]
            self.parent[item] = root
            item = next_item
        return root

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def detect_redundancy_clusters(
    rows: Sequence[Mapping[str, float]],
    *,
    corr_threshold: float = 0.8,
    domain_groups: Mapping[str, Sequence[str]] | None = None,
) -> tuple[RedundancyCluster, ...]:
    """Build redundancy clusters from pairwise correlation and declared domain groups."""

    if not 0.0 <= corr_threshold <= 1.0:
        raise ValueError("corr_threshold must be in [0, 1]")
    feature_names = tuple(sorted({feature for row in rows for feature in row}))
    graph = _UnionFind()
    for feature in feature_names:
        graph.add(feature)

    evidence_by_pair: dict[tuple[str, str], RedundancyEvidence] = {}
    for index, left in enumerate(feature_names):
        for right in feature_names[index + 1 :]:
            corr = abs(_pearson(_column(rows, left), _column(rows, right)))
            if corr >= corr_threshold:
                graph.union(left, right)
                evidence_by_pair[(left, right)] = RedundancyEvidence(
                    max_abs_corr=corr,
                    max_predictability_r2=corr * corr,
                )

    for group_id, features in (domain_groups or {}).items():
        normalized = tuple(feature for feature in features if feature in feature_names)
        if len(normalized) < 2:
            continue
        first = normalized[0]
        for feature in normalized[1:]:
            graph.union(first, feature)
            evidence_by_pair[(min(first, feature), max(first, feature))] = RedundancyEvidence(
                domain_rule=group_id,
            )

    grouped: dict[str, list[str]] = {}
    for feature in feature_names:
        grouped.setdefault(graph.find(feature), []).append(feature)

    clusters: list[RedundancyCluster] = []
    for features in grouped.values():
        if len(features) < 2:
            continue
        ordered_features = tuple(sorted(features))
        evidence = _merge_cluster_evidence(ordered_features, evidence_by_pair)
        clusters.append(
            RedundancyCluster(
                cluster_id="_".join(ordered_features),
                features=ordered_features,
                evidence=evidence,
            )
        )
    return tuple(sorted(clusters, key=lambda cluster: cluster.cluster_id))


def group_attributions(
    attributions: Mapping[str, float],
    clusters: Sequence[RedundancyCluster],
) -> dict[str, float]:
    """Sum feature-level attributions into redundancy-cluster attributions."""

    return {
        cluster.cluster_id: sum(
            float(attributions.get(feature, 0.0)) for feature in cluster.features
        )
        for cluster in clusters
    }


def ambiguity_intervals(
    attribution_samples: Iterable[Mapping[str, float]],
    cluster: RedundancyCluster,
) -> tuple[FeatureInterval, ...]:
    """Return feature attribution ranges across methods, bootstraps, or policies."""

    samples = tuple(attribution_samples)
    if not samples:
        raise ValueError("at least one attribution sample is required")
    intervals: list[FeatureInterval] = []
    for feature in cluster.features:
        values = tuple(float(sample.get(feature, 0.0)) for sample in samples)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("attribution samples must be finite")
        intervals.append(
            FeatureInterval(
                feature=feature,
                lower=min(values),
                upper=max(values),
            )
        )
    return tuple(intervals)


def is_allocation_identifiable(
    intervals: Sequence[FeatureInterval],
    *,
    epsilon: float = 1.0e-9,
) -> bool:
    """Return true only when every feature interval is separated from every other."""

    if epsilon < 0.0:
        raise ValueError("epsilon must be non-negative")
    for index, left in enumerate(intervals):
        for right in intervals[index + 1 :]:
            separated = left.upper + epsilon < right.lower or right.upper + epsilon < left.lower
            if not separated:
                return False
    return True


def _column(rows: Sequence[Mapping[str, float]], feature: str) -> tuple[float, ...]:
    return tuple(float(row.get(feature, 0.0)) for row in rows)


def _pearson(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise ValueError("columns must have equal length")
    if len(left) < 2:
        return 0.0
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum(
        (lvalue - left_mean) * (rvalue - right_mean)
        for lvalue, rvalue in zip(left, right, strict=True)
    )
    left_ss = sum((value - left_mean) ** 2 for value in left)
    right_ss = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_ss * right_ss)
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def _merge_cluster_evidence(
    features: tuple[str, ...],
    evidence_by_pair: Mapping[tuple[str, str], RedundancyEvidence],
) -> RedundancyEvidence:
    max_corr = 0.0
    max_r2 = 0.0
    domain_rules: list[str] = []
    for index, left in enumerate(features):
        for right in features[index + 1 :]:
            evidence = evidence_by_pair.get((min(left, right), max(left, right)))
            if evidence is None:
                continue
            max_corr = max(max_corr, evidence.max_abs_corr)
            max_r2 = max(max_r2, evidence.max_predictability_r2)
            if evidence.domain_rule is not None:
                domain_rules.append(evidence.domain_rule)
    return RedundancyEvidence(
        max_abs_corr=max_corr,
        max_predictability_r2=max_r2,
        domain_rule=",".join(sorted(set(domain_rules))) or None,
    )

"""
Source ranking for federation - scores connectors by relevance.

Implements multi-factor scoring algorithm that considers trust, completeness,
freshness, and latency to rank data sources for a given composition request.
"""

from __future__ import annotations

from datetime import UTC, timedelta

from polisyos.common.logger import get_logger
from polisyos.core.evaluation import WeightedScorer
from polisyos.fabric.connectors.federation.types import (
    CompositionRequest,
    RankedSource,
    RankingWeights,
)
from polisyos.fabric.connectors.quality.report import DataQualityReport
from polisyos.fabric.finite import ensure_non_negative_finite, ensure_probability
from polisyos.fabric.temporal import utc_now
from polisyos.ir.connectors import ConnectorMetadataSpec, TrustLevel

logger = get_logger(__name__)


class SourceRanker:
    """
    Ranks connectors by relevance to a composition request.

    Uses multi-factor scoring:
    - Trust level (0.4 default weight)
    - Completeness (0.3 default weight)
    - Freshness (0.2 default weight)
    - Latency (0.1 default weight)
    """

    def __init__(self, weights: RankingWeights | None = None) -> None:
        """Initialize ranker with custom or default weights."""
        self.weights = weights or RankingWeights()
        self.weights.validate_sum()
        self._scorer = WeightedScorer(
            {
                "trust": self.weights.trust,
                "completeness": self.weights.completeness,
                "freshness": self.weights.freshness,
                "latency": self.weights.latency,
            }
        )

    def rank_sources(
        self,
        candidates: list[ConnectorMetadataSpec],
        request: CompositionRequest,
        quality_reports: dict[str, DataQualityReport] | None = None,
        *,
        enforce_max_staleness: bool = True,
    ) -> list[RankedSource]:
        """
        Rank sources by relevance to request.

        Args:
            candidates: List of connector metadata to rank
            request: Composition request with preferences
            quality_reports: Optional quality reports keyed by connector_id
            enforce_max_staleness: If True, drop sources older than max_staleness

        Returns:
            List of RankedSource sorted by relevance (highest first)
        """
        quality_reports = quality_reports or {}
        ranked: list[RankedSource] = []

        for connector in candidates:
            quality_report = quality_reports.get(connector.fully_qualified_id)

            if (
                enforce_max_staleness
                and request.max_staleness
                and self._is_stale(connector, quality_report, request.max_staleness)
            ):
                logger.info(
                    "Excluding stale connector",
                    connector=connector.fully_qualified_id,
                )
                continue

            score, components = self._calculate_relevance_score(
                connector=connector,
                quality_report=quality_report,
                request=request,
            )

            ranked.append(
                RankedSource(
                    connector_id=connector.fully_qualified_id,
                    metadata=connector,
                    relevance_score=score,
                    score_components=components,
                    quality_report=quality_report,
                )
            )

        ranked.sort(key=lambda r: r.relevance_score, reverse=True)

        logger.info(
            "Ranked sources",
            dataset=request.dataset_pattern,
            count=len(ranked),
            top_source=ranked[0].connector_id if ranked else None,
        )

        return ranked

    def _calculate_relevance_score(
        self,
        connector: ConnectorMetadataSpec,
        quality_report: DataQualityReport | None,
        request: CompositionRequest,
    ) -> tuple[float, dict[str, float]]:
        """Calculate 0.0-1.0 relevance score for a connector."""
        trust_score = self._calculate_trust_score(connector)
        completeness_score = self._calculate_completeness_score(quality_report)
        freshness_score = self._calculate_freshness_score(
            connector, quality_report, request.max_staleness
        )
        latency_score = self._calculate_latency_score(connector, quality_report)

        component_scores = {
            "trust": trust_score,
            "completeness": completeness_score,
            "freshness": freshness_score,
            "latency": latency_score,
        }
        total_score = ensure_probability(
            self._scorer.score(component_scores).score,
            what="source relevance score",
        )
        return total_score, component_scores

    def _calculate_trust_score(self, connector: ConnectorMetadataSpec) -> float:
        """Calculate trust score (0.0-1.0) based on TrustLevel."""
        trust_level = connector.trust_level

        if trust_level == TrustLevel.AUTHORITATIVE:
            return 1.0
        if trust_level == TrustLevel.HIGH:
            return 0.75
        if trust_level == TrustLevel.MEDIUM:
            return 0.5
        if trust_level == TrustLevel.LOW:
            return 0.25
        return 0.0

    def _calculate_completeness_score(self, quality_report: DataQualityReport | None) -> float:
        """Calculate completeness score (0.0-1.0) from quality report."""
        if quality_report is None:
            return 0.5

        completeness = getattr(quality_report, "completeness_score", None)
        if completeness is None:
            completeness = getattr(quality_report, "completeness", None)

        if completeness is None:
            return 0.5
        try:
            return ensure_probability(
                completeness,
                what="source completeness score",
                clamp=True,
            )
        except ValueError:
            return 0.5

    def _calculate_freshness_score(
        self,
        connector: ConnectorMetadataSpec,
        quality_report: DataQualityReport | None,
        max_staleness,
    ) -> float:
        """Calculate freshness score (0.0-1.0) based on last update time."""
        last_updated = connector.last_updated
        if last_updated is None and quality_report is not None:
            last_updated = quality_report.freshness_status.last_updated

        if last_updated is None and quality_report is not None:
            age_seconds = quality_report.freshness_status.data_age_seconds
            if age_seconds is not None:
                try:
                    age_seconds = ensure_non_negative_finite(
                        age_seconds,
                        what="freshness data_age_seconds",
                    )
                except ValueError:
                    return 0.5
                last_updated = utc_now() - timedelta(seconds=age_seconds)

        if last_updated is None:
            return 0.5

        now = utc_now()
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=UTC)

        age_hours = max(0.0, (now - last_updated).total_seconds() / 3600.0)
        if max_staleness is not None and age_hours > max_staleness.total_seconds() / 3600.0:
            return 0.0

        return ensure_probability(
            0.5 ** (age_hours / 24.0),
            what="source freshness score",
        )

    def _calculate_latency_score(
        self,
        connector: ConnectorMetadataSpec,
        quality_report: DataQualityReport | None,
    ) -> float:
        """Calculate latency score (0.0-1.0) based on average response time."""
        latency_ms = connector.observed_latency_ms
        if latency_ms is None and quality_report is not None:
            latency_ms = getattr(quality_report, "avg_latency_ms", None)

        if latency_ms is None:
            return 0.5

        try:
            latency_ms = ensure_non_negative_finite(latency_ms, what="latency_ms")
        except ValueError:
            return 0.5
        latency_score = 1.0 / (1.0 + latency_ms / 100.0)
        return ensure_probability(latency_score, what="source latency score")

    def _is_stale(
        self,
        connector: ConnectorMetadataSpec,
        quality_report: DataQualityReport | None,
        max_staleness,
    ) -> bool:
        if max_staleness is None:
            return False
        last_updated = connector.last_updated
        if last_updated is None and quality_report is not None:
            last_updated = quality_report.freshness_status.last_updated
        if last_updated is None:
            return False
        now = utc_now()
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=UTC)
        return (now - last_updated) > max_staleness

    def explain_score(self, ranked_source: RankedSource) -> str:
        """Generate human-readable explanation of a source's score."""
        lines = [
            f"Source: {ranked_source.connector_id}",
            f"Total Score: {ranked_source.relevance_score:.3f}",
            "",
            "Component Scores:",
        ]

        for component, score in ranked_source.score_components.items():
            weight = getattr(self.weights, component)
            contribution = weight * score
            lines.append(
                f"  {component.capitalize()}: {score:.3f} "
                f"(weight={weight:.2f}, contribution={contribution:.3f})"
            )

        return "\n".join(lines)

    def compare_sources(self, source_a: RankedSource, source_b: RankedSource) -> str:
        """Generate comparison between two sources."""
        lines = [
            f"Comparing {source_a.connector_id} vs {source_b.connector_id}",
            f"Scores: {source_a.relevance_score:.3f} vs {source_b.relevance_score:.3f}",
            "",
            "Component Breakdown:",
        ]

        for component in ["trust", "completeness", "freshness", "latency"]:
            score_a = source_a.score_components[component]
            score_b = source_b.score_components[component]
            diff = score_a - score_b
            winner = source_a.connector_id if diff > 0 else source_b.connector_id

            lines.append(
                f"  {component.capitalize()}: {score_a:.3f} vs {score_b:.3f} "
                f"(diff={diff:+.3f}, winner={winner})"
            )

        return "\n".join(lines)

"""Deterministic FastLane resolver for metric -> fetch plan mapping."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polisyos.common.logger import get_logger
from polisyos.core.contracts.control import (
    DataNeed,
    FetchPlan,
    FetchPlanFallback,
    MetricCandidate,
)
from polisyos.fabric.catalog.registry import DataContractRegistry
from polisyos.fabric.catalog.search import MetricSearcher
from polisyos.fabric.catalog.source_bindings import SourceBinding, SourceBindingRegistry
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.ir.connectors import TrustLevel

logger = get_logger(__name__)


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(parts).encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _trust_level_score(level: TrustLevel | None) -> float:
    if level is None:
        return 0.5
    mapping = {
        TrustLevel.UNVERIFIED: 0.2,
        TrustLevel.LOW: 0.35,
        TrustLevel.MEDIUM: 0.6,
        TrustLevel.HIGH: 0.8,
        TrustLevel.AUTHORITATIVE: 1.0,
    }
    return mapping.get(level, 0.5)


def _freshness_score(last_updated: datetime | None) -> float:
    if last_updated is None:
        return 0.5
    stamp = last_updated
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (datetime.now(timezone.utc) - stamp).total_seconds() / 3600.0)
    # 24h half-life.
    return max(0.05, min(1.0, 0.5 ** (age_hours / 24.0)))


@dataclass(frozen=True)
class FastLaneResolveResult:
    fetch_plans: list[FetchPlan]
    candidates: list[MetricCandidate]
    warnings: list[str]


class FastLaneResolver:
    """Resolves `DataNeed` into ranked candidates and concrete fetch plans."""

    def __init__(
        self,
        *,
        curated_dir: Path,
        bindings_filename: str = SourceBindingRegistry.DEFAULT_FILENAME,
    ) -> None:
        self._bindings = SourceBindingRegistry(curated_dir, filename=bindings_filename, strict=False)
        self._contracts = DataContractRegistry(curated_dir, strict=False)
        self._searcher = MetricSearcher(list(self._contracts), threshold=0.45, max_results=12)
        self._connector_registry = ConnectorRegistry.get_instance()

    @property
    def binding_registry(self) -> SourceBindingRegistry:
        return self._bindings

    def resolve(
        self,
        data_needs: list[DataNeed],
        *,
        max_candidates_per_need: int = 5,
        max_fallbacks: int = 2,
    ) -> FastLaneResolveResult:
        fetch_plans: list[FetchPlan] = []
        all_candidates: list[MetricCandidate] = []
        warnings: list[str] = []

        for need in data_needs:
            candidates = self.resolve_candidates_for_need(
                need,
                max_candidates=max_candidates_per_need,
            )
            if not candidates:
                warnings.append(f"No FastLane candidates for metric '{need.metric}'")
                continue
            all_candidates.extend(candidates)
            primary = candidates[0]
            fallbacks = [
                FetchPlanFallback(
                    connector_id=item.connector_id,
                    dataset_id=item.dataset_id,
                    profile_id=item.profile_id,
                    filters=item.filters_template,
                )
                for item in candidates[1 : max_fallbacks + 1]
            ]
            plan = FetchPlan(
                plan_id=_stable_id("plan", need.metric, primary.connector_id, primary.dataset_id),
                metric_id=primary.metric_id,
                connector_id=primary.connector_id,
                dataset_id=primary.dataset_id,
                profile_id=primary.profile_id,
                filters=self._build_filters(need=need, candidate=primary),
                date_start=need.time_start,
                date_end=need.time_end,
                granularity=need.granularity,
                quality_min=need.quality_min,
                source_lane="fastlane",
                fallbacks=fallbacks,
                metadata={
                    "purpose": need.purpose,
                    "match_reason": primary.match_reason,
                    "confidence": primary.confidence,
                },
            )
            fetch_plans.append(plan)

        return FastLaneResolveResult(
            fetch_plans=fetch_plans,
            candidates=all_candidates,
            warnings=warnings,
        )

    def search_catalog(
        self,
        *,
        metric_query: str,
        geography: str | None = None,
        limit: int = 25,
    ) -> list[MetricCandidate]:
        results: list[MetricCandidate] = []
        bindings = self._bindings.search(metric_query, geography=geography, limit=limit)
        for idx, binding in enumerate(bindings, start=1):
            score, trust_score, freshness_score, latency_ms, reason = self._score_binding(
                binding=binding,
                metric_match=1.0,
                need=DataNeed(metric=binding.metric_id, geography=geography),
            )
            results.append(
                MetricCandidate(
                    candidate_id=_stable_id("cand", binding.metric_id, binding.connector_id, binding.dataset_id),
                    metric_id=binding.metric_id,
                    connector_id=binding.connector_id,
                    dataset_id=binding.dataset_id,
                    profile_id=binding.profile_id,
                    source_lane="fastlane",
                    confidence=score,
                    rank=idx,
                    trust_score=trust_score,
                    freshness_score=freshness_score,
                    latency_estimate_ms=latency_ms,
                    filters_template=binding.filters_template,
                    match_reason=reason,
                    metadata={"priority": binding.priority},
                )
            )
        return results

    def resolve_candidates_for_need(
        self,
        need: DataNeed,
        *,
        max_candidates: int = 5,
    ) -> list[MetricCandidate]:
        metric_candidates = self._resolve_metric_candidates(need.metric)
        ranked: list[MetricCandidate] = []
        for metric_id, metric_match in metric_candidates:
            bindings = self._bindings.bindings_for_metric(metric_id, geography=need.geography)
            for binding in bindings:
                confidence, trust_score, freshness_score, latency_ms, reason = self._score_binding(
                    binding=binding,
                    metric_match=metric_match,
                    need=need,
                )
                ranked.append(
                    MetricCandidate(
                        candidate_id=_stable_id(
                            "cand",
                            metric_id,
                            binding.connector_id,
                            binding.dataset_id,
                            need.geography or "*",
                        ),
                        metric_id=metric_id,
                        connector_id=binding.connector_id,
                        dataset_id=binding.dataset_id,
                        profile_id=binding.profile_id,
                        source_lane="fastlane",
                        confidence=confidence,
                        rank=1,
                        trust_score=trust_score,
                        freshness_score=freshness_score,
                        coverage_estimate=None,
                        latency_estimate_ms=latency_ms,
                        filters_template=binding.filters_template,
                        match_reason=reason,
                        metadata={
                            "priority": binding.priority,
                            "tags": binding.tags,
                            "metric_match": metric_match,
                        },
                    )
                )

        ranked.sort(
            key=lambda item: (
                -item.confidence,
                -item.trust_score,
                item.latency_estimate_ms if item.latency_estimate_ms is not None else 1_000_000,
                item.connector_id,
                item.dataset_id,
            )
        )

        for rank, candidate in enumerate(ranked, start=1):
            candidate.rank = rank
        return ranked[:max_candidates]

    def _resolve_metric_candidates(self, metric_query: str) -> list[tuple[str, float]]:
        query = metric_query.strip()
        if not query:
            return []
        if query in self._bindings.list_metric_ids():
            return [(query, 1.0)]
        if query in self._contracts:
            return [(query, 1.0)]
        response = self._searcher.search(query)
        ranked = [(result.contract.metric_id, result.confidence) for result in response.results]
        if ranked:
            return ranked
        wildcard_bindings = self._bindings.search(query, limit=10)
        seen: set[str] = set()
        fallback: list[tuple[str, float]] = []
        for item in wildcard_bindings:
            if item.metric_id in seen:
                continue
            seen.add(item.metric_id)
            fallback.append((item.metric_id, 0.55))
        return fallback

    def _score_binding(
        self,
        *,
        binding: SourceBinding,
        metric_match: float,
        need: DataNeed,
    ) -> tuple[float, float, float, int | None, str]:
        metadata = self._get_connector_metadata(binding.connector_id)
        trust_score = max(binding.trust, _trust_level_score(metadata.get("trust_level")))
        freshness_score = _freshness_score(metadata.get("last_updated"))
        latency_ms = metadata.get("latency_ms")

        granularity_score = 0.7
        if not binding.granularity:
            granularity_score = 0.7
        elif need.granularity.lower() in binding.granularity:
            granularity_score = 1.0
        else:
            granularity_score = 0.35

        geography_score = 1.0 if binding.matches_geography(need.geography) else 0.15
        priority_score = 1.0 / (1.0 + (binding.priority / 25.0))

        confidence = (
            0.30 * max(0.0, min(1.0, metric_match))
            + 0.20 * trust_score
            + 0.18 * freshness_score
            + 0.18 * granularity_score
            + 0.08 * geography_score
            + 0.06 * priority_score
        )
        confidence = max(0.0, min(1.0, confidence))

        reason = (
            f"metric={metric_match:.2f}, trust={trust_score:.2f}, "
            f"freshness={freshness_score:.2f}, granularity={granularity_score:.2f}"
        )
        return confidence, trust_score, freshness_score, latency_ms, reason

    def _get_connector_metadata(self, connector_id: str) -> dict[str, Any]:
        try:
            meta = self._connector_registry.get_metadata(connector_id)
        except Exception:
            logger.debug(
                "Failed to get connector metadata for %s", connector_id, exc_info=True,
            )
            return {"trust_level": None, "last_updated": None, "latency_ms": None}
        return {
            "trust_level": meta.trust_level,
            "last_updated": meta.last_updated,
            "latency_ms": int(meta.observed_latency_ms) if meta.observed_latency_ms else None,
        }

    @staticmethod
    def _build_filters(*, need: DataNeed, candidate: MetricCandidate) -> dict[str, list[str]]:
        filters = {key: list(values) for key, values in candidate.filters_template.items()}
        geography = (need.geography or "").strip()
        if geography and "geo" not in filters and "country" not in filters:
            filters["geo"] = [geography]
        return filters


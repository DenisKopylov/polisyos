"""Bounded on-demand metadata discovery (ExploreLane)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.async_tools import run_coro_sync
from polisyos.common.logger import get_logger
from polisyos.core.contracts.control import DataNeed, DiscoveryCandidate
from polisyos.fabric.connectors.profiles.resolver import resolve_connection_config
from polisyos.ir.connectors import ConnectorCapability

from .providers import RetrievalProviders, resolve_retrieval_providers

if TYPE_CHECKING:
    from polisyos.fabric.connectors.base import ConnectionConfig
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExploreLaneLimits:
    """Explore lane limits public type."""
    max_sources_per_query: int = 5
    max_discovery_calls_per_source: int = 25
    max_candidates_total: int = 50
    time_budget_ms: int = 5_000
    cost_budget_usd: float = 0.0


@dataclass(frozen=True)
class ExploreLaneDiscoverResult:
    """Budget-bounded discovery output with candidate datasets, fetch count, and warnings."""
    candidates: list[DiscoveryCandidate]
    docs_fetched_total: int
    warnings: list[str]


class ExploreLaneDiscovery:
    """Live discovery orchestrator with strict budget guardrails."""

    def __init__(
        self,
        *,
        registry: ConnectorRegistry | None = None,
        profiles: SourceProfileRegistry | None = None,
        providers: RetrievalProviders | None = None,
    ) -> None:
        resolved = providers or resolve_retrieval_providers(
            registry=registry,
            profiles=profiles,
        )
        self._registry = resolved.registry
        self._profiles = resolved.profiles

    def discover(
        self,
        data_needs: list[DataNeed],
        *,
        limits: ExploreLaneLimits | None = None,
    ) -> ExploreLaneDiscoverResult:
        active_limits = limits or ExploreLaneLimits()
        return cast(
            "ExploreLaneDiscoverResult",
            run_coro_sync(self._discover_async(data_needs, limits=active_limits)),
        )

    async def _discover_async(
        self,
        data_needs: list[DataNeed],
        *,
        limits: ExploreLaneLimits,
    ) -> ExploreLaneDiscoverResult:
        started = time.perf_counter()
        docs_fetched_total = 0
        warnings: list[str] = []
        candidates: list[DiscoveryCandidate] = []

        connector_entries = list(
            self._registry.query_entries(capabilities=ConnectorCapability.CATALOG_BROWSE)
        )
        connector_entries = connector_entries[: max(1, limits.max_sources_per_query)]

        for need in data_needs:
            for entry in connector_entries:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                if elapsed_ms >= limits.time_budget_ms:
                    warnings.append("time_budget_reached")
                    break
                if len(candidates) >= limits.max_candidates_total:
                    warnings.append("candidate_budget_reached")
                    break

                connector_id = entry.short_id
                connector = self._registry.get(connector_id, enable_cache=False)
                config = self._resolve_connection_config(entry.metadata.namespace, connector_id)
                if config is None:
                    warnings.append(f"missing_connection_config:{connector_id}")
                    continue

                handle = await self._registry.get_connection(connector_id, config)
                try:
                    per_source_calls = 0
                    dataset_iterator = cast(
                        "Any",
                        connector.list_datasets(handle),
                    )
                    async for descriptor in dataset_iterator:
                        per_source_calls += 1
                        docs_fetched_total += 1
                        if per_source_calls > limits.max_discovery_calls_per_source:
                            break
                        if len(candidates) >= limits.max_candidates_total:
                            break

                        score = self._descriptor_match_score(need=need, descriptor=descriptor)
                        if score <= 0.0:
                            continue

                        schema_excerpt: dict[str, Any] = {}
                        if score >= 0.7:
                            try:
                                schema_raw = await connector.get_dataset_schema(
                                    handle,
                                    descriptor.dataset_id,
                                )
                                if isinstance(schema_raw, dict):
                                    schema_excerpt = schema_raw
                            except Exception:
                                logger.debug(
                                    "Failed to fetch dataset schema for connector=%s dataset=%s",
                                    connector_id, descriptor.dataset_id, exc_info=True,
                                )
                                schema_excerpt = {}

                        candidates.append(
                            DiscoveryCandidate(
                                candidate_id=(
                                    f"disc_{need.metric}_{connector_id}_{descriptor.dataset_id}"
                                ),
                                metric_id=need.metric,
                                connector_id=connector_id,
                                dataset_id=descriptor.dataset_id,
                                dataset_name=descriptor.name,
                                description=descriptor.description,
                                profile_id=self._default_profile_id(entry.metadata.namespace),
                                confidence=score,
                                coverage_estimate=None,
                                latency_estimate_ms=(
                                    int(entry.metadata.observed_latency_ms)
                                    if entry.metadata.observed_latency_ms
                                    else None
                                ),
                                schema_excerpt=schema_excerpt,
                                discovered_at=datetime.now(UTC),
                                metadata={
                                    "tags": list(descriptor.tags),
                                    "supports_filters": list(descriptor.supports_filters),
                                    "namespace": entry.metadata.namespace,
                                },
                            )
                        )
                except Exception as exc:
                    warnings.append(f"discover_failed:{connector_id}:{exc}")
                finally:
                    await self._registry.release_connection(connector_id, handle)

        candidates.sort(
            key=lambda item: (
                -item.confidence,
                item.connector_id,
                item.dataset_id,
            )
        )
        return ExploreLaneDiscoverResult(
            candidates=candidates[: limits.max_candidates_total],
            docs_fetched_total=docs_fetched_total,
            warnings=warnings,
        )

    def _resolve_connection_config(
        self,
        family: str,
        connector_id: str,
    ) -> ConnectionConfig | None:
        default = self._registry.get_default_config(connector_id)
        if default is not None:
            return cast("ConnectionConfig", default)
        profiles = self._profiles.list_by_family(family)
        if not profiles:
            return None
        return cast("ConnectionConfig", resolve_connection_config(profiles[0]))

    def _default_profile_id(self, family: str) -> str | None:
        profiles = self._profiles.list_by_family(family)
        if not profiles:
            return None
        return cast("str | None", profiles[0].profile_id)

    @staticmethod
    def _descriptor_match_score(*, need: DataNeed, descriptor: Any) -> float:
        metric_query = need.metric.strip().lower()
        tokens = [token for token in metric_query.replace(".", " ").replace("_", " ").split() if token]
        if not tokens:
            return 0.0
        searchable = " ".join(
            [
                str(getattr(descriptor, "dataset_id", "")).lower(),
                str(getattr(descriptor, "name", "")).lower(),
                str(getattr(descriptor, "description", "")).lower(),
                " ".join(str(tag).lower() for tag in getattr(descriptor, "tags", ()) or ()),
            ]
        )
        if not searchable.strip():
            return 0.0
        hits = sum(1 for token in tokens if token in searchable)
        if hits == 0:
            return 0.0
        base = hits / len(tokens)
        if metric_query in searchable:
            base = max(base, 0.9)
        return min(1.0, max(0.05, base))

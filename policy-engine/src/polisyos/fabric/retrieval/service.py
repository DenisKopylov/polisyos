"""Hybrid retrieval service (FastLane + ExploreLane + PromotionLane)."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from polisyos.common.logger import get_logger
from polisyos.core.contracts.control import (
    DataContext,
    DataNeed,
    DataResolveRequest,
    DiscoveryCandidate,
    FetchPlan,
    FetchPlanFallback,
    IndexStats,
    MetricCandidate,
    PromotionCandidate,
)
from polisyos.datasets.batch.source_registry import SourceSpec, load_source_registry
from polisyos.fabric.catalog.resolver_fast_lane import FastLaneResolver
from polisyos.fabric.catalog.source_bindings import SourceBinding
from polisyos.fabric.observability import FABRIC_TRACE_NAMES

from .executor import ExecutePlanResult, FetchExecutor
from .explore_lane import ExploreLaneDiscoverResult, ExploreLaneDiscovery, ExploreLaneLimits
from .providers import RetrievalProviders, resolve_retrieval_providers

if TYPE_CHECKING:
    from collections.abc import Sequence

    from polisyos.core.observability import MetricsRegistry, PolicyOSTracer
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry

logger = get_logger(__name__)


@dataclass(frozen=True)
class ResolveOutcome:
    """Resolve outcome public type."""
    mode: str
    fetch_plans: list[FetchPlan]
    candidates: list[MetricCandidate]
    warnings: list[str]
    telemetry: dict[str, object]


@dataclass(frozen=True)
class DiscoverOutcome:
    """Discover outcome public type."""
    candidates: list[DiscoveryCandidate]
    docs_fetched_total: int
    warnings: list[str]


@dataclass(frozen=True)
class ExecuteOutcome:
    """Execute outcome public type."""
    data_context: DataContext
    previews: list[ExecutePlanResult]
    promoted_count: int
    fallback_triggered_count: int


def _flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null"}:
        return None
    return text


def _coerce_int(value: object, *, default: int = 0) -> int:
    try:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            return int(value)
    except (TypeError, ValueError):
        pass
    return default


def _coerce_float(value: object, *, default: float = 0.0) -> float:
    try:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value)
    except (TypeError, ValueError):
        pass
    return default


def _coerce_filter_map(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for key, raw_values in value.items():
        if not isinstance(key, str):
            continue
        if isinstance(raw_values, list):
            normalized[key] = [str(item) for item in raw_values]
        elif raw_values is not None:
            normalized[key] = [str(raw_values)]
    return normalized


class RetrievalService:
    """High-level retrieval orchestrator for control API and NL pipeline."""

    def __init__(
        self,
        *,
        curated_dir: Path,
        cas_root: Path | None = None,
        dataset_catalog: object | None = None,
        max_local_index_docs: int = 2_048,
        max_promotion_candidates: int = 512,
        registry: ConnectorRegistry | None = None,
        profiles: SourceProfileRegistry | None = None,
        tracer: PolicyOSTracer | None = None,
        metrics: MetricsRegistry | None = None,
        fastlane: FastLaneResolver | None = None,
        executor: FetchExecutor | None = None,
        explore: ExploreLaneDiscovery | None = None,
        providers: RetrievalProviders | None = None,
    ) -> None:
        resolved = providers or resolve_retrieval_providers(
            registry=registry,
            profiles=profiles,
            tracer=tracer,
            metrics=metrics,
        )
        resolved_registry = resolved.registry
        resolved_profiles = resolved.profiles
        resolved_tracer = resolved.tracer
        resolved_metrics = resolved.metrics
        self._fastlane = fastlane or FastLaneResolver(
            curated_dir=curated_dir,
            connector_registry=resolved_registry,
        )
        self._explore = explore or ExploreLaneDiscovery(
            providers=resolved,
        )
        self._executor = executor or FetchExecutor(
            cas_root=cas_root,
            providers=resolved,
        )
        self._dataset_catalog = dataset_catalog  # DatasetCatalogGraph (optional)
        self._registry = resolved_registry
        self._profiles = resolved_profiles
        self._tracer = resolved_tracer
        self._metrics = resolved_metrics
        self._promotion_queue: OrderedDict[str, PromotionCandidate] = OrderedDict()
        self._local_index_docs: OrderedDict[str, dict[str, object]] = OrderedDict()
        self._index_size_bytes = 0
        self._docs_added_last_run = 0
        self._last_updated: datetime | None = None
        self._catalog_source_policies: dict[str, SourceSpec] | None = None
        self._max_local_index_docs = max(1, max_local_index_docs)
        self._max_promotion_candidates = max(1, max_promotion_candidates)
        self._state_lock = threading.RLock()

    def _source_policy(self, source_name: str) -> SourceSpec | None:
        normalized = (source_name or "").strip()
        if not normalized:
            return None
        if self._catalog_source_policies is None:
            registry_path = Path(__file__).resolve().parents[2] / "datasets" / "batch" / "source_registry.yaml"
            try:
                registry = load_source_registry(registry_path)
            except Exception:
                logger.debug("Failed to load dataset source registry for retrieval policy lookup", exc_info=True)
                self._catalog_source_policies = {}
            else:
                self._catalog_source_policies = {spec.name: spec for spec in registry.sources}
        return self._catalog_source_policies.get(normalized)

    def _catalog_date_window(
        self,
        *,
        source_name: str,
        need: DataNeed,
    ) -> tuple[str | None, str | None, SourceSpec | None]:
        policy = self._source_policy(source_name)
        if need.time_start or need.time_end or policy is None:
            return need.time_start, need.time_end, policy
        if policy.history_policy != "rolling_window" or policy.default_lookback_days is None:
            return None, None, policy
        date_end = datetime.now(UTC)
        date_start = date_end - timedelta(days=int(policy.default_lookback_days))
        return date_start.isoformat(), date_end.isoformat(), policy

    def resolve(self, request: DataResolveRequest) -> ResolveOutcome:
        started = time.perf_counter()
        warnings: list[str] = []
        candidates: list[MetricCandidate] = []
        fetch_plans: list[FetchPlan] = []
        phase_metrics: list[dict[str, object]] = []
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["retrieval_resolve"],
            attributes={
                "retrieval.mode": request.mode,
                "retrieval.need_count": len(request.data_needs),
            },
        ):
            fastlane_enabled = _flag("POLISYOS_RETRIEVAL_FASTLANE_ENABLED", default=True)
            explore_enabled = _flag("POLISYOS_RETRIEVAL_EXPLORE_ENABLED", default=True)

            unresolved: list[DataNeed] = list(request.data_needs)
            if request.mode in {"fastlane", "hybrid"} and fastlane_enabled:
                phase_start = time.perf_counter()
                fast = self._fastlane.resolve(request.data_needs)
                candidates.extend(fast.candidates)
                fetch_plans.extend(fast.fetch_plans)
                warnings.extend(fast.warnings)
                resolved_metrics = {plan.metric_id for plan in fast.fetch_plans}
                unresolved = [need for need in request.data_needs if need.metric not in resolved_metrics]
                phase_metrics.append(
                    {
                        "phase": "resolve_fast_lane",
                        "lane": "fastlane",
                        "duration_ms": int((time.perf_counter() - phase_start) * 1000),
                        "candidates_total": len(fast.candidates),
                        "candidates_selected": len(fast.fetch_plans),
                        "docs_fetched": 0,
                        "route_breakdown": self._route_breakdown(fast.candidates),
                    }
                )
            elif request.mode in {"fastlane", "hybrid"} and not fastlane_enabled:
                warnings.append("fastlane_disabled_by_feature_flag")

            if unresolved and self._dataset_catalog is not None:
                phase_start = time.perf_counter()
                catalog_plans, catalog_candidates = self._resolve_via_catalog(unresolved)
                fetch_plans.extend(catalog_plans)
                candidates.extend(catalog_candidates)
                resolved_metrics = {plan.metric_id for plan in fetch_plans}
                unresolved = [need for need in unresolved if need.metric not in resolved_metrics]
                phase_metrics.append(
                    {
                        "phase": "resolve_dataset_catalog",
                        "lane": "catalog",
                        "duration_ms": int((time.perf_counter() - phase_start) * 1000),
                        "candidates_total": len(catalog_candidates),
                        "candidates_selected": len(catalog_plans),
                        "docs_fetched": 0,
                        "route_breakdown": self._route_breakdown(catalog_candidates),
                    }
                )

            should_explore = (
                request.mode == "explorelane"
                or (
                    request.mode == "hybrid"
                    and request.allow_explore_fallback
                    and bool(unresolved)
                )
            )
            if should_explore:
                if not explore_enabled:
                    warnings.append("explorelane_disabled_by_feature_flag")
                else:
                    phase_start = time.perf_counter()
                    discover_outcome = self.discover(
                        data_needs=request.data_needs if request.mode == "explorelane" else unresolved
                    )
                    warnings.extend(discover_outcome.warnings)
                    self._update_local_index(discover_outcome.candidates)
                    explore_plans = self._build_plans_from_discovery(
                        candidates=discover_outcome.candidates,
                        existing_metric_ids={plan.metric_id for plan in fetch_plans},
                        data_needs=request.data_needs,
                    )
                    fetch_plans.extend(explore_plans)
                    candidates.extend(
                        [
                            MetricCandidate(
                                candidate_id=item.candidate_id,
                                metric_id=item.metric_id,
                                connector_id=item.connector_id,
                                dataset_id=item.dataset_id,
                                profile_id=item.profile_id,
                                source_lane="explorelane",
                                confidence=item.confidence,
                                rank=index + 1,
                                trust_score=0.5,
                                freshness_score=0.5,
                                coverage_estimate=item.coverage_estimate,
                                latency_estimate_ms=item.latency_estimate_ms,
                                filters_template={},
                                match_reason="explore_lane_discovery",
                                metadata=item.metadata,
                            )
                            for index, item in enumerate(discover_outcome.candidates)
                        ]
                    )
                    phase_metrics.append(
                        {
                            "phase": "discover_explore_lane",
                            "lane": "explorelane",
                            "duration_ms": int((time.perf_counter() - phase_start) * 1000),
                            "candidates_total": len(discover_outcome.candidates),
                            "candidates_selected": len(explore_plans),
                        "docs_fetched": discover_outcome.docs_fetched_total,
                            "route_breakdown": self._route_breakdown(discover_outcome.candidates),
                        }
                    )

            if not fetch_plans:
                warnings.append("no_fetch_plans_resolved")

            total_duration_ms = int((time.perf_counter() - started) * 1000)
            with self._state_lock:
                local_index_docs_total = len(self._local_index_docs)
                local_index_size_bytes = self._index_size_bytes
            telemetry = {
                "mode": request.mode,
                "lane_used": self._lane_used(fetch_plans),
                "metadata_docs_fetched": sum(
                    _coerce_int(item.get("docs_fetched", 0))
                    for item in phase_metrics
                    if isinstance(item, dict)
                ),
                "local_index_size_bytes": local_index_size_bytes,
                "local_index_docs_total": local_index_docs_total,
                "candidates_filtered": max(0, len(candidates) - len(fetch_plans)),
                "candidates_promoted": 0,
                "duration_ms": total_duration_ms,
                "phases": phase_metrics,
                "warnings": list(warnings),
                "resolution_routes": {
                    "candidates": self._route_breakdown(candidates),
                    "selected": self._route_breakdown(fetch_plans),
                },
            }
            if getattr(self._metrics, "record_fabric_query", None):
                self._metrics.record_fabric_query(
                    operation="resolve",
                    duration_seconds=max(total_duration_ms / 1000.0, 0.0),
                    row_count=len(fetch_plans),
                    status="success" if fetch_plans else "empty",
                )
            return ResolveOutcome(
                mode=request.mode,
                fetch_plans=fetch_plans,
                candidates=candidates,
                warnings=warnings,
                telemetry=telemetry,
            )

    def discover(
        self,
        *,
        data_needs: list[DataNeed],
        max_sources_per_query: int = 5,
        max_discovery_calls_per_source: int = 25,
        max_candidates_total: int = 50,
        time_budget_ms: int = 5_000,
        cost_budget_usd: float = 0.0,
    ) -> DiscoverOutcome:
        started = time.perf_counter()
        limits = ExploreLaneLimits(
            max_sources_per_query=max_sources_per_query,
            max_discovery_calls_per_source=max_discovery_calls_per_source,
            max_candidates_total=max_candidates_total,
            time_budget_ms=time_budget_ms,
            cost_budget_usd=cost_budget_usd,
        )
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["retrieval_discover"],
            attributes={"retrieval.need_count": len(data_needs)},
        ):
            result: ExploreLaneDiscoverResult = self._explore.discover(data_needs, limits=limits)
        if getattr(self._metrics, "record_fabric_query", None):
            self._metrics.record_fabric_query(
                operation="discover",
                duration_seconds=max(time.perf_counter() - started, 0.0),
                row_count=len(result.candidates),
                status="success",
            )
        return DiscoverOutcome(
            candidates=result.candidates,
            docs_fetched_total=result.docs_fetched_total,
            warnings=result.warnings,
        )

    def preview(self, plan: FetchPlan, *, allow_fallback: bool = True) -> ExecutePlanResult:
        return self._executor.preview(plan, allow_fallback=allow_fallback)

    def execute_fetch_plans(
        self,
        plans: list[FetchPlan],
        *,
        persist_payload: bool = False,
        allow_fallback: bool = True,
    ) -> ExecuteOutcome:
        started = time.perf_counter()
        data_metrics: list[Any] = []
        previews: list[ExecutePlanResult] = []
        promoted_count = 0
        fallback_triggered_count = 0
        with self._tracer.start_as_current_span(
            FABRIC_TRACE_NAMES["retrieval_execute"],
            attributes={"retrieval.plan_count": len(plans)},
        ):
            for plan in plans:
                outcome = self._executor.execute(
                    plan,
                    persist_payload=persist_payload,
                    allow_fallback=allow_fallback,
                )
                previews.append(outcome)
                if outcome.fallback_used:
                    fallback_triggered_count += 1
                if outcome.metric is not None:
                    data_metrics.append(outcome.metric)
                    promoted_count += self._emit_promotion_candidate(
                        plan=outcome.used_plan,
                        completeness=outcome.metric.completeness,
                    )

        with self._state_lock:
            index_docs_total = len(self._local_index_docs)
            index_size_bytes = self._index_size_bytes
        data_context = DataContext(
            metrics=data_metrics,
            metadata_docs_fetched=0,
            index_docs_total=index_docs_total,
            index_size_bytes=index_size_bytes,
        )
        execute_outcome = ExecuteOutcome(
            data_context=data_context,
            previews=previews,
            promoted_count=promoted_count,
            fallback_triggered_count=fallback_triggered_count,
        )
        if getattr(self._metrics, "record_fabric_query", None):
            self._metrics.record_fabric_query(
                operation="execute_fetch_plans",
                duration_seconds=max(time.perf_counter() - started, 0.0),
                row_count=sum(metric.row_count for metric in data_metrics),
                status="success" if previews else "empty",
            )
        return execute_outcome

    def search_catalog(
        self,
        *,
        metric_query: str,
        geography: str | None = None,
        limit: int = 25,
    ) -> list[MetricCandidate]:
        return cast(
            "list[MetricCandidate]",
            self._fastlane.search_catalog(
                metric_query=metric_query,
                geography=geography,
                limit=limit,
            ),
        )

    def get_index_stats(self) -> IndexStats:
        with self._state_lock:
            source_coverage: dict[str, int] = {}
            for row in self._local_index_docs.values():
                source = str(row.get("connector_id") or "unknown")
                source_coverage[source] = source_coverage.get(source, 0) + 1
            return IndexStats(
                index_docs_total=len(self._local_index_docs),
                index_size_bytes=self._index_size_bytes,
                indexed_sources=len(source_coverage),
                docs_added_last_run=self._docs_added_last_run,
                source_coverage=source_coverage,
                last_updated=self._last_updated,
            )

    def list_promotion_candidates(self) -> list[PromotionCandidate]:
        with self._state_lock:
            values = list(self._promotion_queue.values())
        values.sort(key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return values

    def approve_promotion(self, promotion_id: str, *, reason: str | None = None) -> bool:
        with self._state_lock:
            candidate = self._promotion_queue.get(promotion_id)
            if candidate is None:
                return False
            if candidate.status == "approved":
                return True
            updated = candidate.model_copy(
                update={
                    "status": "approved",
                    "metadata": {
                        **candidate.metadata,
                        "approval_reason": reason or "",
                            "approved_at": datetime.now(UTC).isoformat(),
                    },
                }
            )
            self._store_promotion_candidate_locked(updated)
        self._promote_binding(updated)
        return True

    def reject_promotion(self, promotion_id: str, *, reason: str | None = None) -> bool:
        with self._state_lock:
            candidate = self._promotion_queue.get(promotion_id)
            if candidate is None:
                return False
            self._store_promotion_candidate_locked(
                candidate.model_copy(
                    update={
                        "status": "rejected",
                        "metadata": {
                            **candidate.metadata,
                            "rejection_reason": reason or "",
                            "rejected_at": datetime.now(UTC).isoformat(),
                        },
                    }
                )
            )
        return True

    def _build_plans_from_discovery(
        self,
        *,
        candidates: list[DiscoveryCandidate],
        existing_metric_ids: set[str],
        data_needs: list[DataNeed],
    ) -> list[FetchPlan]:
        by_metric: dict[str, list[DiscoveryCandidate]] = {}
        for candidate in candidates:
            by_metric.setdefault(candidate.metric_id, []).append(candidate)
        need_map = {need.metric: need for need in data_needs}
        plans: list[FetchPlan] = []
        for metric_id, rows in by_metric.items():
            if metric_id in existing_metric_ids:
                continue
            rows.sort(key=lambda item: (-item.confidence, item.connector_id, item.dataset_id))
            primary = rows[0]
            need = need_map.get(metric_id, DataNeed(metric=metric_id))
            fallbacks = [
                FetchPlanFallback(
                    connector_id=item.connector_id,
                    dataset_id=item.dataset_id,
                    metric_id=item.metric_id,
                    profile_id=item.profile_id,
                    filters={},
                    metadata={
                        "resolution_route": item.metadata.get("resolution_route", item.source_lane),
                    "confidence": item.confidence,
                    },
                )
                for item in rows[1:3]
            ]
            plans.append(
                FetchPlan(
                    plan_id=_stable_id("plan", metric_id, primary.connector_id, primary.dataset_id),
                    metric_id=metric_id,
                    connector_id=primary.connector_id,
                    dataset_id=primary.dataset_id,
                    profile_id=primary.profile_id,
                    filters={},
                    date_start=need.time_start,
                    date_end=need.time_end,
                    granularity=need.granularity,
                    quality_min=need.quality_min,
                    source_lane="explorelane",
                    fallbacks=fallbacks,
                    metadata={
                        "discovered": True,
                        "confidence": primary.confidence,
                        "resolution_route": primary.metadata.get("resolution_route", "explorelane"),
                    },
                )
            )
        return plans

    def _update_local_index(self, candidates: list[DiscoveryCandidate]) -> None:
        added = 0
        now_iso = datetime.now(UTC).isoformat()
        with self._state_lock:
            for candidate in candidates:
                key = f"{candidate.connector_id}:{candidate.dataset_id}"
                if key not in self._local_index_docs:
                    added += 1
                else:
                    self._local_index_docs.pop(key, None)
                self._local_index_docs[key] = {
                    "connector_id": candidate.connector_id,
                    "dataset_id": candidate.dataset_id,
                    "metric_id": candidate.metric_id,
                    "confidence": candidate.confidence,
                    "profile_id": candidate.profile_id,
                    "updated_at": now_iso,
                }
            self._trim_ordered_dict_locked(self._local_index_docs, self._max_local_index_docs)
            self._docs_added_last_run = added
            self._recompute_index_size_locked()
            self._last_updated = datetime.now(UTC)

    def _emit_promotion_candidate(self, *, plan: FetchPlan, completeness: float) -> int:
        if not _flag("POLISYOS_RETRIEVAL_PROMOTION_ENABLED", default=True):
            return 0
        if completeness < plan.quality_min:
            return 0
        if plan.source_lane != "explorelane":
            return 0
        promotion_id = _stable_id("promo", plan.metric_id, plan.connector_id, plan.dataset_id)
        with self._state_lock:
            if promotion_id in self._promotion_queue:
                return 0
            candidate = PromotionCandidate(
                promotion_id=promotion_id,
                metric_id=plan.metric_id,
                connector_id=plan.connector_id,
                dataset_id=plan.dataset_id,
                profile_id=plan.profile_id,
                source_lane="explorelane",
                confidence=(
                    _coerce_float(plan.metadata.get("confidence", 0.8), default=0.8)
                    if isinstance(plan.metadata, dict)
                    else 0.8
                ),
                signals=[
                    "resolved_successfully",
                    "fetch_successfully",
                    "quality_pass",
                ],
                status="pending",
                created_at=datetime.now(UTC),
                metadata={
                    "quality_min": plan.quality_min,
                    "completeness": completeness,
                },
            )
            self._store_promotion_candidate_locked(candidate)
        return 1

    def _promote_binding(self, candidate: PromotionCandidate) -> None:
        binding = SourceBinding(
            metric_id=candidate.metric_id,
            connector_id=candidate.connector_id,
            dataset_id=candidate.dataset_id,
            profile_id=candidate.profile_id,
            geography_patterns=["*"],
            granularity=[],
            priority=25,
            trust=max(0.5, min(1.0, candidate.confidence)),
            filters_template={},
            tags=["promoted"],
            aliases=[],
            metadata={"promotion_id": candidate.promotion_id},
        )
        self._fastlane.binding_registry.upsert(binding)
        self._fastlane.refresh_search_index()
        if _flag("POLISYOS_RETRIEVAL_PROMOTION_PERSIST", default=False):
            self._fastlane.binding_registry.persist()

    def _recompute_index_size_locked(self) -> None:
        self._index_size_bytes = len(
            json.dumps(dict(self._local_index_docs), ensure_ascii=True, sort_keys=True).encode("utf-8")
        )

    @staticmethod
    def _trim_ordered_dict_locked(mapping: OrderedDict[str, Any], max_items: int) -> None:
        while len(mapping) > max_items:
            mapping.popitem(last=False)

    def _store_promotion_candidate_locked(self, candidate: PromotionCandidate) -> None:
        self._promotion_queue.pop(candidate.promotion_id, None)
        self._promotion_queue[candidate.promotion_id] = candidate
        self._trim_ordered_dict_locked(self._promotion_queue, self._max_promotion_candidates)

    def _resolve_via_catalog(
        self,
        unresolved: list[DataNeed],
    ) -> tuple[list[FetchPlan], list[MetricCandidate]]:
        """Try to resolve data needs via DatasetCatalogGraph."""
        plans: list[FetchPlan] = []
        candidates: list[MetricCandidate] = []
        catalog = self._dataset_catalog
        if catalog is None:
            return plans, candidates

        for need in unresolved:
            resolved_rows: list[dict[str, object]] = []

            binding_fn = getattr(catalog, "resolve_metric_bindings", None)
            if binding_fn is not None:
                try:
                    bindings = binding_fn(need.metric, top_k=3)
                except Exception:
                    logger.debug("Catalog binding lookup failed for metric %s", need.metric, exc_info=True)
                    bindings = []
                for binding in bindings:
                    connector_id = str(getattr(binding, "connector_id", "") or "").strip()
                    request_dataset_id = str(getattr(binding, "request_dataset_id", "") or "").strip()
                    if not connector_id or not request_dataset_id:
                        continue
                    resolved_rows.append(
                        {
                            "catalog_dataset_id": str(getattr(binding, "catalog_dataset_id", "") or ""),
                            "distribution_id": str(getattr(binding, "distribution_id", "") or ""),
                            "connector_id": connector_id,
                            "profile_id": _optional_text(getattr(binding, "profile_id", None)),
                            "request_dataset_id": request_dataset_id,
                            "default_filters": _coerce_filter_map(
                                getattr(binding, "default_filters", {}) or {}
                            ),
                            "confidence": _coerce_float(
                                getattr(binding, "confidence", 0.0) or 0.0
                            ),
                            "catalog_title": str(getattr(binding, "title", "") or ""),
                            "execution_tier": str(getattr(binding, "execution_tier", "catalog") or "catalog"),
                            "source": str(getattr(binding, "source", "") or ""),
                        }
                    )

            if not resolved_rows:
                find_fn = getattr(catalog, "find_by_polisyos_metric", None)
                resolve_target_fn = getattr(catalog, "resolve_fetch_target", None)
                if find_fn is None or resolve_target_fn is None:
                    continue
                try:
                    results = find_fn(need.metric, top_k=3)
                except Exception:
                    logger.debug("Catalog lookup failed for metric %s", need.metric, exc_info=True)
                    continue
                for result in results:
                    try:
                        target = resolve_target_fn(result.id)
                    except Exception:
                        logger.debug("Catalog fetch target resolution failed for %s", result.id, exc_info=True)
                        continue
                    if target is None or not target.connector_id or not target.request_dataset_id or not target.parser_supported:
                        continue
                    resolved_rows.append(
                        {
                            "catalog_dataset_id": target.catalog_dataset_id,
                            "distribution_id": target.distribution_id,
                            "connector_id": target.connector_id,
                            "profile_id": _optional_text(target.profile_id),
                            "request_dataset_id": target.request_dataset_id,
                            "default_filters": _coerce_filter_map(target.default_filters),
                            "confidence": max(0.05, _coerce_float(result.similarity) * 0.8),
                            "catalog_title": result.title,
                            "execution_tier": getattr(result, "execution_tier", "catalog"),
                            "source": getattr(result, "source", ""),
                        }
                    )

            if not resolved_rows:
                continue

            deduped_rows: list[dict[str, object]] = []
            seen: set[tuple[str, str]] = set()
            for row in resolved_rows:
                dedupe_key = (str(row["connector_id"]), str(row["request_dataset_id"]))
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                deduped_rows.append(row)

            fallbacks: list[FetchPlanFallback] = []
            for rank, row in enumerate(deduped_rows, start=1):
                candidate = MetricCandidate(
                    candidate_id=_stable_id(
                        "cat",
                        need.metric,
                        str(row["connector_id"]),
                        str(row["request_dataset_id"]),
                    ),
                    metric_id=need.metric,
                    connector_id=str(row["connector_id"]),
                    dataset_id=str(row["request_dataset_id"]),
                    profile_id=_optional_text(row["profile_id"]),
                    source_lane="catalog",
                    confidence=max(0.05, min(1.0, _coerce_float(row["confidence"]))),
                    rank=rank,
                    trust_score=0.7,
                    freshness_score=0.6,
                    coverage_estimate=0.75,
                    latency_estimate_ms=1500,
                    filters_template=_coerce_filter_map(row["default_filters"]),
                    match_reason="dataset_catalog_metric_binding",
                    metadata={
                        "catalog_dataset_id": row["catalog_dataset_id"],
                        "distribution_id": row["distribution_id"],
                        "catalog_title": row["catalog_title"],
                        "execution_tier": row["execution_tier"],
                        "resolution_route": "catalog",
                    },
                )
                candidates.append(candidate)
                if rank > 1:
                    fallbacks.append(
                        FetchPlanFallback(
                            connector_id=str(row["connector_id"]),
                            dataset_id=str(row["request_dataset_id"]),
                            metric_id=need.metric,
                            profile_id=_optional_text(row["profile_id"]),
                            filters=_coerce_filter_map(row["default_filters"]),
                            metadata={
                                "resolution_route": "catalog",
                                "catalog_dataset_id": row["catalog_dataset_id"],
                                "distribution_id": row["distribution_id"],
                            },
                        )
                    )

            primary = deduped_rows[0]
            date_start, date_end, policy = self._catalog_date_window(
                source_name=str(primary.get("source") or ""),
                need=need,
            )
            plans.append(
                FetchPlan(
                    plan_id=_stable_id(
                        "plan",
                        need.metric,
                        str(primary["connector_id"]),
                        str(primary["request_dataset_id"]),
                    ),
                    metric_id=need.metric,
                    connector_id=str(primary["connector_id"]),
                    dataset_id=str(primary["request_dataset_id"]),
                    profile_id=_optional_text(primary["profile_id"]),
                    filters=_coerce_filter_map(primary["default_filters"]),
                    date_start=date_start,
                    date_end=date_end,
                    granularity=need.granularity,
                    quality_min=need.quality_min,
                    source_lane="catalog",
                    fallbacks=fallbacks[:2],
                    metadata={
                        "catalog_discovered": True,
                        "catalog_dataset_id": primary["catalog_dataset_id"],
                        "distribution_id": primary["distribution_id"],
                        "catalog_title": primary["catalog_title"],
                        "execution_tier": primary["execution_tier"],
                        "source": primary.get("source", ""),
                        "history_policy": policy.history_policy if policy else "",
                        "default_lookback_days": policy.default_lookback_days if policy else None,
                        "manual_backfill_allowed": bool(policy.allow_manual_backfill) if policy else False,
                        "resolution_route": "catalog",
                    },
                )
            )
        return plans, candidates

    @staticmethod
    def _lane_used(plans: list[FetchPlan]) -> str:
        if not plans:
            return "none"
        lanes = {plan.source_lane for plan in plans}
        if len(lanes) == 1:
            return str(next(iter(lanes)))
        return "hybrid"

    @staticmethod
    def _route_breakdown(items: Sequence[object]) -> dict[str, int]:
        breakdown: dict[str, int] = {}
        for item in items:
            metadata = getattr(item, "metadata", None)
            route = None
            if isinstance(metadata, dict):
                route = metadata.get("resolution_route")
            if not route:
                route = getattr(item, "source_lane", None) or "unknown"
            route_name = str(route)
            breakdown[route_name] = breakdown.get(route_name, 0) + 1
        return dict(sorted(breakdown.items()))

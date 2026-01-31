"""
Federation planner for multi-source composition.

Generates optimized execution plans by querying the connector registry,
ranking sources, and determining the optimal fetch strategy.
"""
from __future__ import annotations

from datetime import datetime

from polisyos.common.logger import get_logger
from polisyos.fabric.connectors.base import FetchRequest
from polisyos.fabric.connectors.registry import ConnectorPreferences, ConnectorRegistry
from polisyos.fabric.connectors.quality.report import DataQualityReport
from polisyos.fabric.connectors.contracts.registry import SchemaRegistry

from polisyos.fabric.connectors.federation.ranker import SourceRanker
from polisyos.fabric.connectors.federation.types import (
    CompositionRequest,
    CompositionStrategy,
    CoverageProfile,
    ExecutionPlan,
    PlannedSource,
    PlanningError,
    RankedSource,
)

logger = get_logger(__name__)


class FederationPlanner:
    """
    Generates execution plans for multi-source composition.

    Responsibilities:
    - Query ConnectorRegistry for candidates
    - Rank candidates by relevance
    - Generate optimized fetch plan
    - Include fallback sources for resilience
    """

    def __init__(
        self,
        registry: ConnectorRegistry,
        ranker: SourceRanker,
        *,
        schema_registry: SchemaRegistry | None = None,
    ) -> None:
        self.registry = registry
        self.ranker = ranker
        self.schema_registry = schema_registry

    def plan(
        self,
        request: CompositionRequest,
        quality_reports: dict[str, DataQualityReport] | None = None,
    ) -> ExecutionPlan:
        """
        Generate execution plan for composition request.

        Steps:
        1. Query registry for candidate connectors
        2. Rank candidates by relevance
        3. Generate fetch plan (which sources, in what order)
        4. Include fallback sources
        5. Add optimization hints

        Args:
            request: Composition request
            quality_reports: Optional quality reports for ranking

        Returns:
            ExecutionPlan with primary and fallback sources

        Raises:
            PlanningError: If plan cannot be generated
        """
        logger.info(
            "Planning federation",
            dataset=request.dataset_pattern,
            strategy=request.strategy.value,
        )

        preferences = ConnectorPreferences(min_trust_level=request.min_trust_level)
        candidates = self.registry.find_connectors_for_dataset(
            dataset_pattern=request.dataset_pattern,
            preferences=preferences,
        )

        if not candidates:
            raise PlanningError(
                f"No connectors found for dataset '{request.dataset_pattern}' "
                f"with min trust level {request.min_trust_level.name}"
            )

        ranked_sources = self.ranker.rank_sources(
            candidates=[meta for meta, _ in candidates],
            request=request,
            quality_reports=quality_reports,
        )

        # Enrich ranked sources with coverage profile
        for ranked in ranked_sources:
            ranked.coverage = self._build_coverage_profile(
                ranked.connector_id, request.dataset_pattern
            )

        primary_sources = self._select_primary_sources(ranked_sources, request)
        fallback_sources = self._select_fallback_sources(
            ranked_sources=ranked_sources,
            primary_sources=primary_sources,
            max_fallbacks=request.max_fallback_sources,
            request=request,
        )

        can_parallelize = self._can_parallelize(primary_sources, request)
        estimated_cost = self._estimate_cost(primary_sources)

        plan = ExecutionPlan(
            request=request,
            primary_sources=primary_sources,
            fallback_sources=fallback_sources,
            can_parallelize=can_parallelize,
            estimated_cost_ms=estimated_cost,
            planning_timestamp=datetime.utcnow(),
        )

        logger.info(
            "Plan generated",
            primary_sources=len(plan.primary_sources),
            fallback_sources=len(plan.fallback_sources),
            can_parallelize=can_parallelize,
        )

        return plan

    def _build_coverage_profile(
        self, connector_id: str, dataset_pattern: str
    ) -> CoverageProfile | None:
        try:
            entry = self.registry.get_entry(connector_id)
        except Exception:
            return None

        descriptor = None
        for desc in entry.dataset_descriptors:
            if desc.dataset_id == dataset_pattern:
                descriptor = desc
                break
        if descriptor is None:
            for desc in entry.dataset_descriptors:
                if dataset_pattern in desc.dataset_id or dataset_pattern in desc.name:
                    descriptor = desc
                    break

        if descriptor is None:
            return None

        columns: set[str] = set()
        key_columns: tuple[str, ...] = ()
        time_dimension = None

        if descriptor.schema_id and self.schema_registry is not None:
            try:
                schema = self.schema_registry.get(descriptor.schema_id)
                columns = set(schema.field_names())
                key_columns = tuple(schema.effective_grain_dims())
                time_dimension = schema.time_dimension
            except Exception:
                pass

        if not columns and descriptor.metadata:
            metadata_columns = descriptor.metadata.get("columns")
            if isinstance(metadata_columns, (list, tuple, set)):
                columns = set(str(c) for c in metadata_columns)

        if not key_columns and descriptor.metadata:
            metadata_keys = descriptor.metadata.get("key_columns")
            if isinstance(metadata_keys, (list, tuple, set)):
                key_columns = tuple(str(c) for c in metadata_keys)

        return CoverageProfile(
            dataset_id=descriptor.dataset_id,
            time_range=(descriptor.date_start, descriptor.date_end),
            columns=frozenset(columns),
            key_columns=key_columns,
            time_dimension=time_dimension,
            row_count=descriptor.estimated_rows,
        )

    def _select_primary_sources(
        self,
        ranked_sources: list[RankedSource],
        request: CompositionRequest,
    ) -> list[PlannedSource]:
        if request.strategy == CompositionStrategy.UNION:
            selected = self._select_for_union(ranked_sources, request)
        elif request.strategy == CompositionStrategy.JOIN:
            selected = self._select_for_join(ranked_sources, request)
        elif request.strategy == CompositionStrategy.OVERLAY:
            selected = self._select_for_overlay(ranked_sources, request)
        elif request.strategy == CompositionStrategy.CONSENSUS:
            selected = self._select_for_consensus(ranked_sources, request)
        else:
            raise PlanningError(f"Unknown strategy: {request.strategy}")

        return [self._planned_source(source, request) for source in selected]

    def _select_for_union(
        self,
        ranked_sources: list[RankedSource],
        request: CompositionRequest,
    ) -> list[RankedSource]:
        max_sources = request.max_primary_sources or 3
        selected: list[RankedSource] = []
        covered_start = None
        covered_end = None

        for source in ranked_sources:
            coverage = source.coverage
            if coverage is None or not coverage.has_time_range():
                if len(selected) < max_sources:
                    selected.append(source)
                continue

            start, end = coverage.time_range
            expands = False
            if covered_start is None or covered_end is None:
                expands = True
            else:
                if start and covered_start and start < covered_start:
                    expands = True
                if end and covered_end and end > covered_end:
                    expands = True
                if start and covered_end and start > covered_end:
                    expands = True
                if end and covered_start and end < covered_start:
                    expands = True

            if expands and len(selected) < max_sources:
                selected.append(source)
                if covered_start is None or (start and start < covered_start):
                    covered_start = start
                if covered_end is None or (end and end > covered_end):
                    covered_end = end

            if len(selected) >= max_sources:
                break

        if not selected:
            selected = ranked_sources[:max_sources]

        return selected

    def _select_for_join(
        self,
        ranked_sources: list[RankedSource],
        request: CompositionRequest,
    ) -> list[RankedSource]:
        max_sources = request.max_primary_sources or 3
        selected: list[RankedSource] = []
        covered_columns: set[str] = set()

        for source in ranked_sources:
            coverage = source.coverage
            if coverage is None or not coverage.columns:
                if len(selected) < max_sources:
                    selected.append(source)
                continue

            new_cols = set(coverage.columns) - covered_columns
            if new_cols or len(selected) < max_sources:
                selected.append(source)
                covered_columns.update(coverage.columns)

            if len(selected) >= max_sources:
                break

        if not selected:
            selected = ranked_sources[:max_sources]

        return selected

    def _select_for_overlay(
        self,
        ranked_sources: list[RankedSource],
        request: CompositionRequest,
    ) -> list[RankedSource]:
        max_sources = request.max_primary_sources or 4
        ordered = ranked_sources
        if request.primary_source:
            primary = next(
                (s for s in ranked_sources if s.connector_id == request.primary_source),
                None,
            )
            if not primary:
                raise PlanningError(
                    f"Specified primary source '{request.primary_source}' not found"
                )
            ordered = [primary] + [s for s in ranked_sources if s != primary]

        return ordered[:max_sources]

    def _select_for_consensus(
        self,
        ranked_sources: list[RankedSource],
        request: CompositionRequest,
    ) -> list[RankedSource]:
        min_sources = 3
        max_sources = request.max_primary_sources or 5
        selected = ranked_sources[: max(min_sources, max_sources)]

        if len(selected) < min_sources:
            logger.warning(
                "CONSENSUS strategy works best with 3+ sources",
                found=len(selected),
            )

        return selected

    def _select_fallback_sources(
        self,
        ranked_sources: list[RankedSource],
        primary_sources: list[PlannedSource],
        max_fallbacks: int,
        request: CompositionRequest,
    ) -> list[PlannedSource]:
        primary_ids = {s.connector_id for s in primary_sources}
        fallback_candidates = [
            s for s in ranked_sources if s.connector_id not in primary_ids
        ]

        selected = fallback_candidates[:max_fallbacks]
        return [self._planned_source(source, request) for source in selected]

    def _planned_source(
        self,
        ranked: RankedSource,
        request: CompositionRequest | None,
    ) -> PlannedSource:
        dataset_id = request.dataset_pattern if request else "fallback"
        fetch_request = FetchRequest(dataset_id=dataset_id)

        return PlannedSource(
            connector_id=ranked.connector_id,
            metadata=ranked.metadata,
            fetch_request=fetch_request,
            relevance_score=ranked.relevance_score,
            score_components=ranked.score_components,
            coverage=ranked.coverage,
        )

    def _can_parallelize(
        self,
        sources: list[PlannedSource],
        request: CompositionRequest,
    ) -> bool:
        return True

    def _estimate_cost(self, sources: list[PlannedSource]) -> float:
        total_ms = 0.0
        for source in sources:
            if source.expected_latency_ms:
                total_ms += source.expected_latency_ms
            else:
                total_ms += 500.0
        total_ms += 100.0
        return total_ms

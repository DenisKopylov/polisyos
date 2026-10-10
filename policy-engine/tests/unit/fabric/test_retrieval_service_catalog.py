from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core.contracts.control import (
    DataNeed,
    DataResolveRequest,
    DiscoveryCandidate,
    FetchPlan,
    FetchPlanFallback,
    MetricCandidate,
)
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.domains.catalog.knowledge.search import DatasetCatalogGraph
from polisyos.data_forge.domains.catalog.knowledge.types import (
    DatasetCoverage,
    DatasetRecord,
    DatasetSearchResult,
    DistributionRecord,
    MetricBindingMatch,
    ResolvedFetchTarget,
)
from polisyos.fabric.catalog.resolver_fast_lane import FastLaneResolveResult
from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest, FetchResult
from polisyos.fabric.retrieval.executor import FetchExecutor
from polisyos.fabric.retrieval.explore_lane import (
    ExploreLaneDiscoverResult,
    ExploreLaneDiscovery,
)
from polisyos.fabric.retrieval.providers import RetrievalProviders
from polisyos.fabric.retrieval.service import RetrievalService
from polisyos.ir.connectors import DataVersion, QualityTier, VersionStrategy


class _BindingCatalog:
    def resolve_metric_bindings(self, metric_name: str, *, top_k: int = 20):
        if metric_name != "gdp":
            return []
        return [
            MetricBindingMatch(
                metric_id="gdp",
                catalog_dataset_id="catalog-gdp",
                distribution_id="dist-gdp-1",
                connector_id="worldbank.wdi",
                profile_id="worldbank_wdi",
                request_dataset_id="NY.GDP.MKTP.CD",
                confidence=0.92,
                execution_tier="fetchable",
                source="worldbank",
                title="GDP per capita",
            )
        ]


class _ScopedBindingCatalog:
    def __init__(
        self,
        *,
        countries: list[str],
        time_start: str | None,
        time_end: str | None,
        regions: list[str] | None = None,
    ) -> None:
        self._coverage = DatasetCoverage(
            countries=countries,
            regions=regions or [],
            time_start=time_start,
            time_end=time_end,
        )

    def resolve_metric_bindings(self, metric_name: str, *, top_k: int | None = 20):
        if metric_name != "scope_metric":
            return []
        return [
            MetricBindingMatch(
                metric_id="scope_metric",
                catalog_dataset_id="catalog-scope",
                distribution_id="dist-scope",
                connector_id="worldbank.wdi",
                profile_id="worldbank_wdi",
                request_dataset_id="scope_dataset",
                confidence=0.92,
                execution_tier="fetchable",
                source="worldbank",
                title="Scoped fixture",
            )
        ]

    def reconciled_metric_binding_population(self, metric_name: str):
        return self.resolve_metric_bindings(metric_name, top_k=None)

    def get_dataset(self, dataset_id: str):
        if dataset_id != "catalog-scope":
            return None
        return DatasetSearchResult(
            id=dataset_id,
            title="Scoped fixture",
            coverage=self._coverage,
        )


class _RequestIdCollisionCatalog(_ScopedBindingCatalog):
    def get_dataset(self, dataset_id: str):
        if dataset_id in {"scope_dataset", "forged-catalog"}:
            return DatasetSearchResult(
                id=dataset_id,
                title="Identifier collision row",
                coverage=DatasetCoverage(
                    countries=["DEU"],
                    time_start="2020",
                    time_end="2030",
                ),
            )
        return super().get_dataset(dataset_id)


class _WrongConnectorScopeCatalog(_ScopedBindingCatalog):
    def resolve_metric_bindings(self, metric_name: str, *, top_k: int | None = 20):
        bindings = super().resolve_metric_bindings(metric_name, top_k=top_k)
        return [
            binding.model_copy(update={"connector_id": "other.connector"}) for binding in bindings
        ]

    def reconciled_metric_binding_population(self, metric_name: str):
        return self.resolve_metric_bindings(metric_name, top_k=None)


class _SelectedPlanFastLane:
    def __init__(self, plan: FetchPlan) -> None:
        self._plan = plan

    def resolve(self, data_needs: list[DataNeed]) -> FastLaneResolveResult:
        return FastLaneResolveResult(
            fetch_plans=(self._plan,),
            candidates=(),
            warnings=(),
        )


def _selected_scope_plan(*, metadata: dict[str, object] | None = None) -> FetchPlan:
    return FetchPlan(
        plan_id="selected-scope-plan",
        metric_id="scope_metric",
        connector_id="worldbank.wdi",
        dataset_id="scope_dataset",
        profile_id="worldbank_wdi",
        source_lane="fastlane",
        metadata=metadata or {},
    )


def _actual_scope_catalog(tmp_path: Path) -> DatasetCatalogGraph:
    db_path = tmp_path / "scope-catalog.duckdb"
    index_dir = tmp_path / "scope-index"
    index_dir.mkdir()
    build_graph(
        records=iter(
            [
                DatasetRecord(
                    id="catalog-scope",
                    title="Scoped GDP",
                    source="worldbank",
                    source_dataset_id="scope_dataset",
                    polisyos_metrics=["scope_metric"],
                    execution_tier="fetchable",
                    distributions=[
                        DistributionRecord(
                            id="dist-scope",
                            connector_type="worldbank.wdi",
                            source_locator="scope_dataset",
                            profile_id="worldbank_wdi",
                            machine_readable=True,
                            parser_supported=True,
                        )
                    ],
                    preferred_distribution_id="dist-scope",
                    coverage=DatasetCoverage(
                        countries=["DEU"],
                        time_start="2020",
                        time_end="2030",
                    ),
                )
            ]
        ),
        db_path=db_path,
    )
    return DatasetCatalogGraph(
        db_path,
        index_dir,
        overlay_path=tmp_path / "missing-overlay.duckdb",
    )


class _OneCandidateExplore:
    def discover(self, data_needs, *, limits=None):
        del data_needs, limits
        return ExploreLaneDiscoverResult(
            candidates=[
                DiscoveryCandidate(
                    candidate_id="explore-scope",
                    metric_id="scope_metric",
                    connector_id="worldbank.wdi",
                    dataset_id="scope_dataset",
                    profile_id="worldbank_wdi",
                    confidence=0.9,
                )
            ],
            docs_fetched_total=1,
            warnings=[],
        )


def _resolve_scoped_need(tmp_path, catalog, need: DataNeed):
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(curated_dir=curated_dir, dataset_catalog=catalog)
    return service.resolve(
        DataResolveRequest(
            data_needs=[need],
            mode="fastlane",
            allow_explore_fallback=False,
        ),
        run_profile="prod_full",
    )


class _RollingWindowBindingCatalog:
    def resolve_metric_bindings(self, metric_name: str, *, top_k: int = 20):
        if metric_name != "health_outcomes":
            return []
        return [
            MetricBindingMatch(
                metric_id="health_outcomes",
                catalog_dataset_id="catalog-openaq",
                distribution_id="dist-openaq-1",
                connector_id="rest.json",
                profile_id="openaq_v2",
                request_dataset_id="openaq_air_quality_city_day",
                confidence=0.88,
                execution_tier="fetchable",
                source="openaq_v2",
                title="OpenAQ city-day air quality aggregates",
            )
        ]


class _NoneProfileBindingCatalog:
    def resolve_metric_bindings(self, metric_name: str, *, top_k: int = 20):
        if metric_name != "gdp":
            return []

        class _Binding:
            metric_id = "gdp"
            catalog_dataset_id = "catalog-gdp"
            distribution_id = "dist-gdp-1"
            connector_id = "worldbank.wdi"
            profile_id = None
            request_dataset_id = "NY.GDP.MKTP.CD"
            confidence = 0.92
            execution_tier = "fetchable"
            source = "worldbank"
            title = "GDP per capita"

        return [_Binding()]


class _CatalogOnlyBindingCatalog:
    def resolve_metric_bindings(self, metric_name: str, *, top_k: int = 20):
        if metric_name != "gdp":
            return []
        return [
            MetricBindingMatch(
                metric_id="gdp",
                catalog_dataset_id="catalog-gdp",
                distribution_id="dist-gdp-catalog-only",
                connector_id="worldbank.wdi",
                profile_id="worldbank_wdi",
                request_dataset_id="NY.GDP.MKTP.CD",
                confidence=0.99,
                execution_tier="catalog",
                title="GDP catalog metadata only",
            )
        ]


class _TargetCatalog:
    def find_by_polisyos_metric(self, metric_name: str, *, top_k: int = 20):
        if metric_name != "gdp":
            return []
        return [
            DatasetSearchResult(
                id="catalog-gdp",
                title="GDP per capita",
                polisyos_metrics=["gdp"],
                similarity=1.0,
            )
        ]

    def resolve_fetch_target(self, dataset_id: str):
        if dataset_id != "catalog-gdp":
            return None
        return ResolvedFetchTarget(
            catalog_dataset_id="catalog-gdp",
            connector_id="worldbank.wdi",
            profile_id="worldbank_wdi",
            request_dataset_id="NY.GDP.MKTP.CD",
            distribution_id="dist-gdp-1",
            parser_supported=False,
        )


def test_catalog_resolution_uses_request_dataset_id(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(curated_dir=curated_dir, dataset_catalog=_BindingCatalog())
    plans, candidates = service._resolve_via_catalog(
        [DataNeed(metric="gdp")], run_profile="prod_full"
    )
    assert len(plans) == 1
    assert plans[0].dataset_id == "NY.GDP.MKTP.CD"
    assert plans[0].connector_id == "worldbank.wdi"
    assert plans[0].metadata["catalog_dataset_id"] == "catalog-gdp"
    assert candidates[0].dataset_id == "NY.GDP.MKTP.CD"


def test_catalog_resolution_skips_unfetchable_targets(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(curated_dir=curated_dir, dataset_catalog=_TargetCatalog())
    plans, candidates = service._resolve_via_catalog(
        [DataNeed(metric="gdp")], run_profile="prod_full"
    )
    assert plans == []
    assert candidates == []


def test_catalog_resolution_rejects_catalog_only_metric_bindings(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(
        curated_dir=curated_dir,
        dataset_catalog=_CatalogOnlyBindingCatalog(),
    )

    plans, candidates = service._resolve_via_catalog(
        [DataNeed(metric="gdp")], run_profile="prod_full"
    )

    assert plans == []
    assert candidates == []


def test_catalog_resolution_applies_rolling_window_defaults_for_rest_sources(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(
        curated_dir=curated_dir, dataset_catalog=_RollingWindowBindingCatalog()
    )
    plans, candidates = service._resolve_via_catalog(
        [DataNeed(metric="health_outcomes")], run_profile="prod_full"
    )

    assert len(plans) == 1
    assert len(candidates) == 1
    assert plans[0].connector_id == "rest.json"
    assert plans[0].date_start is not None
    assert plans[0].date_end is not None
    assert plans[0].metadata["history_policy"] == "rolling_window"
    assert plans[0].metadata["default_lookback_days"] == 90


def test_catalog_resolution_preserves_none_profile_id(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(
        curated_dir=curated_dir, dataset_catalog=_NoneProfileBindingCatalog()
    )

    plans, candidates = service._resolve_via_catalog(
        [DataNeed(metric="gdp")], run_profile="prod_full"
    )

    assert len(plans) == 1
    assert len(candidates) == 1
    assert plans[0].profile_id is None
    assert candidates[0].profile_id is None


def test_catalog_resolution_keeps_country_and_year_compatible_candidate(tmp_path) -> None:
    catalog = _ScopedBindingCatalog(
        countries=["DEU"],
        time_start="2020",
        time_end="2030",
    )
    outcome = _resolve_scoped_need(
        tmp_path,
        catalog,
        DataNeed(
            metric="scope_metric",
            geography="DEU",
            time_start="2025",
            time_end="2025",
        ),
    )

    assert len(outcome.fetch_plans) == 1
    assert outcome.fetch_plans[0].date_start == "2025"
    assert outcome.fetch_plans[0].date_end == "2025"
    assert not any(item.startswith("catalog_scope_") for item in outcome.warnings)


def test_catalog_resolution_excludes_known_country_mismatch(tmp_path) -> None:
    catalog = _ScopedBindingCatalog(
        countries=["UKR"],
        time_start="2020",
        time_end="2030",
    )
    outcome = _resolve_scoped_need(
        tmp_path,
        catalog,
        DataNeed(
            metric="scope_metric",
            geography="DEU",
            time_start="2025",
            time_end="2025",
        ),
    )

    assert outcome.fetch_plans == []
    assert outcome.candidates == []
    assert "catalog_scope_incompatible:scope_metric:catalog-scope" in outcome.warnings


def test_catalog_resolution_excludes_known_year_mismatch(tmp_path) -> None:
    catalog = _ScopedBindingCatalog(
        countries=["DEU"],
        time_start="2020",
        time_end="2024",
    )
    outcome = _resolve_scoped_need(
        tmp_path,
        catalog,
        DataNeed(
            metric="scope_metric",
            geography="DEU",
            time_start="2025",
            time_end="2025",
        ),
    )

    assert outcome.fetch_plans == []
    assert outcome.candidates == []
    assert "catalog_scope_incompatible:scope_metric:catalog-scope" in outcome.warnings


def test_catalog_resolution_keeps_unknown_coverage_declared_unknown(tmp_path) -> None:
    catalog = _ScopedBindingCatalog(
        countries=[],
        time_start=None,
        time_end=None,
    )
    outcome = _resolve_scoped_need(
        tmp_path,
        catalog,
        DataNeed(
            metric="scope_metric",
            geography="DEU",
            time_start="2025",
            time_end="2025",
        ),
    )

    assert len(outcome.fetch_plans) == 1
    assert any(
        item.startswith("catalog_scope_unverified:scope_metric:") for item in outcome.warnings
    )


def test_catalog_resolution_does_not_default_malformed_time_scope(tmp_path) -> None:
    catalog = _ScopedBindingCatalog(
        countries=["DEU"],
        time_start="2020",
        time_end="2030",
    )
    outcome = _resolve_scoped_need(
        tmp_path,
        catalog,
        DataNeed(
            metric="scope_metric",
            geography="DEU",
            time_start="not-a-date",
            time_end="2025",
        ),
    )

    assert len(outcome.fetch_plans) == 1
    assert outcome.fetch_plans[0].date_start == "not-a-date"
    assert outcome.fetch_plans[0].date_end == "2025"
    assert any(
        item.startswith("catalog_scope_unverified:scope_metric:") for item in outcome.warnings
    )


def test_explore_lane_cannot_reselect_known_incompatible_catalog_target(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    catalog = _ScopedBindingCatalog(
        countries=["UKR"],
        time_start="2020",
        time_end="2024",
    )
    service = RetrievalService(
        curated_dir=curated_dir,
        dataset_catalog=catalog,
        explore=_OneCandidateExplore(),
    )
    outcome = service.resolve(
        DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric="scope_metric",
                    geography="DEU",
                    time_start="2025",
                    time_end="2025",
                )
            ],
            mode="explorelane",
        ),
        run_profile="prod_full",
    )

    assert outcome.fetch_plans == []
    assert outcome.candidates == []
    assert "catalog_scope_incompatible:scope_metric:catalog-scope" in outcome.warnings


def test_fastlane_cannot_bypass_known_catalog_scope_mismatch(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    (curated_dir / "source_bindings.json").write_text(
        """{
          "schema_version": "1.0",
          "bindings": [{
            "metric_id": "scope_metric",
            "connector_id": "worldbank.wdi",
            "dataset_id": "scope_dataset",
            "profile_id": "worldbank_wdi",
            "geography_patterns": ["*"],
            "granularity": ["annual"],
            "priority": 10,
            "trust": 0.9,
            "filters_template": {},
            "tags": [],
            "aliases": []
          }]
        }""",
        encoding="utf-8",
    )
    catalog = _ScopedBindingCatalog(
        countries=["UKR"],
        time_start="2020",
        time_end="2024",
    )
    service = RetrievalService(curated_dir=curated_dir, dataset_catalog=catalog)
    outcome = service.resolve(
        DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric="scope_metric",
                    geography="DEU",
                    time_start="2025",
                    time_end="2025",
                )
            ],
            mode="fastlane",
            allow_explore_fallback=False,
        ),
        run_profile="prod_full",
    )

    assert outcome.fetch_plans == []
    assert outcome.candidates == []
    assert "catalog_scope_incompatible:scope_metric:catalog-scope" in outcome.warnings


@pytest.mark.parametrize(
    ("time_start", "time_end"),
    [("2019", "2025"), ("2015", "2022"), ("2022", "2028")],
)
def test_catalog_resolution_keeps_partial_time_overlap_unverified(
    tmp_path, time_start: str, time_end: str
) -> None:
    catalog = _ScopedBindingCatalog(
        countries=["DEU"],
        time_start="2020",
        time_end="2024",
    )
    outcome = _resolve_scoped_need(
        tmp_path,
        catalog,
        DataNeed(
            metric="scope_metric",
            geography="DEU",
            time_start=time_start,
            time_end=time_end,
        ),
    )

    assert len(outcome.fetch_plans) == 1
    assert any(
        item == "catalog_scope_unverified:scope_metric:time_coverage_partial_overlap"
        for item in outcome.warnings
    )
    assert not any(item.startswith("catalog_scope_incompatible:") for item in outcome.warnings)


@pytest.mark.parametrize(
    "metadata",
    [{"catalog_dataset_id": "forged-catalog"}, {}],
    ids=["metadata-self-label", "request-id-string-collision"],
)
def test_fastlane_scope_identity_uses_reconciled_binding_not_metadata_or_id_spelling(
    tmp_path, metadata: dict[str, object]
) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    catalog = _RequestIdCollisionCatalog(
        countries=["UKR"],
        time_start="2020",
        time_end="2024",
    )
    service = RetrievalService(
        curated_dir=curated_dir,
        dataset_catalog=catalog,
        fastlane=_SelectedPlanFastLane(_selected_scope_plan(metadata=metadata)),
    )
    outcome = service.resolve(
        DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric="scope_metric",
                    geography="DEU",
                    time_start="2025",
                    time_end="2025",
                )
            ],
            mode="fastlane",
            allow_explore_fallback=False,
        ),
        run_profile="prod_full",
    )

    assert outcome.fetch_plans == []
    assert "catalog_scope_incompatible:scope_metric:catalog-scope" in outcome.warnings


def test_fastlane_scope_identity_does_not_accept_wrong_connector_binding(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    catalog = _WrongConnectorScopeCatalog(
        countries=["UKR"],
        time_start="2020",
        time_end="2024",
    )
    service = RetrievalService(
        curated_dir=curated_dir,
        dataset_catalog=catalog,
        fastlane=_SelectedPlanFastLane(
            _selected_scope_plan(metadata={"catalog_dataset_id": "catalog-scope"})
        ),
    )
    outcome = service.resolve(
        DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric="scope_metric",
                    geography="DEU",
                    time_start="2025",
                    time_end="2025",
                )
            ],
            mode="fastlane",
            allow_explore_fallback=False,
        ),
        run_profile="prod_full",
    )

    assert len(outcome.fetch_plans) == 1
    assert any(
        item == "catalog_scope_unverified:scope_metric:catalog_identity_unresolved"
        for item in outcome.warnings
    )


@pytest.mark.parametrize(
    "needs",
    [
        [
            DataNeed(metric="scope_metric", geography="UKR", time_start="2025", time_end="2025"),
            DataNeed(metric="scope_metric"),
        ],
        [
            DataNeed(metric="scope_metric"),
            DataNeed(metric="scope_metric", geography="UKR", time_start="2025", time_end="2025"),
        ],
        [
            DataNeed(metric="scope_metric", geography="DEU", time_start="2020", time_end="2024"),
            DataNeed(metric="scope_metric", geography="UKR", time_start="2025", time_end="2025"),
        ],
    ],
    ids=["scoped-then-unscoped", "unscoped-then-scoped", "two-conflicting-scopes"],
)
def test_same_metric_need_occurrences_are_not_collapsed_to_last_scope(
    tmp_path, needs: list[DataNeed]
) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(
        curated_dir=curated_dir,
        dataset_catalog=_ScopedBindingCatalog(
            countries=["DEU"],
            time_start="2020",
            time_end="2024",
        ),
    )

    retained, warnings = service._filter_known_incompatible_catalog_targets(
        [_selected_scope_plan()],
        needs,
        run_profile="prod_full",
    )

    assert retained == [_selected_scope_plan()]
    assert "catalog_scope_incompatible:scope_metric:catalog-scope" in warnings
    assert "catalog_scope_unverified:scope_metric:duplicate_need_scope_ambiguous" in warnings


def test_actual_catalog_route_does_not_publish_incompatible_candidate(tmp_path) -> None:
    catalog = _actual_scope_catalog(tmp_path)
    try:
        outcome = _resolve_scoped_need(
            tmp_path,
            catalog,
            DataNeed(
                metric="scope_metric",
                geography="UKR",
                time_start="2040",
                time_end="2040",
            ),
        )
    finally:
        catalog.close()

    assert outcome.fetch_plans == []
    assert outcome.candidates == []
    assert any(
        item.startswith("catalog_scope_incompatible:scope_metric:") for item in outcome.warnings
    )


def test_two_explicitly_incompatible_need_occurrences_publish_no_candidate(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(
        curated_dir=curated_dir,
        dataset_catalog=_ScopedBindingCatalog(
            countries=["DEU"],
            time_start="2020",
            time_end="2024",
        ),
    )
    outcome = service.resolve(
        DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric="scope_metric", geography="DEU", time_start="2025", time_end="2025"
                ),
                DataNeed(
                    metric="scope_metric", geography="UKR", time_start="2025", time_end="2025"
                ),
            ],
            mode="fastlane",
            allow_explore_fallback=False,
        ),
        run_profile="prod_full",
    )

    assert outcome.fetch_plans == []
    assert outcome.candidates == []
    assert any(
        item.startswith("catalog_scope_incompatible:scope_metric:") for item in outcome.warnings
    )


def test_resolve_filters_explore_candidates_and_preserves_raw_index(tmp_path) -> None:
    """Keep raw discovery indexed while applying each request before ResolveOutcome emission."""
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(
        curated_dir=curated_dir,
        dataset_catalog=_ScopedBindingCatalog(
            countries=["UKR"],
            time_start="2020",
            time_end="2024",
        ),
        explore=_OneCandidateExplore(),
    )
    incompatible = service.resolve(
        DataResolveRequest(
            data_needs=[
                DataNeed(metric="scope_metric", geography="DEU", time_start="2025", time_end="2025")
            ],
            mode="explorelane",
        ),
        run_profile="prod_full",
    )

    assert incompatible.fetch_plans == []
    assert incompatible.candidates == []
    assert service.get_index_stats().index_docs_total == 1

    compatible = service.resolve(
        DataResolveRequest(
            data_needs=[
                DataNeed(metric="scope_metric", geography="UKR", time_start="2022", time_end="2023")
            ],
            mode="explorelane",
        ),
        run_profile="prod_full",
    )

    assert compatible.fetch_plans
    assert any(item.dataset_id == "scope_dataset" for item in compatible.candidates)
    assert service.get_index_stats().index_docs_total == 1


def test_fallback_with_alternate_metric_uses_parent_request_scope(tmp_path) -> None:
    class _AlternateMetricFallbackCatalog:
        _bindings = {
            "scope_metric": [("catalog-primary", "primary-dataset")],
            "metric.corrected": [
                ("catalog-fallback-bad", "fallback-bad"),
                ("catalog-fallback-good", "fallback-good"),
            ],
        }
        _coverage = {
            "catalog-primary": DatasetCoverage(
                countries=["DEU"], time_start="2020", time_end="2030"
            ),
            "catalog-fallback-bad": DatasetCoverage(
                countries=["UKR"], time_start="2020", time_end="2024"
            ),
            "catalog-fallback-good": DatasetCoverage(
                countries=["DEU"], time_start="2020", time_end="2030"
            ),
        }

        def reconciled_metric_binding_population(self, metric_name: str):
            return [
                MetricBindingMatch(
                    metric_id=metric_name,
                    catalog_dataset_id=catalog_id,
                    distribution_id=f"dist-{request_dataset_id}",
                    connector_id="worldbank.wdi",
                    profile_id="worldbank_wdi",
                    request_dataset_id=request_dataset_id,
                    execution_tier="fetchable",
                    source="worldbank",
                )
                for catalog_id, request_dataset_id in self._bindings.get(metric_name, [])
            ]

        def get_dataset(self, dataset_id: str):
            coverage = self._coverage.get(dataset_id)
            if coverage is None:
                return None
            return DatasetSearchResult(id=dataset_id, title=dataset_id, coverage=coverage)

    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    plan = FetchPlan(
        plan_id="scope-with-alternate-metric-fallbacks",
        metric_id="scope_metric",
        connector_id="worldbank.wdi",
        dataset_id="primary-dataset",
        profile_id="worldbank_wdi",
        fallbacks=[
            FetchPlanFallback(
                connector_id="worldbank.wdi",
                dataset_id="fallback-bad",
                metric_id="metric.corrected",
                profile_id="worldbank_wdi",
            ),
            FetchPlanFallback(
                connector_id="worldbank.wdi",
                dataset_id="fallback-good",
                metric_id="metric.corrected",
                profile_id="worldbank_wdi",
            ),
        ],
    )
    service = RetrievalService(
        curated_dir=curated_dir,
        dataset_catalog=_AlternateMetricFallbackCatalog(),
        fastlane=_SelectedPlanFastLane(plan),
    )

    outcome = service.resolve(
        DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric="scope_metric",
                    geography="DEU",
                    time_start="2025",
                    time_end="2025",
                )
            ],
            mode="fastlane",
            allow_explore_fallback=False,
        ),
        run_profile="prod_full",
    )

    assert len(outcome.fetch_plans) == 1
    assert [fallback.dataset_id for fallback in outcome.fetch_plans[0].fallbacks] == [
        "fallback-good"
    ]
    assert "catalog_scope_incompatible:scope_metric:catalog-fallback-bad" in outcome.warnings


def test_fallback_without_matching_request_scope_is_unverified(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    plan = FetchPlan(
        plan_id="unmatched-request-fallback",
        metric_id="unrequested_metric",
        connector_id="worldbank.wdi",
        dataset_id="primary-dataset",
        fallbacks=[
            FetchPlanFallback(
                connector_id="worldbank.wdi",
                dataset_id="fallback-dataset",
                metric_id="metric.corrected",
            )
        ],
    )
    service = RetrievalService(
        curated_dir=curated_dir,
        fastlane=_SelectedPlanFastLane(plan),
    )

    outcome = service.resolve(
        DataResolveRequest(
            data_needs=[
                DataNeed(
                    metric="scope_metric",
                    geography="DEU",
                    time_start="2025",
                    time_end="2025",
                )
            ],
            mode="fastlane",
            allow_explore_fallback=False,
        ),
        run_profile="prod_full",
    )

    assert len(outcome.fetch_plans) == 1
    assert [fallback.dataset_id for fallback in outcome.fetch_plans[0].fallbacks] == [
        "fallback-dataset"
    ]
    assert "catalog_scope_unverified:unrequested_metric:request_scope_unmatched" in outcome.warnings


def test_known_incompatible_fallback_is_removed_but_unknown_fallback_remains(tmp_path) -> None:
    class _FallbackCatalog:
        def reconciled_metric_binding_population(self, metric_name: str):
            if metric_name != "scope_metric":
                return []
            return [
                MetricBindingMatch(
                    metric_id="scope_metric",
                    catalog_dataset_id=catalog_id,
                    distribution_id=f"dist-{request_id}",
                    connector_id="worldbank.wdi",
                    profile_id="worldbank_wdi",
                    request_dataset_id=request_id,
                    execution_tier="fetchable",
                    source="worldbank",
                )
                for request_id, catalog_id in (
                    ("primary-dataset", "catalog-primary"),
                    ("bad-dataset", "catalog-bad"),
                    ("good-dataset", "catalog-good"),
                )
            ]

        def get_dataset(self, dataset_id: str):
            coverage = {
                "catalog-primary": DatasetCoverage(
                    countries=["DEU"], time_start="2020", time_end="2030"
                ),
                "catalog-bad": DatasetCoverage(
                    countries=["UKR"], time_start="2020", time_end="2024"
                ),
                "catalog-good": DatasetCoverage(
                    countries=["DEU"], time_start="2020", time_end="2030"
                ),
            }.get(dataset_id)
            if coverage is None:
                return None
            return DatasetSearchResult(id=dataset_id, title=dataset_id, coverage=coverage)

    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(curated_dir=curated_dir, dataset_catalog=_FallbackCatalog())
    plan = FetchPlan(
        plan_id="scope-with-fallbacks",
        metric_id="scope_metric",
        connector_id="worldbank.wdi",
        dataset_id="primary-dataset",
        profile_id="worldbank_wdi",
        fallbacks=[
            FetchPlanFallback(
                connector_id="worldbank.wdi",
                dataset_id="bad-dataset",
                metric_id="scope_metric",
                profile_id="worldbank_wdi",
            ),
            FetchPlanFallback(
                connector_id="worldbank.wdi",
                dataset_id="good-dataset",
                metric_id="scope_metric",
                profile_id="worldbank_wdi",
            ),
            FetchPlanFallback(
                connector_id="worldbank.wdi",
                dataset_id="unknown-dataset",
                metric_id="scope_metric",
                profile_id="worldbank_wdi",
            ),
        ],
    )

    retained, warnings = service._filter_known_incompatible_catalog_targets(
        [plan],
        [DataNeed(metric="scope_metric", geography="DEU", time_start="2025", time_end="2025")],
        run_profile="prod_full",
    )

    assert [fallback.dataset_id for fallback in retained[0].fallbacks] == [
        "good-dataset",
        "unknown-dataset",
    ]
    assert "catalog_scope_incompatible:scope_metric:catalog-bad" in warnings
    assert "catalog_scope_unverified:scope_metric:catalog_identity_unresolved" in warnings


def test_actual_catalog_route_uses_reconciled_binding_and_exact_dataset_reader(tmp_path) -> None:
    catalog = _actual_scope_catalog(tmp_path)
    try:
        outcome = _resolve_scoped_need(
            tmp_path,
            catalog,
            DataNeed(
                metric="scope_metric",
                geography="DEU",
                time_start="2025",
                time_end="2025",
            ),
        )
    finally:
        catalog.close()

    assert len(outcome.fetch_plans) == 1
    assert outcome.fetch_plans[0].metadata["catalog_dataset_id"] == "catalog-scope"
    assert not any(item.startswith("catalog_scope_") for item in outcome.warnings)


@pytest.mark.parametrize(
    "refusal",
    ["reconciliation", "dataset_read"],
)
def test_actual_catalog_refusals_are_not_downgraded_to_scope_warnings(
    tmp_path, monkeypatch, refusal: str
) -> None:
    catalog = _actual_scope_catalog(tmp_path)
    try:
        if refusal == "reconciliation":

            def refuse_population(_metric_name: str):
                raise ValueError("catalog_metric_binding_population_identity_drift")

            monkeypatch.setattr(catalog, "reconciled_metric_binding_population", refuse_population)
            expected = "catalog_metric_binding_population_identity_drift"
        else:
            monkeypatch.setattr(catalog, "get_dataset", lambda _dataset_id: None)
            expected = "catalog_dataset_identity_unresolved"

        curated_dir = tmp_path / "curated"
        curated_dir.mkdir()
        service = RetrievalService(curated_dir=curated_dir, dataset_catalog=catalog)
        with pytest.raises((ValueError, RuntimeError), match=expected):
            service.resolve(
                DataResolveRequest(
                    data_needs=[
                        DataNeed(
                            metric="scope_metric",
                            geography="DEU",
                            time_start="2025",
                            time_end="2025",
                        )
                    ],
                    mode="fastlane",
                    allow_explore_fallback=False,
                ),
                run_profile="prod_full",
            )
    finally:
        catalog.close()


def test_retrieval_service_bounds_local_index_docs(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(curated_dir=curated_dir, max_local_index_docs=2)

    service._update_local_index(
        [
            DiscoveryCandidate(
                candidate_id="c1",
                metric_id="gdp",
                connector_id="worldbank",
                dataset_id="ds1",
                confidence=0.9,
            ),
            DiscoveryCandidate(
                candidate_id="c2",
                metric_id="inflation",
                connector_id="imf",
                dataset_id="ds2",
                confidence=0.8,
            ),
            DiscoveryCandidate(
                candidate_id="c3",
                metric_id="population",
                connector_id="un",
                dataset_id="ds3",
                confidence=0.7,
            ),
        ]
    )

    stats = service.get_index_stats()
    assert stats.index_docs_total == 2
    assert stats.index_size_bytes > 0
    assert list(service._local_index_docs.keys()) == ["imf:ds2", "un:ds3"]


def test_retrieval_service_bounds_promotion_queue(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(curated_dir=curated_dir, max_promotion_candidates=2)

    for idx in range(3):
        created = datetime(2026, 1, idx + 1, tzinfo=UTC)
        plan = FetchPlan(
            plan_id=f"plan-{idx}",
            metric_id=f"metric-{idx}",
            connector_id=f"connector-{idx}",
            dataset_id=f"dataset-{idx}",
            source_lane="explorelane",
            quality_min=0.5,
            metadata={"confidence": 0.9, "created_for_test": created.isoformat()},
        )
        assert service._emit_promotion_candidate(plan=plan, completeness=1.0) == 1

    candidates = service.list_promotion_candidates()
    assert len(candidates) == 2
    assert {item.metric_id for item in candidates} == {"metric-1", "metric-2"}


def test_retrieval_service_reports_resolution_route_breakdown(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(curated_dir=curated_dir)
    service._fastlane.resolve = lambda needs: FastLaneResolveResult(
        fetch_plans=(
            FetchPlan(
                plan_id="plan-1",
                metric_id="gdp",
                connector_id="worldbank.wdi",
                dataset_id="NY.GDP.MKTP.CD",
                metadata={"resolution_route": "semantic"},
            ),
        ),
        candidates=(
            MetricCandidate(
                candidate_id="cand-semantic",
                metric_id="gdp",
                connector_id="worldbank.wdi",
                dataset_id="NY.GDP.MKTP.CD",
                confidence=0.91,
                metadata={"resolution_route": "semantic"},
            ),
            MetricCandidate(
                candidate_id="cand-manual",
                metric_id="gdp",
                connector_id="manual.csv",
                dataset_id="gdp_backup",
                confidence=0.55,
                metadata={"resolution_route": "manual_binding"},
            ),
        ),
        warnings=(),
    )

    outcome = service.resolve(
        DataResolveRequest(data_needs=[DataNeed(metric="gdp")], mode="fastlane")
    )

    assert outcome.telemetry["resolution_routes"]["candidates"] == {
        "manual_binding": 1,
        "semantic": 1,
    }
    assert outcome.telemetry["resolution_routes"]["selected"] == {"semantic": 1}


def test_fallback_to_plan_updates_metric_id_and_analytics() -> None:
    plan = FetchPlan(
        plan_id="plan-primary",
        metric_id="metric.primary",
        connector_id="connector.primary",
        dataset_id="dataset.primary",
        metadata={"resolution_route": "semantic"},
        fallbacks=[
            FetchPlanFallback(
                connector_id="connector.fallback",
                dataset_id="dataset.fallback",
                metric_id="metric.corrected",
                metadata={
                    "resolution_route": "manual_binding",
                    "fallback_reason": "operator_override",
                },
            )
        ],
    )

    fallback = FetchExecutor._fallback_to_plan(plan, plan.fallbacks[0])

    assert fallback.metric_id == "metric.corrected"
    assert fallback.metadata["resolution_route"] == "manual_binding"
    assert fallback.metadata["fallback_reason"] == "operator_override"
    assert fallback.metadata["fallback_history"][0]["from_metric_id"] == "metric.primary"


class _RecordingTracer:
    def __init__(self) -> None:
        self.spans: list[tuple[str, dict[str, object]]] = []

    def start_as_current_span(
        self,
        name: str,
        *,
        attributes: dict[str, object] | None = None,
    ):
        self.spans.append((name, dict(attributes or {})))
        return nullcontext()


class _RecordingMetrics:
    def __init__(self) -> None:
        self.query_calls: list[dict[str, object]] = []
        self.fetch_calls: list[dict[str, object]] = []

    def record_fabric_query(self, **kwargs: object) -> None:
        self.query_calls.append(dict(kwargs))

    def record_fabric_connector_fetch(self, **kwargs: object) -> None:
        self.fetch_calls.append(dict(kwargs))


def test_fetch_executor_uses_injected_registry_profiles_and_observability(
    monkeypatch,
) -> None:
    tracer = _RecordingTracer()
    metrics = _RecordingMetrics()

    class _FakeConnector:
        async def fetch(
            self,
            handle: object,
            request: FetchRequest,
        ) -> FetchResult[dict[str, object]]:
            del handle, request
            return FetchResult(
                data=[{"value": 1}],
                row_count=1,
                schema_id="schema.test",
                schema_version="1.0",
                version=DataVersion(
                    strategy=VersionStrategy.TIMESTAMP,
                    value="version-1",
                    timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                ),
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                completeness=1.0,
                quality_tier=QualityTier.SILVER,
                quality_flags=[],
            )

    class _FakeRegistry:
        def get(
            self,
            connector_id: str,
            *,
            enable_cache: bool = False,
        ) -> _FakeConnector:
            del connector_id, enable_cache
            return _FakeConnector()

        def get_default_config(self, connector_id: str) -> ConnectionConfig:
            del connector_id
            return ConnectionConfig(url="https://example.test/data")

        async def get_connection(
            self,
            connector_id: str,
            config: ConnectionConfig | None,
        ) -> object:
            del connector_id, config
            return object()

        async def release_connection(self, connector_id: str, handle: object) -> None:
            del connector_id, handle

    class _FakeProfiles:
        def get(self, profile_id: str) -> None:
            del profile_id
            return None

    def _unexpected(*args, **kwargs):
        raise AssertionError("global provider lookup should not be used")

    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers.ConnectorRegistry.get_instance",
        _unexpected,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers.SourceProfileRegistry.get_instance",
        _unexpected,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers.get_tracer",
        _unexpected,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers.get_metrics",
        _unexpected,
    )

    executor = FetchExecutor(
        registry=_FakeRegistry(),
        profiles=_FakeProfiles(),
        tracer=tracer,
        metrics=metrics,
    )

    outcome = executor.execute(
        FetchPlan(
            plan_id="plan.test",
            metric_id="metric.test",
            connector_id="demo.connector",
            dataset_id="dataset.test",
            quality_min=0.5,
        )
    )

    assert outcome.metric is not None
    assert metrics.fetch_calls[0]["status"] == "success"
    assert tracer.spans[0][0] == "fabric.connector.fetch"


def test_explore_lane_uses_injected_registry_and_profiles(monkeypatch) -> None:
    class _FakeDescriptor:
        dataset_id = "dataset.demo"
        name = "Demo dataset"
        description = "demo metric coverage"
        tags = ("demo", "metric")
        supports_filters = ("country",)

    class _FakeConnector:
        async def list_datasets(self, handle: object):
            del handle
            yield _FakeDescriptor()

    class _FakeRegistry:
        def query_entries(self, *, capabilities: object):
            del capabilities
            return [
                SimpleNamespace(
                    short_id="demo.connector",
                    metadata=SimpleNamespace(
                        namespace="demo",
                        observed_latency_ms=25,
                    ),
                )
            ]

        def get(
            self,
            connector_id: str,
            *,
            enable_cache: bool = False,
        ) -> _FakeConnector:
            del connector_id, enable_cache
            return _FakeConnector()

        def get_default_config(self, connector_id: str) -> ConnectionConfig:
            del connector_id
            return ConnectionConfig(url="https://example.test/discover")

        async def get_connection(
            self,
            connector_id: str,
            config: ConnectionConfig | None,
        ) -> object:
            del connector_id, config
            return object()

        async def release_connection(self, connector_id: str, handle: object) -> None:
            del connector_id, handle

    class _FakeProfiles:
        def list_by_family(self, family: str):
            del family
            return [SimpleNamespace(profile_id="profile.demo")]

    def _unexpected(*args, **kwargs):
        del args, kwargs
        raise AssertionError("unexpected singleton lookup")

    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers.ConnectorRegistry.get_instance",
        _unexpected,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers.SourceProfileRegistry.get_instance",
        _unexpected,
    )

    discovery = ExploreLaneDiscovery(
        registry=_FakeRegistry(),
        profiles=_FakeProfiles(),
    )
    result = discovery.discover([DataNeed(metric="demo metric")])

    assert len(result.candidates) == 1
    assert result.candidates[0].profile_id == "profile.demo"


def test_retrieval_service_discover_uses_injected_executor_explore_and_observability(
    tmp_path,
    monkeypatch,
) -> None:
    tracer = _RecordingTracer()
    metrics = _RecordingMetrics()

    class _FakeExplore:
        def discover(
            self,
            data_needs: list[DataNeed],
            *,
            limits: object,
        ) -> ExploreLaneDiscoverResult:
            del data_needs, limits
            return ExploreLaneDiscoverResult(
                candidates=[
                    DiscoveryCandidate(
                        candidate_id="disc-1",
                        metric_id="gdp",
                        connector_id="demo.connector",
                        dataset_id="dataset.demo",
                        profile_id="profile.demo",
                        confidence=0.8,
                    )
                ],
                docs_fetched_total=3,
                warnings=[],
            )

    class _FakeExecutor:
        artifact_store = None

        def preview(self, plan: FetchPlan, *, allow_fallback: bool = True):
            del plan, allow_fallback
            raise AssertionError("preview should not be called")

    class _FakeFastLane:
        def search_catalog(
            self, *, metric_query: str, geography: str | None = None, limit: int = 25
        ):
            del metric_query, geography, limit
            return []

    def _unexpected(*args, **kwargs):
        raise AssertionError("global provider lookup should not be used")

    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers.ConnectorRegistry.get_instance",
        _unexpected,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers.SourceProfileRegistry.get_instance",
        _unexpected,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers.get_tracer",
        _unexpected,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.providers.get_metrics",
        _unexpected,
    )

    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(
        curated_dir=curated_dir,
        registry=SimpleNamespace(),
        profiles=SimpleNamespace(),
        tracer=tracer,
        metrics=metrics,
        fastlane=_FakeFastLane(),
        executor=_FakeExecutor(),
        explore=_FakeExplore(),
    )

    outcome = service.discover(data_needs=[DataNeed(metric="gdp")])

    assert outcome.docs_fetched_total == 3
    assert metrics.query_calls[0]["operation"] == "discover"
    assert tracer.spans[0][0] == "fabric.retrieval.discover"


def test_retrieval_service_provider_bundle_builds_nested_components_without_singletons(
    tmp_path,
    monkeypatch,
) -> None:
    tracer = _RecordingTracer()
    metrics = _RecordingMetrics()

    class _FakeDescriptor:
        dataset_id = "dataset.demo"
        name = "demo metric dataset"
        description = "demo metric coverage"
        tags = ("demo", "metric")
        supports_filters = ("country",)

    class _FakeConnector:
        async def list_datasets(self, handle: object):
            del handle
            yield _FakeDescriptor()

        async def fetch(
            self,
            handle: object,
            request: FetchRequest,
        ) -> FetchResult[list[dict[str, object]]]:
            del handle, request
            return FetchResult(
                data=[{"value": 1}],
                row_count=1,
                schema_id="schema.demo",
                schema_version="1.0",
                version=DataVersion(
                    strategy=VersionStrategy.TIMESTAMP,
                    value="version-demo",
                    timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                ),
                fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
                completeness=1.0,
                quality_tier=QualityTier.SILVER,
                quality_flags=[],
            )

        async def get_dataset_schema(
            self,
            handle: object,
            dataset_id: str,
        ) -> dict[str, object]:
            del handle, dataset_id
            return {"fields": ["value"]}

    class _FakeRegistry:
        def query_entries(self, *, capabilities: object):
            del capabilities
            return [
                SimpleNamespace(
                    short_id="demo.connector",
                    metadata=SimpleNamespace(
                        namespace="demo",
                        observed_latency_ms=25,
                    ),
                )
            ]

        def get(
            self,
            connector_id: str,
            *,
            enable_cache: bool = False,
        ) -> _FakeConnector:
            del connector_id, enable_cache
            return _FakeConnector()

        def get_default_config(self, connector_id: str) -> ConnectionConfig:
            del connector_id
            return ConnectionConfig(url="https://example.test/demo")

        async def get_connection(
            self,
            connector_id: str,
            config: ConnectionConfig | None,
        ) -> object:
            del connector_id, config
            return object()

        async def release_connection(self, connector_id: str, handle: object) -> None:
            del connector_id, handle

    class _FakeProfiles:
        def get(self, profile_id: str) -> None:
            del profile_id
            return None

        def list_by_family(self, family: str):
            del family
            return [SimpleNamespace(profile_id="profile.demo")]

    def _unexpected(*args, **kwargs):
        raise AssertionError("global provider lookup should not be used")

    monkeypatch.setattr(
        "polisyos.fabric.retrieval.service.resolve_retrieval_providers",
        _unexpected,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.executor.resolve_retrieval_providers",
        _unexpected,
    )
    monkeypatch.setattr(
        "polisyos.fabric.retrieval.explore_lane.resolve_retrieval_providers",
        _unexpected,
    )
    monkeypatch.setattr(
        "polisyos.fabric.catalog.providers._default_connector_registry",
        _unexpected,
    )

    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(
        curated_dir=curated_dir,
        providers=RetrievalProviders(
            registry=_FakeRegistry(),  # type: ignore[arg-type]
            profiles=_FakeProfiles(),  # type: ignore[arg-type]
            tracer=tracer,  # type: ignore[arg-type]
            metrics=metrics,  # type: ignore[arg-type]
        ),
    )

    discover = service.discover(data_needs=[DataNeed(metric="demo metric")])
    preview = service.preview(
        FetchPlan(
            plan_id="plan.demo",
            metric_id="metric.demo",
            connector_id="demo.connector",
            dataset_id="dataset.demo",
            quality_min=0.5,
        )
    )

    assert discover.docs_fetched_total == 1
    assert preview.preview.coverage_ok is True
    assert any(call["operation"] == "discover" for call in metrics.query_calls)
    assert any(call["status"] == "success" for call in metrics.fetch_calls)
    assert {span[0] for span in tracer.spans} >= {
        "fabric.retrieval.discover",
        "fabric.connector.fetch",
    }

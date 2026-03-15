from __future__ import annotations

from polisyos.core.contracts.control import DataNeed
from polisyos.datasets.knowledge.types import DatasetSearchResult, MetricBindingMatch, ResolvedFetchTarget
from polisyos.fabric.retrieval.service import RetrievalService


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
                title="GDP per capita",
            )
        ]


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
    plans, candidates = service._resolve_via_catalog([DataNeed(metric="gdp")])
    assert len(plans) == 1
    assert plans[0].dataset_id == "NY.GDP.MKTP.CD"
    assert plans[0].connector_id == "worldbank.wdi"
    assert plans[0].metadata["catalog_dataset_id"] == "catalog-gdp"
    assert candidates[0].dataset_id == "NY.GDP.MKTP.CD"


def test_catalog_resolution_skips_unfetchable_targets(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(curated_dir=curated_dir, dataset_catalog=_TargetCatalog())
    plans, candidates = service._resolve_via_catalog([DataNeed(metric="gdp")])
    assert plans == []
    assert candidates == []


def test_catalog_resolution_applies_rolling_window_defaults_for_rest_sources(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(curated_dir=curated_dir, dataset_catalog=_RollingWindowBindingCatalog())
    plans, candidates = service._resolve_via_catalog([DataNeed(metric="health_outcomes")])

    assert len(plans) == 1
    assert len(candidates) == 1
    assert plans[0].connector_id == "rest.json"
    assert plans[0].date_start is not None
    assert plans[0].date_end is not None
    assert plans[0].metadata["history_policy"] == "rolling_window"
    assert plans[0].metadata["default_lookback_days"] == 90

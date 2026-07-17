from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

from polisyos.core.contracts.control import (
    DataNeed,
    DataResolveRequest,
    DiscoveryCandidate,
    FetchPlan,
    FetchPlanFallback,
    MetricCandidate,
)
from polisyos.data_forge.domains.catalog.knowledge.types import (
    DatasetSearchResult,
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


def test_catalog_resolution_rejects_catalog_only_metric_bindings(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(
        curated_dir=curated_dir,
        dataset_catalog=_CatalogOnlyBindingCatalog(),
    )

    plans, candidates = service._resolve_via_catalog([DataNeed(metric="gdp")])

    assert plans == []
    assert candidates == []


def test_catalog_resolution_applies_rolling_window_defaults_for_rest_sources(tmp_path) -> None:
    curated_dir = tmp_path / "curated"
    curated_dir.mkdir()
    service = RetrievalService(
        curated_dir=curated_dir, dataset_catalog=_RollingWindowBindingCatalog()
    )
    plans, candidates = service._resolve_via_catalog([DataNeed(metric="health_outcomes")])

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

    plans, candidates = service._resolve_via_catalog([DataNeed(metric="gdp")])

    assert len(plans) == 1
    assert len(candidates) == 1
    assert plans[0].profile_id is None
    assert candidates[0].profile_id is None


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

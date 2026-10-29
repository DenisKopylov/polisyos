"""Behavioral custody tests across the real catalog and fetch executor."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, Literal

import duckdb
import pandas as pd
import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.core.contracts.control import (
    DataNeed,
    DataResolveRequest,
    FetchPlan,
    FetchPlanFallback,
)
from polisyos.data_forge.domains.catalog.batch.graph_builder import build_graph
from polisyos.data_forge.read_api import catalog as catalog_api
from polisyos.fabric.catalog.resolver_fast_lane import FastLaneResolveResult
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.retrieval.providers import RetrievalProviders
from polisyos.fabric.retrieval.service import RetrievalService
from polisyos.ir.connectors import DataVersion, FetchResult, VersionStrategy


@dataclass(frozen=True)
class _RecordedHTTPExchange:
    """Capture the minimal World Bank transport protocol used by the real owner."""

    kind: Literal["health", "data"]
    url: str
    params: dict[str, str]
    response: object
    headers: dict[str, str]


@contextmanager
def build_real_fetch_owner(
    tmp_path,
    *,
    dataset_names=("primary", "fallback"),
    connector_id="test.recorded",
    providers_override=None,
    source_location=None,
    patch_fastlane=True,
    metric_id="metric.test",
    dataset_records=None,
    artifact_store=None,
    artifact_store_config=None,
    catalog_updated_at: datetime | None = None,
):
    """Use a real graph, with only the connector transport controlled.

    An explicit aware timestamp is a synthetic fixture ingestion input. It is
    written before readers/admission and never establishes source currentness.
    """
    if catalog_updated_at is not None and (
        catalog_updated_at.tzinfo is None or catalog_updated_at.utcoffset() is None
    ):
        raise ValueError("fixture_catalog_updated_at_timezone_required")
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetRecord,
        DistributionRecord,
    )

    graph_path = tmp_path / "catalog.duckdb"
    records = [
        DatasetRecord(
            id=f"catalog-{name}",
            title=f"Recorded {name}",
            dataset_id=name,
            source_dataset_id=name,
            polisyos_metrics=[metric_id],
            execution_tier="transport_ready",
            distributions=[
                DistributionRecord(
                    id=f"distribution-{name}",
                    connector_type=connector_id,
                    source_locator=name,
                    parser_supported=True,
                    machine_readable=True,
                    connector_params={"url": source_location} if source_location else {},
                )
            ],
        )
        for name in dataset_names
    ]
    build_graph(records=records if dataset_records is None else dataset_records, db_path=graph_path)
    if catalog_updated_at is not None:
        # Complete fixture construction before opening any Catalog read owner.
        with duckdb.connect(str(graph_path)) as fixture_writer:
            fixture_writer.execute(
                "UPDATE ds_datasets SET updated_at = ?",
                [catalog_updated_at.astimezone(UTC).replace(tzinfo=None)],
            )
    overlay_path = tmp_path / "overlay.duckdb"
    index_dir = tmp_path
    graph = catalog_api.DatasetCatalogGraph(graph_path, index_dir, overlay_path=overlay_path)
    rows = [{"row_id": f"r-{index}", "value": index + 0.5, "optional": None} for index in range(12)]
    requests = []
    preview_reject = set()
    payload = {"value": rows}
    result_updates = {}

    from polisyos.fabric.connectors.base import BaseConnector, ConnectionHandle, HealthStatus
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.types import (
        ValidationIssue,
        ValidationResult,
        ValidationSeverity,
    )
    from polisyos.ir.connectors import (
        ConnectorCapability,
        ConnectorMetadataSpec,
        FetchRequest,
        QualityTier,
        TrustLevel,
        capabilities_from_flags,
    )

    if providers_override is None:
        if connector_id != "test.recorded":
            raise ValueError("controlled_recorded_transport_requires_test_recorded_connector_id")
        recorded_transport_url = "https://transport.invalid/recorded"

        class RecordedFixtureConnector(BaseConnector[Any]):
            """Test-only source that returns recorded rows through the real registry."""

            connector_id: ClassVar[str] = "test.recorded"
            capabilities: ClassVar[ConnectorCapability] = ConnectorCapability.FULL_FETCH
            metadata: ClassVar[ConnectorMetadataSpec] = ConnectorMetadataSpec(
                connector_id="recorded",
                version="1.0.0",
                namespace="test",
                source_name="Recorded transport fixture",
                source_organization="PolicyOS tests",
                trust_level=TrustLevel.UNVERIFIED,
                quality_tier=QualityTier.UNVERIFIED,
                capabilities=capabilities_from_flags(ConnectorCapability.FULL_FETCH),
                description="Deterministic test-only connector; no network transport is performed.",
            )

            @classmethod
            def validate_config(cls, config: ConnectionConfig) -> ValidationResult:
                if (
                    config.url != recorded_transport_url
                    or config.headers
                    or config.auth_method is not None
                    or config.auth_credentials
                ):
                    return ValidationResult.failure(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            message="recorded fixture requires its exact unauthenticated endpoint",
                            field="url",
                            code="recorded_fixture_config_mismatch",
                        )
                    )
                return ValidationResult.success()

            async def connect(self, config: ConnectionConfig) -> ConnectionHandle:
                validation = self.validate_config(config)
                if not validation.valid:
                    raise ValueError("invalid test.recorded connector config")
                return self._create_handle(config)

            async def disconnect(self, handle: ConnectionHandle) -> None:
                del handle

            async def health_check(self, handle: ConnectionHandle) -> HealthStatus:
                del handle
                return HealthStatus(healthy=True, message="recorded test transport is available")

            async def fetch(
                self,
                handle: ConnectionHandle,
                request: FetchRequest,
            ) -> FetchResult[Any]:
                del handle
                requests.append(request)
                data = payload["value"]
                count = len(data)
                return FetchResult(
                    data=data,
                    row_count=count,
                    schema_id="test.recorded.rows",
                    schema_version="1.0.0",
                    version=DataVersion(
                        strategy=VersionStrategy.TIMESTAMP,
                        value="recorded-v1",
                        timestamp=datetime(2026, 9, 8, tzinfo=UTC),
                    ),
                    fetched_at=datetime(2026, 9, 8, tzinfo=UTC),
                    completeness=(
                        0.0 if request.page_size and request.dataset_id in preview_reject else 1.0
                    ),
                    quality_flags=frozenset({"recorded-test-transport"}),
                    total_count=count,
                    bytes_transferred=421,
                ).model_copy(update=result_updates)

        registry = ConnectorRegistry()
        registry.register(
            RecordedFixtureConnector,
            config=ConnectionConfig(url=recorded_transport_url),
        )
        providers = RetrievalProviders(
            registry=registry,
            profiles=SimpleNamespace(get=lambda _: None),
            tracer=SimpleNamespace(start_as_current_span=lambda *args, **kwargs: nullcontext()),
            metrics=SimpleNamespace(
                record_fabric_query=lambda **kwargs: None,
                record_fabric_connector_fetch=lambda **kwargs: None,
            ),
        )
    else:
        # Use the supplied real connector registry directly. Do not register an
        # unrelated FileTabular-derived placeholder as a side effect.
        providers = providers_override
    plan = FetchPlan(
        plan_id="plan-primary",
        metric_id=metric_id,
        connector_id=connector_id,
        dataset_id=dataset_names[0],
        quality_min=0.5,
        source_lane="fastlane",
    )
    local_cas_root = (
        tmp_path / "cas" if artifact_store is None and artifact_store_config is None else None
    )
    service = RetrievalService(
        curated_dir=tmp_path,
        cas_root=local_cas_root,
        artifact_store=artifact_store,
        artifact_store_config=artifact_store_config,
        dataset_catalog=graph,
        providers=providers,
    )
    if patch_fastlane:
        service._fastlane.resolve = lambda needs: FastLaneResolveResult(
            fetch_plans=(plan,), candidates=(), warnings=()
        )
    try:
        yield SimpleNamespace(
            service=service,
            graph=graph,
            graph_path=graph_path,
            plan=plan,
            rows=rows,
            requests=requests,
            payload=payload,
            preview_reject=preview_reject,
            store=service.artifact_store,
            providers=providers,
            curated_dir=tmp_path,
            cas_root=tmp_path / "cas",
            overlay_path=overlay_path,
            result_updates=result_updates,
        )
    finally:
        graph.close()


@contextmanager
def build_recorded_file_fetch_owner(
    tmp_path,
    *,
    canonicalize_catalog_source=False,
    catalog_source_locator=None,
    catalog_connector_params=None,
    profile_base_url=None,
    with_catalog_profile=False,
    catalog_updated_at: datetime | None = None,
):
    """Use the real FileTabularConnector and exact catalog binding for custody tests.

    The test-only recorded_file_local profile binds executor configuration only. This fixture
    does not claim catalog-publisher currentness.
    """
    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetRecord,
        DistributionRecord,
    )
    from polisyos.fabric.connectors.base import ConnectionHandle
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.sources.file_tabular import FileTabularConnector
    from polisyos.ir.connectors import FetchRequest

    tmp_path.mkdir(parents=True, exist_ok=True)
    csv_path = tmp_path / "recorded.csv"
    frame = pd.DataFrame(
        {"row_id": [f"r-{i}" for i in range(12)], "value": [i + 0.5 for i in range(12)]}
    )
    frame.to_csv(csv_path, index=False)
    catalog_locator = (
        Path(catalog_source_locator)
        if catalog_source_locator is not None
        else csv_path
        if canonicalize_catalog_source
        else None
    )
    if catalog_locator is not None:
        catalog_locator.parent.mkdir(parents=True, exist_ok=True)
        catalog_locator.write_bytes(csv_path.read_bytes())
    primary_connector_params = (
        dict(catalog_connector_params)
        if catalog_connector_params is not None
        else {"url": str(csv_path)}
    )
    if catalog_locator is not None:
        canonical_catalog_locator = catalog_locator.resolve(strict=True)
        configured_locator = primary_connector_params.get("url")
        if configured_locator is None:
            configured_locator = primary_connector_params.get("path")
        if isinstance(configured_locator, str) and configured_locator.strip():
            assert Path(configured_locator).resolve(strict=True) == canonical_catalog_locator
    profiles = SourceProfileRegistry()
    selected_profile_id = "recorded_file_local" if with_catalog_profile else None
    if selected_profile_id is not None:
        profiles.register(
            SourceProfile(
                profile_id=selected_profile_id,
                display_name="Recorded local file fixture",
                description="Controlled local-file profile with no excluded auth inputs",
                connector_family="files",
                base_url=str(
                    profile_base_url
                    if profile_base_url is not None
                    else catalog_locator or csv_path
                ),
                headers={},
                auth_policy="none",
            )
        )
    dataset_records = [
        DatasetRecord(
            id=f"catalog-{name}",
            title=f"Recorded {name}",
            dataset_id=name,
            source="recorded_file",
            source_dataset_id=name,
            polisyos_metrics=["metric.test"],
            execution_tier="transport_ready",
            distributions=[
                DistributionRecord(
                    id=f"distribution-{name}",
                    connector_type="files.tabular",
                    source_locator=(
                        str(catalog_locator) if name == "primary" and catalog_locator else name
                    ),
                    profile_id=selected_profile_id or "",
                    parser_supported=True,
                    machine_readable=True,
                    connector_params=(
                        primary_connector_params if name == "primary" else {"url": str(csv_path)}
                    ),
                    # Canonical capture fixtures resolve the intended primary target
                    # before read-only binding; retain symbolic fallback for the
                    # foreign-binding negative case.
                    quality_score=1.0 if name == "primary" and catalog_locator else 0.0,
                )
            ],
        )
        for name in ("primary", "fallback")
    ]
    requests: list[FetchRequest] = []

    class RecordingFileTabularConnector(FileTabularConnector):
        async def fetch(self, handle: ConnectionHandle, request: FetchRequest) -> FetchResult[Any]:
            requests.append(request)
            return await super().fetch(handle, request)

    registry = ConnectorRegistry()
    registry.register(RecordingFileTabularConnector, config=ConnectionConfig(url=str(csv_path)))
    providers = RetrievalProviders(
        registry=registry,
        profiles=profiles,
        tracer=SimpleNamespace(start_as_current_span=lambda *a, **k: nullcontext()),
        metrics=SimpleNamespace(
            record_fabric_query=lambda **kwargs: None,
            record_fabric_connector_fetch=lambda **kwargs: None,
        ),
    )
    with build_real_fetch_owner(
        tmp_path,
        connector_id="files.tabular",
        providers_override=providers,
        source_location=str(csv_path),
        patch_fastlane=False,
        dataset_records=dataset_records,
        catalog_updated_at=catalog_updated_at,
    ) as owner:
        owner.csv_path = csv_path
        owner.frame = frame
        owner.rows = frame.to_dict(orient="records")
        owner.requests = requests
        owner.index_dir = tmp_path
        if selected_profile_id is not None:
            # Match the graph-owned request id derived from this distribution source locator.
            admitted_dataset_id = (
                str(catalog_locator) if catalog_locator is not None else owner.plan.dataset_id
            )
            owner.plan = owner.plan.model_copy(
                update={
                    "dataset_id": admitted_dataset_id,
                    "profile_id": selected_profile_id,
                }
            )
        yield owner


@contextmanager
def build_worldbank_fetch_owner(tmp_path, *, artifact_store=None):
    """Run the committed WDI HTTP fixture against its exact graph-bound plan.

    Publisher currentness is witnessed separately through the complete catalog fixture.
    The USA/DEU GDP identities in the recorded HTTP payload remain unchanged.
    """
    import ast
    import json
    from pathlib import Path

    from polisyos.data_forge.domains.catalog.batch.normalizer import normalize_worldbank
    from polisyos.data_forge.domains.catalog.knowledge.types import DatasetCoverage
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.fabric.connectors.profiles.builtin_profiles import BUILTIN_PROFILES
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.sources.world_bank import (
        WorldBankConnector,
        normalize_worldbank_records,
    )

    tmp_path.mkdir(parents=True, exist_ok=True)
    fixture_source = Path(__file__).parent / "connectors/sources/test_production_connectors.py"
    tree = ast.parse(fixture_source.read_text())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "test_world_bank_fetch_with_mock_http"
    )
    declaration = next(
        node
        for node in function.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "responses"
    )
    responses = ast.literal_eval(declaration.value)
    requests: list[_RecordedHTTPExchange] = []
    raw_rows = [row for page in sorted(responses) for row in responses[page][1]]
    indicator_ids = {row["indicator"]["id"] for row in raw_rows}
    assert indicator_ids == {"NY.GDP.MKTP.CD"}
    indicator_names = {row["indicator"]["value"] for row in raw_rows}
    assert len(indicator_names) == 1
    record = normalize_worldbank(
        {"id": "NY.GDP.MKTP.CD", "name": next(iter(indicator_names))},
        metrics_map={"gdp": {"worldbank_indicators": ["NY.GDP.MKTP.CD"]}},
    )
    years = sorted({int(row["date"]) for row in raw_rows})
    countries = sorted({row["countryiso3code"] for row in raw_rows})
    record = record.model_copy(
        update={
            "coverage": DatasetCoverage(
                countries=countries,
                time_start=str(years[0]),
                time_end=str(years[-1]),
                granularity="annual",
            ),
            "distributions": [
                dist.model_copy(update={"default_filters": {"country": ["US", "DE"]}})
                for dist in record.distributions
            ],
        }
    )

    async def request_json(_session, url, *, params, connector_id):
        assert connector_id == "worldbank.wdi"
        assert url.endswith("/indicator/NY.GDP.MKTP.CD")
        if "page" in params:
            request_kind: Literal["health", "data"] = "data"
            body = responses[int(params["page"])]
        else:
            request_kind = "health"
            assert params == {"format": "json", "per_page": "1"}
            body = [{"pages": 1}, [raw_rows[0]]]
        headers = {
            "ETag": '"wdi-etag-1"',
            "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
        }
        requests.append(
            _RecordedHTTPExchange(
                kind=request_kind,
                url=url,
                params=dict(params),
                response=body,
                headers=headers,
            )
        )
        return body, headers, json.dumps(body).encode()

    class _RecordedSession:
        """Provide the lifecycle surface used by the real HTTP connector cleanup."""

        def __init__(self) -> None:
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    async def get_session(self, handle):
        session = handle.get_state(self._STATE_SESSION_KEY)
        if session is None or session.closed:
            session = _RecordedSession()
            handle.set_state(self._STATE_SESSION_KEY, session)
        return session

    registry = ConnectorRegistry()
    registry.register(
        WorldBankConnector, config=ConnectionConfig(url="https://api.worldbank.org/v2")
    )
    providers = RetrievalProviders(
        registry=registry,
        profiles=SourceProfileRegistry(),
        tracer=SimpleNamespace(start_as_current_span=lambda *args, **kwargs: nullcontext()),
        metrics=SimpleNamespace(
            record_fabric_query=lambda **kwargs: None,
            record_fabric_connector_fetch=lambda **kwargs: None,
        ),
    )
    providers.profiles.register(
        next(profile for profile in BUILTIN_PROFILES if profile.profile_id == "worldbank_wdi")
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(WorldBankConnector, "_request_json", staticmethod(request_json))
        patch.setattr(WorldBankConnector, "_get_session", get_session)
        with build_real_fetch_owner(
            tmp_path,
            dataset_names=("NY.GDP.MKTP.CD",),
            connector_id="worldbank.wdi",
            providers_override=providers,
            source_location="https://api.worldbank.org/v2",
            patch_fastlane=False,
            metric_id="gdp",
            dataset_records=[record],
            artifact_store=artifact_store,
        ) as owner:
            owner.plan = owner.plan.model_copy(
                update={"profile_id": "worldbank_wdi", "filters": {"country": ["US", "DE"]}}
            )
            if (
                owner.graph.bind_fetch_target(
                    metric_id=owner.plan.metric_id,
                    connector_id=owner.plan.connector_id,
                    request_dataset_id=owner.plan.dataset_id,
                    profile_id=owner.plan.profile_id,
                    filters=owner.plan.filters,
                )
                is None
            ):
                raise AssertionError("worldbank_http_plan_not_bound_by_exact_catalog_graph")
            records = [row for page in sorted(responses) for row in responses[page][1]]
            owner.frame = normalize_worldbank_records(records, "NY.GDP.MKTP.CD")
            owner.rows = owner.frame.to_dict(orient="records")
            owner.http_requests = requests
            owner.http_fixture_source = fixture_source
            owner.http_responses = responses
            owner.catalog_record = record
            yield owner


def test_real_fetch_owner_closes_graph_on_consumer_error(tmp_path):
    import duckdb

    with pytest.raises(RuntimeError, match="fixture consumer failed"):
        with build_real_fetch_owner(tmp_path) as owner:
            connection = owner.graph._store._con
            raise RuntimeError("fixture consumer failed")

    with pytest.raises(duckdb.ConnectionException):
        connection.execute("SELECT 1")


@pytest.fixture
def real_fetch_owner(tmp_path):
    with build_real_fetch_owner(tmp_path) as owner:
        yield owner


def _recorded_file_bound_plan(owner):
    """Return the existing candidate plan only after exact graph binding succeeds."""
    plan = owner.plan
    binding = owner.graph.bind_fetch_target(
        metric_id=plan.metric_id,
        connector_id=plan.connector_id,
        request_dataset_id=plan.dataset_id,
        profile_id=plan.profile_id,
        filters=plan.filters,
    )
    if binding is None:
        raise AssertionError("recorded_file_candidate_plan_not_graph_bound")
    return plan


def _execute(owner, plan=None):
    if plan is None:
        resolved = owner.service.resolve(
            DataResolveRequest(
                data_needs=[DataNeed(metric=owner.plan.metric_id)],
                mode="fastlane",
                catalog_run_profile="prod_full",
            )
        )
        plan = resolved.fetch_plans[0]
    return owner.service.execute_fetch_plans([plan], persist_payload=True).previews[0]


def _exercise_worldbank_pool_protocol(owner) -> None:
    """Reuse one real pool so its health validation and data pagination both run."""
    from polisyos.common.async_tools import run_coro_sync
    from polisyos.fabric.retrieval.executor import _fetch_request

    async def _exercise() -> None:
        registry = owner.providers.registry
        connector = registry.get("worldbank.wdi", enable_cache=False)
        config = registry.get_default_config("worldbank.wdi")
        request = _fetch_request(owner.plan, page_size=None)
        for _ in range(2):
            handle = await registry.get_connection("worldbank.wdi", config)
            try:
                await connector.fetch(handle, request)
            finally:
                await registry.release_connection("worldbank.wdi", handle)

    run_coro_sync(_exercise())


def test_fetch_executor_refuses_persistence_without_catalog_binding(real_fetch_owner, monkeypatch):
    owner = real_fetch_owner
    before_artifact_ids = set(owner.store.iter_artifact_ids())
    from polisyos.fabric.retrieval import custody

    monkeypatch.setattr(custody, "_bind_plan", lambda *_args, **_kwargs: None)
    with pytest.raises(custody.FabricFetchCustodyError) as error:
        _execute(owner)

    assert error.value.code == "catalog_fetch_target_not_admitted"
    assert any(request.page_size is None for request in owner.requests)
    assert set(owner.store.iter_artifact_ids()) == before_artifact_ids


def test_persisted_fetch_carries_complete_payload_and_actual_catalog(real_fetch_owner):
    owner = real_fetch_owner
    executed = _execute(owner)
    assert getattr(executed.metric, "fetch_receipt_ref", None) is not None
    from polisyos.core.artifacts import (
        artifact_manifest_profile_sha256,
        input_ref_from_artifact_ref,
        load_core_json_artifact,
    )
    from polisyos.fabric.retrieval.custody import FabricFetchReceipt, resolve_persisted_fetch

    receipt_ref = executed.metric.fetch_receipt_ref
    assert receipt_ref.manifest_profile_sha256 is not None
    receipt = FabricFetchReceipt.model_validate(load_core_json_artifact(owner.store, receipt_ref))
    assert receipt.result.data.manifest_profile_sha256 is not None
    assert receipt.catalog_binding_ref.manifest_profile_sha256 is not None
    receipt_manifest = owner.store.get_manifest_by_profile(
        receipt_ref.artifact_id,
        receipt_ref.manifest_profile_sha256,
    )
    assert receipt_manifest.inputs == [
        input_ref_from_artifact_ref(receipt.result.data, role="fetched_payload"),
        input_ref_from_artifact_ref(receipt.catalog_binding_ref, role="catalog_binding"),
    ]
    assert artifact_manifest_profile_sha256(receipt_manifest) == (
        receipt_ref.manifest_profile_sha256
    )

    resolved = resolve_persisted_fetch(
        store=owner.store,
        fetch_receipt_ref=executed.metric.fetch_receipt_ref,
        catalog=owner.graph,
        providers=owner.providers,
    )
    assert resolved.result.data == owner.rows
    assert resolved.result.row_count == len(owner.rows)
    assert resolved.result.bytes_transferred == 421
    assert resolved.result.quality_flags == frozenset({"recorded-test-transport"})
    assert resolved.result.data[-1]["row_id"] == "r-11"
    assert "optional" in resolved.result.data[-1] and resolved.result.data[-1]["optional"] is None
    assert resolved.used_plan.dataset_id == "primary"
    assert resolved.payload_ref == executed.metric.payload_ref == executed.payload_ref


def test_persisted_fetch_capture_owner_runs_safe_preflight_and_postflight(tmp_path):
    from polisyos.core import canon
    from polisyos.fabric.retrieval.service import (
        FetchCapturePostflightView,
        FetchCapturePreflightView,
        RetrievalService,
    )

    runtime_store = FileSystemCAS(tmp_path / "persisted-capture-operation-cas")
    with build_recorded_file_fetch_owner(
        tmp_path,
        canonicalize_catalog_source=True,
        with_catalog_profile=True,
    ) as owner:
        service = RetrievalService(
            curated_dir=tmp_path,
            artifact_store=runtime_store,
            dataset_catalog=owner.graph,
            providers=owner.providers,
        )
        plan = _recorded_file_bound_plan(owner)
        callback_order: list[str] = []
        plan_fingerprints: list[str] = []
        config_fingerprints: list[tuple[str, str | None]] = []

        def preflight(view: FetchCapturePreflightView) -> None:
            callback_order.append("preflight")
            plan_fingerprints.append(view.plan_fingerprint)
            config_fingerprints.append(
                (view.effective_config_fingerprint, view.source_profile_fingerprint)
            )
            assert owner.requests == []
            assert view.plan_id == plan.plan_id
            assert view.metric_id == plan.metric_id
            assert view.connector_id == "files.tabular"
            binding = owner.graph.bind_fetch_target(
                metric_id=plan.metric_id,
                connector_id=plan.connector_id,
                request_dataset_id=plan.dataset_id,
                profile_id=plan.profile_id,
                filters=plan.filters,
            )
            assert view.catalog_binding_fingerprint == canon.fingerprint(
                binding.model_dump(mode="json"),
                prefix=True,
                canon_spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
            )
            assert view.target_profile_id == plan.profile_id
            assert tuple(name for name, _ in view.connector_param_locators) == ("url",)
            assert view.connector_param_locators[0][1].classification == "local"
            assert view.effective_locator.local_path == str(owner.csv_path)
            assert str(owner.csv_path) not in repr(view)

        def postflight(view: FetchCapturePostflightView) -> None:
            callback_order.append("postflight")
            assert view.plan_fingerprint == plan_fingerprints[0]
            assert (
                view.effective_config_fingerprint,
                view.source_profile_fingerprint,
            ) == config_fingerprints[0]
            assert len(view.metrics) == 1
            metric = view.metrics[0]
            assert metric.plan_id == plan.plan_id
            assert metric.payload_ref is not None
            assert metric.fetch_receipt_ref is not None
            assert not hasattr(metric, "sample_rows")

        outcome = service.execute_persisted_fetch_capture(
            [plan],
            preflight=preflight,
            postflight=postflight,
        )

        assert callback_order == ["preflight", "postflight"]
        assert len(owner.requests) == 2
        assert outcome.previews[0].used_plan == plan
        assert not outcome.previews[0].fallback_used
        metric = outcome.data_context.metrics[0]
        assert metric.payload_ref is not None
        assert metric.fetch_receipt_ref is not None
        assert runtime_store.has(metric.payload_ref.artifact_id)
        assert runtime_store.has(metric.fetch_receipt_ref.artifact_id)


def test_persisted_fetch_capture_owner_rejects_non_none_preflight_result(tmp_path):
    from polisyos.fabric.retrieval.service import RetrievalService

    runtime_store = FileSystemCAS(tmp_path / "persisted-capture-veto-cas")
    with build_recorded_file_fetch_owner(
        tmp_path,
        canonicalize_catalog_source=True,
        with_catalog_profile=True,
    ) as owner:
        service = RetrievalService(
            curated_dir=tmp_path,
            artifact_store=runtime_store,
            dataset_catalog=owner.graph,
            providers=owner.providers,
        )
        plan = _recorded_file_bound_plan(owner)
        execute_calls: list[object] = []

        def trap_execute(*args: object, **kwargs: object) -> object:
            execute_calls.append((args, kwargs))
            raise AssertionError("a non-None preflight result must refuse before execution")

        service.execute_fetch_plans = trap_execute  # type: ignore[method-assign]
        with pytest.raises(ValueError, match="preflight_must_return_none"):
            service.execute_persisted_fetch_capture(
                [plan],
                preflight=lambda _view: False,
                postflight=lambda _view: None,
            )
        assert execute_calls == []
        assert runtime_store.iter_artifact_ids() == []


@pytest.mark.parametrize("reject_postflight", [False, True])
def test_persisted_fetch_capture_defers_explore_promotion_until_postflight(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    reject_postflight: bool,
) -> None:
    from polisyos.fabric.retrieval.service import RetrievalService

    monkeypatch.setenv("POLISYOS_RETRIEVAL_PROMOTION_ENABLED", "1")
    runtime_store = FileSystemCAS(tmp_path / f"promotion-capture-cas-{reject_postflight}")
    with build_recorded_file_fetch_owner(
        tmp_path,
        canonicalize_catalog_source=True,
        with_catalog_profile=True,
    ) as owner:
        service = RetrievalService(
            curated_dir=tmp_path,
            artifact_store=runtime_store,
            dataset_catalog=owner.graph,
            providers=owner.providers,
        )
        plan = _recorded_file_bound_plan(owner).model_copy(update={"source_lane": "explorelane"})

        def preflight(_view) -> None:
            assert service.list_promotion_candidates() == []

        def postflight(_view) -> None:
            assert service.list_promotion_candidates() == []
            if reject_postflight:
                raise ValueError("fixture_postflight_refused")

        if reject_postflight:
            with pytest.raises(ValueError, match="fixture_postflight_refused"):
                service.execute_persisted_fetch_capture(
                    [plan],
                    preflight=preflight,
                    postflight=postflight,
                )
            assert service.list_promotion_candidates() == []
        else:
            outcome = service.execute_persisted_fetch_capture(
                [plan],
                preflight=preflight,
                postflight=postflight,
            )
            candidates = service.list_promotion_candidates()
            assert outcome.promoted_count == 1
            assert len(candidates) == 1
            assert candidates[0].source_lane == "explorelane"
            assert candidates[0].status == "pending"


@pytest.mark.parametrize(
    "replacement",
    [None, object(), SimpleNamespace(resolve_metric_bindings=lambda *a, **k: [])],
    ids=["missing", "sentinel", "duck-typed"],
)
def test_catalog_removal_refuses_fastlane_measurement(real_fetch_owner, replacement):
    owner = real_fetch_owner
    owner.service._dataset_catalog = replacement
    with pytest.raises(ValueError, match="catalog"):
        _execute(owner)
    assert not any(request.page_size is None for request in owner.requests)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dataset_id", "invented"),
        ("connector_id", "invented"),
        ("profile_id", "invented"),
        ("metric_id", "invented"),
    ],
)
def test_unknown_catalog_tuple_refuses_real_fetch(real_fetch_owner, field, value):
    owner = real_fetch_owner
    plan = owner.plan.model_copy(update={field: value})
    if field == "connector_id":
        # Unknown connectors are refused by the preview boundary before catalog
        # binding or a full fetch; that refusal is returned as an error preview.
        artifact_ids_before = set(owner.store.iter_artifact_ids())
        outcome = _execute(owner, plan)
        assert outcome.preview.status == "error"
        assert outcome.preview.connector_id == plan.connector_id
        assert outcome.preview.message
        assert outcome.metric is None
        assert outcome.payload_ref is None
        assert outcome.fetch_receipt_ref is None
        assert owner.requests == []
        assert set(owner.store.iter_artifact_ids()) == artifact_ids_before
    else:
        with pytest.raises(ValueError, match="catalog"):
            _execute(owner, plan)
    assert not any(request.page_size is None for request in owner.requests)


def test_fallback_admits_actual_selected_catalog_target(real_fetch_owner):
    owner = real_fetch_owner
    owner.preview_reject.add("primary")
    plan = owner.plan.model_copy(
        update={
            "fallbacks": [FetchPlanFallback(connector_id="test.recorded", dataset_id="fallback")]
        }
    )
    executed = _execute(owner, plan)
    assert getattr(executed, "fetch_receipt_ref", None) is not None
    from polisyos.fabric.retrieval.custody import resolve_persisted_fetch

    resolved = resolve_persisted_fetch(
        store=owner.store,
        fetch_receipt_ref=executed.fetch_receipt_ref,
        catalog=owner.graph,
        providers=owner.providers,
    )
    assert executed.fallback_used
    assert resolved.used_plan.dataset_id == "fallback"
    assert resolved.catalog_binding.target.request_dataset_id == "fallback"


def test_fallback_cannot_reuse_primary_catalog_markers(real_fetch_owner):
    owner = real_fetch_owner
    owner.preview_reject.add("primary")
    plan = owner.plan.model_copy(
        update={
            "fallbacks": [
                FetchPlanFallback(
                    connector_id="test.recorded",
                    dataset_id="invented",
                    metadata=owner.plan.metadata,
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="catalog"):
        _execute(owner, plan)


def test_dataframe_payload_roundtrip_preserves_entire_table(real_fetch_owner):
    owner = real_fetch_owner
    frame = pd.DataFrame(owner.rows).set_index("row_id")
    owner.payload["value"] = frame
    executed = _execute(owner)
    assert getattr(executed, "fetch_receipt_ref", None) is not None
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.fabric.retrieval.custody import (
        FabricFetchReceipt,
        _encode_payload,
        resolve_persisted_fetch,
    )

    receipt = FabricFetchReceipt.model_validate(
        load_core_json_artifact(owner.store, executed.fetch_receipt_ref)
    )
    assert receipt.payload_encoding == "pandas_arrow_ipc"
    encoded, _, _ = _encode_payload(frame)
    assert owner.store.get_bytes(receipt.result.data) == encoded
    resolved = resolve_persisted_fetch(
        store=owner.store,
        fetch_receipt_ref=executed.fetch_receipt_ref,
        catalog=owner.graph,
        providers=owner.providers,
    )
    pd.testing.assert_frame_equal(resolved.result.data, frame)


def test_arrow_table_payload_roundtrip_preserves_entire_table(real_fetch_owner: Any) -> None:
    import pyarrow as pa

    owner = real_fetch_owner
    table = pa.Table.from_pylist(owner.rows)
    owner.payload["value"] = table
    executed = _execute(owner)
    assert getattr(executed, "fetch_receipt_ref", None) is not None
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.fabric.retrieval.custody import (
        FabricFetchReceipt,
        _encode_payload,
        resolve_persisted_fetch,
    )

    receipt = FabricFetchReceipt.model_validate(
        load_core_json_artifact(owner.store, executed.fetch_receipt_ref)
    )
    assert receipt.payload_encoding == "arrow_ipc"
    encoded, _, _ = _encode_payload(table)
    assert owner.store.get_bytes(receipt.result.data) == encoded
    resolved = resolve_persisted_fetch(
        store=owner.store,
        fetch_receipt_ref=executed.fetch_receipt_ref,
        catalog=owner.graph,
        providers=owner.providers,
    )
    assert isinstance(resolved.result.data, pa.Table)
    assert resolved.result.data.equals(table)
    assert resolved.result.data.schema.equals(table.schema, check_metadata=True)
    assert resolved.replayed_result.data.equals(table)


def test_json_object_payload_roundtrip_preserves_complete_mapping(real_fetch_owner: Any) -> None:
    owner = real_fetch_owner
    data = {"records": owner.rows}
    owner.payload["value"] = data
    executed = _execute(owner)
    assert executed.fetch_receipt_ref is not None
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.fabric.retrieval.custody import (
        FabricFetchReceipt,
        _encode_payload,
        resolve_persisted_fetch,
    )

    receipt = FabricFetchReceipt.model_validate(
        load_core_json_artifact(owner.store, executed.fetch_receipt_ref)
    )
    assert receipt.payload_encoding == "canonical_json"
    encoded, media_type, encoding = _encode_payload(data)
    assert media_type == "application/json"
    assert encoding == "canonical_json"
    assert owner.store.get_bytes(receipt.result.data) == encoded
    resolved = resolve_persisted_fetch(
        store=owner.store,
        fetch_receipt_ref=executed.fetch_receipt_ref,
        catalog=owner.graph,
        providers=owner.providers,
    )
    assert resolved.result.data == data
    assert resolved.replayed_result.data == data


def _copy_artifact(store, original_ref, payload, *, inputs=None, profiled=True):
    from polisyos.core import canon
    from polisyos.core.artifacts import PutOptions

    manifest = store.get_manifest(original_ref.artifact_id)
    options = PutOptions(
        kind=manifest.kind,
        media_type=manifest.media_type,
        schema=manifest.artifact_schema,
        producer=manifest.producer,
        inputs=manifest.inputs if inputs is None else inputs,
    )
    if manifest.media_type == "application/json" and profiled:
        return store.put_json(
            canon.from_canonical_bytes(payload),
            options,
            canon_spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
            return_selected_profile=True,
        )
    return store.put_bytes(payload, options, return_selected_profile=profiled)


@pytest.mark.parametrize("mutation", ["tail_value", "stable_metadata", "source_changed"])
def test_real_connector_readback_refuses_complete_counterfeit_chain(tmp_path, mutation):
    from polisyos.core import canon
    from polisyos.core.artifacts import input_ref_from_artifact_ref
    from polisyos.fabric.retrieval import custody

    with build_recorded_file_fetch_owner(tmp_path) as owner:
        executed = _execute(owner, owner.plan)
        receipt = custody.FabricFetchReceipt.model_validate(
            canon.from_canonical_bytes(
                owner.store.get_bytes(executed.fetch_receipt_ref.artifact_id)
            )
        )
        receipt_ref = executed.fetch_receipt_ref
        if mutation == "source_changed":
            changed = owner.frame.copy()
            changed.loc[11, "value"] = 999.5
            changed.to_csv(owner.csv_path, index=False)
        elif mutation == "tail_value":
            frame = custody._decode_payload(
                owner.store.get_bytes(receipt.result.data.artifact_id), receipt.payload_encoding
            )
            frame.loc[11, "value"] = 999.5
            raw, _, _ = custody._encode_payload(frame)
            payload_ref = _copy_artifact(owner.store, receipt.result.data, raw)
            receipt = receipt.model_copy(
                update={"result": receipt.result.model_copy(update={"data": payload_ref})}
            )
        else:
            receipt = receipt.model_copy(
                update={
                    "result": receipt.result.model_copy(
                        update={"quality_flags": frozenset({"fabricated-quality"})}
                    )
                }
            )
        if mutation != "source_changed":
            receipt_ref = _copy_artifact(
                owner.store,
                executed.fetch_receipt_ref,
                canon.to_canonical_bytes(
                    receipt.model_dump(mode="json"),
                    spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
                ),
                inputs=[
                    input_ref_from_artifact_ref(receipt.result.data, role="fetched_payload"),
                    input_ref_from_artifact_ref(
                        receipt.catalog_binding_ref, role="catalog_binding"
                    ),
                ],
            )
        with pytest.raises(ValueError, match="source_changed"):
            custody.resolve_persisted_fetch(
                store=owner.store,
                fetch_receipt_ref=receipt_ref,
                catalog=owner.graph,
                providers=owner.providers,
            )


def test_json_payload_storage_uses_the_encoded_snapshot_when_source_mutates(tmp_path, monkeypatch):
    from polisyos.core import canon
    from polisyos.fabric.retrieval import custody

    with build_real_fetch_owner(tmp_path) as owner:
        source_rows = [{"row_id": "captured-row", "value": 1.5}]
        owner.payload["value"] = source_rows
        encoded_snapshots: list[bytes] = []
        mutated_data: list[Any] = []
        original_encode = custody._encode_payload

        def _encode_then_mutate(data):
            encoded = original_encode(data)
            if (
                isinstance(data, list)
                and data
                and isinstance(data[0], dict)
                and data[0].get("row_id") == "captured-row"
            ):
                assert encoded[1] == "application/json"
                encoded_snapshots.append(encoded[0])
                data[0]["value"] = 999.5
                mutated_data.append(data)
            return encoded

        monkeypatch.setattr(custody, "_encode_payload", _encode_then_mutate)
        executed = _execute(owner, owner.plan)
        assert executed.fetch_receipt_ref is not None
        assert len(encoded_snapshots) == 1
        assert len(mutated_data) == 1
        assert mutated_data[0][0]["value"] == 999.5

        receipt = custody.FabricFetchReceipt.model_validate(
            canon.from_canonical_bytes(
                owner.store.get_bytes(executed.fetch_receipt_ref.artifact_id)
            )
        )
        stored_payload = owner.store.get_bytes(receipt.result.data.artifact_id)
        assert stored_payload == encoded_snapshots[0]
        assert canon.from_canonical_bytes(stored_payload) == [
            {"row_id": "captured-row", "value": 1.5}
        ]


def test_profileless_json_payload_is_not_reclassified_as_verified(tmp_path):
    from polisyos.core import canon
    from polisyos.core.artifacts import input_ref_from_artifact_ref
    from polisyos.fabric.retrieval import custody

    with build_recorded_file_fetch_owner(tmp_path) as owner:
        executed = _execute(owner, owner.plan)
        assert executed.fetch_receipt_ref is not None
        receipt = custody.FabricFetchReceipt.model_validate(
            canon.from_canonical_bytes(
                owner.store.get_bytes(executed.fetch_receipt_ref.artifact_id)
            )
        )
        payload = owner.store.get_bytes(receipt.result.data.artifact_id)
        profileless_payload = _copy_artifact(
            owner.store, receipt.result.data, payload, inputs=[], profiled=False
        )
        assert profileless_payload.manifest_profile_sha256 is None
        receipt = receipt.model_copy(
            update={"result": receipt.result.model_copy(update={"data": profileless_payload})}
        )
        receipt_ref = _copy_artifact(
            owner.store,
            executed.fetch_receipt_ref,
            canon.to_canonical_bytes(
                receipt.model_dump(mode="json"),
                spec=canon.CanonSpec(forbid_floats=False, exclude_none=False),
            ),
            inputs=[
                input_ref_from_artifact_ref(profileless_payload, role="fetched_payload"),
                input_ref_from_artifact_ref(receipt.catalog_binding_ref, role="catalog_binding"),
            ],
        )

        with pytest.raises(
            custody.FabricFetchCustodyError, match="fabric_fetch_profile_unverified"
        ):
            custody.resolve_persisted_fetch(
                store=owner.store,
                fetch_receipt_ref=receipt_ref,
                catalog=owner.graph,
                providers=owner.providers,
            )


@pytest.mark.parametrize("source", ["baseline", "previously_absent_overlay"])
def test_graph_session_cannot_sign_new_unread_source_bytes(real_fetch_owner, source):
    owner = real_fetch_owner
    path = owner.graph_path if source == "baseline" else owner.overlay_path
    with path.open("ab") as handle:
        handle.write(b"new bytes not consumed by the open catalog read session")
    with pytest.raises(ValueError, match="catalog"):
        _execute(owner)


def test_tail_secret_blocks_full_payload_before_any_cas_emission(real_fetch_owner):
    owner = real_fetch_owner
    owner.rows[-1]["access_token"] = "real-sensitive-value-12345678"
    with pytest.raises(ValueError, match="secret|pii"):
        _execute(owner)
    assert not list(owner.cas_root.rglob("*.blob"))


def test_payload_row_count_is_recomputed_before_persistence(real_fetch_owner):
    owner = real_fetch_owner
    owner.result_updates["row_count"] = len(owner.rows) + 1
    with pytest.raises(ValueError, match="row_count"):
        _execute(owner)


def test_data_only_new_catalog_target_is_admitted_beyond_search_top_three(tmp_path):
    names = tuple(f"dataset-{index}" for index in range(7))
    with build_real_fetch_owner(tmp_path, dataset_names=names) as owner:
        executed = _execute(owner, owner.plan.model_copy(update={"dataset_id": names[-1]}))
        from polisyos.fabric.retrieval.custody import resolve_persisted_fetch

        resolved = resolve_persisted_fetch(
            store=owner.store,
            fetch_receipt_ref=executed.fetch_receipt_ref,
            catalog=owner.graph,
            providers=owner.providers,
        )
        assert resolved.catalog_binding.target.request_dataset_id == names[-1]


def test_real_connector_recomputes_full_current_source_and_preserves_raw_capture(tmp_path):
    import hashlib

    from polisyos.fabric.retrieval.custody import resolve_persisted_fetch

    with build_recorded_file_fetch_owner(tmp_path) as owner:
        executed = _execute(owner, owner.plan)
        resolved = resolve_persisted_fetch(
            store=owner.store,
            fetch_receipt_ref=executed.fetch_receipt_ref,
            catalog=owner.graph,
            providers=owner.providers,
        )
        pd.testing.assert_frame_equal(resolved.result.data, owner.frame)
        pd.testing.assert_frame_equal(resolved.replayed_result.data, resolved.result.data)
        digest = "sha256:" + hashlib.sha256(owner.csv_path.read_bytes()).hexdigest()
        assert resolved.result.version.content_hash == digest
        assert resolved.result.data.attrs["lineage"]["content_hash"] == digest
        assert resolved.replayed_result.fetched_at > resolved.result.fetched_at
        assert resolved.checked_at >= resolved.replayed_result.fetched_at
        assert resolved.source_agreement == "recomputed"


def _catalog_request(owner, **updates):
    return {
        "metric_id": owner.plan.metric_id,
        "connector_id": owner.plan.connector_id,
        "request_dataset_id": owner.plan.dataset_id,
        "profile_id": owner.plan.profile_id,
        "filters": dict(owner.plan.filters),
        **updates,
    }


def test_bulk_catalog_owner_preserves_full_order_and_refuses_novel_tuple(real_fetch_owner):
    owner = real_fetch_owner
    requests = [_catalog_request(owner), _catalog_request(owner, request_dataset_id="invented")]
    outcomes = owner.graph.bind_fetch_targets(requests)
    assert [item.status for item in outcomes] == ["bound", "not_admitted"]
    assert [item.request.request_dataset_id for item in outcomes] == ["primary", "invented"]
    assert outcomes[0].binding == owner.graph.bind_fetch_target(**requests[0])
    assert outcomes[1].binding is None


def test_bulk_catalog_owner_returns_nothing_on_mid_read_source_change(
    real_fetch_owner, monkeypatch
):
    owner = real_fetch_owner
    store = owner.graph._store
    actual = store.resolve_metric_bindings

    def changed(*args, **kwargs):
        values = actual(*args, **kwargs)
        owner.graph_path.write_bytes(owner.graph_path.read_bytes() + b"changed-after-read")
        return values

    monkeypatch.setattr(store, "resolve_metric_bindings", changed)
    from polisyos.data_forge.domains.catalog.knowledge.derivation_catalog_selection import (
        CatalogSelectionError,
    )

    with pytest.raises(CatalogSelectionError) as raised:
        owner.graph.bind_fetch_targets([_catalog_request(owner)])
    assert raised.value.code == "catalog_read_session_stale"
    assert raised.value.detail == "catalog_read_session_stale"
    assert owner.graph_path.read_bytes().endswith(b"changed-after-read")


def test_bulk_catalog_owner_data_only_growth_uses_same_single_admission(tmp_path):
    with build_real_fetch_owner(
        tmp_path, dataset_names=("primary", "new-recorded-target")
    ) as owner:
        requests = [
            _catalog_request(owner),
            _catalog_request(owner, request_dataset_id="new-recorded-target"),
        ]
        outcomes = owner.graph.bind_fetch_targets(requests)
        assert [item.status for item in outcomes] == ["bound", "bound"]
        assert [item.binding for item in outcomes] == [
            owner.graph.bind_fetch_target(**req) for req in requests
        ]


def test_bulk_catalog_owner_types_unreadable_rows_as_ambiguous(tmp_path):
    import duckdb

    with build_real_fetch_owner(tmp_path) as owner:
        owner.graph.close()
        with duckdb.connect(str(owner.graph_path)) as connection:
            connection.execute(
                "UPDATE ds_metric_bindings SET default_filters = ? WHERE dataset_id = ?",
                ['{"country": "not-a-list"}', "catalog-primary"],
            )
        with_graph = catalog_api.DatasetCatalogGraph(owner.graph_path, tmp_path)
        try:
            outcome = with_graph.bind_fetch_targets([_catalog_request(owner)])[0]
            assert outcome.status == "ambiguous"
            assert outcome.binding is None
            assert "ValidationError" in outcome.reason
        finally:
            with_graph.close()


def test_explicit_metric_binding_admits_its_real_nonpreferred_distribution(tmp_path):
    import duckdb

    with build_real_fetch_owner(tmp_path) as owner:
        owner.graph.close()
        with duckdb.connect(str(owner.graph_path)) as connection:
            connection.execute(
                "INSERT INTO ds_distributions SELECT * REPLACE (? AS id, ? AS source_locator) "
                "FROM ds_distributions WHERE id = ?",
                ["nonpreferred-real", "alternate", "distribution-primary"],
            )
            connection.execute(
                "INSERT INTO ds_metric_bindings SELECT * REPLACE (? AS distribution_id, "
                "? AS request_dataset_id) FROM ds_metric_bindings WHERE dataset_id = ?",
                ["nonpreferred-real", "alternate", "catalog-primary"],
            )
        graph = catalog_api.DatasetCatalogGraph(owner.graph_path, tmp_path)
        try:
            bound = graph.bind_fetch_target(
                **_catalog_request(owner, request_dataset_id="alternate")
            )
            assert bound.target.distribution_id == "nonpreferred-real"
            assert bound.binding.distribution_id == "nonpreferred-real"
            assert (
                graph.resolve_fetch_target("catalog-primary").distribution_id
                == "distribution-primary"
            )
        finally:
            graph.close()


def _build_full_published_catalog_fixture(tmp_path, monkeypatch):
    """Reuse the existing owner-complete publisher fixture by its canonical path."""
    import importlib.util
    import sys

    fixture_path = Path(__file__).parents[1] / "runtime" / "http" / "_published_catalog_fixture.py"
    module_name = "_e02_fetch_custody_published_catalog_fixture"
    spec = importlib.util.spec_from_file_location(module_name, fixture_path)
    if spec is None or spec.loader is None:
        raise AssertionError("complete published catalog fixture module spec is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.build_published_catalog_fixture(tmp_path, monkeypatch)


def test_worldbank_fixture_current_catalog_receipt_admits_its_exact_fetch_plan(
    tmp_path, monkeypatch
):
    fixture = _build_full_published_catalog_fixture(tmp_path, monkeypatch)
    try:
        service = RetrievalService(
            curated_dir=tmp_path / "curated",
            dataset_catalog=fixture.producer_graph,
            profiles=fixture.profile_registry,
        )
        resolved = service.resolve(
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
        assert fixture.report_basis_state == "current"
        assert fixture.publish_receipt_state == "current"
        assert fixture.readiness["consumer_ready"] is True
        assert len(resolved.fetch_plans) == 1
        assert len(resolved.candidates) == 1
        assert resolved.candidates[0].metadata["source_currentness"] == "current"
        assert (
            resolved.candidates[0].metadata["plan_admission_reason"]
            == "catalog_profile_inputs_covered"
        )
        plan = resolved.fetch_plans[0]
        assert plan.connector_id == "worldbank.wdi"
        assert plan.dataset_id == "scope_dataset"
        assert plan.profile_id == "worldbank_wdi"
    finally:
        fixture.producer_graph.close()
        fixture.close()


def test_worldbank_connector_replays_existing_http_fixture_through_real_owner(tmp_path):
    from polisyos.fabric.retrieval.custody import resolve_persisted_fetch

    with build_worldbank_fetch_owner(tmp_path) as owner:
        executed = _execute(owner, owner.plan)
        before = tuple(owner.http_requests)
        resolved = resolve_persisted_fetch(
            store=owner.store,
            fetch_receipt_ref=executed.fetch_receipt_ref,
            catalog=owner.graph,
            providers=owner.providers,
        )
        pd.testing.assert_frame_equal(resolved.result.data, owner.frame)
        pd.testing.assert_frame_equal(resolved.replayed_result.data, owner.frame)
        replayed_requests = owner.http_requests[len(before) :]
        assert [request.kind for request in replayed_requests] == ["health", "data", "data"]
        health = replayed_requests[0]
        data = replayed_requests[1:]
        assert health.params == {"format": "json", "per_page": "1"}
        assert "page" not in health.params
        assert [request.params["page"] for request in data] == ["1", "2"]
        assert all(request.response in owner.http_responses.values() for request in data)
        assert all(request.headers["ETag"] == '"wdi-etag-1"' for request in replayed_requests)
        assert resolved.used_plan.connector_id == "worldbank.wdi"
        assert resolved.used_plan.dataset_id == "NY.GDP.MKTP.CD"


def test_worldbank_fixture_distinguishes_pool_health_from_paginated_data(tmp_path):
    """Witness one pool health check and two complete paginated data fetches."""
    with build_worldbank_fetch_owner(tmp_path) as owner:
        start = len(owner.http_requests)
        _exercise_worldbank_pool_protocol(owner)
        exchanges = owner.http_requests[start:]

        assert [exchange.kind for exchange in exchanges] == [
            "health",
            "data",
            "data",
            "data",
            "data",
        ]
        health = [exchange for exchange in exchanges if exchange.kind == "health"]
        data = [exchange for exchange in exchanges if exchange.kind == "data"]
        assert len(health) == 1
        assert all(exchange.params == {"format": "json", "per_page": "1"} for exchange in health)
        assert all("page" not in exchange.params for exchange in health)
        assert [exchange.params["page"] for exchange in data] == ["1", "2", "1", "2"]
        assert all("page" in exchange.params for exchange in data)
        assert all(exchange.response is not None and exchange.headers for exchange in exchanges)


@pytest.mark.parametrize(
    "variant",
    [
        "valid",
        "null_values",
        "wrong_schema",
        "missing_registry",
        "fake_registry",
        "missing_contract",
    ],
)
def test_current_registry_validates_full_result_without_fetch_or_mutation(tmp_path, variant):
    from polisyos.fabric.connectors.contracts import ContractRegistry
    from polisyos.fabric.retrieval.custody import resolve_persisted_fetch

    with build_worldbank_fetch_owner(tmp_path) as owner:
        executed = _execute(owner, owner.plan)
        resolved = resolve_persisted_fetch(
            store=owner.store,
            fetch_receipt_ref=executed.fetch_receipt_ref,
            catalog=owner.graph,
            providers=owner.providers,
        )
        result = resolved.replayed_result
        if variant == "null_values":
            frame = result.data.copy()
            frame["value"] = float("nan")
            result = result.model_copy(update={"data": frame})
        elif variant == "wrong_schema":
            result = result.model_copy(update={"schema_id": "fabricated.schema"})
        elif variant == "missing_registry":
            owner.providers.registry.configure_contracts(None)
        elif variant == "fake_registry":
            owner.providers.registry.configure_contracts(
                SimpleNamespace(resolve=lambda *args: None)
            )
        elif variant == "missing_contract":
            owner.providers.registry.configure_contracts(ContractRegistry())
        registry = owner.providers.registry
        configuration = (registry._contract_registry, registry._contract_validation_mode)
        before = tuple(owner.http_requests)
        validation = registry.validate_fetch_result(
            connector_id="worldbank.wdi", dataset_id="NY.GDP.MKTP.CD", result=result
        )
        assert tuple(owner.http_requests) == before
        assert (registry._contract_registry, registry._contract_validation_mode) == configuration
        if variant == "valid":
            assert validation.errors == ()
        else:
            assert validation.errors
        if variant in {"valid", "null_values", "wrong_schema"}:
            contract = configuration[0].resolve("worldbank.wdi", "NY.GDP.MKTP.CD")
            assert validation.contract_id == contract.contract_id
            assert validation.contract_version == str(contract.schema_version)
            assert validation.contract_content_hash == contract.content_hash
        else:
            assert validation.contract_id is None
            assert validation.contract_version is None
            assert validation.contract_content_hash is None
        if variant == "null_values":
            assert any("field 'value' completeness" in error for error in validation.errors)
        if variant == "wrong_schema":
            assert any("schema_id" in error for error in validation.errors)


def test_fetch_executor_keeps_supplied_tenant_store_for_persist_and_readback(tmp_path):
    """The exact runtime tenant view owns both fetch writes and later resolution."""
    root_store = FileSystemCAS(tmp_path / "shared-cas")
    runtime_store = root_store.for_tenant("tenant-a", cell_id="cell-a")
    foreign_store = root_store.for_tenant("tenant-b", cell_id="cell-b")

    with build_real_fetch_owner(tmp_path, artifact_store=runtime_store) as owner:
        assert owner.service.artifact_store is runtime_store
        executed = _execute(owner)
        assert executed.fetch_receipt_ref is not None
        assert executed.payload_ref is not None
        assert runtime_store.has(executed.fetch_receipt_ref)
        assert runtime_store.has(executed.payload_ref)
        assert not foreign_store.has(executed.fetch_receipt_ref)
        with pytest.raises(PermissionError, match="not readable by tenant"):
            foreign_store.get_bytes(executed.fetch_receipt_ref.artifact_id)

        from polisyos.fabric.retrieval.custody import resolve_persisted_fetch

        resolved = resolve_persisted_fetch(
            store=owner.service.artifact_store,
            fetch_receipt_ref=executed.fetch_receipt_ref,
            catalog=owner.graph,
            providers=owner.providers,
        )
        assert resolved.result.data == owner.rows
        assert resolved.payload_ref == executed.payload_ref


def test_fetch_executor_local_config_remains_a_standalone_control(tmp_path):
    """An explicit local store config preserves the standalone capture lane."""
    from polisyos.core.artifacts.backends.config import ArtifactStoreConfig

    configured_store = ArtifactStoreConfig(
        backend="filesystem", root=str(tmp_path / "standalone-cas")
    )
    with build_real_fetch_owner(
        tmp_path,
        artifact_store_config=configured_store,
    ) as owner:
        executed = _execute(owner)
        assert executed.fetch_receipt_ref is not None
        assert owner.service.artifact_store is owner.store
        assert owner.store.artifact_store_config() == configured_store
        assert owner.store.has(executed.fetch_receipt_ref)


def test_persisted_fetch_replay_uses_one_atomic_current_profile_snapshot(tmp_path, monkeypatch):
    from polisyos.fabric.connectors.sources import file_tabular
    from polisyos.fabric.retrieval.custody import resolve_persisted_fetch
    from polisyos.fabric.retrieval.executor import FetchExecutor

    with build_recorded_file_fetch_owner(
        tmp_path, canonicalize_catalog_source=True, with_catalog_profile=True
    ) as owner:
        executed = _execute(owner, _recorded_file_bound_plan(owner))
        assert executed.fetch_receipt_ref is not None
        profile = owner.providers.profiles.get("recorded_file_local")
        assert profile is not None
        alternate_path = tmp_path / "replay-profile-replacement.csv"
        alternate_path.write_bytes(owner.csv_path.read_bytes())
        observed_urls: list[str] = []
        original_read = file_tabular.read_location_bytes

        async def _record_read(config, *args, **kwargs):
            observed_urls.append(config.url)
            return await original_read(config, *args, **kwargs)

        monkeypatch.setattr(file_tabular, "read_location_bytes", _record_read)
        original_bind = FetchExecutor._bind_execution
        profile_replaced = False

        def _bind_then_replace(executor, plan):
            nonlocal profile_replaced
            binding = original_bind(executor, plan)
            if executor._profiles is owner.providers.profiles and not profile_replaced:
                owner.providers.profiles.register(
                    profile.model_copy(update={"base_url": str(alternate_path)}),
                    override=True,
                )
                profile_replaced = True
            return binding

        monkeypatch.setattr(FetchExecutor, "_bind_execution", _bind_then_replace)
        resolved = resolve_persisted_fetch(
            store=owner.store,
            fetch_receipt_ref=executed.fetch_receipt_ref,
            catalog=owner.graph,
            providers=owner.providers,
        )

        assert profile_replaced
        # FileTabularConnector reads once for health_check and once for fetch;
        # both operations must retain the one config captured before replacement.
        assert observed_urls
        assert set(observed_urls) == {str(owner.csv_path)}
        assert resolved.source_agreement == "recomputed"
        assert resolved.fetch_receipt_ref == executed.fetch_receipt_ref


def test_worldbank_fetch_owner_persists_into_the_supplied_cas(tmp_path: Path) -> None:
    """The recorded connector's real fetch receipts use the selected store."""
    store = FileSystemCAS(tmp_path / "selected-cas")
    with build_worldbank_fetch_owner(tmp_path / "capture", artifact_store=store) as owner:
        assert owner.store is store
        resolved = owner.service.resolve(
            DataResolveRequest(
                data_needs=[DataNeed(metric=owner.plan.metric_id)],
                mode="fastlane",
                catalog_run_profile="prod_full",
            )
        )
        result = owner.service.execute_fetch_plans(
            list(resolved.fetch_plans), persist_payload=True, allow_fallback=False
        )
        assert len(result.previews) == 1
        preview = result.previews[0]
        assert preview.fetch_receipt_ref is not None
        assert preview.metric.payload_ref is not None
        assert store.get_bytes(preview.fetch_receipt_ref)
        assert store.get_bytes(preview.metric.payload_ref)

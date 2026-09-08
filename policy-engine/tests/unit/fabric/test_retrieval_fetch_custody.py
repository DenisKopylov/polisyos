"""Behavioral custody tests across the real catalog and fetch executor."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

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
):
    """Use a real graph, with only the connector transport controlled."""
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
    overlay_path = tmp_path / "overlay.duckdb"
    graph = catalog_api.DatasetCatalogGraph(graph_path, tmp_path, overlay_path=overlay_path)
    rows = [{"row_id": f"r-{index}", "value": index + 0.5, "optional": None} for index in range(12)]
    requests = []
    preview_reject = set()
    payload = {"value": rows}
    result_updates = {}

    class Connector:
        async def fetch(self, handle, request):
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
                completeness=0.0
                if request.page_size and request.dataset_id in preview_reject
                else 1.0,
                quality_flags=frozenset({"recorded-test-transport"}),
                total_count=count,
                bytes_transferred=421,
            ).model_copy(update=result_updates)

    class Registry:
        def get(self, connector_id, *, enable_cache=False):
            return Connector()

        def get_default_config(self, connector_id):
            return ConnectionConfig(url="https://transport.invalid/recorded")

        async def get_connection(self, connector_id, config):
            return object()

        async def release_connection(self, connector_id, handle):
            pass

    providers = providers_override or RetrievalProviders(
        registry=Registry(),
        profiles=SimpleNamespace(get=lambda _: None),
        tracer=SimpleNamespace(start_as_current_span=lambda *args, **kwargs: nullcontext()),
        metrics=SimpleNamespace(
            record_fabric_query=lambda **kwargs: None,
            record_fabric_connector_fetch=lambda **kwargs: None,
        ),
    )
    plan = FetchPlan(
        plan_id="plan-primary",
        metric_id=metric_id,
        connector_id=connector_id,
        dataset_id=dataset_names[0],
        quality_min=0.5,
        source_lane="fastlane",
        metadata={"resolution_route": "catalog", "catalog_discovered": True},
    )
    service = RetrievalService(
        curated_dir=tmp_path, cas_root=tmp_path / "cas", dataset_catalog=graph, providers=providers
    )
    if patch_fastlane:
        service._fastlane.resolve = lambda needs: FastLaneResolveResult(
            fetch_plans=(plan,), candidates=(), warnings=()
        )
    yield SimpleNamespace(
        service=service,
        graph=graph,
        graph_path=graph_path,
        plan=plan,
        rows=rows,
        requests=requests,
        payload=payload,
        preview_reject=preview_reject,
        store=FileSystemCAS(tmp_path / "cas"),
        providers=providers,
        curated_dir=tmp_path,
        cas_root=tmp_path / "cas",
        overlay_path=overlay_path,
        result_updates=result_updates,
    )
    graph.close()


@contextmanager
def build_recorded_file_fetch_owner(tmp_path):
    """Run the actual registered FileTabularConnector against a local CSV."""
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.fabric.connectors.registry import ConnectorRegistry
    from polisyos.fabric.connectors.sources.file_tabular import FileTabularConnector

    tmp_path.mkdir(parents=True, exist_ok=True)
    csv_path = tmp_path / "recorded.csv"
    frame = pd.DataFrame(
        {"row_id": [f"r-{i}" for i in range(12)], "value": [i + 0.5 for i in range(12)]}
    )
    frame.to_csv(csv_path, index=False)
    registry = ConnectorRegistry()
    registry.register(FileTabularConnector, config=ConnectionConfig(url=str(csv_path)))
    providers = RetrievalProviders(
        registry=registry,
        profiles=SourceProfileRegistry(),
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
    ) as owner:
        owner.csv_path = csv_path
        owner.frame = frame
        owner.rows = frame.to_dict(orient="records")
        yield owner


@contextmanager
def build_worldbank_fetch_owner(tmp_path):
    """Use the committed WDI HTTP fixture through the actual registered owner.

    The fixture remains a transport instrument: its USA/DEU GDP identities are
    preserved, and it is never relabeled as the Ukraine credit population.
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
    requests = []
    raw_rows = [row for page in sorted(responses) for row in responses[page][1]]
    indicator_ids = {row["indicator"]["id"] for row in raw_rows}
    assert indicator_ids == {"NY.GDP.MKTP.CD"}
    indicator_names = {row["indicator"]["value"] for row in raw_rows}
    assert len(indicator_names) == 1
    # The catalog's existing WDI owner supplies license, parser/readiness and
    # annual frequency; the complete recorded response supplies exact coverage.
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
                dist.model_copy(
                    update={
                        "default_filters": {"country": ["US", "DE"]},
                    }
                )
                for dist in record.distributions
            ],
        }
    )

    async def request_json(_session, url, *, params, connector_id):
        assert connector_id == "worldbank.wdi"
        assert url.endswith("/indicator/NY.GDP.MKTP.CD")
        requests.append((url, dict(params)))
        body = responses[int(params["page"])]
        return (
            body,
            {"ETag": '"wdi-etag-1"', "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT"},
            json.dumps(body).encode(),
        )

    async def get_session(self, _handle):
        return object()

    registry = ConnectorRegistry()
    registry.register(
        WorldBankConnector, config=ConnectionConfig(url="https://api.worldbank.org/v2")
    )
    providers = RetrievalProviders(
        registry=registry,
        profiles=SourceProfileRegistry(),
        tracer=SimpleNamespace(start_as_current_span=lambda *a, **k: nullcontext()),
        metrics=SimpleNamespace(
            record_fabric_query=lambda **kwargs: None,
            record_fabric_connector_fetch=lambda **kwargs: None,
        ),
    )
    providers.profiles.register(
        next(p for p in BUILTIN_PROFILES if p.profile_id == "worldbank_wdi")
    )
    tmp_path.mkdir(parents=True, exist_ok=True)
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
        ) as owner:
            owner.plan = owner.plan.model_copy(
                update={"profile_id": "worldbank_wdi", "filters": {"country": ["US", "DE"]}}
            )
            records = [row for page in sorted(responses) for row in responses[page][1]]
            owner.frame = normalize_worldbank_records(records, "NY.GDP.MKTP.CD")
            owner.rows = owner.frame.to_dict(orient="records")
            owner.http_requests = requests
            owner.http_fixture_source = fixture_source
            owner.http_responses = responses
            owner.catalog_record = record
            yield owner


@pytest.fixture
def real_fetch_owner(tmp_path):
    with build_real_fetch_owner(tmp_path) as owner:
        yield owner


def _execute(owner, plan=None):
    resolved = owner.service.resolve(
        DataResolveRequest(data_needs=[DataNeed(metric=owner.plan.metric_id)], mode="fastlane")
    )
    return owner.service.execute_fetch_plans(
        [plan or resolved.fetch_plans[0]], persist_payload=True
    ).previews[0]


def test_persisted_fetch_carries_complete_payload_and_actual_catalog(real_fetch_owner):
    owner = real_fetch_owner
    executed = _execute(owner)
    assert getattr(executed.metric, "fetch_receipt_ref", None) is not None
    from polisyos.fabric.retrieval.custody import resolve_persisted_fetch

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
    with pytest.raises(ValueError, match="catalog"):
        _execute(owner, owner.plan.model_copy(update={field: value}))
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
    from polisyos.fabric.retrieval.custody import resolve_persisted_fetch

    resolved = resolve_persisted_fetch(
        store=owner.store,
        fetch_receipt_ref=executed.fetch_receipt_ref,
        catalog=owner.graph,
        providers=owner.providers,
    )
    pd.testing.assert_frame_equal(resolved.result.data, frame)


def _copy_artifact(store, original_ref, payload, *, inputs=None):
    from polisyos.core.artifacts import PutOptions

    manifest = store.get_manifest(original_ref.artifact_id)
    return store.put_bytes(
        payload,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            inputs=manifest.inputs if inputs is None else inputs,
        ),
    )


@pytest.mark.parametrize("mutation", ["tail_value", "stable_metadata", "source_changed"])
def test_real_connector_readback_refuses_complete_counterfeit_chain(tmp_path, mutation):
    from polisyos.core import canon
    from polisyos.core.artifacts import InputRef
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
                    InputRef(artifact_id=receipt.result.data.artifact_id, role="fetched_payload"),
                    InputRef(
                        artifact_id=receipt.catalog_binding_ref.artifact_id, role="catalog_binding"
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
    with pytest.raises(ValueError, match="catalog_fetch_source_changed"):
        owner.graph.bind_fetch_targets([_catalog_request(owner)])


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
        assert owner.http_requests[len(before) :] == list(before[-2:])
        assert resolved.used_plan.connector_id == "worldbank.wdi"
        assert resolved.used_plan.dataset_id == "NY.GDP.MKTP.CD"


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

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from polisyos.fabric.connectors import contract_for_family
from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.event_stream import EventStreamConnector
from polisyos.fabric.connectors.sources.file_tabular import FileTabularConnector
from polisyos.fabric.connectors.sources.geojson import GeoJSONConnector
from polisyos.fabric.connectors.sources.graphql_api import GraphQLConnector
from polisyos.fabric.connectors.sources.object_storage import ObjectStorageConnector
from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector


@pytest.fixture(autouse=True)
def _reset_registries():
    ConnectorRegistry.reset_instance()
    SourceProfileRegistry.reset_instance()
    yield
    ConnectorRegistry.reset_instance()
    SourceProfileRegistry.reset_instance()


@pytest.mark.parametrize(
    ("family", "connector_id"),
    [
        ("files", "files.tabular"),
        ("object_storage", "object_storage.blob"),
        ("sql", "sql.query"),
        ("graphql", "graphql.api"),
        ("geojson", "geojson.features"),
        ("stream", "stream.jsonl"),
    ],
)
def test_family_contracts_align_with_registry_and_profiles(family: str, connector_id: str):
    registry = ConnectorRegistry.get_instance()
    profiles = SourceProfileRegistry.get_instance()

    assert registry.has(connector_id)
    assert profiles.list_by_family(family)

    connector = registry.get(connector_id)
    contract = contract_for_family(family)
    for capability in contract.required_capabilities:
        assert connector.capabilities & capability


@pytest.mark.asyncio
async def test_file_tabular_connector_fetches_csv_and_introspects_schema(tmp_path: Path):
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("country,value\nUA,1\nDE,2\n", encoding="utf-8")

    connector = FileTabularConnector()
    handle = await connector.connect(
        ConnectionConfig(url=str(csv_path), headers={"X-File-Format": "csv"})
    )
    result = await connector.fetch(handle, FetchRequest(dataset_id="sample"))
    schema = await connector.get_dataset_schema(handle, "sample")
    await connector.disconnect(handle)

    assert result.row_count == 2
    assert schema["schema_id"] == "files.tabular.sample"
    assert schema["format"] == "csv"


@pytest.mark.asyncio
async def test_object_storage_connector_preserves_provider_metadata(tmp_path: Path):
    csv_path = tmp_path / "object.csv"
    csv_path.write_text("id,value\n1,10\n", encoding="utf-8")
    url = csv_path.as_uri()

    connector = ObjectStorageConnector()
    handle = await connector.connect(ConnectionConfig(url=url, headers={"X-File-Format": "csv"}))
    result = await connector.fetch(handle, FetchRequest(dataset_id="object"))
    schema = await connector.get_dataset_schema(handle, "object")
    await connector.disconnect(handle)

    assert result.row_count == 1
    assert result.data.attrs["lineage"]["provider"] == "file"
    assert schema["provider"] == "file"
    assert schema["object_key"].endswith("object.csv")


@pytest.mark.asyncio
async def test_sql_query_connector_fetches_sqlite_and_lists_tables(tmp_path: Path):
    db_path = tmp_path / "demo.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE demo_table (id INTEGER, value TEXT)")
        conn.executemany("INSERT INTO demo_table VALUES (?, ?)", [(1, "a"), (2, "b")])
        conn.commit()
    finally:
        conn.close()

    connector = SQLQueryConnector()
    handle = await connector.connect(
        ConnectionConfig(
            url=f"sqlite:///{db_path}",
            headers={"X-SQL-Table": "demo_table"},
        )
    )
    datasets = [dataset async for dataset in connector.list_datasets(handle)]
    result = await connector.fetch(handle, FetchRequest(dataset_id="demo_table"))
    schema = await connector.get_dataset_schema(handle, "demo_table")
    await connector.disconnect(handle)

    assert any(dataset.dataset_id == "demo_table" for dataset in datasets)
    assert result.row_count == 2
    assert schema["table"] == "demo_table"


@pytest.mark.asyncio
async def test_graphql_connector_fetches_query_and_introspects_schema(unused_tcp_port: int):
    import aiohttp.web

    async def handler(request):
        body = await request.json()
        assert "query" in body
        return aiohttp.web.json_response(
            {"data": {"items": [{"id": "a", "value": 1}, {"id": "b", "value": 2}]}}
        )

    app = aiohttp.web.Application()
    app.router.add_post("/graphql", handler)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, "127.0.0.1", unused_tcp_port)
    await site.start()

    connector = GraphQLConnector()
    handle = await connector.connect(
        ConnectionConfig(
            url=f"http://127.0.0.1:{unused_tcp_port}/graphql",
            headers={
                "X-GraphQL-Query": "query Demo { items { id value } }",
                "X-GraphQL-DataPath": "data.items",
            },
        )
    )
    try:
        result = await connector.fetch(handle, FetchRequest(dataset_id="demo"))
        schema = await connector.get_dataset_schema(handle, "demo")
    finally:
        await connector.disconnect(handle)
        await runner.cleanup()

    assert result.row_count == 2
    assert schema["endpoint"].endswith("/graphql")
    assert schema["fields"][0]["name"] == "id"


@pytest.mark.asyncio
async def test_geojson_connector_preserves_crs_and_lineage(tmp_path: Path):
    geojson_path = tmp_path / "sample.geojson"
    geojson_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {"type": "name", "properties": {"name": "EPSG:3857"}},
                "features": [
                    {
                        "type": "Feature",
                        "id": "f1",
                        "properties": {"name": "Kyiv"},
                        "geometry": {"type": "Point", "coordinates": [30.52, 50.45]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    connector = GeoJSONConnector()
    handle = await connector.connect(ConnectionConfig(url=geojson_path.as_uri()))
    result = await connector.fetch(handle, FetchRequest(dataset_id="feature_collection"))
    schema = await connector.get_dataset_schema(handle, "feature_collection")
    await connector.disconnect(handle)

    assert result.row_count == 1
    assert result.data.attrs["spatial_metadata"]["crs"] == "EPSG:3857"
    assert schema["spatial_metadata"]["geometry_types"] == ["Point"]
    assert schema["lineage"]["source_location"].endswith("sample.geojson")


@pytest.mark.asyncio
async def test_event_stream_connector_streams_messages_and_schema(tmp_path: Path):
    stream_path = tmp_path / "events.jsonl"
    stream_path.write_text(
        "\n".join(
            [
                json.dumps({"kind": "created", "value": 1}),
                json.dumps({"kind": "updated", "value": 2}),
                json.dumps({"kind": "deleted", "value": 3}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    connector = EventStreamConnector()
    handle = await connector.connect(
        ConnectionConfig(
            url=stream_path.as_uri(),
            headers={"X-Stream-ChunkSize": "2", "X-Stream-Topic": "audit-events"},
        )
    )
    chunks = [
        chunk
        async for chunk in connector.fetch_stream(handle, FetchRequest(dataset_id="audit-events"))
    ]
    result = await connector.fetch(handle, FetchRequest(dataset_id="audit-events"))
    schema = await connector.get_dataset_schema(handle, "audit-events")
    await connector.disconnect(handle)

    assert len(chunks) == 2
    assert chunks[0].row_count == 2
    assert result.row_count == 3
    assert schema["subject_or_topic"] == "audit-events"
    assert len(schema["message_ids"]) == 3

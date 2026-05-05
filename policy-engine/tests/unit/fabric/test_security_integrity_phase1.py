from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.contracts.schema import (
    DataSchema,
    FieldSpec,
    SchemaType,
    SchemaVersion,
)
from polisyos.fabric.connectors.http_limits import read_bounded_response_body
from polisyos.fabric.connectors.reference.rest_json import GenericRESTConnector
from polisyos.fabric.connectors.reference.sdmx import SDMXConnector
from polisyos.fabric.connectors.sources._file_common import read_location_bytes
from polisyos.fabric.connectors.sources.graphql_api import GraphQLConnector
from polisyos.fabric.connectors.sources.opendatasoft import OpendatasoftConnector
from polisyos.fabric.connectors.sources.socrata import SocrataConnector
from polisyos.fabric.connectors.sources.sparql import SPARQLConnector
from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
from polisyos.fabric.connectors.types import FetchError
from polisyos.fabric.quality import compute_quality_indicators
from polisyos.fabric.safety import FabricSafetyError, UnsafePathSegmentError

REPO_ROOT = Path(__file__).resolve().parents[2]
FABRIC_ROOT = REPO_ROOT / "src" / "polisyos" / "fabric"

REVIEWED_RAW_SQL_INTERPOLATION_SITES = {
    "src/polisyos/fabric/claims/conflicts/detect.py": {
        "c399b5a31c8db8ae": "variable placeholder count only; values are parameterized",
    },
    "src/polisyos/fabric/claims/conflicts/resolve.py": {
        "1f716a5d17a09b2a": "variable placeholder count only; values are parameterized",
        "323887071583a3a7": "variable placeholder count only; values are parameterized",
        "440f34b3cbf71bb3": "variable placeholder count only; values are parameterized",
        "7638f54b2c7b532d": "variable placeholder count only; values are parameterized",
        "d7e0df7eca15b34e": "variable placeholder count only; values are parameterized",
        "db3d521f0a3c4d6e": "variable placeholder count only; values are parameterized",
    },
    "src/polisyos/fabric/connectors/cache/_store_index.py": {
        "2dd7efbd0ca4c789": "where fragments are assembled from fixed predicates with parameters",
        "8b2dfae046738d31": "where fragments are assembled from fixed predicates with parameters",
    },
    "src/polisyos/fabric/connectors/contracts/_schema_core.py": {
        "131e23b5bd481082": "schema DDL compiler quotes table identifiers",
    },
    "src/polisyos/fabric/connectors/contracts/evolution.py": {
        "1a7fbf48a8327c09": "schema evolution DDL compiler validates table and field identifiers",
        "517127080e03e2c4": "schema evolution DDL compiler validates table and field identifiers",
        "53f41563966125dd": "schema evolution DDL compiler validates table and field identifiers",
        "59bea8d3500c5ff2": "schema evolution DDL compiler validates table and field identifiers",
        "05c247bcddf829cd": "schema evolution DDL compiler validates table and field identifiers",
    },
    "src/polisyos/fabric/connectors/sources/sql_query.py": {
        "3ddd1fd10f41b8d6": "table identifier is quoted by Fabric safety helper",
    },
    "src/polisyos/fabric/storage/duckdb_adapter.py": {
        "8cd5eeb809f92422": "identifiers are regex-validated and quoted before interpolation",
    },
    "src/polisyos/fabric/world/materialize/duckdb.py": {
        "16d7a6e83921ed7d": "projection tables are validated/quoted before interpolation",
        "26a9762532f8d336": "temporary table name is generated and used read-only",
        "7a231523251aa5b5": "projection tables are validated/quoted before interpolation",
        "80ad2357732201d0": "projection tables are validated/quoted before interpolation",
        "9c8a59900c89ccf7": "world migration table and column identifiers are validated/quoted",
        "ee5e8aa8c3261e75": "projection tables are validated/quoted before interpolation",
    },
    "src/polisyos/fabric/world/materialize/kuzu.py": {
        "74a58da5fc860b72": "Kuzu table identifier is validated and CSV path is quoted",
    },
    "src/polisyos/fabric/world/materialize/projections.py": {
        "1e9a2d229f2c2814": "temporary tables and columns are generated or quoted",
        "1ec5647776b1f979": "temporary tables and columns are generated or quoted",
        "244115796b2e5947": "temporary tables are generated and registered internally",
        "8ff7f363e4c9d90a": "temporary tables are generated and registered internally",
        "a42606df3c99edfe": "temporary tables are generated and registered internally",
        "a7d8f141575c3889": "temporary tables are generated and registered internally",
        "ae78379a63661624": "temporary tables are generated and registered internally",
        "bcdca1705dd514d8": "temporary table is generated and registered internally",
        "c8ee3ae2768cd962": "temporary tables are generated and registered internally",
    },
    "src/polisyos/fabric/world/materialize/sql.py": {
        "1d8472965fa8c6f4": "internal SQL templates compose fixed Fabric world DDL/DML",
        "34ef96fe23793fdf": "internal SQL templates compose fixed Fabric world DDL/DML",
        "6d45c2e30d11c83b": "internal SQL templates compose fixed Fabric world DDL/DML",
        "85bc27ec9f37387a": "internal SQL templates compose fixed Fabric world DDL/DML",
        "8b4240f5f9a84f50": "internal SQL templates compose fixed Fabric world DDL/DML",
        "deaa8ac71057781e": "internal SQL templates compose fixed Fabric world DDL/DML",
        "e1142f31413815c0": "internal SQL templates compose fixed Fabric world DDL/DML",
        "e62d158b9d32a778": "internal SQL templates compose fixed Fabric world DDL/DML",
    },
    "src/polisyos/fabric/world/store/snapshots.py": {
        "0f74d87a62ae6af2": "world table identifiers are validated/quoted",
        "1720efc5689addfd": "world table/column identifiers are validated or quoted",
        "80ad2357732201d0": "world table identifiers are validated/quoted",
        "b0ee9b648f705282": "table name is validated before SQL literal use",
        "e9148995f139df78": "world table/column identifiers are validated or quoted",
    },
    "src/polisyos/fabric/world_query.py": {
        "155b6c18f9428940": "world query identifiers are fixed aliases or validated columns",
        "7825470ae136d982": "world query identifiers are fixed aliases or validated columns",
        "af93334b4f42f6e1": "world table/column identifiers are allow-listed or validated",
    },
}


class _FakeResponse:
    def __init__(
        self,
        *,
        body: bytes = b"{}",
        headers: dict[str, str] | None = None,
        status: int = 200,
    ) -> None:
        self.status = status
        self.headers = headers or {}
        self._body = body

    async def read(self) -> bytes:
        return self._body

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def test_bounded_response_reader_rejects_content_length_over_limit() -> None:
    async def _exercise() -> None:
        response = _FakeResponse(headers={"Content-Length": "11"})
        with pytest.raises(FetchError, match="safe limit"):
            await read_bounded_response_body(
                response,
                connector_id="test.connector",
                url="https://example.test/data",
                max_response_bytes=10,
                max_decompressed_bytes=10,
            )

    import asyncio

    asyncio.run(_exercise())


@pytest.mark.asyncio
async def test_file_location_rejects_traversal_and_oversized_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="traversal"):
        await read_location_bytes(
            ConnectionConfig(url="../secret.csv", headers={"X-File-Format": "csv"})
        )

    csv_path = tmp_path / "oversized.csv"
    csv_path.write_text("id,value\n1,10\n", encoding="utf-8")
    with pytest.raises(ValueError, match="safe byte limit"):
        await read_location_bytes(
            ConnectionConfig(
                url=str(csv_path),
                headers={"X-File-Format": "csv", "X-File-MaxBytes": "4"},
            )
        )


@pytest.mark.asyncio
async def test_rest_json_rejects_oversized_json_body() -> None:
    connector = GenericRESTConnector()
    handle = await connector.connect(
        ConnectionConfig(
            url="https://example.test/api",
            headers={"X-REST-MaxResponseBytes": "4", "X-REST-DataPath": "data"},
        )
    )

    class _FakeSession:
        def get(self, *_args: object, **_kwargs: object) -> _FakeResponse:
            return _FakeResponse(body=b'{"data":[]}', headers={"Content-Length": "11"})

    try:
        with pytest.raises(FetchError, match="safe limit"):
            await connector._request_page_raw(
                handle,
                _FakeSession(),  # type: ignore[arg-type]
                "https://example.test/api",
                {},
            )
    finally:
        await connector.disconnect(handle)


@pytest.mark.asyncio
async def test_rest_json_rejects_repeated_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    connector = GenericRESTConnector()
    handle = await connector.connect(
        ConnectionConfig(
            url="https://example.test/api",
            headers={
                "X-REST-Pagination": "cursor",
                "X-REST-DataPath": "data",
                "X-REST-CursorPath": "next",
            },
        )
    )
    calls = 0

    async def _fake_get_session(_handle: Any) -> object:
        return object()

    async def _fake_request_page_raw(
        _handle: Any,
        _session: object,
        _url: str,
        _params: dict[str, Any],
        _headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, str], int]:
        nonlocal calls
        calls += 1
        payload = {"data": [{"id": calls}], "next": "same-cursor"}
        raw = json.dumps(payload).encode("utf-8")
        return {"json": payload, "_raw": raw, "headers": {}}, {}, len(raw)

    monkeypatch.setattr(connector, "_get_session", _fake_get_session)
    monkeypatch.setattr(connector, "_request_page_raw", _fake_request_page_raw)

    try:
        with pytest.raises(FetchError, match="repeated cursor"):
            await connector.fetch(handle, FetchRequest(dataset_id="cursor_fixture"))
    finally:
        await connector.disconnect(handle)


def test_malicious_query_filter_fixtures_are_rejected() -> None:
    with pytest.raises(FabricSafetyError):
        SocrataConnector._build_soql_params(
            FetchRequest(dataset_id="x", filters=(("field; DROP TABLE rows", ("a",)),))
        )

    with pytest.raises(FabricSafetyError):
        OpendatasoftConnector._build_where(
            FetchRequest(dataset_id="x", filters=(("field OR 1=1", ("a",)),))
        )

    with pytest.raises(UnsafePathSegmentError):
        SDMXConnector._build_filter_path(
            FetchRequest(dataset_id="x", filters=(("geo", ("../UA",)),))
        )

    sql_result = SQLQueryConnector.validate_config(
        ConnectionConfig(
            url="sqlite:///tmp/demo.sqlite",
            headers={"X-SQL-Query": "SELECT * FROM safe_table; DROP TABLE safe_table"},
        )
    )
    assert not sql_result.valid
    assert any(issue.field == "X-SQL-Query" for issue in sql_result.issues)


def test_schema_sql_builders_reject_unsafe_table_identifiers() -> None:
    schema = DataSchema(
        schema_id="phase1.sql_fixture",
        version=SchemaVersion(1, 0, 0),
        fields=(FieldSpec(name="safe_column", data_type=SchemaType.INT64),),
    )

    with pytest.raises(FabricSafetyError):
        schema.to_duckdb_create_table("safe_table; DROP TABLE world_facts")


@pytest.mark.asyncio
async def test_sparql_fetch_rejects_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SPARQLConnector()
    template = {"fixture": "SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"}
    handle = await connector.connect(
        ConnectionConfig(
            url="https://query.example.test",
            headers={"X-SPARQL-QueryTemplates": json.dumps(template)},
        )
    )

    class _FakeSession:
        def post(self, *_args: object, **_kwargs: object) -> _FakeResponse:
            return _FakeResponse(
                body=b"{}",
                headers={
                    "Content-Length": str(connector.resilience_profile.max_response_bytes + 1)
                },
            )

    async def _fake_get_session(_self: SPARQLConnector, _handle: Any) -> _FakeSession:
        return _FakeSession()

    monkeypatch.setattr(SPARQLConnector, "_get_session", _fake_get_session)
    try:
        with pytest.raises(FetchError, match="safe limit"):
            await connector.fetch(handle, FetchRequest(dataset_id="fixture"))
    finally:
        await connector.disconnect(handle)


def test_graphql_bound_headers_are_validated() -> None:
    result = GraphQLConnector.validate_config(
        ConnectionConfig(
            url="https://example.test/graphql",
            headers={
                "X-GraphQL-Query": "query { node }",
                "X-GraphQL-MaxJsonBytes": "0",
            },
        )
    )
    assert not result.valid
    assert any(issue.field == "X-GraphQL-MaxJsonBytes" for issue in result.issues)


def test_non_finite_numeric_values_are_typed_missingness_not_silent_score() -> None:
    indicators = compute_quality_indicators(
        pd.DataFrame({"a": [1.0, float("inf")], "b": [3.0, 4.0]}),
        metric_id="non_finite_fixture",
    )
    assert indicators.missingness == pytest.approx(0.25)


def test_fabric_datetime_calls_are_utc_aware() -> None:
    violations: list[str] = []
    for path in sorted(FABRIC_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "utcnow":
                violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
            if isinstance(func, ast.Attribute) and func.attr == "fromtimestamp":
                has_tz = any(keyword.arg == "tz" for keyword in node.keywords)
                if not has_tz:
                    violations.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert violations == []


def test_raw_sql_interpolation_sites_are_reviewed() -> None:
    sql_tokens = (
        "SELECT ",
        "DELETE ",
        "INSERT ",
        "CREATE ",
        "DROP ",
        "COPY ",
        "PRAGMA ",
        "ALTER ",
    )
    unreviewed: list[str] = []
    for path in sorted(FABRIC_ROOT.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.JoinedStr):
                continue
            segment = ast.get_source_segment(source, node) or ""
            upper = segment.upper()
            if not any(token in upper for token in sql_tokens):
                continue
            if "COMPONENT MUST CREATE CONNECTOR" in upper:
                continue
            if "FAILED TO EXPORT CSV VIA DUCKDB COPY" in upper:
                continue
            if "UNKNOWN COPY POLICY" in upper:
                continue
            rel_path = str(path.relative_to(REPO_ROOT))
            normalized = re.sub(r"\s+", " ", segment).strip()
            fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
            reason = REVIEWED_RAW_SQL_INTERPOLATION_SITES.get(rel_path, {}).get(fingerprint, "")
            if not reason:
                unreviewed.append(f"{rel_path}:{node.lineno}:{fingerprint}")
    assert unreviewed == []

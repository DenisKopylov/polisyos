"""Tests for SPARQLConnector."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from polisyos.fabric.connectors.base import ConnectionConfig, FetchRequest
from polisyos.fabric.connectors.sources.sparql import _MAX_LIMIT, SPARQLConnector
from polisyos.fabric.connectors.types import FetchError
from polisyos.fabric.quality.safety import UnsafeFilterExpressionError
from polisyos.ir.connectors import ConnectorCapability

FIXTURES_DIR = (
    Path(__file__).resolve().parents[4] / "_data" / "fabric" / "connectors" / "sources" / "sparql"
)


def _run_async(coro):
    return asyncio.run(coro)


def _load_fixture(name: str):
    return json.loads((FIXTURES_DIR / name).read_text())


def _sparql_config(*, templates: dict[str, str] | None = None) -> ConnectionConfig:
    headers: dict[str, str] = {}
    if templates:
        headers["X-SPARQL-QueryTemplates"] = json.dumps(templates)
    headers.setdefault("X-SPARQL-AllowInlineQuery", "false")
    return ConnectionConfig(url="https://query.wikidata.org", headers=headers)


# ---------------------------------------------------------------------------
# Mock helpers for SPARQL POST requests
# ---------------------------------------------------------------------------


def _make_mock_session(fixture_body):
    """Create a mock aiohttp session that returns fixture_body for POST."""
    raw = json.dumps(fixture_body).encode("utf-8")

    class _FakeResponse:
        status = 200
        headers = {"ETag": '"sparql-etag-1"'}

        async def read(self):
            return raw

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class _FakeSession:
        def post(self, url, **kwargs):
            return _FakeResponse()

        async def close(self):
            pass

        @property
        def closed(self):
            return False

    return _FakeSession()


def _fake_get_session_factory(fixture_body):
    session = _make_mock_session(fixture_body)

    async def _fake(self, _handle):
        return session

    return _fake


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class TestSPARQLMetadata:
    def test_connector_id(self):
        assert SPARQLConnector.connector_id == "sparql.endpoint"

    def test_capabilities(self):
        caps = SPARQLConnector.capabilities
        assert caps & ConnectorCapability.FULL_FETCH
        assert caps & ConnectorCapability.DIMENSION_FILTER

    def test_validate_config_missing_url(self):
        config = ConnectionConfig(url="")
        result = SPARQLConnector.validate_config(config)
        assert not result.valid

    def test_validate_config_ok(self):
        config = ConnectionConfig(url="https://query.wikidata.org")
        result = SPARQLConnector.validate_config(config)
        assert result.valid


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


class TestSPARQLConfig:
    def test_parse_query_templates(self):
        templates = {"countries": "SELECT ?c WHERE { ?c a dbo:Country } LIMIT 10"}
        config = _sparql_config(templates=templates)
        result = SPARQLConnector._get_query_templates(config)
        assert "countries" in result
        assert "SELECT" in result["countries"]

    def test_empty_templates(self):
        config = _sparql_config()
        result = SPARQLConnector._get_query_templates(config)
        assert result == {}

    def test_default_graph(self):
        config = ConnectionConfig(
            url="https://example.test",
            headers={"X-SPARQL-DefaultGraph": "http://dbpedia.org"},
        )
        assert SPARQLConnector._get_default_graph(config) == "http://dbpedia.org"


# ---------------------------------------------------------------------------
# Query resolution
# ---------------------------------------------------------------------------


class TestQueryResolution:
    def test_resolve_from_template(self):
        connector = SPARQLConnector()

        async def _exercise():
            config = _sparql_config(
                templates={"countries": "SELECT ?c WHERE { ?c a dbo:Country } LIMIT 10"}
            )
            handle = await connector.connect(config)
            req = FetchRequest(dataset_id="countries")
            query = SPARQLConnector._resolve_query(handle, req)
            await connector.disconnect(handle)
            return query

        query = _run_async(_exercise())
        assert "SELECT ?c" in query

    def test_resolve_inline_query(self):
        connector = SPARQLConnector()

        async def _exercise():
            handle = await connector.connect(
                ConnectionConfig(
                    url="https://query.wikidata.org",
                    headers={"X-SPARQL-AllowInlineQuery": "true"},
                )
            )
            req = FetchRequest(dataset_id="SELECT ?s WHERE { ?s ?p ?o } LIMIT 5")
            query = SPARQLConnector._resolve_query(handle, req)
            await connector.disconnect(handle)
            return query

        query = _run_async(_exercise())
        assert query == "SELECT ?s WHERE { ?s ?p ?o } LIMIT 5"

    def test_resolve_with_parameter_substitution(self):
        connector = SPARQLConnector()

        async def _exercise():
            config = _sparql_config(
                templates={"by_type": "SELECT ?s WHERE { ?s a {{iri:type}} } LIMIT 100"}
            )
            handle = await connector.connect(config)
            req = FetchRequest(
                dataset_id="by_type",
                filters=(("type", ("dbo:Country",)),),
            )
            query = SPARQLConnector._resolve_query(handle, req)
            await connector.disconnect(handle)
            return query

        query = _run_async(_exercise())
        assert "dbo:Country" in query
        assert "{{iri:type}}" not in query

    def test_resolve_with_literal_substitution_escapes_quotes(self):
        connector = SPARQLConnector()

        async def _exercise():
            config = _sparql_config(
                templates={
                    "by_label": "SELECT ?s WHERE { ?s rdfs:label {{literal:label}}@en } LIMIT 10"
                }
            )
            handle = await connector.connect(config)
            req = FetchRequest(
                dataset_id="by_label",
                filters=(("label", ('A" OR ?s ?p ?o',)),),
            )
            query = SPARQLConnector._resolve_query(handle, req)
            await connector.disconnect(handle)
            return query

        query = _run_async(_exercise())
        assert '"A\\" OR ?s ?p ?o"' in query

    def test_resolve_rejects_legacy_untyped_placeholders(self):
        connector = SPARQLConnector()

        async def _exercise():
            config = _sparql_config(
                templates={"legacy": "SELECT ?s WHERE { ?s a {{type}} } LIMIT 10"}
            )
            handle = await connector.connect(config)
            req = FetchRequest(
                dataset_id="legacy",
                filters=(("type", ("dbo:Country",)),),
            )
            SPARQLConnector._resolve_query(handle, req)

        with pytest.raises(
            UnsafeFilterExpressionError,
            match="must declare an explicit kind",
        ):
            _run_async(_exercise())

    def test_resolve_unknown_template_raises(self):
        connector = SPARQLConnector()

        async def _exercise():
            handle = await connector.connect(_sparql_config())
            req = FetchRequest(dataset_id="nonexistent_template")
            SPARQLConnector._resolve_query(handle, req)

        with pytest.raises(FetchError, match="No SPARQL query template"):
            _run_async(_exercise())

    def test_resolve_rejects_unexpected_filters(self):
        connector = SPARQLConnector()

        async def _exercise():
            config = _sparql_config(
                templates={"countries": "SELECT ?c WHERE { ?c a dbo:Country } LIMIT 10"}
            )
            handle = await connector.connect(config)
            req = FetchRequest(
                dataset_id="countries",
                filters=(("country", ("UA",)),),
            )
            SPARQLConnector._resolve_query(handle, req)

        with pytest.raises(
            UnsafeFilterExpressionError,
            match="does not declare placeholders",
        ):
            _run_async(_exercise())


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------


class TestGuardrails:
    def test_adds_limit_if_missing(self):
        query = "SELECT ?s WHERE { ?s ?p ?o }"
        result = SPARQLConnector._apply_guardrails(query)
        assert f"LIMIT {_MAX_LIMIT}" in result

    def test_preserves_existing_small_limit(self):
        query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 50"
        result = SPARQLConnector._apply_guardrails(query)
        assert "LIMIT 50" in result

    def test_caps_excessive_limit(self):
        query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 999999"
        result = SPARQLConnector._apply_guardrails(query)
        assert f"LIMIT {_MAX_LIMIT}" in result


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


class TestSPARQLParsing:
    def test_parse_select_results(self):
        fixture = _load_fixture("select_response.json")
        df = SPARQLConnector._parse_sparql_results(fixture)
        assert len(df) == 2
        assert "country" in df.columns
        assert "population" in df.columns
        assert "label" in df.columns
        assert df["label"].tolist() == ["United States", "Germany"]

    def test_parse_empty_bindings(self):
        body = {"results": {"bindings": []}}
        df = SPARQLConnector._parse_sparql_results(body)
        assert df.empty


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------


class TestSPARQLFetch:
    def test_fetch_with_template(self, monkeypatch):
        connector = SPARQLConnector()
        fixture = _load_fixture("select_response.json")
        monkeypatch.setattr(
            SPARQLConnector,
            "_get_session",
            _fake_get_session_factory(fixture),
        )

        async def _exercise():
            config = _sparql_config(
                templates={
                    "countries": "SELECT ?country ?population ?label WHERE { ?country a dbo:Country } LIMIT 10"
                }
            )
            handle = await connector.connect(config)
            request = FetchRequest(dataset_id="countries")
            result = await connector.fetch(handle, request)
            await connector.disconnect(handle)
            return result

        result = _run_async(_exercise())
        assert result.row_count == 2
        assert "country" in result.data.columns
        assert result.schema_id == "sparql.endpoint.countries"


# ---------------------------------------------------------------------------
# List datasets (templates)
# ---------------------------------------------------------------------------


class TestSPARQLListDatasets:
    def test_list_templates(self):
        connector = SPARQLConnector()

        async def _exercise():
            config = _sparql_config(
                templates={
                    "countries": "SELECT ...",
                    "cities": "SELECT ...",
                }
            )
            handle = await connector.connect(config)
            datasets = []
            async for ds in connector.list_datasets(handle):
                datasets.append(ds)
            await connector.disconnect(handle)
            return datasets

        datasets = _run_async(_exercise())
        assert len(datasets) == 2
        ids = {d.dataset_id for d in datasets}
        assert "countries" in ids
        assert "cities" in ids


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestSPARQLHealth:
    def test_health_ok(self, monkeypatch):
        connector = SPARQLConnector()

        class _FakeOKResp:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

        class _FakeSession:
            def post(self, url, **kwargs):
                return _FakeOKResp()

            async def close(self):
                pass

            @property
            def closed(self):
                return False

        async def _fake_session(self, _handle):
            return _FakeSession()

        monkeypatch.setattr(SPARQLConnector, "_get_session", _fake_session)

        async def _exercise():
            handle = await connector.connect(_sparql_config())
            status = await connector.health_check(handle)
            await connector.disconnect(handle)
            return status

        status = _run_async(_exercise())
        assert status.healthy is True

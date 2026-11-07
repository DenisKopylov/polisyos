from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CoreSourcesCompatibilityContext,
    ObservationPlan,
    bind_core_sources_compatibility_context,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import (
    loaders,
    registry,
    transformers,
    validators,
    writers,
)


def test_core_sources_writers_keep_memory_limit_formatting() -> None:
    assert writers._format_duckdb_memory_limit(1024 * 1024 * 1024) == "1024MB"


def test_canonical_leaves_work_before_legacy_facade_in_fresh_process() -> None:
    script = """
import sys
import duckdb
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import ObservationPlan
from polisyos.data_forge.domains.catalog.batch.core_sources import loaders, registry, validators, writers

facade_name = "polisyos.data_forge.domains.catalog.batch.core_sources_ingest"
assert facade_name not in sys.modules
plan = ObservationPlan(
    dataset_id="fixture", source="worldbank", raw_variable="value", canonical_var="gdp",
    connector_id="worldbank.wdi", profile_id="worldbank_wdi", request_dataset_id="WDI",
    default_filters={}, update_frequency="annual",
)
requests = validators._chunked_observation_requests(
    plan=plan, filters=(), source="worldbank", start_year=2020, end_year=2020,
)
assert len(requests) == 1 and requests[0].dataset_id == "WDI"
assert (requests[0].date_start.year, requests[0].date_end.year) == (2020, 2020)
assert loaders._bulk_country_values("ilo", ("UA",)) == ["UKR"]
with duckdb.connect(":memory:") as connection:
    registry._ensure_registry_tables(connection)
    rows = [{"country_code": "UA", "year": 2020, "value": 3.5}]
    initial = writers._insert_generic_observations(con=connection, plan=plan, rows=rows)
    assert (initial.attempted, initial.inserted, initial.replaced) == (1, 1, 0)
    observation_id = connection.execute("SELECT observation_id FROM ds_observations").fetchone()[0]
    assert loaders._existing_observation_ids(connection, [observation_id]) == {observation_id}
    assert facade_name not in sys.modules
    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
    facade._unregistered_dependency = object()
    facade._sync_implementation_globals()
    assert all("_unregistered_dependency" not in leaf.__dict__ for leaf in (writers, validators, loaders))
    repeated = writers._insert_generic_observations(con=connection, plan=plan, rows=rows)
    assert (repeated.attempted, repeated.inserted, repeated.replaced) == (1, 0, 1)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_insert_generic_observations_uses_request_scoped_batch_size(monkeypatch, tmp_path) -> None:
    database = tmp_path / "observations.duckdb"
    connection = duckdb.connect(str(database))
    registry._ensure_registry_tables(connection)
    chunk_lengths: list[int] = []
    original_chunker = loaders._iter_chunked_values

    def _record_chunks(values, chunk_size):
        for chunk in original_chunker(values, chunk_size):
            chunk_lengths.append(len(chunk))
            yield chunk

    plan = ObservationPlan(
        dataset_id="dataset",
        source="worldbank",
        raw_variable="value",
        canonical_var="gdp",
        connector_id="worldbank.wdi",
        profile_id="worldbank_wdi",
        request_dataset_id="NY.GDP.MKTP.CD",
        default_filters={"sex": ["T"], "unit": ["USD"]},
        update_frequency="annual",
    )
    rows = [
        {
            "country_code": "UA",
            "year": 2020,
            "value": float(index),
            "partner": f"P{index}",
            "sex": "T",
            "unit": "USD",
        }
        for index in range(5)
    ]
    requests = validators._chunked_observation_requests(
        plan=plan,
        filters=tuple((key, tuple(value)) for key, value in plan.default_filters.items()),
        source=plan.source,
        start_year=2020,
        end_year=2020,
    )
    assert len(requests) == 1
    assert requests[0].dataset_id == "NY.GDP.MKTP.CD"
    assert requests[0].filters == (("sex", ("T",)), ("unit", ("USD",)))
    assert requests[0].date_start == datetime(2020, 1, 1, tzinfo=UTC)
    assert requests[0].date_end == datetime(2020, 12, 31, tzinfo=UTC)
    context = CoreSourcesCompatibilityContext(
        {(writers.__name__, "_OBSERVATION_INSERT_BATCH_SIZE"): 2}
    )

    try:
        connection.execute("BEGIN TRANSACTION")
        existing = writers._insert_generic_observations(
            con=connection,
            plan=plan,
            rows=[{**rows[0], "value": -1.0}],
            acquisition_method="earlier",
        )
        assert (existing.attempted, existing.inserted, existing.replaced) == (1, 1, 0)
        monkeypatch.setattr(writers, "_iter_chunked_values", _record_chunks)
        with bind_core_sources_compatibility_context(context):
            stats = writers._insert_generic_observations(
                con=connection,
                plan=plan,
                rows=rows,
                acquisition_method="connector",
                source_watermark="fixture-watermark",
                dataset_version="fixture-v2",
            )

        connection.execute("COMMIT")
        assert chunk_lengths == [2, 2, 1]
        assert (stats.attempted, stats.inserted, stats.replaced) == (5, 4, 1)
    finally:
        connection.close()

    expected = []
    for index in range(5):
        condition = json.dumps(
            {"partner": f"P{index}", "sex": "T", "unit": "USD"},
            sort_keys=True,
            separators=(",", ":"),
        )
        condition_digest = hashlib.sha256(condition.encode()).hexdigest()[:12]
        identity = f"dataset|value|gdp|UA|2020|None|None|{condition_digest}"
        observation_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
        expected.append(
            (
                observation_id,
                "dataset",
                "value",
                "gdp",
                "UA",
                2020,
                None,
                None,
                float(index),
                condition,
                "connector",
                "fixture-watermark",
                "fixture-v2",
            )
        )
    with duckdb.connect(str(database), read_only=True) as fresh:
        actual = fresh.execute(
            "SELECT observation_id, dataset_id, raw_variable, canonical_var, country_code, "
            "year, survey_year, wave, value, condition_json, acquisition_method, "
            "source_watermark, dataset_version FROM ds_observations ORDER BY condition_json"
        ).fetchall()
        assert actual == expected
        assert len({row[0] for row in actual}) == 5
        assert loaders._existing_observation_ids(fresh, [row[0] for row in expected]) == {
            row[0] for row in expected
        }


def test_writer_resolves_transformer_dependency_without_facade_bootstrap(monkeypatch) -> None:
    monkeypatch.delattr(writers, "_normalize_observation_row", raising=False)
    monkeypatch.setattr(
        transformers,
        "_normalize_observation_row",
        lambda _row: ("UA", 2020, None, None, 1.5, "{}"),
    )
    monkeypatch.setattr(writers, "_observation_id", lambda *args, **kwargs: "obs-1", raising=False)
    monkeypatch.setattr(
        writers, "_existing_observation_ids", lambda _con, _ids: set(), raising=False
    )
    monkeypatch.setattr(
        writers,
        "_iter_chunked_values",
        lambda values, _size: [list(values)],
        raising=False,
    )

    class _FakeConnection:
        def __init__(self) -> None:
            self.rows: list[tuple] = []

        def executemany(self, _sql: str, values: list[tuple]) -> None:
            self.rows.extend(values)

    plan = ObservationPlan(
        dataset_id="dataset",
        source="ilo",
        raw_variable="value",
        canonical_var="employment",
        connector_id="sdmx.source",
        profile_id="ilo_sdmx",
        request_dataset_id="DF_TEST",
        default_filters={},
        update_frequency="annual",
    )
    connection = _FakeConnection()

    stats = writers._insert_generic_observations(
        con=connection,
        plan=plan,
        rows=[{"REF_AREA": "UA", "TIME_PERIOD": "2020", "value": 1.5}],
    )

    assert stats.attempted == 1
    assert stats.inserted == 1
    assert stats.replaced == 0
    assert len(connection.rows) == 1


def test_core_sources_writers_keep_facade_compatibility() -> None:
    from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade

    assert facade._format_duckdb_memory_limit(1536 * 1024 * 1024) == "1536MB"


def test_writer_deserializer_uses_request_scoped_sketch_id_builder() -> None:
    plan = ObservationPlan(
        dataset_id="dataset",
        source="who",
        raw_variable="value",
        canonical_var="health_outcomes",
        connector_id="who.gho",
        profile_id="who_gho",
        request_dataset_id="indicator",
        default_filters={},
        update_frequency="annual",
    )
    payload = {"plan": writers._serialize_observation_plan(plan), "time_range": [2020, 2021]}
    context = CoreSourcesCompatibilityContext(
        {(writers.__name__, "_support_sketch_id"): lambda _plan: "request-sketch-id"}
    )

    with bind_core_sources_compatibility_context(context):
        sketch = writers._deserialize_support_sketch(payload)

    assert sketch is not None
    assert sketch.sketch_id == "request-sketch-id"


def test_connector_session_cache_uses_one_captured_effective_profile_set(
    monkeypatch, tmp_path: Path
) -> None:
    from polisyos.data_forge.domains.catalog.batch.config import (
        DatasetBatchConfig,
        _runtime_source_profile_snapshot_scope,
    )
    from polisyos.data_forge.domains.catalog.batch.core_sources.api import (
        _resolve_profile_config,
        _resolve_source_execution_policy,
    )
    from polisyos.fabric.connectors.profiles.models import SourceProfile
    from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry

    registry = SourceProfileRegistry()
    profile_ids = (
        "worldbank_wdi",
        "eurostat_public",
        "who_gho",
        "unpd_dataportal",
        "unesco_uis_public",
        "fixture_sdmx",
    )
    for profile_id in profile_ids:
        registry.register(
            SourceProfile(
                profile_id=profile_id,
                display_name=profile_id,
                connector_family="sdmx" if profile_id == "fixture_sdmx" else profile_id,
                base_url=f"https://before.example/{profile_id}",
                max_concurrency=2,
            )
        )
    monkeypatch.setattr(SourceProfileRegistry, "_instance", registry)
    monkeypatch.setenv("POLISYOS_UNPD_API_TOKEN", "captured-env-token")
    monkeypatch.setenv("POLISYOS_DATASET_LEGACY_SERIAL", "0")
    config = DatasetBatchConfig(snapshot_root=tmp_path / "snapshot")
    received = []

    class _FakeConnector:
        async def connect(self, connection_config):
            received.append(connection_config)
            return object()

        async def disconnect(self, _handle) -> None:
            return None

    for connector_name in (
        "WorldBankConnector",
        "EurostatConnector",
        "WHOConnector",
        "UNPDConnector",
        "UNESCOUISConnector",
        "SDMXSourceConnector",
    ):
        monkeypatch.setattr(writers, connector_name, _FakeConnector)

    async def _exercise() -> None:
        with _runtime_source_profile_snapshot_scope() as profile_snapshot:
            original_signature = config.run_signature
            for profile_id in profile_ids:
                current = registry.get(profile_id)
                assert current is not None
                registry.register(
                    current.model_copy(
                        update={
                            "base_url": f"https://after.example/{profile_id}",
                            "headers": {"X-PolicyOS-Changed": "current-registry-only"},
                            "max_concurrency": 9,
                        },
                        deep=True,
                    ),
                    override=True,
                )
            monkeypatch.setenv("POLISYOS_UNPD_API_TOKEN", "later-env-token")
            assert config.run_signature == original_signature
            assert "captured-env-token" not in repr(profile_snapshot)

            cache = writers._ConnectorSessionCache()
            await cache.get_worldbank()
            await cache.get_eurostat()
            await cache.get_who()
            await cache.get_unpd()
            await cache.get_unesco_uis()
            await cache.get_sdmx("fixture_sdmx")
            await cache.close()

            assert [item.url for item in received] == [
                f"https://before.example/{profile_id}" for profile_id in profile_ids
            ]
            assert all(not item.headers for item in received[:3])
            assert dict(received[3].auth_credentials) == {"token": "captured-env-token"}
            assert not received[4].headers
            assert (
                _resolve_profile_config("fixture_sdmx").url == "https://before.example/fixture_sdmx"
            )
            assert (
                _resolve_source_execution_policy(
                    source="fixture_sdmx", profile_id="fixture_sdmx"
                ).max_concurrency
                == 2
            )

        assert (
            _resolve_source_execution_policy(
                source="fixture_sdmx", profile_id="fixture_sdmx"
            ).max_concurrency
            == 9
        )

    asyncio.run(_exercise())

from __future__ import annotations

import asyncio
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
    writers,
)


def test_core_sources_writers_keep_memory_limit_formatting() -> None:
    assert writers._format_duckdb_memory_limit(1024 * 1024 * 1024) == "1024MB"


def test_insert_generic_observations_uses_request_scoped_batch_size(monkeypatch) -> None:
    connection = duckdb.connect(":memory:")
    registry._ensure_registry_tables(connection)
    chunk_lengths: list[int] = []
    original_chunker = loaders._iter_chunked_values

    def _record_chunks(values, chunk_size):
        for chunk in original_chunker(values, chunk_size):
            chunk_lengths.append(len(chunk))
            yield chunk

    monkeypatch.setattr(writers, "_iter_chunked_values", _record_chunks)
    plan = ObservationPlan(
        dataset_id="dataset",
        source="worldbank",
        raw_variable="value",
        canonical_var="gdp",
        connector_id="worldbank.wdi",
        profile_id="worldbank_wdi",
        request_dataset_id="NY.GDP.MKTP.CD",
        default_filters={},
        update_frequency="annual",
    )
    rows = [
        {"country_code": "UA", "year": 2020, "value": float(index), "partner": f"P{index}"}
        for index in range(5)
    ]
    context = CoreSourcesCompatibilityContext(
        {(writers.__name__, "_OBSERVATION_INSERT_BATCH_SIZE"): 2}
    )

    try:
        with bind_core_sources_compatibility_context(context):
            stats = writers._insert_generic_observations(
                con=connection,
                plan=plan,
                rows=rows,
            )

        assert chunk_lengths == [2, 2, 1]
        assert stats.attempted == stats.inserted == 5
        assert stats.replaced == 0
        assert connection.execute("SELECT COUNT(*) FROM ds_observations").fetchone()[0] == 5
    finally:
        connection.close()


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

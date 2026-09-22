from __future__ import annotations

from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import ObservationPlan
from polisyos.data_forge.domains.catalog.batch.core_sources import transformers, writers


def test_core_sources_writers_keep_memory_limit_formatting() -> None:
    assert writers._format_duckdb_memory_limit(1024 * 1024 * 1024) == "1024MB"


def test_writer_resolves_transformer_dependency_without_facade_bootstrap(monkeypatch) -> None:
    monkeypatch.delattr(writers, "_normalize_observation_row", raising=False)
    monkeypatch.setattr(
        transformers,
        "_normalize_observation_row",
        lambda _row: ("UA", 2020, None, None, 1.5, "{}"),
    )
    monkeypatch.setattr(writers, "_observation_id", lambda *args, **kwargs: "obs-1", raising=False)
    monkeypatch.setattr(writers, "_existing_observation_ids", lambda _con, _ids: set(), raising=False)
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

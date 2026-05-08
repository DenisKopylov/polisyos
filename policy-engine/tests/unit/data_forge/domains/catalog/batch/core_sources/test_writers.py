from __future__ import annotations

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
from polisyos.data_forge.domains.catalog.batch.core_sources import writers


def test_core_sources_writers_keep_memory_limit_formatting() -> None:
    assert writers._format_duckdb_memory_limit(1024 * 1024 * 1024) == "1024MB"
    assert facade._format_duckdb_memory_limit(1536 * 1024 * 1024) == "1536MB"

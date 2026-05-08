from __future__ import annotations

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
from polisyos.data_forge.domains.catalog.batch.core_sources import api


def test_core_sources_api_module_keeps_facade_entrypoints() -> None:
    assert callable(api.run_core_sources_ingest_async)
    assert callable(facade.run_core_sources_ingest_async)
    assert callable(facade._run_core_sources_ingest_async)


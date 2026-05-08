from __future__ import annotations

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
from polisyos.data_forge.domains.catalog.batch.core_sources import registry


def test_core_sources_registry_helpers_are_reexported() -> None:
    assert callable(registry._build_catalog_observation_plans)
    assert callable(facade._build_catalog_observation_plans)


from __future__ import annotations

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
from polisyos.data_forge.domains.catalog.batch.core_sources import loaders


def test_core_sources_loaders_resolve_repo_data_paths() -> None:
    assert loaders._seed_alignments_path().exists()
    assert facade._seed_alignments_path().exists()


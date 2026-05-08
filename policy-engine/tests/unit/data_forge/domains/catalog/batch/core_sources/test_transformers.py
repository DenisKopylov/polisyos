from __future__ import annotations

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
from polisyos.data_forge.domains.catalog.batch.core_sources import transformers


def test_core_sources_transformers_keep_scalar_coercion_behavior() -> None:
    assert transformers._as_int("7") == 7
    assert facade._as_float("3.5") == 3.5


from __future__ import annotations

from polisyos.data_forge.domains.catalog.batch import core_sources_ingest as facade
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CoreSourcesCompatibilityContext,
    bind_core_sources_compatibility_context,
)
from polisyos.data_forge.domains.catalog.batch.core_sources import transformers


def test_core_sources_transformers_keep_scalar_coercion_behavior() -> None:
    assert transformers._as_int("7") == 7
    assert facade._as_float("3.5") == 3.5


def test_transformer_uses_request_scoped_scalar_converter() -> None:
    context = CoreSourcesCompatibilityContext(
        {(transformers.__name__, "_as_float"): lambda _value: 17.25}
    )
    with bind_core_sources_compatibility_context(context):
        row = transformers._normalize_observation_row(
            {"country_code": "UA", "year": "2022", "value": "1.5"}
        )

    assert row is not None
    assert row[4] == 17.25

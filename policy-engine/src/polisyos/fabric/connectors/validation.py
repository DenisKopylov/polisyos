from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.ir.connectors import FetchResult

if TYPE_CHECKING:
    from polisyos.fabric.connectors.contracts import CoercionResult, SchemaRegistry


def validate_fetch_result_against_schema(
    result: FetchResult[Any],
    registry: "SchemaRegistry",
    *,
    strict: bool = False,
) -> list[str]:
    """
    Validate a FetchResult payload against its declared schema.

    Args:
        result: FetchResult containing data + schema metadata
        registry: Schema registry to look up schema
        strict: If True, fail on extra columns

    Returns:
        List of validation errors (empty if valid)
    """
    import pandas as pd

    from polisyos.fabric.connectors.contracts import (
        SchemaRegistry,
        SchemaVersion,
        validate_dataframe_against_schema,
    )

    if not isinstance(registry, SchemaRegistry):
        raise TypeError("registry must be a SchemaRegistry instance")

    schema = registry.get(
        result.schema_id,
        SchemaVersion.parse(result.schema_version),
    )

    if isinstance(result.data, pd.DataFrame):
        df = result.data
    elif isinstance(result.data, list):
        df = pd.DataFrame(result.data)
    else:
        return [
            "Cannot validate: data is not a DataFrame or list of dicts",
        ]

    return validate_dataframe_against_schema(df, schema, strict)


def coerce_fetch_result_against_schema(
    result: FetchResult[Any],
    registry: "SchemaRegistry",
    *,
    strict: bool = False,
    normalize_columns: bool = True,
    drop_extra: bool = False,
) -> "CoercionResult":
    """
    Coerce FetchResult data to its declared schema.

    Returns a CoercionResult with the coerced DataFrame and any issues.
    """
    import pandas as pd

    from polisyos.fabric.connectors.contracts import (
        CoercionResult,
        SchemaRegistry,
        SchemaVersion,
        coerce_dataframe_to_schema,
    )

    if not isinstance(registry, SchemaRegistry):
        raise TypeError("registry must be a SchemaRegistry instance")

    schema = registry.get(
        result.schema_id,
        SchemaVersion.parse(result.schema_version),
    )

    if isinstance(result.data, pd.DataFrame):
        df = result.data
    elif isinstance(result.data, list):
        df = pd.DataFrame(result.data)
    else:
        return CoercionResult(
            dataframe=pd.DataFrame(),
            errors=("Cannot coerce: data is not a DataFrame or list of dicts",),
            warnings=(),
            coerced_columns=(),
            dropped_columns=(),
        )

    return coerce_dataframe_to_schema(
        df,
        schema,
        strict=strict,
        normalize_columns=normalize_columns,
        drop_extra=drop_extra,
    )


__all__ = [
    "validate_fetch_result_against_schema",
    "coerce_fetch_result_against_schema",
]

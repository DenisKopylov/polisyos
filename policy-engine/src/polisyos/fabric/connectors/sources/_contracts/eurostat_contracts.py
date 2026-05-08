"""Public contracts eurostat contracts module API."""

from __future__ import annotations

from polisyos.fabric.connectors.contracts import (
    Additivity,
    ConnectorSchemaContract,
    DataSchema,
    FieldMapping,
    FieldSpec,
    SchemaType,
    SchemaVersion,
    SemanticType,
    make_field_id,
)

from ._governance import FIELD_ID_MAJOR_BUMP_APPROVAL

_SCHEMA_ID = "eurostat.data.generic"


def _field_id(name: str) -> str:
    return make_field_id(_SCHEMA_ID, name)


EUROSTAT_GENERIC_SCHEMA = DataSchema(
    schema_id=_SCHEMA_ID,
    version=SchemaVersion(2, 0, 0),
    fields=(
        FieldSpec(
            name="dataset_id",
            field_id=_field_id("dataset_id"),
            data_type=SchemaType.STRING,
            nullable=False,
            max_length=128,
        ),
        FieldSpec(
            name="observation_index",
            field_id=_field_id("observation_index"),
            data_type=SchemaType.INT64,
            nullable=False,
            semantic_type=SemanticType.INDEX,
        ),
        FieldSpec(
            name="time_period",
            field_id=_field_id("time_period"),
            data_type=SchemaType.STRING,
            nullable=True,
            semantic_type=SemanticType.TEMPORAL,
            max_length=32,
            expected_completeness=0.60,
        ),
        FieldSpec(
            name="unit",
            field_id=_field_id("unit"),
            data_type=SchemaType.STRING,
            nullable=True,
            max_length=64,
            expected_completeness=0.0,
        ),
        FieldSpec(
            name="value",
            field_id=_field_id("value"),
            data_type=SchemaType.FLOAT64,
            nullable=True,
            additivity=Additivity.SEMI_ADDITIVE,
            expected_completeness=0.70,
        ),
        FieldSpec(
            name="dimensions_json",
            field_id=_field_id("dimensions_json"),
            data_type=SchemaType.STRING,
            nullable=False,
            max_length=8192,
        ),
    ),
    primary_key=("dataset_id", "observation_index"),
    grain_dims=("dataset_id", "observation_index"),
    time_dimension="time_period",
    time_granularity=None,
    required_completeness=0.70,
    allowed_null_fields=frozenset({"time_period", "unit", "value"}),
    source="Eurostat",
    description="Normalized JSON-stat output schema for Eurostat datasets.",
    tags=frozenset({"eurostat", "jsonstat", "macro"}),
)

EUROSTAT_GENERIC_CONTRACT = ConnectorSchemaContract(
    contract_id="eurostat.data.generic",
    connector_id="eurostat.data",
    dataset_id="*",
    schema=EUROSTAT_GENERIC_SCHEMA,
    field_mappings=(
        FieldMapping(source_path="id", target_field="dimensions_json", transform="json"),
        FieldMapping(source_path="value", target_field="value", transform="float"),
    ),
    min_completeness=0.60,
    field_completeness={
        "dataset_id": 1.0,
        "observation_index": 1.0,
        "dimensions_json": 1.0,
        "value": 0.60,
    },
    description="Wildcard contract for normalized Eurostat JSON-stat datasets.",
    created_by="phase16",
    approval=FIELD_ID_MAJOR_BUMP_APPROVAL,
)

EUROSTAT_CONTRACTS = (EUROSTAT_GENERIC_CONTRACT,)

__all__ = [
    "EUROSTAT_CONTRACTS",
    "EUROSTAT_GENERIC_CONTRACT",
    "EUROSTAT_GENERIC_SCHEMA",
]

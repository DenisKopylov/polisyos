"""Public contracts ukons contracts module API."""

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

_SCHEMA_ID = "ukons.datasets.generic"


def _field_id(name: str) -> str:
    return make_field_id(_SCHEMA_ID, name)


UKONS_GENERIC_SCHEMA = DataSchema(
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
            name="observation",
            field_id=_field_id("observation"),
            data_type=SchemaType.FLOAT64,
            nullable=True,
            additivity=Additivity.SEMI_ADDITIVE,
            expected_completeness=0.60,
        ),
        FieldSpec(
            name="time_period",
            field_id=_field_id("time_period"),
            data_type=SchemaType.STRING,
            nullable=True,
            semantic_type=SemanticType.TEMPORAL,
            max_length=64,
            expected_completeness=0.50,
        ),
        FieldSpec(
            name="geography",
            field_id=_field_id("geography"),
            data_type=SchemaType.STRING,
            nullable=True,
            semantic_type=SemanticType.CODE,
            max_length=64,
            expected_completeness=0.50,
        ),
        FieldSpec(
            name="dimensions_json",
            field_id=_field_id("dimensions_json"),
            data_type=SchemaType.STRING,
            nullable=False,
            max_length=8192,
        ),
    ),
    primary_key=("dataset_id", "dimensions_json"),
    grain_dims=("dataset_id", "dimensions_json"),
    time_dimension="time_period",
    time_granularity=None,
    required_completeness=0.60,
    allowed_null_fields=frozenset({"observation", "time_period", "geography"}),
    source="UK Office for National Statistics",
    description="Normalized observations schema for ONS dataset endpoints.",
    tags=frozenset({"ukons", "ons", "macro"}),
)

UKONS_GENERIC_CONTRACT = ConnectorSchemaContract(
    contract_id="ukons.datasets.generic",
    connector_id="ukons.datasets",
    dataset_id="*",
    schema=UKONS_GENERIC_SCHEMA,
    field_mappings=(
        FieldMapping(source_path="observations.*.observation", target_field="observation"),
        FieldMapping(source_path="observations.*.dimensions", target_field="dimensions_json"),
    ),
    min_completeness=0.50,
    field_completeness={
        "dataset_id": 1.0,
        "dimensions_json": 1.0,
        "observation": 0.50,
    },
    description="Wildcard contract for UK ONS observations endpoint.",
    created_by="phase16",
    approval=FIELD_ID_MAJOR_BUMP_APPROVAL,
)

UKONS_CONTRACTS = (UKONS_GENERIC_CONTRACT,)

__all__ = [
    "UKONS_CONTRACTS",
    "UKONS_GENERIC_CONTRACT",
    "UKONS_GENERIC_SCHEMA",
]

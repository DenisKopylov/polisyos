"""Public contracts world bank contracts module API."""

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
    TimeGranularity,
    make_field_id,
)

from ._governance import FIELD_ID_MAJOR_BUMP_APPROVAL

_SCHEMA_ID = "worldbank.wdi.generic"


def _field_id(name: str) -> str:
    return make_field_id(_SCHEMA_ID, name)


WDI_GENERIC_SCHEMA = DataSchema(
    schema_id=_SCHEMA_ID,
    version=SchemaVersion(2, 0, 0),
    fields=(
        FieldSpec(
            name="country_code",
            field_id=_field_id("country_code"),
            data_type=SchemaType.STRING,
            nullable=False,
            semantic_type=SemanticType.CODE,
            max_length=3,
        ),
        FieldSpec(
            name="country_name",
            field_id=_field_id("country_name"),
            data_type=SchemaType.STRING,
            nullable=True,
            max_length=256,
            expected_completeness=0.95,
        ),
        FieldSpec(
            name="indicator_id",
            field_id=_field_id("indicator_id"),
            data_type=SchemaType.STRING,
            nullable=False,
            max_length=128,
        ),
        FieldSpec(
            name="indicator_name",
            field_id=_field_id("indicator_name"),
            data_type=SchemaType.STRING,
            nullable=True,
            max_length=512,
            expected_completeness=0.95,
        ),
        FieldSpec(
            name="year",
            field_id=_field_id("year"),
            data_type=SchemaType.INT64,
            nullable=False,
            bounds=(1960, 2100),
            semantic_type=SemanticType.TEMPORAL,
        ),
        FieldSpec(
            name="value",
            field_id=_field_id("value"),
            data_type=SchemaType.FLOAT64,
            nullable=True,
            additivity=Additivity.SEMI_ADDITIVE,
            expected_completeness=0.80,
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
            name="decimal",
            field_id=_field_id("decimal"),
            data_type=SchemaType.INT64,
            nullable=True,
            expected_completeness=0.0,
        ),
    ),
    primary_key=("country_code", "indicator_id", "year"),
    grain_dims=("country_code", "indicator_id", "year"),
    time_dimension="year",
    time_granularity=TimeGranularity.ANNUAL,
    geo_dimension="country_code",
    required_completeness=0.80,
    allowed_null_fields=frozenset({"value", "unit", "decimal", "country_name", "indicator_name"}),
    source="The World Bank Group",
    description="Generic annual schema for World Development Indicators (WDI).",
    tags=frozenset({"worldbank", "wdi", "macro"}),
)

WDI_GENERIC_CONTRACT = ConnectorSchemaContract(
    contract_id="worldbank.wdi.generic",
    connector_id="worldbank.wdi",
    dataset_id="*",
    schema=WDI_GENERIC_SCHEMA,
    field_mappings=(
        FieldMapping(source_path="countryiso3code", target_field="country_code"),
        FieldMapping(source_path="country.value", target_field="country_name"),
        FieldMapping(source_path="indicator.id", target_field="indicator_id"),
        FieldMapping(source_path="indicator.value", target_field="indicator_name"),
        FieldMapping(source_path="date", target_field="year", transform="int"),
        FieldMapping(source_path="value", target_field="value", transform="float"),
        FieldMapping(source_path="unit", target_field="unit"),
        FieldMapping(source_path="decimal", target_field="decimal", transform="int"),
    ),
    min_completeness=0.70,
    field_completeness={
        "country_code": 1.0,
        "indicator_id": 1.0,
        "year": 1.0,
        "value": 0.70,
    },
    completeness_scope="latest_window",
    completeness_window_rows=2000,
    description="Wildcard contract for World Bank WDI indicators.",
    created_by="phase16",
    approval=FIELD_ID_MAJOR_BUMP_APPROVAL,
)

WORLD_BANK_CONTRACTS = (WDI_GENERIC_CONTRACT,)

__all__ = [
    "WDI_GENERIC_CONTRACT",
    "WDI_GENERIC_SCHEMA",
    "WORLD_BANK_CONTRACTS",
]

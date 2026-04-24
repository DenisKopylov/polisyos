"""Public contracts wvs contracts module API."""

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
)

WVS_GENERIC_SCHEMA = DataSchema(
    schema_id="wvs.wave7.generic",
    version=SchemaVersion(1, 0, 0),
    fields=(
        FieldSpec(
            name="country_code",
            data_type=SchemaType.STRING,
            nullable=False,
            semantic_type=SemanticType.CODE,
            max_length=3,
        ),
        FieldSpec(
            name="country_name",
            data_type=SchemaType.STRING,
            nullable=True,
            max_length=256,
            expected_completeness=0.70,
        ),
        FieldSpec(
            name="survey_year",
            data_type=SchemaType.INT64,
            nullable=False,
            semantic_type=SemanticType.TEMPORAL,
            bounds=(1990, 2100),
        ),
        FieldSpec(
            name="wave",
            data_type=SchemaType.INT64,
            nullable=False,
            semantic_type=SemanticType.INDEX,
            bounds=(1, 20),
        ),
        FieldSpec(
            name="indicator_code",
            data_type=SchemaType.STRING,
            nullable=False,
            max_length=64,
        ),
        FieldSpec(
            name="indicator_label",
            data_type=SchemaType.STRING,
            nullable=True,
            max_length=512,
            expected_completeness=0.70,
        ),
        FieldSpec(
            name="value",
            data_type=SchemaType.FLOAT64,
            nullable=True,
            additivity=Additivity.SEMI_ADDITIVE,
            expected_completeness=0.60,
        ),
        FieldSpec(
            name="sample_size",
            data_type=SchemaType.INT64,
            nullable=True,
            expected_completeness=0.20,
        ),
    ),
    primary_key=("country_code", "survey_year", "wave", "indicator_code"),
    grain_dims=("country_code", "survey_year", "wave", "indicator_code"),
    time_dimension="survey_year",
    time_granularity=TimeGranularity.ANNUAL,
    geo_dimension="country_code",
    required_completeness=0.60,
    allowed_null_fields=frozenset(
        {"country_name", "indicator_label", "value", "sample_size"},
    ),
    source="World Values Survey",
    description="Normalized survey-wave schema for World Values Survey connector.",
    tags=frozenset({"wvs", "survey", "values"}),
)

WVS_GENERIC_CONTRACT = ConnectorSchemaContract(
    contract_id="wvs.wave7.generic",
    connector_id="wvs.wave7",
    dataset_id="*",
    schema=WVS_GENERIC_SCHEMA,
    field_mappings=(
        FieldMapping(source_path="country_code", target_field="country_code"),
        FieldMapping(source_path="country_name", target_field="country_name"),
        FieldMapping(source_path="survey_year", target_field="survey_year", transform="int"),
        FieldMapping(source_path="wave", target_field="wave", transform="int"),
        FieldMapping(source_path="indicator_code", target_field="indicator_code"),
        FieldMapping(source_path="indicator_label", target_field="indicator_label"),
        FieldMapping(source_path="value", target_field="value", transform="float"),
        FieldMapping(source_path="sample_size", target_field="sample_size", transform="int"),
    ),
    min_completeness=0.55,
    field_completeness={
        "country_code": 1.0,
        "survey_year": 1.0,
        "wave": 1.0,
        "indicator_code": 1.0,
        "value": 0.55,
    },
    description="Wildcard contract for WVS wave-based indicator observations.",
    created_by="phase0b",
)

WVS_CONTRACTS = (WVS_GENERIC_CONTRACT,)

__all__ = [
    "WVS_CONTRACTS",
    "WVS_GENERIC_CONTRACT",
    "WVS_GENERIC_SCHEMA",
]

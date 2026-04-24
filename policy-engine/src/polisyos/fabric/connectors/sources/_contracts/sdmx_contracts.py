"""Schema contracts for SDMX statistical data connectors.

SDMX produces dynamic schemas — the dimension columns vary per dataflow
(e.g. ECB EXR has FREQ, CURRENCY, CURRENCY_DENOM; OECD GDP has LOCATION,
SUBJECT, MEASURE). Only the ``value`` column is guaranteed across all
dataflows, so the generic contract defines a minimal fixed set and marks
additional dimension columns as dynamic.
"""

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

SDMX_GENERIC_SCHEMA = DataSchema(
    schema_id="sdmx.generic",
    version=SchemaVersion(1, 0, 0),
    fields=(
        FieldSpec(
            name="value",
            data_type=SchemaType.FLOAT64,
            nullable=True,
            additivity=Additivity.SEMI_ADDITIVE,
            expected_completeness=0.85,
        ),
        FieldSpec(
            name="time_period",
            data_type=SchemaType.STRING,
            nullable=True,
            semantic_type=SemanticType.TEMPORAL,
            max_length=32,
            expected_completeness=0.90,
        ),
        FieldSpec(
            name="freq",
            data_type=SchemaType.STRING,
            nullable=True,
            semantic_type=SemanticType.CODE,
            max_length=8,
            expected_completeness=0.0,
        ),
    ),
    primary_key=(),
    grain_dims=(),
    time_dimension="time_period",
    time_granularity=TimeGranularity.QUARTERLY,
    required_completeness=0.70,
    allowed_null_fields=frozenset({"value", "time_period", "freq"}),
    source="SDMX REST API",
    description=(
        "Generic SDMX schema with minimal fixed columns. "
        "Dimension columns are dynamic and depend on the specific dataflow."
    ),
    tags=frozenset({"sdmx", "statistical", "multi-agency"}),
)

SDMX_GENERIC_CONTRACT = ConnectorSchemaContract(
    contract_id="sdmx.generic",
    connector_id="sdmx.source",
    dataset_id="*",
    schema=SDMX_GENERIC_SCHEMA,
    field_mappings=(
        FieldMapping(source_path="value", target_field="value", transform="float"),
        FieldMapping(source_path="TIME_PERIOD", target_field="time_period"),
        FieldMapping(source_path="FREQ", target_field="freq"),
    ),
    min_completeness=0.60,
    field_completeness={
        "value": 0.70,
    },
    completeness_scope="latest_window",
    completeness_window_rows=500,
    description="Wildcard contract for SDMX dataflows (dynamic dimension columns).",
    created_by="wave1",
)

SDMX_CONTRACTS = (SDMX_GENERIC_CONTRACT,)

__all__ = [
    "SDMX_CONTRACTS",
    "SDMX_GENERIC_CONTRACT",
    "SDMX_GENERIC_SCHEMA",
]

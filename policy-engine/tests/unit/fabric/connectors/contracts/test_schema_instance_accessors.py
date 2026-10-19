from __future__ import annotations

from polisyos.fabric.connectors.contracts import (
    ConnectorSchemaContract,
    DataSchema,
    FieldSpec,
    InferenceResult,
    SchemaRegistration,
    SchemaType,
    SchemaVersion,
)


def _schema() -> DataSchema:
    return DataSchema(
        schema_id="test.native.override-retirement",
        version=SchemaVersion(1, 0, 0),
        fields=(FieldSpec(name="id", data_type=SchemaType.STRING, nullable=False),),
        primary_key=("id",),
        required_completeness=0.0,
    )


def test_instance_schema_accessors_preserve_alias_and_wire_contract() -> None:
    schema = _schema()
    models = (
        (
            ConnectorSchemaContract(
                contract_id="test.native.override-retirement",
                connector_id="test.native",
                dataset_id="fixture",
                schema=schema,
            ),
            "connector_schema",
        ),
        (InferenceResult(schema=schema), "inferred_schema"),
        (SchemaRegistration.from_schema(schema), "registered_schema"),
    )

    for model, field_name in models:
        assert model.schema is schema
        assert type(model).model_fields[field_name].alias == "schema"
        assert "schema" in type(model).model_json_schema(by_alias=True)["properties"]
        assert model.model_dump(by_alias=True)["schema"] == schema.model_dump(by_alias=True)

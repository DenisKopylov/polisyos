from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from pydantic import BaseModel, Field
from pydantic_core import PydanticUndefined

from polisyos.schemas.abi_models import ABIModelEntry, Priority
from tools.quality.diagnostics import gen_schema


def _entry(
    *,
    version_field: str | None = "schema_version",
    schema_variant_version: str | None = None,
) -> ABIModelEntry:
    return ABIModelEntry(
        abi_key="version_metadata_demo",
        fqn="demo.models.VersionMetadataDemo",
        module="scientist",
        schema_file="version_metadata_demo.schema.json",
        priority=Priority.P1,
        version_field=version_field,
        schema_variant_version=schema_variant_version,
    )


def test_stock_scientist_manifest_uses_required_literal_schema_version(
    tmp_path: Path,
) -> None:
    (entry,) = gen_schema.select_abi_entries(["retained_skg_snapshot_v1_1"])
    resolved = gen_schema._resolve_entry(entry)
    field_info = resolved.cls.model_fields[entry.version_field]
    assert field_info.default is PydanticUndefined

    schema = gen_schema._generate_model_schema(resolved.cls)
    assert schema["properties"][entry.version_field]["const"] == "1.1"

    output_dir = tmp_path / "snapshots"
    assert (
        gen_schema.main(
            [
                "--models",
                entry.abi_key,
                "--output-dir",
                str(output_dir),
                "--cache-dir",
                str(tmp_path / "cache"),
            ]
        )
        == 0
    )
    manifest = json.loads((output_dir / "scientist" / "_manifest.json").read_text(encoding="utf-8"))
    assert manifest["models"][entry.abi_key]["schema_version"] == "1.1"


def test_required_single_literal_supplies_static_schema_version() -> None:
    class FutureModel(BaseModel):
        schema_version: Literal["7.8"]

    assert gen_schema._schema_version_for(_entry(), FutureModel) == "7.8"


def test_actual_default_precedes_literal_domain_and_explicit_variant_precedes_default() -> None:
    class DefaultedModel(BaseModel):
        schema_version: Literal["1.0", "1.1"] = "1.0"

    assert gen_schema._schema_version_for(_entry(), DefaultedModel) == "1.0"
    assert (
        gen_schema._schema_version_for(
            _entry(schema_variant_version="1.1"),
            DefaultedModel,
        )
        == "1.1"
    )


@pytest.mark.parametrize(
    "model",
    [
        type(
            "AmbiguousLiteralModel",
            (BaseModel,),
            {"__annotations__": {"schema_version": Literal["1.0", "1.1"]}},
        ),
        type(
            "DynamicStringModel",
            (BaseModel,),
            {"__annotations__": {"schema_version": str}},
        ),
    ],
)
def test_required_ambiguous_or_dynamic_version_is_not_invented(
    model: type[BaseModel],
) -> None:
    assert gen_schema._schema_version_for(_entry(), model) is None


def test_missing_version_field_is_not_invented() -> None:
    class MissingFieldModel(BaseModel):
        value: int

    assert gen_schema._schema_version_for(_entry(), MissingFieldModel) is None
    assert gen_schema._schema_version_for(_entry(version_field=None), MissingFieldModel) is None


def test_default_factory_is_never_executed_for_version_metadata() -> None:
    calls: list[str] = []

    def make_version() -> str:
        calls.append("called")
        return "9.9"

    class FactoryVersionModel(BaseModel):
        schema_version: str = Field(default_factory=make_version)

    assert calls == []
    assert gen_schema._schema_version_for(_entry(), FactoryVersionModel) is None
    assert calls == []

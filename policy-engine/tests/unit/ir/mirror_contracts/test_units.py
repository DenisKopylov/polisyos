import tomllib
from pathlib import Path

from polisyos.ir.kernel.units import (
    DEFAULT_UNITS_REGISTRY,
    CountUnit,
    DimensionlessUnit,
    DurationUnit,
    GenericUnit,
    MoneyUnit,
    RateUnit,
    UnitKind,
    UnitSpec,
)
from polisyos.runtime.quality.derived_observations import load_transform_family_registry
from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test_units_source_modules_have_static_contracts() -> None:
    assert_source_stem_has_static_contract("ir", "units")


def test_derivation_owner_uses_registered_generic_index_unit() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    payload = tomllib.loads(
        (repo_root / "architecture/production_quality/derivation_family_registry.toml").read_text(
            encoding="utf-8"
        )
    )

    registry = load_transform_family_registry({"families": payload["families"]})

    assert registry.families[0].input_specs[1].basis.unit == "index"
    assert DEFAULT_UNITS_REGISTRY.units["index"] == GenericUnit(
        label="index",
        description="generic measured index level",
    )
    assert "percent_gdp" not in DEFAULT_UNITS_REGISTRY.units


def test_unparameterized_unit_spec_preserves_enum_runtime_and_schema() -> None:
    unit = UnitSpec.model_validate({"kind": "money"})

    assert unit.kind is UnitKind.MONEY
    assert type(unit.model_dump(mode="python")["kind"]) is UnitKind
    assert unit.model_dump(mode="json") == {"kind": "money"}
    assert UnitSpec.model_json_schema()["properties"]["kind"] == {"$ref": "#/$defs/UnitKind"}


def test_concrete_unit_kind_schemas_remain_literal_and_discriminated() -> None:
    cases = (
        (MoneyUnit, "money", {"currency": "USD"}),
        (RateUnit, "rate", {}),
        (CountUnit, "count", {}),
        (DurationUnit, "duration", {}),
        (DimensionlessUnit, "dimensionless", {}),
        (GenericUnit, "generic", {"label": "index"}),
    )

    for model, kind, extra in cases:
        payload = {"kind": kind, **extra}
        instance = model.model_validate(payload)

        assert instance.kind == kind
        assert model.model_json_schema()["properties"]["kind"] == {
            "const": kind,
            "default": kind,
            "title": "Kind",
            "type": "string",
        }

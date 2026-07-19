import tomllib
from pathlib import Path

from polisyos.ir.kernel.units import DEFAULT_UNITS_REGISTRY, GenericUnit
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

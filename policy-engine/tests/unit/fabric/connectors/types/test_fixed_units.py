"""Behavioral evidence for the fixed unit factor owner."""

from decimal import Decimal

import pytest

from polisyos.fabric.connectors.types.fixed_units import (
    FixedUnitFactorError,
    resolve_fixed_unit_factor,
)
from polisyos.fabric.connectors.types.units import STANDARD_UNITS


@pytest.mark.parametrize(
    ("source", "target", "multiplier", "definition_hash"),
    [
        (
            "cm",
            "m",
            "0.01",
            "sha256:a64c7737dbc0fa7e1b6a789e96d34f9a6f498a0aaf27816d8dc0fe57f2c8d4ef",
        ),
        (
            "m",
            "cm",
            "100",
            "sha256:5ee2091833b4194ca99ea733bd306d74987c35022a62ee539604ec3925da2808",
        ),
    ],
)
def test_fixed_factor_preserves_the_registered_definition_identity(
    source: str, target: str, multiplier: str, definition_hash: str
) -> None:
    factor = resolve_fixed_unit_factor(source, target)

    assert (factor.raw_unit, factor.canonical_unit, factor.multiplier) == (
        source,
        target,
        multiplier,
    )
    assert factor.definition_content_sha256 == definition_hash
    assert factor.definition_basis_content_sha256 == (
        "sha256:05b2363a679c1636cdb2f5b862ad88b279f5aafe3481d01aa93a5837148e384f"
    )
    assert factor.transform_ref == "fabric://units/fixed-multiplicative/v1"
    assert factor.executor_version == "polisyos.fabric.units.fixed-multiplicative.v1"
    reverse = resolve_fixed_unit_factor(target, source)
    assert Decimal(factor.multiplier) * Decimal(reverse.multiplier) == 1


@pytest.mark.parametrize(
    ("source", "target", "reason"),
    [
        ("m", "K", "unit_transform_incompatible_dimensions"),
        ("degC", "K", "unit_transform_offset_not_admissible"),
        ("USD", "EUR", "unit_transform_rate_required"),
        ("unregistered", "m", "unit_transform_definition_unregistered"),
    ],
)
def test_fixed_factor_refuses_unregistered_or_nonmultiplicative_conversions(
    source: str, target: str, reason: str
) -> None:
    with pytest.raises(FixedUnitFactorError) as error:
        resolve_fixed_unit_factor(source, target)

    assert error.value.code == reason


def test_fixed_factor_refuses_definition_drift_outside_the_requested_pair(monkeypatch) -> None:
    with monkeypatch.context() as altered:
        altered.setitem(STANDARD_UNITS, "kg", STANDARD_UNITS["kg"]._replace(category="drift"))
        with pytest.raises(FixedUnitFactorError, match="unit_transform_definition_content_drift"):
            resolve_fixed_unit_factor("cm", "m")

    assert resolve_fixed_unit_factor("cm", "m").multiplier == "0.01"

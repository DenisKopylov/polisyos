"""Resolve fixed multiplicative unit factors against Fabric's pinned definitions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from ._units_base import STANDARD_UNITS, SUPERSCRIPT_MAP
from ._units_core import Unit
from ._units_errors import UnitConversionError, UnitParseError
from ._units_prefixes import PREFIX_FACTORS

if TYPE_CHECKING:
    from collections.abc import Mapping
    from decimal import Decimal

    from ._units_base import BaseUnit

__all__ = ["FixedUnitFactor", "FixedUnitFactorError", "resolve_fixed_unit_factor"]


_FIXED_UNIT_TRANSFORM_REF = "fabric://units/fixed-multiplicative/v1"
_FIXED_UNIT_EXECUTOR_VERSION = "polisyos.fabric.units.fixed-multiplicative.v1"
_UNIT_DIMENSIONS = (
    "length",
    "mass",
    "time",
    "current",
    "temperature",
    "amount",
    "luminosity",
    "currency",
    "population",
    "information",
    "angle",
)
_FIXED_UNIT_DEFINITION_BASIS_CONTENT_SHA256 = (
    "sha256:05b2363a679c1636cdb2f5b862ad88b279f5aafe3481d01aa93a5837148e384f"
)
_FIXED_UNIT_STANDARD_UNITS = MappingProxyType(dict(STANDARD_UNITS))
_FIXED_UNIT_PREFIX_FACTORS = MappingProxyType(dict(PREFIX_FACTORS))
_FIXED_UNIT_SUPERSCRIPT_MAP = MappingProxyType(dict(SUPERSCRIPT_MAP))


@dataclass(frozen=True, slots=True)
class FixedUnitFactor:
    """Resolved unit arithmetic and its definition identity.

    It describes the factor only. Applying it to a measured quantity requires
    separately bound source and target representations.
    """

    raw_unit: str
    canonical_unit: str
    multiplier: str
    definition_basis_content_sha256: str
    definition_content_sha256: str
    transform_ref: Literal["fabric://units/fixed-multiplicative/v1"] = _FIXED_UNIT_TRANSFORM_REF
    executor_version: Literal["polisyos.fabric.units.fixed-multiplicative.v1"] = (
        _FIXED_UNIT_EXECUTOR_VERSION
    )


class FixedUnitFactorError(ValueError):
    """Raised when the pinned unit domain cannot resolve the requested factor."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def _unit_definition_basis_sha256(
    standard_units: Mapping[str, BaseUnit],
    prefix_factors: Mapping[str, Decimal],
    superscript_map: Mapping[str, str],
) -> str:
    """Hash the full static definition basis admitted by the fixed-unit v1 owner."""
    payload = {
        "standard_units": [
            {
                "registry_key": registry_key,
                "symbol": definition.symbol,
                "dimension": {
                    name: getattr(definition.dimension, name) for name in _UNIT_DIMENSIONS
                },
                "to_si_factor": str(definition.to_si_factor),
                "to_si_offset": str(definition.to_si_offset),
                "aliases": list(definition.aliases),
                "category": definition.category,
            }
            for registry_key, definition in sorted(standard_units.items())
        ],
        "prefix_factors": {key: str(value) for key, value in sorted(prefix_factors.items())},
        "superscript_map": dict(sorted(superscript_map.items())),
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _require_fixed_unit_definition_basis() -> str:
    """Require both the frozen v1 snapshot and current owner maps to match the v1 pin."""
    try:
        snapshot_sha256 = _unit_definition_basis_sha256(
            _FIXED_UNIT_STANDARD_UNITS,
            _FIXED_UNIT_PREFIX_FACTORS,
            _FIXED_UNIT_SUPERSCRIPT_MAP,
        )
        current_sha256 = _unit_definition_basis_sha256(
            STANDARD_UNITS,
            PREFIX_FACTORS,
            SUPERSCRIPT_MAP,
        )
    except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
        raise FixedUnitFactorError("unit_transform_definition_content_drift") from exc
    if (
        snapshot_sha256 != _FIXED_UNIT_DEFINITION_BASIS_CONTENT_SHA256
        or current_sha256 != _FIXED_UNIT_DEFINITION_BASIS_CONTENT_SHA256
    ):
        raise FixedUnitFactorError("unit_transform_definition_content_drift")
    return snapshot_sha256


def _unit_definition_payload(unit: Unit) -> dict[str, object]:
    """Describe the frozen local definitions used by the fixed-unit v1 parser."""
    components: list[dict[str, object]] = []
    for symbol, power in unit._components:
        definition = _FIXED_UNIT_STANDARD_UNITS.get(symbol)
        if definition is None:
            raise FixedUnitFactorError("unit_transform_definition_unregistered", symbol)
        components.append(
            {
                "power": power,
                "symbol": definition.symbol,
                "dimension": {
                    name: getattr(definition.dimension, name) for name in _UNIT_DIMENSIONS
                },
                "to_si_factor": str(definition.to_si_factor),
                "to_si_offset": str(definition.to_si_offset),
                "aliases": list(definition.aliases),
                "category": definition.category,
            }
        )
    return {
        "parsed_symbol": unit.symbol,
        "dimension": {name: getattr(unit.dimension, name) for name in _UNIT_DIMENSIONS},
        "to_canonical_factor": str(unit.to_canonical_factor),
        "to_canonical_offset": str(unit.to_canonical_offset),
        "components": components,
    }


def resolve_fixed_unit_factor(raw_unit: str, canonical_unit: str) -> FixedUnitFactor:
    """Resolve a positive fixed multiplier using the pinned Fabric v1 definitions.

    Args:
        raw_unit: Unit of the input quantity.
        canonical_unit: Unit into which the quantity may be converted.

    Returns:
        The exact multiplier and its definition basis.

    Raises:
        FixedUnitFactorError: The units or current definition basis are unsupported.
    """
    if not raw_unit.strip() or not canonical_unit.strip():
        raise FixedUnitFactorError("unit_transform_unit_missing")

    basis_sha256 = _require_fixed_unit_definition_basis()
    try:
        parse = Unit._parse_with_definition_maps
        source = parse(
            raw_unit,
            standard_units=_FIXED_UNIT_STANDARD_UNITS,
            prefix_factors=_FIXED_UNIT_PREFIX_FACTORS,
            superscript_map=_FIXED_UNIT_SUPERSCRIPT_MAP,
        )
        target = parse(
            canonical_unit,
            standard_units=_FIXED_UNIT_STANDARD_UNITS,
            prefix_factors=_FIXED_UNIT_PREFIX_FACTORS,
            superscript_map=_FIXED_UNIT_SUPERSCRIPT_MAP,
        )
    except UnitParseError as exc:
        raise FixedUnitFactorError("unit_transform_definition_unregistered", str(exc)) from exc
    # The registered percent-to-ratio scale does not establish what a value
    # measures: its population, time and denominator still need binding.
    if (source.is_dimensionless or target.is_dimensionless) and (source.symbol, target.symbol) != (
        "percent",
        "ratio",
    ):
        raise FixedUnitFactorError("unit_transform_dimensionless_not_admissible")
    if not source.is_compatible_with(target):
        raise FixedUnitFactorError("unit_transform_incompatible_dimensions")
    try:
        conversion = source.get_conversion_factor(target)
    except UnitConversionError as exc:
        raise FixedUnitFactorError("unit_transform_incompatible_dimensions", str(exc)) from exc
    if conversion.requires_rate:
        raise FixedUnitFactorError("unit_transform_rate_required")
    if conversion.offset != 0:
        raise FixedUnitFactorError("unit_transform_offset_not_admissible")
    if conversion.multiplier <= 0:
        raise FixedUnitFactorError("unit_transform_multiplier_not_positive")
    for unit in (source, target):
        for symbol, _power in unit._components:
            definition = _FIXED_UNIT_STANDARD_UNITS.get(symbol)
            if definition is None:
                raise FixedUnitFactorError("unit_transform_definition_unregistered", symbol)
            if getattr(definition.dimension, "currency", 0):
                raise FixedUnitFactorError("unit_transform_currency_rate_law_missing", symbol)
            if getattr(definition.dimension, "population", 0):
                raise FixedUnitFactorError("unit_transform_population_law_missing", symbol)
    if conversion.multiplier == 1 and source.symbol != target.symbol:
        raise FixedUnitFactorError("unit_transform_semantic_identity_unproven")

    definition_payload = {
        "executor_version": _FIXED_UNIT_EXECUTOR_VERSION,
        "transform_ref": _FIXED_UNIT_TRANSFORM_REF,
        "definition_basis_content_sha256": basis_sha256,
        "raw_unit": raw_unit,
        "canonical_unit": canonical_unit,
        "source": _unit_definition_payload(source),
        "target": _unit_definition_payload(target),
        "multiplier": format(conversion.multiplier, "f"),
        "offset": format(conversion.offset, "f"),
    }
    definition_hash = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                definition_payload,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
    )

    if _require_fixed_unit_definition_basis() != basis_sha256:
        raise FixedUnitFactorError("unit_transform_definition_content_drift")
    return FixedUnitFactor(
        raw_unit=raw_unit,
        canonical_unit=canonical_unit,
        multiplier=format(conversion.multiplier, "f"),
        definition_basis_content_sha256=basis_sha256,
        definition_content_sha256=definition_hash,
    )

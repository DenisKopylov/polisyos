from decimal import Decimal
from types import MappingProxyType

from polisyos.fabric.connectors.types._units_base import STANDARD_UNITS, SUPERSCRIPT_MAP
from polisyos.fabric.connectors.types._units_core import Unit
from polisyos.fabric.connectors.types._units_prefixes import PREFIX_FACTORS


def _parse_with_maps(unit_text, *, units=None, prefixes=None, superscripts=None):
    return Unit._parse_with_definition_maps(
        unit_text,
        standard_units=MappingProxyType(dict(STANDARD_UNITS if units is None else units)),
        prefix_factors=MappingProxyType(dict(PREFIX_FACTORS if prefixes is None else prefixes)),
        superscript_map=MappingProxyType(
            dict(SUPERSCRIPT_MAP if superscripts is None else superscripts)
        ),
    )


def test_definition_parser_uses_supplied_unit_prefix_and_exponent_maps():
    changed_units = dict(STANDARD_UNITS)
    changed_units["km"] = changed_units["km"]._replace(to_si_factor=Decimal("2000"))
    changed_prefixes = dict(PREFIX_FACTORS)
    changed_prefixes["Mio"] = Decimal("2000000")
    changed_superscripts = dict(SUPERSCRIPT_MAP)
    changed_superscripts["\u00b2"] = "3"

    speed = _parse_with_maps("km/h", units=changed_units)
    large_currency = _parse_with_maps("Mio EUR", prefixes=changed_prefixes)
    cubed_length = _parse_with_maps("m\u00b2", superscripts=changed_superscripts)

    assert speed.to_canonical_factor == Decimal("2000") / Decimal("3600")
    assert large_currency.to_canonical_factor == Decimal("2000000")
    assert cubed_length.dimension.length == 3


def test_public_parse_keeps_using_existing_live_definition_maps():
    assert Unit.parse("km").to_canonical_factor == STANDARD_UNITS["km"].to_si_factor

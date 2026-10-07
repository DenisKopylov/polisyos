"""Retain catalog/type markers while removing real family/layout properties."""

from __future__ import annotations

import argparse

import pytest

from polisyos.ir.kernel import slots
from polisyos.scientist.validation.verification.ic import service


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("control", choices=("catalog_is_ic", "family_owner", "layout_paths"))
    control = parser.parse_args().control
    if control == "catalog_is_ic":
        service._mechanism_family_positive_for_property = lambda certificate, property: True
    elif control == "family_owner":
        original = service.get_mechanism_family_spec
        service.get_mechanism_family_spec = lambda mechanism_id: original("bayes_tax_pl_v1")
    else:
        # Preserve the builder object, aliases, module, signature and all IR
        # types/slot IDs while replacing only its materialization operation.
        def no_materialization(slot_registry):
            return SlotLayout(layout={})  # noqa: F821 - original function globals own the type

        slots.build_slot_layout.__code__ = no_materialization.__code__
    return int(pytest.main([
        "tests/unit/foundry/methods/catalog/mechanism/test_family_consumer_contract.py",
        "-o", "addopts=", "-q", "-ra",
        "--basetemp", f"/tmp/e02-F-continuation-20261006/foundry/family-removal-{control}-tmp",
    ]))


if __name__ == "__main__":
    raise SystemExit(main())

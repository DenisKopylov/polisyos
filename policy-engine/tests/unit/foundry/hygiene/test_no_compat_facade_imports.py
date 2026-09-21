from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "polisyos.foundry.base",
        "polisyos.foundry.types",
        "polisyos.foundry.domain.state",
        "polisyos.foundry.domain.mechanisms.fiscal",
        "polisyos.foundry.domain.mechanisms.labor",
        "polisyos.foundry.domain.mechanisms.treasury",
    ],
)
def test_legacy_foundry_compat_facades_are_not_importable(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_domain_mechanisms_compatibility_root_is_not_importable() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("polisyos.foundry.domain.mechanisms")

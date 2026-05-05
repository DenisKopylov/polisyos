from __future__ import annotations

import importlib

import pytest


def test_canonical_synthetic_control_imports_resolve() -> None:
    package_module = importlib.import_module("polisyos.foundry.methods.causal")
    canonical_module = importlib.import_module(
        "polisyos.foundry.methods.catalog.causal.synthetic_control"
    )

    assert package_module.SyntheticControlMethod is canonical_module.SyntheticControlMethod


@pytest.mark.parametrize(
    "module_name",
    [
        "polisyos.foundry.methods.catalog.causal.scm",
        "polisyos.foundry.methods.causal.scm",
        "polisyos.foundry.methods.causal.synthetic_control",
    ],
)
def test_removed_legacy_synthetic_control_import_paths_fail(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)

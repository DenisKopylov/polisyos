from __future__ import annotations

import importlib


def test_catalog_direct_imports_resolve_same_class() -> None:
    legacy_module = importlib.import_module("polisyos.foundry.methods.catalog.causal.scm")
    canonical_module = importlib.import_module(
        "polisyos.foundry.methods.catalog.causal.synthetic_control"
    )

    assert legacy_module.SyntheticControlMethod is canonical_module.SyntheticControlMethod


def test_catalog_legacy_shim_has_empty_all() -> None:
    legacy_module = importlib.import_module("polisyos.foundry.methods.catalog.causal.scm")

    assert legacy_module.__all__ == []


def test_catalog_legacy_star_import_does_not_export_method() -> None:
    imported: dict[str, object] = {}
    exec("from polisyos.foundry.methods.catalog.causal.scm import *", {}, imported)

    assert "SyntheticControlMethod" not in imported


def test_flattened_facade_direct_import_paths_resolve_same_class() -> None:
    legacy_module = importlib.import_module("polisyos.foundry.methods.causal.scm")
    canonical_module = importlib.import_module("polisyos.foundry.methods.causal.synthetic_control")

    assert legacy_module.SyntheticControlMethod is canonical_module.SyntheticControlMethod

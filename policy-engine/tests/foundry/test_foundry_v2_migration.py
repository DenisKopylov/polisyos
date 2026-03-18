from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "polisyos.foundry.methods.catalog.causal.scm",
        "polisyos.foundry.methods.causal.protocols",
        "polisyos.foundry.methods.causal.synthetic_control",
        "polisyos.foundry.methods.econometrics.panel",
        "polisyos.foundry.methods.econometrics.protocols",
        "polisyos.foundry.methods.optimization.lp",
        "polisyos.foundry.methods.optimization.protocols",
    ],
)
def test_foundry_v2_removed_deep_legacy_import_paths_are_not_importable(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_foundry_v2_bootstrap_registry_symbol_is_removed() -> None:
    methods_module = importlib.import_module("polisyos.foundry.methods")
    discovery_module = importlib.import_module("polisyos.foundry.methods.discovery")

    assert not hasattr(methods_module, "bootstrap_registry")
    assert not hasattr(discovery_module, "bootstrap_registry")

    with pytest.raises(ImportError):
        exec("from polisyos.foundry.methods.discovery import bootstrap_registry", {}, {})


def test_foundry_v2_compatibility_shim_files_are_deleted() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    removed_paths = [
        repo_root / "src/polisyos/foundry/methods/causal/scm.py",
        repo_root / "src/polisyos/foundry/methods/causal/protocols.py",
        repo_root / "src/polisyos/foundry/methods/econometrics/panel.py",
        repo_root / "src/polisyos/foundry/methods/econometrics/protocols.py",
        repo_root / "src/polisyos/foundry/methods/optimization/lp.py",
        repo_root / "src/polisyos/foundry/methods/optimization/protocols.py",
        repo_root / "src/polisyos/foundry/methods/catalog/causal/scm.py",
    ]

    assert all(not path.exists() for path in removed_paths)

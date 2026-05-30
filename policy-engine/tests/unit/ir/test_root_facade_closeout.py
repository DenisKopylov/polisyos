from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path

import pytest


def test_ir_root_contains_only_facade_python_files() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    ir_root = repo_root / "src" / "polisyos" / "ir"
    allowed = {"__init__.py", "api.py", "_api.py"}

    root_python_files = sorted(path.name for path in ir_root.glob("*.py"))

    assert root_python_files
    assert set(root_python_files) <= allowed
    assert root_python_files == sorted(name for name in root_python_files if name in allowed)


def test_removed_ir_large_aliases_are_not_resolved() -> None:
    for module_name in (
        "polisyos.ir.model_spec",
        "polisyos.ir.refs",
        "polisyos.ir.types",
    ):
        _drop_module(module_name)
        importlib.import_module("polisyos.ir")

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)


def test_ir_refs_and_references_no_longer_collide_as_sibling_implementations() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    ir_root = repo_root / "src" / "polisyos" / "ir"

    assert not (ir_root / "refs").exists()
    assert not (ir_root / "references").exists()
    assert (ir_root / "registry" / "refs.py").is_file()
    assert not (ir_root / "registry" / "references.py").exists()
    assert (ir_root / "loading" / "citations.py").is_file()

    package_contract = tomllib.loads(
        (repo_root / "architecture" / "packages" / "ir.toml").read_text(encoding="utf-8")
    )

    assert {
        entry.get("name") for entry in package_contract.get("allowed_name_collision", [])
    }.isdisjoint({"refs-vs-references", "refs/references", "refs"})


def test_ir_real_public_surfaces_are_not_registered_as_last_mile_shims() -> None:
    real_surfaces = {
        "polisyos.ir.connectors",
        "polisyos.ir.trinity",
    }
    repo_root = Path(__file__).resolve().parents[3]
    payload = tomllib.loads((repo_root / "architecture/shims.toml").read_text(encoding="utf-8"))
    registered_fqns = {
        entry["source_fqn"]
        for section in ("planned_source_move", "shim")
        for entry in payload.get(section, [])
        if entry.get("source_fqn")
    }

    assert real_surfaces.isdisjoint(registered_fqns)


def test_removed_ir_medium_aliases_are_not_resolved() -> None:
    for module_name in (
        "polisyos.ir.canon",
        "polisyos.ir.citations",
        "polisyos.ir.norm_pack",
        "polisyos.ir.registry_fragments",
    ):
        _drop_module(module_name)
        importlib.import_module("polisyos.ir")

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)


def test_ir_phase_5_3_has_no_last_mile_import_shims() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    payload = tomllib.loads((repo_root / "architecture/shims.toml").read_text(encoding="utf-8"))
    planned = [
        entry
        for entry in payload.get("planned_source_move", [])
        if entry["owner"] == "team-ir" and entry["wave"] == "3.2"
    ]
    shim_fqns = {
        entry.get("source_fqn")
        for entry in payload.get("shim", [])
        if entry.get("owner") == "team-ir"
    }

    assert planned == []
    assert "polisyos.ir.refs" not in shim_fqns


def test_ir_package_contract_covers_live_first_level_roots() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    ir_root = repo_root / "src" / "polisyos" / "ir"
    single_file_surface_modules = {
        "polisyos.ir._internal",
        "polisyos.ir.connectors",
        "polisyos.ir.schemas",
        "polisyos.ir.trinity",
    }
    package_contract = tomllib.loads(
        (repo_root / "architecture" / "packages" / "ir.toml").read_text(encoding="utf-8")
    )
    declared_roots = {
        Path(entry).name for entry in package_contract["layout"]["implementation_roots"]
    }
    live_roots = {
        path.name
        for path in ir_root.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }

    assert live_roots <= declared_roots
    for module_name in single_file_surface_modules:
        assert importlib.import_module(module_name).__name__ == module_name


def _drop_module(module_name: str) -> None:
    for loaded_name in list(sys.modules):
        if loaded_name == module_name or loaded_name.startswith(f"{module_name}."):
            sys.modules.pop(loaded_name, None)

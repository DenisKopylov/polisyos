"""Runtime contract for the complete IR connector module export surface."""

from __future__ import annotations

import ast
import importlib
import runpy
from pathlib import Path
from types import ModuleType

import pytest


def _target_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        result: set[str] = set()
        for child in target.elts:
            result.update(_target_names(child))
        return result
    return set()


def _public_module_bindings(source_path: Path) -> list[str]:
    """Derive module-level names exposed by the legacy implicit star import."""
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.TypeAlias):
            names.update(_target_names(node.name))
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                names.update(_target_names(target))
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
    return sorted(name for name in names if not name.startswith("_"))


def _assert_connector_exports_match_source(module: ModuleType) -> None:
    source_path = Path(module.__file__).resolve(strict=True)
    expected = _public_module_bindings(source_path)
    runtime_public_names = sorted(name for name in vars(module) if not name.startswith("_"))
    assert runtime_public_names == expected, (
        "connector runtime namespace must match source-bound public declarations"
    )
    exports = getattr(module, "__all__", None)
    assert isinstance(exports, list), "polisyos.ir.connectors must declare a list __all__"
    assert sorted(exports) == expected, (
        "connector __all__ must preserve every source-bound public module export"
    )
    assert len(exports) == len(set(exports)), "connector __all__ repeats a public export"
    for name in exports:
        assert hasattr(module, name), f"connector export {name!r} is unresolved"


def test_connectors_exports_match_all_source_bound_public_names() -> None:
    """The explicit facade must preserve the prior implicit wildcard surface."""
    module = importlib.import_module("polisyos.ir.connectors")
    _assert_connector_exports_match_source(module)


def test_star_import_exposes_every_declared_public_binding(tmp_path: Path) -> None:
    """A real wildcard consumer receives the complete explicit public facade."""
    consumer = tmp_path / "wildcard_consumer.py"
    consumer.write_text("from polisyos.ir.connectors import *\n", encoding="utf-8")
    namespace = runpy.run_path(str(consumer))
    module = importlib.import_module("polisyos.ir.connectors")
    runtime_exports = sorted(name for name in namespace if not name.startswith("__"))
    assert runtime_exports == _public_module_bindings(Path(module.__file__))


@pytest.mark.parametrize("name", ["CapabilitySet", "DataT"])
def test_export_oracle_detects_removed_public_type_declarations(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """A retained alias or TypeVar cannot disappear behind other export markers."""
    module = importlib.import_module("polisyos.ir.connectors")
    assert hasattr(module, name)
    monkeypatch.setattr(module, "__all__", [item for item in module.__all__ if item != name])
    with pytest.raises(AssertionError, match="preserve every source-bound public module export"):
        _assert_connector_exports_match_source(module)

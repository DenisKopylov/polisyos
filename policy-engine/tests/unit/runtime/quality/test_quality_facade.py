"""Runtime Quality preserves its facade while deferring unrelated owner imports."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

_PRODUCT = Path(__file__).resolve().parents[4]
_FACADE = _PRODUCT / "src/polisyos/runtime/quality/__init__.py"
_EXPORT_CENSUS_SHA256 = "96a6dc5fa6ce8a007b7632f4d57764d021209650f7e561c0153d1c3c178e9f8b"
_OWNER_CENSUS_SHA256 = "f50f474dd0cfb750a04b06f8eeee0c25f438728104c006b31f5ec1ec6331d090"


def _load_facade(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    name = "_quality_facade_contract_test"
    spec = importlib.util.spec_from_file_location(name, _FACADE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


def test_historical_export_and_owner_census_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    facade = _load_facade(monkeypatch)
    exports = facade.__all__
    routes = facade._LAZY_IMPORTS
    assert len(exports) == 976
    assert len(set(exports)) == len(exports)
    assert set(exports) == set(routes)
    assert hashlib.sha256(json.dumps(exports, separators=(",", ":")).encode()).hexdigest() == (
        _EXPORT_CENSUS_SHA256
    )
    assert (
        hashlib.sha256(
            json.dumps(routes, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == _OWNER_CENSUS_SHA256
    )


def test_actual_inventory_resolves_complete_lazy_export_denominator() -> None:
    from tools.devx.architecture import guardrails

    inventory = guardrails._entrypoint_inventory("polisyos.runtime.quality")
    assert inventory.export_count == 976, inventory.export_resolution.get("reason")
    assert inventory.known_export_count == 976
    assert inventory.facade_mode_observed == "lazy_facade"
    assert inventory.export_resolution["complete"] is True
    assert (
        hashlib.sha256(
            json.dumps(list(inventory.exports), separators=(",", ":")).encode()
        ).hexdigest()
        == _EXPORT_CENSUS_SHA256
    )


def test_every_named_and_wildcard_export_is_the_defining_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade = _load_facade(monkeypatch)
    modules: dict[str, ModuleType] = {}
    objects: dict[str, object] = {}
    imports: list[str] = []
    for name, (owner, attribute) in facade._LAZY_IMPORTS.items():
        module = modules.setdefault(owner, ModuleType(owner))
        value = object()
        setattr(module, attribute, value)
        objects[name] = value

    def import_owner(name: str) -> ModuleType:
        imports.append(name)
        return modules[name]

    monkeypatch.setattr(facade, "importlib", SimpleNamespace(import_module=import_owner))
    for name in facade.__all__:
        assert name not in vars(facade)
        assert getattr(facade, name) is objects[name]
        assert getattr(facade, name) is objects[name]
    assert len(imports) == len(facade.__all__)
    namespace: dict[str, object] = {}
    exec("from _quality_facade_contract_test import *", namespace)  # noqa: S102 - Literal star-import semantics.
    assert {name: namespace[name] for name in facade.__all__} == objects
    assert len(imports) == len(facade.__all__)


def test_historical_direct_owner_modules_are_deferred_and_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade = _load_facade(monkeypatch)
    imports: list[str] = []

    def import_owner(name: str) -> ModuleType:
        imports.append(name)
        return ModuleType(name)

    monkeypatch.setattr(facade, "importlib", SimpleNamespace(import_module=import_owner))
    assert "acquisition_planner" in facade._SUBMODULES
    assert "design_axes" in facade._SUBMODULES
    for name in facade._SUBMODULES:
        value = getattr(facade, name)
        assert value.__name__ == f"{facade.__name__}.{name}"
        assert getattr(facade, name) is value
    assert len(imports) == len(facade._SUBMODULES)


@pytest.mark.parametrize("failure", ["import", "attribute"])
def test_failed_owner_resolution_propagates_and_does_not_cache(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    facade = _load_facade(monkeypatch)
    name = facade.__all__[0]
    owner, attribute = facade._LAZY_IMPORTS[name]
    module = ModuleType(owner)
    error = ImportError("requested owner unavailable")

    def unavailable(name: str) -> ModuleType:
        assert name == owner
        if failure == "import":
            raise error
        return module

    monkeypatch.setattr(facade, "importlib", SimpleNamespace(import_module=unavailable))
    expected_error = ImportError if failure == "import" else AttributeError
    with pytest.raises(expected_error) as caught:
        getattr(facade, name)
    if failure == "import":
        assert caught.value is error
    assert name not in vars(facade)
    value = object()
    setattr(module, attribute, value)
    monkeypatch.setattr(
        facade, "importlib", SimpleNamespace(import_module=lambda requested: module)
    )
    assert getattr(facade, name) is value


def test_dir_and_unknown_attribute_do_not_initialize_any_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade = _load_facade(monkeypatch)

    def unexpected_import(name: str) -> ModuleType:
        pytest.fail(f"listing or unknown lookup imported {name}")

    monkeypatch.setattr(facade, "importlib", SimpleNamespace(import_module=unexpected_import))
    names = dir(facade)
    assert set(facade.__all__) <= set(names)
    assert set(facade._SUBMODULES) <= set(names)
    assert names == sorted(set(names))
    with pytest.raises(AttributeError, match="undeclared_quality_owner"):
        _ = facade.undeclared_quality_owner


def test_real_cold_package_and_enum_identity_without_unrelated_ml_imports() -> None:
    script = r"""
import importlib, sys
sys.path.insert(0, sys.argv[1])
quality = importlib.import_module("polisyos.runtime.quality")
assert len(quality.__all__) == 976
assert "polisyos.runtime.quality.scorecard" not in sys.modules
assert "polisyos.runtime.quality.generation_cycle" not in sys.modules
assert "torch" not in sys.modules
assert "sklearn" not in sys.modules
from polisyos.runtime.quality import RunState, resolve_evaluation_mode
owner = importlib.import_module("polisyos.runtime.quality.evaluation_modes")
assert RunState is importlib.import_module("polisyos.runtime.quality.run_state").RunState
assert resolve_evaluation_mode is owner.resolve_evaluation_mode
assert resolve_evaluation_mode("deployment").canonical_mode == "deployment"
assert quality.evaluation_modes is owner
assert "polisyos.runtime.quality.scorecard" not in sys.modules
assert "torch" not in sys.modules
print("real cold facade and owner identity PASS")
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(_PRODUCT / "src")],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

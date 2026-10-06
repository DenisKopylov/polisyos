"""Supported library loader and source-configuration boundaries after PR65."""

from __future__ import annotations

import importlib
import importlib.util
import pickle
import runpy
from pathlib import Path

import pytest

PREFIX = "polisyos.foundry.methods.catalog.causal"


@pytest.mark.parametrize("name", ["causal_engine", "id_engine", "interference"])
def test_supported_import_loader_resolves_package_not_retired_shadow_file(name: str) -> None:
    module = importlib.import_module(f"{PREFIX}.{name}")
    spec = importlib.util.find_spec(module.__name__)
    assert spec is not None and spec.submodule_search_locations is not None
    source = Path(module.__file__)
    assert source.name == "__init__.py"
    assert Path(spec.origin) == source
    assert Path(spec.loader.get_filename(spec.name)) == source
    assert importlib.import_module(spec.name) is module
    # These files were already retired before this slice. A filename client has
    # no implied alias; library imports use the supported package address.
    retired = source.parent.parent / f"{name}.py"
    assert not retired.exists()
    with pytest.raises(FileNotFoundError):
        runpy.run_path(str(retired))
    file_spec = importlib.util.spec_from_file_location("retired_filename_probe", retired)
    assert file_spec is not None
    with pytest.raises(FileNotFoundError):
        file_spec.loader.exec_module(importlib.util.module_from_spec(file_spec))


def test_real_registry_keeps_canonical_method_and_public_engine_identities() -> None:
    from polisyos.foundry.methods.catalog.causal._registry_boot import register_causal_methods
    from polisyos.foundry.methods.catalog.causal.causal_engine import CausalEngine
    from polisyos.foundry.methods.catalog.causal.causal_engine.api import CausalEngine as Owner
    from polisyos.foundry.methods.catalog.causal.symbolic_identify import SymbolicIdentify
    from polisyos.foundry.methods.causal import ensure_causal_methods_registered
    from polisyos.foundry.methods.registry import MethodRegistry

    methods = register_causal_methods()
    assert SymbolicIdentify in methods
    ensure_causal_methods_registered()
    assert MethodRegistry.get_instance().get(SymbolicIdentify.signature.fqn) is SymbolicIdentify
    assert CausalEngine is Owner
    assert pickle.loads(pickle.dumps(CausalEngine)) is Owner  # noqa: S301 - own class bytes


def _census_functions() -> dict:
    product = Path(__file__).resolve().parents[6]
    path = product / "docs/research/e02-cloud-test-plan/verification/F/api-20261006/census.py"
    return runpy.run_path(str(path))


def test_computed_import_rows_classify_basis_not_actual_clients() -> None:
    functions = _census_functions()
    code = b"""import importlib
MAP = {"supported": ("polisyos.foundry.methods.catalog.causal.causal_engine", "CausalEngine"),
       "other": ("polisyos.core", "ArtifactRef")}
def select(name):
    module_name, attr_name = MAP[name]
    return importlib.import_module(module_name)
def other(name):
    return importlib.import_module(f"{__name__}.{name}")
def external(config):
    return importlib.import_module(config.module)
"""
    rows = functions["python_rows"]("policy-engine/src/polisyos/core/fixture.py", code)[2]
    assert len(rows) == 3
    basis = [row["source_configuration_basis"] for row in rows]
    assert {row["classification"] for row in basis} == {
        "finite_source_configuration",
        "fixed_other_namespace",
        "computed_argument_unresolved",
    }
    assert all(row["runtime_client_established"] is False for row in basis)
    finite = next(row for row in basis if row["classification"] == "finite_source_configuration")
    assert f"{PREFIX}.causal_engine" in finite["declared_addresses"]
    assert finite["unresolved_by_construction"]


@pytest.mark.parametrize("filename", ["CAUSAL_ENGINE.PY", "INTERFERENCE.PY", "ID_ENGINE.PY"])
def test_case_insensitive_lexical_mentions_do_not_invent_import_clients(filename: str) -> None:
    functions = _census_functions()
    code = (
        f'import importlib\nTEXT = "{filename}"\ndef external(name):\n'
        "    return importlib.import_module(name)\n"
    ).encode()
    assert functions["TOKEN"].search(code.decode())
    imports, strings, dynamic = functions["python_rows"]("outside/runtime.py", code)
    assert imports == strings == []
    assert len(dynamic) == 1
    assert (
        dynamic[0]["source_configuration_basis"]["classification"] == "computed_argument_unresolved"
    )
    assert dynamic[0]["source_configuration_basis"]["runtime_client_established"] is False

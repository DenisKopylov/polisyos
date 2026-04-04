from __future__ import annotations

import importlib
import sys

from polisyos.foundry import compile as compile_foundry
from polisyos.foundry import compile_program, execute
from polisyos.foundry.quickstart import run_trivial_compile_execute


def test_foundry_package_exports_docs_facing_api() -> None:
    importlib.import_module("polisyos.foundry.compile")
    importlib.import_module("polisyos.foundry.execute")
    assert compile_program is compile_foundry
    assert callable(execute)


def test_foundry_package_exports_docs_facing_api_when_submodule_imported_first(
    monkeypatch,
) -> None:
    for module_name in (
        "polisyos.foundry",
        "polisyos.foundry.compile",
        "polisyos.foundry.execute",
    ):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    foundry = importlib.import_module("polisyos.foundry")
    importlib.import_module("polisyos.foundry.compile")
    importlib.import_module("polisyos.foundry.execute")

    assert getattr(foundry, "compile_program") is getattr(foundry, "compile")
    assert callable(getattr(foundry, "execute"))


def test_run_trivial_compile_execute(tmp_path) -> None:
    result = run_trivial_compile_execute(cas_root=tmp_path)

    assert result.compile_ok is True
    assert result.execute_ok is True
    assert result.exec_plan_artifact_id is not None
    assert result.simulation_result_artifact_id is not None

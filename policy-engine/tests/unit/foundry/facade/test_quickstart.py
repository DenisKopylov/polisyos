from __future__ import annotations

import importlib
import sys

from polisyos.foundry import compile as compile_foundry
from polisyos.foundry import compile_program, execute
from polisyos.foundry._quickstart import (
    run_feedback_compile_execute,
    run_feedback_multiplicity_demo,
    run_trivial_compile_execute,
)


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

    assert foundry.compile_program is foundry.compile
    assert callable(foundry.execute)


def test_run_trivial_compile_execute(tmp_path) -> None:
    result = run_trivial_compile_execute(cas_root=tmp_path)

    assert result.compile_ok is True
    assert result.execute_ok is True
    assert result.exec_plan_artifact_id is not None
    assert result.simulation_result_artifact_id is not None


def test_run_feedback_compile_execute(tmp_path) -> None:
    result = run_feedback_compile_execute(cas_root=tmp_path)

    assert result.compile_ok is True
    assert result.execute_ok is True
    assert result.exec_plan_artifact_id is not None
    assert result.simulation_result_artifact_id is not None
    assert result.feedback_result_artifact_id is not None
    assert result.feedback_convergence_certificate_artifact_id is not None


def test_run_feedback_multiplicity_demo(tmp_path) -> None:
    result = run_feedback_multiplicity_demo(cas_root=tmp_path)

    assert result.compile_ok is True
    assert result.execute_ok is True
    assert result.feedback_result_artifact_id is not None
    assert result.feedback_convergence_certificate_artifact_id is not None
    assert result.equilibrium_multiplicity_report_artifact_id is not None

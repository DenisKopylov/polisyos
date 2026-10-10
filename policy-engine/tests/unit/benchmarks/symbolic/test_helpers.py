from __future__ import annotations

import builtins
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from benchmarks.symbolic._helpers import (
    canon,
    dowhy_available,
    is_rule_subsequence,
    latex_from_result,
    make_admg,
    make_bidirected_edge,
    make_dag,
    make_directed_edge,
    rule_names_from_result,
    y0_available,
)
from polisyos.ir.analytics.causal_graph import EdgeMark, GraphType

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_RUNNER = _PROJECT_ROOT / "benchmarks" / "symbolic" / "run_symbolic_benchmark.py"


def test_graph_helpers_build_expected_edge_marks_and_graphs() -> None:
    directed = make_directed_edge("A", "B")
    bidirected = make_bidirected_edge("B", "C")

    assert (directed.src, directed.dst, directed.mark_src, directed.mark_dst) == (
        "A",
        "B",
        EdgeMark.TAIL,
        EdgeMark.ARROW,
    )
    assert (bidirected.src, bidirected.dst, bidirected.mark_src, bidirected.mark_dst) == (
        "B",
        "C",
        EdgeMark.ARROW,
        EdgeMark.ARROW,
    )

    dag = make_dag([("B", "C"), ("A", "B")], extra_nodes=("Z", "A"))
    assert dag.graph_type is GraphType.DAG
    assert dag.nodes == ["A", "B", "C", "Z"]
    assert [(edge.src, edge.dst) for edge in dag.edges] == [("B", "C"), ("A", "B")]

    admg = make_admg(["Y", "X"], [make_bidirected_edge("X", "Y")], metadata={"case": "bow"})
    assert admg.graph_type is GraphType.ADMG
    assert admg.nodes == ["Y", "X"]
    assert admg.metadata == {"case": "bow"}


def test_result_projection_and_rule_subsequence_are_content_based() -> None:
    estimand = SimpleNamespace(to_latex=lambda: "P(Y | do(X=2.0))")
    result = SimpleNamespace(
        estimand_ast=estimand,
        recovery_estimand=None,
        proof_steps=[
            SimpleNamespace(rule_name="ID_DECOMPOSE"),
            SimpleNamespace(rule_name="ID_FACTORIZE"),
            SimpleNamespace(rule_name="ID_SUM_OUT"),
        ],
    )

    assert canon("P(Y | do(X=2.0))") == "P(Y|do(X=2))"
    assert canon(None) is None
    assert latex_from_result(result) == "P(Y | do(X=2.0))"
    assert latex_from_result(SimpleNamespace()) is None
    assert rule_names_from_result(result) == ["ID_DECOMPOSE", "ID_FACTORIZE", "ID_SUM_OUT"]
    assert is_rule_subsequence(result, ("ID_DECOMPOSE", "ID_SUM_OUT"))
    assert not is_rule_subsequence(result, ("ID_SUM_OUT", "ID_DECOMPOSE"))


@pytest.mark.parametrize(
    ("probe", "module_name"),
    [(y0_available, "y0"), (dowhy_available, "dowhy")],
)
def test_optional_comparator_probe_reports_importability(
    monkeypatch: pytest.MonkeyPatch,
    probe: Callable[[], bool],
    module_name: str,
) -> None:
    original_import = builtins.__import__
    imported: list[str] = []

    def import_available(name, *args, **kwargs):
        if name == module_name:
            imported.append(name)
            return ModuleType(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_available)

    assert probe() is True
    assert imported == [module_name]


@pytest.mark.parametrize(
    ("probe", "module_name"),
    [(y0_available, "y0"), (dowhy_available, "dowhy")],
)
def test_optional_comparator_probe_reports_missing_module_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    probe: Callable[[], bool],
    module_name: str,
) -> None:
    original_import = builtins.__import__

    def import_missing(name, *args, **kwargs):
        if name == module_name:
            raise ModuleNotFoundError(f"No module named {module_name!r}", name=module_name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_missing)

    assert probe() is False


def test_symbolic_runner_help_keeps_standalone_cli_available() -> None:
    result = subprocess.run(
        [sys.executable, str(_RUNNER), "--help"],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
    assert "--tags" in result.stdout


def test_symbolic_runner_import_does_not_load_pytest_configuration() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import runpy, sys; "
                "runpy.run_path(sys.argv[1], run_name='symbolic_import_probe'); "
                "assert 'benchmarks.conftest' not in sys.modules"
            ),
            str(_RUNNER),
        ],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr

"""Exercise the real producer and explicitly controlled evidence-admission fixtures."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tools.quality.testing import mutation


def _project(tmp_path: Path, *, source: str = "return value + 1") -> Path:
    root = tmp_path / "project"
    (root / "tests").mkdir(parents=True)
    (root / "sample_math.py").write_text(f"def adjust(value):\n    {source}\n")
    (root / "sibling.py").write_text("raise AssertionError('sibling source imported')\n")
    (root / "tests/test_sample_math.py").write_text(
        "import sample_math\n"
        "def test_adjust():\n"
        "    assert 'mutants' in sample_math.__file__\n"
        "    assert sample_math.adjust(2) == 3\n"
    )
    (root / "tests/test_sibling.py").write_text("raise AssertionError('sibling test collected')\n")
    return root


def _target() -> mutation.MutationTarget:
    return mutation.MutationTarget(
        paths="sample_math.py", tests="tests/test_sample_math.py", threshold_pct=100.0
    )


def _result(root: Path) -> dict:
    return json.loads((root / "_build/mutation/probe.json").read_text())


@pytest.fixture
def supported_real_engine() -> None:
    if reason := mutation._unsupported_station():
        pytest.skip(f"UNRUN real mutation execution: {reason}")


def test_declared_native_station_is_unrun_before_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _project(tmp_path)
    monkeypatch.setattr(mutation.sys, "platform", "darwin")
    monkeypatch.setattr(mutation.sys, "version_info", (3, 14, 3))
    monkeypatch.setattr(mutation.platform, "machine", lambda: "arm64")

    def unexpected_engine(*args, **kwargs):
        pytest.fail("unsupported station launched a mutation subprocess")

    monkeypatch.setattr(mutation, "run_command", unexpected_engine)
    assert mutation._run_target(root, name="probe", target=_target()) == 2
    result = _result(root)
    assert result["status"] == "unrun"
    assert "unsupported mutation station" in result["reason"]
    assert "supported Linux station" in result["reason"]
    assert "workspace" not in result


def test_real_mutant_is_killed_without_running_or_mutating_sibling(
    tmp_path: Path, supported_real_engine: None
) -> None:
    root = _project(tmp_path)
    assert mutation._run_target(root, name="probe", target=_target()) == 0
    result = _result(root)
    assert result["status"] == "pass"
    assert result["killed"] == result["total"] > 0
    assert result["mutated_sources"] == ["sample_math.py"]
    assert result["executed_tests"] == ["tests/test_sample_math.py::test_adjust"]
    assert not (root / "mutants").exists()


def test_failing_clean_baseline_is_unrun(tmp_path: Path, supported_real_engine: None) -> None:
    root = _project(tmp_path, source="return value + 2")
    assert mutation._run_target(root, name="probe", target=_target()) == 2
    result = _result(root)
    assert result["status"] == "unrun"
    assert result["reason"].startswith("mutmut run did not execute successfully:")
    assert (
        "FAILED tests/test_sample_math.py::test_adjust"
        in (Path(result["workspace"]) / "run.log").read_text()
    )


def test_zero_mutants_is_unrun(tmp_path: Path, supported_real_engine: None) -> None:
    root = _project(tmp_path)
    (root / "sample_math.py").write_text("VALUE = 3\n")
    (root / "tests/test_sample_math.py").write_text(
        "from sample_math import VALUE\ndef test_value():\n    assert VALUE == 3\n"
    )
    assert mutation._run_target(root, name="probe", target=_target()) == 2
    result = _result(root)
    assert result["status"] == "unrun"
    assert result["reason"].startswith("mutmut run did not execute successfully:")
    assert (
        "could not find any test case for any mutant"
        in (Path(result["workspace"]) / "run.log").read_text()
    )


def test_real_survivor_is_failure(tmp_path: Path, supported_real_engine: None) -> None:
    root = _project(tmp_path)
    (root / "tests/test_sample_math.py").write_text(
        "import sample_math\ndef test_adjust():\n    assert sample_math.adjust(2) > 0\n"
    )
    assert mutation._run_target(root, name="probe", target=_target()) == 1
    assert _result(root)["status"] == "fail"
    assert _result(root)["survived"] > 0


def _controlled_results(work: Path, *, survived: bool = False) -> None:
    """Write controlled protocol outcomes, not a claim that real mutants ran."""
    mutants = work / "mutants"
    mutants.mkdir()
    (mutants / "sample_math.py").write_text(
        "def x_adjust__mutmut_1(value):\n    return value - 1\n"
    )
    (mutants / "sample_math.py.meta").write_text(
        json.dumps({"exit_code_by_key": {"sample_math.x_adjust__mutmut_1": 0 if survived else 1}})
    )
    (mutants / "mutmut-cicd-stats.json").write_text(
        json.dumps({"total": 1, "killed": int(not survived), "survived": int(survived)})
    )
    (mutants / "mutmut-stats.json").write_text(
        json.dumps({"duration_by_test": {"tests/test_sample_math.py::test_adjust": 0.01}})
    )


@pytest.mark.parametrize(
    "corruption",
    [
        "none",
        "survivor",
        "remove_summary",
        "false_total",
        "remove_metadata",
        "internal_error",
        "sibling_test",
        "sibling_source",
        "zero_mutants",
    ],
)
def test_controlled_protocol_admission_consumes_outcomes_and_rejects_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corruption: str
) -> None:
    root = _project(tmp_path)
    produced = False

    def controlled_engine(argv, **kwargs):
        nonlocal produced
        if "export-cicd-stats" in argv:
            work = Path(kwargs["cwd"])
            _controlled_results(work, survived=corruption == "survivor")
            # The unmodified controlled evidence must pass before the removal probe.
            baseline = mutation._admit(work, ["sample_math.py"], ["tests/test_sample_math.py"])
            assert baseline["total"] == 1
            produced = True
            summary = work / "mutants/mutmut-cicd-stats.json"
            if corruption == "remove_summary":
                summary.unlink()
            elif corruption == "false_total":
                payload = json.loads(summary.read_text())
                payload["total"] += 1
                summary.write_text(json.dumps(payload))
            elif corruption == "remove_metadata":
                (work / "mutants/sample_math.py.meta").unlink()
            elif corruption == "internal_error":
                metadata = work / "mutants/sample_math.py.meta"
                payload = json.loads(metadata.read_text())
                first = next(iter(payload["exit_code_by_key"]))
                payload["exit_code_by_key"][first] = 3
                metadata.write_text(json.dumps(payload))
            elif corruption == "sibling_test":
                (work / "mutants/mutmut-stats.json").write_text(
                    json.dumps({"duration_by_test": {"tests/test_sibling.py::test_sibling": 0.01}})
                )
            elif corruption == "sibling_source":
                (work / "mutants/sibling.py.meta").write_text("{}")
            elif corruption == "zero_mutants":
                (work / "mutants/sample_math.py").write_text("VALUE = 3\n")
                (work / "mutants/sample_math.py.meta").write_text(
                    json.dumps({"exit_code_by_key": {}})
                )
                summary.write_text(json.dumps({"total": 0, "killed": 0, "survived": 0}))
        return subprocess.CompletedProcess(
            argv, 0, stdout="controlled protocol fixture\n", stderr=""
        )

    monkeypatch.setattr(mutation, "_unsupported_station", lambda: None)
    monkeypatch.setattr(mutation, "run_command", controlled_engine)
    expected = {"none": (0, "pass"), "survivor": (1, "fail")}.get(corruption, (2, "unrun"))
    assert mutation._run_target(root, name="probe", target=_target()) == expected[0]
    assert produced
    assert _result(root)["status"] == expected[1]


def test_missing_declared_source_never_becomes_empty_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mutation, "_unsupported_station", lambda: None)
    root = _project(tmp_path)
    target = mutation.MutationTarget(
        paths="missing.py", tests="tests/test_sample_math.py", threshold_pct=100.0
    )
    assert mutation._run_target(root, name="probe", target=target) == 2
    assert "missing" in _result(root)["reason"]

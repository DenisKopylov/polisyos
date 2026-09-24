"""Behavioral checks for structure verdicts across real Git stations."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

VALIDATION_SCRIPT = (
    Path(__file__).resolve().parents[3] / "tools/quality/validation/repository_structure_phase0.py"
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def station(tmp_path: Path) -> Path:
    root = tmp_path / "station"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.name", "Instrument probe")
    _git(root, "config", "user.email", "probe@example.invalid")
    product = root / "policy-engine"
    product.mkdir()
    (product / "pyproject.toml").write_text('[project]\nname="probe"\nversion="0"\n')
    (root / ".gitignore").write_text(".benchmarks/\n.polisyos-tools/\n.tmp/\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "probe base")
    return root


def _gate(root: Path, *args: str) -> tuple[int, list[dict]]:
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATION_SCRIPT),
            "--repo-root",
            str(root / "policy-engine"),
            "gate",
            "--json",
            *args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "Traceback" not in result.stderr, result.stderr
    return result.returncode, json.loads(result.stdout)["findings"]


def test_ignored_and_untracked_state_does_not_change_commit_verdict(station: Path) -> None:
    clean = station.parent / "clean"
    _git(station, "worktree", "add", "--detach", str(clean), "HEAD")
    for name in (".benchmarks", ".polisyos-tools", ".tmp"):
        (station / "policy-engine" / name).mkdir()
    namespace = station / "policy-engine/src/polisyos/local_probe"
    namespace.mkdir(parents=True)
    (namespace / "__init__.py").write_text("")

    assert _gate(clean) == (0, [])
    assert _gate(station) == _gate(clean)
    assert _gate(station, "--mode", "fail-closed") == _gate(clean, "--mode", "fail-closed")


def test_default_refuses_committed_output_even_when_directory_is_ignored(station: Path) -> None:
    output = station / "policy-engine/.tmp/committed-output"
    output.parent.mkdir()
    output.write_text("tracked")
    _git(station, "add", "-f", "policy-engine/.tmp/committed-output")

    code, findings = _gate(station)

    assert code == 1, findings
    assert [(item["gate"], item.get("path")) for item in findings] == [
        ("build_output_gate", "policy-engine/.tmp")
    ]


def test_missing_tracked_input_is_reported_instead_of_disappearing(station: Path) -> None:
    output = station / "policy-engine/.tmp/committed-output"
    output.parent.mkdir()
    output.write_text("tracked")
    _git(station, "add", "-f", "policy-engine/.tmp/committed-output")
    output.unlink()

    code, findings = _gate(station)

    assert code == 2
    assert [item["gate"] for item in findings] == ["repository_input"]
    assert "Tracked input is unavailable" in findings[0]["message"]


def test_untracked_policy_and_catalog_peer_cannot_change_gate_inputs(station: Path) -> None:
    product = station / "policy-engine"
    for relative in (
        "src/polisyos/foundry/methods/catalog/__init__.py",
        "src/polisyos/foundry/methods/probe/__init__.py",
        "src/polisyos/widget/api.py",
    ):
        path = product / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    _git(station, "add", ".")
    before = {gate: _gate(station, "--gate", gate) for gate in ("empty_namespace", "loose_files")}
    (product / "src/polisyos/foundry/methods/catalog/probe").mkdir()
    layout = product / "architecture/packages/layout.toml"
    layout.parent.mkdir(parents=True)
    layout.write_text("[defaults]\nmax_root_py_files = 0\n")

    assert {
        gate: _gate(station, "--gate", gate) for gate in ("empty_namespace", "loose_files")
    } == before


def test_required_configuration_cannot_be_supplied_by_the_station(station: Path) -> None:
    (station / "policy-engine/README.md").write_text("Probe product\n")
    _git(station, "add", "policy-engine/README.md")
    _git(station, "rm", "policy-engine/pyproject.toml")
    before = _gate(station)
    (station / "policy-engine/pyproject.toml").write_text("[project]\nname='local'\n")

    after = _gate(station)

    assert before[0] == after[0] == 2
    assert [item["gate"] for item in before[1]] == ["repository_input"]
    assert [item["gate"] for item in after[1]] == ["repository_input"]


@pytest.mark.parametrize(("lines", "expected_code"), [(300, 0), (301, 1)])
def test_pyproject_reports_physical_measurement_and_semantic_omissions(
    station: Path, lines: int, expected_code: int
) -> None:
    manifest = station / "policy-engine/pyproject.toml"
    original = manifest.read_text()
    manifest.write_text(original + "# no configuration change\n" * (lines - 3))
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATION_SCRIPT),
            "--repo-root",
            str(manifest.parent),
            "gate",
            "--gate",
            "pyproject_size",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(result.stdout)
    assert result.returncode == expected_code, result.stderr
    assert report["status"] == ("FAILED" if expected_code else "passed")
    assert report["measurement"]["pyproject_physical_lines"] == lines
    assert report["measurement"]["pyproject_max_lines"] == 300
    assert "comments and blank lines" in report["measurement"]["measures"]
    assert "configuration complexity" in report["measurement"]["not_measured"]
    assert "dependency correctness" in report["measurement"]["not_measured"]
    assert report["complete_verdict"] is True


@pytest.mark.parametrize("mode", ["report-only", "fail-closed"])
def test_missing_pyproject_is_unrun_even_when_report_only(station: Path, mode: str) -> None:
    (station / "policy-engine/pyproject.toml").unlink()
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATION_SCRIPT),
            "--repo-root",
            str(station / "policy-engine"),
            "gate",
            "--gate",
            "pyproject_size",
            "--mode",
            mode,
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(result.stdout)
    assert result.returncode == 2
    assert report["status"] == "UNRUN"
    assert report["complete_verdict"] is False
    assert report["finding_coverage"] == "partial"
    assert "pyproject.toml" in report["findings"][0]["message"]
    assert "Traceback" not in result.stderr


def test_registered_pyproject_command_prints_omissions_on_clean_input(station: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.cli",
            "validation",
            "repository-structure-phase0",
            "--repo-root",
            str(station / "policy-engine"),
            "gate",
            "--gate",
            "pyproject_size",
        ],
        cwd=VALIDATION_SCRIPT.parents[3],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "passed" in result.stdout
    assert "Not measured:" in result.stdout
    assert "configuration complexity" in result.stdout
    assert "comments and blank lines" in result.stdout


def test_malformed_gate_policy_is_unrun_instead_of_a_traceback(station: Path) -> None:
    policy = station / "policy-engine/architecture/exceptions/structure_remediation.toml"
    policy.parent.mkdir(parents=True)
    policy.write_text("[broken\n")
    _git(station, "add", "policy-engine/architecture/exceptions/structure_remediation.toml")
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATION_SCRIPT),
            "--repo-root",
            str(station / "policy-engine"),
            "gate",
            "--gate",
            "pyproject_size",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == "UNRUN"
    assert report["finding_coverage"] == "partial"
    assert report["complete_verdict"] is False
    assert report["findings"][0]["gate"] == "repository_input"
    assert "Traceback" not in result.stderr

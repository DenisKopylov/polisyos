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

    assert code == 1
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

    assert before[0] == after[0] == 1
    assert [item["gate"] for item in before[1]] == ["repository_input"]
    assert [item["gate"] for item in after[1]] == ["repository_input"]

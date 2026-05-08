from __future__ import annotations

import subprocess
import tomllib
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PHASE7_GATES = {
    "empty_namespace_gate",
    "loose_files_gate",
    "name_collision_gate",
    "pyproject_size_gate",
    "cache_dir_gate",
    "build_output_gate",
    "dynamic_imports_gate",
    "pickle_compat_gate",
    "public_surface_snapshot_gate",
    "import_cycles_gate",
    "import_time_regression_gate",
    "reexport_shim_shape_gate",
}


def _read_toml(path: str) -> dict:
    with (REPO_ROOT / path).open("rb") as stream:
        return tomllib.load(stream)


def test_phase7_structure_gate_registry_is_fail_closed() -> None:
    payload = _read_toml("architecture/gates/structure_remediation.toml")
    header = payload["structure_remediation_gates"]
    gates = {gate["id"]: gate for gate in payload["gate"]}

    assert header["status"] == "fail_closed"
    assert header["phase"] == "repository-structure-remediation-phase-7"
    assert set(gates) >= PHASE7_GATES
    for gate_id in PHASE7_GATES:
        gate = gates[gate_id]
        assert gate["mode"] == "fail_closed", gate_id
        assert "report-only" not in gate["command"], gate_id
    for gate_id in {"loose_files_gate", "cache_dir_gate", "build_output_gate"}:
        assert gates[gate_id]["exceptions"] == "architecture/exceptions/structure_remediation.toml"


def test_phase7_structure_exceptions_are_owner_approved_and_time_bounded() -> None:
    payload = _read_toml("architecture/exceptions/structure_remediation.toml")
    header = payload["structure_remediation_exceptions"]
    today = date.today()

    assert header["status"] == "active"
    assert header["phase"] == "repository-structure-remediation-phase-7"
    for exception in payload["exception"]:
        assert exception["id"]
        assert exception["gate"] in PHASE7_GATES
        assert exception["owner"].startswith("team-")
        assert exception["reason"]
        assert exception["match"]
        sunset = exception["sunset"]
        assert sunset != "none"
        assert date.fromisoformat(sunset) >= today, exception["id"]


def test_phase7_structure_gates_run_fail_closed_with_registered_exceptions() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_structure_phase0.py",
            "gate",
            "--gate",
            "all",
            "--mode",
            "fail-closed",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_phase7_closeout_evidence_is_recorded() -> None:
    closeout = (
        REPO_ROOT / "docs" / "plans" / "accepted" / "REPOSITORY_STRUCTURE_REMEDIATION_CLOSEOUT.md"
    )
    accepted_plan = (
        REPO_ROOT / "docs" / "plans" / "accepted" / "REPOSITORY_STRUCTURE_REMEDIATION_PLAN.md"
    )

    assert closeout.exists()
    assert accepted_plan.exists()
    text = closeout.read_text(encoding="utf-8")
    assert "10,975 total tests" in text
    assert "0 failures" in text
    assert "phase3a-fulltests-12core-20260504-rerun-20260504T111449Z" in text

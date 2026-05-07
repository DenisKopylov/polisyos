from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATION_SCRIPT = (
    REPO_ROOT / "tools" / "quality" / "validation" / "repository_structure_phase0.py"
)


def _load_validation_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("repository_structure_phase0", VALIDATION_SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_toml(path: Path) -> dict:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_name_collision_gate_is_fail_closed() -> None:
    gates = _load_toml(REPO_ROOT / "architecture" / "structure_remediation_gates.toml")
    name_gate = next(gate for gate in gates["gate"] if gate["id"] == "name_collision_gate")

    assert name_gate["mode"] == "fail_closed"
    assert "tools/quality/validation/name_collision_gate.py" in name_gate["command"]


def test_phase1c_name_registry_covers_current_collisions() -> None:
    validation = _load_validation_module()

    findings = validation.collect_gate_findings(REPO_ROOT, "name_collision")

    assert findings == []


def test_phase1c_name_registry_fails_for_new_unregistered_collision() -> None:
    validation = _load_validation_module()
    inventory = {
        "repeated_directory_names": [
            {
                "name": "phase1c_unregistered_probe",
                "packages": [
                    {
                        "package": "core",
                        "locations": ["src/polisyos/core/phase1c_unregistered_probe"],
                    },
                    {
                        "package": "fabric",
                        "locations": ["src/polisyos/fabric/phase1c_unregistered_probe"],
                    },
                ],
            }
        ]
    }

    findings = validation.gate_name_collision(REPO_ROOT, inventory)

    assert findings
    assert findings[0]["unresolved_packages"] == ["core", "fabric"]


def test_phase1c_plan_names_have_registry_or_backlog_decisions() -> None:
    registry = _load_toml(REPO_ROOT / "architecture" / "name_registry.toml")
    shared = {entry["name"] for entry in registry.get("shared_name", [])}
    backlog = {entry["name"] for entry in registry.get("rename_backlog", [])}
    required_names = {
        "analytics",
        "causal",
        "contracts",
        "data_plane",
        "discovery",
        "governance",
        "kernel",
        "methods",
        "provenance",
        "runtime",
        "validation",
    }

    assert required_names <= shared | backlog


def test_runtime_collision_inventory_includes_top_level_runtime_package() -> None:
    validation = _load_validation_module()
    inventory = validation.collect_inventory(REPO_ROOT)
    runtime_entry = next(
        entry for entry in inventory["repeated_directory_names"] if entry["name"] == "runtime"
    )

    packages = {entry["package"] for entry in runtime_entry["packages"]}

    assert {"foundry", "runtime"}.issubset(packages)

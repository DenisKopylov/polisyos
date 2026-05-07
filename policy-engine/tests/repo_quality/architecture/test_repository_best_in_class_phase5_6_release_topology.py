from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase5_6_migration_classes_are_physical_and_documented() -> None:
    contract = _read_toml("ops/migrations/migration-contracts.toml")
    classes = {item["id"]: item for item in contract["migration_class"]}

    assert {"db", "runtime_state", "api_schemas", "ir"} == set(classes)
    for class_id, migration_class in classes.items():
        target_path = REPO_ROOT / migration_class["target_path"]
        assert target_path.is_dir(), class_id
        assert (target_path / "README.md").exists(), class_id
        assert migration_class["operator_docs"], class_id

    assert list((REPO_ROOT / "ops/migrations/db").glob("*.sql"))
    assert not list((REPO_ROOT / "ops/migrations").glob("*.sql"))


def test_phase5_6_python_helper_bindings_point_to_live_contracts() -> None:
    from tools.ops_runners.migrations.contracts import validate_helper_binding

    contract = _read_toml("ops/migrations/migration-contracts.toml")
    bindings = {item["artifact"]: item for item in contract["helper_binding"]}
    assert {
        "policy_ir",
        "dataset_manifest",
        "run_manifest",
        "duckdb_to_postgresql",
    } == set(bindings)

    for artifact in bindings:
        binding = validate_helper_binding(artifact, REPO_ROOT)
        assert binding.release_gate.startswith("ops/release/promotion-gates.toml#")


def test_phase5_6_policy_ir_helper_uses_bound_ir_registry(tmp_path: Path) -> None:
    from tools.ops_runners.migrations import migrate

    source = tmp_path / "policy_ir.json"
    target = tmp_path / "migrated.json"
    source.write_text('{"schema_version":"1.0","payload":"same-version smoke"}', encoding="utf-8")

    assert migrate.main(["policy_ir", str(source), str(target)]) == 0
    assert '"schema_version": "1.0"' in target.read_text(encoding="utf-8")


def test_phase5_6_release_topology_declares_cli_and_breaking_migration_gate() -> None:
    topology = _read_toml("ops/release/deployment-topology.toml")
    units = {item["id"]: item for item in topology["deployment_unit"]}
    assert {"control_plane", "data_plane", "frontend", "cli", "python_packages"} <= set(units)

    gates = _read_toml("ops/release/promotion-gates.toml")
    gate_ids = {item["id"] for item in gates["gate"]}
    assert "breaking_migration_runbook_docs" in gate_ids
    assert "cli_command_surface" in gate_ids

    for unit in units.values():
        assert set(unit["required_gates"]) <= gate_ids, unit["id"]


def test_phase5_6_breaking_migration_docs_are_gate_evidence() -> None:
    gates = _read_toml("ops/release/promotion-gates.toml")
    gate = {item["id"]: item for item in gates["gate"]}["breaking_migration_runbook_docs"]

    for path in gate["required_evidence"]:
        assert _path_exists(path), path

    runbook = (REPO_ROOT / "docs/runbooks/migration-release-promotion.md").read_text(
        encoding="utf-8"
    )
    for term in ("runtime-state", "API schema", "IR schema", "persisted artifact"):
        assert term in runbook


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _path_exists(path: str) -> bool:
    if any(char in path for char in "*?["):
        return bool(list(REPO_ROOT.glob(path)))
    return (REPO_ROOT / path).exists()

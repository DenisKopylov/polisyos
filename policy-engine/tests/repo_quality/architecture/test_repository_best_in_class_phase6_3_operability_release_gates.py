# ruff: noqa: S101, S607

from __future__ import annotations

import subprocess
import tomllib
from pathlib import Path
from typing import Any

from tools.ops_runners.release import check_operability_release_gates as gates

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent


def test_phase6_3_operability_release_gate_contract_is_fail_closed() -> None:
    contract = _read_toml("architecture/operability_release_supply_chain_gates.toml")
    header = contract["operability_release_supply_chain_gates"]
    gate_ids = {item["id"]: item for item in contract["gate"]}

    assert header["status"] == "fail_closed"
    assert header["phase"] == "repository-best-in-class-phase-6.3"
    assert (
        header["gate_command"]
        == "uv run polisyos-tools release check-operability-release-gates --fail-closed"
    )
    assert header["release_workflow"] == ".github/workflows/release.yml"
    assert header["release_workflow_job"] == "operability-release-gate"
    assert header["promotion_gate_id"] == "operability_release_supply_chain"
    assert {
        "slo-runbook-coverage",
        "component-observability",
        "alert-to-runbook",
        "migration-classes",
        "release-topology",
        "promotion-gates",
        "compatibility-release-metadata",
        "release-supply-chain",
        "workflow-permissions-oidc",
    } == set(gate_ids)

    for raw_path in header["source_contracts"]:
        assert _path_or_glob_exists(raw_path), raw_path
    for gate in gate_ids.values():
        assert gate["mode"] == "fail_closed", gate["id"]
        assert gate["owner"].startswith("team-"), gate["id"]
        assert gate["blocks"], gate["id"]
        for raw_path in gate["source_contracts"]:
            assert _path_or_glob_exists(raw_path), (gate["id"], raw_path)


def test_phase6_3_release_topology_requires_operability_supply_chain_gate() -> None:
    topology = _read_toml("ops/release/deployment-topology.toml")
    promotion = _read_toml("ops/release/promotion-gates.toml")
    units = {item["id"]: item for item in topology["deployment_unit"]}
    promotion_gates = {item["id"]: item for item in promotion["gate"]}

    assert topology["deployment_topology"]["mode"] == "fail_closed"
    assert promotion["promotion_gates"]["mode"] == "fail_closed"
    assert "operability_release_supply_chain" in promotion_gates
    assert "compatibility_release_metadata" in promotion_gates

    for unit in units.values():
        assert "operability_release_supply_chain" in unit["required_gates"], unit["id"]
        assert "compatibility_release_metadata" in unit["required_gates"], unit["id"]
        assert set(unit["required_gates"]) <= set(promotion_gates), unit["id"]


def test_phase6_3_release_workflow_blocks_on_operability_gate() -> None:
    workflow = (WORKSPACE_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "operability-release-gate:" in workflow
    assert "Release / Operability and promotion gates" in workflow
    assert "check-operability-release-gates" in workflow
    assert "--fail-closed" in workflow
    assert "release-operability-gates" in workflow

    supply_chain = _read_toml("architecture/control_plane_supply_chain.toml")
    release_tier = {item["id"]: item for item in supply_chain["ruleset_tier"]}[
        "release-gate-checks"
    ]
    assert "Release / Operability and promotion gates" in release_tier["required_jobs"]
    release_candidate = {item["phase"]: item for item in supply_chain["release_phase_gate"]}[
        "release_candidate"
    ]
    assert "operability release gate" in release_candidate["checks"]


def test_phase6_3_fail_closed_report_has_no_findings() -> None:
    report = gates.build_report(repo_root=REPO_ROOT)

    assert report["phase"] == "repository-best-in-class-phase-6.3"
    assert report["mode"] == "fail_closed"
    assert report["status"] == "passed", report["findings"]
    assert report["finding_count"] == 0, report["findings"]
    assert report["summary"]["operability"]["public_stable_component_count"] >= 8
    assert report["summary"]["release_promotion"]["deployment_unit_count"] >= 6
    assert report["summary"]["supply_chain"]["control_plane_blocker_count"] == 0


def test_phase6_3_release_tool_is_registered_and_cli_passes() -> None:
    from tools.registry import TOOL_SPECS_BY_KEY

    spec = TOOL_SPECS_BY_KEY[("release", "check-operability-release-gates")]

    assert spec.module == "tools.ops_runners.release.check_operability_release_gates"
    assert spec.callable_name == "main"
    assert spec.status.value == "active"

    completed = subprocess.run(
        [
            "uv",
            "run",
            "polisyos-tools",
            "release",
            "check-operability-release-gates",
            "--fail-closed",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "repository-best-in-class-phase-6.3" in completed.stdout


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _path_or_glob_exists(path: str) -> bool:
    base = WORKSPACE_ROOT if path.startswith(".github/") else REPO_ROOT
    if any(char in path for char in "*?["):
        return bool(list(base.glob(path)))
    return (base / path).exists()

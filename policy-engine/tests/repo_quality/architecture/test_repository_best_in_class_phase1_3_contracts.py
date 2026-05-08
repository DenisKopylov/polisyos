from __future__ import annotations

import datetime as dt
import json
import tomllib
from pathlib import Path
from typing import Any

from tools.quality.validation import architecture_report_only_contracts as phase1_3

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase1_3_package_contracts_are_primary_and_mirrored() -> None:
    package_paths = sorted(
        path
        for path in (REPO_ROOT / "architecture" / "packages").glob("*.toml")
        if path.stem not in {"boundaries", "layout"}
    )
    contracts = {path.stem: _read_toml(path) for path in package_paths}
    expected_modules = {
        item["module"]
        for item in _read_toml(REPO_ROOT / "architecture" / "packages" / "boundaries.toml")[
            "package"
        ]
    } | {
        item["module"]
        for item in _read_toml(REPO_ROOT / "architecture" / "public_surface" / "contract.toml")["package"]
    }
    contract_modules = {contract["package"]["module"] for contract in contracts.values()}

    assert expected_modules == contract_modules

    for package_id, contract in contracts.items():
        package = contract["package"]
        assert package["primary_contract"] is True
        assert package["gate_mode"] == "report_only"
        assert package["owner"]
        assert package["legacy_aggregate_mirrors"]
        for sunset in contract.get("sunset", []):
            assert _date(sunset["date"]) >= dt.date.today()

        for table in (
            "layout",
            "boundaries",
            "public_surface",
            "tests",
            "slo_runbook",
            "observability",
            "name_collisions",
            "exceptions",
            "sunsets",
            "extension_host",
        ):
            assert table in contract, (package_id, table)

        assert contract["boundaries"]["public_facade"].startswith("polisyos.")
        assert "allowed_dependencies" in contract["boundaries"]
        assert contract["boundaries"]["forbidden_dependencies"]
        assert contract["tests"]["unit_roots"]
        assert "integration_required" in contract["tests"]
        assert "property_required" in contract["tests"]
        assert contract["public_surface"]["supported_entrypoints"]
        assert contract["extension_host"]["status"]
        assert "extension_points" in contract["extension_host"]
        assert contract["name_collisions"]["status"] in {"none", "declared"}
        assert contract["exceptions"]["status"] in {"none", "declared"}

    families = {
        family["id"]: family
        for family in _read_toml(REPO_ROOT / "architecture" / "generated_artifacts.toml")["family"]
    }
    aggregate = families["architecture-package-contract-aggregates"]
    assert aggregate["source_of_truth"] == "architecture/packages/*.toml"
    assert aggregate["drift_gate"] == "automated_report_only"


def test_phase1_3_report_only_gates_have_owners_evidence_and_no_fail_closed_mode() -> None:
    payload = _read_toml(REPO_ROOT / "architecture" / "gates" / "report_only.toml")
    gates = {gate["id"]: gate for gate in payload["gate"]}

    assert payload["report_only_gates"]["status"] == "report_only"
    assert {
        "package-contract-schema",
        "package-aggregate-mirror",
        "module-size-budget",
        "generated-artifact-contracts",
        "extension-points",
        "runbook-coverage",
        "component-observability",
        "runtime-state-layout",
        "test-ratchets",
        "directory-contracts",
        "static-analysis-overrides",
    } <= set(gates)

    for gate in gates.values():
        assert gate["mode"] == "report_only", gate["id"]
        assert gate["owner"], gate["id"]
        assert gate["command"], gate["id"]
        assert _path_pattern_exists(gate["evidence"]), gate["id"]
        assert _date(gate["target_fail_closed_not_before"]) >= dt.date.today()
        for source in gate["source_contracts"]:
            assert _path_pattern_exists(source), (gate["id"], source)


def test_phase1_3_requested_contract_surfaces_are_drafted_or_expanded() -> None:
    groups = _read_toml(REPO_ROOT / "architecture" / "conceptual_groups.toml")
    assert groups["conceptual_groups"]["status"] == "report_only"
    assert {group["id"] for group in groups["group"]} == {
        "packages",
        "imports",
        "public_surface",
        "exceptions",
        "policies",
        "gates",
        "baselines",
    }

    expected_statuses = {
        "architecture/tests/ratchets.toml": "active",
        "architecture/tooling/static_analysis_overrides.toml": "report_only",
        "architecture/imports/reports.toml": "report_only",
    }
    for relative_path, table in {
        "architecture/tests/ratchets.toml": "test_ratchets",
        "architecture/tooling/static_analysis_overrides.toml": "static_analysis_overrides",
        "architecture/imports/reports.toml": "import_reports",
    }.items():
        payload = _read_toml(REPO_ROOT / relative_path)
        assert payload[table]["status"] == expected_statuses[relative_path], relative_path

    for relative_path, table in {
        "architecture/runbook_coverage.toml": "runbook_coverage",
        "architecture/component_observability.toml": "component_observability",
    }.items():
        payload = _read_toml(REPO_ROOT / relative_path)
        assert payload[table]["default_gate_mode"] == "report_only", relative_path

    runtime_state = _read_toml(REPO_ROOT / "architecture" / "runtime_state_layout.toml")
    assert runtime_state["runtime_state_layout"]["default_gate_mode"] in {
        "report_only",
        "fail_closed",
    }
    assert runtime_state["state_surface"]

    extension_points = _read_toml(REPO_ROOT / "architecture" / "extension_points.toml")
    assert extension_points["phase_1_3_report_only_overlay"]["status"] == "report_only"
    assert extension_points["phase_1_3_extension_point"]

    directory_contracts = _read_toml(REPO_ROOT / "architecture" / "policies" / "directory_contracts.toml")
    assert directory_contracts["phase_1_3_report_only_overlay"]["status"] == "report_only"
    assert {item["path"] for item in directory_contracts["phase_1_3_directory"]} >= {
        "architecture/packages",
        "architecture/gates",
        "architecture/imports",
    }

    static = _read_toml(REPO_ROOT / "architecture" / "tooling" / "static_analysis_overrides.toml")
    assert {item["id"] for item in static["dead_override_check"]} == {
        "inline-type-ignore-dead-check",
        "ruff-noqa-dead-check",
    }


def test_phase1_3_module_size_budget_sets_defaults_and_shrinking_god_module_budgets() -> None:
    payload = _read_toml(REPO_ROOT / "architecture" / "module_size_budget.toml")
    header = payload["module_size_budget"]

    assert header["status"] == "report_only"
    assert header["default_warning_lines"] == 1000
    assert header["default_fail_closed_target_lines"] == 2500
    assert _date(header["fail_closed_not_before"]) >= dt.date.today()

    budgets = payload["budget"]
    assert len(budgets) >= 10
    assert {
        "src/polisyos/foundry/methods/catalog/causal/causal_engine.py",
        "src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py",
        "src/polisyos/runtime/http/services/control.py",
    } <= {budget["path"] for budget in budgets}

    for budget in budgets:
        assert (REPO_ROOT / budget["path"]).exists(), budget["path"]
        assert budget["warning_lines"] == 1000
        assert budget["target_lines"] <= 2500
        assert budget["next_ratchet_lines"] < budget["baseline_lines"] or (
            budget["next_ratchet_lines"]
            == budget["target_lines"]
            == budget["baseline_lines"]
            == 2500
        )
        assert budget["report_only_limit_lines"] >= budget["target_lines"]
        assert _date(budget["sunset"]) >= dt.date.today()


def test_phase1_3_report_only_validator_reports_without_contract_errors(tmp_path: Path) -> None:
    packages_report = phase1_3.build_report(REPO_ROOT, report="packages")
    assert packages_report["mode"] == "report_only"
    assert packages_report["contract_error_count"] == 0
    assert packages_report["summary"]["package_contract_count"] >= 16
    assert packages_report["summary"]["report_only_gate_count"] >= 12

    mirror_report = phase1_3.build_report(REPO_ROOT, report="package-mirrors")
    assert mirror_report["contract_error_count"] == 0

    output = tmp_path / "phase1_3_report.json"
    assert (
        phase1_3.run_cli(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--report",
                "package-mirrors",
                "--fail-on-contract-errors",
                "--json-output",
                str(output),
            ]
        )
        == 0
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "reported"


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _path_pattern_exists(pattern: str) -> bool:
    if any(char in pattern for char in "*?["):
        return bool(list(REPO_ROOT.glob(pattern)))
    return (REPO_ROOT / pattern).exists()


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)

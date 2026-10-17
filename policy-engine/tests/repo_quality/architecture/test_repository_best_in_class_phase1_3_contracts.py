from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest

from tools.quality.validation import architecture_report_only_contracts as phase1_3

REPO_ROOT = phase1_3.REPO_ROOT


def test_phase1_3_package_contracts_are_primary_and_mirrored() -> None:
    family_registry = _read_toml(REPO_ROOT / "architecture" / "generated_artifacts.toml")
    family = next(
        item
        for item in family_registry["family"]
        if item["id"] == "architecture-package-contract-aggregates"
    )
    registered_outputs = set(family["outputs"])
    package_paths = sorted(
        path
        for path in (REPO_ROOT / "architecture" / "packages").glob("*.toml")
        if path.relative_to(REPO_ROOT).as_posix() not in registered_outputs
    )
    contracts = {path.stem: _read_toml(path) for path in package_paths}
    contract_modules = {contract["package"]["module"] for contract in contracts.values()}
    boundary_modules = {
        item["module"]
        for item in _read_toml(REPO_ROOT / "architecture" / "packages" / "boundaries.toml")[
            "package"
        ]
    }
    public_modules = {
        item["module"]
        for item in _read_toml(REPO_ROOT / "architecture" / "public_surface" / "contract.toml")[
            "package"
        ]
    }
    declared_entrypoints = {
        entry
        for contract in contracts.values()
        for entry in contract["public_surface"]["supported_entrypoints"]
    }

    assert boundary_modules == contract_modules
    assert contract_modules <= public_modules
    assert public_modules - contract_modules <= declared_entrypoints

    for package_id, contract in contracts.items():
        package = contract["package"]
        assert package["primary_contract"] is True
        assert package["gate_mode"] == "report_only"
        assert package["owner"]
        assert package["legacy_aggregate_mirrors"]
        for sunset in contract.get("sunset", []):
            assert isinstance(_date(sunset["date"]), dt.date)

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
    assert aggregate["source_of_truth"] == (
        "primary package contracts in architecture/packages/*.toml; "
        "registered family outputs are excluded"
    )
    assert "--fail-on-package-mirror-errors" in aggregate["check_command"]
    assert aggregate["drift_gate"] == "automated_report_only"


def test_phase1_3_report_only_gates_have_owners_evidence_and_no_fail_closed_mode() -> None:
    payload = _read_toml(REPO_ROOT / "architecture" / "gates" / "report_only.toml")
    gates = {gate["id"]: gate for gate in payload["gate"]}

    assert payload["report_only_gates"]["status"] == "report_only"
    assert {
        "package-contract-schema",
        "package-aggregate-mirror",
        "module-size-budget",
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
        assert isinstance(_date(gate["target_fail_closed_not_before"]), dt.date)
        for source in gate["source_contracts"]:
            assert _path_pattern_exists(source), (gate["id"], source)

    expiry_findings = [
        item
        for item in phase1_3._validate_report_only_gates(REPO_ROOT)
        if item.message == "target_fail_closed_not_before must be today or future"
    ]
    assert {item.subject: item.detail for item in expiry_findings} == dict.fromkeys(
        {
            "package-contract-schema",
            "debt-ledger-reconciliation",
            "compatibility-release-gates",
            "package-aggregate-mirror",
            "module-size-budget",
            "extension-points",
            "runbook-coverage",
            "component-observability",
            "runtime-state-layout",
            "test-ratchets",
            "directory-contracts",
            "directory-hygiene-assets",
            "static-analysis-overrides",
            "dead-static-analysis-overrides",
        },
        "2026-10-01",
    )


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

    directory_contracts = _read_toml(
        REPO_ROOT / "architecture" / "policies" / "directory_contracts.toml"
    )
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
        "src/polisyos/foundry/methods/catalog/causal/causal_engine/artifacts.py",
        "src/polisyos/scientist/nodes/builtins/decide/build_decision_packet.py",
        "src/polisyos/runtime/http/services/control/__init__.py",
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


def test_phase1_3_report_only_validator_scopes_package_mirror_property(tmp_path: Path) -> None:
    packages_report = phase1_3.build_report(REPO_ROOT, report="packages")
    assert packages_report["mode"] == "report_only"
    assert packages_report["contract_error_count"] > 0
    package_contract_errors = [
        item for item in packages_report["contract_errors"] if item["check"] == "package-contract"
    ]
    assert len(package_contract_errors) == 6
    expired = [
        item for item in package_contract_errors if "invalid or expired date" in item["message"]
    ]
    assert [(item["subject"], item["detail"]) for item in expired] == [
        ("architecture/packages/berl.toml", "2026-08-01"),
        ("architecture/packages/calibration.toml", "2026-08-01"),
        ("architecture/packages/common.toml", "2026-08-01"),
        ("architecture/packages/ddm.toml", "2026-08-01"),
        ("architecture/packages/fabric.toml", "2026-10-01"),
    ]
    assert any(
        item["subject"] == "polisyos.runtime.quality"
        and item["message"] == "aggregate package has no primary package contract file"
        for item in package_contract_errors
    )
    assert any(item["check"] == "report-only-gates" for item in packages_report["contract_errors"])
    assert packages_report["summary"]["package_contract_count"] >= 16
    report_gate_expiry_errors = [
        item
        for item in packages_report["contract_errors"]
        if item["check"] == "report-only-gates"
        and item["message"] == "target_fail_closed_not_before must be today or future"
    ]
    assert {item["subject"]: item["detail"] for item in report_gate_expiry_errors} == dict.fromkeys(
        {
            "package-contract-schema",
            "debt-ledger-reconciliation",
            "compatibility-release-gates",
            "package-aggregate-mirror",
            "module-size-budget",
            "extension-points",
            "runbook-coverage",
            "component-observability",
            "runtime-state-layout",
            "test-ratchets",
            "directory-contracts",
            "directory-hygiene-assets",
            "static-analysis-overrides",
            "dead-static-analysis-overrides",
        },
        "2026-10-01",
    )
    assert packages_report["summary"]["report_only_gate_count"] == 14

    mirror_report = phase1_3.build_report(REPO_ROOT, report="package-mirrors")
    family_check = mirror_report["summary"]["generated_family_checks"][
        "architecture-package-contract-aggregates"
    ]
    assert family_check["status"] == "failed"
    assert family_check["error_count"] == 14
    assert len(family_check["errors"]) == 14
    unbound_public_rows = family_check["unmapped_public_surface_rows"]
    assert set(unbound_public_rows) == {"polisyos.runtime.quality"}
    assert unbound_public_rows["polisyos.runtime.quality"]["status"] == "not_established"
    assert len(unbound_public_rows["polisyos.runtime.quality"]["unverified_fields"]) == 8
    assert mirror_report["contract_error_count"] > 0
    assert any(item["check"] == "package-contract" for item in mirror_report["contract_errors"])

    output = tmp_path / "phase1_3_report.json"
    assert (
        phase1_3.run_cli(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--report",
                "package-mirrors",
                "--fail-on-package-mirror-errors",
                "--json-output",
                str(output),
            ]
        )
        == 1
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert (
        payload["summary"]["generated_family_checks"]["architecture-package-contract-aggregates"][
            "status"
        ]
        == "failed"
    )
    assert (
        payload["summary"]["generated_family_checks"]["architecture-package-contract-aggregates"][
            "error_count"
        ]
        == 14
    )
    assert (
        phase1_3.run_cli(
            [
                "--repo-root",
                str(REPO_ROOT),
                "--report",
                "package-mirrors",
                "--fail-on-contract-errors",
            ]
        )
        == 1
    )


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _path_pattern_exists(pattern: str) -> bool:
    if any(char in pattern for char in "*?["):
        return bool(list(REPO_ROOT.glob(pattern)))
    return (REPO_ROOT / pattern).exists()


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def _copy_package_mirror_fixture(destination: Path) -> Path:
    architecture = destination / "architecture"
    shutil.copytree(REPO_ROOT / "architecture" / "packages", architecture / "packages")
    for relative in (
        "generated_artifacts.toml",
        "public_surface/contract.toml",
        "tests/topology.toml",
    ):
        source = REPO_ROOT / "architecture" / relative
        target = architecture / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return destination


PRODUCT_ROOT_FOR_TESTS = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file() and (parent / "tools").is_dir()
)


def _replace_array_table_value(
    path: Path,
    *,
    table: str,
    identity: str,
    value: str,
    field: str,
    replacement: str,
) -> None:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(rf"(?m)^\[\[{re.escape(table)}\]\]\s*$", text))
    for index in reversed(range(len(matches))):
        match = matches[index]
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start() : end]
        row = tomllib.loads(block)[table][0]
        if row.get(identity) == value:
            updated, count = re.subn(
                rf"(?m)^{re.escape(field)}\s*=.*$",
                replacement,
                block,
                count=1,
            )
            if count != 1:
                raise AssertionError(f"field not found in {table} row: {field}")
            path.write_text(text[: match.start()] + updated + text[end:], encoding="utf-8")
            return
    raise AssertionError(f"array row not found: {table}.{identity}={value}")


def _drop_array_row(path: Path, table: str, identity: str, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(rf"(?m)^\[\[{re.escape(table)}\]\]\s*$", text))
    for index in reversed(range(len(matches))):
        match = matches[index]
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start() : end]
        row = tomllib.loads(block)[table][0]
        if row.get(identity) == value:
            path.write_text(text[: match.start()] + text[end:], encoding="utf-8")
            return
    raise AssertionError(f"array row not found: {table}.{identity}={value}")


def test_package_mirror_reconciles_every_source_and_preserves_declared_nested_entrypoint(
    tmp_path: Path,
) -> None:
    repo = _copy_package_mirror_fixture(tmp_path / "repo")
    family = next(
        item
        for item in _read_toml(repo / "architecture/generated_artifacts.toml")["family"]
        if item["id"] == "architecture-package-contract-aggregates"
    )
    registered_outputs = set(family["outputs"])
    contracts = {
        path.stem: _read_toml(path)
        for path in (repo / "architecture/packages").glob("*.toml")
        if path.relative_to(repo).as_posix() not in registered_outputs
    }
    findings, summary = phase1_3._validate_package_mirror_projection(repo)
    observed = {(item.subject, item.message.removesuffix(" drift")) for item in findings}
    assert observed == {
        ("architecture/packages/common.toml", "public_surface.supported_entrypoints"),
        ("architecture/packages/core.toml", "public_surface.supported_entrypoints"),
        ("architecture/packages/data_forge.toml", "public_surface.notes"),
        ("architecture/packages/data_forge.toml", "public_surface.supported_entrypoints"),
        ("architecture/packages/ddm.toml", "public_surface.facade_mode"),
        ("architecture/packages/fabric.toml", "public_surface.supported_entrypoints"),
        ("architecture/packages/foundry.toml", "public_surface.notes"),
        ("architecture/packages/foundry.toml", "public_surface.supported_entrypoints"),
        ("architecture/packages/ir.toml", "public_surface.supported_entrypoints"),
        ("architecture/packages/lex.toml", "public_surface.supported_entrypoints"),
        ("architecture/packages/runtime.toml", "public_surface.supported_entrypoints"),
        ("architecture/packages/scientist.toml", "public_surface.notes"),
        ("architecture/packages/scientist.toml", "public_surface.supported_entrypoints"),
        (
            "architecture/public_surface/contract.toml",
            "public surface row has no complete source contract",
        ),
    }
    assert len(findings) == 14
    assert (
        summary["unmapped_public_surface_rows"]["polisyos.runtime.quality"]["status"]
        == "not_established"
    )
    assert summary["source_contract_file_count"] == 19
    assert summary["primary_source_contract_count"] == 19
    assert summary["projection_row_counts"] == {
        "boundaries": 19,
        "public_surface": 20,
        "layout": 6,
        "topology": 13,
    }
    assert summary["primary_source_contract_count"] == sum(
        summary["topology_source_dispositions"].values()
    )
    assert summary["topology_source_dispositions"] == {
        "direct": 13,
        "explicit_source_exception": 5,
        "nested_coverage": 1,
    }
    expected_layout = {
        contract["package"]["name"]: contract["layout"]["legacy_layout_status"]
        for contract in contracts.values()
        if contract["layout"].get("legacy_layout_mirror") == "architecture/packages/layout.toml"
    }
    actual_layout = {
        row["name"]: row["current_status"]
        for row in _read_toml(repo / "architecture/packages/layout.toml")["package"]
    }
    assert actual_layout == expected_layout


def test_package_mirror_rejects_malformed_raw_typed_fields(tmp_path: Path) -> None:
    cases = (
        {
            "name": "nonlist-source-and-projection",
            "field": "supported_entrypoints",
            "source_old": 'supported_entrypoints = ["polisyos.common", "polisyos.common.config"]',
            "source_new": 'supported_entrypoints = "not-an-array-source"',
            "projection_old": 'supported_entrypoints = ["polisyos.common", "polisyos.common.config", "polisyos.common.canonical", "polisyos.common.canonical_profile", "polisyos.common.hashing", "polisyos.common.migrations"]',
            "projection_new": 'supported_entrypoints = "different-nonarray-mirror"',
            "expected_messages": {
                "public_surface.supported_entrypoints has malformed source value",
                "public_surface.supported_entrypoints has malformed projection value",
            },
        },
        {
            "name": "nonstr-list-member",
            "field": "supported_entrypoints",
            "source_old": 'supported_entrypoints = ["polisyos.common", "polisyos.common.config"]',
            "source_new": 'supported_entrypoints = ["polisyos.common", 7]',
            "projection_old": 'supported_entrypoints = ["polisyos.common", "polisyos.common.config", "polisyos.common.canonical", "polisyos.common.canonical_profile", "polisyos.common.hashing", "polisyos.common.migrations"]',
            "projection_new": 'supported_entrypoints = ["polisyos.common", "7"]',
            "expected_messages": {
                "public_surface.supported_entrypoints has malformed source value"
            },
        },
        {
            "name": "nonstr-projection-list-member",
            "field": "supported_entrypoints",
            "source_old": 'supported_entrypoints = ["polisyos.common", "polisyos.common.config"]',
            "source_new": 'supported_entrypoints = ["polisyos.common", "7"]',
            "projection_old": 'supported_entrypoints = ["polisyos.common", "polisyos.common.config", "polisyos.common.canonical", "polisyos.common.canonical_profile", "polisyos.common.hashing", "polisyos.common.migrations"]',
            "projection_new": 'supported_entrypoints = ["polisyos.common", 7]',
            "expected_messages": {
                "public_surface.supported_entrypoints has malformed projection value"
            },
        },
        {
            "name": "source-bool-vs-projection-string",
            "field": "major_subsystem",
            "source_old": "major_subsystem = false",
            "source_new": 'major_subsystem = "False"',
            "projection_old": "major_subsystem = false",
            "projection_new": 'major_subsystem = "False"',
            "expected_messages": {
                "public_surface.major_subsystem has malformed source value",
                "public_surface.major_subsystem has malformed projection value",
            },
        },
        {
            "name": "source-bool-vs-projection-string-opposite-side",
            "field": "major_subsystem",
            "source_old": "major_subsystem = false",
            "source_new": "major_subsystem = false",
            "projection_old": "major_subsystem = false",
            "projection_new": 'major_subsystem = "False"',
            "expected_messages": {"public_surface.major_subsystem has malformed projection value"},
        },
    )
    for case in cases:
        repo = _copy_package_mirror_fixture(tmp_path / case["name"])
        source = repo / "architecture/packages/common.toml"
        source_text = source.read_text(encoding="utf-8")
        assert case["source_old"] in source_text
        source.write_text(
            source_text.replace(case["source_old"], case["source_new"], 1), encoding="utf-8"
        )
        projection = repo / "architecture/public_surface/contract.toml"
        projection_text = projection.read_text(encoding="utf-8")
        assert case["projection_old"] in projection_text
        projection.write_text(
            projection_text.replace(case["projection_old"], case["projection_new"], 1),
            encoding="utf-8",
        )

        findings, _ = phase1_3._validate_package_mirror_projection(repo)
        observed_messages = {
            finding.message for finding in findings if finding.message.startswith("public_surface.")
        }
        assert case["expected_messages"] <= observed_messages
        assert not any(
            finding.subject == "architecture/packages/common.toml"
            and finding.message == f"public_surface.{case['field']} drift"
            for finding in findings
        )


def test_package_mirror_rejects_malformed_source_table(tmp_path: Path) -> None:
    repo = _copy_package_mirror_fixture(tmp_path / "malformed-source-table")
    source = repo / "architecture/packages/common.toml"
    source_text = source.read_text(encoding="utf-8")
    assert "[public_surface]" in source_text
    source.write_text(
        source_text.replace("[public_surface]", 'public_surface = "not-a-table"', 1),
        encoding="utf-8",
    )

    findings, _ = phase1_3._validate_package_mirror_projection(repo)
    assert any(
        finding.subject == "architecture/packages/common.toml"
        and finding.message == "public_surface has malformed source value"
        for finding in findings
    )


def test_package_mirror_cli_fails_on_real_projection_drift(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = _copy_package_mirror_fixture(tmp_path / "cli-drift")
    shutil.copytree(
        PRODUCT_ROOT_FOR_TESTS / "architecture", repo / "architecture", dirs_exist_ok=True
    )
    _replace_array_table_value(
        repo / "architecture/public_surface/contract.toml",
        table="package",
        identity="module",
        value="polisyos.common",
        field="facade_mode",
        replacement='facade_mode = "wrong-mode"',
    )
    output = tmp_path / "cli-drift-report.json"
    # The package mirror CLI is the behavior under test. Its summary contains a
    # separate repository-wide Ruff liveness report, which is not meaningful for
    # this deliberately small fixture, so supply only that unrelated summary.
    monkeypatch.setattr(
        phase1_3, "_summary", lambda _repo, **_kwargs: {"generated_family_checks": {}}
    )
    exit_code = phase1_3.run_cli(
        [
            "--repo-root",
            str(repo),
            "--report",
            "package-mirrors",
            "--fail-on-package-mirror-errors",
            "--json-output",
            str(output),
        ]
    )
    assert exit_code == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    family = payload["summary"]["generated_family_checks"][
        "architecture-package-contract-aggregates"
    ]
    assert family["status"] == "failed"
    assert any(
        finding["subject"] == "architecture/packages/common.toml"
        and finding["message"] == "public_surface.facade_mode drift"
        for finding in family["errors"]
    )


def test_package_mirror_rejects_noop_command_that_keeps_failure_flag(tmp_path: Path) -> None:
    repo = _copy_package_mirror_fixture(tmp_path / "noop-command")
    registry = repo / "architecture/generated_artifacts.toml"
    text = registry.read_text(encoding="utf-8")
    family_start = text.index('id = "architecture-package-contract-aggregates"')
    command_start = text.index("check_command = [", family_start)
    command_end = text.index("\n]", command_start) + 2
    registry.write_text(
        text[:command_start]
        + 'check_command = ["echo", "--fail-on-package-mirror-errors"]'
        + text[command_end:],
        encoding="utf-8",
    )
    findings = phase1_3._validate_package_mirror_projection(repo)[0]
    assert any(
        finding.subject == "architecture/generated_artifacts.toml"
        and finding.message == "family check_command must match the canonical verifier route"
        for finding in findings
    )


def test_package_mirror_rejects_missing_extra_drift_and_uncovered_rows(tmp_path: Path) -> None:
    missing = _copy_package_mirror_fixture(tmp_path / "missing")
    _drop_array_row(
        missing / "architecture/packages/boundaries.toml", "package", "module", "polisyos.common"
    )
    findings = phase1_3._validate_package_mirrors(missing)
    assert any("missing a source-derived row" in item.message for item in findings)

    extra = _copy_package_mirror_fixture(tmp_path / "extra")
    with (extra / "architecture/packages/boundaries.toml").open("a", encoding="utf-8") as handle:
        handle.write('\n[[package]]\nmodule = "polisyos.unregistered"\n')
    findings = phase1_3._validate_package_mirrors(extra)
    assert any("no matching source declaration" in item.message for item in findings)

    drift = _copy_package_mirror_fixture(tmp_path / "drift")
    path = drift / "architecture/packages/boundaries.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'public_facade = "polisyos.common"', 'public_facade = "polisyos.wrong"', 1
        ),
        encoding="utf-8",
    )
    findings = phase1_3._validate_package_mirrors(drift)
    assert any("public_facade drift" in item.message for item in findings)

    missing_source = _copy_package_mirror_fixture(tmp_path / "missing-source")
    (missing_source / "architecture/packages/common.toml").unlink()
    findings = phase1_3._validate_package_mirrors(missing_source)
    assert any("no matching source declaration" in item.message for item in findings)

    layout = _copy_package_mirror_fixture(tmp_path / "layout")
    _drop_array_row(layout / "architecture/packages/layout.toml", "package", "name", "berl")
    findings = phase1_3._validate_package_mirrors(layout)
    assert any("package layout is missing" in item.message for item in findings)

    topology = _copy_package_mirror_fixture(tmp_path / "topology")
    path = topology / "architecture/tests/topology.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'unit_path = "tests/unit/foundry"', 'unit_path = "tests/unit/sibling"', 1
        ),
        encoding="utf-8",
    )
    findings = phase1_3._validate_package_mirrors(topology)
    assert any(
        item.subject.endswith("foundry-agent-sim-world.toml")
        and "nested unit roots are not strictly covered" in item.message
        for item in findings
    )

    source_path = _copy_package_mirror_fixture(tmp_path / "source-path")
    path = source_path / "architecture/tests/topology.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'source_path = "src/polisyos/common"',
            'source_path = "src/polisyos/sibling"',
            1,
        ),
        encoding="utf-8",
    )
    findings = phase1_3._validate_package_mirrors(source_path)
    assert any(
        item.subject.endswith("common.toml") and item.message == "test_topology.source_path drift"
        for item in findings
    )

    registry = _copy_package_mirror_fixture(tmp_path / "registry")
    path = registry / "architecture/generated_artifacts.toml"
    registry_text = path.read_text(encoding="utf-8")
    check_start = registry_text.index(
        "check_command = [", registry_text.index('id = "architecture-package-contract-aggregates"')
    )
    check_end = registry_text.index("\n]", check_start)
    check_block = registry_text[check_start:check_end]
    check_block = check_block.replace(
        "--fail-on-package-mirror-errors", "--fail-on-contract-errors", 1
    )
    path.write_text(
        registry_text[:check_start] + check_block + registry_text[check_end:], encoding="utf-8"
    )
    findings = phase1_3._validate_package_mirrors(registry)
    assert any(
        item.message == "family check_command must match the canonical verifier route"
        for item in findings
    )

    missing_output = _copy_package_mirror_fixture(tmp_path / "missing-output")
    path = missing_output / "architecture/generated_artifacts.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace('  "architecture/packages/layout.toml",\n', "", 1),
        encoding="utf-8",
    )
    findings = phase1_3._validate_package_mirrors(missing_output)
    assert any("registered outputs differ" in item.message for item in findings)


def test_package_mirror_cli_reports_malformed_family_inputs_before_source_discovery(
    tmp_path: Path, monkeypatch: Any
) -> None:
    def append_non_table(family_document: dict[str, Any]) -> None:
        family_document["family"].append(True)

    def change_family_id_type(family_document: dict[str, Any]) -> None:
        family = next(
            row
            for row in family_document["family"]
            if type(row) is dict and row.get("id") == "architecture-package-contract-aggregates"
        )
        family["id"] = True

    def change_family_container_type(family_document: dict[str, Any]) -> None:
        family_document["family"] = True

    cases = (
        (
            "non-table-row",
            append_non_table,
            "family registry row does not satisfy generated-artifact schema",
        ),
        (
            "malformed-id",
            change_family_id_type,
            "family registry row does not satisfy generated-artifact schema",
        ),
        (
            "non-array-container",
            change_family_container_type,
            "family registry rows must be an array",
        ),
    )
    original_read_toml = phase1_3._read_toml
    monkeypatch.setattr(
        phase1_3, "_summary", lambda _repo, **_kwargs: {"generated_family_checks": {}}
    )

    for case_name, mutate_family_document, expected_message in cases:
        repo = _copy_package_mirror_fixture(tmp_path / case_name)
        shutil.copytree(
            PRODUCT_ROOT_FOR_TESTS / "architecture", repo / "architecture", dirs_exist_ok=True
        )
        output = tmp_path / f"{case_name}-report.json"
        family_path = repo / "architecture" / "generated_artifacts.toml"
        family_reads = 0

        def read_with_malformed_family_input(
            path: Path,
            *,
            expected_family_path: Path = family_path,
            mutation: Any = mutate_family_document,
        ) -> dict[str, Any]:
            nonlocal family_reads
            data = original_read_toml(path)
            if path == expected_family_path:
                family_reads += 1
                mutation(data)
            return data

        monkeypatch.setattr(phase1_3, "_read_toml", read_with_malformed_family_input)
        exit_code = phase1_3.run_cli(
            [
                "--repo-root",
                str(repo),
                "--report",
                "package-mirrors",
                "--fail-on-package-mirror-errors",
                "--json-output",
                str(output),
            ]
        )

        assert exit_code == 1
        assert family_reads == 1
        payload = json.loads(output.read_text(encoding="utf-8"))
        family = payload["summary"]["generated_family_checks"][
            "architecture-package-contract-aggregates"
        ]
        assert family["status"] == "failed"
        assert any(
            finding["subject"] == "architecture/generated_artifacts.toml"
            and finding["message"] == expected_message
            for finding in family["errors"]
        )
        assert not any(
            finding["check"] == "package-contract"
            and finding["subject"]
            in {"architecture/packages/boundaries.toml", "architecture/packages/layout.toml"}
            for finding in payload["contract_errors"]
        )

        generated_output = tmp_path / f"{case_name}-generated-report.json"
        generated_exit_code = phase1_3.run_cli(
            [
                "--repo-root",
                str(repo),
                "--report",
                "generated-artifacts",
                "--fail-on-contract-errors",
                "--json-output",
                str(generated_output),
            ]
        )
        assert generated_exit_code == 1
        assert family_reads == 2
        generated_payload = json.loads(generated_output.read_text(encoding="utf-8"))
        assert any(
            finding["check"] == "generated-artifacts"
            and finding["subject"] == "architecture/generated_artifacts.toml"
            and finding["message"] == expected_message
            for finding in generated_payload["contract_errors"]
        )


def test_legacy_operability_route_join_catches_removed_route_and_preserves_phase63(
    monkeypatch: Any, capsys: Any
) -> None:
    from tools.ops_runners.release import check_operability_release_gates as phase6_3

    baseline = phase1_3.build_report(REPO_ROOT, report="runbook-coverage")
    route_join = baseline["summary"]["legacy_operability_routes"]
    by_source = route_join["by_source"]
    runbook_coverage = by_source["architecture/runbook_coverage.toml"]
    component_observability = by_source["architecture/component_observability.toml"]
    assert runbook_coverage["runbooks"] == {
        "occurrence_count": 16,
        "routed_occurrence_count": 16,
        "unrouted_occurrence_count": 0,
    }
    assert runbook_coverage["slo_files"] == {
        "occurrence_count": 13,
        "routed_occurrence_count": 12,
        "unrouted_occurrence_count": 1,
    }
    assert component_observability["slo_files"] == {
        "occurrence_count": 4,
        "routed_occurrence_count": 4,
        "unrouted_occurrence_count": 0,
    }
    runbook_occurrences = [
        item
        for item in route_join["occurrences"]
        if item["source_file"] == "architecture/runbook_coverage.toml"
        and item["field"] == "runbooks"
    ]
    legacy_slo_occurrences = [
        item
        for item in route_join["occurrences"]
        if item["source_file"] == "architecture/runbook_coverage.toml"
        and item["field"] == "slo_files"
    ]
    component_slo_occurrences = [
        item
        for item in route_join["occurrences"]
        if item["source_file"] == "architecture/component_observability.toml"
        and item["field"] == "slo_files"
    ]
    assert len(runbook_occurrences) == 16
    assert all(item["routed"] and item["active_routes"] for item in runbook_occurrences)
    assert len(legacy_slo_occurrences) == 13
    assert sum(item["routed"] for item in legacy_slo_occurrences) == 12
    assert len(component_slo_occurrences) == 4
    assert all(item["routed"] and item["active_routes"] for item in component_slo_occurrences)
    assert [item["path"] for item in route_join["missing_occurrences"]] == [
        "ops/observability/slo/schema_drift.yaml"
    ]
    retained_route = next(
        item
        for item in route_join["occurrences"]
        if item["path"] == "docs/runbooks/retained-artifact-recovery.md"
    )
    assert retained_route["active_routes"] == [
        {"component": "data_forge", "owner": "team-data-forge"}
    ]

    phase63_before = phase6_3.build_report(repo_root=REPO_ROOT)
    index_path = REPO_ROOT / "ops/components/index.toml"
    phase1_3_read_toml = phase1_3._read_toml
    phase6_3_read_toml = phase6_3._read_toml
    remaining_data_forge_runbook_counts: list[int] = []

    def remove_only_retained_artifact_route(data: dict[str, Any]) -> dict[str, Any]:
        data_forge = next(item for item in data["component"] if item["id"] == "data_forge")
        data_forge["runbooks"].remove("docs/runbooks/retained-artifact-recovery.md")
        remaining_data_forge_runbook_counts.append(len(data_forge["runbooks"]))
        return data

    def read_phase1_3_with_removed_route(path: Path) -> dict[str, Any]:
        data = phase1_3_read_toml(path)
        return remove_only_retained_artifact_route(data) if path == index_path else data

    def read_phase6_3_with_removed_route(path: Path) -> dict[str, Any]:
        data = phase6_3_read_toml(path)
        return remove_only_retained_artifact_route(data) if path == index_path else data

    monkeypatch.setattr(phase1_3, "_read_toml", read_phase1_3_with_removed_route)
    monkeypatch.setattr(phase6_3, "_read_toml", read_phase6_3_with_removed_route)
    phase63_after = phase6_3.build_report(repo_root=REPO_ROOT)
    assert phase63_after == phase63_before
    assert phase63_after["finding_count"] == phase63_before["finding_count"]

    exit_code = phase1_3.run_cli(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--report",
            "runbook-coverage",
            "--fail-on-contract-errors",
        ]
    )
    cli_report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert all(count == 2 for count in remaining_data_forge_runbook_counts)
    route_join_after = cli_report["summary"]["legacy_operability_routes"]
    assert [item["path"] for item in route_join_after["missing_occurrences"]] == [
        "docs/runbooks/retained-artifact-recovery.md",
        "ops/observability/slo/schema_drift.yaml",
    ]
    retained_route_after = next(
        item
        for item in route_join_after["occurrences"]
        if item["path"] == "docs/runbooks/retained-artifact-recovery.md"
    )
    assert retained_route_after["active_routes"] == []
    remaining_data_forge_routes = {
        item["path"]
        for item in route_join_after["occurrences"]
        if any(route["component"] == "data_forge" for route in item["active_routes"])
    }
    assert remaining_data_forge_routes == {
        "docs/runbooks/broken-contract-generation.md",
        "docs/runbooks/replay-or-restore.md",
    }
    route_errors = [
        item for item in cli_report["contract_errors"] if item["check"] == "operability-route"
    ]
    assert {item["subject"] for item in route_errors} == {
        "docs/runbooks/retained-artifact-recovery.md",
        "ops/observability/slo/schema_drift.yaml",
    }
    expiry_errors = [
        item
        for item in cli_report["contract_errors"]
        if item["check"] == "report-only-gates"
        and item["message"] == "target_fail_closed_not_before must be today or future"
    ]
    assert len(expiry_errors) == 14


def test_legacy_operability_route_join_reads_index_named_by_contract(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = _copy_package_mirror_fixture(tmp_path / "repo")
    for relative in (
        "architecture/runbook_coverage.toml",
        "architecture/component_observability.toml",
        "ops/components/index.toml",
    ):
        source = REPO_ROOT / relative
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    runbook_contract_path = repo / "architecture/runbook_coverage.toml"
    active_index_path = repo / "ops/components/index.toml"
    declared_index_path = repo / "ops/components/alternate-component-index.toml"
    shutil.copy2(active_index_path, declared_index_path)
    original_read_toml = phase1_3._read_toml
    requested_indexes: list[str] = []

    def read_with_alternate_active_index(path: Path) -> dict[str, Any]:
        if path == runbook_contract_path:
            contract = original_read_toml(path)
            contract["runbook_coverage"]["component_index"] = (
                "ops/components/alternate-component-index.toml"
            )
            return contract
        if path == declared_index_path:
            requested_indexes.append(path.relative_to(repo).as_posix())
            index = original_read_toml(active_index_path)
            data_forge = next(item for item in index["component"] if item["id"] == "data_forge")
            data_forge["runbooks"].remove("docs/runbooks/retained-artifact-recovery.md")
            return index
        return original_read_toml(path)

    monkeypatch.setattr(phase1_3, "_read_toml", read_with_alternate_active_index)
    monkeypatch.setattr(phase1_3, "_validate_report_only_gates", lambda _repo: [])
    monkeypatch.setattr(phase1_3, "_summary", lambda _repo, **_kwargs: {})
    report = phase1_3.build_report(repo, report="runbook-coverage")
    route_join = report["summary"]["legacy_operability_routes"]
    assert requested_indexes == ["ops/components/alternate-component-index.toml"]
    assert [item["path"] for item in route_join["missing_occurrences"]] == [
        "docs/runbooks/retained-artifact-recovery.md",
        "ops/observability/slo/schema_drift.yaml",
    ]
    retained_route = next(
        item
        for item in route_join["occurrences"]
        if item["path"] == "docs/runbooks/retained-artifact-recovery.md"
    )
    assert retained_route["active_routes"] == []


def test_legacy_operability_route_rejects_nul_in_declared_index_path(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = tmp_path / "repo"
    for relative in (
        "architecture/generated_artifacts.toml",
        "architecture/runbook_coverage.toml",
        "architecture/component_observability.toml",
        "ops/components/index.toml",
    ):
        source = PRODUCT_ROOT_FOR_TESTS / relative
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    runbook_path = repo / "architecture/runbook_coverage.toml"
    runbook_text = runbook_path.read_text(encoding="utf-8")
    old_index = 'component_index = "ops/components/index.toml"'
    assert old_index in runbook_text
    runbook_path.write_text(
        runbook_text.replace(old_index, 'component_index = "\\u0000"', 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(phase1_3, "_validate_list_contract", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(phase1_3, "_validate_report_only_gates", lambda _repo: [])
    monkeypatch.setattr(phase1_3, "_summary", lambda _repo, **_kwargs: {})
    output = tmp_path / "nul-index-report.json"
    exit_code = phase1_3.run_cli(
        [
            "--repo-root",
            str(repo),
            "--report",
            "runbook-coverage",
            "--fail-on-contract-errors",
            "--json-output",
            str(output),
        ]
    )
    assert exit_code == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert any(
        item["check"] == "operability-route"
        and item["subject"] == "architecture/runbook_coverage.toml"
        and item["message"] == "runbook coverage component_index must not contain NUL"
        for item in payload["contract_errors"]
    )
    route_summary = payload["summary"]["legacy_operability_routes"]
    assert route_summary["route_index_available"] is False
    assert route_summary["missing_occurrences"] == []
    assert len(route_summary["unresolved_occurrences"]) == route_summary["occurrence_count"]


def _copy_legacy_operability_inputs(repo: Path) -> None:
    for relative in (
        "architecture/generated_artifacts.toml",
        "architecture/runbook_coverage.toml",
        "architecture/component_observability.toml",
        "ops/components/index.toml",
    ):
        source = PRODUCT_ROOT_FOR_TESTS / relative
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _run_legacy_operability_report(
    repo: Path,
    output: Path,
    monkeypatch: Any,
) -> tuple[int, dict[str, Any]]:
    monkeypatch.setattr(phase1_3, "_validate_list_contract", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(phase1_3, "_validate_report_only_gates", lambda _repo: [])
    monkeypatch.setattr(phase1_3, "_summary", lambda _repo, **_kwargs: {})
    exit_code = phase1_3.run_cli(
        [
            "--repo-root",
            str(repo),
            "--report",
            "runbook-coverage",
            "--fail-on-contract-errors",
            "--json-output",
            str(output),
        ]
    )
    return exit_code, json.loads(output.read_text(encoding="utf-8"))


def _set_declared_component_index(repo: Path, relative_path: str) -> None:
    runbook_path = repo / "architecture/runbook_coverage.toml"
    runbook_text = runbook_path.read_text(encoding="utf-8")
    old_index = 'component_index = "ops/components/index.toml"'
    assert old_index in runbook_text
    runbook_path.write_text(
        runbook_text.replace(old_index, f'component_index = "{relative_path}"', 1),
        encoding="utf-8",
    )


def _route_for_path(summary: dict[str, Any], path: str) -> dict[str, Any]:
    return next(item for item in summary["occurrences"] if item["path"] == path)


def test_legacy_operability_route_accepts_in_root_symlink_and_consumes_its_route(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = tmp_path / "repo"
    _copy_legacy_operability_inputs(repo)
    declared_index = repo / "ops/components/declared.toml"
    in_root_index = repo / "ops/components/in-root-index.toml"
    in_root_index.parent.mkdir(parents=True, exist_ok=True)
    in_root_index.write_text(
        'component = [{ id = "probe-component", owner = "probe-owner", '
        'runbooks = ["docs/runbooks/replay-or-restore.md"], '
        'slo_file = "ops/components/probe/slo.yaml", legacy_slo_files = [] }]\n',
        encoding="utf-8",
    )
    declared_index.symlink_to(in_root_index)
    _set_declared_component_index(repo, "ops/components/declared.toml")

    _exit_code, payload = _run_legacy_operability_report(
        repo, tmp_path / "in-root-symlink-report.json", monkeypatch
    )
    summary = payload["summary"]["legacy_operability_routes"]
    occurrence = _route_for_path(summary, "docs/runbooks/replay-or-restore.md")

    assert summary.get("route_index_available", True) is True
    assert occurrence["routed"] is True
    assert occurrence["active_routes"] == [{"component": "probe-component", "owner": "probe-owner"}]


def test_legacy_operability_route_external_symlink_keeps_basis_unresolved(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside-index.toml"
    _copy_legacy_operability_inputs(repo)
    declared_index = repo / "ops/components/declared.toml"
    in_root_index = repo / "ops/components/in-root-index.toml"
    in_root_index.parent.mkdir(parents=True, exist_ok=True)
    in_root_index.write_text(
        'component = [{ id = "inside-component", owner = "inside-owner", '
        'runbooks = ["docs/runbooks/broken-contract-generation.md"], '
        'slo_file = "ops/components/inside/slo.yaml", legacy_slo_files = [] }]\n',
        encoding="utf-8",
    )
    outside.write_text(
        'component = [{ id = "outside-component", owner = "outside-owner", '
        'runbooks = ["docs/runbooks/replay-or-restore.md"], '
        'slo_file = "ops/components/outside/slo.yaml", legacy_slo_files = [] }]\n',
        encoding="utf-8",
    )
    declared_index.symlink_to(in_root_index)
    _set_declared_component_index(repo, "ops/components/declared.toml")

    _inside_exit, inside_payload = _run_legacy_operability_report(
        repo, tmp_path / "inside-symlink-report.json", monkeypatch
    )
    inside_summary = inside_payload["summary"]["legacy_operability_routes"]
    inside_occurrence = _route_for_path(inside_summary, "docs/runbooks/replay-or-restore.md")
    assert inside_occurrence["routed"] is False

    declared_index.unlink()
    declared_index.symlink_to(outside)
    _outside_exit, outside_payload = _run_legacy_operability_report(
        repo, tmp_path / "outside-symlink-report.json", monkeypatch
    )
    summary = outside_payload["summary"]["legacy_operability_routes"]
    occurrence = _route_for_path(summary, "docs/runbooks/replay-or-restore.md")

    assert outside.resolve().is_relative_to(repo.resolve()) is False
    assert occurrence["routed"] is None
    assert occurrence["active_routes"] is None
    assert any(
        item["message"] == "declared active component index resolves outside repository root"
        for item in outside_payload["contract_errors"]
    )
    assert summary["route_index_available"] is False
    assert summary["missing_occurrences"] == []
    assert len(summary["unresolved_occurrences"]) == summary["occurrence_count"]


def test_legacy_operability_route_reads_resolved_target_after_link_retarget(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo = tmp_path / "repo"
    outside = tmp_path / "outside-index.toml"
    _copy_legacy_operability_inputs(repo)
    declared_index = repo / "ops/components/declared.toml"
    in_root_index = repo / "ops/components/in-root-index.toml"
    in_root_index.parent.mkdir(parents=True, exist_ok=True)
    in_root_index.write_text(
        'component = [{ id = "admitted-component", owner = "admitted-owner", '
        'runbooks = ["docs/runbooks/replay-or-restore.md"], '
        'slo_file = "ops/components/admitted/slo.yaml", legacy_slo_files = [] }]\n',
        encoding="utf-8",
    )
    outside.write_text(
        'component = [{ id = "retargeted-component", owner = "retargeted-owner", '
        'runbooks = ["docs/runbooks/replay-or-restore.md"], '
        'slo_file = "ops/components/retargeted/slo.yaml", legacy_slo_files = [] }]\n',
        encoding="utf-8",
    )
    declared_index.symlink_to(in_root_index)
    _set_declared_component_index(repo, "ops/components/declared.toml")

    original_resolver = phase1_3.resolve_admitted_path

    def retarget_after_resolution(path: Path, root: Path) -> Path:
        resolved = original_resolver(path, root)
        if path == declared_index:
            declared_index.unlink()
            declared_index.symlink_to(outside)
        return resolved

    monkeypatch.setattr(phase1_3, "resolve_admitted_path", retarget_after_resolution)
    _exit_code, payload = _run_legacy_operability_report(
        repo, tmp_path / "retargeted-symlink-report.json", monkeypatch
    )
    summary = payload["summary"]["legacy_operability_routes"]
    occurrence = _route_for_path(summary, "docs/runbooks/replay-or-restore.md")

    assert summary.get("route_index_available", True) is True
    assert occurrence["routed"] is True
    assert occurrence["active_routes"] == [
        {"component": "admitted-component", "owner": "admitted-owner"}
    ]


@pytest.mark.parametrize(
    ("source_kind", "expected_message"),
    [
        ("directory", "declared active component index is not a regular file"),
        ("toml", "declared active component index is not valid TOML"),
        ("utf8", "declared active component index is not valid UTF-8"),
        ("missing", "declared active component index file is missing"),
        ("permission", "declared active component index is not readable"),
        ("symlink-loop", "declared active component index could not be inspected"),
        ("missing-component", "active component registry must contain a component array"),
        ("wrong-component", "active component registry must contain a component array"),
        ("malformed-sibling", "active component registry row must be a table"),
        ("missing-id", "active route row must declare a string component id"),
        ("wrong-id", "active route row must declare a string component id"),
        ("empty-id", "active route row must declare a string component id"),
        ("missing-owner", "active route row must declare a string owner"),
        ("wrong-owner", "active route row must declare a string owner"),
        ("empty-owner", "active route row must declare a string owner"),
        ("missing-runbooks", "active route row must declare `runbooks` an array"),
        ("missing-slo-file", "active route row must declare `slo_file` a string"),
        ("empty-runbooks", "active route field `runbooks` must be a nonempty array"),
        ("wrong-runbooks", "active route field `runbooks` must be an array"),
        ("wrong-runbook-member", "active route field `runbooks` must contain nonempty strings"),
        ("wrong-slo-file", "active route field `slo_file` must be a nonempty string"),
        ("empty-slo-file", "active route field `slo_file` must be a nonempty string"),
        ("wrong-legacy-slo-files", "active route field `legacy_slo_files` must be an array"),
        (
            "wrong-legacy-slo-member",
            "active route field `legacy_slo_files` must contain nonempty strings",
        ),
    ],
)
def test_legacy_operability_route_declared_index_admission_failures_are_typed(
    tmp_path: Path,
    monkeypatch: Any,
    source_kind: str,
    expected_message: str,
) -> None:
    repo = tmp_path / source_kind
    for relative in (
        "architecture/generated_artifacts.toml",
        "architecture/runbook_coverage.toml",
        "architecture/component_observability.toml",
        "ops/components/index.toml",
    ):
        source = PRODUCT_ROOT_FOR_TESTS / relative
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    runbook_path = repo / "architecture/runbook_coverage.toml"
    runbook_text = runbook_path.read_text(encoding="utf-8")
    old_index = 'component_index = "ops/components/index.toml"'
    assert old_index in runbook_text
    declared_path = "ops/components/declared-component-index.toml"
    runbook_path.write_text(
        runbook_text.replace(old_index, f'component_index = "{declared_path}"', 1),
        encoding="utf-8",
    )
    declared_index = repo / declared_path
    declared_index.parent.mkdir(parents=True, exist_ok=True)
    if source_kind == "directory":
        declared_index.mkdir()
    elif source_kind == "toml":
        declared_index.write_text("component = [\n", encoding="utf-8")
    elif source_kind == "utf8":
        declared_index.write_bytes(b"\xffnot-utf8")
    elif source_kind == "permission":
        shutil.copy2(PRODUCT_ROOT_FOR_TESTS / "ops/components/index.toml", declared_index)
        declared_index.chmod(0)
        try:
            declared_index.read_text(encoding="utf-8")
        except PermissionError:
            pass
        else:
            declared_index.chmod(0o600)
            pytest.skip("filesystem permissions do not deny reads for this test process")
    elif source_kind == "symlink-loop":
        loop_target = declared_index.with_name("declared-component-index-loop.toml")
        declared_index.symlink_to(loop_target)
        loop_target.symlink_to(declared_index)
    elif source_kind == "missing-component":
        declared_index.write_text("other = []\n", encoding="utf-8")
    elif source_kind == "wrong-component":
        declared_index.write_text("component = 7\n", encoding="utf-8")
    elif source_kind == "malformed-sibling":
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = "team-data-forge", '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"], '
            'slo_file = "ops/components/data_forge/slo.yaml" }, false]\n',
            encoding="utf-8",
        )
    elif source_kind == "missing-id":
        declared_index.write_text(
            'component = [{ owner = "team-data-forge", '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"], '
            'slo_file = "ops/components/data_forge/slo.yaml" }]\n',
            encoding="utf-8",
        )
    elif source_kind == "wrong-id":
        declared_index.write_text(
            'component = [{ id = 7, owner = "team-data-forge", '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"], '
            'slo_file = "ops/components/data_forge/slo.yaml" }]\n',
            encoding="utf-8",
        )
    elif source_kind == "empty-id":
        declared_index.write_text(
            'component = [{ id = "", owner = "team-data-forge", '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"], '
            'slo_file = "ops/components/data_forge/slo.yaml" }]\n',
            encoding="utf-8",
        )
    elif source_kind == "missing-owner":
        declared_index.write_text(
            'component = [{ id = "data_forge", '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"], '
            'slo_file = "ops/components/data_forge/slo.yaml" }]\n',
            encoding="utf-8",
        )
    elif source_kind == "wrong-owner":
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = 7, '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"], '
            'slo_file = "ops/components/data_forge/slo.yaml" }]\n',
            encoding="utf-8",
        )
    elif source_kind == "empty-owner":
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = "", '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"], '
            'slo_file = "ops/components/data_forge/slo.yaml" }]\n',
            encoding="utf-8",
        )
    elif source_kind == "missing-runbooks":
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = "team-data-forge", '
            'slo_file = "ops/components/data_forge/slo.yaml" }]\n',
            encoding="utf-8",
        )
    elif source_kind == "missing-slo-file":
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = "team-data-forge", '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"] }]\n',
            encoding="utf-8",
        )
    elif source_kind == "empty-runbooks":
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = "team-data-forge", '
            'runbooks = [], slo_file = "ops/components/data_forge/slo.yaml" }]\n',
            encoding="utf-8",
        )
    elif source_kind == "wrong-runbooks":
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = "team-data-forge", '
            'runbooks = "not-an-array", slo_file = "ops/components/data_forge/slo.yaml" }]\n',
            encoding="utf-8",
        )
    elif source_kind == "wrong-runbook-member":
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = "team-data-forge", '
            'runbooks = [false], slo_file = "ops/components/data_forge/slo.yaml" }]\n',
            encoding="utf-8",
        )
    elif source_kind in {"wrong-slo-file", "empty-slo-file"}:
        slo_file = "7" if source_kind == "wrong-slo-file" else '""'
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = "team-data-forge", '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"], '
            f"slo_file = {slo_file}" + " }]\n",
            encoding="utf-8",
        )
    elif source_kind == "wrong-legacy-slo-files":
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = "team-data-forge", '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"], '
            'slo_file = "ops/components/data_forge/slo.yaml", legacy_slo_files = "bad" }]\n',
            encoding="utf-8",
        )
    elif source_kind == "wrong-legacy-slo-member":
        declared_index.write_text(
            'component = [{ id = "data_forge", owner = "team-data-forge", '
            'runbooks = ["docs/runbooks/retained-artifact-recovery.md"], '
            'slo_file = "ops/components/data_forge/slo.yaml", legacy_slo_files = [7] }]\n',
            encoding="utf-8",
        )
    elif source_kind != "missing":
        raise AssertionError(f"unknown source kind: {source_kind}")

    monkeypatch.setattr(phase1_3, "_validate_list_contract", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(phase1_3, "_validate_report_only_gates", lambda _repo: [])
    monkeypatch.setattr(phase1_3, "_summary", lambda _repo, **_kwargs: {})
    output = tmp_path / f"{source_kind}-report.json"
    exit_code = phase1_3.run_cli(
        [
            "--repo-root",
            str(repo),
            "--report",
            "runbook-coverage",
            "--fail-on-contract-errors",
            "--json-output",
            str(output),
        ]
    )
    assert exit_code == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    errors = [
        item
        for item in payload["contract_errors"]
        if item["check"] == "operability-route"
        and item["subject"] == declared_path
        and item["message"] == expected_message
    ]
    assert len(errors) == 1
    route_summary = payload["summary"]["legacy_operability_routes"]
    assert route_summary["route_index_available"] is False
    assert route_summary["missing_occurrences"] == []
    assert len(route_summary["unresolved_occurrences"]) == route_summary["occurrence_count"]

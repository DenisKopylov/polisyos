from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from tools import cli as tools_cli
from tools.devx.workspace import acceptance_audit, verify
from tools.devx.workspace import repository_sota_closeout as sota
from tools.lib import fs as fs_module
from tools.lib import timing as timing_module
from tools.lib.fs import (
    SecureOutputRoot,
    bind_secure_output_root,
    scoped_report_path,
    write_scoped_report_text,
)
from tools.lib.timing import bind_cli_output_scope, read_timing_records
from tools.ops_runners.release import (
    check_compatibility_release_gates as compatibility,
)
from tools.ops_runners.release import (
    check_operability_release_gates as operability,
)
from tools.ops_runners.reports import dead_overrides
from tools.quality.testing import report_test_ratchets
from tools.quality.validation import (
    architecture_report_only_contracts,
    check_package_import_gates,
    directory_health,
    repository_last_mile_inventory,
)


def _execute_embedded_report_snippet(source: str, filename: str) -> None:
    # Execute the real embedded producer so this test verifies its report output.
    exec(compile(source, filename, "exec"), {})  # noqa: S102


PRODUCT_ROOT = Path(tools_cli.__file__).resolve().parents[1]


def _assert_product_modules_loaded() -> None:
    for module in (
        tools_cli,
        sota,
        verify,
        fs_module,
        timing_module,
        acceptance_audit,
        repository_last_mile_inventory,
        check_package_import_gates,
        directory_health,
        report_test_ratchets,
        dead_overrides,
        architecture_report_only_contracts,
        operability,
        compatibility,
    ):
        assert Path(module.__file__).resolve().is_relative_to(PRODUCT_ROOT)


def _all_live_child_commands() -> list[tuple[str, tuple[str, ...]]]:
    commands = [
        (gate, tuple(argv))
        for gate, argv in sota._registered_subprocess_gates(skip_generated_checks=False)
    ]
    commands.extend((gate, tuple(argv)) for gate, argv in sota._supporting_subprocess_gates())
    for row in sota._gate_registry_rows():
        if not isinstance(row, dict):
            continue
        coverage = row.get("coverage")
        if not isinstance(coverage, list) or not any(
            isinstance(route, str) and route.startswith("conditional:") for route in coverage
        ):
            continue
        command = sota._parse_gate_command(row.get("command"))
        if command is not None:
            commands.append((str(row["id"]), tuple(command)))
    gate_ids = [gate for gate, _command in commands]
    assert len(gate_ids) == len(set(gate_ids))
    return commands


def _report_option_paths(argv: tuple[str, ...]) -> list[tuple[str, Path]]:
    options = sota._CHILD_REPORT_OUTPUT_OPTIONS
    paths: list[tuple[str, Path]] = []
    for index, token in enumerate(argv):
        option, separator, value = token.partition("=")
        if option not in options:
            continue
        if option == "--output" and "--check" in argv:
            continue
        if separator:
            raw_path = value
        else:
            assert index + 1 < len(argv), f"{option} must have a report path"
            raw_path = argv[index + 1]
        paths.append((option, Path(raw_path)))
    return paths


def _report_path_set(commands: list[tuple[str, tuple[str, ...]]]) -> set[Path]:
    paths: set[Path] = set()
    for gate, command in commands:
        routed = tuple(sota._route_native_child_report_outputs(gate, command))
        paths.update(path for _option, path in _report_option_paths(routed))
    return paths


def _output_for(outputs: dict[str, Path], gate: str, option: str) -> Path:
    matches = [
        path
        for key, path in outputs.items()
        if key == f"{gate}:{option}" or key.startswith(f"{gate}:{option}:")
    ]
    assert len(matches) == 1, f"expected one output for {gate} {option}; found {len(matches)}"
    return matches[0]


def _args_after_script(argv: tuple[str, ...], script: str) -> list[str]:
    return list(argv[argv.index(script) + 1 :])


def _run_actual_report_emitters(
    monkeypatch: pytest.MonkeyPatch,
    fixture_root: Path,
) -> dict[str, Path]:
    support = dict(sota._supporting_subprocess_gates())
    routed = {
        gate: sota._route_native_child_report_outputs(gate, tuple(command))
        for gate, command in support.items()
    }
    outputs: dict[str, Path] = {}
    for gate, command in routed.items():
        occurrence_counts: Counter[str] = Counter()
        for option, path in _report_option_paths(tuple(command)):
            occurrence = occurrence_counts[option]
            occurrence_counts[option] += 1
            key = f"{gate}:{option}" if occurrence == 0 else f"{gate}:{option}:{occurrence}"
            outputs[key] = path

    monkeypatch.setattr(repository_last_mile_inventory, "collect_inventory", lambda *a, **k: {})
    monkeypatch.setattr(repository_last_mile_inventory, "validate_inventory", lambda _value: [])
    monkeypatch.setattr(repository_last_mile_inventory, "check_artifacts", lambda *_a, **_k: [])
    monkeypatch.setattr(
        check_package_import_gates,
        "build_report",
        lambda *_a, **_k: {
            "status": "passed",
            "complete_verdict": True,
            "finding_count": 0,
            "findings": [],
        },
    )
    directory_payload: dict[str, Any] = {
        "status": "passed",
        "generated_at": "2026-10-15T00:00:00+00:00",
        "contract": "fixture.toml",
        "mode": "report_only",
        "top_level_path_moves_active": False,
        "fail_closed_closure": False,
        "contract_error_count": 0,
        "finding_count": 0,
        "regression_count": 0,
        "contract_errors": [],
        "findings": [],
        "regressions": [],
        "dashboard": {
            "metrics": {},
            "local_residue_by_class": {},
            "asset_counts": {},
            "max_directory_depth_by_root": {},
            "largest_subtrees_by_tracked_file_count": [],
        },
    }
    monkeypatch.setattr(directory_health, "build_report", lambda *_a, **_k: directory_payload)
    monkeypatch.setattr(
        report_test_ratchets,
        "_build_payload",
        lambda *_a, **_k: {
            "summary": {
                "floor_regressions": [],
                "strict_mirror_regressions": [],
                "property_regressions": [],
                "test_helper_topology_status": "ok",
            }
        },
    )
    monkeypatch.setattr(dead_overrides, "build_report", lambda *_a, **_k: {"findings": []})
    monkeypatch.setattr(
        architecture_report_only_contracts,
        "build_report",
        lambda *_a, **_k: {"contract_error_count": 0, "findings": []},
    )
    monkeypatch.setattr(
        operability, "build_report", lambda *_a, **_k: {"finding_count": 0, "findings": []}
    )
    monkeypatch.setattr(
        compatibility,
        "build_report",
        lambda *_a, **_k: {"contract_error_count": 0, "findings": []},
    )
    monkeypatch.setattr(acceptance_audit, "load_manual_evidence", lambda _path: {})
    monkeypatch.setattr(
        acceptance_audit, "resolve_manual_evidence_path", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        acceptance_audit,
        "run_audit",
        lambda **_kwargs: acceptance_audit.AuditReport(checks=()),
    )

    last_mile = routed["last-mile-inventory"]
    assert (
        repository_last_mile_inventory.main(
            _args_after_script(
                last_mile, "tools/quality/validation/repository_last_mile_inventory.py"
            )
        )
        == 0
    )

    package_imports = routed["package-import-gates"]
    assert (
        check_package_import_gates.main(
            _args_after_script(
                package_imports, "tools/quality/validation/check_package_import_gates.py"
            )
        )
        == 0
    )

    health = routed["directory-health"]
    assert (
        directory_health.main(
            _args_after_script(health, "tools/quality/validation/directory_health.py")
        )
        == 0
    )

    ratchets = routed["test-ratchets-helper-topology"]
    old_argv = sys.argv
    try:
        sys.argv = [
            "report_test_ratchets.py",
            *_args_after_script(ratchets, "tools/quality/testing/report_test_ratchets.py"),
        ]
        assert report_test_ratchets.main() == 0
    finally:
        sys.argv = old_argv

    dead = routed["dead-overrides"]
    assert (
        dead_overrides.main(_args_after_script(dead, "tools/ops_runners/reports/dead_overrides.py"))
        == 0
    )

    module_size = routed["validator-module-size"]
    assert (
        architecture_report_only_contracts.run_cli(
            _args_after_script(
                module_size, "tools/quality/validation/architecture_report_only_contracts.py"
            )
        )
        == 0
    )

    operability_args = _args_after_script(
        routed["operability-release"],
        "tools/ops_runners/release/check_operability_release_gates.py",
    )
    assert operability.main(operability_args) == 0

    compatibility_args = _args_after_script(
        routed["compatibility-release"],
        "tools/ops_runners/release/check_compatibility_release_gates.py",
    )
    assert compatibility.main(compatibility_args) == 0

    acceptance = routed["acceptance-audit"]
    assert tools_cli.main([*acceptance[3:], "--no-default-manual-evidence"]) == 0

    schema_dir = fixture_root / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "fixture.json").write_text("{}\n", encoding="utf-8")
    old_cwd = Path.cwd()
    try:
        os.chdir(fixture_root)
        _execute_embedded_report_snippet(sota.SCHEMA_PURITY_SNIPPET, "<schema-purity-fixture>")
        _execute_embedded_report_snippet(
            verify.SCHEMA_PURITY_SNIPPET, "<verify-schema-purity-fixture>"
        )
    finally:
        os.chdir(old_cwd)

    outputs["schema-purity"] = scoped_report_path(
        "schema-purity", Path("_build/.tmp/last-mile/schemas-python-residue.txt")
    )
    outputs["workspace-verify-schema-purity"] = scoped_report_path(
        "workspace-verify-schema-purity",
        Path("_build/.tmp/last-mile/schemas-python-residue.txt"),
    )
    return outputs


def test_live_sota_child_set_routes_and_captures_each_owned_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_product_modules_loaded()
    output = tmp_path / "native-output"
    output.mkdir()
    commands = _all_live_child_commands()
    expected_gate_ids = Counter(gate for gate, _command in commands)

    calls: list[tuple[str, ...]] = []
    invoked_gates: list[str] = []

    original_subprocess_gate = sota._run_subprocess_with_receipt

    def record_subprocess_gate(
        gate: str,
        command: Any,
        *,
        receipt_dir: Path | None,
    ) -> Any:
        invoked_gates.append(gate)
        return original_subprocess_gate(gate, command, receipt_dir=receipt_dir)

    def controlled_child(argv: Any, **_kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        routed = tuple(str(part) for part in argv)
        calls.append(routed)
        return subprocess.CompletedProcess(
            args=list(routed),
            returncode=0,
            stdout=f"stdout:{len(calls)}\n".encode(),
            stderr=f"stderr:{len(calls)}\n".encode(),
        )

    def controlled_conditional(*, gate: dict[str, Any], receipt_dir: Path | None) -> list[Any]:
        command = sota._parse_gate_command(gate.get("command"))
        assert command is not None
        completed = sota._run_subprocess_with_receipt(
            str(gate["id"]), command, receipt_dir=receipt_dir
        )
        return [] if completed.returncode == 0 else [sota.Finding(str(gate["id"]), "failed")]

    monkeypatch.setattr(sota, "run_command", controlled_child)
    monkeypatch.setattr(sota, "_run_subprocess_with_receipt", record_subprocess_gate)
    monkeypatch.setattr(
        sota,
        "_conditional_gate_handlers",
        lambda: {"docs-freshness-runtime": controlled_conditional},
    )
    receipt_dir = output / "children"
    args = argparse.Namespace(skip_generated_checks=False, subprocess_receipt_dir=receipt_dir)

    with SecureOutputRoot(output) as root, bind_cli_output_scope(root):
        findings = sota._run_fail_closed_subprocess_gates(args)
        assert findings == []
        assert Counter(invoked_gates) == expected_gate_ids

        report_paths = _report_path_set(commands)
        assert len(report_paths) == len(
            {
                path
                for gate, command in commands
                for _option, path in _report_option_paths(
                    tuple(sota._route_native_child_report_outputs(gate, command))
                )
            }
        )
        assert all(path.is_relative_to(root.root) for path in report_paths)
        check_only_outputs = [
            (gate, command)
            for gate, command in commands
            if "--output" in command and "--check" in command
        ]
        assert check_only_outputs
        for gate, command in check_only_outputs:
            assert sota._route_native_child_report_outputs(gate, command) == command

        receipt_files = sorted(receipt_dir.glob("*/receipt.json"))
        stdout_files = sorted(receipt_dir.glob("*/stdout.bin"))
        stderr_files = sorted(receipt_dir.glob("*/stderr.bin"))
        assert Counter(calls) == Counter(
            tuple(sota._route_native_child_report_outputs(gate, command))
            for gate, command in commands
        )
        expected_count = sum(expected_gate_ids.values())
        assert len(receipt_files) == len(stdout_files) == len(stderr_files) == expected_count
        assert {path.parent.name for path in receipt_files} == set(expected_gate_ids)
        for receipt_path in receipt_files:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            child_dir = receipt_path.parent
            assert receipt["gate"] == child_dir.name
            assert receipt["exit_code"] == 0
            assert (child_dir / "stdout.bin").read_bytes().startswith(b"stdout:")
            assert (child_dir / "stderr.bin").read_bytes().startswith(b"stderr:")


def test_all_live_sota_report_cli_emitters_write_complete_scoped_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _assert_product_modules_loaded()
    output = tmp_path / "native-output"
    output.mkdir()
    fixture_root = tmp_path / "source-fixture"
    fixture_root.mkdir()
    with SecureOutputRoot(output) as root, bind_cli_output_scope(root):
        outputs = _run_actual_report_emitters(monkeypatch, fixture_root)
        expected_report_paths = _report_path_set(_all_live_child_commands())
        schema_paths = {
            scoped_report_path(
                "schema-purity", Path("_build/.tmp/last-mile/schemas-python-residue.txt")
            ),
            scoped_report_path(
                "workspace-verify-schema-purity",
                Path("_build/.tmp/last-mile/schemas-python-residue.txt"),
            ),
        }
        actual_report_paths = {path for key, path in outputs.items() if "schema-purity" not in key}
        assert actual_report_paths == expected_report_paths
        assert {outputs["schema-purity"], outputs["workspace-verify-schema-purity"]} == schema_paths
        for sink, path in outputs.items():
            assert path.is_relative_to(root.root), sink
            assert path.is_file(), sink
            if "schema-purity" not in sink:
                assert path.stat().st_size > 0, sink

        for sink in (
            _output_for(outputs, "directory-health", "--json-output"),
            _output_for(outputs, "acceptance-audit", "--json-output"),
        ):
            report = json.loads(sink.read_text(encoding="utf-8"))
            assert isinstance(report, dict)
            assert report
        assert "# Platform Acceptance Audit" in _output_for(
            outputs, "acceptance-audit", "--summary"
        ).read_text(encoding="utf-8")
        assert outputs["schema-purity"].read_text(encoding="utf-8") == ""
        assert outputs["workspace-verify-schema-purity"].read_text(encoding="utf-8") == ""

        requested = tmp_path / "caller-selected" / "sota-report.json"
        monkeypatch.setattr(sota, "_preflight_checks", lambda: (("fixture", lambda: []),))
        assert sota.main(["--contract-only", "--output-json", str(requested)]) == 0
        routed_sota_report = (
            root.root / "children" / "repository-sota-closeout" / "reports" / requested.name
        )
        assert json.loads(routed_sota_report.read_text(encoding="utf-8"))["status"] == "passed"

        timing_records = read_timing_records(root.root / ".polisyos-tools/timing.jsonl")
        assert any(record.tool == "workspace.acceptance-audit" for record in timing_records)


def test_unscoped_direct_report_api_keeps_path_write_overwrite_semantics(
    tmp_path: Path,
) -> None:
    from tools.lib.fs import scoped_report_path, write_scoped_report_text

    report = tmp_path / "ordinary" / "report.json"
    report.parent.mkdir()
    report.write_bytes(b"prior caller report\n")
    assert scoped_report_path("ordinary-cli", report) == report
    write_scoped_report_text(report, "complete replacement\n", atomic=False)
    assert report.read_text(encoding="utf-8") == "complete replacement\n"


def test_parent_symlink_escape_probe_fails_if_nofollow_is_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "native-output"
    output.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    outside_marker = external / "preserve.marker"
    marker = b"external directory remains unchanged\n"
    outside_marker.write_bytes(marker)
    (output / "children").symlink_to(external, target_is_directory=True)

    with SecureOutputRoot(output) as root, bind_secure_output_root(root):
        path = scoped_report_path("guarded-sink", Path("report.json"))
        with pytest.raises(OSError):
            write_scoped_report_text(path, "guarded output\n", atomic=False)

    assert outside_marker.read_bytes() == marker
    escaped_report = external / "unguarded-sink" / "reports" / "report.json"
    assert not escaped_report.exists()

    with SecureOutputRoot(output) as root, bind_secure_output_root(root):
        monkeypatch.setattr(fs_module.os, "O_NOFOLLOW", 0)
        path = scoped_report_path("unguarded-sink", Path("report.json"))
        write_scoped_report_text(path, "escaped output\n", atomic=False)

    assert outside_marker.read_bytes() == marker
    assert escaped_report.read_text(encoding="utf-8") == "escaped output\n"
    with pytest.raises(AssertionError):
        assert not escaped_report.exists()

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

from tools.cli import EX_CONFIG, main
from tools.lib.output import ToolMessage, ToolResult, format_tool_result
from tools.lib.runner import ToolStatus
from tools.lib.timing import ToolRunRecord, append_timing_record, read_timing_records
from tools.registry import (
    CATEGORY_MANIFEST,
    TOOL_SPECS_BY_KEY,
    dependency_edges,
    render_reference_docs,
    zones,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _entry_callable(path: Path) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return "main"
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "check":
            return "check"
    return None


def test_unified_cli_help_discovers_tool_categories(capsys) -> None:
    exit_code = main(["--help"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Commands:" in captured.out
    assert "diagnostics" in captured.out
    assert "workspace" in captured.out


def test_registry_discovers_zoned_package_entry_points() -> None:
    missing: list[str] = []
    for category, manifest in CATEGORY_MANIFEST.items():
        for path in sorted(manifest.implementation_root.glob("*.py")):
            if path.name in {"__init__.py", "_common.py"}:
                continue
            if _entry_callable(path) is None:
                continue
            command = path.stem.replace("_", "-")
            if (category, command) not in TOOL_SPECS_BY_KEY:
                missing.append(f"{category}.{command}")

    assert missing == []


def test_list_groups_commands_by_zone(capsys) -> None:
    exit_code = main(["list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    for zone in zones():
        assert f"{zone}:" in captured.out
    assert "  workspace:" in captured.out
    assert "  benchmarks:" in captured.out


def test_quarantined_tools_block_before_import(capsys) -> None:
    exit_code = main(["diagnostics", "check-udf-perf"])

    captured = capsys.readouterr()
    assert exit_code == EX_CONFIG
    assert "quarantined" in captured.err
    assert "polisyos.fabric.udf.engine" in captured.err


def test_command_help_delegates_to_underlying_parser(capsys) -> None:
    exit_code = main(["diagnostics", "check-setup", "--help"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Smoke test" in captured.out


def test_graph_and_reference_docs_are_generated_from_metadata(capsys) -> None:
    graph_exit = main(["graph", "--format", "mermaid"])
    graph_output = capsys.readouterr().out

    assert graph_exit == 0
    assert graph_output.startswith("graph TD")
    assert ("diagnostics.gen-schema", "diagnostics.abi-diff") in dependency_edges()
    docs = render_reference_docs()
    assert "## Zones" in docs
    assert "## Dependency Graph" in docs
    assert "`check-udf-perf` | `quarantined`" in docs
    assert "`polisyos-tools workspace bootstrap`" in docs
    assert "`polisyos-tools workspace lint-fast`" in docs
    assert "`polisyos-tools workspace format-check`" in docs


def test_completion_snippets_cover_supported_shells(capsys) -> None:
    assert main(["completion", "zsh"]) == 0
    assert "_POLISYOS_TOOLS_COMPLETE=zsh_source" in capsys.readouterr().out


def test_common_output_formatters_are_structured() -> None:
    result = ToolResult(
        tool="lint.example",
        status="failed",
        exit_code=1,
        messages=(
            ToolMessage(
                level="error",
                message="bad thing",
                path="x.py",
                line=3,
                rule_id="T1",
            ),
        ),
    )

    assert format_tool_result(result, "json").endswith("\n")
    assert '"status": "failed"' in format_tool_result(result, "json")
    assert '"version": "2.1.0"' in format_tool_result(result, "sarif")
    assert "<testsuite" in format_tool_result(result, "junit")


def test_legacy_statuses_are_explicit() -> None:
    assert TOOL_SPECS_BY_KEY[("diagnostics", "check-udf-perf")].status == ToolStatus.QUARANTINED
    assert TOOL_SPECS_BY_KEY[("demos", "run-export-demo")].status == ToolStatus.DEPRECATED


def test_report_timing_summarizes_budgeted_runs(tmp_path: Path, capsys) -> None:
    timing_log = tmp_path / "timing.jsonl"
    append_timing_record(
        timing_log,
        ToolRunRecord(
            tool="workspace.verify",
            category="workspace",
            output_format="text",
            status="ok",
            preflight_status="ok",
            started_at="2026-04-13T10:00:00+00:00",
            duration_ms=450000.0,
            exit_code=0,
        ),
    )
    append_timing_record(
        timing_log,
        ToolRunRecord(
            tool="lint.lint-imports",
            category="lint",
            output_format="json",
            status="failed",
            preflight_status="ok",
            started_at="2026-04-13T10:01:00+00:00",
            duration_ms=1200.0,
            exit_code=1,
        ),
    )

    summary_path = tmp_path / "timing-summary.md"
    exit_code = main(
        [
            "report-timing",
            "--timing-log",
            str(timing_log),
            "--output-format",
            "json",
            "--limit",
            "2",
            "--summary-markdown",
            str(summary_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["record_count"] == 2
    assert payload["summaries"][0]["tool"] == "workspace.verify"
    assert payload["summaries"][0]["over_budget_runs"] == 1
    assert summary_path.exists()
    assert "Tool Timing Summary" in summary_path.read_text(encoding="utf-8")


def test_quarantined_preflight_records_skipped_run(tmp_path: Path, capsys) -> None:
    timing_log = tmp_path / "timing.jsonl"

    exit_code = main(["diagnostics", "check-udf-perf", "--timing-log", str(timing_log)])

    captured = capsys.readouterr()
    records = read_timing_records(timing_log)
    assert exit_code == EX_CONFIG
    assert "quarantined" in captured.err
    assert records[-1].tool == "diagnostics.check-udf-perf"
    assert records[-1].status == "skipped"
    assert records[-1].preflight_status == "quarantined"


def test_python_module_cli_smoke_subprocess() -> None:
    result = subprocess.run(  # noqa: S603 - trusted repo-local CLI smoke test
        # Trusted smoke invocation of the repo-local CLI.
        [sys.executable, "-m", "tools.cli", "list", "--output-format", "json"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert any(item["qualified_name"] == "diagnostics.gen-schema" for item in payload)
    assert any(
        item["zone"] == "research" and item["qualified_name"] == "benchmarks.run-all"
        for item in payload
    )


def test_python_module_compatibility_shim_smoke_subprocess() -> None:
    result = subprocess.run(  # noqa: S603 - trusted compatibility shim smoke test
        # Trusted smoke invocation of the compatibility shim.
        [sys.executable, "-m", "tools.devx.workspace.bootstrap", "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--profile" in result.stdout

from __future__ import annotations

import contextvars
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from tools import cli as tools_cli
from tools.devx.workspace import repository_sota_closeout, tool_configs
from tools.lib.fs import SecureOutputRoot, bind_secure_output_root
from tools.lib.runner import ToolSpec, run_command
from tools.lib.timing import (
    DEFAULT_TIMING_LOG_ENV,
    append_timing_record,
    bind_cli_output_scope,
    make_timing_record,
    read_timing_records,
)

PRODUCT_ROOT = Path(tools_cli.__file__).resolve().parents[1]
TOOL_IMPORT_ROOT = Path(tool_configs.__file__).resolve().parents[3]
CHILD_PRODUCT_ROOT_ENV = "POLISYOS_TEST_PRODUCT_ROOT"
CHILD_IMPORT_ROOT_ENV = "POLISYOS_TEST_IMPORT_ROOT"
CHILD_REPORT_ENV = "POLISYOS_TEST_REPORT"


@pytest.fixture(autouse=True)
def _use_canonical_product_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tool_configs, "REPO_ROOT", PRODUCT_ROOT)
    monkeypatch.setattr(repository_sota_closeout, "REPO_ROOT", PRODUCT_ROOT)


def _record(name: str):
    spec = ToolSpec(
        name=name,
        zone="repo",
        category="output-scope-test",
        module="tools.devx.workspace.tool_configs",
    )
    return make_timing_record(
        spec,
        {
            "status": "ok",
            "preflight_status": "ok",
            "started_at": "2026-10-15T00:00:00+00:00",
            "duration_ms": 1.0,
            "mode": "test",
        },
        exit_code=0,
        output_format="json",
    )


def _child_cli_code() -> str:
    return (
        "import os, sys; "
        "sys.path.insert(0, os.environ['POLISYOS_TEST_IMPORT_ROOT']); "
        "from pathlib import Path; "
        "from tools.devx.workspace import tool_configs; "
        "tool_configs.REPO_ROOT=Path(os.environ['POLISYOS_TEST_PRODUCT_ROOT']); "
        "from tools.cli import main; "
        "raise SystemExit(main(['workspace','tool-configs','--check','--json-output',"
        "os.environ['POLISYOS_TEST_REPORT']]))"
    )


def test_product_cli_scopes_report_and_timing_and_preserves_complete_report(
    tmp_path: Path,
) -> None:
    output = tmp_path / "native-output"
    output.mkdir()
    report_path = output / "tool-configs-report.json"
    with SecureOutputRoot(output) as root, bind_cli_output_scope(root):
        first_code = tools_cli.main(
            ["workspace", "tool-configs", "--check", "--json-output", str(report_path)]
        )
        first_report = json.loads(report_path.read_text(encoding="utf-8"))
        second_code = tools_cli.main(
            ["workspace", "tool-configs", "--check", "--json-output", str(report_path)]
        )
        second_report = json.loads(report_path.read_text(encoding="utf-8"))
        timing_path = Path(os.environ[DEFAULT_TIMING_LOG_ENV])
        records = read_timing_records(timing_path)

    expected_keys = {
        "status",
        "generated_files",
        "drift_findings",
        "override_findings",
    }
    assert first_code == int(first_report["status"] == "failed")
    assert second_code == int(second_report["status"] == "failed")
    assert set(first_report) == expected_keys
    assert second_report == first_report
    assert [record.tool for record in records] == [
        "workspace.tool-configs",
        "workspace.tool-configs",
    ]


def test_canonical_sota_child_bridge_scopes_child_cli_report_and_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "native-output"
    output.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    report_path = output / "tool-configs-report.json"
    external_report = external / report_path.name
    marker = b"external report is preserved\n"
    external_report.write_bytes(marker)
    moved_output = tmp_path / "moved-output"
    receipt_dir = output / "children"
    monkeypatch.setenv(CHILD_PRODUCT_ROOT_ENV, str(PRODUCT_ROOT))
    monkeypatch.setenv(CHILD_IMPORT_ROOT_ENV, str(TOOL_IMPORT_ROOT))
    monkeypatch.setenv(CHILD_REPORT_ENV, str(report_path))

    with SecureOutputRoot(output) as root, bind_cli_output_scope(root):
        output.rename(moved_output)
        output.symlink_to(external, target_is_directory=True)
        completed = repository_sota_closeout._run_subprocess_with_receipt(
            "output-scope-child",
            [sys.executable, "-c", _child_cli_code()],
            receipt_dir=receipt_dir,
        )
        report = json.loads((moved_output / report_path.name).read_text(encoding="utf-8"))
        receipt_path = moved_output / "children/output-scope-child/receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        records = read_timing_records(root.root / ".polisyos-tools/timing.jsonl")

    assert completed.returncode == int(report["status"] == "failed")
    assert set(report) == {
        "status",
        "generated_files",
        "drift_findings",
        "override_findings",
    }
    assert external_report.read_bytes() == marker
    assert receipt["gate"] == "output-scope-child"
    assert receipt["stdout"]["byte_length"] == len(completed.stdout.encode("utf-8"))
    assert [record.tool for record in records] == ["workspace.tool-configs"]


def test_unscoped_tool_config_json_keeps_atomic_overwrite_compatibility(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "ordinary" / "report.json"
    report_path.parent.mkdir()
    report_path.write_bytes(b"caller-owned prior report\n")

    exit_code = tool_configs.main(["--check", "--json-output", str(report_path)])

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert exit_code == int(report["status"] == "failed")
    assert set(report) == {
        "status",
        "generated_files",
        "drift_findings",
        "override_findings",
    }


def test_scoped_report_parent_symlink_is_rejected_without_touching_target(
    tmp_path: Path,
) -> None:
    output = tmp_path / "native-output"
    output.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    external_marker = external / "preserve.marker"
    marker = b"foreign output directory remains untouched\n"
    external_marker.write_bytes(marker)
    external_report = external / "report.json"
    assert not external_report.exists()
    (output / "redirect").symlink_to(external, target_is_directory=True)

    with (
        SecureOutputRoot(output) as root,
        bind_secure_output_root(root),
        pytest.raises(OSError, match=r"(?i)symbolic link|not a directory|too many levels"),
    ):
        tool_configs.main(["--check", "--json-output", str(output / "redirect" / "report.json")])

    assert external_marker.read_bytes() == marker
    assert not external_report.exists()


def test_foreign_preexisting_report_is_not_adopted_by_scoped_cli(tmp_path: Path) -> None:
    output = tmp_path / "native-output"
    output.mkdir()
    report_path = output / "report.json"
    marker = b"foreign preexisting output\n"
    report_path.write_bytes(marker)

    with (
        SecureOutputRoot(output) as root,
        bind_secure_output_root(root),
        pytest.raises(FileExistsError),
    ):
        tool_configs.main(["--check", "--json-output", str(report_path)])

    assert report_path.read_bytes() == marker


def test_scoped_timing_retains_all_concurrent_thread_appends(tmp_path: Path) -> None:
    output = tmp_path / "native-output"
    output.mkdir()
    with SecureOutputRoot(output) as root, bind_cli_output_scope(root):
        contexts = [contextvars.copy_context() for _ in range(16)]
        lock_path = root.root / ".polisyos-tools/.timing.jsonl.lock"
        active = 0
        maximum_active = 0
        counter_lock = threading.Lock()

        def hold_lock() -> None:
            nonlocal active, maximum_active
            with root.open_owned_binary(lock_path):
                with counter_lock:
                    active += 1
                    maximum_active = max(maximum_active, active)
                time.sleep(0.01)
                with counter_lock:
                    active -= 1

        with ThreadPoolExecutor(max_workers=16) as pool:
            lock_futures = [pool.submit(context.run, hold_lock) for context in contexts]
            for future in lock_futures:
                future.result()
        contexts = [contextvars.copy_context() for _ in range(16)]
        timing_path = root.root / ".polisyos-tools/timing.jsonl"
        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = [
                pool.submit(
                    context.run,
                    append_timing_record,
                    timing_path,
                    _record(f"thread-{index}"),
                )
                for index, context in enumerate(contexts)
            ]
            for future in futures:
                future.result()
        records = read_timing_records(timing_path)

    assert maximum_active == 1
    assert {record.tool for record in records} == {
        f"output-scope-test.thread-{index}" for index in range(16)
    }
    assert len(records) == 16


def test_scoped_timing_retains_all_concurrent_child_process_appends(tmp_path: Path) -> None:
    output = tmp_path / "native-output"
    output.mkdir()
    child = (
        "import os; "
        "from tools.lib.runner import ToolSpec; "
        "from tools.lib.timing import "
        "append_timing_record, make_timing_record, timing_log_from_env; "
        "spec=ToolSpec(name=os.environ['CASE'], zone='repo', category='child', module='test'); "
        "record=make_timing_record(spec, {'status':'ok','preflight_status':'ok',"
        "'started_at':'2026-10-15T00:00:00+00:00','duration_ms':1.0}, "
        "exit_code=0, output_format='json'); "
        "append_timing_record(timing_log_from_env(), record)"
    )
    with SecureOutputRoot(output) as root, bind_cli_output_scope(root):
        contexts = [contextvars.copy_context() for _ in range(16)]

        def run_child(index: int) -> None:
            result = run_command(
                [sys.executable, "-c", child],
                env={**os.environ, "CASE": f"child-{index}"},
                cwd=TOOL_IMPORT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stderr

        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = [
                pool.submit(context.run, run_child, index) for index, context in enumerate(contexts)
            ]
            for future in futures:
                future.result()
        timing_path = root.root / ".polisyos-tools/timing.jsonl"
        records = read_timing_records(timing_path)

    assert {record.tool for record in records} == {f"child.child-{index}" for index in range(16)}
    assert len(records) == 16

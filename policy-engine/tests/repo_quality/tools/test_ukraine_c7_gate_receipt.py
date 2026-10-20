from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.data_forge.domains.ukraine.manifests import (
    PartAGateExecutionReceipt,
    PartAGateManifest,
)
from polisyos.data_forge.domains.ukraine.models import build_default_pipeline_config
from tools.ops_runners.ukraine_data import validate_part_a

C7_PATH = "tests/integration/test_c7_synthetic_full_pipeline.py"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _run_tiny_pytest(
    workspace: Path,
    *,
    attempt_id: str = "a" * 32,
    pytest_arguments: tuple[str, ...] = (),
    module_skip_reason: str | None = None,
    earlier_tryfirst_filter: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Run the production receipt plugin against a portable two-case C7 fixture."""

    (workspace / "src" / "polisyos").mkdir(parents=True)
    test_path = workspace / C7_PATH
    test_path.parent.mkdir(parents=True)
    source = "import pytest\npytestmark = pytest.mark.integration\n"
    if module_skip_reason is not None:
        source = (
            "import pytest\npytestmark = [pytest.mark.integration, pytest.mark.skipif(True, reason="
            + repr(module_skip_reason)
            + ")]\n"
        )
    source += (
        "def test_first_case():\n    assert 2 + 2 == 4\n\n"
        "def test_second_case():\n    assert 'policy' in 'public policy'\n"
    )
    test_path.write_text(source, encoding="utf-8")
    (workspace / "pytest.ini").write_text(
        "[pytest]\nmarkers =\n    integration: tiny C7 fixture\n", encoding="utf-8"
    )
    if earlier_tryfirst_filter:
        (workspace / "tests" / "conftest.py").write_text(
            "import pytest\n\n"
            "@pytest.hookimpl(tryfirst=True)\n"
            "def pytest_collection_modifyitems(items):\n"
            "    if items:\n"
            "        items.pop()\n",
            encoding="utf-8",
        )
    (workspace / "pyproject.toml").write_text(
        "[project]\nname = 'c7-gate-fixture'\nversion = '0.0.0'\n",
        encoding="utf-8",
    )
    receipt_root = workspace.parent / f"receipts-{attempt_id}"
    receipt_root.mkdir()
    workload_path = receipt_root / "workload.json"
    phases_path = receipt_root / "phases.json"
    environment = dict(os.environ)
    source_root = str(REPO_ROOT)
    inherited_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_root if not inherited_pythonpath else source_root + os.pathsep + inherited_pythonpath
    )
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    environment.update(
        {
            "POLISYOS_PYTEST_RECEIPT_ATTEMPT_ID": attempt_id,
            "POLISYOS_PYTEST_RECEIPT_SIDECAR": str(workload_path),
            "POLISYOS_PYTEST_RECEIPT_OUTPUT_ROOT": str(receipt_root),
            "POLISYOS_PYTEST_RECEIPT_PHASES_SIDECAR": str(phases_path),
            "POLISYOS_PYTEST_RECEIPT_REPO_ROOT": str(workspace),
            "POLISYOS_PYTEST_RECEIPT_CODE_ROOT": str(REPO_ROOT),
            "POLISYOS_PYTEST_RECEIPT_TEST_PATHS": json.dumps([C7_PATH]),
        }
    )
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--import-mode=importlib",
        "--strict-markers",
        "-o",
        "addopts=",
        "-p",
        "tools.quality.testing.pytest_workload_receipt",
        *pytest_arguments,
        C7_PATH,
    ]
    completed = subprocess.run(
        command,
        cwd=workspace,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed, workload_path, phases_path


def _read_receipt(
    workspace: Path,
    workload_path: Path,
    phases_path: Path,
    exit_code: int,
) -> PartAGateExecutionReceipt:
    return validate_part_a._read_execution_receipt(
        attempt_id="a" * 32,
        workspace_root=workspace,
        workload_path=workload_path,
        phases_path=phases_path,
        exit_code=exit_code,
    )


def test_real_pytest_child_records_complete_c7_collection_and_all_phases(
    tmp_path: Path,
) -> None:
    completed, workload_path, phases_path = _run_tiny_pytest(tmp_path / "checkout")

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "2 passed" in completed.stdout
    receipt = _read_receipt(tmp_path / "checkout", workload_path, phases_path, 0)
    assert len(receipt.node_ids) == 2
    assert receipt.complete_pass
    assert receipt.collection_context.pluggy_version


def test_real_module_setup_skip_is_preserved_as_skipped_with_reason(tmp_path: Path) -> None:
    completed, workload_path, phases_path = _run_tiny_pytest(
        tmp_path / "checkout",
        module_skip_reason="lifelines is required for C7",
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    receipt = _read_receipt(tmp_path / "checkout", workload_path, phases_path, 0)
    assert receipt.complete_lifecycle
    assert not receipt.complete_pass
    assert receipt.complete_skip
    assert validate_part_a._classify_execution_receipt(receipt) == "skipped"
    manifest = PartAGateManifest(
        status="skipped",
        passed=False,
        skipped=True,
        execution_receipt=receipt,
    )
    assert manifest.skipped and not manifest.passed
    assert all(
        not any(
            phase.node_id == node_id and phase.when == "call" for phase in receipt.phase_reports
        )
        for node_id in receipt.node_ids
    )
    assert all(
        "lifelines is required for C7" in (phase.reason or "")
        for phase in receipt.phase_reports
        if phase.outcome == "skipped"
    )
    incomplete = PartAGateExecutionReceipt.model_validate(
        receipt.model_dump()
        | {"phase_reports": [phase.model_dump() for phase in receipt.phase_reports[:-1]]}
    )
    assert not incomplete.complete_lifecycle
    with pytest.raises(ValidationError, match="complete skip evidence"):
        PartAGateManifest(
            status="skipped",
            passed=False,
            skipped=True,
            execution_receipt=incomplete,
        )


def test_earlier_tryfirst_filter_cannot_narrow_the_c7_denominator(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    completed, workload_path, phases_path = _run_tiny_pytest(
        workspace,
        earlier_tryfirst_filter=True,
    )

    assert completed.returncode != 0
    with pytest.raises((OSError, ValueError)):
        _read_receipt(workspace, workload_path, phases_path, completed.returncode)


def test_collect_only_zero_exit_does_not_prove_c7_execution(tmp_path: Path) -> None:
    completed, workload_path, phases_path = _run_tiny_pytest(
        tmp_path / "checkout",
        pytest_arguments=("--collect-only",),
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    receipt = _read_receipt(tmp_path / "checkout", workload_path, phases_path, 0)
    assert receipt.node_ids
    assert receipt.phase_reports == []
    assert not receipt.complete_pass


def test_narrowed_pytest_selection_cannot_reconcile_full_c7_collection(
    tmp_path: Path,
) -> None:
    completed, workload_path, phases_path = _run_tiny_pytest(
        tmp_path / "checkout",
        pytest_arguments=("-k", "first_case"),
    )

    assert completed.returncode != 0
    with pytest.raises((OSError, ValueError)):
        _read_receipt(tmp_path / "checkout", workload_path, phases_path, completed.returncode)


def test_missing_phase_is_incomplete_execution_not_a_pass(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    completed, workload_path, phases_path = _run_tiny_pytest(workspace)
    assert completed.returncode == 0, completed.stdout + completed.stderr

    phases = json.loads(phases_path.read_text(encoding="utf-8"))
    phases["phase_reports"].pop()
    phases_path.write_text(json.dumps(phases), encoding="utf-8")
    receipt = _read_receipt(workspace, workload_path, phases_path, completed.returncode)

    assert not receipt.complete_lifecycle
    assert not receipt.complete_pass


def test_replaced_attempt_and_workload_bytes_fail_receipt_binding(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    completed, workload_path, phases_path = _run_tiny_pytest(workspace)
    assert completed.returncode == 0, completed.stdout + completed.stderr

    phases = json.loads(phases_path.read_text(encoding="utf-8"))
    phases["attempt_id"] = "b" * 32
    phases_path.write_text(json.dumps(phases), encoding="utf-8")
    with pytest.raises(ValueError, match="attempt identity"):
        _read_receipt(workspace, workload_path, phases_path, completed.returncode)

    completed, workload_path, phases_path = _run_tiny_pytest(
        tmp_path / "second-checkout", attempt_id="d" * 32
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    workload_path.write_text(workload_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="does not bind"):
        validate_part_a._read_execution_receipt(
            attempt_id="d" * 32,
            workspace_root=tmp_path / "second-checkout",
            workload_path=workload_path,
            phases_path=phases_path,
            exit_code=completed.returncode,
        )


def test_duplicate_phase_report_is_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "checkout"
    completed, workload_path, phases_path = _run_tiny_pytest(workspace)
    assert completed.returncode == 0, completed.stdout + completed.stderr

    phases = json.loads(phases_path.read_text(encoding="utf-8"))
    phases["phase_reports"].append(phases["phase_reports"][0])
    phases_path.write_text(json.dumps(phases), encoding="utf-8")
    with pytest.raises(ValidationError, match="duplicate node phase"):
        _read_receipt(workspace, workload_path, phases_path, completed.returncode)


def test_removing_phase_proof_while_success_marker_remains_cannot_pass_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    (checkout / "src" / "polisyos").mkdir(parents=True)
    (checkout / "tests" / "integration").mkdir(parents=True)
    (checkout / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    (checkout / C7_PATH).write_text("def test_case():\n    assert True\n", encoding="utf-8")
    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False

    def success_marker_only(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout="2 passed", stderr="")

    monkeypatch.setattr(validate_part_a.subprocess, "run", success_marker_only)
    manifest = validate_part_a.run_part_a_gate(config.server, checkout)

    assert manifest.status == "failed"
    assert manifest.passed is False
    assert manifest.execution_receipt is None
    assert "2 passed" in "\n".join(manifest.notes)
    with pytest.raises(ValidationError, match="complete C7 phase evidence"):
        PartAGateManifest(status="passed", passed=True)

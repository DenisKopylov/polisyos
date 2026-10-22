from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
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


_TEMP_PATH_CAPTURE_ENV = "POLISYOS_TEST_C7_TEMP_PATH_CAPTURE"


def _make_output_location_checkout(workspace: Path) -> None:
    (workspace / "src" / "polisyos").mkdir(parents=True)
    test_path = workspace / C7_PATH
    test_path.parent.mkdir(parents=True)
    test_path.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "import pytest\n"
        "pytestmark = pytest.mark.integration\n"
        "def test_c7_output_locations(request, tmp_path):\n"
        "    request.config.cache.set('c7-output-probe', 'written')\n"
        "    (tmp_path / 'c7-temp-probe.txt').write_text('written', encoding='utf-8')\n"
        "    capture = os.environ.get('POLISYOS_TEST_C7_TEMP_PATH_CAPTURE')\n"
        "    if capture:\n"
        "        Path(capture).write_text(str(tmp_path), encoding='utf-8')\n"
        "def test_c7_output_location_second_case():\n"
        "    assert 'policy' in 'public policy'\n",
        encoding="utf-8",
    )
    (workspace / "pytest.ini").write_text(
        "[pytest]\ncache_dir = _cache/pytest\nmarkers =\n    integration: synthetic C7 fixture\n",
        encoding="utf-8",
    )
    (workspace / "pyproject.toml").write_text(
        "[project]\nname = 'c7-output-location-fixture'\nversion = '0.0.0'\n",
        encoding="utf-8",
    )


def _install_real_gate_child(
    monkeypatch: pytest.MonkeyPatch,
    *,
    remove_attempt_options: bool = False,
) -> list[dict[str, object]]:
    observations: list[dict[str, object]] = []
    real_run = subprocess.run

    def translate_uv_to_real_pytest(
        command: list[str],
        *,
        cwd: Path,
        capture_output: bool,
        text: bool,
        env: dict[str, str],
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert command[1:3] == ["run", "pytest"]
        pytest_args = list(command[3:])
        if remove_attempt_options:
            filtered: list[str] = []
            index = 0
            while index < len(pytest_args):
                if pytest_args[index] == "-o" and index + 1 < len(pytest_args):
                    if pytest_args[index + 1].startswith("cache_dir="):
                        index += 2
                        continue
                if pytest_args[index].startswith("--basetemp="):
                    index += 1
                    continue
                filtered.append(pytest_args[index])
                index += 1
            pytest_args = filtered
        child_env = dict(env)
        inherited = child_env.get("PYTHONPATH", "")
        child_env["PYTHONPATH"] = os.pathsep.join(
            value for value in (str(REPO_ROOT), str(REPO_ROOT / "src"), inherited) if value
        )
        translated = [sys.executable, "-B", "-m", "pytest", *pytest_args]
        completed = real_run(
            translated,
            cwd=cwd,
            capture_output=capture_output,
            text=text,
            env=child_env,
            check=check,
        )
        attempt_root = Path(child_env["POLISYOS_PYTEST_RECEIPT_OUTPUT_ROOT"])
        cache_option = next(
            (
                pytest_args[index + 1][len("cache_dir=") :]
                for index, value in enumerate(pytest_args[:-1])
                if value == "-o" and pytest_args[index + 1].startswith("cache_dir=")
            ),
            None,
        )
        basetemp_option = next(
            (
                value[len("--basetemp=") :]
                for value in pytest_args
                if value.startswith("--basetemp=")
            ),
            None,
        )
        capture_path = child_env.get(_TEMP_PATH_CAPTURE_ENV)
        captured_tmp_path = (
            Path(capture_path).read_text(encoding="utf-8")
            if capture_path and Path(capture_path).is_file()
            else None
        )
        cache_path = Path(cache_option) if cache_option else None
        basetemp_path = Path(basetemp_option) if basetemp_option else None
        observations.append(
            {
                "attempt_root": str(attempt_root),
                "attempt_mode": attempt_root.stat().st_mode & 0o777,
                "attempt_owner_uid": attempt_root.stat().st_uid if hasattr(os, "geteuid") else None,
                "cache_dir": cache_option,
                "basetemp": basetemp_option,
                "checkout_cache_exists": (cwd / "_cache" / "pytest").is_dir(),
                "checkout_cache_files": [
                    str(path.relative_to(cwd))
                    for path in (cwd / "_cache" / "pytest").rglob("*")
                    if path.is_file()
                ],
                "attempt_cache_files": (
                    [
                        str(path.relative_to(attempt_root))
                        for path in cache_path.rglob("*")
                        if path.is_file()
                    ]
                    if cache_path and cache_path.is_dir()
                    else []
                ),
                "attempt_basetemp_files": (
                    [
                        str(path.relative_to(attempt_root))
                        for path in basetemp_path.rglob("*")
                        if path.is_file()
                    ]
                    if basetemp_path and basetemp_path.is_dir()
                    else []
                ),
                "captured_tmp_path": captured_tmp_path,
                "returncode": completed.returncode,
                "stdout": completed.stdout or "",
                "stderr": completed.stderr or "",
                "translated_argv": translated,
            }
        )
        return completed

    monkeypatch.setattr(validate_part_a.subprocess, "run", translate_uv_to_real_pytest)
    return observations


def _write_c7_child_evidence(
    destination: Path,
    *,
    manifest: PartAGateManifest,
    observation: dict[str, object],
) -> None:
    destination.write_text(
        json.dumps(
            {
                "manifest": manifest.model_dump(mode="json"),
                "child_stdout": observation["stdout"],
                "child_stderr": observation["stderr"],
                "child_returncode": observation["returncode"],
                "translated_argv": observation["translated_argv"],
                "output_observation": {
                    key: value
                    for key, value in observation.items()
                    if key not in {"stdout", "stderr", "translated_argv"}
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_repository_gate_places_real_pytest_cache_and_basetemp_in_attempt_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "checkout"
    _make_output_location_checkout(workspace)
    temp_parent = tmp_path / "system-temp"
    temp_parent.mkdir()
    monkeypatch.setenv("TMPDIR", str(temp_parent))
    monkeypatch.setattr(tempfile, "tempdir", None)
    capture_path = tmp_path / "captured-inner-tmp-path.txt"
    junit_path = tmp_path / "c7-junit.xml"
    monkeypatch.setenv(_TEMP_PATH_CAPTURE_ENV, str(capture_path))
    monkeypatch.setenv("PYTEST_ADDOPTS", f"--junitxml={junit_path}")
    test_input = workspace / C7_PATH
    pytest_config = workspace / "pytest.ini"
    original_inputs = {
        test_input: test_input.read_bytes(),
        pytest_config: pytest_config.read_bytes(),
    }
    observations = _install_real_gate_child(monkeypatch)
    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False

    manifest = validate_part_a.run_part_a_gate(config.server, workspace)

    assert manifest.status == "passed", manifest.notes
    assert manifest.passed is True
    assert manifest.execution_receipt is not None
    assert manifest.execution_receipt.complete_pass
    assert len(manifest.execution_receipt.node_ids) == 2
    assert len(observations) == 1
    observation = observations[0]
    attempt_root = Path(str(observation["attempt_root"]))
    cache_dir = Path(str(observation["cache_dir"]))
    basetemp = Path(str(observation["basetemp"]))
    assert attempt_root.parent == temp_parent.resolve()
    assert not attempt_root.is_relative_to(workspace.resolve())
    if os.name == "posix":
        assert observation["attempt_mode"] == 0o700
        assert observation["attempt_owner_uid"] == os.geteuid()
    assert cache_dir == attempt_root / "pytest-cache"
    assert basetemp == attempt_root / "pytest-basetemp"
    assert observation["attempt_cache_files"]
    assert any(
        value.endswith("c7-temp-probe.txt") for value in observation["attempt_basetemp_files"]
    )
    captured_tmp_path = Path(str(observation["captured_tmp_path"]))
    assert captured_tmp_path.is_relative_to(basetemp)
    assert observation["checkout_cache_exists"] is False
    assert "2 passed" in str(observation["stdout"])
    assert observation["stderr"] == ""
    assert junit_path.is_file()
    assert 'tests="2"' in junit_path.read_text(encoding="utf-8")
    assert "2 passed" in "\n".join(manifest.notes)
    assert {path: path.read_bytes() for path in original_inputs} == original_inputs
    assert not attempt_root.exists()
    assert manifest.command == [
        config.server.uv_bin,
        "run",
        "pytest",
        "-q",
        "-ra",
        "--import-mode=importlib",
        "--strict-markers",
        "-o",
        "addopts=",
        "-o",
        f"cache_dir={attempt_root / 'pytest-cache'}",
        f"--basetemp={attempt_root / 'pytest-basetemp'}",
        "-p",
        "tools.quality.testing.pytest_workload_receipt",
        C7_PATH,
    ]
    _write_c7_child_evidence(
        tmp_path / "c7-private-attempt-positive-evidence.json",
        manifest=manifest,
        observation=observation,
    )


def test_removing_attempt_cache_and_temp_options_keeps_c7_marker_green_but_escapes_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "checkout"
    _make_output_location_checkout(workspace)
    temp_parent = tmp_path / "system-temp"
    temp_parent.mkdir()
    monkeypatch.setenv("TMPDIR", str(temp_parent))
    monkeypatch.setattr(tempfile, "tempdir", None)
    capture_path = tmp_path / "captured-inner-tmp-path.txt"
    monkeypatch.setenv(_TEMP_PATH_CAPTURE_ENV, str(capture_path))
    observations = _install_real_gate_child(monkeypatch, remove_attempt_options=True)
    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False

    manifest = validate_part_a.run_part_a_gate(config.server, workspace)

    assert manifest.status == "passed", manifest.notes
    assert manifest.passed is True
    assert manifest.execution_receipt is not None
    assert manifest.execution_receipt.complete_pass
    assert len(observations) == 1
    observation = observations[0]
    attempt_root = Path(str(observation["attempt_root"]))
    captured_tmp_path = Path(str(observation["captured_tmp_path"]))
    assert observation["cache_dir"] is None
    assert observation["basetemp"] is None
    assert observation["checkout_cache_exists"] is True
    assert observation["checkout_cache_files"]
    assert not captured_tmp_path.is_relative_to(attempt_root)
    assert "2 passed" in str(observation["stdout"])
    assert not attempt_root.exists()
    _write_c7_child_evidence(
        tmp_path / "c7-private-attempt-removal-control.json",
        manifest=manifest,
        observation=observation,
    )


def test_repository_gate_fails_closed_when_system_temp_is_inside_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "checkout"
    _make_output_location_checkout(workspace)
    monkeypatch.setenv("TMPDIR", str(workspace))
    monkeypatch.setattr(tempfile, "tempdir", None)
    calls: list[list[str]] = []

    def should_not_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="1 passed", stderr="")

    monkeypatch.setattr(validate_part_a.subprocess, "run", should_not_run)
    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False

    manifest = validate_part_a.run_part_a_gate(config.server, workspace)

    assert manifest.status == "failed"
    assert not manifest.passed and not manifest.skipped
    assert calls == []
    assert "inside the repository checkout" in " ".join(manifest.notes)
    assert list(workspace.glob("polisyos-ukraine-c7-*")) == []


def test_repository_gate_rejects_present_non_junit_pytest_addopts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "checkout"
    _make_output_location_checkout(workspace)
    temp_parent = tmp_path / "system-temp"
    temp_parent.mkdir()
    monkeypatch.setenv("TMPDIR", str(temp_parent))
    monkeypatch.setattr(tempfile, "tempdir", None)
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    calls: list[list[str]] = []

    def should_not_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="2 passed", stderr="")

    monkeypatch.setattr(validate_part_a.subprocess, "run", should_not_run)
    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False

    manifest = validate_part_a.run_part_a_gate(config.server, workspace)

    assert manifest.status == "failed"
    assert not manifest.passed and not manifest.skipped
    assert calls == []
    assert "outside the JUnit-only profile" in " ".join(manifest.notes)
    assert list(temp_parent.glob("polisyos-ukraine-c7-*")) == []


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

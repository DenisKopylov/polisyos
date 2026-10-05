from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.data_forge.domains.ukraine import cli, server
from polisyos.data_forge.domains.ukraine.manifests import PartAGateManifest
from polisyos.data_forge.domains.ukraine.models import build_default_pipeline_config
from polisyos.data_forge.domains.ukraine.orchestrator import UkraineDataOrchestrator


def _make_repository_checkout(root: Path) -> Path:
    """Create only the structural inputs needed for the repository gate."""

    (root / "src" / "polisyos").mkdir(parents=True)
    (root / "tests" / "integration").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    (root / "tests" / "integration" / "test_c7_synthetic_full_pipeline.py").write_text(
        "", encoding="utf-8"
    )
    return root


def _make_fake_uv(
    root: Path,
    record_path: Path,
    *,
    returncode: int,
    stdout: str,
) -> Path:
    """Create a subprocess fixture that records the actual gate invocation."""

    executable = root / "uv-fixture"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "Path(os.environ['UDF04_RECORD']).write_text("
        "json.dumps({'argv': sys.argv[1:], 'cwd': str(Path.cwd()), "
        "'integration': os.environ.get('POLISYOS_RUN_INTEGRATION')}), "
        "encoding='utf-8')\n"
        f"print({stdout!r})\n"
        f"raise SystemExit({returncode})\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _cli_environment(product_root: Path, record_path: Path) -> dict[str, str]:
    """Expose this checkout to a child CLI and direct its subprocess receipt to temp."""

    env = os.environ.copy()
    python_paths = [str(product_root / "src"), str(product_root)]
    if env.get("PYTHONPATH"):
        python_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_paths)
    env["UDF04_RECORD"] = str(record_path)
    return env


def _write_gate_config(tmp_path: Path, uv_executable: Path):
    """Build an isolated config that disables only the server-host admission check."""

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False
    config.server.uv_bin = str(uv_executable)
    config_path = tmp_path / "pipeline-config.json"
    config_path.write_text(config.model_dump_json(), encoding="utf-8")
    return config, config_path


def test_orchestrator_default_workspace_root_is_product_root_not_source_package(
    tmp_path: Path,
) -> None:
    """The default repository context must be the product root, not ``src/polisyos``."""

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    orchestrator = UkraineDataOrchestrator(config)

    expected_product_root = Path(__file__).resolve().parents[3]
    assert orchestrator.repo_root == expected_product_root
    assert orchestrator.repo_root != expected_product_root / "src" / "polisyos"


def test_installed_package_workspace_discovery_returns_unavailable_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A site-packages layout without repository inputs has no inferred root."""

    from polisyos.data_forge.domains.ukraine import orchestrator as orchestrator_module

    installed_package = (
        tmp_path / "site-packages" / "polisyos" / "data_forge" / "domains" / "ukraine"
    )
    installed_package.mkdir(parents=True)
    monkeypatch.setattr(orchestrator_module, "__file__", str(installed_package / "orchestrator.py"))

    assert orchestrator_module._discover_workspace_root() is None


def test_cli_preserves_build_root_and_forwards_workspace_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The artifact root and repository workspace root remain distinct CLI inputs."""

    captured: dict[str, object] = {}
    build_root = tmp_path / "artifacts"
    workspace_root = tmp_path / "checkout"

    class _Manifest:
        def model_dump(self, **_: object) -> dict[str, object]:
            return {}

    class _CapturingOrchestrator:
        def __init__(self, config: object, **kwargs: object) -> None:
            captured["build_root"] = config.build_root.root  # type: ignore[attr-defined]
            captured.update(kwargs)

        def validate_part_a(self) -> SimpleNamespace:
            return SimpleNamespace(status="skipped", manifest=_Manifest())

    monkeypatch.setattr(cli, "UkraineDataOrchestrator", _CapturingOrchestrator)
    monkeypatch.setattr(cli, "_emit", lambda payload: captured.update(emitted=payload))

    result = cli.main(
        [
            "--root",
            str(build_root),
            "--workspace-root",
            str(workspace_root),
            "validate-part-a",
        ]
    )

    assert result == 1
    assert captured["build_root"] == build_root
    forwarded_workspace = captured.get("workspace_root")
    if forwarded_workspace is None:
        forwarded_workspace = captured.get("repo_root")
    assert forwarded_workspace == workspace_root


@pytest.mark.parametrize(
    ("returncode", "stdout", "expected_status", "expected_passed", "expected_skipped"),
    [
        (0, "1 passed", "passed", True, False),
        (0, "1 passed, 0 skipped in 0.1s", "passed", True, False),
        (0, "1 skipped in 0.1s", "skipped", False, True),
        (1, "1 failed", "failed", False, False),
        (1, "1 failed, 1 skipped in 0.1s", "failed", False, True),
    ],
)
def test_part_a_gate_records_command_cwd_env_exit_and_skip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    returncode: int,
    stdout: str,
    expected_status: str,
    expected_passed: bool,
    expected_skipped: bool,
) -> None:
    """A recording subprocess proves gate semantics without provisioning or running C7."""

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False
    repo_root = _make_repository_checkout(tmp_path / "checkout")
    calls: list[dict[str, object]] = []

    def recording_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"command": list(command), **kwargs})
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(server.subprocess, "run", recording_run)

    manifest = server.run_part_a_gate(config.server, repo_root)

    assert len(calls) == 1
    assert manifest.server_only is True
    call = calls[0]
    assert call["command"] == [
        "uv",
        "run",
        "pytest",
        "-q",
        "tests/integration/test_c7_synthetic_full_pipeline.py",
    ]
    assert call["cwd"] == repo_root
    assert call["capture_output"] is True
    assert call["text"] is True
    assert call["check"] is False
    assert call["env"]["POLISYOS_RUN_INTEGRATION"] == "1"  # type: ignore[index]
    assert call["env"] is not os.environ
    assert manifest.command == call["command"]
    assert manifest.status == expected_status
    assert manifest.passed is expected_passed
    assert manifest.skipped is expected_skipped


def test_public_cli_uses_ops_gate_from_outside_workspace_and_persists_failure(
    tmp_path: Path,
) -> None:
    """The public command sends an explicit checkout to the ops gate callback."""

    product_root = Path(__file__).resolve().parents[3]
    outside_cwd = tmp_path / "outside-cwd"
    outside_cwd.mkdir()
    workspace_root = _make_repository_checkout(tmp_path / "checkout")
    record_path = tmp_path / "uv-record.json"
    uv_executable = _make_fake_uv(
        tmp_path,
        record_path,
        returncode=1,
        stdout="1 failed in 0.1s",
    )
    config, config_path = _write_gate_config(tmp_path, uv_executable)
    command = [
        sys.executable,
        "-m",
        "tools.ops_runners.ukraine_data.cli",
        "--config",
        str(config_path),
        "--root",
        str(config.build_root.root),
        "--workspace-root",
        str(workspace_root),
        "validate-part-a",
    ]

    completed = subprocess.run(
        command,
        cwd=outside_cwd,
        env=_cli_environment(product_root, record_path),
        capture_output=True,
        check=False,
        text=True,
    )

    recorded_call = json.loads(record_path.read_text(encoding="utf-8"))
    persisted_gate = json.loads(
        config.build_root.part_a_gate_manifest_path.read_text(encoding="utf-8")
    )
    assert completed.returncode == 1
    assert recorded_call == {
        "argv": ["run", "pytest", "-q", "tests/integration/test_c7_synthetic_full_pipeline.py"],
        "cwd": str(workspace_root),
        "integration": "1",
    }
    assert persisted_gate["status"] == "failed"
    assert persisted_gate["passed"] is False
    assert persisted_gate["command"][0] == str(uv_executable)


def test_public_cli_unavailable_workspace_skips_ops_subprocess(
    tmp_path: Path,
) -> None:
    """The public ops route returns typed unavailable for a non-checkout root."""

    product_root = Path(__file__).resolve().parents[3]
    outside_cwd = tmp_path / "outside-cwd"
    outside_cwd.mkdir()
    invalid_workspace = tmp_path / "not-a-checkout"
    record_path = tmp_path / "uv-record.json"
    uv_executable = _make_fake_uv(
        tmp_path,
        record_path,
        returncode=0,
        stdout="1 passed in 0.1s",
    )
    config, config_path = _write_gate_config(tmp_path, uv_executable)
    command = [
        sys.executable,
        "-m",
        "tools.ops_runners.ukraine_data.cli",
        "--config",
        str(config_path),
        "--root",
        str(config.build_root.root),
        "--workspace-root",
        str(invalid_workspace),
        "validate-part-a",
    ]

    completed = subprocess.run(
        command,
        cwd=outside_cwd,
        env=_cli_environment(product_root, record_path),
        capture_output=True,
        check=False,
        text=True,
    )

    persisted_gate = json.loads(
        config.build_root.part_a_gate_manifest_path.read_text(encoding="utf-8")
    )
    assert completed.returncode == 1
    assert not record_path.exists()
    assert persisted_gate["status"] == "unavailable"
    assert persisted_gate["passed"] is False
    assert persisted_gate["command"] == []
    assert str(invalid_workspace) in " ".join(persisted_gate["notes"])


def test_public_cli_gate_result_unlocks_d4_and_request_reads_back(
    tmp_path: Path,
) -> None:
    """The ops gate result is consumed by D4 and its producer artifact is readable."""

    from polisyos.data_forge.domains.ukraine.manifests import (
        BuildRunManifest,
        write_manifest,
    )
    from polisyos.data_forge.domains.ukraine.models import StageId

    product_root = Path(__file__).resolve().parents[3]
    outside_cwd = tmp_path / "outside-cwd"
    outside_cwd.mkdir()
    record_path = tmp_path / "uv-record.json"
    uv_executable = _make_fake_uv(
        tmp_path,
        record_path,
        returncode=0,
        stdout="1 passed, 0 skipped in 0.1s",
    )
    config, config_path = _write_gate_config(tmp_path, uv_executable)
    write_manifest(
        config.build_root.manifests_dir / "build_run_d3.json",
        BuildRunManifest(
            run_id="d3_completed_fixture",
            stage_id=StageId.D3,
            status="completed",
            started_at="2026-10-05T00:00:00Z",
            finished_at="2026-10-05T00:00:00Z",
        ),
    )
    common_args = ["--config", str(config_path), "--root", str(config.build_root.root)]
    gate = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.ops_runners.ukraine_data.cli",
            *common_args,
            "validate-part-a",
        ],
        cwd=outside_cwd,
        env=_cli_environment(product_root, record_path),
        capture_output=True,
        check=False,
        text=True,
    )
    build = subprocess.run(
        [sys.executable, "-m", "tools.ops_runners.ukraine_data.cli", *common_args, "build", "d4"],
        cwd=outside_cwd,
        env=_cli_environment(product_root, record_path),
        capture_output=True,
        check=False,
        text=True,
    )

    recorded_call = json.loads(record_path.read_text(encoding="utf-8"))
    persisted_gate = json.loads(
        config.build_root.part_a_gate_manifest_path.read_text(encoding="utf-8")
    )
    d4_manifest = json.loads(
        (config.build_root.manifests_dir / "build_run_d4.json").read_text(encoding="utf-8")
    )
    assert gate.returncode == 0
    assert build.returncode == 0
    assert recorded_call == {
        "argv": ["run", "pytest", "-q", "tests/integration/test_c7_synthetic_full_pipeline.py"],
        "cwd": str(product_root),
        "integration": "1",
    }
    assert persisted_gate["status"] == "passed"
    assert persisted_gate["skipped"] is False
    assert d4_manifest["status"] == "completed"
    d4_output = Path(d4_manifest["outputs"][0]["path"])
    handoff = json.loads(d4_output.read_text(encoding="utf-8"))
    assert d4_output.name == "d4_governance_request.json"
    assert handoff["schema_version"] == "policyos.data_forge.ukraine.d4_governance_request.v1"
    assert handoff["authority_purpose"] == "producer_governance_handoff"
    assert "governance_admissibility" in handoff["may_not_use_for"]


@pytest.mark.parametrize(
    ("returncode", "stdout", "expected_status", "expected_passed", "expected_skipped"),
    [
        (0, "1 passed, 0 skipped in 0.1s", "passed", True, False),
        (1, "1 failed, 1 skipped in 0.1s", "failed", False, True),
    ],
)
def test_ops_runner_classifies_pytest_summary_like_domain_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    returncode: int,
    stdout: str,
    expected_status: str,
    expected_passed: bool,
    expected_skipped: bool,
) -> None:
    """Ops and domain paths share the same pass, failure, and skip interpretation."""

    from tools.ops_runners.ukraine_data import validate_part_a

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False
    repo_root = _make_repository_checkout(tmp_path / "checkout")

    def recording_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(validate_part_a.subprocess, "run", recording_run)

    manifest = validate_part_a.run_part_a_gate(config.server, repo_root)

    assert manifest.status == expected_status
    assert manifest.passed is expected_passed
    assert manifest.skipped is expected_skipped


def test_ops_runner_preserves_server_only_guard_before_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The moved ops gate remains blocked outside Linux server execution."""

    from tools.ops_runners.ukraine_data import validate_part_a

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    repo_root = _make_repository_checkout(tmp_path / "checkout")
    calls: list[object] = []

    def recording_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        raise AssertionError("server-only gate must reject before starting subprocess")

    monkeypatch.setattr(server.sys, "platform", "darwin")
    monkeypatch.setattr(server.shutil, "which", lambda _: "/usr/bin/python")
    monkeypatch.setattr(validate_part_a.subprocess, "run", recording_run)

    with pytest.raises(server.LocalExecutionBlockedError, match="Server-only command blocked"):
        validate_part_a.run_part_a_gate(config.server, repo_root)

    assert calls == []


def test_part_a_gate_reports_typed_unavailable_without_checkout(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An installed layout without a repository gate is unavailable, not a false pass."""

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False
    installed_root = tmp_path / "installed-wheel"
    installed_root.mkdir()
    calls: list[object] = []

    def recording_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0] if args else [], 0, stdout="", stderr="")

    monkeypatch.setattr(server.subprocess, "run", recording_run)

    manifest = server.run_part_a_gate(config.server, installed_root)

    assert manifest.server_only is True
    assert manifest.status == "unavailable"
    assert manifest.passed is False
    assert manifest.skipped is False
    assert manifest.command == []
    assert calls == []
    assert manifest.notes
    assert "checkout" in " ".join(manifest.notes).lower()


def test_part_a_gate_missing_workspace_is_unavailable_before_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A missing workspace fails closed without touching the subprocess seam."""

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    calls: list[object] = []

    def recording_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        raise AssertionError("missing workspace must not start the repository gate")

    monkeypatch.setattr(server.subprocess, "run", recording_run)

    manifest = server.run_part_a_gate(config.server, None)

    assert manifest.server_only is True
    assert manifest.status == "unavailable"
    assert manifest.passed is False
    assert manifest.skipped is False
    assert manifest.command == []
    assert calls == []


def test_ops_runner_composes_domain_orchestrator_with_gate_callback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The ops entry invokes its callback through the domain orchestrator."""

    from tools.ops_runners.ukraine_data import validate_part_a

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False
    workspace_root = _make_repository_checkout(tmp_path / "checkout")
    captured: dict[str, object] = {}

    def recording_gate(config: object, workspace_root: Path | None) -> PartAGateManifest:
        captured["config"] = config
        captured["workspace_root"] = workspace_root
        return PartAGateManifest(status="passed", server_only=True, passed=True)

    monkeypatch.setattr(validate_part_a, "_run_repository_gate", recording_gate)
    orchestrator = validate_part_a.build_orchestrator(config, workspace_root)
    summary = orchestrator.validate_part_a()

    assert orchestrator.part_a_gate_runner is validate_part_a.run_part_a_gate
    assert summary.status == "passed"
    assert captured["config"] is config.server
    assert captured["workspace_root"] == workspace_root


def test_ops_bootstrap_composes_domain_orchestrator_with_renderer_callback(
    tmp_path: Path,
) -> None:
    """The ops bootstrap entry uses the domain renderer callback seam."""

    from tools.ops_runners.ukraine_data import server_bootstrap

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    orchestrator = server_bootstrap.build_orchestrator(config, tmp_path / "checkout")

    assert orchestrator.bootstrap_script_renderer is server_bootstrap.render_bootstrap_script
    assert orchestrator.server_capability_probe is server_bootstrap.probe_local_server_capabilities

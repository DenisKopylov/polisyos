from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.data_forge.domains.ukraine import cli, server
from polisyos.data_forge.domains.ukraine.models import build_default_pipeline_config
from polisyos.data_forge.domains.ukraine.orchestrator import UkraineDataOrchestrator


def test_orchestrator_default_workspace_root_is_product_root_not_source_package(
    tmp_path: Path,
) -> None:
    """The default repository context must be the product root, not ``src/polisyos``."""

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    orchestrator = UkraineDataOrchestrator(config)

    expected_product_root = Path(__file__).resolve().parents[3]
    assert orchestrator.repo_root == expected_product_root
    assert orchestrator.repo_root != expected_product_root / "src" / "polisyos"


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
        (0, "1 skipped", "skipped", False, True),
        (1, "1 failed", "failed", False, False),
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
    repo_root = tmp_path / "checkout"
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

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from polisyos.data_forge.domains.ukraine import cli, server
from polisyos.data_forge.domains.ukraine.manifests import (
    PartAGateExecutionReceipt,
    PartAGateManifest,
    PytestCasePhaseReport,
)
from polisyos.data_forge.domains.ukraine.models import build_default_pipeline_config
from polisyos.data_forge.domains.ukraine.orchestrator import UkraineDataOrchestrator
from tools.lib.timing import (
    PYTEST_WORKLOAD_PREDICATE_PROVENANCE,
    PYTEST_WORKLOAD_SCHEMA_VERSION,
    pytest_node_map_digest,
)


def _passing_gate_manifest() -> PartAGateManifest:
    node_id = "tests/integration/test_c7_synthetic_full_pipeline.py::test_case"
    receipt = PartAGateExecutionReceipt(
        attempt_id="b" * 32,
        test_path="tests/integration/test_c7_synthetic_full_pipeline.py",
        source_sha256="sha256:" + "0" * 64,
        pytest_version="9.0.0",
        config_path="pytest.ini",
        config_sha256="sha256:" + "1" * 64,
        node_ids=[node_id],
        phase_reports=[
            PytestCasePhaseReport(node_id=node_id, when=phase, outcome="passed")
            for phase in ("setup", "call", "teardown")
        ],
        pytest_exit_status=0,
        workload_receipt_sha256="sha256:" + "2" * 64,
        phases_receipt_sha256="sha256:" + "3" * 64,
    )
    return PartAGateManifest(
        status="passed",
        passed=True,
        execution_receipt=receipt,
    )


def _write_synthetic_execution_receipts(call: dict[str, object]) -> None:
    """Write a typed fixture matching the runner's unique per-attempt paths."""

    environment = cast("dict[str, str]", call["env"])
    workspace = cast("Path", call["cwd"])
    attempt_id = environment["POLISYOS_PYTEST_RECEIPT_ATTEMPT_ID"]
    workload_path = Path(environment["POLISYOS_PYTEST_RECEIPT_SIDECAR"])
    phases_path = Path(environment["POLISYOS_PYTEST_RECEIPT_PHASES_SIDECAR"])
    test_path = "tests/integration/test_c7_synthetic_full_pipeline.py"
    node_ids = {test_path: [f"{test_path}::test_case"]}
    source_bytes = (workspace / test_path).read_bytes()
    source_digest = "sha256:" + hashlib.sha256(source_bytes).hexdigest()
    config_path = "pytest.ini"
    config_bytes = (workspace / config_path).read_bytes()
    config_digest = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
    workload = {
        "attempt_id": attempt_id,
        "node_ids_by_path": node_ids,
        "workload_identity": {
            "schema_version": PYTEST_WORKLOAD_SCHEMA_VERSION,
            "predicate_provenance": PYTEST_WORKLOAD_PREDICATE_PROVENANCE,
            "test_paths": [test_path],
            "source_digests": {test_path: source_digest},
            "pytest_version": pytest.__version__,
            "config_path": config_path,
            "config_digest": config_digest,
            "node_map_digest": pytest_node_map_digest(node_ids),
        },
    }
    workload_bytes = (json.dumps(workload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    workload_path.write_bytes(workload_bytes)
    phases = {
        "schema_version": "policyos.timing.pytest_case_phases.v1",
        "attempt_id": attempt_id,
        "workload_receipt_sha256": "sha256:" + hashlib.sha256(workload_bytes).hexdigest(),
        "pytest_exit_status": 0,
        "phase_reports": [
            {"node_id": next(iter(node_ids[test_path])), "when": phase, "outcome": "passed"}
            for phase in ("setup", "call", "teardown")
        ],
    }
    phases_path.write_text(
        json.dumps(phases, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _make_repository_checkout(root: Path) -> Path:
    """Create only the structural inputs needed for the repository gate."""

    (root / "src" / "polisyos").mkdir(parents=True)
    (root / "tests" / "integration").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
    (root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (root / "tests" / "integration" / "test_c7_synthetic_full_pipeline.py").write_text(
        "def test_case():\n    assert True\n", encoding="utf-8"
    )
    return root


def test_orchestrator_default_workspace_root_is_unset(
    tmp_path: Path,
) -> None:
    """The domain orchestrator does not infer repository context from its module path."""

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    orchestrator = UkraineDataOrchestrator(config)

    assert orchestrator.repo_root is None
    assert orchestrator.workspace_root is None


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

    monkeypatch.setattr(cli, "_emit", lambda payload: captured.update(emitted=payload))

    def factory(config: object, workspace_root: Path | None) -> _CapturingOrchestrator:
        orchestrator = _CapturingOrchestrator(config, workspace_root=workspace_root)
        return orchestrator

    result = cli.main(
        [
            "--root",
            str(build_root),
            "--workspace-root",
            str(workspace_root),
            "validate-part-a",
        ],
        orchestrator_factory=factory,
    )

    assert result == 1
    assert captured["build_root"] == build_root
    forwarded_workspace = captured.get("workspace_root")
    if forwarded_workspace is None:
        forwarded_workspace = captured.get("repo_root")
    assert forwarded_workspace == workspace_root


@pytest.mark.parametrize(
    ("returncode", "stdout"),
    [(0, "1 passed"), (0, "1 skipped"), (1, "1 failed")],
)
def test_part_a_gate_requires_structured_execution_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    returncode: int,
    stdout: str,
) -> None:
    """Console summaries and exit codes cannot substitute for C7 execution evidence."""

    from tools.ops_runners.ukraine_data import validate_part_a

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False
    repo_root = _make_repository_checkout(tmp_path / "checkout")
    calls: list[dict[str, object]] = []

    def recording_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"command": list(command), **kwargs})
        return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(validate_part_a.subprocess, "run", recording_run)

    manifest = validate_part_a.run_part_a_gate(config.server, repo_root)

    assert len(calls) == 1
    assert manifest.server_only is True
    call = calls[0]
    assert call["command"] == [
        "uv",
        "run",
        "pytest",
        "-q",
        "-p",
        "tools.quality.testing.pytest_workload_receipt",
        "tests/integration/test_c7_synthetic_full_pipeline.py",
    ]
    assert call["cwd"] == repo_root
    assert call["capture_output"] is True
    assert call["text"] is True
    assert call["check"] is False
    assert call["env"]["POLISYOS_RUN_INTEGRATION"] == "1"  # type: ignore[index]
    assert call["env"]["POLISYOS_PYTEST_RECEIPT_PHASES_SIDECAR"]  # type: ignore[index]
    assert call["env"] is not os.environ
    assert manifest.command == call["command"]
    assert manifest.status == "failed"
    assert manifest.passed is False
    assert manifest.skipped is False
    assert manifest.execution_receipt is None


def test_part_a_gate_reports_typed_unavailable_without_checkout(
    tmp_path: Path,
) -> None:
    """An installed layout without a repository gate is unavailable, not a false pass."""

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False
    installed_root = tmp_path / "installed-wheel"
    installed_root.mkdir()
    manifest = server.run_part_a_gate(config.server, installed_root)

    assert manifest.server_only is True
    assert manifest.status == "unavailable"
    assert manifest.passed is False
    assert manifest.skipped is False
    assert manifest.command == []
    assert manifest.notes
    assert "checkout" in " ".join(manifest.notes).lower()


def test_domain_gate_with_checkout_but_without_ops_runner_is_unavailable(
    tmp_path: Path,
) -> None:
    """A valid checkout does not make the domain itself a process launcher."""

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False
    repo_root = _make_repository_checkout(tmp_path / "checkout")

    manifest = server.run_part_a_gate(config.server, repo_root)

    assert manifest.status == "unavailable"
    assert manifest.command == []
    assert manifest.passed is False
    assert "ops" in " ".join(manifest.notes).lower()


def test_part_a_gate_missing_workspace_is_unavailable_before_subprocess(
    tmp_path: Path,
) -> None:
    """A missing workspace fails closed without touching the subprocess seam."""

    config = build_default_pipeline_config(root=tmp_path / "artifacts")

    manifest = server.run_part_a_gate(config.server, None)

    assert manifest.server_only is True
    assert manifest.status == "unavailable"
    assert manifest.passed is False
    assert manifest.skipped is False
    assert manifest.command == []


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
        return _passing_gate_manifest()

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
    from tools.ops_runners.ukraine_data.validate_part_a import run_part_a_gate

    assert orchestrator.part_a_gate_runner is run_part_a_gate


def test_console_cli_composes_ops_runner_for_part_a_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The installed console route injects Ops at the composition boundary."""

    from tools.ops_runners import ukraine_data_cli
    from tools.ops_runners.ukraine_data import validate_part_a

    config = build_default_pipeline_config(root=tmp_path / "artifacts")
    config.server.require_server_for_build = False
    config_path = tmp_path / "config.json"
    config_path.write_text(config.model_dump_json(), encoding="utf-8")
    workspace_root = _make_repository_checkout(tmp_path / "checkout")
    calls: list[dict[str, object]] = []

    def recording_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append({"command": list(command), **kwargs})
        _write_synthetic_execution_receipts(calls[-1])
        return subprocess.CompletedProcess(command, 0, stdout="3 passed", stderr="")

    monkeypatch.setattr(validate_part_a.subprocess, "run", recording_run)
    result = ukraine_data_cli.main(
        [
            "--config",
            str(config_path),
            "--workspace-root",
            str(workspace_root),
            "validate-part-a",
        ]
    )

    assert result == 0
    assert len(calls) == 1
    assert calls[0]["command"] == [
        "uv",
        "run",
        "pytest",
        "-q",
        "-p",
        "tools.quality.testing.pytest_workload_receipt",
        "tests/integration/test_c7_synthetic_full_pipeline.py",
    ]
    assert calls[0]["cwd"] == workspace_root
    assert calls[0]["env"]["POLISYOS_RUN_INTEGRATION"] == "1"  # type: ignore[index]
    assert calls[0]["check"] is False

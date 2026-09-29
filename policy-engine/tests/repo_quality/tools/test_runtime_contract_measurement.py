"""Runtime contract CLI distinguishes unavailable checks from measured drift."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.ops_runners.runtime import check_runtime_api_contract as gate


def test_skipped_client_check_is_named_in_clean_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["check-runtime-api-contract", "--skip-client-drift"])
    monkeypatch.setattr(gate, "_check_openapi_drift", lambda **kwargs: [])

    def forbidden_client(**kwargs):
        raise AssertionError("client check was explicitly skipped")

    monkeypatch.setattr(gate, "_check_runtime_client_family_drift", forbidden_client)
    assert gate.main() == 0
    output = capsys.readouterr().out
    assert "client freshness explicitly omitted" in output
    assert "Not measured:" in output


def test_missing_openapi_comparator_is_unrun(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys, "argv", ["check-runtime-api-contract", "--openapi", str(tmp_path / "missing.json")]
    )
    assert gate.main() == 2
    assert "UNRUN" in capsys.readouterr().out


def test_failed_client_process_retains_prior_findings_as_partial(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(sys, "argv", ["check-runtime-api-contract"])
    monkeypatch.setattr(gate, "_check_openapi_drift", lambda **kwargs: ["OpenAPI drift witness"])

    def failed_generator(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            7,
            stdout="generator stdout detail",
            stderr="generator stderr detail",
        )

    monkeypatch.setattr(gate.subprocess, "run", failed_generator)
    assert gate.main() == 2
    output = capsys.readouterr().out
    assert "UNRUN" in output
    assert "return code 7" in output
    assert "generator stderr detail" in output
    assert "partial coverage: OpenAPI drift witness" in output


def _install_successful_generator(monkeypatch, *, byte_drift: bool = False) -> None:
    generated_outputs = (
        "packages/runtime-api-client/types.ts",
        "packages/runtime-api-client/canonicalRuntimeApiClient.ts",
        "packages/runtime-api-client/canonicalRuntimeApiClient.js",
    )

    def successful_generator(command, **kwargs):
        output_root = Path(command[command.index("--output-root") + 1])
        repo_root = Path(kwargs["cwd"])
        for relative in generated_outputs:
            destination = output_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            committed = repo_root / relative
            content = committed.read_bytes()
            if byte_drift and relative.endswith("types.ts"):
                content += b"// generated mismatch\n"
            destination.write_bytes(content)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(gate.subprocess, "run", successful_generator)


def test_matching_client_family_passes(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["check-runtime-api-contract"])
    monkeypatch.setattr(gate, "_check_openapi_drift", lambda **kwargs: [])
    _install_successful_generator(monkeypatch)

    assert gate.main() == 0
    output = capsys.readouterr().out
    assert "Runtime API contract check passed" in output


def test_client_family_byte_drift_is_measured_as_failed(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["check-runtime-api-contract"])
    monkeypatch.setattr(gate, "_check_openapi_drift", lambda **kwargs: [])
    _install_successful_generator(monkeypatch, byte_drift=True)

    assert gate.main() == 1
    output = capsys.readouterr().out
    assert "Runtime API contract check FAILED" in output
    assert "Runtime API client drift detected: packages/runtime-api-client/types.ts" in output

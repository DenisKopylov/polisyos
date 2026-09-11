"""Runtime contract CLI distinguishes unavailable checks from measured drift."""

from __future__ import annotations

import subprocess
import sys

from tools.ops_runners.runtime import check_runtime_api_contract as gate


def test_skipped_client_check_is_named_in_clean_output(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["check-runtime-api-contract", "--skip-client-drift"])
    monkeypatch.setattr(gate, "_check_openapi_drift", lambda **kwargs: [])

    def forbidden_client(**kwargs):
        raise AssertionError("client check was explicitly skipped")

    monkeypatch.setattr(gate, "_check_runtime_client_drift", forbidden_client)
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


def test_failed_client_process_retains_prior_findings_as_partial(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["check-runtime-api-contract"])
    monkeypatch.setattr(gate, "_check_openapi_drift", lambda **kwargs: ["OpenAPI drift witness"])

    def failed_client(**kwargs):
        subprocess.run([sys.executable, "-c", "raise SystemExit(7)"], check=True)
        return []

    monkeypatch.setattr(gate, "_check_runtime_client_drift", failed_client)
    assert gate.main() == 2
    output = capsys.readouterr().out
    assert "UNRUN" in output
    assert "partial coverage: OpenAPI drift witness" in output

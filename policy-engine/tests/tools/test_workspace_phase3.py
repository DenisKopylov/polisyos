from __future__ import annotations

from pathlib import Path

import pytest

from tools.devx.workspace import bootstrap, doctor, verify
from tools.devx.workspace._common import CommandSpec


def test_bootstrap_builds_expected_command_sequence(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(bootstrap, "_ensure_python_baseline", lambda: None)
    monkeypatch.setattr(bootstrap, "_ensure_uv_available", lambda *, allow_install: None)
    monkeypatch.setattr(bootstrap, "_ensure_node_baseline", lambda *, skip_frontend: None)
    monkeypatch.setattr(bootstrap, "uv_command", lambda: ("uv",))
    monkeypatch.setattr(bootstrap, "run_command", lambda spec: seen.append(spec))

    exit_code = bootstrap.main([])

    assert exit_code == 0
    assert [spec.label for spec in seen] == [
        "uv sync",
        "pre-commit install",
        "npm ci",
        "Playwright browser install",
        "doctor",
    ]


def test_doctor_lists_optional_surfaces(capsys) -> None:
    exit_code = doctor.main(["--list-surfaces"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "runtime-signing" in captured.out


def test_doctor_fails_for_missing_optional_surface_credentials(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    monkeypatch.setattr(doctor, "_check_python", lambda: doctor.CheckResult("python", True, "ok"))
    monkeypatch.setattr(doctor, "_check_node", lambda: doctor.CheckResult("node", True, "ok"))
    monkeypatch.setattr(doctor, "_check_uv", lambda: doctor.CheckResult("uv", True, "ok"))

    exit_code = doctor.main(
        [
            "--surface",
            "runtime-signing",
            "--skip-playwright",
            "--skip-lockfile-checks",
            "--skip-contract-checks",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "[FAIL] runtime-signing:" in captured.out


def test_verify_rejects_invalid_pytest_worker_setting() -> None:
    with pytest.raises(SystemExit, match="positive integer or 'auto'"):
        verify._resolve_pytest_workers("0")


def test_verify_backend_only_runs_backend_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[CommandSpec] = []

    monkeypatch.setattr(verify, "uv_command", lambda: ("uv",))
    monkeypatch.setattr(verify, "run_command", lambda spec: seen.append(spec))

    exit_code = verify.main(
        [
            "--backend-only",
            "--skip-doctor",
            "--pytest-workers",
            "2",
        ]
    )

    labels = [spec.label for spec in seen]
    assert exit_code == 0
    assert any(label.startswith("pytest fast backend gate") for label in labels)
    assert all(not label.startswith("npm ") for label in labels)

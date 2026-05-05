from __future__ import annotations

import importlib

workspace_common = importlib.import_module("tools.devx.workspace._common")
workspace_doctor = importlib.import_module("tools.devx.workspace.doctor")
workspace_verify = importlib.import_module("tools.devx.workspace.verify")


def test_workspace_baseline_helpers_pin_supported_versions() -> None:
    assert workspace_common.python_baseline_matches((3, 14, 0))
    assert not workspace_common.python_baseline_matches((3, 13, 9))
    assert workspace_common.node_baseline_matches("v22.14.0")
    assert not workspace_common.node_baseline_matches("v23.0.0")


def test_workspace_surface_status_accepts_alternative_signing_envs() -> None:
    ok, message = workspace_common.surface_status(
        "runtime-signing",
        environ={"POLISYOS_SIGNING_KEY_FILE": "/tmp/polisyos-signing.pem"},
    )

    assert ok
    assert "POLISYOS_SIGNING_KEY_FILE" in message


def test_workspace_surface_status_reports_missing_frontend_sentry_build_envs() -> None:
    ok, message = workspace_common.surface_status("frontend-sentry-build", environ={})

    assert not ok
    assert "SENTRY_AUTH_TOKEN" in message
    assert "SENTRY_ORG" in message
    assert "SENTRY_PROJECT" in message


def test_workspace_doctor_lists_known_optional_surfaces(capsys) -> None:
    code = workspace_doctor.main(["--list-surfaces"])
    out = capsys.readouterr().out

    assert code == 0
    assert "llm-openai" in out
    assert "runtime-signing" in out
    assert "frontend-sentry-build" in out


def test_workspace_verify_uses_parallel_non_benchmark_slice_when_requested() -> None:
    commands = workspace_verify._build_backend_pytest_commands(
        pytest_workers="auto",
        pytest_dist="worksteal",
        xdist_available=True,
    )

    assert len(commands) == 2
    assert commands[0].label == "pytest fast backend gate (parallel non-benchmark)"
    assert "-n" in commands[0].argv
    assert "auto" in commands[0].argv
    assert "not integration and not benchmark" in commands[0].argv
    assert commands[0].env is not None
    assert commands[0].env["OMP_NUM_THREADS"] == "1"
    assert commands[1].label == "pytest fast backend benchmarks"
    assert "benchmark and not integration" in commands[1].argv
    assert "-n" not in commands[1].argv
    assert commands[1].env is not None
    assert commands[1].env["OPENBLAS_NUM_THREADS"] == "1"


def test_workspace_verify_keeps_single_serial_pytest_when_parallelism_disabled() -> None:
    commands = workspace_verify._build_backend_pytest_commands(
        pytest_workers=None,
        pytest_dist="worksteal",
        xdist_available=True,
    )

    assert len(commands) == 1
    assert commands[0].label == "pytest fast backend gate"
    assert commands[0].argv[-3:] == ("-m", "not integration", "--ignore=tests/unit/runtime/http")
    assert commands[0].env is not None
    assert commands[0].env["MKL_NUM_THREADS"] == "1"

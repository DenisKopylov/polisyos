from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module(module_name: str, relative_path: str):
    path = Path(__file__).resolve().parents[3] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


workspace_common = _load_module("_common", "tools/workspace/_common.py")
workspace_doctor = _load_module("workspace_doctor_test", "tools/workspace/doctor.py")


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

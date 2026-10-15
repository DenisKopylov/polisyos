from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest


@pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="requires an installed Linux wheel"
)
def test_installed_wheel_without_checkout_reports_gate_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An installed console consumer fails closed without a source checkout."""

    orchestrator = importlib.import_module("polisyos.data_forge.domains.ukraine.orchestrator")
    server = importlib.import_module("polisyos.data_forge.domains.ukraine.server")
    installed_origin = Path(orchestrator.__file__).resolve()
    installed_prefix = Path(sysconfig.get_path("purelib")).resolve()
    assert installed_origin.is_relative_to(installed_prefix)

    fake_root = tmp_path / "marker-shaped-environment"
    fake_module = (
        fake_root
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
        / "polisyos"
        / "data_forge"
        / "domains"
        / "ukraine"
        / "orchestrator.py"
    )
    fake_module.parent.mkdir(parents=True)
    fake_module.write_text("# installed module origin fixture\n", encoding="utf-8")
    (fake_root / "pyproject.toml").write_text("[project]\nname = 'fake-parent'\n", encoding="utf-8")
    (fake_root / "src" / "polisyos").mkdir(parents=True)
    fake_c7 = fake_root / "tests" / "integration" / "test_c7_synthetic_full_pipeline.py"
    fake_c7.parent.mkdir(parents=True)
    fake_c7.write_text("# marker only\n", encoding="utf-8")

    monkeypatch.setattr(orchestrator, "__file__", str(fake_module))
    assert server.is_repository_checkout(fake_root) is True
    assert orchestrator.UkraineDataOrchestrator().workspace_root is None
    fake_c7.unlink()
    assert server.is_repository_checkout(fake_root) is False
    assert orchestrator.UkraineDataOrchestrator().workspace_root is None

    scripts = Path(sysconfig.get_path("scripts"))
    entrypoint = scripts / "ukraine-data"
    assert entrypoint.is_file()
    sentinel_dir = tmp_path / "sentinel-bin"
    sentinel_dir.mkdir()
    sentinel_call = tmp_path / "uv-called"
    uv = sentinel_dir / "uv"
    uv.write_text(
        '#!/bin/sh\nprintf called > "$POLISYOS_UV_SENTINEL"\nexit 97\n',
        encoding="utf-8",
    )
    uv.chmod(0o755)
    workdir = tmp_path / "outside-checkout"
    workdir.mkdir()
    build_root = tmp_path / "ukraine-output"
    env = {
        "PATH": os.pathsep.join((str(sentinel_dir), str(scripts), "/usr/bin", "/bin")),
        "HOME": str(tmp_path),
        "POLISYOS_SERVER_EXECUTION": "1",
        "POLISYOS_UV_SENTINEL": str(sentinel_call),
    }
    result = subprocess.run(
        [str(entrypoint), "--root", str(build_root), "validate-part-a"],
        cwd=workdir,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    run_manifest = json.loads(result.stdout)
    gate_path = build_root / "manifests" / "part_a_gate_manifest.json"
    gate_manifest = json.loads(gate_path.read_text(encoding="utf-8"))
    assert run_manifest["status"] == "unavailable"
    assert run_manifest["errors"] == ["part_a_gate_status=unavailable"]
    assert run_manifest["metrics"]["passed"] is False
    assert run_manifest["metrics"]["skipped"] is False
    assert gate_manifest["status"] == "unavailable"
    assert gate_manifest["command"] == []
    assert gate_manifest["passed"] is False
    assert gate_manifest["skipped"] is False
    assert "checkout is unavailable" in " ".join(gate_manifest["notes"]).lower()
    assert not sentinel_call.exists()

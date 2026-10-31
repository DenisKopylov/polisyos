from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from polisyos.data_forge.domains.ukraine.models import build_default_pipeline_config


def _product_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _cold_environment(product_root: Path, path: Path) -> dict[str, str]:
    environment = {
        "PATH": str(path),
        "PYTHONPATH": os.pathsep.join((str(product_root / "src"), str(product_root))),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    for name in ("HOME", "TMPDIR", "TEMP", "TMP"):
        value = os.environ.get(name)
        if value:
            environment[name] = value
    return environment


def test_cold_ops_cli_composes_server_bootstrap_and_persists_outputs(
    tmp_path: Path,
) -> None:
    product_root = _product_root()
    workdir = tmp_path / "workspace"
    workdir.mkdir()
    artifact_root = tmp_path / "artifacts"
    storage_root = tmp_path / "server-storage"
    storage_root.mkdir()
    config_path = tmp_path / "pipeline.json"
    config = build_default_pipeline_config(root=artifact_root)
    config.server.require_server_for_build = False
    config.server.storage_root = storage_root
    config.server.workdir = workdir
    config.server.python_bin = sys.executable
    config_path.write_text(config.model_dump_json(indent=2), encoding="utf-8")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    uv_called = tmp_path / "uv-called"
    uv = fake_bin / "uv"
    uv.write_text(
        f"#!/bin/sh\nprintf called > {shlex.quote(str(uv_called))}\nexit 97\n",
        encoding="utf-8",
    )
    uv.chmod(0o755)
    environment = _cold_environment(product_root, fake_bin)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.ops_runners.ukraine_data_cli",
            "--config",
            str(config_path),
            "--root",
            str(artifact_root),
            "--workspace-root",
            str(workdir),
            "bootstrap-server",
            "--write-capabilities",
        ],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "completed"
    assert payload["stage_id"] == "bootstrap_server"
    persisted_manifest = json.loads(
        (artifact_root / "manifests" / "build_run_bootstrap_server.json").read_text(
            encoding="utf-8"
        )
    )
    assert persisted_manifest == payload
    output_paths = {Path(item["path"]) for item in payload["outputs"]}
    bootstrap_path = artifact_root / "logs" / "bootstrap_server.sh"
    capability_path = artifact_root / "manifests" / "server_capability_manifest.json"
    assert storage_root / "env.sh" in output_paths
    assert bootstrap_path in output_paths
    assert capability_path in output_paths
    assert "uv run ukraine-data bootstrap-server --write-capabilities" in (
        bootstrap_path.read_text(encoding="utf-8")
    )
    assert f"cd {workdir}" in bootstrap_path.read_text(encoding="utf-8")
    assert not uv_called.exists()


def test_cold_domain_cli_refuses_to_run_without_ops_factory(tmp_path: Path) -> None:
    product_root = _product_root()
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    artifact_root = tmp_path / "artifacts"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from polisyos.data_forge.domains.ukraine.cli import main; "
            "main(['--root', "
            f"{str(artifact_root)!r}, "
            "'validate-part-a'])",
        ],
        cwd=tmp_path,
        env=_cold_environment(product_root, fake_bin),
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode != 0
    assert "Ukraine CLI requires an Ops composition factory." in result.stderr
    assert not artifact_root.exists()

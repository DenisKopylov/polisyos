"""Run the real client generators against copied inputs with hostile ambient tools."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("script", "output"),
    [
        (
            "packages/runtime-api-client/scripts/generate-runtime-api-client.sh",
            "packages/runtime-api-client/types.ts",
        ),
        (
            "apps/runtime-dashboard/scripts/generate-api-client.sh",
            "apps/runtime-dashboard/src/api/types.ts",
        ),
    ],
)
def test_real_client_generator_binds_copied_input_and_locked_tools_from_two_directories(
    tmp_path: Path,
    script: str,
    output: str,
) -> None:
    """Ambient pnpm/npx and caller OpenAPI bytes cannot substitute for the station."""
    source = tmp_path / "source"
    relatives = [
        "package.json",
        "pnpm-workspace.yaml",
        "pnpm-lock.yaml",
        "apps/runtime-dashboard/package.json",
        "packages/runtime-api-client/package.json",
        "packages/runtime-api-client/scripts/generate-runtime-api-client.sh",
        "packages/runtime-api-client/scripts/normalize-recursive-openapi-types.mjs",
        "packages/runtime-api-client/scripts/canonicalize-runtime-client.mjs",
        "apps/runtime-dashboard/scripts/generate-api-client.sh",
        "tools/ops_runners/runtime/generate_runtime_client.py",
    ]
    for relative in relatives:
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    for relative in [
        "node_modules",
        "apps/runtime-dashboard/node_modules",
        "packages/runtime-api-client/node_modules",
    ]:
        dependency = ROOT / relative
        assert dependency.is_dir(), f"UNRUN: frozen pnpm install required: {dependency}"
        (source / relative).symlink_to(dependency, target_is_directory=True)
    (source / ".venv/bin").mkdir(parents=True)
    (source / ".venv/bin/python").symlink_to(sys.executable)
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Copied station", "version": "1"},
        "paths": {},
        "components": {
            "schemas": {
                "CopiedStationWitness": {
                    "type": "object",
                    "properties": {"copied_input": {"type": "string"}},
                }
            }
        },
    }
    (source / "schemas").mkdir()
    (source / "schemas/runtime_api_v1.openapi.json").write_text(json.dumps(spec))
    ambient = tmp_path / "ambient"
    (ambient / "schemas").mkdir(parents=True)
    (ambient / "schemas/runtime_api_v1.openapi.json").write_text("ambient-wrong-input")
    poison = tmp_path / "bin"
    poison.mkdir()
    for executable in ("npx", "pnpm"):
        path = poison / executable
        path.write_text("#!/bin/sh\necho 'ambient-tool-substitution' >&2\nexit 73\n")
        path.chmod(0o755)
    env = {**os.environ, "PATH": f"{poison}{os.pathsep}{os.environ['PATH']}"}
    out = tmp_path / "generated"
    command = ["bash", str(source / script), "--output-root", str(out)]
    observed: list[dict[str, bytes]] = []
    for cwd in (source, ambient):
        if out.exists():
            shutil.rmtree(out)
        result = subprocess.run(
            command, cwd=cwd, env=env, text=True, capture_output=True, check=False, timeout=120
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "CopiedStationWitness" in (out / output).read_text()
        observed.append(
            {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
        )
    assert observed[0] == observed[1]

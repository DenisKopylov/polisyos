"""Check that the GCP source archive closes over native Hatch wheel assets."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tomllib
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[3]


def test_gcp_archive_contains_exact_hatch_force_include_sources(tmp_path):
    workspace = tmp_path / "workspace"
    product = workspace / "policy-engine"
    (product / "ops/cloud/gcp").mkdir(parents=True)
    shutil.copyfile(
        PRODUCT / "ops/cloud/gcp/package_repo.sh",
        product / "ops/cloud/gcp/package_repo.sh",
    )
    for name in ["README.md", "pyproject.toml", "uv.lock"]:
        (product / name).write_text("fixture\n")
    shutil.copyfile(PRODUCT / "hatch.toml", product / "hatch.toml")
    (product / "src").mkdir()
    (product / "tools").mkdir()
    (product / "schemas").mkdir()

    config = tomllib.loads((product / "hatch.toml").read_text())
    forced_sources = config["build"]["targets"]["wheel"]["force-include"]
    expected = {}
    for source in forced_sources:
        asset = product / source
        asset.parent.mkdir(parents=True, exist_ok=True)
        content = f"source bytes for {source}\n".encode()
        asset.write_bytes(content)
        expected[f"policy-engine/{source}"] = content
    unlisted = product / "data/dataset_catalog/unlisted.yaml"
    unlisted.write_text("not declared by Hatch\n")

    output = workspace / "archives"
    result = subprocess.run(
        ["bash", str(product / "ops/cloud/gcp/package_repo.sh")],
        cwd=product,
        env={**os.environ, "OUT_DIR": str(output), "UPLOAD": "0"},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    (archive_path,) = output.glob("*.tar.gz")
    with tarfile.open(archive_path) as archive:
        members = {
            member.name: archive.extractfile(member).read()
            for member in archive.getmembers()
            if member.isfile()
        }
    assert {name: members.get(name) for name in expected} == expected
    assert "policy-engine/data/dataset_catalog/unlisted.yaml" not in members

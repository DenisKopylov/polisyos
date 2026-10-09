"""Check that the GCP source archive closes over native Hatch wheel assets."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tomllib
from pathlib import Path

import pytest

PRODUCT = Path(__file__).resolve().parents[3]


def _project_fixture(tmp_path: Path, hatch_manifest: str) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    product = workspace / "policy-engine"
    (product / "ops/cloud/gcp").mkdir(parents=True)
    shutil.copyfile(
        PRODUCT / "ops/cloud/gcp/package_repo.sh",
        product / "ops/cloud/gcp/package_repo.sh",
    )
    for name in ["README.md", "pyproject.toml", "uv.lock"]:
        (product / name).write_text("fixture\n")
    (product / "hatch.toml").write_text(hatch_manifest)
    (product / "src").mkdir()
    (product / "tools").mkdir()
    (product / "schemas").mkdir()
    return workspace, product


def _force_include_manifest(source: str, target: str) -> str:
    return f'[build.targets.wheel.force-include]\n"{source}" = "{target}"\n'


def _run_packager(product: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(product / "ops/cloud/gcp/package_repo.sh")],
        cwd=product,
        env={**os.environ, "OUT_DIR": str(output), "UPLOAD": "0"},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _archive_files(archive_path: Path) -> dict[str, bytes]:
    with tarfile.open(archive_path) as archive:
        members = {}
        for member in archive.getmembers():
            if member.isfile():
                stream = archive.extractfile(member)
                assert stream is not None
                members[member.name] = stream.read()
        return members


def test_gcp_archive_contains_exact_hatch_force_include_sources(tmp_path):
    (workspace, product) = _project_fixture(tmp_path, (PRODUCT / "hatch.toml").read_text())

    config = tomllib.loads((product / "hatch.toml").read_text())
    forced_sources = config["build"]["targets"]["wheel"]["force-include"]
    expected = {}
    for source in forced_sources:
        asset = product / source
        asset.parent.mkdir(parents=True, exist_ok=True)
        original = PRODUCT / source
        shutil.copyfile(original, asset)
        content = original.read_bytes()
        expected[f"policy-engine/{source}"] = content
    unlisted = product / "data/dataset_catalog/unlisted.yaml"
    unlisted.write_text("not declared by Hatch\n")

    output = workspace / "archives"
    result = _run_packager(product, output)
    assert result.returncode == 0, result.stdout + result.stderr
    (archive_path,) = output.glob("*.tar.gz")
    members = _archive_files(archive_path)
    assert {name: members.get(name) for name in expected} == expected
    assert "policy-engine/data/dataset_catalog/unlisted.yaml" not in members


@pytest.mark.parametrize("shape", ["inside_parent", "outside_parent", "missing", "leaf"])
def test_gcp_archive_refuses_symlinked_or_missing_source_paths(tmp_path, shape):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    if shape == "inside_parent":
        target_dir = product / "internal"
        target_dir.mkdir()
        (target_dir / "item.yaml").write_text("redirected in-root bytes\n")
        (product / "assets").symlink_to(target_dir, target_is_directory=True)
    elif shape == "outside_parent":
        target_dir = workspace / "outside"
        target_dir.mkdir()
        (target_dir / "item.yaml").write_text("redirected outside bytes\n")
        (product / "assets").symlink_to(target_dir, target_is_directory=True)
    elif shape == "leaf":
        target = product / "internal/item.yaml"
        target.parent.mkdir()
        target.write_text("redirected leaf bytes\n")
        link = product / source
        link.parent.mkdir(parents=True)
        link.symlink_to(target)

    output = workspace / "archives"
    result = _run_packager(product, output)
    assert result.returncode != 0
    assert source in result.stderr
    assert not list(output.glob("*.tar.gz"))


def test_gcp_archive_refuses_a_symlink_in_a_nested_source_component(tmp_path):
    source = "assets/region/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/region/item.yaml")
    )
    (product / "assets").mkdir()
    target_dir = product / "internal"
    target_dir.mkdir()
    (target_dir / "item.yaml").write_text("redirected in-root bytes\n")
    (product / "assets/region").symlink_to(target_dir, target_is_directory=True)

    output = workspace / "archives"
    result = _run_packager(product, output)
    assert result.returncode != 0
    assert source in result.stderr
    assert not list(output.glob("*.tar.gz"))


def test_gcp_archive_accepts_a_clean_directory_force_include(tmp_path):
    source = "bundle"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/bundle")
    )
    (product / source).mkdir()
    (product / source / "item.yaml").write_text("directory asset bytes\n")

    output = workspace / "archives"
    result = _run_packager(product, output)
    assert result.returncode == 0, result.stdout + result.stderr
    (archive_path,) = output.glob("*.tar.gz")
    members = _archive_files(archive_path)
    assert members["policy-engine/bundle/item.yaml"] == b"directory asset bytes\n"


def test_gcp_archive_refuses_symlinked_members_in_directory_force_include(tmp_path):
    source = "bundle"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/bundle")
    )
    bundle = product / source
    bundle.mkdir()
    (bundle / "item.yaml").write_text("directory asset bytes\n")
    internal = product / "internal"
    internal.mkdir()
    (internal / "secret.yaml").write_text("must not enter archive\n")
    (bundle / "redirected").symlink_to(internal, target_is_directory=True)

    output = workspace / "archives"
    result = _run_packager(product, output)
    assert result.returncode != 0
    assert source in result.stderr
    assert not list(output.glob("*.tar.gz"))


def test_gcp_archive_refuses_symlinked_fixed_source_root_before_opening_archive(tmp_path):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("manifest source remains valid\n")
    external_source_root = workspace / "external-src"
    external_source_root.mkdir()
    (external_source_root / "module.py").write_text("must not be archived\n")
    source_root = product / "src"
    source_root.rmdir()
    source_root.symlink_to(external_source_root, target_is_directory=True)

    output = workspace / "archives"
    result = _run_packager(product, output)
    assert result.returncode != 0
    assert "policy-engine/src" in result.stderr
    assert not list(output.glob("*.tar.gz"))


def test_gcp_archive_accepts_excluded_symlinks_without_archiving_them(tmp_path):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("manifest source bytes\n")
    (product / "src/kept.py").write_text("selected source\n")
    external = workspace / "external.py"
    external.write_text("excluded links target\n")
    pycache = product / "src/__pycache__"
    pycache.mkdir()
    (pycache / "compiled.pyc").symlink_to(external)
    (product / "src/excluded.pyc").symlink_to(external)

    output = workspace / "archives"
    result = _run_packager(product, output)
    assert result.returncode == 0, result.stdout + result.stderr
    (archive_path,) = output.glob("*.tar.gz")
    members = _archive_files(archive_path)
    assert members["policy-engine/src/kept.py"] == b"selected source\n"
    assert not any("__pycache__" in name or name.endswith(".pyc") for name in members)


def test_gcp_archive_refuses_special_members_before_opening_archive(tmp_path):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("manifest source bytes\n")
    os.mkfifo(product / "src/nonregular.pipe")

    output = workspace / "archives"
    result = _run_packager(product, output)
    assert result.returncode != 0
    assert "policy-engine/src/nonregular.pipe" in result.stderr
    assert not list(output.glob("*.tar.gz"))

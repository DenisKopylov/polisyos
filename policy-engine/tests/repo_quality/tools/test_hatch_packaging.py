"""Prove native Hatch discovery with real repository packages and backend artifacts."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shlex
import shutil
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest
from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder

ROOT = Path(__file__).resolve().parents[3]
# Original build contract, retained as an independent migration control.
LEGACY = """[tool.hatch.build.targets.wheel]
packages = ["src/polisyos", "tools"]

[tool.hatch.build]
directory = "_build/dist"

[tool.hatch.build.targets.sdist]
include = [
  "src/polisyos",
  "benchmarks",
  "docs",
  "ops",
  "schemas",
  "tools",
  "CHANGELOG.md",
  "README.md",
  "ruff.toml",
  "mypy.ini",
  "basedpyright.toml",
  "pytest.ini",
  "mutmut.cfg",
  "pyproject.toml",
]
"""
INCLUDES = tomllib.loads(LEGACY)["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
# Two governance documents are outside this lane's permitted content denominator.
EXCLUDED_NAMES = {"debt-register.md", "ledger.md"}


def _replace(path: Path, text: str) -> None:
    path.unlink(missing_ok=True)  # Scratch clones share immutable source inodes.
    path.write_text(text)


def _clone(source: Path, destination: Path) -> Path:
    shutil.copytree(
        source, destination, copy_function=os.link, ignore=shutil.ignore_patterns("_build")
    )
    return destination


def _wheel(root: Path) -> tuple[Path, dict[str, str]]:
    wheel = Path(next(WheelBuilder(str(root)).build(versions=["standard"])))
    with zipfile.ZipFile(wheel) as archive:
        content = {
            name: hashlib.sha256(archive.read(name)).hexdigest()
            for name in archive.namelist()
            if not name.endswith("/RECORD")
        }
    return wheel, content


def _sdist(root: Path) -> tuple[Path, dict[str, str]]:
    archive_path = Path(next(SdistBuilder(str(root)).build()))
    with tarfile.open(archive_path) as archive:
        content = {}
        for member in archive.getmembers():
            if member.isfile():
                stream = archive.extractfile(member)
                assert stream is not None
                content[member.name.split("/", 1)[1]] = hashlib.sha256(stream.read()).hexdigest()
    return archive_path, content


@pytest.fixture(scope="module")
def contexts(tmp_path_factory):
    scratch = tmp_path_factory.mktemp("hatch-contexts")
    native = scratch / "native"
    native.mkdir()
    listed = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    selected = sorted(
        {
            name
            for name in listed
            if name
            and Path(name).name.casefold() not in EXCLUDED_NAMES
            and any(
                name == prefix or name.startswith(prefix + "/")
                for prefix in [*INCLUDES, "hatch.toml"]
            )
        }
    )
    copied = []
    for name in selected:
        source = ROOT / name
        assert source.is_file(), f"missing or non-file packaging input: {name}"
        assert not source.is_symlink(), f"unresolved packaging input: {name}"
        destination = native / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied.append(name)
    legacy = _clone(native, scratch / "legacy")
    (legacy / "hatch.toml").unlink(missing_ok=True)
    metadata = (native / "pyproject.toml").read_text().split("[tool.hatch.", 1)[0]
    _replace(legacy / "pyproject.toml", metadata + LEGACY)
    print(
        json.dumps(
            {
                "backend": importlib.metadata.version("hatchling"),
                "context_paths": len(copied),
                "excluded_basenames": sorted(EXCLUDED_NAMES),
                "source_packages": ["src/polisyos", "tools"],
            },
            sort_keys=True,
        )
    )
    return native, legacy, scratch


def test_native_backend_preserves_complete_wheel_and_sdist_contract(contexts):
    native, legacy, scratch = contexts
    old_wheel, old_members = _wheel(legacy)
    old_sdist, old_sdist_members = _sdist(legacy)
    assert (native / "hatch.toml").is_file(), "native Hatch configuration is required"
    assert "hatch" not in tomllib.loads((native / "pyproject.toml").read_text()).get("tool", {})
    new_wheel, new_members = _wheel(native)
    new_sdist, new_sdist_members = _sdist(native)
    assert (
        old_wheel.parent.relative_to(legacy)
        == new_wheel.parent.relative_to(native)
        == Path("_build/dist")
    )
    assert (
        old_sdist.parent.relative_to(legacy)
        == new_sdist.parent.relative_to(native)
        == Path("_build/dist")
    )
    assert old_members == new_members  # Every member, METADATA and all entry-point groups.
    assert any(name.startswith("tools/") for name in new_members)
    old_wire = tomllib.loads((legacy / "pyproject.toml").read_text())
    new_wire = tomllib.loads((native / "pyproject.toml").read_text())
    del old_wire["tool"]["hatch"]
    assert old_wire == new_wire  # Also preserves empty extension groups and uv tables.
    assert new_sdist_members.keys() - old_sdist_members.keys() == {"hatch.toml"}
    assert not old_sdist_members.keys() - new_sdist_members.keys()
    assert {
        name for name in old_sdist_members if old_sdist_members[name] != new_sdist_members[name]
    } == {"pyproject.toml"}
    extracted = scratch / "extracted"
    with tarfile.open(new_sdist) as archive:
        archive.extractall(extracted, filter="data")
    (rebuilt_root,) = extracted.iterdir()
    _, rebuilt_members = _wheel(rebuilt_root)
    assert rebuilt_members == new_members
    print(
        json.dumps(
            {
                "wheel_members_except_record": len(new_members),
                "sdist_members": len(new_sdist_members),
                "sdist_delta": ["hatch.toml", "pyproject.toml"],
            }
        )
    )


@pytest.mark.parametrize("mutation", ["missing", "wrong_prefix", "packages", "entrypoint"])
def test_missing_or_wrong_native_config_is_detected_by_real_build(contexts, mutation):
    native, legacy, scratch = contexts
    assert (native / "hatch.toml").is_file(), "native Hatch configuration is required"
    broken = _clone(native, scratch / mutation)
    config = broken / "hatch.toml"
    if mutation == "missing":
        config.unlink()
    elif mutation == "wrong_prefix":
        _replace(config, config.read_text().replace("[build", "[tool.hatch.build"))
    elif mutation == "packages":
        _replace(
            config, config.read_text().replace('["src/polisyos", "tools"]', '["src/polisyos"]')
        )
    else:
        manifest = broken / "pyproject.toml"
        _replace(manifest, manifest.read_text().replace('polisyos-tools = "tools.cli:main"\n', ""))
    _, expected = _wheel(legacy)
    try:
        wheel, observed = _wheel(broken)
    except ValueError as error:
        assert mutation in {"missing", "wrong_prefix"}
        print(f"{mutation}: backend rejected: {error}")
    else:
        assert observed != expected or wheel.parent.relative_to(broken) != Path("_build/dist")
        print(f"{mutation}: backend artifact differs from the legacy contract")


@pytest.mark.parametrize("stage", [0, 1])
def test_docker_manifest_copy_keeps_native_build_behavior(contexts, stage):
    native, legacy, scratch = contexts
    assert (native / "hatch.toml").is_file(), "native Hatch configuration is required"
    copies = [
        shlex.split(line)[1:-1]
        for line in (ROOT / "Dockerfile.reproducible").read_text().splitlines()
        if line.casefold().startswith("copy ") and "pyproject.toml" in line.casefold()
    ]
    assert len(copies) == 2
    context = _clone(native, scratch / f"docker-{stage}")
    # Replay the explicit manifest COPY selection; existing later source COPYs
    # are supplied by the real source basis. This does not claim image health.
    if "hatch.toml" not in copies[stage]:
        (context / "hatch.toml").unlink()
    for name in copies[stage]:
        assert (ROOT / name).is_file()
    _, expected = _wheel(legacy)
    wheel, observed = _wheel(context)
    assert observed == expected
    assert wheel.parent.relative_to(context) == Path("_build/dist")


def test_gcp_archive_carries_buildable_native_config(contexts):
    native, legacy, scratch = contexts
    assert (native / "hatch.toml").is_file(), "native Hatch configuration is required"
    workspace = scratch / "cloud"
    workspace.mkdir()
    product = _clone(native, workspace / "policy-engine")
    shutil.copyfile(ROOT / "uv.lock", product / "uv.lock")
    output = workspace / "archives"
    result = subprocess.run(
        ["bash", str(product / "ops/cloud/gcp/package_repo.sh")],
        cwd=product,
        env={**os.environ, "OUT_DIR": str(output), "UPLOAD": "0"},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    (archive_path,) = output.glob("*.tar.gz")
    extracted = workspace / "extracted"
    with tarfile.open(archive_path) as archive:
        archive.extractall(extracted, filter="data")
    wheel, observed = _wheel(extracted / "policy-engine")
    _, expected = _wheel(legacy)
    assert observed == expected
    assert wheel.parent.relative_to(extracted / "policy-engine") == Path("_build/dist")


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_context_rejects_nonfile_tracked_input(tmp_path, tmp_path_factory, monkeypatch, kind):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    (source / "pyproject.toml").write_text('[project]\nname = "fixture"\nversion = "0"\n')
    declared = source / "docs/evidence.txt"
    declared.parent.mkdir()
    declared.write_text("declared evidence\n")
    subprocess.run(
        ["git", "-C", str(source), "add", "pyproject.toml", "docs/evidence.txt"],
        check=True,
    )
    declared.unlink()
    if kind == "directory":
        declared.mkdir()
    monkeypatch.setitem(globals(), "ROOT", source)
    with pytest.raises(
        AssertionError, match=r"missing or non-file packaging input: docs/evidence\.txt"
    ):
        contexts.__wrapped__(tmp_path_factory)

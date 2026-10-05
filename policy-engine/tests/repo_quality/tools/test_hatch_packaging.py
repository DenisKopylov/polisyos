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
from pathlib import Path, PurePosixPath

import pytest
from hatchling.builders.sdist import SdistBuilder
from hatchling.builders.wheel import WheelBuilder
from pathspec import GitIgnoreSpec

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
APP_PACKAGE_SOURCE_SENTINELS = {
    "apps/runtime-dashboard/src/hygiene_sdist_sentinel.py": "APP_PACKAGE_SENTINEL = 'python'\n",
    "apps/runtime-dashboard/src/hygiene_sdist_sentinel.ts": "export const APP_PACKAGE_SENTINEL = 'typescript';\n",
    "packages/atlas-ui/src/hygiene_sdist_sentinel.js": "export const APP_PACKAGE_SENTINEL = 'javascript';\n",
    "packages/atlas-ui/src/hygiene_sdist_sentinel.tsx": "export const AppPackageSentinel = () => null;\n",
}


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


def _hatch_readme_spec(root: Path) -> GitIgnoreSpec:
    selectors = _hatch_config(root)["build"]["targets"]["sdist"]["include"]
    readme_selectors = [
        selector for selector in selectors if PurePosixPath(selector).name.casefold() == "readme.md"
    ]
    assert readme_selectors, "native Hatch sdist must configure a README selector"
    return GitIgnoreSpec.from_lines(readme_selectors)


def _app_package_payload_members(content: dict[str, str], readme_spec: GitIgnoreSpec) -> list[str]:
    return sorted(
        name
        for name in content
        if name.startswith(("apps/", "packages/"))
        and not (
            PurePosixPath(name).name.casefold() == "readme.md" and readme_spec.match_file(name)
        )
    )


def _assert_no_app_package_payload_members(
    content: dict[str, str], readme_spec: GitIgnoreSpec
) -> None:
    payload_members = _app_package_payload_members(content, readme_spec)
    assert not payload_members, (
        f"sdist included non-README apps/packages payloads: {payload_members}"
    )


def _hatch_config(root: Path) -> dict:
    return tomllib.loads((root / "hatch.toml").read_text())


def _paths_selected_by(root: Path, selectors: list[str]) -> set[str]:
    include_spec = GitIgnoreSpec.from_lines(selectors)
    selected = set()
    for path in root.rglob("*"):
        if not path.is_file() or "_build" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        if include_spec.match_file(relative):
            selected.add(relative)
    return selected


def _wheel_force_include_sources(root: Path) -> dict[str, Path]:
    force_include = (
        _hatch_config(root)
        .get("build", {})
        .get("targets", {})
        .get("wheel", {})
        .get("force-include", {})
    )
    members = {}
    for source, target in force_include.items():
        source_path = root / source
        assert source_path.exists(), f"missing wheel force-include source: {source}"
        if source_path.is_file():
            members[target] = source_path
        else:
            for path in source_path.rglob("*"):
                if path.is_file():
                    relative = path.relative_to(source_path).as_posix()
                    members[f"{target.rstrip('/')}/{relative}"] = path
    return members


@pytest.fixture(scope="module")
def contexts(tmp_path_factory):
    scratch = tmp_path_factory.mktemp("hatch-contexts")
    native = scratch / "native"
    native.mkdir()
    owner_config = _hatch_config(ROOT)["build"]["targets"]
    native_sdist_include = owner_config["sdist"]["include"]
    native_wheel = owner_config["wheel"]
    native_wheel_packages = native_wheel.get("packages", [])
    native_force_include_sources = list(native_wheel.get("force-include", {}))
    input_selectors = list(
        dict.fromkeys(
            [
                *INCLUDES,
                "hatch.toml",
                *native_sdist_include,
                *native_wheel_packages,
                *native_force_include_sources,
            ]
        )
    )
    input_spec = GitIgnoreSpec.from_lines(input_selectors)
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
            and (
                input_spec.match_file(name)
                or (name.startswith(("apps/", "packages/")) and Path(name).name == "README.md")
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
    for name, contents in APP_PACKAGE_SOURCE_SENTINELS.items():
        destination = native / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(contents)
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
                "apps_packages_readmes": sorted(
                    name
                    for name in copied
                    if name.startswith(("apps/", "packages/")) and Path(name).name == "README.md"
                ),
                "apps_packages_source_sentinels": sorted(APP_PACKAGE_SOURCE_SENTINELS),
                "native_sdist_include": native_sdist_include,
                "native_wheel_packages": native_wheel_packages,
                "native_wheel_force_include_sources": sorted(native_force_include_sources),
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
    force_include_sources = _wheel_force_include_sources(native)
    assert not old_members.keys() - new_members.keys()
    assert (
        new_members.keys() - old_members.keys() == set(force_include_sources) - old_members.keys()
    )
    for target, source in force_include_sources.items():
        assert new_members[target] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert any(name.startswith("tools/") for name in new_members)
    old_wire = tomllib.loads((legacy / "pyproject.toml").read_text())
    new_wire = tomllib.loads((native / "pyproject.toml").read_text())
    del old_wire["tool"]["hatch"]
    assert old_wire == new_wire  # Also preserves empty extension groups and uv tables.
    native_sdist_include = _hatch_config(native)["build"]["targets"]["sdist"]["include"]
    expected_sdist_additions = _paths_selected_by(
        native, native_sdist_include
    ) - _paths_selected_by(legacy, INCLUDES)
    assert new_sdist_members.keys() - old_sdist_members.keys() == expected_sdist_additions
    assert not old_sdist_members.keys() - new_sdist_members.keys()
    assert expected_sdist_additions
    assert {
        name for name in old_sdist_members if old_sdist_members[name] != new_sdist_members[name]
    } == {"pyproject.toml"}
    readme_spec = _hatch_readme_spec(native)
    _assert_no_app_package_payload_members(old_sdist_members, readme_spec)
    apps_packages_readmes = {
        name
        for name in old_sdist_members
        if name.startswith(("apps/", "packages/")) and Path(name).name == "README.md"
    }
    assert "apps/README.md" in apps_packages_readmes
    assert "packages/README.md" in apps_packages_readmes
    assert apps_packages_readmes <= new_sdist_members.keys()
    _assert_no_app_package_payload_members(new_sdist_members, readme_spec)
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
                "sdist_delta": sorted(expected_sdist_additions),
            }
        )
    )


def test_native_sdist_excludes_frontend_sources_and_rejects_scope_leak_mutant(contexts):
    native, _, scratch = contexts
    readme_spec = _hatch_readme_spec(native)
    _, native_members = _sdist(native)
    _assert_no_app_package_payload_members(native_members, readme_spec)
    expected_readmes = {
        path.relative_to(native).as_posix()
        for path in native.rglob("README.md")
        if path.is_file()
        and any(
            path.relative_to(native).as_posix().startswith(f"{root}/")
            for root in ("apps", "packages")
        )
        and "_build" not in path.parts
    }
    native_readmes = {
        name
        for name in native_members
        if name.startswith(("apps/", "packages/")) and Path(name).name == "README.md"
    }
    assert expected_readmes == native_readmes
    native_payload_members = _app_package_payload_members(native_members, readme_spec)
    assert not native_payload_members

    mutant = _clone(native, scratch / "native-including-apps-packages")
    config = mutant / "hatch.toml"
    config_text = config.read_text()
    include_marker = '  "hatch.toml",\n'
    assert config_text.count(include_marker) == 1
    _replace(
        config,
        config_text.replace(
            include_marker,
            include_marker + '  "apps",\n  "packages",\n',
        ),
    )
    assert (mutant / "pyproject.toml").read_bytes() == (native / "pyproject.toml").read_bytes()
    _, mutant_members = _sdist(mutant)
    mutant_payload_members = _app_package_payload_members(mutant_members, readme_spec)
    assert set(APP_PACKAGE_SOURCE_SENTINELS) <= set(mutant_payload_members)
    with pytest.raises(AssertionError, match="non-README apps/packages payloads"):
        _assert_no_app_package_payload_members(mutant_members, readme_spec)
    print(
        json.dumps(
            {
                "native_readme_members": sorted(native_readmes),
                "native_payload_members": native_payload_members,
                "mutated_hatch_includes": ["apps", "packages"],
                "mutated_pyproject_unchanged": True,
                "mutant_payload_members": mutant_payload_members,
                "negative_control": "PASS non-README payload oracle rejected mutated native sdist",
            },
            sort_keys=True,
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
    native, _, scratch = contexts
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
    _, expected = _wheel(native)
    wheel, observed = _wheel(context)
    assert observed == expected
    assert wheel.parent.relative_to(context) == Path("_build/dist")


def test_gcp_archive_carries_buildable_native_config(contexts):
    native, _, scratch = contexts
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
    _, expected = _wheel(native)
    assert observed == expected
    assert wheel.parent.relative_to(extracted / "policy-engine") == Path("_build/dist")

    mutant_workspace = scratch / "cloud-force-include-mutant"
    mutant_workspace.mkdir()
    mutant_product = _clone(native, mutant_workspace / "policy-engine")
    shutil.copyfile(ROOT / "uv.lock", mutant_product / "uv.lock")
    probe = mutant_product / "architecture/hygiene_bundle_probe.toml"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text("bundle_probe = true\n")
    config = mutant_product / "hatch.toml"
    config_text = config.read_text()
    force_include_header = "[build.targets.wheel.force-include]\n"
    assert config_text.count(force_include_header) == 1
    _replace(
        config,
        config_text.replace(
            force_include_header,
            force_include_header
            + '"architecture/hygiene_bundle_probe.toml" = "polisyos/hygiene_bundle_probe.toml"\n',
        ),
    )
    mutant_output = mutant_workspace / "archives"
    mutant_result = subprocess.run(
        ["bash", str(mutant_product / "ops/cloud/gcp/package_repo.sh")],
        cwd=mutant_product,
        env={**os.environ, "OUT_DIR": str(mutant_output), "UPLOAD": "0"},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert mutant_result.returncode == 0, mutant_result.stdout + mutant_result.stderr
    (mutant_archive,) = mutant_output.glob("*.tar.gz")
    with tarfile.open(mutant_archive) as archive:
        bundled_probe = archive.extractfile("policy-engine/architecture/hygiene_bundle_probe.toml")
        assert bundled_probe is not None
        assert bundled_probe.read() == probe.read_bytes()
    mutant_extracted = mutant_workspace / "extracted"
    mutant_extracted.mkdir()
    with tarfile.open(mutant_archive) as archive:
        archive.extractall(mutant_extracted, filter="data")
    mutant_extracted = mutant_extracted / "policy-engine"
    _, mutant_observed = _wheel(mutant_extracted)
    mutant_force_include = _wheel_force_include_sources(mutant_extracted)
    mutant_target_sha256 = hashlib.sha256(
        mutant_force_include["polisyos/hygiene_bundle_probe.toml"].read_bytes()
    ).hexdigest()
    assert mutant_observed["polisyos/hygiene_bundle_probe.toml"] == mutant_target_sha256

    probe.unlink()
    missing_output = mutant_workspace / "missing-source-archives"
    missing_result = subprocess.run(
        ["bash", str(mutant_product / "ops/cloud/gcp/package_repo.sh")],
        cwd=mutant_product,
        env={**os.environ, "OUT_DIR": str(missing_output), "UPLOAD": "0"},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert missing_result.returncode != 0
    assert (
        "Configured Hatch wheel force-include source is missing: "
        "architecture/hygiene_bundle_probe.toml"
    ) in missing_result.stderr
    assert not list(missing_output.glob("*.tar.gz"))

    escape_config_text = config.read_text()
    source_selector = '"architecture/hygiene_bundle_probe.toml" = '
    assert escape_config_text.count(source_selector) == 1
    _replace(
        config,
        escape_config_text.replace(
            source_selector,
            '"../../hygiene_outside_probe.toml" = ',
        ),
    )
    escape_output = mutant_workspace / "escape-source-archives"
    escape_result = subprocess.run(
        ["bash", str(mutant_product / "ops/cloud/gcp/package_repo.sh")],
        cwd=mutant_product,
        env={**os.environ, "OUT_DIR": str(escape_output), "UPLOAD": "0"},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert escape_result.returncode != 0
    assert "Configured Hatch wheel force-include source escapes policy-engine" in (
        escape_result.stderr
    )
    assert not list(escape_output.glob("*.tar.gz"))
    print(
        json.dumps(
            {
                "native_bundle_archive_count": len(list(output.glob("*.tar.gz"))),
                "native_wheel_member_count": len(observed),
                "mutant_added_force_include_source": "architecture/hygiene_bundle_probe.toml",
                "mutant_archive_member": "policy-engine/architecture/hygiene_bundle_probe.toml",
                "mutant_wheel_target": "polisyos/hygiene_bundle_probe.toml",
                "mutant_wheel_target_sha256": mutant_target_sha256,
                "missing_source_control": missing_result.stderr.strip(),
                "missing_source_archive_count": len(list(missing_output.glob("*.tar.gz"))),
                "escape_source_control": escape_result.stderr.strip(),
                "escape_source_archive_count": len(list(escape_output.glob("*.tar.gz"))),
                "negative_control": "PASS missing/out-of-root configured sources rejected pre-archive",
            },
            sort_keys=True,
        )
    )


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_context_rejects_nonfile_tracked_input(tmp_path, tmp_path_factory, monkeypatch, kind):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "--quiet", str(source)], check=True)
    (source / "pyproject.toml").write_text('[project]\nname = "fixture"\nversion = "0"\n')
    (source / "hatch.toml").write_text(
        "[build.targets.wheel]\npackages = []\n\n"
        '[build.targets.sdist]\ninclude = ["docs/evidence.txt"]\n'
    )
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

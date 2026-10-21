"""Check that the GCP source archive closes over native Hatch wheel assets."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
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
    (product / "src/fixture.py").write_text("fixture source\n")
    (product / "tools").mkdir()
    (product / "tools/fixture.py").write_text("fixture tool\n")
    (product / "schemas").mkdir()
    (product / "schemas/fixture.yaml").write_text("fixture: true\n")
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(
        ["git", "config", "user.name", "GCP package fixture"],
        cwd=workspace,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "gcp-package-fixture@example.invalid"],
        cwd=workspace,
        check=True,
    )
    return workspace, product


def _force_include_manifest(source: str, target: str) -> str:
    return f'[build.targets.wheel.force-include]\n"{source}" = "{target}"\n'


def _commit_fixture(product: Path) -> None:
    subprocess.run(["git", "add", "--all"], cwd=product, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fixture source freeze"],
        cwd=product,
        check=True,
    )


def _run_packager(
    product: Path,
    output: Path,
    *,
    commit: bool = True,
    fixed_date: str | None = None,
    python_bin: Path | None = None,
    extra_env: dict[str, str] | None = None,
    caller_cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    if commit:
        _commit_fixture(product)
    env = {**os.environ, "OUT_DIR": str(output), "UPLOAD": "0"}
    if fixed_date is not None:
        fake_bin = product.parent / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        date_command = fake_bin / "date"
        date_command.write_text(f"#!/bin/sh\nprintf '%s\\n' '{fixed_date}'\n")
        date_command.chmod(0o755)
        env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    if python_bin is not None:
        env["PYTHON_BIN"] = str(python_bin)
    if extra_env is not None:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(product / "ops/cloud/gcp/package_repo.sh")],
        cwd=caller_cwd or product,
        env=env,
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


@pytest.mark.parametrize(
    "source",
    [
        "production_data/synthetic-no-secret.csv",
        "production_data/nested/synthetic-no-secret.csv",
        "PRODUCTION_DATA/nested/synthetic-no-secret.csv",
    ],
)
def test_gcp_archive_refuses_protected_production_data_force_include(tmp_path, source):
    target = "polisyos/fixture/synthetic-no-secret.csv"
    workspace, product = _project_fixture(tmp_path, _force_include_manifest(source, target))
    protected_source = product / source
    protected_source.parent.mkdir(parents=True)
    protected_source.write_text("synthetic-only protected fixture\n")

    output = workspace / "archives"
    result = _run_packager(product, output)

    assert result.returncode != 0
    assert "Refusing protected production_data force-include source" in result.stderr
    assert not list(output.glob("*.tar.gz"))


@pytest.mark.parametrize("parent_repository", [False, True])
def test_gcp_archive_requires_a_committed_git_source_tree(tmp_path, parent_repository):
    if parent_repository:
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(tmp_path),
                "-c",
                "user.name=GCP ancestor fixture",
                "-c",
                "user.email=gcp-ancestor@example.invalid",
                "commit",
                "--allow-empty",
                "-qm",
                "ancestor source freeze",
            ],
            check=True,
        )
    source = "assets/safe.yaml"
    workspace, product = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/fixture/safe.yaml")
    )
    source_path = product / source
    source_path.parent.mkdir(parents=True)
    source_path.write_text("fixture source\n")
    shutil.rmtree(workspace / ".git")

    output = workspace / "archives"
    result = _run_packager(product, output, commit=False)

    assert result.returncode != 0
    assert "GCP source archive requires a committed Git source tree" in result.stderr
    assert not output.exists()


def test_gcp_archive_ignores_replacement_refs_when_freezing_source(tmp_path):
    source = "assets/safe.yaml"
    target = "polisyos/fixture/safe.yaml"
    workspace, product = _project_fixture(tmp_path, _force_include_manifest(source, target))
    source_path = product / source
    source_path.parent.mkdir(parents=True)
    original = b"bytes from the selected commit\n"
    replacement = b"bytes from a replacement ref\n"
    source_path.write_bytes(original)
    _commit_fixture(product)
    selected_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source_path.write_bytes(replacement)
    _commit_fixture(product)
    replacement_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "checkout", "--quiet", selected_commit], cwd=workspace, check=True)
    subprocess.run(
        ["git", "replace", selected_commit, replacement_commit], cwd=workspace, check=True
    )

    output = workspace / "archives"
    result = _run_packager(product, output, commit=False)

    assert result.returncode == 0, result.stdout + result.stderr
    (archive_path,) = output.glob("*.tar.gz")
    members = _archive_files(archive_path)
    assert members[f"policy-engine/{source}"] == original
    assert replacement not in members.values()


def test_gcp_archive_still_accepts_regular_force_include_sources(tmp_path):
    source = "assets/safe.yaml"
    target = "polisyos/fixture/safe.yaml"
    expected = b"ordinary packaged resource\n"
    workspace, product = _project_fixture(tmp_path, _force_include_manifest(source, target))
    safe_source = product / source
    safe_source.parent.mkdir(parents=True)
    safe_source.write_bytes(expected)

    output = workspace / "archives"
    result = _run_packager(product, output)

    assert result.returncode == 0, result.stdout + result.stderr
    (archive_path,) = output.glob("*.tar.gz")
    assert _archive_files(archive_path)[f"policy-engine/{source}"] == expected


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
    shutil.rmtree(source_root)
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


def test_gcp_archive_excludes_distribution_named_egg_info_components(tmp_path):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("manifest source bytes\n")
    (product / "src/kept.py").write_text("selected source\n")
    literal_metadata = product / "src/.egg-info"
    distribution_metadata = product / "src/polisyos.egg-info"
    literal_metadata.mkdir()
    distribution_metadata.mkdir()
    (literal_metadata / "PKG-INFO").write_text("literal metadata\n")
    (distribution_metadata / "PKG-INFO").write_text("distribution metadata\n")

    output = workspace / "archives"
    result = _run_packager(product, output)
    assert result.returncode == 0, result.stdout + result.stderr
    (archive_path,) = output.glob("*.tar.gz")
    members = _archive_files(archive_path)
    assert members["policy-engine/src/kept.py"] == b"selected source\n"
    assert "policy-engine/src/.egg-info/PKG-INFO" not in members
    assert "policy-engine/src/polisyos.egg-info/PKG-INFO" not in members


def test_gcp_archive_does_not_include_untracked_special_members(tmp_path):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("manifest source bytes\n")
    _commit_fixture(product)
    os.mkfifo(product / "src/nonregular.pipe")

    output = workspace / "archives"
    result = _run_packager(product, output, commit=False)
    assert result.returncode == 0, result.stdout + result.stderr
    (archive_path,) = output.glob("*.tar.gz")
    members = _archive_files(archive_path)
    assert "policy-engine/src/nonregular.pipe" not in members
    assert members["policy-engine/src/fixture.py"] == b"fixture source\n"


def test_gcp_archive_refuses_untracked_regular_sources_outside_the_source_freeze(tmp_path):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("committed manifest source\n")
    _commit_fixture(product)
    untracked = product / "src/uncommitted.py"
    untracked.write_text("not part of the selected source tree\n")

    output = workspace / "archives"
    result = _run_packager(product, output, commit=False)

    assert result.returncode != 0
    assert "Uncommitted GCP archive source is outside the source freeze" in result.stderr
    assert "policy-engine/src/uncommitted.py" in result.stderr
    assert not list(output.glob("*.tar.gz"))


def test_gcp_archive_checks_source_freeze_from_a_nested_git_caller(tmp_path):
    source = "assets/item.yaml"
    workspace, product = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("committed manifest source\n")
    _commit_fixture(product)
    untracked = product / "src/nested-uncommitted.py"
    untracked.write_text("not part of the selected source tree\n")

    nested_workspace = workspace / "raw" / "runner"
    nested_workspace.mkdir(parents=True)
    output = workspace / "archives"
    result = _run_packager(
        product,
        output,
        commit=False,
        fixed_date="20261021-010204",
        caller_cwd=nested_workspace,
    )

    assert result.returncode != 0
    assert "Uncommitted GCP archive source is outside the source freeze" in result.stderr
    assert "policy-engine/src/nested-uncommitted.py" in result.stderr
    assert not list(output.glob("*.tar.gz"))


def test_gcp_archive_refuses_an_ancestor_repository_with_valid_archive_sources(tmp_path):
    source = "assets/item.yaml"
    workspace, product = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("committed parent source\n")
    _commit_fixture(product)
    parent_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=workspace, text=True
    ).strip()

    nested_workspace = workspace / "raw" / "runner"
    nested_product = nested_workspace / "policy-engine"
    nested_script = nested_product / "ops/cloud/gcp/package_repo.sh"
    nested_script.parent.mkdir(parents=True)
    shutil.copyfile(PRODUCT / "ops/cloud/gcp/package_repo.sh", nested_script)
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=nested_workspace, text=True
        ).strip()
        == parent_head
    )

    output = nested_workspace / "archives"
    result = _run_packager(nested_product, output, commit=False)

    assert result.returncode != 0
    assert "at the selected workspace root" in result.stderr
    assert not output.exists()


def test_gcp_archive_reads_force_include_bytes_from_the_committed_source_tree(tmp_path):
    source = "data/dataset_catalog/metrics_map.yaml"
    target = "polisyos/data_forge/domains/catalog/_resources/metrics_map.yaml"
    workspace, product = _project_fixture(tmp_path, _force_include_manifest(source, target))
    source_path = product / source
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"committed catalog source\n")
    private_path = product / "production_data/private.csv"
    private_path.parent.mkdir(parents=True)
    private_path.write_bytes(b"PROTECTED-SYNTHETIC-SENTINEL\n")
    _commit_fixture(product)

    source_path.unlink()
    os.link(private_path, source_path)
    assert os.path.samefile(source_path, private_path)
    output = workspace / "archives"
    result = _run_packager(product, output, commit=False)

    assert result.returncode == 0, result.stdout + result.stderr
    (archive_path,) = output.glob("*.tar.gz")
    members = _archive_files(archive_path)
    assert members[f"policy-engine/{source}"] == b"committed catalog source\n"
    assert all(b"PROTECTED-SYNTHETIC-SENTINEL" not in value for value in members.values())


@pytest.mark.parametrize("existing_kind", ["symlink", "regular"])
def test_gcp_archive_refuses_preexisting_output_without_following_or_replacing_it(
    tmp_path, existing_kind
):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("committed asset\n")
    _commit_fixture(product)
    output = workspace / "archives"
    output.mkdir()
    short_sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    destination = output / f"policy-engine-20261021-010203-{short_sha}.tar.gz"
    protected = product / "production_data/private.tar.gz"
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b"protected destination sentinel\n")
    if existing_kind == "symlink":
        destination.symlink_to(protected)
        before = protected.read_bytes()
    else:
        destination.write_bytes(b"existing archive bytes\n")
        before = destination.read_bytes()

    result = _run_packager(product, output, commit=False, fixed_date="20261021-010203")

    assert result.returncode != 0
    assert "Refusing existing GCP archive destination" in result.stderr
    if existing_kind == "symlink":
        assert destination.is_symlink()
        assert destination.resolve() == protected
        assert protected.read_bytes() == before
    else:
        assert destination.read_bytes() == before


def test_gcp_archive_destination_creation_is_no_clobber_under_competition(tmp_path):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("committed asset\n")
    _commit_fixture(product)
    output = workspace / "archives"

    fake_bin = workspace / "fake-bin"
    fake_bin.mkdir()
    date_command = fake_bin / "date"
    date_command.write_text("#!/bin/sh\nprintf '%s\\n' '20261021-010203'\n")
    date_command.chmod(0o755)
    env = {
        **os.environ,
        "OUT_DIR": str(output),
        "UPLOAD": "0",
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
    }
    command = ["bash", str(product / "ops/cloud/gcp/package_repo.sh")]
    first = subprocess.Popen(
        command, cwd=product, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    second = subprocess.Popen(
        command, cwd=product, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    first_output = first.communicate(timeout=30)
    second_output = second.communicate(timeout=30)
    results = [(first.returncode, *first_output), (second.returncode, *second_output)]

    assert sorted(code for code, _, _ in results) == [0, 1]
    assert (
        sum("Refusing existing GCP archive destination" in stderr for _, _, stderr in results) == 1
    )
    (archive_path,) = output.glob("*.tar.gz")
    assert _archive_files(archive_path)[f"policy-engine/{source}"] == b"committed asset\n"


def test_gcp_archive_refuses_output_alias_created_after_shell_path_selection(tmp_path):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("committed asset\n")
    _commit_fixture(product)
    output = workspace / "archives"
    output.mkdir()
    short_sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    destination = output / f"policy-engine-20261021-010203-{short_sha}.tar.gz"
    protected = product / "production_data/private.tar.gz"
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b"protected target sentinel\n")
    wrapper_dir = workspace / "wrapper"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "python"
    wrapper.write_text(
        "#!/bin/sh\n"
        'cat > "${PYTHON_WRAPPER_SOURCE}"\n'
        'ln -s "${OUTPUT_ALIAS_TARGET}" "$3"\n'
        'exec "${REAL_PYTHON_BIN}" "${PYTHON_WRAPPER_SOURCE}" "$2" "$3" "$4"\n'
    )
    wrapper.chmod(0o755)
    result = _run_packager(
        product,
        output,
        commit=False,
        fixed_date="20261021-010203",
        python_bin=wrapper,
        extra_env={
            "PYTHON_WRAPPER_SOURCE": str(wrapper_dir / "source.py"),
            "REAL_PYTHON_BIN": sys.executable,
            "OUTPUT_ALIAS_TARGET": str(protected),
        },
    )

    assert result.returncode != 0
    assert "Refusing existing GCP archive destination" in result.stderr
    assert destination.is_symlink()
    assert destination.resolve() == protected
    assert protected.read_bytes() == b"protected target sentinel\n"


def test_gcp_archive_upload_reads_the_created_file_descriptor_after_path_swap(tmp_path):
    source = "assets/item.yaml"
    (workspace, product) = _project_fixture(
        tmp_path, _force_include_manifest(source, "polisyos/assets/item.yaml")
    )
    configured_source = product / source
    configured_source.parent.mkdir(parents=True)
    configured_source.write_text("committed asset\n")
    _commit_fixture(product)
    output = workspace / "archives"
    short_sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    archive_path = output / f"policy-engine-20261021-010203-{short_sha}.tar.gz"
    archive_backup = workspace / "archive-backup.tar.gz"
    protected = product / "production_data/private.tar.gz"
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b"protected upload sentinel\n")
    captured_upload = workspace / "uploaded-source.tar.gz"
    captured_destination = workspace / "uploaded-destination.txt"
    fake_bin = workspace / "fake-bin"
    fake_bin.mkdir()
    fake_gcloud = fake_bin / "gcloud"
    fake_gcloud.write_text(
        f"#!{sys.executable}\n"
        "import os, shutil, sys\n"
        "from pathlib import Path\n"
        "assert sys.argv[1:3] == ['storage', 'cp']\n"
        "assert sys.argv[3] == '-'\n"
        "archive_path = Path(os.environ['UPLOAD_ARCHIVE_PATH'])\n"
        "os.replace(archive_path, Path(os.environ['UPLOAD_ARCHIVE_BACKUP']))\n"
        "archive_path.symlink_to(Path(os.environ['UPLOAD_ALIAS_TARGET']))\n"
        "with Path(os.environ['UPLOAD_CAPTURE']).open('wb') as target:\n"
        "    shutil.copyfileobj(sys.stdin.buffer, target)\n"
        "Path(os.environ['UPLOAD_DEST_CAPTURE']).write_text(sys.argv[4])\n"
    )
    fake_gcloud.chmod(0o755)

    result = _run_packager(
        product,
        output,
        commit=False,
        fixed_date="20261021-010203",
        extra_env={
            "UPLOAD": "1",
            "BUCKET_NAME": "synthetic-bucket",
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "UPLOAD_ARCHIVE_PATH": str(archive_path),
            "UPLOAD_ARCHIVE_BACKUP": str(archive_backup),
            "UPLOAD_ALIAS_TARGET": str(protected),
            "UPLOAD_CAPTURE": str(captured_upload),
            "UPLOAD_DEST_CAPTURE": str(captured_destination),
        },
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert captured_destination.read_text() == (
        f"gs://synthetic-bucket/bootstrap/repo/{archive_path.name}"
    )
    assert archive_path.is_symlink()
    assert protected.read_bytes() == b"protected upload sentinel\n"
    assert captured_upload.read_bytes() == archive_backup.read_bytes()
    assert _archive_files(captured_upload)[f"policy-engine/{source}"] == b"committed asset\n"

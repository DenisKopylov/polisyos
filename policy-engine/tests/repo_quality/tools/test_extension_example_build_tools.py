from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import ClassVar

import pytest

from tools.quality.validation import extension_example_build_tools as build_tools

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_native_profile_reuses_exact_q2_lock_without_reusing_q2_purpose() -> None:
    profile, profile_raw, lock, lock_raw, helper_raw = build_tools._source_inputs(REPO_ROOT)

    assert profile["purpose"] == "native-extension-example-wheel-build-only"
    assert profile["purpose"] != "q2-installed-wave-build-tools-only"
    assert build_tools._sha256(profile_raw) == build_tools._sha256(
        (REPO_ROOT / build_tools.PROFILE_PATH).read_bytes()
    )
    assert build_tools._sha256(lock_raw) == profile["lock_sha256"]
    assert build_tools._sha256(helper_raw) == profile["q2_helper_sha256"]
    assert lock["build_backend"]["backend"] == profile["build_backend"]
    assert profile["cache_path"] == ".cache/native-extension-example-build-tools"


def test_native_profile_rejects_a_q2_purpose_substitution() -> None:
    profile_raw = (REPO_ROOT / build_tools.PROFILE_PATH).read_bytes()
    changed = profile_raw.replace(
        b"native-extension-example-wheel-build-only",
        b"q2-installed-wave-build-tools-only",
    )

    with pytest.raises(build_tools.ExampleBuildToolsError, match="bounded source contract"):
        build_tools._parse_profile(changed)


def test_project_requirement_accepts_locked_backend_and_rejects_uncovered_floor() -> None:
    package = REPO_ROOT / "examples/extensions/fabric_connector"
    profile, _, lock, _, _ = build_tools._source_inputs(REPO_ROOT)
    result = build_tools._validate_project_build_system(package, profile, lock)
    assert result["name"] == "polisyos-fabric-connector-example"
    assert result["version"] == "0.1.0"

    raw = (
        (package / "pyproject.toml")
        .read_bytes()
        .replace(
            b"hatchling>=1.24",
            b"hatchling>=9.99",
        )
    )
    with tempfile.TemporaryDirectory() as directory:
        project = Path(directory)
        (project / "pyproject.toml").write_bytes(raw)
        with pytest.raises(build_tools.ExampleBuildToolsError, match="does not satisfy"):
            build_tools._validate_project_build_system(project, profile, lock)


def test_wheel_build_command_uses_a_fresh_owned_uv_cache(monkeypatch, tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    selected: dict[str, object] = {}

    def record_interpreter_check(python, env_path, owned_cache, interpreter):
        selected.update(
            python=python,
            env_path=env_path,
            cache_root=owned_cache,
            interpreter=interpreter,
        )

    monkeypatch.setattr(build_tools, "_verify_build_python", record_interpreter_check)
    command = build_tools._build_command(
        "/usr/bin/uv",
        Path("/cache/bin/python"),
        Path("/fresh/output"),
        cache_root,
    )

    assert selected["python"] == Path("/cache/bin/python")
    assert selected["env_path"] == Path("/cache")
    assert selected["cache_root"] == cache_root
    assert selected["interpreter"]["implementation"] == "CPython"
    assert command[:3] == ["/usr/bin/uv", "--no-config", "--cache-dir"]
    cache_path = Path(command[3])
    assert cache_path.parent == cache_root
    assert cache_path.name.startswith("uv-cache-")
    assert cache_path.is_dir()
    assert not cache_path.is_symlink()
    assert command[4:] == [
        "build",
        "--offline",
        "--no-build-isolation",
        "--python",
        "/cache/bin/python",
        "--wheel",
        "--out-dir",
        "/fresh/output",
    ]


def test_new_cache_file_refuses_symlink_without_touching_target(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    requirements = cache_root / "requirements"
    requirements.mkdir()
    sentinel = tmp_path / "outside-sentinel"
    sentinel.write_bytes(b"preserve")
    link = requirements / "locked-requirements.txt"
    link.symlink_to(sentinel)

    with pytest.raises(
        build_tools.ExampleBuildToolsError,
        match=r"overwrite|symlink|exclusively",
    ):
        build_tools._write_new_cache_file(
            requirements,
            link.name,
            b"replacement",
            within=cache_root,
        )

    assert sentinel.read_bytes() == b"preserve"


def test_cache_root_refuses_symlinked_parent_without_touching_target(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"preserve")
    cache_alias = tmp_path / ".cache"
    cache_alias.symlink_to(outside, target_is_directory=True)

    with pytest.raises(build_tools.ExampleBuildToolsError, match=r"physical|symlink|alias"):
        build_tools._ensure_cache_root(cache_alias / "native-example-tools", tmp_path)

    assert sentinel.read_bytes() == b"preserve"
    assert not (outside / "native-example-tools").exists()


def test_new_cache_file_fails_closed_on_permission_error(monkeypatch, tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    requirements = cache_root / "requirements"
    requirements.mkdir()
    target_name = "permission-denied.txt"
    real_open = build_tools.os.open

    def denied_open(path, flags, mode=0o777):
        if path == str(requirements / target_name):
            raise PermissionError("simulated cache write denial")
        return real_open(path, flags, mode)

    monkeypatch.setattr(build_tools.os, "open", denied_open)
    with pytest.raises(build_tools.ExampleBuildToolsError, match="exclusively"):
        build_tools._write_new_cache_file(
            requirements,
            target_name,
            b"locked",
            within=cache_root,
        )
    assert not (requirements / target_name).exists()


def test_built_wheel_selection_requires_one_fresh_regular_artifact(tmp_path: Path) -> None:
    (tmp_path / "stale.whl").write_bytes(b"wheel")
    (tmp_path / "second.whl").write_bytes(b"wheel")

    with pytest.raises(build_tools.ExampleBuildToolsError, match="exactly one wheel"):
        build_tools._select_built_wheel(tmp_path)


def test_build_tool_cache_uses_ignored_product_cache_root() -> None:
    profile = build_tools._parse_profile((REPO_ROOT / build_tools.PROFILE_PATH).read_bytes())
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", str(profile["cache_path"]) + "/probe"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_locked_commands_drop_inherited_configuration_and_bound_timeouts(
    monkeypatch, tmp_path: Path
) -> None:
    names = (
        "HOME",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTEST_ADDOPTS",
        "VIRTUAL_ENV",
        "OPENAI_API_KEY",
        "PIP_INDEX_URL",
        "UV_CONFIG_FILE",
    )
    cache_environment_names = (
        "UV_CACHE_DIR",
        "XDG_CACHE_HOME",
        "HATCH_CACHE_DIR",
        "TMPDIR",
        "TEMP",
        "TMP",
    )
    for name in (*names, *cache_environment_names):
        monkeypatch.setenv(name, "must-not-cross-boundary")
    cache_root = tmp_path / "cache"
    calls: list[dict[str, object]] = []

    def timeout_run(argv, **kwargs):
        calls.append(kwargs)
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    monkeypatch.setattr(build_tools.subprocess, "run", timeout_run)
    for _ in range(2):
        with pytest.raises(build_tools.ExampleBuildToolsError, match="timed out after 7s"):
            build_tools._run(["locked-command"], cache_root=cache_root, timeout=7)

    assert len(calls) == 2
    process_roots: list[Path] = []
    cache_paths: dict[str, list[Path]] = {
        "UV_CACHE_DIR": [],
        "XDG_CACHE_HOME": [],
        "HATCH_CACHE_DIR": [],
        "TMPDIR": [],
    }
    cache_root_resolved = cache_root.resolve()
    for call in calls:
        environment = call["env"]
        assert isinstance(environment, dict)
        assert call["timeout"] == 7
        assert all(name not in environment for name in names)
        assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
        assert environment["PYTHONNOUSERSITE"] == "1"
        for name in cache_paths:
            path = Path(environment[name])
            assert path.is_dir()
            assert not path.is_symlink()
            assert path.resolve().is_relative_to(cache_root_resolved)
            assert path.name.startswith(
                {
                    "UV_CACHE_DIR": "uv-cache-",
                    "XDG_CACHE_HOME": "xdg-cache-",
                    "HATCH_CACHE_DIR": "hatch-cache-",
                    "TMPDIR": "tmp-",
                }[name]
            )
            assert path.parent.name.startswith("process-")
            assert path.parent.parent == cache_root_resolved
            cache_paths[name].append(path)
        assert environment["TEMP"] == environment["TMP"] == environment["TMPDIR"]
        process_roots.append(Path(environment["TMPDIR"]).parent)

    assert len(set(process_roots)) == 2
    assert all(len(set(paths)) == 2 for paths in cache_paths.values())


def test_probe_uses_isolated_python_and_never_executes_pth_or_sitecustomize(tmp_path: Path) -> None:
    _, _, lock, _, _ = build_tools._source_inputs(REPO_ROOT)
    env_path = tmp_path / "build-tools-venv"
    purelib = (
        env_path
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    purelib.mkdir(parents=True)
    marker_pth, marker_site = tmp_path / "pth-ran", tmp_path / "sitecustomize-ran"
    (purelib / "injected.pth").write_text(
        f"import pathlib; pathlib.Path({str(marker_pth)!r}).write_text('ran')\n", encoding="utf-8"
    )
    (purelib / "sitecustomize.py").write_text(
        f"from pathlib import Path; Path({str(marker_site)!r}).write_text('ran')\n",
        encoding="utf-8",
    )
    command = build_tools._probe_command(Path(sys.executable), lock, env_path)
    assert command[1:3] == ["-I", "-S"]
    with pytest.raises(build_tools.ExampleBuildToolsError, match=r"unexpected \.pth file"):
        build_tools._run(command, cache_root=tmp_path / "cache", timeout=30)
    assert not marker_pth.exists()
    assert not marker_site.exists()


def _fixture_wheel(directory: Path, *, invalid_record: bool = False):
    name, version = "fixture-demo", "1.2.3"
    dist_info = "fixture_demo-1.2.3.dist-info"
    files = {
        "fixture_pkg/__init__.py": b"def factory():\n    return object()\n",
        f"{dist_info}/METADATA": b"Metadata-Version: 2.1\nName: fixture-demo\nVersion: 1.2.3\n\n",
        f"{dist_info}/WHEEL": b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n",
        f"{dist_info}/entry_points.txt": b"[polisyos.fabric_connectors]\nexample.local_rows = fixture_pkg:factory\n",
    }
    record = f"{dist_info}/RECORD"
    rows = []
    for path, data in sorted(files.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        rows.append([path, f"sha256={digest}", str(len(data))])
    if invalid_record:
        rows[0][1] = "sha256=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    rows.append([record, "", ""])
    stream = io.StringIO()
    csv.writer(stream, lineterminator="\n").writerows(rows)
    files[record] = stream.getvalue().encode()
    wheel = directory / "fixture_demo-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for path, data in files.items():
            archive.writestr(path, data)
    project = {
        "name": name,
        "version": version,
        "entry_points": {
            "polisyos.fabric_connectors": {"example.local_rows": "fixture_pkg:factory"}
        },
    }
    return wheel, project, files


def test_wheel_metadata_tag_entry_point_and_complete_record_are_recomputed(tmp_path: Path) -> None:
    wheel, project, member_bytes = _fixture_wheel(tmp_path)
    identity = build_tools._validate_wheel_identity(wheel, project, {"wheel_tag": "py3-none-any"})
    assert identity["filename"] == wheel.name
    assert (
        identity["files"]["fixture_pkg/__init__.py"]["sha256"]
        == hashlib.sha256(member_bytes["fixture_pkg/__init__.py"]).hexdigest()
    )
    bad = tmp_path / "bad"
    bad.mkdir()
    bad_wheel, bad_project, _ = _fixture_wheel(bad, invalid_record=True)
    with pytest.raises(build_tools.ExampleBuildToolsError, match="hash or size differs"):
        build_tools._validate_wheel_identity(bad_wheel, bad_project, {"wheel_tag": "py3-none-any"})


def _fake_distribution(tmp_path: Path, identity, wheel: Path, member_bytes):
    dist_info = str(identity["dist_info"])
    root = tmp_path / "site-packages"
    rows = []
    for member, data in member_bytes.items():
        target = root / member
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    direct = {
        "url": wheel.as_uri(),
        "archive_info": {"hashes": {"sha256": identity["wheel_sha256"]}},
    }
    direct_path = f"{dist_info}/direct_url.json"
    direct_raw = json.dumps(direct).encode()
    direct_file = root / direct_path
    direct_file.parent.mkdir(parents=True, exist_ok=True)
    direct_file.write_bytes(direct_raw)
    installed = {
        **{p: b for p, b in member_bytes.items() if not p.endswith("/RECORD")},
        direct_path: direct_raw,
    }
    for path, data in sorted(installed.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
        rows.append([path, f"sha256={digest}", str(len(data))])
    record = f"{dist_info}/RECORD"
    rows.append([record, "", ""])
    stream = io.StringIO()
    csv.writer(stream, lineterminator="\n").writerows(rows)
    record_file = root / record
    record_file.write_text(stream.getvalue(), encoding="utf-8")

    class FakeDistribution:
        metadata: ClassVar[dict[str, str]] = {"Name": identity["name"]}
        version = str(identity["version"])
        entry_points = (
            SimpleNamespace(
                group="polisyos.fabric_connectors",
                name="example.local_rows",
                value="fixture_pkg:factory",
            ),
        )

        def __init__(self):
            self.files = tuple(PurePosixPath(row[0]) for row in rows)

        def locate_file(self, item):
            return root / str(item)

        def read_text(self, name):
            path = root / dist_info / name
            return path.read_text(encoding="utf-8") if path.exists() else None

    return FakeDistribution(), record_file, direct_file


def test_fresh_discovery_rejects_editable_wrong_payload_and_wrong_record(
    monkeypatch, tmp_path: Path
) -> None:
    wheel, project, members = _fixture_wheel(tmp_path)
    identity = build_tools._validate_wheel_identity(wheel, project, {"wheel_tag": "py3-none-any"})
    binding = {
        "status": "verified",
        "group": "polisyos.fabric_connectors",
        "name": "example.local_rows",
        "value": "fixture_pkg:factory",
        "module_files": [
            {
                "relative_path": "fixture_pkg/__init__.py",
                "byte_count": len(members["fixture_pkg/__init__.py"]),
                "sha256": hashlib.sha256(members["fixture_pkg/__init__.py"]).hexdigest(),
            }
        ],
    }
    editable, _, direct_file = _fake_distribution(tmp_path / "editable", identity, wheel, members)
    direct = json.loads(direct_file.read_text())
    direct["dir_info"] = {"editable": True}
    direct_file.write_text(json.dumps(direct))
    monkeypatch.setattr(build_tools.importlib_metadata, "distribution", lambda _name: editable)
    with pytest.raises(
        build_tools.ExampleBuildToolsError, match="not the exact regular local wheel"
    ):
        build_tools._verify_installed_wheel_identity(
            identity,
            binding,
            group="polisyos.fabric_connectors",
            entry_point_name="example.local_rows",
        )

    wrong, _, _ = _fake_distribution(tmp_path / "wrong", identity, wheel, members)
    (tmp_path / "wrong/site-packages/fixture_pkg/__init__.py").write_bytes(b"changed")
    monkeypatch.setattr(build_tools.importlib_metadata, "distribution", lambda _name: wrong)
    with pytest.raises(
        build_tools.ExampleBuildToolsError, match=r"RECORD hash or size differs|payload differs"
    ):
        build_tools._verify_installed_wheel_identity(
            identity,
            binding,
            group="polisyos.fabric_connectors",
            entry_point_name="example.local_rows",
        )

    bad, record_file, _ = _fake_distribution(tmp_path / "bad-record", identity, wheel, members)
    record_file.write_text(
        record_file.read_text().replace(
            "fixture_pkg/__init__.py,sha256=", "fixture_pkg/__init__.py,sha256=AAAAAAAA", 1
        )
    )
    monkeypatch.setattr(build_tools.importlib_metadata, "distribution", lambda _name: bad)
    with pytest.raises(build_tools.ExampleBuildToolsError, match="RECORD hash or size differs"):
        build_tools._verify_installed_wheel_identity(
            identity,
            binding,
            group="polisyos.fabric_connectors",
            entry_point_name="example.local_rows",
        )


def _append_recorded_installed_member(
    distribution, site_packages: Path, record_file: Path, relative_path: str, raw: bytes
) -> None:
    target = site_packages / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    rows = {
        row[0]: (row[1], row[2])
        for row in csv.reader(record_file.read_text(encoding="utf-8").splitlines())
    }
    rows[relative_path] = (
        "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip("="),
        str(len(raw)),
    )
    record_name = record_file.relative_to(site_packages).as_posix()
    rows[record_name] = ("", "")
    stream = io.StringIO()
    csv.writer(stream, lineterminator="\n").writerows(
        [[path, digest, size] for path, (digest, size) in sorted(rows.items())]
    )
    record_file.write_text(stream.getvalue(), encoding="utf-8")
    distribution.files = tuple(PurePosixPath(path) for path in rows)


def _fixture_provider_binding(member_bytes):
    return {
        "status": "verified",
        "group": "polisyos.fabric_connectors",
        "name": "example.local_rows",
        "value": "fixture_pkg:factory",
        "module_files": [
            {
                "relative_path": "fixture_pkg/__init__.py",
                "byte_count": len(member_bytes["fixture_pkg/__init__.py"]),
                "sha256": hashlib.sha256(member_bytes["fixture_pkg/__init__.py"]).hexdigest(),
            }
        ],
    }


def test_uv_installer_metadata_is_record_bound_and_closed(tmp_path: Path, monkeypatch) -> None:
    wheel, project, members = _fixture_wheel(tmp_path)
    identity = build_tools._validate_wheel_identity(wheel, project, {"wheel_tag": "py3-none-any"})
    binding = _fixture_provider_binding(members)
    dist_info = str(identity["dist_info"])

    valid, record, _ = _fake_distribution(tmp_path / "valid", identity, wheel, members)
    site = tmp_path / "valid/site-packages"
    _append_recorded_installed_member(valid, site, record, f"{dist_info}/INSTALLER", b"uv")
    cache_member = f"{dist_info}/uv_cache.json"
    _append_recorded_installed_member(valid, site, record, cache_member, b'{"directories":{}}')
    monkeypatch.setattr(build_tools.importlib_metadata, "distribution", lambda _name: valid)
    accepted = build_tools._verify_installed_wheel_identity(
        identity, binding, group="polisyos.fabric_connectors", entry_point_name="example.local_rows"
    )
    assert accepted["installed_file_count"] == len(identity["files"])

    tampered, tampered_record, _ = _fake_distribution(
        tmp_path / "tampered", identity, wheel, members
    )
    tampered_site = tmp_path / "tampered/site-packages"
    _append_recorded_installed_member(
        tampered, tampered_site, tampered_record, f"{dist_info}/INSTALLER", b"uv"
    )
    _append_recorded_installed_member(
        tampered, tampered_site, tampered_record, cache_member, b'{"directories":{}}'
    )
    (tampered_site / cache_member).write_bytes(b'{"directories":{"tampered":true}}')
    monkeypatch.setattr(build_tools.importlib_metadata, "distribution", lambda _name: tampered)
    with pytest.raises(build_tools.ExampleBuildToolsError, match="RECORD hash or size differs"):
        build_tools._verify_installed_wheel_identity(
            identity,
            binding,
            group="polisyos.fabric_connectors",
            entry_point_name="example.local_rows",
        )

    wrong_installer, wrong_record, _ = _fake_distribution(
        tmp_path / "wrong-installer", identity, wheel, members
    )
    wrong_site = tmp_path / "wrong-installer/site-packages"
    _append_recorded_installed_member(
        wrong_installer, wrong_site, wrong_record, f"{dist_info}/INSTALLER", b"pip"
    )
    _append_recorded_installed_member(
        wrong_installer, wrong_site, wrong_record, cache_member, b'{"directories":{}}'
    )
    monkeypatch.setattr(
        build_tools.importlib_metadata, "distribution", lambda _name: wrong_installer
    )
    with pytest.raises(
        build_tools.ExampleBuildToolsError, match="file inventory differs from the wheel"
    ):
        build_tools._verify_installed_wheel_identity(
            identity,
            binding,
            group="polisyos.fabric_connectors",
            entry_point_name="example.local_rows",
        )

    unknown, unknown_record, _ = _fake_distribution(tmp_path / "unknown", identity, wheel, members)
    unknown_site = tmp_path / "unknown/site-packages"
    _append_recorded_installed_member(
        unknown, unknown_site, unknown_record, f"{dist_info}/INSTALLER", b"uv"
    )
    _append_recorded_installed_member(
        unknown, unknown_site, unknown_record, f"{dist_info}/other_state.json", b"{}"
    )
    monkeypatch.setattr(build_tools.importlib_metadata, "distribution", lambda _name: unknown)
    with pytest.raises(
        build_tools.ExampleBuildToolsError, match="file inventory differs from the wheel"
    ):
        build_tools._verify_installed_wheel_identity(
            identity,
            binding,
            group="polisyos.fabric_connectors",
            entry_point_name="example.local_rows",
        )

    missing, missing_record, _ = _fake_distribution(tmp_path / "missing", identity, wheel, members)
    missing_site = tmp_path / "missing/site-packages"
    _append_recorded_installed_member(
        missing, missing_site, missing_record, f"{dist_info}/INSTALLER", b"uv"
    )
    _append_recorded_installed_member(
        missing, missing_site, missing_record, cache_member, b'{"directories":{}}'
    )
    (missing_site / cache_member).unlink()
    monkeypatch.setattr(build_tools.importlib_metadata, "distribution", lambda _name: missing)
    with pytest.raises(build_tools.ExampleBuildToolsError, match="RECORD member cannot be read"):
        build_tools._verify_installed_wheel_identity(
            identity,
            binding,
            group="polisyos.fabric_connectors",
            entry_point_name="example.local_rows",
        )


def test_actual_offline_uv_install_passes_exact_installed_wheel_verifier(
    tmp_path: Path, monkeypatch
) -> None:
    if build_tools.shutil.which("uv") is None:
        pytest.skip("the offline local-wheel integration requires the configured uv executable")
    wheel, project, members = _fixture_wheel(tmp_path)
    identity = build_tools._validate_wheel_identity(wheel, project, {"wheel_tag": "py3-none-any"})
    actual_tmp = tmp_path / "actual"
    actual_tmp.mkdir()
    cache_root, env_path, _python, _interpreter = _create_test_build_tools_venv(actual_tmp)
    uv, _uv_profile = build_tools._uv_identity(cache_root)
    build_tools._run(
        build_tools._uv_command(
            uv,
            cache_root,
            "pip",
            "install",
            "--offline",
            "--no-index",
            "--reinstall",
            "--no-deps",
            "--python",
            str(_python),
            str(wheel),
        ),
        cache_root=cache_root,
        timeout=60,
    )
    site_packages = _test_site_packages(env_path)
    distribution = next(
        item
        for item in build_tools.importlib_metadata.distributions(path=[str(site_packages)])
        if item.metadata.get("Name") == project["name"]
    )
    monkeypatch.setattr(build_tools.importlib_metadata, "distribution", lambda _name: distribution)
    binding = _fixture_provider_binding(members)
    accepted = build_tools._verify_installed_wheel_identity(
        identity, binding, group="polisyos.fabric_connectors", entry_point_name="example.local_rows"
    )
    assert accepted["status"] == (
        "installed-distribution-entry-point-and-provider-bytes-match-built-wheel"
    )
    assert accepted["installed_file_count"] == len(identity["files"])
    installer = distribution.read_text("INSTALLER")
    assert installer is not None and installer.strip() == "uv"
    if f"{identity['dist_info']}/uv_cache.json" in {str(item) for item in distribution.files or ()}:
        assert (site_packages / str(identity["dist_info"]) / "uv_cache.json").is_file()


def test_native_profile_interpreter_identity_matches_cpython_contract() -> None:
    profile, *_ = build_tools._source_inputs(REPO_ROOT)
    identity = build_tools._interpreter_identity(profile)

    assert identity["implementation"] == profile["python_implementation"] == "CPython"
    assert identity["executable_sha256"] == build_tools._sha256_file(
        Path(str(identity["executable"]))
    )


def _create_test_build_tools_venv(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, object]]:
    profile, _, _, _, _ = build_tools._source_inputs(REPO_ROOT)
    interpreter = build_tools._interpreter_identity(profile)
    cache_root = tmp_path / "cache"
    environments = build_tools._cache_directory(cache_root, "environments")
    env_path = build_tools._new_cache_path(environments, "bootstrap-test", within=cache_root)
    python = build_tools._create_build_tools_venv(env_path, cache_root, interpreter)
    return cache_root, env_path, python, interpreter


def _test_site_packages(env_path: Path) -> Path:
    if build_tools.os.name == "nt":
        return env_path / "Lib" / "site-packages"
    return (
        env_path
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )


def test_stdlib_bootstrap_creates_a_verified_venv_without_pth(tmp_path: Path) -> None:
    _cache_root, env_path, python, interpreter = _create_test_build_tools_venv(tmp_path)
    config = {
        key.strip(): value.strip()
        for key, value in (
            line.split("=", 1)
            for line in (env_path / "pyvenv.cfg").read_text(encoding="utf-8").splitlines()
        )
    }
    expected_executable = Path(str(interpreter["executable"]))

    assert python.is_file()
    assert Path(config["home"].strip()).resolve() == expected_executable.parent
    assert config["include-system-site-packages"].strip() == "false"
    assert config["version"].strip() == ".".join(str(value) for value in interpreter["version"])
    assert Path(config["executable"].strip()).resolve() == expected_executable
    assert config["command"].strip() == (f"{expected_executable} -m venv --without-pip {env_path}")
    assert list(_test_site_packages(env_path).glob("*.pth")) == []


def test_stdlib_bootstrap_probe_rejects_executable_pth_without_running_it(tmp_path: Path) -> None:
    cache_root, env_path, python, _ = _create_test_build_tools_venv(tmp_path)
    _, _, lock, _, _ = build_tools._source_inputs(REPO_ROOT)
    sentinel = tmp_path / "pth-executed"
    (_test_site_packages(env_path) / "injected.pth").write_text(
        f"import pathlib; pathlib.Path({str(sentinel)!r}).write_text('ran')\n",
        encoding="utf-8",
    )

    with pytest.raises(build_tools.ExampleBuildToolsError, match=r"unexpected \.pth file"):
        build_tools._run(
            build_tools._probe_command(python, lock, env_path),
            cache_root=cache_root,
            timeout=30,
        )

    assert not sentinel.exists()


def test_venv_bootstrap_recipe_participates_in_cache_identity(monkeypatch) -> None:
    profile, profile_raw, _lock, lock_raw, q2_helper_raw = build_tools._source_inputs(REPO_ROOT)
    interpreter = build_tools._interpreter_identity(profile)
    native_helper_raw = Path(build_tools.__file__).read_bytes()
    uv_identity = {"path": "/usr/bin/uv", "version": "uv 0.10.6"}
    current = build_tools._cache_key(
        profile_raw, lock_raw, q2_helper_raw, native_helper_raw, interpreter, uv_identity
    )
    monkeypatch.setattr(build_tools, "VENV_BOOTSTRAP_RECIPE", "changed-bootstrap")
    changed = build_tools._cache_key(
        profile_raw, lock_raw, q2_helper_raw, native_helper_raw, interpreter, uv_identity
    )

    assert current != changed


def test_cached_build_python_cache_marker_cannot_authorize_a_fake_interpreter(
    tmp_path: Path,
) -> None:
    profile, profile_raw, lock, lock_raw, q2_helper_raw = build_tools._source_inputs(REPO_ROOT)
    interpreter = build_tools._interpreter_identity(profile)
    native_helper_raw = Path(build_tools.__file__).read_bytes()
    uv_identity = {"path": "/usr/bin/uv", "version": "uv 0.10.6"}
    cache_key = build_tools._cache_key(
        profile_raw,
        lock_raw,
        q2_helper_raw,
        native_helper_raw,
        interpreter,
        uv_identity,
    )
    cache_root = tmp_path / str(profile["cache_path"])
    env_path = cache_root / "environments" / cache_key
    bin_path = env_path / "bin"
    bin_path.mkdir(parents=True)
    sentinel = tmp_path / "fake-python-executed"
    python = bin_path / "python"
    python.write_text(
        f"#!/bin/sh\nprintf ran > {str(sentinel)!r}\nprintf '{{\"verified\":true}}\n'\n",
        encoding="utf-8",
    )
    python.chmod(0o700)
    executable = Path(str(interpreter["executable"]))
    version = ".".join(str(value) for value in interpreter["version"])
    (env_path / "pyvenv.cfg").write_text(
        f"home = {executable.parent}\n"
        "include-system-site-packages = false\n"
        f"version = {version}\n"
        f"executable = {executable}\n"
        f"command = {executable} -m venv --without-pip {env_path}\n",
        encoding="utf-8",
    )
    expected_marker = {
        "schema": "policyos.native-extension-example-build-tools-cache.v2",
        "purpose": build_tools.PROFILE_PURPOSE,
        "cache_key": cache_key,
        "venv_bootstrap_recipe": build_tools.VENV_BOOTSTRAP_RECIPE,
        "profile_sha256": build_tools._sha256(profile_raw),
        "lock_sha256": build_tools._sha256(lock_raw),
        "q2_helper_sha256": build_tools._sha256(q2_helper_raw),
        "native_helper_sha256": build_tools._sha256(native_helper_raw),
        "interpreter": interpreter,
        "uv": uv_identity,
    }
    (env_path / build_tools.CACHE_MANIFEST).write_text(
        json.dumps(expected_marker, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(build_tools.ExampleBuildToolsError, match="bytes differ"):
        build_tools._ensure_build_tools_python(
            tmp_path,
            profile,
            profile_raw,
            lock,
            lock_raw,
            q2_helper_raw,
            tmp_path / "wheelhouse",
            interpreter,
            "/usr/bin/uv",
            uv_identity,
        )

    assert not sentinel.exists()


def test_cached_build_python_accepts_an_exact_host_interpreter_symlink(tmp_path: Path) -> None:
    profile, *_ = build_tools._source_inputs(REPO_ROOT)
    interpreter = build_tools._interpreter_identity(profile)
    cache_root = tmp_path / "cache"
    env_path = cache_root / "environments" / "cached"
    bin_path = env_path / "bin"
    bin_path.mkdir(parents=True)
    python = bin_path / "python"
    python.symlink_to(Path(str(interpreter["executable"])))
    executable = Path(str(interpreter["executable"]))
    version = ".".join(str(value) for value in interpreter["version"])
    (env_path / "pyvenv.cfg").write_text(
        f"home = {executable.parent}\n"
        "include-system-site-packages = false\n"
        f"version = {version}\n"
        f"executable = {executable}\n"
        f"command = {executable} -m venv --without-pip {env_path}\n",
        encoding="utf-8",
    )

    build_tools._verify_build_python(python, env_path, cache_root, interpreter)


def test_wheelhouse_retry_skips_retained_partial_attempt_without_deleting_it(
    monkeypatch, tmp_path: Path
) -> None:
    _, _, lock, lock_raw, _ = build_tools._source_inputs(REPO_ROOT)
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    attempts: list[Path] = []

    def fetch_once_or_retry(_lock, destination: Path) -> None:
        attempts.append(destination)
        destination.mkdir(mode=0o700)
        if len(attempts) == 1:
            (destination / "partial-input").write_bytes(b"retained failure")
            raise build_tools.q2.BuildToolsInputError("simulated partial locked fetch")
        (destination / "complete-input").write_bytes(b"complete")

    def validate_attempt(_lock, destination: Path) -> dict[str, object]:
        if not (destination / "complete-input").is_file():
            raise build_tools.q2.BuildToolsInputError("retained attempt is incomplete")
        return {"validated": True}

    monkeypatch.setattr(build_tools.q2, "fetch_locked_inputs", fetch_once_or_retry)
    monkeypatch.setattr(build_tools.q2, "validate_quarantine", validate_attempt)

    with pytest.raises(build_tools.q2.BuildToolsInputError, match="partial locked fetch"):
        build_tools._ensure_wheelhouse(cache_root, lock, lock_raw)

    first_attempt = attempts[0]
    result = build_tools._ensure_wheelhouse(cache_root, lock, lock_raw)

    assert len(attempts) == 2
    assert result == attempts[1]
    assert first_attempt.is_dir()
    assert (first_attempt / "partial-input").read_bytes() == b"retained failure"


def test_wheel_install_targets_lexical_active_venv_interpreter(monkeypatch, tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    base_python = base / "python"
    base_python.write_bytes(b"base interpreter")
    prefix = tmp_path / ".venv"
    target_python = prefix / "bin" / "python"
    target_python.parent.mkdir(parents=True)
    target_python.symlink_to(base_python)
    monkeypatch.setattr(build_tools.sys, "executable", str(target_python))
    monkeypatch.setattr(build_tools.sys, "prefix", str(prefix))
    monkeypatch.setattr(build_tools.sys, "base_prefix", str(base))

    command = build_tools._target_python_install_argv(
        "/usr/bin/uv", tmp_path / "cache", tmp_path / "example.whl"
    )

    assert command[-3:] == ["--python", str(target_python), str(tmp_path / "example.whl")]
    assert target_python.resolve() == base_python


def test_wheel_install_refuses_global_or_outside_environment_interpreters(
    monkeypatch, tmp_path: Path
) -> None:
    prefix = tmp_path / ".venv"
    prefix.mkdir()
    global_python = tmp_path / "python"
    global_python.write_bytes(b"global interpreter")
    monkeypatch.setattr(build_tools.sys, "executable", str(global_python))
    monkeypatch.setattr(build_tools.sys, "prefix", str(prefix))
    monkeypatch.setattr(build_tools.sys, "base_prefix", str(prefix))

    with pytest.raises(build_tools.ExampleBuildToolsError, match="active virtual environment"):
        build_tools._target_python_install_argv(
            "/usr/bin/uv", tmp_path / "cache-global", tmp_path / "example.whl"
        )

    monkeypatch.setattr(build_tools.sys, "base_prefix", str(tmp_path / "base"))
    with pytest.raises(build_tools.ExampleBuildToolsError, match="inside the active"):
        build_tools._target_python_install_argv(
            "/usr/bin/uv", tmp_path / "cache-outside", tmp_path / "example.whl"
        )


def _write_cached_build_python_environment(
    tmp_path: Path, interpreter: dict[str, object], home: Path
) -> tuple[Path, Path, Path]:
    cache_root = tmp_path / "cache"
    env_path = cache_root / "environments" / "candidate"
    python = env_path / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.symlink_to(Path(str(interpreter["executable"])))
    executable = Path(str(interpreter["executable"]))
    version = ".".join(str(value) for value in interpreter["version"])
    (env_path / "pyvenv.cfg").write_text(
        f"home = {home}\n"
        "include-system-site-packages = false\n"
        f"version = {version}\n"
        f"executable = {executable}\n"
        f"command = {executable} -m venv --without-pip {env_path}\n",
        encoding="utf-8",
    )
    return cache_root, env_path, python


def test_cached_build_python_rejects_unknown_uv_profile_field(tmp_path: Path) -> None:
    profile, *_ = build_tools._source_inputs(REPO_ROOT)
    interpreter = build_tools._interpreter_identity(profile)
    home = Path(str(interpreter["executable"])).parent
    cache_root, env_path, python = _write_cached_build_python_environment(
        tmp_path, interpreter, home
    )
    config_path = env_path / "pyvenv.cfg"
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + "uv = 0.10.6\n",
        encoding="utf-8",
    )

    with pytest.raises(
        build_tools.ExampleBuildToolsError,
        match="incomplete or unknown stdlib field set",
    ):
        build_tools._verify_build_python(python, env_path, cache_root, interpreter)


def test_cached_build_python_rejects_changed_creation_recipe(tmp_path: Path) -> None:
    profile, *_ = build_tools._source_inputs(REPO_ROOT)
    interpreter = build_tools._interpreter_identity(profile)
    home = Path(str(interpreter["executable"])).parent
    cache_root, env_path, python = _write_cached_build_python_environment(
        tmp_path, interpreter, home
    )
    config_path = env_path / "pyvenv.cfg"
    config = config_path.read_text(encoding="utf-8")
    expected = f"command = {interpreter['executable']} -m venv --without-pip {env_path}"
    replacement = f"command = {interpreter['executable']} -m venv {env_path}"
    if config.count(expected) != 1:
        raise AssertionError("expected stdlib creation command missing")
    config_path.write_text(config.replace(expected, replacement, 1), encoding="utf-8")

    with pytest.raises(
        build_tools.ExampleBuildToolsError,
        match="differs from the selected stdlib virtual environment profile",
    ):
        build_tools._verify_build_python(python, env_path, cache_root, interpreter)


def test_cached_build_python_accepts_resolved_host_home_alias(tmp_path: Path) -> None:
    profile, *_ = build_tools._source_inputs(REPO_ROOT)
    interpreter = build_tools._interpreter_identity(profile)
    expected_home = Path(str(interpreter["executable"])).parent
    configured_home = tmp_path / "uv-host-home-alias"
    configured_home.symlink_to(expected_home, target_is_directory=True)

    assert configured_home != expected_home
    assert configured_home.resolve(strict=True) == expected_home
    assert configured_home.samefile(expected_home)
    cache_root, env_path, python = _write_cached_build_python_environment(
        tmp_path, interpreter, configured_home
    )

    build_tools._verify_build_python(python, env_path, cache_root, interpreter)


@pytest.mark.parametrize("retarget_alias", [False, True])
def test_cached_build_python_rejects_foreign_or_retargeted_home(
    tmp_path: Path, retarget_alias: bool
) -> None:
    profile, *_ = build_tools._source_inputs(REPO_ROOT)
    interpreter = build_tools._interpreter_identity(profile)
    expected_home = Path(str(interpreter["executable"])).parent
    foreign_home = tmp_path / "foreign-python-home"
    foreign_home.mkdir()
    configured_home = foreign_home
    if retarget_alias:
        configured_home = tmp_path / "uv-host-home-alias"
        configured_home.symlink_to(expected_home, target_is_directory=True)
        assert configured_home.samefile(expected_home)
        configured_home.unlink()
        configured_home.symlink_to(foreign_home, target_is_directory=True)
        assert configured_home.samefile(foreign_home)
    cache_root, env_path, python = _write_cached_build_python_environment(
        tmp_path, interpreter, configured_home
    )

    with pytest.raises(
        build_tools.ExampleBuildToolsError,
        match="differs from the selected stdlib virtual environment profile",
    ):
        build_tools._verify_build_python(python, env_path, cache_root, interpreter)

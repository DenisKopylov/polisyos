"""Behavioral controls for the source-owned Q2 offline build-tool profile."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import tomllib
import zipfile
from pathlib import Path
from typing import Any

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from tools.quality.validation import q2_build_tool_wheel_lock as gate

_PRODUCT_ROOT = Path(__file__).resolve().parents[3]
PROFILE_PATH = gate.Q2_PROFILE_PATH


_ROOT_REQUIREMENTS = ["packaging>=1.0", "pathspec>=1.0", "pluggy>=1.0"]


def _csv_record(files: dict[str, bytes], *, orphan: bool = False) -> bytes:
    rows = []
    for name, raw in sorted(files.items()):
        digest = (
            "sha256="
            + __import__("base64")
            .urlsafe_b64encode(hashlib.sha256(raw).digest())
            .rstrip(b"=")
            .decode()
        )
        rows.append([name, digest, str(len(raw))])
    record_name = next(
        name.rsplit("/", 1)[0] + "/RECORD" for name in files if name.endswith(".dist-info/METADATA")
    )
    rows.append([record_name, "", ""])
    if orphan:
        rows.append(["orphan.py", "sha256=YWJj", "3"])
    output = io.StringIO(newline="")
    csv.writer(output, lineterminator="\n").writerows(rows)
    return output.getvalue().encode()


def _wheel(
    name: str,
    version: str,
    requires_dist: list[str],
    *,
    provides_extras: list[str] | None = None,
    orphan_record: bool = False,
    corrupt_record: bool = False,
) -> tuple[bytes, bytes, str]:
    normalized = name.replace("-", "_")
    dist_info = f"{normalized}-{version}.dist-info"
    entry_points = (
        "[console_scripts]\nhatchling = hatchling.cli:hatchling\n" if name == "hatchling" else None
    )
    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {name}",
        f"Version: {version}",
        "Requires-Python: >=3.8",
        *(f"Requires-Dist: {item}" for item in requires_dist),
        *(f"Provides-Extra: {item}" for item in (provides_extras or [])),
        "",
    ]
    metadata = "\n".join(metadata_lines).encode()
    files = {
        f"{normalized}/__init__.py": b"VALUE = 1\n",
        f"{dist_info}/METADATA": metadata,
        f"{dist_info}/WHEEL": (
            b"Wheel-Version: 1.0\nGenerator: q2-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
        ),
    }
    if entry_points is not None:
        files[f"{dist_info}/entry_points.txt"] = entry_points.encode()
    record = _csv_record(files, orphan=orphan_record)
    if corrupt_record:
        record = record.replace(b"sha256=", b"sha256=AAAA", 1)
    files[f"{dist_info}/RECORD"] = record
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path, raw in sorted(files.items()):
            archive.writestr(path, raw)
    return output.getvalue(), metadata, entry_points or ""


def _make_case(
    *, root_requires: list[str] | None = None
) -> tuple[dict[str, Any], dict[str, bytes], dict[str, bytes]]:
    requires = _ROOT_REQUIREMENTS if root_requires is None else root_requires
    specifications = [
        ("hatchling", "1.0.0", requires, []),
        ("packaging", "1.0.0", [], []),
        ("pathspec", "1.0.0", [], []),
        ("pluggy", "1.0.0", ['coverage; extra == "testing"'], ["testing"]),
    ]
    rows = []
    wheels = {}
    releases = {}
    for name, version, requirements, extras in specifications:
        raw, metadata, entry_points = _wheel(name, version, requirements, provides_extras=extras)
        filename = f"{name}-{version}-py3-none-any.whl"
        digest = hashlib.sha256(raw).hexdigest()
        release_url = f"https://pypi.org/pypi/{name}/{version}/json"
        file_url = f"https://files.pythonhosted.org/packages/test/{filename}"
        release = {
            "info": {
                "name": name,
                "version": version,
                "requires_python": ">=3.8",
                "requires_dist": requirements,
            },
            "urls": [
                {
                    "filename": filename,
                    "url": file_url,
                    "digests": {"sha256": digest},
                    "size": len(raw),
                    "yanked": False,
                }
            ],
        }
        release_raw = json.dumps(release, sort_keys=True, separators=(",", ":")).encode()
        rows.append(
            {
                "name": name,
                "version": version,
                "filename": filename,
                "url": file_url,
                "size_bytes": len(raw),
                "sha256": digest,
                "wheel_tags": ["py3-none-any"],
                "requires_python": ">=3.8",
                "requires_dist": requirements,
                "provides_extras": extras,
                "metadata_sha256": hashlib.sha256(metadata).hexdigest(),
                "pypi_release": {
                    "json_url": release_url,
                    "json_sha256": hashlib.sha256(release_raw).hexdigest(),
                    "pypi_file_sha256": digest,
                    "pypi_file_size_bytes": len(raw),
                    "upload_time_iso_8601": "2026-01-01T00:00:00Z",
                    "yanked": False,
                },
                "entry_points": entry_points,
            }
        )
        wheels[filename] = raw
        releases[name] = release_raw
    lock = {
        "schema": gate.LOCK_SCHEMA,
        "build_backend": {
            "root_requirement": "hatchling==1.0.0",
            "backend": "hatchling.build",
            "installer_entry_point": "hatchling = hatchling.cli:hatchling",
            "selected_extras": [],
        },
        "portable_artifact_profile": {
            "wheel_tag_required": "py3-none-any",
            "target_python_marker_environment": {
                "implementation": "CPython",
                "python_version": "3.14",
            },
        },
        "artifacts": rows,
        "closure": {
            "roots": ["hatchling==1.0.0"],
            "expected_distribution_set": [
                "hatchling==1.0.0",
                "packaging==1.0.0",
                "pathspec==1.0.0",
                "pluggy==1.0.0",
            ],
            "requested_extras_by_distribution": {
                "hatchling": [],
                "packaging": [],
                "pathspec": [],
                "pluggy": [],
            },
        },
        "installation_policy": {"max_download_bytes": gate.MAX_TOTAL_BYTES},
    }
    return lock, wheels, releases


def _refresh_artifact(
    lock: dict[str, Any], wheels: dict[str, bytes], releases: dict[str, bytes], name: str
) -> None:
    row = next(item for item in lock["artifacts"] if item["name"] == name)
    raw = wheels[row["filename"]]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        metadata = archive.read(f"{name.replace('-', '_')}-{row['version']}.dist-info/METADATA")
    parsed = gate.Parser().parsestr(metadata.decode())
    digest = hashlib.sha256(raw).hexdigest()
    row["size_bytes"] = len(raw)
    row["sha256"] = digest
    row["metadata_sha256"] = hashlib.sha256(metadata).hexdigest()
    row["requires_dist"] = parsed.get_all("Requires-Dist", [])
    row["pypi_release"]["pypi_file_sha256"] = digest
    row["pypi_release"]["pypi_file_size_bytes"] = len(raw)
    release = json.loads(releases[name])
    release["info"]["requires_dist"] = row["requires_dist"]
    release["urls"][0]["digests"]["sha256"] = digest
    release["urls"][0]["size"] = len(raw)
    releases[name] = json.dumps(release, sort_keys=True, separators=(",", ":")).encode()
    row["pypi_release"]["json_sha256"] = hashlib.sha256(releases[name]).hexdigest()


def test_complete_source_locked_universal_closure_is_accepted() -> None:
    lock, wheels, releases = _make_case()
    receipt = gate.validate_lock_and_wheels(lock, wheels, releases)
    assert receipt["status"] == "verified_portable_wheel_closure"
    assert receipt["distribution_count"] == len(lock["artifacts"]) == 4
    assert {edge["to"] for edge in receipt["active_edges"]} == {"packaging", "pathspec", "pluggy"}
    assert not any(edge["to"] == "coverage" for edge in receipt["active_edges"])


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_wheelhouse_membership_is_exact(mutation: str) -> None:
    lock, wheels, releases = _make_case()
    if mutation == "missing":
        wheels.pop(next(iter(wheels)))
    else:
        wheels["unlisted-9.9-py3-none-any.whl"] = b"unlisted"
    with pytest.raises(gate.BuildToolsInputError):
        gate.validate_lock_and_wheels(lock, wheels, releases)


def test_retained_quarantine_is_reverified_before_environment_setup(tmp_path: Path) -> None:
    lock, wheels, releases = _make_case()
    for filename, raw in wheels.items():
        (tmp_path / filename).write_bytes(raw)
    for name, raw in releases.items():
        version = next(row["version"] for row in lock["artifacts"] if row["name"] == name)
        (tmp_path / f"{name}-{version}.json").write_bytes(raw)

    proof = gate.validate_quarantine(lock, tmp_path)
    assert proof["status"] == "retained_quarantine_reverified_before_venv"
    assert proof["closure"]["status"] == "verified_portable_wheel_closure"

    wheel_path = tmp_path / next(iter(wheels))
    corrupted = bytearray(wheel_path.read_bytes())
    corrupted[0] ^= 1
    wheel_path.write_bytes(corrupted)
    with pytest.raises(gate.BuildToolsInputError, match="size or SHA-256"):
        gate.validate_quarantine(lock, tmp_path)


def test_active_transitive_dependency_cannot_be_removed_from_lock() -> None:
    lock, wheels, releases = _make_case()
    lock["artifacts"] = [row for row in lock["artifacts"] if row["name"] != "pathspec"]
    lock["closure"]["expected_distribution_set"].remove("pathspec==1.0.0")
    lock["closure"]["requested_extras_by_distribution"].pop("pathspec")
    wheels.pop("pathspec-1.0.0-py3-none-any.whl")
    releases.pop("pathspec")
    with pytest.raises(gate.BuildToolsInputError, match="active dependency closure is incomplete"):
        gate.validate_lock_and_wheels(lock, wheels, releases)


def test_metadata_edge_removal_with_consistent_outer_pins_fails_closure() -> None:
    lock, wheels, releases = _make_case()
    raw, _, _ = _wheel("hatchling", "1.0.0", ["packaging>=1.0"])
    wheels["hatchling-1.0.0-py3-none-any.whl"] = raw
    _refresh_artifact(lock, wheels, releases, "hatchling")
    with pytest.raises(gate.BuildToolsInputError, match="unreachable extra distributions"):
        gate.validate_lock_and_wheels(lock, wheels, releases)


def test_optional_extra_requires_its_transitive_wheel_closure() -> None:
    lock, wheels, releases = _make_case()
    lock["closure"]["requested_extras_by_distribution"]["pluggy"] = ["testing"]
    with pytest.raises(gate.BuildToolsInputError, match="active dependency closure is incomplete"):
        gate.validate_lock_and_wheels(lock, wheels, releases)


def test_unsupported_requirement_marker_is_not_treated_as_inactive() -> None:
    lock, wheels, releases = _make_case()
    raw, _, _ = _wheel("hatchling", "1.0.0", ["unknowndep; sys_platform == 'linux'"])
    wheels["hatchling-1.0.0-py3-none-any.whl"] = raw
    _refresh_artifact(lock, wheels, releases, "hatchling")
    with pytest.raises(gate.BuildToolsInputError, match="unsupported dependency marker"):
        gate.validate_lock_and_wheels(lock, wheels, releases)


@pytest.mark.parametrize("mutation", ["orphan-record", "corrupt-record"])
def test_record_is_exactly_equal_to_wheel_members_and_content(mutation: str) -> None:
    lock, wheels, releases = _make_case()
    raw, _, _ = _wheel(
        "hatchling",
        "1.0.0",
        _ROOT_REQUIREMENTS,
        orphan_record=mutation == "orphan-record",
        corrupt_record=mutation == "corrupt-record",
    )
    wheels["hatchling-1.0.0-py3-none-any.whl"] = raw
    _refresh_artifact(lock, wheels, releases, "hatchling")
    with pytest.raises(gate.BuildToolsInputError, match="RECORD"):
        gate.validate_lock_and_wheels(lock, wheels, releases)


def test_duplicate_lock_keys_and_changed_source_bytes_fail() -> None:
    duplicate = b'{"schema":"policyos.q2.portable-build-tool-wheel-lock.v1","schema":"other"}'
    with pytest.raises(gate.BuildToolsInputError, match="duplicate JSON"):
        gate.load_lock(duplicate, expected_sha256=hashlib.sha256(duplicate).hexdigest())
    source = b'{"schema":"policyos.q2.portable-build-tool-wheel-lock.v1"}'
    with pytest.raises(gate.BuildToolsInputError, match="source-bound digest"):
        gate.load_lock(source, expected_sha256="0" * 64)


def test_profile_requires_exact_pyproject_settings_and_source_hashes() -> None:
    profile = {
        "schema": gate.PROFILE_SCHEMA,
        "pyproject_path": "pyproject.toml",
        "helper_path": "tools/quality/validation/q2_build_tool_wheel_lock.py",
        "helper_sha256": "a" * 64,
        "lock_path": "docs/research/q2/builder-inputs/hatchling.json",
        "lock_sha256": "b" * 64,
        "build_system_requirement": "hatchling>=1.27.0",
        "build_backend": "hatchling.build",
        "root_requirement": "hatchling==1.27.0",
        "python_implementation": "CPython",
        "python_version": "3.14",
        "selected_extras": [],
        "wheel_tag": "py3-none-any",
        "index_policy": "offline-only",
        "install_policy": "verified-wheelhouse-no-deps-no-builds",
        "profile_scope": "q2-installed-wave-build-tools-only",
    }
    pyproject = (
        '[build-system]\nrequires = ["hatchling>=1.27.0"]\n'
        'build-backend = "hatchling.build"\n\n'
        "[tool.policyos.q2_build_tools]\n"
        f'profile_path = "{PROFILE_PATH}"\n'
    ).encode()
    profile_raw = (
        "\n".join(f"{key} = {json.dumps(value)}" for key, value in profile.items()) + "\n"
    ).encode()
    assert (
        gate.verify_pyproject_profile(
            pyproject,
            profile_raw=profile_raw,
            helper_path=profile["helper_path"],
            helper_sha256=profile["helper_sha256"],
            lock_path=profile["lock_path"],
            lock_sha256=profile["lock_sha256"],
        )
        == profile
    )

    changed_profile = profile_raw.replace(
        b'index_policy = "offline-only"', b'index_policy = "online"'
    )
    with pytest.raises(gate.BuildToolsInputError, match="profile"):
        gate.verify_pyproject_profile(
            pyproject,
            profile_raw=changed_profile,
            helper_path=profile["helper_path"],
            helper_sha256=profile["helper_sha256"],
            lock_path=profile["lock_path"],
            lock_sha256=profile["lock_sha256"],
        )


def test_pyproject_build_system_requirement_and_backend_are_bound_to_profile() -> None:
    pyproject = (_PRODUCT_ROOT / "pyproject.toml").read_bytes()
    profile_raw = (_PRODUCT_ROOT / PROFILE_PATH).read_bytes()
    profile = tomllib.loads(profile_raw.decode())
    helper_raw = (_PRODUCT_ROOT / profile["helper_path"]).read_bytes()
    lock_raw = (_PRODUCT_ROOT / profile["lock_path"]).read_bytes()
    gate.verify_pyproject_profile(
        pyproject,
        profile_raw=profile_raw,
        helper_path=profile["helper_path"],
        helper_sha256=hashlib.sha256(helper_raw).hexdigest(),
        lock_path=profile["lock_path"],
        lock_sha256=hashlib.sha256(lock_raw).hexdigest(),
    )
    build_requirement = b'requires = ["hatchling>=1.27.0"]'
    profile_requirement = b'build_system_requirement = "hatchling>=1.27.0"'
    assert pyproject.count(build_requirement) == 1
    assert profile_raw.count(profile_requirement) == 1

    changed_build_system = pyproject.replace(
        build_requirement, b'requires = ["hatchling>=1.26.0"]', 1
    )
    with pytest.raises(gate.BuildToolsInputError, match="build-system"):
        gate.verify_pyproject_profile(
            changed_build_system,
            profile_raw=profile_raw,
            helper_path=profile["helper_path"],
            helper_sha256=hashlib.sha256(helper_raw).hexdigest(),
            lock_path=profile["lock_path"],
            lock_sha256=hashlib.sha256(lock_raw).hexdigest(),
        )

    changed_profile = profile_raw.replace(
        profile_requirement, b'build_system_requirement = "hatchling>=1.26.0"', 1
    )
    with pytest.raises(gate.BuildToolsInputError, match="profile"):
        gate.verify_pyproject_profile(
            pyproject,
            profile_raw=changed_profile,
            helper_path=profile["helper_path"],
            helper_sha256=hashlib.sha256(helper_raw).hexdigest(),
            lock_path=profile["lock_path"],
            lock_sha256=hashlib.sha256(lock_raw).hexdigest(),
        )

    changed_pointer = pyproject.replace(
        f'profile_path = "{PROFILE_PATH}"'.encode(),
        b'profile_path = "architecture/packaging/other.toml"',
        1,
    )
    with pytest.raises(gate.BuildToolsInputError, match="profile path"):
        gate.verify_pyproject_profile(
            changed_pointer,
            profile_raw=profile_raw,
            helper_path=profile["helper_path"],
            helper_sha256=hashlib.sha256(helper_raw).hexdigest(),
            lock_path=profile["lock_path"],
            lock_sha256=hashlib.sha256(lock_raw).hexdigest(),
        )


def test_lock_closure_is_bound_to_exact_cpython_profile() -> None:
    lock, wheels, releases = _make_case()
    lock["portable_artifact_profile"]["target_python_marker_environment"]["implementation"] = "PyPy"
    with pytest.raises(gate.BuildToolsInputError, match=r"exactly CPython 3\.14"):
        gate.validate_lock_and_wheels(lock, wheels, releases)


@pytest.mark.parametrize("removed_member", ["profile", "lock", "helper"])
def test_source_archive_member_removal_preserving_profile_markers_stops_preparation(
    removed_member: str,
) -> None:
    pyproject = (_PRODUCT_ROOT / "pyproject.toml").read_bytes()
    profile_raw = (_PRODUCT_ROOT / PROFILE_PATH).read_bytes()
    profile = tomllib.loads(profile_raw.decode())
    helper_raw = (_PRODUCT_ROOT / profile["helper_path"]).read_bytes()
    lock_raw = (_PRODUCT_ROOT / profile["lock_path"]).read_bytes()
    source_blobs = {
        "pyproject.toml": pyproject,
        PROFILE_PATH: profile_raw,
        profile["helper_path"]: helper_raw,
        profile["lock_path"]: lock_raw,
    }
    archive_members = dict(source_blobs)
    called: list[str] = []
    admitted = gate.run_after_source_admission(
        profile,
        pyproject,
        lock_raw,
        source_blobs,
        archive_members,
        lambda _lock: called.append("prepare") or "prepared",
    )
    assert admitted["action_result"] == "prepared"
    assert called == ["prepare"]
    assert PROFILE_PATH in admitted["source_transport"]["members"]

    removed_path = {
        "profile": PROFILE_PATH,
        "lock": profile["lock_path"],
        "helper": profile["helper_path"],
    }[removed_member]
    removed_archive = {
        path: value for path, value in archive_members.items() if path != removed_path
    }
    called.clear()
    with pytest.raises(gate.BuildToolsInputError, match="transport set is missing"):
        gate.run_after_source_admission(
            profile,
            pyproject,
            lock_raw,
            source_blobs,
            removed_archive,
            lambda _lock: called.append("prepare"),
        )
    assert called == []

    extra_archive = dict(archive_members)
    extra_archive["docs/research/undeclared-build-tool-input.json"] = b"marker"
    with pytest.raises(gate.BuildToolsInputError, match="transport set is missing"):
        gate.run_after_source_admission(
            profile,
            pyproject,
            lock_raw,
            source_blobs,
            extra_archive,
            lambda _lock: called.append("prepare"),
        )
    assert called == []


@pytest.mark.parametrize("mutation", ["wrong-url-host", "wrong-size"])
def test_artifact_url_and_size_must_match_the_source_lock(mutation: str) -> None:
    lock, wheels, releases = _make_case()
    if mutation == "wrong-url-host":
        lock["artifacts"][0]["url"] = lock["artifacts"][0]["url"].replace(
            "files.pythonhosted.org", "unknown.invalid"
        )
    else:
        lock["artifacts"][0]["size_bytes"] += 1
    with pytest.raises(gate.BuildToolsInputError):
        gate.validate_lock_and_wheels(lock, wheels, releases)


class _FakeResponse:
    def __init__(self, url: str, raw: bytes, *, final_url: str | None = None) -> None:
        self.status = 200
        self.headers = {"Content-Length": str(len(raw))}
        self._url = final_url or url
        self._raw = io.BytesIO(raw)

    def geturl(self) -> str:
        return self._url

    def read(self, amount: int = -1) -> bytes:
        return self._raw.read(amount)

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_download_rejects_redirect_even_when_response_has_bytes(tmp_path: Path) -> None:
    lock, _, _ = _make_case()
    first = lock["artifacts"][0]

    def opener(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 30
        return _FakeResponse(url, b"x", final_url="https://unknown.invalid/redirect")

    with pytest.raises(gate.BuildToolsInputError, match="redirected"):
        gate.fetch_locked_inputs(lock, tmp_path / "quarantine", opener=opener)
    assert (tmp_path / "quarantine").is_dir()
    assert first["url"].startswith("https://files.pythonhosted.org/")


def test_download_cumulative_cap_fails_before_unbounded_reads(tmp_path: Path) -> None:
    lock, _, _ = _make_case()
    lock["installation_policy"]["max_download_bytes"] = 1

    def opener(url: str, timeout: int) -> _FakeResponse:
        return _FakeResponse(url, b"xx")

    with pytest.raises(gate.BuildToolsInputError, match="byte bound"):
        gate.fetch_locked_inputs(lock, tmp_path / "quarantine", opener=opener)


def _assert_requirements_text_matches_lock(text: str, lock: dict[str, Any]) -> None:
    expected: dict[str, tuple[str, str]] = {}
    for row in lock["artifacts"]:
        name = canonicalize_name(row["name"])
        assert name not in expected
        expected[name] = (row["version"], row["sha256"])

    parsed: dict[str, tuple[str, str]] = {}
    lines = text.splitlines()
    for line in lines:
        requirement_text, marker, digest = line.partition(" --hash=sha256:")
        assert marker == " --hash=sha256:"
        assert len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)

        requirement = Requirement(requirement_text)
        assert requirement.url is None
        assert requirement.marker is None
        assert not requirement.extras
        pins = list(requirement.specifier)
        assert len(pins) == 1 and pins[0].operator == "=="
        name = canonicalize_name(requirement.name)
        assert requirement_text == f"{name}=={pins[0].version}"
        assert name not in parsed
        parsed[name] = (pins[0].version, digest)

    assert len(lines) == len(lock["artifacts"])
    assert parsed == expected


def test_requirements_include_every_locked_hash_pinned_distribution() -> None:
    lock, _, _ = _make_case()
    text = gate.requirements_text(lock)
    _assert_requirements_text_matches_lock(text, lock)

    lines = text.splitlines()
    first_line = lines[0]
    first_requirement = first_line.partition(" --hash=sha256:")[0]
    with pytest.raises(AssertionError):
        _assert_requirements_text_matches_lock(text.replace(first_line, first_requirement, 1), lock)

    without_one_distribution = "\n".join(lines[1:]) + "\n"
    with pytest.raises(AssertionError):
        _assert_requirements_text_matches_lock(without_one_distribution, lock)

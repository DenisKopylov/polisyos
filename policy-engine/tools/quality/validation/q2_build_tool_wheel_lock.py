"""Validate and materialize the portable Q2 PEP 517 build-tool profile.

This source-owned helper accepts one exact source-bound lock, verifies the
entire official universal-wheel closure, and stages verified bytes for an
offline isolated build-tools environment. Host Python, OS, uv and wrapper
identity are observations recorded by the caller; they are not artifact IDs.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from email.parser import Parser
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

LOCK_SCHEMA = "policyos.q2.portable-build-tool-wheel-lock.v1"
PROFILE_SCHEMA = "policyos.q2.build-tools-profile.v1"
Q2_PROFILE_PATH = "architecture/packaging/q2_build_tools.toml"
MAX_TOTAL_BYTES = 1_048_576
MAX_RELEASE_JSON_BYTES = 128 * 1024
CHUNK_BYTES = 64 * 1024


class BuildToolsInputError(ValueError):
    """A source lock, wheel, upstream record, profile, or closure is invalid."""


class _HTTPResponse(Protocol):
    status: int | None
    headers: Mapping[str, str]

    def geturl(self) -> str: ...

    def read(self, size: int = -1) -> bytes: ...

    def __enter__(self) -> _HTTPResponse: ...

    def __exit__(self, *args: object) -> object: ...


def _no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BuildToolsInputError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_no_duplicate_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BuildToolsInputError(f"{label} is not strict UTF-8 JSON") from error
    if type(value) is not dict:
        raise BuildToolsInputError(f"{label} root must be an object")
    return value


def sha256_bytes(raw: bytes) -> str:
    """Return the lowercase SHA-256 digest of exact bytes."""
    return hashlib.sha256(raw).hexdigest()


def load_lock(raw: bytes, *, expected_sha256: str) -> dict[str, Any]:
    """Read a source-bound lock and reject duplicate keys or byte drift."""
    if not _is_sha256(expected_sha256) or sha256_bytes(raw) != expected_sha256:
        raise BuildToolsInputError("portable build-tool lock differs from its source-bound digest")
    lock = _json_object(raw, "portable build-tool lock")
    if lock.get("schema") != LOCK_SCHEMA:
        raise BuildToolsInputError("unsupported portable build-tool lock schema")
    return lock


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def verify_pyproject_profile(
    pyproject_raw: bytes,
    *,
    profile_raw: bytes,
    helper_path: str,
    helper_sha256: str,
    lock_path: str,
    lock_sha256: str,
) -> dict[str, Any]:
    """Require the architecture-owned Q2 profile to bind exact source bytes."""
    import tomllib

    if type(pyproject_raw) is not bytes or type(profile_raw) is not bytes:
        raise BuildToolsInputError("pyproject or Q2 profile source is missing or not byte-bound")
    try:
        document = tomllib.loads(pyproject_raw.decode("utf-8"))
        profile = tomllib.loads(profile_raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise BuildToolsInputError(
            "source pyproject.toml or Q2 profile is not valid UTF-8 TOML"
        ) from error
    tool = document.get("tool") if type(document) is dict else None
    policyos = tool.get("policyos") if type(tool) is dict else None
    profile_pointer = policyos.get("q2_build_tools") if type(policyos) is dict else None
    if type(profile_pointer) is not dict or profile_pointer != {"profile_path": Q2_PROFILE_PATH}:
        raise BuildToolsInputError(
            "pyproject Q2 build-tools profile path is absent or differs from source bindings"
        )
    expected = {
        "schema": PROFILE_SCHEMA,
        "pyproject_path": "pyproject.toml",
        "helper_path": helper_path,
        "helper_sha256": helper_sha256,
        "lock_path": lock_path,
        "lock_sha256": lock_sha256,
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
    if type(profile) is not dict or profile != expected:
        raise BuildToolsInputError(
            "architecture Q2 build-tools profile is absent, has extra fields, or "
            "differs from source bindings"
        )
    build_system = document.get("build-system")
    if type(build_system) is not dict or build_system != {
        "requires": [profile["build_system_requirement"]],
        "build-backend": profile["build_backend"],
    }:
        raise BuildToolsInputError(
            "pyproject build-system differs from the Q2 source-bound backend requirement"
        )
    if not _is_sha256(helper_sha256) or not _is_sha256(lock_sha256):
        raise BuildToolsInputError("Q2 profile helper and lock digests must be lowercase SHA-256")
    return profile


def verify_profile_lock(profile: dict[str, Any], lock: dict[str, Any]) -> None:
    """Reconcile pyproject's narrow offline profile with the complete source lock."""
    backend = lock.get("build_backend")
    artifact_profile = lock.get("portable_artifact_profile")
    if (
        type(backend) is not dict
        or type(artifact_profile) is not dict
        or backend.get("backend") != profile.get("build_backend")
        or backend.get("build_system_requirement") != profile.get("build_system_requirement")
        or backend.get("root_requirement") != profile.get("root_requirement")
        or backend.get("selected_extras") != profile.get("selected_extras")
        or artifact_profile.get("wheel_tag_required") != profile.get("wheel_tag")
        or artifact_profile.get("target_python_marker_environment")
        != {
            "implementation": profile.get("python_implementation"),
            "python_version": profile.get("python_version"),
        }
        or profile.get("index_policy") != "offline-only"
        or profile.get("install_policy") != "verified-wheelhouse-no-deps-no-builds"
    ):
        raise BuildToolsInputError("pyproject profile differs from source lock or offline policy")
    installation_policy = lock.get("installation_policy")
    if (
        type(installation_policy) is not dict
        or installation_policy.get("max_download_bytes") != MAX_TOTAL_BYTES
    ):
        raise BuildToolsInputError(
            "portable lock must use the reviewed cumulative artifact byte limit"
        )
    by_name, _ = _artifact_rows(lock)
    root_match = re.fullmatch(
        r"([A-Za-z0-9_.-]+)==([0-9]+(?:\.[0-9]+)*)",
        backend.get("root_requirement", ""),
    )
    if root_match is None:
        raise BuildToolsInputError("source lock backend root must be an exact pin")
    root_name = _canonical_name(root_match.group(1))
    if root_name not in by_name or by_name[root_name]["version"] != root_match.group(2):
        raise BuildToolsInputError("source lock backend root does not match a locked artifact")
    closure = lock.get("closure")
    expected_pins = closure.get("expected_distribution_set") if type(closure) is dict else None
    requested_extras = (
        closure.get("requested_extras_by_distribution") if type(closure) is dict else None
    )
    if (
        type(expected_pins) is not list
        or type(requested_extras) is not dict
        or set(requested_extras) != set(by_name)
        or backend.get("selected_extras") != requested_extras.get(root_name)
    ):
        raise BuildToolsInputError("source lock closure or requested extras are incomplete")
    expected_names: set[str] = set()
    for pin in expected_pins:
        if not isinstance(pin, str):
            raise BuildToolsInputError("source lock closure pin must be a string")
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9]+(?:\.[0-9]+)*)", pin)
        if match is None:
            raise BuildToolsInputError("source lock closure contains a non-exact pin")
        name = _canonical_name(match.group(1))
        if (
            name in expected_names
            or name not in by_name
            or by_name[name]["version"] != match.group(2)
        ):
            raise BuildToolsInputError("source lock closure pins differ from artifact identities")
        expected_names.add(name)
    if expected_names != set(by_name):
        raise BuildToolsInputError("source lock closure set differs from the locked artifact set")
    roots = closure.get("roots")
    if roots != [backend["root_requirement"]]:
        raise BuildToolsInputError("source lock closure roots differ from the selected backend")
    for name, values in requested_extras.items():
        if type(values) is not list or any(type(value) is not str for value in values):
            raise BuildToolsInputError(f"source lock selected extras are malformed for {name}")
        if not set(values).issubset(set(by_name[name].get("provides_extras", []))):
            raise BuildToolsInputError(f"source lock selects an undeclared extra for {name}")


def verify_source_transport(
    profile: dict[str, Any],
    source_blobs: dict[str, bytes],
    archive_members: dict[str, bytes],
) -> dict[str, Any]:
    """Require the complete project/profile/helper/lock set in Git and archive bytes."""
    project_path = profile.get("pyproject_path")
    helper_path = profile.get("helper_path")
    lock_path = profile.get("lock_path")
    if any(
        not isinstance(path, str)
        or not path
        or Path(path).is_absolute()
        or ".." in Path(path).parts
        for path in (project_path, Q2_PROFILE_PATH, helper_path, lock_path)
    ):
        raise BuildToolsInputError("source transport set is missing or has extra archive members")
    required = {project_path, Q2_PROFILE_PATH, helper_path, lock_path}
    if len(required) != 4 or set(source_blobs) != required or set(archive_members) != required:
        raise BuildToolsInputError("source transport set is missing or has extra archive members")
    for path in sorted(required):
        if type(source_blobs[path]) is not bytes or type(archive_members[path]) is not bytes:
            raise BuildToolsInputError(f"source transport member is not byte-bound: {path}")
        if source_blobs[path] != archive_members[path]:
            raise BuildToolsInputError(f"Git blob and source archive member differ: {path}")
    if sha256_bytes(source_blobs[helper_path]) != profile.get("helper_sha256") or sha256_bytes(
        source_blobs[lock_path]
    ) != profile.get("lock_sha256"):
        raise BuildToolsInputError("source transport helper or lock hash differs from Q2 profile")
    return {
        "status": "source_git_blob_archive_members_reconciled",
        "members": sorted(required),
        "byte_counts": {path: len(source_blobs[path]) for path in sorted(required)},
        "sha256": {path: sha256_bytes(source_blobs[path]) for path in sorted(required)},
    }


def run_after_source_admission(
    profile: dict[str, Any],
    pyproject_raw: bytes,
    lock_raw: bytes,
    source_blobs: dict[str, bytes],
    archive_members: dict[str, bytes],
    action: Callable[[dict[str, Any]], object],
) -> object:
    """Call the build preparation only after profile, Git/archive, lock and closure admission."""
    profile_raw = source_blobs.get(Q2_PROFILE_PATH)
    if type(profile_raw) is not bytes:
        raise BuildToolsInputError("source transport Q2 profile is missing or not byte-bound")
    validated_profile = verify_pyproject_profile(
        pyproject_raw,
        profile_raw=profile_raw,
        helper_path=profile.get("helper_path", ""),
        helper_sha256=profile.get("helper_sha256", ""),
        lock_path=profile.get("lock_path", ""),
        lock_sha256=profile.get("lock_sha256", ""),
    )
    if profile != validated_profile:
        raise BuildToolsInputError("supplied Q2 profile differs from parsed pyproject bindings")
    lock = load_lock(lock_raw, expected_sha256=validated_profile["lock_sha256"])
    transport = verify_source_transport(validated_profile, source_blobs, archive_members)
    verify_profile_lock(profile, lock)
    result = action(lock)
    return {"lock": lock, "source_transport": transport, "action_result": result}


def validate_quarantine(lock: dict[str, Any], wheelhouse: Path) -> dict[str, Any]:
    """Re-read a retained quarantine and revalidate every file before venv creation."""
    by_name, by_filename = _artifact_rows(lock)
    if wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise BuildToolsInputError("verified wheelhouse must be a regular directory")
    expected_names = set(by_filename) | {
        f"{name}-{row['version']}.json" for name, row in by_name.items()
    }
    entries = list(wheelhouse.iterdir())
    observed_names = {entry.name for entry in entries}
    if observed_names != expected_names:
        raise BuildToolsInputError("retained wheelhouse path set differs from complete lock")
    wheels: dict[str, bytes] = {}
    releases: dict[str, bytes] = {}
    for entry in entries:
        if entry.is_symlink() or not entry.is_file():
            raise BuildToolsInputError(
                f"retained wheelhouse member is not a regular file: {entry.name}"
            )
        if entry.name in by_filename:
            byte_limit = by_filename[entry.name]["size_bytes"]
        else:
            name = next(
                name
                for name, row in by_name.items()
                if entry.name == f"{name}-{row['version']}.json"
            )
            byte_limit = MAX_RELEASE_JSON_BYTES
        if entry.stat().st_size > byte_limit:
            raise BuildToolsInputError(
                f"retained wheelhouse member exceeds its locked byte bound: {entry.name}"
            )
        raw = entry.read_bytes()
        if entry.name in by_filename:
            wheels[entry.name] = raw
        else:
            name = next(
                name
                for name, row in by_name.items()
                if entry.name == f"{name}-{row['version']}.json"
            )
            releases[name] = raw
    closure = validate_lock_and_wheels(lock, wheels, releases)
    return {
        "status": "retained_quarantine_reverified_before_venv",
        "path": str(wheelhouse),
        "files": sorted(observed_names),
        "closure": closure,
    }


def _canonical_name(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise BuildToolsInputError("distribution name must be a nonempty string")
    return re.sub(r"[-_.]+", "-", value).lower()


def _version_tuple(value: str) -> tuple[int, ...]:
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value) is None:
        raise BuildToolsInputError(f"unsupported numeric version syntax: {value}")
    parts = [int(part) for part in value.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _compare_version(left: str, operator: str, right: str) -> bool:
    lhs, rhs = _version_tuple(left), _version_tuple(right)
    if operator == "==":
        return lhs == rhs
    if operator == ">=":
        return lhs >= rhs
    if operator == "<=":
        return lhs <= rhs
    if operator == ">":
        return lhs > rhs
    if operator == "<":
        return lhs < rhs
    return _unsupported_operator(operator)


def _unsupported_operator(operator: str) -> bool:
    raise BuildToolsInputError(f"unsupported version operator: {operator}")


def _satisfies_python(value: object, python_version: str) -> bool:
    if value is None:
        return True
    if not isinstance(value, str) or not value:
        raise BuildToolsInputError("Requires-Python must be a nonempty string or null")
    for clause in value.split(","):
        match = re.fullmatch(r"\s*(==|>=|<=|>|<)\s*([0-9]+(?:\.[0-9]+)*)\s*", clause)
        if match is None:
            raise BuildToolsInputError(f"unsupported Requires-Python clause: {clause}")
        operator, requested = match.groups()
        if not _compare_version(python_version, operator, requested):
            return False
    return True


def _active_requirement(
    requirement: str, *, python_version: str, implementation: str, extras: set[str]
) -> tuple[bool, str, str, str]:
    normalized = requirement.replace('"', "'")
    match = re.fullmatch(
        r"\s*([A-Za-z0-9_.-]+)\s*(?:(==|>=|<=|>|<)\s*([0-9]+(?:\.[0-9]+)*))?\s*(?:;\s*(.*))?\s*",
        normalized,
    )
    if match is None:
        raise BuildToolsInputError(f"unsupported Requires-Dist syntax: {requirement}")
    name, operator, requested, marker = match.groups()
    active = True
    if marker:
        extra_match = re.fullmatch(r"extra\s*==\s*'([^']+)'", marker)
        python_match = re.fullmatch(r"python_version\s*(==|>=|<=|>|<)\s*'([0-9]+\.[0-9]+)'", marker)
        implementation_match = re.fullmatch(
            r"platform_python_implementation\s*==\s*'([^']+)'", marker
        )
        if extra_match:
            active = extra_match.group(1) in extras
        elif python_match:
            marker_operator, marker_value = python_match.groups()
            active = _compare_version(python_version, marker_operator, marker_value)
        elif implementation_match:
            active = implementation_match.group(1) == implementation
        else:
            raise BuildToolsInputError(f"unsupported dependency marker: {marker}")
    return active, _canonical_name(name), operator or "", requested or ""


def _official_url(value: object, *, host: str, filename: str) -> str:
    if not isinstance(value, str):
        raise BuildToolsInputError("artifact URL must be a string")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != host
        or parsed.hostname != host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
        or parsed.path.rsplit("/", 1)[-1] != filename
        or "\\" in parsed.path
    ):
        raise BuildToolsInputError(f"URL is not the exact official HTTPS URL for {filename}")
    return value


def _artifact_rows(
    lock: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = lock.get("artifacts")
    if type(rows) is not list or not rows:
        raise BuildToolsInputError("lock must contain the complete nonempty artifact list")
    by_name: dict[str, dict[str, Any]] = {}
    by_filename: dict[str, dict[str, Any]] = {}
    for row in rows:
        if type(row) is not dict:
            raise BuildToolsInputError("artifact row must be an object")
        raw_name = row.get("name")
        if (
            not isinstance(raw_name, str)
            or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?", raw_name) is None
        ):
            raise BuildToolsInputError("artifact name is malformed")
        name = _canonical_name(raw_name)
        filename = row.get("filename")
        version = row.get("version")
        if (
            not isinstance(filename, str)
            or not isinstance(version, str)
            or re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", version) is None
            or filename != f"{re.sub(r'[-_.]+', '_', name)}-{version}-py3-none-any.whl"
            or name in by_name
            or filename in by_filename
            or not _is_sha256(row.get("sha256"))
            or type(row.get("size_bytes")) is not int
            or row["size_bytes"] <= 0
        ):
            raise BuildToolsInputError(
                "artifact identity, universal wheel name, digest, or size is invalid"
            )
        _official_url(row.get("url"), host="files.pythonhosted.org", filename=filename)
        release = row.get("pypi_release")
        if type(release) is not dict or not _is_sha256(release.get("json_sha256")):
            raise BuildToolsInputError(f"PyPI release witness is incomplete for {name}")
        if release.get("yanked") is not False:
            raise BuildToolsInputError(f"yanked artifacts are not admissible: {name}")
        _official_url(release.get("json_url"), host="pypi.org", filename="json")
        expected_release_url = f"https://pypi.org/pypi/{name}/{version}/json"
        if release["json_url"] != expected_release_url:
            raise BuildToolsInputError(f"PyPI release URL differs from canonical identity: {name}")
        if not _is_sha256(release.get("pypi_file_sha256")):
            raise BuildToolsInputError(f"PyPI digest witness is malformed for {name}")
        if type(release.get("pypi_file_size_bytes")) is not int:
            raise BuildToolsInputError(f"PyPI size witness is malformed for {name}")
        if (
            release["pypi_file_sha256"] != row["sha256"]
            or release["pypi_file_size_bytes"] != row["size_bytes"]
        ):
            raise BuildToolsInputError(
                f"PyPI wheel digest or size differs from portable lock for {name}"
            )
        for field in ("wheel_tags", "requires_dist", "provides_extras"):
            values = row.get(field)
            if type(values) is not list or any(type(value) is not str for value in values):
                raise BuildToolsInputError(f"artifact {field} must be a list of strings: {name}")
        requires_python = row.get("requires_python")
        if requires_python is not None and type(requires_python) is not str:
            raise BuildToolsInputError(f"artifact Requires-Python must be a string or null: {name}")
        if row["wheel_tags"] != ["py3-none-any"]:
            raise BuildToolsInputError(f"artifact lock does not declare a universal wheel: {name}")
        by_name[name] = row
        by_filename[filename] = row
    return by_name, by_filename


def _parse_wheel(raw: bytes, row: dict[str, Any]) -> dict[str, Any]:
    filename = row["filename"]
    if len(raw) != row["size_bytes"] or sha256_bytes(raw) != row["sha256"]:
        raise BuildToolsInputError(f"wheel byte size or SHA-256 differs from lock: {filename}")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as error:
        raise BuildToolsInputError(f"wheel is not a valid ZIP: {filename}") from error
    with archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise BuildToolsInputError(f"wheel has duplicate ZIP member: {filename}")
        file_names = {item.filename for item in infos if not item.is_dir()}
        for info in infos:
            pieces = info.filename.replace("\\", "/").split("/")
            mode = info.external_attr >> 16
            if (
                info.filename.startswith(("/", "\\"))
                or ".." in pieces
                or "\x00" in info.filename
                or (mode and (mode & 0o170000) not in (0, 0o100000, 0o040000))
            ):
                raise BuildToolsInputError(f"unsafe or special wheel ZIP member: {info.filename!r}")
        dist_infos = sorted({name.split("/", 1)[0] for name in file_names if ".dist-info/" in name})
        if len(dist_infos) != 1:
            raise BuildToolsInputError("wheel must contain exactly one .dist-info directory")
        dist_info = dist_infos[0]
        expected_dist_info = f"{re.sub(r'[-_.]+', '_', row['name'])}-{row['version']}.dist-info"
        if dist_info != expected_dist_info:
            raise BuildToolsInputError(f"wheel .dist-info identity differs from lock: {filename}")
        metadata_path = f"{dist_info}/METADATA"
        wheel_path = f"{dist_info}/WHEEL"
        record_path = f"{dist_info}/RECORD"
        if not {metadata_path, wheel_path, record_path}.issubset(file_names):
            raise BuildToolsInputError("wheel lacks required METADATA, WHEEL, or RECORD")
        metadata_raw = archive.read(metadata_path)
        metadata = Parser().parsestr(metadata_raw.decode("utf-8"))
        expected_extras = row.get("provides_extras")
        expected_requires = row.get("requires_dist")
        if (
            len(metadata.get_all("Name", [])) != 1
            or _canonical_name(metadata.get("Name", "")) != _canonical_name(row["name"])
            or len(metadata.get_all("Version", [])) != 1
            or metadata.get("Version") != row["version"]
            or len(metadata.get_all("Requires-Python", []))
            != (1 if row.get("requires_python") is not None else 0)
            or metadata.get("Requires-Python") != row.get("requires_python")
            or metadata.get_all("Provides-Extra", []) != expected_extras
            or metadata.get_all("Requires-Dist", []) != expected_requires
            or sha256_bytes(metadata_raw) != row.get("metadata_sha256")
        ):
            raise BuildToolsInputError(f"wheel METADATA differs from lock: {filename}")
        if not _satisfies_python(row.get("requires_python"), "3.14"):
            raise BuildToolsInputError(
                f"wheel does not support the locked CPython 3.14 profile: {filename}"
            )
        wheel_metadata = Parser().parsestr(archive.read(wheel_path).decode("utf-8"))
        tags = wheel_metadata.get_all("Tag", [])
        if (
            wheel_metadata.get_all("Wheel-Version", []) != ["1.0"]
            or wheel_metadata.get_all("Root-Is-Purelib", []) != ["true"]
            or tags != row.get("wheel_tags")
            or tags != ["py3-none-any"]
        ):
            raise BuildToolsInputError(f"wheel tag differs from universal lock: {filename}")
        record_rows = list(csv.reader(io.StringIO(archive.read(record_path).decode("utf-8"))))
        record: dict[str, list[str]] = {}
        for values in record_rows:
            if len(values) != 3 or values[0] in record:
                raise BuildToolsInputError(
                    f"wheel RECORD has malformed or duplicate rows: {filename}"
                )
            record[values[0]] = values[1:]
        if set(record) != file_names:
            raise BuildToolsInputError(
                f"wheel RECORD path set differs from ZIP members: {filename}"
            )
        for member in sorted(file_names):
            digest, size = record[member]
            contents = archive.read(member)
            if member == record_path:
                if digest or size:
                    raise BuildToolsInputError("wheel RECORD must omit its own digest and size")
                continue
            if not digest.startswith("sha256="):
                raise BuildToolsInputError(f"wheel RECORD is not SHA-256-bound: {member}")
            encoded = (
                base64.urlsafe_b64encode(hashlib.sha256(contents).digest()).rstrip(b"=").decode()
            )
            if digest != f"sha256={encoded}" or size != str(len(contents)):
                raise BuildToolsInputError(f"wheel RECORD digest or size mismatch: {member}")
        entry_points_path = f"{dist_info}/entry_points.txt"
        entry_points = (
            archive.read(entry_points_path).decode("utf-8")
            if entry_points_path in file_names
            else ""
        )
        return {
            "name": metadata.get("Name"),
            "version": metadata.get("Version"),
            "requires_python": metadata.get("Requires-Python"),
            "requires_dist": metadata.get_all("Requires-Dist", []),
            "provides_extras": metadata.get_all("Provides-Extra", []),
            "entry_points": entry_points,
            "wheel_tags": tags,
        }


def _verify_release(raw: bytes, row: dict[str, Any]) -> None:
    release = row["pypi_release"]
    if len(raw) > MAX_RELEASE_JSON_BYTES or sha256_bytes(raw) != release["json_sha256"]:
        raise BuildToolsInputError(f"PyPI release JSON bytes differ from lock: {row['name']}")
    value = _json_object(raw, f"PyPI release JSON for {row['name']}")
    info = value.get("info", {})
    if type(info) is not dict or _canonical_name(info.get("name", "")) != _canonical_name(
        row["name"]
    ):
        raise BuildToolsInputError("PyPI release identity Name differs from lock")
    if info.get("version") != row["version"]:
        raise BuildToolsInputError("PyPI release identity Version differs from lock")
    files = value.get("urls")
    if type(files) is not list:
        raise BuildToolsInputError("PyPI release response has no URL list")
    matches = [
        item for item in files if type(item) is dict and item.get("filename") == row["filename"]
    ]
    if len(matches) != 1:
        raise BuildToolsInputError("PyPI release response must have exactly one locked wheel")
    item = matches[0]
    digest_record = item.get("digests")
    if (
        type(digest_record) is not dict
        or item.get("url") != row["url"]
        or digest_record.get("sha256") != row["sha256"]
        or type(item.get("size")) is not int
        or item["size"] != row["size_bytes"]
        or item.get("yanked") is not False
        or info.get("requires_python") != row.get("requires_python")
    ):
        raise BuildToolsInputError(f"PyPI file record differs from lock: {row['name']}")
    raw_api_requires = info.get("requires_dist") or []
    if type(raw_api_requires) is not list or any(
        type(item) is not str for item in raw_api_requires
    ):
        raise BuildToolsInputError("PyPI Requires-Dist must be a list of strings")
    api_requires = [value.replace('"', "'") for value in raw_api_requires]
    wheel_requires = [value.replace('"', "'") for value in row.get("requires_dist", [])]
    if api_requires != wheel_requires:
        raise BuildToolsInputError(f"PyPI Requires-Dist differs from lock: {row['name']}")


def validate_lock_and_wheels(
    lock: dict[str, Any], wheels: dict[str, bytes], release_json: dict[str, bytes]
) -> dict[str, Any]:
    """Verify exact portable distribution bytes, upstream witness, RECORD and dependency closure."""
    if lock.get("schema") != LOCK_SCHEMA:
        raise BuildToolsInputError("unsupported portable build-tool lock schema")
    by_name, by_filename = _artifact_rows(lock)
    if set(wheels) != set(by_filename):
        raise BuildToolsInputError(
            f"wheelhouse set differs from lock; missing={sorted(set(by_filename) - set(wheels))}, "
            f"extra={sorted(set(wheels) - set(by_filename))}"
        )
    if set(release_json) != set(by_name):
        raise BuildToolsInputError("release JSON set differs from complete locked distribution set")
    profile = lock.get("portable_artifact_profile")
    if type(profile) is not dict:
        raise BuildToolsInputError("portable artifact profile is missing")
    target = profile.get("target_python_marker_environment")
    if type(target) is not dict or target != {
        "implementation": "CPython",
        "python_version": "3.14",
    }:
        raise BuildToolsInputError("portable lock target must be exactly CPython 3.14")
    backend = lock.get("build_backend")
    if type(backend) is not dict or backend.get("selected_extras") != []:
        raise BuildToolsInputError("Q2 build backend must select an explicit empty extra set")
    extras = lock.get("closure", {}).get("requested_extras_by_distribution")
    if type(extras) is not dict or set(extras) != set(by_name):
        raise BuildToolsInputError("every locked distribution must declare its requested extras")
    for name, selected in extras.items():
        if type(selected) is not list or any(type(value) is not str for value in selected):
            raise BuildToolsInputError(f"selected extras are malformed for {name}")
        declared = set(by_name[name].get("provides_extras", []))
        if not set(selected).issubset(declared):
            raise BuildToolsInputError(f"requested extra is not declared by {name}")
    parsed: dict[str, dict[str, Any]] = {}
    for name, row in by_name.items():
        _verify_release(release_json[name], row)
        parsed[name] = _parse_wheel(wheels[row["filename"]], row)
    root_requirement = backend.get("root_requirement")
    root_match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9]+(?:\.[0-9]+)*)", root_requirement or "")
    if root_match is None:
        raise BuildToolsInputError("build backend root must be an exact pin")
    root_name = _canonical_name(root_match.group(1))
    if root_name not in by_name or by_name[root_name]["version"] != root_match.group(2):
        raise BuildToolsInputError("locked build backend root is absent")
    if extras[root_name] != backend["selected_extras"]:
        raise BuildToolsInputError("root extras differ from the dedicated build-tool profile")
    closure = lock.get("closure")
    declared_set = closure.get("expected_distribution_set") if type(closure) is dict else None
    if type(declared_set) is not list:
        raise BuildToolsInputError("complete dependency closure set is absent")
    if closure.get("roots") != [backend["root_requirement"]]:
        raise BuildToolsInputError("dependency closure roots differ from the selected backend")
    expected_names: set[str] = set()
    for pin in declared_set:
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([0-9]+(?:\.[0-9]+)*)", pin or "")
        if match is None:
            raise BuildToolsInputError("dependency closure contains a non-exact version pin")
        name = _canonical_name(match.group(1))
        if (
            name in expected_names
            or name not in by_name
            or by_name[name]["version"] != match.group(2)
        ):
            raise BuildToolsInputError(
                "dependency closure pin is duplicate or differs from wheel rows"
            )
        expected_names.add(name)
    if expected_names != set(by_name):
        raise BuildToolsInputError(
            "wheel rows differ from the declared complete distribution closure"
        )
    visited: set[str] = set()
    active_edges: list[dict[str, str]] = []
    pending = [root_name]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        if current not in by_name:
            raise BuildToolsInputError(f"active dependency missing from wheel lock: {current}")
        visited.add(current)
        for requirement in parsed[current]["requires_dist"]:
            active, dependency, operator, requested = _active_requirement(
                requirement,
                python_version="3.14",
                implementation="CPython",
                extras=set(extras[current]),
            )
            if not active:
                continue
            if dependency not in by_name:
                raise BuildToolsInputError(
                    f"active dependency closure is incomplete: {current} -> {dependency}"
                )
            dep_version = by_name[dependency]["version"]
            if operator and not _compare_version(dep_version, operator, requested):
                raise BuildToolsInputError(
                    f"locked dependency does not satisfy {requirement}: {dep_version}"
                )
            active_edges.append({"from": current, "requirement": requirement, "to": dependency})
            pending.append(dependency)
    if visited != expected_names:
        raise BuildToolsInputError(
            f"unreachable extra distributions in wheel lock: {sorted(expected_names - visited)}"
        )
    entry = backend.get("installer_entry_point")
    if not isinstance(entry, str) or entry not in parsed[root_name]["entry_points"]:
        raise BuildToolsInputError(
            "locked Hatchling console entry point is absent from wheel METADATA"
        )
    return {
        "status": "verified_portable_wheel_closure",
        "distribution_count": len(visited),
        "wheel_filenames": sorted(by_filename),
        "active_edges": sorted(active_edges, key=lambda row: (row["from"], row["requirement"])),
        "selected_extras_by_distribution": extras,
        "host_profile": "separate per-run observation; not established by portable wheel bytes",
    }


def _read_limited(response: _HTTPResponse, *, byte_limit: int, total_remaining: int) -> bytes:
    status = response.status
    if status != 200:
        raise BuildToolsInputError(f"artifact response has HTTP status {status!r}, expected 200")
    content_length = response.headers.get("Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except (TypeError, ValueError) as error:
            raise BuildToolsInputError("artifact Content-Length is malformed") from error
        if declared < 0 or declared > byte_limit or declared > total_remaining:
            raise BuildToolsInputError("artifact Content-Length exceeds a configured byte bound")
    chunks: list[bytes] = []
    size = 0
    while True:
        block = response.read(min(CHUNK_BYTES, byte_limit - size + 1, total_remaining - size + 1))
        if not block:
            break
        size += len(block)
        if size > byte_limit or size > total_remaining:
            raise BuildToolsInputError("download exceeded its per-file or cumulative byte limit")
        chunks.append(block)
    raw = b"".join(chunks)
    if content_length is not None and len(raw) != int(content_length):
        raise BuildToolsInputError("downloaded byte count differs from HTTP Content-Length")
    return raw


def fetch_locked_inputs(
    lock: dict[str, Any],
    destination: Path,
    *,
    opener: Callable[..., _HTTPResponse] = urllib.request.urlopen,
) -> tuple[dict[str, bytes], dict[str, bytes], dict[str, Any]]:
    """Fetch exactly the locked PyPI records and wheels into fresh bounded quarantine."""
    if destination.exists() or destination.is_symlink():
        raise BuildToolsInputError(f"download destination must be absent: {destination}")
    destination.mkdir(parents=True, exist_ok=False)
    by_name, _by_filename = _artifact_rows(lock)
    wheels: dict[str, bytes] = {}
    releases: dict[str, bytes] = {}
    used = 0
    receipts: list[dict[str, Any]] = []
    installation_policy = lock.get("installation_policy")
    total_limit = (
        installation_policy.get("max_download_bytes") if type(installation_policy) is dict else None
    )
    if type(total_limit) is not int or not 0 < total_limit <= MAX_TOTAL_BYTES:
        raise BuildToolsInputError("lock must declare an explicit bounded total download size")
    for name, row in sorted(by_name.items()):
        for kind, url, limit, target, expected in (
            (
                "release-json",
                row["pypi_release"]["json_url"],
                MAX_RELEASE_JSON_BYTES,
                releases,
                row["pypi_release"]["json_sha256"],
            ),
            ("wheel", row["url"], row["size_bytes"], wheels, row["sha256"]),
        ):
            filename = row["filename"] if kind == "wheel" else f"{name}-{row['version']}.json"
            _official_url(
                url,
                host="files.pythonhosted.org" if kind == "wheel" else "pypi.org",
                filename=filename if kind == "wheel" else "json",
            )
            remaining = total_limit - used
            if remaining <= 0:
                raise BuildToolsInputError("cumulative official artifact download limit exhausted")
            response = opener(url, timeout=30)
            with response:
                final_url = response.geturl()
                if final_url != url:
                    raise BuildToolsInputError(
                        f"download redirected away from exact allowlisted URL: {final_url}"
                    )
                raw = _read_limited(response, byte_limit=limit, total_remaining=remaining)
            if sha256_bytes(raw) != expected:
                raise BuildToolsInputError(f"download digest differs from source lock: {filename}")
            used += len(raw)
            target[name if kind == "release-json" else row["filename"]] = raw
            retained = destination / filename
            retained.write_bytes(raw)
            if retained.read_bytes() != raw:
                raise BuildToolsInputError(f"quarantined artifact readback differs: {filename}")
            receipts.append(
                {
                    "kind": kind,
                    "name": name,
                    "url": url,
                    "bytes": len(raw),
                    "sha256": sha256_bytes(raw),
                    "retained_path": filename,
                }
            )
    result = validate_lock_and_wheels(lock, wheels, releases)
    quarantine = validate_quarantine(lock, destination)
    return (
        wheels,
        releases,
        {
            "closure": result,
            "quarantine_reverification": quarantine,
            "downloaded_bytes": used,
            "items": receipts,
            "quarantine": str(destination),
        },
    )


def requirements_text(lock: dict[str, Any]) -> str:
    """Render the complete explicitly locked no-deps wheel install requirement set."""
    by_name, _ = _artifact_rows(lock)
    lines = []
    for name, row in sorted(by_name.items()):
        lines.append(f"{name}=={row['version']} --hash=sha256:{row['sha256']}")
    return "\n".join(lines) + "\n"


def installed_probe_code(lock: dict[str, Any]) -> str:
    """Return a closed constant probe for origins, exact distributions and wrapper target."""
    expected = {_canonical_name(row["name"]): row["version"] for row in lock["artifacts"]}
    entry = lock["build_backend"]["installer_entry_point"]
    entry_definition = entry.split("=", 1)[1].strip()
    entry_module, entry_callable = entry_definition.split(":", 1)
    return f"""import hashlib
import importlib.metadata as metadata
import json
import sys
import sysconfig
from pathlib import Path

expected = {expected!r}
entry = {entry!r}
entry_module = {entry_module!r}
entry_callable = {entry_callable!r}
purelib = Path(sysconfig.get_paths()["purelib"]).resolve()
prefix = Path(sys.prefix).resolve()
sys.path.insert(0, str(purelib))
pth_files = sorted(str(path) for path in purelib.glob("*.pth"))
if pth_files:
    raise SystemExit("unexpected .pth file: " + repr(pth_files))
distributions = {{}}
origins = {{}}
for distribution in metadata.distributions(path=[str(purelib)]):
    name = (distribution.metadata.get("Name") or "").lower().replace("_", "-").replace(".", "-")
    if name in distributions:
        raise SystemExit("duplicate distribution: " + name)
    distributions[name] = distribution.version
    origins[name] = str(Path(distribution.locate_file("")).resolve())
if distributions != expected:
    raise SystemExit("installed set/version mismatch: " + repr(distributions))
if any(not Path(origin).is_relative_to(purelib) for origin in origins.values()):
    raise SystemExit("installed distribution origin escapes venv site-packages")
import hatchling
origin = Path(hatchling.__file__).resolve()
if not origin.is_relative_to(purelib):
    raise SystemExit("Hatchling origin escapes venv")
script = prefix / "bin" / "hatchling"
if not script.is_file() or script.is_symlink():
    raise SystemExit("entrypoint script missing/nonregular")
raw = script.read_bytes()
first = raw.splitlines()[0].decode("utf-8")
if not first.startswith("#!"):
    raise SystemExit("entrypoint lacks interpreter shebang")
target = Path(first[2:])
if not target.is_absolute() or target.resolve() != Path(sys.executable).resolve():
    raise SystemExit("entrypoint target differs from venv interpreter")
launcher_source = raw.decode("utf-8", errors="replace")
if entry_module not in launcher_source or entry_callable not in launcher_source:
    raise SystemExit("entrypoint does not implement locked console entry")
print(json.dumps({{"verified": True, "version": sys.version,
    "implementation": sys.implementation.name, "prefix": str(prefix),
    "purelib": str(purelib), "distributions": distributions, "origins": origins,
    "hatchling_origin": str(origin), "entrypoint": str(script),
    "entrypoint_sha256": hashlib.sha256(raw).hexdigest(),
    "entrypoint_target": str(target.resolve()), "pth_files": pth_files}}, sort_keys=True))
"""

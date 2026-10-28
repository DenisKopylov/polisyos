#!/usr/bin/env python3
"""Run the frozen Q2 source -> archive -> rebuilt wheel consumer wave."""

from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from datetime import UTC, datetime
from functools import partial
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from defusedxml import ElementTree as SafeET

if TYPE_CHECKING:
    from types import ModuleType


def _git_executable() -> str:
    """Resolve Git once per process without relying on a partial PATH command."""
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is not available on PATH")
    return str(Path(executable).resolve(strict=True))


HERE = Path(__file__).resolve().parent
HANDOFF_ROOT = HERE.parent
REQUIRED_PRODUCT = "policy-engine"
RESOURCE_CONTRACT_RELATIVE = "tools/quality/validation/packaged_resource_contract.py"
PROFILE_TARGET_ROOT = "polisyos/foundry/methods/catalog/causal/_dowhy_profile/"
RESOURCE_TARGET_ROOTS = (
    "polisyos/data_forge/domains/catalog/_resources/",
    "polisyos/foundry/methods/catalog/_resources/",
)
FORBIDDEN_ARCHIVE_SIBLING_ROOTS = (
    "policy-engine/data/dataset_catalog/",
    "policy-engine/architecture/production_quality/",
    "policy-engine/workers/dowhy-014/",
)
INSTALLED_ORIGIN_GATE_PATH = HERE / "installed_origin_gate_r4.py"
INSTALLED_ORIGIN_GATE_SHA256 = "8acde537d5588648e042384f38e18359e6b3a103d03e8af79fca226989ae6872"
BUILD_TOOL_HELPER_RELATIVE = "tools/quality/validation/q2_build_tool_wheel_lock.py"
BUILD_TOOL_PROFILE_RELATIVE = "architecture/packaging/q2_build_tools.toml"
BUILD_TOOL_LOCK_RELATIVE = (
    "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
    "q2-packaging/builder-inputs/hatchling-1.27.0-wheel-lock-r1.json"
)


class WaveFailure(RuntimeError):  # noqa: N818 - its class name is part of the Q2 receipt wire format.
    """Raised when a required frozen-wave invariant is not established."""


WaveFailureError = WaveFailure


def _failure_receipt_text(error: BaseException) -> str:
    """Render the established exception class name and message for Q2 receipts."""

    return f"{type(error).__name__}: {error}"


def exact_nonbool_count_matches(value: object, expected: object) -> bool:
    """Match JSON integer values only when both operands are exact non-boolean integers."""
    return type(value) is int and type(expected) is int and value == expected


def json_values_match_exactly(actual: object, expected: object) -> bool:
    """Compare JSON-shaped values without Python's bool/int or int/float aliases."""
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, dict):
        expected_dict = expected
        return actual.keys() == expected_dict.keys() and all(
            json_values_match_exactly(actual[key], expected_dict[key]) for key in actual
        )
    if isinstance(actual, list):
        expected_list = expected
        return len(actual) == len(expected_list) and all(
            json_values_match_exactly(left, right)
            for left, right in zip(actual, expected_list, strict=True)
        )
    return actual == expected


class HashingReader:
    """A read-only stream wrapper which hashes bytes consumed by tarfile."""

    def __init__(self, stream: object) -> None:
        self.stream = stream
        self.digest = hashlib.sha256()
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        data = self.stream.read(size)
        self.digest.update(data)
        self.bytes_read += len(data)
        return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(partial(stream.read, 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_installed_origin_gate() -> tuple[bytes, dict[str, Any]]:
    """Load the hash-bound stdlib gate for build preflight and isolated proof."""
    gate_bytes = _read_regular_without_symlink_components(
        INSTALLED_ORIGIN_GATE_PATH, "Q2 installed-origin gate"
    )[1]
    if sha256_bytes(gate_bytes) != INSTALLED_ORIGIN_GATE_SHA256:
        raise WaveFailure("Q2 installed-origin gate source differs from its frozen hash")
    namespace: dict[str, Any] = {"__name__": "e02_q2_installed_origin_gate_r3"}
    # S102: gate_bytes are hash-checked against the frozen installed-origin gate before evaluation.
    exec(compile(gate_bytes, str(INSTALLED_ORIGIN_GATE_PATH), "exec"), namespace)  # noqa: S102
    return gate_bytes, namespace


def _read_regular_without_symlink_components(
    path_value: str | Path, label: str
) -> tuple[Path, bytes]:
    """Read a regular file through a no-follow descriptor walk of every path component."""
    supplied = Path(path_value)
    if not supplied.is_absolute():
        raise WaveFailure(f"{label} path must be absolute: {supplied}")
    path = Path(os.path.abspath(supplied))
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise WaveFailure(f"{label} cannot be opened safely on this platform")
    if os.open not in os.supports_dir_fd or os.stat not in os.supports_dir_fd:
        raise WaveFailure(f"{label} cannot be opened safely with directory descriptors")
    parts = path.parts[1:]
    if path.anchor != os.sep or not parts:
        raise WaveFailure(f"{label} must name a file below the filesystem root: {path}")

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory_fds: list[int] = []
    directory_identities: list[tuple[int, int]] = []
    file_descriptor = -1
    try:
        current_fd = os.open(path.anchor, directory_flags)
        directory_fds.append(current_fd)
        for component in parts[:-1]:
            next_fd = os.open(component, directory_flags, dir_fd=current_fd)
            directory_fds.append(next_fd)
            named = os.stat(component, dir_fd=current_fd, follow_symlinks=False)
            opened = os.fstat(next_fd)
            if (
                not stat.S_ISDIR(named.st_mode)
                or not stat.S_ISDIR(opened.st_mode)
                or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                raise WaveFailure(
                    f"{label} contains a replaced or symlinked directory: {component}"
                )
            directory_identities.append((opened.st_dev, opened.st_ino))
            current_fd = next_fd

        final_name = parts[-1]
        before = os.stat(final_name, dir_fd=current_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise WaveFailure(f"{label} must be a regular non-symlink file: {path}")
        file_descriptor = os.open(final_name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=current_fd)
        with os.fdopen(file_descriptor, "rb") as stream:
            file_descriptor = -1
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
                before.st_dev,
                before.st_ino,
            ):
                raise WaveFailure(f"{label} changed before open: {path}")
            data = stream.read()
            after_open = os.fstat(stream.fileno())

        after_name = os.stat(final_name, dir_fd=current_fd, follow_symlinks=False)

        def file_signature(item: os.stat_result) -> tuple[int, int, int, int, int, int]:
            return (
                item.st_dev,
                item.st_ino,
                item.st_size,
                item.st_mtime_ns,
                item.st_ctime_ns,
                item.st_mode,
            )

        if (
            file_signature(before) != file_signature(opened)
            or file_signature(opened) != file_signature(after_open)
            or file_signature(before) != file_signature(after_name)
            or len(data) != after_open.st_size
        ):
            raise WaveFailure(f"{label} changed while being read: {path}")

        cursor = Path(path.anchor)
        for component_index, component in enumerate(parts):
            cursor = cursor / component
            observed = cursor.lstat()
            if stat.S_ISLNK(observed.st_mode):
                raise WaveFailure(f"{label} contains a symlinked path component: {cursor}")
            if component_index < len(directory_identities):
                expected_identity = directory_identities[component_index]
                if (
                    not stat.S_ISDIR(observed.st_mode)
                    or (observed.st_dev, observed.st_ino) != expected_identity
                ):
                    raise WaveFailure(f"{label} path changed while being read: {cursor}")
            elif file_signature(observed) != file_signature(before):
                raise WaveFailure(f"{label} path changed while being read: {cursor}")
        if path.resolve(strict=True) != path:
            raise WaveFailure(f"{label} path does not resolve to its supplied path: {path}")
        return path, data
    except WaveFailure:
        raise
    except (OSError, NotImplementedError, TypeError) as error:
        raise WaveFailure(
            f"{label} could not be read without following symlinks: {path}: {error}"
        ) from error
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        for descriptor in reversed(directory_fds):
            os.close(descriptor)


def load_verified_json_file(
    path_value: str | Path,
    expected_sha256: str,
    label: str,
    *,
    expected_schema_version: int | None = None,
) -> tuple[Path, dict[str, Any], str]:
    """Read one absolute, non-symlink JSON input bound by its exact SHA-256."""
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise WaveFailure(f"{label} SHA-256 must be 64 lowercase hexadecimal characters")
    path, data = _read_regular_without_symlink_components(path_value, label)
    actual_sha256 = sha256_bytes(data)
    if actual_sha256 != expected_sha256:
        raise WaveFailure(
            f"{label} content SHA-256 differs: expected={expected_sha256} actual={actual_sha256}"
        )
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WaveFailure(f"{label} is not valid UTF-8 JSON: {path}") from error
    if not isinstance(value, dict):
        raise WaveFailure(f"{label} JSON root must be an object: {path}")
    if expected_schema_version is not None and not exact_nonbool_count_matches(
        value.get("schema_version"), expected_schema_version
    ):
        raise WaveFailure(f"{label} has an unsupported schema version")
    return path, value, actual_sha256


def json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_command(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    log_stem: Path,
    check: bool = True,
    stream_output: bool = False,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command while retaining complete stdout/stderr, including on timeout."""
    if not argv or not Path(argv[0]).is_absolute() or not Path(argv[0]).is_file():
        raise WaveFailure("consumer command must start with an existing absolute executable")
    log_stem.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = log_stem.with_suffix(".stdout.txt")
    stderr_path = log_stem.with_suffix(".stderr.txt")
    timed_out = False
    try:
        if stream_output:
            with stdout_path.open("wb") as stdout_stream, stderr_path.open("wb") as stderr_stream:
                # S603: frozen consumer argv is explicit; shell execution is disabled.
                raw_result = subprocess.run(  # noqa: S603
                    argv,
                    cwd=cwd,
                    env=env,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                    check=False,
                    timeout=timeout_seconds,
                )
            result = subprocess.CompletedProcess(
                argv,
                raw_result.returncode,
                stdout_path.read_text(encoding="utf-8", errors="replace"),
                stderr_path.read_text(encoding="utf-8", errors="replace"),
            )
        else:
            # S603: frozen consumer argv is explicit; shell execution is disabled.
            result = subprocess.run(  # noqa: S603
                argv,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
            stdout_path.write_text(result.stdout, encoding="utf-8")
            stderr_path.write_text(result.stderr, encoding="utf-8")
    except subprocess.TimeoutExpired as error:
        timed_out = True
        if not stream_output:
            for path, partial in ((stdout_path, error.stdout), (stderr_path, error.stderr)):
                if isinstance(partial, str):
                    path.write_bytes(partial.encode("utf-8"))
                elif isinstance(partial, bytes):
                    path.write_bytes(partial)
                else:
                    path.write_bytes(b"")
        result = subprocess.CompletedProcess(
            argv,
            None,
            stdout_path.read_text(encoding="utf-8", errors="replace"),
            stderr_path.read_text(encoding="utf-8", errors="replace"),
        )
    json_write(
        log_stem.with_suffix(".command.json"),
        {
            "argv": argv,
            "cwd": str(cwd),
            "returncode": result.returncode,
            "stream_output": stream_output,
            "timeout_seconds": timeout_seconds,
            "timed_out": timed_out,
            "pythonpath_unset": "PYTHONPATH" not in env,
            "controlled_environment": {
                key: value
                for key, value in sorted(env.items())
                if key.startswith("E02_")
                or key
                in {
                    "OUT_DIR",
                    "UPLOAD",
                    "PYTHON_BIN",
                    "EXPECTED_SOURCE_SHA",
                    "UV_PROJECT_ENVIRONMENT",
                }
            },
        },
    )
    if timed_out:
        raise WaveFailure(
            f"Command timed out after {timeout_seconds}s; full output retained at {log_stem}"
        )
    if check and result.returncode:
        raise WaveFailure(
            f"Command failed ({result.returncode}); full output retained at {log_stem}"
        )
    return result


def clean_child_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PYTHON",
    ):
        env.pop(key, None)
    for key in tuple(env):
        if key.startswith("E02_"):
            env.pop(key)
    return env


def require_absolute_file(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise WaveFailure(f"{label} must be an absolute path: {value}")
    if not path.is_file():
        raise WaveFailure(f"{label} is unavailable: {path}")
    # Keep a venv's symlinked bin/python spelling; resolving it would escape the venv.
    return Path(os.path.abspath(path))


def git_text(repo: Path, *args: str) -> str:
    readonly_commands = {"rev-parse", "symbolic-ref", "status"}
    if not args or args[0] not in readonly_commands or any("\0" in arg for arg in args):
        raise WaveFailure("Git helper accepts only NUL-free read-only metadata queries")
    # S603: absolute Git is constrained to read-only metadata queries and receives separate argv.
    result = subprocess.run(  # noqa: S603
        [_git_executable(), "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    if result.returncode:
        raise WaveFailure(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def git_blob(repo: Path, source_sha: str, relative_path: str) -> bytes:
    """Read one regular tracked blob from the selected immutable source commit."""
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise WaveFailure("Git blob lookup requires a full source commit")
    path = PurePosixPath(relative_path)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise WaveFailure("Git blob lookup requires a safe repository-relative path")
    # S603: the selected commit and source path are data arguments; shell use is disabled.
    result = subprocess.run(  # noqa: S603
        [_git_executable(), "-C", str(repo), "cat-file", "blob", f"{source_sha}:{path.as_posix()}"],
        capture_output=True,
        check=False,
        shell=False,
    )
    if result.returncode:
        raise WaveFailure(f"frozen source blob is unavailable: {relative_path}")
    return result.stdout


def frozen_source_preflight(repo: Path, source_sha: str, source_tree: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise WaveFailure("--source-sha must be the actual full 40-character frozen commit")
    if not re.fullmatch(r"[0-9a-f]{40}", source_tree):
        raise WaveFailure("--source-tree must be the actual full 40-character frozen tree")
    head = git_text(repo, "rev-parse", "HEAD")
    if head != source_sha:
        raise WaveFailure(
            f"HEAD differs from the supplied freeze: HEAD={head}, supplied={source_sha}"
        )
    actual_tree = git_text(repo, "rev-parse", f"{source_sha}^{{tree}}")
    if actual_tree != source_tree:
        raise WaveFailure(
            f"commit tree differs from supplied freeze: actual="
            f"{actual_tree}"
            f", supplied="
            f"{source_tree}"
        )
    if git_text(repo, "symbolic-ref", "-q", "HEAD") == "":
        raise WaveFailure("frozen source checkout is detached; attach the intended branch first")
    tracked_changes = git_text(repo, "status", "--porcelain=v1", "--untracked-files=no")
    if tracked_changes:
        raise WaveFailure("tracked source changes remain after freeze; no build was started")


def run_frozen_gcp_archive_selector(
    *,
    repo: Path,
    frozen_product: Path,
    source_sha: str,
    source_tree: str,
    output: Path,
    python_bin: Path,
    log_stem: Path,
) -> dict[str, Any]:
    """Run the committed GCP selector from the exact attached frozen checkout."""
    frozen_source_preflight(repo, source_sha, source_tree)
    if not output.is_absolute() or output.exists():
        raise WaveFailure("GCP archive output must be a new absolute path")
    if not python_bin.is_absolute() or not python_bin.is_file():
        raise WaveFailure("GCP archive Python executable must be an existing absolute file")

    selector_relative = "ops/cloud/gcp/package_repo.sh"
    selector_git_path = f"{REQUIRED_PRODUCT}/{selector_relative}"
    selector_repo_path = repo / selector_git_path
    selector_frozen_path = frozen_product / selector_relative
    _, frozen_selector_bytes = _read_regular_without_symlink_components(
        selector_frozen_path, "frozen GCP package selector"
    )
    committed_selector_bytes = git_blob(repo, source_sha, selector_git_path)
    if frozen_selector_bytes != committed_selector_bytes:
        raise WaveFailure("frozen archive GCP selector differs from the selected Git blob")
    _, attached_selector_bytes = _read_regular_without_symlink_components(
        selector_repo_path, "attached GCP package selector"
    )
    if attached_selector_bytes != committed_selector_bytes:
        raise WaveFailure("attached GCP selector differs from the frozen Git blob")

    bash_value = shutil.which("bash")
    if bash_value is None:
        raise WaveFailure("bash executable is not available on PATH")
    bash = Path(bash_value).resolve(strict=True)
    package_env = clean_child_env()
    package_env.update(
        {
            "EXPECTED_SOURCE_SHA": source_sha,
            "OUT_DIR": str(output),
            "UPLOAD": "0",
            "PYTHON_BIN": str(python_bin),
        }
    )
    frozen_source_preflight(repo, source_sha, source_tree)
    result = run_command(
        [str(bash), str(selector_repo_path)],
        cwd=repo,
        env=package_env,
        log_stem=log_stem,
    )
    frozen_source_preflight(repo, source_sha, source_tree)
    _, attached_selector_after = _read_regular_without_symlink_components(
        selector_repo_path, "attached GCP package selector after execution"
    )
    if attached_selector_after != committed_selector_bytes:
        raise WaveFailure("attached GCP selector changed while creating the archive")

    archive_path = one_matching_file(output, "policy-engine-*.tar.gz")
    source_abbrev = git_text(repo, "rev-parse", "--short", source_sha)
    if not re.fullmatch(
        rf"policy-engine-\d{{8}}-\d{{6}}-{re.escape(source_abbrev)}\.tar\.gz",
        archive_path.name,
    ):
        raise WaveFailure("GCP archive filename does not identify the frozen source commit")
    source_line = f"Created {archive_path} from committed source {source_sha}"
    if not result.stdout.splitlines() or result.stdout.splitlines()[-1] != source_line:
        raise WaveFailure("GCP selector did not report the exact frozen source commit")

    member_relatives = (
        "README.md",
        "pyproject.toml",
        "hatch.toml",
        "uv.lock",
        selector_relative,
    )
    verified_members: dict[str, dict[str, Any]] = {}
    with tarfile.open(archive_path, "r:*") as archive:
        for relative in member_relatives:
            archive_name = f"{REQUIRED_PRODUCT}/{relative}"
            frozen_member_path = frozen_product / relative
            _, frozen_member_bytes = _read_regular_without_symlink_components(
                frozen_member_path, f"frozen GCP selector input {relative}"
            )
            committed_member_bytes = git_blob(repo, source_sha, archive_name)
            if frozen_member_bytes != committed_member_bytes:
                raise WaveFailure(
                    f"frozen archive GCP selector input differs from the selected Git blob: "
                    f"{relative}"
                )
            try:
                member = archive.getmember(archive_name)
            except KeyError as error:
                raise WaveFailure(
                    f"GCP archive omitted frozen selector input: {archive_name}"
                ) from error
            if not member.isfile():
                raise WaveFailure(
                    f"GCP archive selector input is not a regular file: {archive_name}"
                )
            stream = archive.extractfile(member)
            if stream is None:
                raise WaveFailure(f"cannot read GCP archive selector input: {archive_name}")
            with stream:
                archive_bytes = stream.read()
            if archive_bytes != committed_member_bytes:
                raise WaveFailure(
                    f"GCP archive member differs from the selected Git blob: {archive_name}"
                )
            verified_members[archive_name] = {
                "bytes": len(archive_bytes),
                "sha256": sha256_bytes(archive_bytes),
            }

    return {
        "source_sha": source_sha,
        "source_tree": source_tree,
        "source_abbrev": source_abbrev,
        "selector_path": selector_git_path,
        "selector_sha256": sha256_bytes(committed_selector_bytes),
        "source_line": source_line,
        "archive_path": str(archive_path),
        "archive_sha256": sha256_file(archive_path),
        "verified_members": verified_members,
    }


def safe_relative_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise WaveFailure(f"unsafe archive member path: {name!r}")
    return path


def load_resource_contract_module(frozen_product: Path) -> ModuleType:
    """Load the source-owned reusable resource contract from the frozen archive."""
    helper_path = frozen_product / RESOURCE_CONTRACT_RELATIVE
    resolved, _ = _read_regular_without_symlink_components(
        helper_path, "runtime resource contract helper"
    )
    spec = importlib.util.spec_from_file_location("e02_q2_packaged_resource_contract", resolved)
    if spec is None or spec.loader is None:
        raise WaveFailure("cannot load source-owned runtime resource contract helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "validate_manifest_resources", None)):
        raise WaveFailure("runtime resource contract helper has no manifest validator")
    return module


def source_resource_inventory(
    python: Path,
    frozen_product: Path,
    run_root: Path,
    log_dir: Path,
) -> dict[str, Any]:
    """Derive the complete resource set by importing runtime owners from the archive."""
    helper_path = frozen_product / RESOURCE_CONTRACT_RELATIVE
    result = run_command(
        [
            str(python),
            "-I",
            str(helper_path),
            "source",
            "--product-root",
            str(frozen_product),
        ],
        cwd=run_root,
        env=clean_child_env(),
        log_stem=log_dir / "source-runtime-resource-inventory",
    )
    try:
        inventory = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise WaveFailure("source runtime resource helper did not emit valid JSON") from error
    if (
        type(inventory) is not dict
        or inventory.get("schema") != "polisyos.packaged-resource-contract.v1"
        or type(inventory.get("assets")) is not list
        or not inventory["assets"]
    ):
        raise WaveFailure("source runtime resource helper returned an incomplete inventory")
    return inventory


def extract_git_archive(
    repo: Path, source_sha: str, destination: Path, log_dir: Path
) -> dict[str, Any]:
    """Extract the selected committed product without storing a second full tar."""
    destination.mkdir(parents=True, exist_ok=False)
    command = [_git_executable(), "-C", str(repo), "archive", source_sha, "--", REQUIRED_PRODUCT]
    # S603: this reads one immutable archive with absolute Git and no shell.
    process = subprocess.Popen(  # noqa: S603
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False
    )
    if not (process.stdout is not None):
        raise AssertionError()
    if not (process.stderr is not None):
        raise AssertionError()
    reader = HashingReader(process.stdout)
    member_count = 0
    file_count = 0
    try:
        with tarfile.open(fileobj=reader, mode="r|") as archive:
            for member in archive:
                member_count += 1
                relative = safe_relative_member(member.name)
                if relative.parts[0] != REQUIRED_PRODUCT:
                    raise WaveFailure(
                        f"git archive emitted a path outside {REQUIRED_PRODUCT}: {member.name}"
                    )
                tail = PurePosixPath(*relative.parts[1:])
                if not tail.parts:
                    continue
                target = destination.joinpath(*tail.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise WaveFailure(
                        f"git archive contains unsupported member kind: {member.name}"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = archive.extractfile(member)
                if payload is None:
                    raise WaveFailure(f"unable to read git archive member: {member.name}")
                with payload, target.open("wb") as output:
                    shutil.copyfileobj(payload, output, length=1024 * 1024)
                target.chmod(member.mode & 0o777)
                file_count += 1
        while reader.read(1024 * 1024):
            pass
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        returncode = process.wait()
        (log_dir / "git-archive.stderr.txt").write_text(stderr, encoding="utf-8")
        json_write(
            log_dir / "git-archive.json",
            {
                "argv": command,
                "returncode": returncode,
                "sha256": reader.digest.hexdigest(),
                "archive_bytes": reader.bytes_read,
                "members": member_count,
                "regular_files": file_count,
                "extracted_to": str(destination),
            },
        )
        if returncode:
            raise WaveFailure(f"git archive failed ({returncode}); stderr retained")
        return {"sha256": reader.digest.hexdigest(), "archive_bytes": reader.bytes_read}
    except BaseException as error:
        if process.poll() is None:
            process.kill()
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        process.wait()
        (log_dir / "git-archive.stderr.txt").write_text(stderr, encoding="utf-8")
        json_write(
            log_dir / "git-archive-partial.json",
            {
                "argv": command,
                "failure": f"{type(error).__name__}: {error}",
                "partial_sha256": reader.digest.hexdigest(),
                "archive_bytes_read": reader.bytes_read,
                "members_seen": member_count,
                "extracted_to": str(destination),
            },
        )
        raise


def extract_frozen_product(
    repo: Path, source_sha: str, source_root: Path, log_dir: Path
) -> tuple[dict[str, Any], Path]:
    """Extract the frozen product at its package path below the wave source root."""
    source_root.mkdir(parents=True, exist_ok=False)
    frozen_product = source_root / REQUIRED_PRODUCT
    archive_receipt = extract_git_archive(repo, source_sha, frozen_product, log_dir)
    return archive_receipt, frozen_product


def read_asset_manifest(
    frozen_product: Path,
    manifest: dict[str, Any],
    owner_inventory: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not exact_nonbool_count_matches(manifest.get("schema_version"), 1):
        raise WaveFailure("primary manifest has an unsupported schema version")
    candidate = manifest.get("candidate_baseline")
    if not isinstance(candidate, dict):
        raise WaveFailure("manifest omits its candidate asset baseline")
    assets = candidate.get("force_include_assets")
    declared_count = candidate.get("force_include_count")
    if not isinstance(assets, list) or not assets:
        raise WaveFailure("manifest force-include resources must be a nonempty complete list")
    if not exact_nonbool_count_matches(declared_count, len(assets)):
        raise WaveFailure("manifest force-include count differs from its complete resource list")
    config = tomllib.loads((frozen_product / "hatch.toml").read_text(encoding="utf-8"))
    force_include = config["build"]["targets"]["wheel"]["force-include"]
    expected_mapping: dict[str, str] = {}
    expected_targets: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise WaveFailure("manifest force-include entries must be objects")
        source = asset.get("source")
        archive = asset.get("archive")
        wheel = asset.get("wheel")
        byte_count = asset.get("bytes")
        digest = asset.get("sha256")
        if not all(isinstance(value, str) and value for value in (source, archive, wheel)):
            raise WaveFailure("manifest force-include paths must be nonempty strings")
        source_member = safe_relative_member(source)
        wheel_member = safe_relative_member(wheel)
        if source_member.as_posix() != source or wheel_member.as_posix() != wheel:
            raise WaveFailure("manifest force-include paths must be canonical relative paths")
        if source in expected_mapping or wheel in expected_targets:
            raise WaveFailure("manifest force-include source and wheel targets must be unique")
        if archive != f"policy-engine/{source}":
            raise WaveFailure(f"manifest GCP archive path does not match source path: {source}")
        if not exact_nonbool_count_matches(byte_count, byte_count) or byte_count < 0:
            raise WaveFailure(f"manifest asset byte count is invalid: {source}")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise WaveFailure(f"manifest asset SHA-256 is invalid: {source}")
        expected_mapping[source] = wheel
        expected_targets.add(wheel)
    if not isinstance(force_include, dict) or force_include != expected_mapping:
        raise WaveFailure(
            "frozen hatch.toml force-include map differs from the complete content-bound manifest; "
            "reconcile the manifest before running the wave"
        )
    if owner_inventory is not None:
        contract = load_resource_contract_module(frozen_product)
        try:
            contract.validate_manifest_resources(
                owner_inventory,
                assets,
                force_include,
            )
            contract.verify_source_resource_bytes(frozen_product, owner_inventory["assets"])
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise WaveFailure(f"runtime-owned resource contract failed: {error}") from error
    for asset in assets:
        path = frozen_product / asset["source"]
        if not path.is_file() or path.is_symlink():
            raise WaveFailure(f"force-include source is absent or symlinked: {asset['source']}")
        data = path.read_bytes()
        observed = {"bytes": len(data), "sha256": sha256_bytes(data)}
        expected = {key: asset[key] for key in ("bytes", "sha256")}
        if not exact_nonbool_count_matches(
            asset.get("bytes"), len(data)
        ) or not json_values_match_exactly(observed, expected):
            raise WaveFailure(
                f"frozen asset differs from candidate baseline; reconcile first: {asset['source']} "
                f"expected={expected} actual={observed}"
            )
    return manifest, assets


def profile_target_members(assets: list[dict[str, Any]]) -> set[str]:
    return {asset["wheel"] for asset in assets if asset["wheel"].startswith(PROFILE_TARGET_ROOT)}


def verify_wheel(wheel_path: Path, assets: list[dict[str, Any]]) -> dict[str, Any]:
    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())
        if len(names) != len(wheel.namelist()):
            raise WaveFailure(f"wheel has duplicate member names: {wheel_path}")
        rows = {}
        for asset in assets:
            target = asset["wheel"]
            if target not in names:
                raise WaveFailure(f"wheel omitted force-include target: {target} in {wheel_path}")
            data = wheel.read(target)
            observed = {"bytes": len(data), "sha256": sha256_bytes(data)}
            expected = {key: asset[key] for key in ("bytes", "sha256")}
            if observed != expected:
                raise WaveFailure(
                    f"wheel asset differs: {wheel_path}!{target}: {observed} != {expected}"
                )
            rows[target] = observed
        actual_profile = {
            name
            for name in names
            if name.startswith(PROFILE_TARGET_ROOT) and not name.endswith("/")
        }
        if actual_profile != profile_target_members(assets):
            raise WaveFailure(
                f"wheel DoWhy profile target has undeclared/missing members: "
                f"actual={sorted(actual_profile)} expected={sorted(profile_target_members(assets))}"
            )
        return {"path": str(wheel_path), "sha256": sha256_file(wheel_path), "assets": rows}


def verify_tar_assets(
    archive_path: Path,
    assets: list[dict[str, Any]],
    *,
    member_prefix: str,
    exact_force_directories: bool,
) -> dict[str, Any]:
    with tarfile.open(archive_path, "r:*") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(set(names)) != len(names):
            raise WaveFailure(f"archive repeats member names: {archive_path}")
        regular = {member.name: member for member in members if member.isfile()}
        directories = [member for member in members if member.isdir()]
        special = [member for member in members if not member.isfile() and not member.isdir()]
        if member_prefix == "policy-engine/" and special:
            raise WaveFailure(
                f"GCP archive contains symlink/special members: "
                f"{[(member.name, member.type) for member in special]}"
            )
        names_by_source = {asset["source"]: f"{member_prefix}{asset['source']}" for asset in assets}
        missing = sorted(
            archive_name for archive_name in names_by_source.values() if archive_name not in regular
        )
        if missing:
            raise WaveFailure(
                f"archive omitted force-include sources: {missing} from {archive_path}"
            )
        rows = {}
        for asset in assets:
            archive_name = names_by_source[asset["source"]]
            member = regular[archive_name]
            stream = archive.extractfile(member)
            if stream is None:
                raise WaveFailure(f"cannot read archive asset {member.name} from {archive_path}")
            with stream:
                data = stream.read()
            observed = {"bytes": len(data), "sha256": sha256_bytes(data)}
            expected = {key: asset[key] for key in ("bytes", "sha256")}
            if observed != expected:
                raise WaveFailure(
                    f"archive asset differs: {archive_path}:{member.name}: {observed} != {expected}"
                )
            rows[member.name] = observed
        if exact_force_directories:
            for root in FORBIDDEN_ARCHIVE_SIBLING_ROOTS:
                expected = {
                    asset["archive"] for asset in assets if asset["archive"].startswith(root)
                }
                observed = {name for name in regular if name.startswith(root)}
                if observed != expected:
                    raise WaveFailure(
                        f"archive selected undeclared sibling(s) under {root}: "
                        f"actual={sorted(observed)} expected={sorted(expected)}"
                    )
        return {
            "path": str(archive_path),
            "sha256": sha256_file(archive_path),
            "archive_member_denominator": {
                "members": len(members),
                "regular_files": len(regular),
                "directories": len(directories),
                "symlinks_or_specials": len(special),
            },
            "force_include_assets": rows,
            "exact_force_directories": exact_force_directories,
            "member_prefix": member_prefix,
        }


def one_matching_file(directory: Path, pattern: str) -> Path:
    found = sorted(directory.glob(pattern))
    if len(found) != 1 or not found[0].is_file():
        raise WaveFailure(f"expected exactly one {pattern} under {directory}; found {found}")
    return found[0]


def product_root_from_sdist(
    archive_path: Path,
    destination: Path,
    source_product: Path,
    expected_prefix: str,
) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    seen_prefixes: set[str] = set()
    seen_files: set[str] = set()
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive:
            relative = safe_relative_member(member.name)
            seen_prefixes.add(relative.parts[0])
            if relative.parts[0] != expected_prefix:
                raise WaveFailure(
                    f"unexpected sdist root: {member.name}, wanted {expected_prefix}/"
                )
            tail = PurePosixPath(*relative.parts[1:])
            if not tail.parts:
                continue
            target = destination.joinpath(*tail.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise WaveFailure(f"sdist has unsupported member kind: {member.name}")
            if tail.as_posix() in seen_files:
                raise WaveFailure(f"sdist repeats a member: {member.name}")
            seen_files.add(tail.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = archive.extractfile(member)
            if stream is None:
                raise WaveFailure(f"cannot read sdist member: {member.name}")
            temporary = target.with_name(target.name + ".q2-writing")
            digest = hashlib.sha256()
            hardlinked = False
            try:
                with stream, temporary.open("wb") as output:
                    for block in iter(partial(stream.read, 1024 * 1024), b""):
                        digest.update(block)
                        output.write(block)
                original = source_product / tail
                if (
                    original.is_file()
                    and not original.is_symlink()
                    and sha256_file(original) == digest.hexdigest()
                    and (original.stat().st_mode & 0o777) == (member.mode & 0o777)
                ):
                    os.link(original, target)
                    temporary.unlink()
                    hardlinked = True
                else:
                    os.replace(temporary, target)
                if not hardlinked:
                    target.chmod(member.mode & 0o777)
            except BaseException:
                # Keep any incomplete member for diagnosis; do not clean run scratch on failure.
                raise
    if seen_prefixes != {expected_prefix}:
        raise WaveFailure(f"sdist has unexpected top-level roots: {sorted(seen_prefixes)}")
    return destination


def product_root_from_gcp(archive_path: Path, destination: Path, source_product: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    expected_prefix = "policy-engine"
    seen_prefixes: set[str] = set()
    seen_files: set[str] = set()
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive:
            relative = safe_relative_member(member.name)
            seen_prefixes.add(relative.parts[0])
            if relative.parts[0] != expected_prefix:
                raise WaveFailure(f"unexpected GCP archive root: {member.name}")
            tail = PurePosixPath(*relative.parts[1:])
            if not tail.parts:
                continue
            target = destination.joinpath(*tail.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise WaveFailure(f"GCP archive has unsupported member kind: {member.name}")
            if tail.as_posix() in seen_files:
                raise WaveFailure(f"GCP archive repeats a member: {member.name}")
            seen_files.add(tail.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = archive.extractfile(member)
            if stream is None:
                raise WaveFailure(f"cannot read GCP archive member: {member.name}")
            temporary = target.with_name(target.name + ".q2-writing")
            digest = hashlib.sha256()
            hardlinked = False
            try:
                with stream, temporary.open("wb") as output:
                    for block in iter(partial(stream.read, 1024 * 1024), b""):
                        digest.update(block)
                        output.write(block)
                original = source_product / tail
                if (
                    original.is_file()
                    and not original.is_symlink()
                    and sha256_file(original) == digest.hexdigest()
                    and (original.stat().st_mode & 0o777) == (member.mode & 0o777)
                ):
                    os.link(original, target)
                    temporary.unlink()
                    hardlinked = True
                else:
                    os.replace(temporary, target)
                if not hardlinked:
                    target.chmod(member.mode & 0o777)
            except BaseException:
                # Keep any incomplete member for diagnosis; do not clean run scratch on failure.
                raise
    if seen_prefixes != {expected_prefix}:
        raise WaveFailure(f"GCP archive has unexpected top-level roots: {sorted(seen_prefixes)}")
    return destination


def run_build(
    uv: str,
    build_python: Path,
    product: Path,
    output: Path,
    *,
    wheel: bool,
    sdist: bool,
    log_dir: Path,
    env: dict[str, str],
) -> Path | tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=False)
    argv = [uv, "build", "--offline", "--no-build-isolation", "--python", str(build_python)]
    if wheel:
        argv.append("--wheel")
    if sdist:
        argv.append("--sdist")
    argv.extend(["--out-dir", str(output)])
    run_command(argv, cwd=product, env=env, log_stem=log_dir / output.name)
    wheel_path = one_matching_file(output, "*.whl") if wheel else None
    sdist_path = one_matching_file(output, "*.tar.gz") if sdist else None
    if wheel and sdist:
        if not (wheel_path):
            raise AssertionError()
        if not (sdist_path):
            raise AssertionError()
        return wheel_path, sdist_path
    if wheel:
        if not (wheel_path):
            raise AssertionError()
        return wheel_path
    if sdist_path:
        return sdist_path
    raise WaveFailure("no build target requested")


def interpreter_info(python: Path, *, log_dir: Path, name: str) -> dict[str, Any]:
    """Inspect a venv without importing `site` or executing any `.pth` file."""
    code = (
        "import json, sys, sysconfig; "
        "print(json.dumps({'implementation': sys.implementation.name, "
        "'version': list(sys.version_info[:3]), 'executable': sys.executable, "
        "'abi': sysconfig.get_config_var('SOABI'), "
        "'cache_tag': sys.implementation.cache_tag, "
        "'base_executable': sys._base_executable, 'prefix': sys.prefix, "
        "'purelib': sysconfig.get_paths()['purelib']}))"
    )
    if not python.is_absolute() or not python.is_file():
        raise WaveFailure("interpreter inspection requires an absolute existing Python executable")
    # S603: executable is the validated Python path and code is a constant inspection probe.
    result = subprocess.run(  # noqa: S603
        [str(python.resolve()), "-S", "-c", code],
        env=clean_child_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    (log_dir / f"{name}-info.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (log_dir / f"{name}-info.stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise WaveFailure(f"unable to inspect {name} interpreter; output retained")
    info = json.loads(result.stdout)
    venv_root = python.parent.parent
    if (venv_root / "pyvenv.cfg").is_file():
        version = info["version"]
        info["prefix"] = str(venv_root)
        info["purelib"] = str(
            venv_root / "lib" / f"python{version[0]}.{version[1]}" / "site-packages"
        )
    info["hatchling"] = distribution_version(Path(info["purelib"]), "hatchling")
    return info


def distribution_version(site: Path, distribution: str) -> str | None:
    prefix = distribution.replace("-", "_").lower() + "-"
    for metadata in sorted(site.glob("*.dist-info/METADATA")):
        if not metadata.parent.name.lower().startswith(prefix):
            continue
        for line in metadata.read_text(encoding="utf-8").splitlines():
            if line.startswith("Version: "):
                return line.removeprefix("Version: ").strip()
    return None


def configure_build_env(
    uv: str,
    base_python: Path,
    lock: dict[str, Any],
    buildtools: ModuleType,
    wheelhouse: Path,
    run_root: Path,
    env: dict[str, str],
    log_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    """Install only the complete verified wheel closure into a fresh offline venv."""
    quarantine_proof = buildtools.validate_quarantine(lock, wheelhouse)
    venv = run_root / "build-tools-env"
    run_command(
        [uv, "venv", "--python", str(base_python), str(venv)],
        cwd=run_root,
        env=env,
        log_stem=log_dir / "create-build-tools-env",
    )
    python = venv / "bin" / "python"
    if not python.is_file():
        raise WaveFailure(f"expected Unix virtual-environment interpreter: {python}")
    info = interpreter_info(python, log_dir=log_dir, name="build-tools-env")
    if info["implementation"] != "cpython" or info["version"][:2] != [3, 14]:
        raise WaveFailure(
            f"build tools env must use CPython 3.14: {info['implementation']} {info['version']}"
        )
    purelib = Path(info["purelib"]).resolve()
    if tuple(purelib.glob("*.pth")):
        raise WaveFailure("fresh build-tools venv contains a .pth file")
    requirements = run_root / "build-tools-requirements.txt"
    requirements.write_text(buildtools.requirements_text(lock), encoding="utf-8")
    install_argv = [
        uv,
        "pip",
        "install",
        "--offline",
        "--no-index",
        "--find-links",
        str(wheelhouse),
        "--python",
        str(python),
        "--only-binary",
        ":all:",
        "--no-deps",
        "--require-hashes",
        "--requirement",
        str(requirements),
    ]
    run_command(
        install_argv,
        cwd=run_root,
        env=env,
        log_stem=log_dir / "install-build-tools-offline",
    )
    probe = run_command(
        [str(python), "-I", "-S", "-c", buildtools.installed_probe_code(lock)],
        cwd=run_root,
        env=clean_child_env(),
        log_stem=log_dir / "build-tools-installed-origin-proof",
    )
    try:
        installed = json.loads(probe.stdout)
    except json.JSONDecodeError as error:
        raise WaveFailure("installed build-tools probe did not emit JSON") from error
    if (
        type(installed) is not dict
        or installed.get("verified") is not True
        or installed.get("implementation") != "cpython"
        or installed.get("distributions")
        != {
            row["name"].replace("_", "-").replace(".", "-"): row["version"]
            for row in lock["artifacts"]
        }
    ):
        raise WaveFailure("offline build-tools installed-origin proof failed")
    wrapper = run_command(
        [str(venv / "bin" / "hatchling"), "--help"],
        cwd=run_root,
        env=clean_child_env(),
        log_stem=log_dir / "hatchling-console-entrypoint-smoke",
    )
    if "usage:" not in wrapper.stdout.lower():
        raise WaveFailure("verified Hatchling console entry point did not return CLI usage")
    profile = {
        "status": "isolated_offline_build_tools_installed",
        "python": str(python),
        "python_info": info,
        "host_platform": {"system": platform.system(), "machine": platform.machine()},
        "requirements_sha256": sha256_file(requirements),
        "install_argv": install_argv,
        "wheelhouse": str(wheelhouse),
        "pre_venv_quarantine_proof": quarantine_proof,
        "installed_origin_proof": installed,
        "entrypoint_smoke": {
            "status": "passed",
            "stdout_sha256": sha256_bytes(wrapper.stdout.encode()),
        },
        "application_dependency_site": "not appended or consulted by the build-tools environment",
    }
    json_write(run_root / "build-tools-host-profile.json", profile)
    return python, profile


def load_source_bound_build_tools(
    repo: Path, source_sha: str, frozen_product: Path
) -> tuple[
    ModuleType,
    dict[str, Any],
    bytes,
    dict[str, bytes],
    dict[str, bytes],
    Path,
    dict[str, Any],
]:
    """Bind and authenticate the pyproject, profile, helper and lock before helper execution."""
    project_bytes = _read_regular_without_symlink_components(
        frozen_product / "pyproject.toml", "frozen product pyproject.toml"
    )[1]
    try:
        project = tomllib.loads(project_bytes.decode("utf-8"))
        profile_pointer = project["tool"]["policyos"]["q2_build_tools"]
    except (UnicodeDecodeError, KeyError, tomllib.TOMLDecodeError) as error:
        raise WaveFailure(
            "frozen pyproject does not declare the Q2 build-tools profile path"
        ) from error
    if type(profile_pointer) is not dict or profile_pointer != {
        "profile_path": BUILD_TOOL_PROFILE_RELATIVE
    }:
        raise WaveFailure("frozen pyproject Q2 profile pointer does not name the canonical profile")
    profile_path = frozen_product / BUILD_TOOL_PROFILE_RELATIVE
    profile_raw = _read_regular_without_symlink_components(
        profile_path, "frozen Q2 build-tools source profile"
    )[1]
    try:
        profile = tomllib.loads(profile_raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise WaveFailure("frozen Q2 build-tools profile is not valid UTF-8 TOML") from error
    if type(profile) is not dict or (
        profile.get("pyproject_path") != "pyproject.toml"
        or profile.get("helper_path") != BUILD_TOOL_HELPER_RELATIVE
        or profile.get("lock_path") != BUILD_TOOL_LOCK_RELATIVE
    ):
        raise WaveFailure("frozen Q2 profile does not name the canonical helper and lock")
    helper_path = frozen_product / BUILD_TOOL_HELPER_RELATIVE
    lock_path = frozen_product / BUILD_TOOL_LOCK_RELATIVE
    helper_bytes = _read_regular_without_symlink_components(
        helper_path, "frozen Q2 build-tools source helper"
    )[1]
    lock_bytes = _read_regular_without_symlink_components(
        lock_path, "frozen Q2 build-tools wheel lock"
    )[1]
    archive_members = {
        "pyproject.toml": project_bytes,
        BUILD_TOOL_PROFILE_RELATIVE: profile_raw,
        BUILD_TOOL_HELPER_RELATIVE: helper_bytes,
        BUILD_TOOL_LOCK_RELATIVE: lock_bytes,
    }
    source_blobs = {
        "pyproject.toml": git_blob(repo, source_sha, "policy-engine/pyproject.toml"),
        BUILD_TOOL_PROFILE_RELATIVE: git_blob(
            repo, source_sha, f"policy-engine/{BUILD_TOOL_PROFILE_RELATIVE}"
        ),
        BUILD_TOOL_HELPER_RELATIVE: git_blob(
            repo, source_sha, f"policy-engine/{BUILD_TOOL_HELPER_RELATIVE}"
        ),
        BUILD_TOOL_LOCK_RELATIVE: git_blob(
            repo, source_sha, f"policy-engine/{BUILD_TOOL_LOCK_RELATIVE}"
        ),
    }
    if source_blobs != archive_members:
        raise WaveFailure(
            "source Git blobs and frozen archive project/profile/helper/lock members differ"
        )
    helper_sha = sha256_bytes(helper_bytes)
    lock_sha = sha256_bytes(lock_bytes)
    if profile.get("helper_sha256") != helper_sha or profile.get("lock_sha256") != lock_sha:
        raise WaveFailure("frozen helper or wheel-lock bytes differ from Q2 profile bindings")
    helper_spec = importlib.util.spec_from_file_location("q2_build_tool_wheel_lock", helper_path)
    if helper_spec is None or helper_spec.loader is None:
        raise WaveFailure("cannot load the hash-bound Q2 build-tools helper")
    helper_module = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helper_module)
    try:
        helper_module.verify_pyproject_profile(
            project_bytes,
            profile_raw=profile_raw,
            helper_path=BUILD_TOOL_HELPER_RELATIVE,
            helper_sha256=helper_sha,
            lock_path=BUILD_TOOL_LOCK_RELATIVE,
            lock_sha256=lock_sha,
        )
    except ValueError as error:
        raise WaveFailure(f"source-bound Q2 build-tools profile rejected: {error}") from error
    binding = {
        "profile": profile,
        "helper_path": str(helper_path),
        "helper_sha256": helper_sha,
        "lock_path": str(lock_path),
        "lock_sha256": lock_sha,
    }
    return helper_module, profile, lock_bytes, source_blobs, archive_members, helper_path, binding


def measure_app_dependency_profile(
    python: Path,
    expected_site: Path,
    log_dir: Path,
) -> dict[str, Any]:
    """Bind the one unprocessed dependency site to actual lexical app sysconfig."""
    lexical = Path(os.path.abspath(python))
    if not lexical.is_file() or not (lexical.parent.parent / "pyvenv.cfg").is_file():
        raise WaveFailure("dependency exception requires an actual lexical app venv")
    code = (
        "import json,sys,sysconfig;print(json.dumps({"
        "'prefix':sys.prefix,'purelib':sysconfig.get_path('purelib'),"
        "'executable':sys.executable,'base_executable':sys._base_executable,"
        "'version':list(sys.version_info[:3])}))"
    )
    result = run_command(
        [str(lexical), "-I", "-S", "-c", code],
        cwd=log_dir,
        env=clean_child_env(),
        log_stem=log_dir / "app-dependency-sysconfig",
    )
    info = json.loads(result.stdout)
    prefix = lexical.parent.parent.resolve(strict=True)
    site = Path(info["purelib"]).resolve(strict=True)
    if (
        info["version"][:2] != [3, 14]
        or Path(info["prefix"]).resolve(strict=True) != prefix
        or Path(info["executable"]) != lexical
        or site != expected_site.resolve(strict=True)
        or not site.is_relative_to(prefix)
    ):
        raise WaveFailure("dependency site is not the measured app sysconfig purelib")
    inputs = []
    for path in [prefix / "pyvenv.cfg", *sorted(site.glob("*.pth"))]:
        canonical, raw = _read_regular_without_symlink_components(path, "app profile input")
        inputs.append(
            {
                "path": str(canonical),
                "bytes": len(raw),
                "sha256": sha256_bytes(raw),
                "hex": raw.hex(),
            }
        )
    return {
        "schema": "policyos.q2.app_dependency_profile.v1",
        "python": str(lexical),
        "prefix": str(prefix),
        "purelib": str(site),
        "sysconfig": info,
        "inputs": inputs,
        "pth_processing": "never; append exact measured directory only",
    }


def dependency_profile_guard(profile: dict[str, Any] | None) -> str:
    """Generate the same exact measured-site predicate for both actual children."""
    return (
        "import hashlib as _q2_hashlib\n"
        "_q2_dependency_profile = " + repr(profile) + "\n"
        "def _q2_dependency_site_allowed(value):\n"
        "    profile = _q2_dependency_profile\n"
        "    if profile is None:\n        return False\n"
        "    if profile.get('schema') != 'policyos.q2.app_dependency_profile.v1':\n"
        "        raise RuntimeError('unbound dependency profile')\n"
        "    site = Path(profile['purelib']).resolve(strict=True)\n"
        "    prefix = Path(profile['prefix']).resolve(strict=True)\n"
        "    if not site.is_relative_to(prefix):\n"
        "        raise RuntimeError('dependency site escapes measured app prefix')\n"
        "    declared = {row['path'] for row in profile['inputs']}\n"
        "    actual = {str(prefix / 'pyvenv.cfg')} | {str(p) for p in site.glob('*.pth')}\n"
        "    if declared != actual:\n        raise RuntimeError('app profile input set changed')\n"
        "    for row in profile['inputs']:\n"
        "        path = Path(row['path'])\n"
        "        if path.is_symlink() or path.resolve(strict=True) != path:\n"
        "            raise RuntimeError('app profile input path changed')\n"
        "        raw = path.read_bytes()\n"
        "        if len(raw) != row['bytes'] or _q2_hashl"
        "ib.sha256(raw).hexdigest() != row['sha256']:\n"
        "            raise RuntimeError('app profile input bytes changed')\n"
        "    return Path(value).resolve() == site\n"
    )


def configure_installed_env(
    uv: str,
    base_python: Path,
    run_root: Path,
    app_dependency_site: Path,
    source_product: Path,
    env: dict[str, str],
    log_dir: Path,
    origin_gate_source: bytes,
    *,
    app_python: Path | None = None,
) -> tuple[Path, Path]:
    dependency_profile = (
        measure_app_dependency_profile(app_python, app_dependency_site, log_dir)
        if app_python is not None
        else None
    )
    json_write(run_root / "app-dependency-profile.json", dependency_profile)
    venv = run_root / "installed-consumer-env"
    run_command(
        [uv, "venv", "--python", str(base_python), str(venv)],
        cwd=run_root,
        env=env,
        log_stem=log_dir / "create-installed-consumer-env",
    )
    python = venv / "bin" / "python"
    if not python.is_file():
        raise WaveFailure(f"expected Unix virtual-environment interpreter: {python}")
    info = interpreter_info(python, log_dir=log_dir, name="installed-consumer-env")
    if info["version"][:2] != [3, 14]:
        raise WaveFailure(f"installed consumer env must use CPython 3.14, got {info['version']}")
    purelib = Path(info["purelib"]).resolve()
    prefix = Path(info["prefix"]).resolve()
    if not purelib.is_relative_to(prefix):
        raise WaveFailure(f"installed site-packages escapes isolated prefix: {purelib} vs {prefix}")
    if tuple(purelib.glob("*.pth")):
        raise WaveFailure(
            "fresh installed consumer venv contains a .pth file; refusing to execute it"
        )
    if sha256_bytes(origin_gate_source) != INSTALLED_ORIGIN_GATE_SHA256:
        raise WaveFailure("verified installed-origin gate bytes changed before venv setup")
    gate_module_path = purelib / "q2_installed_origin_gate.py"
    if gate_module_path.exists() or gate_module_path.is_symlink():
        raise WaveFailure(
            f"unexpected file already occupies the installed-origin helper path: {gate_module_path}"
        )
    try:
        gate_module_path.write_bytes(origin_gate_source)
    except OSError as error:
        raise WaveFailure(
            f"cannot materialize the verified installed-origin helper: {gate_module_path}"
        ) from error
    if gate_module_path.read_bytes() != origin_gate_source:
        raise WaveFailure("installed-origin helper readback differs from the verified gate bytes")
    if not app_dependency_site.is_dir():
        raise WaveFailure(f"locked dependency site is missing: {app_dependency_site}")
    sitecustomize = (
        f"from pathlib import Path\nimport sys\n_q2_dependency_site = Path("
        f"{str(app_dependency_site)!r}"
        f").resolve()\nif not _q2_dependency_site.is_dir():\n    raise "
        f"RuntimeError(f'Q2 dependency site is missing: "
        f"{{_q2_dependency_site}}')\n_q2_dependency_text = "
        f"str(_q2_dependency_site)\nif _q2_dependency_text in sys.path:\n    "
        f"raise RuntimeError('Q2 dependency site was already processed; "
        f"editable .pth injection is forbidden')\n"
        f"sys.path.append(_q2_dependency_text)\n"
    )
    (purelib / "sitecustomize.py").write_text(sitecustomize, encoding="utf-8")
    origin_plugin = (
        "from __future__ import annotations\n"
        + dependency_profile_guard(dependency_profile)
        + (
            "import json, os, sys, sysconfig\n"
            "from pathlib import Path\n"
            "import pytest\n"
            "import q2_installed_origin_gate\n"
            "\n"
            '_REPORTED_PURELIB = Path(sysconfig.get_paths()["purelib"])\n'
            "_CANONICAL_PURELIB = _REPORTED_PURELIB.resolve(strict=True)\n"
            "\n"
            "def _under(path, root):\n"
            "    try:\n"
            "        Path(path).resolve().relative_to(Path(root).resolve())\n"
            "        return True\n"
            "    except (OSError, ValueError):\n"
            "        return False\n"
            "\n"
            "def pytest_collection_finish(session):\n"
            '    out = Path(os.environ["E02_NODEIDS_REPORT"])\n'
            "    out.write_text(json.dumps(sorted(item.nodeid"
            ' for item in session.items), indent=2) + "\\n")\n'
            "\n"
            "def pytest_sessionfinish(session, exitstatus):\n"
            "    purelib_reported = _REPORTED_PURELIB\n"
            "    purelib = _CANONICAL_PURELIB\n"
            '    dependency_site = Path(os.environ["E02_DEPENDENCY_SITE"]).resolve()\n'
            '    source = Path(os.environ["E02_SOURCE_ROOT"]).resolve()\n'
            '    live_product = Path(os.environ["E02_LIVE_PRODUCT_ROOT"]).resolve()\n'
            "    forbidden_roots = [source, live_product]\n"
            "    forbidden_sys_path = [p for p in sys.path if"
            " p and not _q2_dependency_site_allowed(p) and an"
            "y(_under(p, root) for root in forbidden_roots)]\n"
            "    origins, errors = q2_installed_origin_gate.verify_loaded_module_origins(\n"
            "        purelib_reported, sys.modules.copy()\n"
            "    )\n"
            '    if "polisyos" not in origins:\n'
            '        errors.append({"module": "polisyos", "re'
            'ason": "installed package root was not imported"'
            "})\n"
            "    if forbidden_sys_path:\n"
            '        errors.append({"sys_path": forbidden_sys'
            '_path, "reason": "source or test path injected"}'
            ")\n"
            "    normalized_sys_path = [str(Path(path).resolve()) for path in sys.path]\n"
            "    try:\n"
            "        installed_index = normalized_sys_path.index(str(purelib))\n"
            "        dependency_index = normalized_sys_path.index(str(dependency_site))\n"
            "        if installed_index >= dependency_index:\n"
            '            errors.append({"sys_path": normalize'
            'd_sys_path, "reason": "installed site does not p'
            'recede dependency site"})\n'
            "    except ValueError:\n"
            '        errors.append({"sys_path": normalized_sy'
            's_path, "reason": "installed/dependency site mis'
            'sing"})\n'
            '    report = {"verified": not errors, "purelib_r'
            'eported": str(purelib_reported), "purelib": str('
            'purelib), "sys_path": sys.path, "origins": origi'
            'ns, "errors": errors}\n'
            '    Path(os.environ["E02_ORIGIN_REPORT"]).write_'
            "text(json.dumps(report, indent=2, sort_keys=True"
            ') + "\\n")\n'
            "    if errors:\n"
            '        print("Q2 installed-origin proof failed:'
            ' " + json.dumps(errors, sort_keys=True), file=sy'
            "s.stderr)\n"
            "        session.exitstatus = pytest.ExitCode.TESTS_FAILED\n"
        )
    )
    (purelib / "q2_installed_origin_plugin.py").write_text(origin_plugin, encoding="utf-8")
    json_write(
        run_root / "installed-env-config.json",
        {
            "venv": str(venv),
            "python": str(python),
            "purelib": str(purelib),
            "app_dependency_site_appended_without_pth_processing": str(app_dependency_site),
            "source_product": str(source_product),
            "PYTHONPATH": None,
            "installation_mode": "one venv reused sequentially with uv pip --reinstall --no-deps",
        },
    )
    return python, purelib


def installed_runtime_proof(
    python: Path,
    purelib: Path,
    assets: list[dict[str, Any]],
    source_product: Path,
    live_product: Path,
    app_dependency_site: Path,
    run_root: Path,
    profile: str,
    env: dict[str, str],
    log_dir: Path,
    owner_inventory_path: Path,
    origin_gate_source: bytes,
    *,
    app_python: Path | None = None,
) -> dict[str, Any]:
    dependency_profile = (
        measure_app_dependency_profile(app_python, app_dependency_site, log_dir)
        if app_python is not None
        else None
    )
    expected = {
        asset["wheel"]: {"bytes": asset["bytes"], "sha256": asset["sha256"]} for asset in assets
    }
    resource_helper = source_product / RESOURCE_CONTRACT_RELATIVE
    resource_result = run_command(
        [
            str(python),
            "-I",
            str(resource_helper),
            "installed",
            "--expected-inventory",
            str(owner_inventory_path),
            "--purelib",
            str(purelib),
            "--forbidden-root",
            str(source_product),
            "--forbidden-root",
            str(live_product),
        ],
        cwd=run_root,
        env=clean_child_env(),
        log_stem=log_dir / f"{profile}-importlib-resource-contract",
    )
    try:
        resource_proof = json.loads(resource_result.stdout)
    except json.JSONDecodeError as error:
        raise WaveFailure("installed resource helper did not emit valid JSON") from error
    if (
        type(resource_proof) is not dict
        or resource_proof.get("schema") != "polisyos.packaged-resource-contract.v1"
        or set(resource_proof.get("runtime_owner_targets", [])) != set(expected)
        or set(resource_proof.get("importlib_resources", {})) != set(expected)
    ):
        raise WaveFailure("installed resource helper did not prove the complete runtime owner set")
    for target, expected_asset in expected.items():
        observed = resource_proof["importlib_resources"].get(target)
        if (
            type(observed) is not dict
            or not exact_nonbool_count_matches(observed.get("bytes"), expected_asset["bytes"])
            or observed.get("sha256") != expected_asset["sha256"]
        ):
            raise WaveFailure(f"importlib.resources bytes differ from source for {target}")
    code = (
        origin_gate_source.decode("utf-8")
        + dependency_profile_guard(dependency_profile)
        + "\n"
        + (
            "import hashlib, importlib, importlib.metadata, json, os, sys, "
            "sysconfig\nfrom pathlib import Path\nfrom typing import get_args\n"
            'purelib_reported=Path(sysconfig.get_paths()["purelib"])\n'
            "purelib=purelib_reported.resolve()\nprefix=Path(sys.prefix).resolve()\n"
            'source=Path(os.environ["E02_SOURCE_ROOT"]).resolve()\n'
            'live_product=Path(os.environ["E02_LIVE_PRODUCT_ROOT"]).resolve()\n'
            'dependency_site=Path(os.environ["E02_DEPENDENCY_SITE"]).resolve()\n'
            "forbidden_roots=(source,live_product)\nassert "
            "purelib.is_relative_to(prefix)\nassert sys.flags.isolated\nassert not "
            'os.environ.get("PYTHONPATH")\nassert not any(p and '
            "any(Path(p).resolve()==root or Path(p).resolve().is_relative_to(root"
            ") for root in forbidden_roots) for p in sys.path"
            " if not _q2_dependency_site_allowed(p))\n"
            "normalized_sys_path=[Path(p).resolve() for p in sys.path]\nassert "
            "normalized_sys_path.index(purelib)<normalized_sys_path.index(depende"
            'ncy_site),sys.path\nassets=json.loads(Path(os.environ["E02_ASSET_EXPE'
            'CTED_JSON"]).read_text())\nprofile=os.environ["E02_PROFILE_NAME"]\n'
            "import polisyos, tools\nfrom polisyos.data_forge.domains.catalog "
            "import _resources\nfrom polisyos.foundry.methods.catalog import "
            "dependency_authority\nfrom polisyos.foundry.methods.catalog.causal "
            "import _dowhy_worker\nmodule_origins,module_origin_errors=verify_load"
            "ed_module_origins(purelib_reported,sys.modules.copy())\nassert "
            "module_origins\nassert not module_origin_errors,module_origin_errors\n"
            'assert {"polisyos","tools"} <= set(module_origins),module_origins\n'
            "def resolve_selected_installed_readers(\n    profile: str,\n    "
            "purelib: Path,\n    assets: dict[str, dict[str, Any]],\n    "
            "resources_module: Any,\n    authority_module: Any,\n    worker_module: "
            "Any,\n) -> dict[str, Path]:\n    # Resolve every typed reader and bind "
            "it to the selected installed targets.\n    if not profile:\n        "
            'raise AssertionError("installed profile label is required")\n    '
            'catalog_targets = {\n        target.rsplit("/", 1)[-1]: target\n       '
            ' for target in assets\n        if target.startswith("polisyos/data_fo'
            'rge/domains/catalog/_resources/")\n    }\n    catalog_names = '
            "tuple(get_args(resources_module.CatalogDefaultResource))\n    assert "
            "set(catalog_targets) == set(catalog_names), (profile, "
            "catalog_targets, catalog_names)\n    reader_paths: dict[str, Path] = "
            "{}\n    for name in catalog_names:\n        actual = "
            "Path(resources_module.catalog_default_resource_path(name)).resolve(s"
            "trict=True)\n        expected_path = (purelib / "
            "catalog_targets[name]).resolve(strict=True)\n        assert actual == "
            "expected_path, (profile, name, actual, expected_path)\n        "
            'reader_paths[f"{profile}:catalog-default:{name}"] = actual\n    '
            "registry_path = Path(authority_module._DIGEST_REGISTRY_PATH).resolve"
            "(strict=True)\n    packaged_registry_path = "
            "Path(authority_module._PACKAGED_DIGEST_REGISTRY_PATH).resolve(strict"
            "=True)\n    assert registry_path == packaged_registry_path, (profile, "
            "registry_path, packaged_registry_path)\n    registry = "
            "authority_module.load_digest_domain_registry(registry_path)\n    "
            "assert registry.statement.domains, profile\n    registry_target = "
            '"polisyos/foundry/methods/catalog/_resources/method_catalog_dependen'
            'cy_digest_domains.toml"\n    expected_registry = (purelib / '
            "registry_target).resolve(strict=True)\n    assert registry_path == "
            "expected_registry, (profile, registry_path, expected_registry)\n    "
            'reader_paths[f"{profile}:dependency-authority:digest-registry"] = '
            "registry_path\n    profile_targets = [target for target in assets if "
            '"/_dowhy_profile/" in target]\n    assert profile_targets, profile\n   '
            " profile_dirs = {(purelib / Path(target).parent).resolve(strict=True"
            ") for target in profile_targets}\n    assert len(profile_dirs) == 1, "
            "(profile, profile_dirs)\n    worker_directory = "
            "Path(worker_module._worker_directory()).resolve(strict=True)\n    "
            "expected_worker_directory = next(iter(profile_dirs))\n    assert "
            "worker_directory == expected_worker_directory, (profile, "
            "worker_directory, expected_worker_directory)\n    "
            'reader_paths[f"{profile}:dowhy-worker:profile-directory"] = '
            "worker_directory\n    return reader_paths\n\n\ndef "
            "verify_selected_installed_resources(\n    profile: str,\n    purelib: "
            "Path,\n    assets: dict[str, dict[str, Any]],\n    resources_module: "
            "Any,\n    authority_module: Any,\n    worker_module: Any,\n) -> "
            "tuple[dict[str, dict[str, Any]], dict[str, str]]:\n    # Verify the "
            "whole manifest and every canonical reader result at one boundary.\n   "
            " reader_paths = resolve_selected_installed_readers(\n        profile, "
            "purelib, assets, resources_module, authority_module, worker_module\n  "
            "  )\n    return verify_installed_resources(purelib, assets, "
            "reader_paths)\n\nasset_rows,reader_rows=verify_selected_installed_reso"
            "urces(profile,purelib,assets,_resources,dependency_authority,_dowhy_"
            'worker)\nprint(json.dumps({"python":sys.version,"prefix":str(prefix),'
            '"purelib_reported":str(purelib_reported),"purelib":str(purelib),"pol'
            'icyos_origin":str(Path(polisyos.__file__)),"tools_origin":str(Path(t'
            'ools.__file__)),"module_origins":module_origins,"assets":asset_rows,'
            '"reader_paths":reader_rows,"profile":profile},sort_keys=True))\n'
        )
    )
    child_env = clean_child_env()
    child_env.update(
        {
            "E02_SOURCE_ROOT": str(source_product),
            "E02_LIVE_PRODUCT_ROOT": str(live_product),
            "E02_DEPENDENCY_SITE": str(app_dependency_site),
            "E02_ASSET_EXPECTED_JSON": str(run_root / "asset-targets-expected.json"),
            "E02_PROFILE_NAME": profile,
        }
    )
    json_write(run_root / "asset-targets-expected.json", expected)
    result = run_command(
        [str(python), "-I", "-c", code],
        cwd=run_root,
        env=child_env,
        log_stem=log_dir / f"{profile}-installed-runtime-proof",
    )
    proof = json.loads(result.stdout)
    if proof.get("profile") != profile:
        raise WaveFailure("installed proof reported the wrong profile")
    if Path(proof["purelib"]).resolve() != purelib.resolve():
        raise WaveFailure(f"installed proof used unexpected purelib: {proof['purelib']}")
    proof_assets = proof.get("assets")
    if not isinstance(proof_assets, dict) or set(proof_assets) != set(expected):
        raise WaveFailure("installed proof did not cover the complete manifest resource set")
    for target, expected_asset in expected.items():
        actual_asset = proof_assets.get(target)
        if (
            not isinstance(actual_asset, dict)
            or not exact_nonbool_count_matches(actual_asset.get("bytes"), expected_asset["bytes"])
            or actual_asset.get("sha256") != expected_asset["sha256"]
            or not isinstance(actual_asset.get("installed_path"), str)
        ):
            raise WaveFailure(f"installed proof asset bytes or digest differ: {target}")
    proof["runtime_owner_importlib_resources"] = resource_proof
    return proof


def baseline_node_ids(source_product: Path, manifest: dict[str, Any]) -> set[str]:
    relative = manifest["original_q2_suite"]["baseline_junit_path"]
    baseline_path = source_product / relative
    compressed = baseline_path.read_bytes()
    if sha256_bytes(compressed) != manifest["original_q2_suite"]["baseline_junit_sha256"]:
        raise WaveFailure(
            "tracked original Q2 JUnit baseline checksum changed; reconcile before running"
        )
    root = SafeET.fromstring(gzip.decompress(compressed))
    rows = list(root.iter("testcase"))
    if not exact_nonbool_count_matches(
        manifest["original_q2_suite"].get("baseline_case_count"), len(rows)
    ):
        raise WaveFailure(f"original Q2 baseline denominator differs: {len(rows)}")
    ids: set[str] = set()
    for case in rows:
        classname = case.attrib["classname"]
        if classname == "test_installed_catalog_defaults":
            test_path = manifest["original_q2_suite"]["test_paths"][-1]
        else:
            dotted = classname.split(".")
            test_path = "/".join([*dotted[:-1], dotted[-1] + ".py"])
        if not any(
            test_path == candidate for candidate in manifest["original_q2_suite"]["test_paths"]
        ):
            raise WaveFailure(
                f"baseline JUnit case falls outside declared original suite: {classname}"
            )
        ids.add(f"{test_path}::{case.attrib['name']}")
    if len(ids) != len(rows):
        raise WaveFailure("original baseline JUnit contains duplicate node IDs")
    return ids


def node_ids_sha256(node_ids: set[str] | list[str]) -> str:
    """Hash a canonical, sorted, newline-delimited node-ID set."""
    return sha256_bytes(("\n".join(sorted(node_ids)) + "\n").encode("utf-8"))


def historical_baseline_subset_ids(
    manifest: dict[str, Any], expected_original_ids: set[str]
) -> set[str]:
    """Rebuild and validate the named 91-baseline-plus-nine-consumer subset."""
    expected = set(expected_original_ids)
    additional = manifest["additional_installed_consumers"]
    for group in (additional["dependency_profile"], additional["canonical_bridge_and_worker"]):
        for selector in group["selectors"]:
            node_id = f"{group['test_path']}::{selector}"
            if node_id in expected:
                raise WaveFailure(
                    f"historical installed consumer duplicates an original ID: {node_id}"
                )
            expected.add(node_id)

    declaration = manifest.get("current_primary_suite", {}).get("historical_baseline_subset")
    if not isinstance(declaration, dict):
        raise WaveFailure("current primary suite omits the named historical baseline subset")
    if not exact_nonbool_count_matches(declaration.get("selected_node_count"), len(expected)):
        raise WaveFailure(
            "historical baseline subset count differs from its recomputed IDs: "
            f"declared={declaration.get('selected_node_count')} actual={len(expected)}"
        )
    if declaration.get("selected_node_ids_sha256") != node_ids_sha256(expected):
        raise WaveFailure("historical baseline subset ID digest differs from its recomputed IDs")
    if not isinstance(declaration.get("name"), str) or not declaration["name"].strip():
        raise WaveFailure("historical baseline subset must have a nonempty name")
    return expected


def selected_group_node_ids(group: dict[str, Any], candidates: set[str]) -> set[str]:
    """Resolve every named selector to its complete source-collected node-ID family."""
    path = group.get("test_path")
    selectors = group.get("selectors")
    if not isinstance(path, str) or not path or not isinstance(selectors, list) or not selectors:
        raise WaveFailure("installed consumer group must have a test path and nonempty selectors")
    if any(not isinstance(selector, str) or not selector for selector in selectors):
        raise WaveFailure(f"invalid selector list in {path}")
    if len(set(selectors)) != len(selectors):
        raise WaveFailure(f"duplicate selector in {path}")
    safe_relative_member(path)
    resolved: set[str] = set()
    for selector in selectors:
        if not isinstance(selector, str) or not selector:
            raise WaveFailure(f"invalid selector in {path}: {selector!r}")
        stem = f"{path}::{selector}"
        matches = (
            {node_id for node_id in candidates if node_id == stem}
            if "[" in selector
            else {
                node_id
                for node_id in candidates
                if node_id == stem or node_id.startswith(stem + "[")
            }
        )
        if not matches:
            raise WaveFailure(f"declared selector has no content-bound node IDs: {stem}")
        resolved.update(matches)
    return resolved


def current_primary_suite_ids(
    manifest: dict[str, Any], expected_original_ids: set[str]
) -> set[str]:
    """Load exact current IDs and reconcile each additional selector to its full family."""
    suite = manifest.get("current_primary_suite")
    if not isinstance(suite, dict):
        raise WaveFailure("manifest omits current_primary_suite")
    raw_ids = suite.get("selected_node_ids")
    if (
        not isinstance(raw_ids, list)
        or not raw_ids
        or any(not isinstance(item, str) for item in raw_ids)
    ):
        raise WaveFailure("current primary suite node IDs must be a nonempty string list")
    if raw_ids != sorted(set(raw_ids)):
        raise WaveFailure("current primary suite node IDs must be sorted and unique")
    declared_count = suite.get("selected_node_count")
    if not exact_nonbool_count_matches(declared_count, len(raw_ids)):
        raise WaveFailure("current primary suite count differs from its complete node-ID list")
    if suite.get("selected_node_ids_sha256") != node_ids_sha256(raw_ids):
        raise WaveFailure("current primary suite digest differs from its complete node-ID list")

    original_suite = manifest.get("original_q2_suite")
    baseline_path_values = (
        original_suite.get("test_paths") if isinstance(original_suite, dict) else None
    )
    if (
        not isinstance(baseline_path_values, list)
        or not baseline_path_values
        or any(not isinstance(path, str) or not path for path in baseline_path_values)
    ):
        raise WaveFailure("manifest original Q2 test paths must be a nonempty string list")
    baseline_paths = set(baseline_path_values)
    for path in baseline_paths:
        safe_relative_member(path)
    additional = manifest.get("additional_installed_consumers")
    if (
        not isinstance(additional, dict)
        or not additional
        or any(not isinstance(group, dict) for group in additional.values())
    ):
        raise WaveFailure("manifest omits or malforms additional installed consumer selectors")
    group_path_values = [group.get("test_path") for group in additional.values()]
    if any(not isinstance(path, str) or not path for path in group_path_values):
        raise WaveFailure("additional installed consumer paths must be nonempty strings")
    group_paths = set(group_path_values)
    if baseline_paths & group_paths:
        raise WaveFailure(
            "current primary baseline and additional consumer paths must be complete and disjoint"
        )
    declared_paths = baseline_paths | group_paths
    source_hashes = suite.get("source_file_sha256")
    if not isinstance(source_hashes, dict) or set(source_hashes) != declared_paths:
        raise WaveFailure(
            "current primary suite source-hash paths differ from the complete selected path set"
        )
    for path, digest in source_hashes.items():
        if not isinstance(path, str):
            raise WaveFailure("current primary suite source-hash paths must be strings")
        safe_relative_member(path)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise WaveFailure(f"current primary suite has an invalid source hash for {path}")

    ids = set(raw_ids)
    for node_id in raw_ids:
        pieces = node_id.split("::")
        if len(pieces) < 2 or any(not piece for piece in pieces) or pieces[0] not in declared_paths:
            raise WaveFailure(
                f"current primary suite contains an unbound source-qualified ID: {node_id}"
            )
        function_name = pieces[-1].split("[", 1)[0]
        if not function_name.startswith("test_"):
            raise WaveFailure(f"current primary suite contains a non-test selector: {node_id}")

    historical = historical_baseline_subset_ids(manifest, expected_original_ids)
    if not historical <= ids:
        raise WaveFailure(
            "current primary suite omits IDs from the historical 91-plus-nine subset: "
            f"{sorted(historical - ids)}"
        )
    claimed_group_ids: set[str] = set()
    for group in additional.values():
        claimed_group_ids.update(selected_group_node_ids(group, ids))
    declared_group_ids = {node_id for node_id in ids if node_id.split("::", 1)[0] in group_paths}
    if declared_group_ids != claimed_group_ids:
        raise WaveFailure(
            "current primary additional-consumer IDs differ from complete selector families: "
            f"unbound={sorted(declared_group_ids - claimed_group_ids)} "
            f"missing={sorted(claimed_group_ids - declared_group_ids)}"
        )
    if not expected_original_ids <= ids:
        raise WaveFailure("current primary suite omits original Q2 node IDs")
    return ids


def verify_current_primary_suite_sources(
    frozen_product: Path, manifest: dict[str, Any], expected_original_ids: set[str]
) -> set[str]:
    """Verify every source file that contributes the current selected pytest collection."""
    ids = current_primary_suite_ids(manifest, expected_original_ids)
    source_hashes = manifest["current_primary_suite"]["source_file_sha256"]
    for relative, expected_sha in sorted(source_hashes.items()):
        source = frozen_product.joinpath(*safe_relative_member(relative).parts)
        if not source.is_file() or source.is_symlink():
            raise WaveFailure(f"current primary suite source is absent or symlinked: {relative}")
        actual_sha = sha256_file(source)
        if actual_sha != expected_sha:
            raise WaveFailure(
                f"current primary suite source changed; reconcile ID manifest first: {relative} "
                f"expected={expected_sha} actual={actual_sha}"
            )
    return ids


def _module_function_index(
    tree: ast.Module,
) -> dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]:
    functions: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.setdefault(node.name, []).append(node)
    return functions


def _local_function_closure(
    root_name: str,
    functions: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]],
    *,
    source_path: str,
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    closure: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    pending = [root_name]
    while pending:
        name = pending.pop()
        if name in closure:
            continue
        candidates = functions.get(name, [])
        if len(candidates) != 1:
            raise WaveFailure(
                f"selected test/helper {name!r} in {source_path} is absent or ambiguous"
            )
        function = candidates[0]
        closure[name] = function
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in functions
                and node.func.id not in closure
            ):
                pending.append(node.func.id)
    return closure


def _is_file_fixture_loader(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "spec_from_file_location"
        for node in ast.walk(function)
    )


def _verify_fixture_loader_key(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    source_path: str,
) -> str:
    parameters = function.args.posonlyargs + function.args.args
    if not parameters:
        raise WaveFailure(f"file fixture loader in {source_path} has no kind parameter")
    kind_parameter = parameters[0].arg
    env_keys = [
        node.slice
        for node in ast.walk(function)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "os"
        and node.value.attr == "environ"
    ]
    matching = []
    for expression in env_keys:
        text = ast.unparse(expression)
        if "E02_" in text and "_FIXTURE_PATH" in text and f"{kind_parameter}.upper()" in text:
            matching.append(text)
    if len(matching) != 1:
        raise WaveFailure(
            f"file fixture loader in {source_path} must derive one E02_<KIND>_FIXTURE_PATH "
            f"from its kind argument; found {matching}"
        )
    return matching[0]


def _verify_call_arity(
    call: ast.Call,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    label: str,
) -> None:
    if any(isinstance(argument, ast.Starred) for argument in call.args):
        raise WaveFailure(f"fixture callback uses an unresolved starred argument: {label}")
    if any(keyword.arg is None for keyword in call.keywords):
        raise WaveFailure(f"fixture callback uses unresolved **kwargs: {label}")
    positional = function.args.posonlyargs + function.args.args
    positional_names = [argument.arg for argument in positional]
    if len(call.args) > len(positional) and function.args.vararg is None:
        raise WaveFailure(f"fixture callback passes too many positional arguments: {label}")
    supplied_positional = positional_names[: len(call.args)]
    supplied_keywords = [keyword.arg for keyword in call.keywords if keyword.arg is not None]
    if set(supplied_positional) & set(supplied_keywords):
        raise WaveFailure(f"fixture callback binds an argument twice: {label}")
    accepted_keywords = {argument.arg for argument in function.args.args} | {
        argument.arg for argument in function.args.kwonlyargs
    }
    if function.args.kwarg is None and not set(supplied_keywords) <= accepted_keywords:
        raise WaveFailure(f"fixture callback passes an unknown keyword: {label}")
    if len(call.args) < len(positional) - len(function.args.defaults):
        required_positional = set(positional_names[: len(positional) - len(function.args.defaults)])
        if not required_positional <= set(supplied_positional + supplied_keywords):
            raise WaveFailure(f"fixture callback omits a required positional argument: {label}")
    required_keyword_only = {
        argument.arg
        for argument, default in zip(
            function.args.kwonlyargs, function.args.kw_defaults, strict=True
        )
        if default is None
    }
    if not required_keyword_only <= set(supplied_keywords):
        raise WaveFailure(f"fixture callback omits a required keyword-only argument: {label}")


def _class_method_index(
    tree: ast.Module,
) -> dict[tuple[str, ...], dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]]:
    """Index methods by their complete nested class path."""
    result: dict[tuple[str, ...], dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]] = {}

    def collect(body: list[ast.stmt], class_path: tuple[str, ...]) -> None:
        for node in body:
            if not isinstance(node, ast.ClassDef):
                continue
            nested_path = (*class_path, node.name)
            methods = result.setdefault(nested_path, {})
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.setdefault(child.name, []).append(child)
            collect(node.body, nested_path)

    collect(tree.body, ())
    return result


def _class_local_function_closure(
    root_name: str,
    class_path: tuple[str, ...],
    root_function: ast.FunctionDef | ast.AsyncFunctionDef,
    functions: dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]],
    class_methods: dict[tuple[str, ...], dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]],
    *,
    source_path: str,
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Follow module helpers and same-class ``self`` helpers from a class test."""
    root_key = "::".join((*class_path, root_name))
    closure = {root_key: root_function}
    pending = [(root_key, root_function, class_path)]
    while pending:
        _, function, scope = pending.pop()
        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            callee_key: str | None = None
            callee_scope: tuple[str, ...] = ()
            candidates: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
            if isinstance(node.func, ast.Name):
                candidates = functions.get(node.func.id, [])
                if candidates:
                    callee_key = node.func.id
            elif (
                scope
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
            ):
                candidates = class_methods.get(scope, {}).get(node.func.attr, [])
                if candidates:
                    callee_scope = scope
                    callee_key = "::".join((*scope, node.func.attr))
            if callee_key is None:
                continue
            if len(candidates) != 1:
                raise WaveFailure(
                    f"selected helper {callee_key!r} in {source_path} is absent or ambiguous"
                )
            if callee_key not in closure:
                closure[callee_key] = candidates[0]
                pending.append((callee_key, candidates[0], callee_scope))
    return closure


def verify_transitive_test_bindings(
    frozen_product: Path,
    manifest: dict[str, Any],
    expected_original_ids: set[str],
) -> dict[str, Any]:
    """Resolve every selected test through any dynamic fixture module to its callable target."""
    current_ids = verify_current_primary_suite_sources(
        frozen_product, manifest, expected_original_ids
    )
    additional = manifest["additional_installed_consumers"]
    selected_ids = set(current_ids)
    historical_ids = historical_baseline_subset_ids(manifest, expected_original_ids)
    if not historical_ids <= selected_ids:
        raise WaveFailure("current transitive selector set omits the historical baseline subset")

    selected_by_path: dict[str, set[tuple[tuple[str, ...], str]]] = {}
    for node_id in selected_ids:
        pieces = node_id.split("::")
        if len(pieces) < 2 or any(not piece for piece in pieces):
            raise WaveFailure(
                f"transitive binding found an invalid source-qualified test ID: {node_id}"
            )
        test_path = pieces[0]
        class_path = tuple(pieces[1:-1])
        function_name = pieces[-1].split("[", 1)[0]
        if not function_name.startswith("test_"):
            raise WaveFailure(f"transitive binding found an unsupported test node ID: {node_id}")
        selected_by_path.setdefault(test_path, set()).add((class_path, function_name))

    module_cache: dict[
        str,
        tuple[
            ast.Module,
            dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]],
            dict[tuple[str, ...], dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]]],
        ],
    ] = {}
    for test_path in selected_by_path:
        relative = safe_relative_member(test_path)
        source = frozen_product.joinpath(*relative.parts)
        if not source.is_file() or source.is_symlink():
            raise WaveFailure(f"selected test source is absent or symlinked: {test_path}")
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=test_path)
        functions = _module_function_index(tree)
        class_methods = _class_method_index(tree)
        module_cache[test_path] = (tree, functions, class_methods)
        for class_path, function_name in selected_by_path[test_path]:
            candidates = (
                class_methods.get(class_path, {}).get(function_name, [])
                if class_path
                else functions.get(function_name, [])
            )
            if len(candidates) != 1:
                selected = "::".join((*class_path, function_name))
                raise WaveFailure(
                    f"selected test node {test_path}::{selected} has no unique function body"
                )

    fixture_paths = additional["canonical_bridge_and_worker"].get("fixture_paths")
    if not isinstance(fixture_paths, dict) or not all(
        isinstance(kind, str) and isinstance(path, str) for kind, path in fixture_paths.items()
    ):
        raise WaveFailure("canonical worker consumers must declare a kind-to-fixture-path mapping")

    fixture_kinds: set[str] = set()
    callback_calls: dict[str, list[tuple[str, str, ast.Call]]] = {}
    fixture_details: dict[str, dict[str, Any]] = {}
    for test_path, test_targets in selected_by_path.items():
        _, functions, class_methods = module_cache[test_path]
        for class_path, test_name in test_targets:
            test_key = "::".join((*class_path, test_name)) if class_path else test_name
            if class_path:
                test_function = class_methods[class_path][test_name][0]
                closure = _class_local_function_closure(
                    test_name,
                    class_path,
                    test_function,
                    functions,
                    class_methods,
                    source_path=test_path,
                )
            else:
                closure = _local_function_closure(test_name, functions, source_path=test_path)
            loader_names = {
                name for name, function in closure.items() if _is_file_fixture_loader(function)
            }
            if not loader_names:
                continue
            loader_patterns = {
                name: _verify_fixture_loader_key(function, source_path=test_path)
                for name, function in closure.items()
                if name in loader_names
            }
            if test_key in loader_names:
                raise WaveFailure(
                    f"selected test {test_path}::{test_name} loads a fixture inline; "
                    "the loader-to-callable binding is not statically resolvable"
                )
            for _scope_name, scope in closure.items():
                variables: dict[str, str] = {}
                loader_calls = [
                    node
                    for node in ast.walk(scope)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in loader_patterns
                ]
                for call in loader_calls:
                    if len(call.args) != 1 or not isinstance(call.args[0], ast.Constant):
                        raise WaveFailure(
                            f"selected test {test_path}::{test_name} has a nonliteral fixture kind"
                        )
                    kind = call.args[0].value
                    if not isinstance(kind, str) or not kind:
                        raise WaveFailure(
                            f"selected test {test_path}::{test_name} has an invalid fixture kind"
                        )
                    fixture_kinds.add(kind)
                    targets: list[str] = []
                    for node in ast.walk(scope):
                        if isinstance(node, ast.Assign) and node.value is call:
                            targets.extend(
                                target.id for target in node.targets if isinstance(target, ast.Name)
                            )
                        elif (
                            isinstance(node, ast.AnnAssign)
                            and node.value is call
                            and isinstance(node.target, ast.Name)
                        ):
                            targets.append(node.target.id)
                    if len(targets) != 1:
                        raise WaveFailure(
                            f"selected fixture module in {test_path}::{test_name} must bind to "
                            "one local name"
                        )
                    variables[targets[0]] = kind
                for node in ast.walk(scope):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in variables
                    ):
                        kind = variables[node.func.value.id]
                        callback_calls.setdefault(kind, []).append(
                            (test_path, node.func.attr, node)
                        )
            if loader_patterns:
                for name in loader_names:
                    if name not in closure:
                        raise WaveFailure(f"unresolved fixture loader {name!r} in {test_path}")

    if fixture_kinds != set(fixture_paths):
        raise WaveFailure(
            "manifest fixture kinds differ from transitive selected-test bindings: "
            f"used={sorted(fixture_kinds)} declared={sorted(fixture_paths)}"
        )
    for kind in sorted(fixture_kinds):
        relative = safe_relative_member(fixture_paths[kind])
        fixture_source = frozen_product.joinpath(*relative.parts)
        if not fixture_source.is_file() or fixture_source.is_symlink():
            raise WaveFailure(f"fixture source for {kind!r} is absent or symlinked: {relative}")
        fixture_tree = ast.parse(
            fixture_source.read_text(encoding="utf-8"), filename=relative.as_posix()
        )
        functions = _module_function_index(fixture_tree)
        calls = callback_calls.get(kind, [])
        if not calls:
            raise WaveFailure(
                f"selected tests load fixture {kind!r} without calling a bound function"
            )
        callback_receipts = []
        transitive_functions: set[str] = set()
        for test_path, callback_name, call in calls:
            candidates = functions.get(callback_name, [])
            if len(candidates) != 1:
                raise WaveFailure(
                    f"fixture callback "
                    f"{kind}"
                    f"."
                    f"{callback_name}"
                    f" from "
                    f"{test_path}"
                    f" is absent or ambiguous"
                )
            _verify_call_arity(
                call,
                candidates[0],
                label=f"{test_path} -> {relative.as_posix()}::{callback_name}",
            )
            closure = _local_function_closure(
                callback_name,
                functions,
                source_path=relative.as_posix(),
            )
            transitive_functions.update(closure)
            callback_receipts.append(
                {
                    "selected_test_path": test_path,
                    "callback": callback_name,
                    "line": candidates[0].lineno,
                }
            )
        fixture_details[kind] = {
            "path": relative.as_posix(),
            "sha256": sha256_file(fixture_source),
            "callbacks": callback_receipts,
            "transitive_local_functions": sorted(transitive_functions),
        }
    return {
        "historical_baseline_subset_node_ids": len(historical_ids),
        "historical_baseline_subset_sha256": node_ids_sha256(historical_ids),
        "current_primary_suite_node_ids": len(current_ids),
        "current_primary_suite_sha256": node_ids_sha256(current_ids),
        "selected_test_functions_by_file": {
            path: len(names) for path, names in sorted(selected_by_path.items())
        },
        "fixture_bindings": fixture_details,
    }


def pytest_arguments(
    python: Path,
    frozen_product: Path,
    manifest: dict[str, Any],
    output: Path,
) -> list[str]:
    paths = manifest["original_q2_suite"]["test_paths"]
    args = [str(frozen_product / path) for path in paths]
    for group in manifest["additional_installed_consumers"].values():
        group_path = str(frozen_product / group["test_path"])
        args.extend(f"{group_path}::{selector}" for selector in group["selectors"])
    return [
        str(python),
        "-I",
        "-m",
        "pytest",
        "-p",
        "q2_installed_origin_plugin",
        "-o",
        "addopts=",
        "-o",
        f"cache_dir={output / 'pytest-cache'}",
        "--import-mode=importlib",
        "--confcutdir",
        str(frozen_product / "tests/unit"),
        "--strict-markers",
        "-q",
        "-ra",
        "-s",
        "--junitxml",
        str(output / "wave-junit.xml"),
        "--basetemp",
        str(output / "pytest-tmp"),
        *args,
    ]


def junit_node_ids(junit_path: Path, original_doc_path: str) -> tuple[set[str], dict[str, int]]:
    root = SafeET.parse(junit_path).getroot()
    cases = list(root.iter("testcase"))
    node_ids: set[str] = set()
    counts = {"tests": len(cases), "skipped": 0, "failures": 0, "errors": 0}
    for case in cases:
        classname = case.attrib["classname"]
        if classname == "test_installed_catalog_defaults":
            path = original_doc_path
        else:
            dotted = classname.split(".")
            path = "/".join([*dotted[:-1], dotted[-1] + ".py"])
        node_ids.add(f"{path}::{case.attrib['name']}")
        counts["skipped"] += case.find("skipped") is not None
        counts["failures"] += case.find("failure") is not None
        counts["errors"] += case.find("error") is not None
    if len(node_ids) != len(cases):
        raise WaveFailure("pytest JUnit repeats a node ID")
    return node_ids, counts


def verify_consumer_run(
    result: subprocess.CompletedProcess[str],
    *,
    run_root: Path,
    output: Path,
    manifest: dict[str, Any],
    expected_original_ids: set[str],
    expected_current_ids: set[str],
) -> dict[str, Any]:
    nodeids_path = output / "collected-nodeids.json"
    origin_path = output / "origin-proof.json"
    junit_path = output / "wave-junit.xml"
    stdout_path = output / "consumer-suite.stdout.txt"
    stderr_path = output / "consumer-suite.stderr.txt"
    for path in (nodeids_path, origin_path, junit_path, stdout_path, stderr_path):
        if not path.is_file():
            raise WaveFailure(f"pytest did not produce required evidence: {path}")
    collected_list = json.loads(nodeids_path.read_text(encoding="utf-8"))
    collected = set(collected_list)
    if len(collected) != len(collected_list):
        raise WaveFailure("pytest collection contains duplicate IDs")
    missing_original = expected_original_ids - collected
    if missing_original:
        raise WaveFailure(f"frozen run omitted original Q2 IDs: {sorted(missing_original)}")
    historical_ids = historical_baseline_subset_ids(manifest, expected_original_ids)
    if not historical_ids <= expected_current_ids:
        raise WaveFailure("expected current suite omits its named historical baseline subset")
    if collected != expected_current_ids:
        raise WaveFailure(
            "collected consumer set differs from the content-bound current primary suite: "
            f"extra={sorted(collected - expected_current_ids)} "
            f"missing={sorted(expected_current_ids - collected)}"
        )
    actual, counts = junit_node_ids(
        junit_path,
        manifest["original_q2_suite"]["test_paths"][-1],
    )
    if actual != collected:
        raise WaveFailure(
            f"executed JUnit IDs differ from collection: missing={sorted(collected - actual)} "
            f"extra={sorted(actual - collected)}"
        )
    origin = json.loads(origin_path.read_text(encoding="utf-8"))
    if not origin.get("verified"):
        raise WaveFailure(f"installed origin/sys.path proof failed: {origin.get('errors')}")
    if not exact_nonbool_count_matches(counts["tests"], len(expected_current_ids)):
        raise WaveFailure(
            f"JUnit count differs from content-bound current suite: "
            f"actual={counts['tests']} expected={len(expected_current_ids)}"
        )
    if counts["skipped"] or counts["failures"] or counts["errors"]:
        raise WaveFailure(f"consumer suite did not complete cleanly: {counts}")
    if result.returncode:
        raise WaveFailure(f"pytest exited {result.returncode}; full output retained in {output}")
    if not exact_nonbool_count_matches(counts["tests"], len(collected)):
        raise WaveFailure(
            f"JUnit test count differs from collected node IDs: {counts} vs {len(collected)}"
        )
    return {
        "returncode": result.returncode,
        "counts": counts,
        "original_q2_ids": len(expected_original_ids),
        "selected_node_ids": len(collected),
        "selected_node_ids_sha256": node_ids_sha256(collected),
        "historical_baseline_subset_node_ids": len(historical_ids),
        "historical_baseline_subset_sha256": node_ids_sha256(historical_ids),
        "all_original_q2_ids_present": True,
        "additional_collected_ids": len(collected - expected_original_ids),
        "collected_nodeids_path": str(nodeids_path),
        "junit_path": str(junit_path),
        "origin_proof_path": str(origin_path),
        "process_output": {
            "capture_mode": (
                "pytest -s; complete child/test stdout and stderr captured by run_command"
            ),
            "stdout_path": str(stdout_path),
            "stdout_bytes": stdout_path.stat().st_size,
            "stdout_sha256": sha256_file(stdout_path),
            "stderr_path": str(stderr_path),
            "stderr_bytes": stderr_path.stat().st_size,
            "stderr_sha256": sha256_file(stderr_path),
        },
    }


def run_worker_profile(
    uv: str,
    supplied_python: str | None,
    frozen_product: Path,
    run_root: Path,
    env: dict[str, str],
    log_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    lock = frozen_product / "workers/dowhy-014/uv.lock"
    lock_hash_before = sha256_file(lock)
    if supplied_python:
        python = require_absolute_file(supplied_python, "--worker-python")
        mode = "pre-existing separate locked worker interpreter supplied by caller"
    else:
        if platform.system() != "Linux":
            raise WaveFailure(
                "worker provisioning is limited to Linux; supply an existing Linux "
                "worker interpreter or run this frozen wave on the supported Linux "
                "worker"
            )
        worker_env = run_root / "worker-profile-env"
        worker_env.mkdir(parents=True, exist_ok=False)
        setup_env = clean_child_env()
        setup_env["UV_PROJECT_ENVIRONMENT"] = str(worker_env / ".venv")
        profile = frozen_product / "workers/dowhy-014"
        offline = run_command(
            [uv, "sync", "--locked", "--offline", "--project", str(profile), "--python", "3.12"],
            cwd=run_root,
            env=setup_env,
            log_stem=log_dir / "worker-profile-sync-offline",
            check=False,
        )
        if offline.returncode:
            # Retain the failed offline evidence, then make the authorized locked online attempt.
            online = run_command(
                [uv, "sync", "--locked", "--project", str(profile), "--python", "3.12"],
                cwd=run_root,
                env=setup_env,
                log_stem=log_dir / "worker-profile-sync-online-fallback",
                check=False,
            )
            if online.returncode:
                raise WaveFailure(
                    "locked worker profile failed both offline setup and the online "
                    "locked fallback; both complete logs are retained"
                )
        python = worker_env / ".venv" / "bin" / "python"
        if not python.is_file():
            raise WaveFailure(
                f"locked worker sync did not produce the requested interpreter: {python}"
            )
        mode = "one locked profile env; offline first with retained online fallback if needed"
    info = interpreter_info(python, log_dir=log_dir, name="dowhy-worker")
    if info["version"][:2] != [3, 12]:
        raise WaveFailure(f"worker interpreter must be Python 3.12, got {info['version']}")
    version = distribution_version(Path(info["purelib"]), "dowhy")
    (log_dir / "dowhy-worker-version.stdout.txt").write_text(f"{version or ''}\n", encoding="utf-8")
    (log_dir / "dowhy-worker-version.stderr.txt").write_text("", encoding="utf-8")
    if version != "0.14":
        raise WaveFailure(f"worker environment must contain DoWhy 0.14: {version}")
    lock_hash_after = sha256_file(lock)
    if lock_hash_before != lock_hash_after:
        raise WaveFailure("worker setup changed the frozen uv.lock")
    return python, {
        "python": str(python),
        "mode": mode,
        "python_version": info["version"],
        "dowhy_version": version,
        "lock_sha256_before": lock_hash_before,
        "lock_sha256_after": lock_hash_after,
    }


def run_wave(args: argparse.Namespace) -> Path:
    repo = Path(args.repo).resolve(strict=True)
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        raise WaveFailure(f"--repo must be the attached repository root: {repo}")
    if platform.system() != "Linux":
        raise WaveFailure("the installed worker profile wave is scoped to the supported Linux host")
    frozen_source_preflight(repo, args.source_sha, args.source_tree)
    manifest_path, manifest, manifest_sha256 = load_verified_json_file(
        args.manifest,
        args.manifest_sha256,
        "primary source-freeze manifest",
        expected_schema_version=1,
    )
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_root = (
        Path(args.output_root).resolve() if args.output_root else HANDOFF_ROOT / "raw" / "runs"
    )
    output_root.mkdir(parents=True, exist_ok=True)
    run_root = output_root / f"{args.source_sha}-{stamp}-pid{os.getpid()}"
    run_root.mkdir(parents=False, exist_ok=False)
    (run_root / "logs").mkdir()
    receipt: dict[str, Any] = {
        "status": "running",
        "source_sha": args.source_sha,
        "source_tree": args.source_tree,
        "repo": str(repo),
        "started_utc": datetime.now(UTC).isoformat(),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha256,
        "uv": None,
        "profiles": {},
        "retention": "all files are retained; this runner has no cleanup path",
    }
    receipt_path = run_root / "run-receipt.json"
    json_write(receipt_path, receipt)
    try:
        env = clean_child_env()
        uv = shutil.which("uv")
        if not uv:
            raise WaveFailure("uv executable is not available on PATH")
        uv_version = run_command(
            [uv, "--version"], cwd=repo, env=env, log_stem=run_root / "logs" / "uv-version"
        ).stdout.strip()
        app_python = require_absolute_file(args.app_python, "--app-python")
        app_info = interpreter_info(app_python, log_dir=run_root / "logs", name="app-build")
        if app_info["implementation"] != "cpython" or app_info["version"][:2] != [3, 14]:
            raise WaveFailure(
                "application inventory interpreter must be CPython 3.14: "
                f"{app_info['implementation']} {app_info['version']}"
            )
        base_python = require_absolute_file(app_info["base_executable"], "app base Python")
        dependency_site = Path(app_info["purelib"]).resolve()
        receipt["uv"] = {
            "executable": str(Path(uv).resolve()),
            "version": uv_version,
            "sha256": sha256_file(Path(uv).resolve()),
        }
        receipt["app_build_interpreter"] = app_info
        origin_gate_source, _ = load_installed_origin_gate()
        receipt["installed_origin_gate_sha256"] = INSTALLED_ORIGIN_GATE_SHA256
        receipt["tooling_note"] = (
            "Hatchling distribution bytes come from the source-bound portable lock. "
            "The app environment is retained for source-owner inventory and consumers, "
            "not consulted by the isolated build-tools venv."
        )
        source_root = run_root / "frozen-source"
        archive_receipt, frozen_product = extract_frozen_product(
            repo, args.source_sha, source_root, run_root / "logs"
        )
        (
            buildtools,
            build_tool_profile,
            build_tool_lock_bytes,
            build_source_blobs,
            build_archive_members,
            _,
            build_tool_binding,
        ) = load_source_bound_build_tools(repo, args.source_sha, frozen_product)
        wheelhouse = run_root / "build-tool-quarantine"

        def prepare_source_bound_build_tools(lock: dict[str, Any]) -> dict[str, Any]:
            _, _, download_receipt = buildtools.fetch_locked_inputs(lock, wheelhouse)
            build_python_value, host_profile = configure_build_env(
                uv,
                base_python,
                lock,
                buildtools,
                wheelhouse,
                run_root,
                env,
                run_root / "logs",
            )
            return {
                "download_receipt": download_receipt,
                "python": str(build_python_value),
                "host_profile": host_profile,
            }

        admitted = buildtools.run_after_source_admission(
            build_tool_profile,
            build_archive_members["pyproject.toml"],
            build_tool_lock_bytes,
            build_source_blobs,
            build_archive_members,
            prepare_source_bound_build_tools,
        )
        build_tool_binding["source_transport"] = admitted["source_transport"]
        action_result = admitted["action_result"]
        downloaded_build_tool_receipt = action_result["download_receipt"]
        build_python = Path(action_result["python"])
        build_host_profile = action_result["host_profile"]
        receipt["portable_build_tool_distribution_closure"] = {
            **build_tool_binding,
            **downloaded_build_tool_receipt,
            "host_profile_status": build_host_profile["status"],
            "host_profile_path": "build-tools-host-profile.json",
            "host_profile_sha256": sha256_file(run_root / "build-tools-host-profile.json"),
            "upstream_release_witness": (
                "PyPI-supplied JSON and wheel digest; no signature/attestation claim"
            ),
        }
        json_write(receipt_path, receipt)
        owner_inventory = source_resource_inventory(
            app_python,
            frozen_product,
            run_root,
            run_root / "logs",
        )
        manifest, assets = read_asset_manifest(frozen_product, manifest, owner_inventory)
        owner_inventory_path = run_root / "runtime-resource-owner-inventory.json"
        json_write(owner_inventory_path, owner_inventory)
        owner_targets = sorted(row["wheel"] for row in owner_inventory["assets"])
        receipt["source_runtime_resource_contract"] = {
            "helper_path": f"{REQUIRED_PRODUCT}/{RESOURCE_CONTRACT_RELATIVE}",
            "helper_sha256": sha256_file(frozen_product / RESOURCE_CONTRACT_RELATIVE),
            "inventory_sha256": sha256_bytes(
                json.dumps(owner_inventory, sort_keys=True, separators=(",", ":")).encode()
            ),
            "resource_count": len(owner_targets),
            "targets": owner_targets,
        }
        project_metadata = tomllib.loads(
            (frozen_product / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]
        sdist_prefix = (
            project_metadata["name"].replace("-", "_") + f"-{project_metadata['version']}"
        )
        expected_original_ids = baseline_node_ids(frozen_product, manifest)
        if not exact_nonbool_count_matches(len(expected_original_ids), 91):
            raise WaveFailure(
                f"original Q2 expected ID denominator changed: {len(expected_original_ids)}"
            )
        current_primary_ids = verify_current_primary_suite_sources(
            frozen_product, manifest, expected_original_ids
        )
        transitive_bindings = verify_transitive_test_bindings(
            frozen_product,
            manifest,
            expected_original_ids,
        )
        receipt["git_archive"] = archive_receipt
        receipt["force_include_assets"] = assets
        receipt["force_include_count"] = len(assets)
        receipt["original_q2_ids"] = len(expected_original_ids)
        receipt["current_primary_suite_node_ids"] = len(current_primary_ids)
        receipt["current_primary_suite_sha256"] = node_ids_sha256(current_primary_ids)
        receipt["historical_baseline_subset_node_ids"] = len(
            historical_baseline_subset_ids(manifest, expected_original_ids)
        )
        receipt["transitive_test_bindings"] = transitive_bindings
        json_write(receipt_path, receipt)

        source_build = run_build(
            uv,
            build_python,
            frozen_product,
            run_root / "dist-source",
            wheel=True,
            sdist=True,
            log_dir=run_root / "logs",
            env=env,
        )
        if not (isinstance(source_build, tuple)):
            raise AssertionError()
        source_wheel, source_sdist = source_build
        source_wheel_receipt = verify_wheel(source_wheel, assets)
        sdist_receipt = verify_tar_assets(
            source_sdist,
            assets,
            member_prefix=f"{sdist_prefix}/",
            exact_force_directories=False,
        )
        sdist_product = product_root_from_sdist(
            source_sdist,
            run_root / "sdist-extracted" / sdist_prefix,
            frozen_product,
            sdist_prefix,
        )
        sdist_wheel = run_build(
            uv,
            build_python,
            sdist_product,
            run_root / "dist-sdist",
            wheel=True,
            sdist=False,
            log_dir=run_root / "logs",
            env=env,
        )
        if not (isinstance(sdist_wheel, Path)):
            raise AssertionError()
        sdist_wheel_receipt = verify_wheel(sdist_wheel, assets)

        gcp_output = run_root / "gcp-archive"
        gcp_archive_binding = run_frozen_gcp_archive_selector(
            repo=repo,
            frozen_product=frozen_product,
            source_sha=args.source_sha,
            source_tree=args.source_tree,
            output=gcp_output,
            python_bin=build_python,
            log_stem=run_root / "logs" / "gcp-package-archive",
        )
        gcp_archive = Path(gcp_archive_binding["archive_path"])
        receipt["gcp_archive_source_binding"] = gcp_archive_binding
        json_write(receipt_path, receipt)
        gcp_receipt = verify_tar_assets(
            gcp_archive,
            assets,
            member_prefix="policy-engine/",
            exact_force_directories=True,
        )
        gcp_product = product_root_from_gcp(
            gcp_archive,
            run_root / "gcp-extracted" / "policy-engine",
            frozen_product,
        )
        gcp_wheel = run_build(
            uv,
            build_python,
            gcp_product,
            run_root / "dist-gcp",
            wheel=True,
            sdist=False,
            log_dir=run_root / "logs",
            env=env,
        )
        if not (isinstance(gcp_wheel, Path)):
            raise AssertionError()
        gcp_wheel_receipt = verify_wheel(gcp_wheel, assets)

        worker_python, worker_info = run_worker_profile(
            uv,
            args.worker_python,
            frozen_product,
            run_root,
            env,
            run_root / "logs",
        )
        installed_python, purelib = configure_installed_env(
            uv,
            base_python,
            run_root,
            dependency_site,
            frozen_product,
            env,
            run_root / "logs",
            origin_gate_source,
        )

        run_inputs = {
            "E02_CATALOG_EXPECTED_JSON": run_root / "catalog-expected.json",
            "E02_PROFILE_EXPECTED_JSON": run_root / "profile-expected.json",
        }
        resources = {}
        for asset in assets:
            if asset["wheel"].startswith(RESOURCE_TARGET_ROOTS[0]):
                resources[Path(asset["source"]).name] = {
                    "bytes": asset["bytes"],
                    "sha256": asset["sha256"],
                }
        worker_assets = {
            Path(asset["source"]).name: {"bytes": asset["bytes"], "sha256": asset["sha256"]}
            for asset in assets
            if asset["source"].startswith("workers/dowhy-014/")
        }
        json_write(run_inputs["E02_CATALOG_EXPECTED_JSON"], {"resources": resources})
        json_write(run_inputs["E02_PROFILE_EXPECTED_JSON"], {"assets": worker_assets})
        receipt["inputs"] = {key: str(path) for key, path in run_inputs.items()}
        receipt["worker"] = worker_info

        profiles = [
            ("source-wheel", source_wheel, source_wheel_receipt),
            ("rebuilt-sdist-wheel", sdist_wheel, sdist_wheel_receipt),
            ("rebuilt-gcp-archive-wheel", gcp_wheel, gcp_wheel_receipt),
        ]
        bridge_consumers = manifest["additional_installed_consumers"]["canonical_bridge_and_worker"]
        for name, wheel_path, wheel_receipt in profiles:
            output = run_root / "consumer-runs" / name
            output.mkdir(parents=True, exist_ok=False)
            install = run_command(
                [
                    uv,
                    "pip",
                    "install",
                    "--offline",
                    "--reinstall",
                    "--no-deps",
                    "--python",
                    str(installed_python),
                    str(wheel_path),
                ],
                cwd=run_root,
                env=env,
                log_stem=output / "install-wheel",
            )
            del install
            if tuple(purelib.glob("*.pth")):
                raise WaveFailure(f"wheel install created a .pth file in the isolated env: {name}")
            runtime_proof = installed_runtime_proof(
                installed_python,
                purelib,
                assets,
                frozen_product,
                repo / REQUIRED_PRODUCT,
                dependency_site,
                run_root,
                name,
                env,
                output,
                owner_inventory_path,
                origin_gate_source,
            )
            worker_test_env = clean_child_env()
            worker_test_env.update(
                {
                    **{key: str(value) for key, value in run_inputs.items()},
                    "E02_TEST_DOWHY_WORKER_PYTHON": str(worker_python),
                    "E02_SOURCE_ROOT": str(frozen_product),
                    "E02_LIVE_PRODUCT_ROOT": str(repo / REQUIRED_PRODUCT),
                    "E02_DEPENDENCY_SITE": str(dependency_site),
                    "E02_NODEIDS_REPORT": str(output / "collected-nodeids.json"),
                    "E02_ORIGIN_REPORT": str(output / "origin-proof.json"),
                }
            )
            for kind, relative_path in bridge_consumers["fixture_paths"].items():
                worker_test_env[f"E02_{kind.upper()}_FIXTURE_PATH"] = str(
                    frozen_product / relative_path
                )
            result = run_command(
                pytest_arguments(installed_python, frozen_product, manifest, output),
                cwd=repo,
                env=worker_test_env,
                log_stem=output / "consumer-suite",
                check=False,
                stream_output=True,
            )
            consumer_receipt = verify_consumer_run(
                result,
                run_root=run_root,
                output=output,
                manifest=manifest,
                expected_original_ids=expected_original_ids,
                expected_current_ids=current_primary_ids,
            )
            receipt["profiles"][name] = {
                "wheel": wheel_receipt,
                "installed_runtime": runtime_proof,
                "consumers": consumer_receipt,
            }
            json_write(receipt_path, receipt)

        receipt["artifacts"] = {
            "source_wheel": source_wheel_receipt,
            "source_sdist": sdist_receipt,
            "rebuilt_sdist_wheel": sdist_wheel_receipt,
            "gcp_archive": gcp_receipt,
            "rebuilt_gcp_wheel": gcp_wheel_receipt,
        }
        _, _, final_manifest_sha256 = load_verified_json_file(
            manifest_path,
            manifest_sha256,
            "primary source-freeze manifest",
            expected_schema_version=1,
        )
        if final_manifest_sha256 != manifest_sha256:
            raise WaveFailure("primary source-freeze manifest changed during the wave")
        receipt["status"] = "pass"
        receipt["finished_utc"] = datetime.now(UTC).isoformat()
        json_write(receipt_path, receipt)
        return run_root
    except BaseException as error:
        receipt["status"] = "failed"
        receipt["failure"] = _failure_receipt_text(error)
        receipt["finished_utc"] = datetime.now(UTC).isoformat()
        json_write(receipt_path, receipt)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="attached, clean repository root")
    parser.add_argument("--source-sha", required=True, help="actual full SHA of the frozen commit")
    parser.add_argument("--source-tree", required=True, help="actual full tree SHA of that commit")
    parser.add_argument("--manifest", required=True, help="absolute frozen manifest path")
    parser.add_argument("--manifest-sha256", required=True, help="exact manifest SHA-256")
    parser.add_argument(
        "--app-python",
        required=True,
        help="absolute existing Python 3.14 build/test dependency interpreter",
    )
    parser.add_argument(
        "--worker-python", help="absolute existing Python 3.12 DoWhy 0.14 worker interpreter"
    )
    parser.add_argument(
        "--output-root", help="optional new-run parent; defaults to this ignored LOCAL raw/runs"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the installed wave and preserve its machine- and human-readable status."""

    try:
        completed_run = run_wave(parse_args(argv))
    except (OSError, WaveFailure, KeyError, ValueError, json.JSONDecodeError) as error:
        sys.stderr.write(f"Q2 frozen installed wave failed: {error}\n")
        return 1
    sys.stdout.write(f"Q2 frozen installed wave passed: {completed_run}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

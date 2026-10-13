#!/usr/bin/env python3
"""Recompute Q2 source/selector/resource inputs from an exact committed checkout.

This LOCAL-only admission utility does not build or install a package and does not
execute collected tests. Its `prepare` mode writes candidate manifest rebindings
to a new raw output directory. Its `check` mode additionally requires the source
manifest, supplement, and timeout-driver pins to equal those recomputations.
"""

from __future__ import annotations

import argparse
import ast
import copy
import difflib
import gzip
import hashlib
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any


HANDOFF_REL = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging"
)
MANIFEST_REL = f"{HANDOFF_REL}/installed-wave-manifest.json"
RUNNER_REL = f"{HANDOFF_REL}/raw/run.py"
TIMEOUT_REL = f"{HANDOFF_REL}/raw/timeout_driver.py"
SUPPLEMENT_REL = f"{HANDOFF_REL}/raw/supplemental_run.py"
SUPPLEMENT_MANIFEST_REL = f"{HANDOFF_REL}/raw/supplemental-manifest.json"
SITE_CUSTOMIZE_REL = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/linux-profile/raw/sitecustomize.py"
REVIEWED_PROFILE_NAMES = (
    "source-wheel",
    "rebuilt-sdist-wheel",
    "rebuilt-gcp-archive-wheel",
)
HATCH_REL = "policy-engine/hatch.toml"
APP_PROJECT_REL = "policy-engine/pyproject.toml"
APP_LOCK_REL = "policy-engine/uv.lock"
DOWHY_PROJECT_REL = "policy-engine/workers/dowhy-014/pyproject.toml"
DOWHY_LOCK_REL = "policy-engine/workers/dowhy-014/uv.lock"
DOWHY_PYTHON_REL = "policy-engine/workers/dowhy-014/.python-version"
DOWHY_README_REL = "policy-engine/workers/dowhy-014/README.md"
GCP_PACKAGE_REL = "policy-engine/ops/cloud/gcp/package_repo.sh"


class AuditFailure(RuntimeError):
    """Raised when source-derived Q2 inputs do not satisfy the current runner."""


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


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_ids_sha256(ids: set[str] | list[str]) -> str:
    return sha256(("\n".join(sorted(ids)) + "\n").encode("utf-8"))


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in value:
        raise AuditFailure(f"unsafe source-relative path: {value!r}")
    return path


def git_run(repo: Path, *args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=False)
    if result.returncode:
        stderr = result.stderr.decode("utf-8", "replace").strip()
        raise AuditFailure(f"git {' '.join(args)} failed ({result.returncode}): {stderr}")
    return result.stdout if binary else result.stdout.decode("utf-8", "strict").strip()


def read_commit_blob(repo: Path, commit: str, relative: str) -> bytes:
    """Read one regular blob directly from a commit object; reject symlinks."""
    safe_relative(relative)
    raw = git_run(repo, "ls-tree", "-z", commit, "--", relative, binary=True)
    assert isinstance(raw, bytes)
    entries = [entry for entry in raw.split(b"\0") if entry]
    if len(entries) != 1:
        raise AuditFailure(f"source object is absent or ambiguous at {commit}:{relative}")
    header, actual_path = entries[0].split(b"\t", 1)
    mode, kind, object_id = header.decode("ascii").split()
    if actual_path.decode("utf-8", "strict") != relative:
        raise AuditFailure(f"Git path mismatch for {relative}")
    if mode not in {"100644", "100755"} or kind != "blob":
        raise AuditFailure(f"source object must be a regular file: {relative} ({mode} {kind})")
    data = git_run(repo, "cat-file", "blob", object_id, binary=True)
    assert isinstance(data, bytes)
    return data


def require_frozen_checkout(repo: Path, source_sha: str, source_tree: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise AuditFailure("source SHA must be a full 40-character commit SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", source_tree):
        raise AuditFailure("source tree must be a full 40-character tree SHA")
    root = Path(str(git_run(repo, "rev-parse", "--show-toplevel"))).resolve(strict=True)
    if root != repo.resolve(strict=True):
        raise AuditFailure(f"repo must be the attached checkout root: {root}")
    if git_run(repo, "symbolic-ref", "-q", "HEAD") == "":
        raise AuditFailure("source checkout is detached")
    if git_run(repo, "rev-parse", "HEAD") != source_sha:
        raise AuditFailure("attached source HEAD differs from supplied freeze SHA")
    if git_run(repo, "rev-parse", f"{source_sha}^{{tree}}") != source_tree:
        raise AuditFailure("supplied source tree differs from the commit object")
    if git_run(repo, "status", "--porcelain=v1", "--untracked-files=no"):
        raise AuditFailure(
            "tracked source is dirty; source-object readback is not an executable freeze"
        )


def read_regular_local(path: Path) -> bytes:
    """Read an ignored local input through a no-follow descriptor walk of every component."""
    if not path.is_absolute():
        raise AuditFailure(f"input path must be absolute: {path}")
    path = Path(os.path.abspath(path))
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise AuditFailure("local input cannot be opened safely on this platform")
    if os.open not in os.supports_dir_fd or os.stat not in os.supports_dir_fd:
        raise AuditFailure("local input cannot be opened safely with directory descriptors")
    parts = path.parts[1:]
    if path.anchor != os.sep or not parts:
        raise AuditFailure(f"local input must name a file below the filesystem root: {path}")

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
                raise AuditFailure(
                    f"local input contains a replaced or symlinked directory: {component}"
                )
            directory_identities.append((opened.st_dev, opened.st_ino))
            current_fd = next_fd

        final_name = parts[-1]
        before = os.stat(final_name, dir_fd=current_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise AuditFailure(f"input must be a regular non-symlink file: {path}")
        file_descriptor = os.open(final_name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=current_fd)
        with os.fdopen(file_descriptor, "rb") as stream:
            file_descriptor = -1
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
                before.st_dev,
                before.st_ino,
            ):
                raise AuditFailure(f"input was replaced before it was opened: {path}")
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
            raise AuditFailure(f"input changed while it was read: {path}")

        cursor = Path(path.anchor)
        component_index = 0
        for component in parts:
            cursor = cursor / component
            observed = cursor.lstat()
            if stat.S_ISLNK(observed.st_mode):
                raise AuditFailure(f"local input contains a symlinked path component: {cursor}")
            if component_index < len(directory_identities):
                expected_identity = directory_identities[component_index]
                if (
                    not stat.S_ISDIR(observed.st_mode)
                    or (observed.st_dev, observed.st_ino) != expected_identity
                ):
                    raise AuditFailure(f"local input path changed while it was read: {cursor}")
            elif file_signature(observed) != file_signature(before):
                raise AuditFailure(f"local input path changed while it was read: {cursor}")
            component_index += 1
        if path.resolve(strict=True) != path:
            raise AuditFailure(f"local input path does not resolve to its supplied path: {path}")
        return data
    except AuditFailure:
        raise
    except (OSError, NotImplementedError, TypeError) as error:
        raise AuditFailure(
            f"input could not be read without following symlinks: {path}: {error}"
        ) from error
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        for descriptor in reversed(directory_fds):
            os.close(descriptor)


def parse_json(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditFailure(f"invalid UTF-8 JSON in {label}: {error}") from error
    if not isinstance(value, dict):
        raise AuditFailure(f"JSON root must be an object: {label}")
    if not exact_nonbool_count_matches(value.get("schema_version"), 1):
        raise AuditFailure(f"unsupported manifest schema version: {label}")
    return value


def baseline_ids_from_junit(compressed: bytes, manifest: dict[str, Any]) -> set[str]:
    baseline = manifest["original_q2_suite"]
    if sha256(compressed) != baseline["baseline_junit_sha256"]:
        raise AuditFailure("source JUnit bytes differ from the original baseline digest")
    try:
        root = ET.fromstring(gzip.decompress(compressed))
    except (OSError, ET.ParseError) as error:
        raise AuditFailure(f"original Q2 JUnit is unreadable: {error}") from error
    cases = list(root.iter("testcase"))
    if not exact_nonbool_count_matches(baseline.get("baseline_case_count"), len(cases)):
        raise AuditFailure(
            f"original Q2 JUnit count differs: {len(cases)} != {baseline['baseline_case_count']}"
        )
    test_paths = baseline["test_paths"]
    ids: set[str] = set()
    for case in cases:
        classname = case.attrib.get("classname", "")
        name = case.attrib.get("name", "")
        if not classname or not name:
            raise AuditFailure("original Q2 JUnit case omits classname or name")
        if classname == "test_installed_catalog_defaults":
            test_path = test_paths[-1]
        else:
            parts = classname.split(".")
            test_path = "/".join(parts[:-1] + [parts[-1] + ".py"])
        if test_path not in test_paths:
            raise AuditFailure(
                f"original Q2 JUnit case falls outside baseline source paths: {classname}"
            )
        ids.add(f"{test_path}::{name}")
    if len(ids) != len(cases):
        raise AuditFailure("original Q2 JUnit contains duplicate reconstructed node IDs")
    return ids


def parse_collected_ids(stdout: str, allowed_paths: set[str]) -> set[str]:
    ids: list[str] = []
    for line in stdout.splitlines():
        value = line.strip()
        for path in allowed_paths:
            if value.startswith(f"{path}::"):
                ids.append(value)
                break
    result = set(ids)
    if not result:
        raise AuditFailure("pytest collect-only produced no canonical node IDs")
    if len(result) != len(ids):
        raise AuditFailure("pytest collect-only output repeated a node ID")
    return result


def collect_ids(
    *,
    repo: Path,
    python: Path,
    product: Path,
    selectors: list[str],
    allowed_paths: set[str],
    output_root: Path,
    label: str,
    timeout_seconds: float,
) -> tuple[set[str], dict[str, Any]]:
    args = [
        str(python),
        "-B",
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "--collect-only",
        "-q",
        "--no-header",
        "--no-summary",
        "--color=no",
        "-o",
        "addopts=",
        "--import-mode=importlib",
        "--confcutdir",
        str(product / "tests/unit"),
        "--rootdir",
        str(product),
        *selectors,
    ]
    env = os.environ.copy()
    for key in (
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "VIRTUAL_ENV",
        "CONDA_PREFIX",
        "UV_PROJECT_ENVIRONMENT",
        "UV_PYTHON",
    ):
        env.pop(key, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = os.pathsep.join((str(product / "src"), str(product)))
    env["POLISYOS_RUN_INTEGRATION"] = "1"
    started = time.monotonic()
    try:
        result = subprocess.run(
            args,
            cwd=product,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = (
            error.stdout.decode("utf-8", "replace")
            if isinstance(error.stdout, bytes)
            else (error.stdout or "")
        )
        stderr = (
            error.stderr.decode("utf-8", "replace")
            if isinstance(error.stderr, bytes)
            else (error.stderr or "")
        )
        (output_root / f"{label}.stdout.txt").write_text(stdout, encoding="utf-8")
        (output_root / f"{label}.stderr.txt").write_text(stderr, encoding="utf-8")
        raise AuditFailure(
            f"source pytest collection timed out after {timeout_seconds}s: {label}"
        ) from error
    wall = time.monotonic() - started
    (output_root / f"{label}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (output_root / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    record = {
        "argv": args,
        "cwd": str(product),
        "returncode": result.returncode,
        "timeout_seconds": timeout_seconds,
        "wall_seconds": wall,
        "stdout_sha256": sha256(result.stdout.encode("utf-8")),
        "stderr_sha256": sha256(result.stderr.encode("utf-8")),
        "collected_node_count": None,
        "collected_node_ids_sha256": None,
    }
    if result.returncode:
        raise AuditFailure(f"source pytest collection exited {result.returncode}: {label}")
    ids = parse_collected_ids(result.stdout, allowed_paths)
    record["collected_node_count"] = len(ids)
    record["collected_node_ids_sha256"] = canonical_ids_sha256(ids)
    return ids, record


def selected_group_ids(group: dict[str, Any], collected: set[str]) -> set[str]:
    path = group["test_path"]
    selectors = group["selectors"]
    if not isinstance(path, str) or not isinstance(selectors, list) or not selectors:
        raise AuditFailure("installed consumer group must have a test_path and selectors")
    resolved: set[str] = set()
    for selector in selectors:
        if not isinstance(selector, str) or not selector:
            raise AuditFailure(f"invalid selector in {path}: {selector!r}")
        stem = f"{path}::{selector}"
        if "[" in selector:
            matches = {node_id for node_id in collected if node_id == stem}
        else:
            matches = {
                node_id
                for node_id in collected
                if node_id == stem or node_id.startswith(stem + "[")
            }
        if not matches:
            raise AuditFailure(f"declared selector did not resolve in actual collection: {stem}")
        resolved.update(matches)
    return resolved


def asset_rows_from_config(
    repo: Path, source_sha: str, manifest: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    hatch = tomllib.loads(read_commit_blob(repo, source_sha, HATCH_REL).decode("utf-8"))
    build = hatch["build"]["targets"]
    force_include = build["wheel"]["force-include"]
    sdist_include = set(build["sdist"]["include"])
    if not isinstance(force_include, dict) or not force_include:
        raise AuditFailure("frozen hatch.toml must define a nonempty wheel force-include map")
    rows: list[dict[str, Any]] = []
    for source, wheel in sorted(force_include.items()):
        if not isinstance(source, str) or not isinstance(wheel, str):
            raise AuditFailure("wheel force-include entries must map strings to strings")
        source_rel = f"policy-engine/{safe_relative(source).as_posix()}"
        archive = f"policy-engine/{source}"
        if source not in sdist_include:
            raise AuditFailure(f"source distribution omits wheel resource source: {source}")
        data = read_commit_blob(repo, source_sha, source_rel)
        rows.append(
            {
                "source": source,
                "archive": archive,
                "wheel": wheel,
                "bytes": len(data),
                "sha256": sha256(data),
            }
        )
    return rows, {
        "hatch_config_sha256": sha256(read_commit_blob(repo, source_sha, HATCH_REL)),
        "wheel_force_include_count": len(rows),
        "sdist_include_reconciled": True,
        "force_include_map_sha256": canonical_json_sha256(force_include),
        "asset_targets_sha256": canonical_json_sha256(rows),
        "source_derived_resource_count": len(rows),
        "source_resource_map_nonempty": bool(rows),
        "assets": rows,
        "resource_wheel_targets": sorted(str(row["wheel"]) for row in rows),
    }


def canonical_json_sha256(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(data)


def installed_origin_gate_binding(primary_source: bytes) -> tuple[str, str]:
    """Resolve the exact ignored local gate filename/hash declared by the frozen runner."""
    try:
        tree = ast.parse(primary_source.decode("utf-8", "strict"), filename=RUNNER_REL)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise AuditFailure("primary runner cannot be parsed for its installed-origin gate") from error
    values: dict[str, ast.expr] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
        for name in ("INSTALLED_ORIGIN_GATE_PATH", "INSTALLED_ORIGIN_GATE_SHA256"):
            if name in targets:
                if targets != [name] or name in values:
                    raise AuditFailure(f"primary runner has an ambiguous {name} binding")
                values[name] = node.value
    if set(values) != {"INSTALLED_ORIGIN_GATE_PATH", "INSTALLED_ORIGIN_GATE_SHA256"}:
        raise AuditFailure("primary runner omits its exact installed-origin gate binding")
    path_value = values["INSTALLED_ORIGIN_GATE_PATH"]
    if not (isinstance(path_value, ast.BinOp) and isinstance(path_value.op, ast.Div) and isinstance(path_value.left, ast.Name) and path_value.left.id == "HERE" and isinstance(path_value.right, ast.Constant) and type(path_value.right.value) is str):
        raise AuditFailure("installed-origin gate path is not a literal HERE-relative filename")
    filename = path_value.right.value
    if not filename.endswith(".py") or Path(filename).name != filename or filename in {"", ".", ".."} or chr(92) in filename or "/" in filename:
        raise AuditFailure("installed-origin gate filename is not one safe Python source member")
    digest_value = values["INSTALLED_ORIGIN_GATE_SHA256"]
    if not isinstance(digest_value, ast.Constant) or type(digest_value.value) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest_value.value):
        raise AuditFailure("installed-origin gate SHA-256 is not one full lowercase digest")
    relative = f"{HANDOFF_REL}/raw/{filename}"
    safe_relative(relative)
    return relative, digest_value.value


def input_file_records(
    repo: Path,
    source_sha: str,
    supplemental_manifest_value: str,
    supplemental_manifest_sha256: str,
) -> tuple[dict[str, Any], dict[str, bytes]]:
    tracked = (
        MANIFEST_REL,
        RUNNER_REL,
        TIMEOUT_REL,
        SUPPLEMENT_REL,
        SUPPLEMENT_MANIFEST_REL,
        SITE_CUSTOMIZE_REL,
        HATCH_REL,
        APP_PROJECT_REL,
        APP_LOCK_REL,
        DOWHY_PROJECT_REL,
        DOWHY_LOCK_REL,
        DOWHY_PYTHON_REL,
        DOWHY_README_REL,
        GCP_PACKAGE_REL,
    )
    tracked_rows: dict[str, Any] = {}
    capsule_contents: dict[str, bytes] = {}
    for relative in tracked:
        data = read_commit_blob(repo, source_sha, relative)
        tracked_rows[relative] = {"bytes": len(data), "sha256": sha256(data)}
        capsule_contents[relative] = data
    supplemental_manifest_path = Path(supplemental_manifest_value)
    if not supplemental_manifest_path.is_absolute():
        raise AuditFailure("supplemental manifest path must be absolute")
    supplemental_manifest_path = Path(os.path.abspath(supplemental_manifest_path))
    try:
        supplemental_manifest_relative = supplemental_manifest_path.relative_to(repo).as_posix()
    except ValueError as error:
        raise AuditFailure(
            "supplemental manifest must be inside the attached repository"
        ) from error
    safe_relative(supplemental_manifest_relative)
    if not re.fullmatch(r"[0-9a-f]{64}", supplemental_manifest_sha256):
        raise AuditFailure("supplemental manifest SHA-256 must be full lowercase hex")
    if supplemental_manifest_relative == SUPPLEMENT_MANIFEST_REL:
        supplemental_manifest_bytes = capsule_contents[SUPPLEMENT_MANIFEST_REL]
    else:
        supplemental_manifest_path = repo / supplemental_manifest_relative
        ignored = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "check-ignore",
                "--quiet",
                "--",
                supplemental_manifest_relative,
            ],
            capture_output=True,
            check=False,
        )
        if ignored.returncode != 0:
            raise AuditFailure(
                f"external supplemental manifest is not an ignored path: {supplemental_manifest_relative}"
            )
        supplemental_manifest_bytes = read_regular_local(supplemental_manifest_path)
        capsule_contents[supplemental_manifest_relative] = supplemental_manifest_bytes

    raw_rows: dict[str, Any] = {}
    origin_gate_relative, origin_gate_sha256 = installed_origin_gate_binding(capsule_contents[RUNNER_REL])
    gate_ignored = subprocess.run(["git", "-C", str(repo), "check-ignore", "--quiet", "--", origin_gate_relative], capture_output=True, check=False)
    if gate_ignored.returncode != 0:
        raise AuditFailure("installed-origin gate must remain an ignored local runner input")
    origin_gate_bytes = read_regular_local(repo / origin_gate_relative)
    if sha256(origin_gate_bytes) != origin_gate_sha256:
        raise AuditFailure("local installed-origin gate differs from the exact source-runner SHA pin")
    raw_rows[origin_gate_relative] = {"bytes": len(origin_gate_bytes), "sha256": origin_gate_sha256, "ignored": True}
    capsule_contents[origin_gate_relative] = origin_gate_bytes
    if sha256(supplemental_manifest_bytes) != supplemental_manifest_sha256:
        raise AuditFailure(
            "explicit supplemental manifest SHA-256 differs from its exact input bytes"
        )
    if supplemental_manifest_relative != SUPPLEMENT_MANIFEST_REL:
        raw_rows[supplemental_manifest_relative] = {
            "bytes": len(supplemental_manifest_bytes),
            "sha256": sha256(supplemental_manifest_bytes),
            "ignored": True,
        }
    return {
        "tracked_git_objects": tracked_rows,
        "ignored_local_inputs": raw_rows,
        "supplemental_manifest_path": str(supplemental_manifest_path),
        "supplemental_manifest_sha256": supplemental_manifest_sha256,
    }, capsule_contents


def profile_names_from_runner_sources(
    primary_source: bytes, supplemental_source: bytes
) -> tuple[list[str], list[str]]:
    """Extract the three literal profile contracts from both existing runners."""
    primary_tree = ast.parse(primary_source.decode("utf-8"), filename=RUNNER_REL)
    supplemental_tree = ast.parse(supplemental_source.decode("utf-8"), filename=SUPPLEMENT_REL)
    primary_candidates: list[list[str]] = []
    for node in ast.walk(primary_tree):
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "profiles" for target in node.targets
        ):
            continue
        value = node.value
        if isinstance(value, ast.List) and all(
            isinstance(item, ast.Tuple)
            and item.elts
            and isinstance(item.elts[0], ast.Constant)
            and isinstance(item.elts[0].value, str)
            for item in value.elts
        ):
            primary_candidates.append([item.elts[0].value for item in value.elts])
    supplemental_names: list[str] | None = None
    for node in supplemental_tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "PROFILE_NAMES" for target in node.targets
        ):
            if isinstance(node.value, (ast.Tuple, ast.List)) and all(
                isinstance(item, ast.Constant) and isinstance(item.value, str)
                for item in node.value.elts
            ):
                supplemental_names = [item.value for item in node.value.elts]
    if len(primary_candidates) != 1 or supplemental_names is None:
        raise AuditFailure("cannot derive one literal profile list from both existing Q2 runners")
    return primary_candidates[0], supplemental_names


def profile_contract_is_supported(
    manifest_names: list[str], primary_names: list[str], supplemental_names: list[str]
) -> bool:
    return (
        tuple(manifest_names) == REVIEWED_PROFILE_NAMES
        and tuple(primary_names) == REVIEWED_PROFILE_NAMES
        and tuple(supplemental_names) == REVIEWED_PROFILE_NAMES
    )


def primary_manifest_matches_collection(
    manifest: dict[str, Any],
    expected_ids: set[str],
    expected_assets: list[dict[str, Any]],
    source_hashes: dict[str, str],
) -> bool:
    """Reconcile all current primary count-bearing declarations to source objects."""
    suite = manifest.get("current_primary_suite")
    candidate = manifest.get("candidate_baseline")
    if not isinstance(suite, dict) or not isinstance(candidate, dict):
        return False
    ids = suite.get("selected_node_ids")
    return (
        isinstance(ids, list)
        and ids == sorted(expected_ids)
        and exact_nonbool_count_matches(suite.get("selected_node_count"), len(expected_ids))
        and suite.get("selected_node_ids_sha256") == canonical_ids_sha256(expected_ids)
        and json_values_match_exactly(suite.get("source_file_sha256"), source_hashes)
        and exact_nonbool_count_matches(candidate.get("force_include_count"), len(expected_assets))
        and json_values_match_exactly(candidate.get("force_include_assets"), expected_assets)
    )


def supplemental_manifest_count_mismatches(
    manifest: dict[str, Any], *, asset_count: int, supplemental_id_count: int
) -> list[str]:
    """Return source-freeze count fields that fail exact typed content reconciliation."""
    mismatches: list[str] = []
    primary_inputs = manifest.get("primary_inputs")
    supplement = manifest.get("supplemental_suite")
    if not isinstance(primary_inputs, dict) or not exact_nonbool_count_matches(
        primary_inputs.get("force_include_asset_count_per_profile"), asset_count
    ):
        mismatches.append("force_include_asset_count_per_profile")
    if not isinstance(supplement, dict) or not exact_nonbool_count_matches(
        supplement.get("expected_node_count"), supplemental_id_count
    ):
        mismatches.append("supplemental_suite.expected_node_count")
    return mismatches


def manifest_mismatches(
    current: dict[str, Any], proposed: dict[str, Any], current_raw: bytes, proposed_raw: bytes
) -> list[str]:
    mismatches: list[str] = []
    if current_raw != proposed_raw:
        for key in ("candidate_baseline", "current_primary_suite"):
            if not json_values_match_exactly(current.get(key), proposed.get(key)):
                mismatches.append(key)
    return mismatches


def rebind_timeout_driver(source: str, runner_sha: str) -> tuple[str, bytes]:
    tree = ast.parse(source)
    values: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if len(targets) == 1 and targets[0] == "EXPECTED_RUNNER_SHA256":
                if not isinstance(node.value, ast.Constant) or not isinstance(
                    node.value.value, str
                ):
                    raise AuditFailure("timeout driver runner pin is not a literal")
                values[targets[0]] = node.value.value
    if set(values) != {"EXPECTED_RUNNER_SHA256"}:
        raise AuditFailure("timeout driver must expose one reviewed runner SHA pin")
    literal = f'EXPECTED_RUNNER_SHA256 = "{values["EXPECTED_RUNNER_SHA256"]}"'
    if source.count(literal) != 1:
        raise AuditFailure("cannot safely rebind exactly one timeout-driver runner pin")
    updated = source.replace(literal, f'EXPECTED_RUNNER_SHA256 = "{runner_sha}"', 1)
    return updated, updated.encode("utf-8")


def validate_recomputed_ids(
    manifest: dict[str, Any],
    expected_ids: set[str],
    expected_assets: list[dict[str, Any]] | None = None,
) -> None:
    suite = manifest.get("current_primary_suite")
    if not isinstance(suite, dict):
        raise AuditFailure("manifest omits current_primary_suite")
    declared = suite.get("selected_node_ids")
    if not isinstance(declared, list) or declared != sorted(set(declared)):
        raise AuditFailure("selected_node_ids must be sorted and unique")
    if not exact_nonbool_count_matches(suite.get("selected_node_count"), len(declared)):
        raise AuditFailure("selected_node_count does not equal the declared ID list length")
    if suite.get("selected_node_ids_sha256") != canonical_ids_sha256(declared):
        raise AuditFailure("selected_node_ids_sha256 does not recompute from the ID list")
    if set(declared) != expected_ids:
        missing = sorted(expected_ids - set(declared))
        extra = sorted(set(declared) - expected_ids)
        raise AuditFailure(
            f"declared node IDs differ from actual source collection: missing={missing[:8]} extra={extra[:8]}"
        )
    if expected_assets is not None:
        candidate = manifest.get("candidate_baseline")
        actual_assets = (
            candidate.get("force_include_assets") if isinstance(candidate, dict) else None
        )
        if (
            not isinstance(candidate, dict)
            or not exact_nonbool_count_matches(
                candidate.get("force_include_count"), len(expected_assets)
            )
            or not json_values_match_exactly(actual_assets, expected_assets)
        ):
            raise AuditFailure(
                "manifest force-include resources differ from frozen hatch.toml and source bytes"
            )


def validate_supplemental_node_ids(manifest: dict[str, Any], expected_ids: set[str]) -> None:
    suite = manifest.get("supplemental_suite")
    if not isinstance(suite, dict):
        raise AuditFailure("supplemental manifest omits its suite")
    declared = suite.get("selected_node_ids")
    if (
        not isinstance(declared, list)
        or not declared
        or any(not isinstance(item, str) for item in declared)
    ):
        raise AuditFailure("supplemental selected IDs must be a nonempty string list")
    if declared != sorted(set(declared)):
        raise AuditFailure("supplemental selected IDs must be sorted and unique")
    declared_count = suite.get("expected_node_count")
    if not exact_nonbool_count_matches(declared_count, len(declared)):
        raise AuditFailure("supplemental selected-ID count differs from its full list")
    if suite.get("selected_node_ids_sha256") != canonical_ids_sha256(declared):
        raise AuditFailure("supplemental selected-ID digest differs from its full list")
    if set(declared) != expected_ids:
        raise AuditFailure("supplemental manifest IDs differ from actual source collection")
    group = {"test_path": suite.get("test_path"), "selectors": suite.get("selectors")}
    if selected_group_ids(group, expected_ids) != expected_ids:
        raise AuditFailure("supplemental source collection contains undeclared selector IDs")


def self_test_origin_gate_symlink() -> bool:
    """Load same-byte modules through outside symlink paths and require refusal."""
    import importlib.machinery
    import importlib.util
    import runpy
    import tempfile

    gate_path = Path(__file__).resolve(strict=True).with_name("installed_origin_gate_r4.py")
    if not gate_path.is_file():
        raise AuditFailure(f"installed-origin gate source is missing: {gate_path}")
    verify = runpy.run_path(str(gate_path)).get("verify_loaded_module_origins")
    if not callable(verify):
        raise AuditFailure("installed-origin gate has no generic loaded-module verifier")
    with tempfile.TemporaryDirectory(prefix="q2-origin-") as scratch:
        root = Path(scratch)
        purelib, outside = root / "site-packages", root / "outside"
        purelib.mkdir()
        outside.mkdir()
        nested = outside / "nested"
        nested.mkdir()
        source = purelib / "origin_probe.py"
        payload = b"VALUE = 17\n"
        source.write_bytes(payload)
        outside_target = outside / "origin_probe.py"
        outside_target.write_bytes(payload)
        direct_alias = outside / "origin_probe_alias.py"
        direct_alias.symlink_to(source)
        escape = purelib / "escape"
        escape.symlink_to(nested, target_is_directory=True)
        if direct_alias.read_bytes() != source.read_bytes() or outside_target.read_bytes() != source.read_bytes():
            raise AuditFailure("outside origin controls do not preserve identical bytes")

        inside_spec = importlib.util.spec_from_file_location("polisyos.origin_probe_inside", source)
        direct_spec = importlib.util.spec_from_file_location("polisyos.origin_probe_direct_escape", direct_alias)
        if inside_spec is None or inside_spec.loader is None or direct_spec is None or direct_spec.loader is None:
            raise AuditFailure("cannot construct real importlib module-origin controls")
        inside_module = importlib.util.module_from_spec(inside_spec)
        inside_spec.loader.exec_module(inside_module)
        _, inside_errors = verify(purelib, {inside_spec.name: inside_module})
        if inside_errors:
            raise AuditFailure(f"inside installed module was rejected: {inside_errors}")

        direct_module = importlib.util.module_from_spec(direct_spec)
        direct_spec.loader.exec_module(direct_module)
        if Path(direct_module.__file__).resolve(strict=True).is_relative_to(purelib.resolve(strict=True)):
            raise AuditFailure("direct symlink control did not resolve to the inside target")
        _, direct_errors = verify(purelib, {direct_spec.name: direct_module})
        direct_rejected = any(error.get("module") == direct_spec.name for error in direct_errors)

        # SourceFileLoader is the real Python source loader; using its raw path
        # preserves the link/.. traversal that abspath would erase before stat.
        traversal_path = purelib / "escape" / ".." / "origin_probe.py"
        traversal_name = "polisyos.origin_probe_parent_escape"
        traversal_loader = importlib.machinery.SourceFileLoader(traversal_name, str(traversal_path))
        traversal_spec = importlib.machinery.ModuleSpec(traversal_name, traversal_loader, origin=str(traversal_path))
        traversal_spec.has_location = True
        traversal_module = importlib.util.module_from_spec(traversal_spec)
        traversal_loader.exec_module(traversal_module)
        reported = Path(traversal_module.__file__)
        if reported != traversal_path:
            raise AuditFailure("source loader did not preserve the reported parent-traversal origin")
        resolved = reported.resolve(strict=True)
        if resolved.is_relative_to(purelib.resolve(strict=True)) or resolved.read_bytes() != source.read_bytes():
            raise AuditFailure("parent-traversal control did not load identical bytes from outside purelib")
        _, traversal_errors = verify(purelib, {traversal_name: traversal_module})
        traversal_rejected = any(error.get("module") == traversal_name for error in traversal_errors)
        return direct_rejected and traversal_rejected

def self_test() -> dict[str, Any]:
    """Exercise manifest drift controls without a repository, build, or test suite."""
    baseline = {"tests/unit/test_source.py::test_baseline"}
    selected = {"tests/unit/test_consumer.py::test_consumes_bound_artifact"}
    actual = baseline | selected
    template: dict[str, Any] = {
        "current_primary_suite": {
            "selected_node_ids": sorted(actual),
            "selected_node_count": 2,
            "selected_node_ids_sha256": canonical_ids_sha256(actual),
        },
        "additional_installed_consumers": {
            "consumer": {
                "test_path": "tests/unit/test_consumer.py",
                "selectors": ["test_consumes_bound_artifact"],
            }
        },
        "candidate_baseline": {
            "force_include_assets": [
                {"source": "x", "wheel": "pkg/_resources/x", "bytes": 1, "sha256": "a" * 64}
            ]
        },
    }
    validate_recomputed_ids(template, actual)

    cases: dict[str, bool] = {}
    expanded_actual = actual | {"tests/unit/test_registry.py::test_registry[missing]", "tests/unit/test_registry.py::test_registry[unreadable]", "tests/unit/test_registry.py::test_registry[corrupt]"}
    expanded_manifest = copy.deepcopy(template)
    expanded_suite = expanded_manifest["current_primary_suite"]
    expanded_suite["selected_node_ids"] = sorted(expanded_actual)
    expanded_suite["selected_node_count"] = len(expanded_actual)
    expanded_suite["selected_node_ids_sha256"] = canonical_ids_sha256(expanded_actual)
    validate_recomputed_ids(expanded_manifest, expanded_actual, template["candidate_baseline"]["force_include_assets"])
    cases["count-derived-from-complete-variable-collection"] = expanded_suite["selected_node_count"] == len(expanded_actual) and len(expanded_actual) != len(actual)
    for name, mutate in (
        (
            "corrupt-count-mismatch",
            lambda value: value["current_primary_suite"].update(selected_node_count=3),
        ),
        (
            "float-count-alias",
            lambda value: value["current_primary_suite"].update(selected_node_count=2.0),
        ),
        (
            "boolean-count-alias",
            lambda value: value["current_primary_suite"].update(selected_node_count=True),
        ),
        (
            "string-count-alias",
            lambda value: value["current_primary_suite"].update(selected_node_count="2"),
        ),
        (
            "negative-count",
            lambda value: value["current_primary_suite"].update(selected_node_count=-1),
        ),
        (
            "corrupt-digest",
            lambda value: value["current_primary_suite"].update(selected_node_ids_sha256="0" * 64),
        ),
        # Leave the selector marker and the independently collected source IDs untouched.
        (
            "remove-selected-id-with-marker-preserved",
            lambda value: value["current_primary_suite"].update(
                selected_node_ids=sorted(baseline),
                selected_node_count=len(baseline),
                selected_node_ids_sha256=canonical_ids_sha256(baseline),
            ),
        ),
        (
            "remove-config-derived-resource-with-map-preserved",
            lambda value: value["candidate_baseline"].update(force_include_assets=[]),
        ),
    ):
        candidate = copy.deepcopy(template)
        mutate(candidate)
        try:
            validate_recomputed_ids(
                candidate, actual, template["candidate_baseline"]["force_include_assets"]
            )
        except AuditFailure:
            cases[name] = True
        else:
            cases[name] = False
    if not all(cases.values()):
        raise AuditFailure(f"self-test failed to reject drift controls: {cases}")
    gate_source = (
        "from pathlib import Path\n"
        "HERE = Path(__file__).resolve().parent\n"
        'INSTALLED_ORIGIN_GATE_PATH = HERE / "installed_origin_gate_r4.py"\n'
        f'INSTALLED_ORIGIN_GATE_SHA256 = "{"a" * 64}"\n'
    ).encode("utf-8")
    expected_gate_binding = (f"{HANDOFF_REL}/raw/installed_origin_gate_r4.py", "a" * 64)
    if installed_origin_gate_binding(gate_source) != expected_gate_binding:
        raise AuditFailure("runner origin-gate binding did not resolve exact literal inputs")
    try:
        installed_origin_gate_binding(gate_source.replace(("a" * 64).encode(), b"bad"))
    except AuditFailure:
        cases["malformed-runner-gate-digest-rejected"] = True
    else:
        cases["malformed-runner-gate-digest-rejected"] = False
    if not cases["malformed-runner-gate-digest-rejected"]:
        raise AuditFailure("source audit accepted a non-full runner gate digest")
    cases["outside-identical-byte-symlink-and-parent-traversal-origin-controls"] = self_test_origin_gate_symlink()
    if not cases["outside-identical-byte-symlink-and-parent-traversal-origin-controls"]:
        raise AuditFailure("installed-origin verifier accepted an outside symlink/path-normalization falsifier")
    class_actual = {
        "tests/unit/test_supplemental.py::TestSupplemental::test_parameterized[a]",
        "tests/unit/test_supplemental.py::TestSupplemental::test_parameterized[b]",
        "tests/unit/test_supplemental.py::TestSupplemental::test_refusal",
    }
    class_resolved = selected_group_ids(
        {
            "test_path": "tests/unit/test_supplemental.py",
            "selectors": [
                "TestSupplemental::test_parameterized",
                "TestSupplemental::test_refusal",
            ],
        },
        class_actual,
    )
    cases["class-and-parameterized-node-id-resolution"] = class_resolved == class_actual
    if class_resolved != class_actual:
        raise AuditFailure("class-qualified parameterized node IDs did not resolve completely")

    supplemental_actual = {
        "tests/unit/test_supplemental.py::test_parameterized[a]",
        "tests/unit/test_supplemental.py::test_parameterized[b]",
    }
    supplemental_template = {
        "supplemental_suite": {
            "test_path": "tests/unit/test_supplemental.py",
            "selectors": ["test_parameterized"],
            "selected_node_ids": sorted(supplemental_actual),
            "expected_node_count": len(supplemental_actual),
            "selected_node_ids_sha256": canonical_ids_sha256(supplemental_actual),
        }
    }
    validate_supplemental_node_ids(supplemental_template, supplemental_actual)
    supplemental_removal = copy.deepcopy(supplemental_template)
    supplemental_removal["supplemental_suite"]["selected_node_ids"] = sorted(
        supplemental_actual - {"tests/unit/test_supplemental.py::test_parameterized[b]"}
    )
    supplemental_removal["supplemental_suite"]["expected_node_count"] = 1
    supplemental_removal["supplemental_suite"]["selected_node_ids_sha256"] = canonical_ids_sha256(
        supplemental_removal["supplemental_suite"]["selected_node_ids"]
    )
    try:
        validate_supplemental_node_ids(supplemental_removal, supplemental_actual)
    except AuditFailure:
        cases["supplemental-parameterized-id-removal-with-selector-preserved"] = True
    else:
        cases["supplemental-parameterized-id-removal-with-selector-preserved"] = False
    if not cases["supplemental-parameterized-id-removal-with-selector-preserved"]:
        raise AuditFailure("supplemental selector marker survived selected-node removal")
    profile_contract_control = profile_contract_is_supported(
        list(REVIEWED_PROFILE_NAMES), list(REVIEWED_PROFILE_NAMES), list(REVIEWED_PROFILE_NAMES)
    ) and not profile_contract_is_supported(
        list(REVIEWED_PROFILE_NAMES), ["source-wheel"], list(REVIEWED_PROFILE_NAMES)
    )
    if not profile_contract_control:
        raise AuditFailure("self-test failed to reject a divergent primary profile contract")
    return {
        "status": "pass",
        "product_source_read": False,
        "pytest_collection": False,
        "build_or_install": False,
        "actual_node_ids": len(actual),
        "corrupt_field_and_marker_preserving_removal_controls": cases,
        "profile_contract_divergence_control": profile_contract_control,
    }


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    repo = Path(args.repo).resolve(strict=True)
    product = repo / "policy-engine"
    python = Path(args.python).resolve(strict=True)
    if not args.python.startswith("/") or not python.is_file():
        raise AuditFailure(f"collector Python is unavailable: {python}")
    if args.collection_timeout_seconds <= 0:
        raise AuditFailure("collection timeout must be positive and explicit")
    output = Path(args.output_root).resolve()
    if output.exists():
        raise AuditFailure(f"output directory already exists; preserve old receipts: {output}")
    require_frozen_checkout(repo, args.source_sha, args.source_tree)
    output.mkdir(parents=True, exist_ok=False)

    helper_path = Path(__file__).resolve(strict=True)
    helper_sha = sha256(read_regular_local(helper_path))
    input_records, local_capsule_bytes = input_file_records(
        repo, args.source_sha, args.supplemental_manifest, args.supplemental_manifest_sha256
    )
    supplemental_manifest_relative = input_records["supplemental_manifest_path"]
    supplemental_manifest_relative = (
        Path(supplemental_manifest_relative).relative_to(repo).as_posix()
    )

    original_manifest_bytes = read_commit_blob(repo, args.source_sha, MANIFEST_REL)
    manifest = parse_json(original_manifest_bytes, MANIFEST_REL)
    if (repo / MANIFEST_REL).read_bytes() != original_manifest_bytes:
        raise AuditFailure("working manifest bytes differ from frozen Git object")
    original = baseline_ids_from_junit(
        read_commit_blob(
            repo,
            args.source_sha,
            f"policy-engine/{manifest['original_q2_suite']['baseline_junit_path']}",
        ),
        manifest,
    )
    if not exact_nonbool_count_matches(
        manifest["original_q2_suite"].get("baseline_case_count"), len(original)
    ):
        raise AuditFailure("baseline Q2 ID denominator does not equal its declared count")

    baseline_paths = manifest["original_q2_suite"]["test_paths"]
    if manifest["current_primary_suite"]["selection"]["baseline_paths"] != baseline_paths:
        raise AuditFailure("current primary baseline paths diverge from the original Q2 path set")
    baseline_ids, baseline_collection = collect_ids(
        repo=repo,
        python=python,
        product=product,
        selectors=baseline_paths,
        allowed_paths=set(baseline_paths),
        output_root=output,
        label="collect-primary-baseline",
        timeout_seconds=args.collection_timeout_seconds,
    )
    if not original <= baseline_ids:
        raise AuditFailure(
            f"source collection lost original Q2 cases: {sorted(original - baseline_ids)}"
        )

    groups = manifest["additional_installed_consumers"]
    group_paths: dict[str, list[str]] = {}
    for group in groups.values():
        path = group["test_path"]
        if path in baseline_paths:
            raise AuditFailure(
                f"current runner cannot select a consumer twice across baseline/group: {path}"
            )
        group_paths.setdefault(path, []).extend(group["selectors"])
    extra_ids: set[str] = set()
    additional_collections = {}
    for index, (path, selectors) in enumerate(sorted(group_paths.items())):
        specs = [f"{path}::{selector}" for selector in selectors]
        collected, record = collect_ids(
            repo=repo,
            python=python,
            product=product,
            selectors=specs,
            allowed_paths={path},
            output_root=output,
            label=f"collect-primary-consumers-{index:02d}",
            timeout_seconds=args.collection_timeout_seconds,
        )
        path_group = [group for group in groups.values() if group["test_path"] == path]
        resolved: set[str] = set()
        for group in path_group:
            resolved.update(selected_group_ids(group, collected))
        if resolved != collected:
            raise AuditFailure(
                f"actual collection contains undeclared IDs for {path}: {sorted(collected - resolved)}"
            )
        extra_ids.update(resolved)
        additional_collections[path] = record

    primary_ids = baseline_ids | extra_ids
    if not primary_ids:
        raise AuditFailure("source-derived Q2 primary selector set is empty")
    if not original <= primary_ids:
        raise AuditFailure("source-derived primary selectors omit original Q2 cases")

    historical = set(original)
    for group_name in ("dependency_profile", "canonical_bridge_and_worker"):
        if group_name not in groups:
            raise AuditFailure(f"historical Q2 subset owner group is missing: {group_name}")
        historical.update(selected_group_ids(groups[group_name], extra_ids))
    if historical != set(original) | {
        node_id
        for node_id in extra_ids
        if node_id.split("::", 1)[0]
        in {
            groups["dependency_profile"]["test_path"],
            groups["canonical_bridge_and_worker"]["test_path"],
        }
    }:
        raise AuditFailure("historical Q2 subset resolution is inconsistent")
    historical_decl = manifest["current_primary_suite"]["historical_baseline_subset"]
    if not exact_nonbool_count_matches(
        historical_decl.get("selected_node_count"), len(historical)
    ) or historical_decl.get("selected_node_ids_sha256") != canonical_ids_sha256(historical):
        raise AuditFailure(
            "historical 91-plus-nine subset does not recompute from its original baseline and named groups"
        )
    if not historical <= primary_ids:
        raise AuditFailure(
            "source-derived primary suite does not retain the historical baseline subset"
        )

    supplemental_bytes = local_capsule_bytes[supplemental_manifest_relative]
    supplemental = parse_json(supplemental_bytes, supplemental_manifest_relative)
    supplemental_path = supplemental["supplemental_suite"]["test_path"]
    supplemental_selectors = supplemental["supplemental_suite"]["selectors"]
    if (
        supplemental["primary_inputs"]["required_profiles"]
        != manifest["required_outcome"]["profiles"]
    ):
        raise AuditFailure("primary and supplemental profile contracts differ")
    if supplemental_path in group_paths or supplemental_path in baseline_paths:
        raise AuditFailure("supplemental selection duplicates a primary module")
    supplement_specs = [f"{supplemental_path}::{selector}" for selector in supplemental_selectors]
    supplemental_collected, supplemental_collection = collect_ids(
        repo=repo,
        python=python,
        product=product,
        selectors=supplement_specs,
        allowed_paths={supplemental_path},
        output_root=output,
        label="collect-supplemental-consumers",
        timeout_seconds=args.collection_timeout_seconds,
    )
    supplemental_group = {"test_path": supplemental_path, "selectors": supplemental_selectors}
    supplemental_ids = selected_group_ids(supplemental_group, supplemental_collected)
    if supplemental_ids != supplemental_collected:
        raise AuditFailure("supplemental collection includes an undeclared selector")
    direct_supplemental_ids = {
        f"{supplemental_path}::{selector}" for selector in supplemental_selectors
    }

    source_paths = sorted(set(baseline_paths) | set(group_paths))
    if set(manifest["current_primary_suite"]["source_file_sha256"]) != set(source_paths):
        raise AuditFailure(
            "manifest source digest paths do not equal the complete selected test module set"
        )
    source_hashes = {
        path: sha256(read_commit_blob(repo, args.source_sha, f"policy-engine/{path}"))
        for path in source_paths
    }
    supplement_test_sha = sha256(
        read_commit_blob(repo, args.source_sha, f"policy-engine/{supplemental_path}")
    )
    fixture_paths = groups["canonical_bridge_and_worker"].get("fixture_paths", {})
    fixture_hashes = {
        relative: sha256(read_commit_blob(repo, args.source_sha, f"policy-engine/{relative}"))
        for relative in sorted(set(fixture_paths.values()))
    }

    assets, asset_receipt = asset_rows_from_config(repo, args.source_sha, manifest)
    lock_and_build_paths = (
        HATCH_REL,
        APP_PROJECT_REL,
        APP_LOCK_REL,
        DOWHY_PROJECT_REL,
        DOWHY_LOCK_REL,
        DOWHY_PYTHON_REL,
        DOWHY_README_REL,
        GCP_PACKAGE_REL,
    )
    locked_inputs = {
        path: {"bytes": len(data), "sha256": sha256(data)}
        for path in lock_and_build_paths
        for data in [read_commit_blob(repo, args.source_sha, path)]
    }

    proposed = copy.deepcopy(manifest)
    # candidate_baseline.source_sha/tree identify the historical asset candidate.
    # Keep them unchanged: putting this commit's SHA in its own tracked manifest
    # would make the commit identity self-referential. The actual freeze belongs
    # in this external audit receipt and in the caller's command parameters.
    proposed["candidate_baseline"]["force_include_count"] = len(assets)
    proposed["candidate_baseline"]["force_include_assets"] = assets
    suite = proposed["current_primary_suite"]
    suite["selected_node_ids"] = sorted(primary_ids)
    suite["selected_node_count"] = len(primary_ids)
    suite["selected_node_ids_sha256"] = canonical_ids_sha256(primary_ids)
    suite["source_file_sha256"] = source_hashes
    proposed_manifest_bytes = (json.dumps(proposed, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    proposed_manifest_sha = sha256(proposed_manifest_bytes)

    proposed_supplement = copy.deepcopy(supplemental)
    proposed_supplement["primary_inputs"]["manifest_sha256"] = proposed_manifest_sha
    proposed_supplement["primary_inputs"]["runner_sha256"] = sha256(
        read_commit_blob(repo, args.source_sha, RUNNER_REL)
    )
    proposed_supplement["primary_inputs"]["force_include_asset_count_per_profile"] = len(assets)
    proposed_supplement["supplemental_suite"]["test_sha256"] = supplement_test_sha
    proposed_supplement["supplemental_suite"]["expected_node_count"] = len(supplemental_ids)
    proposed_supplement["supplemental_suite"]["selected_node_ids"] = sorted(supplemental_ids)
    proposed_supplement["supplemental_suite"]["selected_node_ids_sha256"] = canonical_ids_sha256(
        supplemental_ids
    )
    validate_supplemental_node_ids(proposed_supplement, supplemental_ids)
    proposed_supplement_bytes = (
        json.dumps(proposed_supplement, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    ).encode("utf-8")
    proposed_supplement_sha = sha256(proposed_supplement_bytes)

    runner_bytes = read_commit_blob(repo, args.source_sha, RUNNER_REL)
    supplemental_runner_bytes = local_capsule_bytes[SUPPLEMENT_REL]
    primary_profile_names, supplemental_profile_names = profile_names_from_runner_sources(
        runner_bytes, supplemental_runner_bytes
    )
    timeout_bytes = read_commit_blob(repo, args.source_sha, TIMEOUT_REL)
    timeout_text = timeout_bytes.decode("utf-8")
    rebound_timeout, rebound_timeout_bytes = rebind_timeout_driver(
        timeout_text, sha256(runner_bytes)
    )
    timeout_patch = "".join(
        difflib.unified_diff(
            timeout_text.splitlines(keepends=True),
            rebound_timeout.splitlines(keepends=True),
            fromfile=TIMEOUT_REL,
            tofile=f"{TIMEOUT_REL} (rebound proposal)",
        )
    ).encode("utf-8")

    profiles = proposed["required_outcome"]["profiles"]
    runner_limitations = []
    direct_primary_ids = {
        f"{group['test_path']}::{selector}"
        for group in groups.values()
        for selector in group["selectors"]
    }
    primary_group_ids = {
        node_id for group in groups.values() for node_id in selected_group_ids(group, primary_ids)
    }
    primary_group_expansions = sorted(primary_group_ids - direct_primary_ids)
    if (
        tuple(profiles) != REVIEWED_PROFILE_NAMES
        or tuple(primary_profile_names) != REVIEWED_PROFILE_NAMES
        or tuple(supplemental_profile_names) != REVIEWED_PROFILE_NAMES
    ):
        runner_limitations.append(
            "primary runner, supplemental runner, and manifest do not share the reviewed three-profile contract"
        )
    profile_case_count = len(profiles) * (len(primary_ids) + len(supplemental_ids))

    # Run the existing AST/fixture binding verifier on the source-derived proposal.
    import importlib.util

    runner_path = repo / RUNNER_REL
    actual_runner_sha = sha256(read_commit_blob(repo, args.source_sha, RUNNER_REL))
    if sha256(read_regular_local(runner_path)) != actual_runner_sha:
        raise AuditFailure("working runner differs from its frozen Git object")
    spec = importlib.util.spec_from_file_location("q2_source_audit_existing_runner", runner_path)
    if spec is None or spec.loader is None:
        raise AuditFailure("cannot import existing Q2 source verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original_ids = module.baseline_node_ids(product, proposed)
    transitive = None
    transitive = module.verify_transitive_test_bindings(product, proposed, original_ids)

    current_manifest_pin = sha256(original_manifest_bytes)
    current_supplement_pin = sha256(supplemental_bytes)
    current_supp_manifest = parse_json(supplemental_bytes, supplemental_manifest_relative)
    expected_timeout_values = {"runner_sha256": actual_runner_sha}
    timeout_mismatches = []
    for key, expected in expected_timeout_values.items():
        constant = "EXPECTED_RUNNER_SHA256"
        if f'{constant} = "{expected}"' not in timeout_text:
            timeout_mismatches.append(constant)
    supplement_mismatches = []
    for key, expected in (
        ("runner_sha256", actual_runner_sha),
        ("manifest_sha256", proposed_manifest_sha),
        ("required_profiles", profiles),
    ):
        if not json_values_match_exactly(
            current_supp_manifest["primary_inputs"].get(key), expected
        ):
            supplement_mismatches.append(key)
    supplement_mismatches.extend(
        supplemental_manifest_count_mismatches(
            current_supp_manifest,
            asset_count=len(assets),
            supplemental_id_count=len(supplemental_ids),
        )
    )
    if current_supp_manifest["supplemental_suite"].get("test_sha256") != supplement_test_sha:
        supplement_mismatches.append("supplemental_suite.test_sha256")
    if current_supp_manifest["supplemental_suite"].get("selected_node_ids") != sorted(
        supplemental_ids
    ):
        supplement_mismatches.append("supplemental_suite.selected_node_ids")
    if current_supp_manifest["supplemental_suite"].get(
        "selected_node_ids_sha256"
    ) != canonical_ids_sha256(supplemental_ids):
        supplement_mismatches.append("supplemental_suite.selected_node_ids_sha256")

    receipt = {
        "schema_version": 1,
        "status": "source_collection_and_content_audit_only",
        "source_sha": args.source_sha,
        "source_tree": args.source_tree,
        "audit_helper_sha256": helper_sha,
        "repo": str(repo),
        "frozen_checkout_clean_tracked": True,
        "build_started": False,
        "install_started": False,
        "tests_executed": False,
        "pytest_collection_only": True,
        "primary": {
            "baseline_ids": len(baseline_ids),
            "original_q2_ids": len(original),
            "additional_ids": len(extra_ids),
            "source_derived_ids": len(primary_ids),
            "source_derived_ids_sha256": canonical_ids_sha256(primary_ids),
            "manifest_ids_equal_source_collection": primary_manifest_matches_collection(
                manifest, primary_ids, assets, source_hashes
            ),
            "current_manifest_sha256": current_manifest_pin,
            "proposed_manifest_sha256": proposed_manifest_sha,
            "source_file_sha256": source_hashes,
            "baseline_collection": baseline_collection,
            "additional_collections": additional_collections,
        },
        "supplemental": {
            "source_derived_ids": len(supplemental_ids),
            "source_derived_ids_sha256": canonical_ids_sha256(supplemental_ids),
            "current_manifest_sha256": current_supplement_pin,
            "proposed_manifest_sha256": proposed_supplement_sha,
            "test_sha256": supplement_test_sha,
            "collection": supplemental_collection,
        },
        "profiles": profiles,
        "primary_runner_profile_names": primary_profile_names,
        "supplemental_runner_profile_names": supplemental_profile_names,
        "source_derived_profile_case_count": profile_case_count,
        "reviewed_route_count_comparison": {
            "primary_source_collection": len(primary_ids),
            "primary_manifest_ids": len(proposed["current_primary_suite"]["selected_node_ids"]),
            "primary_collection_matches_manifest": set(
                proposed["current_primary_suite"]["selected_node_ids"]
            )
            == primary_ids,
            "supplemental_source_collection": len(supplemental_ids),
            "supplemental_manifest_ids": len(
                proposed_supplement["supplemental_suite"]["selected_node_ids"]
            ),
            "supplemental_collection_matches_manifest": set(
                proposed_supplement["supplemental_suite"]["selected_node_ids"]
            )
            == supplemental_ids,
            "required_profiles": list(profiles),
            "profile_cases_from_source_counts": profile_case_count,
            "is_acceptance": False,
        },
        "runner_limitations": sorted(set(runner_limitations)),
        "primary_selector_expansions": primary_group_expansions,
        "supplemental_selector_expansion_detected": supplemental_ids != direct_supplemental_ids,
        "count_is_not_runtime_acceptance": True,
        "primary_selection_finality": "FINAL_SOURCE_REQUIRED",
        "resource_config": asset_receipt,
        "transitive_fixture_sha256": fixture_hashes,
        "lock_build_and_archive_inputs": locked_inputs,
        "source_freeze_input_capsule": input_records,
        "timeout_driver_stale_constants": timeout_mismatches,
        "supplement_manifest_stale_fields": supplement_mismatches,
        "existing_runner_static_transitive_binding": transitive,
        "required_runtime_followup": [
            "Only the actual frozen installed wheel, rebuilt sdist wheel, and rebuilt archive wheel waves can establish consumer behavior and installed origins.",
            "Every profile must reconcile complete collected IDs to JUnit and zero skips/failures/errors, then verify all source/archive/wheel/installed resource bytes.",
            "The source collection here is not installed-package evidence or G adjudication.",
        ],
    }
    current_mismatches = manifest_mismatches(
        manifest, proposed, original_manifest_bytes, proposed_manifest_bytes
    )
    receipt["manifest_rebind_fields_needed"] = current_mismatches
    receipt["source_object_and_actual_collection_reconcile"] = (
        primary_manifest_matches_collection(manifest, primary_ids, assets, source_hashes)
        and not current_mismatches
    )
    receipt["capsule_bindings_current"] = not timeout_mismatches and not supplement_mismatches

    if sha256(read_regular_local(helper_path)) != helper_sha:
        raise AuditFailure("Q2 source audit helper changed while it was running")
    final_input_records, _ = input_file_records(
        repo, args.source_sha, args.supplemental_manifest, args.supplemental_manifest_sha256
    )
    if final_input_records != input_records:
        raise AuditFailure("one or more source-freeze audit inputs changed during collection")

    (output / "proposed-installed-wave-manifest.json").write_bytes(proposed_manifest_bytes)
    (output / "proposed-supplemental-manifest.json").write_bytes(proposed_supplement_bytes)
    (output / "proposed-timeout-driver.patch").write_bytes(timeout_patch)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("self-test", help="run lightweight in-memory drift controls")
    for command in ("prepare", "check"):
        sub = subparsers.add_parser(
            command, help="collect source IDs and rebind source-object inputs"
        )
        sub.add_argument("--repo", required=True, help="attached source checkout root")
        sub.add_argument("--source-sha", required=True, help="full final commit SHA")
        sub.add_argument("--source-tree", required=True, help="full final tree SHA")
        sub.add_argument(
            "--python",
            required=True,
            help="absolute existing Python with pytest and locked test dependencies",
        )
        sub.add_argument(
            "--collection-timeout-seconds",
            type=float,
            required=True,
            help="measured/approved collect-only timeout",
        )
        sub.add_argument(
            "--output-root", required=True, help="new absent ignored raw output directory"
        )
        sub.add_argument(
            "--supplemental-manifest",
            required=True,
            help="absolute ignored versioned supplement manifest path",
        )
        sub.add_argument(
            "--supplemental-manifest-sha256",
            required=True,
            help="exact supplement manifest SHA-256",
        )
    args = parser.parse_args()
    if args.command == "self-test":
        print(json.dumps(self_test(), indent=2, sort_keys=True))
        return 0
    output = Path(args.output_root).resolve()
    output_was_present = output.exists()
    try:
        receipt = run_audit(args)
        (output / "source-input-audit.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        exact = (
            receipt["source_object_and_actual_collection_reconcile"]
            and receipt["capsule_bindings_current"]
            and not receipt["runner_limitations"]
        )
        receipt_status = "source_preflight_exact" if exact else "source_preflight_rebind_required"
        receipt["status"] = receipt_status
        (output / "source-input-audit.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "status": receipt_status,
                    "source_sha": args.source_sha,
                    "source_tree": args.source_tree,
                    "primary_ids": receipt["primary"]["source_derived_ids"],
                    "supplemental_ids": receipt["supplemental"]["source_derived_ids"],
                    "profile_cases": receipt["source_derived_profile_case_count"],
                    "outputs": str(output),
                },
                sort_keys=True,
            )
        )
        return 0 if args.command == "prepare" or exact else 1
    except (
        AuditFailure,
        OSError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        subprocess.SubprocessError,
    ) as error:
        if output_was_present:
            print(
                f"Q2 source input audit refused existing output directory without changing it: {output}",
                file=sys.stderr,
            )
            return 2
        output.mkdir(parents=True, exist_ok=True)
        failure = {
            "status": "source_preflight_error",
            "source_sha": getattr(args, "source_sha", None),
            "source_tree": getattr(args, "source_tree", None),
            "build_started": False,
            "install_started": False,
            "tests_executed": False,
            "error": f"{type(error).__name__}: {error}",
        }
        (output / "source-input-audit.json").write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Q2 source input audit failed before any build: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

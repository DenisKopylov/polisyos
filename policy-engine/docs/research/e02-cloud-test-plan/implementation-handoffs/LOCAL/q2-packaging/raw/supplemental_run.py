#!/usr/bin/env python3
"""Run the separate source-selected installed-consumer supplement after primary Q2 passes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import shutil
import stat
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from defusedxml import ElementTree

if TYPE_CHECKING:
    from subprocess import CompletedProcess
    from types import ModuleType


HERE = Path(__file__).resolve().parent
HANDOFF_ROOT = HERE.parent
PRIMARY_RUNNER_PATH = HERE / "run.py"
PRODUCT_NAME = "policy-engine"
PROFILE_NAMES = (
    "source-wheel",
    "rebuilt-sdist-wheel",
    "rebuilt-gcp-archive-wheel",
)


class SupplementalError(RuntimeError):
    """Raised when a primary input, installed run, or retained receipt is invalid."""


def exact_nonbool_count_matches(value: object, expected: object) -> bool:
    """Match JSON integer values only when both operands are exact non-boolean integers."""
    return type(value) is int and type(expected) is int and value == expected


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_regular_without_symlink_components(
    path_value: str | Path, label: str
) -> tuple[Path, bytes]:
    """Read a regular file through a no-follow descriptor walk of every path component."""
    supplied = Path(path_value)
    if not supplied.is_absolute():
        raise SupplementalError(f"{label} path must be absolute: {supplied}")
    path = Path(os.path.abspath(supplied))
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise SupplementalError(f"{label} cannot be opened safely on this platform")
    if os.open not in os.supports_dir_fd or os.stat not in os.supports_dir_fd:
        raise SupplementalError(f"{label} cannot be opened safely with directory descriptors")
    parts = path.parts[1:]
    if path.anchor != os.sep or not parts:
        raise SupplementalError(f"{label} must name a file below the filesystem root: {path}")

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
                raise SupplementalError(
                    f"{label} contains a replaced or symlinked directory: {component}"
                )
            directory_identities.append((opened.st_dev, opened.st_ino))
            current_fd = next_fd

        final_name = parts[-1]
        before = os.stat(final_name, dir_fd=current_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise SupplementalError(f"{label} must be a regular non-symlink file: {path}")
        file_descriptor = os.open(final_name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=current_fd)
        with os.fdopen(file_descriptor, "rb") as stream:
            file_descriptor = -1
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
                before.st_dev,
                before.st_ino,
            ):
                raise SupplementalError(f"{label} changed before open: {path}")
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
            raise SupplementalError(f"{label} changed while being read: {path}")

        cursor = Path(path.anchor)
        component_index = 0
        for component in parts:
            cursor = cursor / component
            observed = cursor.lstat()
            if stat.S_ISLNK(observed.st_mode):
                raise SupplementalError(f"{label} contains a symlinked path component: {cursor}")
            if component_index < len(directory_identities):
                expected_identity = directory_identities[component_index]
                if (
                    not stat.S_ISDIR(observed.st_mode)
                    or (observed.st_dev, observed.st_ino) != expected_identity
                ):
                    raise SupplementalError(f"{label} path changed while being read: {cursor}")
            elif file_signature(observed) != file_signature(before):
                raise SupplementalError(f"{label} path changed while being read: {cursor}")
            component_index += 1
        if path.resolve(strict=True) != path:
            raise SupplementalError(f"{label} path does not resolve to its supplied path: {path}")
        return path, data
    except SupplementalError:
        raise
    except (OSError, NotImplementedError, TypeError) as error:
        raise SupplementalError(
            f"{label} could not be read without following symlinks: {path}: {error}"
        ) from error
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        for descriptor in reversed(directory_fds):
            os.close(descriptor)


def read_verified_json_input(
    path_value: str | Path, expected_sha256: str, label: str
) -> tuple[Path, dict[str, Any], str]:
    """Read one absolute, non-symlink JSON input bound by its exact SHA-256."""
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise SupplementalError(f"{label} SHA-256 must be 64 lowercase hexadecimal characters")
    path, data = _read_regular_without_symlink_components(path_value, label)
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if actual_sha256 != expected_sha256:
        raise SupplementalError(
            f"{label} content SHA-256 differs: expected={expected_sha256} actual={actual_sha256}"
        )
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SupplementalError(f"{label} is not valid UTF-8 JSON: {path}") from error
    if not isinstance(value, dict):
        raise SupplementalError(f"{label} JSON root must be an object: {path}")
    return path, value, actual_sha256


def json_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_primary_runner(expected_sha256: str) -> ModuleType:
    if PRIMARY_RUNNER_PATH.is_symlink() or not PRIMARY_RUNNER_PATH.is_file():
        raise SupplementalError(
            f"primary runner must be a regular non-symlink input: {PRIMARY_RUNNER_PATH}"
        )
    before_sha256 = sha256_file(PRIMARY_RUNNER_PATH)
    if before_sha256 != expected_sha256:
        raise SupplementalError(
            f"primary runner hash differs from the selected supplement: expected={expected_sha256} actual={before_sha256}"
        )
    spec = importlib.util.spec_from_file_location("q2_primary_runner", PRIMARY_RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise SupplementalError(f"cannot load primary runner: {PRIMARY_RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if sha256_file(PRIMARY_RUNNER_PATH) != before_sha256:
        raise SupplementalError("primary runner changed while being imported")
    return module


def require_file(value: str | Path, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise SupplementalError(f"{label} must be absolute: {path}")
    path = Path(os.path.abspath(path))
    if not path.is_file():
        raise SupplementalError(f"{label} is missing: {path}")
    return path


def verify_primary_profile(
    *,
    runner: ModuleType,
    run_root: Path,
    profile_name: str,
    profile: dict[str, Any],
    primary_manifest: dict[str, Any],
    expected_ids: set[str],
    assets: list[dict[str, Any]],
    purelib: Path,
    source_product: Path,
    live_product: Path,
    dependency_site: Path,
) -> dict[str, Any]:
    wheel_receipt = profile["wheel"]
    wheel_path = require_file(wheel_receipt["path"], f"{profile_name} wheel")
    if not wheel_path.resolve().is_relative_to(run_root.resolve()):
        raise SupplementalError(f"{profile_name} wheel escaped the primary run directory")
    wheel_proof = runner.verify_wheel(wheel_path, assets)
    if wheel_receipt.get("sha256") != wheel_proof["sha256"]:
        raise SupplementalError(f"{profile_name} wheel hash differs from its primary receipt")
    if not runner.json_values_match_exactly(wheel_proof["assets"], wheel_receipt.get("assets")):
        raise SupplementalError(f"{profile_name} wheel asset receipt differs on readback")

    consumer = profile["consumers"]
    collected_path = require_file(consumer["collected_nodeids_path"], f"{profile_name} node IDs")
    collected = json.loads(collected_path.read_text(encoding="utf-8"))
    if set(collected) != expected_ids or len(collected) != len(expected_ids):
        raise SupplementalError(
            f"{profile_name} primary collection differs from the content-bound current suite: "
            f"actual={len(collected)} expected={len(expected_ids)}"
        )
    junit_path = require_file(consumer["junit_path"], f"{profile_name} JUnit")
    executed, counts = runner.junit_node_ids(
        junit_path,
        primary_manifest["original_q2_suite"]["test_paths"][-1],
    )
    if executed != expected_ids:
        raise SupplementalError(
            f"{profile_name} primary JUnit differs from the content-bound current suite: "
            f"actual={len(executed)} expected={len(expected_ids)}"
        )
    if not runner.json_values_match_exactly(
        counts, {"tests": len(expected_ids), "skipped": 0, "failures": 0, "errors": 0}
    ):
        raise SupplementalError(f"{profile_name} primary JUnit is not fully green: {counts}")
    if (
        consumer.get("returncode") != 0
        or not runner.exact_nonbool_count_matches(
            consumer.get("selected_node_ids"), len(expected_ids)
        )
        or consumer.get("selected_node_ids_sha256") != runner.node_ids_sha256(expected_ids)
        or not consumer.get("all_original_q2_ids_present")
    ):
        raise SupplementalError(
            f"{profile_name} primary summary does not prove its complete current suite"
        )
    process_output = consumer["process_output"]
    for stream in ("stdout", "stderr"):
        stream_path = require_file(process_output[f"{stream}_path"], f"{profile_name} {stream}")
        actual_stream = {"bytes": stream_path.stat().st_size, "sha256": sha256_file(stream_path)}
        expected_stream = {
            "bytes": process_output[f"{stream}_bytes"],
            "sha256": process_output[f"{stream}_sha256"],
        }
        if not runner.json_values_match_exactly(actual_stream, expected_stream):
            raise SupplementalError(f"{profile_name} primary {stream} differs from its receipt")
    primary_command_path = junit_path.parent / "consumer-suite.command.json"
    primary_command = json.loads(
        require_file(primary_command_path, f"{profile_name} command record").read_text(
            encoding="utf-8"
        )
    )
    if primary_command.get("returncode") != 0 or primary_command.get("timed_out"):
        raise SupplementalError(f"{profile_name} primary command record is not a clean completion")

    origin_path = require_file(consumer["origin_proof_path"], f"{profile_name} origin proof")
    origin = json.loads(origin_path.read_text(encoding="utf-8"))
    if not origin.get("verified") or origin.get("errors"):
        raise SupplementalError(f"{profile_name} primary installed origin proof failed")
    if Path(origin.get("purelib", "")).resolve() != purelib.resolve():
        raise SupplementalError(f"{profile_name} origin proof names another purelib")
    for module_name, module_origin in origin.get("origins", {}).items():
        origins = module_origin if isinstance(module_origin, list) else [module_origin]
        if not origins or any(
            not Path(path).resolve().is_relative_to(purelib.resolve()) for path in origins
        ):
            raise SupplementalError(
                f"{profile_name} primary module origin escaped installed purelib: {module_name}"
            )
    sys_path = [Path(path).resolve() for path in origin.get("sys_path", []) if path]
    if any(
        path == root or path.is_relative_to(root)
        for path in sys_path
        for root in (source_product.resolve(), live_product.resolve())
    ):
        raise SupplementalError(f"{profile_name} primary origin proof includes a source path")
    if purelib.resolve() not in sys_path or dependency_site.resolve() not in sys_path:
        raise SupplementalError(f"{profile_name} primary origin proof omits a required site path")
    if sys_path.index(purelib.resolve()) >= sys_path.index(dependency_site.resolve()):
        raise SupplementalError(f"{profile_name} installed site does not precede dependencies")

    runtime = profile["installed_runtime"]
    runtime_assets = runtime.get("assets", {})
    expected_targets = {row["wheel"]: row for row in assets}
    if set(runtime_assets) != set(expected_targets) or len(runtime_assets) != len(expected_targets):
        raise SupplementalError(
            f"{profile_name} installed proof does not cover every manifest asset"
        )
    for target, expected in expected_targets.items():
        row = runtime_assets[target]
        installed_path = Path(row["installed_path"]).resolve(strict=True)
        if not installed_path.is_relative_to(purelib.resolve()):
            raise SupplementalError(f"{profile_name} installed asset escaped purelib: {target}")
        actual = {"bytes": installed_path.stat().st_size, "sha256": sha256_file(installed_path)}
        required = {key: expected[key] for key in ("bytes", "sha256")}
        observed_receipt = {key: row.get(key) for key in required}
        if not runner.json_values_match_exactly(
            actual, required
        ) or not runner.json_values_match_exactly(observed_receipt, required):
            raise SupplementalError(f"{profile_name} installed asset differs: {target}")

    return {
        "wheel": {"path": str(wheel_path), "sha256": wheel_proof["sha256"]},
        "primary_selected_node_ids": len(executed),
        "primary_junit_counts": counts,
        "primary_origin_verified": True,
        "primary_installed_asset_count": len(runtime_assets),
    }


def suite_node_ids(product: Path, manifest: dict[str, Any]) -> set[str]:
    suite = manifest.get("supplemental_suite")
    if not isinstance(suite, dict):
        raise SupplementalError("supplemental manifest omits its suite")
    test_path = suite.get("test_path")
    test_sha = suite.get("test_sha256")
    selectors = suite.get("selectors")
    if not isinstance(test_path, str) or not test_path or not isinstance(test_sha, str):
        raise SupplementalError("supplemental manifest test path/hash is incomplete")
    if (
        not isinstance(selectors, list)
        or not selectors
        or any(not isinstance(item, str) or not item for item in selectors)
    ):
        raise SupplementalError("supplemental selectors must be a nonempty string list")
    if len(set(selectors)) != len(selectors):
        raise SupplementalError("supplemental selectors must be unique")
    from pathlib import PurePosixPath

    relative_test_path = PurePosixPath(test_path)
    if (
        relative_test_path.is_absolute()
        or not relative_test_path.parts
        or ".." in relative_test_path.parts
        or relative_test_path.as_posix() != test_path
        or chr(92) in test_path
    ):
        raise SupplementalError("supplemental test path must be safe and source-relative")
    test_file = product.joinpath(*relative_test_path.parts)
    if not test_file.is_file() or test_file.is_symlink() or sha256_file(test_file) != test_sha:
        raise SupplementalError("frozen supplemental test module differs from its manifest")
    raw_ids = suite.get("selected_node_ids")
    expected_count = suite.get("expected_node_count")
    declared_digest = suite.get("selected_node_ids_sha256")
    if (
        not isinstance(raw_ids, list)
        or not raw_ids
        or any(not isinstance(item, str) for item in raw_ids)
    ):
        raise SupplementalError("supplemental selected node IDs must be a nonempty string list")
    if raw_ids != sorted(set(raw_ids)) or not exact_nonbool_count_matches(
        expected_count, len(raw_ids)
    ):
        raise SupplementalError(
            "supplemental selected node IDs are not complete, sorted, and unique"
        )
    ids = set(raw_ids)
    actual_digest = hashlib.sha256(("\n".join(sorted(ids)) + "\n").encode("utf-8")).hexdigest()
    if declared_digest != actual_digest:
        raise SupplementalError(
            "supplemental selected-node digest differs from its complete ID list"
        )
    group = {"test_path": test_path, "selectors": selectors}
    resolved: set[str] = set()
    for selector in selectors:
        stem = f"{test_path}::{selector}"
        matches = (
            {node_id for node_id in ids if node_id == stem}
            if "[" in selector
            else {node_id for node_id in ids if node_id == stem or node_id.startswith(stem + "[")}
        )
        if not matches:
            raise SupplementalError(f"supplemental selector has no content-bound IDs: {stem}")
        resolved.update(matches)
    if resolved != ids:
        raise SupplementalError(
            f"supplemental IDs differ from all declared selector families: {sorted(ids - resolved)}"
        )
    return ids


def verify_supplemental_run(
    *,
    result: CompletedProcess[str],
    output: Path,
    expected_ids: set[str],
    purelib: Path,
    source_product: Path,
    live_product: Path,
    dependency_site: Path,
    expected_denominator_properties: dict[str, Any],
) -> dict[str, Any]:
    nodeids_path = output / "collected-nodeids.json"
    junit_path = output / "supplemental-junit.xml"
    origin_path = output / "origin-proof.json"
    stdout_path = output / "consumer-suite.stdout.txt"
    stderr_path = output / "consumer-suite.stderr.txt"
    required_files = (nodeids_path, junit_path, origin_path, stdout_path, stderr_path)
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise SupplementalError(f"supplemental consumer evidence is missing: {missing}")

    collected = json.loads(nodeids_path.read_text(encoding="utf-8"))
    if set(collected) != expected_ids or len(collected) != len(expected_ids):
        raise SupplementalError(
            f"supplemental collected IDs differ: expected={sorted(expected_ids)} actual={collected}"
        )
    junit = ElementTree.parse(junit_path).getroot()
    cases = list(junit.iter("testcase"))
    actual_ids = {
        f"{'/'.join(case.attrib['classname'].split('.'))}.py::{case.attrib['name']}"
        for case in cases
    }
    if actual_ids != expected_ids:
        raise SupplementalError(
            "supplemental executed JUnit IDs differ from the content-bound selector set"
        )
    counts = {
        "tests": len(cases),
        "skipped": sum(case.find("skipped") is not None for case in cases),
        "failures": sum(case.find("failure") is not None for case in cases),
        "errors": sum(case.find("error") is not None for case in cases),
    }
    if not exact_nonbool_count_matches(counts.get("tests"), len(expected_ids)) or any(
        not exact_nonbool_count_matches(counts.get(key), 0)
        for key in ("skipped", "failures", "errors")
    ):
        raise SupplementalError(f"supplemental JUnit is not fully green: {counts}")
    properties = {
        prop.attrib["name"]: prop.attrib["value"]
        for node in junit.iter("properties")
        for prop in node.findall("property")
    }
    if not isinstance(expected_denominator_properties, dict) or not expected_denominator_properties:
        raise SupplementalError("supplemental manifest omits source/AST denominator properties")
    required_keys = {
        "source_contract_package_definitions",
        "source_contract_supported_entrypoints",
        "ast_inventory_unresolved_package_rows",
    }
    if not required_keys <= set(expected_denominator_properties):
        raise SupplementalError("supplemental manifest omits a required source/AST denominator")
    if any(
        not isinstance(key, str)
        or not key
        or not exact_nonbool_count_matches(value, value)
        or value < 0
        for key, value in expected_denominator_properties.items()
    ):
        raise SupplementalError("supplemental manifest source/AST denominator values are malformed")
    required_properties = {
        key: str(value) for key, value in expected_denominator_properties.items()
    }
    if any(properties.get(key) != value for key, value in required_properties.items()):
        raise SupplementalError(
            "supplemental JUnit is missing the required source/AST denominators"
        )

    origin = json.loads(origin_path.read_text(encoding="utf-8"))
    if not origin.get("verified") or origin.get("errors"):
        raise SupplementalError(
            f"supplemental installed origin proof failed: {origin.get('errors')}"
        )
    if Path(origin.get("purelib", "")).resolve() != purelib.resolve():
        raise SupplementalError("supplemental origin proof names a different installed site")
    origins = origin.get("origins", {})
    if "polisyos" not in origins:
        raise SupplementalError("supplemental origin proof did not import the product root")
    for module_name, module_origin in origins.items():
        module_paths = module_origin if isinstance(module_origin, list) else [module_origin]
        if not module_paths or any(
            not Path(path).resolve().is_relative_to(purelib.resolve()) for path in module_paths
        ):
            raise SupplementalError(
                f"supplemental module did not load from installed purelib: {module_name}"
            )
    sys_path = [Path(path).resolve() for path in origin.get("sys_path", []) if path]
    for forbidden_root in (source_product.resolve(), live_product.resolve()):
        if any(path == forbidden_root or path.is_relative_to(forbidden_root) for path in sys_path):
            raise SupplementalError("supplemental origin proof includes a source or test path")
    if purelib.resolve() not in sys_path or dependency_site.resolve() not in sys_path:
        raise SupplementalError("supplemental origin proof omits an installed/dependency site")
    if sys_path.index(purelib.resolve()) >= sys_path.index(dependency_site.resolve()):
        raise SupplementalError("supplemental installed site does not precede dependencies")
    if not result.returncode:
        returncode = 0
    else:
        raise SupplementalError(f"pytest exited {result.returncode}")

    process_output = {}
    for label, path in (("stdout", stdout_path), ("stderr", stderr_path)):
        process_output[label] = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return {
        "returncode": returncode,
        "counts": counts,
        "selected_node_ids": len(collected),
        "collected_nodeids_path": str(nodeids_path),
        "junit_path": str(junit_path),
        "origin_proof_path": str(origin_path),
        "origin_verified": True,
        "source_contract_package_definitions": int(
            properties["source_contract_package_definitions"]
        ),
        "source_contract_supported_entrypoints": int(
            properties["source_contract_supported_entrypoints"]
        ),
        "ast_inventory_unresolved_package_rows": int(
            properties["ast_inventory_unresolved_package_rows"]
        ),
        "runtime_declared_exports_resolved": int(properties["runtime_declared_exports_resolved"]),
        "process_output": process_output,
    }


def require_exact_resource_count(value: object, actual_count: int) -> None:
    """Require the manifest count to be an exact positive integer matching content."""
    if actual_count < 1 or not exact_nonbool_count_matches(value, actual_count):
        raise SupplementalError(
            "primary manifest resource count must be an exact positive integer matching the full resource list"
        )


def run_supplement(args: argparse.Namespace) -> Path:
    supplemental_manifest_path, manifest, supplemental_manifest_sha256 = read_verified_json_input(
        args.supplemental_manifest,
        args.supplemental_manifest_sha256,
        "supplemental source-freeze manifest",
    )
    if not exact_nonbool_count_matches(manifest.get("schema_version"), 1):
        raise SupplementalError("unsupported supplemental manifest schema version")
    primary_manifest_path, selected_primary_manifest, primary_manifest_sha256 = (
        read_verified_json_input(
            args.primary_manifest, args.primary_manifest_sha256, "primary source-freeze manifest"
        )
    )
    if manifest["primary_inputs"].get("manifest_sha256") != primary_manifest_sha256:
        raise SupplementalError(
            "supplemental manifest is not bound to the supplied primary manifest bytes"
        )
    if not manifest["supplemental_suite"].get("selectors"):
        raise SupplementalError("supplemental suite has no selected selectors")
    primary_runner_sha256 = manifest["primary_inputs"].get("runner_sha256")
    if not isinstance(primary_runner_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", primary_runner_sha256
    ):
        raise SupplementalError("supplement does not bind the primary runner bytes")
    if manifest["primary_inputs"].get("primary_suite_manifest_field") != "current_primary_suite":
        raise SupplementalError(
            "supplement does not bind the primary current suite selector contract"
        )

    repo = Path(args.repo).resolve(strict=True)
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        raise SupplementalError(f"--repo must be an attached Git repository: {repo}")
    runner = load_primary_runner(primary_runner_sha256)
    _, primary_manifest, verified_primary_sha256 = runner.load_verified_json_file(
        primary_manifest_path,
        primary_manifest_sha256,
        "primary source-freeze manifest",
        expected_schema_version=1,
    )
    if (
        verified_primary_sha256 != primary_manifest_sha256
        or primary_manifest != selected_primary_manifest
    ):
        raise SupplementalError("primary manifest bytes changed between verified readers")
    runner.frozen_source_preflight(repo, args.source_sha, args.source_tree)

    primary_root = Path(args.primary_run).resolve(strict=True)
    receipt_path = primary_root / "run-receipt.json"
    primary_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if primary_receipt.get("status") != manifest["primary_inputs"]["required_status"]:
        raise SupplementalError("primary package wave did not finish with status=pass")
    if (primary_receipt.get("source_sha"), primary_receipt.get("source_tree")) != (
        args.source_sha,
        args.source_tree,
    ):
        raise SupplementalError("primary wave was not built from the supplied frozen source")
    if set(primary_receipt.get("profiles", {})) != set(PROFILE_NAMES):
        raise SupplementalError("primary wave does not contain exactly the three required profiles")
    if (primary_receipt.get("manifest_path"), primary_receipt.get("manifest_sha256")) != (
        str(primary_manifest_path),
        primary_manifest_sha256,
    ):
        raise SupplementalError(
            "primary run receipt does not bind the supplied manifest path and bytes"
        )
    primary_manifest, assets = runner.read_asset_manifest(
        primary_root / "frozen-source" / PRODUCT_NAME, primary_manifest
    )
    expected_asset_count = manifest["primary_inputs"].get("force_include_asset_count_per_profile")
    require_exact_resource_count(expected_asset_count, len(assets))
    primary_source = primary_root / "frozen-source" / PRODUCT_NAME
    original_primary_ids = runner.baseline_node_ids(primary_source, primary_manifest)
    baseline_count = primary_manifest["original_q2_suite"]["baseline_case_count"]
    if not runner.exact_nonbool_count_matches(baseline_count, len(original_primary_ids)):
        raise SupplementalError(
            "primary original Q2 ID denominator differs from its baseline manifest: "
            f"actual={len(original_primary_ids)} expected={baseline_count}"
        )
    try:
        expected_primary_ids = runner.verify_current_primary_suite_sources(
            primary_source, primary_manifest, original_primary_ids
        )
    except runner.WaveFailure as error:
        raise SupplementalError(
            f"primary current suite manifest/source is invalid: {error}"
        ) from error

    env_config_path = primary_root / "installed-env-config.json"
    env_config = json.loads(env_config_path.read_text(encoding="utf-8"))
    installed_python = require_file(env_config["python"], "primary installed consumer Python")
    purelib = Path(env_config["purelib"]).resolve(strict=True)
    installed_prefix = Path(env_config["venv"]).resolve(strict=True)
    dependency_site = Path(
        env_config["app_dependency_site_appended_without_pth_processing"]
    ).resolve(strict=True)
    if not purelib.is_relative_to(installed_prefix):
        raise SupplementalError("primary consumer purelib escapes the reusable venv")
    if tuple(purelib.glob("*.pth")):
        raise SupplementalError("primary consumer venv contains a .pth file")
    if not (purelib / "q2_installed_origin_plugin.py").is_file():
        raise SupplementalError("primary installed-origin plugin is absent")

    source_product = primary_root / "frozen-source" / PRODUCT_NAME
    live_product = repo / PRODUCT_NAME
    test_file = source_product / manifest["supplemental_suite"]["test_path"]
    expected_ids = suite_node_ids(source_product, manifest)
    if not test_file.is_file():
        raise SupplementalError(f"frozen supplemental test file is absent: {test_file}")
    uv = shutil.which("uv")
    if not uv:
        raise SupplementalError("uv executable is not available on PATH")

    primary_profiles = {}
    for profile_name in PROFILE_NAMES:
        primary_profiles[profile_name] = verify_primary_profile(
            runner=runner,
            run_root=primary_root,
            profile_name=profile_name,
            profile=primary_receipt["profiles"][profile_name],
            primary_manifest=primary_manifest,
            expected_ids=expected_primary_ids,
            assets=assets,
            purelib=purelib,
            source_product=source_product,
            live_product=live_product,
            dependency_site=dependency_site,
        )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if args.output_root and not Path(args.output_root).is_absolute():
        raise SupplementalError("--output-root must be absolute")
    output_root = (
        Path(args.output_root).resolve() if args.output_root else HERE / "supplemental-runs"
    )
    output_root.mkdir(parents=True, exist_ok=True)
    run_root = output_root / f"{args.source_sha}-{stamp}-pid{os.getpid()}"
    run_root.mkdir(parents=False, exist_ok=False)
    receipt_path = run_root / "supplemental-receipt.json"
    receipt: dict[str, Any] = {
        "status": "running",
        "source_sha": args.source_sha,
        "source_tree": args.source_tree,
        "repo": str(repo),
        "primary_run": str(primary_root),
        "primary_receipt_sha256": sha256_file(primary_root / "run-receipt.json"),
        "primary_runner_path": str(PRIMARY_RUNNER_PATH),
        "primary_runner_sha256": primary_runner_sha256,
        "primary_manifest_path": str(primary_manifest_path),
        "primary_manifest_sha256": primary_manifest_sha256,
        "supplemental_manifest_path": str(supplemental_manifest_path),
        "supplemental_manifest_sha256": supplemental_manifest_sha256,
        "supplemental_runner_sha256": sha256_file(Path(__file__).resolve()),
        "test_file": str(test_file),
        "test_file_sha256": sha256_file(test_file),
        "installed_environment": {
            "python": str(installed_python),
            "purelib": str(purelib),
            "dependency_site": str(dependency_site),
            "reuse": "one primary installed consumer venv, three sequential wheel reinstalls",
        },
        "primary_profile_preflight": primary_profiles,
        "profiles": {},
        "retention": "All files are retained; this driver has no cleanup path.",
    }
    json_write(receipt_path, receipt)

    try:
        env = runner.clean_child_env()
        previous_wall_seconds: float | None = None
        for profile_name in PROFILE_NAMES:
            profile_receipt = primary_receipt["profiles"][profile_name]
            wheel = Path(profile_receipt["wheel"]["path"]).resolve(strict=True)
            output = run_root / profile_name
            output.mkdir(parents=False, exist_ok=False)
            profile_state: dict[str, Any] = {
                "status": "running",
                "wheel": {"path": str(wheel), "sha256": profile_receipt["wheel"]["sha256"]},
            }
            receipt["profiles"][profile_name] = profile_state
            json_write(receipt_path, receipt)

            runner.run_command(
                [
                    uv,
                    "pip",
                    "install",
                    "--offline",
                    "--reinstall",
                    "--no-deps",
                    "--python",
                    str(installed_python),
                    str(wheel),
                ],
                cwd=run_root,
                env=env,
                log_stem=output / "install-wheel",
            )
            if tuple(purelib.glob("*.pth")):
                raise SupplementalError(f"wheel install created a .pth file: {profile_name}")

            profile_timeout = (
                None if previous_wall_seconds is None else math.ceil(2 * previous_wall_seconds)
            )
            profile_state["consumer_timeout_seconds"] = profile_timeout
            child_env = runner.clean_child_env()
            child_env.update(
                {
                    "E02_SOURCE_ROOT": str(source_product),
                    "E02_LIVE_PRODUCT_ROOT": str(live_product),
                    "E02_DEPENDENCY_SITE": str(dependency_site),
                    "E02_NODEIDS_REPORT": str(output / "collected-nodeids.json"),
                    "E02_ORIGIN_REPORT": str(output / "origin-proof.json"),
                }
            )
            argv = [
                str(installed_python),
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
                str(source_product / "tests/unit"),
                "--rootdir",
                str(source_product),
                "--strict-markers",
                "-q",
                "-ra",
                "-s",
                "--junitxml",
                str(output / "supplemental-junit.xml"),
                "--basetemp",
                str(output / "pytest-tmp"),
                str(test_file),
            ]
            start = time.monotonic()
            try:
                result = runner.run_command(
                    argv,
                    cwd=repo,
                    env=child_env,
                    log_stem=output / "consumer-suite",
                    check=False,
                    stream_output=True,
                    timeout_seconds=profile_timeout,
                )
            except BaseException:
                profile_state["consumer_wall_seconds"] = time.monotonic() - start
                profile_state["consumer_output"] = output_record(output)
                profile_state["status"] = "failed"
                profile_state["failure"] = (
                    "consumer command raised; command record and terminal streams are hash-bound"
                )
                json_write(receipt_path, receipt)
                raise
            profile_state["consumer_wall_seconds"] = time.monotonic() - start
            profile_state["consumer_output"] = output_record(output)
            profile_state["status"] = "consumer-finished"
            json_write(receipt_path, receipt)

            try:
                proof = verify_supplemental_run(
                    result=result,
                    output=output,
                    expected_ids=expected_ids,
                    purelib=purelib,
                    source_product=source_product,
                    live_product=live_product,
                    dependency_site=dependency_site,
                    expected_denominator_properties=manifest["supplemental_suite"][
                        "denominator_properties"
                    ],
                )
            except BaseException as error:
                profile_state["status"] = "failed"
                profile_state["failure"] = f"{type(error).__name__}: {error}"
                profile_state["consumer_output"] = output_record(output)
                json_write(receipt_path, receipt)
                raise
            profile_state["consumer"] = proof
            profile_state["status"] = "pass"
            profile_state["consumer_output"] = output_record(output)
            json_write(receipt_path, receipt)
            previous_wall_seconds = profile_state["consumer_wall_seconds"]

        read_verified_json_input(
            primary_manifest_path, primary_manifest_sha256, "primary source-freeze manifest"
        )
        read_verified_json_input(
            supplemental_manifest_path,
            supplemental_manifest_sha256,
            "supplemental source-freeze manifest",
        )
        receipt["status"] = "pass"
        receipt["finished_utc"] = datetime.now(UTC).isoformat()
        json_write(receipt_path, receipt)
        return run_root
    except BaseException as error:
        for profile_state in receipt["profiles"].values():
            if profile_state.get("status") in {"running", "consumer-finished"}:
                profile_state["status"] = "failed"
                profile_state["failure"] = f"{type(error).__name__}: {error}"
        receipt["status"] = "failed"
        receipt["failure"] = f"{type(error).__name__}: {error}"
        receipt["finished_utc"] = datetime.now(UTC).isoformat()
        json_write(receipt_path, receipt)
        raise


def output_record(output: Path) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for stream in ("stdout", "stderr"):
        path = output / f"consumer-suite.{stream}.txt"
        if path.is_file():
            record[stream] = {
                "path": str(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        else:
            record[stream] = {
                "path": None,
                "bytes": None,
                "sha256": None,
                "unavailable_reason": "command did not create stream file",
            }
    command_path = output / "consumer-suite.command.json"
    if command_path.is_file():
        command = json.loads(command_path.read_text(encoding="utf-8"))
        record["command_record"] = {
            "path": str(command_path),
            "bytes": command_path.stat().st_size,
            "sha256": sha256_file(command_path),
            "returncode": command.get("returncode"),
            "timed_out": command.get("timed_out"),
            "timeout_seconds": command.get("timeout_seconds"),
        }
    else:
        record["command_record"] = {
            "path": None,
            "bytes": None,
            "sha256": None,
            "unavailable_reason": "command wrapper did not create command.json",
        }
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", required=True, help="attached repository root containing policy-engine"
    )
    parser.add_argument("--source-sha", required=True, help="actual full frozen Git commit SHA")
    parser.add_argument("--source-tree", required=True, help="actual full frozen Git tree SHA")
    parser.add_argument(
        "--primary-manifest", required=True, help="absolute primary freeze manifest path"
    )
    parser.add_argument(
        "--primary-manifest-sha256", required=True, help="exact primary manifest SHA-256"
    )
    parser.add_argument(
        "--supplemental-manifest", required=True, help="absolute supplemental freeze manifest path"
    )
    parser.add_argument(
        "--supplemental-manifest-sha256", required=True, help="exact supplemental manifest SHA-256"
    )
    parser.add_argument(
        "--primary-run", required=True, help="completed primary run directory with status=pass"
    )
    parser.add_argument(
        "--output-root", help="optional absolute path for a new retained run directory"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_root = run_supplement(args)
    except BaseException as error:
        sys.stderr.write(f"supplemental installed wave failed: {type(error).__name__}: {error}\n")
        return 1
    sys.stdout.write(f"{run_root}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

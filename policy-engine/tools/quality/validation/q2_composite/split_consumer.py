#!/usr/bin/env python3
"""Consume a source-bound Q2 wheel on the existing Linux worker profile.

This candidate uses the existing CPython 3.14 dependency environment and the
separate, already-provisioned CPython 3.12 DoWhy profile. It creates no virtual
environment, installs no dependencies, and has no source-checkout import path.
"""

# ruff: noqa: TC004 -- protocol imports are deferred until their external byte pins pass.

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import stat
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    from split_protocol import (
        MAX_INSTALLER_METADATA_OVERHEAD_BYTES,
        MAX_WORKER_LOG_AND_TEST_TEMP_BYTES,
        MAX_WORKER_METADATA_BYTES,
        PROFILE_CHAIN_KEYS,
        REQUEST_SCHEMA,
        SplitProtocolError,
        _relative,
        build_source_inventory,
        canonical_json_bytes,
        load_json_bytes,
        require_worker_space,
        sha256_bytes,
        sha256_file,
        snapshot_installed_tree,
        validate_inventory,
        validate_request_binding,
        validate_source_audit_selection,
        verify_installed_inventory,
        verify_wheel_inventory,
        wheel_uncompressed_bytes,
        worker_write_budget,
    )


_PROTOCOL_EXPORTS = (
    "MAX_INSTALLER_METADATA_OVERHEAD_BYTES",
    "MAX_WORKER_LOG_AND_TEST_TEMP_BYTES",
    "MAX_WORKER_METADATA_BYTES",
    "PROFILE_CHAIN_KEYS",
    "REQUEST_SCHEMA",
    "SplitProtocolError",
    "_relative",
    "build_source_inventory",
    "canonical_json_bytes",
    "load_json_bytes",
    "require_worker_space",
    "sha256_bytes",
    "sha256_file",
    "snapshot_installed_tree",
    "validate_inventory",
    "validate_request_binding",
    "validate_source_audit_selection",
    "verify_installed_inventory",
    "verify_wheel_inventory",
    "wheel_uncompressed_bytes",
    "worker_write_budget",
)


def _raw_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _preflight_regular_bytes(path: Path, label: str) -> bytes:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current = current / component
        try:
            mode = current.lstat().st_mode
        except OSError as error:
            raise ValueError(f"{label} path component cannot be inspected: {current}") from error
        if stat.S_ISLNK(mode):
            raise ValueError(f"{label} path has a symlinked component: {current}")
    if not stat.S_ISREG(absolute.lstat().st_mode):
        raise ValueError(f"{label} must be a regular file: {absolute}")
    return absolute.read_bytes()


def _preflight_json(raw: bytes, label: str) -> dict[str, Any]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"{label} contains duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not strict JSON") from error
    if type(value) is not dict:
        raise ValueError(f"{label} root must be an object")
    return value


def _load_pinned_protocol(args: argparse.Namespace) -> None:
    """Verify the source-bound handoff before executing its protocol module."""
    transfer = Path(os.path.abspath(args.transfer_root))
    request_path = Path(os.path.abspath(args.request))
    if request_path.parent != transfer or request_path.name != "split-consumer-request.json":
        raise ValueError("request must be the named file directly inside the transfer root")
    request_raw = _preflight_regular_bytes(request_path, "split-consumer request")
    external_pin = args.request_sha256
    if (
        type(external_pin) is not str
        or len(external_pin) != 64
        or any(char not in "0123456789abcdef" for char in external_pin)
        or _raw_sha256(request_raw) != external_pin
    ):
        raise ValueError("split-consumer request differs from its external SHA-256 pin")
    request = _preflight_json(request_raw, "split-consumer request")
    harness = request.get("harness")
    if type(harness) is not dict:
        raise ValueError("source-bound request has no harness pins")
    if (
        harness.get("protocol_file") != "split_protocol.py"
        or harness.get("consumer_file") != "split_consumer.py"
    ):
        raise ValueError("source-bound request names unexpected protocol or consumer files")
    consumer_path = Path(os.path.abspath(__file__))
    if consumer_path.parent != transfer:
        raise ValueError("executing consumer is not the transferred source-bound copy")
    consumer_raw = _preflight_regular_bytes(consumer_path, "split consumer")
    protocol_path = transfer / "split_protocol.py"
    protocol_raw = _preflight_regular_bytes(protocol_path, "split protocol")
    for label, raw, key in (
        ("split consumer", consumer_raw, "consumer_sha256"),
        ("split protocol", protocol_raw, "protocol_sha256"),
    ):
        expected = harness.get(key)
        if (
            type(expected) is not str
            or len(expected) != 64
            or any(char not in "0123456789abcdef" for char in expected)
            or _raw_sha256(raw) != expected
        ):
            raise ValueError(f"{label} differs from its source-bound request pin")

    spec = importlib.util.spec_from_file_location(
        "e02_source_bound_q2_split_protocol", protocol_path
    )
    if spec is None or spec.loader is None:
        raise ValueError("cannot load the verified source-bound split protocol")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # Do not grow the transferred source bundle with an incidental pyc file.
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    for name in _PROTOCOL_EXPORTS:
        globals()[name] = getattr(module, name)


Q2_RUNNER_RELATIVE = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
    "LOCAL/q2-packaging/raw/run.py"
)
Q2_GATE_RELATIVE = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
    "LOCAL/q2-packaging/raw/installed_origin_gate_r4.py"
)
SUPPLEMENTAL_RUNNER_RELATIVE = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
    "LOCAL/q2-packaging/raw/supplemental_run.py"
)
BUILD_PROFILE_RELATIVE = "architecture/packaging/q2_build_tools.toml"
RESOURCE_HELPER_RELATIVE = "tools/quality/validation/packaged_resource_contract.py"
MAX_WHEEL_BYTES = 65 * 1024 * 1024


def _read_regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SplitProtocolError(f"{label} must be an existing regular non-symlink file: {path}")
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current = current / component
        try:
            if current.is_symlink():
                raise SplitProtocolError(f"{label} has a symlinked path component: {current}")
        except OSError as error:
            raise SplitProtocolError(f"{label} path cannot be inspected: {current}") from error
    resolved = path.resolve(strict=True)
    if resolved != path.absolute():
        raise SplitProtocolError(f"{label} path spelling differs from its resolved path: {path}")
    return resolved.read_bytes()


def _child(root: Path, name: object, label: str) -> Path:
    if type(name) is not str or not name or Path(name).name != name or name in {".", ".."}:
        raise SplitProtocolError(f"{label} must be a single filename")
    path = root / name
    _read_regular(path, label)
    return path


def _child_relative(root: Path, value: object, label: str) -> Path:
    """Resolve one canonical relative transfer path without following symlinks."""
    relative = _relative(value, label=label)
    candidate = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise SplitProtocolError(f"{label} contains a symlinked path component: {current}")
    _read_regular(candidate, label)
    try:
        candidate.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, RuntimeError, ValueError) as error:
        raise SplitProtocolError(f"{label} escapes the transfer root") from error
    return candidate


def _verify_transfer_file_set(root: Path, expected_files: set[str]) -> None:
    """Require the whole worker transfer tree to equal its source-bound file set."""
    observed_files: set[str] = set()
    observed_directories: set[str] = set()
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in (*dirnames, *filenames):
            path = current_path / name
            if path.is_symlink():
                raise SplitProtocolError(f"worker transfer contains a symlink: {path}")
            relative = path.relative_to(root).as_posix()
            if path.is_dir():
                observed_directories.add(relative)
            elif path.is_file():
                observed_files.add(relative)
            else:
                raise SplitProtocolError(f"worker transfer contains a special member: {path}")
    expected_directories = {
        "/".join(PurePosixPath(name).parts[:index])
        for name in expected_files
        for index in range(1, len(PurePosixPath(name).parts))
    }
    if observed_files != expected_files or observed_directories != expected_directories:
        raise SplitProtocolError(
            "worker transfer full member set differs from the pinned request: "
            f"missing_files={sorted(expected_files - observed_files)[:20]} "
            f"unexpected_files={sorted(observed_files - expected_files)[:20]} "
            f"missing_dirs={sorted(expected_directories - observed_directories)[:20]} "
            f"unexpected_dirs={sorted(observed_directories - expected_directories)[:20]}"
        )


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SplitProtocolError(f"cannot load source-owned module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hash_pin(path: Path, expected: object, label: str) -> str:
    if type(expected) is not str or len(expected) != 64:
        raise SplitProtocolError(f"{label} pin must be a full SHA-256")
    observed = sha256_file(path)
    if observed != expected:
        raise SplitProtocolError(f"{label} differs from the transferred source-bound pin")
    return observed


def _write_new_or_same(path: Path, content: bytes, label: str) -> dict[str, Any]:
    if path.is_symlink():
        raise SplitProtocolError(f"refusing symlinked {label}: {path}")
    if path.exists():
        observed = _read_regular(path, label)
        if observed != content:
            raise SplitProtocolError(f"existing {label} differs; refusing to overwrite: {path}")
        return {"path": str(path), "sha256": sha256_bytes(observed), "created": False}
    path.write_bytes(content)
    observed = _read_regular(path, label)
    if observed != content:
        raise SplitProtocolError(f"{label} readback differs after write: {path}")
    return {"path": str(path), "sha256": sha256_bytes(observed), "created": True}


def _parse_interpreter_json(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SplitProtocolError(f"{label} did not emit JSON") from error
    if type(value) is not dict:
        raise SplitProtocolError(f"{label} JSON root must be an object")
    return value


def origin_plugin_source() -> bytes:
    """Return the small pytest hook bound to the existing Q2 origin gate."""
    source = """from __future__ import annotations

import json
import os
import sys
import sysconfig
from pathlib import Path

import pytest
import polisyos
import tools
import q2_installed_origin_gate


def _under(path: object, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(root.resolve())
        return True
    except (OSError, TypeError, ValueError):
        return False


def pytest_collection_finish(session: object) -> None:
    target = Path(os.environ["E02_Q2_INSTALLED_TARGET"])
    dependency_site = Path(os.environ["E02_DEPENDENCY_SITE"])
    observed = sorted(item.nodeid for item in session.items)
    Path(os.environ["E02_NODEIDS_REPORT"]).write_text(
        json.dumps(observed, indent=2) + "\\n", encoding="utf-8"
    )
    Path(os.environ["E02_Q2_TARGET_PROOF"]).write_text(
        json.dumps(
            {
                "purelib": str(target.resolve()),
                "target": str(target.resolve()),
                "dependency_site": str(dependency_site.resolve()),
                "node_ids": len(observed),
            },
            sort_keys=True,
        )
        + "\\n",
        encoding="utf-8",
    )


def pytest_sessionfinish(session: object, exitstatus: int) -> None:
    target = Path(os.environ["E02_Q2_INSTALLED_TARGET"]).resolve(strict=True)
    interpreter_purelib = Path(sysconfig.get_paths()["purelib"]).resolve(strict=True)
    source = Path(os.environ["E02_SOURCE_ROOT"]).resolve(strict=True)
    live_product = Path(os.environ["E02_LIVE_PRODUCT_ROOT"]).resolve(strict=True)
    dependency_site = Path(os.environ["E02_DEPENDENCY_SITE"]).resolve(strict=True)
    forbidden = [source, live_product]
    errors: list[dict[str, object]] = []
    forbidden_sys_path = [
        entry for entry in sys.path if entry and any(_under(entry, root) for root in forbidden)
    ]
    if forbidden_sys_path:
        errors.append({"sys_path": forbidden_sys_path, "reason": "source checkout import path"})
    normalized = [Path(entry).resolve() for entry in sys.path if entry]
    try:
        target_index = normalized.index(target)
    except ValueError:
        target_index = -1
        errors.append({"reason": "installed target absent from sys.path"})
    try:
        dependency_index = normalized.index(dependency_site)
    except ValueError:
        dependency_index = -1
        errors.append({"reason": "selected dependency site absent from sys.path"})
    if target_index < 0 or dependency_index < 0 or target_index > dependency_index:
        errors.append(
            {
                "reason": "installed target must precede the dependency profile",
                "target_index": target_index,
                "dependency_index": dependency_index,
            }
        )
    origins, origin_errors = q2_installed_origin_gate.verify_loaded_module_origins(
        target, sys.modules.copy()
    )
    if "polisyos" not in origins:
        origin_errors.append({"module": "polisyos", "reason": "installed root was not imported"})
    errors.extend(origin_errors)
    report = {
        "verified": not errors,
        "pytest_exit_status": exitstatus,
        "purelib": str(target),
        "interpreter_purelib": str(interpreter_purelib),
        "dependency_site": str(dependency_site),
        "sys_path": sys.path,
        "origins": {
            name: [
                row.get("resolved_file", row.get("resolved_path"))
                for row in (
                    [detail]
                    if "resolved_file" in detail
                    else detail.get("namespace_locations", [])
                )
            ]
            for name, detail in origins.items()
        },
        "origin_details": origins,
        "errors": errors,
    }
    Path(os.environ["E02_ORIGIN_REPORT"]).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\\n", encoding="utf-8"
    )
    if errors:
        print("Q2 split installed-origin proof failed: " + json.dumps(errors), file=sys.stderr)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
"""
    return source.encode("utf-8")


def pytest_target_bootstrap_source() -> bytes:
    """Return a neutral -I bootstrap for one distinct installed target directory."""
    source = """from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

target = Path(os.environ["E02_Q2_INSTALLED_TARGET"]).resolve(strict=True)
dependency_site = Path(os.environ["E02_DEPENDENCY_SITE"]).resolve(strict=True)
if not target.is_dir() or not dependency_site.is_dir():
    raise RuntimeError("Q2 installed target or selected dependency site is absent")
sys.path = [entry for entry in sys.path if entry and Path(entry).resolve() != target]
sys.path.insert(0, str(target))
if dependency_site not in [Path(entry).resolve() for entry in sys.path if entry]:
    sys.path.append(str(dependency_site))
sys.argv = ["pytest", *sys.argv[1:]]
runpy.run_module("pytest", run_name="__main__")
"""
    return source.encode("utf-8")


def _validate_wheel_metadata_target(
    purelib: Path, wheel_name: str, project_name: str, project_version: str
) -> dict[str, Any]:
    expected_prefix = project_name.replace("-", "_").lower() + "-"
    if not wheel_name.startswith(expected_prefix) or not wheel_name.endswith(".whl"):
        raise SplitProtocolError("selected wheel filename does not match the frozen project")
    metadata_roots = sorted(
        path
        for path in purelib.glob("*.dist-info")
        if path.name.lower().startswith(expected_prefix)
    )
    if len(metadata_roots) != 1 or metadata_roots[0].is_symlink():
        raise SplitProtocolError(
            f"expected one installed distribution metadata root, found {metadata_roots}"
        )
    metadata_file = metadata_roots[0] / "METADATA"
    raw = _read_regular(metadata_file, "installed wheel metadata")
    headers: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.lower()] = value.strip()
    if headers.get("name", "").lower().replace("-", "_") != project_name.lower().replace("-", "_"):
        raise SplitProtocolError("installed distribution metadata name differs from pyproject")
    if headers.get("version") != project_version:
        raise SplitProtocolError("installed distribution metadata version differs from pyproject")
    wheel_metadata = metadata_roots[0] / "WHEEL"
    record_metadata = metadata_roots[0] / "RECORD"
    _read_regular(wheel_metadata, "installed WHEEL metadata")
    _read_regular(record_metadata, "installed RECORD metadata")
    return {
        "root": str(metadata_roots[0]),
        "name": headers["name"],
        "version": headers["version"],
        "files": sorted(path.name for path in metadata_roots[0].iterdir()),
    }


def _check_preinstall_target(purelib: Path, inventory: dict[str, Any]) -> dict[str, Any]:
    if purelib.is_symlink() or not purelib.is_dir():
        raise SplitProtocolError(
            "selected interpreter purelib must be an existing regular directory"
        )
    conflicts = [
        str(purelib / root)
        for root in inventory["package_roots"]
        if (purelib / root).exists() or (purelib / root).is_symlink()
    ]
    if conflicts:
        raise SplitProtocolError(f"existing purelib already contains a package root: {conflicts}")
    expected_info_root = inventory["project_metadata"]["dist_info_root"]
    metadata_path = purelib / expected_info_root
    if metadata_path.exists() or metadata_path.is_symlink():
        raise SplitProtocolError(
            f"existing purelib already contains the selected distribution metadata: {metadata_path}"
        )
    before_snapshot = snapshot_installed_tree(purelib)
    return {
        "purelib": str(purelib),
        "package_roots_absent": list(inventory["package_roots"]),
        "existing_pth_files": [
            {"path": str(path), "sha256": sha256_file(path)}
            for path in sorted(purelib.glob("*.pth"))
        ],
        "existing_egg_link_files": [str(path) for path in sorted(purelib.glob("*.egg-link"))],
        "whole_target_before_snapshot_sha256": sha256_bytes(canonical_json_bytes(before_snapshot)),
        "whole_target_before_file_count": len(before_snapshot),
        "_whole_target_before_snapshot": before_snapshot,
    }


def _tree_regular_file_bytes(root: Path) -> int:
    if root.is_symlink() or not root.is_dir():
        raise SplitProtocolError(f"expected a regular directory for size accounting: {root}")
    total = 0
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in (*dirnames, *filenames):
            path = current_path / name
            if path.is_symlink():
                raise SplitProtocolError(f"size accounting encountered a symlink: {path}")
        for name in filenames:
            path = current_path / name
            if not path.is_file():
                raise SplitProtocolError(f"size accounting encountered a special file: {path}")
            total += path.stat().st_size
    return total


def _output_tree_bytes(root: Path, *, excluded_roots: set[Path] | None = None) -> int:
    """Count retained outputs while optionally accounting installed targets separately."""
    excluded = {path.resolve(strict=True) for path in (excluded_roots or set())}
    total = 0
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        if current_path.resolve(strict=True) in excluded:
            dirnames[:] = []
            continue
        kept_dirs: list[str] = []
        for name in (*dirnames, *filenames):
            path = current_path / name
            if path.is_symlink():
                raise SplitProtocolError(f"worker output contains a symlink: {path}")
            if path.is_dir() and path.resolve(strict=True) not in excluded:
                kept_dirs.append(name)
        dirnames[:] = kept_dirs
        for name in filenames:
            path = current_path / name
            if path.resolve(strict=True) in excluded:
                continue
            if not path.is_file():
                raise SplitProtocolError(f"worker output contains a special file: {path}")
            total += path.stat().st_size
    return total


def _verify_source_selection(
    runner: ModuleType,
    repo: Path,
    manifest: dict[str, Any],
    request: dict[str, Any],
) -> tuple[set[str], set[str], dict[str, Any]]:
    product = repo / "policy-engine"
    original = runner.baseline_node_ids(product, manifest)
    current = runner.verify_current_primary_suite_sources(product, manifest, original)
    transitive = runner.verify_transitive_test_bindings(product, manifest, original)
    selection = request.get("consumer_selection")
    if type(selection) is not dict or (
        selection.get("manifest_driven") is not True
        or selection.get("primary_node_ids") != sorted(current)
        or selection.get("primary_node_ids_sha256") != runner.node_ids_sha256(current)
        or selection.get("transitive_fixture_bindings_sha256")
        != sha256_bytes(canonical_json_bytes(transitive))
    ):
        raise SplitProtocolError(
            "worker recomputed test selection differs from the host source-bound selector receipt"
        )
    return original, current, transitive


def _run_installed_resource_helper(
    runner: ModuleType,
    python: Path,
    product: Path,
    repo: Path,
    owner_inventory: dict[str, Any],
    purelib: Path,
    dependency_site: Path,
    run_root: Path,
    logs: Path,
) -> dict[str, Any]:
    inventory_path = run_root / "runtime-resource-owner-inventory.json"
    runner.json_write(inventory_path, owner_inventory)
    helper = product / RESOURCE_HELPER_RELATIVE
    env = runner.clean_child_env()
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "E02_Q2_INSTALLED_TARGET": str(purelib.resolve(strict=True)),
            "E02_DEPENDENCY_SITE": str(dependency_site.resolve(strict=True)),
        }
    )
    bootstrap = run_root / "run-installed-resource-helper.py"
    bootstrap.write_text(
        "import os, runpy, sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(os.environ['E02_Q2_INSTALLED_TARGET']).resolve()))\n"
        "_q2_dependency_site = str(Path(os.environ['E02_DEPENDENCY_SITE']).resolve())\n"
        "if _q2_dependency_site not in [str(Path(entry).resolve())\n"
        "        for entry in sys.path if entry]:\n"
        "    sys.path.append(_q2_dependency_site)\n"
        f"sys.argv = [{str(helper)!r}, 'installed', '--expected-inventory', "
        f"{str(inventory_path)!r}, '--purelib', {str(purelib)!r}, "
        f"'--forbidden-root', {str(repo)!r}, '--forbidden-root', {str(product)!r}]\n"
        f"runpy.run_path({str(helper)!r}, run_name='__main__')\n",
        encoding="utf-8",
    )
    result = runner.run_command(
        [str(python), "-I", str(bootstrap)],
        cwd=run_root,
        env=env,
        log_stem=logs / "canonical-installed-resource-contract",
    )
    proof = _parse_interpreter_json(result.stdout, "canonical installed resource contract")
    if proof.get("schema") != "polisyos.packaged-resource-contract.v1":
        raise SplitProtocolError("canonical installed resource helper returned an unknown schema")
    expected_targets = {row["wheel"] for row in owner_inventory["assets"]}
    if set(proof.get("runtime_owner_targets", [])) != expected_targets:
        raise SplitProtocolError("installed runtime owner resource set differs from source owners")
    if set(proof.get("importlib_resources", {})) != expected_targets:
        raise SplitProtocolError("importlib.resources did not read every source-owned resource")
    for row in owner_inventory["assets"]:
        observed = proof["importlib_resources"].get(row["wheel"])
        if observed != {"bytes": row["bytes"], "sha256": row["sha256"]}:
            raise SplitProtocolError(f"installed importlib.resources bytes differ: {row['wheel']}")
    return proof


def _poisoned_neighbor_probe(
    runner: ModuleType,
    python: Path,
    installed_target: Path,
    dependency_site: Path,
    product: Path,
    repo: Path,
    owner_inventory: dict[str, Any],
    run_root: Path,
    logs: Path,
) -> dict[str, Any]:
    neutral_cwd = run_root / "neutral-consumer-cwd"
    neutral_cwd.mkdir()
    poison_root = neutral_cwd / "polisyos" / "data_forge" / "domains" / "catalog" / "_resources"
    poison_root.mkdir(parents=True)
    for index, row in enumerate(owner_inventory["owners"]["catalog_defaults"]):
        name = row["name"]
        for directory in (neutral_cwd, poison_root):
            candidate = directory / name
            candidate.write_bytes(f"poison-{index}-{directory.name}\n".encode())
    expected_path = run_root / "owner-assets-expected.json"
    runner.json_write(expected_path, owner_inventory)
    script = """import json, os, sys
from pathlib import Path
from typing import get_args
target = Path(os.environ["E02_Q2_INSTALLED_TARGET"]).resolve(strict=True)
dependency_site = Path(os.environ["E02_DEPENDENCY_SITE"]).resolve(strict=True)
sys.path.insert(0, str(target))
if str(dependency_site) not in [str(Path(entry).resolve()) for entry in sys.path if entry]:
    sys.path.append(str(dependency_site))
from polisyos.data_forge.domains.catalog import _resources
from polisyos.foundry.methods.catalog import dependency_authority
from polisyos.foundry.methods.catalog.causal import _dowhy_worker
import polisyos, tools
import q2_installed_origin_gate

repo = Path(os.environ["E02_SOURCE_ROOT"]).resolve(strict=True)
product = Path(os.environ["E02_LIVE_PRODUCT_ROOT"]).resolve(strict=True)
expected = json.loads(Path(os.environ["E02_OWNER_ASSETS"]).read_text(encoding="utf-8"))
rows = expected["owners"]["catalog_defaults"]
targets = {Path(row["wheel"]).name: row for row in rows}
names = tuple(get_args(_resources.CatalogDefaultResource))
assert set(targets) == set(names), (sorted(targets), sorted(names))
for name in names:
    resolved = Path(_resources.catalog_default_resource_path(name)).resolve(strict=True)
    expected_path = (target / targets[name]["wheel"]).resolve(strict=True)
    assert resolved == expected_path, (name, resolved, expected_path)
    assert resolved.read_bytes() == (target / targets[name]["wheel"]).read_bytes(), name
registry = Path(dependency_authority._DIGEST_REGISTRY_PATH).resolve(strict=True)
packaged_registry = Path(dependency_authority._PACKAGED_DIGEST_REGISTRY_PATH).resolve(strict=True)
assert registry == packaged_registry
assert dependency_authority.load_digest_domain_registry(registry).statement.domains
worker_dir = Path(_dowhy_worker._worker_directory()).resolve(strict=True)
worker_targets = expected["owners"]["worker_profile_assets"]
expected_worker = (target / worker_targets[0]["wheel"]).parent.resolve(strict=True)
assert worker_dir == expected_worker, (worker_dir, expected_worker)
assert all((worker_dir / row["name"]).is_file() for row in worker_targets)
origins, errors = q2_installed_origin_gate.verify_loaded_module_origins(target, sys.modules.copy())
assert not errors, errors
assert {"polisyos", "tools"} <= set(origins), sorted(origins)
for entry in sys.path:
    if entry:
        path = Path(entry).resolve(strict=False)
        assert path != repo and not path.is_relative_to(repo)
        assert path != product and not path.is_relative_to(product)
print(
    json.dumps(
        {
            "catalog_readers": {
                name: str(_resources.catalog_default_resource_path(name)) for name in names
            },
            "dependency_registry": str(registry),
            "dowhy_worker_directory": str(worker_dir),
            "origins": origins,
            "poison_neighbor_cwd": os.getcwd(),
            "verified": True,
        },
        sort_keys=True,
    )
)
"""
    script_path = run_root / "installed-reader-poison-control.py"
    script_path.write_text(script, encoding="utf-8")
    env = runner.clean_child_env()
    env.update(
        {
            "E02_SOURCE_ROOT": str(repo),
            "E02_LIVE_PRODUCT_ROOT": str(product),
            "E02_OWNER_ASSETS": str(expected_path),
            "E02_Q2_INSTALLED_TARGET": str(installed_target.resolve(strict=True)),
            "E02_DEPENDENCY_SITE": str(dependency_site.resolve(strict=True)),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    result = runner.run_command(
        [str(python), "-I", str(script_path)],
        cwd=neutral_cwd,
        env=env,
        log_stem=logs / "installed-reader-poison-control",
    )
    return _parse_interpreter_json(result.stdout, "installed reader poison-neighbor control")


def _run_primary_suite(
    runner: ModuleType,
    app_python: Path,
    bootstrap: Path,
    repo: Path,
    product: Path,
    manifest: dict[str, Any],
    target: Path,
    dependency_site: Path,
    output: Path,
    *,
    timeout_seconds: float,
    expected_original_ids: set[str],
    expected_current_ids: set[str],
) -> dict[str, Any]:
    """Run and fully reconcile the source-derived primary consumers for one profile."""
    output.mkdir(parents=True, exist_ok=False)
    env = runner.clean_child_env()
    env.update(
        {
            "E02_SOURCE_ROOT": str(repo),
            "E02_LIVE_PRODUCT_ROOT": str(product),
            "E02_DEPENDENCY_SITE": str(dependency_site),
            "E02_Q2_INSTALLED_TARGET": str(target),
            "E02_NODEIDS_REPORT": str(output / "collected-nodeids.json"),
            "E02_ORIGIN_REPORT": str(output / "origin-proof.json"),
            "E02_Q2_TARGET_PROOF": str(output / "installed-target-proof.json"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    canonical = runner.pytest_arguments(app_python, product, manifest, output)
    if canonical[:4] != [str(app_python), "-I", "-m", "pytest"]:
        raise SplitProtocolError("canonical primary runner changed its isolated pytest entry")
    result = runner.run_command(
        [str(app_python), "-I", str(bootstrap), *canonical[4:]],
        cwd=repo,
        env=env,
        log_stem=output / "consumer-suite",
        check=False,
        stream_output=True,
        timeout_seconds=timeout_seconds,
    )
    proof = runner.verify_consumer_run(
        result,
        run_root=output,
        output=output,
        manifest=manifest,
        expected_original_ids=expected_original_ids,
        expected_current_ids=expected_current_ids,
    )
    target_proof = load_json_bytes(
        _read_regular(output / "installed-target-proof.json", "primary target proof"),
        label="primary target proof",
    )
    if (
        target_proof.get("purelib") != str(target.resolve(strict=True))
        or target_proof.get("dependency_site") != str(dependency_site.resolve(strict=True))
        or target_proof.get("node_ids") != len(expected_current_ids)
    ):
        raise SplitProtocolError("primary target proof differs from selected profile or IDs")
    return proof


def _run_supplemental_suite(
    runner: ModuleType,
    supplemental_runner: ModuleType,
    app_python: Path,
    bootstrap: Path,
    repo: Path,
    product: Path,
    supplemental_manifest: dict[str, Any],
    target: Path,
    dependency_site: Path,
    output: Path,
    *,
    timeout_seconds: float,
    expected_ids: set[str],
) -> dict[str, Any]:
    """Run the separate content-selected supplemental suite for one installed profile."""
    output.mkdir(parents=True, exist_ok=False)
    suite = supplemental_manifest["supplemental_suite"]
    test_path = suite["test_path"]
    test_file = product.joinpath(*PurePosixPath(test_path).parts)
    selectors = suite["selectors"]
    env = runner.clean_child_env()
    env.update(
        {
            "E02_SOURCE_ROOT": str(repo),
            "E02_LIVE_PRODUCT_ROOT": str(product),
            "E02_DEPENDENCY_SITE": str(dependency_site),
            "E02_Q2_INSTALLED_TARGET": str(target),
            "E02_NODEIDS_REPORT": str(output / "collected-nodeids.json"),
            "E02_ORIGIN_REPORT": str(output / "origin-proof.json"),
            "E02_Q2_TARGET_PROOF": str(output / "installed-target-proof.json"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    pytest_args = [
        "-p",
        "q2_installed_origin_plugin",
        "-o",
        "addopts=",
        "-o",
        f"cache_dir={output / 'pytest-cache'}",
        "--import-mode=importlib",
        "--confcutdir",
        str(product / "tests/unit"),
        "--rootdir",
        str(product),
        "--strict-markers",
        "-q",
        "-ra",
        "-s",
        "--junitxml",
        str(output / "supplemental-junit.xml"),
        "--basetemp",
        str(output / "pytest-tmp"),
        *(f"{test_file}::{selector}" for selector in selectors),
    ]
    result = runner.run_command(
        [str(app_python), "-I", str(bootstrap), *pytest_args],
        cwd=repo,
        env=env,
        log_stem=output / "consumer-suite",
        check=False,
        stream_output=True,
        timeout_seconds=timeout_seconds,
    )
    proof = supplemental_runner.verify_supplemental_run(
        result=result,
        output=output,
        expected_ids=expected_ids,
        purelib=target,
        source_product=product,
        live_product=repo / "policy-engine",
        dependency_site=dependency_site,
        expected_denominator_properties=suite["denominator_properties"],
    )
    target_proof = load_json_bytes(
        _read_regular(output / "installed-target-proof.json", "supplemental target proof"),
        label="supplemental target proof",
    )
    if (
        target_proof.get("purelib") != str(target.resolve(strict=True))
        or target_proof.get("dependency_site") != str(dependency_site.resolve(strict=True))
        or target_proof.get("node_ids") != len(expected_ids)
    ):
        raise SplitProtocolError("supplemental target proof differs from selected profile or IDs")
    return proof


def _execute_consumer_matrix(
    profiles: list[str],
    *,
    run_primary: Callable[[str], dict[str, Any]],
    run_supplemental: Callable[[str], dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Complete every primary profile before admitting any supplemental consumer run."""
    if (
        not profiles
        or any(type(profile) is not str or not profile for profile in profiles)
        or len(profiles) != len(set(profiles))
    ):
        raise SplitProtocolError("consumer matrix profile sequence is malformed")
    primary = {profile: run_primary(profile) for profile in profiles}
    supplemental = {profile: run_supplemental(profile) for profile in profiles}
    return {"primary": primary, "supplemental": supplemental}


def _write_receipt(runner: ModuleType, path: Path, receipt: dict[str, Any]) -> None:
    receipt["updated_utc"] = datetime.now(UTC).isoformat()
    runner.json_write(path, receipt)


def _run(args: argparse.Namespace) -> Path:
    if platform.system() != "Linux":
        raise SplitProtocolError(
            "the installed consumer half is scoped to the supported Linux worker"
        )
    repo = Path(args.repo).resolve(strict=True)
    transfer = Path(args.transfer_root).resolve(strict=True)
    scratch = Path(args.scratch_root).resolve(strict=True)
    scratch_free_at_start = shutil.disk_usage(scratch).free
    output = Path(args.output_root).resolve()
    if transfer.is_symlink() or not transfer.is_dir():
        raise SplitProtocolError("transfer root must be a regular directory")
    if output.exists() or output.is_symlink() or not output.is_relative_to(scratch):
        raise SplitProtocolError("worker output must be a fresh child of its measured scratch root")

    request_path = Path(args.request).resolve(strict=True)
    if request_path.parent != transfer or request_path.name != "split-consumer-request.json":
        raise SplitProtocolError("pinned request must be the source-bound transfer root request")
    request_raw = _read_regular(request_path, "split-consumer request")
    if sha256_bytes(request_raw) != args.request_sha256:
        raise SplitProtocolError("split-consumer request differs from its external handoff pin")
    request = load_json_bytes(request_raw, label="split-consumer request")
    if request.get("schema") != REQUEST_SCHEMA:
        raise SplitProtocolError("unsupported split-consumer request schema")
    source = request.get("source")
    if type(source) is not dict:
        raise SplitProtocolError("split request has no frozen source identity")
    source_sha, source_tree = source.get("commit"), source.get("tree")

    q2_runner_path = repo / Q2_RUNNER_RELATIVE
    runner = _load_module(q2_runner_path, "e02_q2_existing_runner_split_worker")
    runner.frozen_source_preflight(repo, source_sha, source_tree)
    harness = request.get("harness")
    if type(harness) is not dict:
        raise SplitProtocolError("split request has no source-bound harness pins")
    if harness.get("q2_runner_relative") != Q2_RUNNER_RELATIVE:
        raise SplitProtocolError("split request names an unexpected Q2 runner path")
    q2_runner_sha = _hash_pin(q2_runner_path, harness.get("q2_runner_sha256"), "Q2 runner")
    gate_path = repo / Q2_GATE_RELATIVE
    gate_bytes, _gate_module = runner.load_installed_origin_gate()
    gate_sha = sha256_bytes(gate_bytes)
    if gate_sha != harness.get("installed_origin_gate_sha256"):
        raise SplitProtocolError("installed-origin gate differs from the host source-bound pin")
    if gate_path != runner.INSTALLED_ORIGIN_GATE_PATH:
        raise SplitProtocolError("Q2 runner resolves a different installed-origin gate")
    build_profile_path = repo / "policy-engine" / BUILD_PROFILE_RELATIVE
    build_profile_sha = _hash_pin(
        build_profile_path, harness.get("build_profile_sha256"), "Q2 build profile"
    )
    if harness.get("build_profile_relative") != BUILD_PROFILE_RELATIVE:
        raise SplitProtocolError("split request names an unexpected source-bound build profile")

    manifest_path = _child(transfer, "source-freeze-manifest.json", "source-freeze manifest")
    inventory_path = _child(
        transfer, "complete-wheel-source-inventory.json", "complete package inventory"
    )
    manifest_raw = _read_regular(manifest_path, "source-freeze manifest")
    manifest_sha = sha256_bytes(manifest_raw)
    manifest = load_json_bytes(manifest_raw, label="source-freeze manifest")
    if manifest.get("schema_version") != 1:
        raise SplitProtocolError("source-freeze manifest has an unsupported version")
    if (
        manifest.get("candidate_baseline", {}).get("source_sha") != source_sha
        or manifest.get("candidate_baseline", {}).get("source_tree") != source_tree
    ):
        raise SplitProtocolError("source-freeze manifest differs from the worker checkout")
    manifest_hash_request = request.get("manifest_sha256")
    if manifest_sha != manifest_hash_request:
        raise SplitProtocolError("transferred source-freeze manifest differs from host pin")
    inventory_raw = _read_regular(inventory_path, "complete package inventory")
    inventory_sha = sha256_bytes(inventory_raw)
    inventory = load_json_bytes(inventory_raw, label="complete package inventory")
    if inventory_sha != request.get("inventory_sha256"):
        raise SplitProtocolError("transferred package inventory differs from host pin")
    validate_inventory(inventory)

    source_audit_binding = request.get("source_audit")
    if type(source_audit_binding) is not dict:
        raise SplitProtocolError("request omits the exact source-audit selection receipt")
    if (
        source_audit_binding.get("receipt_file") != "source-input-audit.json"
        or source_audit_binding.get("supplemental_manifest_file") != "supplemental-manifest.json"
        or source_audit_binding.get("supplemental_runner_file") != "supplemental_run.py"
    ):
        raise SplitProtocolError("source-audit companion filenames differ from the frozen bundle")
    source_audit_path = _child(
        transfer, source_audit_binding.get("receipt_file"), "source-audit check receipt"
    )
    source_audit_raw = _read_regular(source_audit_path, "source-audit check receipt")
    source_audit_sha = sha256_bytes(source_audit_raw)
    if source_audit_sha != source_audit_binding.get("receipt_sha256"):
        raise SplitProtocolError("transferred source-audit receipt differs from host pin")
    supplemental_path = _child(
        transfer,
        source_audit_binding.get("supplemental_manifest_file"),
        "supplemental source manifest",
    )
    supplemental_raw = _read_regular(supplemental_path, "supplemental source manifest")
    supplemental_sha = sha256_bytes(supplemental_raw)
    if supplemental_sha != source_audit_binding.get("supplemental_manifest_sha256"):
        raise SplitProtocolError("transferred supplemental manifest differs from host pin")
    source_audit = load_json_bytes(source_audit_raw, label="source-audit check receipt")
    source_matrix = validate_source_audit_selection(
        source_audit,
        expected_commit=source_sha,
        expected_tree=source_tree,
        manifest_sha256=manifest_sha,
        supplemental_manifest_sha256=supplemental_sha,
    )
    if source_matrix["profiles"] != list(PROFILE_CHAIN_KEYS):
        raise SplitProtocolError(
            "source audit does not select the complete supported profile chain"
        )
    request_selection = request.get("consumer_selection")
    if type(request_selection) is not dict:
        raise SplitProtocolError("request omits the source-selected consumer matrix")
    for selection_key in (
        "profiles",
        "primary_node_ids",
        "primary_node_ids_sha256",
        "supplemental_node_ids",
        "supplemental_node_ids_sha256",
        "profile_case_count",
    ):
        if request_selection.get(selection_key) != source_matrix[selection_key]:
            raise SplitProtocolError(
                f"worker source-audit matrix differs at consumer_selection.{selection_key}"
            )
    expected_plan = [
        {"phase": phase, "profile": profile}
        for phase in ("primary", "supplemental")
        for profile in source_matrix["profiles"]
    ]
    if request_selection.get("execution_plan") != expected_plan:
        raise SplitProtocolError("request does not bind every profile and consumer phase")
    supplemental_runner_binding = source_audit_binding.get("supplemental_runner_file")
    supplemental_runner_path = _child(
        transfer, supplemental_runner_binding, "supplemental manifest runner"
    )
    supplemental_runner_sha = _hash_pin(
        supplemental_runner_path,
        source_audit_binding.get("supplemental_runner_sha256"),
        "supplemental manifest runner",
    )
    canonical_supplemental_runner = repo / SUPPLEMENTAL_RUNNER_RELATIVE
    canonical_supplemental_bytes = _read_regular(
        canonical_supplemental_runner, "frozen supplemental manifest runner"
    )
    if sha256_bytes(canonical_supplemental_bytes) != supplemental_runner_sha:
        raise SplitProtocolError("transferred supplemental runner differs from frozen source")
    if _read_regular(supplemental_runner_path, "transferred supplemental manifest runner") != (
        canonical_supplemental_bytes
    ):
        raise SplitProtocolError(
            "supplemental runner transfer differs from the frozen source bytes"
        )
    supplemental_runner = _load_module(
        supplemental_runner_path, "e02_q2_supplemental_runner_split_worker"
    )
    supplemental_manifest = load_json_bytes(supplemental_raw, label="supplemental source manifest")
    product_for_supplement = repo / "policy-engine"
    supplemental_ids = supplemental_runner.suite_node_ids(
        product_for_supplement, supplemental_manifest
    )
    if sorted(supplemental_ids) != source_matrix["supplemental_node_ids"]:
        raise SplitProtocolError(
            "worker canonical supplemental selector set differs from source-audit check"
        )

    capacity_binding = request.get("worker_capacity")
    if type(capacity_binding) is not dict:
        raise SplitProtocolError("request omits its measured Linux worker capacity receipt")
    capacity_path = _child(
        transfer, capacity_binding.get("receipt_file"), "worker capacity receipt"
    )
    capacity_raw = _read_regular(capacity_path, "worker capacity receipt")
    if sha256_bytes(capacity_raw) != capacity_binding.get("receipt_sha256"):
        raise SplitProtocolError("transferred worker capacity receipt differs from host pin")
    capacity = load_json_bytes(capacity_raw, label="worker capacity receipt")
    if (
        capacity.get("schema") != "policyos.e02.q2.worker-capacity.v1"
        or capacity.get("source") != source
        or capacity_binding.get("scratch_root") != "/scratch"
        or capacity.get("scratch_root") != capacity_binding.get("scratch_root")
        or capacity.get("free_after_checkout_bytes")
        != capacity_binding.get("free_after_checkout_bytes")
        or capacity.get("thin_fast_forward_pack_bytes")
        != capacity_binding.get("thin_fast_forward_pack_bytes")
        or capacity.get("checkout_growth_bytes") != capacity_binding.get("checkout_growth_bytes")
    ):
        raise SplitProtocolError("capacity receipt measurements differ from the host request")

    artifact_rows = request.get("artifacts")
    if type(artifact_rows) is not list:
        raise SplitProtocolError("request omits the complete profile wheel set")
    wheel_paths: dict[str, Path] = {}
    for artifact in artifact_rows:
        if type(artifact) is not dict or type(artifact.get("profile")) is not str:
            raise SplitProtocolError("source-derived profile artifact row is malformed")
        profile = artifact["profile"]
        if profile in wheel_paths:
            raise SplitProtocolError("source-derived profile wheel is duplicated")
        wheel_paths[profile] = _child_relative(transfer, artifact.get("file"), f"{profile} wheel")
    expected_transfer_files = {
        "split-consumer-request.json",
        "source-freeze-manifest.json",
        "complete-wheel-source-inventory.json",
        "worker-capacity-receipt.json",
        "source-input-audit.json",
        "supplemental-manifest.json",
        "supplemental_run.py",
        "split_protocol.py",
        "split_consumer.py",
        *(artifact["file"] for artifact in artifact_rows),
    }
    _verify_transfer_file_set(transfer, expected_transfer_files)
    transfer_metadata_bytes = sum(
        path.stat().st_size
        for path in (
            request_path,
            manifest_path,
            inventory_path,
            capacity_path,
            source_audit_path,
            supplemental_path,
            _child(transfer, harness.get("protocol_file"), "split protocol"),
            _child(transfer, harness.get("consumer_file"), "split consumer"),
            supplemental_runner_path,
        )
    )
    if transfer_metadata_bytes > MAX_WORKER_METADATA_BYTES:
        raise SplitProtocolError("worker transfer metadata exceeds its measured 4 MiB budget")
    oversized = {
        profile: path.stat().st_size
        for profile, path in wheel_paths.items()
        if path.stat().st_size > MAX_WHEEL_BYTES
    }
    if oversized:
        raise SplitProtocolError(f"profile wheel exceeds the per-artifact limit: {oversized}")
    binding = validate_request_binding(
        request,
        manifest,
        inventory,
        manifest_sha256=manifest_sha,
        inventory_sha256=inventory_sha,
        expected_commit=source_sha,
        expected_tree=source_tree,
        wheel_paths=wheel_paths,
    )
    protocol_path = _child(transfer, harness.get("protocol_file"), "split protocol")
    consumer_path = _child(transfer, harness.get("consumer_file"), "split consumer")
    if protocol_path.name != Path(__file__).name or consumer_path.name != Path(__file__).name:
        raise SplitProtocolError(
            "transferred protocol and consumer must use their frozen filenames"
        )
    protocol_sha = _hash_pin(protocol_path, harness.get("protocol_sha256"), "split protocol")
    consumer_sha = _hash_pin(consumer_path, harness.get("consumer_sha256"), "split consumer")
    if protocol_sha != sha256_file(Path(__file__).with_name("split_protocol.py")):
        raise SplitProtocolError("executing split protocol differs from the host-transfer copy")
    if consumer_sha != sha256_file(Path(__file__)):
        raise SplitProtocolError("executing split consumer differs from the host-transfer copy")

    output.mkdir(parents=True)
    logs = output / "logs"
    logs.mkdir()
    bootstrap = output / "run-installed-pytest.py"
    bootstrap_binding = _write_new_or_same(
        bootstrap, pytest_target_bootstrap_source(), "isolated pytest bootstrap"
    )
    receipt_path = output / "worker-consumer-receipt.json"
    receipt: dict[str, Any] = {
        "schema": "policyos.e02.q2.split-worker-consumer-receipt.v1",
        "status": "running",
        "source": {"commit": source_sha, "tree": source_tree},
        "request": {"path": str(request_path), "sha256": args.request_sha256},
        "harness": {
            "q2_runner_sha256": q2_runner_sha,
            "protocol_sha256": protocol_sha,
            "consumer_sha256": consumer_sha,
            "installed_origin_gate_sha256": gate_sha,
            "build_profile_sha256": build_profile_sha,
        },
        "inputs": {
            "manifest_sha256": manifest_sha,
            "inventory_sha256": inventory_sha,
            "artifacts": binding["artifacts"],
            "source_audit_receipt_sha256": source_audit_sha,
            "supplemental_runner_sha256": supplemental_runner_sha,
            "source_audit_selection": {
                "profiles": source_matrix["profiles"],
                "primary_ids": len(source_matrix["primary_node_ids"]),
                "primary_ids_sha256": source_matrix["primary_node_ids_sha256"],
                "supplemental_ids": len(source_matrix["supplemental_node_ids"]),
                "supplemental_ids_sha256": source_matrix["supplemental_node_ids_sha256"],
                "profile_case_count": source_matrix["profile_case_count"],
                "execution_plan": expected_plan,
            },
        },
        "retention": "all worker command outputs and runtime receipts retained",
        "scratch_free_bytes_at_start": scratch_free_at_start,
        "isolated_pytest_bootstrap": bootstrap_binding,
    }
    _write_receipt(runner, receipt_path, receipt)
    try:
        wheel_receipts: dict[str, dict[str, Any]] = {}
        for profile in source_matrix["profiles"]:
            wheel_path = wheel_paths[profile]
            if not wheel_path.is_file() or wheel_path.is_symlink():
                raise SplitProtocolError(f"{profile} is not a regular transferred wheel")
            wheel_inventory = verify_wheel_inventory(wheel_path, inventory)
            wheel_size_uncompressed = wheel_uncompressed_bytes(wheel_path)
            wheel_receipts[profile] = {
                "path": str(wheel_path),
                "sha256": sha256_file(wheel_path),
                "bytes": wheel_path.stat().st_size,
                "uncompressed_bytes": wheel_size_uncompressed,
                "inventory": wheel_inventory,
            }
        allocation = request["worker_write_budget"]["allocations_bytes"]
        overhead = request.get("installed_target_overhead_bytes")
        if type(overhead) is not dict:
            raise SplitProtocolError("source request omits the installed-target overhead receipt")
        gate_bytes, _ = runner.load_installed_origin_gate()
        plugin_bytes = origin_plugin_source()
        expected_overhead = {
            "origin_gate": len(gate_bytes),
            "origin_plugin": len(plugin_bytes),
            "installer_metadata_reserve": MAX_INSTALLER_METADATA_OVERHEAD_BYTES,
        }
        if overhead != expected_overhead:
            raise SplitProtocolError(
                "origin harness/install metadata reservation differs from source"
            )
        recomputed_budget = worker_write_budget(
            fast_forward_pack_bytes=capacity["thin_fast_forward_pack_bytes"],
            checkout_growth_bytes=capacity["checkout_growth_bytes"],
            wheel_bytes=sum(row["bytes"] for row in wheel_receipts.values()),
            package_target_bytes=sum(row["uncompressed_bytes"] for row in wheel_receipts.values())
            + len(wheel_receipts) * sum(expected_overhead.values()),
            installer_transient_bytes=max(row["bytes"] for row in wheel_receipts.values()),
            logs_and_test_temp_bytes=MAX_WORKER_LOG_AND_TEST_TEMP_BYTES,
            request_and_metadata_bytes=MAX_WORKER_METADATA_BYTES,
        )
        if recomputed_budget != request["worker_write_budget"]:
            raise SplitProtocolError(
                "worker write budget does not reproduce from transferred evidence"
            )
        if (
            allocation["installed_package_target"]
            != recomputed_budget["allocations_bytes"]["installed_package_target"]
        ):
            raise SplitProtocolError("worker target-byte budget differs from all profile installs")
        if allocation["wheel_transfer"] != sum(row["bytes"] for row in wheel_receipts.values()):
            raise SplitProtocolError("worker transfer budget differs from all compressed wheels")

        app_python = runner.require_absolute_file(args.python, "existing product Python")
        worker_python = runner.require_absolute_file(args.dowhy_python, "existing DoWhy Python")
        uv = runner.require_absolute_file(args.uv, "existing uv executable")
        app_info = runner.interpreter_info(app_python, log_dir=logs, name="existing-product-python")
        if app_info["implementation"] != "cpython" or app_info["version"][:2] != [3, 14]:
            raise SplitProtocolError("worker product interpreter must be existing CPython 3.14")
        purelib = Path(app_info["purelib"]).resolve(strict=True)
        dependency_site = (
            Path(args.dependency_site).resolve(strict=True) if args.dependency_site else purelib
        )
        if dependency_site != purelib:
            raise SplitProtocolError(
                "this split profile currently requires one existing dependency site "
                "equal to purelib"
            )
        receipt["runtime_profile"] = {
            "product_python": app_info,
            "dependency_site": str(dependency_site),
            "uv": {"path": str(uv), "sha256": sha256_file(uv)},
        }
        _write_receipt(runner, receipt_path, receipt)

        worker_profile = request.get("worker_profile")
        if type(worker_profile) is not dict:
            raise SplitProtocolError("request omits the selected locked DoWhy profile")
        expected_lock = repo / "policy-engine" / worker_profile["dowhy_lock_relative"]
        lock_sha = _hash_pin(expected_lock, worker_profile["dowhy_lock_sha256"], "DoWhy lock")
        if (
            worker_profile.get("dowhy_python_version") != [3, 12]
            or worker_profile.get("dowhy_distribution_version") != "0.14"
        ):
            raise SplitProtocolError(
                "source-bound worker profile is not the required DoWhy 0.14 profile"
            )
        selected_worker, worker_profile_receipt = runner.run_worker_profile(
            str(uv),
            str(worker_python),
            repo / "policy-engine",
            output,
            runner.clean_child_env(),
            logs,
        )
        worker_import_code = (
            "import hashlib, importlib.metadata, json, pathlib, sys, sysconfig, dowhy\n"
            "purelib = pathlib.Path(sysconfig.get_paths()['purelib']).resolve(strict=True)\n"
            "module = pathlib.Path(dowhy.__file__).resolve(strict=True)\n"
            "pth = []\n"
            "for path in sorted(purelib.glob('*.pth')):\n"
            "    pth.append({'path': str(path.resolve(strict=True)), "
            "'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})\n"
            "print(json.dumps({\n"
            "    'version': importlib.metadata.version('dowhy'),\n"
            "    'module': str(module),\n"
            "    'purelib': str(purelib),\n"
            "    'module_under_purelib': module.is_relative_to(purelib),\n"
            "    'sys_path': sys.path,\n"
            "    'pth_files': pth,\n"
            "}))\n"
        )
        worker_probe = runner.run_command(
            [
                str(selected_worker),
                "-I",
                "-c",
                worker_import_code,
            ],
            cwd=output,
            env=runner.clean_child_env(),
            log_stem=logs / "actual-dowhy-import",
        )
        worker_import = _parse_interpreter_json(worker_probe.stdout, "actual DoWhy import")
        if worker_import.get("version") != worker_profile["dowhy_distribution_version"]:
            raise SplitProtocolError(
                "actual DoWhy import differs from source-bound selected profile"
            )
        if worker_import.get("module_under_purelib") is not True:
            raise SplitProtocolError(
                "DoWhy module origin is outside the selected worker interpreter purelib"
            )
        worker_module_path = Path(worker_import.get("module", "")).resolve(strict=True)
        worker_purelib = Path(worker_import.get("purelib", "")).resolve(strict=True)
        worker_sys_path = [
            Path(value).resolve() for value in worker_import.get("sys_path", []) if value
        ]
        worker_pth_files = worker_import.get("pth_files")
        if type(worker_pth_files) is not list or any(
            type(row) is not dict
            or set(row) != {"path", "sha256"}
            or type(row["path"]) is not str
            or not Path(row["path"]).is_absolute()
            or type(row["sha256"]) is not str
            or len(row["sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in row["sha256"])
            or not Path(row["path"]).resolve().is_relative_to(worker_purelib)
            for row in worker_pth_files
        ):
            raise SplitProtocolError("DoWhy .pth evidence is not a complete purelib receipt")
        if not worker_module_path.is_relative_to(worker_purelib):
            raise SplitProtocolError("DoWhy module path is not contained by selected purelib")
        if worker_module_path.is_relative_to(repo):
            raise SplitProtocolError(
                "DoWhy worker import unexpectedly came from the source checkout"
            )
        if worker_purelib not in worker_sys_path:
            raise SplitProtocolError(
                "DoWhy origin receipt omits its actual interpreter purelib from sys.path"
            )
        if any(path == repo or path.is_relative_to(repo) for path in worker_sys_path):
            raise SplitProtocolError("DoWhy runtime sys.path contains the source checkout")
        if lock_sha != worker_profile_receipt["lock_sha256_after"]:
            raise SplitProtocolError(
                "DoWhy profile lock changed during read-only worker verification"
            )
        receipt["runtime_profile"]["dowhy_profile"] = worker_profile_receipt
        receipt["runtime_profile"]["dowhy_actual_import"] = worker_import

        current_free = shutil.disk_usage(scratch).free
        capacity_check = require_worker_space(
            free_bytes=current_free, budget=request["worker_write_budget"], after_transfer=True
        )
        receipt["worker_capacity_after_transfer"] = {
            **capacity_check,
            "scratch_root": str(scratch),
            "checked_before_install": True,
        }
        _write_receipt(runner, receipt_path, receipt)

        product = repo / "policy-engine"
        owner_inventory = runner.source_resource_inventory(app_python, product, output, logs)
        manifest, assets = runner.read_asset_manifest(product, manifest, owner_inventory)
        actual_inventory = build_source_inventory(
            product, manifest, expected_commit=source_sha, expected_tree=source_tree
        )
        if canonical_json_bytes(actual_inventory) != canonical_json_bytes(inventory):
            raise SplitProtocolError(
                "worker source tree package/resource composition differs from host "
                "complete inventory"
            )
        current_wheel_assets: dict[str, dict[str, Any]] = {}
        for profile, wheel_path in wheel_paths.items():
            current_wheel_assets[profile] = runner.verify_wheel(wheel_path, assets)
            if current_wheel_assets[profile]["sha256"] != wheel_receipts[profile]["sha256"]:
                raise SplitProtocolError(
                    f"Q2 asset reader differs from the host {profile} wheel digest"
                )
        original_ids, current_ids, transitive = _verify_source_selection(
            runner, repo, manifest, request
        )
        if current_ids != set(source_matrix["primary_node_ids"]):
            raise SplitProtocolError(
                "worker primary selector set differs from exact source-audit check"
            )
        receipt["source_recomputed"] = {
            "package_file_count": actual_inventory["package_file_count"],
            "package_bytes": actual_inventory["package_bytes"],
            "force_include_count": actual_inventory["force_include_count"],
            "resource_targets": sorted(row["wheel"] for row in owner_inventory["assets"]),
            "consumer_nodes": len(current_ids),
            "consumer_node_ids_sha256": runner.node_ids_sha256(current_ids),
            "transitive_fixture_bindings": transitive,
            "runtime_owner_inventory": owner_inventory,
            "wheel_inventories": {
                profile: row["inventory"] for profile, row in wheel_receipts.items()
            },
            "supplemental_node_ids": len(supplemental_ids),
            "supplemental_node_ids_sha256": source_matrix["supplemental_node_ids_sha256"],
        }
        _write_receipt(runner, receipt_path, receipt)

        temp_root = output / "installer-tmp"
        temp_root.mkdir()
        target_root = output / "profiles"
        target_root.mkdir()
        install_env = runner.clean_child_env()
        install_env.update(
            {
                "TMPDIR": str(temp_root),
                "PYTHONDONTWRITEBYTECODE": "1",
                "UV_CACHE_DIR": str(output / "uv-no-cache"),
            }
        )
        project = tomllib.loads((product / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        profile_targets: dict[str, Path] = {}
        profile_target_receipts: dict[str, dict[str, Any]] = {}
        profile_target_snapshots: dict[str, dict[str, dict[str, Any]]] = {}
        profile_probe_receipts: dict[str, dict[str, Any]] = {}
        profile_logs: dict[str, Path] = {}

        # One clean target per producer path: source, rebuilt sdist, and rebuilt GCP.
        # The dependency environment is shared read-only; no package is installed there.
        for profile in source_matrix["profiles"]:
            wheel_path = wheel_paths[profile]
            profile_root = target_root / profile
            profile_root.mkdir()
            profile_log = logs / profile
            profile_log.mkdir()
            profile_logs[profile] = profile_log
            installed_target = profile_root / "installed-target"
            installed_target.mkdir()
            profile_targets[profile] = installed_target
            gate_path = installed_target / "q2_installed_origin_gate.py"
            plugin_path = installed_target / "q2_installed_origin_plugin.py"
            _write_new_or_same(gate_path, gate_bytes, "installed-origin gate")
            _write_new_or_same(plugin_path, plugin_bytes, "installed-origin pytest plugin")
            if (
                sha256_file(gate_path) != gate_sha
                or _read_regular(plugin_path, "installed-origin pytest plugin") != plugin_bytes
            ):
                raise SplitProtocolError("installed-origin harness bytes differ from source")
            preinstall_target = _check_preinstall_target(installed_target, inventory)
            install_result = runner.run_command(
                [
                    str(uv),
                    "pip",
                    "install",
                    "--offline",
                    "--no-index",
                    "--no-deps",
                    "--no-cache",
                    "--python",
                    str(app_python),
                    "--target",
                    str(installed_target),
                    str(wheel_path),
                ],
                cwd=output,
                env=install_env,
                log_stem=profile_log / "uv-install-selected-wheel",
                check=False,
                timeout_seconds=180,
            )
            if install_result.returncode:
                raise SplitProtocolError(
                    f"offline no-dependency {profile} installation failed with "
                    f"{install_result.returncode}"
                )
            current_pth_files = [
                {"path": str(path), "sha256": sha256_file(path)}
                for path in sorted(installed_target.glob("*.pth"))
            ]
            current_egg_links = [str(path) for path in sorted(installed_target.glob("*.egg-link"))]
            if current_pth_files != preinstall_target["existing_pth_files"]:
                raise SplitProtocolError(f"{profile} install changed the .pth file set")
            if current_egg_links != preinstall_target["existing_egg_link_files"]:
                raise SplitProtocolError(f"{profile} install changed editable-link files")
            before_snapshot = preinstall_target.pop("_whole_target_before_snapshot")
            installed_inventory = verify_installed_inventory(
                installed_target,
                inventory,
                before_snapshot=before_snapshot,
                wheel_path=wheel_path,
            )
            dist_info = _validate_wheel_metadata_target(
                installed_target,
                wheel_path.name,
                project["name"],
                project["version"],
            )
            actual_target_bytes = _tree_regular_file_bytes(installed_target)
            profile_target_allowance = wheel_receipts[profile]["uncompressed_bytes"] + sum(
                expected_overhead.values()
            )
            if actual_target_bytes > profile_target_allowance:
                raise SplitProtocolError(
                    f"{profile} installed target exceeds its source-derived byte allowance"
                )
            after_install_snapshot = snapshot_installed_tree(installed_target)
            profile_target_snapshots[profile] = after_install_snapshot
            profile_target_receipts[profile] = {
                "path": str(installed_target),
                "wheel": wheel_receipts[profile],
                "inventory": installed_inventory,
                "distribution_metadata": dist_info,
                "before_snapshot_sha256": preinstall_target["whole_target_before_snapshot_sha256"],
                "after_install_snapshot_sha256": sha256_bytes(
                    canonical_json_bytes(after_install_snapshot)
                ),
                "actual_target_bytes": actual_target_bytes,
                "profile_target_allowance_bytes": profile_target_allowance,
                "target_order": "installed target precedes existing dependency site",
            }
            probe_root = profile_root / "installed-consumer-probes"
            probe_root.mkdir()
            resource_probe = _run_installed_resource_helper(
                runner,
                app_python,
                product,
                repo,
                owner_inventory,
                installed_target,
                dependency_site,
                probe_root,
                profile_log,
            )
            poison_probe = _poisoned_neighbor_probe(
                runner,
                app_python,
                installed_target,
                dependency_site,
                product,
                repo,
                owner_inventory,
                probe_root,
                profile_log,
            )
            profile_probe_receipts[profile] = {
                "canonical_runtime_resource_contract": resource_probe,
                "poison_neighbor_and_origin_control": poison_probe,
            }
            receipt["installed_profiles"] = {
                **receipt.get("installed_profiles", {}),
                profile: {
                    "target": profile_target_receipts[profile],
                    "probes": profile_probe_receipts[profile],
                },
            }
            _write_receipt(runner, receipt_path, receipt)

        expected_original_ids = runner.baseline_node_ids(product, manifest)
        if expected_original_ids != original_ids:
            raise SplitProtocolError("original suite denominator changed after selection preflight")
        primary_results: dict[str, dict[str, Any]] = {}
        supplemental_results: dict[str, dict[str, Any]] = {}
        expected_supplemental_ids = set(supplemental_ids)
        if sorted(expected_supplemental_ids) != source_matrix["supplemental_node_ids"]:
            raise SplitProtocolError("supplemental selector IDs changed after source admission")

        def run_primary_for_profile(profile: str) -> dict[str, Any]:
            profile_root = target_root / profile
            primary_output = profile_root / "primary-consumers"
            primary_result = _run_primary_suite(
                runner,
                app_python,
                bootstrap,
                repo,
                product,
                manifest,
                profile_targets[profile],
                dependency_site,
                primary_output,
                timeout_seconds=args.timeout_seconds,
                expected_original_ids=expected_original_ids,
                expected_current_ids=current_ids,
            )
            if (
                snapshot_installed_tree(profile_targets[profile])
                != profile_target_snapshots[profile]
            ):
                raise SplitProtocolError(
                    f"{profile} primary consumers mutated the installed package target"
                )
            primary_results[profile] = primary_result
            receipt["consumer_matrix"] = {
                "status": "primary_profiles_complete"
                if len(primary_results) == len(source_matrix["profiles"])
                else "running",
                "primary": dict(primary_results),
                "supplemental": {},
            }
            _write_receipt(runner, receipt_path, receipt)
            return primary_result

        def run_supplemental_for_profile(profile: str) -> dict[str, Any]:
            profile_root = target_root / profile
            supplemental_output = profile_root / "supplemental-consumers"
            supplemental_result = _run_supplemental_suite(
                runner,
                supplemental_runner,
                app_python,
                bootstrap,
                repo,
                product,
                supplemental_manifest,
                profile_targets[profile],
                dependency_site,
                supplemental_output,
                timeout_seconds=args.timeout_seconds,
                expected_ids=expected_supplemental_ids,
            )
            if (
                snapshot_installed_tree(profile_targets[profile])
                != profile_target_snapshots[profile]
            ):
                raise SplitProtocolError(
                    f"{profile} supplemental consumers mutated the installed package target"
                )
            supplemental_results[profile] = supplemental_result
            receipt["consumer_matrix"] = {
                "status": "complete"
                if len(supplemental_results) == len(source_matrix["profiles"])
                else "running",
                "primary": dict(primary_results),
                "supplemental": dict(supplemental_results),
            }
            _write_receipt(runner, receipt_path, receipt)
            return supplemental_result

        # A failure in any primary callback aborts this generic runner before its
        # supplemental callbacks begin; each callback is the real installed consumer.
        consumer_matrix = _execute_consumer_matrix(
            source_matrix["profiles"],
            run_primary=run_primary_for_profile,
            run_supplemental=run_supplemental_for_profile,
        )
        if (
            consumer_matrix["primary"] != primary_results
            or consumer_matrix["supplemental"] != supplemental_results
        ):
            raise SplitProtocolError("consumer matrix callback receipts did not reconcile")

        target_bytes_by_profile = {
            profile: _tree_regular_file_bytes(path) for profile, path in profile_targets.items()
        }
        if any(
            target_bytes_by_profile[profile]
            != profile_target_receipts[profile]["actual_target_bytes"]
            for profile in source_matrix["profiles"]
        ):
            raise SplitProtocolError("installed target bytes changed after consumer replays")
        installed_target_total = sum(target_bytes_by_profile.values())
        if installed_target_total > allocation["installed_package_target"]:
            raise SplitProtocolError(
                "actual three-profile installed targets exceed the source-derived allocation"
            )
        output_bytes = _output_tree_bytes(output, excluded_roots=set(profile_targets.values()))
        if output_bytes > allocation["logs_and_test_temp"]:
            raise SplitProtocolError(
                "retained worker logs, receipts, installer temporary, and consumer outputs exceed "
                "their measured allocation"
            )
        installer_temp_bytes = _output_tree_bytes(temp_root)
        scratch_free_final = shutil.disk_usage(scratch).free
        if scratch_free_final < request["worker_write_budget"]["mandatory_free_reserve_bytes"]:
            raise SplitProtocolError("worker scratch no longer retains the required 4 GiB reserve")
        receipt["installed_consumers"] = {
            "profiles": {
                profile: {
                    "target": profile_target_receipts[profile],
                    "probes": profile_probe_receipts[profile],
                    "primary": primary_results[profile],
                    "supplemental": supplemental_results[profile],
                }
                for profile in source_matrix["profiles"]
            },
            "execution_order": expected_plan,
            "primary_node_ids": len(current_ids),
            "primary_node_ids_sha256": source_matrix["primary_node_ids_sha256"],
            "supplemental_node_ids": len(expected_supplemental_ids),
            "supplemental_node_ids_sha256": source_matrix["supplemental_node_ids_sha256"],
            "complete_profile_case_count": source_matrix["profile_case_count"],
        }
        receipt["worker_actual_write_accounting"] = {
            "non_target_output_bytes": output_bytes,
            "installed_target_bytes_by_profile": target_bytes_by_profile,
            "installed_target_bytes_total": installed_target_total,
            "installer_temp_bytes_remaining": installer_temp_bytes,
            "scratch_free_bytes_at_start": scratch_free_at_start,
            "scratch_free_bytes_at_end": scratch_free_final,
            "free_delta_bytes": scratch_free_at_start - scratch_free_final,
            "free_delta_attribution": (
                "includes concurrent worker activity; retained non-target outputs and each "
                "installed target are separately measured"
            ),
        }
        receipt["status"] = "completed"
        receipt["classification"] = "source_bound_three_profile_installed_consumer_matrix"
        deciding_paths = [str(receipt_path)]
        for profile in source_matrix["profiles"]:
            profile_root = target_root / profile
            deciding_paths.extend(
                str(profile_root / "primary-consumers" / name)
                for name in (
                    "consumer-suite.stdout.txt",
                    "consumer-suite.stderr.txt",
                    "collected-nodeids.json",
                    "origin-proof.json",
                    "installed-target-proof.json",
                    "wave-junit.xml",
                )
            )
            deciding_paths.extend(
                str(profile_root / "supplemental-consumers" / name)
                for name in (
                    "consumer-suite.stdout.txt",
                    "consumer-suite.stderr.txt",
                    "collected-nodeids.json",
                    "origin-proof.json",
                    "installed-target-proof.json",
                    "supplemental-junit.xml",
                )
            )
            deciding_paths.extend(
                str(logs / profile / f"{name}.{stream}.txt")
                for name in (
                    "uv-install-selected-wheel",
                    "canonical-installed-resource-contract",
                    "installed-reader-poison-control",
                )
                for stream in ("stdout", "stderr")
            )
        receipt["deciding_output_paths"] = deciding_paths
        _write_receipt(runner, receipt_path, receipt)
        return receipt_path
    except BaseException as error:
        receipt["status"] = "failed"
        receipt["failure"] = f"{type(error).__name__}: {error}"
        _write_receipt(runner, receipt_path, receipt)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--transfer-root", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument(
        "--python", required=True, help="existing CPython 3.14 dependencies profile"
    )
    parser.add_argument("--dependency-site", help="defaults to the selected Python purelib")
    parser.add_argument(
        "--dowhy-python", required=True, help="existing locked CPython 3.12 profile"
    )
    parser.add_argument("--uv", required=True, help="existing absolute uv executable")
    parser.add_argument("--scratch-root", default="/scratch")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments and arguments[0] == "--run-profile-partition":
        return _run_profile_partition_cli(arguments[1:])
    try:
        parsed = parse_args(arguments)
        _load_pinned_protocol(parsed)
        receipt = _run(parsed)
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        sys.stderr.write(f"Q2 split worker consumer failed: {type(error).__name__}: {error}\n")
        return 1
    sys.stdout.write(f"Q2 split worker consumer completed: {receipt}\n")
    return 0


def _run_profile_partition_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="run one source-bound Linux Q2 profile partition")
    parser.add_argument("--request-stdin", action="store_true", required=True)
    parser.add_argument("--request-sha256", required=True)
    try:
        args = parser.parse_args(argv)
        request_raw = sys.stdin.buffer.read(16 * 1024 * 1024 + 1)
        if len(request_raw) > 16 * 1024 * 1024:
            raise ValueError("profile partition stdin exceeds the 16 MiB request limit")
        if _raw_sha256(request_raw) != args.request_sha256:
            raise ValueError("profile partition request differs from its external SHA-256")
        request = _preflight_json(request_raw, "profile partition request")
        worker_roots = request.get("worker_roots")
        harness = request.get("harness")
        if (
            request.get("request_transport") != "stdin_sha256"
            or type(worker_roots) is not dict
            or type(harness) is not dict
        ):
            raise ValueError("profile partition request omits its roots or harness pins")
        input_root = Path(worker_roots.get("inputs", ""))
        if not input_root.is_absolute() or ".." in input_root.parts:
            raise ValueError("profile partition input mount root is not canonical")
        consumer_path = Path(os.path.abspath(__file__))
        runner_path = consumer_path.with_name("profile_partition_runner.py")
        mounts_path = consumer_path.with_name("worker_mounts.py")
        expected_current = {
            "split_consumer_sha256": _raw_sha256(
                _preflight_regular_bytes(consumer_path, "split consumer")
            ),
            "partition_runner_sha256": _raw_sha256(
                _preflight_regular_bytes(runner_path, "partition runner")
            ),
            "worker_mounts_sha256": _raw_sha256(
                _preflight_regular_bytes(mounts_path, "worker mounts")
            ),
        }
        if any(harness.get(key) != value for key, value in expected_current.items()):
            raise ValueError("profile partition harness bytes differ from the source-bound request")
        gate_relative = request.get("origin_gate_relative_path")
        if (
            type(gate_relative) is not str
            or Path(gate_relative).is_absolute()
            or ".." in Path(gate_relative).parts
        ):
            raise ValueError("installed-origin gate path is not a canonical input-relative file")
        gate_path = input_root / gate_relative
        gate_bytes = _preflight_regular_bytes(gate_path, "installed-origin gate")
        if _raw_sha256(gate_bytes) != request.get("origin_gate_sha256"):
            raise ValueError("installed-origin gate differs from the source-bound input pin")
        mounts_spec = importlib.util.spec_from_file_location("worker_mounts", mounts_path)
        if mounts_spec is None or mounts_spec.loader is None:
            raise ValueError("cannot load the frozen worker mount verifier")
        mounts_module = importlib.util.module_from_spec(mounts_spec)
        sys.modules["worker_mounts"] = mounts_module
        mounts_spec.loader.exec_module(mounts_module)
        spec = importlib.util.spec_from_file_location(
            "e02_q2_profile_partition_runner", runner_path
        )
        if spec is None or spec.loader is None:
            raise ValueError("cannot load the frozen worker profile partition runner")
        runner = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = runner
        spec.loader.exec_module(runner)
        result = runner.run_worker_profile_partition(
            request_raw,
            args.request_sha256,
            origin_gate_bytes=gate_bytes,
            origin_plugin_bytes=origin_plugin_source(),
            bootstrap_bytes=pytest_target_bootstrap_source(),
        )
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        sys.stderr.write(f"Q2 profile partition failed: {type(error).__name__}: {error}\n")
        return 1
    sys.stdout.write(f"Q2 profile partition completed: {result}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

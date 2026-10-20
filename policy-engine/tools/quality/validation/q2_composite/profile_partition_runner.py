"""Prepare and execute one source-bound Linux profile partition without a checkout.

The host prepares exact read-only input/artifact trees and a writable isolated
prefix/receipt pair. The worker verifies those mounted bytes, creates a normal
wheel-derived venv entry point from the selected artifact, and runs the one
source-selected Linux-only pytest node from a small transferred test closure.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import worker_mounts as mounts
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

REQUEST_SCHEMA = "policyos.e02.q2.worker-profile-partition-request.v1"
RESULT_SCHEMA = "policyos.e02.q2.profile-partition-execution.v1"
LA029_NODE_ID = (
    "tests/unit/data_forge/domains/ukraine/test_installed_wheel_no_checkout.py::"
    "test_installed_wheel_without_checkout_reports_gate_unavailable"
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
# The runtime contract validates this as an isolated, private tmpfs on a read-only rootfs.
_WORKER_PRIVATE_TMPFS_ROOT = "/tmp"  # noqa: S108
_PROFILES = ("source-wheel", "rebuilt-sdist-wheel", "rebuilt-gcp-archive-wheel")
MIN_HOST_FREE_BYTES = 4 * 1024 * 1024 * 1024


class ProfilePartitionError(ValueError):
    """A profile partition does not match its source, artifact, or runtime pins."""


def _host_file_bytes(path: str | Path, label: str) -> bytes:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current = current / component
        try:
            info = current.lstat()
        except OSError as error:
            raise ProfilePartitionError(f"{label} path cannot be inspected") from error
        if stat.S_ISLNK(info.st_mode):
            raise ProfilePartitionError(f"{label} traverses a symlink")
    if not stat.S_ISREG(absolute.lstat().st_mode):
        raise ProfilePartitionError(f"{label} must be a regular file")
    return absolute.read_bytes()


def _copy_new(root: Path, relative: str, raw: bytes, label: str) -> dict[str, Any]:
    parsed = _relative_file(relative, f"{label} destination")
    destination = root.joinpath(*parsed.parts)
    current = root
    for component in parsed.parts[:-1]:
        current = current / component
        try:
            info = current.lstat()
        except FileNotFoundError:
            current.mkdir(mode=0o700)
            info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ProfilePartitionError(f"{label} destination traverses a non-directory")
    descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    readback = _regular_bytes(destination, label)
    if readback != raw:
        raise ProfilePartitionError(f"{label} changed during its exclusive copy")
    return {"path": parsed.as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _write_or_match(root: Path, relative: str, raw: bytes, label: str) -> dict[str, Any]:
    parsed = _relative_file(relative, f"{label} path")
    destination = root.joinpath(*parsed.parts)
    if destination.exists() or destination.is_symlink():
        observed = _regular_bytes(destination, label)
        if observed != raw:
            raise ProfilePartitionError(f"existing {label} differs from this profile's source pin")
        return {
            "path": parsed.as_posix(),
            "bytes": len(observed),
            "sha256": hashlib.sha256(observed).hexdigest(),
        }
    return _copy_new(root, parsed.as_posix(), raw, label)


def _ensure_directory_beneath(root: Path, relative: PurePosixPath, label: str) -> Path:
    """Create a mapped receipt directory while rejecting every symlink hop."""
    if root.is_symlink() or not root.is_dir():
        raise ProfilePartitionError(f"{label} mount root must be a real directory")
    current = root
    for component in relative.parts:
        if component in {"", ".", ".."}:
            raise ProfilePartitionError(f"{label} path contains an unsafe component")
        current = current / component
        try:
            info = current.lstat()
        except FileNotFoundError:
            current.mkdir(mode=0o700)
            info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ProfilePartitionError(f"{label} path traverses a non-directory")
    return current


def prepare_worker_profile_mounts(
    plan: dict[str, Any],
    *,
    profile: str,
    source_root: str | Path,
    mount_map: dict[str, Any],
    runtime_contract: dict[str, Any],
    split_consumer_path: str | Path,
    partition_runner_path: str | Path,
    worker_mounts_path: str | Path,
    origin_gate_path: str | Path,
) -> dict[str, Any]:
    """Materialize only frozen LA-029 inputs, three wheels, and harness files.

    This is a host-side preparation step. It never mounts or copies the source
    checkout; only the source-derived three-file test closure and named
    provenance helpers are transferred.
    """
    if (
        type(plan) is not dict
        or plan.get("schema") != "policyos.e02.q2.profile-composite-primary.v1"
    ):
        raise ProfilePartitionError("worker input preparation requires a selected composite plan")
    plan_copy = dict(plan)
    supplied_plan_digest = plan_copy.pop("plan_sha256", None)
    plan_digest = hashlib.sha256(_canonical_json(plan_copy)).hexdigest()
    if supplied_plan_digest != plan_digest:
        raise ProfilePartitionError("worker input preparation received a stale composite plan")
    if profile not in _PROFILES or type(profile) is not str:
        raise ProfilePartitionError("worker input preparation selected an unsupported profile")
    run = next(
        (
            row
            for row in plan.get("run_plan", [])
            if row.get("profile") == profile and row.get("executor") == "linux-worker"
        ),
        None,
    )
    if type(run) is not dict or run.get("node_ids") != [LA029_NODE_ID]:
        raise ProfilePartitionError(
            "worker input preparation differs from the actual LA-029 assignment"
        )
    root = Path(source_root).resolve(strict=True)
    if str(root) != plan.get("source_checkout", {}).get("path"):
        raise ProfilePartitionError(
            "worker input preparation source root differs from the frozen plan"
        )
    inputs_mount = next(row for row in mount_map["mounts"] if row["role"] == "inputs")
    artifacts_mount = next(row for row in mount_map["mounts"] if row["role"] == "artifacts")
    input_root = Path(inputs_mount["host_root"]).resolve(strict=True)
    artifact_root = Path(artifacts_mount["host_root"]).resolve(strict=True)
    if input_root != Path(inputs_mount["host_root"]) or artifact_root != Path(
        artifacts_mount["host_root"]
    ):
        raise ProfilePartitionError("worker input/artifact roots must be canonical host paths")
    for directory, label in ((input_root, "input"), (artifact_root, "artifact")):
        if directory.is_symlink() or not directory.is_dir():
            raise ProfilePartitionError(f"worker {label} root must be a real directory")
    available = os.statvfs(input_root).f_bavail * os.statvfs(input_root).f_frsize
    if available < MIN_HOST_FREE_BYTES:
        raise ProfilePartitionError("worker profile preparation requires the 4 GiB host reserve")
    mounts.validate_mount_map(
        mount_map,
        expected_source=plan["source"],
        expected_plan_sha256=plan_digest,
        expected_profile=profile,
        expected_artifact_sha256=run["artifact_sha256"],
        expected_node_ids_sha256=run["node_ids_sha256"],
        expected_runtime_contract_sha256=hashlib.sha256(
            _canonical_json(mounts.validate_runtime_contract(runtime_contract))
        ).hexdigest(),
    )
    input_rows: list[dict[str, Any]] = []
    worker_files = plan.get("source_inputs", {}).get("worker_test_input_files")
    if type(worker_files) is not list or hashlib.sha256(
        _canonical_json(worker_files)
    ).hexdigest() != plan["source_inputs"].get("worker_test_input_files_sha256"):
        raise ProfilePartitionError("worker test-source closure is absent or stale")
    for row in worker_files:
        relative = _relative_file(row.get("path"), "worker test-source path")
        source_path = root / "policy-engine" / Path(*relative.parts)
        raw = _host_file_bytes(source_path, "frozen worker test-source file")
        if len(raw) != row.get("bytes") or hashlib.sha256(raw).hexdigest() != row.get("sha256"):
            raise ProfilePartitionError("worker test-source file differs from the composite plan")
        copied = _write_or_match(
            input_root,
            f"test-source/{relative.as_posix()}",
            raw,
            "worker test-source copy",
        )
        input_rows.append(copied)
    harness_sources = (
        ("split_consumer.py", split_consumer_path),
        ("profile_partition_runner.py", partition_runner_path),
        ("worker_mounts.py", worker_mounts_path),
        ("q2_installed_origin_gate.py", origin_gate_path),
    )
    harness: dict[str, Any] = {}
    for target, source in harness_sources:
        raw = _host_file_bytes(source, f"worker {target}")
        copied = _write_or_match(input_root, target, raw, f"worker {target}")
        input_rows.append(copied)
        if target == "split_consumer.py":
            harness.update(
                {"split_consumer_relative_path": target, "split_consumer_sha256": copied["sha256"]}
            )
        elif target == "profile_partition_runner.py":
            harness.update(
                {
                    "partition_runner_relative_path": target,
                    "partition_runner_sha256": copied["sha256"],
                }
            )
        elif target == "worker_mounts.py":
            harness.update(
                {"worker_mounts_relative_path": target, "worker_mounts_sha256": copied["sha256"]}
            )
        else:
            harness["origin_gate_sha256"] = copied["sha256"]
    owner_path = Path(plan["owner_inventory"]["path"])
    owner_raw = _host_file_bytes(owner_path, "frozen resource owner inventory")
    if hashlib.sha256(owner_raw).hexdigest() != plan["owner_inventory"]["sha256"]:
        raise ProfilePartitionError("resource owner inventory differs from the composite plan")
    owner_copy = _write_or_match(
        input_root, "resource-owner-inventory.json", owner_raw, "resource owner inventory"
    )
    input_rows.append(owner_copy)
    artifact_rows: list[dict[str, Any]] = []
    for artifact in plan["artifacts"]:
        wheel_raw = _host_file_bytes(artifact["path"], f"{artifact['profile']} wheel")
        if (
            len(wheel_raw) != artifact["bytes"]
            or hashlib.sha256(wheel_raw).hexdigest() != artifact["sha256"]
        ):
            raise ProfilePartitionError("wheel artifact differs from its source producer receipt")
        basename = Path(artifact["path"]).name
        relative = f"wheels/{artifact['profile']}/{basename}"
        copied = _write_or_match(
            artifact_root, relative, wheel_raw, f"{artifact['profile']} wheel transfer"
        )
        artifact_rows.append(
            {**copied, "profile": artifact["profile"], "chain_key": artifact["chain_key"]}
        )
    input_rows.sort(key=lambda row: row["path"])
    artifact_rows.sort(key=lambda row: row["path"])
    if (
        hashlib.sha256(_canonical_json(worker_files)).hexdigest()
        != plan["source_inputs"]["worker_test_input_files_sha256"]
    ):
        raise ProfilePartitionError("worker test-source closure changed during preparation")
    if mounts.verify_mapped_tree(mount_map, role="inputs", expected_files=input_rows)[
        "member_count"
    ] != len(input_rows):
        raise ProfilePartitionError("prepared input tree contains unselected or stale members")
    artifact_member_rows = [
        {key: row[key] for key in ("path", "bytes", "sha256")} for row in artifact_rows
    ]
    if mounts.verify_mapped_tree(mount_map, role="artifacts", expected_files=artifact_member_rows)[
        "member_count"
    ] != len(artifact_member_rows):
        raise ProfilePartitionError("prepared artifact tree contains unselected or stale members")
    return {
        "schema": "policyos.e02.q2.worker-profile-mount-preparation.v1",
        "source": dict(plan["source"]),
        "preparation_profile": profile,
        "plan_sha256": plan_digest,
        "input_root": str(input_root),
        "artifact_root": str(artifact_root),
        "mount_map": mount_map,
        "mount_map_sha256": hashlib.sha256(_canonical_json(mount_map)).hexdigest(),
        "input_members": input_rows,
        "artifact_members": artifact_rows,
        "harness": harness,
        "origin_gate_relative_path": "q2_installed_origin_gate.py",
        "resource_owner_inventory": {
            "path": "resource-owner-inventory.json",
            "sha256": owner_copy["sha256"],
        },
        "worker_files": worker_files,
        "artifact_chain": plan["artifact_chain"],
        "artifacts": plan["artifacts"],
        "owner_resources": plan["owner_resources"],
    }


def finalize_worker_profile_request(
    plan: dict[str, Any],
    prepared: dict[str, Any],
    *,
    profile: str,
    runtime_contract: dict[str, Any],
    container_inspect_receipt: dict[str, Any],
    expected_container_id: str,
    mount_map: dict[str, Any] | None = None,
    request_relative_path: str,
    receipt_relative_path: str,
    entrypoint_name: str,
) -> dict[str, Any]:
    """Bind actual container inspection and the selected generated entrypoint."""
    if profile not in _PROFILES or prepared.get("source") != plan.get("source"):
        raise ProfilePartitionError(
            "worker request preparation is detached from its composite plan"
        )
    mount_map = prepared.get("mount_map") if mount_map is None else mount_map
    runtime = mounts.validate_runtime_contract(runtime_contract)
    runtime_sha = hashlib.sha256(_canonical_json(runtime)).hexdigest()
    run = next(
        (
            row
            for row in plan.get("run_plan", [])
            if row.get("profile") == profile and row.get("executor") == "linux-worker"
        ),
        None,
    )
    if type(run) is not dict:
        raise ProfilePartitionError("selected profile is absent from the worker run plan")
    mounts.validate_mount_map(
        mount_map,
        expected_source=plan["source"],
        expected_plan_sha256=prepared["plan_sha256"],
        expected_profile=profile,
        expected_artifact_sha256=run["artifact_sha256"],
        expected_node_ids_sha256=run["node_ids_sha256"],
        expected_runtime_contract_sha256=runtime_sha,
    )
    map_sha = hashlib.sha256(_canonical_json(mount_map)).hexdigest()
    for role, root_key in (("inputs", "input_root"), ("artifacts", "artifact_root")):
        mapped_root = next(row["host_root"] for row in mount_map["mounts"] if row["role"] == role)
        if Path(mapped_root) != Path(prepared[root_key]):
            raise ProfilePartitionError(
                "profile-specific mount map changed a shared input/artifact root"
            )
    container_identity = mounts.validate_worker_container_inspect_receipt(
        container_inspect_receipt,
        runtime,
        mount_map,
        expected_container_id=expected_container_id,
    )
    input_root = Path(prepared["input_root"])
    inspect_raw = _canonical_json(container_inspect_receipt) + b"\n"
    inspect_copy = _write_or_match(
        input_root,
        "worker-container-inspect.json",
        inspect_raw,
        "field-limited worker container inspection",
    )
    input_members = [*prepared["input_members"], inspect_copy]
    input_members.sort(key=lambda row: row["path"])
    artifact_members = [
        {key: row[key] for key in ("path", "bytes", "sha256")}
        for row in prepared["artifact_members"]
    ]
    input_mount = next(row for row in mount_map["mounts"] if row["role"] == "inputs")
    artifact_mount = next(row for row in mount_map["mounts"] if row["role"] == "artifacts")
    node_digest = run["node_ids_sha256"]
    selected_artifact = next(row for row in plan["artifacts"] if row["profile"] == profile)
    selected_copy = next(row for row in prepared["artifact_members"] if row["profile"] == profile)
    install_plan = mounts.plan_installed_entrypoint(
        runtime,
        mount_map,
        expected_source=plan["source"],
        plan_sha256=prepared["plan_sha256"],
        profile=profile,
        artifact_sha256=selected_artifact["sha256"],
        node_ids_sha256=node_digest,
        wheel_relative_path=selected_copy["path"],
        entrypoint_name=entrypoint_name,
    )
    consumer_path = input_root / prepared["harness"]["split_consumer_relative_path"]
    spec = importlib.util.spec_from_file_location("e02_q2_consumer_helpers", consumer_path)
    if spec is None or spec.loader is None:
        raise ProfilePartitionError("cannot load the frozen source-bound consumer helper")
    consumer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = consumer
    spec.loader.exec_module(consumer)
    harness = {
        key: value for key, value in prepared["harness"].items() if key != "origin_gate_sha256"
    }
    harness["origin_plugin_sha256"] = hashlib.sha256(consumer.origin_plugin_source()).hexdigest()
    harness["pytest_bootstrap_sha256"] = hashlib.sha256(
        consumer.pytest_target_bootstrap_source()
    ).hexdigest()
    request_label = _relative_file(request_relative_path, "worker request label").as_posix()
    if request_label != f"requests/{profile}.json":
        raise ProfilePartitionError("worker request label must be profile-specific")
    receipt_relative = _relative_file(receipt_relative_path, "worker result path").as_posix()
    request = {
        "schema": REQUEST_SCHEMA,
        "source": dict(plan["source"]),
        "profile": profile,
        "artifact_sha256": selected_artifact["sha256"],
        "node_ids": run["node_ids"],
        "node_ids_sha256": node_digest,
        "composite_plan": plan,
        "plan_sha256": prepared["plan_sha256"],
        "runtime_contract": runtime,
        "runtime_contract_sha256": runtime_sha,
        "mount_map": mount_map,
        "mount_map_sha256": map_sha,
        "worker_roots": {
            "inputs": input_mount["worker_root"],
            "artifacts": artifact_mount["worker_root"],
        },
        "input_members": input_members,
        "artifact_members": artifact_members,
        "request_transport": "stdin_sha256",
        "receipt_relative_path": receipt_relative,
        "container_identity": container_identity,
        "container_inspect_ref": {
            "path": "worker-container-inspect.json",
            "sha256": inspect_copy["sha256"],
        },
        "resource_owner_inventory": prepared["resource_owner_inventory"],
        "origin_gate_relative_path": prepared["origin_gate_relative_path"],
        "origin_gate_sha256": prepared["harness"]["origin_gate_sha256"],
        "harness": harness,
        "entrypoint_install_plan": install_plan,
        "entrypoint_install_plan_sha256": hashlib.sha256(_canonical_json(install_plan)).hexdigest(),
    }
    request_raw = _canonical_json(request) + b"\n"
    request_sha = hashlib.sha256(request_raw).hexdigest()
    request_ref = {
        "transport": "stdin_sha256",
        "sha256": request_sha,
        "bytes": len(request_raw),
    }
    if mounts.verify_mapped_tree(mount_map, role="inputs", expected_files=input_members)[
        "member_count"
    ] != len(input_members):
        raise ProfilePartitionError(
            "worker input mount did not read back its complete immutable member set"
        )
    if mounts.verify_mapped_tree(mount_map, role="artifacts", expected_files=artifact_members)[
        "member_count"
    ] != len(artifact_members):
        raise ProfilePartitionError(
            "worker artifact mount did not read back the complete profile set"
        )
    return {
        "request": request,
        "request_ref": request_ref,
        "request_bytes": request_raw,
        "request_sha256": request_sha,
        "container_identity": container_identity,
        "input_members": input_members,
        "artifact_members": artifact_members,
        "entrypoint_install_plan": install_plan,
        "worker_argv": worker_profile_exec_argv(
            runtime,
            container_id=container_identity["container_id"],
            request_sha256=request_sha,
            input_worker_root=input_mount["worker_root"],
        ),
        "expected_output_host_path": str(
            Path(next(row["host_root"] for row in mount_map["mounts"] if row["role"] == "receipts"))
            / Path(*PurePosixPath(receipt_relative).parts)
        ),
    }


def worker_profile_exec_argv(
    runtime_contract: dict[str, Any],
    *,
    container_id: str,
    request_sha256: str,
    input_worker_root: str,
    consumer_relative_path: str = "split_consumer.py",
) -> list[str]:
    """Build the source-pinned worker command without executing Docker."""
    runtime = mounts.validate_runtime_contract(runtime_contract)
    _sha(request_sha256, "worker request SHA-256")
    if type(container_id) is not str or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
        raise ProfilePartitionError(
            "worker execution target must be the measured full container ID"
        )
    input_root = _relative_file(input_worker_root.lstrip("/"), "worker input root")
    if PurePosixPath(input_worker_root).as_posix() != "/" + input_root.as_posix():
        raise ProfilePartitionError("worker input root must be absolute and canonical")
    consumer_relative = _relative_file(consumer_relative_path, "worker consumer path")
    consumer = PurePosixPath(input_worker_root, *consumer_relative.parts).as_posix()
    return [
        "docker",
        "--config",
        runtime["docker"]["config_path"],
        "--context",
        runtime["docker"]["context"],
        "exec",
        "-i",
        container_id,
        runtime["worker"]["python_executable"],
        "-I",
        consumer,
        "--run-profile-partition",
        "--request-stdin",
        "--request-sha256",
        request_sha256,
    ]


def launch_worker_profile_partition(
    prepared_request: dict[str, Any],
    *,
    timeout_seconds: int = 600,
) -> Path:
    """Send one frozen request to the existing worker and retain its command.

    The function is the host-side consumer bridge. It accepts a request that
    has already been bound to the measured container and four exact mount
    prefixes, sends the request bytes only through stdin, and returns the
    worker-written result path after checking its request/source/artifact
    binding. Docker operations are deliberately limited to ``exec`` here.
    """
    expected_bundle_fields = {
        "request",
        "request_ref",
        "request_bytes",
        "request_sha256",
        "container_identity",
        "input_members",
        "artifact_members",
        "entrypoint_install_plan",
        "worker_argv",
        "expected_output_host_path",
    }
    if type(prepared_request) is not dict or set(prepared_request) != expected_bundle_fields:
        raise ProfilePartitionError("worker launch bundle has missing or unrecognized fields")
    request = prepared_request["request"]
    request_raw = prepared_request["request_bytes"]
    request_sha = _sha(prepared_request["request_sha256"], "worker launch request SHA-256")
    if (
        type(request) is not dict
        or type(request_raw) is not bytes
        or len(request_raw) > 16 * 1024 * 1024
        or hashlib.sha256(request_raw).hexdigest() != request_sha
        or request_raw != _canonical_json(request) + b"\n"
        or request.get("request_transport") != "stdin_sha256"
    ):
        raise ProfilePartitionError("worker launch request bytes or stdin transport differ")
    if type(timeout_seconds) is not int or timeout_seconds <= 0:
        raise ProfilePartitionError("worker launch timeout must be a positive integer")
    runtime = mounts.validate_runtime_contract(request.get("runtime_contract"))
    inspect_ref = request.get("container_inspect_ref")
    if type(inspect_ref) is not dict or set(inspect_ref) != {"path", "sha256"}:
        raise ProfilePartitionError("worker launch request omits its field-limited inspection")
    inspect_relative = _relative_file(
        inspect_ref.get("path"), "field-limited worker inspection path"
    )
    if inspect_relative.as_posix() != "worker-container-inspect.json":
        raise ProfilePartitionError("worker launch inspection path is not the fixed input member")
    input_root_host = Path(
        next(row["host_root"] for row in request["mount_map"]["mounts"] if row["role"] == "inputs")
    )
    inspect_raw = _regular_bytes(
        input_root_host / Path(*inspect_relative.parts), "field-limited worker inspection"
    )
    if hashlib.sha256(inspect_raw).hexdigest() != inspect_ref.get("sha256"):
        raise ProfilePartitionError(
            "worker launch inspection bytes differ from their pinned digest"
        )
    identity = mounts.validate_worker_container_inspect_receipt(
        _strict_object(inspect_raw, "field-limited worker inspection"),
        runtime,
        request["mount_map"],
        expected_container_id=request["container_identity"]["container_id"],
    )
    if identity != prepared_request["container_identity"]:
        raise ProfilePartitionError("worker launch identity differs from inspected container")
    plan = request.get("composite_plan")
    if type(plan) is not dict:
        raise ProfilePartitionError("worker launch request omits the composite plan")
    unsigned_plan = dict(plan)
    plan_sha = unsigned_plan.pop("plan_sha256", None)
    if hashlib.sha256(_canonical_json(unsigned_plan)).hexdigest() != plan_sha:
        raise ProfilePartitionError("worker launch composite plan digest is stale")
    run = next(
        (
            row
            for row in plan.get("run_plan", [])
            if row.get("profile") == request.get("profile")
            and row.get("executor") == "linux-worker"
        ),
        None,
    )
    if type(run) is not dict:
        raise ProfilePartitionError("worker launch profile has no source-selected Linux row")
    mounts.validate_mount_map(
        request["mount_map"],
        expected_source=request["source"],
        expected_plan_sha256=plan_sha,
        expected_profile=request["profile"],
        expected_artifact_sha256=request["artifact_sha256"],
        expected_node_ids_sha256=run["node_ids_sha256"],
        expected_runtime_contract_sha256=hashlib.sha256(_canonical_json(runtime)).hexdigest(),
    )
    if prepared_request["request_ref"] != {
        "transport": "stdin_sha256",
        "sha256": request_sha,
        "bytes": len(request_raw),
    }:
        raise ProfilePartitionError(
            "worker launch request reference differs from its exact stdin bytes"
        )
    mounts.verify_mapped_tree(
        request["mount_map"], role="inputs", expected_files=request["input_members"]
    )
    mounts.verify_mapped_tree(
        request["mount_map"], role="artifacts", expected_files=request["artifact_members"]
    )
    input_root = next(
        row["worker_root"] for row in request["mount_map"]["mounts"] if row["role"] == "inputs"
    )
    command = worker_profile_exec_argv(
        runtime,
        container_id=identity["container_id"],
        request_sha256=request_sha,
        input_worker_root=input_root,
    )
    if prepared_request["worker_argv"] != command:
        raise ProfilePartitionError(
            "worker launch argv differs from the recomputed source-bound command"
        )
    receipt_relative = _relative_file(request["receipt_relative_path"], "worker receipt path")
    receipt_mount = next(row for row in request["mount_map"]["mounts"] if row["role"] == "receipts")
    receipts_root = Path(receipt_mount["host_root"])
    receipt_root = _ensure_directory_beneath(
        receipts_root, receipt_relative.parent, "worker receipt"
    )
    result_path = receipt_root / receipt_relative.name
    if str(result_path) != prepared_request["expected_output_host_path"]:
        raise ProfilePartitionError(
            "worker launch output path differs from its exact receipt mount"
        )
    if result_path.exists() or result_path.is_symlink():
        raise ProfilePartitionError("worker result path is not fresh")
    stdout_path = receipt_root / "host-command-stdout.txt"
    stderr_path = receipt_root / "host-command-stderr.txt"
    launch_path = receipt_root / "host-launch.json"
    if any(path.exists() or path.is_symlink() for path in (stdout_path, stderr_path, launch_path)):
        raise ProfilePartitionError("worker host-launch evidence already exists")
    started_at = datetime.now(UTC).isoformat()
    timed_out = False
    returncode: int | None
    try:
        process = subprocess.run(  # noqa: S603 -- argv is rebuilt from the pinned request and worker contract.
            command,
            input=request_raw,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        stdout_raw = process.stdout
        stderr_raw = process.stderr
        returncode = process.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout_raw = error.stdout or b""
        stderr_raw = error.stderr or b""
        if type(stdout_raw) is str:
            stdout_raw = stdout_raw.encode()
        if type(stderr_raw) is str:
            stderr_raw = stderr_raw.encode()
        returncode = None
    _write_exclusive(stdout_path, stdout_raw, "worker Docker stdout")
    _write_exclusive(stderr_path, stderr_raw, "worker Docker stderr")
    launch_receipt = {
        "schema": "policyos.e02.q2.worker-host-launch.v1",
        "source": request["source"],
        "profile": request["profile"],
        "artifact_sha256": request["artifact_sha256"],
        "request_sha256": request_sha,
        "request_bytes": len(request_raw),
        "request_transport": "stdin_sha256",
        "container_identity": identity,
        "argv": command,
        "started_at": started_at,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "returncode": returncode,
        "stdout": _receipt_evidence(stdout_path, receipt_root),
        "stderr": _receipt_evidence(stderr_path, receipt_root),
    }
    _write_exclusive(launch_path, _canonical_json(launch_receipt) + b"\n", "worker host launch")
    if timed_out or returncode != 0:
        raise ProfilePartitionError(
            "worker Docker command failed; host-launch outputs were retained"
        )
    result_raw = _regular_bytes(result_path, "worker profile result")
    result = _strict_object(result_raw, "worker profile result")
    if (
        result.get("schema") != RESULT_SCHEMA
        or result.get("request_sha256") != request_sha
        or result.get("source") != request["source"]
        or result.get("profile") != request["profile"]
        or result.get("artifact_sha256") != request["artifact_sha256"]
        or result.get("executor") != "linux-worker"
        or result.get("returncode") != 0
    ):
        raise ProfilePartitionError("worker result does not match the executed request and source")
    return result_path


def _sha(value: object, label: str, *, length: int = 64) -> str:
    pattern = _SHA1 if length == 40 else _SHA256
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ProfilePartitionError(
            f"{label} is not a canonical SHA-{'1' if length == 40 else '256'}"
        )
    return value


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _strict_object(raw: bytes, label: str) -> dict[str, Any]:
    def unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProfilePartitionError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProfilePartitionError(f"{label} is not strict JSON") from error
    if type(value) is not dict:
        raise ProfilePartitionError(f"{label} root must be an object")
    return value


def _regular_bytes(path: Path, label: str) -> bytes:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current = current / component
        try:
            info = current.lstat()
        except OSError as error:
            raise ProfilePartitionError(f"{label} path cannot be inspected") from error
        if stat.S_ISLNK(info.st_mode):
            raise ProfilePartitionError(f"{label} traverses a symlink")
    if not stat.S_ISREG(absolute.lstat().st_mode):
        raise ProfilePartitionError(f"{label} must be a regular file")
    return absolute.read_bytes()


def _relative_file(value: object, label: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value:
        raise ProfilePartitionError(f"{label} must be a canonical relative POSIX path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ProfilePartitionError(f"{label} must be a canonical relative POSIX path")
    return path


def _relative_member_rows(value: object, label: str) -> list[dict[str, Any]]:
    if type(value) is not list or not value:
        raise ProfilePartitionError(f"{label} must be a nonempty complete member list")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in value:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            raise ProfilePartitionError(f"{label} member record is malformed")
        relative = _relative_file(row["path"], f"{label} path").as_posix()
        if relative in seen or type(row["bytes"]) is not int or row["bytes"] < 0:
            raise ProfilePartitionError(f"{label} member path or size is duplicated/malformed")
        rows.append(
            {
                "path": relative,
                "bytes": row["bytes"],
                "sha256": _sha(row["sha256"], f"{label} member SHA-256"),
            }
        )
        seen.add(relative)
    if [row["path"] for row in rows] != sorted(seen):
        raise ProfilePartitionError(f"{label} members must be sorted by path")
    return rows


def validate_worker_profile_request(
    request: object,
    *,
    request_sha256: str,
    input_root: Path,
    artifact_root: Path,
) -> dict[str, Any]:
    """Recompute one Linux LA-029 request against its complete visible mounts."""
    if type(request) is not dict or request.get("schema") != REQUEST_SCHEMA:
        raise ProfilePartitionError("unsupported Linux profile partition request")
    expected_fields = {
        "schema",
        "source",
        "profile",
        "artifact_sha256",
        "node_ids",
        "node_ids_sha256",
        "composite_plan",
        "plan_sha256",
        "runtime_contract",
        "runtime_contract_sha256",
        "mount_map",
        "mount_map_sha256",
        "worker_roots",
        "input_members",
        "artifact_members",
        "request_transport",
        "receipt_relative_path",
        "container_identity",
        "container_inspect_ref",
        "resource_owner_inventory",
        "origin_gate_relative_path",
        "origin_gate_sha256",
        "harness",
        "entrypoint_install_plan",
        "entrypoint_install_plan_sha256",
    }
    if set(request) != expected_fields:
        raise ProfilePartitionError("worker profile request has missing or unrecognized fields")
    request_sha256 = _sha(request_sha256, "request SHA-256")
    plan = request.get("composite_plan")
    if type(plan) is not dict or type(plan.get("plan_sha256")) is not str:
        raise ProfilePartitionError("worker request omits its source-bound composite plan")
    plan_unsigned = dict(plan)
    plan_digest = plan_unsigned.pop("plan_sha256")
    if hashlib.sha256(_canonical_json(plan_unsigned)).hexdigest() != plan_digest:
        raise ProfilePartitionError("composite plan bytes differ from its own digest")
    if request.get("plan_sha256") != plan_digest or request.get("source") != plan.get("source"):
        raise ProfilePartitionError("worker request is detached from the selected composite plan")
    source = request.get("source")
    if type(source) is not dict or set(source) != {"commit", "tree"}:
        raise ProfilePartitionError("worker request source identity is malformed")
    _sha(source["commit"], "source commit", length=40)
    _sha(source["tree"], "source tree", length=40)
    profile = request.get("profile")
    if profile not in _PROFILES or type(profile) is not str:
        raise ProfilePartitionError("worker request profile is not one of the three producers")
    run_row = next(
        (
            row
            for row in plan.get("run_plan", [])
            if row.get("profile") == profile and row.get("executor") == "linux-worker"
        ),
        None,
    )
    if type(run_row) is not dict:
        raise ProfilePartitionError("worker profile has no source-selected Linux partition")
    if run_row.get("node_ids") != [LA029_NODE_ID] or request.get("node_ids") != [LA029_NODE_ID]:
        raise ProfilePartitionError("worker request differs from the actual LA-029 node selection")
    node_digest = hashlib.sha256((LA029_NODE_ID + "\n").encode()).hexdigest()
    artifact_sha = _sha(request.get("artifact_sha256"), "profile artifact SHA-256")
    if (
        artifact_sha != run_row.get("artifact_sha256")
        or request.get("node_ids_sha256") != node_digest
        or run_row.get("node_ids_sha256") != node_digest
    ):
        raise ProfilePartitionError("worker request artifact or exact node digest differs")
    artifact_row = next(
        (row for row in plan.get("artifacts", []) if row.get("profile") == profile), None
    )
    if type(artifact_row) is not dict or artifact_row.get("sha256") != artifact_sha:
        raise ProfilePartitionError("worker request artifact is not in the complete producer chain")
    container = request.get("container_identity")
    if type(container) is not dict or set(container) != {"container_id", "image_id"}:
        raise ProfilePartitionError("worker container identity is malformed")
    if (
        type(container.get("container_id")) is not str
        or re.fullmatch(r"[0-9a-f]{64}", container["container_id"]) is None
        or container.get("image_id")
        != request.get("runtime_contract", {}).get("image", {}).get("image_id")
    ):
        raise ProfilePartitionError("worker request container identity differs from pinned image")
    runtime_contract = mounts.validate_runtime_contract(request.get("runtime_contract"))
    runtime_sha = hashlib.sha256(_canonical_json(runtime_contract)).hexdigest()
    if runtime_sha != request.get("runtime_contract_sha256"):
        raise ProfilePartitionError("worker runtime contract digest is stale")
    mount_map = request.get("mount_map")
    mounts.validate_mount_map(
        mount_map,
        expected_source=source,
        expected_plan_sha256=plan_digest,
        expected_profile=profile,
        expected_artifact_sha256=artifact_sha,
        expected_node_ids_sha256=node_digest,
        expected_runtime_contract_sha256=runtime_sha,
        host_roots_must_exist=False,
    )
    mount_sha = hashlib.sha256(_canonical_json(mount_map)).hexdigest()
    if mount_sha != request.get("mount_map_sha256"):
        raise ProfilePartitionError("worker mount mapping digest is stale")
    input_mount = next(row for row in mount_map["mounts"] if row["role"] == "inputs")
    artifact_mount = next(row for row in mount_map["mounts"] if row["role"] == "artifacts")
    if set(request.get("worker_roots", {})) != {"inputs", "artifacts"}:
        raise ProfilePartitionError("worker request contains an unapproved runtime root")
    if (
        Path(input_mount["worker_root"]) != input_root
        or Path(artifact_mount["worker_root"]) != artifact_root
    ):
        raise ProfilePartitionError("worker visible mount roots differ from the frozen mapping")
    input_rows = _relative_member_rows(request.get("input_members"), "input mount")
    artifact_rows = _relative_member_rows(request.get("artifact_members"), "artifact mount")
    if request.get("request_transport") != "stdin_sha256":
        raise ProfilePartitionError("worker request transport must be externally SHA-pinned stdin")
    input_tree = mounts.verify_worker_visible_tree(
        mount_map, role="inputs", expected_files=input_rows
    )
    artifact_tree = mounts.verify_worker_visible_tree(
        mount_map, role="artifacts", expected_files=artifact_rows
    )
    expected_artifact_rows = {
        row["profile"]: (row["bytes"], row["sha256"]) for row in plan.get("artifacts", [])
    }
    observed_artifact_rows = {
        PurePosixPath(row["path"]).parts[1]: (row["bytes"], row["sha256"])
        for row in artifact_rows
        if len(PurePosixPath(row["path"]).parts) >= 2
        and PurePosixPath(row["path"]).parts[0] == "wheels"
    }
    if set(expected_artifact_rows) != set(observed_artifact_rows):
        raise ProfilePartitionError("worker artifact mount does not carry all three profile wheels")
    for row in plan["artifacts"]:
        if observed_artifact_rows.get(row["profile"]) != (row["bytes"], row["sha256"]):
            raise ProfilePartitionError("worker artifact mount differs from source chain bytes")
    inputs = plan.get("source_inputs", {})
    source_files = inputs.get("worker_test_input_files") if type(inputs) is dict else None
    if type(source_files) is not list or hashlib.sha256(
        _canonical_json(source_files)
    ).hexdigest() != inputs.get("worker_test_input_files_sha256"):
        raise ProfilePartitionError("worker test source closure is absent or unbound")
    node_path = LA029_NODE_ID.split("::", 1)[0]
    test_row = next((row for row in source_files if row.get("path") == node_path), None)
    if type(test_row) is not dict or test_row.get("role") != "selected_test":
        raise ProfilePartitionError("selected worker test bytes are not in the source closure")
    for row in source_files:
        relative = _relative_file(row.get("path"), "worker test source path")
        path = input_root / "test-source" / Path(*relative.parts)
        raw = _regular_bytes(path, "worker test source")
        if len(raw) != row.get("bytes") or hashlib.sha256(raw).hexdigest() != row.get("sha256"):
            raise ProfilePartitionError("worker test source differs from the frozen source closure")
    harness = request.get("harness")
    harness_fields = {
        "split_consumer_relative_path": "split_consumer_sha256",
        "partition_runner_relative_path": "partition_runner_sha256",
        "worker_mounts_relative_path": "worker_mounts_sha256",
    }
    if type(harness) is not dict or set(harness) != set(harness_fields) | {
        "origin_plugin_sha256",
        "pytest_bootstrap_sha256",
    }:
        raise ProfilePartitionError("worker request harness pins have an unsupported shape")
    if (
        harness.get("split_consumer_relative_path") != "split_consumer.py"
        or harness.get("partition_runner_relative_path") != "profile_partition_runner.py"
        or harness.get("worker_mounts_relative_path") != "worker_mounts.py"
        or request.get("origin_gate_relative_path") != "q2_installed_origin_gate.py"
        or request.get("request_transport") != "stdin_sha256"
        or request.get("receipt_relative_path") != f"results/{profile}/primary-result.json"
    ):
        raise ProfilePartitionError(
            "worker request uses an unapproved harness or profile-specific path"
        )
    for path_field, sha_field in harness_fields.items():
        relative = _relative_file(harness.get(path_field), f"harness {path_field}")
        raw = _regular_bytes(input_root.joinpath(*relative.parts), f"harness {path_field}")
        if hashlib.sha256(raw).hexdigest() != _sha(harness.get(sha_field), f"harness {sha_field}"):
            raise ProfilePartitionError(f"worker harness file differs from its frozen {sha_field}")
    inspect_ref = request.get("container_inspect_ref")
    if type(inspect_ref) is not dict or set(inspect_ref) != {"path", "sha256"}:
        raise ProfilePartitionError("worker request omits the captured container inspection")
    if inspect_ref.get("path") != "worker-container-inspect.json":
        raise ProfilePartitionError(
            "worker request relocates its field-limited inspection evidence"
        )
    inspect_relative = _relative_file(inspect_ref.get("path"), "container inspect path")
    inspect_raw = _regular_bytes(
        input_root.joinpath(*inspect_relative.parts), "field-limited worker container inspection"
    )
    inspect_sha = _sha(inspect_ref.get("sha256"), "container inspection SHA-256")
    if hashlib.sha256(inspect_raw).hexdigest() != inspect_sha:
        raise ProfilePartitionError("worker container inspection differs from its retained pin")
    inspect_receipt = _strict_object(inspect_raw, "worker container inspection")
    observed_container = mounts.validate_worker_container_inspect_receipt(
        inspect_receipt,
        runtime_contract,
        mount_map,
        expected_container_id=container["container_id"],
    )
    if observed_container != container:
        raise ProfilePartitionError("actual worker inspection differs from request identity")
    install_plan = request.get("entrypoint_install_plan")
    if type(install_plan) is not dict:
        raise ProfilePartitionError("worker request omits the selected wheel entrypoint plan")
    install_sha = _sha(request.get("entrypoint_install_plan_sha256"), "entrypoint plan SHA-256")
    if hashlib.sha256(_canonical_json(install_plan)).hexdigest() != install_sha:
        raise ProfilePartitionError("selected entrypoint install plan digest is stale")
    if (
        install_plan.get("source") != source
        or install_plan.get("plan_sha256") != plan_digest
        or install_plan.get("profile") != profile
        or install_plan.get("artifact_sha256") != artifact_sha
        or install_plan.get("node_ids_sha256") != node_digest
        or install_plan.get("runtime_contract_sha256") != runtime_sha
        or install_plan.get("mount_map_sha256") != mount_sha
    ):
        raise ProfilePartitionError("entrypoint install plan differs from the partition request")
    receipt_relative = _relative_file(request.get("receipt_relative_path"), "receipt path")
    receipts_mount = next(row for row in mount_map["mounts"] if row["role"] == "receipts")
    receipt_root = Path(receipts_mount["worker_root"])
    receipt_path = receipt_root.joinpath(*receipt_relative.parts)
    try:
        receipt_path.relative_to(receipt_root)
    except ValueError as error:
        raise ProfilePartitionError("profile receipt escapes its write mount") from error
    owner = plan.get("owner_inventory")
    owner_ref = request.get("resource_owner_inventory")
    if type(owner) is not dict or type(owner_ref) is not dict:
        raise ProfilePartitionError("worker request omits the source-owned resource inventory")
    if owner_ref.get("path") != "resource-owner-inventory.json" or owner_ref.get(
        "sha256"
    ) != owner.get("sha256"):
        raise ProfilePartitionError("worker resource owner inventory path or pin differs")
    owner_path = _relative_file(owner_ref.get("path"), "resource inventory path")
    owner_raw = _regular_bytes(input_root.joinpath(*owner_path.parts), "resource owner inventory")
    owner_sha = hashlib.sha256(owner_raw).hexdigest()
    if owner_sha != owner.get("sha256") or owner_sha != owner_ref.get("sha256"):
        raise ProfilePartitionError("worker resource inventory differs from the source-bound owner")
    return {
        "plan": plan,
        "plan_sha256": plan_digest,
        "profile": profile,
        "source": source,
        "artifact_sha256": artifact_sha,
        "node_ids": [LA029_NODE_ID],
        "node_ids_sha256": node_digest,
        "container_identity": container,
        "container_inspect_ref": inspect_ref,
        "container_inspect_sha256": inspect_sha,
        "inspect_receipt": inspect_receipt,
        "runtime_contract": runtime_contract,
        "runtime_contract_sha256": runtime_sha,
        "mount_map": mount_map,
        "mount_map_sha256": mount_sha,
        "input_root": input_root,
        "artifact_root": artifact_root,
        "input_rows": input_rows,
        "artifact_rows": artifact_rows,
        "input_tree": input_tree,
        "artifact_tree": artifact_tree,
        "install_plan": install_plan,
        "install_plan_sha256": install_sha,
        "receipt_path": receipt_path,
        "owner_path": input_root.joinpath(*owner_path.parts),
        "owner_sha256": owner_sha,
        "test_source_root": input_root / "test-source",
        "test_source_path": input_root / "test-source" / Path(*PurePosixPath(node_path).parts),
        "harness": harness,
    }


def _run(command: list[str], *, cwd: Path, env: dict[str, str], timeout: int) -> dict[str, Any]:
    result = subprocess.run(  # noqa: S603 -- argv and executable are source/request pinned.
        command,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "argv": command,
        "cwd": str(cwd),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _write_exclusive(path: Path, raw: bytes, label: str) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.write(fd, raw)
        os.fsync(fd)
    finally:
        os.close(fd)
    readback = _regular_bytes(path, label)
    if readback != raw:
        raise ProfilePartitionError(f"{label} changed during its exclusive write")
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _evidence(path: Path) -> dict[str, Any]:
    raw = _regular_bytes(path, "retained command output")
    return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}


def _receipt_evidence(path: Path, receipt_root: Path) -> dict[str, str]:
    raw = _regular_bytes(path, "profile partition receipt evidence")
    try:
        relative = path.relative_to(receipt_root).as_posix()
    except ValueError as error:
        raise ProfilePartitionError(
            "profile evidence escaped its dedicated receipt directory"
        ) from error
    _relative_file(relative, "profile evidence path")
    return {"path": relative, "sha256": hashlib.sha256(raw).hexdigest()}


def _write_json_receipt(
    path: Path, receipt_root: Path, value: object, label: str
) -> dict[str, str]:
    _write_exclusive(path, _canonical_json(value) + b"\n", label)
    return _receipt_evidence(path, receipt_root)


def run_worker_profile_partition(
    request_raw: bytes,
    request_sha256: str,
    *,
    origin_gate_bytes: bytes,
    origin_plugin_bytes: bytes,
    bootstrap_bytes: bytes,
) -> Path:
    """Install and run the exact selected Linux consumer in its mapped profile."""
    if __import__("platform").system() != "Linux":
        raise ProfilePartitionError("LA-029 worker partition requires the measured Linux runtime")
    if type(request_raw) is not bytes or len(request_raw) > 16 * 1024 * 1024:
        raise ProfilePartitionError("stdin profile request must be bytes no larger than 16 MiB")
    request_sha256 = _sha(request_sha256, "request SHA-256")
    if hashlib.sha256(request_raw).hexdigest() != request_sha256:
        raise ProfilePartitionError("profile partition request differs from its external SHA-256")
    request = _strict_object(request_raw, "profile partition request")
    input_root = Path(request["worker_roots"]["inputs"])
    artifact_root = Path(request["worker_roots"]["artifacts"])
    identity = validate_worker_profile_request(
        request,
        request_sha256=request_sha256,
        input_root=input_root,
        artifact_root=artifact_root,
    )
    if hashlib.sha256(origin_gate_bytes).hexdigest() != request.get("origin_gate_sha256"):
        raise ProfilePartitionError("installed-origin gate bytes differ from the source-bound pin")
    if (
        hashlib.sha256(origin_plugin_bytes).hexdigest()
        != identity["harness"]["origin_plugin_sha256"]
    ):
        raise ProfilePartitionError(
            "installed-origin plugin differs from the frozen consumer helper"
        )
    if (
        hashlib.sha256(bootstrap_bytes).hexdigest()
        != identity["harness"]["pytest_bootstrap_sha256"]
    ):
        raise ProfilePartitionError(
            "pytest bootstrap differs from its source-bound consumer helper"
        )
    container_identity = identity["container_identity"]
    hostname = os.environ.get("HOSTNAME", "")
    if not hostname or not container_identity["container_id"].startswith(hostname):
        raise ProfilePartitionError(
            "actual container hostname does not match the host-inspected ID"
        )
    os.environ["E02_Q2_CONTAINER_ID"] = container_identity["container_id"]
    os.environ["E02_Q2_IMAGE_ID"] = container_identity["image_id"]
    plan = identity["plan"]
    owner = _strict_object(
        _regular_bytes(identity["owner_path"], "resource owner inventory"),
        "resource owner inventory",
    )
    if owner.get("assets") != plan.get("owner_resources"):
        raise ProfilePartitionError(
            "owner inventory asset bytes differ from the selected composite plan"
        )
    profile = identity["profile"]
    mount_map = identity["mount_map"]
    artifact_member = next(
        (row for row in identity["artifact_rows"] if row["sha256"] == identity["artifact_sha256"]),
        None,
    )
    if artifact_member is None:
        raise ProfilePartitionError(
            "selected profile wheel is absent from the exact artifact mount"
        )
    wheel_relative = artifact_member["path"]
    worker_artifact_root = Path(
        next(row for row in mount_map["mounts"] if row["role"] == "artifacts")["worker_root"]
    )
    wheel_path = worker_artifact_root.joinpath(
        *_relative_file(wheel_relative, "selected wheel path").parts
    )
    install_plan = identity["install_plan"]
    if (
        install_plan.get("wheel_path") != str(wheel_path)
        or install_plan.get("wheel_relative_path") != wheel_relative
    ):
        raise ProfilePartitionError("entrypoint installation selected another profile wheel")
    install = mounts.execute_entrypoint_install(
        install_plan,
        expected_plan_sha256=identity["install_plan_sha256"],
        runtime_contract=identity["runtime_contract"],
        expected_distribution_name=install_plan["distribution"]["name"],
        expected_distribution_version=install_plan["distribution"]["version"],
    )
    prefix = Path(install["prefix"])
    purelib = Path(install["purelib"])
    python = prefix / "bin" / "python"
    gate_path = purelib / "q2_installed_origin_gate.py"
    plugin_path = purelib / "q2_installed_origin_plugin.py"
    gate_binding = _write_exclusive(gate_path, origin_gate_bytes, "installed-origin gate")
    plugin_binding = _write_exclusive(
        plugin_path, origin_plugin_bytes, "installed-origin pytest plugin"
    )
    baseline = mounts.snapshot_profile_prefix_in_worker(
        install["prefix"], identity["runtime_contract"]["worker"]["python_realpath"]
    )
    root = identity["receipt_path"].parent
    root.mkdir(parents=True, exist_ok=True)
    if identity["receipt_path"].exists() or identity["receipt_path"].is_symlink():
        raise ProfilePartitionError("worker result receipt path is not fresh")
    logs = root / "logs"
    logs.mkdir()
    neutral_cwd = Path(tempfile.mkdtemp(prefix="e02-q2-neutral-", dir=_WORKER_PRIVATE_TMPFS_ROOT))
    poison_root = neutral_cwd / "polisyos" / "data_forge" / "domains" / "catalog" / "_resources"
    poison_root.mkdir(parents=True)
    for index, row in enumerate(owner["owners"]["catalog_defaults"]):
        (poison_root / row["name"]).write_bytes(f"poison-{index}\n".encode())
    junit_path = root / "primary-junit.xml"
    collected_path = root / "collected-nodeids.json"
    target_path = root / "installed-target-proof.json"
    origin_path = root / "origin-proof.json"
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": _WORKER_PRIVATE_TMPFS_ROOT,
        "TMPDIR": _WORKER_PRIVATE_TMPFS_ROOT,
        "PYTEST_ADDOPTS": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "E02_SOURCE_ROOT": str(identity["test_source_root"]),
        "E02_LIVE_PRODUCT_ROOT": str(identity["test_source_root"]),
        "E02_DEPENDENCY_SITE": identity["runtime_contract"]["worker"]["dependency_site"],
        "E02_Q2_INSTALLED_TARGET": str(purelib),
        "E02_NODEIDS_REPORT": str(collected_path),
        "E02_ORIGIN_REPORT": str(origin_path),
        "E02_Q2_TARGET_PROOF": str(target_path),
    }
    bootstrap_path = root / "run-installed-pytest.py"
    bootstrap_binding = _write_exclusive(bootstrap_path, bootstrap_bytes, "pytest bootstrap")
    pytest_args = [
        "-p",
        "q2_installed_origin_plugin",
        "-c",
        str(identity["test_source_root"] / "pytest.ini"),
        "--confcutdir",
        str(identity["test_source_root"] / "tests/unit"),
        "--rootdir",
        str(identity["test_source_root"]),
        "--strict-markers",
        "-q",
        "-ra",
        "-s",
        "--junitxml",
        str(junit_path),
        "--basetemp",
        str(root / "pytest-tmp"),
        str(identity["test_source_path"]),
    ]
    suite = _run(
        [str(python), "-I", str(bootstrap_path), *pytest_args],
        cwd=neutral_cwd,
        env=env,
        timeout=300,
    )
    (logs / "pytest-stdout.txt").write_text(suite["stdout"], encoding="utf-8")
    (logs / "pytest-stderr.txt").write_text(suite["stderr"], encoding="utf-8")
    if suite["returncode"] != 0:
        raise ProfilePartitionError("selected Linux primary consumer failed; full output retained")
    try:
        collected = json.loads(_regular_bytes(collected_path, "collected node IDs"))
        origin = _strict_object(
            _regular_bytes(origin_path, "installed origin proof"), "origin proof"
        )
        target_proof = _strict_object(
            _regular_bytes(target_path, "installed target proof"), "target proof"
        )
    except (OSError, json.JSONDecodeError) as error:
        raise ProfilePartitionError(
            "pytest did not produce complete origin/target proof"
        ) from error
    if (
        collected != identity["node_ids"]
        or origin.get("verified") is not True
        or origin.get("errors") != []
    ):
        raise ProfilePartitionError("pytest node/origin proof differs from the selected profile")
    if target_proof.get("purelib") != str(purelib) or target_proof.get("node_ids") != 1:
        raise ProfilePartitionError("pytest target proof differs from the installed profile")
    resource_command = [
        str(python),
        "-I",
        "-m",
        "tools.quality.validation.packaged_resource_contract",
        "installed",
        "--expected-inventory",
        str(identity["owner_path"]),
        "--purelib",
        str(purelib),
        "--forbidden-root",
        str(identity["test_source_root"]),
        "--forbidden-root",
        str(neutral_cwd),
    ]
    resource = _run(resource_command, cwd=neutral_cwd, env=env, timeout=120)
    (logs / "resource-stdout.txt").write_text(resource["stdout"], encoding="utf-8")
    (logs / "resource-stderr.txt").write_text(resource["stderr"], encoding="utf-8")
    if resource["returncode"] != 0:
        raise ProfilePartitionError("installed resource contract failed; full output retained")
    resource_proof = _strict_object(resource["stdout"].encode(), "resource proof")
    expected_resources = {
        row["wheel"]: {"bytes": row["bytes"], "sha256": row["sha256"]} for row in owner["assets"]
    }
    if resource_proof.get("importlib_resources") != expected_resources:
        raise ProfilePartitionError("installed resource readback differs from source-owned bytes")
    poison = _run_poison_probe(
        python=python,
        purelib=purelib,
        dependency_site=Path(env["E02_DEPENDENCY_SITE"]),
        owner=owner,
        neutral_cwd=neutral_cwd,
        input_root=identity["test_source_root"],
    )
    after = mounts.snapshot_profile_prefix_in_worker(
        install["prefix"], identity["runtime_contract"]["worker"]["python_realpath"]
    )
    if baseline != after:
        raise ProfilePartitionError("selected consumer or probes mutated its installed prefix")
    junit_raw = _regular_bytes(junit_path, "primary JUnit")
    junit_ids, junit_counts = _junit_ids(junit_raw, plan["special_document_path"])
    if junit_ids != identity["node_ids"] or junit_counts != {
        "tests": 1,
        "skipped": 0,
        "failures": 0,
        "errors": 0,
    }:
        raise ProfilePartitionError("JUnit does not prove one exact zero-skip Linux node")
    container_identity = identity["container_identity"]
    execution_identity = {
        "schema": "policyos.e02.q2.execution-identity.v1",
        "source": identity["source"],
        "platform_system": "Linux",
        "sys_platform": sys.platform,
        "machine": __import__("platform").machine(),
        "python": os.path.realpath(python),
        "python_version": [3, 14, 0],
        "runner_sha256": identity["plan"]["input_pins"]["consumer_runner_sha256"],
        "source_checkout_root": None,
        "source_input_root": str(identity["test_source_root"]),
        "source_input_members": identity["plan"]["source_inputs"]["worker_test_input_files"],
        "container_id": container_identity["container_id"],
        "image_id": container_identity["image_id"],
        "mount_map_sha256": identity["mount_map_sha256"],
    }
    artifact_transport_rows = []
    for artifact_row in plan["artifacts"]:
        member = next(
            (row for row in identity["artifact_rows"] if row["profile"] == artifact_row["profile"]),
            None,
        )
        if member is None:
            raise ProfilePartitionError("transport cannot bind every source-selected profile wheel")
        artifact_transport_rows.append(
            {
                "profile": artifact_row["profile"],
                "chain_key": artifact_row["chain_key"],
                "path": str(
                    worker_artifact_root / _relative_file(member["path"], "wheel artifact path")
                ),
                "bytes": artifact_row["bytes"],
                "sha256": artifact_row["sha256"],
            }
        )
    _write_exclusive(root / "request.json", request_raw, "stdin profile request")
    transport = {
        "source": identity["source"],
        "input_pins": identity["plan"]["input_pins"],
        "transport_status": "hash_verified_exact_artifact",
        "request_transport": "stdin_sha256",
        "artifact_chain": identity["plan"]["artifact_chain"],
        "artifacts": artifact_transport_rows,
        "container_id": container_identity["container_id"],
        "image_id": container_identity["image_id"],
        "runtime_contract": identity["runtime_contract"],
        "runtime_contract_sha256": identity["runtime_contract_sha256"],
        "mount_map": mount_map,
        "mount_map_sha256": identity["mount_map_sha256"],
        "input_members": [
            {key: row[key] for key in ("path", "bytes", "sha256")} for row in identity["input_rows"]
        ],
        "artifact_members": [
            {key: row[key] for key in ("path", "bytes", "sha256")}
            for row in identity["artifact_rows"]
        ],
        "container_inspect_ref": {
            "path": str(
                Path(
                    next(
                        row["worker_root"] for row in mount_map["mounts"] if row["role"] == "inputs"
                    )
                )
                / identity["container_inspect_ref"]["path"]
            ),
            "sha256": identity["container_inspect_sha256"],
        },
        "container_inspect_sha256": identity["container_inspect_sha256"],
        "source_input_root": str(identity["test_source_root"]),
        "source_input_root_host": next(
            row["host_root"] for row in mount_map["mounts"] if row["role"] == "inputs"
        )
        + "/test-source",
        "source_input_members": plan["source_inputs"]["worker_test_input_files"],
        "request_ref": _receipt_evidence(root / "request.json", root),
        "input_tree": identity["input_tree"],
        "worker_visible_artifact_tree": {
            "member_count": len(identity["artifact_rows"]),
            "members_sha256": hashlib.sha256(
                _canonical_json(identity["artifact_rows"])
            ).hexdigest(),
        },
        "source_checkout_mounted": False,
    }
    _write_exclusive(
        root / "execution-identity.json",
        _canonical_json(execution_identity) + b"\n",
        "execution identity",
    )
    result = {
        "schema": RESULT_SCHEMA,
        "request_sha256": request_sha256,
        "source": identity["source"],
        "input_pins": identity["plan"]["input_pins"],
        "plan_sha256": identity["plan_sha256"],
        "profile": profile,
        "executor": "linux-worker",
        "artifact_sha256": identity["artifact_sha256"],
        "runner_sha256": identity["plan"]["input_pins"]["consumer_runner_sha256"],
        "returncode": 0,
        "execution_identity": _receipt_evidence(root / "execution-identity.json", root),
        "collected_node_ids": _receipt_evidence(collected_path, root),
        "junit": _receipt_evidence(junit_path, root),
        "origin_proof": _receipt_evidence(origin_path, root),
        "installed_target_proof": _receipt_evidence(target_path, root),
        "resource_proof": _write_json_receipt(
            root / "resource-proof.json", root, resource_proof, "resource proof"
        ),
        "resource_stdout": _receipt_evidence(logs / "resource-stdout.txt", root),
        "resource_stderr": _receipt_evidence(logs / "resource-stderr.txt", root),
        "poison_proof": _write_json_receipt(
            root / "poison-proof.json", root, poison, "poison proof"
        ),
        "target_before_snapshot": _write_json_receipt(
            root / "target-before.json", root, baseline, "target before snapshot"
        ),
        "target_after_snapshot": _write_json_receipt(
            root / "target-after.json", root, after, "target after snapshot"
        ),
        "stdout": _receipt_evidence(logs / "pytest-stdout.txt", root),
        "stderr": _receipt_evidence(logs / "pytest-stderr.txt", root),
        "transport_proof": _write_json_receipt(
            root / "transport-proof.json", root, transport, "transport proof"
        ),
        "entrypoint_install_receipt": _write_json_receipt(
            root / "entrypoint-install.json", root, install, "entrypoint install receipt"
        ),
        "support_files": {
            "origin_gate": gate_binding,
            "origin_plugin": plugin_binding,
            "pytest_bootstrap": bootstrap_binding,
        },
    }
    result_path = identity["receipt_path"]
    _write_exclusive(result_path, _canonical_json(result) + b"\n", "profile partition result")
    return result_path


def _junit_ids(raw: bytes, special_document_path: str) -> tuple[list[str], dict[str, int]]:
    try:
        root = ElementTree.fromstring(raw)
    except (ElementTree.ParseError, DefusedXmlException) as error:
        raise ProfilePartitionError("pytest JUnit is malformed XML") from error
    ids: list[str] = []
    counts = {"tests": 0, "skipped": 0, "failures": 0, "errors": 0}
    for case in root.iter("testcase"):
        classname, name = case.attrib.get("classname"), case.attrib.get("name")
        if not classname or not name:
            raise ProfilePartitionError("pytest JUnit case omits classname or name")
        if classname == "test_installed_catalog_defaults":
            path = special_document_path
        else:
            dotted = classname.split(".")
            path = "/".join((*dotted[:-1], dotted[-1] + ".py"))
        ids.append(f"{path}::{name}")
        counts["tests"] += 1
        counts["skipped"] += case.find("skipped") is not None
        counts["failures"] += case.find("failure") is not None
        counts["errors"] += case.find("error") is not None
    if len(ids) != len(set(ids)):
        raise ProfilePartitionError("pytest JUnit repeats a node ID")
    return sorted(ids), counts


def _run_poison_probe(
    *,
    python: Path,
    purelib: Path,
    dependency_site: Path,
    owner: dict[str, Any],
    neutral_cwd: Path,
    input_root: Path,
) -> dict[str, Any]:
    script = "\n".join(
        (
            "import json, sys",
            "from pathlib import Path",
            f"sys.path.insert(0, {str(purelib)!r})",
            f"sys.path.append({str(dependency_site)!r})",
            "from typing import get_args",
            "from polisyos.data_forge.domains.catalog import _resources",
            "from polisyos.foundry.methods.catalog import dependency_authority",
            "from polisyos.foundry.methods.catalog.causal import _dowhy_worker",
            "import q2_installed_origin_gate",
            f"expected = {owner!r}",
            "targets = {\n"
            "    Path(row['wheel']).name: row\n"
            "    for row in expected['owners']['catalog_defaults']\n"
            "}",
            "names = tuple(get_args(_resources.CatalogDefaultResource))",
            "assert set(targets) == set(names)",
            "for name in names:",
            "    selected = Path(\n"
            "        _resources.catalog_default_resource_path(name)\n"
            "    ).resolve(strict=True)",
            "    expected_path = (\n"
            "        Path(sys.path[0]) / targets[name]['wheel']\n"
            "    ).resolve(strict=True)",
            "    assert selected == expected_path",
            "    assert selected.read_bytes() == expected_path.read_bytes()",
            "registry = Path(dependency_authority._DIGEST_REGISTRY_PATH).resolve(strict=True)",
            "assert registry == Path(\n"
            "    dependency_authority._PACKAGED_DIGEST_REGISTRY_PATH\n"
            ").resolve(strict=True)",
            "assert dependency_authority.load_digest_domain_registry(registry).statement.domains",
            "worker_dir = Path(_dowhy_worker._worker_directory()).resolve(strict=True)",
            "expected_worker = (\n"
            "    Path(sys.path[0])\n"
            "    / expected['owners']['worker_profile_assets'][0]['wheel']\n"
            ").parent.resolve(strict=True)",
            "assert worker_dir == expected_worker",
            "assert all(\n"
            "    (worker_dir / row['name']).is_file()\n"
            "    for row in expected['owners']['worker_profile_assets']\n"
            ")",
            "origins, origin_errors = (\n"
            "    q2_installed_origin_gate.verify_loaded_module_origins(\n"
            "        Path(sys.path[0]), sys.modules.copy()\n"
            "    )\n"
            ")",
            "assert not origin_errors, origin_errors",
            "assert {'polisyos', 'tools'} <= set(origins), sorted(origins)",
            f"for forbidden in ({str(neutral_cwd)!r}, {str(input_root)!r}):",
            "    forbidden_path = Path(forbidden).resolve(strict=True)",
            "    resolved_paths = [\n"
            "        Path(entry).resolve(strict=False)\n"
            "        for entry in sys.path\n"
            "        if entry\n"
            "    ]",
            "    assert not any(\n"
            "        path == forbidden_path or path.is_relative_to(forbidden_path)\n"
            "        for path in resolved_paths\n"
            "    )",
            "proof = {\n"
            "    'verified': True,\n"
            "    'purelib': str(Path(sys.path[0]).resolve(strict=True)),\n"
            "    'dependency_site': str(Path(sys.path[-1]).resolve(strict=True)),\n"
            "    'sys_path': sys.path,\n"
            "    'origins': origins,\n"
            "    'catalog_readers': {\n"
            "        name: str(_resources.catalog_default_resource_path(name))\n"
            "        for name in names\n"
            "    },\n"
            "    'dependency_registry': str(registry),\n"
            "    'dowhy_worker_directory': str(worker_dir),\n"
            "}",
            "print(json.dumps(proof, sort_keys=True))",
        )
    )
    script_path = neutral_cwd / "poison-resource-control.py"
    script_path.write_text(script, encoding="utf-8")
    result = _run(
        [str(python), "-I", str(script_path)],
        cwd=neutral_cwd,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": _WORKER_PRIVATE_TMPFS_ROOT,
            "TMPDIR": _WORKER_PRIVATE_TMPFS_ROOT,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        },
        timeout=120,
    )
    if result["returncode"] != 0:
        raise ProfilePartitionError("poisoned-neighbor resource control failed")
    proof = _strict_object(result["stdout"].encode(), "poison control")
    if proof.get("verified") is not True:
        raise ProfilePartitionError("poisoned-neighbor resource control is not verified")
    return {
        **proof,
        "argv": result["argv"],
        "cwd": result["cwd"],
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--request-sha256", required=True)
    parser.parse_args(argv)
    raise ProfilePartitionError(
        "profile partition entry must be dispatched by the source-bound split_consumer wrapper"
    )


if __name__ == "__main__":
    raise SystemExit(main())

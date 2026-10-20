"""Exact host/container mappings for the Q2 Linux-only consumer partition.

The worker is an execution boundary, not a second source checkout. Only the
source-derived input bundle, exact wheel set, per-profile consumer prefix, and
per-profile receipt directory may cross that boundary. Existing dependency and
interpreter volumes stay worker-local and are verified from worker evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import stat
import subprocess
from configparser import ConfigParser
from configparser import Error as ConfigParserError
from email import policy as email_policy
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

RUNTIME_SCHEMA = "policyos.e02.q2.linux-worker-runtime-contract.v1"
RUNTIME_BINDING_SCHEMA = "policyos.e02.q2.worker-runtime-binding.v1"
MOUNT_MAP_SCHEMA = "policyos.e02.q2.worker-mount-map.v1"
WORKER_PROBE_SCHEMA = "policyos.e02.q2.worker-runtime-probe.v1"
ENTRYPOINT_INSTALL_SCHEMA = "policyos.e02.q2.installed-entrypoint-receipt.v1"
Q2_FIRST_LA029_RESOURCE_LIMITS = {
    "memory_bytes": 2 * 1024 * 1024 * 1024,
    "memory_swap_bytes": 2 * 1024 * 1024 * 1024,
    "nano_cpus": 1_000_000_000,
}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SHA256_IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ROLE_ACCESS = {
    "inputs": "read-only",
    "artifacts": "read-only",
    "profile-prefix": "read-write",
    "receipts": "read-write",
}
_WORKER_TMP = PurePosixPath("/tmp")  # noqa: S108 -- isolated tmpfs destination is intentional.
_FORBIDDEN_WORKER_ROOTS = (
    PurePosixPath("/scratch"),
    PurePosixPath("/opt/uv-python"),
    PurePosixPath("/root/.cache/uv"),
    _WORKER_TMP,
)


class WorkerMountError(ValueError):
    """Raised when a host/worker path or runtime identity is not source-bound."""


class WorkerCommandError(WorkerMountError):
    """Raised with complete deciding output when one measured worker command fails."""

    def __init__(self, message: str, observations: list[dict[str, Any]]) -> None:
        super().__init__(message)
        self.observations = observations


def sha256_bytes(raw: bytes) -> str:
    """Return the SHA-256 of exact bytes."""
    return hashlib.sha256(raw).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    """Serialize a JSON-shaped value deterministically for receipt identities."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _digest(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise WorkerMountError(f"{label} must be a lowercase SHA-256")
    return value


def _strict_json_object(raw: bytes, label: str) -> dict[str, Any]:
    """Parse a JSON object without accepting duplicate keys."""

    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        parsed: dict[str, Any] = {}
        for key, value in values:
            if key in parsed:
                raise WorkerMountError(f"{label} contains a duplicate JSON key: {key}")
            parsed[key] = value
        return parsed

    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkerMountError(f"{label} is not strict JSON") from error
    if type(value) is not dict:
        raise WorkerMountError(f"{label} root must be an object")
    return value


def _host_regular_file(value: str | Path, label: str) -> Path:
    """Resolve one canonical host file without accepting symlinked components."""
    if (type(value) is not str and not isinstance(value, Path)) or not value:
        raise WorkerMountError(f"{label} must be an absolute canonical host file")
    supplied_text = str(value)
    path = value if isinstance(value, Path) else Path(value)
    if not path.is_absolute() or ".." in path.parts or str(path) != supplied_text:
        raise WorkerMountError(f"{label} must be an absolute canonical host file")
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current = current / component
        try:
            info = current.lstat()
        except OSError as error:
            raise WorkerMountError(f"{label} path component cannot be inspected") from error
        if stat.S_ISLNK(info.st_mode):
            raise WorkerMountError(f"{label} traverses a symbolic link: {current}")
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise WorkerMountError(f"{label} cannot be resolved") from error
    if resolved != path or not stat.S_ISREG(path.lstat().st_mode):
        raise WorkerMountError(f"{label} must be a regular non-symlink file")
    return path


def load_runtime_binding_input(
    report_path: str | Path,
    *,
    report_sha256: str,
    corrigendum_path: str | Path,
    corrigendum_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    """Read the exact operator-supplied worker facts and their append-only correction.

    This binds the already observed worker only. It does not claim that a new
    consumer container exists or that any proposed mounts have been read back.
    """
    report_file = _host_regular_file(report_path, "worker runtime binding report")
    corrigendum_file = _host_regular_file(corrigendum_path, "worker runtime binding corrigendum")
    report_raw = report_file.read_bytes()
    corrigendum_raw = corrigendum_file.read_bytes()
    observed_report_sha = sha256_bytes(report_raw)
    observed_corrigendum_sha = sha256_bytes(corrigendum_raw)
    if observed_report_sha != _digest(report_sha256, "worker runtime binding report SHA-256"):
        raise WorkerMountError("worker runtime binding report differs from its frozen SHA-256")
    if observed_corrigendum_sha != _digest(
        corrigendum_sha256, "worker runtime binding corrigendum SHA-256"
    ):
        raise WorkerMountError("worker runtime binding corrigendum differs from its frozen SHA-256")
    report = _strict_json_object(report_raw, "worker runtime binding report")
    corrigendum = _strict_json_object(corrigendum_raw, "worker runtime binding corrigendum")
    if report.get("schema") != "q2_worker_runtime_binding_input_v1":
        raise WorkerMountError("worker runtime binding report schema is unsupported")
    if corrigendum.get("schema") != "q2_worker_runtime_binding_readback_corrigendum_v1":
        raise WorkerMountError("worker runtime binding corrigendum schema is unsupported")
    target = corrigendum.get("target_report")
    if (
        type(target) is not dict
        or target.get("path") != str(report_file)
        or target.get("sha256") != observed_report_sha
    ):
        raise WorkerMountError("worker runtime corrigendum does not bind this exact report")
    commands = report.get("readback_commands")
    if type(commands) is not list or not commands:
        raise WorkerMountError("worker runtime report omits explicit readback commands")
    for row in commands:
        if type(row) is not dict or type(row.get("argv")) is not list:
            raise WorkerMountError("worker runtime readback command is malformed")
        if any("Config.Env" in str(argument) for argument in row["argv"]):
            raise WorkerMountError("worker runtime evidence includes an environment dump")
        for field in ("stdout_sha256", "stderr_sha256"):
            _digest(row.get(field), f"worker runtime command {field}")
    frame = report.get("source_frame")
    existing = report.get("existing_worker")
    future = report.get("future_container_intent_not_executed")
    if type(frame) is not dict or type(existing) is not dict or type(future) is not dict:
        raise WorkerMountError("worker runtime report omits its source or runtime boundary")
    if future.get("status") != "draft_only" or future.get("source_checkout_mount") != (
        "forbidden; do not mount /Users/deniskopylov/polisyos or the managed worktree "
        "into the test container"
    ):
        raise WorkerMountError(
            "worker runtime report does not preserve its pending/no-checkout scope"
        )
    identity = {
        "report_path": str(report_file),
        "report_sha256": observed_report_sha,
        "corrigendum_path": str(corrigendum_file),
        "corrigendum_sha256": observed_corrigendum_sha,
        "source_frame_head": frame.get("head"),
        "source_frame_tree": frame.get("tree"),
        "existing_container_id": existing.get("container_id"),
        "existing_image_id": existing.get("image_id"),
        "new_container_status": "not_created",
    }
    return report, corrigendum, identity


def runtime_contract_from_binding_input(report: dict[str, Any]) -> dict[str, Any]:
    """Derive proposed new-container expectations from measured worker paths.

    Read-only/network/tmpfs settings are explicit requested runtime properties;
    they are not inherited as facts from the existing provision container.
    """
    if type(report) is not dict or report.get("schema") != "q2_worker_runtime_binding_input_v1":
        raise WorkerMountError("worker runtime contract requires the admitted binding report")
    existing = report.get("existing_worker")
    future = report.get("future_container_intent_not_executed")
    if type(existing) is not dict or type(future) is not dict:
        raise WorkerMountError("worker runtime report has no existing/future boundary")
    runtime = existing.get("runtime")
    if type(runtime) is not dict or type(runtime.get("python")) is not dict:
        raise WorkerMountError("measured worker runtime omits its Python profile")
    python = runtime["python"]
    installer = runtime.get("uv")
    volumes = future.get("shared_dependency_mounts")
    docker_config = existing.get("docker_config")
    docker_context = existing.get("docker_context")
    image_reference = existing.get("image_repo_digest")
    image_id = existing.get("image_id")
    image_platform = existing.get("image_platform")
    if (
        type(volumes) is not list
        or type(installer) is not dict
        or type(docker_config) is not str
        or type(docker_context) is not str
        or not docker_context
        or type(image_reference) is not str
        or type(image_id) is not str
        or image_platform != "linux/arm64"
        or existing.get("config_image") != image_reference
        or existing.get("state") != "running"
    ):
        raise WorkerMountError("measured worker does not identify a supported pinned runtime")
    # The source observation records a three-volume draft, including uv's
    # package cache. The selected installer runs with --no-cache, so the new
    # consumer mounts only the two runtime/dependency volumes it needs.
    observed_mounts: list[dict[str, Any]] = []
    for row in volumes:
        if type(row) is not dict or set(row) != {"mode", "source", "target"}:
            raise WorkerMountError("future shared worker volume row is malformed")
        if row.get("mode") != "ro":
            raise WorkerMountError("future shared worker volumes must be read-only")
        observed_mounts.append(
            {
                "name": row["source"],
                "destination": row["target"],
                "read_only": True,
            }
        )
    observed_volume_set = {(row["name"], row["destination"]) for row in observed_mounts}
    expected_observed_volumes = {
        ("e02-local-uv-env", "/scratch"),
        ("e02-local-uv-pythons", "/opt/uv-python"),
        ("e02-local-uv-cache", "/root/.cache/uv"),
    }
    if observed_volume_set != expected_observed_volumes:
        raise WorkerMountError(
            "future worker shared-volume evidence differs from its pinned report"
        )
    shared_mounts = [
        row
        for row in observed_mounts
        if row["name"] in {"e02-local-uv-env", "e02-local-uv-pythons"}
    ]
    if (
        python.get("version") != "3.14.0"
        or python.get("realpath")
        != "/opt/uv-python/cpython-3.14.0-linux-aarch64-gnu/bin/python3.14"
        or python.get("venv_launcher") != "/scratch/root-venv/bin/python"
        or python.get("dependency_purelib") != "/scratch/root-venv/lib/python3.14/site-packages"
        or python.get("pytest_file")
        != "/scratch/root-venv/lib/python3.14/site-packages/pytest/__init__.py"
        or python.get("sha256")
        != "87bc29693866a567a3a6263c374c51a16b6745810b67200a319bbe9bf8e6d51e"
        or installer.get("path") != "/usr/local/bin/uv"
        or installer.get("version") != "0.9.21"
    ):
        raise WorkerMountError("measured Python/uv paths differ from the supported local profile")
    return validate_runtime_contract(
        {
            "schema": RUNTIME_SCHEMA,
            "docker": {"config_path": docker_config, "context": docker_context},
            "image": {"reference": image_reference, "image_id": image_id},
            "isolation": {
                "read_only_rootfs": True,
                "network_mode": "none",
                "persistent_volumes": shared_mounts,
                "tmpfs_destinations": [_WORKER_TMP.as_posix()],
            },
            "worker": {
                "platform_system": "Linux",
                "sys_platform": "linux",
                "machine": "aarch64",
                "python_executable": python["venv_launcher"],
                "python_realpath": python["realpath"],
                "python_version": [3, 14, 0],
                "dependency_site": python["dependency_purelib"],
                "pytest_origin": python["pytest_file"],
            },
            "installer": {
                "name": "uv",
                "path": installer["path"],
                "version": installer["version"],
                "sha256": installer.get("sha256"),
            },
            # Operator-selected first-run limits; the new container must be
            # read back after creation before this intent is treated as fact.
            "resources": dict(Q2_FIRST_LA029_RESOURCE_LIMITS),
        }
    )


def worker_container_create_argv(
    runtime_contract: dict[str, Any],
    mount_map: dict[str, Any],
    *,
    container_name: str,
    resource_limits: dict[str, int] | None = None,
) -> list[str]:
    """Prepare, but never execute, the exact no-pull consumer-container command."""
    contract = validate_runtime_contract(runtime_contract)
    if not re.fullmatch(r"e02-q2-[a-z0-9][a-z0-9-]{0,48}", container_name):
        raise WorkerMountError("new worker container name is not a unique Q2 run identifier")
    if type(mount_map) is not dict:
        raise WorkerMountError("new worker container requires a validated mount map")
    if resource_limits is None:
        raise WorkerMountError("new worker resource limits require an explicit operator decision")
    volumes = contract["isolation"]["persistent_volumes"]
    argv = [
        "docker",
        "--config",
        contract["docker"]["config_path"],
        "--context",
        contract["docker"]["context"],
        "create",
        "--pull=never",
        "--name",
        container_name,
        "--read-only",
        "--network",
        contract["isolation"]["network_mode"],
        "--tmpfs",
        f"{_WORKER_TMP.as_posix()}:rw,nosuid,nodev,noexec,size=256m",
    ]
    if type(resource_limits) is not dict or set(resource_limits) != {
        "memory_bytes",
        "memory_swap_bytes",
        "nano_cpus",
    }:
        raise WorkerMountError("new worker resource limits have an unsupported shape")
    if any(type(value) is not int or value <= 0 for value in resource_limits.values()):
        raise WorkerMountError("new worker resource limits must be positive integer measurements")
    if resource_limits["memory_swap_bytes"] < resource_limits["memory_bytes"]:
        raise WorkerMountError("new worker memory-swap limit is below its memory limit")
    if resource_limits != contract["resources"]:
        raise WorkerMountError("new worker limits differ from the operator-selected runtime plan")
    argv.extend(
        (
            "--memory",
            str(resource_limits["memory_bytes"]),
            "--memory-swap",
            str(resource_limits["memory_swap_bytes"]),
            "--cpus",
            str(resource_limits["nano_cpus"] / 1_000_000_000),
        )
    )
    for row in sorted(volumes, key=lambda item: item["destination"]):
        argv.extend(
            (
                "--mount",
                f"type=volume,src={row['name']},dst={row['destination']},readonly",
            )
        )
    for row in mount_map["mounts"]:
        host = _host_path(row["host_root"], f"host {row['role']} root")
        worker = _worker_path(row["worker_root"], f"worker {row['role']} root")
        if "," in str(host):
            raise WorkerMountError("host mount paths may not contain Docker option delimiters")
        access = ",readonly" if row["access"] == "read-only" else ""
        argv.extend(
            (
                "--mount",
                f"type=bind,src={host},dst={worker}{access}",
            )
        )
    argv.extend(("--entrypoint", "/bin/sleep", contract["image"]["reference"], "infinity"))
    return argv


def _dependency_site_bridge_bytes(dependency_site: PurePosixPath) -> bytes:
    """Use Python's normal site loader for the pinned dependency profile."""
    return f"import site; site.addsitedir({dependency_site.as_posix()!r})\n".encode()


def _selected_wheel_metadata(wheel_path: Path, expected_sha256: str) -> dict[str, Any]:
    """Read distribution identity and entry points from the exact selected wheel."""
    expected_sha256 = _digest(expected_sha256, "selected wheel SHA-256")
    try:
        info = wheel_path.lstat()
    except OSError as error:
        raise WorkerMountError("selected wheel path is absent") from error
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise WorkerMountError("selected wheel must be a regular nonsymlink file")
    digest = hashlib.sha256()
    try:
        with wheel_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise WorkerMountError("selected wheel cannot be read") from error
    if digest.hexdigest() != expected_sha256:
        raise WorkerMountError("selected wheel bytes differ from the source-bound artifact")

    try:
        with ZipFile(wheel_path) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)):
                raise WorkerMountError("selected wheel contains duplicate archive members")
            for name in names:
                if not name or "\\" in name:
                    raise WorkerMountError("selected wheel contains a noncanonical archive path")
                path = PurePosixPath(name.rstrip("/"))
                if (
                    path.is_absolute()
                    or path.as_posix() != name.rstrip("/")
                    or not path.parts
                    or any(part in {"", ".", ".."} for part in path.parts)
                ):
                    raise WorkerMountError("selected wheel contains a noncanonical archive path")
            metadata_names = [
                name
                for name in names
                if name.endswith(".dist-info/METADATA") and name.count("/") == 1
            ]
            if len(metadata_names) != 1:
                raise WorkerMountError(
                    "selected wheel must contain one top-level dist-info METADATA"
                )
            dist_info = metadata_names[0].removesuffix("/METADATA")
            named_members = {
                label: f"{dist_info}/{filename}"
                for label, filename in (
                    ("metadata", "METADATA"),
                    ("wheel", "WHEEL"),
                    ("entry_points", "entry_points.txt"),
                )
            }
            member_by_name = {member.filename: member for member in members}
            if any(name not in member_by_name for name in named_members.values()):
                raise WorkerMountError("selected wheel omits required dist-info metadata")
            if any(
                member_by_name[name].file_size > 4 * 1024 * 1024 for name in named_members.values()
            ):
                raise WorkerMountError(
                    "selected wheel dist-info metadata exceeds the bounded reader"
                )
            for name in named_members.values():
                member = member_by_name[name]
                mode = member.external_attr >> 16
                file_kind = stat.S_IFMT(mode)
                if file_kind not in {0, stat.S_IFREG}:
                    raise WorkerMountError("selected wheel metadata member is not a regular file")
            raw_metadata = {key: archive.read(name) for key, name in named_members.items()}
    except (BadZipFile, OSError, RuntimeError) as error:
        raise WorkerMountError("selected wheel archive or metadata is unreadable") from error

    message = BytesParser(policy=email_policy.default).parsebytes(raw_metadata["metadata"])
    name_values = message.get_all("Name", [])
    version_values = message.get_all("Version", [])
    if (
        len(name_values) != 1
        or len(version_values) != 1
        or not str(name_values[0]).strip()
        or not str(version_values[0]).strip()
    ):
        raise WorkerMountError("selected wheel METADATA has no unique name/version")
    parser = ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    try:
        parser.read_string(raw_metadata["entry_points"].decode("utf-8"))
        if parser.defaults():
            raise WorkerMountError("selected wheel entry points may not use DEFAULT values")
        entry_points = {
            section: dict(parser.items(section, raw=True)) for section in parser.sections()
        }
    except (UnicodeDecodeError, ConfigParserError) as error:
        raise WorkerMountError("selected wheel entry_points.txt is malformed") from error
    if any(
        not group
        or any(
            not name or not value.strip() or any(character in value for character in "\r\n\0")
            for name, value in entries.items()
        )
        for group, entries in entry_points.items()
    ):
        raise WorkerMountError("selected wheel entry_points.txt contains an empty entry")
    file_sha256 = {
        named_members[label].rsplit("/", 1)[-1]: sha256_bytes(raw)
        for label, raw in sorted(raw_metadata.items())
    }
    metadata = {
        "wheel_sha256": expected_sha256,
        "dist_info": dist_info,
        "distribution_name": str(name_values[0]).strip(),
        "distribution_version": str(version_values[0]).strip(),
        "entry_points": entry_points,
        "metadata_file_sha256": file_sha256,
    }
    return {**metadata, "sha256": sha256_bytes(canonical_json_bytes(metadata))}


def _venv_sysconfig_code() -> str:
    """Return the fixed source used to read the actual venv layout."""
    return (
        "import json, pathlib, sys, sysconfig; print(json.dumps({"
        "'prefix':str(pathlib.Path(sys.prefix).absolute()),"
        "'purelib':str(pathlib.Path(sysconfig.get_path('purelib')).absolute()),"
        "'scripts':str(pathlib.Path(sysconfig.get_path('scripts')).absolute()),"
        "'executable':str(pathlib.Path(sys.executable).absolute()),"
        "'realpath':str(pathlib.Path(sys.executable).resolve(strict=True))}))"
    )


def _installed_wheel_readback_code(distribution_name: str, entrypoint_name: str) -> str:
    """Return the fixed source that reads installed metadata and generated script bytes."""
    return "\n".join(
        (
            "import hashlib, importlib.metadata as metadata, json, stat, sys, sysconfig",
            "from pathlib import Path, PurePosixPath",
            f"distribution = metadata.distribution({distribution_name!r})",
            "entries = [",
            "    {'group': ep.group, 'name': ep.name, 'value': ep.value}",
            "    for ep in distribution.entry_points",
            "]",
            "entries.sort(key=lambda row: (row['group'], row['name']))",
            "files = distribution.files",
            "if files is None: raise RuntimeError('installed distribution has no RECORD file set')",
            "purelib = Path(sysconfig.get_path('purelib')).resolve(strict=True)",
            "meta_hashes = {}",
            "for name in ('METADATA', 'WHEEL', 'entry_points.txt'):",
            "    matches = [item for item in files if PurePosixPath(str(item)).name == name",
            "               and PurePosixPath(str(item)).parent.name.endswith('.dist-info')]",
            "    if len(matches) != 1: raise RuntimeError(f'expected one installed {name}')",
            "    meta_path = Path(distribution.locate_file(matches[0])).resolve(strict=True)",
            "    if not meta_path.is_relative_to(purelib):",
            "        raise RuntimeError('metadata escaped selected purelib')",
            "    meta_info = meta_path.lstat()",
            "    if not stat.S_ISREG(meta_info.st_mode):",
            "        raise RuntimeError('metadata is not regular')",
            "    meta_hashes[name] = hashlib.sha256(meta_path.read_bytes()).hexdigest()",
            "meta_digest = hashlib.sha256(json.dumps(meta_hashes, sort_keys=True,",
            "    separators=(',', ':')).encode()).hexdigest()",
            "scripts = Path(sysconfig.get_path('scripts')).resolve(strict=True)",
            f"script = scripts / {entrypoint_name!r}",
            "info = script.lstat()",
            "raw = script.read_bytes()",
            "receipt = {",
            "    'name': distribution.metadata['Name'],",
            "    'version': distribution.version,",
            "    'entries': entries,",
            "    'meta_hashes': meta_hashes,",
            "    'metadata_sha256': meta_digest,",
            "    'script_path': str(script),",
            "    'script_bytes': len(raw),",
            "    'script_sha256': hashlib.sha256(raw).hexdigest(),",
            "    'script_mode': stat.S_IMODE(info.st_mode),",
            "    'script_shebang': raw.splitlines()[0].decode('utf-8'),",
            "    'python': str(Path(sys.executable).absolute()),",
            "    'prefix': str(Path(sys.prefix).absolute()),",
            "    'purelib': str(Path(sysconfig.get_path('purelib')).absolute()),",
            "    'scripts': str(scripts),",
            "}",
            "print(json.dumps(receipt, sort_keys=True))",
        )
    )


def _run_observed(
    argv: list[str],
    *,
    cwd: str,
    env: dict[str, str],
    timeout_seconds: int,
    label: str,
    observations: list[dict[str, Any]],
) -> subprocess.CompletedProcess[str]:
    """Run one measured child and retain its full output before interpreting it."""
    result = subprocess.run(  # noqa: S603 -- callers pin the executable and every argument.
        argv,
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    observations.append(
        {
            "label": label,
            "argv": argv,
            "cwd": cwd,
            "env": dict(sorted(env.items())),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    if result.returncode:
        raise WorkerCommandError(f"{label} exited with {result.returncode}", observations.copy())
    return result


def _worker_path(value: object, label: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value:
        raise WorkerMountError(f"{label} must be an absolute canonical POSIX path")
    path = PurePosixPath(value)
    if (
        not path.is_absolute()
        or path == PurePosixPath("/")
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise WorkerMountError(f"{label} must be an absolute canonical POSIX path")
    return path


def _relative_worker(value: object, label: str) -> PurePosixPath:
    if type(value) is not str or not value or "\\" in value:
        raise WorkerMountError(f"{label} must be a canonical relative POSIX path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise WorkerMountError(f"{label} must be a canonical relative POSIX path")
    return path


def _profile_component(value: object) -> str:
    """Return the one safe directory component reserved for a profile prefix."""
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) is None:
        raise WorkerMountError("profile identity is not a safe prefix component")
    return value


def _host_path(value: object, label: str, *, must_exist: bool = True) -> Path:
    if (type(value) is not str and not isinstance(value, Path)) or not value:
        raise WorkerMountError(f"{label} must be an absolute canonical host path")
    supplied_text = str(value)
    supplied = value if isinstance(value, Path) else Path(value)
    if not supplied.is_absolute() or ".." in supplied.parts or str(supplied) != supplied_text:
        raise WorkerMountError(f"{label} must be an absolute canonical host path")
    current = Path(supplied.anchor)
    for component in supplied.parts[1:]:
        current = current / component
        try:
            info = current.lstat()
        except FileNotFoundError:
            if not must_exist:
                break
            raise WorkerMountError(f"{label} does not exist: {current}") from None
        if stat.S_ISLNK(info.st_mode):
            raise WorkerMountError(f"{label} traverses a symbolic link: {current}")
    if must_exist:
        try:
            resolved = supplied.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise WorkerMountError(f"{label} cannot be resolved") from error
        if resolved != supplied or not resolved.is_dir():
            raise WorkerMountError(f"{label} must be a regular directory")
    return supplied


def validate_runtime_contract(value: object) -> dict[str, Any]:
    """Validate the measured, immutable Linux runtime profile expected by Q2."""
    if type(value) is not dict or set(value) != {
        "schema",
        "docker",
        "image",
        "isolation",
        "worker",
        "installer",
        "resources",
    }:
        raise WorkerMountError("worker runtime contract has an unsupported shape")
    if value.get("schema") != RUNTIME_SCHEMA:
        raise WorkerMountError("worker runtime contract schema is unsupported")
    docker = value.get("docker")
    if type(docker) is not dict or set(docker) != {"config_path", "context"}:
        raise WorkerMountError("worker Docker endpoint contract is malformed")
    config_path = docker.get("config_path")
    if (
        type(config_path) is not str
        or not Path(config_path).is_absolute()
        or ".." in Path(config_path).parts
        or type(docker.get("context")) is not str
        or not docker["context"]
    ):
        raise WorkerMountError("worker Docker endpoint is not explicitly identified")
    resources = value.get("resources")
    if type(resources) is not dict or set(resources) != {
        "memory_bytes",
        "memory_swap_bytes",
        "nano_cpus",
    }:
        raise WorkerMountError("worker resource limits are malformed")
    if any(type(limit) is not int or limit <= 0 for limit in resources.values()):
        raise WorkerMountError("worker resource limits must be positive integers")
    if resources["memory_swap_bytes"] != resources["memory_bytes"]:
        raise WorkerMountError("Q2 worker swap must remain disabled")
    image = value.get("image")
    if type(image) is not dict or set(image) != {"reference", "image_id"}:
        raise WorkerMountError("worker image contract is malformed")
    if (
        type(image.get("reference")) is not str
        or "@sha256:" not in image["reference"]
        or _SHA256_IMAGE.fullmatch(image.get("image_id", "")) is None
        or not image["reference"].endswith(image["image_id"])
    ):
        raise WorkerMountError("worker image is not pinned to its exact digest")
    isolation = value.get("isolation")
    if type(isolation) is not dict or set(isolation) != {
        "read_only_rootfs",
        "network_mode",
        "persistent_volumes",
        "tmpfs_destinations",
    }:
        raise WorkerMountError("worker isolation contract is malformed")
    if isolation.get("read_only_rootfs") is not True or isolation.get("network_mode") != "none":
        raise WorkerMountError("Q2 worker requires a read-only root and disabled network")
    volumes = isolation.get("persistent_volumes")
    expected_volumes = {
        ("e02-local-uv-env", "/scratch"),
        ("e02-local-uv-pythons", "/opt/uv-python"),
    }
    if type(volumes) is not list:
        raise WorkerMountError("worker dependency volumes are malformed")
    observed_volumes: list[tuple[str, str]] = []
    for row in volumes:
        if type(row) is not dict or set(row) != {"name", "destination", "read_only"}:
            raise WorkerMountError("worker dependency volume row is malformed")
        name = row.get("name")
        destination = _worker_path(row.get("destination"), "volume destination")
        if type(name) is not str or not name or row.get("read_only") is not True:
            raise WorkerMountError("worker dependency volumes must be named and read-only")
        observed_volumes.append((name, destination.as_posix()))
    if (
        len(observed_volumes) != len(set(observed_volumes))
        or set(observed_volumes) != expected_volumes
    ):
        raise WorkerMountError("worker dependency volume set differs from the measured profile")
    tmpfs = isolation.get("tmpfs_destinations")
    if type(tmpfs) is not list or tmpfs != [_WORKER_TMP.as_posix()]:
        raise WorkerMountError("worker temporary storage must be one isolated /tmp mount")
    _worker_path(tmpfs[0], "tmpfs destination")
    worker = value.get("worker")
    if type(worker) is not dict or set(worker) != {
        "platform_system",
        "sys_platform",
        "machine",
        "python_executable",
        "python_realpath",
        "python_version",
        "dependency_site",
        "pytest_origin",
    }:
        raise WorkerMountError("worker interpreter contract is malformed")
    if (
        worker.get("platform_system") != "Linux"
        or worker.get("sys_platform") != "linux"
        or worker.get("machine") != "aarch64"
        or worker.get("python_version") != [3, 14, 0]
    ):
        raise WorkerMountError("worker interpreter platform/version differs from measurement")
    for key in ("python_executable", "python_realpath", "dependency_site", "pytest_origin"):
        _worker_path(worker.get(key), f"worker {key}")
    if not PurePosixPath(worker["dependency_site"]).is_relative_to("/scratch"):
        raise WorkerMountError("worker dependency site must stay in the read-only env volume")
    if not PurePosixPath(worker["pytest_origin"]).is_relative_to(worker["dependency_site"]):
        raise WorkerMountError("worker pytest origin is outside the selected dependency site")
    if not PurePosixPath(worker["python_realpath"]).is_relative_to("/opt/uv-python"):
        raise WorkerMountError("worker interpreter is outside the read-only Python volume")
    installer = value.get("installer")
    if type(installer) is not dict or set(installer) != {"name", "path", "version", "sha256"}:
        raise WorkerMountError("worker installer identity is malformed")
    if (
        installer.get("name") != "uv"
        or installer.get("version") != "0.9.21"
        or _worker_path(installer.get("path"), "worker installer path").as_posix()
        != "/usr/local/bin/uv"
    ):
        raise WorkerMountError("worker installer differs from the measured supported recipe")
    _digest(installer.get("sha256"), "worker installer SHA-256")
    return value


def validate_mount_map(
    value: object,
    *,
    expected_source: dict[str, str],
    expected_plan_sha256: str,
    expected_profile: str,
    expected_artifact_sha256: str,
    expected_node_ids_sha256: str,
    expected_runtime_contract_sha256: str,
    host_roots_must_exist: bool = True,
) -> dict[str, Any]:
    """Validate exact, non-overlapping host/container prefixes for one partition."""
    if type(value) is not dict or set(value) != {
        "schema",
        "source",
        "plan_sha256",
        "profile",
        "executor",
        "artifact_sha256",
        "node_ids_sha256",
        "runtime_contract_sha256",
        "mounts",
    }:
        raise WorkerMountError("worker mount map has an unsupported shape")
    if (
        value.get("schema") != MOUNT_MAP_SCHEMA
        or value.get("source") != expected_source
        or value.get("plan_sha256") != expected_plan_sha256
        or value.get("profile") != expected_profile
        or value.get("executor") != "linux-worker"
        or value.get("artifact_sha256") != expected_artifact_sha256
        or value.get("node_ids_sha256") != expected_node_ids_sha256
        or value.get("runtime_contract_sha256") != expected_runtime_contract_sha256
    ):
        raise WorkerMountError("worker mount map is stale or belongs to another partition")
    _profile_component(value.get("profile"))
    _profile_component(expected_profile)
    for key in ("plan_sha256", "artifact_sha256", "node_ids_sha256", "runtime_contract_sha256"):
        _digest(value.get(key), f"worker mount map {key}")
    mounts = value.get("mounts")
    if type(mounts) is not list or len(mounts) != len(_ROLE_ACCESS):
        raise WorkerMountError("worker mount map omits a required prefix")
    host_roots: dict[str, Path] = {}
    worker_roots: dict[str, PurePosixPath] = {}
    observed_roles: list[str] = []
    for row in mounts:
        if type(row) is not dict or set(row) != {
            "role",
            "host_root",
            "worker_root",
            "access",
        }:
            raise WorkerMountError("worker mount prefix row has an unsupported shape")
        role = row.get("role")
        if type(role) is not str or role not in _ROLE_ACCESS:
            raise WorkerMountError("worker mount prefix uses an unapproved role")
        if row.get("access") != _ROLE_ACCESS[role]:
            raise WorkerMountError(f"worker {role} mount has the wrong access mode")
        host_root = _host_path(
            row.get("host_root"),
            f"host {role} root",
            must_exist=host_roots_must_exist,
        )
        worker_root = _worker_path(row.get("worker_root"), f"worker {role} root")
        if any(
            worker_root == forbidden or worker_root.is_relative_to(forbidden)
            for forbidden in _FORBIDDEN_WORKER_ROOTS
        ):
            raise WorkerMountError(f"worker {role} prefix aliases a dependency or temporary volume")
        observed_roles.append(role)
        host_roots[role] = host_root
        worker_roots[role] = worker_root
    if observed_roles != sorted(_ROLE_ACCESS):
        raise WorkerMountError("worker mount roles must be sorted, unique, and complete")
    for role, root in host_roots.items():
        for other_role, other_root in host_roots.items():
            if role != other_role and (
                root == other_root
                or root.is_relative_to(other_root)
                or other_root.is_relative_to(root)
            ):
                raise WorkerMountError("host mount prefixes overlap")
    for role, root in worker_roots.items():
        for other_role, other_root in worker_roots.items():
            if role != other_role and (
                root == other_root
                or root.is_relative_to(other_root)
                or other_root.is_relative_to(root)
            ):
                raise WorkerMountError("worker mount prefixes overlap")
    return value


def build_mount_map(
    *,
    source: dict[str, str],
    plan_sha256: str,
    profile: str,
    artifact_sha256: str,
    node_ids_sha256: str,
    runtime_contract: dict[str, Any],
    host_roots: dict[str, str | Path],
    worker_roots: dict[str, str],
) -> dict[str, Any]:
    """Build the exact four-prefix map used by one selected Linux partition."""
    contract = validate_runtime_contract(runtime_contract)
    if set(host_roots) != set(_ROLE_ACCESS) or set(worker_roots) != set(_ROLE_ACCESS):
        raise WorkerMountError("worker map construction requires every exact mount role")
    runtime_sha = sha256_bytes(canonical_json_bytes(contract))
    value = {
        "schema": MOUNT_MAP_SCHEMA,
        "source": dict(source),
        "plan_sha256": _digest(plan_sha256, "worker composite plan SHA-256"),
        "profile": profile,
        "executor": "linux-worker",
        "artifact_sha256": _digest(artifact_sha256, "worker profile artifact SHA-256"),
        "node_ids_sha256": _digest(node_ids_sha256, "worker node-ID SHA-256"),
        "runtime_contract_sha256": runtime_sha,
        "mounts": [
            {
                "role": role,
                "host_root": str(host_roots[role]),
                "worker_root": worker_roots[role],
                "access": _ROLE_ACCESS[role],
            }
            for role in sorted(_ROLE_ACCESS)
        ],
    }
    return validate_mount_map(
        value,
        expected_source=source,
        expected_plan_sha256=plan_sha256,
        expected_profile=profile,
        expected_artifact_sha256=artifact_sha256,
        expected_node_ids_sha256=node_ids_sha256,
        expected_runtime_contract_sha256=runtime_sha,
    )


def verify_worker_visible_tree(
    mount_map: dict[str, Any],
    *,
    role: str,
    expected_files: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify the exact bytes visible at one bind mount from inside the worker."""
    if role not in {"inputs", "artifacts"}:
        raise WorkerMountError("visible member verification is limited to read-only mounts")
    if type(expected_files) is not list or not expected_files:
        raise WorkerMountError(f"{role} worker mount requires a complete nonempty member set")
    row = next((item for item in mount_map["mounts"] if item["role"] == role), None)
    if row is None:
        raise WorkerMountError(f"worker mount map omits {role}")
    root = Path(_worker_path(row["worker_root"], f"{role} worker root").as_posix())
    if root.is_symlink() or not root.is_dir():
        raise WorkerMountError(f"worker {role} bind is absent or symlinked")
    expected: dict[str, tuple[int, str]] = {}
    for item in expected_files:
        if type(item) is not dict or set(item) != {"path", "bytes", "sha256"}:
            raise WorkerMountError(f"{role} expected member record is malformed")
        relative = _relative_worker(item["path"], f"{role} member path")
        if type(item["bytes"]) is not int or item["bytes"] < 0:
            raise WorkerMountError(f"{role} expected member size is malformed")
        expected[relative] = (item["bytes"], _digest(item["sha256"], f"{role} member SHA-256"))
    if len(expected) != len(expected_files):
        raise WorkerMountError(f"{role} expected member set repeats a path")
    observed: dict[str, tuple[int, str]] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in (*dirnames, *filenames):
            candidate = current / name
            info = candidate.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise WorkerMountError(f"worker {role} bind contains a symlink")
            relative = candidate.relative_to(root).as_posix()
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode):
                raise WorkerMountError(f"worker {role} bind contains a special member")
            raw = candidate.read_bytes()
            observed[relative] = (len(raw), sha256_bytes(raw))
    if observed != expected:
        raise WorkerMountError(
            f"worker {role} visible member set/bytes differ: "
            f"missing={sorted(set(expected) - set(observed))} "
            f"unexpected={sorted(set(observed) - set(expected))}"
        )
    return {
        "role": role,
        "member_count": len(observed),
        "members_sha256": sha256_bytes(canonical_json_bytes(expected_files)),
    }


def worker_path_to_host(
    value: object,
    mount_map: dict[str, Any],
    *,
    role: str,
    must_exist: bool = True,
    allow_leaf_symlink: bool = False,
) -> Path:
    """Translate one worker path only through its exact role-owned bind prefix."""
    if role not in _ROLE_ACCESS:
        raise WorkerMountError("worker path translation requested an unapproved role")
    path = _worker_path(value, "worker path")
    row = next((item for item in mount_map["mounts"] if item["role"] == role), None)
    if row is None:
        raise WorkerMountError(f"worker path mapping omits {role}")
    root = PurePosixPath(row["worker_root"])
    if not path.is_relative_to(root):
        raise WorkerMountError(f"worker path is outside its {role} prefix")
    relative = path.relative_to(root)
    host_root = Path(row["host_root"])
    candidate = host_root.joinpath(*relative.parts)
    if must_exist:
        current = host_root
        for index, part in enumerate(relative.parts):
            current = current / part
            try:
                info = current.lstat()
            except OSError as error:
                raise WorkerMountError(f"mapped worker path is missing: {path}") from error
            if stat.S_ISLNK(info.st_mode) and not (
                allow_leaf_symlink and index == len(relative.parts) - 1
            ):
                raise WorkerMountError(f"mapped worker path traverses a symlink: {path}")
        if not candidate.is_symlink():
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, RuntimeError) as error:
                raise WorkerMountError(f"mapped worker path cannot be resolved: {path}") from error
            if not resolved.is_relative_to(host_root) or resolved != candidate:
                raise WorkerMountError(f"mapped worker path escaped its host {role} prefix")
    return candidate


def verify_worker_evidence_ref(
    ref: object,
    mount_map: dict[str, Any],
    *,
    role: str,
    label: str,
) -> dict[str, Any]:
    """Read and hash one worker receipt only through its exact mapped prefix."""
    if type(ref) is not dict or set(ref) != {"path", "sha256"}:
        raise WorkerMountError(f"{label} worker evidence reference is malformed")
    expected_digest = _digest(ref.get("sha256"), f"{label} worker evidence digest")
    host_path = worker_path_to_host(ref.get("path"), mount_map, role=role)
    info = host_path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise WorkerMountError(f"{label} mapped worker evidence is not a regular file")
    raw = host_path.read_bytes()
    observed_digest = sha256_bytes(raw)
    if observed_digest != expected_digest:
        raise WorkerMountError(f"{label} mapped worker evidence changed or was replayed")
    worker_path = _worker_path(ref["path"], f"{label} worker evidence path")
    return {
        "role": role,
        "worker_path": worker_path.as_posix(),
        "host_path": str(host_path),
        "bytes": len(raw),
        "sha256": observed_digest,
    }


def host_path_to_worker(value: str | Path, mount_map: dict[str, Any], *, role: str) -> str:
    """Translate one host path only through its exact role-owned bind prefix."""
    if role not in _ROLE_ACCESS:
        raise WorkerMountError("host path translation requested an unapproved role")
    path = _host_path(str(value), "host path", must_exist=False)
    row = next((item for item in mount_map["mounts"] if item["role"] == role), None)
    if row is None:
        raise WorkerMountError(f"worker path mapping omits {role}")
    root = Path(row["host_root"])
    if path != root and not path.is_relative_to(root):
        raise WorkerMountError(f"host path is outside its {role} prefix")
    relative = path.relative_to(root)
    return PurePosixPath(row["worker_root"], *relative.parts).as_posix()


def verify_mapped_tree(
    mount_map: dict[str, Any],
    *,
    role: str,
    expected_files: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify every member and byte in one read-only host input/artifact mount."""
    if role not in {"inputs", "artifacts"}:
        raise WorkerMountError("complete member verification is limited to read-only mounts")
    if type(expected_files) is not list or not expected_files:
        raise WorkerMountError(f"{role} mount requires a nonempty complete member set")
    expected: dict[str, tuple[int, str]] = {}
    for row in expected_files:
        if type(row) is not dict or set(row) != {"path", "bytes", "sha256"}:
            raise WorkerMountError(f"{role} member receipt has an unsupported shape")
        relative = row.get("path")
        if type(relative) is not str or not relative or "\\" in relative:
            raise WorkerMountError(f"{role} member path must be relative POSIX")
        parsed = PurePosixPath(relative)
        if (
            parsed.is_absolute()
            or parsed.as_posix() != relative
            or not parsed.parts
            or any(part in {"", ".", ".."} for part in parsed.parts)
        ):
            raise WorkerMountError(f"{role} member path is not canonical")
        size = row.get("bytes")
        digest = _digest(row.get("sha256"), f"{role} {relative} digest")
        if type(size) is not int or size < 0 or relative in expected:
            raise WorkerMountError(f"{role} member size or path is invalid")
        expected[relative] = (size, digest)
    if [row["path"] for row in expected_files] != sorted(expected):
        raise WorkerMountError(f"{role} complete member set must be sorted by path")
    mount = next((row for row in mount_map["mounts"] if row["role"] == role), None)
    if mount is None:
        raise WorkerMountError(f"worker mount map omits {role}")
    root = Path(mount["host_root"])
    observed: dict[str, tuple[int, str]] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in sorted(dirnames):
            path = current / name
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise WorkerMountError(f"{role} input contains a symlink or special directory")
        for name in sorted(filenames):
            path = current / name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise WorkerMountError(f"{role} input contains a symlink or special file")
            relative = path.relative_to(root).as_posix()
            raw = path.read_bytes()
            observed[relative] = (len(raw), sha256_bytes(raw))
    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        unexpected = sorted(set(observed) - set(expected))
        changed = sorted(
            key for key in set(expected) & set(observed) if expected[key] != observed[key]
        )
        raise WorkerMountError(
            f"{role} actual member set/bytes differ: missing={missing} "
            f"unexpected={unexpected} changed={changed}"
        )
    return {
        "role": role,
        "member_count": len(observed),
        "members_sha256": sha256_bytes(canonical_json_bytes(expected_files)),
    }


def validate_worker_container(
    inspect_value: object,
    runtime_contract: dict[str, Any],
    mount_map: dict[str, Any],
) -> dict[str, str]:
    """Recompute container image, isolation, and every actual mount from Docker inspect."""
    contract = validate_runtime_contract(runtime_contract)
    if type(inspect_value) is list:
        if len(inspect_value) != 1:
            raise WorkerMountError("Docker inspect must identify exactly one worker container")
        container = inspect_value[0]
    else:
        container = inspect_value
    if type(container) is not dict:
        raise WorkerMountError("Docker inspect result is not an object")
    config = container.get("Config")
    state = container.get("State")
    host = container.get("HostConfig")
    if type(config) is not dict or type(state) is not dict or type(host) is not dict:
        raise WorkerMountError("Docker inspect omits container identity or isolation")
    image = contract["image"]
    isolation = contract["isolation"]
    if (
        config.get("Image") != image["reference"]
        or container.get("Image") != image["image_id"]
        or state.get("Running") is not True
        or host.get("ReadonlyRootfs") is not isolation["read_only_rootfs"]
        or host.get("NetworkMode") != isolation["network_mode"]
        or host.get("Privileged") is not False
        or host.get("AutoRemove") is not False
        or host.get("CapAdd") not in (None, [])
        or host.get("Memory") != contract["resources"]["memory_bytes"]
        or host.get("MemorySwap") != contract["resources"]["memory_swap_bytes"]
        or host.get("NanoCpus") != contract["resources"]["nano_cpus"]
    ):
        raise WorkerMountError("actual worker image or isolation differs from its contract")
    raw_mounts = container.get("Mounts")
    if type(raw_mounts) is not list:
        raise WorkerMountError("Docker inspect omits the actual mount list")
    expected: dict[str, tuple[str, str, str, bool]] = {}
    for row in isolation["persistent_volumes"]:
        expected[row["destination"]] = (
            "volume",
            row["name"],
            "read-only",
            False,
        )
    for row in mount_map["mounts"]:
        expected[row["worker_root"]] = (
            "bind",
            row["host_root"],
            row["access"],
            row["access"] == "read-write",
        )
    for destination in isolation["tmpfs_destinations"]:
        expected[destination] = ("tmpfs", "", "read-write", True)
    observed: dict[str, tuple[str, str, str, bool]] = {}
    for row in raw_mounts:
        if type(row) is not dict:
            raise WorkerMountError("Docker inspect mount row is malformed")
        destination = _worker_path(row.get("Destination"), "actual mount destination").as_posix()
        mount_type = row.get("Type")
        rw = row.get("RW")
        if type(rw) is not bool or destination in observed:
            raise WorkerMountError("Docker inspect duplicates or malforms a mount")
        if mount_type == "volume":
            name = row.get("Name")
            access = "read-write" if rw else "read-only"
        elif mount_type == "bind":
            name = row.get("Source")
            if type(name) is not str or not Path(name).is_absolute():
                raise WorkerMountError("Docker inspect bind source is not an absolute host path")
            name = str(Path(name).resolve(strict=True))
            access = "read-write" if rw else "read-only"
        elif mount_type == "tmpfs":
            name = ""
            access = "read-write" if rw else "read-only"
        else:
            raise WorkerMountError(f"Docker inspect uses an unsupported mount type: {mount_type}")
        observed[destination] = (mount_type, name, access, rw)
    if observed != expected:
        raise WorkerMountError("actual worker mount set/source/access differs from exact mapping")
    container_id = container.get("Id")
    if type(container_id) is not str or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
        raise WorkerMountError("Docker inspect container identity is not a full container ID")
    return {"container_id": container_id, "image_id": image["image_id"]}


_WORKER_INSPECT_FIELDS = (
    ("Id", "{{.Id}}"),
    ("Image", "{{.Image}}"),
    ("Config.Image", "{{.Config.Image}}"),
    ("State.Running", "{{.State.Running}}"),
    ("HostConfig.ReadonlyRootfs", "{{.HostConfig.ReadonlyRootfs}}"),
    ("HostConfig.NetworkMode", "{{.HostConfig.NetworkMode}}"),
    ("HostConfig.Privileged", "{{.HostConfig.Privileged}}"),
    ("HostConfig.AutoRemove", "{{.HostConfig.AutoRemove}}"),
    ("HostConfig.CapAdd", "{{json .HostConfig.CapAdd}}"),
    ("HostConfig.Memory", "{{.HostConfig.Memory}}"),
    ("HostConfig.MemorySwap", "{{.HostConfig.MemorySwap}}"),
    ("HostConfig.NanoCpus", "{{.HostConfig.NanoCpus}}"),
    ("Mounts", "{{json .Mounts}}"),
)


def worker_container_inspect_argv(
    runtime_contract: dict[str, Any], container_id: str
) -> list[dict[str, Any]]:
    """Build exact field-limited Docker inspect commands for one measured container.

    The query list deliberately omits environment variables and the rest of
    Docker's container configuration. Callers retain each complete command
    output in the binding receipt for independent readback.
    """
    contract = validate_runtime_contract(runtime_contract)
    if type(container_id) is not str or re.fullmatch(r"[0-9a-f]{64}", container_id) is None:
        raise WorkerMountError("worker inspect target must be one full container ID")
    base = [
        "docker",
        "--config",
        contract["docker"]["config_path"],
        "--context",
        contract["docker"]["context"],
        "inspect",
    ]
    return [
        {
            "field": field,
            "argv": [*base, "--format", template, container_id],
        }
        for field, template in _WORKER_INSPECT_FIELDS
    ]


def validate_worker_container_inspect_receipt(
    value: object,
    runtime_contract: dict[str, Any],
    mount_map: dict[str, Any],
    *,
    expected_container_id: str,
) -> dict[str, str]:
    """Recompute the worker inspection from exact, retained field-only outputs."""
    contract = validate_runtime_contract(runtime_contract)
    expected_commands = worker_container_inspect_argv(contract, expected_container_id)
    if type(value) is not dict or set(value) != {"schema", "commands"}:
        raise WorkerMountError("worker inspect evidence has an unsupported shape")
    if value.get("schema") != "policyos.e02.q2.worker-container-inspect.v1":
        raise WorkerMountError("worker inspect evidence has an unsupported version")
    commands = value.get("commands")
    if type(commands) is not list or len(commands) != len(expected_commands):
        raise WorkerMountError("worker inspect evidence omits a selected field query")
    observed: dict[str, str] = {}
    for row, expected in zip(commands, expected_commands, strict=True):
        if type(row) is not dict or set(row) != {
            "field",
            "argv",
            "returncode",
            "stdout",
            "stderr",
        }:
            raise WorkerMountError("worker inspect command receipt is malformed")
        if (
            row.get("field") != expected["field"]
            or row.get("argv") != expected["argv"]
            or type(row.get("returncode")) is not int
            or row["returncode"] != 0
            or type(row.get("stdout")) is not str
            or type(row.get("stderr")) is not str
            or row["stderr"]
        ):
            raise WorkerMountError("worker inspect command/output differs from the exact query")
        observed[expected["field"]] = row["stdout"].strip()

    def json_value(field: str) -> object:
        try:
            return json.loads(observed[field])
        except (KeyError, json.JSONDecodeError) as error:
            raise WorkerMountError(f"worker inspect {field} output is not JSON") from error

    try:
        mounts = json.loads(observed["Mounts"])
    except (KeyError, json.JSONDecodeError) as error:
        raise WorkerMountError("worker inspect Mounts output is not JSON") from error
    inspect_value = {
        "Id": observed.get("Id"),
        "Image": observed.get("Image"),
        "Config": {"Image": observed.get("Config.Image")},
        "State": {"Running": json_value("State.Running")},
        "HostConfig": {
            "ReadonlyRootfs": json_value("HostConfig.ReadonlyRootfs"),
            "NetworkMode": observed.get("HostConfig.NetworkMode"),
            "Privileged": json_value("HostConfig.Privileged"),
            "AutoRemove": json_value("HostConfig.AutoRemove"),
            "CapAdd": json_value("HostConfig.CapAdd"),
            "Memory": json_value("HostConfig.Memory"),
            "MemorySwap": json_value("HostConfig.MemorySwap"),
            "NanoCpus": json_value("HostConfig.NanoCpus"),
        },
        "Mounts": mounts,
    }
    identity = validate_worker_container(inspect_value, contract, mount_map)
    if identity["container_id"] != expected_container_id:
        raise WorkerMountError("worker inspect returned a different container identity")
    return identity


def validate_worker_probe(
    probe: object,
    runtime_contract: dict[str, Any],
    mount_map: dict[str, Any],
    *,
    container_identity: dict[str, str],
) -> dict[str, Any]:
    """Verify the worker's actual interpreter, dependencies, and selected prefix."""
    contract = validate_runtime_contract(runtime_contract)
    if type(probe) is not dict or set(probe) != {
        "schema",
        "container_id",
        "image_id",
        "container_hostname",
        "platform_system",
        "sys_platform",
        "machine",
        "python",
        "python_realpath",
        "python_version",
        "sys_prefix",
        "purelib",
        "scripts",
        "dependency_site",
        "pytest_origin",
        "sys_path",
        "installer_path",
        "installer_version",
        "installer_sha256",
    }:
        raise WorkerMountError("worker runtime probe has an unsupported shape")
    expected = contract["worker"]
    target_mount = next(row for row in mount_map["mounts"] if row["role"] == "profile-prefix")
    if (
        probe.get("schema") != WORKER_PROBE_SCHEMA
        or probe.get("container_id") != container_identity.get("container_id")
        or probe.get("image_id") != container_identity.get("image_id")
        or type(probe.get("container_hostname")) is not str
        or not container_identity["container_id"].startswith(probe["container_hostname"])
        or probe.get("platform_system") != expected["platform_system"]
        or probe.get("sys_platform") != expected["sys_platform"]
        or probe.get("machine") != expected["machine"]
        or probe.get("python_realpath") != expected["python_realpath"]
        or probe.get("python_version") != expected["python_version"]
        or probe.get("dependency_site") != expected["dependency_site"]
        or probe.get("pytest_origin") != expected["pytest_origin"]
        or probe.get("installer_path") != contract["installer"]["path"]
        or probe.get("installer_version") != contract["installer"]["version"]
        or probe.get("installer_sha256") != contract["installer"]["sha256"]
    ):
        raise WorkerMountError(
            "worker runtime probe differs from its measured interpreter contract"
        )
    for field in ("python", "sys_prefix", "purelib", "scripts"):
        _worker_path(probe.get(field), f"worker probe {field}")
    prefix = _worker_path(probe["sys_prefix"], "worker sys.prefix")
    target_root = _worker_path(target_mount["worker_root"], "profile prefix mount")
    expected_prefix = target_root / _profile_component(mount_map["profile"])
    if prefix != expected_prefix:
        raise WorkerMountError("worker sys.prefix differs from the fresh selected-profile prefix")
    purelib = _worker_path(probe["purelib"], "worker purelib")
    scripts = _worker_path(probe["scripts"], "worker scripts")
    if not purelib.is_relative_to(prefix) or not scripts.is_relative_to(prefix):
        raise WorkerMountError("worker purelib/scripts escaped the selected profile prefix")
    if probe["python"] != (prefix / "bin" / "python").as_posix():
        raise WorkerMountError("worker Python executable is not the selected profile interpreter")
    raw_sys_path = probe.get("sys_path")
    if type(raw_sys_path) is not list or not raw_sys_path:
        raise WorkerMountError("worker runtime probe omits actual sys.path")
    sys_path = [_worker_path(path, "worker sys.path entry") for path in raw_sys_path]
    if purelib not in sys_path or PurePosixPath(expected["dependency_site"]) not in sys_path:
        raise WorkerMountError("worker sys.path omits selected purelib or dependency site")
    if any(path.is_relative_to(target_root) and path != purelib for path in sys_path):
        raise WorkerMountError("worker sys.path includes an unselected profile-prefix path")
    if sys_path.index(purelib) >= sys_path.index(PurePosixPath(expected["dependency_site"])):
        raise WorkerMountError("worker dependency site precedes the selected installed prefix")
    for role in ("inputs", "artifacts", "receipts"):
        worker_root = _worker_path(
            next(row["worker_root"] for row in mount_map["mounts"] if row["role"] == role),
            f"{role} mount root",
        )
        if any(path == worker_root or path.is_relative_to(worker_root) for path in sys_path):
            raise WorkerMountError(f"worker sys.path contains the {role} input/output mount")
    return dict(probe)


def worker_probe_program() -> str:
    """Return a read-only worker-side runtime probe for the selected prefix."""
    return "\n".join(
        (
            "import hashlib, json, os, platform, subprocess, sys, sysconfig",
            "from pathlib import Path",
            "sys.dont_write_bytecode = True",
            "import pytest",
            "uv = Path('/usr/local/bin/uv')",
            "uv_version = subprocess.check_output([str(uv), '--version'], text=True).strip()",
            "real = lambda value: str(Path(value).resolve(strict=True))",
            "print(json.dumps({",
            "    'schema': '" + WORKER_PROBE_SCHEMA + "',",
            "    'container_id': os.environ['E02_Q2_CONTAINER_ID'],",
            "    'image_id': os.environ['E02_Q2_IMAGE_ID'],",
            "    'container_hostname': os.environ.get('HOSTNAME', ''),",
            "    'platform_system': platform.system(),",
            "    'sys_platform': sys.platform,",
            "    'machine': platform.machine(),",
            "    'python': str(Path(sys.executable).absolute()),",
            "    'python_realpath': real(sys.executable),",
            "    'python_version': list(sys.version_info[:3]),",
            "    'sys_prefix': str(Path(sys.prefix).absolute()),",
            "    'purelib': str(Path(sysconfig.get_path('purelib')).absolute()),",
            "    'scripts': str(Path(sysconfig.get_path('scripts')).absolute()),",
            "    'dependency_site': os.environ['E02_Q2_DEPENDENCY_SITE'],",
            "    'pytest_origin': real(pytest.__file__),",
            "    'sys_path': sys.path,",
            "    'installer_path': str(uv),",
            "    'installer_version': uv_version.removeprefix('uv '),",
            "    'installer_sha256': hashlib.sha256(uv.read_bytes()).hexdigest(),",
            "}, sort_keys=True))",
        )
    )


def _snapshot_prefix_worker(prefix_value: str, python_realpath: str) -> dict[str, Any]:
    """Capture a complete worker-local profile prefix before or after consumption."""
    prefix = _worker_path(prefix_value, "worker profile prefix")
    root = Path(prefix.as_posix())
    real_python = _worker_path(python_realpath, "worker Python realpath")
    if root.is_symlink() or not root.is_dir():
        raise WorkerMountError("worker profile prefix is absent or symlinked")
    files: list[dict[str, Any]] = []
    directories: list[str] = []
    allowed_links = {"bin/python", "bin/python3", "bin/python3.14"}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in sorted(dirnames):
            path = current / name
            info = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise WorkerMountError(f"worker prefix has an unsafe directory: {relative}")
            directories.append(relative)
        for name in sorted(filenames):
            path = current / name
            info = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISREG(info.st_mode):
                raw = path.read_bytes()
                files.append(
                    {
                        "path": relative,
                        "kind": "regular",
                        "bytes": len(raw),
                        "sha256": sha256_bytes(raw),
                        "mode": stat.S_IMODE(info.st_mode),
                    }
                )
            elif stat.S_ISLNK(info.st_mode) and relative in allowed_links:
                resolved = _worker_path(
                    path.resolve(strict=True).as_posix(), "resolved Python link"
                )
                if resolved != real_python:
                    raise WorkerMountError("worker prefix Python link resolves to another runtime")
                files.append(
                    {
                        "path": relative,
                        "kind": "symlink",
                        "target": os.readlink(path),
                        "resolved_worker_path": resolved.as_posix(),
                    }
                )
            else:
                raise WorkerMountError(f"worker prefix has an unsafe file or symlink: {relative}")
    files.sort(key=lambda row: row["path"])
    directories.sort()
    manifest = {
        "schema": "policyos.e02.q2.profile-prefix-snapshot.v1",
        "directories": directories,
        "files": files,
    }
    return {**manifest, "sha256": sha256_bytes(canonical_json_bytes(manifest))}


def execute_entrypoint_install(
    install_plan: dict[str, Any],
    *,
    expected_plan_sha256: str,
    runtime_contract: dict[str, Any],
    expected_distribution_name: str,
    expected_distribution_version: str,
    worker_cwd: str = _WORKER_TMP.as_posix(),
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    """Run the exact fresh-prefix/no-dependency install and return actual readback.

    This worker-side function is intentionally separate from host preparation.
    It is invoked only inside the measured container after the source/input and
    wheel trees have been verified and mounted read-only.
    """
    contract = validate_runtime_contract(runtime_contract)
    if (
        type(install_plan) is not dict
        or install_plan.get("schema") != ENTRYPOINT_INSTALL_SCHEMA
        or install_plan.get("plan_sha256") != _digest(expected_plan_sha256, "plan SHA-256")
        or install_plan.get("runtime_contract_sha256")
        != sha256_bytes(canonical_json_bytes(contract))
        or install_plan.get("runtime_contract") != contract
        or install_plan.get("installer_path") != contract["installer"]["path"]
        or install_plan.get("installer_sha256") != contract["installer"]["sha256"]
        or install_plan.get("installer_version") != contract["installer"]["version"]
    ):
        raise WorkerMountError("worker install plan is stale or uses another installer/runtime")
    prefix = _worker_path(install_plan.get("prefix"), "worker install prefix")
    prefix_mount = _worker_path(
        install_plan.get("profile_prefix_mount"), "worker profile-prefix mount"
    )
    expected_prefix = prefix_mount / _profile_component(install_plan.get("profile"))
    if prefix != expected_prefix:
        raise WorkerMountError("install prefix is not the selected profile's exact mount child")
    purelib = _worker_path(install_plan.get("purelib"), "worker install purelib")
    scripts = _worker_path(install_plan.get("scripts"), "worker install scripts")
    worker_workdir = _worker_path(worker_cwd, "worker install working directory")
    if worker_workdir != _WORKER_TMP:
        raise WorkerMountError("worker install commands must run in the isolated tmpfs")
    prefix_path = Path(prefix.as_posix())
    prefix_mount_path = Path(prefix_mount.as_posix())
    if (
        prefix_mount_path.is_symlink()
        or not prefix_mount_path.is_dir()
        or prefix_path.is_symlink()
        or prefix_path.exists()
    ):
        raise WorkerMountError("selected profile prefix must be a fresh absent child directory")
    prefix_path.mkdir(mode=0o700)
    installer_path = Path(install_plan["installer_path"])
    if installer_path.is_symlink() or not installer_path.is_file():
        raise WorkerMountError("measured worker installer is absent or symlinked")
    installer_raw = installer_path.read_bytes()
    if sha256_bytes(installer_raw) != contract["installer"]["sha256"]:
        raise WorkerMountError("worker installer binary differs from its measured source pin")
    preflight_outputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    clean_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": _WORKER_TMP.as_posix(),
        "TMPDIR": _WORKER_TMP.as_posix(),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "UV_NO_CONFIG": "1",
    }
    uv_result = _run_observed(
        [str(installer_path), "--version"],
        cwd=worker_workdir.as_posix(),
        env=clean_env,
        timeout_seconds=30,
        label="measured uv version",
        observations=preflight_outputs,
    )
    uv_version = uv_result.stdout.strip()
    if uv_version != "uv " + contract["installer"]["version"]:
        raise WorkerMountError("worker installer version differs from its measured source pin")
    wheel_path = _worker_path(install_plan.get("wheel_path"), "selected wheel path")
    wheel = Path(wheel_path.as_posix())
    if wheel.is_symlink() or not wheel.is_file():
        raise WorkerMountError("selected profile wheel is absent or symlinked")
    wheel_metadata = _selected_wheel_metadata(wheel, install_plan["artifact_sha256"])
    if (
        wheel_metadata != install_plan.get("wheel_metadata")
        or install_plan.get("wheel_metadata_sha256") != wheel_metadata["sha256"]
        or install_plan.get("distribution")
        != {
            "name": wheel_metadata["distribution_name"],
            "version": wheel_metadata["distribution_version"],
        }
        or install_plan.get("wheel_entry_points") != wheel_metadata["entry_points"]
    ):
        raise WorkerMountError("selected wheel metadata differs from the source-bound install plan")
    if (
        expected_distribution_name.casefold().replace("-", "_")
        != wheel_metadata["distribution_name"].casefold().replace("-", "_")
        or expected_distribution_version != wheel_metadata["distribution_version"]
    ):
        raise WorkerMountError("selected wheel identity differs from the expected profile artifact")
    commands = install_plan.get("commands")
    if type(commands) is not list or len(commands) != 2:
        raise WorkerMountError("worker install plan omits its two measured commands")
    expected_venv = [
        contract["worker"]["python_executable"],
        "-I",
        "-m",
        "venv",
        "--without-pip",
        prefix.as_posix(),
    ]
    expected_install = [
        contract["installer"]["path"],
        "pip",
        "install",
        "--offline",
        "--no-index",
        "--no-deps",
        "--no-cache",
        "--python",
        (prefix / "bin" / "python").as_posix(),
        wheel_path.as_posix(),
    ]
    if commands != [expected_venv, expected_install]:
        raise WorkerMountError("worker install argv differs from the reviewed offline recipe")
    for argv in commands[:1]:
        _run_observed(
            argv,
            cwd=worker_workdir.as_posix(),
            env=clean_env,
            timeout_seconds=timeout_seconds,
            label="fresh pip-free profile venv",
            observations=outputs,
        )
    purelib_path = Path(purelib.as_posix())
    scripts_path = Path(scripts.as_posix())
    python_path = Path((prefix / "bin" / "python").as_posix())
    if (
        purelib_path.is_symlink()
        or not purelib_path.is_dir()
        or scripts_path.is_symlink()
        or not scripts_path.is_dir()
        or not python_path.exists()
        or not python_path.is_file()
    ):
        raise WorkerMountError("fresh venv sysconfig paths are absent or symlinked")
    sysconfig_code = _venv_sysconfig_code()
    layout = _run_observed(
        [python_path.as_posix(), "-I", "-c", sysconfig_code],
        cwd=worker_workdir.as_posix(),
        env=clean_env,
        timeout_seconds=30,
        label="fresh venv sysconfig",
        observations=preflight_outputs,
    )
    layout_value = json.loads(layout.stdout)
    expected_layout = {
        "prefix": prefix.as_posix(),
        "purelib": purelib.as_posix(),
        "scripts": scripts.as_posix(),
        "executable": python_path.as_posix(),
        "realpath": contract["worker"]["python_realpath"],
    }
    if layout_value != expected_layout:
        raise WorkerMountError("fresh venv interpreter/sysconfig differs from exact worker mapping")
    bridge = install_plan["dependency_bridge"]
    bridge_path = _worker_path(bridge["path"], "dependency-site bridge").as_posix()
    if Path(bridge_path).exists() or Path(bridge_path).is_symlink():
        raise WorkerMountError("fresh dependency-site bridge path already exists")
    bridge_bytes = bridge["content_utf8"].encode("utf-8")
    if (
        len(bridge_bytes) != bridge["bytes"]
        or sha256_bytes(bridge_bytes) != bridge["sha256"]
        or bridge["content_utf8"]
        != _dependency_site_bridge_bytes(
            _worker_path(install_plan["dependency_site"], "dependency site")
        ).decode("utf-8")
    ):
        raise WorkerMountError("dependency-site bridge content differs from exact locked profile")
    bridge_fd = os.open(bridge_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    try:
        os.write(bridge_fd, bridge_bytes)
        os.fsync(bridge_fd)
    finally:
        os.close(bridge_fd)
    if Path(bridge_path).read_bytes() != bridge_bytes:
        raise WorkerMountError("dependency-site bridge readback differs after creation")
    entrypoint_name = install_plan["entrypoint"]["name"]
    script_path = (scripts / entrypoint_name).as_posix()
    script_exists_before_install = Path(script_path).exists() or Path(script_path).is_symlink()
    if script_exists_before_install:
        raise WorkerMountError("selected entrypoint exists before installing the selected wheel")
    _run_observed(
        expected_install,
        cwd=worker_workdir.as_posix(),
        env=clean_env,
        timeout_seconds=timeout_seconds,
        label="selected wheel install",
        observations=outputs,
    )
    receipt_code = _installed_wheel_readback_code(expected_distribution_name, entrypoint_name)
    readback = _run_observed(
        [python_path.as_posix(), "-I", "-c", receipt_code],
        cwd=worker_workdir.as_posix(),
        env=clean_env,
        timeout_seconds=30,
        label="installed wheel entrypoint readback",
        observations=preflight_outputs,
    )
    installed = json.loads(readback.stdout)
    expected_entrypoints = [
        {"group": group, "name": name, "value": value}
        for group, values in install_plan["wheel_entry_points"].items()
        for name, value in values.items()
    ]
    if (
        installed["name"].casefold().replace("-", "_")
        != expected_distribution_name.casefold().replace("-", "_")
        or installed["version"] != expected_distribution_version
        or installed["entries"]
        != sorted(expected_entrypoints, key=lambda row: (row["group"], row["name"]))
        or installed["meta_hashes"] != wheel_metadata["metadata_file_sha256"]
        or installed["metadata_sha256"]
        != sha256_bytes(canonical_json_bytes(wheel_metadata["metadata_file_sha256"]))
        or installed["script_path"] != script_path
        or installed["script_bytes"] <= 0
        or installed["script_mode"] & 0o111 == 0
        or installed["script_shebang"] != "#!" + python_path.as_posix()
        or installed["python"] != python_path.as_posix()
        or installed["prefix"] != prefix.as_posix()
        or installed["purelib"] != purelib.as_posix()
        or installed["scripts"] != scripts.as_posix()
    ):
        raise WorkerMountError("installer-generated entrypoint/distribution readback differs")
    probe_code = worker_probe_program()
    probe = _run_observed(
        [python_path.as_posix(), "-I", "-c", probe_code],
        cwd=worker_workdir.as_posix(),
        env={
            **clean_env,
            "E02_Q2_CONTAINER_ID": os.environ["E02_Q2_CONTAINER_ID"],
            "E02_Q2_IMAGE_ID": os.environ["E02_Q2_IMAGE_ID"],
            "E02_Q2_DEPENDENCY_SITE": install_plan["dependency_site"],
        },
        timeout_seconds=30,
        label="selected worker profile probe",
        observations=preflight_outputs,
    )
    probe_value = json.loads(probe.stdout)
    if (
        probe_value["sys_prefix"] != prefix.as_posix()
        or probe_value["purelib"] != purelib.as_posix()
    ):
        raise WorkerMountError("installed runtime probe does not resolve to selected prefix")
    return {
        "schema": ENTRYPOINT_INSTALL_SCHEMA,
        "source": install_plan["source"],
        "plan_sha256": install_plan["plan_sha256"],
        "profile": install_plan["profile"],
        "artifact_sha256": install_plan["artifact_sha256"],
        "runtime_contract_sha256": install_plan["runtime_contract_sha256"],
        "mount_map_sha256": install_plan["mount_map_sha256"],
        "wheel_entry_points_sha256": install_plan["wheel_entry_points_sha256"],
        "wheel_metadata_sha256": install_plan["wheel_metadata_sha256"],
        "prefix": prefix.as_posix(),
        "purelib": purelib.as_posix(),
        "scripts": scripts.as_posix(),
        "dependency_bridge_before": {
            "exists": True,
            "bytes": len(bridge_bytes),
            "sha256": sha256_bytes(bridge_bytes),
        },
        "dependency_bridge_after": {
            "exists": True,
            "bytes": len(bridge_bytes),
            "sha256": sha256_bytes(Path(bridge_path).read_bytes()),
        },
        "entrypoint": {
            **install_plan["entrypoint"],
            "derived_from_selected_distribution": True,
        },
        "distribution": {
            "name": installed["name"],
            "version": installed["version"],
            "metadata_sha256": installed["metadata_sha256"],
            "metadata_file_sha256": installed["meta_hashes"],
        },
        "script": {
            "path": installed["script_path"],
            "bytes": installed["script_bytes"],
            "sha256": installed["script_sha256"],
            "mode": installed["script_mode"],
            "shebang": installed["script_shebang"],
            "pre_install_exists": script_exists_before_install,
        },
        "runtime_probe": probe_value,
        "preflight_outputs": preflight_outputs,
        "installed_prefix_snapshot_sha256": _snapshot_prefix_worker(
            prefix.as_posix(), contract["worker"]["python_realpath"]
        )["sha256"],
        "install_outputs": outputs,
    }


def snapshot_profile_prefix(
    mount_map: dict[str, Any],
    worker_probe: dict[str, Any],
) -> dict[str, Any]:
    """Hash every prefix member, permitting only the measured Python symlinks."""
    prefix = _worker_path(worker_probe.get("sys_prefix"), "worker sys.prefix")
    root = worker_path_to_host(prefix.as_posix(), mount_map, role="profile-prefix")
    python_realpath = _worker_path(worker_probe.get("python_realpath"), "worker Python realpath")
    files: list[dict[str, Any]] = []
    directories: list[str] = []
    allowed_links = {"bin/python", "bin/python3", "bin/python3.14"}

    def resolve_worker_link(relative: str) -> PurePosixPath:
        current = prefix / PurePosixPath(relative)
        visited: set[PurePosixPath] = set()
        for _ in range(8):
            if current in visited:
                raise WorkerMountError("profile Python symlink chain contains a cycle")
            visited.add(current)
            host_link = worker_path_to_host(
                current.as_posix(),
                mount_map,
                role="profile-prefix",
                allow_leaf_symlink=True,
            )
            if not stat.S_ISLNK(host_link.lstat().st_mode):
                if current != python_realpath:
                    raise WorkerMountError("profile Python symlink chain resolves to another file")
                return current
            target = os.readlink(host_link)
            if target.startswith("/"):
                current = _worker_path(target, "profile Python link target")
            else:
                normalized = posixpath.normpath(PurePosixPath(current.parent, target).as_posix())
                current = _worker_path(normalized, "profile Python link target")
            if current != prefix and not current.is_relative_to(prefix):
                if current != python_realpath:
                    raise WorkerMountError("profile Python link escapes its prefix unexpectedly")
                return current
        raise WorkerMountError("profile Python symlink chain exceeds the bounded link depth")

    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in sorted(dirnames):
            path = current / name
            info = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISLNK(info.st_mode):
                raise WorkerMountError(f"profile prefix contains a symlinked directory: {relative}")
            if not stat.S_ISDIR(info.st_mode):
                raise WorkerMountError(f"profile prefix contains a special directory: {relative}")
            directories.append(relative)
        for name in sorted(filenames):
            path = current / name
            info = path.lstat()
            relative = path.relative_to(root).as_posix()
            if stat.S_ISREG(info.st_mode):
                raw = path.read_bytes()
                files.append(
                    {
                        "path": relative,
                        "kind": "regular",
                        "bytes": len(raw),
                        "sha256": sha256_bytes(raw),
                        "mode": stat.S_IMODE(info.st_mode),
                    }
                )
                continue
            if stat.S_ISLNK(info.st_mode) and relative in allowed_links:
                mapped_target = resolve_worker_link(relative)
                if mapped_target != python_realpath:
                    raise WorkerMountError(
                        "profile interpreter symlink differs from measured Python"
                    )
                files.append(
                    {
                        "path": relative,
                        "kind": "symlink",
                        "target": os.readlink(path),
                        "resolved_worker_path": mapped_target.as_posix(),
                    }
                )
                continue
            raise WorkerMountError(
                f"profile prefix contains a special or unapproved symlink: {relative}"
            )
    files.sort(key=lambda row: row["path"])
    directories.sort()
    manifest = {
        "schema": "policyos.e02.q2.profile-prefix-snapshot.v1",
        "directories": directories,
        "files": files,
    }
    return {**manifest, "sha256": sha256_bytes(canonical_json_bytes(manifest))}


def snapshot_profile_prefix_in_worker(prefix: str, python_realpath: str) -> dict[str, Any]:
    """Capture a selected prefix locally inside the Linux worker namespace."""
    snapshot = _snapshot_prefix_worker(prefix, python_realpath)
    manifest = {key: value for key, value in snapshot.items() if key != "sha256"}
    expected = sha256_bytes(canonical_json_bytes(manifest))
    if snapshot.get("sha256") != expected:
        raise WorkerMountError("worker prefix snapshot digest is internally inconsistent")
    return snapshot


def mount_map_digest(value: dict[str, Any]) -> str:
    """Return the canonical digest after validating the map's self-contained shape."""
    if type(value) is not dict:
        raise WorkerMountError("worker mount map is not an object")
    return sha256_bytes(canonical_json_bytes(value))


def plan_installed_entrypoint(
    runtime_contract: dict[str, Any],
    mount_map: dict[str, Any],
    *,
    expected_source: dict[str, str],
    plan_sha256: str,
    profile: str,
    artifact_sha256: str,
    node_ids_sha256: str,
    wheel_filename: str | None = None,
    wheel_relative_path: str | None = None,
    entrypoint_name: str,
) -> dict[str, Any]:
    """Plan a normal no-dependency wheel install into the isolated worker prefix.

    The selected wheel's metadata supplies the console entry point. The routine
    creates a small, pip-free interpreter prefix, adds one read-only dependency
    site bridge before installation, and asks the measured installer to install
    the wheel normally so the installer itself generates the command script.
    """
    contract = validate_runtime_contract(runtime_contract)
    validate_mount_map(
        mount_map,
        expected_source=expected_source,
        expected_plan_sha256=plan_sha256,
        expected_profile=profile,
        expected_artifact_sha256=artifact_sha256,
        expected_node_ids_sha256=node_ids_sha256,
        expected_runtime_contract_sha256=sha256_bytes(canonical_json_bytes(contract)),
    )
    if (
        type(entrypoint_name) is not str
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", entrypoint_name)
        or (wheel_filename is None) == (wheel_relative_path is None)
    ):
        raise WorkerMountError("selected console entry point or wheel filename is malformed")
    if wheel_relative_path is not None:
        selected_wheel_relative = wheel_relative_path
    elif wheel_filename is not None:
        selected_wheel_relative = wheel_filename
    else:
        raise WorkerMountError("selected wheel path is missing")
    try:
        parsed_wheel_relative = PurePosixPath(selected_wheel_relative)
    except TypeError as error:
        raise WorkerMountError("selected wheel path is malformed") from error
    if (
        type(selected_wheel_relative) is not str
        or not selected_wheel_relative.endswith(".whl")
        or parsed_wheel_relative.is_absolute()
        or parsed_wheel_relative.as_posix() != selected_wheel_relative
        or not parsed_wheel_relative.parts
        or any(part in {"", ".", ".."} for part in parsed_wheel_relative.parts)
        or "\\" in selected_wheel_relative
    ):
        raise WorkerMountError("selected console entry point or wheel path is malformed")
    prefix_root = _worker_path(
        next(row["worker_root"] for row in mount_map["mounts"] if row["role"] == "profile-prefix"),
        "profile prefix mount",
    )
    prefix = prefix_root / _profile_component(profile)
    python = _worker_path(contract["worker"]["python_executable"], "base Python")
    dependency_site = _worker_path(contract["worker"]["dependency_site"], "dependency site")
    installer = _worker_path(contract["installer"]["path"], "worker installer")
    artifact_rows = [row for row in mount_map["mounts"] if row["role"] == "artifacts"]
    if len(artifact_rows) != 1:
        raise WorkerMountError("worker mount map must have exactly one artifact prefix")
    wheel_path = _worker_path(artifact_rows[0]["worker_root"], "artifact prefix").joinpath(
        *parsed_wheel_relative.parts
    )
    wheel_host_path = worker_path_to_host(wheel_path.as_posix(), mount_map, role="artifacts")
    wheel_metadata = _selected_wheel_metadata(wheel_host_path, artifact_sha256)
    wheel_entry_points = wheel_metadata["entry_points"]
    entrypoint_value = wheel_entry_points.get("console_scripts", {}).get(entrypoint_name)
    if type(entrypoint_value) is not str or not entrypoint_value:
        raise WorkerMountError("selected wheel metadata omits the requested console entry point")
    purelib = prefix / "lib" / "python3.14" / "site-packages"
    scripts = prefix / "bin"
    dependency_bridge = purelib / "policyos-e02-existing-dependency-site.pth"
    bridge_bytes = _dependency_site_bridge_bytes(dependency_site)
    return {
        "schema": ENTRYPOINT_INSTALL_SCHEMA,
        "source": dict(expected_source),
        "plan_sha256": _digest(plan_sha256, "plan SHA-256"),
        "profile": profile,
        "artifact_sha256": _digest(artifact_sha256, "artifact SHA-256"),
        "node_ids_sha256": _digest(node_ids_sha256, "node IDs SHA-256"),
        "runtime_contract_sha256": sha256_bytes(canonical_json_bytes(contract)),
        "runtime_contract": contract,
        "mount_map_sha256": mount_map_digest(mount_map),
        "entrypoint": {
            "group": "console_scripts",
            "name": entrypoint_name,
            "value": entrypoint_value,
        },
        "wheel_entry_points": wheel_entry_points,
        "wheel_entry_points_sha256": sha256_bytes(canonical_json_bytes(wheel_entry_points)),
        "wheel_metadata": wheel_metadata,
        "wheel_metadata_sha256": wheel_metadata["sha256"],
        "distribution": {
            "name": wheel_metadata["distribution_name"],
            "version": wheel_metadata["distribution_version"],
        },
        "base_python": python.as_posix(),
        "profile_prefix_mount": prefix_root.as_posix(),
        "prefix": prefix.as_posix(),
        "purelib": purelib.as_posix(),
        "scripts": scripts.as_posix(),
        "dependency_site": dependency_site.as_posix(),
        "dependency_bridge": {
            "path": dependency_bridge.as_posix(),
            "bytes": len(bridge_bytes),
            "sha256": sha256_bytes(bridge_bytes),
            "content_utf8": bridge_bytes.decode("utf-8"),
            "created_before_install": True,
            "must_remain_unchanged": True,
        },
        "wheel_path": wheel_path.as_posix(),
        "wheel_relative_path": selected_wheel_relative,
        "installer_path": installer.as_posix(),
        "installer_version": contract["installer"]["version"],
        "installer_sha256": contract["installer"]["sha256"],
        "python_realpath": contract["worker"]["python_realpath"],
        "commands": [
            [python.as_posix(), "-I", "-m", "venv", "--without-pip", prefix.as_posix()],
            [
                installer.as_posix(),
                "pip",
                "install",
                "--offline",
                "--no-index",
                "--no-deps",
                "--no-cache",
                "--python",
                (prefix / "bin" / "python").as_posix(),
                wheel_path.as_posix(),
            ],
        ],
        "post_install_checks": [
            "sys.prefix equals selected prefix",
            "sysconfig purelib and scripts resolve below selected prefix",
            "dependency site precedes no selected package path and remains worker-only",
            "installed distribution metadata has the selected console_scripts entry",
            "installer-generated script exists, is executable, and uses selected interpreter",
            "entrypoint script and dependency bridge remain unchanged through consumer run",
        ],
    }


def validate_entrypoint_install_receipt(
    receipt: object,
    plan: dict[str, Any],
    worker_probe: dict[str, Any],
    mount_map: dict[str, Any],
    *,
    container_identity: dict[str, str],
    expected_distribution_name: str,
    expected_distribution_version: str,
) -> dict[str, Any]:
    """Reconcile an actual installer-generated script with its selected wheel.

    The receipt binds installed metadata and script bytes; it cannot accept a
    caller-written command or a file that existed before the fresh install.
    """
    if type(receipt) is not dict or set(receipt) != {
        "schema",
        "source",
        "plan_sha256",
        "profile",
        "artifact_sha256",
        "runtime_contract_sha256",
        "mount_map_sha256",
        "wheel_metadata_sha256",
        "prefix",
        "purelib",
        "scripts",
        "dependency_bridge_before",
        "dependency_bridge_after",
        "entrypoint",
        "wheel_entry_points_sha256",
        "runtime_probe",
        "preflight_outputs",
        "install_outputs",
        "distribution",
        "script",
        "installed_prefix_snapshot_sha256",
    }:
        raise WorkerMountError("installed entrypoint receipt has an unsupported shape")
    for key in (
        "plan_sha256",
        "artifact_sha256",
        "runtime_contract_sha256",
        "mount_map_sha256",
        "wheel_metadata_sha256",
    ):
        _digest(receipt.get(key), f"entrypoint receipt {key}")
    _digest(receipt.get("wheel_entry_points_sha256"), "wheel entrypoint metadata digest")
    if (
        receipt.get("schema") != ENTRYPOINT_INSTALL_SCHEMA
        or receipt.get("source") != plan.get("source")
        or receipt.get("plan_sha256") != plan.get("plan_sha256")
        or receipt.get("profile") != plan.get("profile")
        or receipt.get("artifact_sha256") != plan.get("artifact_sha256")
        or receipt.get("runtime_contract_sha256") != plan.get("runtime_contract_sha256")
        or receipt.get("mount_map_sha256") != plan.get("mount_map_sha256")
        or receipt.get("wheel_metadata_sha256") != plan.get("wheel_metadata_sha256")
        or receipt.get("wheel_entry_points_sha256") != plan.get("wheel_entry_points_sha256")
        or receipt.get("runtime_probe") != worker_probe
    ):
        raise WorkerMountError("installed entrypoint belongs to another source/profile/artifact")
    contract = validate_runtime_contract(plan.get("runtime_contract"))
    if sha256_bytes(canonical_json_bytes(contract)) != plan.get("runtime_contract_sha256"):
        raise WorkerMountError("selected worker runtime contract differs from its source pin")
    validate_mount_map(
        mount_map,
        expected_source=plan["source"],
        expected_plan_sha256=plan["plan_sha256"],
        expected_profile=plan["profile"],
        expected_artifact_sha256=plan["artifact_sha256"],
        expected_node_ids_sha256=plan["node_ids_sha256"],
        expected_runtime_contract_sha256=plan["runtime_contract_sha256"],
    )
    wheel_path = worker_path_to_host(plan["wheel_path"], mount_map, role="artifacts")
    actual_wheel_metadata = _selected_wheel_metadata(wheel_path, plan["artifact_sha256"])
    if (
        actual_wheel_metadata != plan.get("wheel_metadata")
        or actual_wheel_metadata["sha256"] != plan.get("wheel_metadata_sha256")
        or plan.get("wheel_entry_points") != actual_wheel_metadata["entry_points"]
        or plan.get("distribution")
        != {
            "name": actual_wheel_metadata["distribution_name"],
            "version": actual_wheel_metadata["distribution_version"],
        }
    ):
        raise WorkerMountError("selected wheel metadata changed after install planning")
    if (
        expected_distribution_name.casefold().replace("-", "_")
        != actual_wheel_metadata["distribution_name"].casefold().replace("-", "_")
        or expected_distribution_version != actual_wheel_metadata["distribution_version"]
    ):
        raise WorkerMountError("selected wheel identity differs from source inventory")
    validate_worker_probe(
        worker_probe,
        contract,
        mount_map,
        container_identity=container_identity,
    )
    prefix = _worker_path(plan.get("prefix"), "selected profile prefix")
    prefix_mount = _worker_path(plan.get("profile_prefix_mount"), "selected profile-prefix mount")
    actual_prefix_mount = _worker_path(
        next(row["worker_root"] for row in mount_map["mounts"] if row["role"] == "profile-prefix"),
        "mapped profile-prefix mount",
    )
    if prefix_mount != actual_prefix_mount or prefix != prefix_mount / _profile_component(
        plan.get("profile")
    ):
        raise WorkerMountError("selected prefix does not bind to its exact profile mount child")
    purelib = _worker_path(plan.get("purelib"), "selected profile purelib")
    scripts = _worker_path(plan.get("scripts"), "selected profile scripts")
    if (
        receipt.get("prefix") != prefix.as_posix()
        or receipt.get("purelib") != purelib.as_posix()
        or receipt.get("scripts") != scripts.as_posix()
        or worker_probe.get("sys_prefix") != prefix.as_posix()
        or worker_probe.get("purelib") != purelib.as_posix()
        or worker_probe.get("scripts") != scripts.as_posix()
    ):
        raise WorkerMountError("installed entrypoint paths differ from actual sysconfig")
    bridge = plan.get("dependency_bridge")
    if type(bridge) is not dict or set(bridge) != {
        "path",
        "bytes",
        "sha256",
        "content_utf8",
        "created_before_install",
        "must_remain_unchanged",
    }:
        raise WorkerMountError("dependency-site bridge plan is malformed")
    if (
        bridge.get("created_before_install") is not True
        or bridge.get("must_remain_unchanged") is not True
        or bridge.get("content_utf8")
        != _dependency_site_bridge_bytes(
            _worker_path(plan.get("dependency_site"), "dependency site")
        ).decode("utf-8")
        or bridge.get("bytes") != len(bridge["content_utf8"].encode("utf-8"))
        or bridge.get("sha256") != sha256_bytes(bridge["content_utf8"].encode("utf-8"))
    ):
        raise WorkerMountError("dependency bridge does not point exactly to the locked site")
    for key, expected in (
        (
            "dependency_bridge_before",
            {"exists": True, "bytes": bridge["bytes"], "sha256": bridge["sha256"]},
        ),
        (
            "dependency_bridge_after",
            {"exists": True, "bytes": bridge["bytes"], "sha256": bridge["sha256"]},
        ),
    ):
        if receipt.get(key) != expected:
            raise WorkerMountError("dependency bridge changed during wheel install or test")
    entrypoint = plan.get("entrypoint")
    observed_entrypoint = receipt.get("entrypoint")
    if (
        type(entrypoint) is not dict
        or observed_entrypoint
        != {
            "group": entrypoint.get("group"),
            "name": entrypoint.get("name"),
            "value": entrypoint.get("value"),
            "derived_from_selected_distribution": True,
        }
        or entrypoint.get("group") != "console_scripts"
    ):
        raise WorkerMountError("installed entrypoint metadata differs from selected wheel")
    preflight = receipt.get("preflight_outputs")
    if type(preflight) is not list or any(type(row) is not dict for row in preflight):
        raise WorkerMountError("worker installer/runtime preflight output set is malformed")
    expected_preflight_labels = [
        "measured uv version",
        "fresh venv sysconfig",
        "installed wheel entrypoint readback",
        "selected worker profile probe",
    ]
    if [row.get("label") for row in preflight] != expected_preflight_labels:
        raise WorkerMountError("worker installer/runtime preflight output set is incomplete")
    clean_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": _WORKER_TMP.as_posix(),
        "TMPDIR": _WORKER_TMP.as_posix(),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "UV_NO_CONFIG": "1",
    }
    for row in preflight:
        if (
            type(row) is not dict
            or set(row) != {"label", "argv", "cwd", "env", "returncode", "stdout", "stderr"}
            or type(row.get("argv")) is not list
            or not row["argv"]
            or any(type(argument) is not str for argument in row["argv"])
            or row.get("cwd") != _WORKER_TMP.as_posix()
            or row.get("returncode") != 0
            or type(row.get("stdout")) is not str
            or type(row.get("stderr")) is not str
        ):
            raise WorkerMountError("worker preflight output is malformed or failed")
    python = (prefix / "bin" / "python").as_posix()
    expected_preflight_argv = [
        [plan["installer_path"], "--version"],
        [python, "-I", "-c", _venv_sysconfig_code()],
        [
            python,
            "-I",
            "-c",
            _installed_wheel_readback_code(expected_distribution_name, plan["entrypoint"]["name"]),
        ],
        [python, "-I", "-c", worker_probe_program()],
    ]
    expected_preflight_env = [
        clean_env,
        clean_env,
        clean_env,
        {
            **clean_env,
            "E02_Q2_CONTAINER_ID": worker_probe["container_id"],
            "E02_Q2_IMAGE_ID": worker_probe["image_id"],
            "E02_Q2_DEPENDENCY_SITE": plan["dependency_site"],
        },
    ]
    if any(
        row["argv"] != argv or row["env"] != env
        for row, argv, env in zip(
            preflight, expected_preflight_argv, expected_preflight_env, strict=True
        )
    ):
        raise WorkerMountError(
            "worker preflight command or environment differs from the reviewed recipe"
        )
    if preflight[0]["stdout"].strip() != "uv " + plan["installer_version"]:
        raise WorkerMountError("worker receipt omits the measured installer version readback")
    try:
        layout = json.loads(preflight[1]["stdout"])
        installed = json.loads(preflight[2]["stdout"])
        observed_probe = json.loads(preflight[3]["stdout"])
    except json.JSONDecodeError as error:
        raise WorkerMountError("worker preflight JSON output is malformed") from error
    if (
        layout
        != {
            "prefix": prefix.as_posix(),
            "purelib": purelib.as_posix(),
            "scripts": scripts.as_posix(),
            "executable": python,
            "realpath": worker_probe.get("python_realpath"),
        }
        or observed_probe != worker_probe
    ):
        raise WorkerMountError("worker preflight layout/probe output differs from actual receipt")
    outputs = receipt.get("install_outputs")
    if type(outputs) is not list or len(outputs) != len(plan.get("commands", [])):
        raise WorkerMountError("installer command output set is incomplete")
    for row, expected_argv in zip(outputs, plan["commands"], strict=True):
        if (
            type(row) is not dict
            or set(row) != {"label", "argv", "cwd", "env", "returncode", "stdout", "stderr"}
            or row.get("label")
            != (
                "fresh pip-free profile venv"
                if expected_argv == plan["commands"][0]
                else "selected wheel install"
            )
            or row.get("argv") != expected_argv
            or row.get("cwd") != _WORKER_TMP.as_posix()
            or row.get("env") != clean_env
            or row.get("returncode") != 0
            or type(row.get("stdout")) is not str
            or type(row.get("stderr")) is not str
        ):
            raise WorkerMountError("installer output is missing or belongs to another command")
    distribution = receipt.get("distribution")
    if (
        type(distribution) is not dict
        or set(distribution) != {"name", "version", "metadata_sha256", "metadata_file_sha256"}
        or distribution.get("name") != expected_distribution_name
        or distribution.get("version") != expected_distribution_version
        or distribution.get("metadata_file_sha256") != actual_wheel_metadata["metadata_file_sha256"]
    ):
        raise WorkerMountError("installed distribution identity differs from source inventory")
    _digest(distribution.get("metadata_sha256"), "installed distribution metadata digest")
    if distribution["metadata_sha256"] != sha256_bytes(
        canonical_json_bytes(actual_wheel_metadata["metadata_file_sha256"])
    ):
        raise WorkerMountError("installed distribution metadata bytes differ from selected wheel")
    script = receipt.get("script")
    name = entrypoint["name"]
    expected_script_path = (scripts / name).as_posix()
    if (
        type(script) is not dict
        or set(script) != {"path", "bytes", "sha256", "mode", "shebang", "pre_install_exists"}
        or script.get("path") != expected_script_path
        or type(script.get("bytes")) is not int
        or script["bytes"] <= 0
        or type(script.get("mode")) is not int
        or script["mode"] & 0o111 == 0
        or type(script.get("shebang")) is not str
        or script.get("pre_install_exists") is not False
    ):
        raise WorkerMountError(
            "entrypoint script is not the fresh selected-prefix installer output"
        )
    _digest(script.get("sha256"), "installed entrypoint script digest")
    expected_entries = sorted(
        [
            {"group": group, "name": name, "value": value}
            for group, entries in actual_wheel_metadata["entry_points"].items()
            for name, value in entries.items()
        ],
        key=lambda row: (row["group"], row["name"]),
    )
    if (
        type(installed) is not dict
        or set(installed)
        != {
            "name",
            "version",
            "entries",
            "meta_hashes",
            "metadata_sha256",
            "script_path",
            "script_bytes",
            "script_sha256",
            "script_mode",
            "script_shebang",
            "python",
            "prefix",
            "purelib",
            "scripts",
        }
        or type(installed.get("name")) is not str
        or installed["name"].casefold().replace("-", "_")
        != expected_distribution_name.casefold().replace("-", "_")
        or installed.get("version") != expected_distribution_version
        or installed.get("entries") != expected_entries
        or installed.get("meta_hashes") != actual_wheel_metadata["metadata_file_sha256"]
        or installed.get("metadata_sha256") != distribution["metadata_sha256"]
        or installed.get("script_path") != expected_script_path
        or installed.get("script_bytes") != script["bytes"]
        or installed.get("script_sha256") != script["sha256"]
        or installed.get("script_mode") != script["mode"]
        or installed.get("script_shebang") != script["shebang"]
        or installed.get("python") != worker_probe.get("python")
        or installed.get("prefix") != prefix.as_posix()
        or installed.get("purelib") != purelib.as_posix()
        or installed.get("scripts") != scripts.as_posix()
    ):
        raise WorkerMountError("actual installer metadata/script readback differs from receipt")
    script_file = worker_path_to_host(script["path"], mount_map, role="profile-prefix")
    bridge_file = worker_path_to_host(bridge["path"], mount_map, role="profile-prefix")
    script_info = script_file.lstat()
    if not stat.S_ISREG(script_info.st_mode) or stat.S_ISLNK(script_info.st_mode):
        raise WorkerMountError("installer-generated entrypoint is not a regular file")
    script_raw = script_file.read_bytes()
    if (
        len(script_raw) != script["bytes"]
        or sha256_bytes(script_raw) != script["sha256"]
        or stat.S_IMODE(script_info.st_mode) != script["mode"]
    ):
        raise WorkerMountError("host-read entrypoint bytes/mode differ from worker receipt")
    first_line = script_raw.splitlines()[0].decode("utf-8", errors="strict")
    if first_line != "#!" + worker_probe.get("python") or script["shebang"] != first_line:
        raise WorkerMountError("installed entrypoint shebang differs from selected interpreter")
    bridge_info = bridge_file.lstat()
    bridge_raw = bridge_file.read_bytes()
    if (
        not stat.S_ISREG(bridge_info.st_mode)
        or stat.S_ISLNK(bridge_info.st_mode)
        or len(bridge_raw) != bridge["bytes"]
        or sha256_bytes(bridge_raw) != bridge["sha256"]
        or bridge_raw.decode("utf-8") != bridge["content_utf8"]
    ):
        raise WorkerMountError("host-read dependency bridge differs from its exact RO-site pin")
    _digest(
        receipt.get("installed_prefix_snapshot_sha256"),
        "installed-prefix snapshot digest",
    )
    actual_snapshot = snapshot_profile_prefix(mount_map, worker_probe)
    if actual_snapshot["sha256"] != receipt["installed_prefix_snapshot_sha256"]:
        raise WorkerMountError("host-read profile prefix changed after installer receipt")
    return dict(receipt)

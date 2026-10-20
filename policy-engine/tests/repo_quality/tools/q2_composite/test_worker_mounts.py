from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

REPO_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "policy-engine").is_dir() and (parent / ".git").exists()
)
POSTIMAGE_ROOT = (
    Path(os.environ["E02_Q2_POSTIMAGE_ROOT"]).resolve(strict=True)
    if os.environ.get("E02_Q2_POSTIMAGE_ROOT")
    else None
)
Q2_SOURCE = (
    POSTIMAGE_ROOT / "policy-engine/tools/quality/validation/q2_composite"
    if POSTIMAGE_ROOT is not None
    else REPO_ROOT / "policy-engine/tools/quality/validation/q2_composite"
)
sys.path.insert(0, str(Q2_SOURCE))
import profile_partition_runner as partition_runner
import pytest
import worker_mounts as mounts

_TMPFS_DESTINATION = "/tmp"  # noqa: S108 -- runtime contract binds the isolated tmpfs mount.


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _wheel_bytes(
    *,
    entrypoint: str = "ukraine-data = tools.ops_runners.ukraine_data_cli:main",
    profile_marker: str | None = None,
) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in (
            (
                "polisyos-0.1.0.dist-info/METADATA",
                b"Metadata-Version: 2.3\nName: polisyos\nVersion: 0.1.0\n\n",
            ),
            ("polisyos-0.1.0.dist-info/WHEEL", b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\n\n"),
            (
                "polisyos-0.1.0.dist-info/entry_points.txt",
                ("[console_scripts]\n" + entrypoint + "\n").encode(),
            ),
            ("polisyos-0.1.0.dist-info/RECORD", b""),
        ):
            archive.writestr(name, content)
        if profile_marker is not None:
            archive.writestr(f"q2-profile-{profile_marker}.txt", profile_marker.encode())
    return buffer.getvalue()


def _runtime_contract() -> dict[str, Any]:
    image = "ghcr.io/astral-sh/uv@sha256:" + "a" * 64
    return {
        "schema": mounts.RUNTIME_SCHEMA,
        "docker": {
            "config_path": "/Users/example/.docker-e02-local",
            "context": "colima-e02-local",
        },
        "image": {"reference": image, "image_id": "sha256:" + "a" * 64},
        "isolation": {
            "read_only_rootfs": True,
            "network_mode": "none",
            "persistent_volumes": [
                {"name": "e02-local-uv-env", "destination": "/scratch", "read_only": True},
                {
                    "name": "e02-local-uv-pythons",
                    "destination": "/opt/uv-python",
                    "read_only": True,
                },
            ],
            "tmpfs_destinations": [_TMPFS_DESTINATION],
        },
        "worker": {
            "platform_system": "Linux",
            "sys_platform": "linux",
            "machine": "aarch64",
            "python_executable": "/scratch/root-venv/bin/python",
            "python_realpath": "/opt/uv-python/cpython-3.14.0-linux-aarch64-gnu/bin/python3.14",
            "python_version": [3, 14, 0],
            "dependency_site": "/scratch/root-venv/lib/python3.14/site-packages",
            "pytest_origin": "/scratch/root-venv/lib/python3.14/site-packages/pytest/__init__.py",
        },
        "installer": {
            "name": "uv",
            "path": "/usr/local/bin/uv",
            "version": "0.9.21",
            "sha256": "1f4478fd05f7d1143449744cd59c6458abd0f0563e4fd48f1544758f7a745658",
        },
        "resources": dict(mounts.Q2_FIRST_LA029_RESOURCE_LIMITS),
    }


def _runtime_binding_report() -> dict[str, Any]:
    return {
        "schema": "q2_worker_runtime_binding_input_v1",
        "source_frame": {"head": "1" * 40, "tree": "2" * 40},
        "existing_worker": {
            "container_id": "3" * 64,
            "container_name": "e02-local-worker-provision",
            "image_id": "sha256:" + "a" * 64,
            "image_repo_digest": "ghcr.io/astral-sh/uv@sha256:" + "a" * 64,
            "image_platform": "linux/arm64",
            "config_image": "ghcr.io/astral-sh/uv@sha256:" + "a" * 64,
            "state": "running",
            "docker_config": "/Users/example/.docker-e02-local",
            "docker_context": "colima-e02-local",
            "runtime": {
                "python": {
                    "version": "3.14.0",
                    "realpath": "/opt/uv-python/cpython-3.14.0-linux-aarch64-gnu/bin/python3.14",
                    "venv_launcher": "/scratch/root-venv/bin/python",
                    "dependency_purelib": "/scratch/root-venv/lib/python3.14/site-packages",
                    "pytest_file": (
                        "/scratch/root-venv/lib/python3.14/site-packages/pytest/__init__.py"
                    ),
                    "sha256": "87bc29693866a567a3a6263c374c51a16b6745810b67200a319bbe9bf8e6d51e",
                },
                "uv": {
                    "path": "/usr/local/bin/uv",
                    "version": "0.9.21",
                    "sha256": "1f4478fd05f7d1143449744cd59c6458abd0f0563e4fd48f1544758f7a745658",
                },
            },
        },
        "future_container_intent_not_executed": {
            "status": "draft_only",
            "source_checkout_mount": (
                "forbidden; do not mount /Users/deniskopylov/polisyos or the managed worktree "
                "into the test container"
            ),
            "shared_dependency_mounts": [
                {"mode": "ro", "source": "e02-local-uv-env", "target": "/scratch"},
                {
                    "mode": "ro",
                    "source": "e02-local-uv-pythons",
                    "target": "/opt/uv-python",
                },
                {
                    "mode": "ro",
                    "source": "e02-local-uv-cache",
                    "target": "/root/.cache/uv",
                },
            ],
        },
        "readback_commands": [
            {
                "argv": ["docker", "inspect", "--format", "selected-fields-only"],
                "stdout_sha256": "d" * 64,
                "stderr_sha256": "e" * 64,
            }
        ],
    }


def test_linux_worker_command_uses_sha_pinned_stdin_and_exact_consumer(tmp_path: Path) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    command = partition_runner.worker_profile_exec_argv(
        contract,
        container_id="f" * 64,
        request_sha256="a" * 64,
        input_worker_root="/mnt/e02-q2/inputs",
    )
    assert command == [
        "docker",
        "--config",
        contract["docker"]["config_path"],
        "--context",
        contract["docker"]["context"],
        "exec",
        "-i",
        "f" * 64,
        contract["worker"]["python_executable"],
        "-I",
        "/mnt/e02-q2/inputs/split_consumer.py",
        "--run-profile-partition",
        "--request-stdin",
        "--request-sha256",
        "a" * 64,
    ]
    assert "--request" not in command
    assert "-i" in command


def _binding_corrigendum(report_path: Path, report_sha256: str) -> dict[str, Any]:
    return {
        "schema": "q2_worker_runtime_binding_readback_corrigendum_v1",
        "target_report": {"path": str(report_path), "sha256": report_sha256},
    }


def _mount_map(root: Path) -> dict[str, Any]:
    host_roots = {}
    for role in ("artifacts", "inputs", "profile-prefix", "receipts"):
        path = root / role
        path.mkdir(parents=True, exist_ok=True)
        host_roots[role] = path
    artifact = _wheel_bytes()
    (host_roots["artifacts"] / "polisyos-0.1.0-py3-none-any.whl").write_bytes(artifact)
    (host_roots["inputs"] / "pytest.ini").write_bytes(b"[pytest]\n")
    return {
        "schema": mounts.MOUNT_MAP_SCHEMA,
        "source": {"commit": "b" * 40, "tree": "c" * 40},
        "plan_sha256": "d" * 64,
        "profile": "rebuilt-sdist-wheel",
        "executor": "linux-worker",
        "artifact_sha256": _digest(artifact),
        "node_ids_sha256": "e" * 64,
        "runtime_contract_sha256": mounts.sha256_bytes(
            mounts.canonical_json_bytes(_runtime_contract())
        ),
        "mounts": [
            {
                "role": "artifacts",
                "host_root": str(host_roots["artifacts"]),
                "worker_root": "/mnt/e02-q2/artifacts",
                "access": "read-only",
            },
            {
                "role": "inputs",
                "host_root": str(host_roots["inputs"]),
                "worker_root": "/mnt/e02-q2/inputs",
                "access": "read-only",
            },
            {
                "role": "profile-prefix",
                "host_root": str(host_roots["profile-prefix"]),
                "worker_root": "/mnt/e02-q2/prefix",
                "access": "read-write",
            },
            {
                "role": "receipts",
                "host_root": str(host_roots["receipts"]),
                "worker_root": "/mnt/e02-q2/receipts",
                "access": "read-write",
            },
        ],
    }


def _inspect(contract: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    image = contract["image"]
    rows = [
        {
            "Type": "volume",
            "Name": item["name"],
            "Source": "/var/lib/docker/volumes/" + item["name"] + "/_data",
            "Destination": item["destination"],
            "RW": False,
        }
        for item in contract["isolation"]["persistent_volumes"]
    ]
    rows.extend(
        {
            "Type": "bind",
            "Source": item["host_root"],
            "Destination": item["worker_root"],
            "RW": item["access"] == "read-write",
        }
        for item in mapping["mounts"]
    )
    rows.append({"Type": "tmpfs", "Source": "", "Destination": _TMPFS_DESTINATION, "RW": True})
    return {
        "Id": "f" * 64,
        "Image": image["image_id"],
        "Config": {"Image": image["reference"]},
        "State": {"Running": True},
        "HostConfig": {
            "ReadonlyRootfs": True,
            "NetworkMode": "none",
            "Privileged": False,
            "AutoRemove": False,
            "CapAdd": [],
            "Memory": contract["resources"]["memory_bytes"],
            "MemorySwap": contract["resources"]["memory_swap_bytes"],
            "NanoCpus": contract["resources"]["nano_cpus"],
        },
        "Mounts": rows,
    }


def _probe(mapping: dict[str, Any], container_identity: dict[str, str]) -> dict[str, Any]:
    prefix = "/mnt/e02-q2/prefix/" + mapping["profile"]
    purelib = prefix + "/lib/python3.14/site-packages"
    dependency_site = "/scratch/root-venv/lib/python3.14/site-packages"
    return {
        "schema": mounts.WORKER_PROBE_SCHEMA,
        "container_id": container_identity["container_id"],
        "image_id": container_identity["image_id"],
        "container_hostname": container_identity["container_id"][:12],
        "platform_system": "Linux",
        "sys_platform": "linux",
        "machine": "aarch64",
        "python": prefix + "/bin/python",
        "python_realpath": "/opt/uv-python/cpython-3.14.0-linux-aarch64-gnu/bin/python3.14",
        "python_version": [3, 14, 0],
        "sys_prefix": prefix,
        "purelib": purelib,
        "scripts": prefix + "/bin",
        "dependency_site": dependency_site,
        "pytest_origin": dependency_site + "/pytest/__init__.py",
        "sys_path": [
            purelib,
            dependency_site,
            "/opt/uv-python/cpython-3.14.0-linux-aarch64-gnu/lib/python3.14",
            "/opt/uv-python/cpython-3.14.0-linux-aarch64-gnu/lib/python3.14/lib-dynload",
        ],
        "installer_path": "/usr/local/bin/uv",
        "installer_version": "0.9.21",
        "installer_sha256": "1f4478fd05f7d1143449744cd59c6458abd0f0563e4fd48f1544758f7a745658",
    }


def _validate_mapping(mapping: dict[str, Any]) -> None:
    mounts.validate_mount_map(
        mapping,
        expected_source=mapping["source"],
        expected_plan_sha256=mapping["plan_sha256"],
        expected_profile=mapping["profile"],
        expected_artifact_sha256=mapping["artifact_sha256"],
        expected_node_ids_sha256=mapping["node_ids_sha256"],
        expected_runtime_contract_sha256=mapping["runtime_contract_sha256"],
    )


def _observation(label: str, argv: list[str], stdout: str, env: dict[str, str]) -> dict[str, Any]:
    return {
        "label": label,
        "argv": argv,
        "cwd": _TMPFS_DESTINATION,
        "env": dict(sorted(env.items())),
        "returncode": 0,
        "stdout": stdout,
        "stderr": "",
    }


def _synthetic_inspect_receipt(
    contract: dict[str, Any], mapping: dict[str, Any], container_id: str
) -> dict[str, Any]:
    """Build a controlled field-query fixture; this is not a Docker observation."""
    expected = mounts.worker_container_inspect_argv(contract, container_id)
    observed = _inspect(contract, mapping)
    observed["Id"] = container_id
    fields = {
        "Id": observed["Id"],
        "Image": observed["Image"],
        "Config.Image": observed["Config"]["Image"],
        "State.Running": json.dumps(observed["State"]["Running"]),
        "HostConfig.ReadonlyRootfs": json.dumps(observed["HostConfig"]["ReadonlyRootfs"]),
        "HostConfig.NetworkMode": observed["HostConfig"]["NetworkMode"],
        "HostConfig.Privileged": json.dumps(observed["HostConfig"]["Privileged"]),
        "HostConfig.AutoRemove": json.dumps(observed["HostConfig"]["AutoRemove"]),
        "HostConfig.CapAdd": json.dumps(observed["HostConfig"]["CapAdd"]),
        "HostConfig.Memory": json.dumps(observed["HostConfig"]["Memory"]),
        "HostConfig.MemorySwap": json.dumps(observed["HostConfig"]["MemorySwap"]),
        "HostConfig.NanoCpus": json.dumps(observed["HostConfig"]["NanoCpus"]),
        "Mounts": json.dumps(observed["Mounts"], separators=(",", ":")),
    }
    return {
        "schema": "policyos.e02.q2.worker-container-inspect.v1",
        "commands": [
            {
                **command,
                "returncode": 0,
                "stdout": fields[command["field"]],
                "stderr": "",
            }
            for command in expected
        ],
    }


def _synthetic_install_receipt(
    install: dict[str, Any],
    mapping: dict[str, Any],
    identity: dict[str, str],
    probe: dict[str, Any],
    installed_files: dict[str, bytes],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Materialize and reconcile a bounded installer fixture without running Linux tools."""
    purelib = mounts.worker_path_to_host(
        install["purelib"], mapping, role="profile-prefix", must_exist=False
    )
    for relative, raw in installed_files.items():
        target = purelib.joinpath(*Path(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)

    bridge = install["dependency_bridge"]
    bridge_path = mounts.worker_path_to_host(
        bridge["path"], mapping, role="profile-prefix", must_exist=False
    )
    bridge_path.parent.mkdir(parents=True, exist_ok=True)
    bridge_bytes = bridge["content_utf8"].encode("utf-8")
    bridge_path.write_bytes(bridge_bytes)

    script_path = mounts.worker_path_to_host(
        install["scripts"] + "/" + install["entrypoint"]["name"],
        mapping,
        role="profile-prefix",
        must_exist=False,
    )
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_bytes = (
        "#!"
        + probe["python"]
        + "\n"
        + "from "
        + install["entrypoint"]["value"].split(":", 1)[0]
        + " import "
        + install["entrypoint"]["value"].split(":", 1)[1]
        + "\nraise SystemExit("
        + install["entrypoint"]["value"].split(":", 1)[1]
        + "())\n"
    ).encode("utf-8")
    script_path.write_bytes(script_bytes)
    script_path.chmod(0o755)
    for name in ("python", "python3", "python3.14"):
        link = script_path.parent / name
        if not link.exists() and not link.is_symlink():
            link.symlink_to(probe["python_realpath"])

    mode = script_path.stat().st_mode & 0o777
    snapshot = mounts.snapshot_profile_prefix(mapping, probe)
    clean_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": _TMPFS_DESTINATION,
        "TMPDIR": _TMPFS_DESTINATION,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "UV_NO_CONFIG": "1",
    }
    expected_entries = sorted(
        [
            {"group": group, "name": name, "value": value}
            for group, values in install["wheel_entry_points"].items()
            for name, value in values.items()
        ],
        key=lambda row: (row["group"], row["name"]),
    )
    metadata_file_sha256 = install["wheel_metadata"]["metadata_file_sha256"]
    metadata_sha256 = mounts.sha256_bytes(mounts.canonical_json_bytes(metadata_file_sha256))
    script_path_value = install["scripts"] + "/" + install["entrypoint"]["name"]
    installed = {
        "name": install["distribution"]["name"],
        "version": install["distribution"]["version"],
        "entries": expected_entries,
        "meta_hashes": metadata_file_sha256,
        "metadata_sha256": metadata_sha256,
        "script_path": script_path_value,
        "script_bytes": len(script_bytes),
        "script_sha256": mounts.sha256_bytes(script_bytes),
        "script_mode": mode,
        "script_shebang": "#!" + probe["python"],
        "python": probe["python"],
        "prefix": install["prefix"],
        "purelib": install["purelib"],
        "scripts": install["scripts"],
    }
    python = install["prefix"] + "/bin/python"
    preflight_env = [
        clean_env,
        clean_env,
        clean_env,
        {
            **clean_env,
            "E02_Q2_CONTAINER_ID": probe["container_id"],
            "E02_Q2_IMAGE_ID": probe["image_id"],
            "E02_Q2_DEPENDENCY_SITE": install["dependency_site"],
        },
    ]

    def observation(
        label: str, argv: list[str], stdout: str, env: dict[str, str]
    ) -> dict[str, Any]:
        return {
            "label": label,
            "argv": argv,
            "cwd": _TMPFS_DESTINATION,
            "env": dict(sorted(env.items())),
            "returncode": 0,
            "stdout": stdout,
            "stderr": "",
        }

    receipt = {
        "schema": mounts.ENTRYPOINT_INSTALL_SCHEMA,
        "source": install["source"],
        "plan_sha256": install["plan_sha256"],
        "profile": install["profile"],
        "artifact_sha256": install["artifact_sha256"],
        "runtime_contract_sha256": install["runtime_contract_sha256"],
        "mount_map_sha256": install["mount_map_sha256"],
        "wheel_metadata_sha256": install["wheel_metadata_sha256"],
        "wheel_entry_points_sha256": install["wheel_entry_points_sha256"],
        "prefix": install["prefix"],
        "purelib": install["purelib"],
        "scripts": install["scripts"],
        "dependency_bridge_before": {
            "exists": True,
            "bytes": len(bridge_bytes),
            "sha256": mounts.sha256_bytes(bridge_bytes),
        },
        "dependency_bridge_after": {
            "exists": True,
            "bytes": len(bridge_bytes),
            "sha256": mounts.sha256_bytes(bridge_bytes),
        },
        "entrypoint": {
            **install["entrypoint"],
            "derived_from_selected_distribution": True,
        },
        "runtime_probe": probe,
        "preflight_outputs": [
            observation(
                "measured uv version",
                [install["installer_path"], "--version"],
                "uv " + install["installer_version"] + "\n",
                preflight_env[0],
            ),
            observation(
                "fresh venv sysconfig",
                [python, "-I", "-c", mounts._venv_sysconfig_code()],
                json.dumps(
                    {
                        "prefix": install["prefix"],
                        "purelib": install["purelib"],
                        "scripts": install["scripts"],
                        "executable": python,
                        "realpath": probe["python_realpath"],
                    },
                    sort_keys=True,
                ),
                preflight_env[1],
            ),
            observation(
                "installed wheel entrypoint readback",
                [
                    python,
                    "-I",
                    "-c",
                    mounts._installed_wheel_readback_code(
                        install["distribution"]["name"], install["entrypoint"]["name"]
                    ),
                ],
                json.dumps(installed, sort_keys=True),
                preflight_env[2],
            ),
            observation(
                "selected worker profile probe",
                [python, "-I", "-c", mounts.worker_probe_program()],
                json.dumps(probe, sort_keys=True),
                preflight_env[3],
            ),
        ],
        "install_outputs": [
            {
                "label": label,
                "argv": argv,
                "cwd": _TMPFS_DESTINATION,
                "env": clean_env,
                "returncode": 0,
                "stdout": "",
                "stderr": "",
            }
            for label, argv in zip(
                ("fresh pip-free profile venv", "selected wheel install"),
                install["commands"],
                strict=True,
            )
        ],
        "distribution": {
            "name": install["distribution"]["name"],
            "version": install["distribution"]["version"],
            "metadata_sha256": metadata_sha256,
            "metadata_file_sha256": metadata_file_sha256,
        },
        "script": {
            "path": script_path_value,
            "bytes": len(script_bytes),
            "sha256": mounts.sha256_bytes(script_bytes),
            "mode": mode,
            "shebang": "#!" + probe["python"],
            "pre_install_exists": False,
        },
        "installed_prefix_snapshot_sha256": snapshot["sha256"],
    }
    mounts.validate_entrypoint_install_receipt(
        receipt,
        install,
        probe,
        mapping,
        container_identity=identity,
        expected_distribution_name=install["distribution"]["name"],
        expected_distribution_version=install["distribution"]["version"],
    )
    return receipt, snapshot


def test_runtime_contract_and_exact_docker_mounts(tmp_path: Path) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    mapping = _mount_map(tmp_path)
    _validate_mapping(mapping)
    identity = mounts.validate_worker_container(_inspect(contract, mapping), contract, mapping)
    probe = mounts.validate_worker_probe(
        _probe(mapping, identity), contract, mapping, container_identity=identity
    )
    assert identity["image_id"] == contract["image"]["image_id"]
    assert probe["purelib"] == (
        "/mnt/e02-q2/prefix/rebuilt-sdist-wheel/lib/python3.14/site-packages"
    )


def test_runtime_binding_keeps_existing_facts_separate_from_new_worker_intent(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "worker-runtime.json"
    corrigendum_path = tmp_path / "worker-runtime-corrigendum.json"
    report_raw = json.dumps(_runtime_binding_report(), sort_keys=True).encode()
    report_path.write_bytes(report_raw)
    corrigendum_raw = json.dumps(
        _binding_corrigendum(report_path, _digest(report_raw)), sort_keys=True
    ).encode()
    corrigendum_path.write_bytes(corrigendum_raw)

    report, corrigendum, identity = mounts.load_runtime_binding_input(
        report_path,
        report_sha256=_digest(report_raw),
        corrigendum_path=corrigendum_path,
        corrigendum_sha256=_digest(corrigendum_raw),
    )
    contract = mounts.runtime_contract_from_binding_input(report)

    assert corrigendum["target_report"]["sha256"] == identity["report_sha256"]
    assert identity["new_container_status"] == "not_created"
    assert {
        (row["name"], row["destination"]) for row in contract["isolation"]["persistent_volumes"]
    } == {
        ("e02-local-uv-env", "/scratch"),
        ("e02-local-uv-pythons", "/opt/uv-python"),
    }
    assert contract["image"]["reference"].endswith(identity["existing_image_id"])

    changed_raw = report_raw.replace(b"draft_only", b"executed__")
    report_path.write_bytes(changed_raw)
    with pytest.raises(mounts.WorkerMountError, match="frozen SHA-256"):
        mounts.load_runtime_binding_input(
            report_path,
            report_sha256=_digest(report_raw),
            corrigendum_path=corrigendum_path,
            corrigendum_sha256=_digest(corrigendum_raw),
        )


def _docker_mount_bindings(argv: list[str]) -> list[dict[str, str | bool]]:
    """Parse only Docker's rendered --mount arguments into their semantic bindings."""
    bindings: list[dict[str, str | bool]] = []
    index = 0
    while index < len(argv):
        if argv[index] != "--mount":
            index += 1
            continue
        if index + 1 >= len(argv):
            raise AssertionError("Docker --mount option has no specification")
        fields: dict[str, str] = {}
        flags: set[str] = set()
        for component in argv[index + 1].split(","):
            if "=" in component:
                key, value = component.split("=", 1)
                if key in fields:
                    raise AssertionError(f"Docker mount repeats {key!r}")
                fields[key] = value
            else:
                flags.add(component)
        if set(fields) != {"type", "src", "dst"} or flags - {"readonly"}:
            raise AssertionError("Docker mount has an unsupported specification")
        bindings.append(
            {
                "type": fields["type"],
                "source": fields["src"],
                "target": fields["dst"],
                "read_only": "readonly" in flags,
            }
        )
        index += 2
    return bindings


def _assert_exact_docker_mount_bindings(
    argv: list[str], expected: list[dict[str, str | bool]]
) -> None:
    """Require the actual command arguments to match every declared mount binding."""
    observed = _docker_mount_bindings(argv)
    if observed != expected:
        raise AssertionError(
            f"Docker mount bindings differ: observed={observed!r}, expected={expected!r}"
        )


def _assert_closed_docker_create_argv(
    argv: list[str],
    contract: dict[str, Any],
    mapping: dict[str, Any],
    *,
    container_name: str,
    resource_limits: dict[str, int],
) -> None:
    """Reject every create argument outside the worker's declared Docker grammar."""
    prefix = [
        "docker",
        "--config",
        contract["docker"]["config_path"],
        "--context",
        contract["docker"]["context"],
        "create",
    ]
    if argv[: len(prefix)] != prefix:
        raise AssertionError("worker create argv has an unsupported Docker CLI prefix")

    flags: set[str] = set()
    values: dict[str, str] = {}
    positional: list[str] = []
    valued_options = {
        "--name",
        "--network",
        "--tmpfs",
        "--memory",
        "--memory-swap",
        "--cpus",
        "--mount",
        "--entrypoint",
    }
    flag_options = {"--pull=never", "--read-only"}
    index = len(prefix)
    while index < len(argv):
        option = argv[index]
        if option in flag_options:
            if option in flags:
                raise AssertionError(f"worker create argv repeats {option!r}")
            flags.add(option)
            index += 1
            continue
        if option in valued_options:
            if index + 1 >= len(argv) or argv[index + 1].startswith("-"):
                raise AssertionError(f"worker create option {option!r} has no value")
            value = argv[index + 1]
            if option != "--mount":
                if option in values:
                    raise AssertionError(f"worker create argv repeats {option!r}")
                values[option] = value
            index += 2
            continue
        if option.startswith("-"):
            raise AssertionError(f"worker create argv uses unsupported option {option!r}")
        positional = argv[index:]
        break

    expected_flags = {"--pull=never", "--read-only"}
    if flags != expected_flags:
        raise AssertionError(f"worker create flags differ: observed={flags!r}")
    tmpfs_destinations = contract["isolation"]["tmpfs_destinations"]
    if tmpfs_destinations != [_TMPFS_DESTINATION]:
        raise AssertionError("worker create tmpfs destinations differ from the supported plan")
    expected_values = {
        "--name": container_name,
        "--network": contract["isolation"]["network_mode"],
        "--tmpfs": f"{_TMPFS_DESTINATION}:rw,nosuid,nodev,noexec,size=256m",
        "--memory": str(resource_limits["memory_bytes"]),
        "--memory-swap": str(resource_limits["memory_swap_bytes"]),
        "--cpus": str(resource_limits["nano_cpus"] / 1_000_000_000),
        "--entrypoint": "/bin/sleep",
    }
    if values != expected_values:
        raise AssertionError(
            f"worker create option values differ: observed={values!r}, expected={expected_values!r}"
        )
    if positional != [contract["image"]["reference"], "infinity"]:
        raise AssertionError(f"worker create image/command tail differs: {positional!r}")

    expected_mounts: list[dict[str, str | bool]] = [
        {
            "type": "volume",
            "source": row["name"],
            "target": row["destination"],
            "read_only": row["read_only"],
        }
        for row in sorted(
            contract["isolation"]["persistent_volumes"],
            key=lambda item: item["destination"],
        )
    ]
    expected_mounts.extend(
        {
            "type": "bind",
            "source": str(Path(row["host_root"]).resolve()),
            "target": row["worker_root"],
            "read_only": row["access"] == "read-only",
        }
        for row in mapping["mounts"]
    )
    _assert_exact_docker_mount_bindings(argv, expected_mounts)


def test_new_worker_create_plan_binds_only_declared_sources_and_roles(
    tmp_path: Path,
) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    fixture_root = tmp_path.resolve()
    mapping = _mount_map(fixture_root)
    _validate_mapping(mapping)
    home = Path.home().resolve()
    checkout = REPO_ROOT.resolve()
    host_roots = [Path(row["host_root"]).resolve() for row in mapping["mounts"]]
    assert all(path.is_relative_to(fixture_root) for path in host_roots)
    if fixture_root.is_relative_to(home):
        assert all(path.is_relative_to(home) for path in host_roots)
    assert all(not path.is_relative_to(checkout) for path in host_roots)

    limits = {
        "memory_bytes": 2 * 1024 * 1024 * 1024,
        "memory_swap_bytes": 2 * 1024 * 1024 * 1024,
        "nano_cpus": 1_000_000_000,
    }
    container_name = "e02-q2-la029-source-wheel"
    argv = mounts.worker_container_create_argv(
        contract,
        mapping,
        container_name=container_name,
        resource_limits=limits,
    )
    _assert_closed_docker_create_argv(
        argv, contract, mapping, container_name=container_name, resource_limits=limits
    )
    with pytest.raises(mounts.WorkerMountError, match="explicit operator decision"):
        mounts.worker_container_create_argv(contract, mapping, container_name=container_name)

    option_boundary = argv.index("--entrypoint")
    unauthorized_source = str(checkout)
    alternate_mount_spellings = (
        ("-v", f"{unauthorized_source}:/workspace/policyos-checkout"),
        ("--volume", f"{unauthorized_source}:/workspace/policyos-checkout"),
        (f"--volume={unauthorized_source}:/workspace/policyos-checkout",),
        (f"--mount=type=bind,src={unauthorized_source},dst=/workspace/policyos-checkout",),
        ("--privileged",),
        ("--read-only",),
    )
    for injected_args in alternate_mount_spellings:
        contaminated_argv = [
            *argv[:option_boundary],
            *injected_args,
            *argv[option_boundary:],
        ]
        with pytest.raises(AssertionError):
            _assert_closed_docker_create_argv(
                contaminated_argv,
                contract,
                mapping,
                container_name=container_name,
                resource_limits=limits,
            )

    unauthorized_mount_specs = (
        f"type=bind,src={unauthorized_source},dst=/workspace/policyos-checkout,readonly",
        "type=volume,src=e02-local-uv-cache,dst=/root/.cache/uv,readonly",
    )
    for mount_spec in unauthorized_mount_specs:
        extra_supported_form = [
            *argv[:option_boundary],
            "--mount",
            mount_spec,
            *argv[option_boundary:],
        ]
        with pytest.raises(AssertionError, match="Docker mount bindings differ"):
            _assert_closed_docker_create_argv(
                extra_supported_form,
                contract,
                mapping,
                container_name=container_name,
                resource_limits=limits,
            )


def test_worker_path_mapping_is_exact_and_role_bounded(tmp_path: Path) -> None:
    mapping = _mount_map(tmp_path)
    _validate_mapping(mapping)
    host_file = tmp_path / "artifacts" / "polisyos-0.1.0-py3-none-any.whl"
    assert mounts.host_path_to_worker(host_file, mapping, role="artifacts") == (
        "/mnt/e02-q2/artifacts/polisyos-0.1.0-py3-none-any.whl"
    )
    assert (
        mounts.worker_path_to_host(
            "/mnt/e02-q2/artifacts/polisyos-0.1.0-py3-none-any.whl", mapping, role="artifacts"
        )
        == host_file
    )
    for path in (
        "/mnt/e02-q2/artifacts-neighbor/profile.whl",
        "/mnt/e02-q2/artifacts/../inputs/pytest.ini",
        "/scratch/root-venv/lib/python3.14/site-packages",
    ):
        with pytest.raises(mounts.WorkerMountError):
            mounts.worker_path_to_host(path, mapping, role="artifacts")
    with pytest.raises(mounts.WorkerMountError, match="outside"):
        mounts.host_path_to_worker(tmp_path / "inputs" / "pytest.ini", mapping, role="artifacts")


def test_worker_evidence_ref_is_rehashed_only_inside_its_mapped_role(tmp_path: Path) -> None:
    mapping = _mount_map(tmp_path)
    raw = b"worker-produced junit bytes\n"
    receipt_path = tmp_path / "receipts" / "run" / "junit.xml"
    receipt_path.parent.mkdir()
    receipt_path.write_bytes(raw)
    worker_ref = {
        "path": "/mnt/e02-q2/receipts/run/junit.xml",
        "sha256": _digest(raw),
    }
    observed = mounts.verify_worker_evidence_ref(
        worker_ref, mapping, role="receipts", label="JUnit"
    )
    assert observed["host_path"] == str(receipt_path)
    assert observed["sha256"] == _digest(raw)
    raw_digest = _digest(raw)
    for invalid in (
        {
            "path": "/scratch/root-venv/lib/python3.14/site-packages/hidden.json",
            "sha256": raw_digest,
        },
        {"path": "/mnt/e02-q2/receipts-neighbor/junit.xml", "sha256": raw_digest},
        {"path": "/mnt/e02-q2/receipts/run/../junit.xml", "sha256": raw_digest},
    ):
        with pytest.raises(mounts.WorkerMountError):
            mounts.verify_worker_evidence_ref(invalid, mapping, role="receipts", label="JUnit")
    receipt_path.write_bytes(b"mutated after worker wrote its receipt\n")
    with pytest.raises(mounts.WorkerMountError, match="changed or was replayed"):
        mounts.verify_worker_evidence_ref(worker_ref, mapping, role="receipts", label="JUnit")


def test_mapping_rejects_overlaps_forbidden_volumes_and_mutated_bind_access(tmp_path: Path) -> None:
    mapping = _mount_map(tmp_path)
    overlap = copy.deepcopy(mapping)
    overlap["mounts"][1]["host_root"] = overlap["mounts"][0]["host_root"]
    with pytest.raises(mounts.WorkerMountError, match="overlap"):
        _validate_mapping(overlap)

    aliases_dependency = copy.deepcopy(mapping)
    aliases_dependency["mounts"][1]["worker_root"] = "/scratch/q2-inputs"
    with pytest.raises(mounts.WorkerMountError, match="dependency"):
        _validate_mapping(aliases_dependency)

    wrong_access = copy.deepcopy(mapping)
    wrong_access["mounts"][0]["access"] = "read-write"
    with pytest.raises(mounts.WorkerMountError, match="wrong access"):
        _validate_mapping(wrong_access)

    unsafe_profile = copy.deepcopy(mapping)
    unsafe_profile["profile"] = "../receipts"
    with pytest.raises(mounts.WorkerMountError, match="safe prefix component"):
        _validate_mapping(unsafe_profile)


def test_inspect_rejects_wrong_image_extra_mount_and_writable_dependency(tmp_path: Path) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    mapping = _mount_map(tmp_path)
    _validate_mapping(mapping)
    for corrupt in ("image", "extra", "volume"):
        actual = _inspect(contract, mapping)
        if corrupt == "image":
            actual["Config"]["Image"] = "ghcr.io/another/image@sha256:" + "0" * 64
        elif corrupt == "extra":
            actual["Mounts"].append(
                {
                    "Type": "bind",
                    "Source": str(tmp_path),
                    "Destination": "/mnt/e02-q2/unexpected",
                    "RW": False,
                }
            )
        else:
            actual["Mounts"][0]["RW"] = True
        with pytest.raises(mounts.WorkerMountError):
            mounts.validate_worker_container(actual, contract, mapping)
    wrong_limits = _inspect(contract, mapping)
    wrong_limits["HostConfig"]["Memory"] -= 1
    with pytest.raises(mounts.WorkerMountError, match="image or isolation"):
        mounts.validate_worker_container(wrong_limits, contract, mapping)


def test_field_limited_worker_inspect_receipt_recomputes_exact_binding(tmp_path: Path) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    mapping = _mount_map(tmp_path)
    container_id = "d" * 64
    expected_argv = mounts.worker_container_inspect_argv(contract, container_id)
    assert len(expected_argv) == 13
    assert all("Config.Env" not in " ".join(row["argv"]) for row in expected_argv)
    assert all("--context" in row["argv"] and "--config" in row["argv"] for row in expected_argv)
    actual = _inspect(contract, mapping)
    actual["Id"] = container_id
    field_values = {
        "Id": actual["Id"],
        "Image": actual["Image"],
        "Config.Image": actual["Config"]["Image"],
        "State.Running": json.dumps(actual["State"]["Running"]),
        "HostConfig.ReadonlyRootfs": json.dumps(actual["HostConfig"]["ReadonlyRootfs"]),
        "HostConfig.NetworkMode": actual["HostConfig"]["NetworkMode"],
        "HostConfig.Privileged": json.dumps(actual["HostConfig"]["Privileged"]),
        "HostConfig.AutoRemove": json.dumps(actual["HostConfig"]["AutoRemove"]),
        "HostConfig.CapAdd": json.dumps(actual["HostConfig"]["CapAdd"]),
        "HostConfig.Memory": json.dumps(actual["HostConfig"]["Memory"]),
        "HostConfig.MemorySwap": json.dumps(actual["HostConfig"]["MemorySwap"]),
        "HostConfig.NanoCpus": json.dumps(actual["HostConfig"]["NanoCpus"]),
        "Mounts": json.dumps(actual["Mounts"], separators=(",", ":")),
    }
    receipt = {
        "schema": "policyos.e02.q2.worker-container-inspect.v1",
        "commands": [
            {
                **command,
                "returncode": 0,
                "stdout": field_values[command["field"]],
                "stderr": "",
            }
            for command in expected_argv
        ],
    }
    assert mounts.validate_worker_container_inspect_receipt(
        receipt,
        contract,
        mapping,
        expected_container_id=container_id,
    ) == {"container_id": container_id, "image_id": contract["image"]["image_id"]}

    tampered_query = copy.deepcopy(receipt)
    tampered_query["commands"][8]["argv"][-2] = "{{.Config.Env}}"
    with pytest.raises(mounts.WorkerMountError, match="exact query"):
        mounts.validate_worker_container_inspect_receipt(
            tampered_query,
            contract,
            mapping,
            expected_container_id=container_id,
        )

    tampered_limit = copy.deepcopy(receipt)
    tampered_limit["commands"][9]["stdout"] = "0"
    with pytest.raises(mounts.WorkerMountError):
        mounts.validate_worker_container_inspect_receipt(
            tampered_limit,
            contract,
            mapping,
            expected_container_id=container_id,
        )


def test_probe_rejects_wrong_prefix_dependency_order_and_stale_container(tmp_path: Path) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    mapping = _mount_map(tmp_path)
    _validate_mapping(mapping)
    identity = mounts.validate_worker_container(_inspect(contract, mapping), contract, mapping)
    for corrupt in ("prefix", "order", "container", "input-sys-path", "sibling-profile"):
        probe = _probe(mapping, identity)
        if corrupt == "prefix":
            probe["sys_prefix"] = "/mnt/e02-q2/prefix-neighbor"
        elif corrupt == "order":
            probe["sys_path"] = list(reversed(probe["sys_path"]))
        elif corrupt == "container":
            probe["container_id"] = "0" * 64
        elif corrupt == "sibling-profile":
            probe["sys_path"].append("/mnt/e02-q2/prefix/source-wheel/lib/python3.14/site-packages")
        else:
            probe["sys_path"].append("/mnt/e02-q2/inputs")
        with pytest.raises(mounts.WorkerMountError):
            mounts.validate_worker_probe(probe, contract, mapping, container_identity=identity)


def test_entrypoint_install_plan_uses_selected_wheel_and_real_uv_recipe(tmp_path: Path) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    mapping = _mount_map(tmp_path)
    source = mapping["source"]
    plan_sha = mapping["plan_sha256"]
    artifact_sha = mapping["artifact_sha256"]
    node_sha = mapping["node_ids_sha256"]
    install = mounts.plan_installed_entrypoint(
        contract,
        mapping,
        expected_source=source,
        plan_sha256=plan_sha,
        profile=mapping["profile"],
        artifact_sha256=artifact_sha,
        node_ids_sha256=node_sha,
        wheel_filename="polisyos-0.1.0-py3-none-any.whl",
        entrypoint_name="ukraine-data",
    )
    assert install["dependency_site"] == contract["worker"]["dependency_site"]
    assert install["commands"] == [
        [
            contract["worker"]["python_executable"],
            "-I",
            "-m",
            "venv",
            "--without-pip",
            "/mnt/e02-q2/prefix/rebuilt-sdist-wheel",
        ],
        [
            "/usr/local/bin/uv",
            "pip",
            "install",
            "--offline",
            "--no-index",
            "--no-deps",
            "--no-cache",
            "--python",
            "/mnt/e02-q2/prefix/rebuilt-sdist-wheel/bin/python",
            "/mnt/e02-q2/artifacts/polisyos-0.1.0-py3-none-any.whl",
        ],
    ]
    assert install["dependency_bridge"]["content_utf8"] == (
        "import site; site.addsitedir(" + repr(contract["worker"]["dependency_site"]) + ")\n"
    )
    assert install["entrypoint"] == {
        "group": "console_scripts",
        "name": "ukraine-data",
        "value": "tools.ops_runners.ukraine_data_cli:main",
    }
    assert install["distribution"] == {"name": "polisyos", "version": "0.1.0"}
    assert install["wheel_metadata"]["wheel_sha256"] == artifact_sha
    assert install["scripts"] == install["prefix"] + "/bin"
    assert install["purelib"].startswith(install["prefix"] + "/lib/python3.14/")
    assert "/scratch/root-venv/bin/ukraine-data" not in install["commands"][1]
    compile(mounts.worker_probe_program(), "q2-worker-probe", "exec")
    compile(mounts._venv_sysconfig_code(), "q2-venv-sysconfig", "exec")
    compile(
        mounts._installed_wheel_readback_code("polisyos", "ukraine-data"),
        "q2-wheel-entrypoint-readback",
        "exec",
    )
    with pytest.raises(mounts.WorkerMountError, match="console entry point"):
        mounts.plan_installed_entrypoint(
            contract,
            mapping,
            expected_source=source,
            plan_sha256=plan_sha,
            profile=mapping["profile"],
            artifact_sha256=artifact_sha,
            node_ids_sha256=node_sha,
            wheel_filename="../selected.whl",
            entrypoint_name="ukraine-data",
        )


def test_entrypoint_plan_requires_requested_command_in_exact_wheel_metadata(
    tmp_path: Path,
) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    mapping = _mount_map(tmp_path)
    wheel_path = tmp_path / "artifacts" / "polisyos-0.1.0-py3-none-any.whl"
    wheel_path.write_bytes(_wheel_bytes(entrypoint="other-command = module:main"))
    mapping["artifact_sha256"] = _digest(wheel_path.read_bytes())
    with pytest.raises(mounts.WorkerMountError, match="omits the requested console entry point"):
        mounts.plan_installed_entrypoint(
            contract,
            mapping,
            expected_source=mapping["source"],
            plan_sha256=mapping["plan_sha256"],
            profile=mapping["profile"],
            artifact_sha256=mapping["artifact_sha256"],
            node_ids_sha256=mapping["node_ids_sha256"],
            wheel_filename="polisyos-0.1.0-py3-none-any.whl",
            entrypoint_name="ukraine-data",
        )


def test_each_profile_entrypoint_plan_binds_its_own_selected_wheel_and_prefix(
    tmp_path: Path,
) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    profiles = ("source-wheel", "rebuilt-sdist-wheel", "rebuilt-gcp-archive-wheel")
    observed_artifacts: set[str] = set()
    observed_prefixes: set[str] = set()
    shared_root = tmp_path / "shared-worker-mounts"
    mapping = _mount_map(shared_root)
    for profile in profiles:
        wheel_filename = f"polisyos-0.1.0-{profile}.whl"
        relative_wheel = f"wheels/{profile}/{wheel_filename}"
        wheel_path = shared_root / "artifacts" / relative_wheel
        wheel_path.parent.mkdir(parents=True)
        wheel_path.write_bytes(_wheel_bytes(profile_marker=profile))
        mapping["profile"] = profile
        mapping["artifact_sha256"] = _digest(wheel_path.read_bytes())
        install = mounts.plan_installed_entrypoint(
            contract,
            mapping,
            expected_source=mapping["source"],
            plan_sha256=mapping["plan_sha256"],
            profile=profile,
            artifact_sha256=mapping["artifact_sha256"],
            node_ids_sha256=mapping["node_ids_sha256"],
            wheel_relative_path=relative_wheel,
            entrypoint_name="ukraine-data",
        )
        assert install["profile"] == profile
        assert install["artifact_sha256"] == _digest(wheel_path.read_bytes())
        assert install["entrypoint"]["value"] == "tools.ops_runners.ukraine_data_cli:main"
        assert install["wheel_relative_path"] == relative_wheel
        assert install["wheel_path"] == f"/mnt/e02-q2/artifacts/{relative_wheel}"
        assert install["profile_prefix_mount"] == "/mnt/e02-q2/prefix"
        assert install["prefix"] == f"/mnt/e02-q2/prefix/{profile}"
        assert install["prefix"] not in observed_prefixes
        observed_artifacts.add(install["artifact_sha256"])
        observed_prefixes.add(install["prefix"])
    assert len(observed_artifacts) == len(profiles)
    assert len(observed_prefixes) == len(profiles)


def test_entrypoint_plan_rejects_artifact_mount_escape_and_ambiguous_wheel_path(
    tmp_path: Path,
) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    mapping = _mount_map(tmp_path)
    common = {
        "expected_source": mapping["source"],
        "plan_sha256": mapping["plan_sha256"],
        "profile": mapping["profile"],
        "artifact_sha256": mapping["artifact_sha256"],
        "node_ids_sha256": mapping["node_ids_sha256"],
        "entrypoint_name": "ukraine-data",
    }
    for invalid in (
        "../polisyos.whl",
        "wheels//polisyos.whl",
        "/outside/polisyos.whl",
        "wheels\\polisyos.whl",
    ):
        with pytest.raises(mounts.WorkerMountError, match="wheel path"):
            mounts.plan_installed_entrypoint(
                contract, mapping, wheel_relative_path=invalid, **common
            )
    with pytest.raises(mounts.WorkerMountError, match="wheel filename"):
        mounts.plan_installed_entrypoint(
            contract,
            mapping,
            wheel_filename="polisyos-0.1.0-py3-none-any.whl",
            wheel_relative_path="wheels/source-wheel/polisyos.whl",
            **common,
        )


def test_installed_entrypoint_receipt_reconciles_bytes_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    contract = mounts.validate_runtime_contract(_runtime_contract())
    mapping = _mount_map(tmp_path)
    install = mounts.plan_installed_entrypoint(
        contract,
        mapping,
        expected_source=mapping["source"],
        plan_sha256=mapping["plan_sha256"],
        profile=mapping["profile"],
        artifact_sha256=mapping["artifact_sha256"],
        node_ids_sha256=mapping["node_ids_sha256"],
        wheel_filename="polisyos-0.1.0-py3-none-any.whl",
        entrypoint_name="ukraine-data",
    )
    identity = mounts.validate_worker_container(_inspect(contract, mapping), contract, mapping)
    probe = _probe(mapping, identity)
    bridge = install["dependency_bridge"]
    bridge_path = mounts.worker_path_to_host(
        bridge["path"], mapping, role="profile-prefix", must_exist=False
    )
    bridge_path.parent.mkdir(parents=True)
    bridge_bytes = bridge["content_utf8"].encode("utf-8")
    bridge_path.write_bytes(bridge_bytes)
    script_path = mounts.worker_path_to_host(
        install["scripts"] + "/ukraine-data", mapping, role="profile-prefix", must_exist=False
    )
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_bytes = (
        "#!" + probe["python"] + "\n"
        "from tools.ops_runners.ukraine_data_cli import main\n"
        "raise SystemExit(main())\n"
    ).encode("utf-8")
    script_path.write_bytes(script_bytes)
    script_path.chmod(0o755)
    python_directory = script_path.parent
    python_target = probe["python_realpath"]
    for name in ("python", "python3", "python3.14"):
        link = python_directory / name
        if not link.exists() and not link.is_symlink():
            link.symlink_to(python_target)
    mode = script_path.stat().st_mode & 0o777
    entrypoint = install["entrypoint"]
    snapshot = mounts.snapshot_profile_prefix(mapping, probe)["sha256"]
    clean_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": _TMPFS_DESTINATION,
        "TMPDIR": _TMPFS_DESTINATION,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "UV_NO_CONFIG": "1",
    }
    expected_entries = sorted(
        [
            {"group": group, "name": name, "value": value}
            for group, values in install["wheel_entry_points"].items()
            for name, value in values.items()
        ],
        key=lambda row: (row["group"], row["name"]),
    )
    metadata_file_sha256 = install["wheel_metadata"]["metadata_file_sha256"]
    metadata_sha256 = mounts.sha256_bytes(mounts.canonical_json_bytes(metadata_file_sha256))
    script_path_value = install["scripts"] + "/ukraine-data"
    installed = {
        "name": "polisyos",
        "version": "0.1.0",
        "entries": expected_entries,
        "meta_hashes": metadata_file_sha256,
        "metadata_sha256": metadata_sha256,
        "script_path": script_path_value,
        "script_bytes": len(script_bytes),
        "script_sha256": _digest(script_bytes),
        "script_mode": mode,
        "script_shebang": "#!" + probe["python"],
        "python": probe["python"],
        "prefix": install["prefix"],
        "purelib": install["purelib"],
        "scripts": install["scripts"],
    }
    python = install["prefix"] + "/bin/python"
    preflight_env = [
        clean_env,
        clean_env,
        clean_env,
        {
            **clean_env,
            "E02_Q2_CONTAINER_ID": probe["container_id"],
            "E02_Q2_IMAGE_ID": probe["image_id"],
            "E02_Q2_DEPENDENCY_SITE": install["dependency_site"],
        },
    ]
    receipt = {
        "schema": mounts.ENTRYPOINT_INSTALL_SCHEMA,
        "source": install["source"],
        "plan_sha256": install["plan_sha256"],
        "profile": install["profile"],
        "artifact_sha256": install["artifact_sha256"],
        "runtime_contract_sha256": install["runtime_contract_sha256"],
        "mount_map_sha256": install["mount_map_sha256"],
        "wheel_metadata_sha256": install["wheel_metadata_sha256"],
        "wheel_entry_points_sha256": install["wheel_entry_points_sha256"],
        "prefix": install["prefix"],
        "purelib": install["purelib"],
        "scripts": install["scripts"],
        "dependency_bridge_before": {
            "exists": True,
            "bytes": len(bridge_bytes),
            "sha256": _digest(bridge_bytes),
        },
        "dependency_bridge_after": {
            "exists": True,
            "bytes": len(bridge_bytes),
            "sha256": _digest(bridge_bytes),
        },
        "entrypoint": {
            **entrypoint,
            "derived_from_selected_distribution": True,
        },
        "runtime_probe": probe,
        "preflight_outputs": [
            _observation(
                "measured uv version",
                ["/usr/local/bin/uv", "--version"],
                "uv " + install["installer_version"] + "\n",
                preflight_env[0],
            ),
            _observation(
                "fresh venv sysconfig",
                [python, "-I", "-c", mounts._venv_sysconfig_code()],
                json.dumps(
                    {
                        "prefix": install["prefix"],
                        "purelib": install["purelib"],
                        "scripts": install["scripts"],
                        "executable": python,
                        "realpath": probe["python_realpath"],
                    },
                    sort_keys=True,
                ),
                preflight_env[1],
            ),
            _observation(
                "installed wheel entrypoint readback",
                [
                    python,
                    "-I",
                    "-c",
                    mounts._installed_wheel_readback_code("polisyos", "ukraine-data"),
                ],
                json.dumps(installed, sort_keys=True),
                preflight_env[2],
            ),
            _observation(
                "selected worker profile probe",
                [python, "-I", "-c", mounts.worker_probe_program()],
                json.dumps(probe, sort_keys=True),
                preflight_env[3],
            ),
        ],
        "install_outputs": [
            {
                "label": label,
                "argv": argv,
                "cwd": _TMPFS_DESTINATION,
                "env": clean_env,
                "returncode": 0,
                "stdout": "",
                "stderr": "",
            }
            for label, argv in zip(
                ("fresh pip-free profile venv", "selected wheel install"),
                install["commands"],
                strict=True,
            )
        ],
        "distribution": {
            "name": "polisyos",
            "version": "0.1.0",
            "metadata_sha256": metadata_sha256,
            "metadata_file_sha256": metadata_file_sha256,
        },
        "script": {
            "path": install["scripts"] + "/ukraine-data",
            "bytes": len(script_bytes),
            "sha256": _digest(script_bytes),
            "mode": mode,
            "shebang": "#!" + probe["python"],
            "pre_install_exists": False,
        },
        "installed_prefix_snapshot_sha256": snapshot,
    }
    validated = mounts.validate_entrypoint_install_receipt(
        receipt,
        install,
        probe,
        mapping,
        container_identity=identity,
        expected_distribution_name="polisyos",
        expected_distribution_version="0.1.0",
    )
    assert validated["script"]["path"].endswith("/bin/ukraine-data")
    assert (
        validated["distribution"]["metadata_file_sha256"]
        == install["wheel_metadata"]["metadata_file_sha256"]
    )
    forged_readback = copy.deepcopy(receipt)
    readback_row = next(
        row
        for row in forged_readback["preflight_outputs"]
        if row["label"] == "installed wheel entrypoint readback"
    )
    forged_value = json.loads(readback_row["stdout"])
    forged_value["entries"][0]["value"] = "somebody_else:main"
    readback_row["stdout"] = json.dumps(forged_value, sort_keys=True)
    with pytest.raises(mounts.WorkerMountError, match="actual installer metadata/script readback"):
        mounts.validate_entrypoint_install_receipt(
            forged_readback,
            install,
            probe,
            mapping,
            container_identity=identity,
            expected_distribution_name="polisyos",
            expected_distribution_version="0.1.0",
        )
    script_path.write_bytes(script_bytes + b"# altered\n")
    with pytest.raises(mounts.WorkerMountError, match="host-read entrypoint"):
        mounts.validate_entrypoint_install_receipt(
            receipt,
            install,
            probe,
            mapping,
            container_identity=identity,
            expected_distribution_name="polisyos",
            expected_distribution_version="0.1.0",
        )
    script_path.write_bytes(script_bytes)
    wrong_source = copy.deepcopy(receipt)
    wrong_source["profile"] = "source-wheel"
    with pytest.raises(mounts.WorkerMountError, match="another source/profile/artifact"):
        mounts.validate_entrypoint_install_receipt(
            wrong_source,
            install,
            probe,
            mapping,
            container_identity=identity,
            expected_distribution_name="polisyos",
            expected_distribution_version="0.1.0",
        )
    wrong_entrypoint = copy.deepcopy(install)
    wrong_entrypoint["entrypoint"] = {
        "group": "console_scripts",
        "name": "ukraine-data",
        "value": "somebody_else:main",
    }
    with pytest.raises(mounts.WorkerMountError, match="metadata differs"):
        mounts.validate_entrypoint_install_receipt(
            receipt,
            wrong_entrypoint,
            probe,
            mapping,
            container_identity=identity,
            expected_distribution_name="polisyos",
            expected_distribution_version="0.1.0",
        )
    (python_directory / "extra.txt").write_text("changed after receipt", encoding="utf-8")
    with pytest.raises(mounts.WorkerMountError, match="profile prefix changed"):
        mounts.validate_entrypoint_install_receipt(
            receipt,
            install,
            probe,
            mapping,
            container_identity=identity,
            expected_distribution_name="polisyos",
            expected_distribution_version="0.1.0",
        )
    (tmp_path / "artifacts" / "polisyos-0.1.0-py3-none-any.whl").write_bytes(
        _wheel_bytes(entrypoint="ukraine-data = attacker:main")
    )
    with pytest.raises(mounts.WorkerMountError, match="source-bound artifact"):
        mounts.validate_entrypoint_install_receipt(
            receipt,
            install,
            probe,
            mapping,
            container_identity=identity,
            expected_distribution_name="polisyos",
            expected_distribution_version="0.1.0",
        )


def test_readonly_input_and_artifact_member_set_is_complete(tmp_path: Path) -> None:
    mapping = _mount_map(tmp_path)
    _validate_mapping(mapping)
    artifact_raw = (tmp_path / "artifacts/polisyos-0.1.0-py3-none-any.whl").read_bytes()
    input_raw = (tmp_path / "inputs/pytest.ini").read_bytes()
    result = mounts.verify_mapped_tree(
        mapping,
        role="artifacts",
        expected_files=[
            {
                "path": "polisyos-0.1.0-py3-none-any.whl",
                "bytes": len(artifact_raw),
                "sha256": _digest(artifact_raw),
            }
        ],
    )
    assert result["member_count"] == 1
    (tmp_path / "artifacts/extra.whl").write_bytes(b"unselected profile\n")
    with pytest.raises(mounts.WorkerMountError, match="unexpected"):
        mounts.verify_mapped_tree(
            mapping,
            role="artifacts",
            expected_files=[
                {
                    "path": "polisyos-0.1.0-py3-none-any.whl",
                    "bytes": len(artifact_raw),
                    "sha256": _digest(artifact_raw),
                }
            ],
        )
    (tmp_path / "artifacts/extra.whl").unlink()
    assert (
        mounts.verify_mapped_tree(
            mapping,
            role="inputs",
            expected_files=[
                {"path": "pytest.ini", "bytes": len(input_raw), "sha256": _digest(input_raw)}
            ],
        )["member_count"]
        == 1
    )


def test_readonly_mount_tree_rejects_symlinks_even_with_matching_target_bytes(
    tmp_path: Path,
) -> None:
    mapping = _mount_map(tmp_path)
    _validate_mapping(mapping)
    alias = tmp_path / "artifacts" / "alias.whl"
    alias.symlink_to(tmp_path / "artifacts" / "profile.whl")
    raw = (tmp_path / "artifacts/polisyos-0.1.0-py3-none-any.whl").read_bytes()
    with pytest.raises(mounts.WorkerMountError, match="symlink"):
        mounts.verify_mapped_tree(
            mapping,
            role="artifacts",
            expected_files=[
                {
                    "path": "polisyos-0.1.0-py3-none-any.whl",
                    "bytes": len(raw),
                    "sha256": _digest(raw),
                }
            ],
        )

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

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
RAW = (
    POSTIMAGE_ROOT / "policy-engine/tools/quality/validation/q2_composite"
    if POSTIMAGE_ROOT is not None
    else REPO_ROOT / "policy-engine/tools/quality/validation/q2_composite"
)
R6 = RAW
sys.path.insert(0, str(RAW))

import profile_composite as composite  # noqa: E402
import profile_partition_runner as partition_runner  # noqa: E402
import split_consumer  # noqa: E402
import test_worker_mounts as worker_fixtures  # noqa: E402
import worker_mounts as worker_mounts  # noqa: E402
from split_protocol import (  # noqa: E402
    PROFILE_CHAIN_KEYS,
    build_source_inventory,
    canonical_json_bytes,
    snapshot_installed_tree,
)

LA029_ID = (
    "tests/unit/data_forge/domains/ukraine/test_installed_wheel_no_checkout.py::"
    "test_installed_wheel_without_checkout_reports_gate_unavailable"
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def node_digest(values: list[str]) -> str:
    return digest(("\n".join(values) + "\n").encode())


def write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))
    return path


def evidence(root: Path, name: str, raw: bytes) -> dict[str, str]:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"path": name, "sha256": digest(raw)}


def json_evidence(root: Path, name: str, value: object) -> dict[str, str]:
    return evidence(root, name, canonical_json_bytes(value))


def test_platform_placement_uses_actual_function_and_class_markers(tmp_path: Path) -> None:
    product = tmp_path / "policy-engine"
    source = (
        b"import sys\n"
        b"import platform as host_platform\n"
        b"import pytest\n"
        b"from pytest.mark import skipif as skip_on\n"
        b"@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux worker')\n"
        b"def test_linux_only(): pass\n"
        b"@skip_on(host_platform.system() != 'Linux', reason='Linux worker alias')\n"
        b"def test_linux_alias(): pass\n"
        b"@pytest.mark.skipif(sys.platform.startswith('win'), reason='not Windows')\n"
        b"class TestPortable:\n"
        b"    def test_portable(self): pass\n"
    )
    path = product / "tests/test_placement.py"
    path.parent.mkdir(parents=True)
    path.write_bytes(source)
    ids = [
        "tests/test_placement.py::TestPortable::test_portable",
        "tests/test_placement.py::test_linux_alias",
        "tests/test_placement.py::test_linux_only",
    ]
    plan = composite.derive_platform_placement(
        product,
        ids,
        source_file_sha256={"tests/test_placement.py": digest(source)},
        host_system="Darwin",
        expected_count=3,
    )
    assert plan["host_node_ids"] == ["tests/test_placement.py::TestPortable::test_portable"]
    assert plan["worker_node_ids"] == [
        "tests/test_placement.py::test_linux_alias",
        "tests/test_placement.py::test_linux_only",
    ]
    assert plan["cases"][1]["skip_on"] == {"Darwin": True, "Linux": False}

    source_without_marker = source.replace(
        b"@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux worker')\n",
        b"",
    )
    path.write_bytes(source_without_marker)
    with pytest.raises(composite.ProfileCompositeError, match="differs from its frozen pin"):
        composite.derive_platform_placement(
            product,
            ids,
            source_file_sha256={"tests/test_placement.py": digest(source)},
            host_system="Darwin",
            expected_count=3,
        )
    changed = composite.derive_platform_placement(
        product,
        ids,
        source_file_sha256={"tests/test_placement.py": digest(source_without_marker)},
        host_system="Darwin",
        expected_count=3,
    )
    assert changed["worker_node_ids"] == ["tests/test_placement.py::test_linux_alias"]
    assert changed["host_node_ids"] == [
        "tests/test_placement.py::TestPortable::test_portable",
        "tests/test_placement.py::test_linux_only",
    ]

    source_with_unbound_skipif = source.replace(
        b"@pytest.mark.skipif(sys.platform.startswith('win'), reason='not Windows')",
        b"@custom.skipif(sys.platform.startswith('win'), reason='not Windows')",
    )
    path.write_bytes(source_with_unbound_skipif)
    with pytest.raises(composite.ProfileCompositeError, match="unbound skipif"):
        composite.derive_platform_placement(
            product,
            ids,
            source_file_sha256={"tests/test_placement.py": digest(source_with_unbound_skipif)},
            host_system="Darwin",
            expected_count=3,
        )


def test_platform_placement_recomputes_the_canonical_la029_source() -> None:
    repo = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (
            parent
            / Path("policy-engine/tests/unit/data_forge/domains/ukraine")
            / "test_installed_wheel_no_checkout.py"
        ).is_file()
    )
    product = repo / "policy-engine"
    source = product / "tests/unit/data_forge/domains/ukraine/test_installed_wheel_no_checkout.py"
    placement = composite.derive_platform_placement(
        product,
        [LA029_ID],
        source_file_sha256={source.relative_to(product).as_posix(): digest(source.read_bytes())},
        host_system="Darwin",
        expected_count=1,
    )
    assert placement["worker_node_ids"] == [LA029_ID]
    assert placement["host_node_ids"] == []


def test_parameterized_node_ids_keep_case_identity_and_refuse_local_marks(tmp_path: Path) -> None:
    product = tmp_path / "policy-engine"
    source = (
        b"import sys\n"
        b"import pytest\n"
        b"@pytest.mark.parametrize('value', ['portable'], ids=['safe'])\n"
        b"def test_portable(value): pass\n"
        b"@pytest.mark.parametrize('value', [pytest.param('linux', id='linux', "
        b"marks=pytest.mark.skipif(not sys.platform.startswith('linux'), reason='linux only'))])\n"
        b"def test_local_skip(value): pass\n"
    )
    path = product / "tests/test_params.py"
    path.parent.mkdir(parents=True)
    path.write_bytes(source)
    placement = composite.derive_platform_placement(
        product,
        ["tests/test_params.py::test_portable[safe]"],
        source_file_sha256={"tests/test_params.py": digest(source)},
        host_system="Darwin",
        expected_count=1,
    )
    assert placement["cases"][0]["parameter_id"] == "safe"
    assert placement["host_node_ids"] == ["tests/test_params.py::test_portable[safe]"]
    with pytest.raises(composite.ProfileCompositeError, match="parameter-local mark"):
        composite.derive_platform_placement(
            product,
            ["tests/test_params.py::test_local_skip[linux]"],
            source_file_sha256={"tests/test_params.py": digest(source)},
            host_system="Darwin",
            expected_count=1,
        )


def _write_fixture_product(tmp_path: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    repo = tmp_path / "source-repo"
    product = repo / "policy-engine"
    files = {
        "src/polisyos/__init__.py": b"PACKAGE = True\n",
        "src/polisyos/data/_resources.py": b"def resolve(name): return name\n",
        "src/polisyos/data/_resources/__init__.py": b"",
        "tools/__init__.py": b"",
        "tools/q2/consumer.py": b"def consume(): return True\n",
        "data/owned/catalog-default.json": b'{"name":"default"}\n',
        "data/owned/digest-registry.toml": b"[registry]\ncurrent = true\n",
        "data/owned/worker-profile.bin": b"worker-profile-bytes\n",
    }
    for relative, payload in files.items():
        path = product / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    asset_rows = [
        {
            "source": source,
            "archive": f"policy-engine/{source}",
            "wheel": wheel,
            "bytes": len(files[source]),
            "sha256": digest(files[source]),
        }
        for source, wheel in (
            (
                "data/owned/catalog-default.json",
                "polisyos/data_forge/domains/catalog/_resources/default.json",
            ),
            (
                "data/owned/digest-registry.toml",
                "polisyos/foundry/methods/catalog/_resources/registry.toml",
            ),
            (
                "data/owned/worker-profile.bin",
                "polisyos/foundry/methods/catalog/causal/_dowhy_profile/worker.bin",
            ),
        )
    ]
    force_include = {row["source"]: row["wheel"] for row in asset_rows}
    hatch = (
        '[build.targets.wheel]\npackages = ["src/polisyos", "tools"]\n'
        "[build.targets.wheel.force-include]\n"
        + "".join(
            f"{json.dumps(source)} = {json.dumps(target)}\n"
            for source, target in force_include.items()
        )
        + "[build.targets.sdist]\ninclude = ["
        + ", ".join(json.dumps(source) for source in force_include)
        + "]\n"
    )
    (product / "hatch.toml").write_text(hatch, encoding="utf-8")
    (product / "pyproject.toml").write_text(
        '[project]\nname = "polisyos"\nversion = "0.0.0"\n', encoding="utf-8"
    )
    gcp = product / "ops/cloud/gcp/package_repo.sh"
    gcp.parent.mkdir(parents=True)
    gcp.write_text(
        "#!/bin/bash\npython3 - << 'PY'\n"
        'include_paths = ["policy-engine/src", "policy-engine/tools"]\n'
        'skip_parts = {"__pycache__", ".git"}\n'
        'skip_suffixes = {".pyc", ".pyo"}\n'
        'skip_names = {".DS_Store"}\nPY\n',
        encoding="utf-8",
    )

    current_repo = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (
            parent
            / Path(
                "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw"
            )
            / "run.py"
        ).is_file()
    )
    q2_rel = Path(
        "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw"
    )
    target_runner = product / q2_rel / "run.py"
    target_supplemental = product / q2_rel / "supplemental_run.py"
    target_runner.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(current_repo / "policy-engine" / q2_rel / "run.py", target_runner)
    shutil.copyfile(
        current_repo / "policy-engine" / q2_rel / "supplemental_run.py", target_supplemental
    )

    current_test_root = current_repo / "policy-engine/tests/unit/data_forge/domains/ukraine"
    shutil.copyfile(current_repo / "policy-engine/pytest.ini", product / "pytest.ini")
    data_forge_conftest = product / "tests/unit/data_forge/conftest.py"
    data_forge_conftest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        current_repo / "policy-engine/tests/unit/data_forge/conftest.py", data_forge_conftest
    )
    la029_path = (
        product / "tests/unit/data_forge/domains/ukraine/test_installed_wheel_no_checkout.py"
    )
    la029_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(current_test_root / "test_installed_wheel_no_checkout.py", la029_path)
    primary_sources = {
        "tests/unit/test_installed_catalog_defaults.py": b"def test_catalog():\n    assert True\n",
        "tests/unit/test_extra.py": b"def test_extra():\n    assert True\n",
    }
    for relative, payload in primary_sources.items():
        path = product / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    supplemental_source = product / "tests/unit/test_supplemental.py"
    supplemental_source.write_text("def test_supplemental():\n    assert True\n", encoding="utf-8")

    baseline_xml = (
        b'<testsuite><testcase classname="test_installed_catalog_defaults" '
        b'name="test_catalog" /></testsuite>'
    )
    baseline_path = product / "tests/fixtures/q2-baseline.xml.gz"
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_bytes(gzip.compress(baseline_xml, mtime=0))

    git = shutil.which("git")
    assert git is not None
    git_path = str(Path(git).resolve())
    git_init = subprocess.run(  # noqa: S603 - executable is resolved and argv is fixture-local.
        [git_path, "-C", str(repo), "init", "-q"], capture_output=True, text=True
    )
    assert git_init.returncode == 0, git_init.stderr
    subprocess.run(  # noqa: S603 - executable is resolved and argv is fixture-local.
        [git_path, "-C", str(repo), "add", "policy-engine"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(  # noqa: S603 - executable is resolved and argv is fixture-local.
        [
            git_path,
            "-C",
            str(repo),
            "-c",
            "user.name=Q2 fixture",
            "-c",
            "user.email=q2@example.invalid",
            "commit",
            "-qm",
            "fixture source",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    identity = composite._git_source_identity(product)[1]
    return product, identity, {"assets": asset_rows, "files": files}


def _test_manifests(
    root: Path, product: Path, source: dict[str, str], assets: list[dict[str, Any]]
) -> tuple[Path, Path, Path, dict[str, str], list[str], list[str]]:
    la029 = LA029_ID
    baseline_id = "tests/unit/test_installed_catalog_defaults.py::test_catalog"
    extra_id = "tests/unit/test_extra.py::test_extra"
    primary_ids = sorted([baseline_id, extra_id, la029])
    supplemental_ids = ["tests/unit/test_supplemental.py::test_supplemental"]
    primary_paths = sorted({node_id.split("::", 1)[0] for node_id in primary_ids})
    source_hashes = {
        relative: digest((product / relative).read_bytes()) for relative in primary_paths
    }
    baseline_rel = "tests/fixtures/q2-baseline.xml.gz"
    baseline_raw = (product / baseline_rel).read_bytes()
    manifest = {
        "schema_version": 1,
        "candidate_baseline": {
            "source_sha": source["commit"],
            "source_tree": source["tree"],
            "force_include_count": len(assets),
            "force_include_assets": assets,
        },
        "original_q2_suite": {
            "baseline_junit_path": baseline_rel,
            "baseline_junit_sha256": digest(baseline_raw),
            "baseline_case_count": 1,
            "test_paths": ["tests/unit/test_installed_catalog_defaults.py"],
        },
        "additional_installed_consumers": {
            "dependency_profile": {
                "test_path": "tests/unit/test_extra.py",
                "selectors": ["test_extra"],
            },
            "canonical_bridge_and_worker": {
                "test_path": (
                    "tests/unit/data_forge/domains/ukraine/test_installed_wheel_no_checkout.py"
                ),
                "selectors": ["test_installed_wheel_without_checkout_reports_gate_unavailable"],
                "fixture_paths": {},
            },
        },
    }
    manifest["current_primary_suite"] = {
        "selection": "fixture complete source selector",
        "source_file_sha256": source_hashes,
        "selected_node_count": len(primary_ids),
        "selected_node_ids_sha256": node_digest(primary_ids),
        "selected_node_ids_sha256_algorithm": "sha256-newline-delimited",
        "selected_node_ids": primary_ids,
        "historical_baseline_subset": {
            "name": "fixture baseline and declared consumers",
            "selected_node_count": len(primary_ids),
            "selected_node_ids_sha256": node_digest(primary_ids),
        },
    }
    supplemental_rel = "tests/unit/test_supplemental.py"
    supplemental_manifest = {
        "schema_version": 1,
        "supplemental_suite": {
            "test_path": supplemental_rel,
            "test_sha256": digest((product / supplemental_rel).read_bytes()),
            "selectors": ["test_supplemental"],
            "selected_node_ids": supplemental_ids,
            "expected_node_count": len(supplemental_ids),
            "selected_node_ids_sha256": node_digest(supplemental_ids),
        },
    }
    manifest_path = write_json(root / "primary-manifest.json", manifest)
    supplemental_path = write_json(root / "supplemental-manifest.json", supplemental_manifest)
    manifest_sha = digest(manifest_path.read_bytes())
    supplemental_sha = digest(supplemental_path.read_bytes())
    profiles = list(PROFILE_CHAIN_KEYS)
    audit = {
        "schema_version": 1,
        "status": "source_preflight_exact",
        "source_sha": source["commit"],
        "source_tree": source["tree"],
        "source_object_and_actual_collection_reconcile": True,
        "capsule_bindings_current": True,
        "frozen_checkout_clean_tracked": True,
        "build_started": False,
        "install_started": False,
        "tests_executed": False,
        "pytest_collection_only": True,
        "runner_limitations": [],
        "primary": {
            "current_manifest_sha256": manifest_sha,
            "source_derived_ids": len(primary_ids),
            "source_derived_node_ids": primary_ids,
            "source_derived_ids_sha256": node_digest(primary_ids),
        },
        "supplemental": {
            "current_manifest_sha256": supplemental_sha,
            "source_derived_ids": len(supplemental_ids),
            "source_derived_node_ids": supplemental_ids,
            "source_derived_ids_sha256": node_digest(supplemental_ids),
        },
        "profiles": profiles,
        "primary_runner_profile_names": profiles,
        "supplemental_runner_profile_names": profiles,
        "source_derived_profile_case_count": len(profiles)
        * (len(primary_ids) + len(supplemental_ids)),
    }
    audit_path = write_json(root / "source-audit.json", audit)
    return (
        manifest_path,
        supplemental_path,
        audit_path,
        source_hashes,
        primary_ids,
        supplemental_ids,
    )


def _owner_inventory(assets: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [{key: row[key] for key in ("source", "wheel", "bytes", "sha256")} for row in assets]
    named = [
        {"name": "catalog-default", "source": assets[0]["source"], "wheel": assets[0]["wheel"]},
        {"name": "digest-registry", "source": assets[1]["source"], "wheel": assets[1]["wheel"]},
        {"name": "worker-profile", "source": assets[2]["source"], "wheel": assets[2]["wheel"]},
    ]
    return {
        "schema": "polisyos.packaged-resource-contract.v1",
        "assets": rows,
        "owners": {
            "catalog_defaults": [named[0]],
            "digest_registry": named[1],
            "worker_profile_assets": [named[2]],
        },
    }


def _fixture_wheel_bytes(profile: str, assets: list[dict[str, Any]], product_root: Path) -> bytes:
    """Return a controlled valid wheel for receipt/barrier tests, not a build witness."""
    buffer = io.BytesIO()
    dist_info = "polisyos-0.0.0.dist-info"
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        for name, raw in (
            (f"{dist_info}/METADATA", b"Metadata-Version: 2.3\nName: polisyos\nVersion: 0.0.0\n\n"),
            (f"{dist_info}/WHEEL", b"Wheel-Version: 1.0\nRoot-Is-Purelib: true\n\n"),
            (
                f"{dist_info}/entry_points.txt",
                b"[console_scripts]\nukraine-data = tools.q2.consumer:main\n",
            ),
            (f"{dist_info}/RECORD", b""),
            ("polisyos/__init__.py", b"PACKAGE = True\n"),
            ("tools/__init__.py", b"TOOLS = True\n"),
            ("tools/q2/consumer.py", b"def main():\n    return 0\n"),
            (f"q2-profile-{profile}.txt", profile.encode("utf-8")),
        ):
            archive.writestr(name, raw)
        for asset in assets:
            archive.writestr(asset["wheel"], (product_root / asset["source"]).read_bytes())
    return buffer.getvalue()


def _fixture_mount_map(
    root: Path, plan: dict[str, Any], profile: str, runtime: dict[str, Any]
) -> dict[str, Any]:
    run = next(
        row
        for row in plan["run_plan"]
        if row["profile"] == profile and row["executor"] == "linux-worker"
    )
    mount_root = root / "worker-mounts"
    host_roots = {
        role: mount_root / role for role in ("artifacts", "inputs", "profile-prefix", "receipts")
    }
    for path in host_roots.values():
        path.mkdir(parents=True, exist_ok=True)
    return worker_mounts.build_mount_map(
        source=plan["source"],
        plan_sha256=plan["plan_sha256"],
        profile=profile,
        artifact_sha256=run["artifact_sha256"],
        node_ids_sha256=run["node_ids_sha256"],
        runtime_contract=runtime,
        host_roots=host_roots,
        worker_roots={
            "artifacts": "/mnt/e02-q2/artifacts",
            "inputs": "/mnt/e02-q2/inputs",
            "profile-prefix": "/mnt/e02-q2/prefix",
            "receipts": "/mnt/e02-q2/receipts",
        },
    )


def _fixture_worker_inspect(
    runtime: dict[str, Any], mapping: dict[str, Any], container_id: str
) -> dict[str, Any]:
    """Create schema-complete synthetic inspect output for the controlled fixture."""
    actual = worker_fixtures._inspect(runtime, mapping)
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
    commands = worker_mounts.worker_container_inspect_argv(runtime, container_id)
    return {
        "schema": "policyos.e02.q2.worker-container-inspect.v1",
        "commands": [
            {
                **command,
                "returncode": 0,
                "stdout": field_values[command["field"]],
                "stderr": "",
            }
            for command in commands
        ],
    }


def _fixture_worker_probe(
    runtime: dict[str, Any], mapping: dict[str, Any], container_id: str
) -> dict[str, Any]:
    prefix = f"/mnt/e02-q2/prefix/{mapping['profile']}"
    purelib = prefix + "/lib/python3.14/site-packages"
    return {
        "schema": worker_mounts.WORKER_PROBE_SCHEMA,
        "container_id": container_id,
        "image_id": runtime["image"]["image_id"],
        "container_hostname": container_id[:12],
        "platform_system": "Linux",
        "sys_platform": "linux",
        "machine": "aarch64",
        "python": prefix + "/bin/python",
        "python_realpath": runtime["worker"]["python_realpath"],
        "python_version": runtime["worker"]["python_version"],
        "sys_prefix": prefix,
        "purelib": purelib,
        "scripts": prefix + "/bin",
        "dependency_site": runtime["worker"]["dependency_site"],
        "pytest_origin": runtime["worker"]["pytest_origin"],
        "sys_path": [
            purelib,
            runtime["worker"]["dependency_site"],
            "/opt/uv-python/cpython-3.14.0-linux-aarch64-gnu/lib/python3.14",
            "/opt/uv-python/cpython-3.14.0-linux-aarch64-gnu/lib/python3.14/lib-dynload",
        ],
        "installer_path": runtime["installer"]["path"],
        "installer_version": runtime["installer"]["version"],
        "installer_sha256": runtime["installer"]["sha256"],
    }


def _primary_execution(
    root: Path,
    plan: dict[str, Any],
    profile: str,
    executor: str,
    source_checkout_root: Path,
    resource_assets: list[dict[str, Any]],
) -> Path:
    run = next(
        row for row in plan["run_plan"] if row["profile"] == profile and row["executor"] == executor
    )
    output = root / profile / executor
    target = output / "installed"
    (target / "polisyos").mkdir(parents=True)
    (target / "tools").mkdir()
    (target / "polisyos/__init__.py").write_text("PACKAGE=True\n", encoding="utf-8")
    (target / "tools/__init__.py").write_text("TOOLS=True\n", encoding="utf-8")
    for row in resource_assets:
        path = target / row["wheel"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((source_checkout_root / "policy-engine" / row["source"]).read_bytes())
    dependency_site = output / "dependencies"
    dependency_site.mkdir(parents=True, exist_ok=True)
    origins = {}
    for package in ("polisyos", "tools"):
        module_file = target / package / "__init__.py"
        origins[package] = {
            "file": str(module_file),
            "resolved_file": str(module_file.resolve()),
            "spec_origin": str(module_file),
            "resolved_spec_origin": str(module_file.resolve()),
        }
    origin = {
        "verified": True,
        "errors": [],
        "purelib": str(target.resolve()),
        "dependency_site": str(dependency_site.resolve()),
        "sys_path": [str(target.resolve()), str(dependency_site.resolve())],
        "origins": origins,
    }
    node_ids = run["node_ids"]
    classes = []
    for node_id in node_ids:
        path, selector = node_id.split("::", 1)
        if path == "tests/unit/test_installed_catalog_defaults.py":
            classname = "test_installed_catalog_defaults"
        else:
            classname = path[:-3].replace("/", ".")
        classes.append(f'<testcase classname="{classname}" name="{selector}" />')
    junit = ("<testsuite>" + "".join(classes) + "</testsuite>").encode()
    target_snapshot = snapshot_installed_tree(target)
    result = {
        "schema": composite.EXECUTION_SCHEMA,
        "source": plan["source"],
        "input_pins": plan["input_pins"],
        "plan_sha256": plan["plan_sha256"],
        "profile": profile,
        "executor": executor,
        "artifact_sha256": run["artifact_sha256"],
        "runner_sha256": plan["input_pins"]["consumer_runner_sha256"],
        "returncode": 0,
        "execution_identity": json_evidence(
            output,
            "identity.json",
            {
                "schema": "policyos.e02.q2.execution-identity.v1",
                "source": plan["source"],
                "platform_system": "Darwin" if executor == "host" else "Linux",
                "sys_platform": "darwin" if executor == "host" else "linux",
                "machine": "test-fixture",
                "python": sys.executable,
                "python_version": list(sys.version_info[:3]),
                "runner_sha256": plan["input_pins"]["consumer_runner_sha256"],
                "source_checkout_root": str(source_checkout_root.resolve()),
            },
        ),
        "collected_node_ids": json_evidence(output, "collected-nodeids.json", node_ids),
        "junit": evidence(output, "junit.xml", junit),
        "origin_proof": json_evidence(output, "origin.json", origin),
        "installed_target_proof": json_evidence(
            output,
            "target.json",
            {
                "purelib": str(target.resolve()),
                "dependency_site": str(dependency_site.resolve()),
                "node_ids": len(node_ids),
            },
        ),
        "resource_proof": json_evidence(
            output,
            "resources.json",
            {
                "schema": "polisyos.packaged-resource-contract.v1",
                "runtime_owner_targets": sorted(row["wheel"] for row in resource_assets),
                "importlib_resources": {
                    row["wheel"]: {"bytes": row["bytes"], "sha256": row["sha256"]}
                    for row in resource_assets
                },
            },
        ),
        "poison_proof": json_evidence(
            output,
            "poison.json",
            {
                "verified": True,
                "catalog_readers": {
                    "catalog-default": str((target / resource_assets[0]["wheel"]).resolve())
                },
                "dependency_registry": str((target / resource_assets[1]["wheel"]).resolve()),
                "dowhy_worker_directory": str(
                    (target / resource_assets[2]["wheel"]).parent.resolve()
                ),
                "origins": origins,
                "poison_neighbor_cwd": str(output),
            },
        ),
        "target_before_snapshot": json_evidence(output, "target-before.json", target_snapshot),
        "target_after_snapshot": json_evidence(output, "target-after.json", target_snapshot),
        "stdout": evidence(output, "stdout.txt", b"pytest stdout\n"),
        "stderr": evidence(output, "stderr.txt", b"pytest stderr\n"),
        "transport_proof": None,
    }
    if executor == "linux-worker":
        transport_root = output / "transport"
        transport_rows = []
        for artifact in plan["artifacts"]:
            transport_path = transport_root / f"{artifact['profile']}.whl"
            transport_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(artifact["path"], transport_path)
            transport_rows.append(
                {
                    "profile": artifact["profile"],
                    "chain_key": artifact["chain_key"],
                    "path": transport_path.relative_to(output).as_posix(),
                    "bytes": artifact["bytes"],
                    "sha256": artifact["sha256"],
                }
            )
        result["transport_proof"] = json_evidence(
            output,
            "transport.json",
            {
                "source": plan["source"],
                "input_pins": plan["input_pins"],
                "transport_status": "hash_verified_exact_artifact",
                "artifact_chain": plan["artifact_chain"],
                "artifacts": transport_rows,
            },
        )
    return write_json(output / "result.json", result)


def _synthetic_worker_execution(
    root: Path,
    plan: dict[str, Any],
    profile: str,
    source_checkout_root: Path,
    runtime: dict[str, Any],
    prepared: dict[str, Any],
    *,
    container_id: str,
) -> Path:
    """Produce a local fixture for the Linux receipt parser, never Docker evidence."""
    run = next(
        row
        for row in plan["run_plan"]
        if row["profile"] == profile and row["executor"] == "linux-worker"
    )
    run = next(
        row
        for row in plan["run_plan"]
        if row["profile"] == profile and row["executor"] == "linux-worker"
    )
    prepared_mounts = prepared["mount_map"]["mounts"]
    mapping = worker_mounts.build_mount_map(
        source=plan["source"],
        plan_sha256=plan["plan_sha256"],
        profile=profile,
        artifact_sha256=run["artifact_sha256"],
        node_ids_sha256=run["node_ids_sha256"],
        runtime_contract=runtime,
        host_roots={row["role"]: row["host_root"] for row in prepared_mounts},
        worker_roots={row["role"]: row["worker_root"] for row in prepared_mounts},
    )
    inspect = worker_fixtures._synthetic_inspect_receipt(runtime, mapping, container_id)
    bundle = partition_runner.finalize_worker_profile_request(
        plan,
        prepared,
        profile=profile,
        runtime_contract=runtime,
        container_inspect_receipt=inspect,
        expected_container_id=container_id,
        mount_map=mapping,
        request_relative_path=f"requests/{profile}.json",
        receipt_relative_path=f"results/{profile}/primary-result.json",
        entrypoint_name="ukraine-data",
    )
    result_path = Path(bundle["expected_output_host_path"])
    result_root = result_path.parent
    result_root.mkdir(parents=True, exist_ok=True)
    request_raw = bundle["request_bytes"]
    request_sha = bundle["request_sha256"]
    request_path = result_root / "request.json"
    request_path.write_bytes(request_raw)

    probe = _fixture_worker_probe(runtime, mapping, container_id)
    selected_files = {
        "polisyos/__init__.py": b"PACKAGE = True\n",
        "tools/__init__.py": b"TOOLS = True\n",
        "tools/q2/__init__.py": b"",
        "tools/q2/consumer.py": b"def main():\n    return 0\n",
        f"q2-profile-{profile}.txt": profile.encode("utf-8"),
        "q2_installed_origin_gate.py": (
            Path(prepared["input_root"]) / "q2_installed_origin_gate.py"
        ).read_bytes(),
        "q2_installed_origin_plugin.py": split_consumer.origin_plugin_source(),
    }
    for resource in plan["owner_resources"]:
        selected_files[resource["wheel"]] = (
            source_checkout_root / "policy-engine" / resource["source"]
        ).read_bytes()
    install_receipt, target_snapshot = worker_fixtures._synthetic_install_receipt(
        bundle["entrypoint_install_plan"],
        mapping,
        bundle["container_identity"],
        probe,
        selected_files,
    )

    purelib = probe["purelib"]
    dependency_site = runtime["worker"]["dependency_site"]
    origin_rows = {
        package: {
            "file": f"{purelib}/{package}/__init__.py",
            "resolved_file": f"{purelib}/{package}/__init__.py",
            "spec_origin": f"{purelib}/{package}/__init__.py",
            "resolved_spec_origin": f"{purelib}/{package}/__init__.py",
        }
        for package in ("polisyos", "tools")
    }
    origin = {
        "verified": True,
        "errors": [],
        "purelib": purelib,
        "dependency_site": dependency_site,
        "sys_path": [
            purelib,
            dependency_site,
            "/opt/uv-python/cpython-3.14.0-linux-aarch64-gnu/lib/python3.14",
            "/opt/uv-python/cpython-3.14.0-linux-aarch64-gnu/lib/python3.14/lib-dynload",
        ],
        "origins": origin_rows,
        "origin_details": origin_rows,
    }
    node_id = run["node_ids"][0]
    worker_classname = node_id.split("::", 1)[0][:-3].replace("/", ".")
    junit = (
        '<testsuite tests="1" skipped="0" failures="0" errors="0">'
        f'<testcase classname="{worker_classname}" name="{node_id.split("::", 1)[1]}"/>'
        "</testsuite>"
    ).encode()
    input_members = [
        {key: row[key] for key in ("path", "bytes", "sha256")} for row in bundle["input_members"]
    ]
    artifact_members = [
        {key: row[key] for key in ("path", "bytes", "sha256")} for row in bundle["artifact_members"]
    ]
    input_tree = worker_mounts.verify_mapped_tree(
        mapping, role="inputs", expected_files=input_members
    )
    artifact_tree = worker_mounts.verify_mapped_tree(
        mapping, role="artifacts", expected_files=artifact_members
    )
    artifact_mount = next(row for row in mapping["mounts"] if row["role"] == "artifacts")
    input_mount = next(row for row in mapping["mounts"] if row["role"] == "inputs")
    artifact_transport = []
    for artifact in plan["artifacts"]:
        member = next(
            row for row in prepared["artifact_members"] if row["profile"] == artifact["profile"]
        )
        artifact_transport.append(
            {
                "profile": artifact["profile"],
                "chain_key": artifact["chain_key"],
                "path": f"{artifact_mount['worker_root']}/{member['path']}",
                "bytes": artifact["bytes"],
                "sha256": artifact["sha256"],
            }
        )
    inspect_ref = bundle["request"]["container_inspect_ref"]
    transport = {
        "source": plan["source"],
        "input_pins": plan["input_pins"],
        "transport_status": "hash_verified_exact_artifact",
        "request_transport": "stdin_sha256",
        "artifact_chain": plan["artifact_chain"],
        "artifacts": artifact_transport,
        "container_id": container_id,
        "image_id": bundle["container_identity"]["image_id"],
        "runtime_contract": runtime,
        "runtime_contract_sha256": bundle["request"]["runtime_contract_sha256"],
        "mount_map": mapping,
        "mount_map_sha256": bundle["request"]["mount_map_sha256"],
        "input_members": input_members,
        "artifact_members": artifact_members,
        "container_inspect_ref": {
            "path": f"{input_mount['worker_root']}/{inspect_ref['path']}",
            "sha256": inspect_ref["sha256"],
        },
        "container_inspect_sha256": inspect_ref["sha256"],
        "source_input_root": f"{input_mount['worker_root']}/test-source",
        "source_input_root_host": str(Path(input_mount["host_root"]) / "test-source"),
        "source_input_members": plan["source_inputs"]["worker_test_input_files"],
        "request_ref": {"path": "request.json", "sha256": digest(request_raw)},
        "input_tree": input_tree,
        "worker_visible_artifact_tree": artifact_tree,
        "source_checkout_mounted": False,
    }
    host_stdout = evidence(result_root, "host-command-stdout.txt", b"fixture docker exec stdout\n")
    host_stderr = evidence(result_root, "host-command-stderr.txt", b"")
    write_json(
        result_root / "host-launch.json",
        {
            "schema": "policyos.e02.q2.worker-host-launch.v1",
            "source": plan["source"],
            "profile": profile,
            "artifact_sha256": run["artifact_sha256"],
            "request_sha256": request_sha,
            "request_transport": "stdin_sha256",
            "container_identity": bundle["container_identity"],
            "argv": bundle["worker_argv"],
            "timeout_seconds": 600,
            "timed_out": False,
            "returncode": 0,
            "stdout": host_stdout,
            "stderr": host_stderr,
        },
    )
    identity = {
        "schema": "policyos.e02.q2.execution-identity.v1",
        "source": plan["source"],
        "platform_system": "Linux",
        "sys_platform": "linux",
        "machine": "aarch64",
        "python": probe["python"],
        "python_version": probe["python_version"],
        "runner_sha256": plan["input_pins"]["consumer_runner_sha256"],
        "source_checkout_root": None,
        "source_input_root": transport["source_input_root"],
        "source_input_members": plan["source_inputs"]["worker_test_input_files"],
        "container_id": container_id,
        "image_id": bundle["container_identity"]["image_id"],
        "mount_map_sha256": transport["mount_map_sha256"],
    }
    identity_ref = json_evidence(result_root, "identity.json", identity)
    collected_ref = json_evidence(result_root, "collected-nodeids.json", run["node_ids"])
    junit_ref = evidence(result_root, "junit.xml", junit)
    origin_ref = json_evidence(result_root, "origin.json", origin)
    target_ref = json_evidence(
        result_root,
        "target.json",
        {
            "purelib": purelib,
            "dependency_site": dependency_site,
            "node_ids": len(run["node_ids"]),
        },
    )
    resource_rows = {
        row["wheel"]: {"bytes": row["bytes"], "sha256": row["sha256"]}
        for row in plan["owner_resources"]
    }
    resource_ref = json_evidence(
        result_root,
        "resources.json",
        {
            "schema": "polisyos.packaged-resource-contract.v1",
            "runtime_owner_targets": sorted(resource_rows),
            "importlib_resources": resource_rows,
        },
    )
    catalog_readers = {
        name: f"{purelib}/{target}" for name, target in plan["catalog_default_targets"].items()
    }
    digest_registry = f"{purelib}/{plan['digest_registry_target']}"
    worker_directories = {str(Path(target).parent) for target in plan["worker_profile_targets"]}
    assert len(worker_directories) == 1
    poison_ref = json_evidence(
        result_root,
        "poison.json",
        {
            "verified": True,
            "purelib": purelib,
            "dependency_site": dependency_site,
            "sys_path": origin["sys_path"],
            "catalog_readers": catalog_readers,
            "dependency_registry": digest_registry,
            "dowhy_worker_directory": f"{purelib}/{next(iter(worker_directories))}",
            "origins": origin_rows,
            "poison_neighbor_cwd": str(result_root / "neutral-cwd"),
        },
    )
    before_ref = json_evidence(result_root, "target-before.json", target_snapshot)
    after_ref = json_evidence(result_root, "target-after.json", target_snapshot)
    stdout_ref = evidence(result_root, "stdout.txt", b"synthetic selected Linux consumer stdout\n")
    stderr_ref = evidence(result_root, "stderr.txt", b"")
    transport_ref = json_evidence(result_root, "transport.json", transport)
    install_ref = json_evidence(result_root, "entrypoint-install.json", install_receipt)
    return write_json(
        result_path,
        {
            "schema": composite.EXECUTION_SCHEMA,
            "request_sha256": request_sha,
            "source": plan["source"],
            "input_pins": plan["input_pins"],
            "plan_sha256": plan["plan_sha256"],
            "profile": profile,
            "executor": "linux-worker",
            "artifact_sha256": run["artifact_sha256"],
            "runner_sha256": plan["input_pins"]["consumer_runner_sha256"],
            "returncode": 0,
            "execution_identity": identity_ref,
            "collected_node_ids": collected_ref,
            "junit": junit_ref,
            "origin_proof": origin_ref,
            "installed_target_proof": target_ref,
            "resource_proof": resource_ref,
            "poison_proof": poison_ref,
            "target_before_snapshot": before_ref,
            "target_after_snapshot": after_ref,
            "stdout": stdout_ref,
            "stderr": stderr_ref,
            "transport_proof": transport_ref,
            "entrypoint_install_receipt": install_ref,
        },
    )


def test_composite_primary_callbacks_precede_supplemental_with_bound_fixtures(
    tmp_path: Path,
) -> None:
    """Check full receipt recomputation and callback order with local fixtures only.

    The generated worker receipt rows are deliberately synthetic and prove no
    Docker or Linux execution. The later native worker run owns that evidence.
    """
    product, source, fixture = _write_fixture_product(tmp_path)
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    manifest_path, supplemental_path, audit_path, source_hashes, primary_ids, supplemental_ids = (
        _test_manifests(inputs, product, source, fixture["assets"])
    )
    manifest = json.loads(manifest_path.read_text())
    asset_manifest = manifest["candidate_baseline"]["force_include_assets"]
    inventory = build_source_inventory(
        product,
        manifest,
        expected_commit=source["commit"],
        expected_tree=source["tree"],
    )
    inventory_path = write_json(inputs / "source-inventory.json", inventory)
    owner_path = write_json(inputs / "owner-inventory.json", _owner_inventory(asset_manifest))
    source_closure = digest(canonical_json_bytes(source_hashes))
    repo = next(parent for parent in product.parents if (parent / ".git").exists())
    product_root = product
    current_repo = next(
        parent
        for parent in Path(__file__).resolve().parents
        if (parent / "policy-engine/architecture/packaging/q2_build_tools.toml").is_file()
    )
    build_profile = current_repo / "policy-engine/architecture/packaging/q2_build_tools.toml"
    dependency_profile = current_repo / "policy-engine/workers/dowhy-014/uv.lock"
    consumer_runner = R6 / "split_consumer.py"
    supplemental_runner = (
        product
        / Path("docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/q2-packaging/raw")
        / "supplemental_run.py"
    )
    pins = {
        "primary_manifest_sha256": digest(manifest_path.read_bytes()),
        "supplemental_manifest_sha256": digest(supplemental_path.read_bytes()),
        "source_audit_receipt_sha256": digest(audit_path.read_bytes()),
        "source_inventory_sha256": digest(inventory_path.read_bytes()),
        "resource_owner_inventory_sha256": digest(owner_path.read_bytes()),
        "build_profile_sha256": digest(build_profile.read_bytes()),
        "consumer_runner_sha256": digest(consumer_runner.read_bytes()),
        "supplemental_runner_sha256": digest(supplemental_runner.read_bytes()),
        "test_source_closure_sha256": source_closure,
        "dependency_profile_sha256": digest(dependency_profile.read_bytes()),
    }
    artifact_root = inputs / "artifacts"
    artifact_rows = []
    chain = dict.fromkeys(composite.ARTIFACT_CHAIN_KEYS, "a" * 64)
    for profile, chain_key in PROFILE_CHAIN_KEYS.items():
        payload = _fixture_wheel_bytes(profile, fixture["assets"], product)
        artifact_path = artifact_root / f"{profile}.whl"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(payload)
        artifact_sha = digest(payload)
        chain[chain_key] = artifact_sha
        artifact_rows.append(
            {
                "profile": profile,
                "chain_key": chain_key,
                "path": str(artifact_path),
                "bytes": len(payload),
                "sha256": artifact_sha,
            }
        )
    plan = composite.create_composite_plan(
        source=source,
        input_pins=pins,
        expected_artifact_chain=chain,
        artifacts=artifact_rows,
        product_root=product_root,
        primary_manifest_path=manifest_path,
        supplemental_manifest_path=supplemental_path,
        source_audit_receipt_path=audit_path,
        source_inventory_path=inventory_path,
        owner_inventory_path=owner_path,
        build_profile_path=build_profile,
        consumer_runner_path=consumer_runner,
        dependency_profile_path=dependency_profile,
        expected_primary_count=len(primary_ids),
        expected_supplemental_count=len(supplemental_ids),
    )
    assert plan["placement"]["worker_node_ids"] == [LA029_ID]
    assert [row["role"] for row in plan["source_inputs"]["worker_test_input_files"]] == [
        "selected_test",
        "pytest_conftest",
        "pytest_configuration",
    ]
    assert sum(row["bytes"] for row in plan["source_inputs"]["worker_test_input_files"]) > 0
    assert plan["placement"]["host_node_ids"] == [
        "tests/unit/test_extra.py::test_extra",
        "tests/unit/test_installed_catalog_defaults.py::test_catalog",
    ]
    assert len(plan["run_plan"]) == 6
    assert plan["primary"]["unique_profile_case_count"] == 9
    assert (
        plan["supplemental"]["admission"]
        == "blocked_until_all_primary_profile_partitions_reconcile"
    )

    runtime = worker_fixtures._runtime_contract()
    worker_mount_root = inputs / "synthetic-worker-mounts"
    first_mapping = _fixture_mount_map(worker_mount_root, plan, plan["profiles"][0], runtime)
    prepared = partition_runner.prepare_worker_profile_mounts(
        plan,
        profile=plan["profiles"][0],
        source_root=repo,
        mount_map=first_mapping,
        runtime_contract=runtime,
        split_consumer_path=R6 / "split_consumer.py",
        partition_runner_path=RAW / "profile_partition_runner.py",
        worker_mounts_path=RAW / "worker_mounts.py",
        origin_gate_path=(
            current_repo
            / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
            "q2-packaging/raw/installed_origin_gate_r4.py"
        ),
    )
    synthetic_container_id = "d" * 64

    host_rows = []
    for profile in plan["profiles"]:
        result_path = _primary_execution(
            inputs / "receipts",
            plan,
            profile,
            "host",
            repo,
            plan["owner_resources"],
        )
        host_rows.append(
            composite.reconcile_primary_execution(
                result_path,
                plan=plan,
                profile=profile,
                executor="host",
                special_document_path=plan["special_document_path"],
            )
        )
    with pytest.raises(composite.ProfileCompositeError, match="missing or duplicates"):
        composite.validate_primary_barrier(plan, host_rows)
    mutated_plan = {**plan, "source": {**plan["source"], "commit": "0" * 40}}
    with pytest.raises(composite.ProfileCompositeError, match="plan bytes changed"):
        composite.validate_primary_barrier(mutated_plan, host_rows)

    events: list[tuple[str, str, str]] = []

    def run_host_primary(partition: dict[str, Any]) -> Path:
        assert partition["executor"] == "host"
        events.append(("primary", partition["profile"], "host"))
        return _primary_execution(
            inputs / "sequenced-receipts",
            plan,
            partition["profile"],
            "host",
            repo,
            plan["owner_resources"],
        )

    def run_linux_primary(partition: dict[str, Any]) -> Path:
        assert partition["executor"] == "linux-worker"
        events.append(("primary", partition["profile"], "linux-worker"))
        return _synthetic_worker_execution(
            inputs / "sequenced-receipts",
            plan,
            partition["profile"],
            repo,
            runtime,
            prepared,
            container_id=synthetic_container_id,
        )

    def run_supplemental(profile: str, admission: dict[str, Any]) -> dict[str, Any]:
        events.append(("supplemental", profile, "controlled-callback"))
        return {
            "profile": profile,
            "barrier_sha256": admission["barrier"]["execution_rows_sha256"],
            "fixture_only": True,
        }

    execution = composite.execute_composite_plan_with_worker(
        plan,
        run_host_partition=run_host_primary,
        run_linux_worker_partition=run_linux_primary,
        run_supplemental_partition=run_supplemental,
    )
    expected_primary_events = [
        ("primary", profile, executor)
        for profile in plan["profiles"]
        for executor in ("host", "linux-worker")
    ]
    expected_supplemental_events = [
        ("supplemental", profile, "controlled-callback") for profile in plan["profiles"]
    ]
    assert events == expected_primary_events + expected_supplemental_events
    assert execution["barrier"]["execution_row_count"] == 6
    assert all(result["fixture_only"] is True for result in execution["supplemental"].values())

    incomplete_events: list[str] = []

    def incomplete_host(partition: dict[str, Any]) -> Path:
        incomplete_events.append("host")
        return _primary_execution(
            inputs / "incomplete-worker-receipt",
            plan,
            partition["profile"],
            "host",
            repo,
            plan["owner_resources"],
        )

    def incomplete_linux(partition: dict[str, Any]) -> Path:
        incomplete_events.append("linux-worker")
        return _primary_execution(
            inputs / "incomplete-worker-receipt",
            plan,
            partition["profile"],
            "linux-worker",
            repo,
            plan["owner_resources"],
        )

    def forbidden_after_incomplete(profile: str, admission: dict[str, Any]) -> dict[str, Any]:
        incomplete_events.append("supplemental")
        raise AssertionError(f"supplemental started without the Linux worker receipt: {profile}")

    with pytest.raises(composite.ProfileCompositeError, match="actual runtime or mount mapping"):
        composite.execute_composite_plan_with_worker(
            plan,
            run_host_partition=incomplete_host,
            run_linux_worker_partition=incomplete_linux,
            run_supplemental_partition=forbidden_after_incomplete,
        )
    assert incomplete_events == ["host", "linux-worker"]

    failed_events: list[str] = []

    def fail_primary(partition: dict[str, Any]) -> Path:
        failed_events.append("primary")
        path = _primary_execution(
            inputs / "failed-sequence-receipts",
            plan,
            partition["profile"],
            partition["executor"],
            repo,
            plan["owner_resources"],
        )
        if len(failed_events) == 2:
            failed = json.loads(path.read_text())
            failed["returncode"] = 1
            path.write_text(json.dumps(failed), encoding="utf-8")
        return path

    def forbidden_supplemental(profile: str, admission: dict[str, Any]) -> dict[str, Any]:
        failed_events.append("supplemental")
        raise AssertionError(f"supplemental started before a complete primary barrier: {profile}")

    with pytest.raises(composite.ProfileCompositeError, match="source/artifact/runner"):
        composite.execute_composite_plan(
            plan,
            run_primary_partition=fail_primary,
            run_supplemental_partition=forbidden_supplemental,
        )
    assert failed_events == ["primary", "primary"]

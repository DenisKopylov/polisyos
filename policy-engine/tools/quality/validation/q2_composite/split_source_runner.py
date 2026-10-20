#!/usr/bin/env python3
"""Candidate host half of Q2's source -> archive -> rebuilt wheel split wave.

The script composes the existing source-owned Q2 runner and locked Hatchling
recipe. It produces one source-bound Linux worker transfer bundle; it never
installs or executes the Linux consumer itself.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import ModuleType

from split_protocol import (
    MAX_INSTALLER_METADATA_OVERHEAD_BYTES,
    MAX_WORKER_LOG_AND_TEST_TEMP_BYTES,
    MAX_WORKER_METADATA_BYTES,
    PROFILE_CHAIN_KEYS,
    REQUEST_SCHEMA,
    SplitProtocolError,
    _project_build_metadata,
    build_source_inventory,
    canonical_json_bytes,
    load_json_bytes,
    sha256_bytes,
    sha256_file,
    validate_source_audit_selection,
    verify_gcp_archive_inventory,
    verify_sdist_inventory,
    verify_wheel_inventory,
    wheel_uncompressed_bytes,
    worker_write_budget,
)

SOURCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = next(
    parent
    for parent in SOURCE_ROOT.parents
    if (parent / ".git").exists() and (parent / "policy-engine").is_dir()
)
RAW_ROOT = (
    REPOSITORY_ROOT
    / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q2-composite-r10"
)
Q2_RUNNER_RELATIVE = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
    "LOCAL/q2-packaging/raw/run.py"
)
BUILD_PROFILE_RELATIVE = "architecture/packaging/q2_build_tools.toml"
SUPPLEMENTAL_RUNNER_RELATIVE = (
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/"
    "LOCAL/q2-packaging/raw/supplemental_run.py"
)
MAX_WHEEL_BYTES = 65 * 1024 * 1024


def _regular(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SplitProtocolError(f"{label} must be an existing regular non-symlink file: {path}")
    return path.read_bytes()


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SplitProtocolError(f"cannot load source-owned module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _verify_worker_capacity(
    capacity_path: Path,
    capacity_sha256: str,
    *,
    source_sha: str,
    source_tree: str,
) -> dict[str, Any]:
    raw = _regular(capacity_path, "worker capacity receipt")
    actual = sha256_bytes(raw)
    if actual != capacity_sha256:
        raise SplitProtocolError("worker capacity receipt hash differs from supplied pin")
    from split_protocol import load_json_bytes

    value = load_json_bytes(raw, label="worker capacity receipt")
    if type(value) is not dict or value.get("schema") != "policyos.e02.q2.worker-capacity.v1":
        raise SplitProtocolError("worker capacity receipt has an unsupported schema")
    if value.get("source") != {"commit": source_sha, "tree": source_tree}:
        raise SplitProtocolError("worker capacity receipt belongs to another source freeze")
    if value.get("scratch_root") != "/scratch":
        raise SplitProtocolError("Q2 Linux consumer capacity must be measured on /scratch")
    free_bytes = value.get("free_after_checkout_bytes")
    pack_bytes = value.get("thin_fast_forward_pack_bytes")
    growth_bytes = value.get("checkout_growth_bytes")
    if any(type(item) is not int or item < 0 for item in (free_bytes, pack_bytes, growth_bytes)):
        raise SplitProtocolError("worker capacity measurements must be non-negative exact integers")
    return {
        **value,
        "sha256": actual,
        "free_after_checkout_bytes": free_bytes,
        "thin_fast_forward_pack_bytes": pack_bytes,
        "checkout_growth_bytes": growth_bytes,
    }


def _inventory_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return canonical_json_bytes(left) == canonical_json_bytes(right)


def _copy_checked(source: Path, destination: Path, *, expected_sha256: str | None = None) -> int:
    if source.is_symlink() or not source.is_file():
        raise SplitProtocolError(f"transfer source is not a regular file: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise SplitProtocolError(f"transfer destination already exists: {destination}")
    shutil.copyfile(source, destination)
    if source.stat().st_size != destination.stat().st_size:
        raise SplitProtocolError(f"transfer copy size changed: {source}")
    if expected_sha256 is not None and sha256_file(destination) != expected_sha256:
        raise SplitProtocolError(f"transfer copy bytes changed: {source}")
    return destination.stat().st_size


def _build_receipt(args: argparse.Namespace) -> Path:
    repo = Path(args.repo).resolve(strict=True)
    if not ((repo / ".git").exists() or (repo / ".git").is_file()):
        raise SplitProtocolError(f"--repo is not the attached source checkout: {repo}")
    manifest_path = Path(args.manifest).resolve(strict=True)
    output_root = Path(args.output_root).resolve()
    if not output_root.is_relative_to(RAW_ROOT.resolve()):
        raise SplitProtocolError(
            "Q2 split output must stay under the candidate ignored RAW directory"
        )
    if not args.execute_host_build:
        raise SplitProtocolError(
            "build is disabled until the final source freeze; rerun only after explicit "
            "--execute-host-build"
        )

    runner_path = repo / Q2_RUNNER_RELATIVE
    runner = _load_module(runner_path, "e02_q2_existing_runner_split_candidate")
    runner.frozen_source_preflight(repo, args.source_sha, args.source_tree)
    manifest_path, manifest, manifest_sha = runner.load_verified_json_file(
        manifest_path,
        args.manifest_sha256,
        "primary source-freeze manifest",
        expected_schema_version=1,
    )
    baseline = manifest.get("candidate_baseline")
    if (
        type(baseline) is not dict
        or baseline.get("source_sha") != args.source_sha
        or baseline.get("source_tree") != args.source_tree
    ):
        raise SplitProtocolError("Q2 manifest does not identify the selected source freeze")

    source_audit_path = Path(args.source_audit_receipt).resolve(strict=True)
    source_audit_raw = _regular(source_audit_path, "source-audit check receipt")
    source_audit_sha = sha256_bytes(source_audit_raw)
    if source_audit_sha != args.source_audit_receipt_sha256:
        raise SplitProtocolError("source-audit receipt differs from its external SHA-256 pin")
    source_audit = load_json_bytes(source_audit_raw, label="source-audit check receipt")
    supplemental_path = Path(args.supplemental_manifest).resolve(strict=True)
    supplemental_raw = _regular(supplemental_path, "supplemental source manifest")
    supplemental_sha = sha256_bytes(supplemental_raw)
    if supplemental_sha != args.supplemental_manifest_sha256:
        raise SplitProtocolError("supplemental manifest differs from its external SHA-256 pin")
    selection = validate_source_audit_selection(
        source_audit,
        expected_commit=args.source_sha,
        expected_tree=args.source_tree,
        manifest_sha256=manifest_sha,
        supplemental_manifest_sha256=supplemental_sha,
    )

    capacity = _verify_worker_capacity(
        Path(args.worker_capacity_receipt).resolve(strict=True),
        args.worker_capacity_sha256,
        source_sha=args.source_sha,
        source_tree=args.source_tree,
    )
    app_python = Path(args.app_python).resolve(strict=True)
    uv = Path(args.uv).resolve(strict=True)
    wheelhouse = Path(args.wheelhouse).resolve(strict=True)
    output_root.mkdir(parents=True, exist_ok=False)
    logs = output_root / "logs"
    logs.mkdir()
    run_root = output_root / "host-build"
    run_root.mkdir()
    receipt_path = output_root / "host-build-receipt.json"
    receipt: dict[str, Any] = {
        "schema": "policyos.e02.q2.split-host-build-receipt.v1",
        "status": "running",
        "source": {"commit": args.source_sha, "tree": args.source_tree},
        "manifest": {"path": str(manifest_path), "sha256": manifest_sha},
        "started_utc": datetime.now(UTC).isoformat(),
        "runner_sha256": sha256_file(runner_path),
        "retention": "all deciding outputs and intermediate source/sdist artifacts retained",
    }
    runner.json_write(receipt_path, receipt)
    try:
        env = runner.clean_child_env()
        host_info = runner.interpreter_info(app_python, log_dir=logs, name="host-existing-app")
        if host_info["implementation"] != "cpython" or host_info["version"][:2] != [3, 14]:
            raise SplitProtocolError("host builder must use the existing CPython 3.14 profile")
        base_python = Path(host_info["base_executable"]).resolve(strict=True)
        receipt["host_profile"] = host_info
        receipt["uv"] = {
            "path": str(uv),
            "version": runner.run_command(
                [str(uv), "--version"], cwd=repo, env=env, log_stem=logs / "uv-version"
            ).stdout.strip(),
            "sha256": sha256_file(uv),
        }

        frozen_source = run_root / "frozen-source"
        archive_receipt = runner.extract_git_archive(repo, args.source_sha, frozen_source, logs)
        product = frozen_source / "policy-engine"
        (
            buildtools,
            build_profile,
            lock_raw,
            source_blobs,
            archive_members,
            _build_helper_path,
            build_binding,
        ) = runner.load_source_bound_build_tools(repo, args.source_sha, product)
        lock = buildtools.load_lock(lock_raw, expected_sha256=build_profile["lock_sha256"])
        buildtools.validate_quarantine(lock, wheelhouse)

        build_environment: dict[str, Any] = {}

        def prepare_existing_locked_wheelhouse(selected_lock: dict[str, Any]) -> dict[str, Any]:
            if canonical_json_bytes(selected_lock) != canonical_json_bytes(lock):
                raise SplitProtocolError("source-admitted builder lock changed before preparation")
            build_python, build_profile_receipt = runner.configure_build_env(
                str(uv),
                base_python,
                selected_lock,
                buildtools,
                wheelhouse,
                run_root,
                env,
                logs,
            )
            build_environment.update(
                {"python": str(build_python), "profile": build_profile_receipt}
            )
            return build_environment

        admitted = buildtools.run_after_source_admission(
            build_profile,
            archive_members["pyproject.toml"],
            lock_raw,
            source_blobs,
            archive_members,
            prepare_existing_locked_wheelhouse,
        )
        build_python = Path(admitted["action_result"]["python"]).resolve(strict=True)
        receipt["build_tools"] = {
            "binding": build_binding,
            "source_transport": admitted["source_transport"],
            "wheelhouse": str(wheelhouse),
            "quarantine_status": "revalidated_existing_locked_wheelhouse_no_network",
            "host_profile": build_environment["profile"],
        }

        owner_inventory = runner.source_resource_inventory(app_python, product, run_root, logs)
        manifest, assets = runner.read_asset_manifest(product, manifest, owner_inventory)
        owner_path = output_root / "runtime-resource-owner-inventory.json"
        runner.json_write(owner_path, owner_inventory)
        owner_sha = sha256_file(owner_path)
        source_inventory = build_source_inventory(
            product,
            manifest,
            expected_commit=args.source_sha,
            expected_tree=args.source_tree,
            hatchling_python=build_python,
        )
        inventory_path = output_root / "complete-wheel-source-inventory.json"
        runner.json_write(inventory_path, source_inventory)
        inventory_sha = sha256_file(inventory_path)
        receipt["source_package_inventory"] = {
            "path": str(inventory_path),
            "sha256": inventory_sha,
            "package_file_count": source_inventory["package_file_count"],
            "package_bytes": source_inventory["package_bytes"],
            "force_include_count": source_inventory["force_include_count"],
            "wheel_roots": source_inventory["package_roots"],
            "runtime_owner_inventory_path": str(owner_path),
            "runtime_owner_inventory_sha256": owner_sha,
        }

        expected_original_ids = runner.baseline_node_ids(product, manifest)
        current_ids = runner.verify_current_primary_suite_sources(
            product, manifest, expected_original_ids
        )
        transitive = runner.verify_transitive_test_bindings(
            product, manifest, expected_original_ids
        )
        receipt["installed_consumer_selection"] = {
            "source": (
                "current_primary_suite plus source-bound original and additional manifest groups"
            ),
            "selected_node_count": len(current_ids),
            "selected_node_ids_sha256": runner.node_ids_sha256(current_ids),
            "transitive_fixture_bindings": transitive,
            "source_audit_receipt_sha256": source_audit_sha,
            "source_audit_profiles": selection["profiles"],
            "source_audit_primary_node_ids": len(selection["primary_node_ids"]),
            "source_audit_primary_node_ids_sha256": selection["primary_node_ids_sha256"],
            "source_audit_supplemental_node_ids": len(selection["supplemental_node_ids"]),
            "source_audit_supplemental_node_ids_sha256": selection["supplemental_node_ids_sha256"],
            "source_audit_profile_case_count": selection["profile_case_count"],
        }
        if current_ids != set(selection["primary_node_ids"]):
            raise SplitProtocolError(
                "host runner primary selector set differs from exact source-audit check"
            )

        source_build = runner.run_build(
            str(uv),
            build_python,
            product,
            run_root / "dist-source",
            wheel=True,
            sdist=True,
            log_dir=logs,
            env=env,
        )
        if not isinstance(source_build, tuple):
            raise AssertionError("source build did not produce wheel and sdist")
        source_wheel, source_sdist = source_build
        source_wheel_assets = runner.verify_wheel(source_wheel, assets)
        source_wheel_packages = verify_wheel_inventory(source_wheel, source_inventory)
        project_metadata = tomllib.loads((product / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]
        sdist_prefix = (
            project_metadata["name"].replace("-", "_") + f"-{project_metadata['version']}"
        )
        sdist_assets = runner.verify_tar_assets(
            source_sdist,
            assets,
            member_prefix=f"{sdist_prefix}/",
            exact_force_directories=False,
        )
        source_sdist_complete = verify_sdist_inventory(source_sdist, source_inventory)
        sdist_product = runner.product_root_from_sdist(
            source_sdist,
            run_root / "sdist-extracted" / sdist_prefix,
            product,
            sdist_prefix,
        )
        sdist_inventory = build_source_inventory(
            sdist_product,
            manifest,
            expected_commit=args.source_sha,
            expected_tree=args.source_tree,
        )
        if not _inventory_equal(source_inventory, sdist_inventory):
            raise SplitProtocolError(
                "rebuilt sdist source package set/bytes differ from Git archive"
            )
        rebuilt_sdist_wheel = runner.run_build(
            str(uv),
            build_python,
            sdist_product,
            run_root / "dist-sdist",
            wheel=True,
            sdist=False,
            log_dir=logs,
            env=env,
        )
        if not isinstance(rebuilt_sdist_wheel, Path):
            raise AssertionError("sdist rebuild did not produce one wheel")
        rebuilt_sdist_assets = runner.verify_wheel(rebuilt_sdist_wheel, assets)
        rebuilt_sdist_packages = verify_wheel_inventory(rebuilt_sdist_wheel, source_inventory)

        gcp_output = run_root / "gcp-archive"
        package_script = product / "ops/cloud/gcp/package_repo.sh"
        package_env = runner.clean_child_env()
        package_env.update(
            {"OUT_DIR": str(gcp_output), "UPLOAD": "0", "PYTHON_BIN": str(build_python)}
        )
        runner.run_command(
            ["bash", str(package_script)],
            cwd=product,
            env=package_env,
            log_stem=logs / "gcp-package-archive",
        )
        gcp_archive = runner.one_matching_file(gcp_output, "policy-engine-*.tar.gz")
        gcp_assets = runner.verify_tar_assets(
            gcp_archive,
            assets,
            member_prefix="policy-engine/",
            exact_force_directories=True,
        )
        gcp_complete = verify_gcp_archive_inventory(gcp_archive, source_inventory)
        gcp_product = runner.product_root_from_gcp(
            gcp_archive,
            run_root / "gcp-extracted" / "policy-engine",
            product,
        )
        gcp_metadata_contract = _project_build_metadata(gcp_product)
        rebuilt_gcp_wheel = runner.run_build(
            str(uv),
            build_python,
            gcp_product,
            run_root / "dist-gcp",
            wheel=True,
            sdist=False,
            log_dir=logs,
            env=env,
        )
        if not isinstance(rebuilt_gcp_wheel, Path):
            raise AssertionError("GCP rebuild did not produce one wheel")
        rebuilt_gcp_assets = runner.verify_wheel(rebuilt_gcp_wheel, assets)
        rebuilt_gcp_packages = verify_wheel_inventory(
            rebuilt_gcp_wheel,
            source_inventory,
            metadata_contract=gcp_metadata_contract,
        )

        profile_wheels: dict[str, tuple[Path, dict[str, Any]]] = {
            "source-wheel": (source_wheel, source_wheel_packages),
            "rebuilt-sdist-wheel": (rebuilt_sdist_wheel, rebuilt_sdist_packages),
            "rebuilt-gcp-archive-wheel": (rebuilt_gcp_wheel, rebuilt_gcp_packages),
        }
        if list(profile_wheels) != selection["profiles"]:
            raise SplitProtocolError(
                "source-audit profile order differs from the three current producer outputs"
            )
        supplemental_runner_path = repo / SUPPLEMENTAL_RUNNER_RELATIVE
        supplemental_runner_bytes = _regular(
            supplemental_runner_path, "source-bound supplemental runner"
        )
        supplemental_runner = _load_module(
            supplemental_runner_path, "e02_q2_supplemental_runner_split_host"
        )
        supplemental_manifest = load_json_bytes(
            supplemental_raw, label="supplemental source manifest"
        )
        supplemental_ids = supplemental_runner.suite_node_ids(product, supplemental_manifest)
        if sorted(supplemental_ids) != selection["supplemental_node_ids"]:
            raise SplitProtocolError(
                "canonical supplemental runner IDs differ from the source-audit check"
            )

        oversized = {
            profile: path.stat().st_size
            for profile, (path, _proof) in profile_wheels.items()
            if path.stat().st_size > MAX_WHEEL_BYTES
        }
        if oversized:
            raise SplitProtocolError(
                f"source-derived worker wheel exceeds the per-artifact transfer limit: {oversized}"
            )
        gate_bytes, _ = runner.load_installed_origin_gate()
        gate_sha = sha256_bytes(gate_bytes)
        origin_plugin = _load_module(
            SOURCE_ROOT / "split_consumer.py", "e02_q2_split_consumer_host"
        )
        plugin_bytes = origin_plugin.origin_plugin_source()
        target_overhead = {
            "origin_gate": len(gate_bytes),
            "origin_plugin": len(plugin_bytes),
            "installer_metadata_reserve": MAX_INSTALLER_METADATA_OVERHEAD_BYTES,
        }
        capacity = _verify_worker_capacity(
            Path(args.worker_capacity_receipt).resolve(strict=True),
            args.worker_capacity_sha256,
            source_sha=args.source_sha,
            source_tree=args.source_tree,
        )
        protocol_path = SOURCE_ROOT / "split_protocol.py"
        consumer_path = SOURCE_ROOT / "split_consumer.py"
        protocol_sha = sha256_file(protocol_path)
        consumer_sha = sha256_file(consumer_path)
        supplemental_runner_sha = sha256_bytes(supplemental_runner_bytes)
        transfer = output_root / "worker-transfer"
        transfer.mkdir()
        transfer_manifest = transfer / "source-freeze-manifest.json"
        transfer_inventory = transfer / "complete-wheel-source-inventory.json"
        transfer_protocol = transfer / "split_protocol.py"
        transfer_consumer = transfer / "split_consumer.py"
        transfer_supplemental_runner = transfer / "supplemental_run.py"
        transfer_capacity = transfer / "worker-capacity-receipt.json"
        transfer_source_audit = transfer / "source-input-audit.json"
        transfer_supplemental = transfer / "supplemental-manifest.json"
        transfer_wheels: dict[str, Path] = {}
        artifact_rows: list[dict[str, Any]] = []
        # Profile subdirectories retain Hatch's original PEP 427 filenames while
        # allowing every producer path to be transported independently.
        for profile, (wheel, _proof) in profile_wheels.items():
            destination = transfer / "wheels" / profile / wheel.name
            _copy_checked(wheel, destination)
            transfer_wheels[profile] = destination
            artifact_rows.append(
                {
                    "profile": profile,
                    "chain_key": PROFILE_CHAIN_KEYS[profile],
                    "file": destination.relative_to(transfer).as_posix(),
                    "bytes": destination.stat().st_size,
                    "sha256": sha256_file(destination),
                }
            )
        _copy_checked(manifest_path, transfer_manifest, expected_sha256=manifest_sha)
        _copy_checked(inventory_path, transfer_inventory, expected_sha256=inventory_sha)
        _copy_checked(protocol_path, transfer_protocol, expected_sha256=protocol_sha)
        _copy_checked(consumer_path, transfer_consumer, expected_sha256=consumer_sha)
        _copy_checked(
            supplemental_runner_path,
            transfer_supplemental_runner,
            expected_sha256=supplemental_runner_sha,
        )
        _copy_checked(
            Path(args.worker_capacity_receipt).resolve(strict=True),
            transfer_capacity,
            expected_sha256=capacity["sha256"],
        )
        _copy_checked(source_audit_path, transfer_source_audit, expected_sha256=source_audit_sha)
        _copy_checked(supplemental_path, transfer_supplemental, expected_sha256=supplemental_sha)
        metadata_bytes = sum(
            path.stat().st_size
            for path in (
                transfer_manifest,
                transfer_inventory,
                transfer_protocol,
                transfer_consumer,
                transfer_supplemental_runner,
                transfer_capacity,
                transfer_source_audit,
                transfer_supplemental,
            )
        )
        if metadata_bytes > MAX_WORKER_METADATA_BYTES:
            raise SplitProtocolError(
                "worker request/inventory/harness transfer exceeds its 4 MiB allocation: "
                f"{metadata_bytes}"
            )
        target_overhead_per_profile = sum(target_overhead.values())
        profile_package_bytes = sum(
            wheel_uncompressed_bytes(path) for path in transfer_wheels.values()
        )
        transfer_wheel_bytes = sum(path.stat().st_size for path in transfer_wheels.values())
        largest_wheel_bytes = max(path.stat().st_size for path in transfer_wheels.values())
        budget = worker_write_budget(
            fast_forward_pack_bytes=capacity["thin_fast_forward_pack_bytes"],
            checkout_growth_bytes=capacity["checkout_growth_bytes"],
            wheel_bytes=transfer_wheel_bytes,
            package_target_bytes=profile_package_bytes
            + len(profile_wheels) * target_overhead_per_profile,
            installer_transient_bytes=largest_wheel_bytes,
            logs_and_test_temp_bytes=MAX_WORKER_LOG_AND_TEST_TEMP_BYTES,
            request_and_metadata_bytes=MAX_WORKER_METADATA_BYTES,
        )
        free_after_checkout = capacity["free_after_checkout_bytes"]
        future_budget = (
            budget["total_bytes"]
            - budget["allocations_bytes"]["thin_fast_forward_pack"]
            - budget["allocations_bytes"]["checkout_growth"]
        )
        if free_after_checkout - future_budget < budget["mandatory_free_reserve_bytes"]:
            raise SplitProtocolError(
                "worker free space after checkout cannot preserve the mandatory 4 GiB reserve"
            )

        q2_runner_sha = sha256_file(runner_path)
        if gate_sha != runner.INSTALLED_ORIGIN_GATE_SHA256:
            raise SplitProtocolError("Q2 installed-origin gate does not match its source pin")
        artifact_chain = {
            "source_archive_sha256": archive_receipt["sha256"],
            "source_wheel_sha256": source_wheel_assets["sha256"],
            "source_sdist_sha256": sha256_file(source_sdist),
            "rebuilt_sdist_wheel_sha256": rebuilt_sdist_assets["sha256"],
            "gcp_archive_sha256": sha256_file(gcp_archive),
            "rebuilt_gcp_wheel_sha256": rebuilt_gcp_assets["sha256"],
        }
        request = {
            "schema": REQUEST_SCHEMA,
            "source": {"commit": args.source_sha, "tree": args.source_tree},
            "manifest_sha256": manifest_sha,
            "inventory_sha256": inventory_sha,
            "artifacts": artifact_rows,
            "artifact_chain": artifact_chain,
            "worker_capacity": {
                "receipt_file": transfer_capacity.name,
                "receipt_sha256": capacity["sha256"],
                "scratch_root": capacity["scratch_root"],
                "free_after_checkout_bytes": free_after_checkout,
                "thin_fast_forward_pack_bytes": capacity["thin_fast_forward_pack_bytes"],
                "checkout_growth_bytes": capacity["checkout_growth_bytes"],
            },
            "worker_write_budget": budget,
            "installed_target_overhead_bytes": target_overhead,
            "consumer_selection": {
                "manifest_driven": True,
                "profiles": selection["profiles"],
                "primary_node_ids": selection["primary_node_ids"],
                "primary_node_ids_sha256": selection["primary_node_ids_sha256"],
                "supplemental_node_ids": selection["supplemental_node_ids"],
                "supplemental_node_ids_sha256": selection["supplemental_node_ids_sha256"],
                "profile_case_count": selection["profile_case_count"],
                "transitive_fixture_bindings_sha256": sha256_bytes(
                    canonical_json_bytes(transitive)
                ),
                "execution_plan": [
                    {"phase": phase, "profile": profile}
                    for phase in ("primary", "supplemental")
                    for profile in selection["profiles"]
                ],
            },
            "source_audit": {
                "receipt_file": transfer_source_audit.name,
                "receipt_sha256": source_audit_sha,
                "supplemental_manifest_file": transfer_supplemental.name,
                "supplemental_manifest_sha256": supplemental_sha,
                "audit_helper_sha256": source_audit.get("audit_helper_sha256"),
                "supplemental_runner_file": transfer_supplemental_runner.name,
                "supplemental_runner_sha256": supplemental_runner_sha,
            },
            "harness": {
                "protocol_file": transfer_protocol.name,
                "protocol_sha256": protocol_sha,
                "consumer_file": transfer_consumer.name,
                "consumer_sha256": consumer_sha,
                "q2_runner_relative": Q2_RUNNER_RELATIVE,
                "q2_runner_sha256": q2_runner_sha,
                "installed_origin_gate_sha256": gate_sha,
                "build_profile_relative": BUILD_PROFILE_RELATIVE,
                "build_profile_sha256": sha256_file(product / BUILD_PROFILE_RELATIVE),
            },
            "worker_profile": {
                "product_python_version": [3, 14],
                "dowhy_python_version": [3, 12],
                "dowhy_distribution_version": "0.14",
                "dowhy_lock_relative": "workers/dowhy-014/uv.lock",
                "dowhy_lock_sha256": sha256_file(product / "workers/dowhy-014/uv.lock"),
                "install_mode": "uv pip --offline --no-deps --no-cache --target existing purelib",
            },
        }
        request_path = transfer / "split-consumer-request.json"
        request_raw = json.dumps(request, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        request_path.write_bytes(request_raw)
        if request_path.stat().st_size + metadata_bytes > MAX_WORKER_METADATA_BYTES:
            raise SplitProtocolError("request plus worker metadata exceeds its 4 MiB allocation")
        receipt["artifacts"] = {
            "source_wheel": {
                "wheel": source_wheel_packages,
                "runtime_resources": source_wheel_assets,
            },
            "source_sdist": {
                "archive_sha256": sha256_file(source_sdist),
                "archive_bytes": source_sdist.stat().st_size,
                "runtime_resources": sdist_assets,
                "complete_members": source_sdist_complete,
            },
            "rebuilt_sdist_wheel": {
                "wheel": rebuilt_sdist_packages,
                "runtime_resources": rebuilt_sdist_assets,
            },
            "gcp_archive": {
                "archive_sha256": sha256_file(gcp_archive),
                "archive_bytes": gcp_archive.stat().st_size,
                "runtime_resources": gcp_assets,
                "complete_members": gcp_complete,
            },
            "rebuilt_gcp_wheel": {
                "wheel": rebuilt_gcp_packages,
                "runtime_resources": rebuilt_gcp_assets,
            },
            "transfer": {
                "directory": str(transfer),
                "request_path": str(request_path),
                "request_sha256": sha256_file(request_path),
                "manifest_path": str(transfer_manifest),
                "inventory_path": str(transfer_inventory),
                "wheel_paths": {profile: str(path) for profile, path in transfer_wheels.items()},
                "source_audit_path": str(transfer_source_audit),
                "supplemental_manifest_path": str(transfer_supplemental),
                "supplemental_runner_path": str(transfer_supplemental_runner),
                "metadata_bytes": request_path.stat().st_size + metadata_bytes,
                "worker_write_budget": budget,
            },
        }
        receipt["status"] = "ready_for_independent_review_and_worker_admission"
        receipt["finished_utc"] = datetime.now(UTC).isoformat()
        runner.json_write(receipt_path, receipt)
        return receipt_path
    except BaseException as error:
        receipt["status"] = "failed"
        receipt["failure"] = f"{type(error).__name__}: {error}"
        receipt["finished_utc"] = datetime.now(UTC).isoformat()
        runner.json_write(receipt_path, receipt)
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-tree", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--source-audit-receipt", required=True)
    parser.add_argument("--source-audit-receipt-sha256", required=True)
    parser.add_argument("--supplemental-manifest", required=True)
    parser.add_argument("--supplemental-manifest-sha256", required=True)
    parser.add_argument("--app-python", required=True, help="existing host CPython 3.14")
    parser.add_argument("--uv", required=True, help="existing absolute uv executable")
    parser.add_argument("--wheelhouse", required=True, help="pre-existing exact locked quarantine")
    parser.add_argument("--worker-capacity-receipt", required=True)
    parser.add_argument("--worker-capacity-sha256", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument(
        "--execute-host-build",
        action="store_true",
        help="explicitly enable the expensive host build after final source freeze",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        receipt = _build_receipt(parse_args(argv))
    except (
        OSError,
        RuntimeError,
        SplitProtocolError,
        KeyError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        sys.stderr.write(f"Q2 split host candidate failed: {type(error).__name__}: {error}\n")
        return 1
    sys.stdout.write(f"Q2 split host candidate ready: {receipt}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

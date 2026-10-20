"""Behavioral checks for the R9 host/worker orchestration bridge.

All worker command results in these tests are explicitly controlled fixtures.
They prove invocation wiring and failure ordering, not Docker or Linux runtime.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = (
    Path(os.environ["E02_Q2_POSTIMAGE_ROOT"]).resolve(strict=True)
    if os.environ.get("E02_Q2_POSTIMAGE_ROOT")
    else next(
        parent
        for parent in HERE.parents
        if (parent / "policy-engine").is_dir() and (parent / ".git").exists()
    )
)
RAW = (
    REPO_ROOT / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw"
)
SOURCE = REPO_ROOT / "policy-engine/tools/quality/validation/q2_composite"
R6 = SOURCE
R7 = SOURCE
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO_ROOT / "policy-engine"))

import test_profile_composite as fixtures  # noqa: E402
import test_worker_mounts as worker_fixtures  # noqa: E402

from tools.quality.validation.q2_composite import q2_composite_cli as composite_cli  # noqa: E402
from tools.quality.validation.q2_composite import (
    run_q2_protocol_a94 as protocol_runner,  # noqa: E402
)
from tools.quality.validation.q2_composite import worker_host_driver as driver_module  # noqa: E402


def _load_postimage_bundle() -> driver_module.SourceBundle:
    """Load candidate code from RAW while binding original external receipts."""
    bundle = driver_module.load_composed_source_bundle(REPO_ROOT, RAW)
    selected_repo = driver_module._repo_root(HERE)
    selected_raw = (
        selected_repo
        / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw"
    )
    return dataclasses.replace(
        bundle,
        repo_root=selected_repo,
        r6_root=selected_raw / "q2-split-candidate-r6-20261020",
        r7_root=selected_raw / "q2-split-candidate-r7-20261020",
    )


def test_source_set_digest_is_sorted_and_detects_member_drift(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    first = source_root / "policy-engine" / "src" / "first.py"
    second = source_root / "policy-engine" / "src" / "second.py"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"first member\n")
    second.write_bytes(b"second member\n")
    entries = [
        ("policy-engine/src/first.py", hashlib.sha256(first.read_bytes()).hexdigest()),
        (
            "policy-engine/src/second.py",
            hashlib.sha256(second.read_bytes()).hexdigest(),
        ),
    ]

    def manifest_bytes(rows: list[dict[str, Any]]) -> bytes:
        return json.dumps(
            {
                "source_set": {
                    "file_count": len(rows),
                    "files": rows,
                    # This legacy claim is retained as metadata and is not an
                    # admission predicate for the recomputed member set.
                    "path_sha256_set_digest": "0" * 64,
                }
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    rows = [
        {"path": path, "bytes": (source_root / path).stat().st_size, "sha256": digest}
        for path, digest in entries
    ]
    original = manifest_bytes(rows)
    manifest, source_digest, legacy_claim = driver_module._verify_frozen_source_set(
        original,
        expected_manifest_sha256=hashlib.sha256(original).hexdigest(),
        repository_root=source_root,
        expected_file_count=2,
    )
    assert manifest["source_set"]["file_count"] == 2
    assert source_digest == driver_module._canonical_source_set_digest(entries)
    assert legacy_claim == "0" * 64
    assert source_digest != legacy_claim
    assert source_digest == driver_module._canonical_source_set_digest(entries[::-1])

    reordered = manifest_bytes(rows[::-1])
    with pytest.raises(driver_module.WorkerHostDriverError, match="frozen SHA-256"):
        driver_module._verify_frozen_source_set(
            reordered,
            expected_manifest_sha256=hashlib.sha256(original).hexdigest(),
            repository_root=source_root,
            expected_file_count=2,
        )

    duplicate = manifest_bytes([*rows, rows[0]])
    with pytest.raises(driver_module.WorkerHostDriverError, match="duplicate"):
        driver_module._verify_frozen_source_set(
            duplicate,
            expected_manifest_sha256=hashlib.sha256(duplicate).hexdigest(),
            repository_root=source_root,
            expected_file_count=3,
        )

    wrong_path_rows = [dict(row) for row in rows]
    wrong_path_rows[0]["path"] = "policy-engine/src/missing.py"
    wrong_path = manifest_bytes(wrong_path_rows)
    with pytest.raises(driver_module.WorkerHostDriverError, match="cannot be inspected"):
        driver_module._verify_frozen_source_set(
            wrong_path,
            expected_manifest_sha256=hashlib.sha256(wrong_path).hexdigest(),
            repository_root=source_root,
            expected_file_count=2,
        )

    wrong_hash_rows = [dict(row) for row in rows]
    wrong_hash_rows[0]["sha256"] = "f" * 64
    wrong_hash = manifest_bytes(wrong_hash_rows)
    with pytest.raises(driver_module.WorkerHostDriverError, match="member changed"):
        driver_module._verify_frozen_source_set(
            wrong_hash,
            expected_manifest_sha256=hashlib.sha256(wrong_hash).hexdigest(),
            repository_root=source_root,
            expected_file_count=2,
        )


def test_canonical_load_binds_r10_set_and_retains_r7_claim_as_provenance() -> None:
    bundle = _load_postimage_bundle()

    assert (
        bundle.source_set_sha256
        == json.loads((SOURCE / "source-manifest-r10.json").read_text(encoding="utf-8"))[
            "source_set"
        ]["sorted_path_sha256_digest"]
    )
    assert (
        bundle.upstream_r7_source_set_sha256
        == "91065f9f205974466a016bfebdf863fa1fb0e370a5b6a1bd8d0b7671d6421b45"
    )
    assert (
        bundle.legacy_declared_source_set_sha256
        == "ac2b3a1d5cd04efd27c63da933ebc184fe553f01f1bacca1a1b36f79d83af804"
    )
    assert (
        bundle.source_manifest_sha256
        == hashlib.sha256((SOURCE / "source-manifest-r10.json").read_bytes()).hexdigest()
    )
    assert (
        Path(bundle.split_consumer.__file__).resolve() == (SOURCE / "split_consumer.py").resolve()
    )


def test_r6_source_verification_uses_r7_supersession_and_rejects_member_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = driver_module._repo_root(HERE)
    bundle = _load_postimage_bundle()
    verified = composite_cli.verify_r6_source_members(repo, source_bundle=bundle)
    superseded_key = next(
        key for key in composite_cli.R6_MEMBER_HASHES if key.endswith("/split_consumer.py")
    )
    assert composite_cli.R6_MEMBER_HASHES[superseded_key] == (
        "e7ff32ad0bd88f39e21e854e10cdddd6ca1e54216a14f88f4dc180c1c9095bd1"
    )
    assert verified[superseded_key] == driver_module.R7_CONSUMER_SHA256
    assert verified[superseded_key] != composite_cli.R6_MEMBER_HASHES[superseded_key]

    original_read = composite_cli._read_regular
    superseded_path = repo.joinpath(*Path(superseded_key).parts)

    def corrupt_member(path: Path, label: str) -> bytes:
        raw = original_read(path, label)
        if path == superseded_path:
            return raw + b"drift"
        return raw

    monkeypatch.setattr(composite_cli, "_read_regular", corrupt_member)
    with pytest.raises(
        composite_cli.CompositeCLIError,
        match="R6/R7 composed source member differs from its selected bytes",
    ):
        composite_cli.verify_r6_source_members(repo, source_bundle=bundle)


def test_live_driver_derives_runtime_from_pinned_worker_readback(
    tmp_path: Path,
) -> None:
    repo, plan, current_repo = _fixture_plan(tmp_path)
    bundle = _load_postimage_bundle()
    neutral = tmp_path / "neutral-live-cwd"
    neutral.mkdir()
    kwargs = {
        "plan": plan,
        "source_bundle": bundle,
        "source_root": repo,
        "origin_gate_path": (
            current_repo
            / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
            / "q2-packaging/raw/installed_origin_gate_r4.py"
        ),
        "neutral_cwd": neutral,
    }
    with pytest.raises(driver_module.WorkerHostDriverError, match="frozen worker readback"):
        driver_module.WorkerHostDriver(
            runtime_contract=worker_fixtures._runtime_contract(),
            output_root=tmp_path / "untrusted-runtime-output",
            **kwargs,
        )

    driver = driver_module.WorkerHostDriver(
        runtime_contract=None,
        output_root=tmp_path / "live-runtime-binding-output",
        **kwargs,
    )

    assert driver.runtime["worker"]["sys_platform"] == "linux"
    assert driver.runtime["resources"] == {
        "memory_bytes": 2 * 1024 * 1024 * 1024,
        "memory_swap_bytes": 2 * 1024 * 1024 * 1024,
        "nano_cpus": 1_000_000_000,
    }
    assert driver.runtime_binding_identity["new_container_status"] == "not_created"
    assert driver.runtime_binding_identity["report_sha256"] == (
        driver_module.WORKER_RUNTIME_REPORT_SHA256
    )


def _fixture_plan(tmp_path: Path) -> tuple[Path, dict[str, Any], Path]:
    product, source, fixture = fixtures._write_fixture_product(tmp_path)
    inputs = tmp_path / "plan-inputs"
    inputs.mkdir()
    (
        manifest_path,
        supplemental_path,
        audit_path,
        source_hashes,
        primary_ids,
        supplemental_ids,
    ) = fixtures._test_manifests(inputs, product, source, fixture["assets"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset_manifest = manifest["candidate_baseline"]["force_include_assets"]
    inventory = fixtures.build_source_inventory(
        product,
        manifest,
        expected_commit=source["commit"],
        expected_tree=source["tree"],
    )
    inventory_path = fixtures.write_json(inputs / "source-inventory.json", inventory)
    owner_path = fixtures.write_json(
        inputs / "owner-inventory.json", fixtures._owner_inventory(asset_manifest)
    )
    repo = product.parent
    current_repo = next(
        parent
        for parent in HERE.parents
        if (parent / "policy-engine/architecture/packaging/q2_build_tools.toml").is_file()
    )
    build_profile = current_repo / "policy-engine/architecture/packaging/q2_build_tools.toml"
    dependency_profile = current_repo / "policy-engine/workers/dowhy-014/uv.lock"
    consumer_runner = R6 / "split_consumer.py"
    supplemental_runner = product / Path(
        "docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
        "q2-packaging/raw/supplemental_run.py"
    )
    pins = {
        "primary_manifest_sha256": fixtures.digest(manifest_path.read_bytes()),
        "supplemental_manifest_sha256": fixtures.digest(supplemental_path.read_bytes()),
        "source_audit_receipt_sha256": fixtures.digest(audit_path.read_bytes()),
        "source_inventory_sha256": fixtures.digest(inventory_path.read_bytes()),
        "resource_owner_inventory_sha256": fixtures.digest(owner_path.read_bytes()),
        "build_profile_sha256": fixtures.digest(build_profile.read_bytes()),
        "consumer_runner_sha256": fixtures.digest(consumer_runner.read_bytes()),
        "supplemental_runner_sha256": fixtures.digest(supplemental_runner.read_bytes()),
        "test_source_closure_sha256": fixtures.digest(fixtures.canonical_json_bytes(source_hashes)),
        "dependency_profile_sha256": fixtures.digest(dependency_profile.read_bytes()),
    }
    artifact_root = inputs / "artifacts"
    chain = dict.fromkeys(
        _load_postimage_bundle().composite.ARTIFACT_CHAIN_KEYS,
        "a" * 64,
    )
    artifacts = []
    for profile, chain_key in fixtures.PROFILE_CHAIN_KEYS.items():
        payload = fixtures._fixture_wheel_bytes(profile, fixture["assets"], product)
        path = artifact_root / f"{profile}.whl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        sha = fixtures.digest(payload)
        chain[chain_key] = sha
        artifacts.append(
            {
                "profile": profile,
                "chain_key": chain_key,
                "path": str(path),
                "bytes": len(payload),
                "sha256": sha,
            }
        )
    bundle = _load_postimage_bundle()
    plan = bundle.composite.create_composite_plan(
        source=source,
        input_pins=pins,
        expected_artifact_chain=chain,
        artifacts=artifacts,
        product_root=product,
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
    return repo, plan, current_repo


@pytest.mark.parametrize(
    ("running_after_stop", "stop_returncode"),
    [(False, 0), (True, 0), (False, 1), (None, 0)],
    ids=["stopped", "still-running", "stop-failed", "inspect-unknown"],
)
def test_driver_runs_recorded_worker_route_through_common_barrier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    running_after_stop: bool | None,
    stop_returncode: int,
) -> None:
    repo, plan, current_repo = _fixture_plan(tmp_path)
    bundle = _load_postimage_bundle()
    runtime = worker_fixtures._runtime_contract()
    neutral = tmp_path / "neutral-cwd"
    neutral.mkdir()
    output_root = tmp_path / "recorded-driver-output"
    prepared_by_profile: dict[str, dict[str, Any]] = {}
    container_by_profile: dict[str, str] = {}
    events: list[tuple[str, str]] = []
    docker_observations: list[dict[str, Any]] = []
    actual_exec_calls: list[list[str]] = []

    original_prepare = bundle.partition_runner.prepare_worker_profile_mounts

    def capture_prepare(
        plan_arg: dict[str, Any],
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
        prepared = original_prepare(
            plan_arg,
            profile=profile,
            source_root=source_root,
            mount_map=mount_map,
            runtime_contract=runtime_contract,
            split_consumer_path=split_consumer_path,
            partition_runner_path=partition_runner_path,
            worker_mounts_path=worker_mounts_path,
            origin_gate_path=origin_gate_path,
        )
        prepared_by_profile[profile] = prepared
        events.append(("prepare", profile))
        return prepared

    original_finalize = bundle.partition_runner.finalize_worker_profile_request

    def capture_finalize(
        plan_arg: dict[str, Any],
        prepared: dict[str, Any],
        *,
        profile: str,
        runtime_contract: dict[str, Any],
        container_inspect_receipt: dict[str, Any],
        expected_container_id: str,
        mount_map: dict[str, Any] | None,
        request_relative_path: str,
        receipt_relative_path: str,
        entrypoint_name: str,
    ) -> dict[str, Any]:
        events.append(("finalize", profile))
        return original_finalize(
            plan_arg,
            prepared,
            profile=profile,
            runtime_contract=runtime_contract,
            container_inspect_receipt=container_inspect_receipt,
            expected_container_id=expected_container_id,
            mount_map=mount_map,
            request_relative_path=request_relative_path,
            receipt_relative_path=receipt_relative_path,
            entrypoint_name=entrypoint_name,
        )

    monkeypatch.setattr(bundle.partition_runner, "prepare_worker_profile_mounts", capture_prepare)
    monkeypatch.setattr(
        bundle.partition_runner,
        "finalize_worker_profile_request",
        capture_finalize,
    )

    def command_runner(
        argv: list[str],
        *,
        cwd: str,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
        shell: bool,
    ) -> SimpleNamespace:
        assert shell is False
        assert capture_output is True
        assert text is True
        assert check is False
        assert timeout > 0
        assert cwd == str(neutral)
        docker_observations.append({"argv": argv, "cwd": cwd})
        if "create" in argv:
            name = argv[argv.index("--name") + 1]
            profile = next(value for value in plan["profiles"] if value not in container_by_profile)
            container_id = hashlib.sha256(name.encode()).hexdigest()
            container_by_profile[profile] = container_id
            events.append(("create", profile))
            return SimpleNamespace(returncode=0, stdout=f"{container_id}\n", stderr="")
        if "start" in argv:
            container_id = argv[-1]
            profile = next(
                name for name, value in container_by_profile.items() if value == container_id
            )
            events.append(("start", profile))
            return SimpleNamespace(returncode=0, stdout=f"{container_id}\n", stderr="")
        if "stop" in argv:
            container_id = argv[-1]
            profile = next(
                name for name, value in container_by_profile.items() if value == container_id
            )
            assert argv[argv.index("--time") + 1] == "10"
            events.append(("stop", profile))
            return SimpleNamespace(
                returncode=stop_returncode,
                stdout=f"{container_id}\n" if stop_returncode == 0 else "",
                stderr="" if stop_returncode == 0 else "controlled stop failure",
            )
        assert "inspect" in argv
        container_id = argv[-1]
        profile = next(
            name for name, value in container_by_profile.items() if value == container_id
        )
        mapping = prepared_by_profile[profile]["mount_map"]
        inspect = worker_fixtures._synthetic_inspect_receipt(runtime, mapping, container_id)
        field_row = next(row for row in inspect["commands"] if row["argv"] == argv)
        post_stop = any(kind == "stop" and name == profile for kind, name in events)
        field_name = field_row["field"]
        if post_stop:
            events.append((f"post-stop-inspect:{field_name}", profile))
            if field_name == "State.Running":
                if running_after_stop is None:
                    field_row["returncode"] = 1
                    field_row["stdout"] = ""
                    field_row["stderr"] = "controlled inspect failure"
                else:
                    field_row["stdout"] = "true\n" if running_after_stop else "false\n"
        else:
            events.append((f"inspect:{field_name}", profile))
        return SimpleNamespace(
            returncode=field_row["returncode"],
            stdout=field_row["stdout"],
            stderr=field_row["stderr"],
        )

    def recorded_exec(
        argv: list[str],
        *,
        input: bytes,
        capture_output: bool,
        timeout: int,
        check: bool,
    ) -> SimpleNamespace:
        assert capture_output is True
        assert timeout == driver.launch_timeout_seconds
        assert check is False
        request_raw = input
        request = json.loads(request_raw)
        profile = request["profile"]
        container_id = container_by_profile[profile]
        assert argv[-2:] == [
            "--request-sha256",
            hashlib.sha256(request_raw).hexdigest(),
        ]
        assert request["container_identity"]["container_id"] == container_id
        actual_exec_calls.append(argv)
        events.append(("launch", profile))
        # This test-only result writer invokes the R7 request finalizer again
        # to make its fixture. Keep that fixture call out of the driver's
        # lifecycle trace, where a second finalization would be false evidence.
        monkeypatch.setattr(
            bundle.partition_runner,
            "finalize_worker_profile_request",
            original_finalize,
        )
        try:
            fixture_result = fixtures._synthetic_worker_execution(
                tmp_path / "fixture-worker-output",
                plan,
                profile,
                repo,
                runtime,
                prepared_by_profile[profile],
                container_id=container_id,
            )
        finally:
            monkeypatch.setattr(
                bundle.partition_runner,
                "finalize_worker_profile_request",
                capture_finalize,
            )
        # The R7 helper models the worker plus a host launch. Here the real R7
        # launcher owns host evidence, so discard only those three test-owned
        # host-side fixture files before returning the worker's result bytes.
        for name in (
            "host-launch.json",
            "host-command-stdout.txt",
            "host-command-stderr.txt",
        ):
            (fixture_result.parent / name).unlink()
        return SimpleNamespace(
            returncode=0,
            stdout=b"fixture worker result retained\n",
            stderr=b"",
        )

    monkeypatch.setattr(bundle.partition_runner.subprocess, "run", recorded_exec)
    coordinator_calls = []
    real_coordinator = bundle.composite.execute_composite_plan_with_worker

    def track_coordinator(
        plan_arg: dict[str, Any],
        *,
        run_host_partition: Callable[[dict[str, Any]], str | Path],
        run_linux_worker_partition: Callable[[dict[str, Any]], str | Path],
        run_supplemental_partition: Callable[[str, dict[str, Any]], dict[str, Any]],
    ) -> dict[str, Any]:
        coordinator_calls.append(True)
        return real_coordinator(
            plan_arg,
            run_host_partition=run_host_partition,
            run_linux_worker_partition=run_linux_worker_partition,
            run_supplemental_partition=run_supplemental_partition,
        )

    monkeypatch.setattr(bundle.composite, "execute_composite_plan_with_worker", track_coordinator)
    driver = driver_module.WorkerHostDriver(
        plan=plan,
        runtime_contract=runtime,
        source_bundle=bundle,
        source_root=repo,
        output_root=output_root,
        origin_gate_path=(
            current_repo
            / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
            / "q2-packaging/raw/installed_origin_gate_r4.py"
        ),
        neutral_cwd=neutral,
        command_runner=command_runner,
        command_execution_mode="recorded_test",
    )

    def run_host(partition: dict[str, Any]) -> Path:
        events.append(("host", partition["profile"]))
        return fixtures._primary_execution(
            tmp_path / "host-receipts",
            plan,
            partition["profile"],
            "host",
            repo,
            plan["owner_resources"],
        )

    def run_supplemental(profile: str, admission: dict[str, Any]) -> dict[str, Any]:
        events.append(("supplemental", profile))
        return {
            "profile": profile,
            "barrier_sha256": admission["barrier"]["execution_rows_sha256"],
        }

    host_executor = SimpleNamespace(plan=plan, run_partition=run_host)
    completed_supplemental: set[str] = set()

    def run_supplemental_through_executor(
        profile: str, admission: dict[str, Any]
    ) -> dict[str, Any]:
        result = run_supplemental(profile, admission)
        completed_supplemental.add(profile)
        return result

    supplemental_executor = SimpleNamespace(
        plan=plan,
        host=host_executor,
        completed=completed_supplemental,
        run_profile=run_supplemental_through_executor,
    )
    if running_after_stop is not False or stop_returncode != 0:
        expected_cleanup_status = (
            "still_running"
            if running_after_stop is True
            else "stop_command_failed_state_not_running"
            if stop_returncode != 0 and running_after_stop is False
            else "unknown"
        )
        with pytest.raises(
            driver_module.WorkerHostDriverError,
            match=(
                f"owned worker container cleanup was not verified \\({expected_cleanup_status}\\)"
            ),
        ):
            composite_cli.execute_composite_plan(
                plan=plan,
                worker_driver=driver,
                host_executor=host_executor,
                supplemental_executor=supplemental_executor,
            )
        assert not completed_supplemental
        assert not any(kind == "supplemental" for kind, _ in events)
        profile = next(iter(container_by_profile))
        sequence_path = (
            output_root / "profiles" / profile / "receipts" / "host-driver-sequence.json"
        )
        sequence = json.loads(sequence_path.read_text(encoding="utf-8"))
        expected_stop_command_status = (
            "succeeded_for_exact_owned_container_id" if stop_returncode == 0 else "failed"
        )
        expected_inspection_status = (
            "still_running"
            if running_after_stop is True
            else "verified_not_running"
            if running_after_stop is False
            else "unknown"
        )
        assert sequence["stop_command_status"] == expected_stop_command_status
        assert sequence["post_stop_inspection"]["status"] == expected_inspection_status
        assert sequence["post_stop_inspection"]["state_running_observed"] == (
            None if running_after_stop is None else str(running_after_stop).lower()
        )
        assert sequence["cleanup_status"] == expected_cleanup_status
        assert sequence["complete"] is False
        return

    result = composite_cli.execute_composite_plan(
        plan=plan,
        worker_driver=driver,
        host_executor=host_executor,
        supplemental_executor=supplemental_executor,
    )

    assert coordinator_calls == [True]
    assert len(actual_exec_calls) == 3
    assert len([row for row in docker_observations if "create" in row["argv"]]) == 3
    assert len([row for row in docker_observations if "inspect" in row["argv"]]) == 3 * 15
    for argv in [row["argv"] for row in docker_observations if "create" in row["argv"]]:
        assert argv[argv.index("--network") + 1] == "none"
        assert argv[argv.index("--memory") + 1] == str(runtime["resources"]["memory_bytes"])
        assert argv[argv.index("--memory-swap") + 1] == str(
            runtime["resources"]["memory_swap_bytes"]
        )
        assert argv[argv.index("--cpus") + 1] == "1.0"
        assert "--read-only" in argv
        assert argv[argv.index("--tmpfs") + 1] == (
            "/tmp:rw,nosuid,nodev,noexec,size=256m"  # noqa: S108 -- isolated worker tmpfs.
        )
        mounts = [argv[index + 1] for index, value in enumerate(argv[:-1]) if value == "--mount"]
        assert (
            sum(
                value.startswith("type=volume,") and value.endswith(",readonly") for value in mounts
            )
            == 2
        )
        assert (
            sum(value.startswith("type=bind,") and value.endswith(",readonly") for value in mounts)
            == 2
        )
        assert (
            sum(
                value.startswith("type=bind,")
                and ",dst=/mnt/e02-q2/prefix" in value
                and ",readonly" not in value
                for value in mounts
            )
            == 1
        )
        assert (
            sum(
                value.startswith("type=bind,")
                and ",dst=/mnt/e02-q2/receipts" in value
                and ",readonly" not in value
                for value in mounts
            )
            == 1
        )
    last_primary = max(
        index for index, (kind, _) in enumerate(events) if kind in {"host", "launch"}
    )
    first_supplemental = min(
        index for index, (kind, _) in enumerate(events) if kind == "supplemental"
    )
    assert first_supplemental > last_primary
    receipt = result["receipt"]
    assert receipt["barrier"]["status"] == "primary_profiles_complete"
    assert receipt["barrier"]["execution_row_count"] == 6
    assert len(receipt["supplemental"]) == 3
    persisted = result["persisted_receipt"]
    assert [row["profile"] for row in persisted["worker_lifecycle"]] == plan["profiles"]
    assert all(
        row["stop_command_status"] == "succeeded_for_exact_owned_container_id"
        and row["post_stop_inspection_status"] == "verified_not_running"
        and row["cleanup_status"] == "stopped_and_verified"
        and (output_root / row["sequence"]["path"]).is_file()
        for row in persisted["worker_lifecycle"]
    )
    assert persisted["source_set_binding"]["r7_recomputed_sorted_source_set_sha256"] == (
        "91065f9f205974466a016bfebdf863fa1fb0e370a5b6a1bd8d0b7671d6421b45"
    )
    assert persisted["worker_runtime_binding_input"]["status"] == (
        "recorded_test_fixture_not_runtime"
    )
    for profile in plan["profiles"]:
        container_id = container_by_profile[profile]
        expected_route = [
            "prepare",
            "create",
            "start",
            *[
                f"inspect:{row['field']}"
                for row in bundle.worker_mounts.worker_container_inspect_argv(runtime, container_id)
            ],
            "finalize",
            "launch",
            "stop",
            "post-stop-inspect:Id",
            "post-stop-inspect:State.Running",
        ]
        observed_route = [
            kind
            for kind, event_profile in events
            if event_profile == profile
            and (
                kind in {"prepare", "create", "start", "finalize", "launch", "stop"}
                or kind.startswith("inspect:")
                or kind.startswith("post-stop-inspect:")
            )
        ]
        assert observed_route == expected_route
        sequence_path = (
            output_root / "profiles" / profile / "receipts" / "host-driver-sequence.json"
        )
        sequence = json.loads(sequence_path.read_text(encoding="utf-8"))
        assert sequence["worker_result_status"] == "fixture_result_not_runtime"
        assert sequence["runtime_binding_status"] == "recorded_test_fixture_not_runtime"
        assert sequence["execution_mode"] == "recorded_test"
        assert sequence["stop_command_status"] == "succeeded_for_exact_owned_container_id"
        assert sequence["post_stop_inspection"]["status"] == "verified_not_running"
        assert sequence["post_stop_inspection"]["container_id_observed"] == sequence["container_id"]
        assert sequence["post_stop_inspection"]["state_running_observed"] == "false"
        assert sequence["cleanup_status"] == "stopped_and_verified"
        post_stop_refs = sequence["post_stop_inspection"]["commands"]
        assert len(post_stop_refs) == 2
        post_stop_rows = [
            json.loads(Path(reference["path"]).read_text(encoding="utf-8"))
            for reference in post_stop_refs
        ]
        assert {row["label"] for row in post_stop_rows} == {
            "container-post-stop-inspect-Id",
            "container-post-stop-inspect-State.Running",
        }
        assert all(
            row["argv"][row["argv"].index("--format") + 1] in {"{{.Id}}", "{{.State.Running}}"}
            for row in post_stop_rows
        )
        assert sequence["container_name"].startswith("e02-q2-")
        assert sequence["container_name"] == f"e02-q2-{sequence['attempt_id']}"
        assert sequence["attempt_id"] in sequence["container_name"]
        assert sequence["command_count"] == 18
        assert len(sequence["commands"]) == 18
        assert all(Path(row["path"]).is_file() for row in sequence["commands"])


def test_worker_attempt_name_is_unique_and_owned_container_stops_after_failure(
    tmp_path: Path,
) -> None:
    repo, plan, current_repo = _fixture_plan(tmp_path)
    bundle = _load_postimage_bundle()
    runtime = worker_fixtures._runtime_contract()
    neutral = tmp_path / "failure-neutral-cwd"
    neutral.mkdir()
    linux_row = next(
        row
        for row in plan["run_plan"]
        if row["phase"] == "primary" and row["executor"] == "linux-worker"
    )
    attempt_names: list[str] = []
    stopped_ids: list[str] = []
    created_ids: list[str] = []
    all_argv: list[list[str]] = []

    def command_runner(
        argv: list[str],
        *,
        cwd: str,
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
        shell: bool,
    ) -> SimpleNamespace:
        assert cwd == str(neutral)
        assert capture_output
        assert text
        assert not check
        assert not shell
        assert timeout > 0
        all_argv.append(argv)
        if "create" in argv:
            name = argv[argv.index("--name") + 1]
            attempt_names.append(name)
            container_id = hashlib.sha256(name.encode()).hexdigest()
            created_ids.append(container_id)
            return SimpleNamespace(returncode=0, stdout=f"{container_id}\n", stderr="")
        if "start" in argv:
            return SimpleNamespace(returncode=1, stdout="", stderr="controlled start failure")
        if "stop" in argv:
            container_id = argv[-1]
            stopped_ids.append(container_id)
            return SimpleNamespace(returncode=0, stdout=f"{container_id}\n", stderr="")
        if "inspect" in argv:
            container_id = argv[-1]
            field = argv[argv.index("--format") + 1]
            if field == "{{.Id}}":
                output = container_id
            elif field == "{{.State.Running}}":
                output = "false"
            else:
                raise AssertionError(f"unexpected post-stop inspect field: {field}")
            return SimpleNamespace(returncode=0, stdout=f"{output}\n", stderr="")
        raise AssertionError(f"inspect/launch must not run after start failure: {argv}")

    for index in range(2):
        driver = driver_module.WorkerHostDriver(
            plan=plan,
            runtime_contract=runtime,
            source_bundle=bundle,
            source_root=repo,
            output_root=tmp_path / f"failed-worker-attempt-{index}",
            origin_gate_path=(
                current_repo
                / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
                / "q2-packaging/raw/installed_origin_gate_r4.py"
            ),
            neutral_cwd=neutral,
            command_runner=command_runner,
            command_execution_mode="recorded_test",
        )
        with pytest.raises(driver_module.WorkerHostDriverError, match="Docker start"):
            driver.run_linux_partition(linux_row)
        sequence_path = (
            driver.output_root
            / "profiles"
            / linux_row["profile"]
            / "receipts"
            / "host-driver-sequence.json"
        )
        sequence = json.loads(sequence_path.read_text(encoding="utf-8"))
        assert sequence["complete"] is False
        assert sequence["stop_command_status"] == "succeeded_for_exact_owned_container_id"
        assert sequence["post_stop_inspection"]["status"] == "verified_not_running"
        assert sequence["cleanup_status"] == "stopped_and_verified"
        assert sequence["container_id"] == created_ids[-1]
        assert sequence["attempt_id"] in sequence["container_name"]

    assert len(set(attempt_names)) == 2
    assert stopped_ids == created_ids
    assert all("rm" not in argv for argv in all_argv)


def test_cli_main_forwards_the_explicit_build_and_source_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "composite-receipt.json"
    captured: dict[str, object] = {}

    def run_composite(**kwargs: object) -> Path:
        captured.update(kwargs)
        return output

    monkeypatch.setattr(composite_cli, "run_composite", run_composite)
    args = [
        "--repo",
        str(tmp_path / "repo"),
        "--build-receipt",
        str(tmp_path / "host-build-receipt.json"),
        "--build-receipt-sha256",
        "a" * 64,
        "--expected-source-commit",
        "b" * 40,
        "--expected-source-tree",
        "c" * 40,
        "--output-root",
        str(tmp_path / "runs" / "attempt-1"),
        "--state-parent",
        str(tmp_path / "neutral-state"),
    ]

    assert composite_cli.main(args) == 0
    assert captured == {
        "repo_root": Path(tmp_path / "repo"),
        "build_receipt_path": Path(tmp_path / "host-build-receipt.json"),
        "build_receipt_sha256": "a" * 64,
        "expected_commit": "b" * 40,
        "expected_tree": "c" * 40,
        "output_root": Path(tmp_path / "runs" / "attempt-1"),
        "state_parent": Path(tmp_path / "neutral-state"),
    }
    assert str(output) in capsys.readouterr().out


def test_r9_receipt_sources_bind_to_the_loaded_concrete_modules() -> None:
    rows = composite_cli.implementation_source_bindings(REPO_ROOT)
    manifest = json.loads((SOURCE / "source-manifest-r10.json").read_text())
    expected_paths = {
        str(REPO_ROOT.joinpath(*Path(row["path"]).parts).resolve())
        for row in manifest["source_set"]["files"]
    }
    assert {row["path"] for row in rows} == expected_paths
    for row in rows:
        path = Path(row["path"])
        raw = path.read_bytes()
        assert row["bytes"] == len(raw)
        assert row["sha256"] == hashlib.sha256(raw).hexdigest()


def test_protocol_runner_binds_nested_r10_source_set_files() -> None:
    manifest = json.loads(protocol_runner.R10_MANIFEST.read_text(encoding="utf-8"))
    source_set = manifest["source_set"]
    rows = source_set["files"]
    assert source_set["file_count"] == len(rows) == 16
    expected = tuple(protocol_runner.ROOT.joinpath(*Path(row["path"]).parts) for row in rows)
    assert (*expected, protocol_runner.R10_MANIFEST) == protocol_runner.SOURCE_FILES


def test_worker_route_without_launch_cannot_reach_supplemental_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, plan, current_repo = _fixture_plan(tmp_path)
    bundle = _load_postimage_bundle()

    def forbidden_docker_command(argv: list[str], **kwargs: object) -> None:
        raise AssertionError("recorded-test removal control must not invoke Docker")

    driver = driver_module.WorkerHostDriver(
        plan=plan,
        runtime_contract=worker_fixtures._runtime_contract(),
        source_bundle=bundle,
        source_root=repo,
        output_root=tmp_path / "removed-launch-output",
        origin_gate_path=(
            current_repo
            / "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
            / "q2-packaging/raw/installed_origin_gate_r4.py"
        ),
        neutral_cwd=tmp_path,
        command_runner=forbidden_docker_command,
        command_execution_mode="recorded_test",
    )
    supplemental_profiles: list[str] = []
    monkeypatch.setattr(
        driver,
        "run_linux_partition",
        lambda partition: tmp_path / "absent-worker-result.json",
    )

    def run_host(partition: dict[str, Any]) -> Path:
        return fixtures._primary_execution(
            tmp_path / "host-receipts",
            plan,
            partition["profile"],
            "host",
            repo,
            plan["owner_resources"],
        )

    def run_supplemental(profile: str, admission: dict[str, Any]) -> dict[str, Any]:
        supplemental_profiles.append(profile)
        return {
            "profile": profile,
            "barrier_sha256": admission["barrier"]["execution_rows_sha256"],
        }

    with pytest.raises(bundle.composite.ProfileCompositeError):
        driver.execute(
            run_host_partition=run_host,
            run_supplemental_partition=run_supplemental,
        )
    assert supplemental_profiles == []

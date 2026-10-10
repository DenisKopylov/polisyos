#!/usr/bin/env python3
"""Apply measured per-profile timeouts around the reviewed Q2 runner."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import stat
import sys
import time
from pathlib import Path
from typing import Any


EXPECTED_RUNNER_SHA256 = "a64bab2a692e9f3a88b0693887a430aa3ee2f78e2ca4fa847ed5871ec0c7a3b0"
EXPECTED_MANIFEST_SHA256 = "1656e209631d8fa401ed65a87c8fff90e07f5996bf8435da4f860e2dc987f277"
EXPECTED_PROFILE_ORDER = (
    "source-wheel",
    "rebuilt-sdist-wheel",
    "rebuilt-gcp-archive-wheel",
)
TIMEOUT_MULTIPLIER = 2


class DriverFailure(RuntimeError):
    """Raised when a previous consumer profile cannot authorize a timeout."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _capture_file_binding(path: Path) -> dict[str, Any]:
    """Bind an existing regular file by its original path, byte count, and digest."""
    binding: dict[str, Any] = {"path": str(path), "available": False}
    try:
        path_snapshot = path.lstat()
    except FileNotFoundError:
        binding["unavailable_reason"] = "file_missing"
        return binding
    except OSError as error:
        binding["unavailable_reason"] = f"stat_error:{error.errno}"
        return binding
    if not stat.S_ISREG(path_snapshot.st_mode):
        binding["unavailable_reason"] = "not_regular_file"
        return binding

    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        binding["unavailable_reason"] = "file_missing"
        return binding
    except OSError as error:
        try:
            current_path = path.lstat()
        except OSError:
            current_path = None
        binding["unavailable_reason"] = (
            "not_regular_file"
            if current_path is not None and not stat.S_ISREG(current_path.st_mode)
            else f"open_error:{error.errno}"
        )
        return binding

    try:
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                binding["unavailable_reason"] = "not_regular_file"
                return binding
            if (before.st_dev, before.st_ino) != (path_snapshot.st_dev, path_snapshot.st_ino):
                binding["unavailable_reason"] = "path_changed_before_open"
                return binding
            digest = hashlib.sha256()
            byte_count = 0
            remaining = before.st_size
            while remaining > 0:
                block = stream.read(min(1024 * 1024, remaining))
                if not block:
                    binding["unavailable_reason"] = "file_changed_during_capture"
                    return binding
                digest.update(block)
                byte_count += len(block)
                remaining -= len(block)
            if stream.read(1):
                binding["unavailable_reason"] = "file_changed_during_capture"
                return binding
            after = os.fstat(stream.fileno())
            stable_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            stable_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            if stable_before != stable_after or byte_count != after.st_size:
                binding["unavailable_reason"] = "file_changed_during_capture"
                return binding
            binding.update(
                {
                    "available": True,
                    "bytes": byte_count,
                    "sha256": digest.hexdigest(),
                }
            )
            return binding
    except OSError as error:
        binding["unavailable_reason"] = f"read_error:{error.errno}"
        return binding


def capture_terminal_command_evidence(log_stem: Path) -> dict[str, Any]:
    """Capture path-bound evidence for a terminal runner command and both streams."""
    return {
        "schema_version": 1,
        "command_record": _capture_file_binding(log_stem.with_suffix(".command.json")),
        "stdout": _capture_file_binding(log_stem.with_suffix(".stdout.txt")),
        "stderr": _capture_file_binding(log_stem.with_suffix(".stderr.txt")),
    }


def verify_terminal_command_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    """Verify that bound command and stream files still match their captured bytes."""
    if evidence.get("schema_version") != 1:
        raise DriverFailure("terminal command evidence has an unsupported schema version")
    command_metadata = None
    for key in ("command_record", "stdout", "stderr"):
        binding = evidence.get(key)
        if not isinstance(binding, dict):
            raise DriverFailure(f"terminal command evidence is missing {key}")
        if binding.get("available") is not True:
            reason = binding.get("unavailable_reason", "unavailability_reason_missing")
            raise DriverFailure(f"terminal command {key} is unavailable: {reason}")
        path_value = binding.get("path")
        expected_bytes = binding.get("bytes")
        expected_sha = binding.get("sha256")
        if not isinstance(path_value, str) or not isinstance(expected_bytes, int) or not isinstance(expected_sha, str):
            raise DriverFailure(f"terminal command {key} binding is incomplete")
        actual = _capture_file_binding(Path(path_value))
        if actual.get("available") is not True:
            reason = actual.get("unavailable_reason", "unavailability_reason_missing")
            raise DriverFailure(f"terminal command {key} cannot be re-read: {reason}")
        if actual.get("bytes") != expected_bytes or actual.get("sha256") != expected_sha:
            raise DriverFailure(f"terminal command {key} changed after capture: {path_value}")
        if key == "command_record":
            try:
                command_bytes = Path(path_value).read_bytes()
                command = json.loads(command_bytes)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                raise DriverFailure(f"terminal command record is unreadable JSON: {path_value}") from error
            if (
                len(command_bytes) != expected_bytes
                or hashlib.sha256(command_bytes).hexdigest() != expected_sha
            ):
                raise DriverFailure(f"terminal command record changed while verifying: {path_value}")
            if (
                not isinstance(command, dict)
                or not isinstance(command.get("timed_out"), bool)
                or "returncode" not in command
                or command.get("stream_output") is not True
            ):
                raise DriverFailure(f"terminal command record lacks streamed outcome metadata: {path_value}")
            command_metadata = command
    if command_metadata is None:
        raise DriverFailure("terminal command record could not be verified")
    return command_metadata


def _load_reviewed_runner(driver_path: Path) -> tuple[Any, dict[str, Any], Path, Path, str, str]:
    runner_path = driver_path.with_name("run.py")
    manifest_path = driver_path.parent.parent / "installed-wave-manifest.json"
    if runner_path.is_symlink() or manifest_path.is_symlink():
        raise DriverFailure("Q2 runner and manifest must be regular, non-symlinked inputs")
    runner_path = runner_path.resolve(strict=True)
    manifest_path = manifest_path.resolve(strict=True)
    runner_sha = sha256_file(runner_path)
    manifest_sha = sha256_file(manifest_path)
    if runner_sha != EXPECTED_RUNNER_SHA256:
        raise DriverFailure(
            f"reviewed runner hash mismatch: expected={EXPECTED_RUNNER_SHA256} actual={runner_sha}"
        )
    if manifest_sha != EXPECTED_MANIFEST_SHA256:
        raise DriverFailure(
            f"reviewed manifest hash mismatch: expected={EXPECTED_MANIFEST_SHA256} actual={manifest_sha}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Only import after both reviewed execution inputs have been content-verified.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("q2_reviewed_runner", runner_path)
    if spec is None or spec.loader is None:
        raise DriverFailure(f"cannot import reviewed Q2 runner: {runner_path}")
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    if sha256_file(runner_path) != runner_sha or sha256_file(manifest_path) != manifest_sha:
        raise DriverFailure("reviewed Q2 runner or manifest changed during import")
    return runner, manifest, runner_path, manifest_path, runner_sha, manifest_sha


def _run_root_from_log_stem(log_stem: Path) -> Path:
    if log_stem.parent.name == "logs":
        return log_stem.parent.parent
    if len(log_stem.parents) >= 3 and log_stem.parents[1].name == "consumer-runs":
        return log_stem.parents[2]
    raise DriverFailure(f"cannot derive Q2 run root from command log path: {log_stem}")


def _expected_selected_ids(runner: Any, manifest: dict[str, Any], run_root: Path) -> set[str]:
    frozen_product = run_root / "frozen-source" / "policy-engine"
    original_ids = runner.baseline_node_ids(frozen_product, manifest)
    baseline_count = manifest["original_q2_suite"]["baseline_case_count"]
    if len(original_ids) != baseline_count:
        raise DriverFailure(
            f"prior profile original baseline differs from its manifest: "
            f"actual={len(original_ids)} expected={baseline_count}"
        )
    try:
        return runner.verify_current_primary_suite_sources(
            frozen_product, manifest, original_ids
        )
    except runner.WaveFailure as error:
        raise DriverFailure(
            f"prior profile current selector manifest is invalid: {error}"
        ) from error


def validate_completed_profile(
    runner: Any,
    manifest: dict[str, Any],
    run_root: Path,
    profile_name: str,
    *,
    expected_timeout_seconds: int | None,
    terminal_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconcile the prior profile's actual collection, JUnit, and output files."""
    run_receipt_path = run_root / "run-receipt.json"
    if not run_receipt_path.is_file():
        raise DriverFailure(f"prior profile has no runner receipt: {run_receipt_path}")
    run_receipt = json.loads(run_receipt_path.read_text(encoding="utf-8"))
    try:
        consumer = run_receipt["profiles"][profile_name]["consumers"]
    except KeyError as error:
        raise DriverFailure(
            f"prior profile has no completed consumer receipt: {profile_name}"
        ) from error

    expected_ids = _expected_selected_ids(runner, manifest, run_root)
    collected_path = Path(consumer["collected_nodeids_path"])
    junit_path = Path(consumer["junit_path"])
    origin_path = Path(consumer["origin_proof_path"])
    command_path = Path(consumer["process_output"]["stdout_path"]).with_name(
        "consumer-suite.command.json"
    )
    if terminal_evidence is None:
        raise DriverFailure("prior profile has no captured terminal command evidence")
    command = verify_terminal_command_evidence(terminal_evidence)
    if Path(terminal_evidence["command_record"]["path"]) != command_path:
        raise DriverFailure("prior profile command-record path differs from captured evidence")
    collected_list = json.loads(collected_path.read_text(encoding="utf-8"))
    collected_ids = set(collected_list)
    if len(collected_ids) != len(collected_list) or collected_ids != expected_ids:
        raise DriverFailure(
            "prior profile collection differs from the complete expected ID set: "
            f"actual={len(collected_ids)} expected={len(expected_ids)}"
        )

    executed_ids, counts = runner.junit_node_ids(
        junit_path,
        manifest["original_q2_suite"]["test_paths"][-1],
    )
    if executed_ids != expected_ids:
        raise DriverFailure(
            "prior profile JUnit set differs from the complete expected ID set: "
            f"actual={len(executed_ids)} expected={len(expected_ids)}"
        )
    if counts["tests"] != len(expected_ids) or any(
        counts[key] for key in ("skipped", "failures", "errors")
    ):
        raise DriverFailure(
            f"prior profile did not pass the complete current selector set: {counts}; "
            f"expected={len(expected_ids)}"
        )
    if consumer["returncode"] != 0 or consumer["selected_node_ids"] != len(expected_ids):
        raise DriverFailure(
            "runner consumer receipt does not confirm the complete current selector set"
        )
    expected_digest = runner.node_ids_sha256(expected_ids)
    if consumer.get("selected_node_ids_sha256") != expected_digest:
        raise DriverFailure("runner consumer receipt has another current selector-set digest")

    origin = json.loads(origin_path.read_text(encoding="utf-8"))
    if not origin.get("verified"):
        raise DriverFailure("prior profile installed-origin proof did not verify")
    if (
        command.get("returncode") != 0
        or command.get("timed_out")
        or command.get("timeout_seconds") != expected_timeout_seconds
        or not command.get("stream_output")
    ):
        raise DriverFailure("prior profile command record does not match its completed run")

    process_output = consumer["process_output"]
    for stream_name in ("stdout", "stderr"):
        path = Path(process_output[f"{stream_name}_path"])
        if not path.is_file():
            raise DriverFailure(f"prior profile {stream_name} stream was not retained: {path}")
        if path.stat().st_size != process_output[f"{stream_name}_bytes"]:
            raise DriverFailure(f"prior profile {stream_name} byte count differs from its receipt")
        if sha256_file(path) != process_output[f"{stream_name}_sha256"]:
            raise DriverFailure(f"prior profile {stream_name} digest differs from its receipt")

    return {
        "exact_current_suite_collection_and_junit_verified": True,
        "current_suite_selected_node_ids": len(expected_ids),
        "current_suite_selected_node_ids_sha256": expected_digest,
        "historical_baseline_subset_node_ids": len(
            runner.historical_baseline_subset_ids(
                manifest,
                runner.baseline_node_ids(
                    run_root / "frozen-source" / "policy-engine", manifest
                ),
            )
        ),
        "zero_skips_failures_errors_verified": True,
        "installed_origin_and_full_streams_verified": True,
        "run_receipt_path": str(run_receipt_path),
        "collection_path": str(collected_path),
        "junit_path": str(junit_path),
        "origin_proof_path": str(origin_path),
        "command_record_path": str(command_path),
        "terminal_command_evidence_verified": True,
        "stdout_path": process_output["stdout_path"],
        "stderr_path": process_output["stderr_path"],
    }


def install_adaptive_run_command(
    runner: Any,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Wrap only consumer commands, delegating all work to the reviewed runner."""
    original = runner.run_command
    state: dict[str, Any] = {"run_root": None, "profiles": []}

    def adaptive_run_command(
        argv: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        log_stem: Path,
        check: bool = True,
        stream_output: bool = False,
        timeout_seconds: float | None = None,
    ) -> Any:
        run_root = _run_root_from_log_stem(log_stem)
        if state["run_root"] is None:
            state["run_root"] = run_root
        elif state["run_root"] != run_root:
            raise runner.WaveFailure("Q2 timeout driver observed multiple run roots")

        if log_stem.name != "consumer-suite":
            return original(
                argv,
                cwd=cwd,
                env=env,
                log_stem=log_stem,
                check=check,
                stream_output=stream_output,
                timeout_seconds=timeout_seconds,
            )

        index = len(state["profiles"])
        if index >= len(EXPECTED_PROFILE_ORDER):
            raise runner.WaveFailure("Q2 runner invoked more than three consumer profiles")
        profile_name = log_stem.parent.name
        if profile_name != EXPECTED_PROFILE_ORDER[index]:
            raise runner.WaveFailure(
                f"Q2 consumer profile order changed: expected={EXPECTED_PROFILE_ORDER[index]} "
                f"actual={profile_name}"
            )
        if not stream_output:
            raise runner.WaveFailure("Q2 consumer streams must remain directly retained")

        validation = None
        if index == 0:
            timeout = None
        else:
            previous = state["profiles"][-1]
            if previous["returncode"] != 0 or previous["elapsed_wall_seconds"] <= 0:
                raise runner.WaveFailure("cannot calibrate from an unsuccessful prior profile")
            try:
                validation = validate_completed_profile(
                    runner,
                    manifest,
                    run_root,
                    previous["profile"],
                    expected_timeout_seconds=previous["timeout_seconds"],
                    terminal_evidence=previous.get("terminal_evidence"),
                )
            except DriverFailure as error:
                previous["validation_error"] = str(error)
                raise runner.WaveFailure(
                    f"prior {previous['profile']} profile cannot authorize a timeout: {error}"
                ) from error
            previous["validation"] = validation
            timeout = math.ceil(TIMEOUT_MULTIPLIER * previous["elapsed_wall_seconds"])

        started = time.monotonic()
        try:
            result = original(
                argv,
                cwd=cwd,
                env=env,
                log_stem=log_stem,
                check=check,
                stream_output=stream_output,
                timeout_seconds=timeout,
            )
        except BaseException as error:
            elapsed = time.monotonic() - started
            command_path = log_stem.with_suffix(".command.json")
            terminal_evidence = capture_terminal_command_evidence(log_stem)
            try:
                verify_terminal_command_evidence(terminal_evidence)
                terminal_evidence_error = None
            except DriverFailure as evidence_error:
                terminal_evidence_error = str(evidence_error)
            try:
                command = (
                    json.loads(command_path.read_text(encoding="utf-8"))
                    if command_path.is_file()
                    else {}
                )
            except (OSError, ValueError, json.JSONDecodeError):
                command = {}
            state["profiles"].append(
                {
                    "profile": profile_name,
                    "timeout_seconds": timeout,
                    "elapsed_wall_seconds": elapsed,
                    "outcome": "timed_out" if command.get("timed_out") else "raised",
                    "error": f"{type(error).__name__}: {error}",
                    "command_record_path": str(command_path),
                    "stdout_path": str(log_stem.with_suffix(".stdout.txt")),
                    "stderr_path": str(log_stem.with_suffix(".stderr.txt")),
                    "terminal_evidence": terminal_evidence,
                    "terminal_evidence_verification_error": terminal_evidence_error,
                    "predecessor_validation": validation,
                }
            )
            raise

        elapsed = time.monotonic() - started
        terminal_evidence = capture_terminal_command_evidence(log_stem)
        try:
            verify_terminal_command_evidence(terminal_evidence)
            terminal_evidence_error = None
        except DriverFailure as evidence_error:
            terminal_evidence_error = str(evidence_error)
        state["profiles"].append(
            {
                "profile": profile_name,
                "timeout_seconds": timeout,
                "elapsed_wall_seconds": elapsed,
                "outcome": "returned",
                "returncode": result.returncode,
                "command_record_path": str(log_stem.with_suffix(".command.json")),
                "stdout_path": str(log_stem.with_suffix(".stdout.txt")),
                "stderr_path": str(log_stem.with_suffix(".stderr.txt")),
                "terminal_evidence": terminal_evidence,
                "terminal_evidence_verification_error": terminal_evidence_error,
                "predecessor_validation": validation,
            }
        )
        if terminal_evidence_error is not None:
            raise runner.WaveFailure(
                f"Q2 consumer command terminal evidence is incomplete or changed: {terminal_evidence_error}"
            )
        return result

    runner.run_command = adaptive_run_command
    return state


def _write_calibration_sidecar(
    runner: Any,
    state: dict[str, Any],
    *,
    driver_path: Path,
    runner_path: Path,
    manifest_path: Path,
    driver_sha: str,
    runner_sha: str,
    manifest_sha: str,
    source_sha: str,
    source_tree: str,
    status: str,
    failure: str | None,
) -> Path | None:
    run_root = state.get("run_root")
    if run_root is None:
        return None
    if (
        sha256_file(driver_path) != driver_sha
        or sha256_file(runner_path) != runner_sha
        or sha256_file(manifest_path) != manifest_sha
    ):
        raise DriverFailure("timeout driver, reviewed runner, or manifest changed during the wave")
    run_root = Path(run_root)
    run_receipt_path = run_root / "run-receipt.json"
    if run_receipt_path.is_file():
        for row in state["profiles"]:
            if row.get("outcome") != "returned" or row.get("validation"):
                continue
            try:
                row["validation"] = validate_completed_profile(
                    runner,
                    json.loads(manifest_path.read_text(encoding="utf-8")),
                    run_root,
                    row["profile"],
                    expected_timeout_seconds=row["timeout_seconds"],
                    terminal_evidence=row.get("terminal_evidence"),
                )
            except (DriverFailure, KeyError, OSError, ValueError, json.JSONDecodeError) as error:
                row["validation_error"] = str(error)

    terminal_evidence_errors = []
    for row in state["profiles"]:
        evidence = row.get("terminal_evidence")
        if not isinstance(evidence, dict):
            verification = {"status": "unavailable", "reason": "capture_not_recorded"}
        else:
            try:
                verify_terminal_command_evidence(evidence)
                verification = {"status": "verified"}
            except DriverFailure as error:
                verification = {"status": "failed", "reason": str(error)}
        row["terminal_evidence_verification"] = verification
        if verification["status"] != "verified":
            terminal_evidence_errors.append(f"{row.get('profile', 'unknown')}: {verification.get('reason')}")

    sidecar = run_root / "timeout-calibration.json"
    if sidecar.exists():
        raise DriverFailure(f"timeout calibration sidecar already exists; preserving it: {sidecar}")
    effective_status = status
    effective_failure = failure
    if terminal_evidence_errors:
        effective_failure = "; ".join(
            value for value in (failure, "terminal command evidence verification failed: " + ", ".join(terminal_evidence_errors))
            if value
        )
        if status == "passed":
            effective_status = "failed"
    record = {
        "status": effective_status,
        "source_sha": source_sha,
        "source_tree": source_tree,
        "runner_path": str(runner_path),
        "runner_sha256": runner_sha,
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "driver_path": str(driver_path.resolve()),
        "driver_sha256": driver_sha,
        "timeout_policy": {
            "profile_order": list(EXPECTED_PROFILE_ORDER),
            "first_profile_unbounded": True,
            "multiplier": TIMEOUT_MULTIPLIER,
            "calibration_source": (
                "immediately preceding content-bound current-suite zero-error profile wall time"
            ),
        },
        "profiles": state["profiles"],
        "run_receipt_path": str(run_receipt_path),
        "failure": effective_failure,
    }
    runner.json_write(sidecar, record)
    if status == "passed" and terminal_evidence_errors:
        raise DriverFailure(effective_failure or "terminal command evidence verification failed")
    return sidecar


def main() -> int:
    driver_path = Path(__file__).resolve(strict=True)
    driver_sha = sha256_file(driver_path)
    runner, manifest, runner_path, manifest_path, runner_sha, manifest_sha = (
        _load_reviewed_runner(driver_path)
    )
    args = runner.parse_args()
    state = install_adaptive_run_command(runner, manifest)
    if sha256_file(driver_path) != driver_sha:
        raise DriverFailure("timeout driver changed after its execution hash was captured")
    status = "failed"
    failure = None
    try:
        completed_run = runner.run_wave(args)
        status = "passed"
    except BaseException as error:
        failure = f"{type(error).__name__}: {error}"
        raise
    finally:
        _write_calibration_sidecar(
            runner,
            state,
            driver_path=driver_path,
            runner_path=runner_path,
            manifest_path=manifest_path,
            driver_sha=driver_sha,
            runner_sha=runner_sha,
            manifest_sha=manifest_sha,
            source_sha=args.source_sha,
            source_tree=args.source_tree,
            status=status,
            failure=failure,
        )
    print(f"Q2 frozen installed wave passed: {completed_run}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Q2 timeout driver failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

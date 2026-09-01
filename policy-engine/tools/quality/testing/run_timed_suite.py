#!/usr/bin/env python3
"""Run an external verification suite while persisting one timing record."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import uuid
from contextlib import suppress
from pathlib import Path

from tools.lib.fs import atomic_write_text
from tools.lib.timing import (
    PytestWorkloadIdentity,
    ToolRunRecord,
    run_timed_operation,
    serialize_tool_run_record,
    verify_pytest_workload_identity,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
_PYTEST_RECEIPT_PLUGIN = "tools.quality.testing.pytest_workload_receipt"
_PYTEST_RECEIPT_SCHEMA_VERSION = "policyos.timing.pytest_execution_receipt.v1"
_RECEIPT_FAILURE_EXIT_CODE = 74


def _validated_repo_path(raw_path: str) -> Path:
    """Resolve a repository-relative working directory and reject path escapes."""

    candidate = (REPO_ROOT / raw_path).resolve()
    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--cwd must stay within the repository") from exc
    if not candidate.is_dir():
        raise argparse.ArgumentTypeError(f"--cwd is not a directory: {raw_path}")
    return candidate


def _validated_repo_output_path(raw_path: str) -> Path:
    """Resolve a repository-relative output path and reject path escapes."""

    candidate = (REPO_ROOT / raw_path).resolve()
    try:
        candidate.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "--receipt-output must stay within the repository"
        ) from exc
    if candidate == REPO_ROOT:
        raise argparse.ArgumentTypeError("--receipt-output must name a file")
    return candidate


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", required=True, help="Stable timing key for this command lane.")
    parser.add_argument("--cwd", default=".", help="Repository-relative working directory.")
    parser.add_argument(
        "--capture-pytest-workload",
        action="store_true",
        help="Capture the exact nodes collected by the timed pytest child.",
    )
    parser.add_argument(
        "--receipt-output",
        type=_validated_repo_output_path,
        help="Repository-relative JSONL output for the bound pytest execution receipt.",
    )
    parser.add_argument("argv", nargs=argparse.REMAINDER, help="Command to run after '--'.")
    args = parser.parse_args()
    if args.argv[:1] == ["--"]:
        args.argv = args.argv[1:]
    if not args.argv:
        parser.error("provide a command after '--'")
    if args.capture_pytest_workload != (args.receipt_output is not None):
        parser.error(
            "--capture-pytest-workload and --receipt-output must be supplied together"
        )
    args.cwd = _validated_repo_path(args.cwd)
    return args


def _split_lane(lane: str) -> tuple[str, str]:
    """Split an optional ``tool:mode`` lane while preserving bare-tool compatibility."""

    if ":" not in lane:
        return lane, "default"
    tool, mode = lane.rsplit(":", 1)
    if not tool or not mode:
        raise ValueError("--lane must be a non-empty tool or tool:mode pair")
    return tool, mode


def _pytest_test_paths(argv: list[str], cwd: Path) -> tuple[str, ...]:
    """Derive complete file selections from one explicit ``python -m pytest`` command."""

    pytest_markers = [
        index
        for index, argument in enumerate(argv[:-1])
        if argument == "-m" and argv[index + 1] == "pytest"
    ]
    if len(pytest_markers) != 1:
        raise ValueError("pytest workload capture requires one 'python -m pytest' command")
    pytest_index = pytest_markers[0] + 2
    selected: list[str] = []
    for argument in argv[pytest_index:]:
        selection_path, separator, _ = argument.partition("::")
        if not selection_path.endswith(".py"):
            continue
        if separator:
            raise ValueError("pytest workload capture requires complete path selections")
        candidate = (cwd / selection_path).resolve()
        try:
            relative = candidate.relative_to(REPO_ROOT).as_posix()
        except ValueError as exc:
            raise ValueError("pytest workload path escapes the repository") from exc
        if not candidate.is_file():
            raise ValueError(f"pytest workload path does not exist: {selection_path}")
        selected.append(relative)
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("pytest workload capture requires unique selected Python paths")
    return tuple(selected)


def _identity_from_payload(payload: object) -> PytestWorkloadIdentity:
    """Construct a typed identity; the public verifier enforces its complete contract."""

    expected_fields = {
        "schema_version",
        "predicate_provenance",
        "test_paths",
        "source_digests",
        "pytest_version",
        "config_path",
        "config_digest",
        "node_map_digest",
    }
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ValueError("pytest workload sidecar identity is not an object")
    source_digests = payload.get("source_digests")
    test_paths = payload.get("test_paths")
    if (
        not isinstance(source_digests, dict)
        or any(
            not isinstance(path, str) or not isinstance(digest, str)
            for path, digest in source_digests.items()
        )
        or not isinstance(test_paths, list)
        or any(not isinstance(path, str) for path in test_paths)
    ):
        raise ValueError("pytest workload sidecar identity has malformed sources")

    def _required_string(field: str) -> str:
        value = payload.get(field)
        if not isinstance(value, str):
            raise ValueError(f"pytest workload sidecar identity has malformed {field}")
        return value

    return PytestWorkloadIdentity(
        schema_version=_required_string("schema_version"),
        predicate_provenance=_required_string("predicate_provenance"),
        test_paths=tuple(test_paths),
        source_digests=tuple(source_digests.items()),
        pytest_version=_required_string("pytest_version"),
        config_path=_required_string("config_path"),
        config_digest=_required_string("config_digest"),
        node_map_digest=_required_string("node_map_digest"),
    )


def _bound_execution_receipt(
    *,
    attempt_id: str,
    timing_key: str,
    cwd: Path,
    argv: list[str],
    selected_paths: tuple[str, ...],
    sidecar_path: Path,
    records: list[ToolRunRecord],
) -> dict[str, object]:
    """Reconcile one same-child collection sidecar with its exact timing record."""

    if len(records) != 1:
        raise ValueError("timed suite did not expose exactly one timing record")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    if not isinstance(sidecar, dict) or set(sidecar) != {
        "attempt_id",
        "node_ids_by_path",
        "workload_identity",
    }:
        raise ValueError("pytest workload sidecar has the wrong shape")
    if sidecar["attempt_id"] != attempt_id:
        raise ValueError("pytest workload sidecar attempt does not match the runner")
    node_map_payload = sidecar["node_ids_by_path"]
    if not isinstance(node_map_payload, dict) or any(
        not isinstance(path, str)
        or not isinstance(node_ids, list)
        or any(not isinstance(node_id, str) for node_id in node_ids)
        for path, node_ids in node_map_payload.items()
    ):
        raise ValueError("pytest workload sidecar node map is malformed")
    node_ids_by_path = {
        path: tuple(node_ids) for path, node_ids in node_map_payload.items()
    }
    identity = _identity_from_payload(sidecar["workload_identity"])
    config_source = REPO_ROOT / identity.config_path
    verify_pytest_workload_identity(
        identity,
        command_test_paths=selected_paths,
        source_bytes={path: (REPO_ROOT / path).read_bytes() for path in selected_paths},
        node_ids_by_path=node_ids_by_path,
        pytest_version=identity.pytest_version,
        config_path=identity.config_path,
        config_bytes=config_source.read_bytes(),
    )
    raw_record = serialize_tool_run_record(records[0])
    workload_identity = {
        "schema_version": identity.schema_version,
        "predicate_provenance": identity.predicate_provenance,
        "test_paths": list(identity.test_paths),
        "source_digests": dict(identity.source_digests),
        "pytest_version": identity.pytest_version,
        "config_path": identity.config_path,
        "config_digest": identity.config_digest,
        "node_map_digest": identity.node_map_digest,
    }
    relative_cwd = cwd.relative_to(REPO_ROOT).as_posix() or "."
    return {
        "schema_version": _PYTEST_RECEIPT_SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "timing_key": timing_key,
        "cwd": relative_cwd,
        "argv": argv,
        "tool_run_record": raw_record,
        "tool_run_record_digest": (
            "sha256:" + hashlib.sha256(raw_record.encode("utf-8")).hexdigest()
        ),
        "workload_identity": workload_identity,
        "node_ids_by_path": {
            path: list(node_ids_by_path[path]) for path in identity.test_paths
        },
    }


def main() -> int:
    """Preserve child semantics and fail closed on an explicit receipt nonreceipt."""

    args = _parse_args()

    tool, mode = _split_lane(args.lane)
    timing_key = f"{tool}:{mode}"
    records: list[ToolRunRecord] = []
    selected_paths: tuple[str, ...] = ()
    child_environment: dict[str, str] | None = None
    scratch: tempfile.TemporaryDirectory[str] | None = None
    sidecar_path: Path | None = None
    attempt_id = uuid.uuid4().hex
    if args.capture_pytest_workload:
        selected_paths = _pytest_test_paths(args.argv, args.cwd)
        build_root = REPO_ROOT / "_build"
        build_root.mkdir(parents=True, exist_ok=True)
        scratch = tempfile.TemporaryDirectory(prefix="timed-pytest-", dir=build_root)
        sidecar_path = Path(scratch.name) / "collection.json"
        child_environment = os.environ.copy()
        existing_plugins = child_environment.get("PYTEST_PLUGINS", "").strip()
        child_environment["PYTEST_PLUGINS"] = ",".join(
            value for value in (existing_plugins, _PYTEST_RECEIPT_PLUGIN) if value
        )
        existing_pythonpath = child_environment.get("PYTHONPATH", "").strip()
        child_environment["PYTHONPATH"] = os.pathsep.join(
            value for value in (str(REPO_ROOT), existing_pythonpath) if value
        )
        child_environment["POLISYOS_PYTEST_RECEIPT_ATTEMPT_ID"] = attempt_id
        child_environment["POLISYOS_PYTEST_RECEIPT_REPO_ROOT"] = str(REPO_ROOT)
        child_environment["POLISYOS_PYTEST_RECEIPT_SIDECAR"] = str(sidecar_path)
        child_environment["POLISYOS_PYTEST_RECEIPT_TEST_PATHS"] = json.dumps(
            selected_paths,
            separators=(",", ":"),
        )
        args.receipt_output.unlink(missing_ok=True)

    def _operation() -> int:
        result = subprocess.run(
            args.argv,
            shell=False,
            cwd=args.cwd,
            env=child_environment,
            check=False,
        )
        return result.returncode

    exit_code = run_timed_operation(
        _operation,
        tool=tool,
        category="external",
        mode=mode,
        record_sink=records.append,
    )
    receipt_failed = False
    if args.capture_pytest_workload:
        try:
            assert sidecar_path is not None
            assert isinstance(args.receipt_output, Path)
            receipt = _bound_execution_receipt(
                attempt_id=attempt_id,
                timing_key=timing_key,
                cwd=args.cwd,
                argv=args.argv,
                selected_paths=selected_paths,
                sidecar_path=sidecar_path,
                records=records,
            )
            atomic_write_text(
                args.receipt_output,
                json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
            )
        except (OSError, TypeError, ValueError) as exc:
            receipt_failed = True
            print(
                f"warning: could not persist pytest execution receipt: {exc}",
                file=sys.stderr,
            )
    if scratch is not None:
        scratch.cleanup()
    if exit_code < 0:
        signal_number = -exit_code
        with suppress(OSError):
            signal.signal(signal_number, signal.SIG_DFL)
        os.kill(os.getpid(), signal_number)
        raise RuntimeError("process survived relayed child termination signal")
    if receipt_failed:
        return _RECEIPT_FAILURE_EXIT_CODE
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

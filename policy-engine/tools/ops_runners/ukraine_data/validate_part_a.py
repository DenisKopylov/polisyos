#!/usr/bin/env python3
"""Run the Ukraine repository-only Part A gate from the ops layer."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.ukraine.manifests import (
    PartAGateCollectionContext,
    PartAGateExecutionReceipt,
    PartAGateManifest,
    PytestCasePhaseReport,
    utc_now_iso,
)
from polisyos.data_forge.domains.ukraine.orchestrator import (
    UkraineDataOrchestrator,
    load_pipeline_config,
)
from polisyos.data_forge.domains.ukraine.server import (
    PartAGateRunner,
    is_repository_checkout,
)
from polisyos.data_forge.domains.ukraine.server import (
    run_part_a_gate as _run_gate_with_runner,
)
from tools.lib.timing import PytestWorkloadIdentity, verify_pytest_workload_identity
from tools.ops_runners.ukraine_data.server_bootstrap import resolve_workspace_root

_C7_TEST_PATH = "tests/integration/test_c7_synthetic_full_pipeline.py"
_WORKLOAD_IDENTITY_SCHEMA = "policyos.timing.pytest_workload.v1"
_WORKLOAD_RECEIPT_SCHEMA = "policyos.ukraine.c7.workload_receipt.v2"
_PHASE_RECEIPT_SCHEMA = "policyos.timing.pytest_case_phases.v2"
_ATTEMPT_ID_ENV = "POLISYOS_PYTEST_RECEIPT_ATTEMPT_ID"
_WORKLOAD_SIDECAR_ENV = "POLISYOS_PYTEST_RECEIPT_SIDECAR"
_WORKLOAD_OUTPUT_ROOT_ENV = "POLISYOS_PYTEST_RECEIPT_OUTPUT_ROOT"
_PHASES_SIDECAR_ENV = "POLISYOS_PYTEST_RECEIPT_PHASES_SIDECAR"
_REPO_ROOT_ENV = "POLISYOS_PYTEST_RECEIPT_REPO_ROOT"
_TEST_PATHS_ENV = "POLISYOS_PYTEST_RECEIPT_TEST_PATHS"
_CODE_ROOT_ENV = "POLISYOS_PYTEST_RECEIPT_CODE_ROOT"

if TYPE_CHECKING:
    from polisyos.data_forge.domains.ukraine.models import PipelineConfig, ServerConfig


def _sha256(payload: bytes) -> str:
    """Return the repository's prefixed digest form for a receipt payload."""

    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"pytest receipt field {key!r} is missing or malformed")
    return value


def _read_execution_receipt(
    *,
    attempt_id: str,
    workspace_root: Path,
    workload_path: Path,
    phases_path: Path,
    exit_code: int,
) -> PartAGateExecutionReceipt:
    """Bind full collected nodes to every same-child setup/call/teardown report."""

    if workload_path.is_symlink() or phases_path.is_symlink():
        raise ValueError("pytest receipt sidecars must be regular, non-symlink files")
    workload_bytes = workload_path.read_bytes()
    phases_bytes = phases_path.read_bytes()
    workload = json.loads(workload_bytes)
    phases = json.loads(phases_bytes)
    if not isinstance(workload, dict) or set(workload) != {
        "schema_version",
        "attempt_id",
        "node_ids_by_path",
        "workload_identity",
        "collection_context",
    }:
        raise ValueError("pytest workload receipt has an unexpected shape")
    if workload.get("schema_version") != _WORKLOAD_RECEIPT_SCHEMA:
        raise ValueError("pytest workload receipt schema is unsupported")
    if not isinstance(phases, dict) or set(phases) != {
        "schema_version",
        "attempt_id",
        "workload_receipt_sha256",
        "pytest_exit_status",
        "phase_reports",
    }:
        raise ValueError("pytest phase receipt has an unexpected shape")
    if workload.get("attempt_id") != attempt_id or phases.get("attempt_id") != attempt_id:
        raise ValueError("pytest receipt attempt identity does not match this run")
    if phases.get("schema_version") != _PHASE_RECEIPT_SCHEMA:
        raise ValueError("pytest phase receipt schema is unsupported")
    if phases.get("workload_receipt_sha256") != _sha256(workload_bytes):
        raise ValueError("pytest phase receipt does not bind the workload receipt")
    if isinstance(phases.get("pytest_exit_status"), bool) or not isinstance(
        phases.get("pytest_exit_status"), int
    ):
        raise ValueError("pytest phase receipt exit status is malformed")
    if phases["pytest_exit_status"] != exit_code:
        raise ValueError("pytest phase receipt and subprocess exit status differ")

    identity_payload = workload.get("workload_identity")
    identity_fields = {
        "schema_version",
        "predicate_provenance",
        "test_paths",
        "source_digests",
        "pytest_version",
        "config_path",
        "config_digest",
        "node_map_digest",
    }
    if not isinstance(identity_payload, dict) or set(identity_payload) != identity_fields:
        raise ValueError("pytest workload identity has an unexpected shape")
    if identity_payload.get("schema_version") != _WORKLOAD_IDENTITY_SCHEMA:
        raise ValueError("pytest workload identity schema is unsupported")
    if identity_payload.get("predicate_provenance") != "recomputed":
        raise ValueError("pytest workload identity is not recomputed")
    test_paths = identity_payload.get("test_paths")
    source_digests = identity_payload.get("source_digests")
    node_map = workload.get("node_ids_by_path")
    if (
        not isinstance(test_paths, list)
        or test_paths != [_C7_TEST_PATH]
        or not isinstance(source_digests, dict)
        or set(source_digests) != {_C7_TEST_PATH}
        or not isinstance(node_map, dict)
        or set(node_map) != {_C7_TEST_PATH}
        or not isinstance(node_map[_C7_TEST_PATH], list)
        or any(not isinstance(node_id, str) for node_id in node_map[_C7_TEST_PATH])
    ):
        raise ValueError("pytest workload receipt does not describe the complete C7 module")
    node_ids = node_map[_C7_TEST_PATH]
    if not node_ids or len(node_ids) != len(set(node_ids)):
        raise ValueError("pytest workload receipt has an empty or duplicate C7 node set")
    if any(not node_id.startswith(f"{_C7_TEST_PATH}::") for node_id in node_ids):
        raise ValueError("pytest workload receipt contains a node outside the C7 module")

    source_digest_items: list[tuple[str, str]] = []
    for path, digest in source_digests.items():
        if not isinstance(path, str) or not isinstance(digest, str):
            raise ValueError("pytest workload source digests are malformed")
        source_digest_items.append((path, digest))
    identity = PytestWorkloadIdentity(
        schema_version=_required_string(identity_payload, "schema_version"),
        predicate_provenance=_required_string(identity_payload, "predicate_provenance"),
        test_paths=tuple(test_paths),
        source_digests=tuple(source_digest_items),
        pytest_version=_required_string(identity_payload, "pytest_version"),
        config_path=_required_string(identity_payload, "config_path"),
        config_digest=_required_string(identity_payload, "config_digest"),
        node_map_digest=_required_string(identity_payload, "node_map_digest"),
    )
    config_path = (workspace_root / identity.config_path).resolve(strict=True)
    config_path.relative_to(workspace_root.resolve())
    verify_pytest_workload_identity(
        identity,
        command_test_paths=(_C7_TEST_PATH,),
        source_bytes={_C7_TEST_PATH: (workspace_root / _C7_TEST_PATH).read_bytes()},
        node_ids_by_path=node_map,
        pytest_version=identity.pytest_version,
        config_path=identity.config_path,
        config_bytes=config_path.read_bytes(),
    )

    collection_context_payload = workload.get("collection_context")
    if not isinstance(collection_context_payload, dict):
        raise ValueError("pytest collection context is missing")
    collection_context = PartAGateCollectionContext.model_validate(collection_context_payload)
    if _C7_TEST_PATH not in collection_context.pytest_arguments:
        raise ValueError("pytest collection context omits the selected C7 test path")
    if "tools.quality.testing.pytest_workload_receipt" not in collection_context.pytest_arguments:
        raise ValueError("pytest collection context omits the receipt plugin selection")
    code_root = Path(__file__).resolve().parents[3]
    plugin_sources = collection_context.repo_plugin_source_digests
    expected_receipt_source = (
        Path(__file__).resolve().parents[3] / "tools/quality/testing/pytest_workload_receipt.py"
    )
    if expected_receipt_source.resolve().is_relative_to(workspace_root.resolve()):
        expected_receipt_id = (
            "workspace:"
            + expected_receipt_source.resolve().relative_to(workspace_root.resolve()).as_posix()
        )
    else:
        expected_receipt_id = (
            "code:" + expected_receipt_source.resolve().relative_to(code_root).as_posix()
        )
    if expected_receipt_id not in plugin_sources:
        raise ValueError("pytest collection context omits the active receipt plugin source")
    expected_conftests: set[str] = set()
    current = (workspace_root / _C7_TEST_PATH).resolve().parent
    workspace_resolved = workspace_root.resolve()
    while True:
        candidate = current / "conftest.py"
        if candidate.is_file():
            expected_conftests.add(
                "workspace:" + candidate.resolve().relative_to(workspace_resolved).as_posix()
            )
        if current == workspace_resolved:
            break
        if workspace_resolved not in current.parents:
            break
        current = current.parent
    if not expected_conftests.issubset(plugin_sources):
        raise ValueError("pytest collection context omits a C7 ancestor conftest")
    for source_id, expected_digest in plugin_sources.items():
        prefix, relative_path = source_id.split(":", 1)
        source_root = workspace_resolved if prefix == "workspace" else code_root
        source_path = (source_root / relative_path).resolve(strict=True)
        source_path.relative_to(source_root.resolve())
        if _sha256(source_path.read_bytes()) != expected_digest:
            raise ValueError("pytest collection plugin/conftest source digest changed")

    phase_reports_payload = phases.get("phase_reports")
    if not isinstance(phase_reports_payload, list):
        raise ValueError("pytest phase reports are missing")
    phase_reports: list[PytestCasePhaseReport] = []
    for item in phase_reports_payload:
        if not isinstance(item, dict) or set(item) != {"node_id", "when", "outcome", "reason"}:
            raise ValueError("pytest phase report is malformed")
        phase_reports.append(PytestCasePhaseReport.model_validate(item))
    return PartAGateExecutionReceipt(
        attempt_id=attempt_id,
        test_path=_C7_TEST_PATH,
        source_sha256=dict(identity.source_digests)[_C7_TEST_PATH],
        pytest_version=identity.pytest_version,
        config_path=identity.config_path,
        config_sha256=identity.config_digest,
        collection_context=collection_context,
        node_ids=node_ids,
        phase_reports=phase_reports,
        pytest_exit_status=exit_code,
        workload_receipt_sha256=_sha256(workload_bytes),
        phases_receipt_sha256=_sha256(phases_bytes),
    )


def _classify_execution_receipt(
    execution_receipt: PartAGateExecutionReceipt | None,
) -> str:
    """Map typed pytest lifecycle evidence to the gate's passed/skipped/failed lattice."""

    if execution_receipt is not None and execution_receipt.complete_pass:
        return "passed"
    if execution_receipt is not None and execution_receipt.complete_skip:
        return "skipped"
    return "failed"


def _run_repository_gate(config: ServerConfig, workspace_root: Path | None) -> PartAGateManifest:
    """Execute C7 against the supplied checkout after domain admission."""

    if workspace_root is None or not is_repository_checkout(workspace_root):
        # The outer domain adapter normally performs this check.  Keep the
        # callback fail-closed when it is called directly by an ops consumer.
        reason = (
            "repository checkout is unavailable for the installed package"
            if workspace_root is None
            else f"repository checkout is unavailable at {workspace_root}"
        )
        return PartAGateManifest(
            status="unavailable",
            command=[],
            server_only=True,
            passed=False,
            skipped=False,
            notes=[reason],
        )

    attempt_id = uuid.uuid4().hex
    execution_receipt: PartAGateExecutionReceipt | None = None
    verification_error: str | None = None
    command = [
        config.uv_bin,
        "run",
        "pytest",
        "-q",
        "-ra",
        "--import-mode=importlib",
        "--strict-markers",
        "-o",
        "addopts=",
        "-p",
        "tools.quality.testing.pytest_workload_receipt",
        _C7_TEST_PATH,
    ]
    receipt_root = Path(tempfile.mkdtemp(prefix="polisyos-ukraine-c7-"))
    workload_path = receipt_root / "workload.json"
    phases_path = receipt_root / "phases.json"
    env = dict(os.environ)
    raw_pytest_addopts = env.pop("PYTEST_ADDOPTS", "")
    env.pop("PYTEST_PLUGINS", None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env[_CODE_ROOT_ENV] = str(Path(__file__).resolve().parents[3])
    env.update(
        {
            "POLISYOS_RUN_INTEGRATION": "1",
            _ATTEMPT_ID_ENV: attempt_id,
            _WORKLOAD_SIDECAR_ENV: str(workload_path),
            _WORKLOAD_OUTPUT_ROOT_ENV: str(receipt_root),
            _PHASES_SIDECAR_ENV: str(phases_path),
            _REPO_ROOT_ENV: str(workspace_root),
            _TEST_PATHS_ENV: json.dumps([_C7_TEST_PATH]),
        }
    )
    if raw_pytest_addopts.strip():
        try:
            approved_addopts = shlex.split(raw_pytest_addopts)
        except ValueError as exc:
            approved_addopts = []
            verification_error = f"C7 rejected malformed PYTEST_ADDOPTS: {exc}"
        else:
            if len(approved_addopts) != 1 or not approved_addopts[0].startswith("--junitxml="):
                verification_error = "C7 rejected PYTEST_ADDOPTS outside the JUnit-only profile"
                approved_addopts = []
        if approved_addopts:
            env["PYTEST_ADDOPTS"] = " ".join(shlex.quote(value) for value in approved_addopts)
    try:
        if verification_error is not None:
            return PartAGateManifest(
                status="failed",
                command=command,
                server_only=True,
                passed=False,
                skipped=False,
                notes=[verification_error],
            )
        completed = subprocess.run(
            command,
            cwd=workspace_root,
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        try:
            execution_receipt = _read_execution_receipt(
                attempt_id=attempt_id,
                workspace_root=workspace_root,
                workload_path=workload_path,
                phases_path=phases_path,
                exit_code=completed.returncode,
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            verification_error = f"C7 execution receipt rejected: {exc}"
    except OSError as exc:
        return PartAGateManifest(
            status="failed",
            command=command,
            server_only=True,
            passed=False,
            skipped=False,
            notes=[f"C7 subprocess could not start: {exc}"],
        )
    finally:
        for path in (workload_path, phases_path):
            path.unlink(missing_ok=True)
        receipt_root.rmdir()

    stdout = completed.stdout or ""
    status = _classify_execution_receipt(execution_receipt)
    passed = status == "passed"
    skipped = status == "skipped"
    notes: list[str] = []
    if stdout.strip():
        notes.append(stdout.strip()[-5000:])
    stderr = (completed.stderr or "").strip()
    if stderr:
        notes.append(stderr[-2000:])
    if verification_error is not None:
        notes.append(verification_error)
    if execution_receipt is not None:
        for phase in execution_receipt.phase_reports:
            if phase.outcome in {"failed", "skipped", "xpassed"}:
                notes.append(f"C7 {phase.node_id} {phase.when} {phase.outcome}: {phase.reason}")
    if not passed and execution_receipt is not None and not skipped:
        notes.append("C7 execution did not complete every collected node phase successfully")
    return PartAGateManifest(
        status=status,
        command=command,
        server_only=True,
        passed=passed,
        skipped=skipped,
        execution_receipt=execution_receipt,
        created_at=utc_now_iso(),
        notes=notes,
    )


def run_part_a_gate(config: ServerConfig, workspace_root: Path | None) -> PartAGateManifest:
    """Run the repository gate through the ops-owned subprocess callback."""

    runner: PartAGateRunner = _run_repository_gate
    return _run_gate_with_runner(config, workspace_root, runner=runner)


def build_orchestrator(
    config: PipelineConfig,
    workspace_root: Path | None,
) -> UkraineDataOrchestrator:
    """Compose the domain orchestrator with this ops-owned gate runner."""

    return UkraineDataOrchestrator(
        config,
        workspace_root=resolve_workspace_root(workspace_root),
        part_a_gate_runner=run_part_a_gate,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--root", type=Path, default=None, help="Artifact/build root.")
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="Repository checkout containing the C7 integration test.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute the gate and persist its typed manifest for the operator."""

    args = _build_parser().parse_args(argv)
    config = load_pipeline_config(args.config, root=args.root)
    summary = build_orchestrator(config, args.workspace_root).validate_part_a()
    print(
        json.dumps(
            summary.manifest.model_dump(mode="json"),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if summary.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

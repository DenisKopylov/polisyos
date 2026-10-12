#!/usr/bin/env python3
"""Assemble a source-qualified, occurrence-first author report from retained inputs.

This is a reporting adapter. It does not execute commands, adjudicate findings,
create registered v4 evaluations, or assign formal G closures.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REPORT_SCHEMA = "policyos.e02.author_proposal_report.v1"
DRAFT_SCHEMA = "policyos.e02.occurrence_evaluations_compact_preparation.v1"
AUTHOR_HANDOFF_PACKET_SCHEMA = "policyos.e02.local_slice_handoff.v2"
AUTHOR_CAPTURE_SCHEMA = "policyos.e02.local_slice_author_capture.v1"
CAPTURE_STATUSES = {"PASS", "FAIL", "ERROR", "SKIP", "UNRUN"}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")


class ReportError(ValueError):
    """Raised when an input cannot safely contribute to the author report."""


def sha256_bytes(value: bytes) -> str:
    """Return the SHA-256 digest of exact input bytes."""
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a regular file without following a symlink."""
    if path.is_symlink() or not path.is_file():
        raise ReportError(f"expected a regular non-symlink file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_root_from_script() -> Path:
    """Locate the checkout containing this report tool."""
    for parent in Path(__file__).resolve().parents:
        if (parent / ".git").exists() and (parent / "policy-engine").is_dir():
            return parent
    raise ReportError("cannot locate repository root from report tool path")


def repo_relative(path: Path, root: Path) -> str:
    """Return a stable repository-relative path for a contained file."""
    try:
        return path.resolve(strict=True).relative_to(root.resolve(strict=True)).as_posix()
    except (OSError, ValueError) as exc:
        raise ReportError(f"input is not a readable file inside the checkout: {path}") from exc


def display_path(path: Path, root: Path) -> str:
    """Show a repository-relative path when possible, otherwise an explicit absolute path."""
    try:
        return repo_relative(path, root)
    except ReportError:
        return path.resolve(strict=True).as_posix()


def path_ref(path: Path, root: Path, *, allow_external: bool = False) -> dict[str, str]:
    """Describe a file by path and exact bytes, without embedding its contents."""
    try:
        relative = repo_relative(path, root)
    except ReportError:
        if not allow_external:
            raise
        relative = path.resolve(strict=True).as_posix()
    return {"path": relative, "sha256": sha256_file(path)}


def read_json(path: Path, *, maximum_bytes: int = 64 * 1024 * 1024) -> tuple[Any, bytes]:
    """Read bounded UTF-8 JSON from a regular file."""
    if path.is_symlink() or not path.is_file():
        raise ReportError(f"expected a regular non-symlink JSON file: {path}")
    raw = path.read_bytes()
    if len(raw) > maximum_bytes:
        raise ReportError(f"JSON input exceeds {maximum_bytes} bytes: {path}")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReportError(f"invalid UTF-8 JSON input: {path}") from exc
    return value, raw


def resolve_pointer(document: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON pointer."""
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ReportError(f"invalid JSON pointer: {pointer}")
    value = document
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(part)] if isinstance(value, list) else value[part]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ReportError(f"unresolvable JSON pointer: {pointer}") from exc
    return value


def validate_sha(value: Any, label: str) -> str:
    """Require a lowercase SHA-256 value."""
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise ReportError(f"{label} must be a lowercase SHA-256 digest")
    return value


def validate_git_sha(value: Any, label: str) -> str:
    """Require a lowercase full Git object ID."""
    if not isinstance(value, str) or GIT_SHA_RE.fullmatch(value) is None:
        raise ReportError(f"{label} must be a full lowercase Git object ID")
    return value


def exact_occurrence_maps(
    *, coverage: dict[str, Any], tasks: dict[str, Any], ledger: dict[str, Any], draft: dict[str, Any],
    coverage_path: Path, tasks_path: Path, root: Path,
) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Validate and index the complete original finding/occurrence/task denominator."""
    if draft.get("schema") != DRAFT_SCHEMA or draft.get("importable") is not False:
        raise ReportError("preparation draft schema/importability differs from its pinned role")
    if draft.get("formal_closure_ids") != [] or ledger.get("formal_closure_ids") != []:
        raise ReportError("preparation or ledger contains a nonempty formal closure list")
    if not isinstance(coverage.get("findings"), list):
        raise ReportError("coverage findings[] is missing")
    if not isinstance(tasks.get("tasks"), dict) or not isinstance(ledger.get("findings"), list):
        raise ReportError("TASKS or proposal ledger shape is invalid")
    if not isinstance(draft.get("occurrences"), list):
        raise ReportError("draft occurrences[] is missing")

    coverage_rel = repo_relative(coverage_path, root)
    coverage_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for finding_index, finding in enumerate(coverage["findings"]):
        finding_id = finding.get("id")
        if not isinstance(finding_id, str) or not isinstance(finding.get("criterion_refs"), list):
            raise ReportError(f"invalid coverage finding row {finding_index}")
        for criterion_index, criterion in enumerate(finding["criterion_refs"]):
            digest = validate_sha(criterion.get("sha256"), "coverage criterion sha256")
            pointer = f"{coverage_rel}#/findings/{finding_index}/criterion_refs/{criterion_index}"
            key = (finding_id, pointer, digest)
            if key in coverage_rows:
                raise ReportError(f"duplicate canonical coverage key: {key}")
            coverage_rows[key] = {"finding": finding, "criterion": criterion}

    ledger_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    ledger_findings: dict[str, dict[str, Any]] = {}
    for finding in ledger["findings"]:
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or finding_id in ledger_findings:
            raise ReportError("ledger finding IDs must be unique strings")
        ledger_findings[finding_id] = finding
        for occurrence in finding.get("occurrences", []):
            original = occurrence.get("original", {})
            pointer = original.get("occurrence_pointer")
            digest = validate_sha(original.get("sha256"), "ledger occurrence sha256")
            key = (finding_id, pointer, digest)
            if key in ledger_rows:
                raise ReportError(f"duplicate ledger occurrence key: {key}")
            ledger_rows[key] = occurrence

    draft_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
    for occurrence in draft["occurrences"]:
        key_data = occurrence.get("key", {})
        key = (
            key_data.get("finding_id"),
            key_data.get("coverage_pointer"),
            validate_sha(key_data.get("criterion_sha256"), "draft criterion sha256"),
        )
        if key in draft_rows:
            raise ReportError(f"duplicate draft occurrence key: {key}")
        draft_rows[key] = occurrence

    expected = Counter(coverage_rows)
    if expected != Counter(ledger_rows) or expected != Counter(draft_rows):
        raise ReportError(
            "coverage/ledger/draft exact occurrence multisets differ "
            f"(coverage={len(coverage_rows)}, ledger={len(ledger_rows)}, draft={len(draft_rows)})"
        )

    route_rows: dict[str, Any] = tasks["tasks"]
    tasks_rel = repo_relative(tasks_path, root)
    for key, row in draft_rows.items():
        finding_id = key[0]
        for route in row.get("task_routes", []):
            task_id = route.get("task_id")
            assignment_pointer = route.get("assignment_pointer")
            if task_id not in route_rows or not isinstance(assignment_pointer, str):
                raise ReportError(f"draft route is not a TASKS assignment for {finding_id}")
            expected_prefix = f"{tasks_rel}#/tasks/{task_id}/finding_ids/"
            if not assignment_pointer.startswith(expected_prefix):
                raise ReportError(f"draft route pointer is not the exact TASKS source: {finding_id}")
            task_id_from_pointer = assignment_pointer.split("#/tasks/", 1)[-1].split("/", 1)[0]
            if task_id_from_pointer != task_id:
                raise ReportError(f"draft route pointer names another task for {finding_id}")
            assignment = resolve_pointer(tasks, "/tasks/" + task_id + "/finding_ids/" + assignment_pointer.rsplit("/", 1)[-1])
            if assignment != finding_id or finding_id not in route_rows[task_id].get("finding_ids", []):
                raise ReportError(f"draft route does not assign {finding_id} to {task_id}")

    if len(coverage_rows) != 291 or len({key[0] for key in coverage_rows}) != 282:
        raise ReportError("canonical denominator is not 291 occurrences / 282 IDs")
    if len(coverage.get("bundles", [])) != 127 or len(tasks["tasks"]) != 26:
        raise ReportError("canonical bundle/task denominator differs from 127 / 26")
    task_route_assignments = sum(len(row.get("finding_ids", [])) for row in route_rows.values())
    if task_route_assignments != 319:
        raise ReportError(f"TASKS route assignment count differs from 319: {task_route_assignments}")
    return draft_rows, ledger_findings, route_rows


def route_names(value: Any) -> set[str]:
    """Split explicit task-plan route labels; never infer from test names or IDs."""
    if not isinstance(value, str):
        return set()
    parts = [value]
    for delimiter in (" / ", " and "):
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(part.split(delimiter))
        parts = next_parts
    return {part.strip() for part in parts if part.strip() and part.strip() not in {
        "No single command; G criterion ledger only",
        "Outside this Mac numerical queue",
    }}


def plan_task_routes(plan: Any, task_rows: dict[str, Any]) -> dict[str, list[str]]:
    """Map exact planned command labels to authoritative TASKS task IDs."""
    register = plan.get("task_register", {}) if isinstance(plan, dict) else {}
    task_map = register.get("task_map", []) if isinstance(register, dict) else []
    routes: dict[str, list[str]] = defaultdict(list)
    if not isinstance(task_map, list):
        return routes
    for item in task_map:
        if not isinstance(item, dict):
            continue
        task_id = item.get("key")
        if task_id not in task_rows:
            continue
        for route in route_names(item.get("queue_route")):
            routes[route].append(task_id)
    return routes


def pytest_status(junit_path: Path | None) -> str | None:
    """Read exact JUnit outcome counts if a captured JUnit file is available."""
    if junit_path is None or junit_path.is_symlink() or not junit_path.is_file():
        return None
    try:
        root = ET.parse(junit_path).getroot()
    except (ET.ParseError, OSError):
        return None
    test_cases = list(root.iter("testcase"))
    if not test_cases:
        # Aggregate counts can describe collection or a summarized report without
        # any test case behavior. They are not a PASS/FAIL witness here.
        return None
    if any(case.find("error") is not None for case in test_cases):
        return "ERROR"
    if any(case.find("failure") is not None for case in test_cases):
        return "FAIL"
    if any(case.find("skipped") is not None for case in test_cases):
        return "SKIP"
    return "PASS"


def classify_metadata(
    metadata: dict[str, Any], command_dir: Path,
) -> tuple[str | None, list[dict[str, str]], bool, str]:
    """Reconcile actual command context, wrapper status, JUnit, timeout, and exit evidence."""
    outputs: list[dict[str, str]] = []
    raw_status = metadata.get("status")
    exit_code = metadata.get("exit_code")
    timed_out = metadata.get("timed_out")
    actual_argv = metadata.get("actual_argv", metadata.get("argv"))
    cwd = metadata.get("cwd")
    if (
        not isinstance(raw_status, str)
        or not raw_status
        or not isinstance(actual_argv, list)
        or not actual_argv
        or not all(isinstance(part, str) and part for part in actual_argv)
        or not isinstance(cwd, str)
        or not cwd
        or not Path(cwd).is_absolute()
        or not isinstance(exit_code, int)
        or isinstance(exit_code, bool)
        or (timed_out is not True and timed_out is not False)
        or "launch_error" not in metadata
        or not isinstance(metadata.get("launch_error"), (str, type(None)))
        or metadata.get("launch_error") is not None
    ):
        return None, outputs, False, "command status/context/exit/timeout/launch-error evidence is malformed or missing"

    for key, filename in (("stdout_sha256", "stdout.bin"), ("stderr_sha256", "stderr.bin")):
        expected = metadata.get(key)
        output_path = command_dir / filename
        if not isinstance(expected, str) or SHA256_RE.fullmatch(expected) is None:
            return None, outputs, False, f"{key} is missing or malformed"
        if output_path.is_symlink() or not output_path.is_file() or sha256_file(output_path) != expected:
            return None, outputs, False, f"{filename} is unavailable or differs from its recorded digest"
        outputs.append({"role": filename.removesuffix(".bin"), "path": output_path.as_posix(), "sha256": expected})

    if timed_out is True:
        return "ERROR", outputs, True, "explicit timed_out=true; JUnit pass cannot override timeout"

    junit_expected = metadata.get("junit_sha256")
    junit_path = command_dir / "junit.xml"
    junit_result: str | None = None
    if junit_expected is not None:
        if not isinstance(junit_expected, str) or SHA256_RE.fullmatch(junit_expected) is None:
            return None, outputs, False, "junit_sha256 is malformed"
        if junit_path.is_symlink() or not junit_path.is_file() or sha256_file(junit_path) != junit_expected:
            return None, outputs, False, "JUnit output is unavailable or differs from its recorded digest"
        outputs.append({"role": "junit", "path": junit_path.as_posix(), "sha256": junit_expected})
        junit_result = pytest_status(junit_path)
        if junit_result is None:
            return None, outputs, False, "JUnit output has no actual classifiable testcase behavior"
    elif junit_path.exists():
        return None, outputs, False, "JUnit output exists without a recorded digest"
    else:
        return None, outputs, False, "no JUnit testcase behavior is available to establish a command outcome"

    if junit_result == "ERROR":
        if exit_code == 1 and raw_status == "ERROR" and metadata.get("pytest_result_status") == "ERROR":
            return "ERROR", outputs, True, "JUnit testcase records an error and process/wrapper agree"
        return None, outputs, False, "JUnit error conflicts with command status or process exit"
    if junit_result == "FAIL":
        if exit_code == 1 and raw_status == "FAIL" and metadata.get("pytest_result_status") == "FAIL":
            return "FAIL", outputs, True, "JUnit testcase records failures and process/wrapper agree"
        return None, outputs, False, "JUnit failure conflicts with command status or exit code"
    if junit_result == "SKIP":
        if (
            exit_code == 0
            and raw_status == "UNCLASSIFIED_SKIP"
            and metadata.get("pytest_result_status") == "UNCLASSIFIED_SKIP"
        ):
            return "SKIP", outputs, True, "JUnit testcase records only skips and process/wrapper agree"
        return None, outputs, False, "JUnit skip result conflicts with command status or exit code"
    if junit_result == "PASS":
        origin = metadata.get("module_origin_assertion")
        output_inventory = metadata.get("command_output_inventory_before_metadata")
        if (
            exit_code == 0
            and raw_status == "PASS"
            and metadata.get("pytest_result_status") == "PASS"
            and isinstance(origin, dict)
            and origin.get("passed") is True
            and isinstance(output_inventory, dict)
            and output_inventory.get("complete") is True
        ):
            return "PASS", outputs, True, "JUnit testcases, process, origin assertion, and output inventory agree"
        return None, outputs, False, "JUnit pass conflicts with wrapper status or process exit"
    return None, outputs, False, "wrapper status and process result do not establish an outcome"


def capture_run_paths(path: Path, root: Path) -> list[tuple[Path, Path | None]]:
    """Find supplied run-manifest/completion pairs without scanning outside the capture root."""
    if path.is_symlink():
        raise ReportError(f"capture input cannot be a symlink: {path}")
    if path.is_file():
        if path.name == "run-manifest.json":
            return [(path, path.parent / "completion.json" if (path.parent / "completion.json").is_file() else None)]
        if path.name == "completion.json":
            manifest = path.parent / "run-manifest.json"
            return [(manifest, path)] if manifest.is_file() else []
        value, _ = read_json(path)
        if isinstance(value, dict) and isinstance(value.get("commands"), list):
            return [(path, None)]
        raise ReportError(f"capture file must be run-manifest, completion, or command receipt: {path}")
    if not path.is_dir():
        raise ReportError(f"capture path does not exist: {path}")
    manifests = sorted(path.rglob("run-manifest.json"))
    if not manifests:
        raise ReportError(f"capture directory contains no run-manifest.json: {path}")
    if len(manifests) > 256:
        raise ReportError(f"capture input contains too many run manifests: {path}")
    return [
        (manifest, manifest.parent / "completion.json" if (manifest.parent / "completion.json").is_file() else None)
        for manifest in manifests
    ]


def read_capture_input(path: Path, root: Path, task_rows: dict[str, Any]) -> list[dict[str, Any]]:
    """Read a supplied primary/supplement capture and index exact command attempts."""
    runs: list[dict[str, Any]] = []
    for manifest_path, completion_path in capture_run_paths(path, root):
        value, raw = read_json(manifest_path)
        if not isinstance(value, dict):
            raise ReportError(f"capture manifest must be a JSON object: {manifest_path}")
        if manifest_path.name != "run-manifest.json":
            # Explicit command receipt input; it is indexed later by exact route/argv.
            capture = {"commands": value.get("commands", []), "schema": value.get("schema")}
            runs.append({
                "input_ref": path_ref(manifest_path, root, allow_external=True),
                "manifest": capture,
                "completion": {},
                "plan_ref": None,
                "task_routes": {},
                "commands": capture["commands"],
                "candidate_match": False,
                "run_manifest_ref": path_ref(manifest_path, root, allow_external=True),
                "completion_ref": None,
                "input_role": None,
            })
            continue
        completion: dict[str, Any] = {}
        completion_ref = None
        if completion_path is not None:
            completion, _ = read_json(completion_path)
            if not isinstance(completion, dict):
                raise ReportError(f"capture completion must be a JSON object: {completion_path}")
            completion_ref = path_ref(completion_path, root)
        plan_path_value = value.get("plan_path")
        plan = None
        plan_ref = None
        task_routes: dict[str, list[str]] = defaultdict(list)
        if isinstance(plan_path_value, str) and plan_path_value:
            plan_path = Path(plan_path_value)
            if not plan_path.is_absolute():
                plan_path = root / plan_path
            plan_allowed = False
            if plan_path.is_file() and not plan_path.is_symlink():
                try:
                    plan_path.resolve(strict=True).relative_to(root.resolve(strict=True))
                    plan_allowed = True
                except ValueError:
                    try:
                        plan_path.resolve(strict=True).relative_to(
                            path.resolve(strict=True) if path.is_dir() else manifest_path.parent.resolve(strict=True)
                        )
                        plan_allowed = True
                    except ValueError:
                        plan_allowed = False
            if plan_allowed:
                plan, _ = read_json(plan_path)
                plan_digest = sha256_file(plan_path)
                if value.get("plan_sha256") == plan_digest:
                    plan_ref = path_ref(plan_path, root, allow_external=True)
                    task_routes = plan_task_routes(plan, task_rows)
        run_directory_value = completion.get("run_directory")
        run_directory = Path(run_directory_value) if isinstance(run_directory_value, str) else manifest_path.parent
        if not run_directory.is_absolute():
            run_directory = root / run_directory
        try:
            run_directory.resolve(strict=True).relative_to(path.resolve(strict=True) if path.is_dir() else manifest_path.parent.resolve(strict=True))
        except (OSError, ValueError):
            # A path-to-file capture may refer to a sibling run directory; keep it unadmitted.
            run_directory = manifest_path.parent
        metadata_rows: list[tuple[Path, dict[str, Any]]] = []
        if run_directory.exists() and run_directory.is_dir():
            for metadata_path in sorted(run_directory.rglob("metadata.json")):
                if metadata_path.is_symlink() or len(metadata_rows) >= 1024:
                    continue
                metadata, _ = read_json(metadata_path)
                if isinstance(metadata, dict):
                    metadata_rows.append((metadata_path.parent, metadata))
        command_statuses = completion.get("command_statuses", {})
        if not isinstance(command_statuses, dict):
            command_statuses = {}
        command_ids = set(value.get("selected_command_ids", [])) | set(command_statuses)
        indexed: list[dict[str, Any]] = []
        for command_id in sorted(command_ids):
            matches = [
                (directory, item)
                for directory, item in metadata_rows
                if item.get("command_id", item.get("id")) == command_id
            ]
            for command_dir, metadata in matches:
                actual_status, outputs, outcome_established, status_qualification = classify_metadata(
                    metadata, command_dir
                )
                advertised = command_statuses.get(command_id)
                input_manifest_matches = (
                    isinstance(value.get("input_manifest_sha256"), str)
                    and metadata.get("input_manifest_sha256") == value.get("input_manifest_sha256")
                )
                source_manifest_matches = (
                    isinstance(value.get("source_input_manifest_sha256"), str)
                    and metadata.get("source_input_manifest_sha256")
                    == value.get("source_input_manifest_sha256")
                )
                frozen_identity_matches = (
                    metadata.get("frozen_commit") == value.get("frozen_commit")
                    and metadata.get("frozen_tree") == value.get("frozen_tree")
                )
                plan_identity_matches = metadata.get("plan_sha256") == value.get("plan_sha256")
                metadata_reported_status = metadata.get("status")
                actual_argv = metadata.get("actual_argv", metadata.get("argv"))
                consistent = (
                    outcome_established
                    and actual_status in CAPTURE_STATUSES
                    and isinstance(advertised, str)
                    and advertised == metadata_reported_status
                    and input_manifest_matches
                    and source_manifest_matches
                    and frozen_identity_matches
                    and plan_identity_matches
                )
                indexed.append({
                    "command_id": command_id,
                    "task_ids": sorted(task_routes.get(command_id, [])),
                    "status": actual_status if actual_status in CAPTURE_STATUSES else "UNRUN",
                    "outcome_established": outcome_established,
                    "status_qualification": status_qualification,
                    "reported_status": metadata_reported_status,
                    "advertised_status": advertised,
                    "status_consistent": consistent,
                    "argv": actual_argv,
                    "cwd": metadata.get("cwd"),
                    "metadata_ref": path_ref(command_dir / "metadata.json", root, allow_external=True),
                    "outputs": [
                        {**item, "path": display_path(Path(item["path"]), root)} for item in outputs
                    ],
                    "input_manifest_sha256": value.get("input_manifest_sha256"),
                    "source_input_manifest_sha256": value.get("source_input_manifest_sha256"),
                    "plan_sha256": value.get("plan_sha256"),
                    "frozen_commit": value.get("frozen_commit"),
                    "frozen_tree": value.get("frozen_tree"),
                    "run_directory": display_path(run_directory, root),
                })
            if not matches and command_id in command_statuses:
                status = command_statuses[command_id]
                indexed.append({
                    "command_id": command_id,
                    "task_ids": sorted(task_routes.get(command_id, [])),
                    "status": "UNRUN",
                    "outcome_established": False,
                    "status_qualification": "No command metadata was found; the completion label is not an outcome witness.",
                    "reported_status": None,
                    "advertised_status": status,
                    "status_consistent": False,
                    "argv": None,
                    "cwd": None,
                    "metadata_ref": None,
                    "outputs": [],
                    "input_manifest_sha256": value.get("input_manifest_sha256"),
                    "source_input_manifest_sha256": value.get("source_input_manifest_sha256"),
                    "plan_sha256": value.get("plan_sha256"),
                    "frozen_commit": value.get("frozen_commit"),
                    "frozen_tree": value.get("frozen_tree"),
                    "run_directory": display_path(run_directory, root) if run_directory.exists() else None,
                })
        runs.append({
            "input_ref": path_ref(path if path.is_file() else manifest_path, root, allow_external=True),
            "manifest": value,
            "completion": completion,
            "plan_ref": plan_ref,
            "task_routes": dict(task_routes),
            "commands": indexed,
            "candidate_match": (
                False
            ),
            "run_manifest_ref": path_ref(manifest_path, root, allow_external=True),
            "completion_ref": completion_ref,
            "input_role": None,
        })
    return runs


def receipt_command_key(command: dict[str, Any]) -> tuple[tuple[str, ...], str] | None:
    """Return exact argv/cwd key from a typed receipt command."""
    argv = command.get("argv")
    if isinstance(argv, list) and argv and all(isinstance(part, str) for part in argv):
        cwd = command.get("cwd")
        if isinstance(cwd, str):
            return tuple(argv), cwd
    command_text = command.get("command")
    cwd = command.get("cwd")
    if isinstance(command_text, str) and isinstance(cwd, str):
        try:
            return tuple(shlex.split(command_text)), cwd
        except ValueError:
            return None
    return None


def captured_command_key(command: dict[str, Any]) -> tuple[tuple[str, ...], str] | None:
    """Return exact argv/cwd key from captured metadata."""
    argv, cwd = command.get("argv"), command.get("cwd")
    if isinstance(argv, list) and argv and all(isinstance(part, str) for part in argv) and isinstance(cwd, str):
        return tuple(argv), cwd
    return None


def read_author_handoff_packet(path: Path, root: Path, freeze: dict[str, str]) -> dict[str, Any]:
    """Read one v2-shaped author packet without treating it as registered admission."""
    artifact, _ = read_json(path)
    if not isinstance(artifact, dict) or artifact.get("schema") != AUTHOR_HANDOFF_PACKET_SCHEMA:
        raise ReportError(f"author handoff packet is not {AUTHOR_HANDOFF_PACKET_SCHEMA}: {path}")
    if artifact.get("candidate_source") != freeze:
        raise ReportError(f"author handoff packet candidate differs from supplied freeze: {path}")
    if artifact.get("formal_closure_ids") != []:
        raise ReportError(f"author handoff packet contains formal closure IDs: {path}")
    bindings = artifact.get("proposal_occurrences")
    commands = artifact.get("commands")
    if not isinstance(bindings, list) or not isinstance(commands, list):
        raise ReportError(f"author handoff packet occurrence/command arrays are missing: {path}")
    seen: set[tuple[str, str, str]] = set()
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ReportError(f"invalid occurrence binding in author handoff packet: {path}")
        key = (binding.get("finding_id"), binding.get("occurrence_pointer"), binding.get("criterion_sha256"))
        if key in seen:
            raise ReportError(f"duplicate occurrence binding in author handoff packet: {path}")
        if (
            not isinstance(key[0], str)
            or not isinstance(key[1], str)
            or not key[1]
            or not isinstance(key[2], str)
            or SHA256_RE.fullmatch(key[2]) is None
        ):
            raise ReportError(f"invalid exact occurrence key in author handoff packet: {path}")
        seen.add(key)
    proposal_ids = artifact.get("proposal_ids")
    if (
        not isinstance(proposal_ids, list)
        or len(proposal_ids) != len(set(proposal_ids))
        or set(proposal_ids) != {key[0] for key in seen}
    ):
        raise ReportError(f"author handoff packet IDs do not exactly cover its occurrence bindings: {path}")
    for command in commands:
        if not isinstance(command, dict) or command.get("status") not in CAPTURE_STATUSES:
            raise ReportError(f"invalid command/status in author handoff packet: {path}")
        if receipt_command_key(command) is None:
            raise ReportError(f"author handoff command lacks exact argv/command and cwd: {path}")
        if command["status"] != "UNRUN" and (
            output_hash(command, "stdout_ref") is None
            or output_hash(command, "stderr_ref") is None
        ):
            raise ReportError(f"executed author handoff command lacks hashed stream refs: {path}")
    return {
        "artifact": artifact,
        "ref": path_ref(path, root, allow_external=True),
        "bindings": seen,
    }


def read_author_capture(
    path: Path,
    root: Path,
    freeze: dict[str, str],
    canonical_occurrence_keys: set[tuple[str, str, str]],
) -> dict[str, Any]:
    """Retain a v1 author packet as explicitly unadmitted occurrence evidence."""
    artifact, _ = read_json(path)
    if not isinstance(artifact, dict) or artifact.get("schema") != AUTHOR_CAPTURE_SCHEMA:
        raise ReportError(f"author capture is not {AUTHOR_CAPTURE_SCHEMA}: {path}")
    formal = artifact.get("formal_closure_ids", [])
    if formal != []:
        raise ReportError(f"author capture contains formal closure IDs: {path}")
    bindings = artifact.get("proposal_occurrences", [])
    if not isinstance(bindings, list):
        raise ReportError(f"author capture proposal_occurrences must be an array: {path}")

    by_fragment: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    for key in canonical_occurrence_keys:
        finding_id, pointer, digest = key
        if "#" not in pointer:
            raise ReportError("canonical occurrence pointer is missing its source fragment")
        fragment_key = (finding_id, pointer.split("#", 1)[1], digest)
        if fragment_key in by_fragment:
            raise ReportError("canonical occurrence fragment is ambiguous")
        by_fragment[fragment_key] = key

    mapped: set[tuple[str, str, str]] = set()
    source_pointers: list[dict[str, str]] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ReportError(f"invalid author occurrence binding: {path}")
        finding_id = binding.get("finding_id")
        occurrence_pointer = binding.get("occurrence_pointer")
        digest = binding.get("criterion_sha256")
        if (
            not isinstance(finding_id, str)
            or not isinstance(occurrence_pointer, str)
            or not occurrence_pointer
            or not isinstance(digest, str)
            or SHA256_RE.fullmatch(digest) is None
        ):
            raise ReportError(f"malformed author occurrence binding: {path}")
        if "#" in occurrence_pointer:
            fragment = occurrence_pointer.split("#", 1)[1]
        else:
            fragment = occurrence_pointer
        fragment_key = (finding_id, fragment, digest)
        canonical_key = by_fragment.get(fragment_key)
        if canonical_key is None:
            raise ReportError(
                f"author capture occurrence does not exactly bind the canonical denominator: {path}"
            )
        if canonical_key in mapped:
            raise ReportError(f"duplicate author occurrence binding: {path}")
        mapped.add(canonical_key)
        source_pointers.append({
            "finding_id": finding_id,
            "author_occurrence_pointer": occurrence_pointer,
            "criterion_sha256": digest,
        })

    proposal_ids = artifact.get("proposal_ids")
    if proposal_ids is not None and (
        not isinstance(proposal_ids, list)
        or not all(isinstance(item, str) for item in proposal_ids)
        or len(proposal_ids) != len(set(proposal_ids))
        or set(proposal_ids) != {key[0] for key in mapped}
    ):
        raise ReportError(f"author capture proposal IDs differ from its exact occurrence bindings: {path}")

    candidate = artifact.get("candidate_source")
    candidate_matches = isinstance(candidate, dict) and candidate == freeze
    return {
        "artifact": artifact,
        "ref": path_ref(path, root, allow_external=True),
        "bindings": mapped,
        "source_pointers": source_pointers,
        "candidate_matches_report_freeze": candidate_matches,
        "registered_handoff_admission": artifact.get("registered_handoff_admission"),
        "qualification": (
            "Unadmitted author capture only. Its v1 schema and author-provided admission text are not a "
            "registered typed receipt, do not bind command outputs to an execution attempt, and cannot "
            "establish a whole-property outcome or closure."
        ),
    }


def output_hash(command: dict[str, Any], key: str) -> str | None:
    """Read a typed handoff command's output digest."""
    ref = command.get(key)
    if isinstance(ref, dict) and isinstance(ref.get("sha256"), str) and SHA256_RE.fullmatch(ref["sha256"]):
        return ref["sha256"]
    return None


def receipt_decision_refs(artifact: dict[str, Any], occurrence_key: tuple[str, str, str]) -> list[dict[str, Any]]:
    """Return only decision records bound to the exact original occurrence."""
    selected: list[dict[str, Any]] = []
    for row in artifact.get("decision_refs", []):
        if not isinstance(row, dict):
            continue
        source_ref = row.get("source_ref", {})
        covers = source_ref.get("covers", []) if isinstance(source_ref, dict) else []
        if any(
            isinstance(item, dict)
            and item.get("finding_id") == occurrence_key[0]
            and item.get("occurrence_pointer") == occurrence_key[1]
            and item.get("criterion_sha256") == occurrence_key[2]
            for item in covers
        ):
            selected.append({
                "kind": row.get("kind"),
                "decision_id": row.get("decision_id"),
                "source_ref": source_ref,
            })
    return selected


def unadmitted_author_command_attempts_for_occurrence(
    *, occurrence_key: tuple[str, str, str], occurrence: dict[str, Any], task_rows: dict[str, Any],
    captures: list[dict[str, Any]], handoff_packets: list[dict[str, Any]],
    freeze: dict[str, str], root: Path,
) -> list[dict[str, Any]]:
    """Match author-packet commands to captures/routes without granting registered admission."""
    finding_id = occurrence_key[0]
    allowed_tasks = {route.get("task_id") for route in occurrence.get("task_routes", [])}
    attempts: list[dict[str, Any]] = []
    for receipt in handoff_packets:
        artifact = receipt["artifact"]
        if occurrence_key not in receipt["bindings"]:
            continue
        for receipt_index, receipt_command in enumerate(artifact.get("commands", [])):
            key = receipt_command_key(receipt_command)
            if key is None:
                continue
            for capture in captures:
                manifest = capture["manifest"]
                completion = capture["completion"]
                if capture.get("candidate_match") is not True:
                    continue
                for captured in capture["commands"]:
                    if captured.get("status_consistent") is not True or captured.get("status") not in CAPTURE_STATUSES:
                        continue
                    if captured_command_key(captured) != key:
                        continue
                    for task_id in captured.get("task_ids", []):
                        if task_id not in allowed_tasks:
                            continue
                        if finding_id not in task_rows.get(task_id, {}).get("finding_ids", []):
                            continue
                        if receipt_command.get("status") != captured.get("status"):
                            continue
                        stdout_sha = output_hash(receipt_command, "stdout_ref")
                        stderr_sha = output_hash(receipt_command, "stderr_ref")
                        captured_hashes = {
                            item.get("role"): item.get("sha256")
                            for item in captured.get("outputs", [])
                            if item.get("role") in {"stdout", "stderr"}
                        }
                        if (
                            stdout_sha is None
                            or stderr_sha is None
                            or captured_hashes.get("stdout") != stdout_sha
                            or captured_hashes.get("stderr") != stderr_sha
                        ):
                            continue
                        if not captured.get("outputs") or not captured.get("metadata_ref"):
                            continue
                        attempts.append({
                            "status": captured["status"],
                            "admission": "UNADMITTED_AUTHOR_COMMAND_ATTEMPT_ONLY",
                            "candidate_source": freeze,
                            "task_route": {
                                "task_id": task_id,
                                "task_pointer": f"{repo_relative(Path('policy-engine/docs/research/e02-cloud-test-plan/execution-prompts/unified-local-2026-10-09/TASKS.json'), root)}#/tasks/{task_id}",
                                "finding_id_is_assigned": True,
                            },
                            "command": {
                                "capture_command_id": captured["command_id"],
                                "receipt_command_index": receipt_index,
                                "argv": list(key[0]),
                                "cwd": key[1],
                                "capture_status": captured["status"],
                                "receipt_status": receipt_command.get("status"),
                                "status_consistent": captured.get("status_consistent") is True,
                                "status_qualification": captured.get("status_qualification"),
                            },
                            "capture_refs": {
                                "run_manifest": capture["run_manifest_ref"],
                                "completion": capture["completion_ref"],
                                "plan": capture["plan_ref"],
                                "metadata": captured["metadata_ref"],
                                "input_manifest_sha256": captured.get("input_manifest_sha256"),
                                "source_input_manifest_sha256": captured.get("source_input_manifest_sha256"),
                                "plan_sha256": captured.get("plan_sha256"),
                                "frozen_commit": captured.get("frozen_commit"),
                                "frozen_tree": captured.get("frozen_tree"),
                            },
                            "unadmitted_author_handoff_packet": receipt["ref"],
                            "outputs": captured["outputs"],
                            "decision_refs_for_occurrence": receipt_decision_refs(artifact, occurrence_key),
                            "qualification": (
                                "The command, exact occurrence, capture, and TASKS route match in the supplied "
                                "author packet. The registered v2 validator was not invoked, so this remains "
                                "UNADMITTED_AUTHOR_COMMAND_ATTEMPT_ONLY and cannot count as an admitted attempt, "
                                "whole-property evaluation, closure, or G decision."
                            ),
                        })
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for attempt in attempts:
        key = (
            attempt["capture_refs"]["run_manifest"]["path"],
            attempt["capture_refs"]["run_manifest"]["sha256"],
            (attempt["capture_refs"].get("completion") or {}).get("path"),
            (attempt["capture_refs"].get("completion") or {}).get("sha256"),
            attempt["capture_refs"]["metadata"]["path"],
            attempt["capture_refs"]["metadata"]["sha256"],
            tuple((item.get("role"), item.get("sha256")) for item in attempt["outputs"]),
            attempt["unadmitted_author_handoff_packet"]["path"],
            attempt["unadmitted_author_handoff_packet"]["sha256"],
            attempt["command"]["receipt_command_index"],
            attempt["task_route"]["task_id"],
        )
        unique[key] = attempt
    return list(unique.values())


def navigation_observations_for_occurrence(
    *, occurrence_key: tuple[str, str, str], occurrence: dict[str, Any],
    task_rows: dict[str, Any], captures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach source-bound task-route observations without treating them as occurrence proof."""
    finding_id = occurrence_key[0]
    allowed_tasks = {route.get("task_id") for route in occurrence.get("task_routes", [])}
    observations: dict[tuple[str, str, str], dict[str, Any]] = {}
    for capture in captures:
        if capture.get("candidate_match") is not True:
            continue
        for command in capture.get("commands", []):
            for task_id in command.get("task_ids", []):
                if task_id not in allowed_tasks or finding_id not in task_rows.get(task_id, {}).get("finding_ids", []):
                    continue
                key = (capture["run_manifest_ref"]["sha256"], command.get("command_id", ""), task_id)
                status_consistent = command.get("status_consistent") is True
                observations[key] = {
                    "status": command.get("status") if status_consistent else None,
                    "reported_status": command.get("reported_status"),
                    "advertised_status": command.get("advertised_status"),
                    "outcome_state": (
                        "CONSISTENT_CAPTURED_COMMAND_RESULT"
                        if status_consistent
                        else "UNESTABLISHED_CAPTURED_COMMAND_RESULT"
                    ),
                    "status_qualification": command.get("status_qualification"),
                    "admission": "NAVIGATION_ONLY_CAPTURE",
                    "capture_role": capture.get("input_role"),
                    "task_route": {
                        "task_id": task_id,
                        "finding_id_is_assigned": True,
                        "occurrence_is_on_task_route": True,
                    },
                    "command": {
                        "capture_command_id": command.get("command_id"),
                        "argv": command.get("argv"),
                        "cwd": command.get("cwd"),
                        "status_consistent": status_consistent,
                    },
                    "capture_refs": {
                        "run_manifest": capture["run_manifest_ref"],
                        "completion": capture.get("completion_ref"),
                        "plan": capture.get("plan_ref"),
                        "metadata": command.get("metadata_ref"),
                        "input_manifest_sha256": command.get("input_manifest_sha256"),
                        "plan_sha256": command.get("plan_sha256"),
                    },
                    "outputs": command.get("outputs", []),
                    "qualification": (
                        "This frozen capture record is attached through the finding's TASKS route for navigation "
                        "only. A consistent command result is still not bound to this exact occurrence by a "
                        "registered receipt and cannot establish a whole-property result or closure. An "
                        "inconsistent/incomplete record has no normalized status."
                    ),
                }
    return list(observations.values())


def source_evidence_refs(draft: dict[str, Any], occurrence: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve author evidence IDs to compact source-path/pointer/hash references."""
    selected: list[dict[str, Any]] = []
    catalog = draft.get("source_evidence_catalog", {})
    evidence = occurrence.get("technical_assessment", {}).get("evidence_boundary", {})
    for evidence_id in evidence.get("source_ref_ids", []):
        row = catalog.get(evidence_id)
        if not isinstance(row, dict):
            raise ReportError(f"draft evidence catalog lacks {evidence_id}")
        selected.append({
            "evidence_id": evidence_id,
            "role": row.get("role"),
            "path": row.get("path"),
            "pointer": row.get("pointer") or row.get("coverage_pointer"),
            "sha256": row.get("sha256_expected_from_owner_inventory") or row.get("criterion_sha256"),
            "source_commit": row.get("source_commit"),
            "git_blob": row.get("git_blob"),
            "qualification": row.get("current_worktree_readback"),
        })
    return selected


def occurrence_report_row(
    *, key: tuple[str, str, str], draft_row: dict[str, Any], coverage_row: dict[str, Any],
    ledger_finding: dict[str, Any], attempts: list[dict[str, Any]],
    author_captures: list[dict[str, Any]], navigation_observations: list[dict[str, Any]],
    draft: dict[str, Any],
) -> dict[str, Any]:
    """Create one compact author-proposal row while preserving exact occurrence identity."""
    original = draft_row.get("key", {})
    history = ledger_finding.get("historical", {})
    source_author = ledger_finding.get("source_author_proposal", {})
    technical = draft_row.get("technical_assessment", {})
    boundary = draft_row.get("original_acceptance_boundary", {})
    task_routes = draft_row.get("task_routes", [])
    p40 = draft.get("same_class_review_catalog", {}).get(draft_row.get("same_class_review_ref"), {})
    author_capture_evidence = [
        {
            "capture_ref": capture["ref"],
            "schema": AUTHOR_CAPTURE_SCHEMA,
            "slice_id": capture["artifact"].get("slice_id"),
            "candidate_matches_report_freeze": capture["candidate_matches_report_freeze"],
            "registered_handoff_admission": capture["registered_handoff_admission"],
            "occurrence_binding": next(
                source_pointer
                for source_pointer in capture["source_pointers"]
                if source_pointer["finding_id"] == key[0]
                and source_pointer["criterion_sha256"] == key[2]
                and (
                    source_pointer["author_occurrence_pointer"] == key[1]
                    or key[1].endswith("#" + source_pointer["author_occurrence_pointer"].split("#", 1)[-1])
                )
            ),
            "admission_state": "UNADMITTED_AUTHOR_EVIDENCE",
            "qualification": capture["qualification"],
        }
        for capture in author_captures
        if key in capture["bindings"]
    ]
    return {
        "finding_id": key[0],
        "occurrence_pointer": key[1],
        "criterion_sha256": key[2],
        "occurrence_ordinal_for_finding": original.get("occurrence_ordinal_for_finding"),
        "source_occurrence": {
            "document": original.get("document"),
            "card_binding": original.get("card_binding"),
            "source_path": original.get("source_span", {}).get("path"),
            "source_commit": original.get("source_span", {}).get("source_commit"),
            "source_git_blob": original.get("source_span", {}).get("git_blob"),
            "source_lines_1_based_inclusive": original.get("source_span", {}).get("lines_1_based_inclusive"),
            "coverage_capability_label": coverage_row.get("capability_label"),
            "criterion_specific_acceptance_boundary": coverage_row.get("criterion_specific_acceptance_not_executed"),
            "source_ref": {
                "path": original.get("source_span", {}).get("path"),
                "commit": original.get("source_span", {}).get("source_commit"),
                "git_blob": original.get("source_span", {}).get("git_blob"),
                "span_sha256": key[2],
            },
        },
        "task_routes_navigation_only": [
            {
                "task_id": route.get("task_id"),
                "assignment_pointer": route.get("assignment_pointer"),
                "role": "routing/navigation only; no evaluation or closure authority",
            }
            for route in task_routes
        ],
        "history_and_source_author_proposal": {
            "historical": history,
            "source_author_proposal": source_author,
            "prior_historical_statuses": draft_row.get("historical_and_source_author_state", {}).get("prior_historical_statuses"),
            "candidate_proposal_modified_by_assembler": False,
            "formal_G_closure": "not_adjudicated",
        },
        "author_technical_proposal": {
            "disposition": draft_row.get("proposal_disposition"),
            "current_property_and_bounded_path": technical.get("current_mechanism_or_bounded_path"),
            "original_acceptance_boundary": boundary,
            "candidate_evidence_boundary": {
                key: technical.get("evidence_boundary", {}).get(key)
                for key in (
                    "candidate_source_binding",
                    "owner_readout_status",
                    "related_retained_wave_evidence_keys",
                    "source_ref_ids",
                )
            },
            "next_owner_or_decision_holder": technical.get("next_owner_or_decision_holder"),
            "owner_assignment_boundary": technical.get("owner_assignment_boundary"),
            "evidence_refs": source_evidence_refs(draft, draft_row),
        },
        "actual_execution": {
            "status": "UNRUN",
            "attempt_statuses": [],
            "attempts": [],
            "evaluation_state": "NOT_ADJUDICATED_BY_ASSEMBLER",
            "qualification": (
                "No registered v4 occurrence evaluation is admitted by this assembler. Task routes, capture "
                "results, and author handoff packets do not establish a candidate evaluation."
            ),
        },
        "unadmitted_author_command_attempts": attempts,
        "unadmitted_author_command_attempts_qualification": (
            "These exact command/capture/route matches came from author-provided handoff packets. The registered "
            "v2 validator was not invoked, so their reported statuses are not admitted evidence or candidate outcomes."
        ),
        "unadmitted_author_capture_evidence": author_capture_evidence,
        "navigation_only_command_observations": navigation_observations,
        "criterion_specific_boundary": {
            "original_property_ref": boundary.get("coverage_row_pointer"),
            "current_property": technical.get("current_mechanism_or_bounded_path", {}).get("property"),
            "proxy_divergence": technical.get("current_mechanism_or_bounded_path", {}).get("proxy_divergence"),
            "source_scope_limit": technical.get("remaining_whole_criterion_quantity_or_dependency"),
            "separate_external_or_G_boundary": technical.get("separate_external_or_G_boundary"),
            "why_unqualified_positive_is_not_claimed": technical.get("why_an_unqualified_positive_is_not_claimed"),
        },
        "next_check": {
            "draft_next_check": draft_row.get("next_check_after_final_source_freeze"),
            "owner_specific_exact_next_check": technical.get("exact_next_check"),
            "post_attempt_reconciliation": (
                "Compare any separately admitted occurrence-specific evidence against this criterion, property, "
                "consumer, and discriminator. The unadmitted command records above do not update this row's evaluation."
            ),
        },
        "p40_review": {
            "bucket": p40.get("P40_bucket"),
            "classification_source_ref": p40.get("row_specific_classification_ref"),
            "classification_ref": draft_row.get("same_class_review_ref"),
            "review_qualification_ref": draft_row.get("owner_review_qualification_ref"),
            "escape_status": technical.get("formal_G_status", "not_adjudicated"),
        },
    }


def load_capture_path(path: Path, root: Path, task_rows: dict[str, Any], freeze: dict[str, str]) -> list[dict[str, Any]]:
    """Load a capture source and mark source identity against the explicit candidate."""
    runs = read_capture_input(path, root, task_rows)
    for run in runs:
        manifest = run["manifest"]
        completion = run["completion"]
        completion_matches = not completion or (
            completion.get("frozen_commit") == manifest.get("frozen_commit")
            and completion.get("frozen_tree") == manifest.get("frozen_tree")
            and completion.get("input_manifest_sha256") == manifest.get("input_manifest_sha256")
            and completion.get("source_input_manifest_sha256")
            == manifest.get("source_input_manifest_sha256")
            and completion.get("plan_sha256") == manifest.get("plan_sha256")
        )
        run["candidate_match"] = (
            manifest.get("frozen_commit") == freeze["commit"]
            and manifest.get("frozen_tree") == freeze["tree"]
            and completion_matches
        )
    return runs


def mark_capture_role(runs: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    """Tag a primary/supplement capture input for report provenance."""
    for run in runs:
        run["input_role"] = role
    return runs


def census_ref(value: str) -> tuple[str, str]:
    """Parse the root-supplied immutable source-census reference."""
    if "@" not in value:
        raise ReportError("source census ref must have the form path-or-pointer@sha256")
    ref, digest = value.rsplit("@", 1)
    if not ref or SHA256_RE.fullmatch(digest) is None:
        raise ReportError("source census ref must include a lowercase SHA-256 digest")
    return ref, digest


def make_argument_parser(root: Path) -> argparse.ArgumentParser:
    """Build CLI parser with repository input defaults and explicit evidence paths."""
    product = root / "policy-engine"
    base = product / "docs/research/e02-cloud-test-plan"
    handoff = base / "implementation-handoffs/LOCAL"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-commit", required=True)
    parser.add_argument("--freeze-tree", required=True)
    parser.add_argument("--source-census-ref", required=True, help="path-or-pointer@sha256 supplied by root")
    parser.add_argument("--primary-capture", required=True, type=Path)
    parser.add_argument("--supplement-capture", action="append", default=[], type=Path)
    parser.add_argument(
        "--author-handoff-packet",
        "--external-receipt",
        dest="author_handoff_packet",
        action="append",
        default=[],
        type=Path,
        help="v2-shaped author packet; retained only as UNADMITTED_AUTHOR_COMMAND_ATTEMPT_ONLY",
    )
    parser.add_argument(
        "--author-capture",
        action="append",
        default=[],
        type=Path,
        help="explicit local_slice_author_capture.v1 packet; retained only as unadmitted author evidence",
    )
    parser.add_argument("--coverage", type=Path, default=base / "closure-decisions/coverage.json")
    parser.add_argument("--tasks", type=Path, default=base / "execution-prompts/unified-local-2026-10-09/TASKS.json")
    parser.add_argument("--ledger", type=Path, default=handoff / "finding-proposals.json")
    parser.add_argument("--draft", type=Path, default=handoff / "crosswalk/occurrence-evaluations-draft.json")
    parser.add_argument("--owned-output-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Build a non-adjudicative, full-denominator author proposal report."""
    root = repo_root_from_script()
    args = make_argument_parser(root).parse_args(argv)
    freeze = {"commit": validate_git_sha(args.freeze_commit, "freeze commit"), "tree": validate_git_sha(args.freeze_tree, "freeze tree")}
    census_reference, census_digest = census_ref(args.source_census_ref)
    owned_root = args.owned_output_root
    output_path = args.output
    if not owned_root.is_absolute() or not output_path.is_absolute():
        raise ReportError("--owned-output-root and --output must be absolute paths")
    if owned_root.is_symlink() or not owned_root.is_dir():
        raise ReportError("--owned-output-root must be an existing non-symlink directory")
    if output_path.exists() or output_path.is_symlink():
        raise ReportError("--output must be a new file; existing files are never overwritten")
    if output_path.parent.absolute() != output_path.parent.resolve(strict=True):
        raise ReportError("--output parent cannot contain symlink path components")
    try:
        output_path.parent.resolve(strict=True).relative_to(owned_root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ReportError("--output must be inside the explicitly supplied owned output root") from exc
    if output_path.parent.is_symlink():
        raise ReportError("--output parent cannot be a symlink")

    coverage, _ = read_json(args.coverage)
    tasks, _ = read_json(args.tasks)
    ledger, _ = read_json(args.ledger)
    draft, _ = read_json(args.draft)
    if not all(isinstance(value, dict) for value in (coverage, tasks, ledger, draft)):
        raise ReportError("coverage, TASKS, ledger, and preparation draft must be JSON objects")
    draft_rows, ledger_findings, task_rows = exact_occurrence_maps(
        coverage=coverage,
        tasks=tasks,
        ledger=ledger,
        draft=draft,
        coverage_path=args.coverage,
        tasks_path=args.tasks,
        root=root,
    )

    primary_captures = mark_capture_role(
        load_capture_path(args.primary_capture, root, task_rows, freeze), "primary"
    )
    supplement_captures: list[dict[str, Any]] = []
    for path in args.supplement_capture:
        supplement_captures.extend(mark_capture_role(
            load_capture_path(path, root, task_rows, freeze), "supplement"
        ))
    captures = [*primary_captures, *supplement_captures]
    handoff_packets = [
        read_author_handoff_packet(path, root, freeze) for path in args.author_handoff_packet
    ]
    canonical_occurrence_keys = set(draft_rows)
    for packet in handoff_packets:
        if not packet["bindings"] <= canonical_occurrence_keys:
            raise ReportError("author handoff packet binds an occurrence outside the canonical denominator")
    author_captures = [
        read_author_capture(path, root, freeze, canonical_occurrence_keys)
        for path in args.author_capture
    ]

    report_rows: list[dict[str, Any]] = []
    for key in draft_rows:
        finding_id, pointer, digest = key
        coverage_pointer = pointer.split("#", 1)[1]
        coverage_finding_pointer = coverage_pointer.split("/criterion_refs/", 1)[0]
        coverage_finding = resolve_pointer(coverage, coverage_finding_pointer)
        occurrence = draft_rows[key]
        unadmitted_attempts = unadmitted_author_command_attempts_for_occurrence(
            occurrence_key=key,
            occurrence=occurrence,
            task_rows=task_rows,
            captures=captures,
            handoff_packets=handoff_packets,
            freeze=freeze,
            root=root,
        )
        navigation_observations = navigation_observations_for_occurrence(
            occurrence_key=key,
            occurrence=occurrence,
            task_rows=task_rows,
            captures=captures,
        )
        report_rows.append(occurrence_report_row(
            key=key,
            draft_row=occurrence,
            coverage_row=coverage_finding,
            ledger_finding=ledger_findings[finding_id],
            attempts=unadmitted_attempts,
            author_captures=author_captures,
            navigation_observations=navigation_observations,
            draft=draft,
        ))

    dispositions = Counter(
        row["author_technical_proposal"]["disposition"]["status"]
        for row in report_rows
    )
    source_author_closed_ids = sorted(
        finding_id
        for finding_id, finding in ledger_findings.items()
        if finding.get("source_author_proposal", {}).get("disposition") == "closed"
    )
    source_author_closed_occurrences = sum(
        len(finding.get("occurrences", []))
        for finding in ledger_findings.values()
        if finding.get("source_author_proposal", {}).get("disposition") == "closed"
    )
    if len(source_author_closed_ids) != 198 or source_author_closed_occurrences != 202:
        raise ReportError(
            "source-author history denominator changed; expected 198 closed IDs / 202 occurrences"
        )
    if dispositions != Counter({"limited": 194, "held": 35, "open": 62}):
        raise ReportError("current per-occurrence technical proposal denominator changed")
    b198 = ledger_findings.get("B198")
    if not isinstance(b198, dict):
        raise ReportError("historical B198 row is missing")
    if (
        b198.get("historical", {}).get("ledger_status") != "closed"
        or b198.get("historical", {}).get("appendix_c_status") != "closed_bounded"
        or b198.get("historical", {}).get("closure_now") != "not_adjudicated"
        or b198.get("source_author_proposal", {}).get("disposition") != "closed"
    ):
        raise ReportError("B198 historical/source-author decision was not preserved")
    execution_states = Counter(row["actual_execution"]["status"] for row in report_rows)
    if not primary_captures or not any(run.get("candidate_match") is True for run in primary_captures):
        raise ReportError("primary capture has no run bound to the supplied final candidate")
    report = {
        "schema": REPORT_SCHEMA,
        "report_kind": "AUTHOR_PROPOSAL_AND_EXECUTION_ATTEMPT_CROSSWALK_ONLY",
        "registered_v4_import": False,
        "G_adjudication": "NOT_PERFORMED",
        "formal_closure_ids": [],
        "source_freeze": {
            "candidate_source": freeze,
            "source_census_ref": census_reference,
            "source_census_sha256": census_digest,
            "qualification": "Root-supplied freeze/census identity; this assembler does not recompute Git/source census acceptance.",
        },
        "input_refs": {
            "coverage": path_ref(args.coverage, root),
            "TASKS": path_ref(args.tasks, root),
            "proposal_ledger": path_ref(args.ledger, root),
            "occurrence_preparation_draft": path_ref(args.draft, root),
            "primary_capture_inputs": [
                run["run_manifest_ref"] for run in primary_captures
            ],
            "supplement_capture_inputs": [
                run["run_manifest_ref"] for run in supplement_captures
            ],
            "unadmitted_author_handoff_packets": [packet["ref"] for packet in handoff_packets],
            "unadmitted_author_captures": [capture["ref"] for capture in author_captures],
        },
        "unadmitted_author_capture_sources": [
            {
                "ref": capture["ref"],
                "schema": AUTHOR_CAPTURE_SCHEMA,
                "slice_id": capture["artifact"].get("slice_id"),
                "candidate_source": capture["artifact"].get("candidate_source"),
                "candidate_matches_report_freeze": capture["candidate_matches_report_freeze"],
                "registered_handoff_admission": capture["registered_handoff_admission"],
                "bound_occurrence_count": len(capture["bindings"]),
                "status": "UNADMITTED_AUTHOR_EVIDENCE",
                "qualification": capture["qualification"],
            }
            for capture in author_captures
        ],
        "denominator": {
            "bundles": len(coverage.get("bundles", [])),
            "finding_ids": len(ledger_findings),
            "canonical_occurrences": len(report_rows),
            "task_definitions": len(task_rows),
            "task_route_assignments": sum(len(task.get("finding_ids", [])) for task in task_rows.values()),
            "source_author_closed_finding_ids": len(source_author_closed_ids),
            "source_author_closed_occurrences": source_author_closed_occurrences,
            "source_author_closed_ids": source_author_closed_ids,
            "report_proposal_disposition_counts": dict(sorted(dispositions.items())),
            "execution_status_counts": dict(sorted(execution_states.items())),
        },
        "authority_and_join_rules": {
            "occurrence_identity": "Exact triple (finding_id, coverage JSON pointer, criterion SHA-256); duplicates remain separate rows.",
            "command_route_join": "Exact capture command route label -> TASKS task ID -> that occurrence's recorded TASKS route -> exact occurrence binding in a supplied author handoff packet; the match is unadmitted.",
            "no_status_propagation": "Task routes or task-level PASS never create occurrence outcomes or proposal closures.",
            "proposal_separation": "Technical proposal disposition, source-author history, unadmitted command observations, actual execution state, and formal G closure are separate fields.",
            "actual_execution_meaning": "actual_execution remains UNRUN because this adapter does not invoke registered v2 admission or registered v4 occurrence evaluation.",
            "author_packet_match_meaning": "A structural match to a v2-shaped author packet is retained only as UNADMITTED_AUTHOR_COMMAND_ATTEMPT_ONLY; it cannot create an admitted attempt, candidate outcome, or closure.",
            "v1_author_capture_meaning": "local_slice_author_capture.v1 is surfaced only as UNADMITTED_AUTHOR_EVIDENCE, even when an exact occurrence pointer maps; it cannot create an admitted attempt, evaluation, or closure.",
            "registered_admission": "No author-supplied v2-shaped packet is passed through the registered validator. All 291 actual_execution rows remain UNRUN, including rows with exact packet/capture matches.",
        },
        "capture_summary": [
            {
                "run_manifest_ref": run.get("run_manifest_ref"),
                "completion_ref": run.get("completion_ref"),
                "plan_ref": run.get("plan_ref"),
                "input_role": run.get("input_role"),
                "candidate_match": run.get("candidate_match") is True,
                "selected_command_ids": run.get("manifest", {}).get("selected_command_ids", []),
                "command_count": len(run.get("commands", [])),
                "routed_command_count": sum(bool(command.get("task_ids")) for command in run.get("commands", [])),
                "status_consistent_count": sum(command.get("status_consistent") is True for command in run.get("commands", [])),
            }
            for run in captures
        ],
        "preserved_history": {
            "B198": {
                "historical": ledger_findings.get("B198", {}).get("historical"),
                "source_author_proposal": ledger_findings.get("B198", {}).get("source_author_proposal"),
                "candidate_proposal_modified_by_assembler": False,
                "formal_G_closure": "not_adjudicated",
                "rule": "Do not reopen or replace historical state without an exact occurrence-bound new defining-property counterexample and separate review.",
            }
        },
        "occurrences": report_rows,
    }
    raw_output = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with output_path.open("xb") as stream:
        stream.write(raw_output)
    print(json.dumps({
        "schema": REPORT_SCHEMA,
        "output": output_path.as_posix(),
        "sha256": sha256_bytes(raw_output),
        "occurrences": len(report_rows),
        "formal_closure_ids": [],
        "execution_status_counts": dict(sorted(execution_states.items())),
        "qualification": "author proposal report only; not registered v4 and not G adjudication",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

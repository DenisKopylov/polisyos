#!/usr/bin/env python3
"""Emit an occurrence-bound E02 proposal ledger without adjudicating closure.

The source author proposals and historical ledger statuses are carried as
provenance. Candidate outcomes are accepted only from an explicit occurrence
evaluation file; task status and historical closure never promote an outcome.
The generated ledger is planning evidence, not runtime proof or G acceptance.

Evaluation input shape:

    {
      "schema": "policyos.e02.occurrence_evaluations.v4",
      "frozen_context": {
        "candidate_source": {"commit": "<40 hex>", "tree": "<40 hex>"},
        "source_footprint_ref": "/source_boundary/source_freeze/source_change_census",
        "source_footprint_sha256": "<canonical JSON SHA-256>"
      },
      "evaluations": [{
        "occurrence_pointer": "<coverage.json JSON pointer>",
        "sha256": "<original criterion block sha256>",
        "candidate_source": {"commit": "<40 hex>", "tree": "<40 hex>"},
        "state": "VERIFIED | BOUNDED_LIMITATION | UNAVAILABLE_INPUT | OPEN_ACTION",
        "result_summary": "...",
        "boundary": {"kind": "...", "details": "..."},
        "execution_context": {
          "source_footprint_sha256": "<same frozen census SHA-256>",
          "configuration_and_lock_evidence_indexes": [0],
          "configuration_scope_evidence_index": null,
          "selected_input_state": "available | unavailable | not_required | not_established",
          "selected_input_evidence_indexes": [1],
          "input_scope_evidence_index": null,
          "backend_profile_evidence_index": 2,
          "consumer_surface_evidence_indexes": [3],
          "typed_slice_receipt_evidence_indexes": [4],
          "decision_research_evidence_indexes": [5]
        },
        "evidence_refs": [{
          "path": "tracked/path", "commit": "<40 hex>",
          "git_blob": "<git blob id>", "sha256": "<file sha256>",
          "role": "property_positive | actual_consumer | negative | ...",
          "pointer": "#/json/pointer", "candidate_source": {"commit": "...", "tree": "..."},
          "covers": {"occurrence_pointer": "...", "sha256": "..."}
        }],
        "attempts": [{
          "action": "...",
          "status": "PASS | FAIL | ERROR | SKIP",
          "result_ref": <same source-bound reference shape>
        }],
        "next_check": "...",
        "proposal_disposition": "closed | limited | held | open",
        "review_escape": {"state": "none_observed"}
      }]
    }

Each evaluation is keyed by both occurrence_pointer and sha256. Evidence refs
must resolve to immutable Git blobs and explicitly bind the exact occurrence
and evaluated candidate. A finding-level candidate proposal requires an
explicit, matching disposition for every source occurrence of that ID. A
VERIFIED evaluation always requires occurrence-specific property, actual-consumer,
and negative evidence, regardless of proposal disposition. A proposed closed
disposition additionally requires VERIFIED state for every occurrence. This does
not set formal_closure_ids; only a separate G adjudication can do that. B198's
historical closed decision is immutable context here; a new proposal that reopens
it needs an occurrence-specific defining-property counterexample.
"""

from __future__ import annotations

import argparse
import ast
import collections
import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

SCHEMA = "policyos.e02.finding_proposals.v4"
EVALUATION_SCHEMA = "policyos.e02.occurrence_evaluations.v4"
SLICE_HANDOFF_SCHEMA = "policyos.e02.local_slice_handoff.v2"
ENVIRONMENT_MANIFEST_SCHEMA = "policyos.e02.execution_environment_manifest.v1"
OUTCOME_STATES = {
    "VERIFIED",
    "BOUNDED_LIMITATION",
    "UNAVAILABLE_INPUT",
    "OPEN_ACTION",
}
COMMAND_OUTCOMES = {"PASS", "FAIL", "ERROR", "SKIP"}
PROPOSAL_DISPOSITIONS = {"closed", "limited", "held", "open"}
P40_BUCKETS = {"NEW_CLASS", "SAME_CLASS_DEEPER"}
SOURCE_DESCENDANT_CACHE: dict[tuple[str, str, str, str], list[str]] = {}

BASE_REL = Path("policy-engine/docs/research/e02-cloud-test-plan")
PACKET_REL = BASE_REL / "execution-prompts/unified-local-2026-10-09"
LOCAL_REL = BASE_REL / "implementation-handoffs/LOCAL"
LOCAL_RAW_PREFIX = f"{LOCAL_REL.as_posix()}/raw/"
LOCAL_RAW_STORAGE = "ignored_local_raw"
EXECUTION_PLAN_PATH = PACKET_REL / "EXECUTION-PLAN.md"
BOOT0_PATH = LOCAL_REL / "BOOT0.json"
SOURCE_CLOSURE_KIND = "complete_repository_git_tree"
Q0_RECEIPT_SCHEMA = "policyos.e02.q0_crosswalk_receipt.v2"
SLICE_HANDOFF_PATH = re.compile(
    rf"^{re.escape(LOCAL_REL.as_posix())}/([a-z0-9]+(?:-[a-z0-9]+)*)\.json$"
)
SOURCE_FREEZE_POLICY = (
    "The candidate commit/tree freezes the complete repository Git tree. A later report checkout "
    "is accepted only when every committed and index/worktree/untracked delta is an explicitly "
    "typed proposal output, occurrence-evaluation input, or named command receipt below. The LOCAL "
    "directory is not an exemption: code, source, tests, configuration, and untyped data there "
    "remain candidate-source changes."
)
REPORT_ARTIFACT_SCHEMAS = {
    (LOCAL_REL / "finding-proposals.json").as_posix(): [
        SCHEMA,
    ],
    (LOCAL_REL / "crosswalk/occurrence-evaluations.json").as_posix(): [EVALUATION_SCHEMA],
    (LOCAL_REL / "crosswalk/receipt.json").as_posix(): [Q0_RECEIPT_SCHEMA],
}
REPORT_TEXT_RECEIPTS = {
    (LOCAL_REL / "crosswalk/checks/coverage-self-check.stdout.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/coverage-self-check.stderr.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/emit-self-check.stdout.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/emit-self-check.stderr.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/emit.stdout.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/emit.stderr.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/ledger-check.stdout.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/ledger-check.stderr.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/source-freeze-probes.stdout.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/source-freeze-probes.stderr.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/count-preserving-probes.stdout.txt").as_posix(),
    (LOCAL_REL / "crosswalk/checks/count-preserving-probes.stderr.txt").as_posix(),
}
INPUT_PATHS = {
    "inputs": PACKET_REL / "INPUTS.json",
    "tasks": PACKET_REL / "TASKS.json",
    "findings": BASE_REL / "integration/connected-closeout-plan-2026-10-08/findings.json",
    "connected_inputs": BASE_REL / "integration/connected-closeout-plan-2026-10-08/inputs.json",
    "coverage": BASE_REL / "closure-decisions/coverage.json",
}
SUPPORTING_TEXT_PATHS = {
    "verification_and_release": (
        BASE_REL / "integration/connected-closeout-plan-2026-10-08/05-verification-and-release.md"
    ),
    "input_deferrals": (
        BASE_REL / "integration/connected-closeout-plan-2026-10-08/06-inputs-and-deferrals.md"
    ),
}
CRITERIA_COVERAGE_PATH = BASE_REL / "closure-decisions/coverage.json"


def require(condition: bool, message: str) -> None:
    """Raise a readable error when an input or ledger invariant fails."""
    if not condition:
        raise ValueError(message)


def repo_root() -> Path:
    """Find the repository root from this script's location."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "policy-engine").is_dir():
            return parent
    raise RuntimeError("could not locate repository root")


def git_bytes(root: Path, *args: str) -> bytes:
    """Read bytes from Git without a shell or working-tree substitution."""
    return git_run(root, *args, check=True, capture_output=True).stdout


def git_text(root: Path, *args: str) -> str:
    """Read one Git result as UTF-8 text."""
    return git_bytes(root, *args).decode("utf-8").strip()


def git_run(
    root: Path,
    *args: str,
    check: bool = True,
    capture_output: bool = False,
    input: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run one argv-only Git read with replacement objects disabled."""
    require(bool(args) and all(isinstance(arg, str) for arg in args), "Git argv is invalid")
    environment = os.environ.copy()
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    try:
        return subprocess.run(  # noqa: S603 -- fixed Git executable and argv; no shell.
            ["git", "--no-replace-objects", *args],  # noqa: S607 -- global Git option disables replacement refs.
            cwd=root,
            env=environment,
            check=check,
            capture_output=capture_output,
            input=input,
        )
    except subprocess.CalledProcessError as exc:
        operation = args[0]
        raise ValueError(f"Git read failed for {operation} (exit {exc.returncode})") from exc


def has_active_git_grafts(graft_data: bytes) -> bool:
    """Return whether the legacy graft file supplies any active parent rows."""
    return any(
        line.strip() and not line.lstrip().startswith(b"#") for line in graft_data.splitlines()
    )


def ensure_git_graph_authoritative(root: Path, *, label: str) -> None:
    """Reject grafted or shallow graph views before relying on Git ancestry."""
    shallow_state = git_text(root, "rev-parse", "--is-shallow-repository")
    require(
        shallow_state == "false",
        f"{label} cannot establish complete Git ancestry in a shallow repository",
    )
    graft_path_value = git_text(root, "rev-parse", "--git-path", "info/grafts")
    graft_path = Path(graft_path_value)
    if not graft_path.is_absolute():
        graft_path = root / graft_path
    try:
        graft_status = graft_path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ValueError(f"{label} cannot inspect Git graft state") from exc
    require(
        not stat.S_ISLNK(graft_status.st_mode) and stat.S_ISREG(graft_status.st_mode),
        f"{label} cannot establish ancestry through a non-regular Git graft path",
    )
    try:
        graft_data = graft_path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{label} cannot read Git graft state") from exc
    require(
        not has_active_git_grafts(graft_data),
        f"{label} cannot establish Git ancestry while active grafts are present",
    )


def changes_from_name_status(output: bytes) -> list[tuple[str, str]]:
    """Parse a NUL-delimited, no-renames Git name-status stream."""
    changes: list[tuple[str, str]] = []
    fields = output.split(b"\0")
    index = 0
    while index < len(fields) and fields[index]:
        require(index + 1 < len(fields), "truncated NUL-delimited Git name-status stream")
        try:
            status = fields[index].decode("ascii")
            path = fields[index + 1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Git name-status row is not ASCII status plus UTF-8 path") from exc
        require(
            status in {"A", "M", "D", "T", "U", "X", "B"},
            f"unexpected Git change status: {status!r}",
        )
        require(bool(path), "Git name-status path is empty")
        changes.append((status, path))
        index += 2
    return changes


def validate_report_artifact(
    path: str,
    payload: bytes | None,
    *,
    label: str,
    expected_candidate: dict[str, str] | None = None,
) -> None:
    """Classify one delta by its exact path and typed report schema."""
    expected_schemas = REPORT_ARTIFACT_SCHEMAS.get(path)
    slice_match = SLICE_HANDOFF_PATH.fullmatch(path)
    if expected_schemas is None and slice_match is not None:
        expected_schemas = [SLICE_HANDOFF_SCHEMA]
    is_text_receipt = path in REPORT_TEXT_RECEIPTS
    require(
        expected_schemas is not None or is_text_receipt,
        f"{label} changes frozen candidate source: {path}",
    )
    if payload is None:
        # A missing proposal output is an ordinary report lifecycle operation. The
        # evaluations input may be removed to leave the affected occurrences UNRUN.
        return
    if is_text_receipt:
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{label} text receipt is not UTF-8: {path}") from exc
        require(b"\0" not in payload, f"{label} text receipt contains NUL bytes: {path}")
        return
    try:
        artifact = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} report artifact is not valid UTF-8 JSON: {path}") from exc
    require(isinstance(artifact, dict), f"{label} report artifact is not an object: {path}")
    require(
        artifact.get("schema") in expected_schemas,
        f"{label} report artifact schema mismatch for {path}",
    )
    if path == (LOCAL_REL / "finding-proposals.json").as_posix():
        validate_proposal_report_artifact(artifact, label=label)
    elif path == (LOCAL_REL / "crosswalk/occurrence-evaluations.json").as_posix():
        validate_evaluation_input_artifact(artifact, label=label)
    elif path == (LOCAL_REL / "crosswalk/receipt.json").as_posix():
        validate_q0_receipt_artifact(artifact, label=label)
    if slice_match is not None and path not in REPORT_ARTIFACT_SCHEMAS:
        validate_slice_handoff(
            artifact,
            path=path,
            slice_id=slice_match.group(1),
            expected_candidate=expected_candidate,
            label=label,
        )


def validate_proposal_report_artifact(artifact: dict[str, Any], *, label: str) -> None:
    """Check the complete-ID/occurrence report shape without treating it as proof."""
    require(artifact.get("schema") == SCHEMA, f"{label} proposal report schema mismatch")
    required = {
        "source_boundary",
        "denominator",
        "route_census",
        "evaluation_mode",
        "formal_closure_ids",
        "findings",
        "p40_review_contract",
    }
    require(required <= set(artifact), f"{label} proposal report is incomplete")
    require(
        artifact.get("formal_closure_ids") == [],
        f"{label} proposal report cannot claim formal G closures",
    )
    denominator = artifact.get("denominator")
    rows = artifact.get("findings")
    require(
        isinstance(denominator, dict) and isinstance(rows, list),
        f"{label} proposal denominator/findings are invalid",
    )
    require(
        set(denominator) == {"bundles", "finding_ids", "canonical_occurrences"},
        f"{label} proposal denominator fields are invalid",
    )
    require(
        all(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0
            for value in denominator.values()
        ),
        f"{label} proposal denominator counts are invalid",
    )
    ids = [row.get("finding_id") for row in rows if isinstance(row, dict)]
    require(
        len(ids) == len(rows) and all(isinstance(value, str) and value for value in ids),
        f"{label} proposal finding rows are invalid",
    )
    require(
        len(ids) == len(set(ids)) == denominator["finding_ids"],
        f"{label} proposal finding-ID denominator mismatch",
    )
    total_occurrences = 0
    seen_pointers: set[str] = set()
    for row in rows:
        occurrences = row.get("occurrences")
        require(isinstance(occurrences, list), f"{label} proposal occurrences missing")
        total_occurrences += len(occurrences)
        for occurrence in occurrences:
            original = occurrence.get("original") if isinstance(occurrence, dict) else None
            evaluation = (
                occurrence.get("candidate_evaluation") if isinstance(occurrence, dict) else None
            )
            property_refs = (
                occurrence.get("original_property_refs") if isinstance(occurrence, dict) else None
            )
            require(
                isinstance(original, dict) and isinstance(evaluation, dict),
                f"{label} proposal occurrence/source evaluation is invalid",
            )
            require(
                isinstance(property_refs, dict),
                f"{label} proposal occurrence property boundary is missing",
            )
            pointer, digest = original.get("occurrence_pointer"), original.get("sha256")
            require(
                isinstance(pointer, str) and pointer and pointer not in seen_pointers,
                f"{label} proposal occurrence pointer is missing or duplicated",
            )
            require(
                isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
                f"{label} proposal original criterion hash is invalid",
            )
            seen_pointers.add(pointer)
            require(
                evaluation.get("state") in OUTCOME_STATES | {"UNRUN"},
                f"{label} proposal occurrence state is invalid",
            )
            boundary = property_refs.get("criterion_specific_acceptance_boundary")
            require(
                isinstance(boundary, dict)
                and boundary.get("kind") == "original_source_span_and_pinned_owner_row"
                and isinstance(boundary.get("coverage_row_pointer"), str)
                and isinstance(boundary.get("coverage_field_refs"), list)
                and boundary.get("acceptance_boundary_state")
                in {
                    "coverage_specific_unexecuted_boundary_present",
                    "original_source_span_only",
                }
                and boundary.get("criterion_source_ref") == "#/criterion_source"
                and boundary.get("coverage_occurrence_ref") == "#/criterion_occurrence"
                and isinstance(boundary.get("owner_binding_state"), str)
                and boundary.get("owner_crosswalk_ref") == "#/author_crosswalk/refs"
                and boundary.get("owner_source_catalog_ref")
                == "/source_boundary/author_source_catalog"
                and isinstance(boundary.get("owner_field_roles"), list)
                and isinstance(boundary.get("owner_property_roles"), list)
                and isinstance(boundary.get("owner_mapping_not_established"), bool)
                and boundary.get("owner_property_boundary_state")
                in {
                    "source_property_or_consumer_ref_present",
                    "not_established_by_author_crosswalk",
                }
                and isinstance(boundary.get("coverage_source_ref"), str),
                f"{label} source-specific property/owner boundary is invalid",
            )
    require(
        total_occurrences == denominator["canonical_occurrences"],
        f"{label} proposal occurrence denominator mismatch",
    )
    require(
        artifact.get("evaluation_mode")
        in {
            "provisional_author_review_pending_final_source_freeze",
            "frozen_candidate_explicit_occurrence_updates",
        },
        f"{label} proposal evaluation mode is invalid",
    )


def validate_evaluation_input_artifact(artifact: dict[str, Any], *, label: str) -> None:
    """Require explicit occurrence rows, never aggregate or task-level evaluation markers."""
    require(
        artifact.get("schema") == EVALUATION_SCHEMA, f"{label} evaluation input schema mismatch"
    )
    require(
        set(artifact) == {"schema", "frozen_context", "evaluations"},
        f"{label} evaluation input has unknown or missing top-level fields",
    )
    context = artifact.get("frozen_context")
    require(isinstance(context, dict), f"{label} frozen_context is required")
    require(
        set(context)
        == {
            "candidate_source",
            "source_footprint_ref",
            "source_footprint_sha256",
        },
        f"{label} frozen_context fields are invalid",
    )
    candidate = context.get("candidate_source")
    require(
        isinstance(candidate, dict)
        and set(candidate) == {"commit", "tree"}
        and all(
            isinstance(candidate.get(key), str)
            and re.fullmatch(r"[0-9a-f]{40}", candidate[key]) is not None
            for key in ("commit", "tree")
        ),
        f"{label} frozen candidate SHA/tree are invalid",
    )
    require(
        context.get("source_footprint_ref")
        == "/source_boundary/source_freeze/source_change_census",
        f"{label} does not bind the recomputed full source footprint",
    )
    require(
        isinstance(context.get("source_footprint_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", context["source_footprint_sha256"]) is not None,
        f"{label} full source-footprint digest is invalid",
    )
    rows = artifact.get("evaluations")
    require(isinstance(rows, list), f"{label} evaluations must be an array")
    seen: set[tuple[str, str]] = set()
    for row in rows:
        require(isinstance(row, dict), f"{label} evaluation row must be an object")
        required_row_fields = {
            "occurrence_pointer",
            "sha256",
            "candidate_source",
            "state",
            "result_summary",
            "boundary",
            "execution_context",
            "evidence_refs",
            "attempts",
            "next_check",
            "review_escape",
        }
        allowed_row_fields = required_row_fields | {
            "proposal_disposition",
            "limitation",
            "falsifier",
            "missing_input",
            "new_defining_property_counterexample",
        }
        require(
            required_row_fields <= set(row) <= allowed_row_fields,
            f"{label} evaluation row has unknown or missing fields",
        )
        pointer, digest = row.get("occurrence_pointer"), row.get("sha256")
        require(
            isinstance(pointer, str)
            and pointer
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            f"{label} evaluation must identify an exact source occurrence",
        )
        key = (pointer, digest)
        require(key not in seen, f"{label} evaluation occurrence is duplicated")
        seen.add(key)
        require(row.get("state") in OUTCOME_STATES, f"{label} evaluation state is invalid")
        require(
            row.get("candidate_source") == candidate,
            f"{label} evaluation candidate differs from frozen_context",
        )
        execution_context = row.get("execution_context")
        require(
            isinstance(execution_context, dict), f"{label} occurrence execution_context is missing"
        )
        require(
            isinstance(execution_context.get("typed_slice_receipt_evidence_indexes"), list)
            and bool(execution_context["typed_slice_receipt_evidence_indexes"]),
            f"{label} occurrence must bind at least one typed slice receipt",
        )


def validate_evaluation_frozen_context(
    artifact: dict[str, Any], expected: dict[str, Any], *, label: str
) -> None:
    """Bind a syntactically valid update to the root-approved complete freeze."""
    require(
        artifact.get("frozen_context") == expected,
        f"{label} frozen_context differs from the root candidate/complete source footprint",
    )


def validate_q0_receipt_artifact(artifact: dict[str, Any], *, label: str) -> None:
    """Require a report receipt to bind its ledger, source checkpoint, and zero closures."""
    require(artifact.get("schema") == Q0_RECEIPT_SCHEMA, f"{label} Q0 receipt schema mismatch")
    checkpoint = artifact.get("source_checkpoint")
    require(
        isinstance(checkpoint, dict)
        and all(
            isinstance(checkpoint.get(key), str) and checkpoint.get(key)
            for key in ("commit", "tree", "branch")
        ),
        f"{label} receipt source checkpoint is incomplete",
    )
    require(
        artifact.get("source_freeze_status")
        in {
            "provisional_source_checkpoint_not_frozen",
            "frozen_candidate",
        },
        f"{label} receipt source-freeze status is invalid",
    )
    ledger = artifact.get("ledger")
    require(
        isinstance(ledger, dict)
        and ledger.get("path") == (LOCAL_REL / "finding-proposals.json").as_posix()
        and isinstance(ledger.get("sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", ledger["sha256"]) is not None,
        f"{label} receipt does not bind the canonical ledger",
    )
    require(isinstance(ledger.get("denominator"), dict), f"{label} receipt denominator is missing")
    require(
        ledger.get("formal_closure_ids") == [], f"{label} receipt cannot claim formal G closures"
    )


def local_raw_path_parts(path: str, *, label: str) -> tuple[str, ...]:
    """Validate a repository-relative, traversal-free path below the ignored LOCAL/raw root."""
    require(isinstance(path, str) and path, f"{label} raw path is required")
    require(
        "\0" not in path and "\\" not in path and not path.startswith("/"),
        f"{label} raw path must be a repository-relative POSIX path",
    )
    parts = tuple(path.split("/"))
    require(
        all(part not in {"", ".", ".."} for part in parts),
        f"{label} raw path contains an empty, dot, or traversal component",
    )
    prefix_parts = tuple((LOCAL_REL / "raw").parts)
    require(
        parts[: len(prefix_parts)] == prefix_parts and len(parts) > len(prefix_parts),
        f"{label} raw path must be below {LOCAL_RAW_PREFIX}",
    )
    return parts


def validate_command_output_ref_shape(
    output_ref: dict[str, Any],
    *,
    candidate_source: dict[str, str],
    label: str,
) -> None:
    """Keep Git-backed refs defaulted while requiring explicit ignored-raw provenance."""
    require(isinstance(output_ref, dict), f"{label} output ref must be an object")
    path, digest = output_ref.get("path"), output_ref.get("sha256")
    require(isinstance(path, str) and path, f"{label} output ref path is required")
    require(
        isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
        f"{label} output ref SHA-256 is invalid",
    )
    storage = output_ref.get("storage")
    is_local_raw = path.startswith(LOCAL_RAW_PREFIX)
    if is_local_raw or storage == LOCAL_RAW_STORAGE:
        require(
            storage == LOCAL_RAW_STORAGE, f"{label} ignored LOCAL/raw output needs explicit storage"
        )
        local_raw_path_parts(path, label=label)
        require(
            set(output_ref)
            == {
                "storage",
                "path",
                "sha256",
                "candidate_source",
                "availability",
            },
            f"{label} ignored raw output fields are incomplete or unknown",
        )
        require(
            output_ref.get("candidate_source") == candidate_source,
            f"{label} ignored raw output differs from the frozen candidate source",
        )
        require(
            output_ref.get("availability") == "available_local_readback",
            f"{label} ignored raw output must declare available local readback",
        )
    else:
        require(storage is None or storage == "git_blob", f"{label} output storage is invalid")


def local_raw_target(root: Path, path: str, *, label: str) -> tuple[Path, os.stat_result]:
    """Resolve a present regular non-symlink raw output strictly beneath the repository root."""
    parts = local_raw_path_parts(path, label=label)
    resolved_root = root.resolve(strict=True)
    current = resolved_root
    last_status: os.stat_result | None = None
    for index, component in enumerate(parts):
        current = current / component
        try:
            status = current.lstat()
        except OSError as exc:
            raise ValueError(f"{label} ignored raw output is unavailable: {path}") from exc
        require(
            not stat.S_ISLNK(status.st_mode),
            f"{label} ignored raw output path contains a symlink: {path}",
        )
        if index < len(parts) - 1:
            require(
                stat.S_ISDIR(status.st_mode),
                f"{label} ignored raw output parent is not a directory: {path}",
            )
        last_status = status
    require(
        last_status is not None and stat.S_ISREG(last_status.st_mode),
        f"{label} ignored raw output must be a regular file: {path}",
    )
    try:
        resolved_target = current.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"{label} ignored raw output is unavailable: {path}") from exc
    require(
        resolved_target.is_relative_to(resolved_root),
        f"{label} ignored raw output resolves outside the repository: {path}",
    )
    return current, last_status


def validate_local_raw_output(
    root: Path,
    output_ref: dict[str, Any],
    *,
    candidate_source: dict[str, str],
    label: str,
    read_bytes: bool = False,
) -> bytes | None:
    """Verify an explicitly ignored raw output against the frozen tree and local bytes."""
    validate_command_output_ref_shape(
        output_ref,
        candidate_source=candidate_source,
        label=label,
    )
    path = output_ref["path"]
    target, path_status = local_raw_target(root, path, label=label)

    require(
        git_text(root, "rev-parse", f"{candidate_source['commit']}^{{tree}}")
        == candidate_source["tree"],
        f"{label} candidate source tree does not resolve",
    )
    committed_path = git_run(
        root,
        "cat-file",
        "-e",
        f"{candidate_source['commit']}:{path}",
        check=False,
        capture_output=True,
    )
    require(
        committed_path.returncode != 0,
        f"{label} ignored raw path is present in the candidate Git tree",
    )
    indexed_path = git_run(
        root,
        "ls-files",
        "--error-unmatch",
        "--",
        path,
        check=False,
        capture_output=True,
    )
    require(indexed_path.returncode != 0, f"{label} ignored raw path is tracked or staged")

    ignore_result = git_run(
        root,
        "check-ignore",
        "-v",
        "-z",
        "--no-index",
        "--stdin",
        input=path.encode("utf-8") + b"\0",
        check=False,
        capture_output=True,
    )
    require(
        ignore_result.returncode == 0, f"{label} raw path is not explicitly ignored by the checkout"
    )
    ignore_fields = ignore_result.stdout.split(b"\0")
    require(
        len(ignore_fields) == 5 and ignore_fields[-1] == b"",
        f"{label} ignore rule witness is malformed",
    )
    try:
        ignore_source, line_number, _pattern, ignored_path = (
            field.decode("utf-8") for field in ignore_fields[:4]
        )
    except UnicodeDecodeError as exc:
        raise ValueError(f"{label} ignore rule witness is not UTF-8") from exc
    require(
        ignored_path == path and line_number.isdecimal(),
        f"{label} ignore rule does not identify the exact raw path",
    )
    ignore_source_parts = tuple(ignore_source.split("/"))
    require(
        bool(ignore_source)
        and not ignore_source.startswith("/")
        and all(part not in {"", ".", ".."} for part in ignore_source_parts),
        f"{label} ignore rule source path is invalid",
    )
    try:
        ignore_source_blob = git_text(
            root, "rev-parse", f"{candidate_source['commit']}:{ignore_source}"
        )
        frozen_ignore_bytes = git_bytes(
            root, "show", f"{candidate_source['commit']}:{ignore_source}"
        )
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} ignore rule source is not frozen candidate input") from exc
    ignore_source_path = root.resolve(strict=True)
    for index, component in enumerate(ignore_source_parts):
        ignore_source_path = ignore_source_path / component
        try:
            ignore_source_status = ignore_source_path.lstat()
        except OSError as exc:
            raise ValueError(f"{label} ignore rule source is unavailable") from exc
        require(
            not stat.S_ISLNK(ignore_source_status.st_mode),
            f"{label} ignore rule source contains a symlink",
        )
        if index < len(ignore_source_parts) - 1:
            require(
                stat.S_ISDIR(ignore_source_status.st_mode),
                f"{label} ignore rule source parent is not a directory",
            )
    require(
        stat.S_ISREG(ignore_source_status.st_mode),
        f"{label} ignore rule source must be a regular tracked file",
    )
    require(
        ignore_source_path.read_bytes() == frozen_ignore_bytes
        and git_text(root, "rev-parse", f"{candidate_source['commit']}:{ignore_source}")
        == ignore_source_blob,
        f"{label} active ignore rule differs from the frozen candidate source",
    )

    no_follow = getattr(os, "O_NOFOLLOW", 0)
    require(
        no_follow != 0,
        f"{label} platform cannot safely read an ignored raw output without following symlinks",
    )
    actual_bytes: bytes | None = None
    try:
        descriptor = os.open(target, os.O_RDONLY | no_follow)
        with os.fdopen(descriptor, "rb") as stream:
            opened_status = os.fstat(stream.fileno())
            require(
                stat.S_ISREG(opened_status.st_mode)
                and (opened_status.st_dev, opened_status.st_ino)
                == (path_status.st_dev, path_status.st_ino),
                f"{label} ignored raw output changed during local readback",
            )
            _, rechecked_status = local_raw_target(root, path, label=label)
            require(
                (rechecked_status.st_dev, rechecked_status.st_ino)
                == (opened_status.st_dev, opened_status.st_ino),
                f"{label} ignored raw output path changed during local readback",
            )
            if read_bytes:
                actual_bytes = stream.read(4 * 1024 * 1024 + 1)
                require(
                    len(actual_bytes) <= 4 * 1024 * 1024,
                    f"{label} ignored raw JSON exceeds the 4 MiB bound",
                )
                actual_digest = sha256(actual_bytes)
            else:
                actual_digest = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as exc:
        raise ValueError(f"{label} ignored raw output is unavailable: {path}") from exc
    require(actual_digest == output_ref["sha256"], f"{label} ignored raw output SHA-256 mismatch")
    return actual_bytes


def decision_refs_by_occurrence(
    artifact: dict[str, Any],
    *,
    label: str,
) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    """Require distinct criterion-specific decision refs for every receipt occurrence."""
    bindings = artifact.get("proposal_occurrences")
    decisions = artifact.get("decision_refs")
    require(
        isinstance(bindings, list) and bool(bindings),
        f"{label} must bind at least one original occurrence",
    )
    require(
        isinstance(decisions, list) and bool(decisions),
        f"{label} must provide criterion-specific decision refs",
    )
    binding_by_cover: dict[tuple[str, str], tuple[str, str, str]] = {}
    for index, binding in enumerate(bindings):
        require(isinstance(binding, dict), f"{label} proposal occurrence is invalid: {index}")
        key = (
            binding.get("finding_id"),
            binding.get("occurrence_pointer"),
            binding.get("criterion_sha256"),
        )
        require(
            all(isinstance(part, str) and part for part in key)
            and re.fullmatch(r"[0-9a-f]{64}", key[2]) is not None,
            f"{label} proposal occurrence identity is invalid: {index}",
        )
        cover_key = (key[1], key[2])
        require(
            cover_key not in binding_by_cover,
            f"{label} occurrence cover is ambiguous or duplicated: {index}",
        )
        binding_by_cover[cover_key] = key

    mapped: dict[tuple[str, str, str], list[dict[str, Any]]] = {
        key: [] for key in binding_by_cover.values()
    }
    decision_identities: dict[tuple[str, str, str], set[str]] = {key: set() for key in mapped}
    for index, decision in enumerate(decisions):
        require(isinstance(decision, dict), f"{label} decision ref is invalid: {index}")
        require(
            decision.get("kind") in {"alternative", "prototype", "bounded_no_alternative"},
            f"{label} decision ref kind is invalid: {index}",
        )
        source_ref = decision.get("source_ref")
        require(isinstance(source_ref, dict), f"{label} decision source ref is invalid: {index}")
        covers = source_ref.get("covers")
        require(
            isinstance(covers, dict) and set(covers) == {"occurrence_pointer", "sha256"},
            f"{label} decision source must name one exact occurrence cover: {index}",
        )
        pointer, digest = covers.get("occurrence_pointer"), covers.get("sha256")
        require(
            isinstance(pointer, str)
            and pointer
            and isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            f"{label} decision cover identity is invalid: {index}",
        )
        key = binding_by_cover.get((pointer, digest))
        require(
            key is not None, f"{label} decision ref covers an unknown or forged criterion: {index}"
        )
        decision_identity = canonical_json_sha256(decision)
        require(
            decision_identity not in decision_identities[key],
            f"{label} contains an exact duplicate decision ref for {key[0]}",
        )
        decision_identities[key].add(decision_identity)
        mapped[key].append(decision)
    missing = [key for key, rows in mapped.items() if not rows]
    require(not missing, f"{label} decision refs do not cover every bound occurrence: {missing}")
    return mapped


def require_handoff_occurrence(
    artifact: dict[str, Any],
    *,
    finding_id: str,
    occurrence_pointer: str,
    criterion_sha256: str,
    label: str,
) -> None:
    """Bind a current evaluation to its exact ID, source pointer, and criterion hash."""
    require(
        {
            "finding_id": finding_id,
            "occurrence_pointer": occurrence_pointer,
            "criterion_sha256": criterion_sha256,
        }
        in artifact.get("proposal_occurrences", []),
        f"{label} does not bind the exact evaluated original criterion occurrence",
    )


def validate_slice_handoff(
    artifact: dict[str, Any],
    *,
    path: str,
    slice_id: str,
    expected_candidate: dict[str, str] | None,
    label: str,
) -> None:
    """Require the registered per-slice handoff shape and its frozen source identity."""
    require(
        artifact.get("schema") == SLICE_HANDOFF_SCHEMA,
        f"{label} slice handoff schema mismatch: {path}",
    )
    require(
        artifact.get("slice_id") == slice_id,
        f"{label} slice_id does not match its direct-child report path: {path}",
    )
    required_fields = {
        "slice_id",
        "slice_base",
        "candidate_source",
        "parents",
        "source_footprint",
        "selected_inputs",
        "backend_profile",
        "commands",
        "chain",
        "controls",
        "consumer_surface",
        "limitations",
        "decision_refs",
        "proposal_ids",
        "proposal_occurrences",
        "formal_closure_ids",
    }
    require(
        required_fields <= set(artifact), f"{label} slice handoff lacks mandatory fields: {path}"
    )
    for key in ("slice_base", "candidate_source"):
        value = artifact.get(key)
        require(
            isinstance(value, dict) and set(value) == {"commit", "tree"},
            f"{label} slice handoff {key} must contain commit and tree: {path}",
        )
        require(
            all(
                isinstance(value.get(field), str)
                and re.fullmatch(r"[0-9a-f]{40}", value[field]) is not None
                for field in ("commit", "tree")
            ),
            f"{label} slice handoff {key} SHAs are invalid: {path}",
        )
    require(
        isinstance(artifact.get("parents"), list),
        f"{label} slice handoff parents must be an array: {path}",
    )
    require(
        all(
            isinstance(parent, str) and re.fullmatch(r"[0-9a-f]{40}", parent)
            for parent in artifact["parents"]
        ),
        f"{label} slice handoff parent SHA is invalid: {path}",
    )
    footprint = artifact.get("source_footprint")
    require(
        isinstance(footprint, list) and bool(footprint),
        f"{label} slice handoff source_footprint must be non-empty: {path}",
    )
    require(
        all(
            isinstance(row, dict) and isinstance(row.get("path"), str) and row["path"]
            for row in footprint
        ),
        f"{label} slice handoff source_footprint rows need paths: {path}",
    )
    require(
        len({row["path"] for row in footprint}) == len(footprint),
        f"{label} slice handoff source_footprint duplicates a path: {path}",
    )
    for key in (
        "selected_inputs",
        "commands",
        "controls",
        "limitations",
        "decision_refs",
        "proposal_ids",
        "proposal_occurrences",
    ):
        require(
            isinstance(artifact.get(key), list),
            f"{label} slice handoff {key} must be an array: {path}",
        )
    proposal_ids = artifact["proposal_ids"]
    require(
        all(isinstance(value, str) and value for value in proposal_ids)
        and len(proposal_ids) == len(set(proposal_ids)),
        f"{label} slice handoff proposal_ids must be unique nonempty IDs: {path}",
    )
    occurrence_bindings = artifact["proposal_occurrences"]
    require(
        all(
            isinstance(row, dict)
            and set(row)
            == {
                "finding_id",
                "occurrence_pointer",
                "criterion_sha256",
            }
            for row in occurrence_bindings
        ),
        f"{label} occurrence bindings must name exact finding/source occurrences: {path}",
    )
    binding_keys = []
    for index, row in enumerate(occurrence_bindings):
        require(
            row.get("finding_id") in proposal_ids,
            f"{label} occurrence binding ID is absent from proposal_ids: {path}/{index}",
        )
        require(
            isinstance(row.get("occurrence_pointer"), str) and row["occurrence_pointer"].strip(),
            f"{label} occurrence pointer is missing: {path}/{index}",
        )
        require(
            isinstance(row.get("criterion_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", row["criterion_sha256"]) is not None,
            f"{label} occurrence criterion hash is invalid: {path}/{index}",
        )
        binding_keys.append((row["finding_id"], row["occurrence_pointer"], row["criterion_sha256"]))
    require(
        len(binding_keys) == len(set(binding_keys)),
        f"{label} slice handoff duplicates an occurrence binding: {path}",
    )
    require(
        set(proposal_ids) == {row["finding_id"] for row in occurrence_bindings},
        f"{label} proposal IDs do not equal occurrence-bound IDs: {path}",
    )
    commands = artifact["commands"]
    require(bool(commands), f"{label} slice handoff must carry deciding command rows: {path}")
    for index, command in enumerate(commands):
        require(
            isinstance(command, dict),
            f"{label} slice handoff command row must be an object: {path}/{index}",
        )
        argv = command.get("argv")
        require(
            (isinstance(argv, list) and bool(argv) and all(isinstance(part, str) for part in argv))
            or (isinstance(command.get("command"), str) and command["command"].strip()),
            f"{label} slice handoff command needs argv or command: {path}/{index}",
        )
        require(
            isinstance(command.get("cwd"), str) and command["cwd"].strip(),
            f"{label} slice handoff command needs a working directory: {path}/{index}",
        )
        status = command.get("status")
        require(
            isinstance(status, str) and status in COMMAND_OUTCOMES | {"UNRUN"},
            f"{label} slice handoff command status is invalid: {path}/{index}",
        )
        if status == "UNRUN":
            require(
                isinstance(command.get("unrun_reason"), str) and command["unrun_reason"].strip(),
                f"{label} slice handoff UNRUN command needs a reason: {path}/{index}",
            )
        else:
            for output_key in ("stdout_ref", "stderr_ref"):
                output_ref = command.get(output_key)
                validate_command_output_ref_shape(
                    output_ref,
                    candidate_source=artifact["candidate_source"],
                    label=f"{label} slice handoff {output_key}: {path}/{index}",
                )
    profile = artifact.get("backend_profile")
    require(
        isinstance(profile, dict)
        and set(profile)
        == {"backend_id", "profile_id", "environment_sha256", "environment_manifest_ref"},
        f"{label} slice handoff backend_profile fields are incomplete or unknown: {path}",
    )
    validate_command_output_ref_shape(
        profile["environment_manifest_ref"],
        candidate_source=artifact["candidate_source"],
        label=f"{label} backend environment manifest: {path}",
    )
    require(
        isinstance(artifact.get("chain"), dict) and bool(artifact["chain"]),
        f"{label} slice handoff chain must be a non-empty object: {path}",
    )
    require(
        isinstance(artifact.get("consumer_surface"), dict) and bool(artifact["consumer_surface"]),
        f"{label} slice handoff consumer_surface must be a non-empty object: {path}",
    )
    require(
        artifact.get("formal_closure_ids") == [],
        f"{label} slice handoff cannot claim formal G closures: {path}",
    )
    decision_refs_by_occurrence(artifact, label=f"{label} slice handoff {path}")
    if expected_candidate is not None:
        require(
            artifact.get("candidate_source") == expected_candidate,
            f"{label} slice handoff is not bound to the frozen candidate: {path}",
        )


def require_typed_report_changes(
    changes: list[tuple[str, str]],
    *,
    label: str,
    payload_for_path: Callable[[str], bytes | None],
    expected_candidate: dict[str, str] | None = None,
) -> list[str]:
    """Accept only exact typed report artifacts and named text receipts; other paths are source."""
    normalized = sorted({path for _, path in changes})
    for _, path in changes:
        validate_report_artifact(
            path,
            payload_for_path(path),
            label=label,
            expected_candidate=expected_candidate,
        )
    return normalized


def source_file_type(path: str) -> str:
    """Classify changed-path denominator by its literal filename suffix."""
    name = Path(path).name.lower()
    if name.endswith(".json.gz"):
        return "json.gz"
    suffix = Path(name).suffix.removeprefix(".")
    return suffix or "extensionless"


def complete_source_change_census(
    root: Path,
    *,
    original_entry_commit: str,
    candidate_commit: str,
    original_entry_tree: str,
    candidate_tree: str,
) -> dict[str, Any]:
    """Recompute the complete original-entry-to-candidate changed-path denominator."""
    require(
        re.fullmatch(r"[0-9a-f]{40}", original_entry_commit) is not None
        and re.fullmatch(r"[0-9a-f]{40}", candidate_commit) is not None,
        "source-change census commits must be full SHAs",
    )
    require(
        re.fullmatch(r"[0-9a-f]{40}", original_entry_tree) is not None
        and re.fullmatch(r"[0-9a-f]{40}", candidate_tree) is not None,
        "source-change census trees must be full SHAs",
    )
    require(
        git_text(root, "rev-parse", f"{original_entry_commit}^{{tree}}") == original_entry_tree,
        "source-change census original-entry tree mismatch",
    )
    require(
        git_text(root, "rev-parse", f"{candidate_commit}^{{tree}}") == candidate_tree,
        "source-change census candidate tree mismatch",
    )
    ensure_git_graph_authoritative(root, label="source-change census")
    ancestry = git_run(
        root,
        "merge-base",
        "--is-ancestor",
        original_entry_commit,
        candidate_commit,
        check=False,
    )
    require(
        ancestry.returncode == 0,
        "source-change census candidate is not descended from the original entry",
    )
    output = git_bytes(
        root,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        original_entry_commit,
        candidate_commit,
        "--",
    )
    changes = changes_from_name_status(output)
    path_records = [
        {"status": status, "path": path, "file_type": source_file_type(path)}
        for status, path in changes
    ]
    file_types = collections.Counter(record["file_type"] for record in path_records)
    status_path_bytes = "".join(
        f"{record['status']}\t{record['path']}\n" for record in path_records
    ).encode("utf-8")
    return {
        "command": [
            "git",
            "diff",
            "--name-status",
            "--no-renames",
            original_entry_commit,
            candidate_commit,
            "--",
        ],
        "base": {"commit": original_entry_commit, "tree": original_entry_tree},
        "candidate": {"commit": candidate_commit, "tree": candidate_tree},
        "changed_paths": len(path_records),
        "file_type_denominator": dict(sorted(file_types.items())),
        "ordered_status_path_sha256": sha256(status_path_bytes),
        "complete_paths": path_records,
    }


def verify_source_descendant(
    root: Path,
    *,
    frozen_commit: str,
    frozen_tree: str,
    descendant_commit: str,
) -> list[str]:
    """Reconcile the complete Git-tree delta after the frozen source checkpoint."""
    require(
        re.fullmatch(r"[0-9a-f]{40}", frozen_commit) is not None,
        "frozen candidate commit must be a full SHA",
    )
    require(
        re.fullmatch(r"[0-9a-f]{40}", frozen_tree) is not None,
        "frozen candidate tree must be a full SHA",
    )
    require(
        re.fullmatch(r"[0-9a-f]{40}", descendant_commit) is not None,
        "report checkout commit must be a full SHA",
    )
    ensure_git_graph_authoritative(root, label="source descendant")
    cache_key = (str(root.resolve()), frozen_commit, frozen_tree, descendant_commit)
    if cache_key in SOURCE_DESCENDANT_CACHE:
        return list(SOURCE_DESCENDANT_CACHE[cache_key])
    require(
        git_text(root, "rev-parse", f"{frozen_commit}^{{commit}}") == frozen_commit,
        "frozen candidate commit does not resolve",
    )
    require(
        git_text(root, "rev-parse", f"{frozen_commit}^{{tree}}") == frozen_tree,
        "frozen candidate tree does not match its commit",
    )
    ancestor = git_run(
        root,
        "merge-base",
        "--is-ancestor",
        frozen_commit,
        descendant_commit,
        check=False,
    )
    require(
        ancestor.returncode == 0,
        "report checkout is not descended from the frozen candidate source",
    )
    output = git_bytes(
        root,
        "diff",
        "--name-status",
        "--no-renames",
        "-z",
        frozen_commit,
        descendant_commit,
        "--",
    )
    changes = changes_from_name_status(output)

    def committed_payload(path: str) -> bytes | None:
        exists = git_run(
            root,
            "cat-file",
            "-e",
            f"{descendant_commit}:{path}",
            check=False,
            capture_output=True,
        )
        if exists.returncode != 0:
            return None
        return git_bytes(root, "show", f"{descendant_commit}:{path}")

    accepted_paths = require_typed_report_changes(
        changes,
        label="committed descendant",
        payload_for_path=committed_payload,
        expected_candidate={"commit": frozen_commit, "tree": frozen_tree},
    )
    SOURCE_DESCENDANT_CACHE[cache_key] = list(accepted_paths)
    return accepted_paths


def worktree_changes(root: Path) -> list[tuple[str, str]]:
    """Collect complete staged, unstaged, and untracked paths with status."""
    raw = git_run(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        check=True,
        capture_output=True,
    )
    raw = raw.stdout
    changes: list[tuple[str, str]] = []
    records = raw.decode("utf-8").split("\0")
    for record in records:
        if not record:
            continue
        require(len(record) >= 4, f"unexpected porcelain status row: {record!r}")
        status = record[:2].strip() or "?"
        path = record[3:]
        # A rename record has a second NUL-delimited path. Renames are not an
        # exemption; record both sides so the old and new names are classified.
        if status in {"R", "C"}:
            require(False, f"rename/copy status is not allowed in source-freeze delta: {record!r}")
        changes.append((status, path))
    return changes


def validate_source_freeze(
    root: Path,
    *,
    report_checkout: object,
    current_head: str,
    current_branch: str | None,
    include_worktree: bool,
    provisional: bool = False,
) -> dict[str, Any]:
    """Bind final receipts to a full-tree candidate or label a provisional source checkpoint."""
    require(isinstance(report_checkout, dict), "report checkout anchor must be an object")
    require(
        set(report_checkout) == {"commit", "tree", "branch"},
        "report checkout anchor must contain commit, tree, and branch",
    )
    commit, tree, branch = (
        report_checkout.get("commit"),
        report_checkout.get("tree"),
        report_checkout.get("branch"),
    )
    require(
        isinstance(commit, str) and isinstance(tree, str),
        "report checkout commit/tree are required",
    )
    require(isinstance(branch, str) and branch, "report checkout must name an attached branch")
    require(current_branch == branch, "current branch differs from frozen report branch")
    committed_receipt_paths = verify_source_descendant(
        root,
        frozen_commit=commit,
        frozen_tree=tree,
        descendant_commit=current_head,
    )
    worktree_changes_rows = worktree_changes(root) if include_worktree and not provisional else []

    def worktree_payload(path: str) -> bytes | None:
        current_path = root / path
        require(not current_path.is_symlink(), f"report artifact cannot be a symlink: {path}")
        return current_path.read_bytes() if current_path.is_file() else None

    worktree_receipt_paths = require_typed_report_changes(
        worktree_changes_rows,
        label="index/worktree/untracked",
        payload_for_path=worktree_payload,
        expected_candidate={"commit": commit, "tree": tree},
    )
    boot0_bytes = git_bytes(root, "show", f"{commit}:{BOOT0_PATH.as_posix()}")
    try:
        boot0 = json.loads(boot0_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("frozen source BOOT0 input is not valid UTF-8 JSON") from exc
    require(isinstance(boot0, dict), "frozen source BOOT0 input is not an object")
    original_entry_commit = boot0.get("slice_base_sha")
    original_entry_tree = boot0.get("candidate_tree_sha")
    require(isinstance(original_entry_commit, str), "BOOT0 original entry commit missing")
    require(isinstance(original_entry_tree, str), "BOOT0 original entry tree missing")
    source_change_census = complete_source_change_census(
        root,
        original_entry_commit=original_entry_commit,
        candidate_commit=commit,
        original_entry_tree=original_entry_tree,
        candidate_tree=tree,
    )
    validator_path = Path(__file__).resolve().relative_to(root).as_posix()
    validator_bytes = (root / validator_path).read_bytes()
    return {
        "status": "provisional_source_checkpoint_not_frozen" if provisional else "frozen_candidate",
        "candidate_source": {"commit": commit, "tree": tree},
        "closure": {
            "kind": "provisional_checkpoint_no_source_closure"
            if provisional
            else SOURCE_CLOSURE_KIND,
            "tree": tree,
            "typed_report_artifact_schemas": REPORT_ARTIFACT_SCHEMAS,
            "slice_handoff_path_pattern": SLICE_HANDOFF_PATH.pattern,
            "slice_handoff_schema": SLICE_HANDOFF_SCHEMA,
            "text_receipt_paths": sorted(REPORT_TEXT_RECEIPTS),
            "policy": (
                SOURCE_FREEZE_POLICY
                if not provisional
                else (
                    "Provisional author crosswalk only. Worktree source deltas are not reconciled, "
                    "no runtime outcomes are admitted, and this checkpoint is not a candidate "
                    "source freeze."
                )
            ),
        },
        "validator": {"path": validator_path, "sha256": sha256(validator_bytes)},
        "source_change_census": source_change_census,
        "descendant_check": {
            "current_head": current_head,
            "committed_receipt_paths": committed_receipt_paths,
            "worktree_receipt_paths": worktree_receipt_paths,
            "worktree_source_deltas_reconciled": not provisional,
        },
    }


def resolve_pointer(document: object, pointer: str) -> object:
    """Resolve a JSON Pointer, accepting the ``#`` form used in handoffs."""
    normalized = pointer.split("#", 1)[-1]
    if normalized in {"", "/"}:
        return document
    require(normalized.startswith("/"), f"invalid JSON Pointer: {pointer}")
    current = document
    for raw_part in normalized[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            require(part.isdigit(), f"invalid array index in JSON Pointer: {pointer}")
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise ValueError(f"JSON Pointer traverses a scalar: {pointer}")
    return current


def sha256(data: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def canonical_json_sha256(value: object) -> str:
    """Hash a JSON value with a stable, whitespace-independent encoding."""
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256(encoded)


def load_canonical_json_object(data: bytes, *, label: str) -> dict[str, Any]:
    """Decode a canonical JSON object while refusing duplicate keys and non-finite values."""

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require(key not in result, f"{label} JSON contains duplicate key: {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError(f"{label} JSON contains non-finite number {value}")

    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc
    require(isinstance(value, dict), f"{label} must be a JSON object")
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    require(
        data == canonical,
        f"{label} must use canonical JSON encoding without a trailing newline",
    )
    return value


def normalized_environment_inputs(value: object, *, label: str) -> list[dict[str, Any]]:
    """Return the complete, identity-sorted selected-input denominator."""
    require(isinstance(value, list), f"{label} selected_inputs must be an array")
    normalized: list[dict[str, Any]] = []
    identities: set[str] = set()
    for index, row in enumerate(value):
        require(isinstance(row, dict), f"{label} selected input row is invalid: {index}")
        identity = row.get("identity")
        status = row.get("status")
        require(
            isinstance(identity, str) and identity.strip(),
            f"{label} selected input identity is missing: {index}",
        )
        require(
            identity not in identities,
            f"{label} selected input identity is duplicated: {identity}",
        )
        identities.add(identity)
        require(
            isinstance(status, str) and status in {"available", "unavailable"},
            f"{label} selected input status is invalid",
        )
        digest = row.get("sha256")
        if status == "available":
            require(
                isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
                f"{label} available input lacks its content hash: {index}",
            )
        else:
            require(
                digest is None,
                f"{label} unavailable input must not claim content bytes: {index}",
            )
        normalized.append({"identity": identity, "status": status, "sha256": digest})
    return sorted(normalized, key=lambda row: row["identity"])


def validate_environment_manifest_bytes(
    data: bytes,
    handoff: dict[str, Any],
    *,
    candidate_source: dict[str, str],
    label: str,
) -> dict[str, Any]:
    """Recompute and reconcile a canonical backend environment manifest."""
    manifest = load_canonical_json_object(data, label=f"{label} environment manifest")
    expected_fields = {
        "schema",
        "candidate_source",
        "backend_id",
        "profile_id",
        "source_refs",
        "runtime",
        "platform",
        "loaded_import_origins",
        "environment_settings",
        "command_runs",
        "selected_inputs",
        "selected_input_denominator_sha256",
    }
    require(
        set(manifest) == expected_fields,
        f"{label} environment manifest fields are incomplete or unknown",
    )
    profile = handoff.get("backend_profile")
    require(isinstance(profile, dict), f"{label} backend_profile must be an object")
    require(
        set(profile)
        == {"backend_id", "profile_id", "environment_sha256", "environment_manifest_ref"},
        f"{label} backend_profile fields are incomplete or unknown",
    )
    require(
        manifest.get("schema") == ENVIRONMENT_MANIFEST_SCHEMA,
        f"{label} environment manifest schema mismatch",
    )
    require(
        manifest.get("candidate_source") == candidate_source,
        f"{label} environment manifest candidate source mismatch",
    )
    for key in ("backend_id", "profile_id"):
        value = profile.get(key)
        require(
            isinstance(value, str) and value.strip(),
            f"{label} backend profile {key} is missing",
        )
        require(manifest.get(key) == value, f"{label} environment manifest {key} mismatch")
    digest = sha256(data)
    require(
        profile.get("environment_sha256") == digest,
        f"{label} backend environment SHA-256 does not match the manifest bytes",
    )
    manifest_ref = profile.get("environment_manifest_ref")
    require(isinstance(manifest_ref, dict), f"{label} environment manifest ref is missing")
    require(
        manifest_ref.get("sha256") == digest,
        f"{label} environment manifest ref SHA-256 does not match its bytes",
    )

    runtime = manifest.get("runtime")
    require(
        isinstance(runtime, dict) and set(runtime) == {"implementation", "version", "executable"},
        f"{label} environment runtime fields are incomplete or unknown",
    )
    require(
        all(isinstance(value, str) and value.strip() for value in runtime.values()),
        f"{label} environment runtime values must be non-empty strings",
    )
    platform = manifest.get("platform")
    require(
        isinstance(platform, dict) and set(platform) == {"system", "release", "machine"},
        f"{label} environment platform fields are incomplete or unknown",
    )
    require(
        all(isinstance(value, str) and value.strip() for value in platform.values()),
        f"{label} environment platform values must be non-empty strings",
    )

    origins = manifest.get("loaded_import_origins")
    require(
        isinstance(origins, list) and bool(origins),
        f"{label} loaded import origins are required",
    )
    origin_modules: set[str] = set()
    for index, origin in enumerate(origins):
        require(
            isinstance(origin, dict) and set(origin) == {"module", "origin", "package_version"},
            f"{label} loaded import origin fields are invalid: {index}",
        )
        module = origin.get("module")
        require(
            isinstance(module, str) and module.strip() and module not in origin_modules,
            f"{label} loaded import origin module is missing or duplicated: {index}",
        )
        require(
            all(
                isinstance(origin.get(key), str) and origin[key].strip()
                for key in ("origin", "package_version")
            ),
            f"{label} loaded import origin lacks its path or package version: {index}",
        )
        origin_modules.add(module)

    settings = manifest.get("environment_settings")
    require(isinstance(settings, dict), f"{label} environment_settings must be an object")
    secret_name = re.compile(
        r"(?:token|secret|password|credential|private[_-]?key|authorization)", re.I
    )
    for key, value in settings.items():
        require(
            isinstance(key, str) and key.strip(),
            f"{label} environment setting name is invalid",
        )
        require(
            secret_name.search(key) is None,
            f"{label} environment setting appears to name secret material: {key}",
        )
        require(
            value is None or isinstance(value, (str, bool, int)),
            f"{label} environment setting must be a non-secret JSON scalar: {key}",
        )

    footprint = handoff.get("source_footprint")
    require(isinstance(footprint, list), f"{label} source footprint is missing")
    footprint_hashes = {
        row.get("path"): row.get("sha256") for row in footprint if isinstance(row, dict)
    }
    source_refs = manifest.get("source_refs")
    require(
        isinstance(source_refs, list) and bool(source_refs),
        f"{label} source refs are required",
    )
    source_paths: set[str] = set()
    source_roles: set[str] = set()
    for index, ref in enumerate(source_refs):
        require(
            isinstance(ref, dict) and set(ref) == {"path", "role", "sha256"},
            f"{label} environment source ref fields are invalid: {index}",
        )
        path, role, source_digest = ref.get("path"), ref.get("role"), ref.get("sha256")
        require(
            isinstance(path, str) and path and path not in source_paths,
            f"{label} environment source path is missing or duplicated: {index}",
        )
        require(
            isinstance(role, str) and role in {"backend_recipe", "configuration", "lockfile"},
            f"{label} environment source role is invalid: {index}",
        )
        require(
            isinstance(source_digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", source_digest) is not None
            and footprint_hashes.get(path) == source_digest,
            f"{label} environment source ref is not bound to the candidate footprint: {path}",
        )
        source_paths.add(path)
        source_roles.add(role)
    require(
        "backend_recipe" in source_roles and bool(source_roles & {"configuration", "lockfile"}),
        f"{label} environment source refs must bind a backend recipe and a config or lockfile",
    )

    normalized_inputs = normalized_environment_inputs(
        handoff.get("selected_inputs"), label=f"{label} handoff"
    )
    manifest_inputs = manifest.get("selected_inputs")
    require(
        manifest_inputs == normalized_inputs,
        f"{label} environment manifest selected inputs differ from the handoff denominator",
    )
    require(
        manifest.get("selected_input_denominator_sha256")
        == canonical_json_sha256(normalized_inputs),
        f"{label} environment selected-input denominator hash mismatch",
    )

    commands = handoff.get("commands")
    command_runs = manifest.get("command_runs")
    require(
        isinstance(commands, list)
        and isinstance(command_runs, list)
        and len(command_runs) == len(commands),
        f"{label} environment command rows do not cover the complete command denominator",
    )
    for index, (command, run) in enumerate(zip(commands, command_runs, strict=True)):
        require(
            isinstance(command, dict) and isinstance(run, dict),
            f"{label} command row is invalid",
        )
        argv = command.get("argv")
        command_text = command.get("command")
        has_argv = (
            isinstance(argv, list) and bool(argv) and all(isinstance(part, str) for part in argv)
        )
        has_command = isinstance(command_text, str) and bool(command_text.strip())
        require(
            has_argv != has_command,
            f"{label} command must use exactly one argv or command form",
        )
        cwd = command.get("cwd")
        require(isinstance(cwd, str) and cwd.strip(), f"{label} command cwd is required: {index}")
        status = command.get("status")
        expected_run: dict[str, Any] = {
            "command_index": index,
            "cwd": cwd,
            "status": status,
        }
        if has_argv:
            expected_run["argv"] = argv
        else:
            expected_run["command"] = command_text
        if status == "UNRUN":
            reason = command.get("unrun_reason")
            require(
                isinstance(reason, str) and reason.strip(),
                f"{label} UNRUN command needs a reason",
            )
            expected_run["unrun_reason"] = reason
        else:
            require(
                isinstance(status, str) and status in COMMAND_OUTCOMES,
                f"{label} command status is invalid: {index}",
            )
            for output_key in ("stdout_ref", "stderr_ref"):
                output_ref = command.get(output_key)
                require(isinstance(output_ref, dict), f"{label} command {output_key} is missing")
                expected_run[f"{output_key.removesuffix('_ref')}_sha256"] = output_ref.get("sha256")
        require(
            run == expected_run,
            f"{label} environment command row differs from the handoff at index {index}",
        )
    return manifest


def validate_backend_environment_manifest(
    root: Path,
    handoff: dict[str, Any],
    *,
    candidate_source: dict[str, str],
    label: str,
) -> dict[str, Any]:
    """Read the source-bound ignored manifest and validate its exact bytes and contents."""
    profile = handoff.get("backend_profile")
    require(isinstance(profile, dict), f"{label} backend_profile must be an object")
    manifest_ref = profile.get("environment_manifest_ref")
    validate_command_output_ref_shape(
        manifest_ref,
        candidate_source=candidate_source,
        label=f"{label} backend environment manifest",
    )
    require(
        manifest_ref.get("storage") == LOCAL_RAW_STORAGE,
        f"{label} environment manifest must be an available ignored LOCAL/raw artifact",
    )
    manifest_bytes = validate_local_raw_output(
        root,
        manifest_ref,
        candidate_source=candidate_source,
        label=f"{label} backend environment manifest",
        read_bytes=True,
    )
    require(isinstance(manifest_bytes, bytes), f"{label} environment manifest bytes were not read")
    return validate_environment_manifest_bytes(
        manifest_bytes,
        handoff,
        candidate_source=candidate_source,
        label=label,
    )


def require_verified_evidence_roles(
    state: str,
    evidence_refs: list[dict[str, Any]],
    *,
    label: str,
) -> None:
    """Require defining-property, real consumer, and negative evidence for VERIFIED."""
    if state != "VERIFIED":
        return
    roles = {ref.get("role") for ref in evidence_refs}
    required_roles = {"property_positive", "actual_consumer", "negative"}
    require(
        required_roles <= roles,
        f"{label} VERIFIED evaluation needs occurrence-bound property-positive, actual-consumer, "
        "and negative evidence regardless of proposal disposition",
    )


def pinned_file_ref(
    root: Path,
    *,
    key: str,
    path: str,
    commit: str,
    expected_blob: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, str]:
    """Read and validate one tracked file at an immutable commit."""
    require(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, f"invalid commit for {key}")
    blob = git_text(root, "rev-parse", f"{commit}:{path}")
    require(expected_blob is None or blob == expected_blob, f"blob mismatch for {key}")
    data = git_bytes(root, "show", f"{commit}:{path}")
    digest = sha256(data)
    require(expected_sha256 is None or digest == expected_sha256, f"sha256 mismatch for {key}")
    return {
        "key": key,
        "path": path,
        "commit": commit,
        "git_blob": blob,
        "sha256": digest,
    }


def validate_pinned_evidence_ref(
    root: Path,
    raw_ref: object,
    *,
    occurrence_pointer: str,
    occurrence_sha256: str,
    candidate_source: dict[str, str],
    label: str,
) -> dict[str, Any]:
    """Verify a source-bound evidence ref for exactly one criterion occurrence."""
    require(isinstance(raw_ref, dict), f"{label} must be a source-bound object")
    path, commit = raw_ref.get("path"), raw_ref.get("commit")
    blob, digest = raw_ref.get("git_blob"), raw_ref.get("sha256")
    require(
        isinstance(path, str) and path and not path.startswith("/"),
        f"{label} path must be repository-relative",
    )
    require(
        isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
        f"{label} commit must be a full SHA",
    )
    require(
        isinstance(blob, str) and re.fullmatch(r"[0-9a-f]{40}", blob) is not None,
        f"{label} git_blob must be a full SHA",
    )
    require(
        isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
        f"{label} sha256 must be a full digest",
    )
    role = raw_ref.get("role")
    require(isinstance(role, str) and role.strip(), f"{label} role is required")
    covers = raw_ref.get("covers")
    require(isinstance(covers, dict), f"{label} covers object is required")
    require(
        covers.get("occurrence_pointer") == occurrence_pointer,
        f"{label} does not bind the exact occurrence pointer",
    )
    require(
        covers.get("sha256") == occurrence_sha256,
        f"{label} does not bind the exact occurrence hash",
    )
    require(
        raw_ref.get("candidate_source") == candidate_source,
        f"{label} candidate source differs from the evaluated candidate",
    )

    resolved_commit = git_text(root, "rev-parse", f"{commit}^{{commit}}")
    require(resolved_commit == commit, f"{label} evidence commit does not resolve")
    resolved_blob = git_text(root, "rev-parse", f"{commit}:{path}")
    require(resolved_blob == blob, f"{label} evidence Git blob mismatch")
    evidence_bytes = git_bytes(root, "show", f"{commit}:{path}")
    require(sha256(evidence_bytes) == digest, f"{label} evidence SHA-256 mismatch")
    ensure_git_graph_authoritative(root, label=label)
    descendant = git_run(
        root,
        "merge-base",
        "--is-ancestor",
        candidate_source["commit"],
        commit,
        check=False,
    )
    require(
        descendant.returncode == 0,
        f"{label} evidence predates or diverges from the frozen candidate source",
    )
    verify_source_descendant(
        root,
        frozen_commit=candidate_source["commit"],
        frozen_tree=candidate_source["tree"],
        descendant_commit=commit,
    )

    pointer = raw_ref.get("pointer")
    if pointer is not None:
        require(isinstance(pointer, str), f"{label} pointer must be a string")
        try:
            parsed = json.loads(evidence_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label} JSON Pointer targets a non-JSON file") from exc
        resolve_pointer(parsed, pointer)
    return dict(raw_ref)


def load_json(root: Path, path: Path) -> dict[str, Any]:
    """Read one JSON object from the repository worktree."""
    value = json.loads((root / path).read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"expected JSON object: {path}")
    return value


def index_unique(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    """Index rows by ID while rejecting duplicate IDs."""
    ids = [row.get("id") for row in rows]
    require(all(isinstance(value, str) and value for value in ids), f"invalid ID in {label}")
    require(len(ids) == len(set(ids)), f"duplicate ID in {label}")
    return {row["id"]: row for row in rows}


def load_pinned_json(
    root: Path,
    *,
    key: str,
    path: str,
    commit: str,
    expected_blob: str | None = None,
    expected_sha256: str | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Load one JSON source from Git and return its immutable catalog ref."""
    source_ref = pinned_file_ref(
        root,
        key=key,
        path=path,
        commit=commit,
        expected_blob=expected_blob,
        expected_sha256=expected_sha256,
    )
    parsed = json.loads(git_bytes(root, "show", f"{commit}:{path}").decode("utf-8"))
    require(isinstance(parsed, dict), f"pinned JSON source is not an object: {key}")
    return source_ref, parsed


def load_sources(
    root: Path,
    *,
    frozen_report_checkout: object | None = None,
    provisional: bool = False,
) -> dict[str, Any]:
    """Load and reconcile the pinned source documents for the ledger."""
    current_head = git_text(root, "rev-parse", "HEAD")
    branch_result = git_run(
        root,
        "symbolic-ref",
        "-q",
        "--short",
        "HEAD",
        capture_output=True,
        check=False,
    )
    current_branch = (
        branch_result.stdout.decode("utf-8").strip() if branch_result.returncode == 0 else None
    )
    if frozen_report_checkout is None:
        report_checkout = {
            "commit": current_head,
            "tree": git_text(root, "rev-parse", "HEAD^{tree}"),
            "branch": current_branch,
        }
    else:
        report_checkout = frozen_report_checkout
    source_freeze = validate_source_freeze(
        root,
        report_checkout=report_checkout,
        current_head=current_head,
        current_branch=current_branch,
        include_worktree=not provisional,
        provisional=provisional,
    )

    documents = {name: load_json(root, path) for name, path in INPUT_PATHS.items()}
    inputs = documents["inputs"]
    tasks = documents["tasks"]
    findings = documents["findings"]
    connected_inputs = documents["connected_inputs"]
    coverage = documents["coverage"]
    boot0 = load_json(root, BOOT0_PATH)

    source_manifest = connected_inputs["source_manifest"]
    author_sources: dict[str, dict[str, str]] = {}
    author_documents: dict[str, dict[str, Any]] = {}
    source_specs = {
        **source_manifest.get("current_author_rows", {}),
        "A_progress": source_manifest.get("A_progress"),
        "B_prior_decisions": source_manifest.get("B_prior_decisions"),
    }
    for source_key, spec in source_specs.items():
        require(isinstance(spec, dict), f"source manifest entry missing: {source_key}")
        source_ref, source_doc = load_pinned_json(
            root,
            key=source_key,
            path=spec["path"],
            commit=spec["git_ref"],
            expected_blob=spec["git_blob"],
        )
        require(
            len(git_bytes(root, "show", f"{spec['git_ref']}:{spec['path']}")) == spec["bytes"],
            f"author packet byte count mismatch: {source_key}",
        )
        author_sources[source_key] = source_ref
        author_documents[source_key] = source_doc

    b_packet = author_documents["B"]
    manual_locator = b_packet["refs"]["manual"]
    manual_path, manual_commit = manual_locator.rsplit("@", 1)
    manual_ref, manual_doc = load_pinned_json(
        root,
        key="B_manual",
        path=manual_path,
        commit=manual_commit,
        expected_blob=b_packet["refs"]["manual_blob"],
    )
    author_sources["B_manual"] = manual_ref
    author_documents["B_manual"] = manual_doc

    # E's row-level evidence locators name additional immutable source reports.
    e_packet = author_documents["E"]
    for input_key, spec in e_packet.get("inputs", {}).items():
        source_ref = pinned_file_ref(
            root,
            key=f"E_{input_key}",
            path=spec["path"],
            commit=spec["revision"],
            expected_sha256=spec["sha256"],
        )
        source_bytes = git_bytes(root, "show", f"{spec['revision']}:{spec['path']}")
        require(len(source_bytes) == spec["bytes"], f"E source byte count mismatch: {input_key}")
        author_sources[source_ref["key"]] = source_ref
        try:
            source_doc = json.loads(source_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            # E catalogs some diagnostic Markdown without row-fragment locators.
            # The immutable file ref is retained; it is not treated as parsed evidence.
            source_doc = None
        if source_doc is not None:
            require(
                isinstance(source_doc, dict), f"E source document is not an object: {input_key}"
            )
            author_documents[source_ref["key"]] = source_doc

    # D's current property/consumer/negative rows are separate from its proposal text.
    d_packet = author_documents["D"]
    d_catalog = d_packet.get("immutable_ref_catalog", {})
    if "G_actions" in d_catalog:
        spec = d_catalog["G_actions"]
        source_ref, source_doc = load_pinned_json(
            root,
            key="D_G_actions",
            path=spec["git_path"],
            commit=spec["git_ref"],
            expected_blob=spec["git_blob"],
            expected_sha256=spec["sha256"],
        )
        author_sources["D_G_actions"] = source_ref
        author_documents["D_G_actions"] = source_doc

    # F's per-ID carriers are immutable evidence packets too. Resolve the whole
    # catalog before building or validating the ledger so both passes compare
    # the same source denominator without mutating the snapshot mid-walk.
    for packet_row in author_documents["F"].get("rows", []):
        carrier = packet_row.get("deciding_per_ID_carrier_ref")
        if not isinstance(carrier, dict):
            continue
        finding_id = packet_row.get("finding_id")
        require(
            isinstance(finding_id, str) and finding_id,
            "F per-ID carrier row is missing its finding ID",
        )
        carrier_ref = pinned_file_ref(
            root,
            key=f"F_carrier_{finding_id}",
            path=carrier["path"],
            commit=carrier["git_ref"],
            expected_blob=carrier["git_blob"],
            expected_sha256=carrier["sha256"],
        )
        author_sources[carrier_ref["key"]] = carrier_ref

    head = report_checkout["commit"]
    original_entry_commit = boot0.get("slice_base_sha")
    original_entry_tree = boot0.get("candidate_tree_sha")
    require(
        isinstance(original_entry_commit, str)
        and re.fullmatch(r"[0-9a-f]{40}", original_entry_commit) is not None,
        "BOOT0 original entry commit must be a full SHA",
    )
    require(
        isinstance(original_entry_tree, str)
        and re.fullmatch(r"[0-9a-f]{40}", original_entry_tree) is not None,
        "BOOT0 original entry tree must be a full SHA",
    )
    require(
        git_text(root, "rev-parse", f"{original_entry_commit}^{{tree}}") == original_entry_tree,
        "BOOT0 original entry commit/tree mismatch",
    )
    ensure_git_graph_authoritative(root, label="BOOT0 source")
    ancestry = git_run(
        root,
        "merge-base",
        "--is-ancestor",
        original_entry_commit,
        head,
        check=False,
    )
    require(
        ancestry.returncode == 0,
        "report checkout is not descended from BOOT0 original entry",
    )
    boot0_bytes = (root / BOOT0_PATH).read_bytes()

    plan_path = EXECUTION_PLAN_PATH.as_posix()
    plan_worktree_bytes = (root / EXECUTION_PLAN_PATH).read_bytes()
    plan_entry_bytes = git_bytes(root, "show", f"{original_entry_commit}:{plan_path}")
    plan_report_bytes = git_bytes(root, "show", f"{head}:{plan_path}")
    require(
        plan_worktree_bytes == plan_entry_bytes == plan_report_bytes,
        "execution plan differs between original entry, report checkout, or worktree",
    )
    execution_plan_source = pinned_file_ref(
        root,
        key="execution_plan",
        path=plan_path,
        commit=original_entry_commit,
        expected_sha256=sha256(plan_entry_bytes),
    )

    closeout_support_sources = []
    for key, rel_path in SUPPORTING_TEXT_PATHS.items():
        worktree_bytes = (root / rel_path).read_bytes()
        entry_bytes = git_bytes(root, "show", f"{original_entry_commit}:{rel_path.as_posix()}")
        report_bytes = git_bytes(root, "show", f"{head}:{rel_path.as_posix()}")
        require(
            worktree_bytes == entry_bytes == report_bytes,
            f"closeout support source differs from original entry/report checkout: {rel_path}",
        )
        closeout_support_sources.append(
            pinned_file_ref(
                root,
                key=key,
                path=rel_path.as_posix(),
                commit=original_entry_commit,
                expected_sha256=sha256(entry_bytes),
            )
        )

    tracked_inputs: list[dict[str, str]] = []
    for name, rel_path in INPUT_PATHS.items():
        worktree_bytes = (root / rel_path).read_bytes()
        entry_bytes = git_bytes(root, "show", f"{original_entry_commit}:{rel_path.as_posix()}")
        head_bytes = git_bytes(root, "show", f"{head}:{rel_path.as_posix()}")
        require(
            worktree_bytes == entry_bytes == head_bytes,
            f"source input differs between original entry, report checkout, or "
            f"worktree: {rel_path}",
        )
        tracked_inputs.append(
            {
                "role": name,
                "path": rel_path.as_posix(),
                "original_entry_commit": original_entry_commit,
                "original_entry_blob": git_text(
                    root, "rev-parse", f"{original_entry_commit}:{rel_path.as_posix()}"
                ),
                "report_commit": head,
                "report_blob": git_text(root, "rev-parse", f"{head}:{rel_path.as_posix()}"),
                "sha256": sha256(worktree_bytes),
            }
        )

    # Coverage refs used by the author crosswalk resolve to this original-entry
    # file, not to an unpinned working-tree copy.
    coverage_input = next(row for row in tracked_inputs if row["role"] == "coverage")
    coverage_ref = pinned_file_ref(
        root,
        key="coverage",
        path=coverage_input["path"],
        commit=original_entry_commit,
        expected_blob=coverage_input["original_entry_blob"],
        expected_sha256=coverage_input["sha256"],
    )
    author_sources["coverage"] = coverage_ref
    author_documents["coverage"] = coverage

    author_rows = findings.get("rows", [])
    coverage_rows = coverage.get("findings", [])
    bundle_rows = coverage.get("bundles", [])
    author_by_id = index_unique(author_rows, "author findings")
    coverage_by_id = index_unique(coverage_rows, "coverage findings")
    coverage_index_by_id = {row["id"]: index for index, row in enumerate(coverage_rows)}
    require(
        set(author_by_id) == set(coverage_by_id),
        "original findings and closure coverage IDs differ",
    )

    tasks_by_id = tasks.get("tasks", {})
    require(isinstance(tasks_by_id, dict), "TASKS.tasks must be an object")
    routes: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for task_id, task in tasks_by_id.items():
        finding_ids = task.get("finding_ids", [])
        require(
            len(finding_ids) == len(set(finding_ids)),
            f"duplicate finding ID within task {task_id}",
        )
        for index, finding_id in enumerate(finding_ids):
            routes[finding_id].append(
                {
                    "task_id": task_id,
                    "task_pointer": f"{PACKET_REL.as_posix()}/TASKS.json#/tasks/{task_id}",
                    "assignment_pointer": (
                        f"{PACKET_REL.as_posix()}/TASKS.json#/tasks/{task_id}/finding_ids/{index}"
                    ),
                }
            )
    require(
        set(routes) == set(author_by_id),
        "current task routes do not cover exactly the original ID set",
    )
    require(
        tasks.get("all282routes_present") is True,
        "declared route flag is false; recomputed route union was complete",
    )
    current_task_ids = set(tasks_by_id)
    for row in author_rows:
        require(
            set(row.get("next_tasks", [])) <= current_task_ids,
            f"original route is missing for {row['id']}",
        )
    q0_ids = set(tasks_by_id.get("Q0", {}).get("finding_ids", []))
    declared_occurrence_count = sum(len(row.get("criterion_refs", [])) for row in coverage_rows)
    author_closed_ids = {row["id"] for row in author_rows if row.get("author_proposal") == "closed"}
    b198_coverage = coverage_by_id.get("B198")
    b198_author = author_by_id.get("B198")
    require(
        isinstance(b198_coverage, dict)
        and b198_coverage.get("ledger_status_historical") == "closed"
        and b198_coverage.get("appendix_c_status_separate") == "closed_bounded"
        and b198_coverage.get("closure_now") == "not_adjudicated"
        and isinstance(b198_author, dict)
        and b198_author.get("author_proposal") == "closed"
        and b198_author.get("G_closure") == "not_adjudicated",
        "B198 historical closed decision and separate current G status must remain distinct",
    )
    route_census = {
        "task_definitions": len(tasks_by_id),
        "route_assignments": sum(len(task.get("finding_ids", [])) for task in tasks_by_id.values()),
        "routed_finding_ids": len(routes),
        "route_gaps": len(set(author_by_id) - set(routes)),
        "ids_with_multiple_task_routes": sum(len(items) > 1 for items in routes.values()),
        "q0_finding_ids": len(q0_ids),
        "author_closed_ids": len(author_closed_ids),
        "author_closed_ids_on_q0": len(author_closed_ids & q0_ids),
        "author_closed_ids_missing_q0": sorted(author_closed_ids - q0_ids),
        "q0_nonclosed_ids": sorted(q0_ids - author_closed_ids),
        "q0_occurrences": sum(
            len(coverage_by_id[finding_id].get("criterion_refs", [])) for finding_id in q0_ids
        ),
        "author_proposal_counts": dict(
            collections.Counter(row.get("author_proposal") for row in author_rows)
        ),
        "basis": {
            "coverage": {
                "path": INPUT_PATHS["coverage"].as_posix(),
                "file_type": "JSON",
                "finding_ids": len(coverage_rows),
                "criterion_occurrences": declared_occurrence_count,
            },
            "author_findings": {
                "path": INPUT_PATHS["findings"].as_posix(),
                "file_type": "JSON",
                "finding_ids": len(author_rows),
                "criterion_occurrences": findings["denominator"]["criterion_occurrences"],
            },
            "task_routes": {
                "path": INPUT_PATHS["tasks"].as_posix(),
                "file_type": "JSON",
            },
        },
    }

    source_manifest = connected_inputs["source_manifest"]["original_criteria"]
    source_by_path = {source["path"]: source for source in source_manifest}
    criterion_sources: dict[str, dict[str, Any]] = {}
    for document, source in coverage["criterion_documents"].items():
        manifest = source_by_path[source["path"]]
        source_commit = manifest["git_ref"]
        source_path = source["path"]
        git_blob = git_text(root, "rev-parse", f"{source_commit}:{source_path}")
        require(
            git_blob == manifest["git_blob"] == source["blob"],
            f"source blob mismatch: {source_path}",
        )
        source_bytes = git_bytes(root, "show", f"{source_commit}:{source_path}")
        require(
            len(source_bytes.splitlines()) == manifest["line_count"],
            f"source line count mismatch: {source_path}",
        )
        criterion_sources[document] = {
            "document": document,
            "path": source_path,
            "file_type": manifest["file_type"],
            "source_commit": source_commit,
            "source_blob": git_blob,
            "source_sha256": sha256(source_bytes),
            "line_count": manifest["line_count"],
        }

    occurrence_count = 0
    for row in coverage_rows:
        finding_id = row["id"]
        refs = row.get("criterion_refs", [])
        occurrence_count += len(refs)
        author_row = author_by_id[finding_id]
        pointer_match = re.fullmatch(
            r"/findings/(\d+)/criterion_refs",
            author_row["original_criteria_pointer"],
        )
        require(pointer_match is not None, f"invalid original pointer: {finding_id}")
        pointer_index = int(pointer_match.group(1))
        require(
            coverage_rows[pointer_index]["id"] == finding_id,
            f"original pointer resolves to a different ID: {finding_id}",
        )
        for ref in refs:
            require(ref.get("criterion_id") == finding_id, f"criterion ID mismatch: {finding_id}")
            source = criterion_sources[ref["document"]]
            source_bytes = git_bytes(
                root,
                "show",
                f"{source['source_commit']}:{source['path']}",
            )
            lines = source_bytes.decode("utf-8").splitlines(keepends=True)
            start, end = ref["lines"]
            actual_digest = sha256("".join(lines[start - 1 : end]).encode("utf-8"))
            require(actual_digest == ref["sha256"], f"criterion block hash mismatch: {finding_id}")

    declared = tasks["original_denominator"]
    require(len(bundle_rows) == declared["bundles"], "bundle denominator mismatch")
    require(len(author_rows) == declared["findings"], "author finding denominator mismatch")
    require(len(coverage_rows) == declared["findings"], "coverage finding denominator mismatch")
    require(
        occurrence_count == declared["criterion_occurrences"], "occurrence denominator mismatch"
    )
    require(
        findings["denominator"]["criterion_occurrences"] == occurrence_count,
        "findings occurrence count mismatch",
    )
    require(
        coverage["denominator"]["canonical_source_block_occurrences"] == occurrence_count,
        "coverage occurrence count mismatch",
    )
    require(
        inputs.get("formal_closure_ids", []) == tasks.get("formal_closure_ids", []),
        "formal closure source fields disagree",
    )
    require(
        inputs.get("formal_closure_ids", []) == [],
        "this proposal ledger cannot carry formal closure IDs",
    )

    return {
        "inputs": inputs,
        "tasks": tasks,
        "findings": findings,
        "coverage": coverage,
        "author_by_id": author_by_id,
        "coverage_by_id": coverage_by_id,
        "coverage_index_by_id": coverage_index_by_id,
        "routes": routes,
        "route_census": route_census,
        "q0_ids": q0_ids,
        "criterion_sources": criterion_sources,
        "tracked_inputs": tracked_inputs,
        "execution_plan_source": execution_plan_source,
        "closeout_support_sources": closeout_support_sources,
        "author_sources": author_sources,
        "author_documents": author_documents,
        "original_entry": {
            "commit": original_entry_commit,
            "tree": original_entry_tree,
            "branch": boot0.get("branch"),
            "handoff_path": BOOT0_PATH.as_posix(),
            "handoff_sha256": sha256(boot0_bytes),
        },
        "report_checkout": report_checkout,
        "current_checkout": {"commit": current_head, "branch": current_branch},
        "source_freeze": source_freeze,
        "occurrence_count": occurrence_count,
        "repo_root": root,
    }


def initial_occurrence(
    finding_id: str,
    coverage_index: int,
    occurrence_index: int,
    ref: dict[str, Any],
    author_row: dict[str, Any],
    source: dict[str, Any],
    task_routes: list[dict[str, str]],
    coverage_path: str,
    report_checkpoint: dict[str, Any],
    work_queue: dict[str, Any],
) -> dict[str, Any]:
    """Build one unassessed occurrence record bound to its source locator."""
    return {
        "original": {
            "occurrence_pointer": (
                f"{coverage_path}#/findings/{coverage_index}/criterion_refs/{occurrence_index}"
            ),
            "author_pointer": (f"{author_row['original_criteria_pointer']}/{occurrence_index}"),
            "criterion_id": ref["criterion_id"],
            "document": ref["document"],
            "card_binding": ref["card"],
            "source_path": source["path"],
            "source_commit": source["source_commit"],
            "source_blob": source["source_blob"],
            "lines": ref["lines"],
            "sha256": ref["sha256"],
        },
        "candidate_evaluation": {
            "state": "UNRUN",
            "assessment": "not_assessed",
            "candidate_source": None,
            "result_summary": None,
            "boundary": {
                "kind": "candidate_not_assessed",
                "report_checkpoint": report_checkpoint,
                "details": (
                    "No frozen candidate-source evaluation is represented; this checkpoint is "
                    "navigation context only."
                ),
            },
            "evidence_refs": [],
            "attempts": [],
            "next_check": {
                "task_refs": task_routes,
                "author_decision_refs": work_queue["external_or_g_choice"]["source_refs"],
                "criterion_boundary_ref": (
                    f"/findings/{coverage_index}/occurrences/{occurrence_index}"
                    "/original_property_refs/criterion_specific_acceptance_boundary"
                ),
                "owner_crosswalk_ref": (
                    f"/findings/{coverage_index}/occurrences/{occurrence_index}/author_crosswalk/refs"
                ),
                "decision_research": {
                    "source_choice_refs": work_queue["external_or_g_choice"]["source_refs"],
                    "property_and_consumer_refs": (
                        f"/findings/{coverage_index}/occurrences/{occurrence_index}/author_crosswalk/refs"
                    ),
                    "state": "candidate_alternatives_or_prototype_not_established",
                    "required_next_result": (
                        "Bind a candidate-specific alternative/prototype comparison, or a bounded "
                        "no-alternative basis with a falsifier, before the external/G choice."
                    ),
                },
                "action": (
                    f"{work_queue['class']}: compare the exact original property with the final "
                    "frozen source/test/config/lock/input/backend/profile/consumer, then perform "
                    "the cited "
                    "owner or G action. Task PASS and historical closure do not update this record."
                ),
            },
            "review_escape": {"state": "not_assessed"},
            "proposal_disposition": None,
        },
    }


def original_property_boundary(
    *,
    coverage_path: str,
    coverage_source_index: int,
    coverage_index: int,
    coverage_row: dict[str, Any],
    author_crosswalk: dict[str, Any],
) -> dict[str, Any]:
    """Bind the original criterion span to its exact coverage and owner rows."""
    coverage_pointer = f"{coverage_path}#/findings/{coverage_index}"
    coverage_fields = [
        ("criterion_specific_acceptance_not_executed", "unexecuted_acceptance_boundary"),
        ("selected_plan_not_executed", "unexecuted_selected_plan"),
        ("capability_label", "capability_state"),
    ]
    field_refs = [
        {
            "source_key": "coverage",
            "pointer": f"/findings/{coverage_index}/{field}",
            "role": role,
        }
        for field, role in coverage_fields
        if field in coverage_row
    ]
    owner_refs = author_crosswalk.get("refs", [])
    owner_roles = list(dict.fromkeys(ref["role"] for ref in owner_refs))
    property_role_names = {
        "current_property",
        "actual_consumer",
        "negative_oracle",
        "individual_oracle_negative",
        "producer_artifact_consumer_scope",
        "producer_artifact_bridge_consumer_surface",
        "current_check",
    }
    property_roles = [role for role in owner_roles if role in property_role_names]
    acceptance_fields_present = any(
        field in coverage_row
        for field in ("criterion_specific_acceptance_not_executed", "selected_plan_not_executed")
    )
    return {
        "kind": "original_source_span_and_pinned_owner_row",
        "coverage_row_pointer": coverage_pointer,
        "coverage_source_ref": f"/source_boundary/input_sources/{coverage_source_index}",
        "coverage_field_refs": field_refs,
        "acceptance_boundary_state": (
            "coverage_specific_unexecuted_boundary_present"
            if acceptance_fields_present
            else "original_source_span_only"
        ),
        "criterion_source_ref": "#/criterion_source",
        "coverage_occurrence_ref": "#/criterion_occurrence",
        "owner_binding_state": author_crosswalk["state"],
        "owner_crosswalk_ref": "#/author_crosswalk/refs",
        "owner_source_catalog_ref": "/source_boundary/author_source_catalog",
        "owner_field_roles": owner_roles,
        "owner_property_roles": property_roles,
        "owner_property_boundary_state": (
            "source_property_or_consumer_ref_present"
            if property_roles
            else "not_established_by_author_crosswalk"
        ),
        "owner_mapping_not_established": (
            not property_roles or "not_established" in author_crosswalk["state"]
        ),
    }


def source_pointer(source_key: str, pointer: str, role: str) -> dict[str, str]:
    """Create a compact ref into a pinned author or evidence packet."""
    return {"source_key": source_key, "pointer": pointer, "role": role}


def author_pointer_sources(author_row: dict[str, Any]) -> list[dict[str, str]]:
    """Qualify each author pointer with the immutable packet that owns it."""
    author = author_row["author_source"]
    refs = []
    for raw_ref in author_row.get("author_row_pointers", []):
        pointer = raw_ref["pointer"]
        normalized = pointer.split("#", 1)[-1]
        if author == "A":
            source_key = "A_progress" if "current_root_adjudication_20261008" in normalized else "A"
        elif author == "B":
            source_key = "B_prior_decisions" if normalized.startswith("/decisions_by_id/") else "B"
        else:
            source_key = author
        refs.append(
            source_pointer(
                source_key,
                normalized,
                raw_ref.get("role", "source_author_row"),
            )
        )
    return refs


def exact_occurrence_author_refs(
    snapshot: dict[str, Any],
    author_row: dict[str, Any],
    coverage_row: dict[str, Any],
    occurrence_index: int,
) -> dict[str, Any]:
    """Map one canonical source occurrence to its author packet without deduping."""
    author = author_row["author_source"]
    finding_id = author_row["id"]
    expected = coverage_row["criterion_refs"][occurrence_index]
    expected_source = snapshot["criterion_sources"][expected["document"]]
    documents = snapshot["author_documents"]
    refs: list[dict[str, str]] = []
    state = "exact_occurrence_and_card_bound"

    if author == "A":
        progress_ref = next(
            ref
            for ref in author_row["author_row_pointers"]
            if "current_root_adjudication_20261008" in ref["pointer"]
        )
        root_pointer = progress_ref["pointer"].split("#", 1)[-1]
        root_row = resolve_pointer(documents["A_progress"], root_pointer)
        require(root_row.get("id") == finding_id, f"A root row ID mismatch: {finding_id}")
        occurrence_pointer = f"{root_pointer}/source_criterion_occurrences/{occurrence_index}"
        source_occurrence = resolve_pointer(documents["A_progress"], occurrence_pointer)
        exact = (
            source_occurrence.get("source_document") == expected_source["path"]
            and source_occurrence.get("source_document_git_blob") == expected_source["source_blob"]
            and source_occurrence.get("source_lines") == expected["lines"]
            and source_occurrence.get("criterion_span_sha256") == expected["sha256"]
            and source_occurrence.get("bundle") == expected["card"]
            and source_occurrence.get("span_hash_verified") is True
        )
        require(
            exact,
            f"A source occurrence does not bind original criterion: "
            f"{finding_id}/{occurrence_index}",
        )
        refs.append(source_pointer("A_progress", occurrence_pointer, "criterion_occurrence"))
        # A's index points to the same row occurrence; retain both producer and owner row refs.
        index_ref = next(
            ref
            for ref in author_row["author_row_pointers"]
            if ref["pointer"].split("#", 1)[-1].startswith("/current_index/")
        )
        index_pointer = index_ref["pointer"].split("#", 1)[-1]
        index_row = resolve_pointer(documents["A"], index_pointer)
        require(index_row.get("id") == finding_id, f"A current index ID mismatch: {finding_id}")
        index_occurrence = index_row["criterion_occurrences"][occurrence_index]
        require(
            index_occurrence.get("bundle") == expected["card"],
            f"A index card mismatch: {finding_id}",
        )
        refs.append(
            source_pointer(
                "A",
                index_pointer + f"/criterion_occurrences/{occurrence_index}",
                "owner_index_occurrence",
            )
        )
    elif author == "B":
        row_ref = next(
            ref
            for ref in author_row["author_row_pointers"]
            if ref["pointer"].split("#", 1)[-1].startswith("/rows/")
        )
        row_pointer = row_ref["pointer"].split("#", 1)[-1]
        current_row = resolve_pointer(documents["B"], row_pointer)
        require(current_row.get("id") == finding_id, f"B current row ID mismatch: {finding_id}")
        manual_pointer = current_row["manual_pointer"]
        manual_row = resolve_pointer(documents["B_manual"], manual_pointer)
        criterion = manual_row["canonical_criterion"]
        exact = (
            manual_row.get("finding_id") == finding_id
            and criterion.get("source_block_sha256") == current_row.get("criterion_sha256")
            and [criterion.get("line_begin"), criterion.get("line_end")]
            == current_row.get("marker_span")
            and manual_row.get("bundle_id") == expected["card"]
            and current_row.get("bundle") == expected["card"]
        )
        require(exact, f"B manual criterion/card mismatch: {finding_id}")
        # B's current canonical criterion is a distinct summary/source criterion
        # from the original B_r19 occurrence. Keep that distinction explicit.
        if len(coverage_row["criterion_refs"]) > 1:
            state = "finding_and_card_bound_occurrence_mapping_not_established"
        elif expected["sha256"] != criterion["source_block_sha256"]:
            state = "finding_and_card_bound_distinct_author_criterion_text"
        refs.extend(
            [
                source_pointer("B", row_pointer, "current_author_row"),
                source_pointer(
                    "B_manual",
                    manual_pointer + "/canonical_criterion",
                    "canonical_original_criterion",
                ),
                source_pointer("B_manual", manual_pointer, "canonical_card_binding"),
            ]
        )
        prior_pointer = current_row.get("prior_index_pointer")
        if isinstance(prior_pointer, str):
            prior_row = resolve_pointer(documents["B_prior_decisions"], prior_pointer)
            require(
                prior_pointer.rsplit("/", 1)[-1] == finding_id and isinstance(prior_row, dict),
                f"B prior decision key mismatch: {finding_id}",
            )
            refs.append(
                source_pointer("B_prior_decisions", prior_pointer, "prior_status_comparison")
            )
    elif author == "C":
        row_ref = author_row["author_row_pointers"][0]
        row_pointer = row_ref["pointer"].split("#", 1)[-1]
        packet_row = resolve_pointer(documents["C"], row_pointer)
        require(packet_row.get("id") == finding_id, f"C row ID mismatch: {finding_id}")
        originals = packet_row.get("original_criteria", [])
        bundles = packet_row.get("bundles", [])
        require(
            len(originals) == len(coverage_row["criterion_refs"]),
            f"C occurrence count mismatch: {finding_id}",
        )
        original = originals[occurrence_index]
        exact_text = (
            original.get("criterion_sha256") == expected["sha256"]
            and [int(value) for value in original.get("line_span", "").split("-")]
            == expected["lines"]
            and original.get("source_document", {}).get("path") == expected_source["path"]
            and original.get("source_document", {}).get("git_blob")
            == expected_source["source_blob"]
        )
        require(exact_text, f"C source occurrence mismatch: {finding_id}/{occurrence_index}")
        if len(originals) == 1:
            require(
                bundles == [expected["card"]], f"C unique occurrence card mismatch: {finding_id}"
            )
        else:
            require(
                collections.Counter(bundles)
                == collections.Counter(ref["card"] for ref in coverage_row["criterion_refs"]),
                f"C duplicate card set mismatch: {finding_id}",
            )
            state = "exact_text_occurrence_card_not_established"
        refs.append(
            source_pointer(
                "C",
                f"{row_pointer}/original_criteria/{occurrence_index}",
                "original_criterion_occurrence",
            )
        )
        refs.append(source_pointer("C", f"{row_pointer}/bundles", "finding_bundle_set"))
        refs.append(source_pointer("C", row_pointer, "source_author_row"))
    elif author == "D":
        packet_rows = documents["D"].get("rows", [])
        hits = []
        for index, row in enumerate(packet_rows):
            original = row.get("original", {}).get("original_fragment", {})
            if (
                row.get("finding_id") == finding_id
                and original.get("document_key") == expected["document"]
                and original.get("lines") == expected["lines"]
                and original.get("sha256") == expected["sha256"]
                and row.get("original", {}).get("card_catalog_key") == f"card_{expected['card']}"
            ):
                hits.append((index, row))
        require(
            len(hits) == 1,
            f"D occurrence/card did not resolve uniquely: {finding_id}/{occurrence_index}",
        )
        row_index, row = hits[0]
        refs.append(source_pointer("D", f"/rows/{row_index}", row.get("role", "source_occurrence")))
        action = row.get("G_action", {})
        if action.get("ref") == "G_actions":
            for field, role in (
                ("property_pointer", "current_property"),
                ("consumer_pointer", "actual_consumer"),
                ("P38_discriminator_pointer", "negative_oracle"),
            ):
                pointer = action.get(field)
                if isinstance(pointer, str):
                    resolve_pointer(documents["D_G_actions"], pointer)
                    refs.append(source_pointer("D_G_actions", pointer, role))
        unique_pointer = f"/unique_finding_proposals/{finding_id}"
        if unique_pointer in {
            ref["pointer"].split("#", 1)[-1] for ref in author_row["author_row_pointers"]
        }:
            refs.append(source_pointer("D", unique_pointer, "unique_finding_proposal"))
    elif author == "E":
        row_ref = author_row["author_row_pointers"][0]
        row_pointer = row_ref["pointer"].split("#", 1)[-1]
        packet_row = resolve_pointer(documents["E"], row_pointer)
        require(packet_row.get("id") == finding_id, f"E row ID mismatch: {finding_id}")
        originals = packet_row.get("original_criteria", [])
        bundles = packet_row.get("bundle_ids", [])
        require(
            len(originals) == len(coverage_row["criterion_refs"]) == len(bundles),
            f"E occurrence/card denominator mismatch: {finding_id}",
        )
        original = originals[occurrence_index]
        exact = (
            original.get("sha256") == expected["sha256"]
            and original.get("lines") == expected["lines"]
            and original.get("path") == expected_source["path"]
            and bundles[occurrence_index] == expected["card"]
        )
        require(exact, f"E occurrence/card mismatch: {finding_id}/{occurrence_index}")
        refs.extend(
            [
                source_pointer(
                    "E",
                    f"{row_pointer}/original_criteria/{occurrence_index}",
                    "original_criterion_occurrence",
                ),
                source_pointer(
                    "E", f"{row_pointer}/bundle_ids/{occurrence_index}", "original_card_binding"
                ),
                source_pointer("E", row_pointer, "source_author_row"),
            ]
        )
        for field, role in (
            ("producer_artifact_bridge_consumer_surface", "producer_artifact_consumer_scope"),
            ("individual_oracle_negative_and_predicate_basis", "individual_oracle_negative"),
            ("bounded_decision_and_original_current_checks", "current_check"),
            ("G_current_original_row_assessment", "G_source_admission_navigation"),
        ):
            locator = packet_row.get(field)
            if isinstance(locator, dict):
                input_key = locator.get("input")
                fragment = locator.get("fragment")
                if isinstance(input_key, str) and isinstance(fragment, str):
                    source_key = f"E_{input_key}"
                    resolve_pointer(documents[source_key], fragment)
                    refs.append(source_pointer(source_key, fragment, role))
    elif author == "F":
        row_ref = author_row["author_row_pointers"][0]
        row_pointer = row_ref["pointer"].split("#", 1)[-1]
        packet_row = resolve_pointer(documents["F"], row_pointer)
        require(packet_row.get("finding_id") == finding_id, f"F row ID mismatch: {finding_id}")
        original_refs = packet_row.get("original_card_refs", [])
        require(
            len(original_refs) == len(coverage_row["criterion_refs"]),
            f"F occurrence count mismatch: {finding_id}",
        )
        original = original_refs[occurrence_index]
        exact_text = (
            original.get("sha256") == expected["sha256"]
            and original.get("lines") == expected["lines"]
            and original.get("source_path") == expected_source["path"]
            and original.get("document_git_blob") == expected_source["source_blob"]
        )
        require(exact_text, f"F source occurrence mismatch: {finding_id}/{occurrence_index}")
        if len(original_refs) == 1:
            require(
                packet_row.get("primary_bundle") == expected["card"],
                f"F unique card mismatch: {finding_id}",
            )
        else:
            state = "exact_text_occurrence_card_not_established"
        refs.extend(
            [
                source_pointer(
                    "F",
                    f"{row_pointer}/original_card_refs/{occurrence_index}",
                    "original_criterion_text_occurrence",
                ),
                source_pointer("F", row_pointer, "source_author_row"),
            ]
        )
        carrier = packet_row.get("deciding_per_ID_carrier_ref")
        if isinstance(carrier, dict):
            carrier_key = f"F_carrier_{finding_id}"
            carrier_ref = snapshot["author_sources"].get(carrier_key)
            require(isinstance(carrier_ref, dict), f"F carrier was not preloaded: {finding_id}")
            refs.append(source_pointer(carrier_key, "", "deciding_per_ID_carrier"))
    else:
        raise ValueError(f"unsupported author source: {author}")

    return {"state": state, "refs": refs}


def author_queue(
    snapshot: dict[str, Any],
    author_row: dict[str, Any],
    coverage_row: dict[str, Any],
    occurrence_index: int,
) -> dict[str, Any]:
    """Classify the next per-occurrence action from pinned author evidence."""
    finding_id = author_row["id"]
    author = author_row["author_source"]
    disposition = author_row["author_proposal"]
    refs: list[dict[str, str]] = []
    queue_class = "named_residual_or_G_decision"
    reuse_state = "candidate_source_equality_not_checked"
    row_refs = author_pointer_sources(author_row)
    refs.extend(row_refs)

    if finding_id == "B198":
        queue_class = "historical_closed_regression_falsifier_only"
        reuse_state = "preserve_prior_closed_decision_unless_new_counterexample"
        e_pointer = row_refs[0]["pointer"]
        refs.append(
            source_pointer("E", f"{e_pointer}/next_verifiable_result", "regression_falsifier_rule")
        )
    elif author == "D" and disposition == "closed":
        row_ref = next(
            ref
            for ref in row_refs
            if ref["source_key"] == "D" and ref["pointer"].startswith("/rows/")
        )
        row = resolve_pointer(snapshot["author_documents"]["D"], row_ref["pointer"])
        require(
            row.get("check_result", {}).get("whole_current_candidate_execution") == "UNRUN",
            f"D closed row no longer declares whole candidate execution UNRUN: {finding_id}",
        )
        queue_class = "run_occurrence_specific_current_property_consumer_negative"
        reuse_state = "bounded_assertions_exist_whole_candidate_execution_unrun"
        refs.append(
            source_pointer(
                "D", f"{row_ref['pointer']}/G_action", "current_property_consumer_negative_plan"
            )
        )
        refs.append(
            source_pointer("D", f"{row_ref['pointer']}/check_result", "explicit_unrun_state")
        )
    elif author == "B" and disposition == "closed":
        row_ref = next(
            ref
            for ref in row_refs
            if ref["source_key"] == "B" and ref["pointer"].startswith("/rows/")
        )
        row = resolve_pointer(snapshot["author_documents"]["B"], row_ref["pointer"])
        if row.get("source_dependency_delta"):
            require(
                row.get("runtime") == "UNRUN affected consumers",
                f"B source dependency delta lacks UNRUN declaration: {finding_id}",
            )
            queue_class = "replay_named_changed_consumer_paths"
            reuse_state = "old_scope_retained_affected_consumers_unrun"
            refs.append(
                source_pointer(
                    "B", f"{row_ref['pointer']}/source_dependency_delta", "changed_consumer_paths"
                )
            )
            refs.append(
                source_pointer("B", f"{row_ref['pointer']}/runtime", "explicit_unrun_state")
            )
        else:
            queue_class = "verify_retained_scope_on_selected_source_then_G_intake"
            reuse_state = "exact_prior_scope_retained_conditional_on_source_input_identity"
            manual_pointer = row["manual_pointer"]
            refs.append(
                source_pointer(
                    "B_manual", f"{manual_pointer}/actual_current_check", "prior_deciding_check"
                )
            )
            refs.append(
                source_pointer(
                    "B_manual", f"{manual_pointer}/deciding_reference_ids", "prior_evidence_locator"
                )
            )
    elif author == "C" and disposition == "closed":
        row_ref = row_refs[0]
        row = resolve_pointer(snapshot["author_documents"]["C"], row_ref["pointer"])
        require(
            row.get("current_root_verdict", {}).get("status")
            == "retained_from_c4_under_c5_root_adjudication",
            f"C current carry-forward status mismatch: {finding_id}",
        )
        queue_class = "reuse_carried_evidence_only_if_exact_candidate_property_unchanged"
        reuse_state = "c4_evidence_carried_forward_not_fresh_runtime_pass"
        refs.append(
            source_pointer(
                "C",
                f"{row_ref['pointer']}/current_c_evaluation",
                "carried_evidence_boundary_and_next_action",
            )
        )
        refs.append(
            source_pointer(
                "C",
                f"{row_ref['pointer']}/current_root_verdict",
                "root_carry_forward_not_G_closure",
            )
        )
    elif author == "A" and disposition == "closed":
        row_ref = next(ref for ref in row_refs if ref["source_key"] == "A_progress")
        queue_class = "G_review_of_exact_A_receipt_and_selected_source"
        reuse_state = "row_specific_A_receipt_exists_selected_source_identity_unchecked"
        refs.append(
            source_pointer(
                "A_progress", f"{row_ref['pointer']}/next_action", "source_and_G_next_action"
            )
        )
        refs.append(
            source_pointer(
                "A_progress",
                f"{row_ref['pointer']}/receipt_packet_ref",
                "row_specific_receipt_locator",
            )
        )
    elif author == "E" and disposition == "closed":
        row_ref = row_refs[0]
        row = resolve_pointer(snapshot["author_documents"]["E"], row_ref["pointer"])
        next_result = row.get("next_verifiable_result", "")
        if next_result == (
            "No row-specific E work remains; G must separately decide code acceptance and "
            "formal finding intake/ledger treatment."
        ):
            queue_class = "G_source_acceptance_and_exact_finding_intake"
            reuse_state = "prior_individualized_oracle_retained_G_decision_pending"
        elif next_result.startswith("E repeats affected native sampling consumers"):
            queue_class = "replay_final_public_reader_affected_native_sampling"
            reuse_state = "affected_native_replay_required_after_public_reader_freeze"
        elif next_result.startswith("E freezes repaired public boundary"):
            queue_class = "freeze_public_boundary_review_then_affected_native_routes"
            reuse_state = "public_boundary_and_native_route_replay_required"
        elif next_result.startswith("G formal intake after current frozen-wave"):
            queue_class = "G_intake_after_frozen_wave_receipt_reconciliation"
            reuse_state = "prior_checks_exist_frozen_wave_reconciliation_required"
        elif next_result.startswith("E checks generic join compatibility"):
            queue_class = "check_generic_join_compatibility_and_diagnostic_claim_boundary"
            reuse_state = "one_affected_boundary_run_required"
        else:
            raise ValueError(f"unclassified E closed-row next result: {finding_id}")
        refs.append(
            source_pointer(
                "E",
                f"{row_ref['pointer']}/next_verifiable_result",
                "row_specific_next_verifiable_result",
            )
        )
        refs.append(
            source_pointer(
                "E",
                f"{row_ref['pointer']}/bounded_decision_and_original_current_checks",
                "row_specific_check_refs",
            )
        )
    elif author == "F" and disposition == "closed":
        row_ref = row_refs[0]
        row = resolve_pointer(snapshot["author_documents"]["F"], row_ref["pointer"])
        require(
            row.get("check_result") == "PASS" and row.get("F_finding_outcome") == "closed",
            f"F prior per-ID check/outcome mismatch: {finding_id}",
        )
        queue_class = "verify_admitted_F_source_and_per_ID_evidence_for_exact_occurrence"
        reuse_state = "per_ID_source_bound_evidence_available_selected_consumer_delta_unchecked"
        refs.append(
            source_pointer("F", f"{row_ref['pointer']}/check_result", "prior_per_ID_check_result")
        )
        refs.append(
            source_pointer(
                "F",
                f"{row_ref['pointer']}/recorded_independent_oracle_and_negative",
                "prior_per_ID_oracle_and_negative",
            )
        )
    elif coverage_row.get("selected_plan_not_executed"):
        queue_class = (
            "execute_exact_selected_plan_or_record_tested_supported_profile_unavailability"
        )
        reuse_state = "criterion_specific_selected_plan_not_executed"
        coverage_index = snapshot["coverage_index_by_id"][finding_id]
        refs.append(
            source_pointer(
                "coverage",
                f"/findings/{coverage_index}/selected_plan_not_executed",
                "criterion_specific_unexecuted_plan",
            )
        )
    else:
        queue_class = "resolve_author_named_residual_then_G_adjudication"
        reuse_state = "author_proposal_not_closed_or_has_named_residual"

    return {
        "class": queue_class,
        "status": "action_required_or_explicit_G_intake",
        "reuse_state": reuse_state,
        "task_refs": snapshot["routes"][finding_id],
        "author_and_evidence_refs": refs,
        "external_or_g_choice": author_decision_route(snapshot, author_row),
        "candidate_source_equality": "not_established_pending_final_source_freeze",
        "property_ref": (
            f"{CRITERIA_COVERAGE_PATH.as_posix()}#/findings/"
            f"{snapshot['coverage_index_by_id'][finding_id]}/criterion_refs/{occurrence_index}"
        ),
    }


def author_decision_route(snapshot: dict[str, Any], author_row: dict[str, Any]) -> dict[str, Any]:
    """Point to each author's concrete residual, external input, or G decision."""
    author = author_row["author_source"]
    finding_id = author_row["id"]
    documents = snapshot["author_documents"]
    refs: list[dict[str, str]] = []
    owner: str | None = None
    kind = "source_author_residual_or_G_review"

    if author == "A":
        progress_ref = next(
            ref
            for ref in author_row["author_row_pointers"]
            if "current_root_adjudication_20261008" in ref["pointer"]
        )
        pointer = progress_ref["pointer"].split("#", 1)[-1]
        root_row = resolve_pointer(documents["A_progress"], pointer)
        require(root_row.get("id") == finding_id, f"A decision row ID mismatch: {finding_id}")
        refs.extend(
            [
                source_pointer(
                    "A_progress", f"{pointer}/next_action", "source_owner_or_G_next_action"
                ),
                source_pointer(
                    "A_progress", f"{pointer}/receipt_packet_ref", "retained_receipt_locator"
                ),
            ]
        )
        action = root_row.get("next_action", "")
        if isinstance(action, str) and action.startswith("G:"):
            owner, kind = "G", "G_decision_or_intake"
        elif isinstance(action, str) and ":" in action:
            owner = action.split(":", 1)[0]
            kind = "named_source_owner_action"
    elif author == "B":
        row_ref = next(
            ref
            for ref in author_row["author_row_pointers"]
            if ref["pointer"].split("#", 1)[-1].startswith("/rows/")
        )
        pointer = row_ref["pointer"].split("#", 1)[-1]
        row = resolve_pointer(documents["B"], pointer)
        require(row.get("id") == finding_id, f"B decision row ID mismatch: {finding_id}")
        owner = row.get("next_owner")
        kind = (
            "external_served_input_or_G_review"
            if "served" in str(row.get("remaining", "")).lower()
            else "named_owner_or_G_review"
        )
        refs.extend(
            [
                source_pointer("B", f"{pointer}/next_owner", "source_named_next_owner"),
                source_pointer(
                    "B", f"{pointer}/source_dependency_delta", "affected_source_consumers"
                ),
            ]
        )
        if "remaining" in row:
            refs.append(
                source_pointer("B", f"{pointer}/remaining", "source_named_remaining_result")
            )
        else:
            manual_pointer = row.get("manual_pointer")
            if isinstance(manual_pointer, str):
                refs.extend(
                    [
                        source_pointer(
                            "B_manual",
                            f"{manual_pointer}/actual_current_check",
                            "retained_deciding_check",
                        ),
                        source_pointer(
                            "B_manual",
                            f"{manual_pointer}/deciding_reference_ids",
                            "retained_deciding_evidence_refs",
                        ),
                    ]
                )
    elif author == "C":
        row_ref = author_row["author_row_pointers"][0]
        pointer = row_ref["pointer"].split("#", 1)[-1]
        row = resolve_pointer(documents["C"], pointer)
        require(row.get("id") == finding_id, f"C decision row ID mismatch: {finding_id}")
        action = row.get("g_action", {})
        owner = action.get("next_owner") if isinstance(action, dict) else None
        kind = "G_criterion_scoped_action"
        refs.extend(
            [
                source_pointer("C", f"{pointer}/g_action", "criterion_scoped_G_action"),
                source_pointer(
                    "C", f"{pointer}/g_current", "current_G_status_and_capability_label"
                ),
                source_pointer("C", f"{pointer}/p37_property_basis", "gate_predicate_basis"),
            ]
        )
    elif author == "D":
        row_ref = next(
            ref
            for ref in author_row["author_row_pointers"]
            if ref["pointer"].split("#", 1)[-1].startswith("/rows/")
        )
        pointer = row_ref["pointer"].split("#", 1)[-1]
        row = resolve_pointer(documents["D"], pointer)
        require(row.get("finding_id") == finding_id, f"D decision row ID mismatch: {finding_id}")
        action = row.get("G_action", {})
        kind = "targeted_current_candidate_verification_then_G_adjudication"
        owner = row.get("closure_owner")
        refs.extend(
            [
                source_pointer(
                    "D", f"{pointer}/G_action", "current_property_consumer_negative_route"
                ),
                source_pointer(
                    "D", f"{pointer}/check_result", "bounded_assertions_vs_whole_candidate_state"
                ),
                source_pointer("D", f"{pointer}/remaining", "named_G_and_external_residuals"),
            ]
        )
        if isinstance(action, dict) and action.get("ref") == "G_actions":
            refs.append(
                source_pointer(
                    "D_G_actions", action["pointer"], "source_bound_property_consumer_discriminator"
                )
            )
    elif author == "E":
        row_ref = author_row["author_row_pointers"][0]
        pointer = row_ref["pointer"].split("#", 1)[-1]
        row = resolve_pointer(documents["E"], pointer)
        require(row.get("id") == finding_id, f"E decision row ID mismatch: {finding_id}")
        owner = row.get("next_owner")
        external = row.get("external_owner_input")
        kind = (
            "external_owner_input_then_G_source_admission"
            if isinstance(external, dict)
            else "named_owner_next_verifiable_result"
        )
        refs.extend(
            [
                source_pointer(
                    "E", f"{pointer}/next_verifiable_result", "exact_next_verifiable_result"
                ),
                source_pointer(
                    "E",
                    f"{pointer}/external_owner_input",
                    "external_owner_input_or_nonapplicability",
                ),
                source_pointer(
                    "E",
                    f"{pointer}/G_current_original_row_assessment",
                    "current_G_source_admission_status",
                ),
            ]
        )
        if isinstance(external, dict) and isinstance(external.get("fragment"), str):
            refs.append(source_pointer("E", external["fragment"], "external_owner_input_details"))
    elif author == "F":
        row_ref = author_row["author_row_pointers"][0]
        pointer = row_ref["pointer"].split("#", 1)[-1]
        row = resolve_pointer(documents["F"], pointer)
        require(row.get("finding_id") == finding_id, f"F decision row ID mismatch: {finding_id}")
        owner = row.get("original_next_owner")
        kind = (
            "external_input_or_G_review"
            if row.get("original_missing_input")
            else "G_source_review_and_affected_consumer_replay"
        )
        refs.extend(
            [
                source_pointer(
                    "F", f"{pointer}/next_concrete_result", "exact_next_concrete_result"
                ),
                source_pointer(
                    "F", f"{pointer}/original_missing_input", "original_missing_input_or_none"
                ),
                source_pointer(
                    "F",
                    f"{pointer}/separate_unavailable_inputs_or_authority",
                    "separate_authority_or_unavailability_boundary",
                ),
                source_pointer(
                    "F", f"{pointer}/G_finding_acceptance", "current_G_finding_acceptance"
                ),
            ]
        )
    else:
        raise ValueError(f"unsupported source author in decision route: {author}")

    for ref in refs:
        resolve_pointer(documents[ref["source_key"]], ref["pointer"])
    return {"kind": kind, "next_owner": owner, "source_refs": refs}


def provisional_occurrence_review() -> dict[str, Any]:
    """Carry author review as provisional evidence without claiming candidate closure."""
    return {
        "status": "source_qualified_author_review_pending_final_candidate_freeze",
        "candidate_source_equality": "not_established_pending_final_source_freeze",
        "candidate_freeze_ref": "/source_boundary/source_freeze/candidate_source",
        "source_change_census_ref": "/source_boundary/source_freeze/source_change_census",
        "assessment_boundary": (
            "This review resolves the original criterion block and source-author packet only. It "
            "does not establish candidate source/test/config/input/backend/consumer equality, "
            "runtime execution, or G closure. Reconcile the complete changed-path and input "
            "denominator after the final source freeze."
        ),
    }


def build_ledger(snapshot: dict[str, Any], evaluations_path: Path | None) -> dict[str, Any]:
    """Build the ledger and apply only explicit occurrence evaluation inputs."""
    root = snapshot["repo_root"]
    coverage = snapshot["coverage"]
    coverage_path = (BASE_REL / "closure-decisions/coverage.json").as_posix()
    coverage_source_index = next(
        index
        for index, source in enumerate(snapshot["tracked_inputs"])
        if source.get("role") == "coverage" and source.get("path") == coverage_path
    )
    records: list[dict[str, Any]] = []

    for coverage_index, coverage_row in enumerate(coverage["findings"]):
        finding_id = coverage_row["id"]
        author_row = snapshot["author_by_id"][finding_id]
        task_routes = snapshot["routes"][finding_id]
        occurrences = []
        for occurrence_index, ref in enumerate(coverage_row["criterion_refs"]):
            crosswalk = exact_occurrence_author_refs(
                snapshot, author_row, coverage_row, occurrence_index
            )
            queue = author_queue(snapshot, author_row, coverage_row, occurrence_index)
            occurrence = initial_occurrence(
                finding_id=finding_id,
                coverage_index=coverage_index,
                occurrence_index=occurrence_index,
                ref=ref,
                author_row=author_row,
                source=snapshot["criterion_sources"][ref["document"]],
                task_routes=task_routes,
                coverage_path=coverage_path,
                report_checkpoint=snapshot["report_checkout"],
                work_queue=queue,
            )
            occurrence["author_crosswalk"] = crosswalk
            occurrence["original_property_refs"] = {
                "criterion_occurrence": occurrence["original"]["occurrence_pointer"],
                "criterion_source": {
                    "path": occurrence["original"]["source_path"],
                    "commit": occurrence["original"]["source_commit"],
                    "git_blob": occurrence["original"]["source_blob"],
                    "lines": occurrence["original"]["lines"],
                    "sha256": occurrence["original"]["sha256"],
                },
                "criterion_specific_acceptance_boundary": original_property_boundary(
                    coverage_path=coverage_path,
                    coverage_source_index=coverage_source_index,
                    coverage_index=coverage_index,
                    coverage_row=coverage_row,
                    author_crosswalk=crosswalk,
                ),
            }
            occurrence["work_queue"] = queue
            occurrence["provisional_review"] = provisional_occurrence_review()
            occurrences.append(occurrence)
        author_index = snapshot["findings"]["rows"].index(author_row)
        author_packet_refs = author_pointer_sources(author_row)
        for packet_ref in author_packet_refs:
            pointer = packet_ref["pointer"]
            resolve_pointer(snapshot["author_documents"][packet_ref["source_key"]], pointer)
        records.append(
            {
                "finding_id": finding_id,
                "ownership": {
                    "unit": coverage_row["unit"],
                    "primary_bundle": coverage_row["primary_bundle"],
                    "source_closure_owner_literal": coverage_row["source_closure_owner_literal"],
                    "companion_bundles": coverage_row["companion_bundles"],
                },
                "historical": {
                    "ledger_status": coverage_row["ledger_status_historical"],
                    "appendix_c_status": coverage_row["appendix_c_status_separate"],
                    "closure_now": coverage_row["closure_now"],
                    "coverage_task_refs": coverage_row["task_refs"],
                },
                "source_author_proposal": {
                    "disposition": author_row["author_proposal"],
                    "source": author_row["author_source"],
                    "row_pointers": author_row["author_row_pointers"],
                    "source_packet_refs": author_packet_refs,
                    "finding_index_pointer": (
                        f"{BASE_REL.as_posix()}/integration/connected-closeout-plan-2026-10-08/findings.json"
                        f"#/rows/{author_index}"
                    ),
                    "next_decision": author_row["next_decision"],
                    "G_closure_field": author_row["G_closure"],
                },
                "original_routes": {
                    "flows": author_row["flows"],
                    "next_tasks": author_row["next_tasks"],
                    "current_tasks": task_routes,
                },
                "candidate_proposal": None,
                "occurrences": occurrences,
            }
        )

    ledger = {
        "schema": SCHEMA,
        "scope": (
            "Occurrence-level crosswalk, source-author proposals, provisional source review, and "
            "explicit evaluation updates only. Candidate execution remains UNRUN until a final "
            "source freeze and occurrence-specific evidence. This ledger is not runtime proof and "
            "does not perform G adjudication."
        ),
        "source_boundary": {
            "original_entry": snapshot["original_entry"],
            "report_checkout": snapshot["report_checkout"],
            "source_freeze": snapshot["source_freeze"],
            "execution_plan_source": snapshot["execution_plan_source"],
            "closeout_support_sources": snapshot["closeout_support_sources"],
            "development_source_base": snapshot["inputs"]["development_source_base"],
            "original_main_anchor": snapshot["inputs"]["main_anchor"],
            "coverage_runtime_source": coverage["runtime_source"],
            "input_sources": snapshot["tracked_inputs"],
            "criterion_sources": list(snapshot["criterion_sources"].values()),
            "author_source_catalog": list(snapshot["author_sources"].values()),
        },
        "denominator": {
            "bundles": len(coverage["bundles"]),
            "finding_ids": len(records),
            "canonical_occurrences": snapshot["occurrence_count"],
        },
        "route_census": snapshot["route_census"],
        "replay_selection": {
            "scope": (
                f"all {snapshot['route_census']['routed_finding_ids']} original IDs and "
                f"all {snapshot['occurrence_count']} criterion occurrences; author proposals "
                f"partition as {snapshot['route_census']['author_proposal_counts']}"
            ),
            "author_proposal_partition": snapshot["route_census"]["author_proposal_counts"],
            "q0_exact_scope_ids": snapshot["route_census"]["q0_finding_ids"],
            "q0_includes_every_author_closed_id": snapshot["route_census"][
                "author_closed_ids_missing_q0"
            ]
            == [],
            "q0_nonclosed_ids": snapshot["route_census"]["q0_nonclosed_ids"],
            "route_basis": snapshot["route_census"]["basis"],
            "rule": (
                "Per-occurrence queue and author evidence refs select the exact property/consumer. "
                "Reuse a prior review only when source, tests, configuration, locks, inputs, "
                "backend/profile, and actual consumer match the frozen candidate; a path-only "
                "intersection is triage, never a closure predicate."
            ),
            "candidate_source_freeze_ref": "/source_boundary/source_freeze",
            "portable_replay": {
                "after_source_freeze": [
                    (
                        "affected source/test/config/lock/generated consumers selected from each "
                        "changed property and the per-occurrence author crosswalk"
                    ),
                    (
                        "one composed required backend replay from the execution plan, retaining "
                        "PASS/FAIL/ERROR/SKIP/UNRUN separately"
                    ),
                    (
                        "canonical regeneration plus declared installed wheel/rebuilt-sdist "
                        "consumers where the original criterion requires them"
                    ),
                    (
                        "required repository gates from AGENTS.md, with exact slice base, "
                        "candidate, environment/input denominator, changed-path intersection, and "
                        "complete deciding output"
                    ),
                ],
                "not_a_gate": (
                    "Task completion, task-level PASS, historical closure, or author-proposed "
                    "closed status does not update an occurrence evaluation."
                ),
            },
            "composed_wave": {
                "denominators": {
                    "bundles": len(coverage["bundles"]),
                    "finding_ids": snapshot["route_census"]["routed_finding_ids"],
                    "criterion_occurrences": snapshot["occurrence_count"],
                    "author_proposed_closed_ids": snapshot["route_census"]["author_closed_ids"],
                    "nonclosed_author_proposals": (
                        snapshot["route_census"]["routed_finding_ids"]
                        - snapshot["route_census"]["author_closed_ids"]
                    ),
                    "task_definitions": snapshot["route_census"]["task_definitions"],
                    "route_assignments": snapshot["route_census"]["route_assignments"],
                    "route_gaps": snapshot["route_census"]["route_gaps"],
                },
                "required_profile": {
                    "profile": "Python 3.14 app profile",
                    "scope": "B state/runtime, A/C/E native, and selected D source scopes",
                    "inputs": "candidate manifest, locks, loaded origins, normal conftest",
                    "receipts": "actual stdout/stderr/JUnit, elapsed time, and RSS",
                    "source_ref": snapshot["closeout_support_sources"][0],
                },
                "conditional_consumers": [
                    {
                        "consumer": "optional GP stack",
                        "scope": (
                            "named D GP/warm/corpus/numerical properties only; never the entire "
                            "minimal suite"
                        ),
                        "source_ref": snapshot["closeout_support_sources"][0],
                    },
                    {
                        "consumer": "installed wheel and rebuilt sdist/archive",
                        "scope": "only criteria that name installed/default/FQN/assets consumers",
                        "source_ref": snapshot["closeout_support_sources"][0],
                    },
                    {
                        "consumer": "canonical generation and served readers",
                        "scope": "only criteria whose source/property crosswalk names them",
                        "source_ref": snapshot["closeout_support_sources"][0],
                    },
                ],
                "repository_gates": [
                    "cd policy-engine && python3 -m tools.cli workspace verify --backend-only",
                    "cd policy-engine && python3 -m tools.cli workspace ci-parity --skip-browser",
                    "cd policy-engine && uv run polisyos-tools architecture guardrails check",
                    (
                        "cd policy-engine && uv run --extra runtime --extra ml polisyos-tools "
                        "runtime check-runtime-api-contract"
                    ),
                ],
                "command_status": (
                    "UNRUN_until_final_source_environment_and_backend_profile_are_frozen"
                ),
                "no_invented_global_command": True,
            },
            "required_local_readonly_authentic_closeout": {
                "source_refs": [
                    (
                        "policy-engine/docs/research/e02-cloud-test-plan/integration/connected-"
                        "closeout-plan-2026-10-08/05-verification-and-release.md#Local read-only "
                        "authentic inputs"
                    ),
                    (
                        "policy-engine/docs/research/e02-cloud-test-plan/integration/connected-"
                        "closeout-plan-2026-10-08/06-inputs-and-deferrals.md#A B01–03; B13 "
                        "authentic served recovery"
                    ),
                    f"{PACKET_REL.as_posix()}/TASKS.json#/tasks/V1",
                    f"{PACKET_REL.as_posix()}/TASKS.json#/tasks/V6",
                ],
                "pinned_source_refs": snapshot["closeout_support_sources"],
                "minimum_input": (
                    "Read-only, criterion-specific local catalog/acquisition/history and L6 "
                    "artifact pair; matching manifest or legitimate versioned replacement; "
                    "source/context/tenant/run refs; preserve the exact consumed subset "
                    "refs/hashes, permissions/verification/context, and unavailable inputs."
                ),
                "consumer_sequence": (
                    "V1 POST→owned-context→N5→CAS→fresh GET; V6 requires V1's authentic profile "
                    "and then producer→later independent failure→CAS/history/debug-served "
                    "readback plus corrupt-ref refusal."
                ),
                "freeze_dependencies": [
                    (
                        "accepted source DAG and owner corrections; exact candidate commit/tree "
                        "and complete changed path/blob manifests"
                    ),
                    (
                        "criterion-specific input hashes and authority/permission/context "
                        "identity, without transferring the data to cloud"
                    ),
                    (
                        "backend/profile freeze and named serving root/instance; portable profile "
                        "remains bounded and does not replace authentic evidence"
                    ),
                ],
                "literal_shell_command_in_plan": False,
                "status": (
                    "not_run_here; no admitted input manifest or final source freeze in this "
                    "crosswalk scope"
                ),
            },
        },
        "formal_closure_ids": list(snapshot["inputs"].get("formal_closure_ids", [])),
        "evaluation_mode": (
            "provisional_author_review_pending_final_source_freeze"
            if snapshot["source_freeze"]["status"] == "provisional_source_checkpoint_not_frozen"
            else "frozen_candidate_explicit_occurrence_updates"
        ),
        "findings": records,
        "p40_review_contract": {
            "applies_to": "new candidate review escapes, not historical criterion records",
            "required_bucket_values": sorted(P40_BUCKETS),
            "first_same_class": "NEW_CLASS with ordinal 1",
            "second_same_class_requires": [
                "structural_widening",
                "or_bounded_residual_with_run_falsifier",
            ],
            "later_same_class": "cite ordinal-2 resolution and record worked_example_no_round",
        },
    }
    if evaluations_path is not None:
        evaluation_doc = json.loads(evaluations_path.read_text(encoding="utf-8"))
        apply_evaluations(ledger, evaluation_doc, root)
    return ledger


def validate_candidate_source(root: Path, candidate: object) -> dict[str, str]:
    """Resolve one occurrence's candidate source identity."""
    require(isinstance(candidate, dict), "candidate_source must be an object")
    require(
        set(candidate) == {"commit", "tree"}, "candidate_source must contain only commit and tree"
    )
    commit, tree = candidate.get("commit"), candidate.get("tree")
    require(
        isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
        "candidate commit must be a full SHA",
    )
    require(
        isinstance(tree, str) and re.fullmatch(r"[0-9a-f]{40}", tree) is not None,
        "candidate tree must be a full SHA",
    )
    resolved_commit = git_text(root, "rev-parse", f"{commit}^{{commit}}")
    resolved_tree = git_text(root, "rev-parse", f"{commit}^{{tree}}")
    require(
        resolved_commit == commit and resolved_tree == tree,
        "candidate commit/tree do not resolve to the declared frozen source",
    )
    return {"commit": commit, "tree": tree}


def validate_evidence_refs(
    root: Path,
    value: object,
    *,
    occurrence_pointer: str,
    occurrence_sha256: str,
    candidate: dict[str, str],
    label: str,
    required: bool,
) -> list[dict[str, Any]]:
    """Validate tracked, immutable evidence bound to one source occurrence."""
    require(isinstance(value, list), f"{label} must be an array")
    if required:
        require(bool(value), f"{label} is required")
    resolved = [
        validate_pinned_evidence_ref(
            root,
            item,
            occurrence_pointer=occurrence_pointer,
            occurrence_sha256=occurrence_sha256,
            candidate_source=candidate,
            label=f"{label}[{index}]",
        )
        for index, item in enumerate(value)
    ]
    return resolved


def validate_attempts(
    root: Path,
    value: object,
    *,
    occurrence_pointer: str,
    occurrence_sha256: str,
    candidate: dict[str, str],
    required: bool,
) -> list[dict[str, Any]]:
    """Require explicit attempts with source-bound occurrence results."""
    require(isinstance(value, list), "attempts must be an array")
    if required:
        require(bool(value), "attempts must record completed attempts")
    checked = []
    for index, attempt in enumerate(value):
        require(isinstance(attempt, dict), f"invalid attempt {index}")
        require(
            isinstance(attempt.get("action"), str) and attempt["action"].strip(),
            f"attempt action missing at index {index}",
        )
        status = attempt.get("status")
        require(
            status in COMMAND_OUTCOMES,
            f"attempt status must preserve PASS/FAIL/ERROR/SKIP at index {index}",
        )
        result_ref = validate_pinned_evidence_ref(
            root,
            attempt.get("result_ref"),
            occurrence_pointer=occurrence_pointer,
            occurrence_sha256=occurrence_sha256,
            candidate_source=candidate,
            label=f"attempts[{index}].result_ref",
        )
        checked.append({"action": attempt["action"], "status": status, "result_ref": result_ref})
    return checked


def validate_slice_footprint(
    root: Path,
    handoff: dict[str, Any],
    *,
    candidate_source: dict[str, str],
    complete_census: dict[str, Any],
    label: str,
) -> None:
    """Reconcile the slice's path subset and file hashes with the frozen tree."""
    census_rows = complete_census.get("complete_paths")
    require(isinstance(census_rows, list), f"{label} full source census is incomplete")
    census = {row["path"]: row["status"] for row in census_rows}
    for index, row in enumerate(handoff.get("source_footprint", [])):
        path, change = row.get("path"), row.get("change")
        require(
            isinstance(path, str) and path,
            f"{label} source footprint path is missing at index {index}",
        )
        require(
            change in {"A", "M", "D", "T", "UNCHANGED"},
            f"{label} source footprint change is invalid for {path}",
        )
        if change == "UNCHANGED":
            require(path not in census, f"{label} labels a changed source as unchanged: {path}")
        else:
            require(
                census.get(path) == change,
                f"{label} source footprint does not match the complete candidate census: {path}",
            )
        if change == "D":
            require(
                row.get("git_blob") is None and row.get("sha256") is None,
                f"{label} deleted source must not claim candidate bytes: {path}",
            )
            continue
        blob, digest = row.get("git_blob"), row.get("sha256")
        require(
            isinstance(blob, str) and re.fullmatch(r"[0-9a-f]{40}", blob) is not None,
            f"{label} source footprint Git blob is invalid: {path}",
        )
        require(
            isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            f"{label} source footprint content hash is invalid: {path}",
        )
        actual_blob = git_text(root, "rev-parse", f"{candidate_source['commit']}:{path}")
        actual_bytes = git_bytes(root, "show", f"{candidate_source['commit']}:{path}")
        require(
            actual_blob == blob and sha256(actual_bytes) == digest,
            f"{label} source footprint bytes differ from frozen candidate: {path}",
        )


def validate_decision_research_rows(
    root: Path,
    decision_refs: list[dict[str, Any]],
    *,
    occurrence_pointer: str,
    occurrence_sha256: str,
    candidate_source: dict[str, str],
    label: str,
) -> list[dict[str, Any]]:
    """Validate every decision option and its evidence against one exact occurrence."""
    require(bool(decision_refs), f"{label} must carry at least one decision research row")
    validated: list[dict[str, Any]] = []
    for index, decision_ref in enumerate(decision_refs):
        require(
            isinstance(decision_ref, dict), f"{label} decision research row is invalid: {index}"
        )
        kind = decision_ref.get("kind")
        require(
            kind in {"alternative", "prototype", "bounded_no_alternative"},
            f"{label} decision research kind is invalid: {index}",
        )
        decision_source_ref = validate_pinned_evidence_ref(
            root,
            decision_ref.get("source_ref"),
            occurrence_pointer=occurrence_pointer,
            occurrence_sha256=occurrence_sha256,
            candidate_source=candidate_source,
            label=f"{label} decision research source ref[{index}]",
        )
        if kind == "alternative":
            require(
                all(
                    isinstance(decision_ref.get(key), str) and decision_ref[key].strip()
                    for key in ("option_id", "tradeoff", "discriminator")
                ),
                f"{label} alternative needs a tradeoff and distinguishing predicate: {index}",
            )
            require(
                decision_source_ref.get("role") == "decision_alternative",
                f"{label} alternative source role is invalid: {index}",
            )
        elif kind == "prototype":
            require(
                isinstance(decision_ref.get("argv"), list)
                and bool(decision_ref["argv"])
                and all(isinstance(part, str) for part in decision_ref["argv"]),
                f"{label} prototype needs its exact command: {index}",
            )
            require(
                decision_ref.get("status") in COMMAND_OUTCOMES | {"UNRUN"},
                f"{label} prototype status is invalid: {index}",
            )
            require(
                decision_source_ref.get("role") == "prototype_result",
                f"{label} prototype source role is invalid: {index}",
            )
        else:
            require(
                isinstance(decision_ref.get("reason"), str)
                and decision_ref["reason"].strip()
                and isinstance(decision_ref.get("falsifier"), str)
                and decision_ref["falsifier"].strip(),
                f"{label} bounded no-alternative basis needs a reason and falsifier: {index}",
            )
            require(
                decision_source_ref.get("role") == "bounded_no_alternative_basis",
                f"{label} no-alternative source role is invalid: {index}",
            )
        validated.append(decision_ref)
    return validated


def validate_typed_slice_receipt(
    root: Path,
    evidence_ref: dict[str, Any],
    *,
    candidate_source: dict[str, str],
    occurrence_pointer: str,
    occurrence_sha256: str,
    finding_id: str,
    evaluation_state: str,
    complete_census: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    """Verify one typed LOCAL receipt describes the exact frozen execution slice."""
    require(
        evidence_ref.get("role") == "typed_slice_receipt",
        f"{label} evidence role must be typed_slice_receipt",
    )
    match = SLICE_HANDOFF_PATH.fullmatch(evidence_ref.get("path", ""))
    require(match is not None, f"{label} must point to a direct-child LOCAL slice receipt")
    data = git_bytes(root, "show", f"{evidence_ref['commit']}:{evidence_ref['path']}")
    try:
        artifact = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not a typed JSON receipt") from exc
    require(isinstance(artifact, dict), f"{label} is not a JSON object")
    validate_slice_handoff(
        artifact,
        path=evidence_ref["path"],
        slice_id=match.group(1),
        expected_candidate=candidate_source,
        label=label,
    )
    validate_slice_source_relationships(root, artifact, label=label)
    command_statuses = {command["status"] for command in artifact["commands"]}
    if evaluation_state == "VERIFIED":
        require(
            "PASS" in command_statuses, f"{label} VERIFIED evaluation has no PASS command result"
        )
    elif evaluation_state == "BOUNDED_LIMITATION":
        require(
            bool(command_statuses & COMMAND_OUTCOMES),
            f"{label} bounded limitation has no recorded command outcome",
        )
    for command_index, command in enumerate(artifact["commands"]):
        if command["status"] == "UNRUN":
            continue
        for output_key in ("stdout_ref", "stderr_ref"):
            output_ref = command[output_key]
            if output_ref.get("storage") == LOCAL_RAW_STORAGE:
                validate_local_raw_output(
                    root,
                    output_ref,
                    candidate_source=candidate_source,
                    label=f"{label} command {command_index} {output_key}",
                )
                continue
            output_path = output_ref["path"]
            require(
                not output_path.startswith("/") and ".." not in Path(output_path).parts,
                f"{label} {output_key} path must be repository-relative",
            )
            git_text(root, "rev-parse", f"{evidence_ref['commit']}:{output_path}")
            output_bytes = git_bytes(root, "show", f"{evidence_ref['commit']}:{output_path}")
            require(
                sha256(output_bytes) == output_ref["sha256"],
                f"{label} command {command_index} {output_key} hash mismatch",
            )
            require(
                len(output_bytes) <= 16 * 1024 * 1024,
                f"{label} command {command_index} {output_key} exceeds the retained-log size bound",
            )
    require(
        finding_id in artifact.get("proposal_ids", []),
        f"{label} does not route the evaluated finding ID",
    )
    require_handoff_occurrence(
        artifact,
        finding_id=finding_id,
        occurrence_pointer=occurrence_pointer,
        criterion_sha256=occurrence_sha256,
        label=label,
    )
    validate_slice_footprint(
        root,
        artifact,
        candidate_source=candidate_source,
        complete_census=complete_census,
        label=label,
    )
    validate_backend_environment_manifest(
        root,
        artifact,
        candidate_source=candidate_source,
        label=label,
    )
    profile = artifact.get("backend_profile", {})
    require(
        all(
            isinstance(profile.get(key), str) and profile[key].strip()
            for key in ("backend_id", "profile_id")
        ),
        f"{label} must name the actual backend and selected profile",
    )
    chain = artifact.get("chain", {})
    require(
        all(
            isinstance(chain.get(key), str) and chain[key].strip()
            for key in ("producer", "artifact", "bridge", "consumer")
        ),
        f"{label} must identify producer, artifact, bridge, and consumer",
    )
    surface = artifact.get("consumer_surface", {})
    require(
        all(
            isinstance(surface.get(key), str) and surface[key].strip()
            for key in ("consumer_id", "path", "selector")
        ),
        f"{label} must bind an exact consumer surface and selector",
    )
    for index, selected_input in enumerate(artifact.get("selected_inputs", [])):
        require(isinstance(selected_input, dict), f"{label} selected input row is invalid: {index}")
        require(
            isinstance(selected_input.get("identity"), str) and selected_input["identity"].strip(),
            f"{label} selected input identity is missing: {index}",
        )
        require(
            selected_input.get("status") in {"available", "unavailable"},
            f"{label} selected input status is invalid: {index}",
        )
        if selected_input["status"] == "available":
            require(
                isinstance(selected_input.get("sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", selected_input["sha256"]) is not None,
                f"{label} available input lacks its content hash: {index}",
            )
    decision_mapping = decision_refs_by_occurrence(artifact, label=label)
    selected_decisions = decision_mapping.get((finding_id, occurrence_pointer, occurrence_sha256))
    require(
        isinstance(selected_decisions, list) and bool(selected_decisions),
        f"{label} has no decision ref for the evaluated original occurrence",
    )
    validate_decision_research_rows(
        root,
        selected_decisions,
        occurrence_pointer=occurrence_pointer,
        occurrence_sha256=occurrence_sha256,
        candidate_source=candidate_source,
        label=label,
    )
    return artifact


def parse_git_commit_header(commit_object: bytes, *, label: str) -> tuple[str, list[str]]:
    """Read the tree and ordered parent identities from one Git commit object."""
    require(isinstance(commit_object, bytes), f"{label} commit object must be bytes")
    header, separator, _message = commit_object.partition(b"\n\n")
    require(bool(separator), f"{label} commit object has no header/message boundary")
    tree_values: list[str] = []
    parent_values: list[str] = []
    for header_line in header.splitlines():
        if header_line.startswith(b"tree "):
            try:
                tree_values.append(header_line.removeprefix(b"tree ").decode("ascii"))
            except UnicodeDecodeError as exc:
                raise ValueError(f"{label} commit tree identity is not ASCII") from exc
        elif header_line.startswith(b"parent "):
            try:
                parent_values.append(header_line.removeprefix(b"parent ").decode("ascii"))
            except UnicodeDecodeError as exc:
                raise ValueError(f"{label} commit parent identity is not ASCII") from exc
    require(len(tree_values) == 1, f"{label} commit object must contain exactly one tree header")
    require(
        re.fullmatch(r"[0-9a-f]{40}", tree_values[0]) is not None,
        f"{label} commit tree identity is invalid",
    )
    require(
        all(re.fullmatch(r"[0-9a-f]{40}", parent) is not None for parent in parent_values),
        f"{label} commit parent identity is invalid",
    )
    return tree_values[0], parent_values


def git_commit_source(
    root: Path,
    source: object,
    *,
    label: str,
) -> tuple[dict[str, str], list[str]]:
    """Resolve a declared commit/tree pair and inspect its actual Git ancestry headers."""
    identity = validate_candidate_source(root, source)
    commit_object = git_bytes(root, "cat-file", "-p", identity["commit"])
    object_tree, parent_ids = parse_git_commit_header(commit_object, label=label)
    require(
        object_tree == identity["tree"],
        f"{label} commit object tree differs from its resolved source tree",
    )
    for parent_index, parent_id in enumerate(parent_ids):
        try:
            resolved_parent = git_text(root, "rev-parse", f"{parent_id}^{{commit}}")
        except (OSError, ValueError) as exc:
            raise ValueError(f"{label} actual Git parent is unavailable: {parent_index}") from exc
        require(
            resolved_parent == parent_id,
            f"{label} actual Git parent does not resolve to the declared commit: {parent_index}",
        )
    return identity, parent_ids


def validate_slice_source_relationships(
    root: Path,
    handoff: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    """Bind slice base, candidate tree, and ordered parent claims to Git objects."""
    ensure_git_graph_authoritative(root, label=label)
    base_identity, _base_parents = git_commit_source(
        root,
        handoff.get("slice_base"),
        label=f"{label} slice base",
    )
    candidate_identity, actual_parent_ids = git_commit_source(
        root,
        handoff.get("candidate_source"),
        label=f"{label} candidate source",
    )
    declared_parent_ids = handoff.get("parents")
    require(
        isinstance(declared_parent_ids, list),
        f"{label} parents must be an ordered array of actual Git parent IDs",
    )
    require(
        declared_parent_ids == actual_parent_ids,
        f"{label} parents do not equal the actual Git parent list in order",
    )
    ancestry = git_run(
        root,
        "merge-base",
        "--is-ancestor",
        base_identity["commit"],
        candidate_identity["commit"],
        check=False,
    )
    require(
        ancestry.returncode == 0,
        (
            f"{label} slice base is not an ancestor of the candidate source"
            if ancestry.returncode == 1
            else f"{label} could not resolve slice-base ancestry (git exit {ancestry.returncode})"
        ),
    )
    return {
        "slice_base": base_identity,
        "candidate_source": candidate_identity,
        "candidate_parent_ids": actual_parent_ids,
    }


def git_read_boundary_self_check(
    root: Path,
    *,
    candidate_source: dict[str, str],
    original_entry: dict[str, str],
) -> dict[str, Any]:
    """Probe immutable Git reads, graph overlays, and missing-object failures."""
    source_text = Path(__file__).read_text(encoding="utf-8")
    syntax_tree = ast.parse(source_text)
    git_subprocess_sites: list[tuple[str | None, str]] = []

    def record_git_subprocess_calls(node: ast.AST, owner: str | None = None) -> None:
        current_owner = owner
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            current_owner = node.name
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
            and node.func.attr in {"run", "check_output", "Popen"}
        ):
            git_subprocess_sites.append((current_owner, node.func.attr))
        for child in ast.iter_child_nodes(node):
            record_git_subprocess_calls(child, current_owner)

    record_git_subprocess_calls(syntax_tree)
    production_sites = [
        site for site in git_subprocess_sites if site[0] != "git_read_boundary_self_check"
    ]
    require(
        production_sites == [("git_run", "run")],
        "Git subprocess reads must be centralized through git_run",
    )

    actual_commit_object = git_bytes(root, "cat-file", "-p", candidate_source["commit"])
    _tree_id, actual_parents = parse_git_commit_header(
        actual_commit_object,
        label="self-check immutable Git object",
    )
    require(bool(actual_parents), "self-check needs a commit with an actual parent")
    original_parent = actual_parents[0]
    missing_parent = "0" * 40
    require(
        original_parent != missing_parent
        and git_run(root, "cat-file", "-e", missing_parent, check=False).returncode != 0,
        "self-check missing parent identity unexpectedly resolves",
    )
    forged_object = actual_commit_object.replace(
        f"parent {original_parent}\n".encode("ascii"),
        f"parent {missing_parent}\n".encode("ascii"),
        1,
    )
    require(forged_object != actual_commit_object, "self-check could not forge a parent view")

    real_run = subprocess.run
    safe_git_calls: list[list[str]] = []
    unsafe_git_calls: list[list[str]] = []

    def replacement_view_spy(
        argv: Sequence[str] | str,
        *args: object,
        **options: object,
    ) -> subprocess.CompletedProcess[Any]:
        command = list(argv) if isinstance(argv, (list, tuple)) else []
        if command and command[0] == "git":
            environment = options.get("env")
            immutable = (
                "--no-replace-objects" in command[1:]
                and isinstance(environment, dict)
                and environment.get("GIT_NO_REPLACE_OBJECTS") == "1"
            )
            if immutable:
                safe_git_calls.append(command)
            else:
                unsafe_git_calls.append(command)
                if command[1:] == ["cat-file", "-p", candidate_source["commit"]]:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout=forged_object,
                        stderr=b"",
                    )
        return real_run(argv, *args, **options)

    unsafe_environment = os.environ.copy()
    unsafe_environment.pop("GIT_NO_REPLACE_OBJECTS", None)
    subprocess.run = replacement_view_spy
    try:
        replacement_view = subprocess.run(  # noqa: S603 -- deliberate unsafe-view self-check only.
            ["git", "cat-file", "-p", candidate_source["commit"]],  # noqa: S607 -- synthetic spy probe, never executed as Git.
            cwd=root,
            env=unsafe_environment,
            check=True,
            capture_output=True,
        )
        require(
            replacement_view.stdout == forged_object,
            "self-check replacement-view spy did not produce its forged parent list",
        )
        immutable_object = git_bytes(root, "cat-file", "-p", candidate_source["commit"])
        require(
            immutable_object == actual_commit_object and immutable_object != forged_object,
            "git_run accepted the synthetic replacement-object parent list",
        )
        census = complete_source_change_census(
            root,
            original_entry_commit=original_entry["commit"],
            candidate_commit=candidate_source["commit"],
            original_entry_tree=original_entry["tree"],
            candidate_tree=candidate_source["tree"],
        )
        verify_source_descendant(
            root,
            frozen_commit=candidate_source["commit"],
            frozen_tree=candidate_source["tree"],
            descendant_commit=candidate_source["commit"],
        )
    finally:
        subprocess.run = real_run

    require(bool(safe_git_calls), "self-check did not exercise immutable Git reads")
    require(
        len(unsafe_git_calls) == 1,
        "a source reader bypassed the immutable Git command wrapper",
    )

    original_git_text = git_text

    def shallow_git_text(_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--is-shallow-repository"):
            return "true"
        return original_git_text(_root, *args)

    globals()["git_text"] = shallow_git_text
    try:
        try:
            ensure_git_graph_authoritative(root, label="self-check shallow repository")
        except ValueError:
            shallow_repository_rejected = True
        else:
            raise ValueError("self-check accepted shallow-repository ancestry")
    finally:
        globals()["git_text"] = original_git_text

    def grafted_git_text(_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--is-shallow-repository"):
            return "false"
        if args == ("rev-parse", "--git-path", "info/grafts"):
            return str(root / "AGENTS.md")
        return original_git_text(_root, *args)

    globals()["git_text"] = grafted_git_text
    try:
        try:
            ensure_git_graph_authoritative(root, label="self-check active graft")
        except ValueError:
            active_grafts_rejected = True
        else:
            raise ValueError("self-check accepted an active Git graft row")
    finally:
        globals()["git_text"] = original_git_text
    require(
        not has_active_git_grafts(b"# inert comment\n \t\n")
        and has_active_git_grafts(b"# comment\n" + b"1" * 40 + b" " + b"2" * 40 + b"\n"),
        "self-check did not distinguish active from inert graft rows",
    )

    missing_commit = "0" * 40
    try:
        validate_candidate_source(
            root,
            {"commit": missing_commit, "tree": candidate_source["tree"]},
        )
    except ValueError:
        missing_candidate_rejected = True
    else:
        raise ValueError("self-check accepted a missing candidate commit")

    missing_base_handoff = {
        "slice_base": {"commit": missing_commit, "tree": candidate_source["tree"]},
        "candidate_source": candidate_source,
        "parents": actual_parents,
    }
    try:
        validate_slice_source_relationships(
            root,
            missing_base_handoff,
            label="self-check missing slice base",
        )
    except ValueError:
        missing_base_rejected = True
    else:
        raise ValueError("self-check accepted a missing slice-base object")

    real_git_bytes = git_bytes

    def missing_parent_git_bytes(_root: Path, *args: str) -> bytes:
        payload = real_git_bytes(root, *args)
        if args == ("cat-file", "-p", candidate_source["commit"]):
            return forged_object
        return payload

    globals()["git_bytes"] = missing_parent_git_bytes
    try:
        try:
            git_commit_source(
                root,
                candidate_source,
                label="self-check missing actual parent",
            )
        except ValueError:
            missing_parent_rejected = True
        else:
            raise ValueError("self-check accepted a missing actual parent object")
    finally:
        globals()["git_bytes"] = real_git_bytes

    return {
        "production_git_subprocess_calls_centralized": production_sites == [("git_run", "run")],
        "immutable_git_reads_observed": len(safe_git_calls),
        "synthetic_replacement_parent_view_demonstrated": replacement_view.stdout == forged_object,
        "synthetic_replacement_parent_view_rejected": immutable_object == actual_commit_object,
        "shallow_repository_rejected": shallow_repository_rejected,
        "active_grafts_rejected": active_grafts_rejected,
        "missing_candidate_normalized_to_value_error": missing_candidate_rejected,
        "missing_slice_base_normalized_to_value_error": missing_base_rejected,
        "missing_parent_normalized_to_value_error": missing_parent_rejected,
        "complete_census_path_count": census["changed_paths"],
        "graph_self_ancestry_delta_count": len(
            verify_source_descendant(
                root,
                frozen_commit=candidate_source["commit"],
                frozen_tree=candidate_source["tree"],
                descendant_commit=candidate_source["commit"],
            )
        ),
    }


def validate_input_evidence_bindings(
    input_state: str,
    input_indexes: list[int],
    evidence_refs: list[dict[str, Any]],
    receipt_inputs: list[dict[str, Any]],
    *,
    label: str,
) -> None:
    """Bind each selected input to source, authority, permission, context, and verification refs."""
    inputs_by_identity: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(receipt_inputs):
        identity = row.get("identity")
        require(
            isinstance(identity, str) and identity.strip(),
            f"{label} input identity is missing: {index}",
        )
        if identity in inputs_by_identity:
            prior = inputs_by_identity[identity]
            require(
                prior.get("status") == row.get("status")
                and prior.get("sha256") == row.get("sha256"),
                f"{label} duplicate input identities disagree: {identity}",
            )
        else:
            inputs_by_identity[identity] = row

    if input_state in {"available", "unavailable"}:
        require(
            bool(inputs_by_identity),
            f"{label} selected-input state lacks an explicit input denominator",
        )
        grouped: dict[str, set[str]] = collections.defaultdict(set)
        input_roles = {
            "selected_input",
            "input_unavailability",
            "input_authority",
            "input_permission",
            "input_context",
            "input_verification",
        }
        for index in input_indexes:
            ref = evidence_refs[index]
            role = ref.get("role")
            require(role in input_roles, f"{label} selected-input evidence role is invalid: {role}")
            identity = ref.get("input_identity")
            require(
                isinstance(identity, str) and identity in inputs_by_identity,
                f"{label} input evidence does not bind a selected input identity",
            )
            require(
                isinstance(ref.get("pointer"), str) and ref["pointer"].strip(),
                f"{label} input evidence needs an exact manifest/context pointer",
            )
            row = inputs_by_identity[identity]
            if role == "selected_input":
                require(
                    row.get("status") == "available",
                    f"{label} selected_input ref targets a non-available input: {identity}",
                )
                require(
                    ref.get("input_sha256") == row.get("sha256"),
                    f"{label} input ref hash differs from the selected input row: {identity}",
                )
            elif role == "input_unavailability":
                require(
                    row.get("status") == "unavailable"
                    and isinstance(ref.get("unavailability_reason"), str)
                    and ref["unavailability_reason"].strip(),
                    f"{label} unavailability ref lacks an explicit unavailable "
                    f"input/reason: {identity}",
                )
            else:
                expected_status = "available" if role == "input_verification" else row.get("status")
                if role == "input_verification":
                    require(
                        isinstance(ref.get("verification_status"), str)
                        and ref["verification_status"].strip(),
                        f"{label} input verification ref lacks its result state: {identity}",
                    )
                require(
                    expected_status in {"available", "unavailable"},
                    f"{label} authority/permission/context ref targets invalid input: {identity}",
                )
            grouped[identity].add(role)

        for identity, row in inputs_by_identity.items():
            required_roles = {
                "input_authority",
                "input_permission",
                "input_context",
                "input_verification",
            }
            if row.get("status") == "available":
                required_roles.add("selected_input")
            elif row.get("status") == "unavailable":
                required_roles.add("input_unavailability")
            else:
                raise ValueError(
                    f"{label} input status must be available or unavailable: {identity}"
                )
            require(
                required_roles <= grouped.get(identity, set()),
                f"{label} input denominator lacks source/authority/permission/context/"
                f"verification refs: {identity}",
            )

        statuses = {row.get("status") for row in inputs_by_identity.values()}
        if input_state == "available":
            require(
                statuses == {"available"},
                f"{label} available input state disagrees with the complete selected-input set",
            )
        else:
            require(
                "unavailable" in statuses,
                f"{label} unavailable input state has no unavailable selected input",
            )
    else:
        require(
            not input_indexes and not receipt_inputs,
            f"{label} no-input state must not carry selected-input evidence",
        )


def validate_execution_context(
    root: Path,
    context: object,
    evidence_refs: list[dict[str, Any]],
    *,
    candidate_source: dict[str, str],
    occurrence_pointer: str,
    occurrence_sha256: str,
    finding_id: str,
    evaluation_state: str,
    source_footprint_sha256: str,
    complete_census: dict[str, Any],
) -> dict[str, Any]:
    """Require exact footprint, input, backend, consumer, and receipt bindings."""
    required = {
        "source_footprint_sha256",
        "configuration_and_lock_evidence_indexes",
        "configuration_scope_evidence_index",
        "selected_input_state",
        "selected_input_evidence_indexes",
        "input_scope_evidence_index",
        "backend_profile_evidence_index",
        "consumer_surface_evidence_indexes",
        "typed_slice_receipt_evidence_indexes",
        "decision_research_evidence_indexes",
    }
    require(
        isinstance(context, dict) and set(context) == required,
        "execution_context fields are incomplete or unknown",
    )
    require(
        context.get("source_footprint_sha256") == source_footprint_sha256,
        "execution_context full source footprint differs from the frozen census",
    )

    def indexes(field: str, *, nonempty: bool = False) -> list[int]:
        value = context.get(field)
        require(isinstance(value, list), f"execution_context.{field} must be an array")
        require(
            all(
                isinstance(index, int)
                and not isinstance(index, bool)
                and 0 <= index < len(evidence_refs)
                for index in value
            ),
            f"execution_context.{field} contains an invalid evidence index",
        )
        require(
            len(value) == len(set(value)),
            f"execution_context.{field} contains duplicate evidence indexes",
        )
        require(not nonempty or bool(value), f"execution_context.{field} cannot be empty")
        return value

    def single_index(field: str, role: str | None = None) -> int | None:
        value = context.get(field)
        if value is None:
            return None
        require(
            isinstance(value, int)
            and not isinstance(value, bool)
            and 0 <= value < len(evidence_refs),
            f"execution_context.{field} is invalid",
        )
        if role is not None:
            require(
                evidence_refs[value].get("role") == role,
                f"execution_context.{field} must reference role {role}",
            )
        return value

    config_indexes = indexes("configuration_and_lock_evidence_indexes")
    config_scope = single_index("configuration_scope_evidence_index", "configuration_scope")
    if config_indexes:
        require(
            config_scope is None, "configuration scope cannot replace exact configuration/lock refs"
        )
        require(
            all(
                evidence_refs[index].get("role") in {"configuration", "lockfile"}
                for index in config_indexes
            ),
            "configuration/lock indexes must point to configuration or lockfile evidence",
        )
    else:
        require(
            config_scope is not None,
            "empty configuration/lock set needs a source-bound configuration_scope ref",
        )

    input_indexes = indexes("selected_input_evidence_indexes")
    input_scope = single_index("input_scope_evidence_index")
    input_state = context.get("selected_input_state")
    require(
        input_state in {"available", "unavailable", "not_required", "not_established"},
        "execution_context selected_input_state is invalid",
    )
    if input_state == "available":
        require(
            bool(input_indexes) and input_scope is None,
            "available selected inputs need exact input refs",
        )
    elif input_state == "unavailable":
        require(
            bool(input_indexes) and input_scope is None,
            "unavailable inputs need exact unavailability refs",
        )
        require(
            evaluation_state in {"UNAVAILABLE_INPUT", "OPEN_ACTION"},
            "unavailable input cannot support a verified result",
        )
    else:
        require(
            not input_indexes and input_scope is not None,
            "no-input/not-established state needs a source-bound scope ref",
        )
        expected_role = (
            "no_input_basis" if input_state == "not_required" else "input_scope_not_established"
        )
        require(
            evidence_refs[input_scope].get("role") == expected_role,
            f"input scope must use role {expected_role}",
        )
        if input_state == "not_established":
            require(
                evaluation_state != "VERIFIED",
                "unestablished input scope cannot support a verified result",
            )

    backend_index = single_index("backend_profile_evidence_index", "backend_profile")
    require(backend_index is not None, "execution_context backend profile evidence is required")
    consumer_indexes = indexes("consumer_surface_evidence_indexes", nonempty=True)
    require(
        all(
            evidence_refs[index].get("role") in {"actual_consumer", "consumer_surface"}
            for index in consumer_indexes
        ),
        "consumer surface indexes must identify an actual consumer",
    )
    receipt_indexes = indexes("typed_slice_receipt_evidence_indexes", nonempty=True)
    decision_indexes = indexes("decision_research_evidence_indexes", nonempty=True)
    receipts = []
    for index in receipt_indexes:
        receipts.append(
            validate_typed_slice_receipt(
                root,
                evidence_refs[index],
                candidate_source=candidate_source,
                occurrence_pointer=occurrence_pointer,
                occurrence_sha256=occurrence_sha256,
                finding_id=finding_id,
                evaluation_state=evaluation_state,
                complete_census=complete_census,
                label=f"execution_context typed receipt[{index}]",
            )
        )
    backend_ref = evidence_refs[backend_index]
    require(
        backend_ref.get("pointer") == "#/backend_profile",
        "backend/profile evidence must identify the backend_profile object",
    )
    require(
        any(
            receipt_ref["path"] == backend_ref.get("path")
            and receipt_ref["commit"] == backend_ref.get("commit")
            for receipt_ref in (evidence_refs[index] for index in receipt_indexes)
        ),
        "backend/profile evidence must be in a selected typed slice receipt",
    )
    receipt_inputs = [row for receipt in receipts for row in receipt.get("selected_inputs", [])]
    validate_input_evidence_bindings(
        input_state,
        input_indexes,
        evidence_refs,
        receipt_inputs,
        label="execution_context selected inputs",
    )
    require(
        all(
            evidence_refs[index].get("role")
            in {
                "decision_alternative",
                "prototype",
                "bounded_no_alternative_basis",
            }
            for index in decision_indexes
        ),
        "decision research indexes must point to alternatives, prototypes, or a bounded "
        "no-alternative basis",
    )
    receipt_paths = {
        (evidence_refs[index]["path"], evidence_refs[index]["commit"]) for index in receipt_indexes
    }
    for index in decision_indexes:
        ref = evidence_refs[index]
        require(
            (ref.get("path"), ref.get("commit")) in receipt_paths,
            "decision alternatives/prototypes must be embedded in the occurrence's typed "
            "slice receipt",
        )
        require(
            isinstance(ref.get("pointer"), str)
            and ref["pointer"].split("#", 1)[-1].startswith("/decision_refs/"),
            "decision research evidence pointer must select a typed receipt decision_refs row",
        )
    return dict(context)


def validate_p40_escape(
    value: object,
    root: Path | None = None,
    *,
    occurrence_pointer: str | None = None,
    occurrence_sha256: str | None = None,
    candidate_source: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Enforce P40 classification and the second-instance resolution contract."""
    require(isinstance(value, dict), "review_escape must be an object")
    state = value.get("state")
    require(state in {"not_assessed", "none_observed", "present"}, "invalid review_escape state")
    if state != "present":
        require("bucket" not in value, "non-escape record cannot claim a P40 bucket")
        return dict(value)

    require(
        value.get("bucket") in P40_BUCKETS,
        "escape must be bucketed NEW_CLASS or SAME_CLASS_DEEPER",
    )
    require(
        isinstance(value.get("class_id"), str) and value["class_id"].strip(),
        "escape class_id is required",
    )
    ordinal = value.get("same_class_ordinal")
    require(
        isinstance(ordinal, int) and not isinstance(ordinal, bool) and ordinal >= 1,
        "same_class_ordinal must be a positive integer",
    )
    if value["bucket"] == "NEW_CLASS":
        require(ordinal == 1, "NEW_CLASS must start at ordinal 1")
    else:
        require(ordinal >= 2, "SAME_CLASS_DEEPER must be at least ordinal 2")
    if ordinal == 1:
        return dict(value)

    if ordinal >= 3:
        require(
            value.get("treatment") == "worked_example_no_round",
            "third and later same-class escapes must be recorded as no-round worked examples",
        )
        resolution = value.get("class_resolution")
        require(isinstance(resolution, dict), "worked example must cite its class resolution")
        require(
            resolution.get("resolution") in {"structural_widening", "bounded_residual"},
            "worked example must identify the accepted second-instance resolution",
        )
        pointer = resolution.get("occurrence_pointer")
        digest = resolution.get("sha256")
        require(
            isinstance(pointer, str) and pointer,
            "worked example resolution occurrence pointer required",
        )
        require(
            isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
            "worked example resolution occurrence hash required",
        )
        return dict(value)

    require(root is not None, "second same-class escape requires source-bound evidence validation")
    require(
        isinstance(occurrence_pointer, str) and occurrence_pointer,
        "second same-class escape needs its exact occurrence pointer",
    )
    require(
        isinstance(occurrence_sha256, str) and occurrence_sha256,
        "second same-class escape needs its exact occurrence hash",
    )
    require(
        isinstance(candidate_source, dict), "second same-class escape needs its candidate source"
    )

    resolution = value.get("second_same_class_resolution")
    require(
        resolution in {"structural_widening", "bounded_residual"},
        "second same-class escape requires structural widening or bounded residual",
    )
    if resolution == "structural_widening":
        mechanism_ref = validate_pinned_evidence_ref(
            root,
            value.get("mechanism_ref"),
            occurrence_pointer=occurrence_pointer,
            occurrence_sha256=occurrence_sha256,
            candidate_source=candidate_source,
            label="review_escape.mechanism_ref",
        )
        falsifier_result_ref = validate_pinned_evidence_ref(
            root,
            value.get("falsifier_result_ref"),
            occurrence_pointer=occurrence_pointer,
            occurrence_sha256=occurrence_sha256,
            candidate_source=candidate_source,
            label="review_escape.falsifier_result_ref",
        )
        require(
            mechanism_ref["role"] == "structural_widening",
            "mechanism_ref role must be structural_widening",
        )
        require(
            falsifier_result_ref["role"] == "falsifier_result",
            "falsifier_result_ref role must be falsifier_result",
        )
        result = dict(value)
        result["mechanism_ref"] = mechanism_ref
        result["falsifier_result_ref"] = falsifier_result_ref
        return result
    else:
        require(
            bool(value.get("smallest_missing_capability")),
            "bounded residual needs smallest missing capability",
        )
        capability_absence_ref = validate_pinned_evidence_ref(
            root,
            value.get("capability_absence_ref"),
            occurrence_pointer=occurrence_pointer,
            occurrence_sha256=occurrence_sha256,
            candidate_source=candidate_source,
            label="review_escape.capability_absence_ref",
        )
        require(
            capability_absence_ref["role"] == "capability_absence",
            "capability_absence_ref role must be capability_absence",
        )
        falsifier = value.get("falsifier")
        require(isinstance(falsifier, dict), "bounded residual needs a falsifier object")
        require(bool(falsifier.get("command")), "bounded residual falsifier command is required")
        falsifier_result_ref = validate_pinned_evidence_ref(
            root,
            falsifier.get("result_ref"),
            occurrence_pointer=occurrence_pointer,
            occurrence_sha256=occurrence_sha256,
            candidate_source=candidate_source,
            label="review_escape.falsifier.result_ref",
        )
        require(
            falsifier_result_ref["role"] == "falsifier_result",
            "bounded residual falsifier result role must be falsifier_result",
        )
        result = dict(value)
        result["capability_absence_ref"] = capability_absence_ref
        result["falsifier"] = {"command": falsifier["command"], "result_ref": falsifier_result_ref}
        return result


def validate_explicit_evaluation(
    evaluation: dict[str, Any],
    root: Path,
    occurrence_pointer: str,
    occurrence_sha256: str,
    *,
    finding_id: str,
    source_footprint_sha256: str,
    complete_census: dict[str, Any],
) -> dict[str, Any]:
    """Validate one explicit, source-bound occurrence evaluation."""
    state = evaluation.get("state")
    require(state in OUTCOME_STATES, f"invalid explicit evaluation state: {state}")
    require(bool(evaluation.get("result_summary")), "result_summary is required")
    boundary = evaluation.get("boundary")
    require(isinstance(boundary, dict), "boundary must be an object")
    require(
        bool(boundary.get("kind")) and bool(boundary.get("details")),
        "boundary needs kind and details",
    )
    require(bool(evaluation.get("next_check")), "next_check is required")
    candidate = validate_candidate_source(root, evaluation.get("candidate_source"))
    evidence = validate_evidence_refs(
        root,
        evaluation.get("evidence_refs"),
        occurrence_pointer=occurrence_pointer,
        occurrence_sha256=occurrence_sha256,
        candidate=candidate,
        label="evidence_refs",
        required=True,
    )
    require_verified_evidence_roles(state, evidence, label="occurrence evaluation")
    execution_context = validate_execution_context(
        root,
        evaluation.get("execution_context"),
        evidence,
        candidate_source=candidate,
        occurrence_pointer=occurrence_pointer,
        occurrence_sha256=occurrence_sha256,
        finding_id=finding_id,
        evaluation_state=state,
        source_footprint_sha256=source_footprint_sha256,
        complete_census=complete_census,
    )
    attempts = validate_attempts(
        root,
        evaluation.get("attempts", []),
        occurrence_pointer=occurrence_pointer,
        occurrence_sha256=occurrence_sha256,
        candidate=candidate,
        required=state in {"UNAVAILABLE_INPUT", "OPEN_ACTION"},
    )
    escape = evaluation.get("review_escape", {"state": "not_assessed"})
    escape = validate_p40_escape(
        escape,
        root,
        occurrence_pointer=occurrence_pointer,
        occurrence_sha256=occurrence_sha256,
        candidate_source=candidate,
    )
    require(
        escape.get("state") in {"none_observed", "present"},
        "an explicit occurrence evaluation must classify P40 review_escape",
    )

    if state == "BOUNDED_LIMITATION":
        require(
            bool(evaluation.get("limitation")), "bounded limitation needs a limitation statement"
        )
        falsifier = evaluation.get("falsifier")
        require(isinstance(falsifier, dict), "bounded limitation needs a falsifier object")
        require(bool(falsifier.get("command")), "bounded limitation needs a falsifier command")
        falsifier_ref = validate_pinned_evidence_ref(
            root,
            falsifier.get("result_ref"),
            occurrence_pointer=occurrence_pointer,
            occurrence_sha256=occurrence_sha256,
            candidate_source=candidate,
            label="falsifier.result_ref",
        )
        falsifier = {"command": falsifier["command"], "result_ref": falsifier_ref}
    if state == "UNAVAILABLE_INPUT":
        missing = evaluation.get("missing_input")
        require(isinstance(missing, dict), "unavailable input needs a missing_input object")
        require(bool(missing.get("identity")), "missing input identity required")
        missing_ref = validate_pinned_evidence_ref(
            root,
            missing.get("unavailability_ref"),
            occurrence_pointer=occurrence_pointer,
            occurrence_sha256=occurrence_sha256,
            candidate_source=candidate,
            label="missing_input.unavailability_ref",
        )
        missing = {"identity": missing["identity"], "unavailability_ref": missing_ref}
    if state == "OPEN_ACTION":
        require(
            isinstance(attempts, list) and bool(attempts),
            "open action must record completed attempts",
        )

    disposition = evaluation.get("proposal_disposition")
    if disposition is not None:
        require(disposition in PROPOSAL_DISPOSITIONS, "invalid proposal_disposition")
    if disposition == "closed":
        roles = {ref["role"] for ref in evidence}
        require(
            {"property_positive", "actual_consumer", "negative"} <= roles,
            "proposed closed needs occurrence-bound property, actual-consumer, and negative "
            "evidence",
        )
        require(state == "VERIFIED", "proposed closed requires a VERIFIED occurrence")

    counterexample = evaluation.get("new_defining_property_counterexample")
    if counterexample is not None:
        require(isinstance(counterexample, dict), "new counterexample must be an object")
        require(bool(counterexample.get("summary")), "new counterexample needs a summary")
        counterexample_refs = validate_evidence_refs(
            root,
            counterexample.get("evidence_refs"),
            occurrence_pointer=occurrence_pointer,
            occurrence_sha256=occurrence_sha256,
            candidate=candidate,
            label="new_defining_property_counterexample.evidence_refs",
            required=True,
        )
        require(
            "property_counterexample" in {ref["role"] for ref in counterexample_refs},
            "new counterexample lacks an occurrence-bound property_counterexample ref",
        )
        counterexample = {
            "summary": counterexample["summary"],
            "evidence_refs": counterexample_refs,
        }

    return {
        "candidate_source": candidate,
        "execution_context": execution_context,
        "evidence_refs": evidence,
        "attempts": attempts,
        "review_escape": escape,
        "falsifier": falsifier if state == "BOUNDED_LIMITATION" else None,
        "missing_input": missing if state == "UNAVAILABLE_INPUT" else None,
        "counterexample": counterexample,
    }


def validate_p40_occurrence_sequence(ledger: dict[str, Any]) -> None:
    """Ensure same-class escapes are ordered and later instances stay no-round.

    The second occurrence is the only one that carries the required structural
    widening or bounded-residual resolution. Later occurrences point back to
    that exact occurrence and are recorded as worked examples.
    """
    by_class: dict[str, dict[int, list[tuple[str, str, dict[str, Any]]]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for finding in ledger.get("findings", []):
        for occurrence in finding.get("occurrences", []):
            original = occurrence.get("original", {})
            evaluation = occurrence.get("candidate_evaluation", {})
            escape = evaluation.get("review_escape", {})
            if escape.get("state") != "present":
                continue
            class_id = escape.get("class_id")
            ordinal = escape.get("same_class_ordinal")
            pointer = original.get("occurrence_pointer")
            digest = original.get("sha256")
            require(
                isinstance(class_id, str) and class_id.strip(),
                "P40 class ID missing from escape",
            )
            require(
                isinstance(ordinal, int) and not isinstance(ordinal, bool) and ordinal >= 1,
                "P40 ordinal missing from escape",
            )
            require(
                isinstance(pointer, str)
                and isinstance(digest, str)
                and re.fullmatch(r"[0-9a-f]{64}", digest) is not None,
                "P40 occurrence identity missing",
            )
            by_class[class_id][ordinal].append((pointer, digest, escape))

    for class_id, occurrences in by_class.items():
        ordinals = sorted(occurrences)
        require(
            ordinals == list(range(1, ordinals[-1] + 1)),
            f"P40 class {class_id} has a missing earlier occurrence",
        )
        for ordinal, rows in occurrences.items():
            expected_bucket = "NEW_CLASS" if ordinal == 1 else "SAME_CLASS_DEEPER"
            signatures = {
                json.dumps(
                    {
                        key: escape.get(key)
                        for key in (
                            "bucket",
                            "class_id",
                            "same_class_ordinal",
                            "second_same_class_resolution",
                            "treatment",
                            "class_resolution",
                        )
                    },
                    sort_keys=True,
                )
                for _, _, escape in rows
            }
            require(
                len(signatures) == 1,
                f"P40 occurrence records disagree about one class ordinal: {class_id}/{ordinal}",
            )
            require(
                rows[0][2].get("bucket") == expected_bucket,
                f"P40 bucket/ordinal mismatch for {class_id}/{ordinal}",
            )
        if len(occurrences) == 1:
            continue

        second_pointer, second_digest, second_escape = occurrences[2][0]
        resolution = second_escape.get("second_same_class_resolution")
        require(
            resolution in {"structural_widening", "bounded_residual"},
            f"P40 second occurrence lacks resolution: {class_id}",
        )
        for ordinal in ordinals[2:]:
            for _, _, escape in occurrences[ordinal]:
                require(
                    escape.get("treatment") == "worked_example_no_round",
                    f"P40 later occurrence is not a no-round worked example: {class_id}/{ordinal}",
                )
                require(
                    escape.get("class_resolution")
                    == {
                        "resolution": resolution,
                        "occurrence_pointer": second_pointer,
                        "sha256": second_digest,
                    },
                    (
                        "P40 worked example does not cite the second occurrence resolution: "
                        f"{class_id}/{ordinal}"
                    ),
                )


def apply_evaluations(ledger: dict[str, Any], evaluation_doc: dict[str, Any], root: Path) -> None:
    """Apply explicit occurrence evaluations without inferring formal closure."""
    require(
        ledger.get("source_boundary", {}).get("source_freeze", {}).get("status")
        == "frozen_candidate",
        "occurrence evaluations require a final frozen candidate source",
    )
    require(evaluation_doc.get("schema") == EVALUATION_SCHEMA, "unknown evaluation input schema")
    raw_evaluations = evaluation_doc.get("evaluations")
    require(isinstance(raw_evaluations, list), "evaluations must be an array")
    source_freeze = ledger.get("source_boundary", {}).get("source_freeze", {})
    frozen_candidate = source_freeze.get("candidate_source")
    require(isinstance(frozen_candidate, dict), "ledger is missing its frozen candidate source")
    source_census = source_freeze.get("source_change_census")
    require(isinstance(source_census, dict), "ledger is missing the recomputed full source census")
    expected_frozen_context = {
        "candidate_source": frozen_candidate,
        "source_footprint_ref": "/source_boundary/source_freeze/source_change_census",
        "source_footprint_sha256": canonical_json_sha256(source_census),
    }
    validate_evaluation_frozen_context(
        evaluation_doc,
        expected_frozen_context,
        label="evaluation input",
    )

    occurrences: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
    for finding in ledger["findings"]:
        for occurrence in finding["occurrences"]:
            original = occurrence["original"]
            key = (original["occurrence_pointer"], original["sha256"])
            require(key not in occurrences, f"duplicate occurrence key: {key[0]}")
            occurrences[key] = (finding, occurrence)

    seen: set[tuple[str, str]] = set()
    proposal_dispositions: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for raw in raw_evaluations:
        require(isinstance(raw, dict), "each evaluation must be an object")
        pointer, digest = raw.get("occurrence_pointer"), raw.get("sha256")
        key = (pointer, digest)
        require(key in occurrences, f"unknown occurrence pointer/hash: {pointer}")
        require(key not in seen, f"duplicate evaluation for occurrence: {pointer}")
        finding, occurrence = occurrences[key]
        normalized = validate_explicit_evaluation(
            raw,
            root,
            pointer,
            digest,
            finding_id=finding["finding_id"],
            source_footprint_sha256=expected_frozen_context["source_footprint_sha256"],
            complete_census=source_census,
        )
        require(
            normalized["candidate_source"] == frozen_candidate,
            f"evaluation candidate differs from the frozen source checkpoint: {pointer}",
        )
        seen.add(key)
        evaluation = {
            "state": raw["state"],
            "assessment": "explicit_candidate_evaluation",
            "candidate_source": normalized["candidate_source"],
            "execution_context": normalized["execution_context"],
            "result_summary": raw["result_summary"],
            "boundary": raw["boundary"],
            "evidence_refs": normalized["evidence_refs"],
            "attempts": normalized["attempts"],
            "next_check": raw["next_check"],
            "review_escape": normalized["review_escape"],
            "proposal_disposition": raw.get("proposal_disposition"),
        }
        if raw["state"] == "BOUNDED_LIMITATION":
            evaluation["limitation"] = raw["limitation"]
            evaluation["falsifier"] = normalized["falsifier"]
        if raw["state"] == "UNAVAILABLE_INPUT":
            evaluation["missing_input"] = normalized["missing_input"]
        if normalized["counterexample"] is not None:
            evaluation["new_defining_property_counterexample"] = normalized["counterexample"]
        occurrence["candidate_evaluation"] = evaluation
        if raw.get("proposal_disposition") is not None:
            proposal_dispositions[finding["finding_id"]].append(
                {
                    "pointer": pointer,
                    "disposition": raw["proposal_disposition"],
                    "candidate_source": normalized["candidate_source"],
                }
            )

    for finding_id, requested in proposal_dispositions.items():
        finding = next(row for row in ledger["findings"] if row["finding_id"] == finding_id)
        expected_pointers = {
            occurrence["original"]["occurrence_pointer"] for occurrence in finding["occurrences"]
        }
        actual_pointers = {item["pointer"] for item in requested}
        dispositions = {item["disposition"] for item in requested}
        require(
            actual_pointers == expected_pointers,
            f"proposal lacks per-occurrence input: {finding_id}",
        )
        by_pointer = {item["pointer"]: item for item in requested}
        ordered = [by_pointer[pointer] for pointer in sorted(expected_pointers)]
        sources = {json.dumps(item["candidate_source"], sort_keys=True) for item in ordered}
        same_candidate = len(sources) == 1

        if finding_id == "B198":
            reopened = any(item["disposition"] != "closed" for item in ordered)
            if reopened:
                for occurrence in finding["occurrences"]:
                    evaluation = occurrence["candidate_evaluation"]
                    require(
                        evaluation.get("new_defining_property_counterexample") is not None,
                        "B198 historical closure cannot be reopened without an occurrence-"
                        "specific defining-property counterexample",
                    )

        if dispositions == {"closed"}:
            require(
                same_candidate, f"closed proposal spans different candidate sources: {finding_id}"
            )
            for occurrence in finding["occurrences"]:
                evaluation = occurrence["candidate_evaluation"]
                require(
                    evaluation["state"] == "VERIFIED",
                    f"proposed closed has unverified occurrence: {finding_id}",
                )
                roles = {ref["role"] for ref in evaluation["evidence_refs"]}
                require(
                    {"property_positive", "actual_consumer", "negative"} <= roles,
                    f"proposed closed lacks occurrence-specific property/consumer/negative "
                    f"evidence: {finding_id}",
                )

        disposition = next(iter(dispositions)) if len(dispositions) == 1 else None
        finding["candidate_proposal"] = {
            "disposition": disposition,
            "status": (
                "proposal_only_not_G_adjudication"
                if disposition is not None and same_candidate
                else "occurrence_proposals_differ_or_span_candidates_not_G_adjudication"
            ),
            "basis_occurrence_pointers": sorted(actual_pointers),
            "occurrence_dispositions": [
                {"occurrence_pointer": item["pointer"], "disposition": item["disposition"]}
                for item in ordered
            ],
            "candidate_sources": [item["candidate_source"] for item in ordered],
        }


def validate_ledger(ledger: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, int]:
    """Reconcile IDs, routes, original locators, and occurrence evaluations."""
    require(ledger.get("schema") == SCHEMA, "ledger schema mismatch")
    require(
        ledger.get("formal_closure_ids") == [],
        "proposal ledger formal_closure_ids must remain empty",
    )
    require(
        ledger.get("formal_closure_ids") == snapshot["inputs"].get("formal_closure_ids", []),
        "formal closure IDs changed",
    )
    require(
        ledger["source_boundary"].get("original_entry") == snapshot["original_entry"],
        "original entry anchor mismatch",
    )
    require(
        ledger["source_boundary"].get("report_checkout") == snapshot["report_checkout"],
        "report checkout anchor mismatch",
    )
    recorded_freeze = ledger["source_boundary"].get("source_freeze")
    current_freeze = snapshot["source_freeze"]
    require(isinstance(recorded_freeze, dict), "complete-tree source freeze missing")
    require(
        {
            key: recorded_freeze.get(key)
            for key in (
                "status",
                "candidate_source",
                "closure",
                "validator",
                "source_change_census",
            )
        }
        == {
            key: current_freeze.get(key)
            for key in (
                "status",
                "candidate_source",
                "closure",
                "validator",
                "source_change_census",
            )
        },
        "source-freeze candidate/tree, typed artifact policy, or validator changed",
    )
    require(
        ledger["source_boundary"].get("execution_plan_source") == snapshot["execution_plan_source"],
        "execution-plan source ref differs from the immutable original-entry blob",
    )
    require(
        ledger["source_boundary"].get("closeout_support_sources")
        == snapshot["closeout_support_sources"],
        "closeout support source refs differ from the immutable original-entry blobs",
    )
    require(
        ledger.get("replay_selection", {}).get("candidate_source_freeze_ref")
        == "/source_boundary/source_freeze",
        "replay selection does not point to the single source-freeze record",
    )
    provisional = recorded_freeze.get("status") == "provisional_source_checkpoint_not_frozen"
    require(
        ledger.get("evaluation_mode")
        == (
            "provisional_author_review_pending_final_source_freeze"
            if provisional
            else "frozen_candidate_explicit_occurrence_updates"
        ),
        "evaluation mode disagrees with source-freeze status",
    )
    require(
        ledger["route_census"] == snapshot["route_census"],
        "route census differs from recomputed complete source set",
    )
    require(
        ledger["source_boundary"].get("input_sources") == snapshot["tracked_inputs"],
        "pinned input source refs differ from original-entry/report checkout comparison",
    )
    require(
        ledger["source_boundary"].get("criterion_sources")
        == list(snapshot["criterion_sources"].values()),
        "criterion source catalog differs from the complete coverage manifest",
    )
    require(
        ledger["source_boundary"].get("author_source_catalog")
        == list(snapshot["author_sources"].values()),
        "author source catalog differs from immutable packet refs",
    )
    rows = ledger.get("findings")
    require(isinstance(rows, list), "findings must be an array")
    row_ids = [row.get("finding_id") for row in rows]
    expected_ids = [row["id"] for row in snapshot["coverage"]["findings"]]
    require(len(row_ids) == len(set(row_ids)), "duplicate finding ID in ledger")
    require(row_ids == expected_ids, "ledger finding ID set/order differs from source")
    require(
        ledger.get("denominator")
        == {
            "bundles": len(snapshot["coverage"]["bundles"]),
            "finding_ids": len(expected_ids),
            "canonical_occurrences": snapshot["occurrence_count"],
        },
        "ledger denominator does not match the complete pinned source set",
    )

    occurrence_count = 0
    unrun_count = 0
    for coverage_row, row in zip(snapshot["coverage"]["findings"], rows, strict=True):
        finding_id = row["finding_id"]
        author = snapshot["author_by_id"][finding_id]
        coverage = snapshot["coverage_by_id"][finding_id]
        require(
            row["ownership"]
            == {
                "unit": coverage["unit"],
                "primary_bundle": coverage["primary_bundle"],
                "source_closure_owner_literal": coverage["source_closure_owner_literal"],
                "companion_bundles": coverage["companion_bundles"],
            },
            f"ownership source mismatch: {finding_id}",
        )
        require(
            row["historical"]["ledger_status"] == coverage["ledger_status_historical"],
            f"historical ledger mismatch: {finding_id}",
        )
        require(
            row["historical"]["appendix_c_status"] == coverage["appendix_c_status_separate"],
            f"Appendix C status mismatch: {finding_id}",
        )
        require(
            row["historical"]["closure_now"] == coverage["closure_now"],
            f"current closure field mismatch: {finding_id}",
        )
        require(
            row["source_author_proposal"]["disposition"] == author["author_proposal"],
            f"author proposal mismatch: {finding_id}",
        )
        require(
            row["source_author_proposal"]["G_closure_field"] == author["G_closure"],
            f"G closure source field mismatch: {finding_id}",
        )
        require(
            row["source_author_proposal"]["row_pointers"] == author["author_row_pointers"],
            f"author row pointer mismatch: {finding_id}",
        )
        require(
            row["original_routes"]["next_tasks"] == author["next_tasks"],
            f"original task route mismatch: {finding_id}",
        )
        require(
            row["original_routes"]["current_tasks"] == snapshot["routes"][finding_id],
            f"current route mismatch: {finding_id}",
        )
        require(
            row["original_routes"]["flows"] == author["flows"],
            f"original flow mismatch: {finding_id}",
        )

        expected_refs = []
        for occurrence_index, ref in enumerate(coverage_row["criterion_refs"]):
            source = snapshot["criterion_sources"][ref["document"]]
            expected_refs.append(
                {
                    "occurrence_pointer": (
                        f"{CRITERIA_COVERAGE_PATH.as_posix()}#/findings/"
                        f"{expected_ids.index(finding_id)}/criterion_refs/{occurrence_index}"
                    ),
                    "author_pointer": (f"{author['original_criteria_pointer']}/{occurrence_index}"),
                    "criterion_id": ref["criterion_id"],
                    "document": ref["document"],
                    "card_binding": ref["card"],
                    "source_path": source["path"],
                    "source_commit": source["source_commit"],
                    "source_blob": source["source_blob"],
                    "lines": ref["lines"],
                    "sha256": ref["sha256"],
                }
            )
        occurrences = row.get("occurrences")
        require(isinstance(occurrences, list), f"occurrences missing: {finding_id}")
        actual_refs = [item.get("original") for item in occurrences]
        require(actual_refs == expected_refs, f"occurrence refs/hash/order mismatch: {finding_id}")
        pointers = [item["occurrence_pointer"] for item in actual_refs]
        require(len(pointers) == len(set(pointers)), f"duplicate occurrence pointer: {finding_id}")
        occurrence_count += len(occurrences)

        for occurrence_index, (item, source_ref) in enumerate(
            zip(occurrences, coverage_row["criterion_refs"], strict=True)
        ):
            source = snapshot["criterion_sources"][source_ref["document"]]
            expected_crosswalk = exact_occurrence_author_refs(
                snapshot, author, coverage, occurrence_index
            )
            require(
                item.get("author_crosswalk") == expected_crosswalk,
                f"author occurrence crosswalk mismatch: {finding_id}/{occurrence_index}",
            )
            expected_property_refs = {
                "criterion_occurrence": expected_refs[occurrence_index]["occurrence_pointer"],
                "criterion_source": {
                    "path": source["path"],
                    "commit": source["source_commit"],
                    "git_blob": source["source_blob"],
                    "lines": source_ref["lines"],
                    "sha256": source_ref["sha256"],
                },
                "criterion_specific_acceptance_boundary": original_property_boundary(
                    coverage_path=CRITERIA_COVERAGE_PATH.as_posix(),
                    coverage_source_index=next(
                        index
                        for index, source_input in enumerate(snapshot["tracked_inputs"])
                        if source_input.get("role") == "coverage"
                        and source_input.get("path") == CRITERIA_COVERAGE_PATH.as_posix()
                    ),
                    coverage_index=snapshot["coverage_index_by_id"][finding_id],
                    coverage_row=coverage,
                    author_crosswalk=expected_crosswalk,
                ),
            }
            require(
                item.get("original_property_refs") == expected_property_refs,
                f"original property locator mismatch: {finding_id}/{occurrence_index}",
            )
            expected_queue = author_queue(snapshot, author, coverage, occurrence_index)
            require(
                item.get("work_queue") == expected_queue,
                f"occurrence action queue mismatch: {finding_id}/{occurrence_index}",
            )
            expected_review = provisional_occurrence_review()
            require(
                item.get("provisional_review") == expected_review,
                f"provisional author-review boundary mismatch: {finding_id}/{occurrence_index}",
            )

            evaluation = item.get("candidate_evaluation")
            require(isinstance(evaluation, dict), f"candidate evaluation missing: {finding_id}")
            state = evaluation.get("state")
            require(state in OUTCOME_STATES | {"UNRUN"}, f"invalid evaluation state: {finding_id}")
            if state == "UNRUN":
                unrun_count += 1
                expected_unrun = initial_occurrence(
                    finding_id=finding_id,
                    coverage_index=snapshot["coverage_index_by_id"][finding_id],
                    occurrence_index=occurrence_index,
                    ref=source_ref,
                    author_row=author,
                    source=source,
                    task_routes=snapshot["routes"][finding_id],
                    coverage_path=CRITERIA_COVERAGE_PATH.as_posix(),
                    report_checkpoint=snapshot["report_checkout"],
                    work_queue=expected_queue,
                )["candidate_evaluation"]
                require(
                    evaluation == expected_unrun,
                    f"UNRUN occurrence contains unearned candidate claims: "
                    f"{finding_id}/{occurrence_index}",
                )
            else:
                require(
                    not provisional,
                    f"provisional source review cannot carry a candidate evaluation: "
                    f"{finding_id}/{occurrence_index}",
                )
                require(
                    evaluation.get("assessment") == "explicit_candidate_evaluation",
                    f"assessment provenance missing: {finding_id}",
                )
                normalized = validate_explicit_evaluation(
                    evaluation,
                    snapshot["repo_root"],
                    expected_refs[occurrence_index]["occurrence_pointer"],
                    source_ref["sha256"],
                    finding_id=finding_id,
                    source_footprint_sha256=canonical_json_sha256(
                        current_freeze["source_change_census"]
                    ),
                    complete_census=current_freeze["source_change_census"],
                )
                require(
                    evaluation.get("candidate_source") == normalized["candidate_source"],
                    f"candidate source mismatch: {finding_id}/{occurrence_index}",
                )
                require(
                    evaluation.get("execution_context") == normalized["execution_context"],
                    f"execution context normalization mismatch: {finding_id}/{occurrence_index}",
                )
                require(
                    normalized["candidate_source"] == current_freeze["candidate_source"],
                    f"evaluation is not bound to the frozen complete candidate tree: "
                    f"{finding_id}/{occurrence_index}",
                )
                require(
                    evaluation.get("evidence_refs") == normalized["evidence_refs"],
                    f"evidence normalization mismatch: {finding_id}/{occurrence_index}",
                )
                require(
                    evaluation.get("attempts") == normalized["attempts"],
                    f"attempt normalization mismatch: {finding_id}/{occurrence_index}",
                )
                require(
                    evaluation.get("review_escape") == normalized["review_escape"],
                    f"P40 review escape normalization mismatch: {finding_id}/{occurrence_index}",
                )
                require(
                    evaluation.get("falsifier") == normalized["falsifier"],
                    f"falsifier normalization mismatch: {finding_id}/{occurrence_index}",
                )
                require(
                    evaluation.get("missing_input") == normalized["missing_input"],
                    f"unavailable-input normalization mismatch: {finding_id}/{occurrence_index}",
                )
                require(
                    evaluation.get("new_defining_property_counterexample")
                    == normalized["counterexample"],
                    f"counterexample normalization mismatch: {finding_id}/{occurrence_index}",
                )

        proposal = row.get("candidate_proposal")
        if provisional:
            require(
                proposal is None,
                f"provisional review cannot carry a finding proposal: {finding_id}",
            )
        if proposal is not None:
            require(
                isinstance(proposal, dict),
                f"candidate proposal must be object or null: {finding_id}",
            )
            disposition = proposal.get("disposition")
            require(
                disposition is None or disposition in PROPOSAL_DISPOSITIONS,
                f"invalid candidate proposal: {finding_id}",
            )
            expected_pointers = {ref["occurrence_pointer"] for ref in expected_refs}
            require(
                set(proposal.get("basis_occurrence_pointers", [])) == expected_pointers,
                f"proposal basis incomplete: {finding_id}",
            )
            occurrence_dispositions = [
                {
                    "occurrence_pointer": item["original"]["occurrence_pointer"],
                    "disposition": item["candidate_evaluation"].get("proposal_disposition"),
                }
                for item in occurrences
            ]
            require(
                all(entry["disposition"] is not None for entry in occurrence_dispositions),
                f"finding proposal lacks per-occurrence dispositions: {finding_id}",
            )
            require(
                proposal.get("occurrence_dispositions") == occurrence_dispositions,
                f"finding proposal occurrence dispositions mismatch: {finding_id}",
            )
            sources = [item["candidate_evaluation"]["candidate_source"] for item in occurrences]
            require(
                proposal.get("candidate_sources") == sources,
                f"finding proposal candidate source list mismatch: {finding_id}",
            )
            dispositions = {entry["disposition"] for entry in occurrence_dispositions}
            expected_disposition = next(iter(dispositions)) if len(dispositions) == 1 else None
            require(
                disposition == expected_disposition,
                f"finding proposal disposition mismatch: {finding_id}",
            )
            same_candidate = len({json.dumps(source, sort_keys=True) for source in sources}) == 1
            expected_status = (
                "proposal_only_not_G_adjudication"
                if disposition is not None and same_candidate
                else "occurrence_proposals_differ_or_span_candidates_not_G_adjudication"
            )
            require(
                proposal.get("status") == expected_status,
                f"proposal authority/status label mismatch: {finding_id}",
            )
            if disposition == "closed":
                require(
                    same_candidate,
                    f"closed proposal spans different candidate sources: {finding_id}",
                )
                for item in occurrences:
                    evaluation = item["candidate_evaluation"]
                    roles = {ref["role"] for ref in evaluation["evidence_refs"]}
                    require(
                        evaluation["state"] == "VERIFIED"
                        and {"property_positive", "actual_consumer", "negative"} <= roles,
                        f"proposed closed lacks occurrence-specific property/consumer/negative "
                        f"evidence: {finding_id}",
                    )
            if finding_id == "B198" and any(
                entry["disposition"] != "closed" for entry in occurrence_dispositions
            ):
                for item in occurrences:
                    require(
                        item["candidate_evaluation"].get("new_defining_property_counterexample")
                        is not None,
                        "B198 historical closure cannot be reopened without occurrence-specific "
                        "defining-property counterexample",
                    )
        else:
            for item in occurrences:
                require(
                    item["candidate_evaluation"].get("proposal_disposition") is None,
                    f"occurrence disposition exists without finding-level proposal: {finding_id}",
                )
    validate_p40_occurrence_sequence(ledger)
    require(
        occurrence_count == snapshot["occurrence_count"], "ledger occurrence denominator mismatch"
    )
    require(
        ledger["denominator"]["finding_ids"] == len(expected_ids),
        "ledger finding denominator mismatch",
    )
    require(
        ledger["denominator"]["canonical_occurrences"] == occurrence_count,
        "ledger occurrence denominator field mismatch",
    )
    return {
        "finding_ids": len(expected_ids),
        "occurrences": occurrence_count,
        "unrun_occurrences": unrun_count,
    }


def self_check(ledger: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Probe explicit occurrence updates and reject count-preserving corruptions."""
    validate_ledger(ledger, snapshot)
    root = snapshot["repo_root"]
    report_checkpoint = ledger["source_boundary"]["report_checkout"]
    git_read_checks = git_read_boundary_self_check(
        root,
        candidate_source={
            "commit": report_checkpoint["commit"],
            "tree": report_checkpoint["tree"],
        },
        original_entry=snapshot["original_entry"],
    )
    # The input-shape probe is deliberately synthetic: before the final source
    # freeze there is no candidate identity to bind. It proves only that the
    # import schema rejects malformed authority context; apply_evaluations
    # performs the real candidate/census equality check.
    frozen_context = {
        "candidate_source": {"commit": "0" * 40, "tree": "1" * 40},
        "source_footprint_ref": "/source_boundary/source_freeze/source_change_census",
        "source_footprint_sha256": "2" * 64,
    }
    empty_update_input = {
        "schema": EVALUATION_SCHEMA,
        "frozen_context": frozen_context,
        "evaluations": [],
    }
    validate_evaluation_input_artifact(empty_update_input, label="self-check empty update input")
    validate_evaluation_frozen_context(
        empty_update_input, frozen_context, label="self-check empty update input"
    )
    frozen_context_rejections = 0
    for field, corrupt_value in (
        (
            "candidate_source",
            {
                "commit": frozen_context["candidate_source"]["commit"],
                "tree": "0" * 40,
            },
        ),
        ("source_footprint_sha256", "0" * 64),
    ):
        corrupted_input = copy.deepcopy(empty_update_input)
        corrupted_input["frozen_context"][field] = corrupt_value
        try:
            validate_evaluation_frozen_context(
                corrupted_input, frozen_context, label="self-check corrupt frozen context"
            )
        except (KeyError, TypeError, ValueError):
            frozen_context_rejections += 1
            continue
        raise ValueError(f"self-check accepted corrupt frozen_context.{field}")

    malformed_task_status = copy.deepcopy(empty_update_input)
    malformed_task_status["task_status"] = "PASS"
    try:
        validate_evaluation_input_artifact(
            malformed_task_status, label="self-check task-level status rejection"
        )
    except (KeyError, TypeError, ValueError):
        task_status_rejected = True
    else:
        raise ValueError("self-check accepted a task-level status as an evaluation input")

    input_digest = "a" * 64
    input_roles = [
        "selected_input",
        "input_authority",
        "input_permission",
        "input_context",
        "input_verification",
    ]
    input_probe_refs = [
        {
            "role": role,
            "input_identity": "probe-dataset-1",
            "pointer": f"/manifest/inputs/0/{role}",
            **({"input_sha256": input_digest} if role == "selected_input" else {}),
            **({"verification_status": "verified"} if role == "input_verification" else {}),
        }
        for role in input_roles
    ]
    input_probe_rows = [
        {
            "identity": "probe-dataset-1",
            "status": "available",
            "sha256": input_digest,
        }
    ]
    validate_input_evidence_bindings(
        "available",
        list(range(len(input_probe_refs))),
        input_probe_refs,
        input_probe_rows,
        label="self-check selected-input binding",
    )
    input_context_rejections = 0
    corrupted_input_refs = copy.deepcopy(input_probe_refs)
    corrupted_input_refs.pop(2)
    try:
        validate_input_evidence_bindings(
            "available",
            list(range(len(corrupted_input_refs))),
            corrupted_input_refs,
            input_probe_rows,
            label="self-check missing input permission ref",
        )
    except (KeyError, TypeError, ValueError):
        input_context_rejections += 1
    else:
        raise ValueError("self-check accepted a selected input without permission evidence")
    corrupted_input_refs = copy.deepcopy(input_probe_refs)
    corrupted_input_refs[0]["input_sha256"] = "0" * 64
    try:
        validate_input_evidence_bindings(
            "available",
            list(range(len(corrupted_input_refs))),
            corrupted_input_refs,
            input_probe_rows,
            label="self-check wrong selected-input hash",
        )
    except (KeyError, TypeError, ValueError):
        input_context_rejections += 1
    else:
        raise ValueError("self-check accepted an input evidence hash mismatch")

    output_path = (LOCAL_REL / "finding-proposals.json").as_posix()
    typed_output = serialized_json(ledger)
    accepted_report_changes = require_typed_report_changes(
        [("M", output_path)],
        label="self-check typed report positive",
        payload_for_path=lambda _: typed_output,
    )
    require(
        accepted_report_changes == [output_path],
        "typed proposal output was not recognized as report data",
    )
    slice_path = (LOCAL_REL / "q0-crosswalk.json").as_posix()
    report_checkpoint = ledger["source_boundary"]["report_checkout"]
    source_identity = {
        "commit": report_checkpoint["commit"],
        "tree": report_checkpoint["tree"],
    }
    original_entry = ledger["source_boundary"]["original_entry"]
    slice_base_identity = {
        "commit": original_entry["commit"],
        "tree": original_entry["tree"],
    }
    candidate_parent_ids = git_text(
        root, "show", "-s", "--format=%P", source_identity["commit"]
    ).split()
    shared_occurrences = [
        {
            "finding_id": "probe-one",
            "occurrence_pointer": "coverage.json#/findings/0/criterion_refs/0",
            "criterion_sha256": "1" * 64,
        },
        {
            "finding_id": "probe-two",
            "occurrence_pointer": "coverage.json#/findings/1/criterion_refs/0",
            "criterion_sha256": "2" * 64,
        },
    ]
    decision_source_path = (BASE_REL / "closure-decisions/coverage.json").as_posix()
    decision_source_bytes = git_bytes(
        root, "show", f"{source_identity['commit']}:{decision_source_path}"
    )
    decision_source_blob = git_text(
        root, "rev-parse", f"{source_identity['commit']}:{decision_source_path}"
    )

    def decision_source_ref(
        source_index: int,
        occurrence_index: int,
        *,
        role: str,
    ) -> dict[str, Any]:
        occurrence = shared_occurrences[occurrence_index]
        return {
            "path": decision_source_path,
            "commit": source_identity["commit"],
            "git_blob": decision_source_blob,
            "sha256": sha256(decision_source_bytes),
            "role": role,
            "covers": {
                "occurrence_pointer": occurrence["occurrence_pointer"],
                "sha256": occurrence["criterion_sha256"],
            },
            "candidate_source": source_identity,
            "pointer": f"#/findings/{source_index}",
        }

    shared_decisions = [
        {
            "kind": "alternative",
            "option_id": "reuse-existing",
            "tradeoff": "Preserve existing route with a smaller change surface.",
            "discriminator": "The existing consumer accepts the added source-bound row.",
            "source_ref": decision_source_ref(0, 0, role="decision_alternative"),
        },
        {
            "kind": "alternative",
            "option_id": "extend-consumer",
            "tradeoff": "Adds a consumer path while preserving the public contract.",
            "discriminator": "The existing consumer rejects the added source-bound row.",
            "source_ref": decision_source_ref(1, 0, role="decision_alternative"),
        },
        {
            "kind": "prototype",
            "argv": ["python", "-m", "pytest", "-k", "reuse_existing"],
            "status": "PASS",
            "source_ref": decision_source_ref(2, 0, role="prototype_result"),
        },
        {
            "kind": "prototype",
            "argv": ["python", "-m", "pytest", "-k", "other_occurrence"],
            "status": "UNRUN",
            "source_ref": decision_source_ref(3, 1, role="prototype_result"),
        },
    ]
    slice_handoff = {
        "schema": SLICE_HANDOFF_SCHEMA,
        "slice_id": "q0-crosswalk",
        "slice_base": slice_base_identity,
        "candidate_source": source_identity,
        "parents": candidate_parent_ids,
        "source_footprint": [{"path": "policy-engine/tests/unit/example.py", "change": "M"}],
        "selected_inputs": [],
        "backend_profile": {"status": "named"},
        "commands": [
            {
                "argv": ["python", "-m", "pytest"],
                "status": "PASS",
                "stdout_ref": {
                    "storage": "ignored_local_raw",
                    "path": (
                        "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs"
                        "/LOCAL/raw/pre-freeze-generated-checks/abi.stdout.txt"
                    ),
                    "sha256": "1" * 64,
                    "candidate_source": source_identity,
                    "availability": "available_local_readback",
                },
                "stderr_ref": {"path": "raw/test.stderr", "sha256": "2" * 64},
            }
        ],
        "chain": {"producer": "source-bound", "consumer": "actual"},
        "controls": [{"kind": "negative", "status": "recorded"}],
        "consumer_surface": {"kind": "test-consumer"},
        "limitations": [],
        "decision_refs": shared_decisions,
        "proposal_ids": ["probe-one", "probe-two"],
        "proposal_occurrences": shared_occurrences,
        "formal_closure_ids": [],
    }
    accepted_slice_paths = require_typed_report_changes(
        [("A", slice_path)],
        label="self-check exact slice report positive",
        payload_for_path=lambda _: json.dumps(slice_handoff).encode("utf-8"),
        expected_candidate=source_identity,
    )
    require(
        accepted_slice_paths == [slice_path], "typed direct-child slice handoff was not recognized"
    )
    source_relationship = validate_slice_source_relationships(
        root,
        slice_handoff,
        label="self-check candidate ancestry and ordered parents",
    )
    parent_mutation_rejected = False
    wrong_parent_handoff = copy.deepcopy(slice_handoff)
    wrong_parent_handoff["parents"] = ["0" * 40]
    try:
        validate_slice_source_relationships(
            root,
            wrong_parent_handoff,
            label="self-check forged candidate parent",
        )
    except ValueError as exc:
        parent_mutation_rejected = "actual Git parent" in str(exc)
    if not parent_mutation_rejected:
        raise ValueError("self-check accepted forged candidate parents")

    wrong_candidate_tree_handoff = copy.deepcopy(slice_handoff)
    wrong_candidate_tree_handoff["candidate_source"]["tree"] = "0" * 40
    try:
        validate_slice_source_relationships(
            root,
            wrong_candidate_tree_handoff,
            label="self-check forged candidate tree",
        )
    except ValueError as exc:
        candidate_tree_mutation_rejected = "candidate commit/tree" in str(exc)
    else:
        candidate_tree_mutation_rejected = False
    if not candidate_tree_mutation_rejected:
        raise ValueError("self-check accepted a candidate tree not owned by its commit")

    wrong_slice_base_tree_handoff = copy.deepcopy(slice_handoff)
    wrong_slice_base_tree_handoff["slice_base"]["tree"] = "0" * 40
    try:
        validate_slice_source_relationships(
            root,
            wrong_slice_base_tree_handoff,
            label="self-check forged slice-base tree",
        )
    except ValueError as exc:
        slice_base_tree_mutation_rejected = "candidate commit/tree" in str(exc)
    else:
        slice_base_tree_mutation_rejected = False
    if not slice_base_tree_mutation_rejected:
        raise ValueError("self-check accepted a slice-base tree not owned by its commit")

    root_commit_ids = git_text(root, "rev-list", "--all", "--max-parents=0").splitlines()
    require(bool(root_commit_ids), "self-check could not find a repository root commit")
    root_candidate_ref = {
        "commit": root_commit_ids[0],
        "tree": git_text(root, "rev-parse", f"{root_commit_ids[0]}^{{tree}}"),
    }
    root_candidate, root_parent_ids = git_commit_source(
        root,
        root_candidate_ref,
        label="self-check root candidate",
    )
    root_handoff = {
        "slice_base": root_candidate,
        "candidate_source": root_candidate,
        "parents": root_parent_ids,
    }
    require(not root_parent_ids, "self-check root commit unexpectedly has parents")
    validate_slice_source_relationships(
        root, root_handoff, label="self-check parentless root commit"
    )

    unrelated_root = None
    for root_commit in root_commit_ids:
        ancestor_probe = git_run(
            root,
            "merge-base",
            "--is-ancestor",
            root_commit,
            source_identity["commit"],
            check=False,
        )
        require(
            ancestor_probe.returncode in {0, 1},
            "self-check could not resolve a repository root ancestry probe",
        )
        if ancestor_probe.returncode == 1:
            unrelated_root = root_commit
            break
    require(unrelated_root is not None, "self-check needs an unrelated root for ancestry rejection")
    unrelated_root_ref = {
        "commit": unrelated_root,
        "tree": git_text(root, "rev-parse", f"{unrelated_root}^{{tree}}"),
    }
    unrelated_base, _ = git_commit_source(
        root,
        unrelated_root_ref,
        label="self-check unrelated root",
    )
    nonancestor_handoff = copy.deepcopy(slice_handoff)
    nonancestor_handoff["slice_base"] = unrelated_base
    try:
        validate_slice_source_relationships(
            root, nonancestor_handoff, label="self-check unrelated slice base"
        )
    except ValueError as exc:
        nonancestor_base_rejected = "not an ancestor" in str(exc)
    else:
        nonancestor_base_rejected = False
    if not nonancestor_base_rejected:
        raise ValueError("self-check accepted a slice base outside candidate ancestry")

    empty_tree_id = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    empty_initial_header = (
        f"tree {empty_tree_id}\nauthor Self Check <self-check@example.invalid> 0 +0000\n"
        "committer Self Check <self-check@example.invalid> 0 +0000\n\n"
    ).encode("ascii")
    parsed_empty_tree, parsed_empty_parents = parse_git_commit_header(
        empty_initial_header,
        label="self-check empty initial commit header",
    )
    require(
        parsed_empty_tree == empty_tree_id and parsed_empty_parents == [],
        "self-check did not preserve an empty initial commit with no parents",
    )
    merge_parent_ids = ["1" * 40, "2" * 40]
    merge_header = (
        f"tree {'3' * 40}\nparent {merge_parent_ids[0]}\nparent {merge_parent_ids[1]}\n"
        "author Self Check <self-check@example.invalid> 0 +0000\n"
        "committer Self Check <self-check@example.invalid> 0 +0000\n\n"
    ).encode("ascii")
    parsed_merge_tree, parsed_merge_parents = parse_git_commit_header(
        merge_header,
        label="self-check ordered merge parents",
    )
    require(
        parsed_merge_tree == "3" * 40 and parsed_merge_parents == merge_parent_ids,
        "self-check did not preserve ordered merge parents",
    )
    raw_fixture_path = LOCAL_RAW_PREFIX + "pre-freeze-generated-checks/abi.stdout.txt"
    raw_fixture_digest = sha256((root / raw_fixture_path).read_bytes())
    raw_fixture_ref = {
        "storage": LOCAL_RAW_STORAGE,
        "path": raw_fixture_path,
        "sha256": raw_fixture_digest,
        "candidate_source": source_identity,
        "availability": "available_local_readback",
    }
    validate_local_raw_output(
        root,
        raw_fixture_ref,
        candidate_source=source_identity,
        label="self-check available ignored raw output",
    )
    ignored_raw_rejections = 0
    raw_mutations = [
        ("wrong_sha256", {**raw_fixture_ref, "sha256": "0" * 64}),
        (
            "missing_file",
            {
                **raw_fixture_ref,
                "path": LOCAL_RAW_PREFIX + "crosswalk/absent-self-check.stdout.txt",
            },
        ),
        (
            "traversal_escape",
            {
                **raw_fixture_ref,
                "path": LOCAL_RAW_PREFIX + "../../../../../../AGENTS.md",
            },
        ),
        (
            "wrong_candidate",
            {
                **raw_fixture_ref,
                "candidate_source": {"commit": "0" * 40, "tree": "1" * 40},
            },
        ),
        (
            "unavailable_readback",
            {**raw_fixture_ref, "availability": "unavailable"},
        ),
        (
            "unstated_storage",
            {key: value for key, value in raw_fixture_ref.items() if key != "storage"},
        ),
    ]
    for name, corrupted_ref in raw_mutations:
        try:
            validate_local_raw_output(
                root,
                corrupted_ref,
                candidate_source=source_identity,
                label=f"self-check ignored raw {name}",
            )
        except (KeyError, OSError, TypeError, ValueError):
            ignored_raw_rejections += 1
        else:
            raise ValueError(f"self-check accepted ignored raw mutation: {name}")
    with tempfile.TemporaryDirectory(
        prefix=".ignored-raw-symlink-self-check-",
        dir=root / LOCAL_REL / "crosswalk/checks",
    ) as temporary_root_name:
        temporary_root = Path(temporary_root_name)
        symlink_relative_path = LOCAL_RAW_PREFIX + "symlink-self-check.stdout.txt"
        symlink_target = temporary_root / "outside-raw-root.txt"
        symlink_target.write_text("synthetic symlink probe", encoding="utf-8")
        symlink_path = temporary_root.joinpath(
            *local_raw_path_parts(
                symlink_relative_path,
                label="self-check symlink path",
            )
        )
        symlink_path.parent.mkdir(parents=True)
        symlink_path.symlink_to(symlink_target)
        try:
            local_raw_target(
                temporary_root,
                symlink_relative_path,
                label="self-check ignored raw symlink",
            )
        except ValueError:
            symlink_rejected = True
        else:
            raise ValueError("self-check accepted a symlink as ignored raw output")
    with tempfile.TemporaryDirectory(
        prefix=".ignored-raw-parent-symlink-self-check-",
        dir=root / LOCAL_REL / "crosswalk/checks",
    ) as temporary_root_name:
        temporary_root = Path(temporary_root_name)
        symlink_relative_path = LOCAL_RAW_PREFIX + "linked-directory/output.stdout.txt"
        symlink_target_directory = temporary_root / "outside-raw-directory"
        symlink_target_directory.mkdir()
        (symlink_target_directory / "output.stdout.txt").write_text(
            "synthetic parent symlink probe",
            encoding="utf-8",
        )
        raw_root = temporary_root.joinpath(*(LOCAL_REL / "raw").parts)
        raw_root.mkdir(parents=True)
        (raw_root / "linked-directory").symlink_to(symlink_target_directory)
        try:
            local_raw_target(
                temporary_root,
                symlink_relative_path,
                label="self-check ignored raw parent symlink",
            )
        except ValueError:
            parent_symlink_rejected = True
        else:
            raise ValueError("self-check accepted a symlinked ignored raw parent")
    shared_decision_mapping_rejections = 0
    duplicate_decision_packet = copy.deepcopy(slice_handoff)
    duplicate_decision_packet["decision_refs"].append(
        copy.deepcopy(duplicate_decision_packet["decision_refs"][0])
    )
    try:
        decision_refs_by_occurrence(
            duplicate_decision_packet,
            label="self-check exact duplicate decision row",
        )
    except ValueError:
        exact_duplicate_decision_rejected = True
    else:
        raise ValueError("self-check accepted an exact duplicate decision row")
    shared_mapping_mutations = [
        (
            "partial_decision_mapping",
            lambda value: value["decision_refs"].pop(),
        ),
        (
            "unknown_decision_cover",
            lambda value: value["decision_refs"][1]["source_ref"]["covers"].update(
                {"occurrence_pointer": "coverage.json#/findings/999/criterion_refs/0"}
            ),
        ),
        (
            "forged_decision_criterion_hash",
            lambda value: value["decision_refs"][1]["source_ref"]["covers"].update(
                {"sha256": "0" * 64}
            ),
        ),
        (
            "unstated_raw_storage",
            lambda value: value["commands"][0]["stdout_ref"].pop("storage"),
        ),
        (
            "raw_path_escape",
            lambda value: value["commands"][0]["stdout_ref"].update(
                {
                    "path": (
                        "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs"
                        "/LOCAL/raw/../../../../../../AGENTS.md"
                    )
                }
            ),
        ),
    ]
    for name, mutate in shared_mapping_mutations:
        corrupted_handoff = copy.deepcopy(slice_handoff)
        mutate(corrupted_handoff)
        try:
            require_typed_report_changes(
                [("M", slice_path)],
                label=f"self-check {name}",
                payload_for_path=lambda _, value=corrupted_handoff: json.dumps(value).encode(
                    "utf-8",
                ),
                expected_candidate=source_identity,
            )
        except (KeyError, TypeError, ValueError):
            shared_decision_mapping_rejections += 1
        else:
            raise ValueError(f"self-check accepted slice handoff mutation: {name}")
    accepted_decision_mapping = decision_refs_by_occurrence(
        slice_handoff,
        label="self-check two-occurrence decision map",
    )
    first_probe = shared_occurrences[0]
    second_probe = shared_occurrences[1]
    first_decisions = accepted_decision_mapping[
        (
            first_probe["finding_id"],
            first_probe["occurrence_pointer"],
            first_probe["criterion_sha256"],
        )
    ]
    second_decisions = accepted_decision_mapping[
        (
            second_probe["finding_id"],
            second_probe["occurrence_pointer"],
            second_probe["criterion_sha256"],
        )
    ]
    require(
        [decision["kind"] for decision in first_decisions]
        == ["alternative", "alternative", "prototype"]
        and [decision["option_id"] for decision in first_decisions[:2]]
        == ["reuse-existing", "extend-consumer"]
        and len(second_decisions) == 1
        and second_decisions[0]["kind"] == "prototype",
        "shared two-occurrence handoff did not retain the full decision set per criterion",
    )
    validated_first_decisions = validate_decision_research_rows(
        root,
        first_decisions,
        occurrence_pointer=first_probe["occurrence_pointer"],
        occurrence_sha256=first_probe["criterion_sha256"],
        candidate_source=source_identity,
        label="self-check all selected decisions",
    )
    require(
        len(validated_first_decisions) == 3,
        "not every same-occurrence decision source was validated",
    )
    validated_second_decisions = validate_decision_research_rows(
        root,
        second_decisions,
        occurrence_pointer=second_probe["occurrence_pointer"],
        occurrence_sha256=second_probe["criterion_sha256"],
        candidate_source=source_identity,
        label="self-check second occurrence decision source",
    )
    require(
        len(validated_second_decisions) == 1,
        "shared handoff decision source was not validated for the second occurrence",
    )
    corrupt_later_decision = copy.deepcopy(first_decisions)
    corrupt_later_decision[2]["source_ref"]["sha256"] = "0" * 64
    try:
        validate_decision_research_rows(
            root,
            corrupt_later_decision,
            occurrence_pointer=first_probe["occurrence_pointer"],
            occurrence_sha256=first_probe["criterion_sha256"],
            candidate_source=source_identity,
            label="self-check later decision source corruption",
        )
    except ValueError:
        later_decision_source_rejected = True
    else:
        raise ValueError("self-check accepted a corrupt later decision source")
    try:
        validate_decision_research_rows(
            root,
            second_decisions,
            occurrence_pointer=first_probe["occurrence_pointer"],
            occurrence_sha256=first_probe["criterion_sha256"],
            candidate_source=source_identity,
            label="self-check foreign occurrence decision source",
        )
    except ValueError:
        foreign_occurrence_source_rejected = True
    else:
        raise ValueError("self-check accepted foreign-occurrence decision evidence")
    issuer_only_decision = {
        "kind": "bounded_no_alternative",
        "reason": (
            "A matching internal issuer and verifier are not established; "
            "hold the protected positive."
        ),
        "falsifier": "Inspect the matching internal issuer, verifier, and currentness source.",
        "source_ref": decision_source_ref(4, 0, role="bounded_no_alternative_basis"),
    }
    validate_decision_research_rows(
        root,
        [issuer_only_decision],
        occurrence_pointer=first_probe["occurrence_pointer"],
        occurrence_sha256=first_probe["criterion_sha256"],
        candidate_source=source_identity,
        label="self-check issuer-only G refusal decision",
    )
    # This candidate has no tracked v2 slice-receipt fixture. Pin the evidence
    # index refs to a real candidate JSON receipt, then stub only its typed-reader
    # boundary below while the actual OPEN_ACTION validators execute.
    issuer_receipt_path = (LOCAL_REL / "native-output-boundary.json").as_posix()
    issuer_receipt_bytes = git_bytes(
        root, "show", f"{source_identity['commit']}:{issuer_receipt_path}"
    )
    issuer_receipt_blob = git_text(
        root, "rev-parse", f"{source_identity['commit']}:{issuer_receipt_path}"
    )

    def issuer_evidence_ref(role: str, pointer: str) -> dict[str, Any]:
        return {
            "path": issuer_receipt_path,
            "commit": source_identity["commit"],
            "git_blob": issuer_receipt_blob,
            "sha256": sha256(issuer_receipt_bytes),
            "role": role,
            "pointer": pointer,
            "candidate_source": source_identity,
            "covers": {
                "occurrence_pointer": first_probe["occurrence_pointer"],
                "sha256": first_probe["criterion_sha256"],
            },
        }

    issuer_evidence_refs = [
        issuer_evidence_ref("configuration_scope", "#/schema"),
        issuer_evidence_ref("no_input_basis", "#/schema"),
        issuer_evidence_ref("backend_profile", "#/backend_profile"),
        issuer_evidence_ref("consumer_surface", "#/consumer_surface"),
        issuer_evidence_ref("typed_slice_receipt", "#/schema"),
        issuer_evidence_ref("bounded_no_alternative_basis", "/decision_refs/0"),
    ]
    issuer_context = {
        "source_footprint_sha256": "c" * 64,
        "configuration_and_lock_evidence_indexes": [],
        "configuration_scope_evidence_index": 0,
        "selected_input_state": "not_required",
        "selected_input_evidence_indexes": [],
        "input_scope_evidence_index": 1,
        "backend_profile_evidence_index": 2,
        "consumer_surface_evidence_indexes": [3],
        "typed_slice_receipt_evidence_indexes": [4],
        "decision_research_evidence_indexes": [5],
    }
    issuer_evaluation = {
        "state": "OPEN_ACTION",
        "result_summary": (
            "Hold the protected positive until a matching internal issuer is established."
        ),
        "boundary": {
            "kind": "issuer_not_established",
            "details": "This is an issuer-only G decision/refusal path; no authority is granted.",
        },
        "next_check": "Inspect the matching internal issuer, verifier, and currentness source.",
        "candidate_source": source_identity,
        "execution_context": issuer_context,
        "evidence_refs": issuer_evidence_refs,
        "attempts": [
            {
                "action": "Inspect the source-owned issuer and refusal path.",
                "status": "SKIP",
                "result_ref": decision_source_ref(5, 0, role="attempt_result"),
            }
        ],
        "review_escape": {"state": "none_observed"},
        "proposal_disposition": "held",
    }

    def issuer_only_receipt_probe(
        _root: Path,
        evidence_ref: dict[str, Any],
        *,
        candidate_source: dict[str, str],
        occurrence_pointer: str,
        occurrence_sha256: str,
        finding_id: str,
        evaluation_state: str,
        complete_census: dict[str, Any],
        label: str,
    ) -> dict[str, Any]:
        require(
            candidate_source == source_identity,
            "issuer-only receipt probe candidate source mismatch",
        )
        require(
            occurrence_pointer == first_probe["occurrence_pointer"],
            "issuer-only receipt probe pointer mismatch",
        )
        require(
            occurrence_sha256 == first_probe["criterion_sha256"],
            "issuer-only receipt probe did not receive the exact criterion hash",
        )
        require(
            finding_id == first_probe["finding_id"] and evaluation_state == "OPEN_ACTION",
            "issuer-only receipt probe is not the expected open G-decision action",
        )
        require(
            evidence_ref == issuer_evidence_refs[4],
            "issuer-only receipt probe selected the wrong receipt",
        )
        return {
            "path": evidence_ref["path"],
            "commit": evidence_ref["commit"],
            "selected_inputs": [],
            "decision_refs": [issuer_only_decision],
        }

    receipt_validator = globals()["validate_typed_slice_receipt"]
    try:
        globals()["validate_typed_slice_receipt"] = issuer_only_receipt_probe
        issuer_evaluation_result = validate_explicit_evaluation(
            issuer_evaluation,
            root,
            first_probe["occurrence_pointer"],
            first_probe["criterion_sha256"],
            finding_id=first_probe["finding_id"],
            source_footprint_sha256=issuer_context["source_footprint_sha256"],
            complete_census={"complete_paths": []},
        )
        require(
            issuer_evaluation_result["execution_context"] == issuer_context
            and len(issuer_evaluation_result["attempts"]) == 1
            and "formal_closure_ids" not in issuer_evaluation_result,
            "issuer-only G refusal mutated or claimed formal closure",
        )
        wrong_hash_rejected = False
        try:
            wrong_hash_evaluation = copy.deepcopy(issuer_evaluation)
            for evidence_ref in wrong_hash_evaluation["evidence_refs"]:
                evidence_ref["covers"]["sha256"] = "0" * 64
            wrong_hash_evaluation["attempts"][0]["result_ref"]["covers"]["sha256"] = "0" * 64
            validate_explicit_evaluation(
                wrong_hash_evaluation,
                root,
                first_probe["occurrence_pointer"],
                "0" * 64,
                finding_id=first_probe["finding_id"],
                source_footprint_sha256=issuer_context["source_footprint_sha256"],
                complete_census={"complete_paths": []},
            )
        except ValueError:
            wrong_hash_rejected = True
        else:
            raise ValueError(
                "self-check accepted issuer-only decision with a foreign criterion hash"
            )
        wrong_decision_role_refs = copy.deepcopy(issuer_evidence_refs)
        wrong_decision_role_refs[5]["role"] = "actual_consumer"
        wrong_decision_role_evaluation = copy.deepcopy(issuer_evaluation)
        wrong_decision_role_evaluation["evidence_refs"] = wrong_decision_role_refs
        try:
            validate_explicit_evaluation(
                wrong_decision_role_evaluation,
                root,
                first_probe["occurrence_pointer"],
                first_probe["criterion_sha256"],
                finding_id=first_probe["finding_id"],
                source_footprint_sha256=issuer_context["source_footprint_sha256"],
                complete_census={"complete_paths": []},
            )
        except ValueError:
            issuer_role_mutation_rejected = True
        else:
            raise ValueError("self-check accepted an issuer-only decision with a false role")
    finally:
        globals()["validate_typed_slice_receipt"] = receipt_validator

    forged_occurrence_handoff = copy.deepcopy(slice_handoff)
    forged_occurrence_handoff["proposal_occurrences"][0]["criterion_sha256"] = "0" * 64
    for decision_ref in forged_occurrence_handoff["decision_refs"]:
        covers = decision_ref["source_ref"]["covers"]
        if covers["occurrence_pointer"] == first_probe["occurrence_pointer"]:
            covers["sha256"] = "0" * 64
    decision_refs_by_occurrence(
        forged_occurrence_handoff,
        label="self-check forged criterion map",
    )
    try:
        require_handoff_occurrence(
            forged_occurrence_handoff,
            finding_id=first_probe["finding_id"],
            occurrence_pointer=first_probe["occurrence_pointer"],
            criterion_sha256=first_probe["criterion_sha256"],
            label="self-check exact occurrence binding",
        )
    except ValueError:
        forged_criterion_rejected = True
    else:
        raise ValueError("self-check accepted a forged criterion binding")
    report_artifact_rejections = 0
    report_rejection_cases = [
        (
            "mechanism_under_LOCAL",
            (LOCAL_REL / "emit_proposals.py").as_posix(),
            b'{"schema":"policyos.e02.finding_proposals.v2"}',
        ),
        (
            "source_input_json_under_LOCAL",
            (LOCAL_REL / "crosswalk/source-input.json").as_posix(),
            b'{"schema":"policyos.e02.finding_proposals.v2"}',
        ),
        (
            "wrong_output_schema",
            output_path,
            b'{"schema":"policyos.e02.untyped.v1"}',
        ),
        (
            "nested_slice_report_path",
            (LOCAL_REL / "crosswalk/q0-crosswalk.json").as_posix(),
            json.dumps(slice_handoff).encode("utf-8"),
        ),
        (
            "slice_report_candidate_mismatch",
            slice_path,
            json.dumps(
                {
                    **slice_handoff,
                    "candidate_source": {
                        "commit": snapshot["original_entry"]["commit"],
                        "tree": snapshot["original_entry"]["tree"],
                    },
                }
            ).encode("utf-8"),
        ),
        (
            "direct_local_config_not_slice_report",
            (LOCAL_REL / "runtime-config.json").as_posix(),
            b'{"schema":"policyos.e02.untyped.v1","slice_id":"runtime-config"}',
        ),
    ]
    for name, path, payload in report_rejection_cases:
        try:
            expected_candidate = (
                source_identity if name == "slice_report_candidate_mismatch" else None
            )
            require_typed_report_changes(
                [("M", path)],
                label=f"self-check {name}",
                payload_for_path=lambda _, output=payload: output,
                expected_candidate=expected_candidate,
            )
        except (KeyError, TypeError, ValueError):
            report_artifact_rejections += 1
        else:
            raise ValueError(f"self-check report classification accepted: {name}")

    def must_reject(name: str, corrupted: dict[str, Any]) -> None:
        try:
            validate_ledger(corrupted, snapshot)
        except (KeyError, TypeError, ValueError):
            return
        raise ValueError(f"self-check mutation accepted: {name}")

    cases: list[tuple[str, dict[str, Any]]] = []

    corrupted = copy.deepcopy(ledger)
    corrupted["findings"][0]["finding_id"] = corrupted["findings"][1]["finding_id"]
    cases.append(("duplicate_id_same_row_count", corrupted))

    corrupted = copy.deepcopy(ledger)
    corrupted["findings"][0]["occurrences"][0]["original"]["sha256"] = "0" * 64
    cases.append(("wrong_occurrence_hash_same_count", corrupted))

    corrupted = copy.deepcopy(ledger)
    corrupted["findings"][0]["original_routes"]["current_tasks"].pop()
    cases.append(("missing_route_same_id_count", corrupted))

    corrupted = copy.deepcopy(ledger)
    corrupted["source_boundary"]["source_freeze"]["candidate_source"]["tree"] = "0" * 40
    cases.append(("wrong_candidate_tree_same_denominator", corrupted))

    corrupted = copy.deepcopy(ledger)
    corrupted["replay_selection"]["candidate_source_freeze_ref"] = (
        "/source_boundary/report_checkout"
    )
    cases.append(("source_freeze_proxy_policy", corrupted))

    corrupted = copy.deepcopy(ledger)
    corrupted["findings"][0]["candidate_proposal"] = {
        "disposition": "closed",
        "status": "proposal_only_not_G_adjudication",
        "basis_occurrence_pointers": [
            row["original"]["occurrence_pointer"] for row in corrupted["findings"][0]["occurrences"]
        ],
    }
    cases.append(("closed_proposal_without_occurrence_evidence", corrupted))

    corrupted = copy.deepcopy(ledger)
    corrupted["findings"][0]["occurrences"][0]["candidate_evaluation"]["review_escape"] = {
        "state": "present",
        "class_id": "unbucketed",
        "same_class_ordinal": 1,
    }
    cases.append(("unbucketed_review_escape", corrupted))

    corrupted = copy.deepcopy(ledger)
    corrupted["findings"][0]["occurrences"][0]["original_property_refs"][
        "criterion_specific_acceptance_boundary"
    ]["owner_crosswalk_ref"] = "wrong-owner-ref"
    cases.append(("wrong_occurrence_owner_boundary_ref_same_count", corrupted))

    corrupted = copy.deepcopy(ledger)
    corrupted["findings"][0]["occurrences"][0]["original_property_refs"][
        "criterion_specific_acceptance_boundary"
    ]["criterion_source_ref"] = "wrong-source-ref"
    cases.append(("wrong_criterion_boundary_hash_same_count", corrupted))

    property_occurrence = next(
        occurrence
        for finding in ledger["findings"]
        for occurrence in finding["occurrences"]
        if occurrence["original_property_refs"]["criterion_specific_acceptance_boundary"][
            "coverage_field_refs"
        ]
    )
    property_pointer = property_occurrence["original"]["occurrence_pointer"]
    corrupted = copy.deepcopy(ledger)
    corrupted_property_occurrence = next(
        occurrence
        for finding in corrupted["findings"]
        for occurrence in finding["occurrences"]
        if occurrence["original"]["occurrence_pointer"] == property_pointer
    )
    corrupted_property_occurrence["original_property_refs"][
        "criterion_specific_acceptance_boundary"
    ]["coverage_field_refs"][0][
        "pointer"
    ] = "/findings/999/criterion_specific_acceptance_not_executed"
    cases.append(("wrong_occurrence_property_field_same_count", corrupted))

    corrupted = copy.deepcopy(ledger)
    corrupted_b198 = next(row for row in corrupted["findings"] if row["finding_id"] == "B198")
    corrupted_b198["historical"]["ledger_status"] = "open"
    cases.append(("B198_historical_decision_changed_same_count", corrupted))

    for name, corrupted in cases:
        must_reject(name, corrupted)

    def p40_occurrence(pointer: str, digest: str, escape: dict[str, Any]) -> dict[str, Any]:
        return {
            "original": {"occurrence_pointer": pointer, "sha256": digest},
            "candidate_evaluation": {"review_escape": escape},
        }

    p40_second_pointer = "coverage.json#/findings/1/criterion_refs/0"
    p40_second_digest = "2" * 64
    valid_p40 = {
        "findings": [
            {
                "occurrences": [
                    p40_occurrence(
                        "coverage.json#/findings/0/criterion_refs/0",
                        "1" * 64,
                        {
                            "state": "present",
                            "bucket": "NEW_CLASS",
                            "class_id": "probe-class",
                            "same_class_ordinal": 1,
                        },
                    ),
                    p40_occurrence(
                        "coverage.json#/findings/3/criterion_refs/0",
                        "4" * 64,
                        {
                            "state": "present",
                            "bucket": "NEW_CLASS",
                            "class_id": "probe-class",
                            "same_class_ordinal": 1,
                        },
                    ),
                    p40_occurrence(
                        p40_second_pointer,
                        p40_second_digest,
                        {
                            "state": "present",
                            "bucket": "SAME_CLASS_DEEPER",
                            "class_id": "probe-class",
                            "same_class_ordinal": 2,
                            "second_same_class_resolution": "bounded_residual",
                        },
                    ),
                    p40_occurrence(
                        "coverage.json#/findings/2/criterion_refs/0",
                        "3" * 64,
                        {
                            "state": "present",
                            "bucket": "SAME_CLASS_DEEPER",
                            "class_id": "probe-class",
                            "same_class_ordinal": 3,
                            "treatment": "worked_example_no_round",
                            "class_resolution": {
                                "resolution": "bounded_residual",
                                "occurrence_pointer": p40_second_pointer,
                                "sha256": p40_second_digest,
                            },
                        },
                    ),
                ],
            }
        ],
    }
    validate_p40_occurrence_sequence(valid_p40)

    p40_mutations = 0
    p40_mutation_cases = [
        (
            "bucket_ordinal_conflict",
            lambda rows: rows[2]["candidate_evaluation"]["review_escape"].update(
                {"same_class_ordinal": 1, "bucket": "NEW_CLASS"}
            ),
        ),
        ("missing_second", lambda rows: rows.pop(2)),
        (
            "later_escape_spends_round",
            lambda rows: rows[3]["candidate_evaluation"]["review_escape"].update(
                {"treatment": "another_repair_round"}
            ),
        ),
        (
            "wrong_resolution_reference",
            lambda rows: rows[3]["candidate_evaluation"]["review_escape"][
                "class_resolution"
            ].update({"sha256": "0" * 64}),
        ),
    ]
    for name, mutate in p40_mutation_cases:
        corrupted_p40 = copy.deepcopy(valid_p40)
        mutate(corrupted_p40["findings"][0]["occurrences"])
        try:
            validate_p40_occurrence_sequence(corrupted_p40)
        except (KeyError, TypeError, ValueError):
            p40_mutations += 1
        else:
            raise ValueError(f"P40 self-check mutation accepted: {name}")
    return {
        "count_preserving_mutations_rejected": len(cases),
        "typed_report_artifact_rejections": report_artifact_rejections,
        "empty_occurrence_update_input_accepted": True,
        "frozen_context_corruptions_rejected": frozen_context_rejections,
        "task_level_status_rejected": task_status_rejected,
        "input_context_corruptions_rejected": input_context_rejections,
        "candidate_evaluations_written": 0,
        "typed_slice_handoff_probe_accepted": True,
        "typed_slice_source_relation_candidate_parent_count": len(
            source_relationship["candidate_parent_ids"]
        ),
        "typed_slice_forged_parent_rejected": parent_mutation_rejected,
        "typed_slice_candidate_tree_mismatch_rejected": candidate_tree_mutation_rejected,
        "typed_slice_base_tree_mismatch_rejected": slice_base_tree_mutation_rejected,
        "typed_slice_nonancestor_base_rejected": nonancestor_base_rejected,
        "typed_slice_root_commit_without_parents_accepted": not root_parent_ids,
        "typed_slice_empty_initial_commit_header_accepted": (
            parsed_empty_tree == empty_tree_id and parsed_empty_parents == []
        ),
        "typed_slice_ordered_merge_parent_header_accepted": (
            parsed_merge_parents == merge_parent_ids
        ),
        "git_read_boundary_checks": git_read_checks,
        "ignored_local_raw_available_readback_accepted": True,
        "ignored_local_raw_mutations_rejected": ignored_raw_rejections,
        "ignored_local_raw_symlink_rejected": symlink_rejected,
        "ignored_local_raw_parent_symlink_rejected": parent_symlink_rejected,
        "shared_two_occurrence_decision_map_accepted": True,
        "three_distinct_decisions_for_one_occurrence_accepted": True,
        "all_selected_decision_sources_validated": len(validated_first_decisions) == 3,
        "shared_second_occurrence_decision_source_validated": len(validated_second_decisions) == 1,
        "exact_duplicate_decision_row_rejected": exact_duplicate_decision_rejected,
        "later_selected_decision_source_corruption_rejected": later_decision_source_rejected,
        "foreign_occurrence_decision_source_rejected": foreign_occurrence_source_rejected,
        "issuer_only_g_refusal_context_accepted": True,
        "issuer_only_wrong_criterion_hash_rejected": wrong_hash_rejected,
        "issuer_only_wrong_decision_role_rejected": issuer_role_mutation_rejected,
        "shared_decision_mapping_mutations_rejected": shared_decision_mapping_rejections,
        "forged_occurrence_criterion_rejected": forged_criterion_rejected,
        "p40_sequence_probe_accepted": True,
        "p40_sequence_mutations_rejected": p40_mutations,
    }


def summary(ledger: dict[str, Any]) -> dict[str, Any]:
    """Return a small recomputable command receipt."""
    counts = collections.Counter(
        occurrence["candidate_evaluation"]["state"]
        for finding in ledger["findings"]
        for occurrence in finding["occurrences"]
    )
    crosswalk_counts = collections.Counter(
        occurrence["author_crosswalk"]["state"]
        for finding in ledger["findings"]
        for occurrence in finding["occurrences"]
    )
    crosswalk_by_author: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    queue_occurrences: dict[str, list[str]] = collections.defaultdict(list)
    choice_counts = collections.Counter()
    provisional_states = collections.Counter()
    for finding in ledger["findings"]:
        for occurrence in finding["occurrences"]:
            queue_occurrences[occurrence["work_queue"]["class"]].append(finding["finding_id"])
            choice_counts[occurrence["work_queue"]["external_or_g_choice"]["kind"]] += 1
            provisional_states[occurrence["provisional_review"]["status"]] += 1
            crosswalk_by_author[finding["source_author_proposal"]["source"]][
                occurrence["author_crosswalk"]["state"]
            ] += 1
    return {
        "scope": "ledger integrity only; no runtime proof or G closure",
        "finding_ids": ledger["denominator"]["finding_ids"],
        "canonical_occurrences": ledger["denominator"]["canonical_occurrences"],
        "candidate_states": dict(counts),
        "author_crosswalk_occurrence_states": dict(crosswalk_counts),
        "author_crosswalk_by_source": {
            author: dict(source_counts)
            for author, source_counts in sorted(crosswalk_by_author.items())
        },
        "route_census": ledger["route_census"],
        "source_freeze_status": ledger["source_boundary"]["source_freeze"]["status"],
        "provisional_review_states": dict(provisional_states),
        "external_or_g_choice_kinds": dict(choice_counts),
        "remaining_queue": {
            queue_class: {
                "occurrences": len(finding_ids),
                "finding_ids": len(set(finding_ids)),
            }
            for queue_class, finding_ids in sorted(queue_occurrences.items())
        },
        "formal_closure_ids": ledger["formal_closure_ids"],
    }


def serialized_json(value: dict[str, Any]) -> bytes:
    """Serialize one report using the emitter's stable readable encoding."""
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build_receipt(
    ledger: dict[str, Any],
    *,
    ledger_path: Path,
    ledger_bytes: bytes,
    mode: str,
    evaluations_path: Path | None,
) -> dict[str, Any]:
    """Create a compact receipt that points to, but does not duplicate, the ledger."""
    root = repo_root()
    command = [
        "python3",
        "-B",
        (LOCAL_REL / "emit_proposals.py").as_posix(),
    ]
    if mode == "provisional_review":
        command.append("--provisional-review")
    else:
        candidate = ledger["source_boundary"]["source_freeze"]["candidate_source"]
        command.extend(["--frozen-commit", candidate["commit"], "--frozen-tree", candidate["tree"]])
        if evaluations_path is not None:
            command.extend(["--evaluations", evaluations_path.relative_to(root).as_posix()])
    source_freeze = ledger["source_boundary"]["source_freeze"]
    return {
        "schema": Q0_RECEIPT_SCHEMA,
        "status": ledger["evaluation_mode"],
        "mode": mode,
        "source_checkpoint": ledger["source_boundary"]["report_checkout"],
        "source_freeze_status": ledger["source_boundary"]["source_freeze"]["status"],
        "ledger": {
            "path": ledger_path.relative_to(root).as_posix(),
            "sha256": sha256(ledger_bytes),
            "denominator": ledger["denominator"],
            "formal_closure_ids": ledger["formal_closure_ids"],
        },
        "candidate_evaluation_states": summary(ledger)["candidate_states"],
        "author_review_states": summary(ledger)["provisional_review_states"],
        "external_or_g_choice_kinds": summary(ledger)["external_or_g_choice_kinds"],
        "source_change_census_ref": "/source_boundary/source_freeze/source_change_census",
        "command": command,
        "command_logs": {
            "stdout": (LOCAL_REL / "crosswalk/checks/emit.stdout.txt").as_posix(),
            "stderr": (LOCAL_REL / "crosswalk/checks/emit.stderr.txt").as_posix(),
        },
        "evaluation_import_contract": {
            "schema": EVALUATION_SCHEMA,
            "occurrence_key": ["occurrence_pointer", "sha256"],
            "frozen_candidate_source": (
                source_freeze["candidate_source"]
                if source_freeze["status"] == "frozen_candidate"
                else None
            ),
            "provisional_report_checkout": (
                ledger["source_boundary"]["report_checkout"]
                if source_freeze["status"] != "frozen_candidate"
                else None
            ),
            "source_footprint_ref": "/source_boundary/source_freeze/source_change_census",
            "source_footprint_sha256": canonical_json_sha256(source_freeze["source_change_census"]),
            "evaluation_input_path": (
                evaluations_path.relative_to(root).as_posix()
                if evaluations_path is not None
                else None
            ),
            "required_execution_context": [
                "configuration_and_lock_evidence_indexes",
                "configuration_scope_evidence_index",
                "selected_input_state",
                "selected_input_evidence_indexes",
                "input_scope_evidence_index",
                "backend_profile_evidence_index",
                "consumer_surface_evidence_indexes",
                "typed_slice_receipt_evidence_indexes",
                "decision_research_evidence_indexes",
            ],
            "candidate_specific_alternative_or_prototype_basis_required": True,
            "unmentioned_occurrences_remain_UNRUN": True,
            "task_status_and_source_author_status_are_not_outcomes": True,
            "partial_proposal_dispositions": sorted(PROPOSAL_DISPOSITIONS),
            "formal_closure_ids": [],
        },
        "authority_boundary": (
            "Author proposals and source-qualified research only. Candidate outcomes require "
            "explicit occurrence evidence bound to the final frozen source; formal G closures "
            "stay empty."
        ),
    }


def validate_receipt(
    receipt: dict[str, Any], *, ledger: dict[str, Any], ledger_path: Path, ledger_bytes: bytes
) -> None:
    """Reconcile the typed crosswalk receipt with the exact ledger bytes and status."""
    require(receipt.get("schema") == Q0_RECEIPT_SCHEMA, "crosswalk receipt schema mismatch")
    require(
        receipt.get("status") == ledger["evaluation_mode"],
        "crosswalk receipt status differs from the ledger",
    )
    require(
        receipt.get("source_checkpoint") == ledger["source_boundary"]["report_checkout"],
        "crosswalk receipt source checkpoint differs from the ledger",
    )
    require(
        receipt.get("source_freeze_status") == ledger["source_boundary"]["source_freeze"]["status"],
        "crosswalk receipt source-freeze status differs from the ledger",
    )
    ledger_ref = receipt.get("ledger")
    require(isinstance(ledger_ref, dict), "crosswalk receipt ledger ref missing")
    require(
        ledger_ref.get("path") == ledger_path.relative_to(repo_root()).as_posix(),
        "crosswalk receipt points to the wrong ledger path",
    )
    require(
        ledger_ref.get("sha256") == sha256(ledger_bytes),
        "crosswalk receipt ledger SHA-256 mismatch",
    )
    require(
        ledger_ref.get("denominator") == ledger["denominator"],
        "crosswalk receipt denominator mismatch",
    )
    require(
        ledger_ref.get("formal_closure_ids") == [],
        "crosswalk receipt cannot claim formal G closures",
    )
    receipt_summary = summary(ledger)
    require(
        receipt.get("candidate_evaluation_states") == receipt_summary["candidate_states"],
        "crosswalk receipt candidate-state summary mismatch",
    )
    require(
        receipt.get("author_review_states") == receipt_summary["provisional_review_states"],
        "crosswalk receipt review-state summary mismatch",
    )
    require(
        receipt.get("external_or_g_choice_kinds") == receipt_summary["external_or_g_choice_kinds"],
        "crosswalk receipt route-choice summary mismatch",
    )
    require(
        receipt.get("source_change_census_ref")
        == "/source_boundary/source_freeze/source_change_census",
        "crosswalk receipt source-change pointer mismatch",
    )
    require(
        isinstance(receipt.get("command"), list) and bool(receipt["command"]),
        "crosswalk receipt command missing",
    )
    contract = receipt.get("evaluation_import_contract")
    freeze = ledger["source_boundary"]["source_freeze"]
    expected_contract = {
        "schema": EVALUATION_SCHEMA,
        "occurrence_key": ["occurrence_pointer", "sha256"],
        "frozen_candidate_source": (
            freeze["candidate_source"] if freeze["status"] == "frozen_candidate" else None
        ),
        "provisional_report_checkout": (
            ledger["source_boundary"]["report_checkout"]
            if freeze["status"] != "frozen_candidate"
            else None
        ),
        "source_footprint_ref": "/source_boundary/source_freeze/source_change_census",
        "source_footprint_sha256": canonical_json_sha256(freeze["source_change_census"]),
        "evaluation_input_path": (
            (LOCAL_REL / "crosswalk/occurrence-evaluations.json").as_posix()
            if any("occurrence-evaluations.json" in str(part) for part in receipt["command"])
            else None
        ),
        "required_execution_context": [
            "configuration_and_lock_evidence_indexes",
            "configuration_scope_evidence_index",
            "selected_input_state",
            "selected_input_evidence_indexes",
            "input_scope_evidence_index",
            "backend_profile_evidence_index",
            "consumer_surface_evidence_indexes",
            "typed_slice_receipt_evidence_indexes",
            "decision_research_evidence_indexes",
        ],
        "candidate_specific_alternative_or_prototype_basis_required": True,
        "unmentioned_occurrences_remain_UNRUN": True,
        "task_status_and_source_author_status_are_not_outcomes": True,
        "partial_proposal_dispositions": sorted(PROPOSAL_DISPOSITIONS),
        "formal_closure_ids": [],
    }
    require(
        contract == expected_contract,
        "evaluation import contract differs from frozen occurrence-update rules",
    )
    command = receipt["command"]
    require(
        command[:3]
        == [
            "python3",
            "-B",
            (LOCAL_REL / "emit_proposals.py").as_posix(),
        ],
        "receipt command does not name the canonical emitter",
    )
    require(
        receipt.get("command_logs")
        == {
            "stdout": (LOCAL_REL / "crosswalk/checks/emit.stdout.txt").as_posix(),
            "stderr": (LOCAL_REL / "crosswalk/checks/emit.stderr.txt").as_posix(),
        },
        "receipt command log paths are not canonical",
    )
    if receipt.get("mode") == "provisional_review":
        require(
            command[3:] == ["--provisional-review"],
            "provisional receipt command args are not canonical",
        )
    else:
        candidate = freeze["candidate_source"]
        expected_args = [
            "--frozen-commit",
            candidate["commit"],
            "--frozen-tree",
            candidate["tree"],
        ]
        if contract["evaluation_input_path"] is not None:
            expected_args.extend(["--evaluations", contract["evaluation_input_path"]])
        require(
            command[3:] == expected_args,
            "final receipt command does not carry the exact frozen SHA/tree and input path",
        )


def main() -> int:
    """Build, validate, or self-check the occurrence-level proposal ledger."""
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="validate the existing ledger")
    mode.add_argument(
        "--provisional-review",
        action="store_true",
        help="emit source-qualified author review while the final candidate freeze is pending",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="run in-memory count-preserving mutation controls without writing reports",
    )
    parser.add_argument(
        "--evaluations", type=Path, help="explicit occurrence evaluation input JSON"
    )
    parser.add_argument(
        "--output", type=Path, help="ledger path; defaults to LOCAL/finding-proposals.json"
    )
    parser.add_argument("--frozen-commit", help="root-approved frozen candidate commit SHA")
    parser.add_argument("--frozen-tree", help="root-approved frozen candidate tree SHA")
    args = parser.parse_args()

    root = repo_root()
    output = args.output or (root / LOCAL_REL / "finding-proposals.json")
    local_dir = (root / LOCAL_REL).resolve()
    require(
        output.resolve().parent == local_dir, "output must remain inside the leased LOCAL directory"
    )
    if args.check:
        require(not args.self_check, "--check and --self-check are separate read-only modes")
        require(
            args.evaluations is None and args.frozen_commit is None and args.frozen_tree is None,
            "--check reads the ledger and does not accept source/evaluation overrides",
        )
        ledger = load_json(root, output.relative_to(root))
        report_checkout = ledger.get("source_boundary", {}).get("report_checkout")
        provisional = (
            ledger.get("source_boundary", {}).get("source_freeze", {}).get("status")
            == "provisional_source_checkpoint_not_frozen"
        )
        snapshot = load_sources(
            root, frozen_report_checkout=report_checkout, provisional=provisional
        )
        checked = validate_ledger(ledger, snapshot)
        ledger_bytes = output.read_bytes()
        receipt_path = root / LOCAL_REL / "crosswalk/receipt.json"
        receipt = load_json(root, receipt_path.relative_to(root))
        validate_receipt(receipt, ledger=ledger, ledger_path=output, ledger_bytes=ledger_bytes)
        print(json.dumps({**summary(ledger), **checked, "mode": "check"}, indent=2))  # noqa: T201 -- CLI JSON output.
        return 0

    if args.provisional_review:
        require(
            args.evaluations is None and args.frozen_commit is None and args.frozen_tree is None,
            "provisional source review cannot import candidate outcomes or freeze overrides",
        )
        snapshot = load_sources(root, provisional=True)
    else:
        require(
            isinstance(args.frozen_commit, str) and isinstance(args.frozen_tree, str),
            "final emission requires root-supplied --frozen-commit and --frozen-tree",
        )
        require(
            re.fullmatch(r"[0-9a-f]{40}", args.frozen_commit) is not None
            and re.fullmatch(r"[0-9a-f]{40}", args.frozen_tree) is not None,
            "frozen candidate commit/tree must be full lowercase SHA-1 values",
        )
        branch = git_text(root, "symbolic-ref", "--short", "HEAD")
        snapshot = load_sources(
            root,
            frozen_report_checkout={
                "commit": args.frozen_commit,
                "tree": args.frozen_tree,
                "branch": branch,
            },
        )
    if args.evaluations is not None:
        require(
            args.evaluations.resolve()
            == (root / LOCAL_REL / "crosswalk/occurrence-evaluations.json").resolve(),
            "evaluation input must use the registered typed "
            "LOCAL/crosswalk/occurrence-evaluations.json path",
        )
    ledger = build_ledger(snapshot, args.evaluations)
    checked = validate_ledger(ledger, snapshot)
    if args.self_check:
        probe_result = self_check(ledger, snapshot)
        print(  # noqa: T201 -- CLI JSON output.
            json.dumps(
                {**summary(ledger), **checked, **probe_result, "mode": "self_check"}, indent=2
            )
        )
        return 0

    require(
        output == root / LOCAL_REL / "finding-proposals.json",
        "emission output must use the leased canonical proposal ledger path",
    )
    mode_name = "provisional_review" if args.provisional_review else "emit"
    ledger_bytes = serialized_json(ledger)
    receipt = build_receipt(
        ledger,
        ledger_path=output,
        ledger_bytes=ledger_bytes,
        mode=mode_name,
        evaluations_path=args.evaluations,
    )
    output.write_bytes(ledger_bytes)
    receipt_path = root / LOCAL_REL / "crosswalk/receipt.json"
    receipt_path.write_bytes(serialized_json(receipt))
    validate_receipt(receipt, ledger=ledger, ledger_path=output, ledger_bytes=ledger_bytes)
    print(  # noqa: T201 -- CLI JSON output.
        json.dumps(
            {
                **summary(ledger),
                **checked,
                "output": output.relative_to(root).as_posix(),
                "mode": mode_name,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

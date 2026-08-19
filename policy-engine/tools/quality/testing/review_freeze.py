#!/usr/bin/env python3
"""Enforce E11 review freezes with a committed, append-only scheduling ledger.

The module deliberately owns only the freeze/disposition bridge.  It delegates review-package
rendering to :mod:`build_review_package`; review findings and reviewer results remain opaque raw
bytes that the ledger content-binds rather than reinterprets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any, Final

# A direct ``python tools/quality/testing/review_freeze.py`` invocation has this directory, rather
# than the product root, on sys.path.  Keep the documented standalone entrypoint usable without
# registering another unified-tool command.
_DIRECT_SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[3]
if __package__ in {None, ""} and str(_DIRECT_SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_DIRECT_SCRIPT_REPO_ROOT))

# The direct-script bootstrap intentionally separates these product imports from stdlib imports.
from tools.lib.fs import atomic_write_bytes, exclusive_lock  # noqa: I001
from tools.quality.testing import build_review_package as review_package
from tools.quality.testing.build_review_package import ReviewPackageError


SCHEMA_VERSION: Final = "policyos.review_freeze.v2"
TREE_FINGERPRINT_ALGORITHM: Final = "git-e11-implementation-tree-v1"
CHECKLIST_MAGIC: Final = b"POLISYOS_E11_BATCH_CHECKLIST\n"
PROVENANCE_LABELS: Final = frozenset(
    {
        "recomputed",
        "independently_reconciled",
        "consumer_asserted",
        "institutionally_supplied",
        "not_established",
    }
)
DISPOSITIONS: Final = frozenset({"fix_now", "batch", "debt"})
EVENT_TYPES: Final = frozenset(
    {
        "open",
        "freeze",
        "review_package",
        "review_result",
        "admit_finding",
        "resolve_member",
        "replay_recorded",
        "closed",
    }
)
_LEDGER_ROOT: Final = ".e11"
_EVIDENCE_ROOT: Final = "tmp/e11"
_NON_SOURCE_ROOTS: Final = ("architecture", "docs")
_ARTIFACT_ROOT: Final = "architecture"
_DEGRADED_REPLAY_CLAIM: Final = "degraded_institutional_scheduling_record"
_AUTHORITY_DENIALS: Final = (
    "implementation authorization",
    "capability claims",
    "owner appointment",
    "automatic amendment of any plan",
    "reviewer-independence proof",
    "receipt semantic-validity proof",
)


class ReviewFreezeError(RuntimeError):
    """Raised when the E11 boundary or its supporting evidence cannot be established."""

    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(code if detail is None else f"{code}: {detail}")


def _canonical_json_bytes(value: object) -> bytes:
    """Return the canonical bytes used for every ledger-side digest."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _sha256(payload: bytes) -> str:
    """Return a namespaced SHA-256 digest."""

    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _repository(value: Path | str) -> Any:
    """Anchor a requested worktree using the existing packager's hardened discovery path."""

    try:
        requested = Path(value).resolve(strict=True)
    except FileNotFoundError as exc:
        raise ReviewFreezeError("repo_root_missing", str(value)) from exc
    if not requested.is_dir():
        raise ReviewFreezeError("repo_root_not_directory", str(requested))
    try:
        repository = review_package._discover_repository(requested)
    except ReviewPackageError as exc:
        raise ReviewFreezeError("repo_root_not_git_worktree", str(exc)) from exc
    if repository.worktree != requested:
        raise ReviewFreezeError("repo_root_not_worktree_root", str(requested))
    return repository


def _implementation_root(repository: Any) -> str:
    """Return the fixed product subtree when this repository has one.

    The repository owns several top-level concerns, while E11 governs the PolicyOS implementation
    under ``policy-engine/``.  Fixture repositories intentionally have no such subtree and use
    their Git root as the implementation root.  This is a constructed repository-layout rule, not
    a caller-provided exclusion.
    """

    candidate = repository.worktree / "policy-engine"
    marker = candidate / "tools" / "quality" / "testing" / "review_freeze.py"
    return "policy-engine" if marker.is_file() else ""


def _source_scope(repository: Any, ledger_relative: str) -> dict[str, object]:
    """Describe the fixed implementation scope bound into one freeze identity."""

    implementation_root = _implementation_root(repository)
    return {
        "implementation_root": f"{implementation_root}/" if implementation_root else ".",
        "included": "all tracked implementation paths except docs/, architecture/, and this ledger's protocol files",
        "excluded_non_source_roots": list(_NON_SOURCE_ROOTS),
        "ledger_path": ledger_relative,
    }


def _artifact_root(repository: Any) -> str:
    """Return the governed-artifact root relative to the anchored Git worktree."""

    implementation_root = _implementation_root(repository)
    return f"{implementation_root}/{_ARTIFACT_ROOT}" if implementation_root else _ARTIFACT_ROOT


def _git_process(repository: Any, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    """Run anchored Git with the existing packager's hermetic environment and argv builder."""

    return subprocess.run(  # noqa: S603 - explicit Git argv built by the hardened packager.
        review_package._git_argv(
            *arguments,
            git_dir=repository.git_dir,
            work_tree=repository.worktree,
        ),
        cwd=repository.worktree,
        env=review_package._git_environment(),
        check=False,
        capture_output=True,
        shell=False,
    )


def _git(repository: Any, *arguments: str) -> bytes:
    """Return stdout from one anchored read-only Git command or raise a typed failure."""

    result = _git_process(repository, *arguments)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise ReviewFreezeError(
            "git_command_failed",
            f"{' '.join(arguments[:2])}: {detail or f'exit {result.returncode}'}",
        )
    return result.stdout


def _resolve_commit(repository: Any, revision: str | None, *, label: str) -> str:
    """Resolve one value to a complete commit object in the anchored worktree."""

    rendered = str(revision or "").strip()
    if not rendered or "\x00" in rendered:
        raise ReviewFreezeError(f"{label}_unresolvable", "empty revision")
    try:
        payload = _git(
            repository, "rev-parse", "--verify", "--end-of-options", f"{rendered}^{{commit}}"
        )
    except ReviewFreezeError as exc:
        raise ReviewFreezeError(f"{label}_unresolvable", rendered) from exc
    resolved = payload.decode("ascii", errors="strict").strip()
    if not resolved:
        raise ReviewFreezeError(f"{label}_unresolvable", rendered)
    return resolved


def _head(repository: Any) -> str:
    """Return the anchored worktree's current commit."""

    return _resolve_commit(repository, "HEAD", label="current_head")


def _require_review_base_ancestor(repository: Any, base_commit: str, head_commit: str) -> None:
    """Reuse the canonical packager's ancestry check for an E11 review range."""

    try:
        with review_package._hermetic_git_context(repository) as git_context:
            review_package._require_ancestor(git_context, base_commit, head_commit)
    except (OSError, ReviewPackageError) as exc:
        raise ReviewFreezeError("review_base_not_ancestor", str(exc)) from exc


def _inside_worktree(
    repository: Any,
    value: Path | str,
    *,
    label: str,
    must_exist: bool,
    file_only: bool = True,
) -> Path:
    """Resolve one non-admin path below the anchored worktree without permitting aliases."""

    raw = Path(value)
    candidate = raw if raw.is_absolute() else repository.worktree / raw
    try:
        path = candidate.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise ReviewFreezeError(f"{label}_missing", str(candidate)) from exc
    try:
        path.relative_to(repository.worktree)
    except ValueError as exc:
        raise ReviewFreezeError(f"{label}_outside_repo", str(path)) from exc
    if (
        path == repository.worktree
        or repository.git_dir in path.parents
        or path == repository.git_dir
    ):
        raise ReviewFreezeError(f"{label}_targets_git_admin", str(path))
    if file_only and path.exists() and not path.is_file():
        raise ReviewFreezeError(f"{label}_not_file", str(path))
    return path


def _relative(repository: Any, path: Path) -> str:
    """Return one canonical slash-normalized path below the anchored worktree."""

    return path.relative_to(repository.worktree).as_posix()


def _require_ledger_path(repository: Any, value: Path | str, *, must_exist: bool) -> Path:
    """Limit writable protocol markers to their fixed, non-source namespace."""

    path = _inside_worktree(repository, value, label="ledger", must_exist=must_exist)
    relative = _relative(repository, path)
    parts = PurePosixPath(relative).parts
    if len(parts) < 2 or parts[0] != _LEDGER_ROOT or path.suffix != ".ledger":
        raise ReviewFreezeError("ledger_path_not_protocol_namespace", relative)
    return path


def _canonical_ledger_relative(lane_id: str) -> str:
    """Return the sole protocol ledger path permitted for one lane.

    A lane cannot choose a second transcript after a blocking admission.  The fixed filename is a
    small, complete-by-construction reconciliation rule: all events for ``gy-def6`` can only occur
    in ``.e11/gy-def6.ledger``.  A separate lane gets a separate, equally deterministic marker.
    """

    if (
        not lane_id
        or "\x00" in lane_id
        or PurePosixPath(lane_id).name != lane_id
        or lane_id in {".", ".."}
    ):
        raise ReviewFreezeError("lane_id_not_ledger_safe", lane_id)
    return f"{_LEDGER_ROOT}/{lane_id}.ledger"


def _ledger_matches_lane(repository: Any, ledger: Path, lane_id: str) -> bool:
    """Return whether a ledger path is the canonical append-only transcript for its lane."""

    try:
        return _relative(repository, ledger) == _canonical_ledger_relative(lane_id)
    except ReviewFreezeError:
        return False


def _require_evidence_path(
    repository: Any,
    value: Path | str,
    *,
    label: str,
    must_exist: bool,
    aliases: Sequence[Path] = (),
) -> Path:
    """Limit mutable raw review evidence to the ignored E11 scratch namespace."""

    path = _inside_worktree(repository, value, label=label, must_exist=must_exist)
    relative = _relative(repository, path)
    if not (relative == _EVIDENCE_ROOT or relative.startswith(f"{_EVIDENCE_ROOT}/")):
        raise ReviewFreezeError(f"{label}_not_evidence_namespace", relative)
    if any(path == alias for alias in aliases):
        raise ReviewFreezeError(f"{label}_aliases_protocol_input", relative)
    # ``check-ignore`` does not support Git's ``--literal-pathspecs`` global option, so use the
    # packager's hardened environment and explicit anchored administration arguments directly.
    # The path has already been resolved under the worktree and is never shell-expanded.
    result = subprocess.run(  # noqa: S603 - fixed Git argv with an already-validated path.
        [
            "git",
            "--no-pager",
            "--no-replace-objects",
            f"--git-dir={repository.git_dir}",
            f"--work-tree={repository.worktree}",
            "check-ignore",
            "-q",
            "--",
            relative,
        ],
        cwd=repository.worktree,
        env=review_package._git_environment(),
        check=False,
        capture_output=True,
        shell=False,
    )
    if result.returncode != 0:
        raise ReviewFreezeError(f"{label}_not_ignored", relative)
    return path


def _require_artifact_receipt_path(
    repository: Any, value: Path | str, *, aliases: Sequence[Path]
) -> Path:
    """Read a replay receipt only from the governed artifact root and bind its exact bytes."""

    path = _inside_worktree(repository, value, label="receipt", must_exist=True)
    relative = _relative(repository, path)
    artifact_root = _artifact_root(repository)
    if not (relative == artifact_root or relative.startswith(f"{artifact_root}/")):
        raise ReviewFreezeError("receipt_not_governed_artifact", relative)
    if any(path == alias for alias in aliases):
        raise ReviewFreezeError("receipt_aliases_protocol_input", relative)
    return path


def _event_digest(entry: dict[str, object]) -> str:
    """Hash one event while excluding the recursive entry-digest field."""

    return _sha256(
        _canonical_json_bytes({key: value for key, value in entry.items() if key != "entry_sha256"})
    )


def _read_bytes(path: Path) -> bytes:
    """Read a ledger's current bytes, treating an absent candidate ledger as empty."""

    return path.read_bytes() if path.exists() else b""


def _parse_ledger(payload: bytes) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Parse JSONL without turning malformed historical bytes into trusted objects."""

    events: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []
    if payload and not payload.endswith(b"\n"):
        issues.append({"code": "ledger_missing_trailing_newline"})
    for line, raw in enumerate(payload.splitlines(), start=1):
        if not raw:
            issues.append({"code": "ledger_blank_line", "line": line})
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            issues.append({"code": "ledger_json_invalid", "line": line, "detail": str(exc)})
            continue
        if not isinstance(value, dict):
            issues.append({"code": "ledger_entry_not_object", "line": line})
            continue
        events.append(value)
    return events, issues


def _validate_event_chain(events: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    """Recompute the JSONL sequence and hash chain, including provenance type safety."""

    issues: list[dict[str, object]] = []
    previous: str | None = None
    for expected_sequence, event in enumerate(events, start=1):
        sequence = event.get("sequence")
        if sequence != expected_sequence:
            issues.append({"code": "ledger_sequence_invalid", "sequence": sequence})
        if event.get("schema_version") != SCHEMA_VERSION:
            issues.append({"code": "ledger_schema_version_invalid", "sequence": sequence})
        if event.get("event_type") not in EVENT_TYPES:
            issues.append({"code": "ledger_event_type_invalid", "sequence": sequence})
        if not isinstance(event.get("lane_id"), str) or not str(event.get("lane_id")).strip():
            issues.append({"code": "ledger_lane_id_invalid", "sequence": sequence})
        if event.get("previous_entry_sha256") != previous:
            issues.append({"code": "ledger_previous_digest_invalid", "sequence": sequence})
        if event.get("entry_sha256") != _event_digest(event):
            issues.append({"code": "ledger_entry_digest_invalid", "sequence": sequence})
        provenance = event.get("predicate_provenance")
        if not isinstance(provenance, dict) or any(
            not isinstance(value, str) or value not in PROVENANCE_LABELS
            for value in provenance.values()
        ):
            issues.append({"code": "ledger_predicate_provenance_invalid", "sequence": sequence})
        if event.get("research_only") is not True:
            issues.append({"code": "ledger_research_only_missing", "sequence": sequence})
        if not isinstance(event.get("authoritative_for"), list):
            issues.append({"code": "ledger_authoritative_for_invalid", "sequence": sequence})
        if not isinstance(event.get("may_not_use_for"), list):
            issues.append({"code": "ledger_may_not_use_for_invalid", "sequence": sequence})
        digest = event.get("entry_sha256")
        previous = digest if isinstance(digest, str) else None
    return issues


def _load_events(path: Path) -> list[dict[str, object]]:
    """Load a valid live transcript before making an E11 decision or candidate append."""

    events, issues = _parse_ledger(_read_bytes(path))
    issues.extend(_validate_event_chain(events))
    if issues:
        raise ReviewFreezeError(
            "ledger_invalid", ", ".join(sorted({str(issue["code"]) for issue in issues}))
        )
    return events


def _head_ledger_blob(repository: Any, ledger: Path) -> bytes | None:
    """Return the exact HEAD blob for a ledger, or ``None`` when it is not yet committed."""

    relative = _relative(repository, ledger)
    result = _git_process(repository, "show", f"HEAD:{relative}")
    if result.returncode == 0:
        return result.stdout
    if result.returncode in {1, 128}:
        return None
    detail = result.stderr.decode("utf-8", errors="replace").strip()
    raise ReviewFreezeError("ledger_head_blob_unavailable", detail or relative)


def _history_issues(repository: Any, ledger: Path) -> list[dict[str, object]]:
    """Independently reconcile Git's complete ledger history and its current-byte prefix."""

    relative = _relative(repository, ledger)
    issues: list[dict[str, object]] = []
    try:
        revisions = (
            _git(
                repository,
                "log",
                "--format=%H",
                "--reverse",
                "--full-history",
                "--",
                relative,
            )
            .decode("ascii", errors="strict")
            .splitlines()
        )
    except ReviewFreezeError as exc:
        return [{"code": "ledger_history_unavailable", "detail": exc.code}]
    prior: bytes | None = None
    for revision in revisions:
        try:
            blob = _git(repository, "show", f"{revision}:{relative}")
        except ReviewFreezeError as exc:
            issues.append(
                {"code": "ledger_history_blob_unavailable", "commit": revision, "detail": exc.code}
            )
            continue
        if prior is not None and not blob.startswith(prior):
            issues.append({"code": "ledger_history_not_append_only", "commit": revision})
        prior = blob
    head_blob = _head_ledger_blob(repository, ledger)
    current = _read_bytes(ledger)
    if head_blob is not None and not current.startswith(head_blob):
        issues.append({"code": "ledger_current_not_append_only"})
    if head_blob is not None and not ledger.exists():
        issues.append({"code": "ledger_current_deleted"})
    return issues


def _committed_events(
    repository: Any, ledger: Path, *, require_live_exact: bool
) -> list[dict[str, object]]:
    """Return the committed transcript, rejecting an uncommitted or rewritten gate predicate."""

    blob = _head_ledger_blob(repository, ledger)
    if blob is None:
        raise ReviewFreezeError("freeze_marker_not_committed")
    current = _read_bytes(ledger)
    if not current.startswith(blob):
        raise ReviewFreezeError("ledger_current_not_append_only")
    if require_live_exact and current != blob:
        raise ReviewFreezeError("ledger_gate_events_not_committed")
    events, issues = _parse_ledger(blob)
    issues.extend(_validate_event_chain(events))
    issues.extend(_history_issues(repository, ledger))
    if not issues:
        issues.extend(_semantic_transcript_issues(repository, ledger, events))
    if issues:
        raise ReviewFreezeError(
            "ledger_history_invalid", ", ".join(sorted({str(issue["code"]) for issue in issues}))
        )
    return events


def _authority_fields(lane_id: str) -> dict[str, object]:
    """Attach the explicit authority boundary every ledger-side artifact must carry."""

    return {
        "research_only": True,
        "authoritative_for": [f"E11 source-bound disposition scheduling for lane {lane_id}"],
        "may_not_use_for": list(_AUTHORITY_DENIALS),
    }


def _expected_predicate_provenance(event: dict[str, object]) -> dict[str, str] | None:
    """Return the exact, admission-frozen predicate labels required for one event type."""

    event_type = event.get("event_type")
    if event_type == "open":
        return {
            "lane_id": "consumer_asserted",
            "receipt_chain_id": "consumer_asserted",
            "review_base_commit": "consumer_asserted",
            "opening_head_commit": "recomputed",
            "review_base_ancestry": "recomputed",
            "required_reviews": "institutionally_supplied",
            "ledger_hash_chain": "recomputed",
        }
    if event_type == "freeze":
        return {
            "ledger_hash_chain": "recomputed",
            "source_tree_fingerprint": "recomputed",
            "current_source_match": "recomputed",
            "source_scope": "recomputed",
            "open_event_binding": "recomputed",
            "reviewer_roster": "institutionally_supplied",
            "review_base_commit": "consumer_asserted",
            "review_base_ancestry": "recomputed",
            "receipt_chain_id": "consumer_asserted",
        }
    if event_type == "review_package":
        is_delta = event.get("package_kind") == "delta"
        return {
            "current_source_match": "recomputed",
            "package_byte_binding": "recomputed",
            "checklist_byte_binding": "recomputed" if is_delta else "not_established",
            "batch_membership": "recomputed" if is_delta else "not_established",
            "reviewer_independence": "institutionally_supplied",
        }
    if event_type == "review_result":
        return {
            "review_package_binding": "recomputed",
            "review_result_byte_binding": "recomputed",
            "reviewer_independence": "institutionally_supplied",
            "reviewer_roster_membership": "recomputed",
            "review_completeness": "institutionally_supplied",
        }
    if event_type == "admit_finding":
        frozen = event.get("freeze_id") is not None
        review_bound = frozen and isinstance(event.get("review_result_id"), str)
        classification = event.get("classification_provenance")
        reasons = event.get("reasons")
        marker_uncommitted = isinstance(reasons, list) and "freeze_marker_not_committed" in reasons
        return {
            "finding_identity": "recomputed",
            "finding_semantics": "consumer_asserted",
            "declared_classification": "consumer_asserted",
            "classification": classification
            if isinstance(classification, str)
            else "not_established",
            "freeze_source_match": (
                "recomputed" if frozen and not marker_uncommitted else "not_established"
            ),
            "review_round_binding": "recomputed" if review_bound else "not_established",
            "batch_membership": "recomputed",
        }
    if event_type == "resolve_member":
        return {
            "batch_membership": "recomputed",
            "delta_review_member_binding": "recomputed",
            "resolution_evidence_binding": "recomputed",
            "repair_acceptance": "institutionally_supplied",
        }
    if event_type == "replay_recorded":
        return {
            "current_source_match": "recomputed",
            "review_round_presence": "recomputed",
            "review_roster_coverage": "recomputed",
            "batch_membership": "recomputed",
            "receipt_byte_binding": "recomputed",
            "receipt_chain_membership": "consumer_asserted",
            "reviewer_independence": "institutionally_supplied",
            "receipt_semantic_validity": "not_established",
        }
    if event_type == "closed":
        return {
            "replay_record_presence": "recomputed",
            "batch_membership": "recomputed",
            "ledger_hash_chain": "recomputed",
            "receipt_chain_membership": "consumer_asserted",
            "reviewer_independence": "institutionally_supplied",
            "receipt_semantic_validity": "not_established",
        }
    return None


def _append_event(repository: Any, ledger: Path, payload: dict[str, object]) -> dict[str, object]:
    """Append exactly one new event while preserving current and committed prefixes."""

    lock = ledger.with_name(f".{ledger.name}.lock")
    with exclusive_lock(lock, content="review-freeze append\n"):
        issues = _history_issues(repository, ledger)
        if issues:
            raise ReviewFreezeError(
                "ledger_history_invalid",
                ", ".join(sorted({str(issue["code"]) for issue in issues})),
            )
        events = _load_events(ledger)
        previous = _read_bytes(ledger)
        if previous and not previous.endswith(b"\n"):
            raise ReviewFreezeError("ledger_missing_trailing_newline")
        lane_id = payload.get("lane_id")
        if not isinstance(lane_id, str) or not lane_id.strip():
            raise ReviewFreezeError("ledger_lane_id_invalid")
        entry: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "sequence": len(events) + 1,
            "previous_entry_sha256": events[-1]["entry_sha256"] if events else None,
            **_authority_fields(lane_id),
            **payload,
        }
        entry["entry_sha256"] = _event_digest(entry)
        semantic_issues = _semantic_transcript_issues(repository, ledger, [*events, entry])
        if semantic_issues:
            raise ReviewFreezeError(
                "ledger_semantic_invalid",
                ", ".join(sorted({str(issue["code"]) for issue in semantic_issues})),
            )
        atomic_write_bytes(ledger, previous + _canonical_json_bytes(entry) + b"\n")
        return entry


def _freeze_events(events: Iterable[dict[str, object]], lane_id: str) -> list[dict[str, object]]:
    """Return immutable freeze events for a lane in append order."""

    return [
        event
        for event in events
        if event.get("lane_id") == lane_id and event.get("event_type") == "freeze"
    ]


def _opening_event(events: Iterable[dict[str, object]], lane_id: str) -> dict[str, object] | None:
    """Return the single lane-opening declaration that a freeze must bind exactly."""

    openings = [
        event
        for event in events
        if event.get("lane_id") == lane_id and event.get("event_type") == "open"
    ]
    return openings[0] if len(openings) == 1 else None


def _freeze_by_id(events: Iterable[dict[str, object]], freeze_id: str) -> dict[str, object] | None:
    """Find one freeze boundary by immutable identifier."""

    return next(
        (
            event
            for event in events
            if event.get("event_type") == "freeze" and event.get("freeze_id") == freeze_id
        ),
        None,
    )


def _superseded_ids(events: Iterable[dict[str, object]], lane_id: str) -> set[str]:
    """Return freeze IDs superseded by a later, append-only repair boundary."""

    return {
        event["supersedes_freeze_id"]
        for event in _freeze_events(events, lane_id)
        if isinstance(event.get("supersedes_freeze_id"), str)
    }


def _active_freeze(events: Iterable[dict[str, object]], lane_id: str) -> dict[str, object] | None:
    """Return the current unsuperseded boundary for a lane."""

    superseded = _superseded_ids(events, lane_id)
    for freeze in reversed(_freeze_events(events, lane_id)):
        if freeze.get("freeze_id") not in superseded:
            return freeze
    return None


def _freeze_state(events: Iterable[dict[str, object]], lane_id: str, freeze_id: str) -> str:
    """Derive a boundary's lifecycle state from immutable later events."""

    state = "frozen"
    for event in events:
        if event.get("lane_id") != lane_id or event.get("freeze_id") != freeze_id:
            continue
        if event.get("event_type") == "replay_recorded":
            state = "replayed"
        elif event.get("event_type") == "closed":
            state = "closed"
    return state


def _lineage(events: Iterable[dict[str, object]], freeze_id: str) -> set[str]:
    """Return a freeze plus all immutable predecessors it explicitly supersedes."""

    by_id = {
        str(event["freeze_id"]): event
        for event in events
        if event.get("event_type") == "freeze" and isinstance(event.get("freeze_id"), str)
    }
    lineage: set[str] = set()
    current = freeze_id
    while current and current not in lineage:
        lineage.add(current)
        event = by_id.get(current)
        prior = event.get("supersedes_freeze_id") if event is not None else None
        current = prior if isinstance(prior, str) else ""
    return lineage


def _resolved_ids(events: Iterable[dict[str, object]], lane_id: str) -> set[str]:
    """Return batch members closed by a content-bound resolution event."""

    return {
        event["finding_id"]
        for event in events
        if event.get("lane_id") == lane_id
        and event.get("event_type") == "resolve_member"
        and isinstance(event.get("finding_id"), str)
    }


def _open_members(
    events: Iterable[dict[str, object]],
    lane_id: str,
    *,
    active_freeze_id: str | None = None,
) -> list[dict[str, object]]:
    """Return unresolved batch members, carrying predecessor members into a repair successor."""

    allowed = _lineage(events, active_freeze_id) if active_freeze_id else None
    resolved = _resolved_ids(events, lane_id)
    return [
        event
        for event in events
        if event.get("lane_id") == lane_id
        and event.get("event_type") == "admit_finding"
        and event.get("disposition") == "batch"
        and isinstance(event.get("finding_id"), str)
        and event["finding_id"] not in resolved
        and (allowed is None or event.get("freeze_id") in allowed)
    ]


def _is_event_committed(repository: Any, ledger: Path, event: dict[str, object]) -> bool:
    """Return whether an exact event is present in the committed ledger prefix."""

    try:
        committed = _committed_events(repository, ledger, require_live_exact=False)
    except ReviewFreezeError:
        return False
    digest = event.get("entry_sha256")
    return isinstance(digest, str) and any(item.get("entry_sha256") == digest for item in committed)


def _source_path(repository: Any, relative: str, ledger_relative: str) -> bool:
    """Return whether one Git-root path belongs to E11's fixed implementation scope."""

    implementation_root = _implementation_root(repository)
    scoped_relative = relative
    if implementation_root:
        prefix = f"{implementation_root}/"
        if not relative.startswith(prefix):
            return False
        scoped_relative = relative.removeprefix(prefix)
    ledger_path = PurePosixPath(ledger_relative)
    ledger_lock = ledger_path.with_name(f".{ledger_path.name}.lock").as_posix()
    if relative in {ledger_relative, ledger_lock} or scoped_relative in {
        ledger_relative,
        ledger_lock,
    }:
        return False
    return not any(
        scoped_relative == root or scoped_relative.startswith(f"{root}/")
        for root in _NON_SOURCE_ROOTS
    )


def _tree_identity(repository: Any, *, commit: str, ledger_relative: str) -> dict[str, object]:
    """Recompute a complete implementation-tree identity, not a caller-declared exclusion set."""

    payload = _git(repository, "ls-tree", "-r", "-z", "--full-tree", commit)
    digest = hashlib.sha256()
    digest.update(f"{TREE_FINGERPRINT_ALGORITHM}\0".encode("ascii"))
    count = 0
    for entry in payload.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b"\t", 1)
        except ValueError as exc:
            raise ReviewFreezeError("git_tree_entry_malformed") from exc
        relative = os.fsdecode(raw_path)
        if not _source_path(repository, relative, ledger_relative):
            continue
        digest.update(metadata)
        digest.update(b"\t")
        digest.update(raw_path)
        digest.update(b"\0")
        count += 1
    return {
        "algorithm": TREE_FINGERPRINT_ALGORITHM,
        "fingerprint": f"sha256:{digest.hexdigest()}",
        "tracked_entry_count": count,
    }


def _nul_paths(payload: bytes) -> tuple[str, ...]:
    """Decode Git's NUL-delimited paths without losing whitespace-bearing names."""

    return tuple(os.fsdecode(item) for item in payload.split(b"\0") if item)


def _local_git_config(repository: Any, key: str) -> bytes | None:
    """Read one effective repository configuration value through the anchored Git context.

    The hardened environment disables system/global values.  Deliberately omit ``--local`` here:
    linked worktrees may place a load-bearing setting in ``config.worktree``, and treating that
    live configuration as absent would re-open the source-stat-cache bypass.
    """

    result = _git_process(repository, "config", "--get", key)
    if result.returncode == 0:
        return result.stdout.strip()
    if result.returncode == 1:
        return None
    detail = result.stderr.decode("utf-8", errors="replace").strip()
    raise ReviewFreezeError("git_source_configuration_unavailable", f"{key}: {detail}")


def _local_git_boolean(repository: Any, key: str) -> bool | None:
    """Read one effective Git boolean with Git's own spelling normalization."""

    result = _git_process(repository, "config", "--bool", "--get", key)
    if result.returncode == 0:
        normalized = result.stdout.strip()
        if normalized == b"true":
            return True
        if normalized == b"false":
            return False
        raise ReviewFreezeError("git_source_configuration_invalid", key)
    if result.returncode == 1:
        return None
    detail = result.stderr.decode("utf-8", errors="replace").strip()
    raise ReviewFreezeError("git_source_configuration_unavailable", f"{key}: {detail}")


def _working_source_changes(repository: Any, ledger_relative: str) -> tuple[str, ...]:
    """Return every staged, unstaged, or nonignored-untracked implementation-source change."""

    changed = _nul_paths(_git(repository, "diff", "--name-only", "-z", "HEAD", "--"))
    untracked = _nul_paths(
        _git(repository, "ls-files", "--others", "--exclude-standard", "-z", "--")
    )
    # ``git diff HEAD`` deliberately does not report a path marked assume-unchanged.  Such an
    # index bit must never create an invisible source change below an E11 boundary.  ``ls-files
    # -v`` renders ordinary cached entries as ``H``; any other tag (including lower-case
    # assume-unchanged and ``S`` skip-worktree) is conservatively a source-scope mismatch.
    flagged: set[str] = set()
    filemode = _local_git_boolean(repository, "core.filemode")
    if filemode is not None:
        if filemode is not True:
            # The source fingerprint binds Git tree modes.  A local false setting would make a
            # chmod-only implementation mutation invisible to ``git diff`` on this worktree.
            flagged.add("source_filemode_unreliable")
    # Git's stat cache is a performance optimization, not an E11 identity source.  The default
    # local settings are safe enough for Git's normal refresh; explicitly weakening ctime/checkstat
    # or delegating freshness to fsmonitor could hide a same-size, restored-mtime source mutation.
    # Rather than call that condition "recomputed", the gate fails closed on those local modes.
    for key in ("core.trustctime", "core.ignorestat"):
        configured = _local_git_boolean(repository, key)
        if (key == "core.trustctime" and configured is False) or (
            key == "core.ignorestat" and configured is True
        ):
            flagged.add(f"source_stat_cache_unreliable:{key}={str(configured).lower()}")
    check_stat = _local_git_config(repository, "core.checkStat")
    if check_stat is not None and check_stat.lower() == b"minimal":
        flagged.add("source_stat_cache_unreliable:core.checkStat=minimal")
    fsmonitor = _local_git_config(repository, "core.fsmonitor")
    if fsmonitor is not None and fsmonitor.lower() not in {b"false", b"no", b"off", b"0", b""}:
        flagged.add("source_stat_cache_unreliable:core.fsmonitor")
    for entry in _git(repository, "ls-files", "-v", "-z", "--").split(b"\0"):
        if not entry:
            continue
        if len(entry) < 3 or entry[1:2] != b" ":
            raise ReviewFreezeError("git_index_entry_malformed")
        tag = entry[:1]
        path = os.fsdecode(entry[2:])
        if tag != b"H" and _source_path(repository, path, ledger_relative):
            flagged.add(f"source_index_flagged:{path}")
    return tuple(
        sorted(
            {
                *(path for path in changed if _source_path(repository, path, ledger_relative)),
                *(path for path in untracked if _source_path(repository, path, ledger_relative)),
                *flagged,
            }
        )
    )


def _freeze_identity(repository: Any, ledger: Path, source_commit: str) -> dict[str, object]:
    """Construct E11's fixed implementation-source identity and require it to be clean."""

    ledger_relative = _relative(repository, ledger)
    changes = _working_source_changes(repository, ledger_relative)
    if changes:
        raise ReviewFreezeError("freeze_worktree_not_clean", ", ".join(changes))
    snapshot = _tree_identity(repository, commit=source_commit, ledger_relative=ledger_relative)
    return {
        **snapshot,
        "source_commit": source_commit,
        "ledger_path": ledger_relative,
        "scope": _source_scope(repository, ledger_relative),
    }


def _source_identity_issues(repository: Any, ledger: Path, freeze: dict[str, object]) -> list[str]:
    """Validate a freeze's persisted source identity against the canonical local scope.

    The ledger is an input to the identity, not an authority that may declare its own exclusion.
    This prevents a self-hashed record from hiding a source path by naming it as ``ledger_path``.
    """

    identity = freeze.get("source_identity")
    if not isinstance(identity, dict):
        return ["freeze_source_identity_missing"]
    source_commit = identity.get("source_commit")
    actual_ledger_relative = _relative(repository, ledger)
    expected_keys = {
        "algorithm",
        "fingerprint",
        "tracked_entry_count",
        "source_commit",
        "ledger_path",
        "scope",
    }
    if set(identity) != expected_keys:
        return ["freeze_source_identity_schema_invalid"]
    if (
        identity.get("algorithm") != TREE_FINGERPRINT_ALGORITHM
        or identity.get("ledger_path") != actual_ledger_relative
        or identity.get("scope") != _source_scope(repository, actual_ledger_relative)
        or not isinstance(source_commit, str)
        or not isinstance(identity.get("fingerprint"), str)
        or not isinstance(identity.get("tracked_entry_count"), int)
    ):
        return ["freeze_source_identity_malformed"]
    try:
        resolved = _resolve_commit(repository, source_commit, label="freeze_source_commit")
        snapshot = _tree_identity(
            repository, commit=resolved, ledger_relative=actual_ledger_relative
        )
    except ReviewFreezeError as exc:
        return [exc.code]
    if resolved != source_commit:
        return ["freeze_source_commit_not_canonical"]
    if (
        snapshot["fingerprint"] != identity["fingerprint"]
        or snapshot["tracked_entry_count"] != identity["tracked_entry_count"]
    ):
        return ["recorded_source_commit_fingerprint_drift"]
    return []


def _source_match(repository: Any, ledger: Path, freeze: dict[str, object]) -> dict[str, object]:
    """Recompute whether the current implementation source still matches a freeze identity."""

    identity = freeze.get("source_identity")
    identity_issues = _source_identity_issues(repository, ledger, freeze)
    if identity_issues or not isinstance(identity, dict):
        return {
            "matches": False,
            "reasons": identity_issues or ["freeze_source_identity_missing"],
            "predicate_provenance": "not_established",
        }
    source_commit = identity.get("source_commit")
    recorded = identity.get("fingerprint")
    ledger_relative = _relative(repository, ledger)
    if not isinstance(source_commit, str) or not isinstance(recorded, str):
        return {
            "matches": False,
            "reasons": ["freeze_source_identity_malformed"],
            "predicate_provenance": "not_established",
        }
    try:
        source = _resolve_commit(repository, source_commit, label="freeze_source_commit")
        current = _head(repository)
        current_snapshot = _tree_identity(
            repository, commit=current, ledger_relative=ledger_relative
        )
        changes = _working_source_changes(repository, ledger_relative)
    except ReviewFreezeError as exc:
        return {"matches": False, "reasons": [exc.code], "predicate_provenance": "not_established"}
    reasons: list[str] = []
    if current_snapshot["fingerprint"] != recorded:
        reasons.append("freeze_source_moved")
    if changes:
        reasons.append("freeze_worktree_changed")
    return {
        "matches": not reasons,
        "reasons": reasons,
        "source_commit": source,
        "current_head": current,
        "current_tree_fingerprint": current_snapshot["fingerprint"],
        "working_changes": list(changes),
        "predicate_provenance": "recomputed",
    }


def _require_active_frozen(
    repository: Any,
    ledger: Path,
    events: Sequence[dict[str, object]],
    *,
    lane_id: str,
    freeze_id: str,
    require_committed: bool,
) -> dict[str, object]:
    """Require a named active frozen boundary and, where load-bearing, its committed authority."""

    active = _active_freeze(events, lane_id)
    if active is None or active.get("freeze_id") != freeze_id:
        raise ReviewFreezeError("freeze_not_active", freeze_id)
    if _freeze_state(events, lane_id, freeze_id) != "frozen":
        raise ReviewFreezeError("freeze_not_admitting_state")
    if require_committed:
        committed = _committed_events(repository, ledger, require_live_exact=True)
        if not any(item.get("entry_sha256") == active.get("entry_sha256") for item in committed):
            raise ReviewFreezeError("freeze_marker_not_committed")
    match = _source_match(repository, ledger, active)
    if not match["matches"]:
        raise ReviewFreezeError("freeze_source_moved", ", ".join(match["reasons"]))
    return active


def _review_package_by_id(
    events: Iterable[dict[str, object]], package_id: str
) -> dict[str, object] | None:
    """Find one package binding by immutable ID."""

    return next(
        (
            event
            for event in events
            if event.get("event_type") == "review_package"
            and event.get("review_package_id") == package_id
        ),
        None,
    )


def _review_result_by_id(
    events: Iterable[dict[str, object]], result_id: str
) -> dict[str, object] | None:
    """Find one content-bound reviewer-result event by ID."""

    return next(
        (
            event
            for event in events
            if event.get("event_type") == "review_result"
            and event.get("review_result_id") == result_id
        ),
        None,
    )


def _bound_evidence_bytes(
    repository: Any,
    ledger: Path,
    *,
    reference: object,
    expected_sha256: object,
    label: str,
) -> bytes:
    """Resolve an ignored evidence file and prove its current bytes still match the ledger."""

    if not isinstance(reference, str) or not isinstance(expected_sha256, str):
        raise ReviewFreezeError(f"{label}_binding_missing")
    path = _require_evidence_path(
        repository, reference, label=label, must_exist=True, aliases=(ledger,)
    )
    payload = path.read_bytes()
    if not payload or not payload.strip():
        raise ReviewFreezeError(f"{label}_empty", reference)
    if _sha256(payload) != expected_sha256:
        raise ReviewFreezeError(f"{label}_digest_drift", reference)
    return payload


def _bound_receipt_bytes(
    repository: Any,
    ledger: Path,
    *,
    reference: object,
    expected_sha256: object,
) -> bytes:
    """Require a replay receipt to be byte-bound both live and at ``HEAD``.

    The record cannot turn an uncommitted governed artifact into a closure predicate.  This only
    establishes byte identity; receipt-chain membership and semantics remain explicitly degraded.
    """

    if not isinstance(reference, str) or not isinstance(expected_sha256, str):
        raise ReviewFreezeError("receipt_binding_missing")
    receipt = _require_artifact_receipt_path(repository, reference, aliases=(ledger,))
    payload = receipt.read_bytes()
    if not payload or not payload.strip():
        raise ReviewFreezeError("receipt_empty", reference)
    if _sha256(payload) != expected_sha256:
        raise ReviewFreezeError("receipt_digest_drift", reference)
    relative = _relative(repository, receipt)
    result = _git_process(repository, "show", f"HEAD:{relative}")
    if result.returncode != 0 or result.stdout != payload:
        raise ReviewFreezeError("receipt_not_committed", relative)
    return payload


def _bound_package_bytes(repository: Any, ledger: Path, package: dict[str, object]) -> bytes:
    """Recompute the canonical packager output and bind it to the persisted package event."""

    package_bytes = _bound_evidence_bytes(
        repository,
        ledger,
        reference=package.get("package_ref"),
        expected_sha256=package.get("package_sha256"),
        label="review_package",
    )
    base_commit = package.get("base_commit")
    head_commit = package.get("head_commit")
    kind = package.get("package_kind")
    if not isinstance(base_commit, str) or not isinstance(head_commit, str):
        raise ReviewFreezeError("review_package_commit_binding_missing")
    base = _resolve_commit(repository, base_commit, label="review_package_base")
    head = _resolve_commit(repository, head_commit, label="review_package_head")
    if base != base_commit or head != head_commit or kind not in {"full", "delta"}:
        raise ReviewFreezeError("review_package_commit_binding_invalid")
    _require_review_base_ancestor(repository, base, head)
    if base == head:
        raise ReviewFreezeError("review_package_range_empty")
    checklist: bytes | None = None
    if kind == "delta":
        checklist = _bound_evidence_bytes(
            repository,
            ledger,
            reference=package.get("checklist_ref"),
            expected_sha256=package.get("checklist_sha256"),
            label="checklist",
        )
    elif package.get("checklist_ref") is not None or package.get("checklist_sha256") is not None:
        raise ReviewFreezeError("review_package_full_has_checklist")
    try:
        review_package._require_neutral_info_attributes(repository)
        review_package._require_bound_repository_configuration(repository)
        with review_package._hermetic_git_context(repository) as git_context:
            expected = review_package._render_package(
                git_context,
                base_commit=base,
                head_commit=head,
                prior_findings=checklist,
            )
    except (OSError, ReviewPackageError) as exc:
        raise ReviewFreezeError("review_package_recompute_failed", str(exc)) from exc
    if package_bytes != expected:
        raise ReviewFreezeError("review_package_not_canonical")
    return package_bytes


def _bound_review_result_bytes(repository: Any, ledger: Path, result: dict[str, object]) -> bytes:
    """Rebind a reviewer result at every consuming transition, never just at admission."""

    return _bound_evidence_bytes(
        repository,
        ledger,
        reference=result.get("result_ref"),
        expected_sha256=result.get("result_sha256"),
        label="review_result",
    )


def _require_committed_review_result(
    repository: Any,
    ledger: Path,
    events: Sequence[dict[str, object]],
    *,
    lane_id: str,
    freeze_id: str,
    review_result_id: str | None,
) -> dict[str, object]:
    """Require a committed reviewer result bound to the exact active source/package boundary."""

    if not isinstance(review_result_id, str) or not review_result_id:
        raise ReviewFreezeError("review_round_missing")
    result = _review_result_by_id(events, review_result_id)
    if result is None or result.get("lane_id") != lane_id or result.get("freeze_id") != freeze_id:
        raise ReviewFreezeError("review_result_not_for_active_freeze")
    package = _review_package_by_id(events, str(result.get("review_package_id") or ""))
    if (
        package is None
        or package.get("lane_id") != lane_id
        or package.get("freeze_id") != freeze_id
    ):
        raise ReviewFreezeError("review_package_binding_missing")
    committed = _committed_events(repository, ledger, require_live_exact=True)
    committed_digests = {item.get("entry_sha256") for item in committed}
    if (
        result.get("entry_sha256") not in committed_digests
        or package.get("entry_sha256") not in committed_digests
    ):
        raise ReviewFreezeError("review_round_not_committed")
    _bound_package_bytes(repository, ledger, package)
    _bound_review_result_bytes(repository, ledger, result)
    return result


def open_lane(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    receipt_chain_id: str,
    review_base_revision: str,
    required_reviews: Sequence[str],
    recorded_at: str,
) -> dict[str, object]:
    """Append a candidate open event; its future freeze becomes authoritative only after commit."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=False)
    review_roster = tuple(
        sorted({str(review).strip() for review in required_reviews if str(review).strip()})
    )
    if (
        not str(lane_id).strip()
        or not str(receipt_chain_id).strip()
        or not review_roster
        or not str(recorded_at).strip()
    ):
        raise ReviewFreezeError("open_event_required_field_missing")
    current = _head(repository)
    review_base = _resolve_commit(repository, review_base_revision, label="review_base")
    _require_review_base_ancestor(repository, review_base, current)
    if review_base == current:
        raise ReviewFreezeError("review_base_equals_current_source")
    existing = _load_events(ledger)
    if any(
        event.get("lane_id") == lane_id and event.get("event_type") == "open" for event in existing
    ):
        raise ReviewFreezeError("lane_already_open_or_frozen")
    return _append_event(
        repository,
        ledger,
        {
            "event_type": "open",
            "lane_id": lane_id,
            "receipt_chain_id": receipt_chain_id,
            "review_base_commit": review_base,
            "opening_head_commit": current,
            "required_reviews": list(review_roster),
            "recorded_at": recorded_at,
            "predicate_provenance": {
                "lane_id": "consumer_asserted",
                "receipt_chain_id": "consumer_asserted",
                "review_base_commit": "consumer_asserted",
                "opening_head_commit": "recomputed",
                "review_base_ancestry": "recomputed",
                "required_reviews": "institutionally_supplied",
                "ledger_hash_chain": "recomputed",
            },
        },
    )


def freeze_lane(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    receipt_chain_id: str,
    recorded_at: str,
    source_commit: str | None = None,
    supersedes_freeze_id: str | None = None,
    receipt_chain_paths: Sequence[str] = (),
) -> dict[str, object]:
    """Append a candidate freeze using a fixed source scope, never a caller-provided exclusion."""

    if receipt_chain_paths:
        raise ReviewFreezeError("receipt_chain_paths_not_supported")
    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=False)
    events = _load_events(ledger)
    active = _active_freeze(events, lane_id)
    if not str(receipt_chain_id).strip() or not str(recorded_at).strip():
        raise ReviewFreezeError("freeze_required_field_missing")
    opening = _opening_event(events, lane_id)
    if opening is None:
        if not any(
            event.get("event_type") == "open" and event.get("lane_id") == lane_id
            for event in events
        ):
            raise ReviewFreezeError("lane_not_open")
        raise ReviewFreezeError("lane_opening_ambiguous")
    opening_roster = opening.get("required_reviews")
    opening_base = opening.get("review_base_commit")
    if not isinstance(opening_roster, list) or not opening_roster:
        raise ReviewFreezeError("lane_opening_roster_invalid")
    if not isinstance(opening_base, str):
        raise ReviewFreezeError("lane_opening_review_base_invalid")
    if opening.get("receipt_chain_id") != receipt_chain_id:
        raise ReviewFreezeError("receipt_chain_id_changed_during_lane")
    if active is None:
        if supersedes_freeze_id is not None:
            raise ReviewFreezeError("supersedes_without_prior_freeze")
    else:
        active_id = str(active.get("freeze_id"))
        if supersedes_freeze_id != active_id:
            raise ReviewFreezeError("freeze_requires_explicit_supersession")
        if _freeze_state(events, lane_id, active_id) != "frozen":
            raise ReviewFreezeError("superseded_freeze_not_open")
        if (
            active.get("receipt_chain_id") != receipt_chain_id
            or active.get("required_reviews") != opening_roster
            or active.get("open_event_sha256") != opening.get("entry_sha256")
            or active.get("review_base_commit") != opening_base
        ):
            raise ReviewFreezeError("receipt_chain_id_changed_during_lane")
        if not _is_event_committed(repository, ledger, active):
            raise ReviewFreezeError("freeze_marker_not_committed")
        prior_members = _open_members(events, lane_id, active_freeze_id=active_id)
        if not prior_members:
            raise ReviewFreezeError("superseding_freeze_requires_open_batch")
        if not all(_is_event_committed(repository, ledger, member) for member in prior_members):
            raise ReviewFreezeError("batch_members_not_committed")
    current = _head(repository)
    resolved = _resolve_commit(repository, source_commit or current, label="source_commit")
    if resolved != current:
        raise ReviewFreezeError("source_commit_not_current_head")
    _require_review_base_ancestor(repository, opening_base, resolved)
    if opening_base == resolved:
        raise ReviewFreezeError("review_base_equals_frozen_source")
    identity = _freeze_identity(repository, ledger, resolved)
    if active is not None:
        prior_identity = active.get("source_identity")
        if not isinstance(prior_identity, dict) or identity["fingerprint"] == prior_identity.get(
            "fingerprint"
        ):
            raise ReviewFreezeError("superseding_freeze_requires_source_repair")
    freeze_id = f"{lane_id}:freeze:{len(events) + 1}"
    payload: dict[str, object] = {
        "event_type": "freeze",
        "lane_id": lane_id,
        "freeze_id": freeze_id,
        "state": "frozen",
        "receipt_chain_id": receipt_chain_id,
        "open_event_sha256": opening["entry_sha256"],
        "required_reviews": opening_roster,
        "review_base_commit": opening_base,
        "source_identity": identity,
        "recorded_at": recorded_at,
        "predicate_provenance": {
            "ledger_hash_chain": "recomputed",
            "source_tree_fingerprint": "recomputed",
            "current_source_match": "recomputed",
            "source_scope": "recomputed",
            "open_event_binding": "recomputed",
            "reviewer_roster": "institutionally_supplied",
            "review_base_commit": "consumer_asserted",
            "review_base_ancestry": "recomputed",
            "receipt_chain_id": "consumer_asserted",
        },
    }
    if supersedes_freeze_id is not None:
        payload["supersedes_freeze_id"] = supersedes_freeze_id
    return _append_event(repository, ledger, payload)


def lane_state(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
) -> dict[str, object]:
    """Render lifecycle only from the committed transcript, exposing live bytes as pending."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=False)
    live_events = _load_events(ledger)
    try:
        events = _committed_events(repository, ledger, require_live_exact=False)
    except ReviewFreezeError as exc:
        if exc.code != "freeze_marker_not_committed":
            raise
        events = []
    pending_count = len(live_events) - len(events)
    active = _active_freeze(events, lane_id)
    freezes = _freeze_events(events, lane_id)
    if active is None:
        live_active = _active_freeze(live_events, lane_id)
        return {
            "lane_id": lane_id,
            "state": "open",
            "active_freeze_id": None,
            "freeze_ids": [event["freeze_id"] for event in freezes],
            "pending_freeze_id": (
                live_active.get("freeze_id") if isinstance(live_active, dict) else None
            ),
            "pending_event_count": pending_count,
            "open_batch_member_ids": [
                event["finding_id"] for event in _open_members(events, lane_id)
            ],
        }
    freeze_id = str(active["freeze_id"])
    members = _open_members(events, lane_id, active_freeze_id=freeze_id)
    derived_state = _freeze_state(events, lane_id, freeze_id)
    lifecycle_event = next(
        (
            event
            for event in reversed(events)
            if event.get("lane_id") == lane_id
            and event.get("freeze_id") == freeze_id
            and event.get("event_type") in {"replay_recorded", "closed"}
        ),
        None,
    )
    return {
        "lane_id": lane_id,
        "state": derived_state,
        "active_freeze_id": freeze_id,
        "pending_freeze_id": None,
        "freeze_ids": [event["freeze_id"] for event in freezes],
        "freeze_marker_committed": True,
        "pending_event_count": pending_count,
        "state_scope": (
            lifecycle_event.get("state_scope") if isinstance(lifecycle_event, dict) else None
        ),
        "state_claim_grade": (
            lifecycle_event.get("state_claim_grade") if isinstance(lifecycle_event, dict) else None
        ),
        "state_semantic_validity": (
            lifecycle_event.get("state_semantic_validity")
            if isinstance(lifecycle_event, dict)
            else None
        ),
        "open_batch_member_ids": [event["finding_id"] for event in members],
        "open_batch_members": [
            {
                "finding_id": event["finding_id"],
                "finding_ref": event["finding_ref"],
                "finding_sha256": event["finding_sha256"],
                "origin_freeze_id": event["freeze_id"],
            }
            for event in members
        ],
        "source_match": _source_match(repository, ledger, active),
    }


def _finding_bytes(repository: Any, finding_path: Path | str, *, ledger: Path) -> tuple[str, bytes]:
    """Read an opaque, ignored raw finding without allowing an alias to the protocol marker."""

    path = _require_evidence_path(
        repository, finding_path, label="finding", must_exist=True, aliases=(ledger,)
    )
    payload = path.read_bytes()
    if not payload or not payload.strip():
        raise ReviewFreezeError("finding_empty")
    return _relative(repository, path), payload


def _record_disposition(
    *,
    repository: Any,
    ledger: Path,
    lane_id: str,
    finding_id: str,
    finding_path: Path | str,
    declared_classification: str,
    classification_provenance: str,
    review_result_id: str | None,
    recorded_at: str,
    recomputed_cosmetic: bool,
    classifier: str | None,
) -> dict[str, object]:
    """Run the disposition gate and append an exact raw-finding admission event."""

    if not str(finding_id).strip() or not str(recorded_at).strip():
        raise ReviewFreezeError("finding_required_field_missing")
    if classification_provenance not in PROVENANCE_LABELS:
        raise ReviewFreezeError("predicate_provenance_invalid", "classification_provenance")
    relative, payload = _finding_bytes(repository, finding_path, ledger=ledger)
    events = _load_events(ledger)
    if any(
        event.get("lane_id") == lane_id
        and event.get("event_type") == "admit_finding"
        and event.get("finding_id") == finding_id
        for event in events
    ):
        raise ReviewFreezeError("finding_id_already_admitted", finding_id)
    freeze = _active_freeze(events, lane_id)
    reasons: list[str]
    source_match: dict[str, object] | None = None
    bound_review_result_id: str | None = None
    if freeze is None:
        disposition = "fix_now"
        reasons = ["lane_not_frozen"]
    elif _freeze_state(events, lane_id, str(freeze["freeze_id"])) != "frozen":
        raise ReviewFreezeError("freeze_not_admitting_state")
    elif not _is_event_committed(repository, ledger, freeze):
        disposition = "batch"
        reasons = ["freeze_marker_not_committed"]
    else:
        source_match = _source_match(repository, ledger, freeze)
        if not source_match["matches"]:
            disposition = "batch"
            reasons = ["freeze_source_moved", *list(source_match["reasons"])]
        else:
            if recomputed_cosmetic and classification_provenance == "recomputed":
                # Debt is permitted only by the local, rerun I001 predicate.  Do not let the
                # caller-supplied review baseline/roster become an unproved premise of the sole
                # permissive disposition.
                disposition = "debt"
                reasons = ["recomputed_cosmetic_classifier"]
            else:
                if review_result_id is not None:
                    _require_committed_review_result(
                        repository,
                        ledger,
                        events,
                        lane_id=lane_id,
                        freeze_id=str(freeze["freeze_id"]),
                        review_result_id=review_result_id,
                    )
                    bound_review_result_id = review_result_id
                disposition = "batch"
                reasons = ["classification_not_recomputed_cosmetic"]
    entry = _append_event(
        repository,
        ledger,
        {
            "event_type": "admit_finding",
            "lane_id": lane_id,
            "freeze_id": freeze.get("freeze_id") if freeze is not None else None,
            "review_result_id": bound_review_result_id,
            "finding_id": finding_id,
            "finding_ref": relative,
            "finding_sha256": _sha256(payload),
            "declared_classification": declared_classification,
            "classification_provenance": classification_provenance,
            "classifier": classifier,
            "disposition": disposition,
            "reasons": reasons,
            "recorded_at": recorded_at,
            "predicate_provenance": {
                "finding_identity": "recomputed",
                "finding_semantics": "consumer_asserted",
                "declared_classification": "consumer_asserted",
                "classification": classification_provenance,
                "freeze_source_match": "recomputed"
                if source_match is not None
                else "not_established",
                "review_round_binding": "recomputed"
                if bound_review_result_id is not None
                else "not_established",
                "batch_membership": "recomputed",
            },
        },
    )
    return {
        "disposition": disposition,
        "freeze_id": entry["freeze_id"],
        "finding_id": finding_id,
        "classification_provenance": classification_provenance,
        "reasons": reasons,
        "freeze_match": source_match["matches"] if source_match is not None else None,
        "event_sha256": entry["entry_sha256"],
    }


def disposition_finding(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    finding_id: str,
    finding_path: Path | str,
    declared_classification: str,
    classification_provenance: str,
    review_result_id: str | None,
    recorded_at: str,
) -> dict[str, object]:
    """Disposition a human/unknown finding; its cosmetic label can never create debt."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=False)
    return _record_disposition(
        repository=repository,
        ledger=ledger,
        lane_id=lane_id,
        finding_id=finding_id,
        finding_path=finding_path,
        declared_classification=declared_classification,
        classification_provenance=classification_provenance,
        review_result_id=review_result_id,
        recorded_at=recorded_at,
        recomputed_cosmetic=False,
        classifier=None,
    )


def _ruff_i001_payload(repository: Any, source_path: Path | str) -> bytes:
    """Recompute the sole v1 debt-capable cosmetic predicate: one safe Ruff I001 result."""

    source = _inside_worktree(repository, source_path, label="ruff_source", must_exist=True)
    relative = _relative(repository, source)
    result = subprocess.run(  # noqa: S603 - fixed Ruff invocation.
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--select",
            "I",
            "--output-format",
            "json",
            relative,
        ],
        cwd=repository.worktree,
        check=False,
        capture_output=True,
        shell=False,
    )
    if result.returncode not in {0, 1}:
        raise ReviewFreezeError("ruff_classifier_unavailable", str(result.returncode))
    try:
        diagnostics = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ReviewFreezeError("ruff_classifier_output_invalid") from exc
    candidates: list[dict[str, object]] = []
    if not isinstance(diagnostics, list):
        raise ReviewFreezeError("ruff_classifier_output_invalid")
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict) or diagnostic.get("code") != "I001":
            continue
        location = diagnostic.get("location")
        fix = diagnostic.get("fix")
        if (
            not isinstance(location, dict)
            or not isinstance(fix, dict)
            or fix.get("applicability") != "safe"
        ):
            continue
        candidates.append(
            {
                "code": "I001",
                "filename": relative,
                "message": str(diagnostic.get("message") or ""),
                "location": {"row": location.get("row"), "column": location.get("column")},
                "end_location": diagnostic.get("end_location"),
                "fix_applicability": "safe",
            }
        )
    if len(candidates) != 1:
        raise ReviewFreezeError("ruff_i001_not_uniquely_established", str(len(candidates)))
    return _canonical_json_bytes(
        {
            "schema_version": "policyos.review_freeze.ruff_i001.v1",
            "research_only": True,
            "authoritative_for": ["recomputed Ruff I001 cosmetic classification only"],
            "may_not_use_for": list(_AUTHORITY_DENIALS),
            "diagnostic": candidates[0],
        }
    )


def write_ruff_i001_finding(
    *,
    repo_root: Path | str,
    source_path: Path | str,
    output_path: Path | str,
) -> Path:
    """Write exact recomputed Ruff evidence into the fixed ignored review-evidence namespace."""

    repository = _repository(repo_root)
    output = _require_evidence_path(
        repository, output_path, label="ruff_finding_output", must_exist=False
    )
    atomic_write_bytes(output, _ruff_i001_payload(repository, source_path))
    return output


def admit_ruff_i001_finding(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    finding_path: Path | str,
    review_result_id: str | None,
    recorded_at: str,
) -> dict[str, object]:
    """Admit byte-bound I001 evidence, degrading any failed reconstruction to ``batch``."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=False)
    relative, supplied = _finding_bytes(repository, finding_path, ledger=ledger)
    recomputed = False
    provenance = "not_established"
    try:
        parsed = json.loads(supplied)
        source = parsed.get("diagnostic", {}).get("filename") if isinstance(parsed, dict) else None
        if not isinstance(source, str):
            raise ValueError("source missing")
        recomputed = supplied == _ruff_i001_payload(repository, source)
        provenance = "recomputed" if recomputed else "not_established"
    except (ReviewFreezeError, ValueError, json.JSONDecodeError):
        recomputed = False
    return _record_disposition(
        repository=repository,
        ledger=ledger,
        lane_id=lane_id,
        finding_id=f"ruff-i001:{hashlib.sha256(supplied).hexdigest()}",
        finding_path=repository.worktree / relative,
        declared_classification="cosmetic",
        classification_provenance=provenance,
        review_result_id=review_result_id,
        recorded_at=recorded_at,
        recomputed_cosmetic=recomputed,
        classifier="ruff_i001_v1" if recomputed else None,
    )


def _package_output(
    repository: Any,
    ledger: Path,
    output_path: Path | str,
    *,
    label: str,
    extra_aliases: Sequence[Path] = (),
) -> Path:
    """Resolve one package/checklist destination without letting it overwrite another input."""

    return _require_evidence_path(
        repository,
        output_path,
        label=label,
        must_exist=False,
        aliases=(ledger, *extra_aliases),
    )


def _build_package(
    *,
    repository: Any,
    ledger: Path,
    lane_id: str,
    freeze_id: str,
    base_revision: str,
    head_revision: str,
    package_output: Path | str,
    package_kind: str,
    checklist: Path | None = None,
    member_bindings: Sequence[dict[str, str]] = (),
) -> dict[str, object]:
    """Delegate rendering to the canonical packager and persist only its byte-bound bridge."""

    events = _load_events(ledger)
    freeze = _require_active_frozen(
        repository,
        ledger,
        events,
        lane_id=lane_id,
        freeze_id=freeze_id,
        require_committed=True,
    )
    expected_head = str(freeze["source_identity"]["source_commit"])
    resolved_head = _resolve_commit(repository, head_revision, label="head_revision")
    resolved_base = _resolve_commit(repository, base_revision, label="base_revision")
    if resolved_head != expected_head:
        raise ReviewFreezeError("review_package_head_not_frozen_source")
    if package_kind == "full":
        expected_base = freeze.get("review_base_commit")
        if not isinstance(expected_base, str) or resolved_base != expected_base:
            raise ReviewFreezeError("full_review_base_not_frozen")
    elif package_kind == "delta":
        predecessor_id = freeze.get("supersedes_freeze_id")
        predecessor = (
            _freeze_by_id(events, predecessor_id) if isinstance(predecessor_id, str) else None
        )
        expected_base = (
            predecessor.get("source_identity", {}).get("source_commit")
            if isinstance(predecessor, dict)
            and isinstance(predecessor.get("source_identity"), dict)
            else None
        )
        if not isinstance(expected_base, str) or resolved_base != expected_base:
            raise ReviewFreezeError("delta_review_base_not_predecessor_source")
    else:
        raise ReviewFreezeError("review_package_kind_invalid", package_kind)
    if resolved_base == resolved_head:
        raise ReviewFreezeError("review_package_range_empty")
    output = _package_output(
        repository,
        ledger,
        package_output,
        label="package_output",
        extra_aliases=((checklist,) if checklist else ()),
    )
    if checklist is not None and output == checklist:
        raise ReviewFreezeError("package_output_aliases_checklist")
    try:
        package = review_package.build_review_package(
            base_revision=resolved_base,
            head_revision=resolved_head,
            output_path=output,
            prior_findings_path=checklist,
            invocation_cwd=repository.worktree,
        )
    except (OSError, ReviewPackageError) as exc:
        raise ReviewFreezeError("review_package_failed", str(exc)) from exc
    package_id = f"{lane_id}:package:{len(events) + 1}"
    entry = _append_event(
        repository,
        ledger,
        {
            "event_type": "review_package",
            "lane_id": lane_id,
            "freeze_id": freeze_id,
            "review_package_id": package_id,
            "package_kind": package_kind,
            "package_ref": _relative(repository, output),
            "package_sha256": _sha256(package),
            "base_commit": resolved_base,
            "head_commit": resolved_head,
            "checklist_ref": _relative(repository, checklist) if checklist is not None else None,
            "checklist_sha256": _sha256(checklist.read_bytes()) if checklist is not None else None,
            "member_bindings": list(member_bindings),
            "predicate_provenance": {
                "current_source_match": "recomputed",
                "package_byte_binding": "recomputed",
                "checklist_byte_binding": "recomputed"
                if checklist is not None
                else "not_established",
                "batch_membership": "recomputed" if checklist is not None else "not_established",
                "reviewer_independence": "institutionally_supplied",
            },
        },
    )
    return {
        "review_package_id": package_id,
        "package_sha256": entry["package_sha256"],
        "head_commit": resolved_head,
        "package_kind": package_kind,
        "event_sha256": entry["entry_sha256"],
    }


def build_full_review_package(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    freeze_id: str,
    base_revision: str,
    head_revision: str,
    package_output: Path | str,
) -> dict[str, object]:
    """Build a full review package through the existing canonical packager."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=True)
    return _build_package(
        repository=repository,
        ledger=ledger,
        lane_id=lane_id,
        freeze_id=freeze_id,
        base_revision=base_revision,
        head_revision=head_revision,
        package_output=package_output,
        package_kind="full",
    )


def record_review_result(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    freeze_id: str,
    review_package_id: str,
    reviewer_id: str,
    result_path: Path | str,
    recorded_at: str,
) -> dict[str, object]:
    """Content-bind opaque reviewer output to a committed package for the exact frozen source."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=True)
    events = _load_events(ledger)
    _require_active_frozen(
        repository, ledger, events, lane_id=lane_id, freeze_id=freeze_id, require_committed=True
    )
    package = _review_package_by_id(events, review_package_id)
    if (
        package is None
        or package.get("lane_id") != lane_id
        or package.get("freeze_id") != freeze_id
    ):
        raise ReviewFreezeError("review_package_not_for_active_freeze")
    if (
        package.get("head_commit")
        != _freeze_by_id(events, freeze_id)["source_identity"]["source_commit"]
    ):
        raise ReviewFreezeError("review_package_head_not_frozen_source")
    committed = _committed_events(repository, ledger, require_live_exact=True)
    if not any(event.get("entry_sha256") == package.get("entry_sha256") for event in committed):
        raise ReviewFreezeError("review_package_not_committed")
    _bound_package_bytes(repository, ledger, package)
    freeze = _freeze_by_id(events, freeze_id)
    required_reviews = freeze.get("required_reviews") if isinstance(freeze, dict) else None
    if not isinstance(required_reviews, list) or reviewer_id not in required_reviews:
        raise ReviewFreezeError("reviewer_not_in_required_roster", reviewer_id)
    if any(
        event.get("freeze_id") == freeze_id and event.get("reviewer_id") == reviewer_id
        for event in events
        if event.get("event_type") == "review_result"
    ):
        raise ReviewFreezeError("reviewer_result_already_recorded", reviewer_id)
    result = _require_evidence_path(
        repository, result_path, label="review_result", must_exist=True, aliases=(ledger,)
    )
    payload = result.read_bytes()
    if not payload or not payload.strip():
        raise ReviewFreezeError("review_result_empty")
    result_id = f"{lane_id}:result:{len(events) + 1}"
    entry = _append_event(
        repository,
        ledger,
        {
            "event_type": "review_result",
            "lane_id": lane_id,
            "freeze_id": freeze_id,
            "review_result_id": result_id,
            "review_package_id": review_package_id,
            "reviewer_id": reviewer_id,
            "result_ref": _relative(repository, result),
            "result_sha256": _sha256(payload),
            "recorded_at": recorded_at,
            "predicate_provenance": {
                "review_package_binding": "recomputed",
                "review_result_byte_binding": "recomputed",
                "reviewer_independence": "institutionally_supplied",
                "reviewer_roster_membership": "recomputed",
                "review_completeness": "institutionally_supplied",
            },
        },
    )
    return {
        "review_result_id": result_id,
        "result_sha256": entry["result_sha256"],
        "event_sha256": entry["entry_sha256"],
    }


def _checklist_bytes(
    repository: Any, *, lane_id: str, freeze_id: str, members: Sequence[dict[str, object]]
) -> bytes:
    """Render a nonempty opaque checklist whose member raw bytes and digests remain exact."""

    if not members:
        raise ReviewFreezeError("batch_empty")
    header = (
        CHECKLIST_MAGIC
        + b"research_only=true\n"
        + b"authoritative_for=E11_batch_checklist_raw_byte_handoff_only\n"
        + b"may_not_use_for=implementation_authorization,capability_claims,owner_appointment,automatic_plan_amendment\n"
        + f"schema_version={SCHEMA_VERSION}\n".encode("ascii")
        + f"lane_id={lane_id}\n".encode()
        + f"freeze_id={freeze_id}\n".encode()
        + f"member_count={len(members)}\n\n".encode("ascii")
    )
    chunks = [header]
    for member in sorted(members, key=lambda event: str(event["finding_id"])):
        reference = member.get("finding_ref")
        digest = member.get("finding_sha256")
        if not isinstance(reference, str) or not isinstance(digest, str):
            raise ReviewFreezeError("batch_member_binding_missing")
        finding = _require_evidence_path(
            repository, reference, label="batch_finding", must_exist=True
        )
        payload = finding.read_bytes()
        if not payload or not payload.strip():
            raise ReviewFreezeError("batch_finding_empty", reference)
        if _sha256(payload) != digest:
            raise ReviewFreezeError("batch_finding_digest_drift", reference)
        chunks.append(
            (
                "section=finding\n"
                f"finding_id={member['finding_id']}\n"
                f"origin_freeze_id={member['freeze_id']}\n"
                f"finding_ref={reference}\n"
                f"finding_sha256={digest}\n"
                f"length={len(payload)}\n\n"
            ).encode()
        )
        chunks.extend((payload, b"\nend_section\n"))
    chunks.append(b"end_checklist\n")
    return b"".join(chunks)


def export_batch_checklist(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    freeze_id: str,
    output_path: Path | str,
) -> bytes:
    """Export an exact carried batch for a committed active repair boundary."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=True)
    events = _load_events(ledger)
    _require_active_frozen(
        repository, ledger, events, lane_id=lane_id, freeze_id=freeze_id, require_committed=True
    )
    output = _package_output(repository, ledger, output_path, label="checklist_output")
    members = _open_members(events, lane_id, active_freeze_id=freeze_id)
    payload = _checklist_bytes(repository, lane_id=lane_id, freeze_id=freeze_id, members=members)
    atomic_write_bytes(output, payload)
    return payload


def build_batch_delta_review_package(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    freeze_id: str,
    checklist_output: Path | str,
    base_revision: str,
    head_revision: str,
    package_output: Path | str,
) -> dict[str, object]:
    """Carry every unresolved predecessor batch member into a canonical delta package once."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=True)
    events = _load_events(ledger)
    _require_active_frozen(
        repository, ledger, events, lane_id=lane_id, freeze_id=freeze_id, require_committed=True
    )
    checklist = _package_output(repository, ledger, checklist_output, label="checklist_output")
    package_path = _package_output(
        repository, ledger, package_output, label="package_output", extra_aliases=(checklist,)
    )
    members = _open_members(events, lane_id, active_freeze_id=freeze_id)
    checklist_bytes = _checklist_bytes(
        repository, lane_id=lane_id, freeze_id=freeze_id, members=members
    )
    atomic_write_bytes(checklist, checklist_bytes)
    bindings = [
        {
            "finding_id": str(member["finding_id"]),
            "finding_sha256": str(member["finding_sha256"]),
            "origin_freeze_id": str(member["freeze_id"]),
        }
        for member in sorted(members, key=lambda event: str(event["finding_id"]))
    ]
    return _build_package(
        repository=repository,
        ledger=ledger,
        lane_id=lane_id,
        freeze_id=freeze_id,
        base_revision=base_revision,
        head_revision=head_revision,
        package_output=package_path,
        package_kind="delta",
        checklist=checklist,
        member_bindings=bindings,
    )


def _resolution_evidence(
    repository: Any,
    resolution_path: Path | str,
    *,
    ledger: Path,
    finding_id: str,
    result: dict[str, object],
    repair_freeze_id: str,
) -> tuple[str, bytes]:
    """Validate the structural bindings in an institutional repair-acceptance witness."""

    path = _require_evidence_path(
        repository, resolution_path, label="resolution", must_exist=True, aliases=(ledger,)
    )
    payload = path.read_bytes()
    try:
        evidence = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ReviewFreezeError("resolution_evidence_invalid") from exc
    expected = {
        "schema_version": "policyos.review_freeze.resolution.v1",
        "finding_id": finding_id,
        "repair_freeze_id": repair_freeze_id,
        "review_result_sha256": result.get("result_sha256"),
        "accepted": True,
    }
    if not isinstance(evidence, dict) or any(
        evidence.get(key) != value for key, value in expected.items()
    ):
        raise ReviewFreezeError("resolution_evidence_invalid")
    return _relative(repository, path), payload


def resolve_batch_member(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    finding_id: str,
    review_result_id: str,
    resolution_path: Path | str,
    recorded_at: str,
) -> dict[str, object]:
    """Resolve one member only through a committed successor delta-review result and witness."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=True)
    events = _load_events(ledger)
    active = _active_freeze(events, lane_id)
    if active is None:
        raise ReviewFreezeError("freeze_not_active")
    active_id = str(active["freeze_id"])
    _require_active_frozen(
        repository, ledger, events, lane_id=lane_id, freeze_id=active_id, require_committed=True
    )
    member = next(
        (
            item
            for item in _open_members(events, lane_id, active_freeze_id=active_id)
            if item.get("finding_id") == finding_id
        ),
        None,
    )
    if member is None:
        raise ReviewFreezeError("batch_member_not_open", finding_id)
    if member.get("freeze_id") == active_id:
        raise ReviewFreezeError("resolution_requires_repaired_successor")
    result = _require_committed_review_result(
        repository,
        ledger,
        events,
        lane_id=lane_id,
        freeze_id=active_id,
        review_result_id=review_result_id,
    )
    package = _review_package_by_id(events, str(result["review_package_id"]))
    bindings = package.get("member_bindings") if package is not None else None
    if package is None or package.get("package_kind") != "delta" or not isinstance(bindings, list):
        raise ReviewFreezeError("resolution_requires_delta_review")
    if not any(
        isinstance(binding, dict)
        and binding.get("finding_id") == finding_id
        and binding.get("finding_sha256") == member.get("finding_sha256")
        and binding.get("origin_freeze_id") == member.get("freeze_id")
        for binding in bindings
    ):
        raise ReviewFreezeError("resolution_member_not_carried_by_delta")
    relative, payload = _resolution_evidence(
        repository,
        resolution_path,
        ledger=ledger,
        finding_id=finding_id,
        result=result,
        repair_freeze_id=active_id,
    )
    return _append_event(
        repository,
        ledger,
        {
            "event_type": "resolve_member",
            "lane_id": lane_id,
            "freeze_id": active_id,
            "finding_id": finding_id,
            "review_result_id": review_result_id,
            "resolution_ref": relative,
            "resolution_sha256": _sha256(payload),
            "recorded_at": recorded_at,
            "predicate_provenance": {
                "batch_membership": "recomputed",
                "delta_review_member_binding": "recomputed",
                "resolution_evidence_binding": "recomputed",
                "repair_acceptance": "institutionally_supplied",
            },
        },
    )


def record_replay(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    freeze_id: str,
    receipt_path: Path | str,
    recorded_at: str,
) -> dict[str, object]:
    """Record a replay only after committed review coverage and every carried blocker close."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=True)
    events = _load_events(ledger)
    _require_active_frozen(
        repository, ledger, events, lane_id=lane_id, freeze_id=freeze_id, require_committed=True
    )
    committed = _committed_events(repository, ledger, require_live_exact=True)
    result_events = [
        event
        for event in committed
        if event.get("event_type") == "review_result"
        and event.get("lane_id") == lane_id
        and event.get("freeze_id") == freeze_id
    ]
    freeze = _freeze_by_id(committed, freeze_id)
    required_reviews = freeze.get("required_reviews") if isinstance(freeze, dict) else None
    completed_reviews = {
        event.get("reviewer_id")
        for event in result_events
        if isinstance(event.get("reviewer_id"), str)
    }
    if (
        not isinstance(required_reviews, list)
        or not required_reviews
        or not set(required_reviews) <= completed_reviews
    ):
        raise ReviewFreezeError("review_round_missing")
    if isinstance(freeze, dict) and freeze.get("supersedes_freeze_id") is not None:
        delta_reviewers = _reviewers_for_round(
            committed,
            lane_id=lane_id,
            freeze_id=freeze_id,
            require_delta=True,
        )
        if not set(required_reviews) <= delta_reviewers:
            raise ReviewFreezeError("successor_delta_review_round_missing")
    open_members = _open_members(events, lane_id, active_freeze_id=freeze_id)
    if open_members:
        raise ReviewFreezeError(
            "open_batch_members", ", ".join(str(member["finding_id"]) for member in open_members)
        )
    receipt = _require_artifact_receipt_path(repository, receipt_path, aliases=(ledger,))
    payload = receipt.read_bytes()
    if not payload or not payload.strip():
        raise ReviewFreezeError("receipt_empty")
    receipt_ref = _relative(repository, receipt)
    receipt_sha256 = _sha256(payload)
    _bound_receipt_bytes(
        repository,
        ledger,
        reference=receipt_ref,
        expected_sha256=receipt_sha256,
    )
    return _append_event(
        repository,
        ledger,
        {
            "event_type": "replay_recorded",
            "lane_id": lane_id,
            "freeze_id": freeze_id,
            "state": "replayed",
            "state_scope": "e11_scheduling_ledger_only",
            "state_claim_grade": _DEGRADED_REPLAY_CLAIM,
            "state_semantic_validity": "not_established",
            "receipt_chain_id": freeze.get("receipt_chain_id"),
            "receipt_ref": receipt_ref,
            "receipt_sha256": receipt_sha256,
            "recorded_at": recorded_at,
            "predicate_provenance": {
                "current_source_match": "recomputed",
                "review_round_presence": "recomputed",
                "review_roster_coverage": "recomputed",
                "batch_membership": "recomputed",
                "receipt_byte_binding": "recomputed",
                "receipt_chain_membership": "consumer_asserted",
                "reviewer_independence": "institutionally_supplied",
                "receipt_semantic_validity": "not_established",
            },
        },
    )


def close_lane(
    *,
    repo_root: Path | str,
    ledger_path: Path | str,
    lane_id: str,
    freeze_id: str,
    recorded_at: str,
) -> dict[str, object]:
    """Close a replayed boundary only after its replay record is itself committed."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=True)
    live_events = _load_events(ledger)
    live_active = _active_freeze(live_events, lane_id)
    if live_active is None or live_active.get("freeze_id") != freeze_id:
        raise ReviewFreezeError("freeze_not_active", freeze_id)
    if _freeze_state(live_events, lane_id, freeze_id) != "replayed":
        raise ReviewFreezeError("freeze_not_closed_after_replay")
    live_source_match = _source_match(repository, ledger, live_active)
    if not live_source_match["matches"]:
        raise ReviewFreezeError("freeze_source_moved", ", ".join(live_source_match["reasons"]))
    head_blob = _head_ledger_blob(repository, ledger)
    if head_blob is None or _read_bytes(ledger) != head_blob:
        raise ReviewFreezeError("replay_event_not_committed")
    events = _committed_events(repository, ledger, require_live_exact=True)
    active = _active_freeze(events, lane_id)
    if active is None or active.get("freeze_id") != freeze_id:
        raise ReviewFreezeError("freeze_not_active", freeze_id)
    if _freeze_state(events, lane_id, freeze_id) != "replayed":
        raise ReviewFreezeError("freeze_not_closed_after_replay")
    if _open_members(events, lane_id, active_freeze_id=freeze_id):
        raise ReviewFreezeError("open_batch_members")
    source_match = _source_match(repository, ledger, active)
    if not source_match["matches"]:
        raise ReviewFreezeError("freeze_source_moved", ", ".join(source_match["reasons"]))
    return _append_event(
        repository,
        ledger,
        {
            "event_type": "closed",
            "lane_id": lane_id,
            "freeze_id": freeze_id,
            "state": "closed",
            "state_scope": "e11_scheduling_ledger_only",
            "state_claim_grade": _DEGRADED_REPLAY_CLAIM,
            "state_semantic_validity": "not_established",
            "recorded_at": recorded_at,
            "predicate_provenance": {
                "replay_record_presence": "recomputed",
                "batch_membership": "recomputed",
                "ledger_hash_chain": "recomputed",
                "receipt_chain_membership": "consumer_asserted",
                "reviewer_independence": "institutionally_supplied",
                "receipt_semantic_validity": "not_established",
            },
        },
    )


def _semantic_issue(
    event: dict[str, object], code: str, detail: str | None = None
) -> dict[str, object]:
    """Build one stable, event-local semantic validation receipt."""

    issue: dict[str, object] = {
        "code": f"ledger_semantic_{code}",
        "sequence": event.get("sequence"),
    }
    if detail is not None:
        issue["detail"] = detail
    return issue


def _semantic_open_members(state: dict[str, object], freeze_id: str) -> list[dict[str, object]]:
    """Return unresolved batch admissions carried into one freeze's explicit lineage."""

    freezes = state["freezes"]
    if not isinstance(freezes, dict):
        return []
    lineage: set[str] = set()
    current: str | None = freeze_id
    while current is not None and current not in lineage:
        lineage.add(current)
        freeze = freezes.get(current)
        current = (
            freeze.get("supersedes_freeze_id")
            if isinstance(freeze, dict) and isinstance(freeze.get("supersedes_freeze_id"), str)
            else None
        )
    members = state["batch_members"]
    if not isinstance(members, dict):
        return []
    return [
        member
        for member in members.values()
        if isinstance(member, dict) and member.get("freeze_id") in lineage
    ]


def _semantic_package_member_bindings(
    package: dict[str, object], members: Sequence[dict[str, object]]
) -> bool:
    """Compare delta bindings to the exact carried, unresolved batch set."""

    bindings = package.get("member_bindings")
    if not isinstance(bindings, list):
        return False
    expected = sorted(
        (
            str(member.get("finding_id")),
            str(member.get("finding_sha256")),
            str(member.get("freeze_id")),
        )
        for member in members
    )
    observed: list[tuple[str, str, str]] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            return False
        finding_id = binding.get("finding_id")
        finding_sha256 = binding.get("finding_sha256")
        origin_freeze_id = binding.get("origin_freeze_id")
        if not all(
            isinstance(value, str) for value in (finding_id, finding_sha256, origin_freeze_id)
        ):
            return False
        observed.append((finding_id, finding_sha256, origin_freeze_id))
    return sorted(observed) == expected


def _semantic_delta_checklist_matches(
    repository: Any,
    ledger: Path,
    package: dict[str, object],
    *,
    lane_id: str,
    freeze_id: str,
    members: Sequence[dict[str, object]],
) -> bool:
    """Reconstruct the opaque delta checklist from the carried batch members.

    The existing packager binds opaque prior-findings bytes but deliberately does not parse them.
    E11 owns the member-to-checklist bridge, so its semantic transcript must prove that the exact
    bytes supplied to the packager are the checklist generated from this batch—not merely trust a
    self-declared member list beside arbitrary opaque input.
    """

    try:
        checklist = _bound_evidence_bytes(
            repository,
            ledger,
            reference=package.get("checklist_ref"),
            expected_sha256=package.get("checklist_sha256"),
            label="checklist",
        )
        expected = _checklist_bytes(
            repository, lane_id=lane_id, freeze_id=freeze_id, members=members
        )
    except ReviewFreezeError:
        return False
    return checklist == expected


def _reviewers_for_round(
    events: Iterable[dict[str, object]],
    *,
    lane_id: str,
    freeze_id: str,
    require_delta: bool,
) -> set[str]:
    """Return reviewers whose committed result consumed the required package kind."""

    package_by_id = {
        event.get("review_package_id"): event
        for event in events
        if event.get("event_type") == "review_package"
        and event.get("lane_id") == lane_id
        and event.get("freeze_id") == freeze_id
        and isinstance(event.get("review_package_id"), str)
    }
    reviewers: set[str] = set()
    for event in events:
        if (
            event.get("event_type") != "review_result"
            or event.get("lane_id") != lane_id
            or event.get("freeze_id") != freeze_id
        ):
            continue
        reviewer = event.get("reviewer_id")
        package_id = event.get("review_package_id")
        package = package_by_id.get(package_id)
        if not isinstance(reviewer, str) or not isinstance(package, dict):
            continue
        if require_delta and package.get("package_kind") != "delta":
            continue
        reviewers.add(reviewer)
    return reviewers


def _semantic_debt_is_recomputed(repository: Any, ledger: Path, event: dict[str, object]) -> bool:
    """Re-run the sole debt-capable classifier instead of trusting a ledger declaration."""

    if (
        event.get("classifier") != "ruff_i001_v1"
        or event.get("classification_provenance") != "recomputed"
        or event.get("declared_classification") != "cosmetic"
    ):
        return False
    try:
        payload = _bound_evidence_bytes(
            repository,
            ledger,
            reference=event.get("finding_ref"),
            expected_sha256=event.get("finding_sha256"),
            label="finding",
        )
        parsed = json.loads(payload)
        diagnostic = parsed.get("diagnostic") if isinstance(parsed, dict) else None
        source = diagnostic.get("filename") if isinstance(diagnostic, dict) else None
        return isinstance(source, str) and payload == _ruff_i001_payload(repository, source)
    except (ReviewFreezeError, ValueError, json.JSONDecodeError):
        return False


def _semantic_transcript_issues(
    repository: Any, ledger: Path, events: Sequence[dict[str, object]]
) -> list[dict[str, object]]:
    """Replay the ledger as a state machine, rejecting self-consistent but unreachable events.

    A hash chain establishes byte continuity, not that an admission was produced by the gate.  This
    validator reconstructs each transition from the preceding validated state and rebinds every
    raw input that a later transition consumes.  Institutional review facts remain explicitly
    degraded scheduling evidence; they never create the ``debt`` disposition.
    """

    issues: list[dict[str, object]] = []
    lanes: dict[str, dict[str, object]] = {}
    freeze_ids: set[str] = set()
    package_ids: set[str] = set()
    result_ids: set[str] = set()

    def state_for(lane_id: str) -> dict[str, object]:
        return lanes.setdefault(
            lane_id,
            {
                "opening": None,
                "active_freeze_id": None,
                "freeze_status": {},
                "freezes": {},
                "packages": {},
                "results": {},
                "reviewers": {},
                "finding_ids": set(),
                "batch_members": {},
            },
        )

    for event in events:
        lane_id = event.get("lane_id")
        if not isinstance(lane_id, str) or not lane_id:
            continue
        if not _ledger_matches_lane(repository, ledger, lane_id):
            issues.append(_semantic_issue(event, "lane_ledger_path_not_canonical"))
            continue
        expected_authority = _authority_fields(lane_id)
        if any(event.get(key) != value for key, value in expected_authority.items()):
            issues.append(_semantic_issue(event, "authority_boundary_invalid"))
            continue
        expected_provenance = _expected_predicate_provenance(event)
        if expected_provenance is None or event.get("predicate_provenance") != expected_provenance:
            issues.append(_semantic_issue(event, "predicate_provenance_invalid"))
            continue
        state = state_for(lane_id)
        event_type = event.get("event_type")
        if event_type == "open":
            roster = event.get("required_reviews")
            if state["opening"] is not None:
                issues.append(_semantic_issue(event, "open_duplicate"))
                continue
            if (
                not isinstance(event.get("receipt_chain_id"), str)
                or not str(event.get("receipt_chain_id")).strip()
                or not isinstance(roster, list)
                or not roster
                or any(not isinstance(item, str) or not item.strip() for item in roster)
                or roster != sorted(set(roster))
            ):
                issues.append(_semantic_issue(event, "open_fields_invalid"))
                continue
            review_base = event.get("review_base_commit")
            opening_head = event.get("opening_head_commit")
            if not isinstance(review_base, str) or not isinstance(opening_head, str):
                issues.append(_semantic_issue(event, "open_review_base_missing"))
                continue
            try:
                resolved_base = _resolve_commit(repository, review_base, label="review_base")
                resolved_head = _resolve_commit(repository, opening_head, label="opening_head")
                _require_review_base_ancestor(repository, resolved_base, resolved_head)
            except ReviewFreezeError as exc:
                issues.append(_semantic_issue(event, exc.code))
                continue
            if (
                resolved_base != review_base
                or resolved_head != opening_head
                or resolved_base == resolved_head
            ):
                issues.append(_semantic_issue(event, "open_review_base_invalid"))
                continue
            state["opening"] = event
            continue

        if event_type == "freeze":
            opening = state["opening"]
            freeze_id = event.get("freeze_id")
            if not isinstance(opening, dict):
                issues.append(_semantic_issue(event, "freeze_without_open"))
                continue
            if not isinstance(freeze_id, str) or not freeze_id or freeze_id in freeze_ids:
                issues.append(_semantic_issue(event, "freeze_id_invalid"))
                continue
            if (
                event.get("state") != "frozen"
                or event.get("open_event_sha256") != opening.get("entry_sha256")
                or event.get("required_reviews") != opening.get("required_reviews")
                or event.get("receipt_chain_id") != opening.get("receipt_chain_id")
                or event.get("review_base_commit") != opening.get("review_base_commit")
            ):
                issues.append(_semantic_issue(event, "freeze_open_binding_invalid"))
                continue
            identity_issues = _source_identity_issues(repository, ledger, event)
            if identity_issues:
                issues.extend(_semantic_issue(event, code) for code in identity_issues)
                continue
            try:
                _require_review_base_ancestor(
                    repository,
                    str(event.get("review_base_commit") or ""),
                    str(event["source_identity"]["source_commit"]),
                )
            except (KeyError, ReviewFreezeError) as exc:
                issues.append(
                    _semantic_issue(event, getattr(exc, "code", "freeze_review_base_invalid"))
                )
                continue
            if event.get("review_base_commit") == event["source_identity"]["source_commit"]:
                issues.append(_semantic_issue(event, "freeze_review_base_empty"))
                continue
            active_id = state["active_freeze_id"]
            if active_id is None:
                if event.get("supersedes_freeze_id") is not None:
                    issues.append(_semantic_issue(event, "freeze_unexpected_supersession"))
                    continue
            else:
                active = state["freezes"].get(active_id)
                if (
                    event.get("supersedes_freeze_id") != active_id
                    or state["freeze_status"].get(active_id) != "frozen"
                    or not _semantic_open_members(state, str(active_id))
                    or not isinstance(active, dict)
                ):
                    issues.append(_semantic_issue(event, "freeze_supersession_invalid"))
                    continue
                previous_identity = active.get("source_identity")
                current_identity = event.get("source_identity")
                if (
                    not isinstance(previous_identity, dict)
                    or not isinstance(current_identity, dict)
                    or previous_identity.get("fingerprint") == current_identity.get("fingerprint")
                ):
                    issues.append(_semantic_issue(event, "freeze_source_repair_missing"))
                    continue
            freeze_ids.add(freeze_id)
            state["freezes"][freeze_id] = event
            state["freeze_status"][freeze_id] = "frozen"
            state["active_freeze_id"] = freeze_id
            continue

        active_id = state["active_freeze_id"]
        active = state["freezes"].get(active_id) if isinstance(active_id, str) else None
        if event_type in {
            "review_package",
            "review_result",
            "admit_finding",
            "resolve_member",
            "replay_recorded",
            "closed",
        } and not isinstance(active, dict):
            if event_type == "admit_finding" and event.get("disposition") == "fix_now":
                if event.get("freeze_id") is not None or event.get("review_result_id") is not None:
                    issues.append(_semantic_issue(event, "unfrozen_fix_now_binding_invalid"))
                continue
            issues.append(_semantic_issue(event, f"{event_type}_without_active_freeze"))
            continue

        if event_type == "review_package":
            package_id = event.get("review_package_id")
            package_kind = event.get("package_kind")
            if (
                event.get("freeze_id") != active_id
                or state["freeze_status"].get(active_id) != "frozen"
                or not isinstance(package_id, str)
                or not package_id
                or package_id in package_ids
                or event.get("head_commit") != active["source_identity"]["source_commit"]
            ):
                issues.append(_semantic_issue(event, "review_package_binding_invalid"))
                continue
            if package_kind == "full":
                expected_base = active.get("review_base_commit")
            elif package_kind == "delta":
                predecessor_id = active.get("supersedes_freeze_id")
                predecessor = (
                    state["freezes"].get(predecessor_id)
                    if isinstance(predecessor_id, str)
                    else None
                )
                predecessor_identity = (
                    predecessor.get("source_identity") if isinstance(predecessor, dict) else None
                )
                expected_base = (
                    predecessor_identity.get("source_commit")
                    if isinstance(predecessor_identity, dict)
                    else None
                )
            else:
                expected_base = None
            if (
                not isinstance(expected_base, str)
                or event.get("base_commit") != expected_base
                or event.get("base_commit") == event.get("head_commit")
            ):
                issues.append(_semantic_issue(event, "review_package_base_invalid"))
                continue
            try:
                _bound_package_bytes(repository, ledger, event)
            except ReviewFreezeError as exc:
                issues.append(_semantic_issue(event, exc.code))
                continue
            members = _semantic_open_members(state, str(active_id))
            if package_kind == "delta":
                if not members or not _semantic_package_member_bindings(event, members):
                    issues.append(_semantic_issue(event, "delta_member_bindings_invalid"))
                    continue
                if not _semantic_delta_checklist_matches(
                    repository,
                    ledger,
                    event,
                    lane_id=lane_id,
                    freeze_id=str(active_id),
                    members=members,
                ):
                    issues.append(_semantic_issue(event, "delta_checklist_not_canonical"))
                    continue
            elif package_kind == "full":
                if event.get("member_bindings") not in ([], None):
                    issues.append(_semantic_issue(event, "full_member_bindings_invalid"))
                    continue
            else:
                issues.append(_semantic_issue(event, "review_package_kind_invalid"))
                continue
            package_ids.add(package_id)
            state["packages"][package_id] = event
            continue

        if event_type == "review_result":
            package_id = event.get("review_package_id")
            result_id = event.get("review_result_id")
            reviewer_id = event.get("reviewer_id")
            package = state["packages"].get(package_id) if isinstance(package_id, str) else None
            roster = active.get("required_reviews")
            reviewers = state["reviewers"].setdefault(str(active_id), set())
            if (
                event.get("freeze_id") != active_id
                or state["freeze_status"].get(active_id) != "frozen"
                or not isinstance(package, dict)
                or package.get("freeze_id") != active_id
                or not isinstance(result_id, str)
                or not result_id
                or result_id in result_ids
                or not isinstance(reviewer_id, str)
                or not isinstance(roster, list)
                or reviewer_id not in roster
                or reviewer_id in reviewers
            ):
                issues.append(_semantic_issue(event, "review_result_binding_invalid"))
                continue
            try:
                _bound_package_bytes(repository, ledger, package)
                _bound_review_result_bytes(repository, ledger, event)
            except ReviewFreezeError as exc:
                issues.append(_semantic_issue(event, exc.code))
                continue
            result_ids.add(result_id)
            state["results"][result_id] = event
            reviewers.add(reviewer_id)
            continue

        if event_type == "admit_finding":
            finding_id = event.get("finding_id")
            if (
                not isinstance(finding_id, str)
                or not finding_id
                or finding_id in state["finding_ids"]
            ):
                issues.append(_semantic_issue(event, "finding_id_invalid"))
                continue
            try:
                _bound_evidence_bytes(
                    repository,
                    ledger,
                    reference=event.get("finding_ref"),
                    expected_sha256=event.get("finding_sha256"),
                    label="finding",
                )
            except ReviewFreezeError as exc:
                issues.append(_semantic_issue(event, exc.code))
                continue
            disposition = event.get("disposition")
            if (
                event.get("freeze_id") != active_id
                or state["freeze_status"].get(active_id) != "frozen"
                or disposition not in {"batch", "debt"}
            ):
                issues.append(_semantic_issue(event, "frozen_disposition_invalid"))
                continue
            result_id = event.get("review_result_id")
            result = state["results"].get(result_id) if isinstance(result_id, str) else None
            if disposition == "debt":
                source_match = _source_match(repository, ledger, active)
                if (
                    result_id is not None
                    or not source_match["matches"]
                    or not _semantic_debt_is_recomputed(repository, ledger, event)
                ):
                    issues.append(_semantic_issue(event, "debt_not_recomputed"))
                    continue
                state["finding_ids"].add(finding_id)
                continue
            if result_id is None:
                # A source-moved or not-yet-committed boundary may still conservatively record a
                # blocker.  It cannot become debt or clear a replay without a later bound result.
                state["finding_ids"].add(finding_id)
                state["batch_members"][finding_id] = event
                continue
            if not isinstance(result, dict) or result.get("freeze_id") != active_id:
                issues.append(_semantic_issue(event, "finding_review_result_missing"))
                continue
            try:
                _bound_review_result_bytes(repository, ledger, result)
            except ReviewFreezeError as exc:
                issues.append(_semantic_issue(event, exc.code))
                continue
            state["finding_ids"].add(finding_id)
            state["batch_members"][finding_id] = event
            continue

        if event_type == "resolve_member":
            finding_id = event.get("finding_id")
            result_id = event.get("review_result_id")
            member = state["batch_members"].get(finding_id) if isinstance(finding_id, str) else None
            result = state["results"].get(result_id) if isinstance(result_id, str) else None
            package = (
                state["packages"].get(result.get("review_package_id"))
                if isinstance(result, dict) and isinstance(result.get("review_package_id"), str)
                else None
            )
            if (
                event.get("freeze_id") != active_id
                or state["freeze_status"].get(active_id) != "frozen"
                or not isinstance(member, dict)
                or member.get("freeze_id") == active_id
                or not isinstance(result, dict)
                or result.get("freeze_id") != active_id
                or not isinstance(package, dict)
                or package.get("package_kind") != "delta"
            ):
                issues.append(_semantic_issue(event, "resolution_binding_invalid"))
                continue
            bindings = package.get("member_bindings")
            if not isinstance(bindings, list) or not any(
                isinstance(binding, dict)
                and binding.get("finding_id") == finding_id
                and binding.get("finding_sha256") == member.get("finding_sha256")
                and binding.get("origin_freeze_id") == member.get("freeze_id")
                for binding in bindings
            ):
                issues.append(_semantic_issue(event, "resolution_member_not_carried"))
                continue
            try:
                _bound_review_result_bytes(repository, ledger, result)
                _resolution_evidence(
                    repository,
                    str(event.get("resolution_ref") or ""),
                    ledger=ledger,
                    finding_id=str(finding_id),
                    result=result,
                    repair_freeze_id=str(active_id),
                )
                _bound_evidence_bytes(
                    repository,
                    ledger,
                    reference=event.get("resolution_ref"),
                    expected_sha256=event.get("resolution_sha256"),
                    label="resolution",
                )
            except ReviewFreezeError as exc:
                issues.append(_semantic_issue(event, exc.code))
                continue
            del state["batch_members"][str(finding_id)]
            continue

        if event_type == "replay_recorded":
            roster = active.get("required_reviews")
            completed = state["reviewers"].get(str(active_id), set())
            successor = active.get("supersedes_freeze_id") is not None
            delta_completed = {
                result.get("reviewer_id")
                for result in state["results"].values()
                if isinstance(result, dict)
                and result.get("freeze_id") == active_id
                and isinstance(result.get("reviewer_id"), str)
                and isinstance(result.get("review_package_id"), str)
                and isinstance(state["packages"].get(result.get("review_package_id")), dict)
                and state["packages"][result["review_package_id"]].get("package_kind") == "delta"
            }
            if (
                event.get("freeze_id") != active_id
                or state["freeze_status"].get(active_id) != "frozen"
                or not isinstance(roster, list)
                or not set(roster) <= completed
                or (successor and not set(roster) <= delta_completed)
            ):
                issues.append(
                    _semantic_issue(
                        event,
                        "successor_delta_review_round_missing"
                        if successor and set(roster) - delta_completed
                        else "replay_review_round_missing",
                    )
                )
                continue
            if _semantic_open_members(state, str(active_id)):
                issues.append(_semantic_issue(event, "replay_open_batch_members"))
                continue
            if (
                event.get("state") != "replayed"
                or event.get("receipt_chain_id") != active.get("receipt_chain_id")
                or event.get("state_scope") != "e11_scheduling_ledger_only"
                or event.get("state_claim_grade") != _DEGRADED_REPLAY_CLAIM
                or event.get("state_semantic_validity") != "not_established"
            ):
                issues.append(_semantic_issue(event, "replay_claim_not_degraded"))
                continue
            source_match = _source_match(repository, ledger, active)
            if not source_match["matches"]:
                issues.append(_semantic_issue(event, "replay_source_moved"))
                continue
            try:
                _bound_receipt_bytes(
                    repository,
                    ledger,
                    reference=event.get("receipt_ref"),
                    expected_sha256=event.get("receipt_sha256"),
                )
            except ReviewFreezeError as exc:
                issues.append(_semantic_issue(event, exc.code))
                continue
            state["freeze_status"][str(active_id)] = "replayed"
            continue

        if event_type == "closed":
            if (
                event.get("freeze_id") != active_id
                or state["freeze_status"].get(active_id) != "replayed"
                or _semantic_open_members(state, str(active_id))
                or event.get("state") != "closed"
                or event.get("state_scope") != "e11_scheduling_ledger_only"
                or event.get("state_claim_grade") != _DEGRADED_REPLAY_CLAIM
                or event.get("state_semantic_validity") != "not_established"
            ):
                issues.append(_semantic_issue(event, "close_transition_invalid"))
                continue
            match = _source_match(repository, ledger, active)
            if not match["matches"]:
                issues.append(_semantic_issue(event, "close_source_moved"))
                continue
            state["freeze_status"][str(active_id)] = "closed"
            continue

        issues.append(_semantic_issue(event, "event_type_unhandled"))
    return issues


def validate_ledger(*, repo_root: Path | str, ledger_path: Path | str) -> dict[str, object]:
    """Validate current JSONL, Git append-only history, and committed-marker status."""

    repository = _repository(repo_root)
    ledger = _require_ledger_path(repository, ledger_path, must_exist=False)
    events, issues = _parse_ledger(_read_bytes(ledger))
    issues.extend(_validate_event_chain(events))
    issues.extend(_history_issues(repository, ledger))
    if not issues:
        issues.extend(_semantic_transcript_issues(repository, ledger, events))
    if events:
        head_blob = _head_ledger_blob(repository, ledger)
        if head_blob is None:
            issues.append({"code": "ledger_marker_not_committed"})
        elif _read_bytes(ledger) != head_blob:
            issues.append({"code": "ledger_gate_events_not_committed"})
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "entry_count": len(events),
        "predicate_provenance": {
            "ledger_hash_chain": "recomputed",
            "git_history_prefix": "independently_reconciled",
            "committed_marker_status": "independently_reconciled",
        },
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the direct script without registering a second unified-tools surface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--ledger", required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    open_parser = commands.add_parser("open")
    open_parser.add_argument("--lane", required=True)
    open_parser.add_argument("--receipt-chain", required=True)
    open_parser.add_argument("--review-base", required=True)
    open_parser.add_argument("--required-review", action="append", required=True)
    open_parser.add_argument("--at", required=True)
    freeze_parser = commands.add_parser("freeze")
    freeze_parser.add_argument("--lane", required=True)
    freeze_parser.add_argument("--receipt-chain", required=True)
    freeze_parser.add_argument("--source-commit")
    freeze_parser.add_argument("--supersedes-freeze-id")
    freeze_parser.add_argument("--at", required=True)
    full_parser = commands.add_parser("build-full")
    full_parser.add_argument("--lane", required=True)
    full_parser.add_argument("--freeze-id", required=True)
    full_parser.add_argument("--base", required=True)
    full_parser.add_argument("--head", required=True)
    full_parser.add_argument("--output", required=True)
    delta_parser = commands.add_parser("build-delta")
    delta_parser.add_argument("--lane", required=True)
    delta_parser.add_argument("--freeze-id", required=True)
    delta_parser.add_argument("--checklist-output", required=True)
    delta_parser.add_argument("--base", required=True)
    delta_parser.add_argument("--head", required=True)
    delta_parser.add_argument("--output", required=True)
    result_parser = commands.add_parser("record-review-result")
    result_parser.add_argument("--lane", required=True)
    result_parser.add_argument("--freeze-id", required=True)
    result_parser.add_argument("--package-id", required=True)
    result_parser.add_argument("--reviewer", required=True)
    result_parser.add_argument("--result", required=True)
    result_parser.add_argument("--at", required=True)
    disposition_parser = commands.add_parser("disposition")
    disposition_parser.add_argument("--lane", required=True)
    disposition_parser.add_argument("--finding-id", required=True)
    disposition_parser.add_argument("--finding", required=True)
    disposition_parser.add_argument("--declared-class", required=True)
    disposition_parser.add_argument("--classification-provenance", required=True)
    disposition_parser.add_argument("--review-result-id")
    disposition_parser.add_argument("--at", required=True)
    derive_parser = commands.add_parser("derive-ruff-i001")
    derive_parser.add_argument("--source-path", required=True)
    derive_parser.add_argument("--output", required=True)
    admit_parser = commands.add_parser("admit-ruff-i001")
    admit_parser.add_argument("--lane", required=True)
    admit_parser.add_argument("--finding", required=True)
    admit_parser.add_argument("--review-result-id")
    admit_parser.add_argument("--at", required=True)
    resolve_parser = commands.add_parser("resolve")
    resolve_parser.add_argument("--lane", required=True)
    resolve_parser.add_argument("--finding-id", required=True)
    resolve_parser.add_argument("--review-result-id", required=True)
    resolve_parser.add_argument("--resolution", required=True)
    resolve_parser.add_argument("--at", required=True)
    replay_parser = commands.add_parser("replay")
    replay_parser.add_argument("--lane", required=True)
    replay_parser.add_argument("--freeze-id", required=True)
    replay_parser.add_argument("--receipt", required=True)
    replay_parser.add_argument("--at", required=True)
    close_parser = commands.add_parser("close")
    close_parser.add_argument("--lane", required=True)
    close_parser.add_argument("--freeze-id", required=True)
    close_parser.add_argument("--at", required=True)
    export_parser = commands.add_parser("export-checklist")
    export_parser.add_argument("--lane", required=True)
    export_parser.add_argument("--freeze-id", required=True)
    export_parser.add_argument("--output", required=True)
    commands.add_parser("validate")
    state_parser = commands.add_parser("state")
    state_parser.add_argument("--lane", required=True)
    return parser.parse_args(argv)


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Run the E11 gate's standalone internal CLI."""

    args = _parse_args(argv)
    common = {"repo_root": args.repo_root, "ledger_path": args.ledger}
    try:
        if args.command == "open":
            result: object = open_lane(
                **common,
                lane_id=args.lane,
                receipt_chain_id=args.receipt_chain,
                review_base_revision=args.review_base,
                required_reviews=tuple(args.required_review),
                recorded_at=args.at,
            )
        elif args.command == "freeze":
            result = freeze_lane(
                **common,
                lane_id=args.lane,
                receipt_chain_id=args.receipt_chain,
                source_commit=args.source_commit,
                supersedes_freeze_id=args.supersedes_freeze_id,
                recorded_at=args.at,
            )
        elif args.command == "build-full":
            result = build_full_review_package(
                **common,
                lane_id=args.lane,
                freeze_id=args.freeze_id,
                base_revision=args.base,
                head_revision=args.head,
                package_output=args.output,
            )
        elif args.command == "build-delta":
            result = build_batch_delta_review_package(
                **common,
                lane_id=args.lane,
                freeze_id=args.freeze_id,
                checklist_output=args.checklist_output,
                base_revision=args.base,
                head_revision=args.head,
                package_output=args.output,
            )
        elif args.command == "record-review-result":
            result = record_review_result(
                **common,
                lane_id=args.lane,
                freeze_id=args.freeze_id,
                review_package_id=args.package_id,
                reviewer_id=args.reviewer,
                result_path=args.result,
                recorded_at=args.at,
            )
        elif args.command == "disposition":
            result = disposition_finding(
                **common,
                lane_id=args.lane,
                finding_id=args.finding_id,
                finding_path=args.finding,
                declared_classification=args.declared_class,
                classification_provenance=args.classification_provenance,
                review_result_id=args.review_result_id,
                recorded_at=args.at,
            )
        elif args.command == "derive-ruff-i001":
            result = {
                "finding_path": str(
                    write_ruff_i001_finding(
                        repo_root=args.repo_root,
                        source_path=args.source_path,
                        output_path=args.output,
                    )
                )
            }
        elif args.command == "admit-ruff-i001":
            result = admit_ruff_i001_finding(
                **common,
                lane_id=args.lane,
                finding_path=args.finding,
                review_result_id=args.review_result_id,
                recorded_at=args.at,
            )
        elif args.command == "resolve":
            result = resolve_batch_member(
                **common,
                lane_id=args.lane,
                finding_id=args.finding_id,
                review_result_id=args.review_result_id,
                resolution_path=args.resolution,
                recorded_at=args.at,
            )
        elif args.command == "replay":
            result = record_replay(
                **common,
                lane_id=args.lane,
                freeze_id=args.freeze_id,
                receipt_path=args.receipt,
                recorded_at=args.at,
            )
        elif args.command == "close":
            result = close_lane(
                **common, lane_id=args.lane, freeze_id=args.freeze_id, recorded_at=args.at
            )
        elif args.command == "export-checklist":
            result = {
                "checklist_bytes": len(
                    export_batch_checklist(
                        **common,
                        lane_id=args.lane,
                        freeze_id=args.freeze_id,
                        output_path=args.output,
                    )
                )
            }
        elif args.command == "validate":
            result = validate_ledger(**common)
        else:
            result = lane_state(**common, lane_id=args.lane)
    except ReviewFreezeError as exc:
        print(f"review-freeze error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.command == "validate" and isinstance(result, dict) and result.get("status") != "pass":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli())

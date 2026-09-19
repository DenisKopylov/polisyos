"""Merge results from parallel node executions.

Merges ``NodeOutcome`` results back into a base ``ExperimentState`` by
applying each outcome's writes using the ``state_writes`` declarations
from their ``NodeSpec``.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    StateMutation,
    StateMutationJournal,
    StateMutationTargetKind,
    StateMutationTargetPresence,
    branch_state,
    mutation_journal_for_state,
)

_MISSING = object()
_DICT_FIELDS = frozenset({"inputs", "artifacts_index", "reports_index", "params"})


class StateReplayIncompatible(ValueError):
    """Typed fail-closed error for a cached mutation that cannot be replayed."""

    code = "state.replay_incompatible"

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{self.code}: {path}: {reason}")


class MergeConflictPolicy(StrEnum):
    """How to resolve overlapping writes produced by a parallel tier."""

    ERROR = "error"
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"


@dataclass(frozen=True)
class MergeConflict:
    """Structured description of an overlapping parallel write."""

    path: str
    aliases: tuple[str, ...]
    resolution: MergeConflictPolicy
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "aliases": list(self.aliases),
            "resolution": self.resolution.value,
            "message": self.message,
        }

    def __str__(self) -> str:
        aliases = ", ".join(self.aliases)
        return f"{self.path} [{aliases}] ({self.resolution.value})"


@dataclass(frozen=True)
class _StagedWrite:
    alias: str
    path: str
    parts: tuple[str, ...]
    value: Any
    operation: str = "set"
    index: int | None = None
    start: int | None = None
    stop: int | None = None
    step: int | None = None
    ordinal: int | None = None
    expected_target_presence: StateMutationTargetPresence | None = None
    expected_target_kind: StateMutationTargetKind | None = None


@dataclass(frozen=True)
class MergeResult:
    """Result of merging parallel outcomes into a base state."""

    state: ExperimentState
    conflicts: list[str] = field(default_factory=list)
    conflict_details: list[MergeConflict] = field(default_factory=list)
    resolved_conflicts: list[MergeConflict] = field(default_factory=list)
    applied_paths: list[str] = field(default_factory=list)
    applied: bool = True


def merge_parallel_outcomes(
    base_state: ExperimentState,
    outcomes: dict[str, NodeOutcome],
    write_specs: dict[str, list[str]],
    *,
    conflict_policy: MergeConflictPolicy = MergeConflictPolicy.ERROR,
    mutation_journals: dict[str, StateMutationJournal | None] | None = None,
) -> MergeResult:
    """Merge outcomes from parallel nodes by their ``state_writes`` declarations.

    The merge runs in two phases:
    1. Collect and validate all writes against the base state.
    2. Apply the staged writes atomically only when no unresolved conflict remains.

    For full dict writes (``params``, ``inputs``, ``artifacts_index``,
    ``reports_index``), the merge expands the write into per-key updates so
    disjoint keys can still merge safely.
    """
    if not outcomes:
        return MergeResult(state=base_state)

    staged = _collect_staged_writes(
        base_state,
        outcomes,
        write_specs,
        mutation_journals=mutation_journals,
    )
    accepted, conflicts, resolved_conflicts = _resolve_conflicts(
        staged,
        conflict_policy=conflict_policy,
    )
    if conflicts:
        return MergeResult(
            state=base_state,
            conflicts=[conflict.message for conflict in conflicts],
            conflict_details=conflicts,
            resolved_conflicts=resolved_conflicts,
            applied=False,
        )

    if not accepted:
        return MergeResult(
            state=base_state,
            resolved_conflicts=resolved_conflicts,
        )

    merged = branch_state(
        base_state,
        write_paths=(write.path for write in accepted),
    ).state
    for write in sorted(accepted, key=_write_order_key):
        _apply_staged_write(merged, write)

    return MergeResult(
        state=merged,
        resolved_conflicts=resolved_conflicts,
        applied_paths=sorted(write.path for write in accepted),
    )


def _collect_staged_writes(
    base_state: ExperimentState,
    outcomes: dict[str, NodeOutcome],
    write_specs: dict[str, list[str]],
    *,
    mutation_journals: dict[str, StateMutationJournal | None] | None = None,
) -> list[_StagedWrite]:
    staged: list[_StagedWrite] = []
    for alias in sorted(outcomes):
        outcome = outcomes[alias]
        for write_field in write_specs.get(alias, []):
            staged.extend(
                _writes_for_spec(
                    alias=alias,
                    write_field=write_field,
                    base_state=base_state,
                    outcome_state=outcome.state,
                    mutation_journal=(
                        mutation_journals.get(alias)
                        if mutation_journals is not None and alias in mutation_journals
                        else mutation_journal_for_state(outcome.state)
                    ),
                )
            )
    return _deduplicate_journal_writes(staged)


def _deduplicate_journal_writes(staged: list[_StagedWrite]) -> list[_StagedWrite]:
    """Select each journal operation once across overlapping declarations."""
    seen: set[tuple[str, int]] = set()
    deduplicated: list[_StagedWrite] = []
    for write in staged:
        if write.ordinal is None:
            deduplicated.append(write)
            continue
        key = (write.alias, write.ordinal)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(write)
    return deduplicated


def _write_order_key(write: _StagedWrite) -> tuple[str, int, str]:
    """Keep alias order deterministic while preserving journal order per alias."""
    return (
        write.alias,
        write.ordinal if write.ordinal is not None else -1,
        write.path,
    )


def _writes_for_spec(
    *,
    alias: str,
    write_field: str,
    base_state: ExperimentState,
    outcome_state: ExperimentState,
    mutation_journal: StateMutationJournal | None = None,
) -> list[_StagedWrite]:
    parts = tuple(part for part in write_field.split(".") if part)
    if not parts:
        return []

    if mutation_journal is not None:
        return _writes_from_mutations(
            alias=alias,
            write_parts=parts,
            mutations=mutation_journal.operations,
        )

    if len(parts) == 1 and parts[0] in _DICT_FIELDS:
        outcome_val = _get_path(outcome_state, parts)
        base_val = _get_path(base_state, parts)
        if not isinstance(outcome_val, dict):
            if outcome_val is _MISSING or outcome_val == base_val:
                return []
            return [_StagedWrite(alias=alias, path=write_field, parts=parts, value=outcome_val)]

        writes: list[_StagedWrite] = []
        base_dict = base_val if isinstance(base_val, dict) else {}
        for key, value in outcome_val.items():
            base_key_val = base_dict.get(key, _MISSING)
            if base_key_val is not _MISSING and value == base_key_val:
                continue
            if base_key_val is _MISSING and key not in base_dict and value is _MISSING:
                continue
            writes.append(
                _StagedWrite(
                    alias=alias,
                    path=f"{write_field}.{key}",
                    parts=(*parts, str(key)),
                    value=value,
                )
            )
        return writes

    outcome_val = _get_path(outcome_state, parts)
    base_val = _get_path(base_state, parts)
    if outcome_val is _MISSING:
        return []
    if base_val is not _MISSING and outcome_val == base_val:
        return []
    return [_StagedWrite(alias=alias, path=write_field, parts=parts, value=outcome_val)]


def _writes_from_mutations(
    *,
    alias: str,
    write_parts: tuple[str, ...],
    mutations: list[StateMutation],
) -> list[_StagedWrite]:
    staged: list[_StagedWrite] = []
    for ordinal, mutation in enumerate(mutations):
        parts = tuple(part for part in mutation.path.split(".") if part)
        if (
            not parts
            or not _paths_overlap(write_parts, parts)
            or not _path_contains(write_parts, parts)
        ):
            continue
        staged.append(
            _StagedWrite(
                alias=alias,
                path=mutation.path,
                parts=parts,
                value=_restore_mutation_value(mutation),
                operation=mutation.operation,
                index=mutation.index,
                start=mutation.start,
                stop=mutation.stop,
                step=mutation.step,
                ordinal=ordinal,
                expected_target_presence=mutation.target_presence,
                expected_target_kind=mutation.target_kind,
            )
        )
    return staged


def _restore_mutation_value(mutation: StateMutation) -> Any:
    if mutation.value_kind != "artifact_ref":
        return mutation.value
    if isinstance(mutation.value, ArtifactRef):
        return mutation.value
    try:
        return ArtifactRef.model_validate(mutation.value)
    except (TypeError, ValueError) as exc:
        raise StateReplayIncompatible(
            mutation.path,
            "artifact ref mutation value is invalid",
        ) from exc


def _path_contains(parent: tuple[str, ...], child: tuple[str, ...]) -> bool:
    return len(parent) <= len(child) and parent == child[: len(parent)]


def _resolve_conflicts(
    staged: list[_StagedWrite],
    *,
    conflict_policy: MergeConflictPolicy,
) -> tuple[list[_StagedWrite], list[MergeConflict], list[MergeConflict]]:
    accepted: list[_StagedWrite] = []
    conflicts: list[MergeConflict] = []
    resolved_conflicts: list[MergeConflict] = []

    for candidate in staged:
        overlapping = [
            existing
            for existing in accepted
            if existing.alias != candidate.alias and _paths_overlap(existing.parts, candidate.parts)
        ]
        if not overlapping:
            accepted.append(candidate)
            continue

        overlap = overlapping[-1]
        conflict_path = _common_conflict_path(overlap.parts, candidate.parts)
        conflict = MergeConflict(
            path=conflict_path,
            aliases=(overlap.alias, candidate.alias),
            resolution=conflict_policy,
            message=(
                f"parallel write conflict on {conflict_path!r} "
                f"between {overlap.alias} and {candidate.alias}"
            ),
        )
        if conflict_policy == MergeConflictPolicy.ERROR:
            conflicts.append(conflict)
            continue

        resolved_conflicts.append(conflict)
        if conflict_policy == MergeConflictPolicy.FIRST_WRITE_WINS:
            continue

        accepted = [
            existing
            for existing in accepted
            if not (
                existing.alias != candidate.alias
                and _paths_overlap(existing.parts, candidate.parts)
            )
        ]
        accepted.append(candidate)

    return accepted, conflicts, resolved_conflicts


def _common_conflict_path(a: tuple[str, ...], b: tuple[str, ...]) -> str:
    prefix: list[str] = []
    for left, right in zip(a, b, strict=False):
        if left != right:
            break
        prefix.append(left)
    if prefix:
        return ".".join(prefix)
    return ".".join(a)


def _paths_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    shared = min(len(a), len(b))
    return a[:shared] == b[:shared]


def _get_path(root: Any, parts: tuple[str, ...]) -> Any:
    current: Any = root
    for part in parts:
        if isinstance(current, BaseModel):
            if not hasattr(current, part):
                return _MISSING
            current = getattr(current, part)
            continue
        if isinstance(current, dict):
            if part not in current:
                return _MISSING
            current = current[part]
            continue
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (IndexError, TypeError, ValueError):
                return _MISSING
            continue
        return _MISSING
    return current


def _set_path(root: Any, parts: tuple[str, ...], value: Any) -> None:
    if len(parts) == 1:
        _assign_value(root, parts[0], value)
        return

    current: Any = root
    for index, part in enumerate(parts[:-1]):
        if isinstance(current, BaseModel):
            child = getattr(current, part, _MISSING)
            if child is _MISSING or child is None:
                raise TypeError(f"Cannot descend through missing state path segment {part!r}")
            current = child
            continue
        if isinstance(current, dict):
            child = current.get(part, _MISSING)
            if child is _MISSING or child is None:
                raise TypeError(f"Cannot descend through missing state path segment {part!r}")
            current = child
            continue
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (IndexError, TypeError, ValueError) as exc:
                raise TypeError(f"Cannot descend into list path segment {part!r}") from exc
            continue
        raise TypeError(f"Cannot descend into non-container path segment {part!r}")
    _assign_value(current, parts[-1], value)


def _assign_value(root: Any, key: str, value: Any) -> None:
    if isinstance(root, BaseModel):
        setattr(root, key, value)
        return
    if isinstance(root, dict):
        root[key] = value
        return
    if isinstance(root, list):
        try:
            root[int(key)] = value
        except (IndexError, TypeError, ValueError) as exc:
            raise TypeError(f"Cannot assign to list path segment {key!r}") from exc
        return
    raise TypeError(f"Cannot assign to path segment {key!r}")


_PROTECTED_DELETE_ROOTS = frozenset({"inputs", "artifacts_index", "reports_index"})


def _target_kind(value: Any) -> StateMutationTargetKind:
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    if isinstance(value, set):
        return "set"
    if isinstance(value, BaseModel):
        return "model"
    return "scalar"


def _validate_target_precondition(root: ExperimentState, write: _StagedWrite) -> None:
    """Reject replay when a journaled operation's target changed shape or vanished."""
    if write.expected_target_presence is None or write.expected_target_kind is None:
        return
    # Direct assignments intentionally overwrite the current leaf.  Their
    # parent path is still checked by _set_path; existing-leaf shape is not a
    # replay precondition (None is a valid replacement target).
    if write.operation == "set":
        return
    actual = _get_path(root, write.parts)
    if write.expected_target_presence == "missing":
        raise StateReplayIncompatible(
            write.path,
            "operation target was not present in producer branch",
        )
    if actual is _MISSING:
        raise StateReplayIncompatible(write.path, "operation target is missing")
    actual_kind = _target_kind(actual)
    if actual_kind != write.expected_target_kind:
        raise StateReplayIncompatible(
            write.path,
            f"operation target kind changed from {write.expected_target_kind!r} "
            f"to {actual_kind!r}",
        )


def _apply_staged_write(root: ExperimentState, write: _StagedWrite) -> None:
    if (
        write.operation in {"delete", "pop", "remove", "clear", "delete_index", "delete_slice"}
        and write.parts
        and write.parts[0] in _PROTECTED_DELETE_ROOTS
    ):
        raise StateReplayIncompatible(
            write.path,
            f"state deletion forbidden for protected root {write.parts[0]!r}",
        )
    _validate_target_precondition(root, write)
    if write.operation == "set":
        try:
            _set_path(root, write.parts, deepcopy(write.value))
        except (IndexError, TypeError, ValueError) as exc:
            raise StateReplayIncompatible(write.path, "set target is incompatible") from exc
        return
    if write.operation == "delete":
        _delete_path(root, write.parts)
        return

    target = _get_path(root, write.parts)
    if target is _MISSING:
        raise StateReplayIncompatible(write.path, "target path is missing")

    if write.operation == "append":
        if not isinstance(target, list):
            raise StateReplayIncompatible(write.path, "append target is not a list")
        target.append(deepcopy(write.value))
    elif write.operation == "extend":
        if not isinstance(target, list):
            raise StateReplayIncompatible(write.path, "extend target is not a list")
        target.extend(deepcopy(write.value or []))
    elif write.operation == "insert":
        if not isinstance(target, list):
            raise StateReplayIncompatible(write.path, "insert target is not a list")
        try:
            target.insert(
                write.index if write.index is not None else len(target),
                deepcopy(write.value),
            )
        except (IndexError, TypeError, ValueError) as exc:
            raise StateReplayIncompatible(write.path, "insert index is invalid") from exc
    elif write.operation == "pop":
        if not isinstance(target, list):
            raise StateReplayIncompatible(write.path, "pop target is not a list")
        try:
            target.pop(write.index if write.index is not None else -1)
        except (IndexError, TypeError, ValueError) as exc:
            raise StateReplayIncompatible(write.path, "pop index is invalid") from exc
    elif write.operation == "remove":
        if not isinstance(target, list):
            raise StateReplayIncompatible(write.path, "remove target is not a list")
        try:
            target.remove(write.value)
        except ValueError as exc:
            raise StateReplayIncompatible(write.path, "remove value is absent") from exc
    elif write.operation == "clear":
        if not isinstance(target, (dict, list, set)):
            raise StateReplayIncompatible(write.path, "clear target is not mutable")
        target.clear()
    elif write.operation == "reverse":
        if not isinstance(target, list):
            raise StateReplayIncompatible(write.path, "reverse target is not a list")
        target.reverse()
    elif write.operation == "sort":
        if not isinstance(target, list):
            raise StateReplayIncompatible(write.path, "sort target is not a list")
        target.sort()
    elif write.operation == "set_index":
        if not isinstance(target, list) or write.index is None:
            raise StateReplayIncompatible(write.path, "set_index target or index is invalid")
        try:
            target[write.index] = deepcopy(write.value)
        except (IndexError, TypeError, ValueError) as exc:
            raise StateReplayIncompatible(write.path, "set_index index is invalid") from exc
    elif write.operation == "delete_index":
        if not isinstance(target, list) or write.index is None:
            raise StateReplayIncompatible(write.path, "delete_index target or index is invalid")
        try:
            del target[write.index]
        except (IndexError, TypeError, ValueError) as exc:
            raise StateReplayIncompatible(write.path, "delete_index index is invalid") from exc
    elif write.operation == "set_slice":
        if not isinstance(target, list):
            raise StateReplayIncompatible(write.path, "set_slice target is not a list")
        try:
            target[slice(write.start, write.stop, write.step)] = deepcopy(write.value or [])
        except (IndexError, TypeError, ValueError) as exc:
            raise StateReplayIncompatible(write.path, "set_slice bounds are invalid") from exc
    elif write.operation == "delete_slice":
        if not isinstance(target, list):
            raise StateReplayIncompatible(write.path, "delete_slice target is not a list")
        try:
            del target[slice(write.start, write.stop, write.step)]
        except (IndexError, TypeError, ValueError) as exc:
            raise StateReplayIncompatible(write.path, "delete_slice bounds are invalid") from exc
    elif write.operation == "replace":
        try:
            _set_path(root, write.parts, deepcopy(write.value))
        except (IndexError, TypeError, ValueError) as exc:
            raise StateReplayIncompatible(write.path, "replace target is incompatible") from exc
    else:
        raise StateReplayIncompatible(write.path, f"unknown operation {write.operation!r}")


def _delete_path(root: ExperimentState, parts: tuple[str, ...]) -> None:
    if not parts or len(parts) == 1:
        raise StateReplayIncompatible(
            write_path(parts),
            "state deletion forbidden at top-level field",
        )
    if parts[0] in _PROTECTED_DELETE_ROOTS:
        raise StateReplayIncompatible(
            write_path(parts),
            f"state deletion forbidden for protected root {parts[0]!r}",
        )
    parent = _get_path(root, parts[:-1])
    if parent is _MISSING:
        raise StateReplayIncompatible(write_path(parts), "delete parent path is missing")
    key = parts[-1]
    if isinstance(parent, BaseModel):
        raise StateReplayIncompatible(
            write_path(parts),
            f"state deletion forbidden for model field {write_path(parts)!r}",
        )
    if isinstance(parent, dict):
        if key not in parent:
            raise StateReplayIncompatible(write_path(parts), "delete target key is missing")
        del parent[key]
        return
    if isinstance(parent, list):
        try:
            del parent[int(key)]
        except (IndexError, TypeError, ValueError) as exc:
            raise StateReplayIncompatible(write_path(parts), "delete index is invalid") from exc
        return
    raise StateReplayIncompatible(
        write_path(parts),
        f"state deletion forbidden for non-container path {write_path(parts)!r}",
    )


def write_path(parts: tuple[str, ...]) -> str:
    """Render a path for state mutation errors."""
    return ".".join(parts)


__all__ = [
    "MergeConflict",
    "MergeConflictPolicy",
    "MergeResult",
    "StateReplayIncompatible",
    "merge_parallel_outcomes",
]

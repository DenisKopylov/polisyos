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

from polisyos.scientist.engine.protocol import NodeOutcome
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.engine.state_branching import branch_state

_MISSING = object()
_DICT_FIELDS = frozenset({"inputs", "artifacts_index", "reports_index", "params"})


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

    staged = _collect_staged_writes(base_state, outcomes, write_specs)
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
    for write in sorted(accepted, key=lambda item: item.path):
        _set_path(merged, write.parts, deepcopy(write.value))

    return MergeResult(
        state=merged,
        resolved_conflicts=resolved_conflicts,
        applied_paths=sorted(write.path for write in accepted),
    )


def _collect_staged_writes(
    base_state: ExperimentState,
    outcomes: dict[str, NodeOutcome],
    write_specs: dict[str, list[str]],
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
                )
            )
    return staged


def _writes_for_spec(
    *,
    alias: str,
    write_field: str,
    base_state: ExperimentState,
    outcome_state: ExperimentState,
) -> list[_StagedWrite]:
    parts = tuple(part for part in write_field.split(".") if part)
    if not parts:
        return []

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
        return _MISSING
    return current


def _set_path(root: Any, parts: tuple[str, ...], value: Any) -> None:
    if len(parts) == 1:
        _assign_value(root, parts[0], value)
        return

    current: Any = root
    for index, part in enumerate(parts[:-1]):
        next_part = parts[index + 1]
        if isinstance(current, BaseModel):
            child = getattr(current, part, _MISSING)
            if child is _MISSING or child is None:
                replacement: Any = {} if index < len(parts) - 2 else {}
                setattr(current, part, replacement)
                child = replacement
            current = child
            continue
        if isinstance(current, dict):
            child = current.get(part, _MISSING)
            if child is _MISSING or child is None:
                current[part] = {}
                child = current[part]
            current = child
            continue
        raise TypeError(f"Cannot descend into non-container path segment {next_part!r}")
    _assign_value(current, parts[-1], value)


def _assign_value(root: Any, key: str, value: Any) -> None:
    if isinstance(root, BaseModel):
        setattr(root, key, value)
        return
    if isinstance(root, dict):
        root[key] = value
        return
    raise TypeError(f"Cannot assign to path segment {key!r}")


__all__ = [
    "MergeConflict",
    "MergeConflictPolicy",
    "MergeResult",
    "merge_parallel_outcomes",
]

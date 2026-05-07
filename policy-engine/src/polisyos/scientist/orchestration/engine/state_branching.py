"""Helpers for bounded state branching in execution hot paths.

The engine previously relied on unconditional ``model_copy(deep=True)`` for
per-node and per-branch isolation.  That is safe but expensive because every
parallel branch deep-copies the full ``ExperimentState`` even when a node only
declares a handful of writes.

This module provides a narrower branching contract:

* create a shallow state copy;
* shallow-copy known mutable top-level mappings;
* isolate only the declared write paths with copy-on-write semantics; and
* keep a small mutation journal describing which fields/paths were isolated.
"""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from polisyos.scientist.orchestration.engine.state import ExperimentState

_MISSING = object()
_TOP_LEVEL_MUTABLE_FIELDS = (
    "inputs",
    "artifacts_index",
    "reports_index",
    "params",
    "budgets",
    "causal_method_params",
)


@dataclass(frozen=True)
class StateMutationJournal:
    """Describe which state surfaces were isolated for one branch."""

    isolated_fields: tuple[str, ...]
    isolated_paths: tuple[str, ...]


@dataclass(frozen=True)
class BranchedState:
    """A branched state plus the isolation journal used to build it."""

    state: ExperimentState
    journal: StateMutationJournal


def branch_state(
    base_state: ExperimentState,
    *,
    write_paths: Iterable[str] = (),
) -> BranchedState:
    """Return a branch-local state with copy-on-write isolation for *write_paths*.

    Top-level mutable mappings are shallow-copied eagerly so direct key writes
    never leak into the base state.  For nested writes, the containers along the
    declared path are isolated lazily by cloning only the traversed branches.
    """

    branched = base_state.model_copy(deep=False)
    isolated_fields: list[str] = []
    for field_name in _TOP_LEVEL_MUTABLE_FIELDS:
        value = getattr(base_state, field_name, None)
        if isinstance(value, dict):
            setattr(branched, field_name, dict(value))
            isolated_fields.append(field_name)

    normalized_paths = _normalize_paths(write_paths)
    for parts in normalized_paths:
        _isolate_write_path(base_state, branched, parts)

    return BranchedState(
        state=branched,
        journal=StateMutationJournal(
            isolated_fields=tuple(isolated_fields),
            isolated_paths=tuple(".".join(parts) for parts in normalized_paths),
        ),
    )


def snapshot_state(base_state: ExperimentState) -> ExperimentState:
    """Return a full rollback-safe snapshot of the mutable state surfaces."""

    branched = base_state.model_copy(deep=False)
    for field_name in _TOP_LEVEL_MUTABLE_FIELDS:
        value = getattr(base_state, field_name, None)
        if isinstance(value, dict):
            setattr(branched, field_name, deepcopy(value))
    return branched


def _normalize_paths(write_paths: Iterable[str]) -> list[tuple[str, ...]]:
    normalized = {
        tuple(part for part in str(path).split(".") if part)
        for path in write_paths
        if str(path).strip()
    }
    return sorted(normalized)


def _isolate_write_path(
    source_state: ExperimentState,
    target_state: ExperimentState,
    parts: tuple[str, ...],
) -> None:
    if not parts:
        return

    top_level = parts[0]
    source_value = getattr(source_state, top_level, _MISSING)
    target_value = getattr(target_state, top_level, _MISSING)
    if source_value is _MISSING or target_value is _MISSING:
        return

    if len(parts) == 1:
        setattr(target_state, top_level, deepcopy(source_value))
        return

    _ensure_isolated_container(
        source_parent=source_value,
        target_parent=target_value,
        parts=parts[1:],
    )


def _ensure_isolated_container(
    *,
    source_parent: Any,
    target_parent: Any,
    parts: tuple[str, ...],
) -> None:
    if not parts:
        return

    part = parts[0]
    source_child = _get_child(source_parent, part)
    if source_child is _MISSING:
        return

    target_child = _get_child(target_parent, part)
    if target_child is source_child:
        cloned = _clone_container(source_child)
        _set_child(target_parent, part, cloned)
        target_child = cloned
    elif target_child is _MISSING:
        target_child = _clone_container(source_child)
        _set_child(target_parent, part, target_child)

    if len(parts) > 1 and _is_branchable_container(target_child):
        _ensure_isolated_container(
            source_parent=source_child,
            target_parent=target_child,
            parts=parts[1:],
        )


def _get_child(container: Any, key: str) -> Any:
    if isinstance(container, BaseModel):
        return getattr(container, key, _MISSING)
    if isinstance(container, dict):
        return container.get(key, _MISSING)
    return _MISSING


def _set_child(container: Any, key: str, value: Any) -> None:
    if isinstance(container, BaseModel):
        setattr(container, key, value)
        return
    if isinstance(container, dict):
        container[key] = value
        return
    raise TypeError(f"Cannot assign nested state field {key!r} on {type(container).__name__}")


def _clone_container(value: Any) -> Any:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return tuple(value)
    if isinstance(value, set):
        return set(value)
    if isinstance(value, BaseModel):
        # Preserve copy-on-write behavior for nested models: clone only the
        # model shell here and let deeper path isolation materialize mutable
        # children lazily as traversal reaches them.
        return value.model_copy(deep=False)
    return deepcopy(value)


def _is_branchable_container(value: Any) -> bool:
    return isinstance(value, (BaseModel, dict, list, tuple, set))


__all__ = [
    "BranchedState",
    "StateMutationJournal",
    "branch_state",
    "snapshot_state",
]

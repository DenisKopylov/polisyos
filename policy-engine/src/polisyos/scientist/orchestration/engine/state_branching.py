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
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

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
    """Describe isolation and concrete state operations for one branch."""

    isolated_fields: tuple[str, ...]
    isolated_paths: tuple[str, ...]
    operations: list[StateMutation] = field(default_factory=list)

    def record(
        self,
        *,
        path: tuple[str, ...],
        operation: StateMutationOperation,
        value: Any = None,
        index: int | None = None,
        start: int | None = None,
        stop: int | None = None,
        step: int | None = None,
    ) -> None:
        """Append one concrete mutation to the branch journal."""
        self.operations.append(
            StateMutation(
                path=".".join(path),
                operation=operation,
                value=deepcopy(value),
                index=index,
                start=start,
                stop=stop,
                step=step,
            )
        )

    def __deepcopy__(self, memo: dict[int, Any]) -> StateMutationJournal:
        """Keep copied state models attached to the originating journal."""
        del memo
        return self


StateMutationOperation = Literal[
    "set",
    "delete",
    "append",
    "extend",
    "insert",
    "pop",
    "remove",
    "clear",
    "reverse",
    "sort",
    "set_index",
    "delete_index",
    "set_slice",
    "delete_slice",
    "replace",
]


class StateMutation(BaseModel):
    """One concrete, replayable mutation emitted by a branch-local state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(min_length=1)
    operation: StateMutationOperation
    value: Any = None
    index: int | None = None
    start: int | None = None
    stop: int | None = None
    step: int | None = None


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
    journal = StateMutationJournal(
        isolated_fields=tuple(isolated_fields),
        isolated_paths=tuple(".".join(parts) for parts in normalized_paths),
        operations=[],
    )
    for parts in normalized_paths:
        _isolate_write_path(base_state, branched, parts)

    _install_mutation_tracking(branched, normalized_paths, journal)
    _attach_mutation_journal(branched, journal)

    return BranchedState(
        state=branched,
        journal=journal,
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
        cloned = _clone_container(source_child, deep=len(parts) == 1)
        _set_child(target_parent, part, cloned)
        target_child = cloned
    elif target_child is _MISSING:
        target_child = _clone_container(source_child, deep=len(parts) == 1)
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


def _clone_container(value: Any, *, deep: bool = False) -> Any:
    if deep:
        return deepcopy(value)
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


_MUTATION_JOURNAL_ATTR = "_polisyos_state_mutation_journal"


def _attach_mutation_journal(state: ExperimentState, journal: StateMutationJournal) -> None:
    """Attach a private journal without widening the public state contract."""
    object.__setattr__(state, _MUTATION_JOURNAL_ATTR, journal)


def mutation_journal_for_state(state: ExperimentState) -> StateMutationJournal | None:
    """Return the branch journal carried by *state*, if one is present."""
    journal = getattr(state, _MUTATION_JOURNAL_ATTR, None)
    if isinstance(journal, StateMutationJournal):
        return journal
    return _find_mutation_journal(state, set())


def mutation_journal_from_operations(
    operations: Iterable[StateMutation],
) -> StateMutationJournal:
    """Build a replay journal for operations loaded from a cache artifact."""
    return StateMutationJournal(
        isolated_fields=(),
        isolated_paths=(),
        operations=list(operations),
    )


def _find_mutation_journal(value: Any, seen: set[int]) -> StateMutationJournal | None:
    if id(value) in seen:
        return None
    seen.add(id(value))
    journal = getattr(value, "_polisyos_mutation_journal", None)
    if isinstance(journal, StateMutationJournal):
        return journal
    if isinstance(value, BaseModel):
        for child in value.__dict__.values():
            found = _find_mutation_journal(child, seen)
            if found is not None:
                return found
    elif isinstance(value, dict):
        for child in value.values():
            found = _find_mutation_journal(child, seen)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple, set)):
        for child in value:
            found = _find_mutation_journal(child, seen)
            if found is not None:
                return found
    return None


def _install_mutation_tracking(
    state: ExperimentState,
    paths: list[tuple[str, ...]],
    journal: StateMutationJournal,
) -> None:
    """Wrap only declared mutable leaves/parents with operation-recording views."""
    installed: list[tuple[str, ...]] = []
    for parts in paths:
        if any(_is_path_prefix(existing, parts) for existing in installed):
            continue
        target = _get_path(state, parts)
        if target is _MISSING:
            if len(parts) >= 2:
                parent_parts = parts[:-1]
                parent = _get_path(state, parent_parts)
                if _is_mutable_container(parent):
                    wrapped_parent = _wrap_mutable_value(
                        parent,
                        parent_parts,
                        journal,
                        recursive=False,
                    )
                    if wrapped_parent is not parent:
                        _set_path(state, parent_parts, wrapped_parent)
                    installed.append(parent_parts)
            continue
        if _is_mutable_container(target):
            wrapped = _wrap_mutable_value(target, parts, journal)
            if wrapped is not target:
                _set_path(state, parts, wrapped)
            installed.append(parts)
            continue
        if len(parts) < 2:
            continue
        parent_parts = parts[:-1]
        parent = _get_path(state, parent_parts)
        if not _is_mutable_container(parent):
            continue
        wrapped_parent = _wrap_mutable_value(parent, parent_parts, journal, recursive=False)
        if wrapped_parent is not parent:
            _set_path(state, parent_parts, wrapped_parent)
        installed.append(parent_parts)


def _is_path_prefix(prefix: tuple[str, ...], path: tuple[str, ...]) -> bool:
    return len(prefix) <= len(path) and prefix == path[: len(prefix)]


def _is_mutable_container(value: Any) -> bool:
    return isinstance(value, (dict, list, set))


def _get_path(root: Any, parts: tuple[str, ...]) -> Any:
    current = root
    for part in parts:
        if isinstance(current, BaseModel):
            current = getattr(current, part, _MISSING)
        elif isinstance(current, dict):
            current = current.get(part, _MISSING)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (IndexError, TypeError, ValueError):
                return _MISSING
        else:
            return _MISSING
        if current is _MISSING:
            return _MISSING
    return current


def _set_path(root: Any, parts: tuple[str, ...], value: Any) -> None:
    if len(parts) == 1:
        _set_child(root, parts[0], value)
        return
    parent = _get_path(root, parts[:-1])
    if parent is _MISSING:
        return
    _set_child(parent, parts[-1], value)


class _TrackedDict(dict[str, Any]):
    """Dict view that records concrete writes/deletes against a branch journal."""

    def __init__(
        self,
        values: dict[str, Any],
        *,
        path: tuple[str, ...],
        journal: StateMutationJournal,
        recursive: bool,
    ) -> None:
        dict.__init__(self)
        self._mutation_path = path
        self._mutation_journal = journal
        for key, value in values.items():
            dict.__setitem__(
                self,
                key,
                _wrap_mutable_value(value, (*path, str(key)), journal)
                if recursive
                else value,
            )

    def __setitem__(self, key: str, value: Any) -> None:
        wrapped = _wrap_mutable_value(
            value,
            (*self._mutation_path, str(key)),
            self._mutation_journal,
        )
        dict.__setitem__(self, key, wrapped)
        self._mutation_journal.record(
            path=(*self._mutation_path, str(key)),
            operation="set",
            value=value,
        )

    def __delitem__(self, key: str) -> None:
        dict.__delitem__(self, key)
        self._mutation_journal.record(
            path=(*self._mutation_path, str(key)),
            operation="delete",
        )

    def update(self, *args: Any, **kwargs: Any) -> None:
        values = dict(*args, **kwargs)
        for key, value in values.items():
            self[key] = value

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key in self:
            return self[key]
        self[key] = default
        return self[key]

    def pop(self, key: str, *args: Any) -> Any:
        if key not in self:
            if args:
                return args[0]
            raise KeyError(key)
        value = dict.pop(self, key)
        self._mutation_journal.record(
            path=(*self._mutation_path, str(key)),
            operation="delete",
        )
        return value

    def popitem(self) -> tuple[str, Any]:
        key, value = dict.popitem(self)
        self._mutation_journal.record(
            path=(*self._mutation_path, str(key)),
            operation="delete",
        )
        return key, value

    def clear(self) -> None:
        keys = list(self)
        dict.clear(self)
        for key in keys:
            self._mutation_journal.record(
                path=(*self._mutation_path, str(key)),
                operation="delete",
            )

    def __deepcopy__(self, memo: dict[int, Any]) -> _TrackedDict:
        existing = memo.get(id(self))
        if existing is not None:
            return existing
        clone = _TrackedDict.__new__(_TrackedDict)
        memo[id(self)] = clone
        clone._mutation_path = self._mutation_path
        clone._mutation_journal = self._mutation_journal
        dict.__init__(clone)
        for key, value in self.items():
            dict.__setitem__(clone, deepcopy(key, memo), deepcopy(value, memo))
        return clone


class _TrackedList(list[Any]):
    """List view that records replayable element/container operations."""

    def __init__(
        self,
        values: list[Any],
        *,
        path: tuple[str, ...],
        journal: StateMutationJournal,
    ) -> None:
        list.__init__(self)
        self._mutation_path = path
        self._mutation_journal = journal
        for index, value in enumerate(values):
            list.append(
                self,
                _wrap_mutable_value(value, (*path, str(index)), journal),
            )

    def __setitem__(self, index: int | slice, value: Any) -> None:
        if isinstance(index, slice):
            values = list(value)
            list.__setitem__(
                self,
                index,
                [
                    _wrap_mutable_value(item, (*self._mutation_path, str(i)), self._mutation_journal)
                    for i, item in enumerate(values)
                ],
            )
            self._mutation_journal.record(
                path=self._mutation_path,
                operation="set_slice",
                value=values,
                start=index.start,
                stop=index.stop,
                step=index.step,
            )
            return
        list.__setitem__(
            self,
            index,
            _wrap_mutable_value(
                value,
                (*self._mutation_path, str(index)),
                self._mutation_journal,
            ),
        )
        self._mutation_journal.record(
            path=self._mutation_path,
            operation="set_index",
            value=value,
            index=index,
        )

    def __delitem__(self, index: int | slice) -> None:
        list.__delitem__(self, index)
        if isinstance(index, slice):
            self._mutation_journal.record(
                path=self._mutation_path,
                operation="delete_slice",
                start=index.start,
                stop=index.stop,
                step=index.step,
            )
        else:
            self._mutation_journal.record(
                path=self._mutation_path,
                operation="delete_index",
                index=index,
            )

    def append(self, value: Any) -> None:
        list.append(
            self,
            _wrap_mutable_value(value, (*self._mutation_path, str(len(self))), self._mutation_journal),
        )
        self._mutation_journal.record(
            path=self._mutation_path,
            operation="append",
            value=value,
        )

    def extend(self, values: Iterable[Any]) -> None:
        values_list = list(values)
        for value in values_list:
            self.append(value)

    def insert(self, index: int, value: Any) -> None:
        list.insert(
            self,
            index,
            _wrap_mutable_value(value, (*self._mutation_path, str(index)), self._mutation_journal),
        )
        self._mutation_journal.record(
            path=self._mutation_path,
            operation="insert",
            value=value,
            index=index,
        )

    def pop(self, index: int = -1) -> Any:
        value = list.pop(self, index)
        self._mutation_journal.record(
            path=self._mutation_path,
            operation="pop",
            index=index,
        )
        return value

    def remove(self, value: Any) -> None:
        list.remove(self, value)
        self._mutation_journal.record(
            path=self._mutation_path,
            operation="remove",
            value=value,
        )

    def clear(self) -> None:
        list.clear(self)
        self._mutation_journal.record(path=self._mutation_path, operation="clear")

    def reverse(self) -> None:
        list.reverse(self)
        self._mutation_journal.record(path=self._mutation_path, operation="reverse")

    def sort(self, *args: Any, **kwargs: Any) -> None:
        list.sort(self, *args, **kwargs)
        self._mutation_journal.record(
            path=self._mutation_path,
            operation="replace",
            value=list(self),
        )

    def __iadd__(self, values: Iterable[Any]) -> _TrackedList:
        self.extend(values)
        return self

    def __imul__(self, count: int) -> _TrackedList:
        list.__imul__(self, count)
        self._mutation_journal.record(
            path=self._mutation_path,
            operation="replace",
            value=list(self),
        )
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> _TrackedList:
        existing = memo.get(id(self))
        if existing is not None:
            return existing
        clone = _TrackedList.__new__(_TrackedList)
        memo[id(self)] = clone
        clone._mutation_path = self._mutation_path
        clone._mutation_journal = self._mutation_journal
        list.__init__(clone)
        for value in self:
            list.append(clone, deepcopy(value, memo))
        return clone


def _wrap_mutable_value(
    value: Any,
    path: tuple[str, ...],
    journal: StateMutationJournal,
    *,
    recursive: bool = True,
) -> Any:
    if isinstance(value, _TrackedDict):
        if value._mutation_journal is journal and value._mutation_path == path:
            return value
        return _TrackedDict(dict(value), path=path, journal=journal, recursive=recursive)
    if isinstance(value, dict):
        return _TrackedDict(value, path=path, journal=journal, recursive=recursive)
    if isinstance(value, _TrackedList):
        if value._mutation_journal is journal and value._mutation_path == path:
            return value
        return _TrackedList(list(value), path=path, journal=journal)
    if isinstance(value, list):
        return _TrackedList(value, path=path, journal=journal)
    if isinstance(value, tuple):
        return tuple(
            _wrap_mutable_value(item, (*path, str(index)), journal)
            for index, item in enumerate(value)
        )
    return value


__all__ = [
    "BranchedState",
    "StateMutation",
    "StateMutationOperation",
    "StateMutationJournal",
    "branch_state",
    "mutation_journal_for_state",
    "mutation_journal_from_operations",
    "snapshot_state",
]

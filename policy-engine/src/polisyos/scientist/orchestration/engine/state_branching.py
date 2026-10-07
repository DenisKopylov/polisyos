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

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from inspect import getattr_static
from operator import index as _index
from typing import Any, ClassVar, Literal, Self, SupportsIndex, cast

from pydantic import BaseModel, ConfigDict, Field, RootModel

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.ir.registry.refs import ArtifactRefModel
from polisyos.scientist.orchestration.engine.state import ExperimentState

_MISSING = object()
_JOURNAL_INTENT_CANON = CanonSpec(forbid_floats=False, exclude_none=False)
_MUTATION_JOURNAL_ATTR = "_polisyos_state_mutation_journal"
_TOP_LEVEL_MUTABLE_FIELDS = (
    "inputs",
    "artifacts_index",
    "reports_index",
    "params",
    "budgets",
    "causal_method_params",
)

StateMutationTargetPresence = Literal["present", "missing"]
StateMutationTargetKind = Literal["missing", "dict", "list", "set", "model", "scalar"]
StateMutationValueKind = Literal["json", "artifact_ref"]


@dataclass(frozen=True)
class StateMutationJournal:
    """Describe isolation and concrete state operations for one branch."""

    isolated_fields: tuple[str, ...]
    isolated_paths: tuple[str, ...]
    operations: list[StateMutation] = field(default_factory=list)
    enforce_write_scope: bool = False
    _isolated_values: dict[int, Any] = field(default_factory=dict, repr=False, compare=False)
    _wrapped_values: dict[int, Any] = field(default_factory=dict, repr=False, compare=False)

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
        target: Any = _MISSING,
        operation_group: int | None = None,
    ) -> None:
        """Append one concrete mutation to the branch journal."""
        target_presence, target_kind = _target_descriptor(target)
        self.operations.append(
            StateMutation(
                path=".".join(path),
                operation=operation,
                value=deepcopy(value),
                value_kind=_mutation_value_kind(value),
                index=index,
                start=start,
                stop=stop,
                step=step,
                target_presence=target_presence,
                target_kind=target_kind,
                operation_group=operation_group,
            )
        )

    def __deepcopy__(self, memo: dict[int, Any]) -> StateMutationJournal:
        """Keep copied state models attached to the originating journal."""
        del memo
        return self


class _JournaledExperimentState(ExperimentState):
    """ExperimentState view that records declared scalar assignments."""

    __slots__ = ()

    def __setattr__(self, name: str, value: Any) -> None:
        try:
            journal = object.__getattribute__(self, _MUTATION_JOURNAL_ATTR)
        except AttributeError:
            journal = None
        if isinstance(journal, StateMutationJournal) and journal.enforce_write_scope:
            if name not in journal.isolated_paths:
                raise ValueError(f"undeclared state_writes at live paths: {[name]}")
            _validate_mutation_attachment(None, value)
            value = _wrap_mutable_value(value, (name,), journal)
        if isinstance(journal, StateMutationJournal) and name in journal.isolated_paths:
            previous = getattr(self, name, _MISSING)
            super().__setattr__(name, value)
            _bind_mutation_root(getattr(self, name), self, name, (name,))
            if previous is not _MISSING:
                journal.record(path=(name,), operation="set", value=value, target=previous)
            return
        super().__setattr__(name, value)

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        journal = mutation_journal_for_state(self)
        if journal is None or not journal.enforce_write_scope:
            return super().model_copy(update=update, deep=deep)
        for name in update or ():
            if name not in journal.isolated_paths:
                raise ValueError(f"undeclared state_writes at live paths: {[name]}")
        copied = super().model_copy(deep=deep)
        for name in type(self).model_fields:
            _bind_mutation_root(getattr(copied, name), copied, name, (name,))
        for name, value in (update or {}).items():
            setattr(copied, name, value)
        return copied


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
    value_kind: StateMutationValueKind = "json"
    index: int | None = None
    start: int | None = None
    stop: int | None = None
    step: int | None = None
    target_presence: StateMutationTargetPresence = "present"
    target_kind: StateMutationTargetKind = "scalar"
    operation_group: int | None = Field(default=None, ge=0, strict=True)


def _mutation_value_kind(value: Any) -> StateMutationValueKind:
    if isinstance(value, (ArtifactRef, ArtifactRefModel)):
        return "artifact_ref"
    return "json"


def _target_descriptor(value: Any) -> tuple[StateMutationTargetPresence, StateMutationTargetKind]:
    if value is _MISSING:
        return "missing", "missing"
    if isinstance(value, dict):
        return "present", "dict"
    if isinstance(value, list):
        return "present", "list"
    if isinstance(value, set):
        return "present", "set"
    if isinstance(value, BaseModel):
        return "present", "model"
    return "present", "scalar"


@dataclass(frozen=True)
class BranchedState:
    """A branched state plus the isolation journal used to build it."""

    state: ExperimentState
    journal: StateMutationJournal


def branch_state(
    base_state: ExperimentState,
    *,
    write_paths: Iterable[str] = (),
    enforce_write_scope: bool | None = None,
) -> BranchedState:
    """Return a branch-local state with copy-on-write isolation for *write_paths*.

    Top-level mutable mappings are shallow-copied eagerly so direct key writes
    never leak into the base state.  For nested writes, the containers along the
    declared path are isolated lazily by cloning only the traversed branches.
    """

    source_journal = mutation_journal_for_state(base_state)
    normalized_paths = _normalize_paths(write_paths)
    if source_journal is not None and source_journal.enforce_write_scope:
        if enforce_write_scope is False:
            raise ValueError("cannot release active producer write scope")
        grant = [tuple(path.split(".")) for path in source_journal.isolated_paths]
        if any(
            not any(_is_path_prefix(allowed, path) for allowed in grant)
            for path in normalized_paths
        ):
            raise ValueError("nested branch cannot broaden active producer write scope")
        enforce_write_scope = True
    if enforce_write_scope is None:
        enforce_write_scope = source_journal.enforce_write_scope if source_journal else False
    branched = _promote_to_journaled_state(base_state.model_copy(deep=False))
    object.__setattr__(branched, _MUTATION_JOURNAL_ATTR, None)
    isolated_fields: list[str] = []
    for field_name in _TOP_LEVEL_MUTABLE_FIELDS:
        value = getattr(base_state, field_name, None)
        if isinstance(value, dict):
            setattr(branched, field_name, dict(value))
            isolated_fields.append(field_name)

    isolation_memo: dict[int, Any] = {}
    journal = StateMutationJournal(
        isolated_fields=tuple(isolated_fields),
        isolated_paths=tuple(".".join(parts) for parts in normalized_paths),
        operations=[],
        enforce_write_scope=enforce_write_scope,
        _isolated_values=isolation_memo,
    )
    for parts in normalized_paths:
        _isolate_write_path(base_state, branched, parts, isolation_memo)

    _install_mutation_tracking(branched, normalized_paths, journal)
    _attach_mutation_journal(branched, journal)

    return BranchedState(
        state=branched,
        journal=journal,
    )


def snapshot_state(base_state: ExperimentState) -> ExperimentState:
    """Return a full rollback-safe snapshot of the mutable state surfaces."""

    branched = base_state.model_copy(deep=False)
    memo: dict[int, Any] = {}
    for field_name in _TOP_LEVEL_MUTABLE_FIELDS:
        value = getattr(base_state, field_name, None)
        if isinstance(value, dict):
            object.__setattr__(branched, field_name, deepcopy(value, memo))
            _bind_mutation_root(getattr(branched, field_name), branched, field_name, (field_name,))
    return branched


def _completed_producer_state(state: ExperimentState) -> ExperimentState:
    """Detach settled engine-owned completion from its producer's live grant.

    The original producer view stays guarded.  Only the executor calls this
    boundary after invocation and cache publication have settled; ordinary
    nested branching cannot release an active grant.
    """
    source = mutation_journal_for_state(state)
    if source is None or not source.enforce_write_scope:
        return state
    completed = state.model_copy(deep=True)
    journal = StateMutationJournal(
        isolated_fields=source.isolated_fields,
        isolated_paths=source.isolated_paths,
        operations=list(source.operations),
    )
    _attach_mutation_journal(completed, journal)
    seen: set[int] = set()

    def rebind(value: Any) -> None:
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, (_TrackedDict, _TrackedList, _TrackedModelMixin)):
            object.__setattr__(value, "_mutation_journal", journal)
        children: Iterable[Any]
        if isinstance(value, BaseModel):
            children = (getattr(value, name) for name in type(value).model_fields)
        elif isinstance(value, dict):
            children = value.values()
        elif isinstance(value, (list, tuple)):
            children = value
        else:
            return
        for child in children:
            rebind(child)

    rebind(completed)
    for name in type(completed).model_fields:
        _bind_mutation_root(getattr(completed, name), completed, name, (name,))
    return completed


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
    memo: dict[int, Any],
) -> None:
    if not parts:
        return

    top_level = parts[0]
    source_value = getattr(source_state, top_level, _MISSING)
    target_value = getattr(target_state, top_level, _MISSING)
    if source_value is _MISSING or target_value is _MISSING:
        return

    if len(parts) == 1:
        setattr(target_state, top_level, deepcopy(source_value, memo))
        return

    _ensure_isolated_container(
        source_parent=source_value,
        target_parent=target_value,
        parts=parts[1:],
        memo=memo,
    )


def _ensure_isolated_container(
    *,
    source_parent: Any,
    target_parent: Any,
    parts: tuple[str, ...],
    memo: dict[int, Any],
) -> None:
    if not parts:
        return

    part = parts[0]
    source_child = _get_child(source_parent, part)
    if source_child is _MISSING:
        return

    target_child = _get_child(target_parent, part)
    if target_child is source_child:
        cloned = _clone_container(source_child, deep=len(parts) == 1, memo=memo)
        _set_child(target_parent, part, cloned)
        target_child = cloned
    elif target_child is _MISSING:
        target_child = _clone_container(source_child, deep=len(parts) == 1, memo=memo)
        _set_child(target_parent, part, target_child)

    if len(parts) > 1 and _is_branchable_container(target_child):
        _ensure_isolated_container(
            source_parent=source_child,
            target_parent=target_child,
            parts=parts[1:],
            memo=memo,
        )


def _get_child(container: Any, key: str) -> Any:
    if isinstance(container, BaseModel):
        return getattr(container, key, _MISSING)
    if isinstance(container, dict):
        return container.get(key, _MISSING)
    if isinstance(container, (list, tuple)):
        try:
            return container[int(key)]
        except (IndexError, TypeError, ValueError):
            return _MISSING
    return _MISSING


def _set_child(container: Any, key: str, value: Any) -> None:
    if isinstance(container, BaseModel):
        setattr(container, key, value)
        return
    if isinstance(container, dict):
        dict.__setitem__(container, key, value)
        if isinstance(container, _TrackedDict):
            _bind_mutation_parent(value, container)
        return
    if isinstance(container, list):
        list.__setitem__(container, int(key), value)
        if isinstance(container, _TrackedList):
            _bind_mutation_parent(value, container)
        return
    raise TypeError(f"Cannot assign nested state field {key!r} on {type(container).__name__}")


def _clone_container(value: Any, *, deep: bool = False, memo: dict[int, Any]) -> Any:
    if id(value) in memo:
        return memo[id(value)]
    if deep:
        return deepcopy(value, memo)
    clone: Any
    if isinstance(value, dict):
        clone = dict(value)
    elif isinstance(value, list):
        clone = list(value)
    elif isinstance(value, tuple):
        clone = tuple(value)
    elif isinstance(value, set):
        clone = set(value)
    elif isinstance(value, BaseModel):
        # Preserve copy-on-write behavior for nested models: clone only the
        # model shell here and let deeper path isolation materialize mutable
        # children lazily as traversal reaches them.
        clone = value.model_copy(deep=False)
    else:
        clone = deepcopy(value, memo)
    memo[id(value)] = clone
    return clone


def _is_branchable_container(value: Any) -> bool:
    return isinstance(value, (BaseModel, dict, list, tuple, set))


def _attach_mutation_journal(state: ExperimentState, journal: StateMutationJournal) -> None:
    """Attach a private journal without widening the public state contract."""
    object.__setattr__(state, _MUTATION_JOURNAL_ATTR, journal)


def _promote_to_journaled_state(state: ExperimentState) -> ExperimentState:
    if not isinstance(state, _JournaledExperimentState):
        state.__class__ = _JournaledExperimentState
    return state


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
    operations = list(operations)
    groups: dict[int, bytes] = {}
    for operation in operations:
        if operation.operation_group is None:
            continue
        intent = to_canonical_bytes(
            operation.model_dump(exclude={"path", "operation_group"}),
            _JOURNAL_INTENT_CANON,
        )
        previous = groups.setdefault(operation.operation_group, intent)
        if previous != intent:
            raise ValueError("inconsistent state mutation operation group")
    return StateMutationJournal(
        isolated_fields=(),
        isolated_paths=(),
        operations=operations,
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
    """Preserve the branch's JSON graph while guarding every mutable neighbor.

    Views do not expand the declared write paths.  A single memo reconciles
    isolated descendants with aliases reached through other parents, so an
    out-of-scope alias is checked before either location can change.
    """
    if journal.enforce_write_scope:
        for field_name in type(state).model_fields:
            value = getattr(state, field_name, None)
            if isinstance(value, (dict, list, tuple, BaseModel)):
                _validate_mutation_attachment(None, value)
                _set_path(state, (field_name,), _wrap_mutable_value(value, (field_name,), journal))
    for parts in paths:
        for length in range(1, len(parts)):
            prefix = parts[:length]
            parent = _get_path(state, prefix)
            if isinstance(parent, dict) and not isinstance(parent, _TrackedDict):
                _set_path(
                    state,
                    prefix,
                    _TrackedDict(parent, path=prefix, journal=journal, recursive=False),
                )
            elif isinstance(parent, list) and not isinstance(parent, _TrackedList):
                _set_path(
                    state,
                    prefix,
                    _TrackedList(parent, path=prefix, journal=journal, recursive=False),
                )
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
    return isinstance(value, (dict, list, set, BaseModel))


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
        if isinstance(root, BaseModel):
            _bind_mutation_root(value, root, parts[0], parts)
        return
    parent = _get_path(root, parts[:-1])
    if parent is _MISSING:
        return
    _set_child(parent, parts[-1], value)
    if isinstance(parent, BaseModel):
        _bind_mutation_root(value, parent, parts[-1], parts)


def _normalize_artifacts_index_ref(path: tuple[str, ...], value: Any) -> Any:
    """Normalize typed IR refs at the artifacts-index mutation boundary."""
    if path != ("artifacts_index",) or not isinstance(value, ArtifactRefModel):
        return value
    return ArtifactRef.model_validate(value.model_dump(mode="python"))


class _TrackedDict(dict[Any, Any]):
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
        self._mutation_owners: list[tuple[Any, Any, tuple[str, ...]]] = []
        self._mutation_roots: list[tuple[BaseModel, str, tuple[str, ...]]] = []
        journal._wrapped_values[id(values)] = (values, self)
        for key, value in values.items():
            dict.__setitem__(
                self,
                key,
                _wrap_mutable_value(value, (*path, str(key)), journal) if recursive else value,
            )
            _bind_mutation_parent(dict.__getitem__(self, key), self)

    def __setitem__(self, key: str, value: Any) -> None:
        _authorize_container_mutation(self, suffixes=((str(key),),))
        _validate_mutation_attachment(self, value)
        previous = self.get(key, _MISSING)
        value = _normalize_artifacts_index_ref(self._mutation_path, value)
        wrapped = _wrap_mutable_value(
            value,
            (*self._mutation_path, str(key)),
            self._mutation_journal,
        )
        dict.__setitem__(self, key, wrapped)
        _bind_mutation_parent(wrapped, self)
        _record_container_mutation(
            self,
            suffix=(str(key),),
            operation="set",
            value=value,
            target=previous,
        )

    def __delitem__(self, key: str) -> None:
        _authorize_container_mutation(self, suffixes=((str(key),),))
        previous = self[key]
        dict.__delitem__(self, key)
        _record_container_mutation(
            self,
            suffix=(str(key),),
            operation="delete",
            target=previous,
        )

    def update(self, *args: Any, **kwargs: Any) -> None:
        values = dict(*args, **kwargs)
        _authorize_container_mutation(self, suffixes=[(str(key),) for key in values])
        for value in values.values():
            _validate_mutation_attachment(self, value)
        for key, value in values.items():
            self[key] = value

    # Like builtins.dict in typeshed, |= accepts update inputs wider than |.
    def __ior__(self, values: Any) -> Self:  # type: ignore[misc]
        self.update(values)
        return self

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
        _authorize_container_mutation(self, suffixes=((str(key),),))
        value = dict.pop(self, key)
        _record_container_mutation(
            self,
            suffix=(str(key),),
            operation="delete",
            target=value,
        )
        return value

    def popitem(self) -> tuple[str, Any]:
        if self:
            _authorize_container_mutation(self, suffixes=((str(next(reversed(self))),),))
        key, value = dict.popitem(self)
        _record_container_mutation(
            self,
            suffix=(str(key),),
            operation="delete",
            target=value,
        )
        return key, value

    def clear(self) -> None:
        items = list(self.items())
        _authorize_container_mutation(self, suffixes=[(str(key),) for key, _ in items])
        dict.clear(self)
        for key, value in items:
            _record_container_mutation(
                self,
                suffix=(str(key),),
                operation="delete",
                target=value,
            )

    def __deepcopy__(self, memo: dict[int, Any]) -> _TrackedDict:
        existing = memo.get(id(self))
        if existing is not None:
            return cast("_TrackedDict", existing)
        clone = _TrackedDict.__new__(_TrackedDict)
        memo[id(self)] = clone
        clone._mutation_path = self._mutation_path
        clone._mutation_journal = self._mutation_journal
        clone._mutation_owners = []
        clone._mutation_roots = []
        dict.__init__(clone)
        for key, value in self.items():
            dict.__setitem__(clone, deepcopy(key, memo), deepcopy(value, memo))
            _bind_mutation_parent(dict.__getitem__(clone, key), clone)
        return clone


class _TrackedList(list[Any]):
    """List view that records replayable element/container operations."""

    def __init__(
        self,
        values: list[Any],
        *,
        path: tuple[str, ...],
        journal: StateMutationJournal,
        recursive: bool = True,
    ) -> None:
        list.__init__(self)
        self._mutation_path = path
        self._mutation_journal = journal
        self._mutation_owners: list[tuple[Any, Any, tuple[str, ...]]] = []
        self._mutation_roots: list[tuple[BaseModel, str, tuple[str, ...]]] = []
        journal._wrapped_values[id(values)] = (values, self)
        for index, value in enumerate(values):
            list.append(
                self,
                _wrap_mutable_value(value, (*path, str(index)), journal) if recursive else value,
            )
            _bind_mutation_parent(list.__getitem__(self, index), self)

    def __setitem__(self, index: SupportsIndex | slice, value: Any) -> None:
        _authorize_container_mutation(self)
        if isinstance(index, slice):
            values = list(value)
            for child in values:
                _validate_mutation_attachment(self, child)
            list.__setitem__(
                self,
                index,
                [
                    _wrap_mutable_value(
                        item,
                        (*self._mutation_path, str(i)),
                        self._mutation_journal,
                    )
                    for i, item in enumerate(values)
                ],
            )
            for child in self:
                _bind_mutation_parent(child, self)
            _record_container_mutation(
                self,
                operation="set_slice",
                value=values,
                start=index.start,
                stop=index.stop,
                step=index.step,
                target=self,
            )
            return
        index = _index(index)
        _validate_mutation_attachment(self, value)
        list.__setitem__(
            self,
            index,
            _wrap_mutable_value(
                value,
                (*self._mutation_path, str(index)),
                self._mutation_journal,
            ),
        )
        _bind_mutation_parent(list.__getitem__(self, index), self)
        _record_container_mutation(
            self,
            operation="set_index",
            value=value,
            index=index,
            target=self,
        )

    def __delitem__(self, index: SupportsIndex | slice) -> None:
        _authorize_container_mutation(self)
        if not isinstance(index, slice):
            index = _index(index)
        list.__delitem__(self, index)
        if isinstance(index, slice):
            _record_container_mutation(
                self,
                operation="delete_slice",
                start=index.start,
                stop=index.stop,
                step=index.step,
                target=self,
            )
        else:
            _record_container_mutation(
                self,
                operation="delete_index",
                index=index,
                target=self,
            )

    def append(self, value: Any) -> None:
        _authorize_container_mutation(self)
        _validate_mutation_attachment(self, value)
        list.append(
            self,
            _wrap_mutable_value(
                value,
                (*self._mutation_path, str(len(self))),
                self._mutation_journal,
            ),
        )
        _bind_mutation_parent(list.__getitem__(self, -1), self)
        _record_container_mutation(
            self,
            operation="append",
            value=value,
            target=self,
        )

    def extend(self, values: Iterable[Any]) -> None:
        _authorize_container_mutation(self)
        values_list = list(values)
        for value in values_list:
            _validate_mutation_attachment(self, value)
        for value in values_list:
            self.append(value)

    def insert(self, index: SupportsIndex, value: Any) -> None:
        index = _index(index)
        _authorize_container_mutation(self)
        _validate_mutation_attachment(self, value)
        list.insert(
            self,
            index,
            _wrap_mutable_value(value, (*self._mutation_path, str(index)), self._mutation_journal),
        )
        for child in self:
            _bind_mutation_parent(child, self)
        _record_container_mutation(
            self,
            operation="insert",
            value=value,
            index=index,
            target=self,
        )

    def pop(self, index: SupportsIndex = -1) -> Any:
        index = _index(index)
        _authorize_container_mutation(self)
        value = list.pop(self, index)
        _record_container_mutation(
            self,
            operation="pop",
            index=index,
            target=self,
        )
        return value

    def remove(self, value: Any) -> None:
        _authorize_container_mutation(self)
        list.remove(self, value)
        _record_container_mutation(
            self,
            operation="remove",
            value=value,
            target=self,
        )

    def clear(self) -> None:
        _authorize_container_mutation(self)
        list.clear(self)
        _record_container_mutation(self, operation="clear", target=self)

    def reverse(self) -> None:
        _authorize_container_mutation(self)
        list.reverse(self)
        _record_container_mutation(self, operation="reverse", target=self)

    def sort(self, *args: Any, **kwargs: Any) -> None:
        _authorize_container_mutation(self)
        list.sort(self, *args, **kwargs)
        _record_container_mutation(
            self,
            operation="replace",
            value=list(self),
            target=self,
        )

    # Like builtins.list in typeshed, += accepts iterables while + requires lists.
    def __iadd__(self, values: Iterable[Any]) -> Self:  # type: ignore[misc]
        self.extend(values)
        return self

    def __imul__(self, count: SupportsIndex) -> Self:
        count = _index(count)
        _authorize_container_mutation(self)
        list.__imul__(self, count)
        _record_container_mutation(
            self,
            operation="replace",
            value=list(self),
            target=self,
        )
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> _TrackedList:
        existing = memo.get(id(self))
        if existing is not None:
            return cast("_TrackedList", existing)
        clone = _TrackedList.__new__(_TrackedList)
        memo[id(self)] = clone
        clone._mutation_path = self._mutation_path
        clone._mutation_journal = self._mutation_journal
        clone._mutation_owners = []
        clone._mutation_roots = []
        list.__init__(clone)
        for value in self:
            list.append(clone, deepcopy(value, memo))
            _bind_mutation_parent(list.__getitem__(clone, -1), clone)
        return clone


class _TrackedModelMixin(BaseModel):
    """Guard the ordinary model field API over the same live owned graph.

    Concrete fields, validators and frozen config remain the original model's
    contract. Custom mutation/copy hooks and private runtime state are refused
    at admission; this finite profile is not a Python object sandbox.
    """

    __slots__ = (
        "_mutation_detached",
        "_mutation_journal",
        "_mutation_owners",
        "_mutation_path",
        "_mutation_roots",
    )

    _original_model_type: ClassVar[type[BaseModel]]
    _mutation_path: ClassVar[tuple[str, ...]]
    _mutation_journal: ClassVar[StateMutationJournal]
    _mutation_owners: ClassVar[list[Any]]
    _mutation_roots: ClassVar[list[Any]]
    _mutation_detached: ClassVar[bool]

    def __setattr__(self, name: str, value: Any) -> None:
        if not self._mutation_journal.enforce_write_scope or type(self).model_config.get("frozen"):
            super().__setattr__(name, value)
            return
        journal = self._mutation_journal
        if name not in self._original_model_type.model_fields:
            raise TypeError("state mutation journaling requires a declared model field")
        _authorize_container_mutation(self, suffixes=((name,),))
        _validate_mutation_attachment(self, value)
        previous = getattr(self, name, _MISSING)
        wrapped = _wrap_mutable_value(value, (*self._mutation_path, name), journal)
        before_fields = self.__dict__.copy()
        before_fields_set = self.__pydantic_fields_set__.copy()
        before_extra = None if self.__pydantic_extra__ is None else self.__pydantic_extra__.copy()
        try:
            super().__setattr__(name, wrapped)
            stored = getattr(self, name)
            _validate_mutation_attachment(self, stored)
            reconciled = _wrap_mutable_value(stored, (*self._mutation_path, name), journal)
            self.__dict__[name] = reconciled
        except Exception:
            # Validation can materialize a different field representation.
            # Refuse unsupported results without retaining a partial field edit.
            object.__setattr__(self, "__dict__", before_fields)
            object.__setattr__(self, "__pydantic_fields_set__", before_fields_set)
            object.__setattr__(self, "__pydantic_extra__", before_extra)
            raise
        _bind_mutation_parent(reconciled, self)
        _record_container_mutation(
            self, suffix=(name,), operation="set", value=reconciled, target=previous
        )

    def __delattr__(self, name: str) -> None:
        if not self._mutation_journal.enforce_write_scope or type(self).model_config.get("frozen"):
            super().__delattr__(name)
            return
        _authorize_container_mutation(self, suffixes=((name,),))
        raise TypeError("model field deletion is not replayable")

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        if not self._mutation_journal.enforce_write_scope:
            return super().model_copy(update=update, deep=deep)
        if any(name not in self._original_model_type.model_fields for name in update or ()):
            raise TypeError("state mutation journaling requires a declared model field")
        _authorize_container_mutation(self, suffixes=((name,) for name in update or ()))
        for value in (update or {}).values():
            _validate_mutation_attachment(None, value)
        copied = super().model_copy(deep=deep)
        # A detached copy is not an alias in the original state. Its setters
        # retain the original logical scope until an actual parent attaches it.
        object.__setattr__(copied, "_mutation_owners", [])
        object.__setattr__(copied, "_mutation_roots", [])
        object.__setattr__(copied, "_mutation_detached", True)
        for name in type(copied).model_fields:
            _bind_mutation_parent(getattr(copied, name), copied)
        for name, value in (update or {}).items():
            if type(copied).model_config.get("frozen"):
                # Frozen models still support their ordinary copy-with-update
                # API; only the new detached model receives the updated field.
                previous = getattr(copied, name)
                wrapped = _wrap_mutable_value(
                    value, (*copied._mutation_path, name), copied._mutation_journal
                )
                copied.__dict__[name] = wrapped
                copied.__pydantic_fields_set__.add(name)
                _bind_mutation_parent(wrapped, copied)
                _record_container_mutation(
                    copied, suffix=(name,), operation="set", value=value, target=previous
                )
            else:
                setattr(copied, name, value)
        return copied

    def __copy__(self) -> Self:
        copied = super().__copy__()
        _initialize_model_tracking(copied, self._mutation_path, self._mutation_journal)
        object.__setattr__(copied, "_mutation_detached", True)
        for name in type(copied).model_fields:
            _bind_mutation_parent(getattr(copied, name), copied)
        return copied

    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> Self:
        memo = {} if memo is None else memo
        existing = memo.get(id(self))
        if existing is not None:
            return cast("Self", existing)
        clone = super().__deepcopy__(memo)
        memo[id(self)] = clone
        _initialize_model_tracking(clone, self._mutation_path, self._mutation_journal)
        object.__setattr__(clone, "_mutation_detached", True)
        for name in type(clone).model_fields:
            _bind_mutation_parent(getattr(clone, name), clone)
        return clone


_TRACKED_MODEL_TYPES: dict[type[BaseModel], type[BaseModel]] = {}


def _ordinary_model_type(value: BaseModel) -> type[BaseModel]:
    original = value._original_model_type if isinstance(value, _TrackedModelMixin) else type(value)
    if type(original) is not type(BaseModel):
        raise TypeError("state mutation journaling requires the canonical BaseModel metaclass")
    hooks = (
        "__new__",
        "__init_subclass__",
        "__pydantic_init_subclass__",
        "__pydantic_on_complete__",
        "__get_pydantic_core_schema__",
        "__get_pydantic_json_schema__",
        "__setattr__",
        "__delattr__",
        "__getattribute__",
        "__copy__",
        "__deepcopy__",
        "model_copy",
        "model_construct",
        "model_post_init",
    )

    def implementation(model: type[BaseModel], name: str) -> Any:
        # Compare raw MRO descriptors before binding or executing custom class
        # hooks. Builtin class-bound methods otherwise compare their receiver.
        hook = getattr_static(model, name)
        return hook.__func__ if isinstance(hook, (classmethod, staticmethod)) else hook

    if any(
        not any(
            implementation(original, name) is implementation(canonical, name)
            for canonical in (BaseModel, RootModel)
        )
        for name in hooks
    ):
        raise TypeError("state mutation journaling requires ordinary BaseModel mutation/copy hooks")
    if value.__pydantic_private__ or value.__pydantic_extra__:
        raise TypeError("state mutation journaling refuses private or extra model runtime state")
    return original


def _initialize_model_tracking(
    value: BaseModel, path: tuple[str, ...], journal: StateMutationJournal
) -> None:
    object.__setattr__(value, "_mutation_path", path)
    object.__setattr__(value, "_mutation_journal", journal)
    object.__setattr__(value, "_mutation_owners", [])
    object.__setattr__(value, "_mutation_roots", [])
    object.__setattr__(value, "_mutation_detached", False)


def _model_members(value: BaseModel) -> Iterable[tuple[str, Any]]:
    return ((name, getattr(value, name)) for name in type(value).model_fields)


def _bind_mutation_root(value: Any, model: BaseModel, name: str, path: tuple[str, ...]) -> None:
    if isinstance(value, (_TrackedDict, _TrackedList, _TrackedModelMixin)) and not any(
        root is model and field == name for root, field, _ in value._mutation_roots
    ):
        value._mutation_roots.append((model, name, path))


def _bind_mutation_parent(
    value: Any,
    parent: _TrackedDict | _TrackedList | _TrackedModelMixin,
    *,
    owner_value: Any = _MISSING,
    suffix: tuple[str, ...] = (),
) -> None:
    """Retain live container ownership rather than an index captured before edits."""
    if isinstance(value, (_TrackedDict, _TrackedList, _TrackedModelMixin)):
        if value._mutation_journal is not parent._mutation_journal:
            return
        member = value if owner_value is _MISSING else owner_value
        if not any(
            owner is parent and owned_value is member and owned_suffix == suffix
            for owner, owned_value, owned_suffix in value._mutation_owners
        ):
            value._mutation_owners.append((parent, member, suffix))
    elif isinstance(value, tuple):
        for index, child in enumerate(value):
            _bind_mutation_parent(
                child,
                parent,
                owner_value=value if owner_value is _MISSING else owner_value,
                suffix=(*suffix, str(index)),
            )


def _current_mutation_paths(
    value: _TrackedDict | _TrackedList | _TrackedModelMixin,
    seen: frozenset[int] = frozenset(),
    *,
    include_detached: bool = False,
) -> list[tuple[str, ...]]:
    """Resolve every live location, or none for a removed descendant view."""
    if id(value) in seen:
        return []
    if not value._mutation_owners and not value._mutation_roots:
        if (
            isinstance(value, _TrackedModelMixin)
            and value._mutation_detached
            and not include_detached
        ):
            return []
        return [value._mutation_path]
    paths = [
        path
        for model, name, path in value._mutation_roots
        if getattr(model, name, _MISSING) is value
    ]
    for parent, owner_value, suffix in value._mutation_owners:
        parent_paths = _current_mutation_paths(
            parent, seen | {id(value)}, include_detached=include_detached
        )
        members = (
            _model_members(parent)
            if isinstance(parent, BaseModel)
            else parent.items()
            if isinstance(parent, dict)
            else enumerate(parent)
        )
        keys = [str(key) for key, child in members if child is owner_value]
        paths.extend((*path, key, *suffix) for path in parent_paths for key in keys)
    return list(dict.fromkeys(paths))


def _validate_mutation_attachment(
    container: _TrackedDict | _TrackedList | _TrackedModelMixin | None, value: Any
) -> None:
    """Reject a cyclic attachment before changing the finite owned JSON graph."""

    def visit(child: Any, ancestors: frozenset[int]) -> None:
        if isinstance(child, (set, bytearray)):
            raise TypeError("state mutation journaling requires a finite JSON container graph")
        if container is not None and child is container:
            raise ValueError("cyclic state mutation attachment")
        if isinstance(child, BaseModel):
            _ordinary_model_type(child)
        if not isinstance(child, (dict, list, tuple, BaseModel)):
            return
        if id(child) in ancestors:
            raise ValueError("cyclic state mutation value")
        nested = (
            (value for _, value in _model_members(child))
            if isinstance(child, BaseModel)
            else child.values()
            if isinstance(child, dict)
            else child
        )
        for item in nested:
            visit(item, ancestors | {id(child)})

    visit(value, frozenset())


def _authorize_container_mutation(
    container: _TrackedDict | _TrackedList | _TrackedModelMixin,
    *,
    suffixes: Iterable[tuple[str, ...]] = ((),),
) -> None:
    """Refuse a moved or aliased live target before changing any branch bytes."""
    if not container._mutation_journal.enforce_write_scope:
        return
    declared = [tuple(path.split(".")) for path in container._mutation_journal.isolated_paths]
    suffixes = tuple(suffixes)
    paths = [
        (*path, *suffix)
        for path in _current_mutation_paths(container, include_detached=True)
        for suffix in suffixes
    ]
    unauthorized = [
        path for path in paths if not any(_is_path_prefix(write, path) for write in declared)
    ]
    if unauthorized:
        raise ValueError(
            f"undeclared state_writes at live paths: {['.'.join(p) for p in unauthorized]}"
        )


def _record_container_mutation(
    container: _TrackedDict | _TrackedList | _TrackedModelMixin,
    *,
    suffix: tuple[str, ...] = (),
    **kwargs: Any,
) -> None:
    """Journal an intent against the current live state, preserving list aliases."""
    paths = _current_mutation_paths(container)
    group = len(container._mutation_journal.operations) if len(paths) > 1 else None
    for path in paths:
        container._mutation_journal.record(path=(*path, *suffix), operation_group=group, **kwargs)


def _wrap_mutable_value(
    value: Any,
    path: tuple[str, ...],
    journal: StateMutationJournal,
    *,
    recursive: bool = True,
) -> Any:
    value = journal._isolated_values.get(id(value), value)
    if (
        isinstance(value, (_TrackedDict, _TrackedList, _TrackedModelMixin))
        and value._mutation_journal is journal
    ):
        return value
    existing = journal._wrapped_values.get(id(value))
    if existing is not None and existing[0] is value:
        return existing[1]
    if isinstance(value, dict):
        return _TrackedDict(value, path=path, journal=journal, recursive=recursive)
    if isinstance(value, list):
        return _TrackedList(value, path=path, journal=journal, recursive=recursive)
    if isinstance(value, tuple):
        return tuple(
            _wrap_mutable_value(item, (*path, str(index)), journal)
            for index, item in enumerate(value)
        )
    if isinstance(value, BaseModel):
        original = _ordinary_model_type(value)
        tracked = _TRACKED_MODEL_TYPES.get(original)
        if tracked is None:
            tracked = type(
                f"_Journaled{original.__name__}",
                (_TrackedModelMixin, original),
                {"__module__": __name__, "_original_model_type": original},
            )
            _TRACKED_MODEL_TYPES[original] = tracked
        # Preserve already-validated fields without re-running constructors.
        wrapped = tracked.model_construct(
            _fields_set=set(value.__pydantic_fields_set__), **dict(_model_members(value))
        )
        _initialize_model_tracking(wrapped, path, journal)
        journal._wrapped_values[id(value)] = (value, wrapped)
        for name, child in _model_members(value):
            wrapped.__dict__[name] = _wrap_mutable_value(child, (*path, name), journal)
            _bind_mutation_parent(getattr(wrapped, name), cast("_TrackedModelMixin", wrapped))
        return wrapped
    return value


__all__ = [
    "BranchedState",
    "StateMutation",
    "StateMutationOperation",
    "StateMutationJournal",
    "StateMutationTargetKind",
    "StateMutationTargetPresence",
    "StateMutationValueKind",
    "branch_state",
    "mutation_journal_for_state",
    "mutation_journal_from_operations",
    "snapshot_state",
]

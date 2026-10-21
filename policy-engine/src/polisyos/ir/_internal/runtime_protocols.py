"""Runtime helpers for checking callable members declared by Protocols."""

from __future__ import annotations

import inspect
import types
from collections.abc import Callable
from typing import Annotated, Union, get_args, get_origin, get_protocol_members, get_type_hints

_MISSING = object()


def protocol_declared_callables_are_callable(
    candidate: object,
    protocol: type[object],
) -> bool:
    """Check callable Protocol methods and explicitly Callable-typed data members.

    Runtime-checkable Protocol membership verifies that attributes are present, but
    does not verify that a declared method or ``Callable`` field is callable. Data
    members with other annotations remain data and are not treated as methods.
    """
    try:
        members = get_protocol_members(protocol)
        annotations = get_type_hints(protocol, include_extras=True)
    except (NameError, TypeError):
        return False

    for name in members:
        if name in annotations:
            allows_none = _callable_annotation_allows_none(annotations[name])
            if allows_none is None:
                continue
            value = getattr(candidate, name, None)
            if allows_none and value is None:
                continue
            if not callable(value):
                return False
            continue

        declared_member = inspect.getattr_static(protocol, name, _MISSING)
        if isinstance(declared_member, property):
            getter = declared_member.fget
            if getter is None:
                continue
            try:
                return_annotation = get_type_hints(getter, include_extras=True).get("return")
            except (NameError, TypeError):
                return False
            allows_none = _callable_annotation_allows_none(return_annotation)
            if allows_none is None:
                continue
            value = getattr(candidate, name, None)
            if allows_none and value is None:
                continue
            if not callable(value):
                return False
            continue

        if (
            inspect.isroutine(declared_member)
            or isinstance(declared_member, (classmethod, staticmethod))
        ) and (not callable(getattr(candidate, name, None))):
            return False

    return True


def _callable_annotation_allows_none(annotation: object) -> bool | None:
    """Classify callable-only annotations, preserving optional ``None`` values."""
    origin = get_origin(annotation)
    if origin is Annotated:
        arguments = get_args(annotation)
        return _callable_annotation_allows_none(arguments[0]) if arguments else None

    if origin in {Union, types.UnionType}:
        arguments = get_args(annotation)
        allows_none = type(None) in arguments
        non_none = tuple(argument for argument in arguments if argument is not type(None))
        if non_none and all(_callable_annotation_allows_none(arg) is False for arg in non_none):
            return allows_none
        return None

    if annotation is Callable or origin is Callable:
        return False
    return None

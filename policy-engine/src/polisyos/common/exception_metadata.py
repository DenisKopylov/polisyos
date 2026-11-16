"""Minimal access to exception storage for owner-emitted diagnostic metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_EXCEPTION_CAUSE_MAX_DEPTH = 6
_SAFE_EXCEPTION_CODE = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]{0,127}\Z")
_SAFE_EXCEPTION_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_.<>]{0,255}\Z")
_TYPE_MODULE_DESCRIPTOR = type.__dict__["__module__"]
_TYPE_QUALNAME_DESCRIPTOR = type.__dict__["__qualname__"]
_BASE_EXCEPTION_CAUSE_DESCRIPTOR = BaseException.__dict__["__cause__"]
_BASE_EXCEPTION_CONTEXT_DESCRIPTOR = BaseException.__dict__["__context__"]
_BASE_EXCEPTION_SUPPRESS_CONTEXT_DESCRIPTOR = BaseException.__dict__["__suppress_context__"]


@dataclass(frozen=True, slots=True)
class _ExceptionCauseNode:
    """Hold one exception and bounded identity metadata for owner-side inspection.

    The live exception object is intentionally excluded from repr/equality: it
    is an internal handle for the caller's exact-type recognizers, not output.
    """

    error: BaseException = field(repr=False, compare=False)
    exception_type: str
    code: str


def _safe_exception_type(error: BaseException) -> str:
    """Return a bounded type label without consulting exception/metaclass hooks."""
    error_type = type(error)
    try:
        module = _TYPE_MODULE_DESCRIPTOR.__get__(error_type, type)
        qualname = _TYPE_QUALNAME_DESCRIPTOR.__get__(error_type, type)
    except Exception:
        return "not_established"
    if type(module) is not str or type(qualname) is not str:
        return "not_established"
    label = f"{module}.{qualname}"
    return label if _SAFE_EXCEPTION_TYPE.fullmatch(label) else "not_established"


def _safe_exception_code(error: BaseException) -> str:
    """Read only a validated code stored directly on the exception instance."""
    metadata = _exception_instance_dict(error)
    code = metadata.get("code") if metadata is not None else None
    return code if type(code) is str and _SAFE_EXCEPTION_CODE.fullmatch(code) else "not_established"


def _next_exception_cause(error: BaseException) -> tuple[BaseException | None, str]:
    """Read base exception storage without consulting subclass descriptors."""
    try:
        cause = _BASE_EXCEPTION_CAUSE_DESCRIPTOR.__get__(error, BaseException)
        if cause is not None:
            if isinstance(cause, BaseException):
                return cause, "cause"
            return None, "access_not_established"
        suppressed = _BASE_EXCEPTION_SUPPRESS_CONTEXT_DESCRIPTOR.__get__(error, BaseException)
        context = _BASE_EXCEPTION_CONTEXT_DESCRIPTOR.__get__(error, BaseException)
    except Exception:
        return None, "access_not_established"
    if type(suppressed) is not bool or (
        context is not None and not isinstance(context, BaseException)
    ):
        return None, "access_not_established"
    if suppressed:
        return None, "context_suppressed"
    if isinstance(context, BaseException):
        return context, "context"
    return None, "no_linked_cause"


def _bounded_exception_cause_nodes(
    error: BaseException,
) -> tuple[tuple[_ExceptionCauseNode, ...], str]:
    """Observe a bounded exception cause/context chain without message access.

    The returned error handles are for caller-owned exact-type inspection only.
    This primitive does not classify causes, authorize retries, or establish
    whether the underlying work completed.
    """
    nodes: list[_ExceptionCauseNode] = []
    seen: set[int] = set()
    current = error
    for _ in range(_EXCEPTION_CAUSE_MAX_DEPTH):
        identity = id(current)
        if identity in seen:
            return tuple(nodes), "cycle_detected"
        seen.add(identity)
        nodes.append(
            _ExceptionCauseNode(
                error=current,
                exception_type=_safe_exception_type(current),
                code=_safe_exception_code(current),
            )
        )
        following, termination = _next_exception_cause(current)
        if following is None:
            return tuple(nodes), termination
        if id(following) in seen:
            return tuple(nodes), "cycle_detected"
        current = following
    return tuple(nodes), "depth_limited"


def _exception_instance_dict(error: BaseException) -> dict[str, object] | None:
    """Return real storage without invoking an exception subclass's hooks.

    Callers still own validation and authorization of any stored metadata. This
    primitive changes no args, cause, traceback, identity or public contract.
    """
    try:
        descriptor = BaseException.__dict__["__dict__"]
        metadata = descriptor.__get__(error)
    except Exception:
        return None
    return metadata if type(metadata) is dict else None

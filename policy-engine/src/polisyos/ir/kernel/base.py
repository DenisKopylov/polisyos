"""Public kernel base module API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

# Generic IR identifiers allow dots and hyphens for namespaced registry ids,
# artifact-friendly labels, and cross-module references.
ID_PATTERN = r"^[a-z][a-z0-9_.-]*$"
# Slot identifiers deliberately exclude ``-`` so runtime state paths remain
# unambiguous and path-like (e.g. ``agents.income``).
SLOT_ID_PATTERN = r"^[a-z][a-z0-9_.]*$"
ARTIFACT_ID_PATTERN = r"^sha256:[0-9a-f]{64}$"


class KernelModel(BaseModel):
    """Kernel model public type."""
    model_config = ConfigDict(extra="forbid", frozen=True)


def reject_float(value: Any) -> Any:
    """Reject float helper."""
    if isinstance(value, float):
        raise ValueError("float forbidden; use string or int")
    return value


def reject_floats_deep(value: Any, *, max_depth: int = 128, _depth: int = 0) -> Any:
    """Reject floats deep helper."""
    if _depth > max_depth:
        raise ValueError(f"float validation depth exceeds max_depth={max_depth}")
    if isinstance(value, float):
        raise ValueError("float forbidden; use string or int")
    if isinstance(value, BaseModel):
        reject_floats_deep(
            value.model_dump(mode="python", round_trip=True),
            max_depth=max_depth,
            _depth=_depth + 1,
        )
        return value
    if isinstance(value, (list, tuple)):
        for item in value:
            reject_floats_deep(item, max_depth=max_depth, _depth=_depth + 1)
        return value
    if isinstance(value, (set, frozenset)):
        for item in value:
            reject_floats_deep(item, max_depth=max_depth, _depth=_depth + 1)
        return value
    if isinstance(value, dict):
        for item in value.values():
            reject_floats_deep(item, max_depth=max_depth, _depth=_depth + 1)
        return value
    return value

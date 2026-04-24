"""Executor data models and shared low-level CAS helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from polisyos.core.artifacts.environment import EnvironmentManifestRef
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import ConstraintReportRef
from polisyos.foundry.methods.exceptions import StatePathTraversalError

__all__ = [
    "ApplyArtifacts",
    "ExecuteArtifacts",
    "ExecutionStrictness",
    "FailureCard",
    "FailureKind",
    "FailureSeverity",
    "artifact_id",
    "get_state_path",
    "load_model",
    "load_payload",
    "load_tensor",
    "put_tensor",
    "set_state_path",
]


class FailureSeverity(str, Enum):
    """Severity classification for method execution failures."""

    FATAL = "fatal"
    RECOVERABLE = "recoverable"
    DEGRADED = "degraded"


class FailureKind(str, Enum):
    """Typed failure family used for executor diagnostics."""

    VALIDATION = "validation"
    CONTRACT = "contract"
    SELECTOR = "selector"
    PATH = "path"
    LIFECYCLE = "lifecycle"
    ROUTING = "routing"
    BACKEND = "backend"
    NUMERICAL = "numerical"
    DEPENDENCY = "dependency"
    INTERNAL = "internal"


class FailureCard(BaseModel, frozen=True, extra="forbid"):
    """Structured failure report for a method node execution."""

    node_id: str
    method_fqn: str
    severity: FailureSeverity
    failure_kind: FailureKind = FailureKind.INTERNAL
    error_type: str
    error_message: str
    traceback_hash: str
    timestamp: float
    retry_eligible: bool
    suggested_fallback: str | None = None
    mechanism_type: str | None = None
    op_kind: str | None = None
    slot_context: tuple[str, ...] = ()
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutionStrictness(str, Enum):
    """Configurable strictness level for program graph execution."""

    FAIL_CLOSED = "fail_closed"
    DEGRADED = "degraded"
    RESEARCH = "research"


@dataclass(frozen=True)
class ExecuteArtifacts:
    """CAS references and diagnostics produced by an execute call."""

    state_delta_ref: ArtifactRef
    metrics_ref: ArtifactRef
    derived_artifacts: tuple[tuple[str, ArtifactRef], ...] = ()
    constraint_report_ref: ConstraintReportRef | None = None
    constraint_hard_fail: bool = False
    environment_ref: EnvironmentManifestRef | None = None
    environment_fingerprint: str | None = None
    failure_cards: tuple[FailureCard, ...] = ()
    degradation_cards: tuple[FailureCard, ...] = ()
    is_degraded: bool = False
    provenance: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class ApplyArtifacts:
    """CAS references produced after applying state changes."""

    state_snapshot_ref: ArtifactRef


# ---------------------------------------------------------------------------
# Shared low-level CAS helpers
# ---------------------------------------------------------------------------


def artifact_id(value: ArtifactRef | ArtifactID | str) -> ArtifactID:
    """Normalize artifact refs and strings into an ArtifactID instance."""
    if isinstance(value, ArtifactRef):
        return value.artifact_id
    if isinstance(value, ArtifactID):
        return value
    return ArtifactID.model_validate(value)


def load_model(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str, model_cls):
    """Load model."""
    data = store.get_bytes(artifact_id(ref))
    payload = from_canonical_bytes(data)
    return model_cls.model_validate(payload)


def load_payload(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str) -> dict[str, Any]:
    """Load payload."""
    data = store.get_bytes(artifact_id(ref))
    payload = from_canonical_bytes(data)
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    if isinstance(payload, dict):
        return payload
    raise ValueError("Invalid intervention payload")


def put_tensor(store: FileSystemCAS, value: Any) -> ArtifactRef:
    """Persist an array-like value as a NumPy tensor artifact."""
    array = np.asarray(value)
    buf = BytesIO()
    np.save(buf, array, allow_pickle=False)
    data = buf.getvalue()
    return store.put_bytes(
        data,
        PutOptions(kind="foundry.patch_value", media_type="application/x-npy"),
    )


def load_tensor(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str) -> np.ndarray:
    """Load tensor."""
    data = store.get_bytes(artifact_id(ref))
    return np.load(BytesIO(data), allow_pickle=False)


# ---------------------------------------------------------------------------
# State path traversal
# ---------------------------------------------------------------------------


def get_state_path(obj: Any, path: str) -> Any:
    """Return state path."""
    if not isinstance(path, str) or not path.strip():
        raise StatePathTraversalError(str(path), operation="read")
    current = obj
    for index, part in enumerate(path.split(".")):
        if not part:
            raise StatePathTraversalError(
                path,
                segment=part,
                segment_index=index,
                current_type=type(current).__name__,
                operation="read",
            )
        if not hasattr(current, part):
            raise StatePathTraversalError(
                path,
                segment=part,
                segment_index=index,
                current_type=type(current).__name__,
                operation="read",
            )
        current = getattr(current, part)
    return current


def set_state_path(obj: Any, path: str, value: Any) -> Any:
    """Return a dataclass-updated state with one dotted path replaced."""
    if not isinstance(path, str) or not path.strip():
        raise StatePathTraversalError(str(path), operation="write")
    return _set_state_path_parts(obj, path, path.split("."), value, segment_offset=0)


def _set_state_path_parts(
    obj: Any,
    full_path: str,
    parts: list[str],
    value: Any,
    *,
    segment_offset: int,
) -> Any:
    if len(parts) == 1:
        segment = parts[0]
        if not segment or not hasattr(obj, segment):
            raise StatePathTraversalError(
                full_path,
                segment=segment,
                segment_index=segment_offset,
                current_type=type(obj).__name__,
                operation="write",
            )
        if not hasattr(obj, "replace"):
            raise StatePathTraversalError(
                full_path,
                segment=segment,
                segment_index=segment_offset,
                current_type=type(obj).__name__,
                operation="write",
            )
        return obj.replace(**{segment: value})
    head, tail = parts[0], parts[1:]
    if not head or not hasattr(obj, head):
        raise StatePathTraversalError(
            full_path,
            segment=head,
            segment_index=segment_offset,
            current_type=type(obj).__name__,
            operation="write",
        )
    child = getattr(obj, head)
    updated = _set_state_path_parts(
        child,
        full_path,
        tail,
        value,
        segment_offset=segment_offset + 1,
    )
    if not hasattr(obj, "replace"):
        raise StatePathTraversalError(
            full_path,
            segment=head,
            segment_index=segment_offset,
            current_type=type(obj).__name__,
            operation="write",
        )
    return obj.replace(**{head: updated})

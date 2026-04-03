"""Executor data models and shared low-level CAS helpers."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from typing import Any

import numpy as np
from pydantic import BaseModel

from polisyos.core.artifacts.environment import EnvironmentManifestRef
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import ConstraintReportRef

__all__ = [
    "ExecuteArtifacts",
    "ApplyArtifacts",
    "FailureSeverity",
    "FailureCard",
    "ExecutionStrictness",
    "artifact_id",
    "load_model",
    "load_payload",
    "put_tensor",
    "load_tensor",
    "get_state_path",
    "set_state_path",
]


class FailureSeverity(str, Enum):
    """Severity classification for method execution failures."""

    FATAL = "fatal"
    RECOVERABLE = "recoverable"
    DEGRADED = "degraded"


class FailureCard(BaseModel, frozen=True, extra="forbid"):
    """Structured failure report for a method node execution."""

    node_id: str
    method_fqn: str
    severity: FailureSeverity
    error_type: str
    error_message: str
    traceback_hash: str
    timestamp: float
    retry_eligible: bool
    suggested_fallback: str | None = None


class ExecutionStrictness(str, Enum):
    """Configurable strictness level for program graph execution."""

    FAIL_CLOSED = "fail_closed"
    DEGRADED = "degraded"
    RESEARCH = "research"


@dataclass(frozen=True)
class ExecuteArtifacts:
    """Execute artifacts public type."""
    state_delta_ref: ArtifactRef
    metrics_ref: ArtifactRef
    constraint_report_ref: ConstraintReportRef | None = None
    constraint_hard_fail: bool = False
    environment_ref: EnvironmentManifestRef | None = None
    environment_fingerprint: str | None = None
    failure_cards: tuple[FailureCard, ...] = ()
    is_degraded: bool = False
    provenance: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class ApplyArtifacts:
    """Apply artifacts public type."""
    state_snapshot_ref: ArtifactRef


# ---------------------------------------------------------------------------
# Shared low-level CAS helpers
# ---------------------------------------------------------------------------


def artifact_id(value: ArtifactRef | ArtifactID | str) -> ArtifactID:
    """Artifact ID helper."""
    if isinstance(value, ArtifactRef):
        return value.artifact_id
    if isinstance(value, ArtifactID):
        return value
    return ArtifactID.model_validate(value)


def load_model(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str, model_cls):  # noqa: ANN201
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
    """Put tensor helper."""
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
    current = obj
    for part in path.split("."):
        current = getattr(current, part)
    return current


def set_state_path(obj: Any, path: str, value: Any) -> Any:
    """Set state path helper."""
    parts = path.split(".")
    if len(parts) == 1:
        return obj.replace(**{parts[0]: value})
    head, tail = parts[0], parts[1:]
    child = getattr(obj, head)
    updated = set_state_path(child, ".".join(tail), value)
    return obj.replace(**{head: updated})

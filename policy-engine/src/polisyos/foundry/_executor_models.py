"""Executor data models and shared low-level CAS helpers."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import numpy as np
from pydantic import BaseModel

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.foundry import ConstraintReportRef
from polisyos.core.artifacts.environment import EnvironmentManifestRef

__all__ = [
    "ExecuteArtifacts",
    "ApplyArtifacts",
    "artifact_id",
    "load_model",
    "load_payload",
    "put_tensor",
    "load_tensor",
    "get_state_path",
    "set_state_path",
]


@dataclass(frozen=True)
class ExecuteArtifacts:
    state_delta_ref: ArtifactRef
    metrics_ref: ArtifactRef
    constraint_report_ref: ConstraintReportRef | None = None
    environment_ref: EnvironmentManifestRef | None = None
    environment_fingerprint: str | None = None


@dataclass(frozen=True)
class ApplyArtifacts:
    state_snapshot_ref: ArtifactRef


# ---------------------------------------------------------------------------
# Shared low-level CAS helpers
# ---------------------------------------------------------------------------


def artifact_id(value: ArtifactRef | ArtifactID | str) -> ArtifactID:
    if isinstance(value, ArtifactRef):
        return value.artifact_id
    if isinstance(value, ArtifactID):
        return value
    return ArtifactID.model_validate(value)


def load_model(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str, model_cls):  # noqa: ANN201
    data = store.get_bytes(artifact_id(ref))
    payload = from_canonical_bytes(data)
    return model_cls.model_validate(payload)


def load_payload(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str) -> dict[str, Any]:
    data = store.get_bytes(artifact_id(ref))
    payload = from_canonical_bytes(data)
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    if isinstance(payload, dict):
        return payload
    raise ValueError("Invalid intervention payload")


def put_tensor(store: FileSystemCAS, value: Any) -> ArtifactRef:
    array = np.asarray(value)
    buf = BytesIO()
    np.save(buf, array, allow_pickle=False)
    data = buf.getvalue()
    return store.put_bytes(
        data,
        PutOptions(kind="foundry.patch_value", media_type="application/x-npy"),
    )


def load_tensor(store: FileSystemCAS, ref: ArtifactRef | ArtifactID | str) -> np.ndarray:
    data = store.get_bytes(artifact_id(ref))
    return np.load(BytesIO(data), allow_pickle=False)


# ---------------------------------------------------------------------------
# State path traversal
# ---------------------------------------------------------------------------


def get_state_path(obj: Any, path: str) -> Any:
    current = obj
    for part in path.split("."):
        current = getattr(current, part)
    return current


def set_state_path(obj: Any, path: str, value: Any) -> Any:
    parts = path.split(".")
    if len(parts) == 1:
        return obj.replace(**{parts[0]: value})
    head, tail = parts[0], parts[1:]
    child = getattr(obj, head)
    updated = set_state_path(child, ".".join(tail), value)
    return obj.replace(**{head: updated})

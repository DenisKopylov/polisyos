"""Executor data models and shared low-level CAS helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from typing import Any, Literal, TypeVar

import numpy as np
from pydantic import BaseModel, Field

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import ArtifactStore, CoreJSONArtifactStore
from polisyos.core.artifacts.environment import EnvironmentManifestRef
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    InputRef,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import from_canonical_bytes as from_canonical_bytes
from polisyos.core.contracts.foundry import (
    ConstraintReportRef,
    ExecPlanRef,
    MethodExecutionBundleRef,
    MethodExecutionOccurrence,
    MethodMetricBinding,
    MethodMetricBindingSetRef,
    ProgramGraphRef,
)
from polisyos.foundry.methods.exceptions import StatePathTraversalError

_ModelT = TypeVar("_ModelT", bound=BaseModel)

_ARTIFACT_OWNER_FIELDS = (
    "ARTIFACT_KIND",
    "ARTIFACT_MEDIA_TYPE",
    "ARTIFACT_SCHEMA_NAME",
    "ARTIFACT_SCHEMA_VERSION",
)

__all__ = [
    "ApplyArtifacts",
    "ExecuteArtifacts",
    "ExecutionStrictness",
    "MethodExecutionCapture",
    "FailureCard",
    "FailureKind",
    "FailureSeverity",
    "artifact_id",
    "artifact_input_ref",
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
    method_metric_binding_set_ref: MethodMetricBindingSetRef | None = None
    method_execution_bundle_ref: MethodExecutionBundleRef | None = None
    environment_fingerprint: str | None = None
    failure_cards: tuple[FailureCard, ...] = ()
    degradation_cards: tuple[FailureCard, ...] = ()
    is_degraded: bool = False
    provenance: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass
class MethodExecutionCapture:
    """Mutable per-execute-session inventory shared across feedback iterations."""

    program_graph_ref: ProgramGraphRef
    exec_plan_ref: ExecPlanRef
    method_metric_binding_set_ref: MethodMetricBindingSetRef
    method_metric_bindings: tuple[MethodMetricBinding, ...] | None = None
    occurrences: list[MethodExecutionOccurrence] = field(default_factory=list)
    environment_manifest_ref: EnvironmentManifestRef | None = None
    limitations: list[str] = field(default_factory=list)
    invocation_count: int = 0
    input_capture_bytes_used: int = 0
    sidecar_bytes_used: int = 0
    sidecar_refs_used: int = 0
    method_execution_bundle_ref: MethodExecutionBundleRef | None = None
    artifact_output_codec: Literal["legacy", "bounded_v3"] = "legacy"

    def begin_invocation(self) -> str:
        """Allocate a stable invocation id unique within this captured run."""
        self.invocation_count += 1
        return f"graph-invocation.{self.invocation_count:06d}"

    def replace_occurrence(self, occurrence: MethodExecutionOccurrence) -> None:
        """Replace the planned row matching ``occurrence_id`` with its latest state."""
        for index, existing in enumerate(self.occurrences):
            if existing.occurrence_id == occurrence.occurrence_id:
                self.occurrences[index] = occurrence
                return
        raise ValueError("method_execution_occurrence_not_predeclared")


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


def artifact_input_ref(
    value: ArtifactRef | ArtifactID | str,
    *,
    role: str,
) -> InputRef:
    """Build a lineage edge without discarding a selected artifact view."""
    if isinstance(value, ArtifactRef):
        return input_ref_from_artifact_ref(value, role=role)
    return InputRef(artifact_id=artifact_id(value), role=role)


def _has_complete_artifact_owner(model_cls: type[BaseModel]) -> bool:
    """Return whether a model declares its complete Core artifact owner contract."""
    owner_values = tuple(getattr(model_cls, field, None) for field in _ARTIFACT_OWNER_FIELDS)
    if not any(value is not None for value in owner_values):
        return False
    if any(not isinstance(value, str) or not value for value in owner_values):
        raise CanonicalProfileRefusalError("canon_profile_typed_artifact_owner_invalid")
    return True


def load_model(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef | ArtifactID | str,
    model_cls: type[_ModelT],
) -> _ModelT:
    """Load a typed artifact through its owner contract when one is declared."""
    from polisyos.core.artifacts import (
        load_core_json_artifact,
        validate_core_model_json_artifact,
    )

    if _has_complete_artifact_owner(model_cls):
        return validate_core_model_json_artifact(model_cls, store, ref)

    payload = load_core_json_artifact(store, ref)
    return model_cls.model_validate(payload)


def load_payload(
    store: CoreJSONArtifactStore,
    ref: ArtifactRef | ArtifactID | str,
) -> dict[str, Any]:
    """Load payload."""
    from polisyos.core.artifacts import load_core_json_artifact

    payload = load_core_json_artifact(store, ref)
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    if isinstance(payload, dict):
        return payload
    raise ValueError("Invalid intervention payload")


def put_tensor(store: ArtifactStore, value: Any) -> ArtifactRef:
    """Persist an array-like value as a NumPy tensor artifact."""
    array = np.asarray(value)
    buf = BytesIO()
    np.save(buf, array, allow_pickle=False)
    data = buf.getvalue()
    return store.put_bytes(
        data,
        PutOptions(kind="foundry.patch_value", media_type="application/x-npy"),
    )


def load_tensor(store: ArtifactStore, ref: ArtifactRef | ArtifactID | str) -> np.ndarray:
    """Load tensor."""
    data = store.get_bytes(ref)
    loaded = np.load(BytesIO(data), allow_pickle=False)
    if isinstance(loaded, np.ndarray):
        return loaded
    if isinstance(loaded, np.lib.npyio.NpzFile):
        loaded.close()
    raise ValueError("Tensor artifact must contain a NumPy array")


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

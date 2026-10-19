"""Cross-process serialization for shipping state and outcomes.

Used by distributed runners (Temporal, Ray) to marshal ``ExperimentState``
and ``NodeOutcome`` across process boundaries.  Uses Pydantic
``model_dump`` / ``model_validate`` with ``orjson`` for speed.

Version header
--------------
``serialize_state_safe`` / ``deserialize_state_safe`` prepend a single
version byte (currently ``\\x01``) and append a SHA-256 integrity hash.
Current state/outcome writers emit a tagged v2 JSON envelope. Readers retain
legacy raw JSON and v1 integrity framing; the framing version is independent of
the typed payload schema. V2 budgets require finite Decimal tags before coercion.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from polisyos.common.logger import get_logger
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.security import AccessScope
    from polisyos.core.trace import TraceRecord

try:
    import orjson

    def _dumps(obj: Any) -> bytes:
        return orjson.dumps(obj)

    def _loads(data: bytes) -> Any:
        return orjson.loads(data)

except ImportError:  # pragma: no cover - fallback
    import json

    def _dumps(obj: Any) -> bytes:  # type: ignore[misc]
        return json.dumps(obj, separators=(",", ":")).encode()

    def _loads(data: bytes) -> Any:  # type: ignore[misc]
        return json.loads(data)


# ---------------------------------------------------------------------------
# Version constants
# ---------------------------------------------------------------------------

_VERSION_1 = b"\x01"
_HASH_LENGTH = 32  # SHA-256 digest length in bytes
_WIRE_MAX_DEPTH = 128
_STATE_WIRE_SCHEMA = "polisyos.scientist.state_wire.v2"
_OUTCOME_WIRE_SCHEMA = "polisyos.scientist.outcome_wire.v2"
_TIMEOUT_CONTEXT_WIRE_SCHEMA = "polisyos.scientist.timeout_context.v2"


_WIRE_TYPE_KEY = "_type"
_WIRE_DECIMAL = "decimal"
_WIRE_BYTES = "bytes"
_WIRE_MODEL = "model"
_WIRE_MAPPING = "mapping"
_WIRE_DATE = "date"
_WIRE_DATETIME = "datetime"
NATIVE_NODE_OUTCOME_STATUS_CONTRACT = "native_node_outcome_v1"
_OUTCOME_MUTATION_WIRE_SCHEMA = "polisyos.scientist.node_outcome.mutations.v1"
_WORKER_EXECUTION_WIRE_SCHEMA = "polisyos.scientist.worker_execution_receipt.v1"


class _WorkerExecutionEnvelope(BaseModel):
    """Strict result envelope for one parent-dispatched staged worker run."""

    model_config = ConfigDict(extra="forbid", strict=True)

    wire_schema: Literal["polisyos.scientist.worker_execution_receipt.v1"]
    invocation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    dispatch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    owner_snapshot_ref: dict[str, Any]
    records: list[dict[str, Any]]
    outcome_b64: str | None = None
    error_payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_result_kind(self) -> _WorkerExecutionEnvelope:
        if (self.outcome_b64 is None) == (self.error_payload is None):
            raise ValueError("worker receipt must contain exactly one result kind")
        return self


@dataclass(frozen=True)
class NativeNodeOutcomeBatch:
    """Worker outcomes whose native status fields passed the typed wire decoder."""

    outcomes: dict[str, NodeOutcome]
    status_contract: Literal["native_node_outcome_v1"] = NATIVE_NODE_OUTCOME_STATUS_CONTRACT

    def admits_success(self, alias: str, outcome: NodeOutcome) -> bool:
        """Admit one outcome only when its decoded native status proves success."""
        return (
            self.status_contract == NATIVE_NODE_OUTCOME_STATUS_CONTRACT
            and self.outcomes.get(alias) is outcome
            and isinstance(outcome, NodeOutcome)
            and outcome.status == "ok"
        )

    @property
    def successful_outcomes(self) -> dict[str, NodeOutcome]:
        """Return only status-verified outcomes admitted to the success band."""
        return {
            alias: outcome
            for alias, outcome in self.outcomes.items()
            if self.admits_success(alias, outcome)
        }


def deserialize_outcome_batch(
    data_by_alias: dict[str, bytes],
) -> NativeNodeOutcomeBatch:
    """Decode a complete batch through the canonical typed outcome boundary."""
    return NativeNodeOutcomeBatch(
        outcomes={alias: deserialize_outcome(data) for alias, data in data_by_alias.items()}
    )


# Transport models keep their established v0 mapping shape.  Artifact models
# are wrapped with their import identity so a nested reference cannot silently
# degrade into an untyped dictionary on a typed boundary.
_WIRE_PLAIN_MODEL_FQNS = frozenset(
    {
        "polisyos.scientist.orchestration.engine.state.ExperimentState",
        "polisyos.scientist.orchestration.engine.protocol.NodeError",
        "polisyos.scientist.orchestration.engine.protocol.NodeEvent",
        "polisyos.scientist.orchestration.engine.protocol.NodeOutcome",
        "polisyos.scientist.orchestration.engine.protocol.NodeOutputDisposition",
        "polisyos.scientist.orchestration.engine.protocol.NodeOutputRefusal",
        "polisyos.scientist.orchestration.engine.protocol.NodeOutputRule",
        "polisyos.scientist.orchestration.engine.protocol.OutputAwareNodeOutcome",
        "polisyos.core.contracts.skip_blockers.SkippedNodeBlocker",
    }
)
_WIRE_MODEL_TYPES: dict[str, type[BaseModel]] | None = None


def _wire_model_types() -> dict[str, type[BaseModel]]:
    """Return the closed set of Pydantic models admitted by this transport."""
    global _WIRE_MODEL_TYPES
    if _WIRE_MODEL_TYPES is None:
        from polisyos.core.artifacts import ArtifactID, ArtifactRef
        from polisyos.core.contracts import SkippedNodeBlocker
        from polisyos.scientist.orchestration.engine.protocol import (
            NodeError,
            NodeEvent,
            NodeOutcome,
            NodeOutputDisposition,
            NodeOutputRefusal,
            NodeOutputRule,
            OutputAwareNodeOutcome,
        )
        from polisyos.scientist.orchestration.engine.state import ExperimentState
        from polisyos.scientist.orchestration.engine.state_branching import (
            StateMutation,
        )

        models = (
            ArtifactID,
            ArtifactRef,
            ExperimentState,
            NodeError,
            NodeEvent,
            NodeOutcome,
            NodeOutputDisposition,
            NodeOutputRefusal,
            NodeOutputRule,
            OutputAwareNodeOutcome,
            StateMutation,
            SkippedNodeBlocker,
        )
        _WIRE_MODEL_TYPES = {f"{model.__module__}.{model.__qualname__}": model for model in models}
    return _WIRE_MODEL_TYPES


def _wire_depth(depth: int) -> None:
    if depth > _WIRE_MAX_DEPTH:
        raise TypeError(f"Wire serialization depth exceeds {_WIRE_MAX_DEPTH}")


def _escape_wire_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    """Escape a user mapping whose reserved tag key is ordinary data."""
    if _WIRE_TYPE_KEY not in payload:
        return payload
    return {
        _WIRE_TYPE_KEY: _WIRE_MAPPING,
        "entries": [[key, value] for key, value in payload.items()],
    }


@dataclass
class _OutcomeWireContext:
    """Per-call owner selection and plain state projection for outcome encoding."""

    outcome: Any
    state: Any
    selected_journal: Any = None
    root_owner: bool = False
    legacy_journal: Any = None
    tracked_journal: Any = None
    tracked_conflict: bool = False
    validation_values: dict[int, Any] = field(default_factory=dict)


def _remember_validation_value(
    value: Any,
    projection: Any,
    context: _OutcomeWireContext | None,
) -> None:
    if context is not None:
        context.validation_values[id(value)] = projection


def _record_wire_journal_owner(
    context: _OutcomeWireContext,
    value: Any,
) -> None:
    from polisyos.scientist.orchestration.engine.state_branching import (
        _wire_mutation_journal_owner,
    )

    journal, owner_kind = _wire_mutation_journal_owner(
        value,
        state_root=value is context.state,
    )
    if journal is None:
        return
    if owner_kind == "root":
        context.selected_journal = journal
        context.root_owner = True
        return
    if context.root_owner:
        return
    if owner_kind == "legacy":
        if context.legacy_journal is None:
            context.legacy_journal = journal
            context.selected_journal = journal
        return
    if owner_kind == "tracked":
        if context.legacy_journal is not None:
            return
        if context.tracked_journal is None:
            context.tracked_journal = journal
            context.selected_journal = journal
        elif context.tracked_journal is not journal:
            context.tracked_conflict = True


def _wire_model_visit_order(value: BaseModel, model_type: type[BaseModel]) -> list[str]:
    """Visit stored model fields in the legacy instance order, then defaults."""
    try:
        namespace = object.__getattribute__(value, "__dict__")
    except AttributeError:
        namespace = {}
    fields = model_type.model_fields
    if type(namespace) is dict:
        stored_names = [name for name in namespace if name in fields]
    else:
        stored_names = []
    stored = set(stored_names)
    return stored_names + [name for name in fields if name not in stored]


def _wire_model_payload(
    value: BaseModel,
    *,
    depth: int,
    seen: set[int],
    model_type: type[BaseModel] | None = None,
    journal_value_mode: bool = False,
    artifact_ref_mapping: bool = False,
    context: _OutcomeWireContext | None = None,
    in_state_subtree: bool = False,
) -> Any:
    """Convert one admitted model using its canonical wire-field definition."""
    model_type = model_type or type(value)
    if getattr(model_type, "__pydantic_root_model__", False):
        root_value = value.root
        encoded = _encode_wire_value(
            root_value,
            depth=depth + 1,
            seen=seen,
            journal_value_mode=journal_value_mode,
            context=context,
            in_state_subtree=in_state_subtree,
        )
        _remember_validation_value(
            value,
            context.validation_values.get(id(root_value), root_value)
            if context is not None
            else root_value,
            context,
        )
        return encoded

    encoded_fields: dict[str, Any] = {}
    validation_fields: dict[str, Any] = {}
    mutation_wire_type = _wire_model_types().get(
        "polisyos.scientist.orchestration.engine.state_branching.StateMutation"
    )
    is_journal_operation = journal_value_mode and model_type is mutation_wire_type
    value_kind = getattr(value, "value_kind", None) if is_journal_operation else None
    for field_name in _wire_model_visit_order(value, model_type):
        field_info = model_type.model_fields[field_name]
        key = field_info.serialization_alias or field_info.alias or field_name
        field_value = getattr(value, field_name)
        child_in_state = in_state_subtree or (
            context is not None
            and not in_state_subtree
            and value is context.outcome
            and field_name == "state"
            and field_value is context.state
        )
        if artifact_ref_mapping and field_name == "manifest_profile_sha256" and field_value is None:
            continue
        if artifact_ref_mapping and field_name == "artifact_id":
            encoded_fields[field_name] = _artifact_id_wire_text(
                field_value,
                depth=depth + 1,
                seen=seen,
                allow_plain_string=False,
            )
            continue
        if is_journal_operation and field_name == "value" and value_kind == "artifact_ref":
            encoded_fields[field_name] = _encode_artifact_ref_mutation_value(
                field_value,
                depth=depth + 1,
                seen=seen,
            )
            continue
        encoded_fields[field_name] = _encode_wire_value(
            field_value,
            depth=depth + 1,
            seen=seen,
            journal_value_mode=journal_value_mode,
            context=context,
            in_state_subtree=child_in_state,
        )
        if context is not None:
            validation_fields[field_name] = context.validation_values.get(
                id(field_value), field_value
            )

    payload: dict[str, Any] = {}
    validation_payload: dict[str, Any] = {}
    for field_name, field_info in model_type.model_fields.items():
        key = field_info.serialization_alias or field_info.alias or field_name
        if field_name in encoded_fields:
            payload[key] = encoded_fields[field_name]
            if context is not None and field_name in validation_fields:
                validation_payload[key] = validation_fields[field_name]
    extra = getattr(value, "__pydantic_extra__", None)
    if isinstance(extra, Mapping):
        for key, item in extra.items():
            if not isinstance(key, str):
                raise TypeError(f"Wire model extra keys must be str, got {type(key).__name__}")
            if key not in payload:
                payload[key] = _encode_wire_value(
                    item,
                    depth=depth + 1,
                    seen=seen,
                    journal_value_mode=journal_value_mode,
                    context=context,
                    in_state_subtree=in_state_subtree,
                )
                if context is not None:
                    validation_payload[key] = context.validation_values.get(id(item), item)
    if context is not None:
        _remember_validation_value(value, validation_payload, context)
    return payload if artifact_ref_mapping else _escape_wire_mapping(payload)


def _artifact_ref_model_origin(value: BaseModel) -> type[BaseModel] | None:
    """Resolve a source-typed artifact reference, including exact tracked origins."""
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.ir.registry.refs import ArtifactRefModel
    from polisyos.scientist.orchestration.engine.state_branching import (
        _owned_wire_model_origin,
    )

    origin = _owned_wire_model_origin(value) or type(value)
    if origin is ArtifactRef:
        return origin
    if type(origin) is type(BaseModel) and issubclass(origin, ArtifactRefModel):
        return origin
    return None


def _artifact_id_wire_text(
    value: Any,
    *,
    depth: int,
    seen: set[int],
    allow_plain_string: bool,
) -> str:
    """Extract canonical text from exact Core/IR ID roots or a plain wire ID."""
    _wire_depth(depth)
    from polisyos.core.artifacts.ids import ArtifactID as CoreArtifactID
    from polisyos.ir.artifacts.contracts import ArtifactID as IRArtifactID

    if type(value) is str and allow_plain_string:
        artifact_id = value
    elif isinstance(value, BaseModel):
        value_id = id(value)
        if value_id in seen:
            raise TypeError("Cycle detected while serializing ArtifactID")
        from polisyos.scientist.orchestration.engine.state_branching import (
            _owned_wire_model_origin,
        )

        origin = _owned_wire_model_origin(value) or type(value)
        if origin is not CoreArtifactID and origin is not IRArtifactID:
            raise TypeError(
                "Artifact reference mutation ID must be a declared Core or IR ArtifactID"
            )
        seen.add(value_id)
        try:
            artifact_id = object.__getattribute__(value, "root")
        finally:
            seen.remove(value_id)
        if type(artifact_id) is not str:
            raise TypeError("Artifact reference mutation ID root must be str")
    else:
        raise TypeError("Artifact reference mutation ID must be a canonical string")

    if (
        len(artifact_id) != 71
        or not artifact_id.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in artifact_id[7:])
    ):
        raise TypeError("Artifact reference mutation ID must be canonical sha256 text")
    return artifact_id


def _encode_artifact_ref_mutation_value(
    value: Any,
    *,
    depth: int,
    seen: set[int],
) -> dict[str, Any]:
    """Encode a declared reference model or a decoded plain sidecar mapping."""
    _wire_depth(depth)
    if isinstance(value, BaseModel):
        value_id = id(value)
        if value_id in seen:
            raise TypeError(f"Cycle detected while serializing {type(value).__name__}")
        model_type = _artifact_ref_model_origin(value)
        if model_type is None:
            raise TypeError("Artifact reference mutation must carry a declared reference model")
        seen.add(value_id)
        try:
            payload = _wire_model_payload(
                value,
                depth=depth,
                seen=seen,
                model_type=model_type,
                artifact_ref_mapping=True,
            )
        finally:
            seen.remove(value_id)
    elif type(value) is dict:
        value_id = id(value)
        if value_id in seen:
            raise TypeError("Cycle detected while serializing mapping")
        seen.add(value_id)
        try:
            payload = {}
            for key, item in dict.items(value):
                if type(key) is not str:
                    raise TypeError(f"Wire mapping keys must be str, got {type(key).__name__}")
                if key == "artifact_id":
                    payload[key] = _artifact_id_wire_text(
                        item,
                        depth=depth + 1,
                        seen=seen,
                        allow_plain_string=True,
                    )
                else:
                    payload[key] = _encode_wire_value(item, depth=depth + 1, seen=seen)
        finally:
            seen.remove(value_id)
    else:
        raise TypeError("Artifact reference mutation must carry a declared model or plain mapping")

    artifact_id = payload.get("artifact_id")
    if type(artifact_id) is not str:
        raise TypeError("Artifact reference mutation is missing a canonical artifact_id")
    return _escape_wire_mapping(payload)


def _encode_wire_value(
    value: Any,
    *,
    depth: int = 0,
    seen: set[int] | None = None,
    journal_value_mode: bool = False,
    context: _OutcomeWireContext | None = None,
    in_state_subtree: bool = False,
) -> Any:
    """Recursively encode bounded wire values and the guarded state projection."""
    _wire_depth(depth)
    seen = seen if seen is not None else set()

    if value is None or isinstance(value, (str, bool, int)):
        _remember_validation_value(value, value, context)
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite float is not supported on the runner wire")
        _remember_validation_value(value, value, context)
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite Decimal is not supported on the runner wire")
        _remember_validation_value(value, value, context)
        return {_WIRE_TYPE_KEY: _WIRE_DECIMAL, "value": str(value)}
    if isinstance(value, (bytes, bytearray, memoryview)):
        _remember_validation_value(value, value, context)
        return {
            _WIRE_TYPE_KEY: _WIRE_BYTES,
            "encoding": "base64",
            "data": base64.b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, datetime):
        _remember_validation_value(value, value, context)
        normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return {
            _WIRE_TYPE_KEY: _WIRE_DATETIME,
            "iso_utc": normalized.isoformat().replace("+00:00", "Z"),
        }
    if isinstance(value, date):
        _remember_validation_value(value, value, context)
        return {_WIRE_TYPE_KEY: _WIRE_DATE, "iso": value.isoformat()}

    value_id = id(value)
    if isinstance(value, BaseModel):
        if value_id in seen:
            raise TypeError(f"Cycle detected while serializing {type(value).__name__}")
        model_type = type(value)
        fqn = f"{model_type.__module__}.{model_type.__qualname__}"
        wire_type = model_type
        wire_fqn = fqn
        wire_types = _wire_model_types()
        if wire_types.get(fqn) is not model_type:
            from polisyos.scientist.orchestration.engine.state_branching import (
                _owned_wire_model_origin,
            )

            original = _owned_wire_model_origin(value)
            if original is None:
                raise TypeError(f"Unsupported model on runner wire: {fqn}")
            original_fqn = f"{original.__module__}.{original.__qualname__}"
            if wire_types.get(original_fqn) is not original:
                raise TypeError(f"Unsupported model on runner wire: {fqn}")
            wire_type = original
            wire_fqn = original_fqn
        seen.add(value_id)
        try:
            if context is not None and in_state_subtree:
                _record_wire_journal_owner(context, value)
            payload = _wire_model_payload(
                value,
                depth=depth,
                seen=seen,
                model_type=wire_type,
                journal_value_mode=journal_value_mode,
                context=context,
                in_state_subtree=in_state_subtree,
            )
        finally:
            seen.remove(value_id)
        if wire_fqn in _WIRE_PLAIN_MODEL_FQNS:
            return payload
        return {
            _WIRE_TYPE_KEY: _WIRE_MODEL,
            "module": wire_type.__module__,
            "qualname": wire_type.__qualname__,
            "value": payload,
        }

    if isinstance(value, Mapping):
        if value_id in seen:
            raise TypeError("Cycle detected while serializing mapping")
        seen.add(value_id)
        try:
            if context is not None and in_state_subtree:
                _record_wire_journal_owner(context, value)
            encoded: dict[str, Any] = {}
            projection: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError(f"Wire mapping keys must be str, got {type(key).__name__}")
                encoded[key] = _encode_wire_value(
                    item,
                    depth=depth + 1,
                    seen=seen,
                    journal_value_mode=journal_value_mode,
                    context=context,
                    in_state_subtree=in_state_subtree,
                )
                if context is not None:
                    projection[key] = context.validation_values.get(id(item), item)
            if context is not None:
                _remember_validation_value(value, projection, context)
            return _escape_wire_mapping(encoded)
        finally:
            seen.remove(value_id)

    if isinstance(value, (list, tuple)):
        if value_id in seen:
            raise TypeError("Cycle detected while serializing sequence")
        seen.add(value_id)
        try:
            if context is not None and in_state_subtree:
                _record_wire_journal_owner(context, value)
            encoded_items: list[Any] = []
            projection_items: list[Any] = []
            for item in value:
                encoded_items.append(
                    _encode_wire_value(
                        item,
                        depth=depth + 1,
                        seen=seen,
                        journal_value_mode=journal_value_mode,
                        context=context,
                        in_state_subtree=in_state_subtree,
                    )
                )
                if context is not None:
                    projection_items.append(context.validation_values.get(id(item), item))
            if context is not None:
                projection = (
                    tuple(projection_items) if isinstance(value, tuple) else projection_items
                )
                _remember_validation_value(value, projection, context)
            return encoded_items
        finally:
            seen.remove(value_id)

    raise TypeError(f"Unsupported type on runner wire: {type(value).__name__}")


def worker_dispatch_sha256(
    *,
    node_id: str,
    alias: str,
    params: Mapping[str, Any],
    state_bytes: bytes,
    trace_carrier: Mapping[str, str],
    timeout_s: float | None,
    max_retries: int,
    context_meta: Mapping[str, Any],
) -> str:
    """Digest the complete typed worker execution payload, excluding receipt fields."""
    import json

    if type(state_bytes) is not bytes:
        raise TypeError("Worker dispatch state must be bytes")
    if type(max_retries) is not int or max_retries < 0:
        raise ValueError("Worker dispatch retry count is invalid")
    payload = {
        "wire_schema": "polisyos.scientist.worker_dispatch.v1",
        "node_id": node_id,
        "alias": alias,
        "params": _encode_wire_value(params),
        "state_sha256": hashlib.sha256(state_bytes).hexdigest(),
        "trace_carrier": _encode_wire_value(trace_carrier),
        "timeout_s": timeout_s,
        "max_retries": max_retries,
        "context_meta": _encode_wire_value(context_meta),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def serialize_worker_execution_receipt(
    *,
    outcome_bytes: bytes | None = None,
    error_payload: dict[str, Any] | None = None,
    invocation_id: str,
    dispatch_sha256: str,
    owner_snapshot_ref: ArtifactRef,
    records: list[TraceRecord],
) -> bytes:
    """Encode one timeout worker outcome with its staged RunContext receipt."""
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.trace import TraceRecord

    if type(owner_snapshot_ref) is not ArtifactRef:
        raise TypeError("Worker receipt owner snapshot must be an ArtifactRef")
    if any(type(record) is not TraceRecord for record in records):
        raise TypeError("Worker receipt events must be TraceRecord values")
    envelope = _WorkerExecutionEnvelope(
        wire_schema=_WORKER_EXECUTION_WIRE_SCHEMA,
        invocation_id=invocation_id,
        dispatch_sha256=dispatch_sha256,
        owner_snapshot_ref=owner_snapshot_ref.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=False,
        ),
        records=[
            record.model_dump(mode="json", by_alias=True, exclude_none=False) for record in records
        ],
        outcome_b64=(
            base64.b64encode(outcome_bytes).decode("ascii") if outcome_bytes is not None else None
        ),
        error_payload=error_payload,
    )
    return _dumps(envelope.model_dump(mode="json", by_alias=True, exclude_none=False))


def deserialize_worker_execution_receipt(
    data: bytes,
) -> tuple[bytes | None, dict[str, Any] | None, str, str, ArtifactRef, list[TraceRecord]]:
    """Decode and strictly validate one timeout worker execution receipt."""
    from polisyos.core.artifacts import ArtifactRef
    from polisyos.core.trace import TraceRecord

    try:
        raw = _loads(_coerce_wire_bytes(data))
        envelope = _WorkerExecutionEnvelope.model_validate(raw)
        owner_ref = ArtifactRef.model_validate(envelope.owner_snapshot_ref)
        if (
            owner_ref.model_dump(mode="json", by_alias=True, exclude_none=False)
            != envelope.owner_snapshot_ref
        ):
            raise DeserializationError("Worker receipt owner reference is noncanonical")
        records: list[TraceRecord] = []
        for item in envelope.records:
            record = TraceRecord.model_validate(item)
            if record.model_dump(mode="json", by_alias=True, exclude_none=False) != item:
                raise DeserializationError("Worker receipt trace record is noncanonical")
            records.append(record)
        outcome_bytes = (
            base64.b64decode(envelope.outcome_b64.encode("ascii"), validate=True)
            if envelope.outcome_b64 is not None
            else None
        )
    except DeserializationError:
        raise
    except (binascii.Error, UnicodeError, *_SERIALIZATION_ERRORS) as exc:
        raise DeserializationError(f"Malformed worker execution receipt: {exc}") from exc
    return (
        outcome_bytes,
        envelope.error_payload,
        envelope.invocation_id,
        envelope.dispatch_sha256,
        owner_ref,
        records,
    )


def _decode_wire_tag(value: Mapping[str, Any], *, depth: int) -> Any:
    """Decode one strict typed wire tag."""
    kind = value.get(_WIRE_TYPE_KEY)
    if not isinstance(kind, str):
        raise DeserializationError("Wire type tag must be a string")

    if kind == _WIRE_DECIMAL:
        if set(value) != {_WIRE_TYPE_KEY, "value"} or not isinstance(value["value"], str):
            raise DeserializationError("Malformed Decimal wire tag")
        try:
            decoded = Decimal(value["value"])
        except (InvalidOperation, ValueError) as exc:
            raise DeserializationError("Malformed Decimal wire value") from exc
        if not decoded.is_finite():
            raise DeserializationError("Non-finite Decimal is not supported on the runner wire")
        return decoded

    if kind == _WIRE_BYTES:
        if set(value) != {_WIRE_TYPE_KEY, "encoding", "data"}:
            raise DeserializationError("Malformed bytes wire tag")
        if value["encoding"] != "base64" or not isinstance(value["data"], str):
            raise DeserializationError("Malformed bytes wire encoding")
        try:
            return base64.b64decode(value["data"].encode("ascii"), validate=True)
        except (binascii.Error, UnicodeEncodeError) as exc:
            raise DeserializationError("Malformed base64 bytes wire value") from exc

    if kind == _WIRE_DATETIME:
        if set(value) != {_WIRE_TYPE_KEY, "iso_utc"} or not isinstance(value["iso_utc"], str):
            raise DeserializationError("Malformed datetime wire tag")
        try:
            return datetime.fromisoformat(value["iso_utc"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise DeserializationError("Malformed datetime wire value") from exc

    if kind == _WIRE_DATE:
        if set(value) != {_WIRE_TYPE_KEY, "iso"} or not isinstance(value["iso"], str):
            raise DeserializationError("Malformed date wire tag")
        try:
            return date.fromisoformat(value["iso"])
        except ValueError as exc:
            raise DeserializationError("Malformed date wire value") from exc

    if kind == _WIRE_MODEL:
        if set(value) != {_WIRE_TYPE_KEY, "module", "qualname", "value"}:
            raise DeserializationError("Malformed model wire tag")
        module = value["module"]
        qualname = value["qualname"]
        if not isinstance(module, str) or not isinstance(qualname, str):
            raise DeserializationError("Malformed model wire identity")
        fqn = f"{module}.{qualname}"
        model_type = _wire_model_types().get(fqn)
        if model_type is None:
            raise DeserializationError(f"Unsupported model on runner wire: {fqn}")
        decoded_value = _decode_wire_value(value["value"], depth=depth + 1)
        try:
            return model_type.model_validate(decoded_value)
        except (TypeError, ValueError, ValidationError) as exc:
            raise DeserializationError(f"Invalid {fqn} wire value: {exc}") from exc

    if kind == _WIRE_MAPPING:
        if set(value) != {_WIRE_TYPE_KEY, "entries"}:
            raise DeserializationError("Malformed mapping wire tag")
        entries = value["entries"]
        if not isinstance(entries, list):
            raise DeserializationError("Malformed mapping wire entries")
        decoded: dict[str, Any] = {}
        for entry in entries:
            if (
                not isinstance(entry, list)
                or len(entry) != 2
                or not isinstance(entry[0], str)
                or entry[0] in decoded
            ):
                raise DeserializationError("Malformed mapping wire entry")
            decoded[entry[0]] = _decode_wire_value(entry[1], depth=depth + 1)
        return decoded

    raise DeserializationError(f"Unsupported runner wire type tag: {kind!r}")


def _decode_wire_value(value: Any, *, depth: int = 0) -> Any:
    """Recursively validate and decode typed wire values."""
    if depth > _WIRE_MAX_DEPTH:
        raise DeserializationError(f"Wire deserialization depth exceeds {_WIRE_MAX_DEPTH}")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DeserializationError("Non-finite float is not supported on the runner wire")
        return value
    if isinstance(value, list):
        return [_decode_wire_value(item, depth=depth + 1) for item in value]
    if isinstance(value, Mapping):
        if _WIRE_TYPE_KEY in value:
            return _decode_wire_tag(value, depth=depth + 1)
        decoded: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise DeserializationError("Wire mapping keys must be str")
            decoded[key] = _decode_wire_value(item, depth=depth + 1)
        return decoded
    raise DeserializationError(f"Unsupported decoded wire value: {type(value).__name__}")


def _typed_state_payload(payload: Any) -> None:
    """Validate v2 budget types before model coercion can hide malformed input."""
    if not isinstance(payload, Mapping) or not isinstance(payload.get("budgets"), Mapping):
        raise DeserializationError("Typed state wire requires an explicit budget mapping")
    for name, budget in payload["budgets"].items():
        if (
            not isinstance(budget, Mapping)
            or set(budget) != {_WIRE_TYPE_KEY, "value"}
            or budget.get(_WIRE_TYPE_KEY) != _WIRE_DECIMAL
            or not isinstance(budget.get("value"), str)
        ):
            raise DeserializationError(f"Typed budget requires a Decimal tag: {name}")


def _typed_envelope(schema: str, value: Any) -> dict[str, Any]:
    return {"wire_schema": schema, "value": value}


def _read_typed_envelope(raw: Any, *, outcome: bool) -> Any:
    if not isinstance(raw, Mapping) or "wire_schema" not in raw:
        return raw
    schema = raw.get("wire_schema")
    expected = _OUTCOME_WIRE_SCHEMA if outcome else _STATE_WIRE_SCHEMA
    if outcome and schema == _OUTCOME_MUTATION_WIRE_SCHEMA:
        return raw  # Historical journal envelope retains its original meaning.
    if schema != expected or set(raw) != {"wire_schema", "value"}:
        raise DeserializationError("Unsupported or malformed typed wire envelope")
    payload = raw["value"]
    if outcome:
        if (
            isinstance(payload, Mapping)
            and payload.get("wire_schema") == _OUTCOME_MUTATION_WIRE_SCHEMA
        ):
            nested = payload.get("outcome")
            state = nested.get("state") if isinstance(nested, Mapping) else None
        else:
            state = payload.get("state") if isinstance(payload, Mapping) else None
    else:
        state = payload
    _typed_state_payload(state)
    return payload


def _validate_state_budget_payload(payload: Mapping[str, Any]) -> None:
    """Reject non-finite legacy budget strings before Pydantic coercion."""
    budgets = payload.get("budgets")
    if not isinstance(budgets, Mapping):
        return
    for name, budget in budgets.items():
        if isinstance(budget, str):
            try:
                budget = Decimal(budget)
            except (InvalidOperation, ValueError):
                continue
        if isinstance(budget, Decimal) and not budget.is_finite():
            raise DeserializationError(f"Non-finite Decimal budget is not supported: {name}")


def _validate_decoded_state(value: Any) -> Any:
    """Validate every decoded state payload, including states inside outcomes."""
    if isinstance(value, Mapping):
        if "run_id" in value and "budgets" in value:
            _validate_state_budget_payload(value)
        nested_state = value.get("state")
        if nested_state is not None:
            _validate_decoded_state(nested_state)
        return value

    from polisyos.scientist.orchestration.engine.state import ExperimentState

    if isinstance(value, ExperimentState):
        for name, budget in value.budgets.items():
            if not budget.is_finite():
                raise DeserializationError(f"Non-finite Decimal budget is not supported: {name}")
    return value


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DeserializationError(Exception):
    """Failed to deserialise state or outcome from bytes."""


logger = get_logger(__name__)
_SERIALIZATION_ERRORS = (
    AttributeError,
    KeyError,
    TypeError,
    ValidationError,
    ValueError,
)
_TRACE_IMPORT_ERRORS = (ImportError, ModuleNotFoundError, AttributeError)
_TRACE_RUNTIME_ERRORS = (RuntimeError, TypeError, ValueError)


# ---------------------------------------------------------------------------
# Plain (legacy-compatible) serialization — version 0
# ---------------------------------------------------------------------------


def serialize_state(state: Any) -> bytes:
    """Serialize ``ExperimentState`` to bytes for cross-process transfer.

    Parameters
    ----------
    state:
        An ``ExperimentState`` Pydantic model instance.

    Returns
    -------
    bytes
        Compact JSON bytes ready for wire transfer.
    """
    encoded = _encode_wire_value(state)
    _typed_state_payload(encoded)
    return _dumps(_typed_envelope(_STATE_WIRE_SCHEMA, encoded))


def deserialize_state(data: bytes) -> Any:
    """Deserialize ``ExperimentState`` from bytes.

    Supports both version-0 (raw JSON) and version-1 (header + hash)
    payloads transparently.

    Returns
    -------
    ExperimentState
        Reconstructed experiment state.

    Raises
    ------
    DeserializationError
        On corrupt, truncated, or version-mismatched data.
    """
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    try:
        data = _coerce_wire_bytes(data)
        # Detect version-1 payload
        if data and data[:1] == _VERSION_1:
            data = _unwrap_safe(data)
        raw = _read_typed_envelope(_loads(data), outcome=False)
        decoded = _validate_decoded_state(_decode_wire_value(raw))
        return ExperimentState.model_validate(decoded)
    except DeserializationError:
        raise
    except _SERIALIZATION_ERRORS as exc:
        raise DeserializationError(f"Failed to deserialize state: {exc}") from exc


def serialize_outcome(outcome: Any) -> bytes:
    """Serialize one fully guarded outcome and its selected mutation journal."""
    from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    if not isinstance(outcome, NodeOutcome):
        encoded = _encode_wire_value(outcome)
        _typed_state_payload(encoded.get("state") if isinstance(encoded, Mapping) else None)
        return _dumps(_typed_envelope(_OUTCOME_WIRE_SCHEMA, encoded))

    context = _OutcomeWireContext(outcome=outcome, state=outcome.state)
    encoded_outcome = _encode_wire_value(outcome, seen=set(), context=context)
    if context.tracked_conflict and context.legacy_journal is None and not context.root_owner:
        raise TypeError("Conflicting tracked mutation journals in serialized state")

    journal = context.selected_journal
    if journal is None:
        _typed_state_payload(encoded_outcome["state"])
        return _dumps(_typed_envelope(_OUTCOME_WIRE_SCHEMA, encoded_outcome))

    projection = context.validation_values.get(id(outcome.state))
    if not isinstance(projection, Mapping):
        raise TypeError("Journaled outcome state has no guarded validation projection")
    state = ExperimentState.model_validate(projection)
    encoded_outcome = dict(encoded_outcome)
    # The outcome walk has already guarded the original state and every sibling.
    # Re-encoding this normalized model is post-guard validation work.
    encoded_outcome["state"] = _encode_wire_value(state, depth=1, seen=set())
    _typed_state_payload(encoded_outcome["state"])
    encoded_mutations = _encode_wire_value(
        journal.operations,
        depth=0,
        seen=set(),
        journal_value_mode=True,
    )
    return _dumps(
        _typed_envelope(
            _OUTCOME_WIRE_SCHEMA,
            {
                "wire_schema": _OUTCOME_MUTATION_WIRE_SCHEMA,
                "outcome": encoded_outcome,
                "state_mutations": encoded_mutations,
            },
        )
    )


def _decode_journaled_outcome(payload: Mapping[str, Any]) -> Any:
    """Decode the bounded operation sidecar and reattach it to the state."""
    from polisyos.scientist.orchestration.engine.protocol import (
        NodeOutcome,
        decode_node_outcome,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.orchestration.engine.state_branching import (
        StateMutation,
        mutation_journal_from_operations,
    )

    if set(payload) != {"wire_schema", "outcome", "state_mutations"}:
        raise DeserializationError("Malformed journaled NodeOutcome envelope")
    if payload.get("wire_schema") != _OUTCOME_MUTATION_WIRE_SCHEMA:
        raise DeserializationError("Unsupported journaled NodeOutcome schema")

    raw_outcome = _validate_decoded_state(_decode_wire_value(payload["outcome"]))
    outcome = decode_node_outcome(raw_outcome)
    if not isinstance(outcome, NodeOutcome):
        raise DeserializationError("Journal envelope does not contain a NodeOutcome")

    operations = _decode_wire_value(payload["state_mutations"])
    if not isinstance(operations, list) or any(
        not isinstance(operation, StateMutation) for operation in operations
    ):
        raise DeserializationError("State mutation sidecar must contain typed operations")
    for operation in operations:
        parts = operation.path.split(".")
        if (
            not parts
            or any(not part for part in parts)
            or parts[0] not in ExperimentState.model_fields
        ):
            raise DeserializationError("State mutation path is not rooted in ExperimentState")

    object.__setattr__(
        outcome.state,
        "_polisyos_state_mutation_journal",
        mutation_journal_from_operations(operations),
    )
    return outcome


def deserialize_outcome(data: bytes) -> Any:
    """Deserialize ``NodeOutcome`` bytes, restoring its typed journal if supplied."""
    from polisyos.scientist.orchestration.engine.protocol import decode_node_outcome

    try:
        data = _coerce_wire_bytes(data)
        if data and data[:1] == _VERSION_1:
            data = _unwrap_safe(data)
        raw = _read_typed_envelope(_loads(data), outcome=True)
        if isinstance(raw, Mapping) and "wire_schema" in raw:
            return _decode_journaled_outcome(raw)
        decoded = _validate_decoded_state(_decode_wire_value(raw))
        return decode_node_outcome(decoded)
    except DeserializationError:
        raise
    except _SERIALIZATION_ERRORS as exc:
        raise DeserializationError(f"Failed to deserialize outcome: {exc}") from exc


# ---------------------------------------------------------------------------
# Safe serialization — version 1 (header + integrity hash)
# ---------------------------------------------------------------------------


def serialize_state_safe(state: Any) -> tuple[bytes, str]:
    """Serialize with version header and SHA-256 integrity hash.

    Returns
    -------
    (payload, sha256_hex)
        The versioned payload bytes and the hex digest.
    """
    json_bytes = serialize_state(state)
    digest = hashlib.sha256(json_bytes).digest()
    payload = _VERSION_1 + json_bytes + digest
    return payload, hashlib.sha256(json_bytes).hexdigest()


def deserialize_state_safe(data: bytes) -> Any:
    """Deserialize a version-1 payload with integrity verification.

    Raises
    ------
    DeserializationError
        On version mismatch, truncated data, or integrity failure.
    """
    json_bytes = _unwrap_safe(_coerce_wire_bytes(data))
    return deserialize_state(json_bytes)


def _unwrap_safe(data: bytes) -> bytes:
    """Strip version header and verify integrity hash."""
    if not data or data[:1] != _VERSION_1:
        raise DeserializationError(
            f"Unsupported serialization version: {data[:1]!r} (expected {_VERSION_1!r})"
        )
    if len(data) < 1 + _HASH_LENGTH + 1:
        raise DeserializationError("Payload too short — truncated?")

    json_bytes = data[1:-_HASH_LENGTH]
    expected_hash = data[-_HASH_LENGTH:]
    actual_hash = hashlib.sha256(json_bytes).digest()

    if actual_hash != expected_hash:
        raise DeserializationError("Integrity check failed — data corrupted")

    return json_bytes


def _coerce_wire_bytes(data: Any) -> bytes:
    """Normalize distributed-runner payloads back into raw bytes.

    Some transports encode nested ``bytes`` values as ``list[int]`` or
    ``bytearray``-compatible wrappers.  Distributed workers should accept those
    wire representations instead of failing deep inside JSON decoding.
    """
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, memoryview):
        return data.tobytes()
    if isinstance(data, str):
        return data.encode()
    if isinstance(data, list) and all(isinstance(item, int) for item in data):
        try:
            return bytes(data)
        except ValueError as exc:
            raise DeserializationError(f"Invalid byte sequence in wire payload: {exc}") from exc
    raise DeserializationError(
        f"Failed to deserialize state: unsupported wire payload type {type(data).__name__}"
    )


# ---------------------------------------------------------------------------
# Context meta extraction
# ---------------------------------------------------------------------------


def _current_trace_ids() -> tuple[str | None, str | None]:
    try:
        from opentelemetry import trace as otel_trace

        span_context = otel_trace.get_current_span().get_span_context()
    except _TRACE_IMPORT_ERRORS:
        return None, None
    except _TRACE_RUNTIME_ERRORS as exc:
        emit_degraded_path(
            component="engine.runner.serialization",
            operation="current_trace_ids",
            reason="trace_context_read_failed",
            exc=exc,
            log=logger,
        )
        return None, None

    if not getattr(span_context, "is_valid", False):
        return None, None
    return (
        f"{int(span_context.trace_id):032x}",
        f"{int(span_context.span_id):016x}",
    )


def _run_attr(run: Any, name: str) -> Any:
    value = getattr(run, name, None)
    if value is not None:
        return value
    manifest = getattr(run, "run_manifest", None)
    if manifest is not None:
        return getattr(manifest, name, None)
    return None


def serialize_context_meta(
    ctx: Any,
    *,
    workflow_id: str | None = None,
    runner_backend: str | None = None,
) -> dict[str, Any]:
    """Extract serializable metadata from ``ExecutionContext``.

    Remote workers cannot receive the store handle or logger directly;
    they reconstruct those from their own environment.  This function
    captures the metadata needed to reconstitute a compatible context.
    """
    meta: dict[str, Any] = {
        "depth": ctx.depth,
    }
    # RunContext metadata
    if ctx.run is not None:
        run_id = _run_attr(ctx.run, "run_id")
        if run_id is not None:
            meta["run_id"] = run_id
        meta["tenant_id"] = getattr(ctx.run, "tenant_id", None)
        meta["cell_id"] = getattr(ctx.run, "cell_id", None)
        registry_bundle = _run_attr(ctx.run, "registry_bundle")
        if registry_bundle is not None and hasattr(registry_bundle, "model_dump"):
            meta["registry_bundle_ref"] = registry_bundle.model_dump(mode="json")
    if workflow_id is not None:
        meta["workflow_id"] = workflow_id
    if runner_backend is not None:
        meta["runner_backend"] = runner_backend
    try:
        from polisyos.core.artifacts.store import FileSystemCAS

        if isinstance(ctx.store, FileSystemCAS):
            meta["store_backend"] = "filesystem"
            meta["store_root"] = str(ctx.store.root)
    except _TRACE_IMPORT_ERRORS:
        pass
    except _TRACE_RUNTIME_ERRORS as exc:
        emit_degraded_path(
            component="engine.runner.serialization",
            operation="serialize_context_meta_store_probe",
            reason="store_context_probe_failed",
            exc=exc,
            details={"runner_backend": runner_backend or "unknown"},
            log=logger,
        )
    trace_id, span_id = _current_trace_ids()
    if trace_id is not None:
        meta["trace_id"] = trace_id
    if span_id is not None:
        meta["span_id"] = span_id
    return meta


_TIMEOUT_ACCESS_SCOPE_FIELDS = frozenset(
    {
        "tenant_id",
        "cell_id",
        "principal_type",
        "user_sub",
        "roles",
        "max_pii_tier",
        "mfa_verified",
        "spiffe_id",
        "delegation_jti",
        "jwt_jti",
    }
)


def _timeout_access_scope_from_wire(raw: Any) -> AccessScope | None:
    """Decode one exact canonical AccessScope object or explicit absence."""
    if raw is None:
        return None
    if type(raw) is not dict or set(raw) != _TIMEOUT_ACCESS_SCOPE_FIELDS:
        raise ValueError("timeout_worker_access_scope_shape_invalid")

    from polisyos.core.security import AccessScope, PIIAccessLevel, PolicyOSRole

    string_fields = (
        "tenant_id",
        "principal_type",
        "user_sub",
        "max_pii_tier",
        "spiffe_id",
        "delegation_jti",
        "jwt_jti",
    )
    if any(type(raw[name]) is not str for name in string_fields):
        raise ValueError("timeout_worker_access_scope_invalid")
    if type(raw["cell_id"]) is not str and raw["cell_id"] is not None:
        raise ValueError("timeout_worker_access_scope_invalid")
    if not raw["tenant_id"].strip() or type(raw["mfa_verified"]) is not bool:
        raise ValueError("timeout_worker_access_scope_invalid")
    roles_raw = raw["roles"]
    if type(roles_raw) is not list or any(type(role) is not str for role in roles_raw):
        raise ValueError("timeout_worker_access_scope_invalid")
    try:
        roles = frozenset(PolicyOSRole(role) for role in roles_raw)
        max_pii_tier = PIIAccessLevel(raw["max_pii_tier"])
    except ValueError as exc:
        raise ValueError("timeout_worker_access_scope_invalid") from exc
    canonical_roles = [role.value for role in sorted(roles, key=lambda role: role.value)]
    if canonical_roles != roles_raw:
        raise ValueError("timeout_worker_access_scope_invalid")
    scope = AccessScope(
        tenant_id=raw["tenant_id"],
        cell_id=raw["cell_id"],
        principal_type=raw["principal_type"],
        user_sub=raw["user_sub"],
        roles=roles,
        max_pii_tier=max_pii_tier,
        mfa_verified=raw["mfa_verified"],
        spiffe_id=raw["spiffe_id"],
        delegation_jti=raw["delegation_jti"],
        jwt_jti=raw["jwt_jti"],
    )
    if scope.to_dict() != raw:
        raise ValueError("timeout_worker_access_scope_noncanonical")
    return scope


def _timeout_access_scope_to_wire(scope: AccessScope | None) -> dict[str, Any] | None:
    """Encode only an exact AccessScope whose full canonical form round-trips."""
    if scope is None:
        return None
    from polisyos.core.security import AccessScope

    if type(scope) is not AccessScope:
        raise ValueError("timeout_worker_access_scope_type_invalid")
    payload = scope.to_dict()
    if _timeout_access_scope_from_wire(payload) != scope:
        raise ValueError("timeout_worker_access_scope_noncanonical")
    return payload


def serialize_timeout_context(ctx: Any, *, expected_run_id: str) -> dict[str, Any]:
    """Encode the closed local context profile admitted by spawn timeout workers.

    The timeout worker must not silently replace a store, run, or optional port.
    This wire admits only the plain local ``ExecutionContext`` backed by a
    filesystem CAS and a JSONL ``RunContext``; richer contexts require an
    explicit typed transport before they can use this process boundary.
    """
    import logging
    from pathlib import Path

    from polisyos.core import run as core_run
    from polisyos.core.artifacts import ArtifactRef, SigningConfig
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.observability import (
        get_metrics,
        get_tracer,
        is_hpc_observability_enabled,
    )
    from polisyos.core.run.worker_lifecycle import WorkerLifecycleCapability
    from polisyos.core.security import (
        get_current_access_scope_or_none,
        get_current_cell_id,
        get_current_tenant_id_or_none,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

    if type(ctx) is not ExecutionContext:
        raise ValueError("timeout_worker_unsupported_execution_context")
    store = ctx.store
    run = ctx.run
    if type(store) is not FileSystemCAS:
        raise ValueError("timeout_worker_filesystem_cas_required")
    if type(run) is not core_run.RunContext:
        raise ValueError("timeout_worker_run_context_required")
    if type(run.run_manifest) is not core_run.RunManifest:
        raise ValueError("timeout_worker_run_manifest_required")
    lifecycle = WorkerLifecycleCapability.for_parent(run)
    run_snapshot = lifecycle.snapshot()
    if not run_snapshot.trace_is_jsonl or run_snapshot.audit_sink_present:
        raise ValueError("timeout_worker_jsonl_trace_profile_required")
    access_scope_wire = _timeout_access_scope_to_wire(run_snapshot.access_scope)
    ambient_access_scope = get_current_access_scope_or_none()
    if ambient_access_scope is not None and ambient_access_scope != run_snapshot.access_scope:
        raise ValueError("timeout_worker_ambient_access_scope_mismatch")
    if run.store is not store:
        raise ValueError("timeout_worker_run_store_mismatch")
    if not isinstance(ctx.logger, logging.Logger):
        raise ValueError("timeout_worker_logger_profile_unsupported")
    if type(ctx.depth) is not int or ctx.depth < 0:
        raise ValueError("timeout_worker_depth_invalid")

    optional_values = (
        ctx.tracer,
        ctx.metrics,
        ctx.audit,
        ctx.fabric,
        ctx.foundry,
        ctx.scholar,
        ctx.lex,
        ctx.memory,
        ctx.eval_safety_execution_context,
        ctx.eval_safety_verifier,
        ctx.epoch_certificate_issuance_owner,
        ctx.prepared_skg_read,
    )
    if any(value is not None for value in optional_values):
        raise ValueError("timeout_worker_optional_context_port_unsupported")
    hpc_observability_enabled = is_hpc_observability_enabled()
    if store._hpc_enabled != hpc_observability_enabled:
        raise ValueError("timeout_worker_observability_setting_mismatch")
    if hpc_observability_enabled and (
        store._metrics is not get_metrics() or store._tracer is not get_tracer()
    ):
        raise ValueError("timeout_worker_custom_store_observability_unsupported")
    if not hpc_observability_enabled and (store._metrics is not None or store._tracer is not None):
        raise ValueError("timeout_worker_custom_store_observability_unsupported")
    if not isinstance(store._signing_config, SigningConfig):
        raise ValueError("timeout_worker_signing_config_required")

    root = store.root.resolve(strict=True)
    trace_path = run_snapshot.trace_path
    if not isinstance(trace_path, Path) or not trace_path.is_absolute():
        raise ValueError("timeout_worker_trace_path_required")
    trace_path = trace_path.resolve(strict=False)
    try:
        trace_path.relative_to(root)
    except ValueError as exc:
        raise ValueError("timeout_worker_trace_path_outside_store") from exc
    if run_snapshot.run_id != expected_run_id:
        raise ValueError("timeout_worker_run_id_mismatch")
    if (
        run_snapshot.run_manifest.tenant_id != run_snapshot.tenant_id
        or run_snapshot.run_manifest.cell_id != run_snapshot.cell_id
    ):
        raise ValueError("timeout_worker_manifest_owner_mismatch")
    if (store._tenant_id, store._cell_id) != (
        run_snapshot.tenant_id,
        run_snapshot.cell_id,
    ):
        raise ValueError("timeout_worker_store_run_owner_mismatch")
    owner_snapshot_ref = run_snapshot.owner_snapshot_ref
    ambient_tenant = get_current_tenant_id_or_none()
    ambient_cell = get_current_cell_id()
    for owner_tenant, owner_cell in (
        (store._tenant_id, store._cell_id),
        (run_snapshot.tenant_id, run_snapshot.cell_id),
    ):
        if owner_tenant is not None and (
            ambient_tenant != owner_tenant
            or (owner_cell is not None and ambient_cell != owner_cell)
        ):
            raise ValueError("timeout_worker_ambient_owner_mismatch")
    if not isinstance(ambient_tenant, str) or not ambient_tenant.strip():
        raise ValueError("timeout_worker_ambient_tenant_required")

    return {
        "schema": _TIMEOUT_CONTEXT_WIRE_SCHEMA,
        "depth": ctx.depth,
        "logger_name": ctx.logger.name,
        "run_id": expected_run_id,
        "workflow_id": "",
        "store": {
            "backend": "filesystem",
            "root": str(root),
            "tenant_id": store._tenant_id,
            "cell_id": store._cell_id,
            "ownership_enforced": store._ownership_enforced,
            "ownership_requires_scope": store._ownership_requires_scope,
            "signing_config": store._signing_config.model_dump(mode="json"),
            "hpc_observability_enabled": hpc_observability_enabled,
        },
        "run": {
            "manifest": run_snapshot.run_manifest.model_dump(mode="json"),
            "trace_path": str(trace_path),
            "tenant_id": run_snapshot.tenant_id,
            "cell_id": run_snapshot.cell_id,
            "owner_snapshot_ref": owner_snapshot_ref.model_dump(
                mode="json", by_alias=True, exclude_none=False
            ),
            "access_scope": access_scope_wire,
        },
        "tenant_scope": {"tenant_id": ambient_tenant, "cell_id": ambient_cell},
    }

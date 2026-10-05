"""Cross-process serialization for shipping state and outcomes.

Used by distributed runners (Temporal, Ray) to marshal ``ExperimentState``
and ``NodeOutcome`` across process boundaries.  Uses Pydantic
``model_dump`` / ``model_validate`` with ``orjson`` for speed.

Version header
--------------
``serialize_state_safe`` / ``deserialize_state_safe`` prepend a single
version byte (currently ``\\x01``) and append a SHA-256 integrity hash.
The plain ``serialize_state`` / ``deserialize_state`` remain backward-
compatible and produce / consume raw JSON bytes (version 0, implicit).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from polisyos.common.logger import get_logger
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome

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
_WIRE_TYPE_KEY = "_type"
_WIRE_DECIMAL = "decimal"
_WIRE_BYTES = "bytes"
_WIRE_MODEL = "model"
_WIRE_MAPPING = "mapping"
_WIRE_DATE = "date"
_WIRE_DATETIME = "datetime"
NATIVE_NODE_OUTCOME_STATUS_CONTRACT = "native_node_outcome_v1"


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


def deserialize_outcome_batch(data_by_alias: dict[str, bytes]) -> NativeNodeOutcomeBatch:
    """Decode a complete batch through the canonical typed outcome boundary."""
    return NativeNodeOutcomeBatch(
        outcomes={
            alias: deserialize_outcome(data)
            for alias, data in data_by_alias.items()
        }
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
        from polisyos.core.artifacts.ids import ArtifactID
        from polisyos.core.artifacts.manifest import ArtifactRef
        from polisyos.core.contracts.skip_blockers import SkippedNodeBlocker
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
            SkippedNodeBlocker,
        )
        _WIRE_MODEL_TYPES = {
            f"{model.__module__}.{model.__qualname__}": model for model in models
        }
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


def _wire_model_payload(
    value: BaseModel,
    *,
    depth: int,
    seen: set[int],
) -> Any:
    """Convert one admitted Pydantic model without losing nested model values."""
    model_type = type(value)
    if getattr(model_type, "__pydantic_root_model__", False):
        return _encode_wire_value(value.model_dump(mode="python"), depth=depth + 1, seen=seen)

    payload: dict[str, Any] = {}
    for field_name, field_info in model_type.model_fields.items():
        key = field_info.serialization_alias or field_info.alias or field_name
        payload[key] = _encode_wire_value(
            getattr(value, field_name),
            depth=depth + 1,
            seen=seen,
        )
    extra = getattr(value, "__pydantic_extra__", None)
    if isinstance(extra, Mapping):
        for key, item in extra.items():
            if not isinstance(key, str):
                raise TypeError(f"Wire model extra keys must be str, got {type(key).__name__}")
            if key not in payload:
                payload[key] = _encode_wire_value(item, depth=depth + 1, seen=seen)
    return _escape_wire_mapping(payload)


def _encode_wire_value(
    value: Any,
    *,
    depth: int = 0,
    seen: set[int] | None = None,
) -> Any:
    """Recursively encode the bounded typed values accepted on the runner wire."""
    _wire_depth(depth)
    seen = seen if seen is not None else set()

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite float is not supported on the runner wire")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite Decimal is not supported on the runner wire")
        return {_WIRE_TYPE_KEY: _WIRE_DECIMAL, "value": str(value)}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {
            _WIRE_TYPE_KEY: _WIRE_BYTES,
            "encoding": "base64",
            "data": base64.b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, datetime):
        normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return {
            _WIRE_TYPE_KEY: _WIRE_DATETIME,
            "iso_utc": normalized.isoformat().replace("+00:00", "Z"),
        }
    if isinstance(value, date):
        return {_WIRE_TYPE_KEY: _WIRE_DATE, "iso": value.isoformat()}

    value_id = id(value)
    if isinstance(value, BaseModel):
        if value_id in seen:
            raise TypeError(f"Cycle detected while serializing {type(value).__name__}")
        model_type = type(value)
        fqn = f"{model_type.__module__}.{model_type.__qualname__}"
        if _wire_model_types().get(fqn) is not model_type:
            raise TypeError(f"Unsupported model on runner wire: {fqn}")
        seen.add(value_id)
        try:
            payload = _wire_model_payload(value, depth=depth, seen=seen)
        finally:
            seen.remove(value_id)
        if fqn in _WIRE_PLAIN_MODEL_FQNS:
            return payload
        return {
            _WIRE_TYPE_KEY: _WIRE_MODEL,
            "module": model_type.__module__,
            "qualname": model_type.__qualname__,
            "value": payload,
        }

    if isinstance(value, Mapping):
        if value_id in seen:
            raise TypeError("Cycle detected while serializing mapping")
        seen.add(value_id)
        try:
            encoded: dict[str, Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise TypeError(f"Wire mapping keys must be str, got {type(key).__name__}")
                encoded[key] = _encode_wire_value(item, depth=depth + 1, seen=seen)
            return _escape_wire_mapping(encoded)
        finally:
            seen.remove(value_id)

    if isinstance(value, (list, tuple)):
        if value_id in seen:
            raise TypeError("Cycle detected while serializing sequence")
        seen.add(value_id)
        try:
            return [
                _encode_wire_value(item, depth=depth + 1, seen=seen) for item in value
            ]
        finally:
            seen.remove(value_id)

    raise TypeError(f"Unsupported type on runner wire: {type(value).__name__}")


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
                raise DeserializationError(
                    f"Non-finite Decimal budget is not supported: {name}"
                )
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
    return _dumps(_encode_wire_value(state))


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
        decoded = _validate_decoded_state(_decode_wire_value(_loads(data)))
        return ExperimentState.model_validate(decoded)
    except DeserializationError:
        raise
    except _SERIALIZATION_ERRORS as exc:
        raise DeserializationError(f"Failed to deserialize state: {exc}") from exc


def serialize_outcome(outcome: Any) -> bytes:
    """Serialize ``NodeOutcome`` to bytes for cross-process transfer."""
    return _dumps(_encode_wire_value(outcome))


def deserialize_outcome(data: bytes) -> Any:
    """Deserialize ``NodeOutcome`` from bytes."""
    from polisyos.scientist.orchestration.engine.protocol import decode_node_outcome

    try:
        data = _coerce_wire_bytes(data)
        if data and data[:1] == _VERSION_1:
            data = _unwrap_safe(data)
        decoded = _validate_decoded_state(_decode_wire_value(_loads(data)))
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
    json_bytes = _dumps(_encode_wire_value(state))
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
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    json_bytes = _unwrap_safe(data)
    try:
        decoded = _validate_decoded_state(_decode_wire_value(_loads(json_bytes)))
        return ExperimentState.model_validate(decoded)
    except _SERIALIZATION_ERRORS as exc:
        raise DeserializationError(f"Failed to deserialize state: {exc}") from exc


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

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

import hashlib
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.scientist.error_semantics import emit_degraded_path

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
    return _dumps(state.model_dump())


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
    from polisyos.scientist.engine.state import ExperimentState

    try:
        data = _coerce_wire_bytes(data)
        # Detect version-1 payload
        if data and data[:1] == _VERSION_1:
            data = _unwrap_safe(data)
        return ExperimentState.model_validate(_loads(data))
    except DeserializationError:
        raise
    except _SERIALIZATION_ERRORS as exc:
        raise DeserializationError(f"Failed to deserialize state: {exc}") from exc


def serialize_outcome(outcome: Any) -> bytes:
    """Serialize ``NodeOutcome`` to bytes for cross-process transfer."""
    return _dumps(outcome.model_dump())


def deserialize_outcome(data: bytes) -> Any:
    """Deserialize ``NodeOutcome`` from bytes."""
    from polisyos.scientist.engine.protocol import NodeOutcome

    try:
        data = _coerce_wire_bytes(data)
        if data and data[:1] == _VERSION_1:
            data = _unwrap_safe(data)
        return NodeOutcome.model_validate(_loads(data))
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
    json_bytes = _dumps(state.model_dump())
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
    from polisyos.scientist.engine.state import ExperimentState

    json_bytes = _unwrap_safe(data)
    try:
        return ExperimentState.model_validate(_loads(json_bytes))
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
        "Failed to deserialize state: unsupported wire payload type "
        f"{type(data).__name__}"
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

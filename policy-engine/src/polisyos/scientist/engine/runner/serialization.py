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
        # Detect version-1 payload
        if data and data[:1] == _VERSION_1:
            data = _unwrap_safe(data)
        return ExperimentState.model_validate(_loads(data))
    except DeserializationError:
        raise
    except Exception as exc:
        raise DeserializationError(f"Failed to deserialize state: {exc}") from exc


def serialize_outcome(outcome: Any) -> bytes:
    """Serialize ``NodeOutcome`` to bytes for cross-process transfer."""
    return _dumps(outcome.model_dump())


def deserialize_outcome(data: bytes) -> Any:
    """Deserialize ``NodeOutcome`` from bytes."""
    from polisyos.scientist.engine.protocol import NodeOutcome

    try:
        if data and data[:1] == _VERSION_1:
            data = _unwrap_safe(data)
        return NodeOutcome.model_validate(_loads(data))
    except DeserializationError:
        raise
    except Exception as exc:
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
    except Exception as exc:
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


# ---------------------------------------------------------------------------
# Context meta extraction
# ---------------------------------------------------------------------------


def serialize_context_meta(ctx: Any) -> dict[str, Any]:
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
        meta["run_id"] = getattr(ctx.run, "run_id", None)
        meta["tenant_id"] = getattr(ctx.run, "tenant_id", None)
        meta["cell_id"] = getattr(ctx.run, "cell_id", None)
    return meta

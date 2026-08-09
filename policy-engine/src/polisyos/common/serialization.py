"""Convert nested runtime objects to JSON-safe data and fast serialized payloads."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, cast

from polisyos.common.logger import get_logger

orjson: Any | None
try:
    import orjson as _orjson
except ModuleNotFoundError:  # pragma: no cover - optional acceleration
    orjson = None
else:
    orjson = _orjson

logger = get_logger(__name__)

UnsupportedSerializationPolicy = Literal["passthrough", "error", "string"]


class SerializationError(ValueError):
    """Raised when runtime serialization cannot produce bounded JSON-safe data."""


class SerializationCycleError(SerializationError):
    """Raised when a cyclic object graph is encountered during serialization."""


class SerializationDepthError(SerializationError):
    """Raised when the configured serialization recursion budget is exceeded."""


class UnsupportedSerializationError(SerializationError):
    """Raised when unsupported objects are rejected by policy."""


class ArtifactIdentityProjectionError(SerializationError):
    """Raised when an artifact does not declare one unambiguous self-identity field."""


@dataclass(frozen=True)
class SerializationPolicy:
    """Bounded conversion policy shared by fast JSON and metadata serialization."""

    sort_keys: bool = False
    max_depth: int = 128
    unsupported: UnsupportedSerializationPolicy = "passthrough"

    def __post_init__(self) -> None:
        if self.max_depth < 1:
            raise ValueError("max_depth must be >= 1")
        if self.unsupported not in {"passthrough", "error", "string"}:
            raise ValueError("unsupported must be 'passthrough', 'error', or 'string'")


_SCALAR_TYPES = (str, int, float, bool, type(None))
_ARTIFACT_SELF_IDENTITY_FIELDS = frozenset({"content_hash", "record_hash"})


def _as_model_dump(value: Any) -> Any | None:
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump(mode="python", by_alias=True, exclude_none=False)
    return None


def artifact_self_identity_projection(value: Any) -> dict[str, Any]:
    """Return an artifact payload without exactly one declared self-identity field.

    The root projection is deliberately narrow: only ``content_hash`` and
    ``record_hash`` may be a self-identity field. A missing declaration or two
    declarations is ambiguous and therefore rejected rather than guessed.
    """

    model_dump = getattr(value, "model_dump", None)
    payload = model_dump(mode="json") if callable(model_dump) else value
    if not isinstance(payload, Mapping):
        raise ArtifactIdentityProjectionError("artifact_identity_payload_mapping_required")
    normalized = {str(key): item for key, item in payload.items()}
    identity_fields = _ARTIFACT_SELF_IDENTITY_FIELDS.intersection(normalized)
    if not identity_fields:
        raise ArtifactIdentityProjectionError("artifact_self_identity_missing")
    if len(identity_fields) != 1:
        raise ArtifactIdentityProjectionError("artifact_self_identity_ambiguous")
    identity_field = next(iter(identity_fields))
    return {key: item for key, item in normalized.items() if key != identity_field}


def _try_tolist(value: Any) -> Any | None:
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return tolist()
        except (TypeError, ValueError, RuntimeError) as exc:
            logger.warning(
                "Serialization tolist() coercion failed for %s; "
                "falling back to generic encoder: %s",
                type(value).__name__,
                exc,
            )
            return None
    return None


def _try_item(value: Any) -> Any | None:
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except (TypeError, ValueError, RuntimeError) as exc:
            logger.warning(
                "Serialization item() coercion failed for %s; falling back to generic encoder: %s",
                type(value).__name__,
                exc,
            )
            return None
    return None


class JsonDataVisitor:
    """Cycle-safe visitor that converts runtime values to JSON-compatible data."""

    def __init__(self, policy: SerializationPolicy) -> None:
        self._policy = policy
        self._seen: set[int] = set()

    def visit(self, value: Any) -> Any:
        """Convert `value` according to the configured serialization policy."""
        return self._visit(value, depth=0)

    def _visit(self, value: Any, *, depth: int) -> Any:
        if depth > self._policy.max_depth:
            raise SerializationDepthError(
                f"Serialization depth exceeded max_depth={self._policy.max_depth}"
            )
        if isinstance(value, _SCALAR_TYPES):
            return value
        if isinstance(value, Enum):
            return self._visit(value.value, depth=depth + 1)

        obj_id = id(value)
        should_track = _is_container_like(value)
        if should_track:
            if obj_id in self._seen:
                raise SerializationCycleError(
                    f"Cycle detected while serializing {type(value).__name__}"
                )
            self._seen.add(obj_id)
        try:
            return self._visit_tracked(value, depth=depth)
        finally:
            if should_track:
                self._seen.discard(obj_id)

    def _visit_tracked(self, value: Any, *, depth: int) -> Any:
        dumped = _as_model_dump(value)
        if dumped is not None:
            return self._visit(dumped, depth=depth + 1)

        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            fields = dataclasses.fields(value)
            items = [(field.name, getattr(value, field.name)) for field in fields]
            if self._policy.sort_keys:
                items = sorted(items, key=lambda pair: pair[0])
            return {str(key): self._visit(item, depth=depth + 1) for key, item in items}

        if isinstance(value, Mapping):
            items = list(value.items())
            if self._policy.sort_keys:
                items = sorted(items, key=lambda pair: str(pair[0]))
            return {str(key): self._visit(item, depth=depth + 1) for key, item in items}

        if isinstance(value, (list, tuple)):
            return [self._visit(item, depth=depth + 1) for item in value]

        if isinstance(value, (set, frozenset)):
            return [
                self._visit(item, depth=depth + 1)
                for item in sorted(value, key=_stable_collection_sort_key)
            ]

        listed = _try_tolist(value)
        if listed is not None:
            return self._visit(listed, depth=depth + 1)

        scalar = _try_item(value)
        if scalar is not None:
            return self._visit(scalar, depth=depth + 1)

        if self._policy.unsupported == "error":
            raise UnsupportedSerializationError(
                f"Unsupported type for JSON serialization: {type(value).__name__}"
            )
        if self._policy.unsupported == "string":
            return str(value)
        return value


def _is_container_like(value: Any) -> bool:
    if isinstance(value, (*_SCALAR_TYPES, Enum)):
        return False
    return (
        isinstance(value, (Mapping, list, tuple, set, frozenset))
        or (dataclasses.is_dataclass(value) and not isinstance(value, type))
        or callable(getattr(value, "model_dump", None))
        or callable(getattr(value, "tolist", None))
        or callable(getattr(value, "item", None))
    )


def _stable_collection_sort_key(value: Any) -> tuple[str, str]:
    if isinstance(value, _SCALAR_TYPES):
        return (type(value).__name__, str(value))
    if isinstance(value, Enum):
        return (type(value).__name__, str(value.value))
    return (type(value).__name__, f"id:{id(value)}")


def to_python_data(
    value: Any,
    *,
    sort_keys: bool = False,
    max_depth: int = 128,
    unsupported: UnsupportedSerializationPolicy = "passthrough",
) -> Any:
    """Convert nested values to JSON/canonical-friendly Python data.

    The conversion is cycle-safe and bounded. Callers that must fail closed for
    unknown objects can set ``unsupported="error"``.
    """
    policy = SerializationPolicy(
        sort_keys=sort_keys,
        max_depth=max_depth,
        unsupported=unsupported,
    )
    return JsonDataVisitor(policy).visit(value)


def strip_none(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with `None` values removed."""
    return {key: value for key, value in data.items() if value is not None}


def stable_json_dumps(value: Any, *, ensure_ascii: bool = True, sort_keys: bool = True) -> str:
    """Serialize values deterministically for configs, metadata, and hash inputs."""
    payload = to_python_data(value, sort_keys=sort_keys, unsupported="error")
    if orjson is not None and not ensure_ascii:
        option = orjson.OPT_SORT_KEYS if sort_keys else 0
        return cast("bytes", orjson.dumps(payload, option=option)).decode("utf-8")
    return json.dumps(
        payload,
        ensure_ascii=ensure_ascii,
        sort_keys=sort_keys,
        separators=(",", ":"),
    )


def fast_json_dumps_bytes(value: Any, *, sort_keys: bool = False) -> bytes:
    """Serialize a JSON-compatible payload to UTF-8 bytes with optional `orjson` acceleration."""
    payload = to_python_data(value, sort_keys=sort_keys, unsupported="error")
    if orjson is not None:
        option = orjson.OPT_SORT_KEYS if sort_keys else 0
        return cast("bytes", orjson.dumps(payload, option=option))
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=sort_keys,
        separators=(",", ":"),
    )
    return rendered.encode("utf-8")


def fast_json_dumps(value: Any, *, sort_keys: bool = False) -> str:
    """Serialize a JSON-compatible payload to text using the fast byte path."""
    return fast_json_dumps_bytes(value, sort_keys=sort_keys).decode("utf-8")


def fast_json_loads(value: bytes | bytearray | memoryview | str) -> Any:
    """Deserialize JSON bytes/text with `orjson` when available and stdlib fallback otherwise."""
    if isinstance(value, str):
        if orjson is not None:
            return orjson.loads(value)
        return json.loads(value)
    raw = bytes(value)
    if orjson is not None:
        return orjson.loads(raw)
    return json.loads(raw.decode("utf-8"))


__all__ = [
    "JsonDataVisitor",
    "SerializationCycleError",
    "SerializationDepthError",
    "SerializationError",
    "SerializationPolicy",
    "UnsupportedSerializationError",
    "fast_json_dumps",
    "fast_json_dumps_bytes",
    "fast_json_loads",
    "stable_json_dumps",
    "strip_none",
    "to_python_data",
]

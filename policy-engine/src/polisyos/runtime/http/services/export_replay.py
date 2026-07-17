"""Shared stable-address and replay binding for existing runtime exports."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Iterable, Mapping, MutableMapping
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Protocol
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict

EXPORT_REPLAY_QUERY_PARAMETER = "export_projection_hash"
EXPORT_REPLAY_CONTRACT = "policyos.runtime.export_replay_binding.v1"

_HEADER_CONTRACT = "X-PolicyOS-Export-Contract"
_HEADER_STABLE_ADDRESS = "X-PolicyOS-Export-Stable-Address"
_HEADER_PROJECTION_HASH = "X-PolicyOS-Export-Projection-Hash"
_HEADER_REPLAY_ADDRESS = "X-PolicyOS-Export-Replay-Address"
_HEADER_AS_OF = "X-PolicyOS-Export-As-Of"

EXPORT_REPLAY_RESPONSE_HEADERS: dict[str, dict[str, Any]] = {
    _HEADER_CONTRACT: {
        "description": "Typed runtime export replay-binding contract.",
        "schema": {"type": "string", "const": EXPORT_REPLAY_CONTRACT},
    },
    _HEADER_STABLE_ADDRESS: {
        "description": "Canonical address excluding the replay pin.",
        "schema": {"type": "string"},
    },
    _HEADER_PROJECTION_HASH: {
        "description": "SHA-256 of the narrow stable semantic export projection.",
        "schema": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    },
    _HEADER_REPLAY_ADDRESS: {
        "description": "Stable address with the current projection hash pinned.",
        "schema": {"type": "string"},
    },
    _HEADER_AS_OF: {
        "description": "Time at which the exported semantics were valid or observed.",
        "schema": {"type": "string", "format": "date-time"},
    },
}


class _HeaderResponse(Protocol):
    headers: MutableMapping[str, str]


class ExportReplayBinding(BaseModel):
    """Describe stable identity and replay for an existing owner export."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract: Literal["policyos.runtime.export_replay_binding.v1"] = EXPORT_REPLAY_CONTRACT
    stable_address: str
    projection_hash: str
    replay_address: str
    as_of: datetime


class ExportReplayPinMismatchError(ValueError):
    """Report that an export no longer matches a requested projection pin."""

    def __init__(self, *, expected: str, actual: str) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"export projection replay pin {expected!r} does not match {actual!r}"
        )


def build_export_stable_address(
    path: str,
    query_items: Iterable[tuple[str, str]],
) -> str:
    """Return a canonical path/query address without its replay pin.

    Args:
        path: Runtime API path for the existing exporter.
        query_items: The request query pairs, including repeated values when present.

    Returns:
        A relative stable address with sorted query pairs.
    """

    stable_items = sorted(
        (str(key), str(value))
        for key, value in query_items
        if key != EXPORT_REPLAY_QUERY_PARAMETER
    )
    if not stable_items:
        return path
    return f"{path}?{urlencode(stable_items)}"


def bind_export_replay(
    response: _HeaderResponse,
    *,
    stable_address: str,
    semantic_projection: object,
    as_of: datetime,
    requested_projection_hash: str | None = None,
) -> ExportReplayBinding:
    """Bind stable projection identity and replay metadata to an HTTP response.

    Args:
        response: Response whose headers receive the shared export convention.
        stable_address: Canonical address without the replay pin.
        semantic_projection: Narrow owner-produced semantics, excluding envelope time.
        as_of: Validity or observation time carried separately from the projection hash.
        requested_projection_hash: Optional caller pin that must match current semantics.

    Returns:
        The strict replay binding written to the response headers.

    Raises:
        ExportReplayPinMismatchError: If the requested pin is stale or malformed.
    """

    projection_hash = hash_export_projection(semantic_projection)
    if requested_projection_hash is not None and not hmac.compare_digest(
        requested_projection_hash,
        projection_hash,
    ):
        raise ExportReplayPinMismatchError(
            expected=requested_projection_hash,
            actual=projection_hash,
        )
    replay_address = build_export_replay_address(
        stable_address,
        {EXPORT_REPLAY_QUERY_PARAMETER: projection_hash},
    )
    binding = ExportReplayBinding(
        stable_address=stable_address,
        projection_hash=projection_hash,
        replay_address=replay_address,
        as_of=as_of,
    )
    response.headers[_HEADER_CONTRACT] = binding.contract
    response.headers[_HEADER_STABLE_ADDRESS] = binding.stable_address
    response.headers[_HEADER_PROJECTION_HASH] = binding.projection_hash
    response.headers[_HEADER_REPLAY_ADDRESS] = binding.replay_address
    response.headers[_HEADER_AS_OF] = binding.as_of.isoformat()
    response.headers["ETag"] = f'"{binding.projection_hash}"'
    return binding


def hash_export_projection(value: object) -> str:
    """Return the canonical SHA-256 for a narrow export projection."""

    encoded = json.dumps(
        _json_ready(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def build_export_replay_address(
    stable_address: str,
    pins: Mapping[str, str],
) -> str:
    """Append sorted replay pins to an already canonical stable address."""

    separator = "&" if "?" in stable_address else "?"
    return f"{stable_address}{separator}{urlencode(sorted(pins.items()))}"


def _json_ready(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Enum):
        return _json_ready(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


__all__ = [
    "EXPORT_REPLAY_CONTRACT",
    "EXPORT_REPLAY_QUERY_PARAMETER",
    "EXPORT_REPLAY_RESPONSE_HEADERS",
    "ExportReplayBinding",
    "ExportReplayPinMismatchError",
    "bind_export_replay",
    "build_export_replay_address",
    "build_export_stable_address",
    "hash_export_projection",
]

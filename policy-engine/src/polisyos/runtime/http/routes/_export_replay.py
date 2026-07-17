"""HTTP error translation for the shared export replay binding."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from polisyos.runtime.http.errors import conflict
from polisyos.runtime.http.services.export_replay import (
    ExportReplayBinding,
    ExportReplayPinMismatchError,
    bind_export_replay,
    build_export_stable_address,
)

if TYPE_CHECKING:
    from datetime import datetime


class _RequestUrl(Protocol):
    path: str


class _RequestQuery(Protocol):
    def multi_items(self) -> list[tuple[str, str]]: ...


class _Request(Protocol):
    url: _RequestUrl
    query_params: _RequestQuery


class _Response(Protocol):
    headers: dict[str, str]


def bind_export_replay_or_conflict(
    *,
    request: _Request,
    response: _Response,
    semantic_projection: object,
    as_of: datetime,
    requested_projection_hash: str | None,
) -> ExportReplayBinding:
    """Apply the common binding and translate a stale pin to runtime HTTP 409."""

    stable_address = build_export_stable_address(
        request.url.path,
        request.query_params.multi_items(),
    )
    try:
        return bind_export_replay(
            response,
            stable_address=stable_address,
            semantic_projection=semantic_projection,
            as_of=as_of,
            requested_projection_hash=requested_projection_hash,
        )
    except ExportReplayPinMismatchError as exc:
        raise conflict(
            str(exc),
            code="export_replay_pin_mismatch",
            extensions={
                "field": "export_projection_hash",
                "expected": exc.expected,
                "actual": exc.actual,
            },
        ) from exc


__all__ = ["bind_export_replay_or_conflict"]

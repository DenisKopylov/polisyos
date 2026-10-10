from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from polisyos.runtime.http.services.export_replay import (
    ExportReplayPinMismatchError,
    bind_export_replay,
    hash_export_projection,
)


def test_stale_export_pin_fails_before_writing_response_headers() -> None:
    projection = {"state": "limited", "evidence_refs": ["artifact://fixture"]}
    as_of = datetime(2026, 10, 10, 12, tzinfo=UTC)
    actual_hash = hash_export_projection(projection)
    successful_response = SimpleNamespace(headers={})

    binding = bind_export_replay(
        successful_response,
        stable_address="/api/v1/exports/fixture",
        semantic_projection=projection,
        as_of=as_of,
        requested_projection_hash=actual_hash,
    )

    assert binding.projection_hash == actual_hash
    assert successful_response.headers["ETag"] == f'"{actual_hash}"'
    assert successful_response.headers["X-PolicyOS-Export-Projection-Hash"] == actual_hash

    stale_response = SimpleNamespace(headers={"X-Preserved": "before"})
    with pytest.raises(ExportReplayPinMismatchError) as raised:
        bind_export_replay(
            stale_response,
            stable_address="/api/v1/exports/fixture",
            semantic_projection=projection,
            as_of=as_of,
            requested_projection_hash="sha256:" + "0" * 64,
        )

    assert raised.value.actual == actual_hash
    assert stale_response.headers == {"X-Preserved": "before"}

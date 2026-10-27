"""Baseline-compatible red probes for unverified cursor admission."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.core.contracts.cursor import CursorState, WatermarkType
from polisyos.fabric.connectors.sources.rest_json import RestJsonConnector
from polisyos.fabric.data_plane.modes import _cursor_version


@pytest.mark.parametrize("watermark", [WatermarkType.ETAG, WatermarkType.REVISION])
def test_b79_present_legacy_version_without_evidence_never_becomes_a_hint(watermark) -> None:
    """Capability and valid syntax cannot replace resolved source evidence."""
    cursor = CursorState(
        cursor_id="rest.json:events",
        connector_id="rest.json",
        dataset_id="events",
        watermark_type=watermark,
        watermark_value="123",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert _cursor_version(cursor, RestJsonConnector()) is None

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polisyos.common.timestamps import ensure_utc, parse_iso_datetime


def test_ensure_utc_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="Naive datetimes are not allowed"):
        ensure_utc(datetime(2026, 1, 1, 12, 0, 0))


def test_parse_iso_datetime_rejects_naive_timestamp_strings() -> None:
    assert parse_iso_datetime("2026-01-01T12:00:00") is None


def test_ensure_utc_preserves_aware_instants() -> None:
    value = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
    assert ensure_utc(value) == value

from __future__ import annotations

from datetime import datetime

import pytest

from polisyos.fabric.data_plane.temporal import TemporalValidationError, parse_datetime_utc


@pytest.mark.parametrize(
    "value",
    [
        "0001-01-01T00:00:00+23:59",
        "9999-12-31T23:59:00-23:59",
    ],
)
def test_parse_datetime_utc_normalizes_offset_overflow_to_temporal_validation(
    value: str,
) -> None:
    """Syntactically valid offsets outside UTC year bounds are typed invalid inputs."""
    assert datetime.fromisoformat(value).tzinfo is not None

    with pytest.raises(
        TemporalValidationError,
        match="outside the representable UTC datetime range",
    ):
        parse_datetime_utc(value)

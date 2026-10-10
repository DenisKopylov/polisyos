from __future__ import annotations

import pytest

from polisyos.common.canonical import from_canonical_bytes, to_canonical_bytes


class ConsumerProfileError(ValueError):
    """Error selected by a caller-specific canonical tag profile."""


def test_caller_profile_round_trips_nested_bytes_and_rejects_other_tags() -> None:
    allowed_tags = frozenset({"bytes"})
    payload = {"records": [{"raw": b"\x00\xff"}]}

    encoded = to_canonical_bytes(
        payload,
        canonical_types=allowed_tags,
        violation_type=ConsumerProfileError,
    )

    assert encoded == (b'{"records":[{"raw":{"_type":"bytes","data":"AP8=","encoding":"base64"}}]}')
    assert (
        from_canonical_bytes(
            encoded,
            canonical_types=allowed_tags,
            violation_type=ConsumerProfileError,
        )
        == payload
    )

    with pytest.raises(
        ConsumerProfileError, match="Unknown canonical _type: 'date'"
    ) as encode_error:
        to_canonical_bytes(
            {"outer": [{"_type": "date", "iso": "2026-10-10"}]},
            canonical_types=allowed_tags,
            violation_type=ConsumerProfileError,
        )
    assert type(encode_error.value) is ConsumerProfileError

    with pytest.raises(
        ConsumerProfileError, match="Unknown canonical _type: 'date'"
    ) as decode_error:
        from_canonical_bytes(
            b'{"outer":[{"_type":"date","iso":"2026-10-10"}]}',
            canonical_types=allowed_tags,
            violation_type=ConsumerProfileError,
        )
    assert type(decode_error.value) is ConsumerProfileError

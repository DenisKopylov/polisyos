from __future__ import annotations

from hashlib import sha256

import pytest

from polisyos.runtime.http.services.cycle_board_sources import (
    _ATLAS_PLAN_SOURCE,
    HistoricalProducerAvailabilityError,
    load_historical_producer_availability,
)


def test_invalid_utf8_owner_bytes_remain_bound_in_the_failed_read_receipt(tmp_path) -> None:
    raw_bytes = b"\xffowner-bytes"
    source_path = tmp_path / _ATLAS_PLAN_SOURCE
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(raw_bytes)

    with pytest.raises(HistoricalProducerAvailabilityError) as raised:
        load_historical_producer_availability(tmp_path)

    receipt = raised.value.read_receipt
    assert receipt.read_status == "read"
    assert receipt.status == "UNRUN"
    assert receipt.coverage == "partial"
    assert receipt.read_error == "UnicodeDecodeError"
    assert receipt.source_content_hash == "sha256:" + sha256(raw_bytes).hexdigest()

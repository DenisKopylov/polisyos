from __future__ import annotations

import pytest

from polisyos.ir.model_layer.canon import (
    CanonSpec,
    CanonViolation,
    from_canonical_bytes,
    to_canonical_bytes,
)


def test_ir_v3_round_trips_future_raw_tag_without_widening_native_tags() -> None:
    spec = CanonSpec(version="0.3.0")
    value = {"_type": "array_digest", "digest": "user-data"}

    encoded = to_canonical_bytes(value, spec)

    assert from_canonical_bytes(encoded, version=spec.version) == value
    with pytest.raises(CanonViolation, match="Unknown canonical _type"):
        from_canonical_bytes(b'{"_type":"array_digest","digest":"native"}', version="0.3.0")

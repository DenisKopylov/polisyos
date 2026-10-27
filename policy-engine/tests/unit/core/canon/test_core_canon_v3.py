from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.core.canon.canon_json import (
    CanonSpec,
    CanonViolation,
    from_canonical_bytes,
    to_canonical_bytes,
)


def test_core_v3_round_trips_raw_tags_alongside_native_values() -> None:
    spec = CanonSpec(version="0.3.0", exclude_none=False)
    value = {"raw": {"_type": "decimal", "value": "1.0"}, "native": Decimal("1.0")}

    encoded = to_canonical_bytes(value, spec)

    assert from_canonical_bytes(encoded, version=spec.version) == value


def test_core_v3_preserves_core_exception_identity() -> None:
    with pytest.raises(CanonViolation):
        from_canonical_bytes(b'{"_type":"mapping","entries":[]}', version="0.3.0")

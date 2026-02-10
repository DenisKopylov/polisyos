from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from polisyos.core.canon import (
    CanonSpec as CoreCanonSpec,
    content_hash as core_content_hash,
    from_canonical_bytes as core_from_canonical_bytes,
    to_canonical_bytes as core_to_canonical_bytes,
)
from polisyos.ir.canon import (
    CanonSpec as IrCanonSpec,
    content_hash as ir_content_hash,
    from_canonical_bytes as ir_from_canonical_bytes,
    to_canonical_bytes as ir_to_canonical_bytes,
)


def _payload() -> dict[str, object]:
    return {
        "text": "policy",
        "num": 42,
        "decimal": Decimal("12.34"),
        "ts": datetime(2026, 2, 9, 20, 0, tzinfo=timezone.utc),
        "date": date(2026, 2, 9),
        "bytes": b"abc",
        "float": 1.25,
        "nested": {"b": 2, "a": 1},
        "items": [1, {"z": 3, "y": 2}],
    }


def test_canonical_bytes_parity_with_core() -> None:
    payload = _payload()
    core_bytes = core_to_canonical_bytes(payload, CoreCanonSpec(forbid_floats=False))
    ir_bytes = ir_to_canonical_bytes(payload, IrCanonSpec(forbid_floats=False))
    assert ir_bytes == core_bytes


def test_from_canonical_bytes_parity_with_core() -> None:
    payload = _payload()
    encoded = core_to_canonical_bytes(payload, CoreCanonSpec(forbid_floats=False))
    assert ir_from_canonical_bytes(encoded) == core_from_canonical_bytes(encoded)


def test_content_hash_parity_with_core() -> None:
    data = b"ir-parity-check"
    assert ir_content_hash(data) == core_content_hash(data)
    assert ir_content_hash(data, prefix=True) == core_content_hash(data, prefix=True)

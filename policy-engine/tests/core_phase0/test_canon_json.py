from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from polisyos.core.canon.canon_json import CanonViolation, to_canonical_bytes


def test_canonical_bytes_stable_for_key_order():
    obj1 = {"b": 1, "a": "x", "nested": {"z": 9, "y": 8}}
    obj2 = {"nested": {"y": 8, "z": 9}, "a": "x", "b": 1}

    b1 = to_canonical_bytes(obj1)
    b2 = to_canonical_bytes(obj2)

    assert b1 == b2
    assert hashlib.sha256(b1).hexdigest() == hashlib.sha256(b2).hexdigest()


def test_float_forbidden():
    with pytest.raises(CanonViolation):
        to_canonical_bytes({"x": 0.1})


def test_nan_inf_forbidden_if_float_enabled():
    with pytest.raises(CanonViolation):
        to_canonical_bytes({"x": float("nan")})
    with pytest.raises(CanonViolation):
        to_canonical_bytes({"x": float("inf")})


def test_datetime_is_canonicalized_to_utc_z():
    dt = datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
    b = to_canonical_bytes({"t": dt})
    s = b.decode("utf-8")
    assert '"_type":"datetime"' in s
    assert "2026-01-10T12:00:00Z" in s


def test_golden_hash_is_stable():
    obj = {
        "b": 1,
        "a": "test",
        "d": {"x": Decimal("1.2300")},
        "t": datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
    }
    b = to_canonical_bytes(obj)
    h = hashlib.sha256(b).hexdigest()
    assert h == "898ed85a304051f6dcaac5cb2718d9fca1b853ab50b026936ea1721d092f0c08"

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.canon import canon_json
from polisyos.core.canon.canon_json import (
    CanonSpec,
    CanonViolation,
    from_canonical_bytes,
    to_canonical_bytes,
)


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


@pytest.mark.parametrize(
    ("payload", "spec"),
    [
        pytest.param(
            {"value": {"_type": "bytes_hex", "value": "00ff"}},
            CanonSpec(),
            id="bytes-alias",
        ),
        pytest.param(
            {"value": {"_type": "float_hex", "value": "0x1.4000000000000p+0"}},
            CanonSpec(forbid_floats=False),
            id="float-alias",
        ),
    ],
)
def test_canonical_encoder_refuses_nonconformant_tag_aliases(
    payload: dict[str, object],
    spec: CanonSpec,
) -> None:
    with pytest.raises(CanonViolation) as refusal:
        to_canonical_bytes(payload, spec)

    assert isinstance(refusal.value, CanonicalProfileRefusalError)
    assert refusal.value.code == "canon_profile_payload_nonconformant"


def test_canonical_encoder_preserves_native_values_under_selected_profile() -> None:
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    payload = {"binary": b"\x00\xff", "ratio": 1.25, "optional": None}

    encoded = to_canonical_bytes(payload, spec)
    decoded = from_canonical_bytes(encoded)

    assert decoded == payload
    assert to_canonical_bytes(decoded, spec) == encoded


@pytest.mark.parametrize(
    ("value", "spec"),
    [
        pytest.param(None, CanonSpec(exclude_none=False), id="null-scalar"),
        pytest.param(b"\x00\xff", CanonSpec(), id="native-bytes"),
        pytest.param(1.25, CanonSpec(forbid_floats=False), id="finite-float"),
    ],
)
def test_core_encoder_round_trips_direct_values(value: object, spec: CanonSpec) -> None:
    encoded = to_canonical_bytes(value, spec)
    decoded = from_canonical_bytes(encoded)

    assert decoded == value
    assert type(decoded) is type(value)
    assert to_canonical_bytes(decoded, spec) == encoded


def test_core_profile_validator_uses_private_raw_encoder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = CanonSpec(forbid_floats=False, exclude_none=False)
    encoded = to_canonical_bytes({"binary": b"\x00\xff", "ratio": 1.25}, spec)

    def reject_public_reentry(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("profile validation must not re-enter the public encoder")

    monkeypatch.setattr(canon_json, "to_canonical_bytes", reject_public_reentry)
    canon_json._validate_core_json_payload_conformance(encoded, spec)


def test_nan_inf_forbidden_if_float_enabled():
    spec = CanonSpec(forbid_floats=False)
    assert b'"_type":"float"' in to_canonical_bytes({"x": 0.1}, spec)
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonViolation, match="NaN/Inf forbidden"):
            to_canonical_bytes({"x": value}, spec)


def test_datetime_is_canonicalized_to_utc_z():
    dt = datetime(2026, 1, 10, 12, 0, 0, tzinfo=UTC)
    b = to_canonical_bytes({"t": dt})
    s = b.decode("utf-8")
    assert '"_type":"datetime"' in s
    assert "2026-01-10T12:00:00Z" in s


def test_golden_hash_is_stable():
    obj = {
        "b": 1,
        "a": "test",
        "d": {"x": Decimal("1.2300")},
        "t": datetime(2026, 1, 10, 12, 0, 0, tzinfo=UTC),
    }
    b = to_canonical_bytes(obj)
    h = hashlib.sha256(b).hexdigest()
    assert h == "898ed85a304051f6dcaac5cb2718d9fca1b853ab50b026936ea1721d092f0c08"

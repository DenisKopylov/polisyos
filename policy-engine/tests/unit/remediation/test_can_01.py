"""Characterization witnesses for the CAN-01 strict-canon migration.

The corpus records the current Core/IR compatibility boundary before any
relocation.  Core and IR intentionally share the ordinary persisted payload
bytes while keeping separate typed-tag profiles, exception identities, and
public facades.  These tests are characterization only; production owners are
not changed in this phase.
"""

from __future__ import annotations

# ruff: noqa: S101
# CAN-01 characterization uses direct pytest assertions as executable golden-corpus oracles.
import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import polisyos.core.canon as core_canon
import polisyos.ir.model_layer.canon as ir_canon
import pytest

if TYPE_CHECKING:
    from types import ModuleType

_GOLDEN_VALUE = {
    "bool": True,
    "bytes": b"\x00\x01\xfe",
    "date": date(2024, 1, 2),
    "datetime": datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC),
    "decimal": Decimal("12.30"),
    "integer": 7,
    "nested": [None, {"z": "café", "a": 0}],
}
_GOLDEN_BYTES = (
    '{"bool":true,"bytes":{"_type":"bytes","data":"AAH+","encoding":"base64"},'
    '"date":{"_type":"date","iso":"2024-01-02"},'
    '"datetime":{"_type":"datetime","iso_utc":"2024-01-02T03:04:05Z"},'
    '"decimal":{"_type":"decimal","value":"12.30"},"integer":7,'
    '"nested":[null,{"a":0,"z":"café"}]}'
).encode()

_CORE_EXTRA_TAGS = [
    (b'{"_type":"float_hex","value":"0x1.8p+1"}', 3.0),
    (b'{"_type":"bytes_hex","value":"00ff"}', b"\x00\xff"),
    (
        b'{"_type":"array_digest","digest":"sha256:abc","length":2}',
        {"_type": "array_digest", "digest": "sha256:abc", "length": 2},
    ),
]


@pytest.mark.parametrize(
    "module",
    [(core_canon,), (ir_canon,)],
    ids=("core", "ir"),
)
def test_ordinary_golden_payload_preserves_bytes_and_round_trips(module: ModuleType) -> None:
    """The shared persisted corpus remains byte-identical in both facades."""

    assert module.to_canonical_bytes(_GOLDEN_VALUE) == _GOLDEN_BYTES
    assert module.from_canonical_bytes(_GOLDEN_BYTES) == _GOLDEN_VALUE


def test_ordinary_golden_payload_has_content_hash_parity() -> None:
    """Structured fingerprints are hashes of the exact golden bytes."""

    expected = hashlib.sha256(_GOLDEN_BYTES).hexdigest()
    core_bytes = core_canon.to_canonical_bytes(_GOLDEN_VALUE)
    ir_bytes = ir_canon.to_canonical_bytes(_GOLDEN_VALUE)

    assert core_bytes == ir_bytes == _GOLDEN_BYTES
    assert core_canon.content_hash(core_bytes) == expected
    assert ir_canon.content_hash(ir_bytes) == expected
    assert core_canon.fingerprint(_GOLDEN_VALUE) == expected
    assert core_canon.content_hash(_GOLDEN_BYTES, prefix=True) == f"sha256:{expected}"


@pytest.mark.parametrize(
    "module",
    [(core_canon,), (ir_canon,)],
    ids=("core", "ir"),
)
def test_malformed_unknown_tag_and_depth_errors_keep_canon_boundary(module: ModuleType) -> None:
    """Malformed JSON, unknown tags, and over-depth values fail explicitly."""

    with pytest.raises(json.JSONDecodeError):
        module.from_canonical_bytes(b'{"broken":')

    unknown_tag = {"_type": "future_tag", "value": "x"}
    with pytest.raises(module.CanonViolation, match="Unknown canonical _type"):
        module.to_canonical_bytes(unknown_tag)
    with pytest.raises(module.CanonViolation, match="Unknown canonical _type"):
        module.from_canonical_bytes(json.dumps(unknown_tag).encode("utf-8"))

    with pytest.raises(module.CanonViolation, match="max_depth=1"):
        module.to_canonical_bytes({"outer": {"inner": 1}}, module.CanonSpec(max_depth=1))
    with pytest.raises(module.CanonViolation, match="max_depth=1"):
        module.from_canonical_bytes(b'{"outer":{"inner":1}}', max_depth=1)


@pytest.mark.parametrize(("payload", "expected"), _CORE_EXTRA_TAGS)
def test_core_preserves_extended_typed_tag_profile(payload: bytes, expected: object) -> None:
    """Core reads and writes the extended tags absent from the IR profile."""

    assert core_canon.to_canonical_bytes(json.loads(payload)) == payload
    assert core_canon.from_canonical_bytes(payload) == expected


@pytest.mark.parametrize("payload", [(payload,) for payload, _ in _CORE_EXTRA_TAGS])
def test_ir_rejects_core_only_typed_tags(payload: bytes) -> None:
    """IR remains strict and does not silently widen its 0.2.0 decoder."""

    with pytest.raises(ir_canon.CanonViolation, match="Unknown canonical _type"):
        ir_canon.to_canonical_bytes(json.loads(payload))
    with pytest.raises(ir_canon.CanonViolation, match="Unknown canonical _type"):
        ir_canon.from_canonical_bytes(payload)


def test_core_and_ir_keep_exception_identity_and_fully_qualified_names() -> None:
    """The two public profiles retain distinct exception classes."""

    assert core_canon.CanonViolation is not ir_canon.CanonViolation
    assert core_canon.CanonViolation.__module__ == "polisyos.core.canon.canon_json"
    assert ir_canon.CanonViolation.__module__ == "polisyos.ir.model_layer.canon"
    assert issubclass(core_canon.CanonViolation, ValueError)
    assert issubclass(ir_canon.CanonViolation, ValueError)


def test_core_and_ir_public_facades_remain_separate() -> None:
    """Core-only hashing helpers are not accidentally exposed through IR."""

    core_public = set(core_canon.__all__)
    ir_public = set(ir_canon.__all__)
    shared = {
        "CanonSpec",
        "CanonViolation",
        "DeprecatedHashAlgorithm",
        "content_hash",
        "from_canonical_bytes",
        "from_canonical_obj",
        "to_canonical_bytes",
    }
    core_only = {"fingerprint", "streaming_hash", "truncated_hash"}

    assert shared <= core_public
    assert shared <= ir_public
    assert core_only <= core_public
    assert core_only.isdisjoint(ir_public)
    assert "HashAlgorithm" not in core_public
    assert "HashAlgorithm" in ir_public
    assert not any(hasattr(ir_canon, name) for name in core_only)


@pytest.mark.parametrize(
    "module",
    [(core_canon,), (ir_canon,)],
    ids=("core", "ir"),
)
def test_explicit_sha1_keeps_deprecated_legacy_hash_identity(module: ModuleType) -> None:
    """Explicit SHA-1 remains readable with a deprecation warning only."""

    payload = b"legacy-canon-payload"
    expected = hashlib.sha1(payload).hexdigest()  # noqa: S324 - legacy SHA-1 witness.

    with pytest.warns(DeprecationWarning, match="sha1 content hashing is deprecated"):
        observed = module.content_hash(payload, algorithm="sha1", prefix=True)

    assert observed == f"sha1:{expected}"

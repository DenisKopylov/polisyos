from __future__ import annotations

import pytest
from polisyos.core.canon import content_hash, fingerprint, streaming_hash, truncated_hash


def test_content_hash_and_prefix() -> None:
    digest = content_hash("abc")
    assert digest == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert content_hash("abc", prefix=True) == f"sha256:{digest}"


def test_fingerprint_is_order_invariant_for_dicts() -> None:
    left = {"b": 2, "a": {"x": 1, "y": [1, 2, 3]}}
    right = {"a": {"y": [1, 2, 3], "x": 1}, "b": 2}
    assert fingerprint(left) == fingerprint(right)


def test_truncated_and_streaming_hash_helpers() -> None:
    assert truncated_hash("payload", length=12) == content_hash("payload")[:12]
    assert truncated_hash("payload", length=12, prefix=True).startswith("sha256:")

    chunks = [b"hello", b"-", b"world"]
    assert streaming_hash(chunks) == content_hash(b"hello-world")


def test_truncated_hash_rejects_non_positive_length() -> None:
    with pytest.raises(ValueError, match="length must be > 0"):
        truncated_hash("x", length=0)

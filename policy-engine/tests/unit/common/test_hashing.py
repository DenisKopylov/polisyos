from __future__ import annotations

import hashlib

from polisyos.common.hashing import content_hash, streaming_hash


def test_streaming_hash_is_invariant_to_binary_chunk_partition() -> None:
    payload = b"\x00policy\xff-evidence"
    partitions = (
        (payload,),
        (memoryview(payload[:4]), payload[4:]),
        (bytearray(payload[:2]), b"", memoryview(payload[2:9]), bytearray(payload[9:])),
    )
    expected = hashlib.sha256(payload).hexdigest()

    assert content_hash(payload) == expected
    for chunks in partitions:
        assert streaming_hash(iter(chunks)) == expected

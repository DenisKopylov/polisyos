from __future__ import annotations

import re
from dataclasses import dataclass

from hypothesis import given, settings
from hypothesis import strategies as st

from polisyos.data_forge.kernel.snapshot import merkle_root


@dataclass(frozen=True)
class _MerkleRef:
    uri: str
    sha256: str


def _artifact_ref(index: int, *, sha256: str, snapshot: int) -> _MerkleRef:
    return _MerkleRef(
        uri=f"polisyos://property/artifact_{index}@snap-{snapshot}",
        sha256=sha256,
    )


_REF_POOL = tuple(
    _artifact_ref(index, sha256=f"{index:064x}", snapshot=index)
    for index in range(8)
)


def _artifact_refs() -> st.SearchStrategy[tuple[_MerkleRef, ...]]:
    return st.lists(st.sampled_from(_REF_POOL), max_size=6).map(tuple)


@given(refs=_artifact_refs())
@settings(max_examples=100)
def test_merkle_root_is_order_independent_and_sha256_shaped(
    refs: tuple[_MerkleRef, ...],
) -> None:
    root = merkle_root(refs)

    assert root == merkle_root(tuple(reversed(refs)))
    assert re.fullmatch(r"[0-9a-f]{64}", root)

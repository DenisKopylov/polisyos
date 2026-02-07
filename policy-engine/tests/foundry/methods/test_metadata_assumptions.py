from __future__ import annotations

from polisyos.foundry.methods.base import MethodMetadata


def test_method_metadata_assumptions_preserved():
    metadata = MethodMetadata(
        description="test",
        assumptions={"parallel_trends": "must hold"},
    )
    assert metadata.assumptions["parallel_trends"] == "must hold"
    digest = metadata.stable_digest()
    assert isinstance(digest, str) and digest


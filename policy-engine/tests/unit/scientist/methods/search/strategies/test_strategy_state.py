"""Controlled decoding failures at the canonical strategy artifact boundary."""

import pytest

from polisyos.scientist.methods.search.strategies.types import StrategyState


@pytest.mark.parametrize("payload", [b"null", b"[]", b"1", b'"string"', b"{}", b"invalid", b"\xff"])
def test_non_checkpoint_artifact_has_controlled_failure(payload: bytes) -> None:
    with pytest.raises(ValueError, match="Strategy checkpoint artifact is invalid"):
        StrategyState.from_artifact(payload)

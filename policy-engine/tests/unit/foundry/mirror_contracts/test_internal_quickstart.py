"""Static mirror contract for the internal quickstart implementation."""

from tests._helpers.mirror_contracts import assert_source_stem_has_static_contract


def test_internal_quickstart_source_has_static_contract() -> None:
    assert_source_stem_has_static_contract("foundry/_internal", "quickstart")

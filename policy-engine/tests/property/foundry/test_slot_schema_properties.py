from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from polisyos.foundry.methods.slot_schema import (
    SLOT_SCHEMA_REGISTRY,
    SemanticCompatibilityError,
    is_semantically_compatible,
)

_HEALTH_CHECKS = [HealthCheck.function_scoped_fixture, HealthCheck.too_slow]
_KNOWN_SLOTS = tuple(sorted(SLOT_SCHEMA_REGISTRY))


@given(
    source=st.sampled_from(_KNOWN_SLOTS),
    target=st.sampled_from(_KNOWN_SLOTS),
)
@settings(max_examples=200, suppress_health_check=_HEALTH_CHECKS)
def test_semantic_compatibility_matches_registry_rules(source: str, target: str) -> None:
    source_schema = SLOT_SCHEMA_REGISTRY[source]
    target_schema = SLOT_SCHEMA_REGISTRY[target]
    expected = (
        source_schema.semantics == target_schema.semantics
        or target_schema.semantics in source_schema.allowed_targets
        or source_schema.semantics in target_schema.allowed_targets
    )

    assert is_semantically_compatible(source, target) is expected


@given(
    known=st.sampled_from(_KNOWN_SLOTS),
    suffix=st.text(
        alphabet=st.characters(min_codepoint=97, max_codepoint=122),
        min_size=1,
        max_size=12,
    ),
)
@settings(max_examples=100, suppress_health_check=_HEALTH_CHECKS)
def test_unknown_slots_are_left_unconstrained(known: str, suffix: str) -> None:
    unknown = f"__unknown__{suffix}"

    assert is_semantically_compatible(unknown, known) is True
    assert is_semantically_compatible(known, unknown) is True


def test_semantic_compatibility_error_reports_meaningful_semantics() -> None:
    with pytest.raises(SemanticCompatibilityError, match="continuous_outcome"):
        raise SemanticCompatibilityError("outcome", "instrument")

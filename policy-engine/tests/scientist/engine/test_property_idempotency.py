"""Property-based tests for idempotency key computation."""

from __future__ import annotations

import re

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.scientist.engine.idempotency import compute_idempotency_key
from polisyos.scientist.engine.protocol import NodeSpec
from polisyos.scientist.engine.state import ExperimentState

pytestmark = pytest.mark.property


def _make_spec(state_reads: list[str] | None = None) -> NodeSpec:
    meta = ComponentMetadata(
        component_id=ComponentId.parse("test.node@1.0.0"),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name="Test",
        description="Test node",
        tags=["test"],
        capabilities=Capability.SCIENTIST_NODE,
    )
    return NodeSpec(metadata=meta, state_reads=state_reads or [])


@given(
    run_id=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))
)
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_key_is_64_char_hex(run_id: str):
    """Idempotency key is always a 64-character hex string."""
    state = ExperimentState(run_id=run_id)
    spec = _make_spec()
    key = compute_idempotency_key(spec, state)
    assert len(key) == 64
    assert re.match(r"^[0-9a-f]{64}$", key)


def test_determinism():
    """Same inputs always produce the same key."""
    state = ExperimentState(run_id="R_det", params={"x": 42})
    spec = _make_spec(state_reads=["params.x"])
    key1 = compute_idempotency_key(spec, state)
    key2 = compute_idempotency_key(spec, state)
    assert key1 == key2


def test_different_state_reads_different_key():
    """Different state values produce different keys."""
    spec = _make_spec(state_reads=["params.x"])
    state_a = ExperimentState(run_id="R_diff", params={"x": 1})
    state_b = ExperimentState(run_id="R_diff", params={"x": 2})
    key_a = compute_idempotency_key(spec, state_a)
    key_b = compute_idempotency_key(spec, state_b)
    assert key_a != key_b


def test_different_run_id_different_key():
    """Different run_ids produce different keys."""
    spec = _make_spec()
    key_a = compute_idempotency_key(spec, ExperimentState(run_id="R_a"))
    key_b = compute_idempotency_key(spec, ExperimentState(run_id="R_b"))
    assert key_a != key_b

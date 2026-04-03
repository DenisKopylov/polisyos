"""Tests for Phase 6: step() specialization with mechanism dispatch and NaN guards."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

import jax
import jax.numpy as jnp
import pytest

from polisyos.foundry._executor_models import ExecutionStrictness
from polisyos.foundry.calibration.pure_executor import PreparedNode, StaticBundle
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.runtime import NaNDetectedError, run_scan, step
from polisyos.foundry.runtime.nan_guard import NaNGuard
from polisyos.ir.kernel import (
    MechanismTypeRegistry,
    MergeRuleKind,
    MergeRuleRegistry,
    MergeRuleSpec,
    SlotRegistry,
    SlotScope,
    SlotSpec,
    SlotKind,
    SlotValueType,
)
from polisyos.ir.kernel.merge_rules import MergeRuleRef


# ---------------------------------------------------------------------------
# Helpers: minimal mock mechanism that produces predictable patches
# ---------------------------------------------------------------------------


class _AddIncomeMechanism:
    """Toy mechanism: adds a fixed delta to agents.income."""

    fidelity = "relaxed"
    debug_mode = False

    def __init__(self, delta: float = 100.0):
        self._delta = delta

    def emit_patches(self, state, key, *, target_mask=None):
        income = state.agents.income
        delta = jnp.full_like(income, self._delta)
        next_key = jax.random.split(key)[0]
        return {
            "income": [{"delta": delta, "base_value": income, "new_value": income + delta}],
        }, next_key


class _NaNMechanism:
    """Toy mechanism: produces NaN in agents.income."""

    fidelity = "relaxed"
    debug_mode = False

    def emit_patches(self, state, key, *, target_mask=None):
        income = state.agents.income
        nan_values = jnp.full_like(income, float("nan"))
        next_key = jax.random.split(key)[0]
        return {
            "income": [{"delta": nan_values, "base_value": income, "new_value": nan_values}],
        }, next_key


def _make_bundle(mechanism, slot_id: str = "income") -> StaticBundle:
    """Build a minimal StaticBundle around a single mechanism."""
    node = PreparedNode(
        node_id="test_node",
        mechanism_type="test",
        rank=0,
        start=0,
        end=999,
        mechanism=mechanism,
        outputs=[slot_id],
    )
    slot_spec = SlotSpec(
        slot_id=slot_id,
        scope=SlotScope.PER_AGENT,
        value_type=SlotValueType.DECIMAL,
        kind=SlotKind.FLOW,
        state_path="agents.income",
        merge_rule=MergeRuleRef(rule_id="sum_default"),
    )
    slot_registry = SlotRegistry(slots={slot_id: slot_spec})
    merge_registry = MergeRuleRegistry(
        rules={"sum_default": MergeRuleSpec(rule_id="sum_default", kind=MergeRuleKind.SUM)},
    )
    mechanism_registry = MechanismTypeRegistry(mechanisms={})
    return StaticBundle(
        nodes=[node],
        slot_registry=slot_registry,
        mechanism_registry=mechanism_registry,
        merge_registry=merge_registry,
        selector_field_registry=None,
        trainables=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_step_without_bundle_returns_identity():
    """step() with no static_bundle returns state unchanged and skipped flag."""
    state = jnp.array([1.0, 2.0])
    key = jax.random.PRNGKey(0)
    controls = jnp.array([0.1])

    result_state, trace = step(state, controls, key, t=0, static_bundle=None)

    assert jnp.array_equal(result_state, state)
    assert trace == {"skipped": True}


def test_step_with_static_bundle_applies_nodes():
    """step() with a StaticBundle actually mutates state via apply_nodes."""
    base_state = GlobalState.empty(n_agents=4, n_firms=1)
    key = jax.random.PRNGKey(42)
    controls = jnp.array([0.0])
    delta = 100.0

    bundle = _make_bundle(_AddIncomeMechanism(delta=delta))
    new_state, trace = step(base_state, controls, key, t=0, static_bundle=bundle)

    expected_income = base_state.agents.income + delta
    assert jnp.allclose(new_state.agents.income, expected_income), (
        f"Expected income {expected_income}, got {new_state.agents.income}"
    )
    assert "skipped" not in trace
    assert trace["t"] == 0


def test_step_nan_guard_strict_raises():
    """Under FAIL_CLOSED, step() raises NaNDetectedError when mechanism produces NaN."""
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    key = jax.random.PRNGKey(7)
    controls = jnp.array([0.0])

    bundle = _make_bundle(_NaNMechanism())
    guard = NaNGuard(enabled=True, check_interval=1, max_diagnostics=10)

    with pytest.raises(NaNDetectedError) as exc_info:
        step(
            base_state, controls, key, t=0,
            static_bundle=bundle,
            nan_guard=guard,
            strictness=ExecutionStrictness.FAIL_CLOSED,
        )

    assert exc_info.value.node_id == "test_node"
    assert exc_info.value.report is not None
    assert not exc_info.value.report.ok


def test_step_nan_guard_research_logs():
    """Under RESEARCH strictness, NaN is logged but no exception raised."""
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    key = jax.random.PRNGKey(7)
    controls = jnp.array([0.0])

    bundle = _make_bundle(_NaNMechanism())
    guard = NaNGuard(enabled=True, check_interval=1, max_diagnostics=10)

    new_state, trace = step(
        base_state, controls, key, t=0,
        static_bundle=bundle,
        nan_guard=guard,
        strictness=ExecutionStrictness.RESEARCH,
    )

    # NaN was detected but not raised
    assert "nan_nodes" in trace
    assert "test_node" in trace["nan_nodes"]

    # Guard accumulated diagnostics
    report = guard.get_report()
    assert not report.ok
    assert len(report.diagnostics) > 0


def test_run_scan_propagates_monotone_time_index():
    """run_scan() should forward the real step index into step()/trace."""
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    key = jax.random.PRNGKey(11)
    controls_seq = jnp.zeros((3, 1))
    bundle = _make_bundle(_AddIncomeMechanism(delta=1.0))

    traces = run_scan(base_state, controls_seq, key, static_bundle=bundle)

    assert jnp.array_equal(traces["t"], jnp.array([0, 1, 2], dtype=jnp.int32))


def test_run_scan_accepts_states_with_cell_blocks():
    """run_scan() should not crash when runtime state carries optional cell blocks."""
    base_state = GlobalState.empty(n_agents=2, n_firms=1, n_cells=3, n_household_cells=2)
    key = jax.random.PRNGKey(17)
    controls_seq = jnp.zeros((2, 1))
    bundle = _make_bundle(_AddIncomeMechanism(delta=1.0))

    traces = run_scan(base_state, controls_seq, key, static_bundle=bundle)

    assert jnp.array_equal(traces["t"], jnp.array([0, 1], dtype=jnp.int32))

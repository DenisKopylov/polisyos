"""Tests for agent_sim PureExecutor and MechanismOrder."""
from __future__ import annotations

import jax.numpy as jnp
import pytest

from polisyos.foundry.agent_sim.executor import MechanismOrder, PureExecutor
from polisyos.foundry.agent_sim.mechanism import Mechanism, MechanismSpec
from polisyos.foundry.agent_sim.mechanisms import TaxationMechanism
from polisyos.foundry.contracts.fidelity import FidelityLevel


class _DummyMechanism(Mechanism):
    """Trivial mechanism that does nothing."""

    def __init__(self, name: str, reads: frozenset, writes: frozenset, stochastic: bool = False):
        self._spec = MechanismSpec(name=name, reads=reads, writes=writes, parameters={}, stochastic=stochastic)

    @property
    def spec(self):
        return self._spec

    def apply(self, state, rng_key, fidelity):
        return state, {}


class TestMechanismOrder:
    def test_single_mechanism(self):
        m = _DummyMechanism("a", frozenset({"x"}), frozenset({"y"}))
        order = MechanismOrder([m])
        assert order.order == [0]

    def test_dependency_ordering(self):
        """If mech B reads what A writes, A should come first."""
        a = _DummyMechanism("a", frozenset(), frozenset({"x"}))
        b = _DummyMechanism("b", frozenset({"x"}), frozenset({"y"}))
        order = MechanismOrder([a, b])
        assert order.order.index(0) < order.order.index(1)

    def test_circular_dependency_raises(self):
        a = _DummyMechanism("a", frozenset({"y"}), frozenset({"x"}))
        b = _DummyMechanism("b", frozenset({"x"}), frozenset({"y"}))
        with pytest.raises(ValueError, match="Circular"):
            MechanismOrder([a, b])


class TestPureExecutor:
    def test_step_returns_metrics(self, simple_state):
        tax = TaxationMechanism(progressive_factor=0.1)
        executor = PureExecutor([tax])
        new_state, metrics = executor.step(simple_state)
        assert "taxation/total_tax_collected" in metrics
        assert int(new_state.time_step) == int(simple_state.time_step) + 1

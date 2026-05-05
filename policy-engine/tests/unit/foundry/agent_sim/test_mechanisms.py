"""Tests for agent_sim mechanisms (Taxation, Consumption)."""

from __future__ import annotations

import jax
from polisyos.foundry.agent_sim.mechanisms import (
    ConsumptionMechanism,
    SharedPolicy,
    TaxationMechanism,
)
from polisyos.foundry.contracts.fidelity import FidelityLevel


class TestTaxationMechanism:
    def test_spec_attributes(self):
        mech = TaxationMechanism(progressive_factor=0.1)
        assert mech.spec.name == "taxation"
        assert not mech.spec.stochastic
        assert "agents.income" in mech.spec.reads

    def test_apply_reduces_income(self, simple_state):
        mech = TaxationMechanism(progressive_factor=0.1)
        pre_income = simple_state.agents.income.sum()
        new_state, metrics = mech.apply(simple_state, None, FidelityLevel.SURROGATE_FLUID)
        post_income = new_state.agents.income.sum()
        assert float(post_income) <= float(pre_income) + 1e-6
        assert "total_tax_collected" in metrics

    def test_zero_progressive_factor(self, simple_state):
        mech = TaxationMechanism(progressive_factor=0.0)
        _, metrics = mech.apply(simple_state, None, FidelityLevel.SURROGATE_FLUID)
        assert float(metrics["total_tax_collected"]) >= 0.0


class TestConsumptionMechanism:
    def test_spec_is_stochastic(self):
        key = jax.random.PRNGKey(0)
        policy = SharedPolicy(obs_dim=5, action_dim=1, hidden_dims=[8], key=key)
        mech = ConsumptionMechanism(policy=policy, min_consumption=0.01)
        assert mech.spec.stochastic is True
        assert "agents.consumption" in mech.spec.writes

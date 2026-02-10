import jax
import jax.numpy as jnp

from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.mechanisms.fiscal import IncomeTax, TaxSubsidy, compute_tax
from polisyos.foundry.executor import apply_patch_map
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def test_budget_accounting() -> None:
    n_agents = 10
    state = GlobalState.empty(n_agents=n_agents, n_firms=2)
    state = state.replace(
        agents=state.agents.replace(
            income=jnp.ones(n_agents) * 1000.0,
            reported_income=jnp.ones(n_agents) * 1000.0,
        ),
        government_balance=jnp.array(0.0),
    )

    tax_mech = IncomeTax(n_agents=n_agents, rate=0.10)
    patches, _ = tax_mech.emit_patches(state, jax.random.PRNGKey(0))
    state = apply_patch_map(
        state,
        patches,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        default_node_id="tax",
    )

    assert float(state.government_balance) == 1000.0

    subsidy_mech = TaxSubsidy(n_agents=n_agents, rate=0.50)
    patches, _ = subsidy_mech.emit_patches(state, jax.random.PRNGKey(1))
    state = apply_patch_map(
        state,
        patches,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        default_node_id="subsidy",
    )

    assert float(state.government_balance) == -3500.0


def test_income_tax_compute_matches_patches() -> None:
    n_agents = 4
    state = GlobalState.empty(n_agents=n_agents, n_firms=1)
    reported = jnp.array([100.0, 50.0, 25.0, 0.0], dtype=jnp.float32)
    state = state.replace(
        agents=state.agents.replace(
            income=jnp.array([100.0, 50.0, 25.0, 0.0], dtype=jnp.float32),
            reported_income=reported,
        )
    )

    mech = IncomeTax(n_agents=n_agents, rate=0.2)
    patches, _ = mech.emit_patches(state, jax.random.PRNGKey(0))
    tax_amount = compute_tax(state, mech.rate)

    assert jnp.allclose(-patches["agents.income"][0]["delta"], tax_amount)
    assert jnp.isclose(patches["government.balance"][0]["delta"], jnp.sum(tax_amount))

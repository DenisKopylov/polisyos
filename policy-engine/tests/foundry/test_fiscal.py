import jax
import jax.numpy as jnp

from polisyos.foundry.domain.state import GlobalState
from polisyos.foundry.executor import apply_patch_map
from polisyos.foundry.fiscal import IncomeTax, TaxSubsidy
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def test_budget_accounting() -> None:
    n_agents = 10
    state = GlobalState.empty(n_agents=n_agents, n_firms=2)
    state = state.replace(
        agents=state.agents.replace(income=jnp.ones(n_agents) * 1000.0),
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

import equinox as eqx
import jax
import jax.numpy as jnp

from polisyos.foundry.mechanisms.fiscal import TaxSubsidy
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.executor import apply_patch_map
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def test_tax_subsidy_gradient_value() -> None:
    n_agents = 10
    state = GlobalState.empty(n_agents=n_agents, n_firms=2)
    state = state.replace(agents=state.agents.replace(income=jnp.ones(n_agents) * 100.0))

    policy = TaxSubsidy(rate=0.10, n_agents=n_agents)

    def loss_fn(policy_model, current_state):
        patches, _ = policy_model.emit_patches(current_state, jax.random.PRNGKey(0))
        next_state = apply_patch_map(
            current_state,
            patches,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            default_node_id="subsidy",
        )
        total_gdp = jnp.sum(next_state.agents.income)
        return -total_gdp

    grad_fn = eqx.filter_grad(loss_fn)
    grads = grad_fn(policy, state)

    assert bool(jnp.isclose(grads.rate, -1000.0))


def test_tax_subsidy_gradient_sign_and_invariants() -> None:
    n_agents = 5
    state = GlobalState.empty(n_agents=n_agents, n_firms=1)
    state = state.replace(agents=state.agents.replace(income=jnp.ones(n_agents) * 1000.0))
    key = jax.random.PRNGKey(0)

    mech = TaxSubsidy(rate=0.1, n_agents=n_agents)

    def loss_fn(mechanism):
        patches, _ = mechanism.emit_patches(state, key)
        next_state = apply_patch_map(
            state,
            patches,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            default_node_id="subsidy",
        )
        return -jnp.mean(next_state.agents.income)

    grad_fn = eqx.filter_grad(loss_fn)
    grads = grad_fn(mech)

    assert grads.rate is not None
    assert float(grads.rate) < 0.0

    patches, _ = mech.emit_patches(state, key)
    next_state = apply_patch_map(
        state,
        patches,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        default_node_id="subsidy",
    )
    assert mech.invariants(next_state)

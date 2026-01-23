import jax
import jax.numpy as jnp

from polisyos.foundry.agent_sim import (
    ConsumptionMechanism,
    GlobalState,
    Mechanism,
    MechanismOrder,
    MechanismSpec,
    PureExecutor,
    SharedPolicy,
    TaxationMechanism,
)
from polisyos.foundry.types import FidelityLevel


class ShockMechanism(Mechanism):
    @property
    def spec(self) -> MechanismSpec:
        return MechanismSpec(
            name="shock",
            reads=frozenset({"agents.wealth"}),
            writes=frozenset({"agents.wealth"}),
            parameters={},
            stochastic=True,
        )

    def apply(self, state: GlobalState, rng_key, fidelity: FidelityLevel):
        del fidelity
        noise = jax.random.normal(rng_key, shape=state.agents.wealth.shape)
        new_wealth = state.agents.wealth + noise
        new_wealth = jnp.where(state.agents.active, new_wealth, state.agents.wealth)
        new_agents = state.agents.replace(wealth=new_wealth)
        return state.replace(agents=new_agents), {"mean_shock": jnp.mean(noise)}


def test_active_mask_propagation() -> None:
    n_agents = 8
    state = GlobalState.empty(n_agents, seed=0)
    active = jnp.array([True] * 4 + [False] * 4)
    agents = state.agents.replace(
        active=active,
        income=jnp.ones(n_agents, dtype=jnp.float32) * 100.0,
    )
    policy = state.policy.replace(tax_rate=jnp.array(0.2, dtype=jnp.float32))
    state = state.replace(agents=agents, policy=policy)

    mech = TaxationMechanism(progressive_factor=0.0)
    executor = PureExecutor([mech], prng_config={"taxation": 1})
    new_state, _ = executor.step(state)

    assert bool(jnp.allclose(new_state.agents.income[~active], state.agents.income[~active]))
    assert bool(jnp.all(new_state.agents.income[active] < state.agents.income[active]))


def test_prng_reproducibility() -> None:
    n_agents = 6
    state1 = GlobalState.empty(n_agents, seed=42)
    state2 = GlobalState.empty(n_agents, seed=42)

    executor = PureExecutor([ShockMechanism()], prng_config={"shock": 99})
    final1, _ = executor.run(state1, n_steps=5)
    final2, _ = executor.run(state2, n_steps=5)

    assert bool(jnp.allclose(final1.agents.wealth, final2.agents.wealth))


def test_mechanism_order() -> None:
    key = jax.random.PRNGKey(0)
    policy = SharedPolicy(obs_dim=10, action_dim=1, hidden_dims=(8,), key=key)
    consumption_mech = ConsumptionMechanism(policy=policy)
    taxation_mech = TaxationMechanism(progressive_factor=0.1)

    order = MechanismOrder([consumption_mech, taxation_mech])
    tax_idx = order.order.index(1)
    cons_idx = order.order.index(0)
    assert tax_idx < cons_idx

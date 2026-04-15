import jax
import jax.numpy as jnp
import pytest

from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.executor import apply_patch_map
from polisyos.foundry.mechanisms.labor import LaborMarketMechanism
from polisyos.ir.kernel.merge_rules import DEFAULT_MERGE_RULE_REGISTRY
from polisyos.ir.kernel.slots import DEFAULT_SLOT_REGISTRY


def _apply_labor(
    state: GlobalState,
    mechanism: LaborMarketMechanism,
    *,
    target_mask: jnp.ndarray | None = None,
) -> GlobalState:
    patches, _ = mechanism.emit_patches(
        state,
        jax.random.PRNGKey(0),
        target_mask=target_mask,
    )
    return apply_patch_map(
        state,
        patches,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        default_node_id="labor",
    )


def test_labor_market_assigns_no_jobs_when_threshold_zero() -> None:
    state = GlobalState.empty(n_agents=4, n_firms=2).replace(
        agents=GlobalState.empty(n_agents=4, n_firms=2).agents.replace(
            active=jnp.array([True, True, False, True], dtype=jnp.bool_),
            income=jnp.array([10.0, 20.0, 30.0, 40.0], dtype=jnp.float32),
            is_employed=jnp.array([True, False, True, False], dtype=jnp.bool_),
            employer_id=jnp.array([0, -1, 1, -1], dtype=jnp.int32),
            skill_level=jnp.ones((4,), dtype=jnp.float32),
        ),
        firms=GlobalState.empty(n_agents=4, n_firms=2).firms.replace(
            wage_offer=jnp.array([50.0, 60.0], dtype=jnp.float32),
        ),
    )

    next_state = _apply_labor(
        state,
        LaborMarketMechanism(employment_threshold=0.0),
    )

    assert next_state.agents.is_employed.tolist() == [False, False, True, False]
    assert next_state.agents.employer_id.tolist() == [-1, -1, 1, -1]
    assert next_state.agents.income.tolist() == [0.0, 0.0, 30.0, 0.0]
    assert next_state.firms.labor_count.tolist() == [0.0, 0.0]


def test_labor_market_target_mask_updates_only_selected_agents() -> None:
    state = GlobalState.empty(n_agents=4, n_firms=2).replace(
        agents=GlobalState.empty(n_agents=4, n_firms=2).agents.replace(
            income=jnp.array([10.0, 20.0, 30.0, 40.0], dtype=jnp.float32),
            is_employed=jnp.array([False, False, True, False], dtype=jnp.bool_),
            employer_id=jnp.array([-1, -1, 1, -1], dtype=jnp.int32),
            skill_level=jnp.ones((4,), dtype=jnp.float32),
        ),
        firms=GlobalState.empty(n_agents=4, n_firms=2).firms.replace(
            wage_offer=jnp.array([50.0, 60.0], dtype=jnp.float32),
        ),
    )
    target_mask = jnp.array([True, False, False, True], dtype=jnp.bool_)

    next_state = _apply_labor(
        state,
        LaborMarketMechanism(employment_threshold=1.0),
        target_mask=target_mask,
    )

    assert bool(next_state.agents.is_employed[0])
    assert bool(next_state.agents.is_employed[3])
    assert int(next_state.agents.employer_id[0]) >= 0
    assert int(next_state.agents.employer_id[3]) >= 0
    assert float(next_state.agents.income[0]) >= 50.0
    assert float(next_state.agents.income[3]) >= 50.0
    assert bool(next_state.agents.is_employed[2])
    assert int(next_state.agents.employer_id[2]) == 1
    assert float(next_state.agents.income[2]) == 30.0
    assert bool(jnp.isclose(jnp.sum(next_state.firms.labor_count), 3.0))


def test_labor_market_rejects_target_mask_shape_mismatch() -> None:
    state = GlobalState.empty(n_agents=3, n_firms=1)
    mechanism = LaborMarketMechanism(employment_threshold=0.5)

    with pytest.raises(ValueError, match="target_mask must match agent count"):
        mechanism.emit_patches(
            state,
            jax.random.PRNGKey(0),
            target_mask=jnp.array([True, False], dtype=jnp.bool_),
        )


def test_labor_market_rejects_zero_firms() -> None:
    state = GlobalState.empty(n_agents=3, n_firms=0)
    mechanism = LaborMarketMechanism(employment_threshold=0.5)

    with pytest.raises(ValueError, match="at least one firm"):
        mechanism.emit_patches(state, jax.random.PRNGKey(0))


def test_labor_market_advances_rng_key_after_independent_draws() -> None:
    state = GlobalState.empty(n_agents=2, n_firms=2)
    mechanism = LaborMarketMechanism(employment_threshold=0.5)
    seed = jax.random.PRNGKey(0)

    _, next_key = mechanism.emit_patches(state, seed)

    assert not bool(jnp.array_equal(seed, next_key))

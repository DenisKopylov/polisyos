import jax
import jax.numpy as jnp

from polisyos.foundry.contracts.state import GlobalState, ModelScalarState


def test_global_state_shapes_and_employment_counts() -> None:
    n_agents = 100
    n_firms = 10

    state = GlobalState.empty(n_agents=n_agents, n_firms=n_firms)

    assert state.agents.size == n_agents
    assert state.firms.size == n_firms

    new_employer_ids = state.agents.employer_id.at[:10].set(0)
    new_agents = state.agents.replace(employer_id=new_employer_ids)
    state = state.replace(agents=new_agents)

    mask_employed = new_employer_ids >= 0
    safe_ids = jnp.where(mask_employed, new_employer_ids, 0)
    counts = jax.ops.segment_sum(jnp.where(mask_employed, 1.0, 0.0), safe_ids, n_firms)

    assert float(counts[0]) == 10.0


def test_model_scalar_state_uses_fixed_float32_values_and_explicit_presence() -> None:
    carrier = ModelScalarState.empty(2)

    assert carrier.values.shape == (2,)
    assert carrier.values.dtype == jnp.float32
    assert carrier.present.shape == (2,)
    assert carrier.present.dtype == jnp.bool_
    assert carrier.values.tolist() == [0.0, 0.0]
    assert carrier.present.tolist() == [False, False]


def test_model_scalar_state_rejects_dynamic_shape_or_dtype_mismatch() -> None:
    import pytest

    with pytest.raises(ValueError, match="values_require_float32"):
        ModelScalarState(
            values=jnp.zeros((2,), dtype=jnp.int32),
            present=jnp.zeros((2,), dtype=jnp.bool_),
        )
    with pytest.raises(ValueError, match="presence_requires_bool"):
        ModelScalarState(
            values=jnp.zeros((2,), dtype=jnp.float32),
            present=jnp.zeros((2,), dtype=jnp.int32),
        )
    with pytest.raises(ValueError, match="shape_mismatch"):
        ModelScalarState(
            values=jnp.zeros((2,), dtype=jnp.float32),
            present=jnp.zeros((1,), dtype=jnp.bool_),
        )

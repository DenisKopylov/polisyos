import jax
import jax.numpy as jnp
from polisyos.foundry import runtime


def test_execute_program_batch_matches_single():
    key = jax.random.PRNGKey(0)
    state = jnp.array([1.0, 2.0])
    controls = jnp.array([[0.1, 0.2], [0.3, 0.4]])

    single_trace = runtime.run_scan(state, controls, key)

    batch_states = jnp.stack([state])
    batch_controls = jnp.stack([controls])
    batch_trace = runtime.execute_program_batch(batch_states, batch_controls, key)

    # Without a static_bundle, step() returns {"skipped": True} —
    # verify batch and single produce the same trace structure.
    assert jax.tree_util.tree_all(
        jax.tree_util.tree_map(
            lambda a, b: jnp.array_equal(a, b),
            jax.tree_util.tree_map(lambda x: x[0], batch_trace),
            single_trace,
        )
    )


def test_execute_program_batch_deterministic_keys():
    key = jax.random.PRNGKey(123)
    states = jnp.stack([jnp.array([0.0]), jnp.array([1.0])])
    controls = jnp.stack([jnp.array([[0.0]]), jnp.array([[0.0]])])

    trace1 = runtime.execute_program_batch(states, controls, key)
    trace2 = runtime.execute_program_batch(states, controls, key)

    # Same input + key => identical outputs
    assert jax.tree_util.tree_all(
        jax.tree_util.tree_map(lambda a, b: jnp.array_equal(a, b), trace1, trace2)
    )

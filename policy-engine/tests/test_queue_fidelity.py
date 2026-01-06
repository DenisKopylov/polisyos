import equinox as eqx
import jax
import jax.numpy as jnp

from src.foundry.queue import QueueMechanism, QueueState, fidelity_gap_report, simulate_queue
from src.foundry.types import FidelityLevel


def _tree_shapes(tree):
    def shape_or_none(x):
        return getattr(x, "shape", None)

    return jax.tree_util.tree_map(shape_or_none, tree)


def _assert_stable_tree(a, b):
    assert jax.tree_util.tree_structure(a) == jax.tree_util.tree_structure(b)
    assert _tree_shapes(a) == _tree_shapes(b)


def test_queue_jit_step_stable():
    state = QueueState(queue_length=jnp.array(10.0))
    mech = QueueMechanism(
        service_rate=4.0,
        arrival_rate=3.0,
        fidelity=FidelityLevel.SURROGATE_FLUID,
    )

    @eqx.filter_jit
    def step(mech, state, key):
        return mech.step(state, key)

    s1 = step(mech, state, jax.random.PRNGKey(0))
    s2 = step(mech, s1, jax.random.PRNGKey(1))

    _assert_stable_tree(state, s1)
    _assert_stable_tree(s1, s2)


def test_queue_fidelity_gap_small():
    key = jax.random.PRNGKey(0)
    state = QueueState(queue_length=jnp.array(5.0))

    fluid = QueueMechanism(
        service_rate=2.0,
        arrival_rate=2.5,
        fidelity=FidelityLevel.SURROGATE_FLUID,
    )
    relaxed = QueueMechanism(
        service_rate=2.0,
        arrival_rate=2.5,
        temperature=1.0,
        fidelity=FidelityLevel.RELAXED_DISCRETE,
    )

    @eqx.filter_jit
    def run(mech):
        return simulate_queue(mech, state, key, steps=10)

    final_fluid = run(fluid)
    final_relaxed = run(relaxed)
    report = fidelity_gap_report(final_fluid, final_relaxed)

    assert report["abs_diff"] < 5.0
    assert report["rel_diff"] < 1.0

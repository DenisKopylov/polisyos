"""Exercise cross-sectional scalar schedules on the native JAX executor."""

from __future__ import annotations

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.foundry.calibration import pure_executor
from polisyos.foundry.calibration.pure_executor import PreparedNode, StaticBundle, run_pure_batch
from polisyos.foundry.contracts.state import GlobalState
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)


def _bundle(mechanism) -> StaticBundle:
    return StaticBundle(
        nodes=[
            PreparedNode(
                node_id="scheduled-log",
                mechanism_type="scheduled_log",
                rank=0,
                start=1,
                end=1,
                mechanism=mechanism,
                outputs=["agents.income"],
            )
        ],
        incoming_dependencies={},
        slot_registry=DEFAULT_SLOT_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        trainables=[],
    )


def _inputs(income):
    states = [GlobalState.empty(n_agents=1, n_firms=1) for _ in range(income.shape[0])]
    states = [
        state.replace(
            agents=state.agents.replace(income=income[index]),
            step=jnp.array(17 + index, dtype=jnp.int32),
        )
        for index, state in enumerate(states)
    ]
    stacked = jax.tree_util.tree_map(lambda *rows: jnp.stack(rows), *states)
    root_key = jax.random.key(19)
    keys = jnp.stack([jax.random.fold_in(root_key, index) for index in range(len(states))])
    return stacked, keys


def _run(income, times, bundle):
    state, keys = _inputs(income)
    return run_pure_batch(
        state,
        times=times,
        keys=keys,
        bundle=bundle,
        metric_paths=["agents.income", "step"],
    )


def _transform(run, income, transform):
    if transform == "eager":
        result = run(income)
    elif transform == "jit":
        result = jax.jit(run)(income)
    elif transform == "grad":
        result = jax.grad(lambda x: jnp.sum(run(x)))(income)
    else:
        result = jax.hessian(lambda x: jnp.sum(run(x)))(income)
    result.block_until_ready()
    jax.effects_barrier()
    return result


@pytest.mark.parametrize("transform", ["eager", "jit", "grad", "hessian"])
def test_batch_preserves_inactive_invalid_row_and_exact_active_derivatives(transform):
    observed = []

    class LogEmitter:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            jax.debug.callback(lambda x: observed.append(x.tolist()), state.agents.income)
            return {"agents.income": [{"delta": jnp.log(state.agents.income)}]}, key

    bundle = _bundle(LogEmitter())
    times = jnp.array([0, 1], dtype=jnp.int32)
    income = jnp.array([[-1.0], [2.0]], dtype=jnp.float32)
    result = _transform(lambda x: _run(x, times, bundle)[1]["agents.income"], income, transform)
    expected = {
        "eager": [[-1.0], [2.0 + np.log(2.0)]],
        "jit": [[-1.0], [2.0 + np.log(2.0)]],
        "grad": [[1.0], [1.5]],
        "hessian": np.diag([0.0, -0.25]).reshape((2, 1, 2, 1)),
    }[transform]
    np.testing.assert_allclose(result, expected, rtol=1e-6)
    assert observed == [[2.0]]


@pytest.mark.parametrize("transform", ["eager", "jit", "grad", "hessian"])
def test_batch_active_invalid_log_keeps_failure_signal(transform):
    observed = []

    class LogEmitter:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            jax.debug.callback(lambda x: observed.append(x.tolist()), state.agents.income)
            return {"agents.income": [{"delta": jnp.log(state.agents.income)}]}, key

    bundle = _bundle(LogEmitter())
    times = jnp.array([0, 1], dtype=jnp.int32)
    income = jnp.zeros((2, 1), dtype=jnp.float32)
    result = _transform(lambda x: _run(x, times, bundle)[1]["agents.income"], income, transform)
    assert not np.all(np.isfinite(result))
    assert observed == [[0.0]]


@pytest.mark.parametrize("typed_keys", [False, True])
def test_batch_preserves_row_state_time_and_distinct_stochastic_streams(typed_keys):
    observed_keys = []

    class RandomEmitter:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            jax.debug.callback(lambda k: observed_keys.append(k.tolist()), jax.random.key_data(key))
            draw = jax.random.uniform(
                key, state.agents.income.shape, dtype=state.agents.income.dtype
            )
            return {"agents.income": [{"delta": draw}]}, key

    income = jnp.array([[3.0], [5.0], [7.0]], dtype=jnp.float32)
    stacked, keys = _inputs(income)
    if not typed_keys:
        keys = jax.random.key_data(keys)
    times = jnp.array([1, 0, 1], dtype=jnp.int32)
    result, metrics = jax.jit(
        lambda state, row_keys: run_pure_batch(
            state,
            times=times,
            keys=row_keys,
            bundle=_bundle(RandomEmitter()),
            metric_paths=["agents.income", "step"],
        )
    )(stacked, keys)
    result.agents.income.block_until_ready()
    jax.effects_barrier()
    expected = income.at[0].add(
        jax.random.uniform(jax.random.split(keys[0])[1], (1,), dtype=income.dtype)
    )
    expected = expected.at[2].add(
        jax.random.uniform(jax.random.split(keys[2])[1], (1,), dtype=income.dtype)
    )
    np.testing.assert_array_equal(metrics["step"], [17, 18, 19])
    np.testing.assert_allclose(metrics["agents.income"], expected)
    np.testing.assert_array_equal(result.agents.income, metrics["agents.income"])
    assert observed_keys == [
        jax.random.key_data(jax.random.split(keys[index])[1]).tolist() for index in [0, 2]
    ]
    assert observed_keys[0] != observed_keys[1]


@pytest.mark.parametrize("malformed", ["float_time", "time_rank", "empty", "keys", "state"])
def test_batch_rejects_malformed_row_axes_before_emitter(malformed):
    traced = []

    class Emitter:
        def emit_patches(self, state, key, *, target_mask=None):
            traced.append(True)
            return {"agents.income": [{"delta": jnp.zeros_like(state.agents.income)}]}, key

    state, keys = _inputs(jnp.array([[1.0], [2.0]]))
    times = jnp.array([0, 1], dtype=jnp.int32)
    if malformed == "float_time":
        times = times.astype(jnp.float32)
    elif malformed == "time_rank":
        times = times[:, None]
    elif malformed == "empty":
        times = times[:0]
    elif malformed == "keys":
        keys = keys[:1]
    else:
        state = state.replace(step=state.step[:1])
    with pytest.raises(ValueError, match="run_pure_batch"):
        run_pure_batch(state, times=times, keys=keys, bundle=_bundle(Emitter()))
    assert traced == []


def test_batch_mapped_predicate_refuses_before_emitter():
    observed = []

    class Emitter:
        def emit_patches(self, state, key, *, target_mask=None):
            jax.debug.callback(lambda x: observed.append(x.tolist()), state.agents.income)
            return {"agents.income": [{"delta": jnp.log(state.agents.income)}]}, key

    bundle = _bundle(Emitter())
    income = jnp.array([[-1.0], [2.0]])
    with pytest.raises(ValueError, match="does not support mapped schedule predicates"):
        jax.vmap(lambda times: _run(income, times, bundle))(
            jnp.array([[0, 1], [1, 0]], dtype=jnp.int32)
        )
    jax.effects_barrier()
    assert observed == []


def test_map_removal_with_markers_retained_exposes_inactive_numerical_execution(monkeypatch):
    observed = []

    class LogEmitter:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            jax.debug.callback(lambda x: observed.append(x.tolist()), state.agents.income)
            return {"agents.income": [{"delta": jnp.log(state.agents.income)}]}, key

    # Preserve the function, row inputs, and neutral branch markers while
    # removing the scalar-map property and its existing mapped admission.
    monkeypatch.setattr(pure_executor.jax.lax, "map", lambda fn, xs: jax.vmap(fn)(xs))
    monkeypatch.setattr(pure_executor, "_admit_schedule_predicate", lambda active: active)
    result = _run(
        jnp.array([[-1.0], [2.0]]), jnp.array([0, 1], dtype=jnp.int32), _bundle(LogEmitter())
    )[1]["agents.income"]
    result.block_until_ready()
    jax.effects_barrier()
    np.testing.assert_allclose(result, [[-1.0], [2.0 + np.log(2.0)]])
    assert observed == [[-1.0], [2.0]]
    # A finite output proxy is green, but the defining no-inactive-emission
    # predicate from the positive tests is false.
    assert observed != [[2.0]]

from __future__ import annotations

import jax
import jax.numpy as jnp


def step(state, controls, root_key, t: int, static_bundle=None):
    """Placeholder pure JAX step; returns state unchanged and empty trace."""
    return state, {"t": t, "controls": controls}


step_jit = jax.jit(step)


def run_scan(initial_state, controls_seq, root_key, static_bundle=None):
    """Run a lax.scan over controls_seq using pure step function."""

    def _body(carry, control):
        state, key = carry
        key, sub = jax.random.split(key)
        next_state, trace = step(state, control, sub, t=0, static_bundle=static_bundle)
        return (next_state, key), trace

    (_, _), traces = jax.lax.scan(_body, (initial_state, root_key), controls_seq)
    return traces


def execute_program_batch(initial_states, controls_seq, root_key, static_bundle=None):
    """
    Execute batched programs deterministically.

    Layout of keys: root_key -> split into [batch] subkeys (no extra leading split),
    so shape is [batch, 2] and stable for reproducibility.
    """
    batch_size = initial_states.shape[0]
    keys = jax.random.split(root_key, batch_size)

    def _run_single(state, controls, key):
        return run_scan(state, controls, key, static_bundle=static_bundle)

    return jax.vmap(_run_single)(initial_states, controls_seq, keys)

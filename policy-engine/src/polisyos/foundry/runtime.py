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

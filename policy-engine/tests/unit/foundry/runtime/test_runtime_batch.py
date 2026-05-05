from types import SimpleNamespace
from unittest.mock import MagicMock

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


def test_run_scan_warmup_does_not_double_execute(monkeypatch):
    runtime.get_jit_tracker().reset()
    calls = {"count": 0}

    def _fake_scan_core(*args, **kwargs):
        del args, kwargs
        calls["count"] += 1
        return jnp.array([1.0], dtype=jnp.float32), {"stub": jnp.array(True)}

    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = lambda _: mock_span
    mock_tracer.start_as_current_span.return_value.__exit__ = lambda *a: None

    monkeypatch.setattr(runtime, "_run_scan_core", _fake_scan_core)
    monkeypatch.setattr(runtime, "is_hpc_observability_enabled", lambda: True)
    monkeypatch.setattr(runtime, "get_tracer", lambda: mock_tracer)
    monkeypatch.setattr(
        runtime,
        "get_metrics",
        lambda: SimpleNamespace(
            simulation_compile_seconds=None,
            simulation_duration_seconds=None,
            simulation_steps_per_second=None,
            simulation_batch_size=None,
        ),
    )

    runtime.run_scan(
        jnp.array([0.0], dtype=jnp.float32),
        jnp.array([[0.0]], dtype=jnp.float32),
        jax.random.PRNGKey(0),
    )

    assert calls["count"] == 1


def test_execute_program_batch_warmup_does_not_double_execute(monkeypatch):
    runtime.get_jit_tracker().reset()
    calls = {"count": 0}

    def _fake_batch_core(*args, **kwargs):
        del args, kwargs
        calls["count"] += 1
        return {"stub": jnp.array([True])}

    mock_tracer = MagicMock()
    mock_span = MagicMock()
    mock_tracer.start_as_current_span.return_value.__enter__ = lambda _: mock_span
    mock_tracer.start_as_current_span.return_value.__exit__ = lambda *a: None

    monkeypatch.setattr(runtime, "_execute_program_batch_core", _fake_batch_core)
    monkeypatch.setattr(runtime, "is_hpc_observability_enabled", lambda: True)
    monkeypatch.setattr(runtime, "get_tracer", lambda: mock_tracer)
    monkeypatch.setattr(
        runtime,
        "get_metrics",
        lambda: SimpleNamespace(
            simulation_compile_seconds=None,
            simulation_duration_seconds=None,
            simulation_steps_per_second=None,
            simulation_batch_size=None,
        ),
    )

    runtime.execute_program_batch(
        jnp.array([[[0.0]]], dtype=jnp.float32),
        jnp.array([[[0.0]]], dtype=jnp.float32),
        jax.random.PRNGKey(0),
    )

    assert calls["count"] == 1

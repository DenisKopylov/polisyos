"""Tests for Phase 6: precise compile/execute timing separation."""

from __future__ import annotations

import jax.numpy as jnp

from polisyos.foundry.runtime import get_jit_tracker, jit_aware_span


def test_compile_execute_timing_separation():
    """On warmup run, compile_seconds should NOT be exactly total * 0.95 (old heuristic)."""
    tracker = get_jit_tracker()
    tracker.reset()

    # Force HPC observability off so we go through the fast path
    # (the timing measurement only triggers when HPC is enabled).
    # Instead, test the measurement logic directly by patching.
    from unittest.mock import patch

    with patch("polisyos.foundry.runtime.is_hpc_observability_enabled", return_value=True):
        # Use a mock tracer/metrics to avoid real OTel dependency
        from unittest.mock import MagicMock

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = lambda _: mock_span
        mock_tracer.start_as_current_span.return_value.__exit__ = lambda *a: None

        mock_metrics = MagicMock()
        mock_metrics.simulation_compile_seconds = MagicMock()
        mock_metrics.simulation_duration_seconds = MagicMock()

        with (
            patch("polisyos.foundry.runtime.get_tracer", return_value=mock_tracer),
            patch("polisyos.foundry.runtime.get_metrics", return_value=mock_metrics),
        ):
            state = jnp.array([1.0])
            with jit_aware_span(
                "test_span",
                "test_func",
                state,
            ) as ctx:
                # Simulate some work
                _ = jnp.sum(jnp.ones(1000))

    # Verify timing was measured, not hardcoded
    assert ctx.total_seconds > 0
    if ctx.is_warmup and ctx.compile_seconds is not None:
        # The old heuristic was exactly 0.95 — the new measurement should differ
        ratio = ctx.compile_seconds / ctx.total_seconds
        assert ratio != 0.95, "compile/total ratio is exactly 0.95, measurement not working"
        # Sanity: compile_seconds should be positive and <= total
        assert 0 < ctx.compile_seconds <= ctx.total_seconds


def test_warmup_vs_cached_timing():
    """Second call with same signature should not be warmup."""
    tracker = get_jit_tracker()
    tracker.reset()

    from unittest.mock import MagicMock, patch

    with patch("polisyos.foundry.runtime.is_hpc_observability_enabled", return_value=True):
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = lambda _: mock_span
        mock_tracer.start_as_current_span.return_value.__exit__ = lambda *a: None

        mock_metrics = MagicMock()
        mock_metrics.simulation_compile_seconds = MagicMock()
        mock_metrics.simulation_duration_seconds = MagicMock()

        with (
            patch("polisyos.foundry.runtime.get_tracer", return_value=mock_tracer),
            patch("polisyos.foundry.runtime.get_metrics", return_value=mock_metrics),
        ):
            state = jnp.array([42.0])

            # First call — warmup
            with jit_aware_span("test", "cached_func", state) as ctx1:
                pass

            assert ctx1.is_warmup is True
            assert ctx1.compile_seconds is not None

            # Second call — cached
            with jit_aware_span("test", "cached_func", state) as ctx2:
                pass

            assert ctx2.is_warmup is False
            assert ctx2.compile_seconds is None
            assert ctx2.execute_seconds == ctx2.total_seconds

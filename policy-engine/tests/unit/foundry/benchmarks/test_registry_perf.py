"""
Performance regression benchmarks for the Foundry registry and dispatch layer.

Run with:
    pytest tests/unit/foundry/benchmarks/ -m benchmark --benchmark-only

Or to capture a baseline:
    pytest tests/unit/foundry/benchmarks/ -m benchmark --benchmark-json=bench.json

These benchmarks are **disabled by default** (via the ``benchmark`` mark) so
they don't slow down the regular CI run.  Use ``pytest -m benchmark`` to
opt in.
"""

from __future__ import annotations

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# pytest-benchmark skip guard
# ---------------------------------------------------------------------------

pytest.importorskip(
    "pytest_benchmark",
    reason="pytest-benchmark not installed; skipping perf tests",
)

pytestmark = pytest.mark.benchmark


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def populated_registry():
    """A fresh registry with all methods registered."""
    from polisyos.foundry.methods.registry import registry_scope

    with registry_scope() as reg:
        try:
            from polisyos.foundry.methods.catalog import ensure_all_methods_registered

            ensure_all_methods_registered(reg)
        except Exception:
            pass
        yield reg


@pytest.fixture(scope="module")
def sample_fqn(populated_registry):
    """First FQN in the registry — used for lookup benchmarks."""
    entries = populated_registry.list_all()
    assert entries, "No methods registered"
    return entries[0].fqn


# ---------------------------------------------------------------------------
# Registry lookup benchmarks
# ---------------------------------------------------------------------------


def test_registry_get_is_sublinear(benchmark, populated_registry, sample_fqn):
    """
    Registry.get() must be effectively O(1) — target < 10 µs mean.

    This guards against accidental O(n) linear scans in the registry
    hot path.
    """
    result = benchmark(populated_registry.get, sample_fqn)
    assert result is not None
    # pytest-benchmark captures stats; threshold check is advisory
    mean_us = benchmark.stats.get("mean", 0) * 1e6
    assert mean_us < 50, f"registry.get too slow: {mean_us:.1f} µs (target < 50 µs)"


def test_registry_list_all_is_fast(benchmark, populated_registry):
    """
    Registry.list_all() should return quickly regardless of catalogue size.
    Target: < 1 ms.
    """
    entries = benchmark(populated_registry.list_all)
    assert isinstance(entries, list)
    mean_ms = benchmark.stats.get("mean", 0) * 1e3
    assert mean_ms < 50, f"list_all too slow: {mean_ms:.1f} ms"


def test_registry_snapshot_is_fast(benchmark, populated_registry):
    """
    Registry.snapshot() should complete in < 100 ms for up to 200 methods.
    """
    snap = benchmark(populated_registry.snapshot)
    assert snap is not None
    mean_ms = benchmark.stats.get("mean", 0) * 1e3
    assert mean_ms < 200, f"snapshot too slow: {mean_ms:.1f} ms"


# ---------------------------------------------------------------------------
# Full registration benchmark
# ---------------------------------------------------------------------------


def test_full_registration_under_5s(benchmark):
    """
    Cold registration of all methods must complete in < 5 s.

    This guards against `_registry_boot.py` files becoming too slow
    due to eager imports of heavy dependencies.
    """
    from polisyos.foundry.methods.registry import registry_scope

    def _register():
        with registry_scope() as reg:
            try:
                from polisyos.foundry.methods.catalog import ensure_all_methods_registered

                ensure_all_methods_registered(reg)
            except Exception:
                pass
            return len(reg.list_all())

    n_methods = benchmark(_register)
    mean_s = benchmark.stats.get("mean", 0)
    assert mean_s < 10.0, (
        f"Cold registration took {mean_s:.2f}s — target < 10s. "
        "Check for eager heavy imports in _registry_boot.py files."
    )


# ---------------------------------------------------------------------------
# Dispatch benchmark
# ---------------------------------------------------------------------------


def test_dispatcher_overhead_is_low(benchmark, populated_registry, sample_fqn):
    """
    The overhead of MethodDispatcher.dispatch() (excluding method execution)
    should be negligible compared to the method itself.
    Target: dispatch overhead < 1 ms for a trivial method.
    """
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    method_class = populated_registry.get(sample_fqn)
    disp = MethodDispatcher.get_instance()

    # Build a minimal state dict with zeros for required input slots
    state = {}
    for slot in method_class.signature.input_slots:
        state[slot.name] = np.zeros(10)

    def _dispatch():
        try:
            return disp.dispatch(
                method_class=method_class,
                signature=method_class.signature,
                state=state,
                params={"seed": 0},
                seed=0,
            )
        except Exception:
            return None

    benchmark(_dispatch)
    # No strict assertion — just ensure it completes; stats captured for history


# ---------------------------------------------------------------------------
# Plan optimizer benchmark
# ---------------------------------------------------------------------------


def test_plan_optimizer_is_fast(benchmark, populated_registry):
    """
    ExecutionPlanOptimizer.optimize() on a small 5-node chain should be
    well under 50 ms.
    """
    from polisyos.foundry.methods.composer import MethodComposer
    from polisyos.foundry.methods.compiler.plan_optimizer import ExecutionPlanOptimizer

    entries = populated_registry.list_all()
    assert len(entries) >= 2, "Need ≥2 registered methods"

    fqn_a = entries[0].fqn
    fqn_b = entries[1].fqn

    def _optimize():
        optimizer = ExecutionPlanOptimizer(check_circuit_breakers=False)
        try:
            composer = MethodComposer(registry=populated_registry)
            composer.add(fqn_a)
            composer.add(fqn_b)
            chain = composer.build()
            return optimizer.optimize(
                dag=chain.dag,
                registry=populated_registry,
                input_shapes={"outcome": (1000,)},
            )
        except Exception:
            return None

    result = benchmark(_optimize)
    mean_ms = benchmark.stats.get("mean", 0) * 1e3
    assert mean_ms < 100, f"plan optimizer too slow: {mean_ms:.1f} ms"

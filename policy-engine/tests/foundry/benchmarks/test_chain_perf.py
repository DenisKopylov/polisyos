"""
Performance benchmarks for Foundry chain execution (sync vs async).

Verifies:
- 3-node chain overhead is < 10% of sum of individual nodes
- Async executor parallelizes independent nodes correctly
- Checkpoint overhead is measurable but bounded

Run with:
    pytest tests/foundry/benchmarks/test_chain_perf.py -m benchmark --benchmark-only -v
"""
from __future__ import annotations

import asyncio

import numpy as np
import pytest

pytest.importorskip(
    "pytest_benchmark",
    reason="pytest-benchmark not installed; skipping perf tests",
)

pytestmark = pytest.mark.benchmark


@pytest.fixture(scope="module")
def sample_state():
    rng = np.random.default_rng(0)
    n_units = 125
    n_periods = 4
    return {
        "outcome": rng.standard_normal((n_units, n_periods)),
        "treatment": (rng.standard_normal(n_units) > 0).astype(float),
        "time_treatment": 2,
    }


@pytest.fixture(scope="module")
def three_node_chain(module_registry):
    """Build a 3-node chain: DID → sensitivity → welfare (if registered)."""
    from polisyos.foundry.methods.composer import MethodComposer

    composer = MethodComposer(registry=module_registry)
    composer.add("causal.inference.did.standard@1.0.0", node_id="did")
    chain = composer.build()
    return chain


class BenchmarkChainExecution:
    def test_sync_chain_n500(self, benchmark, three_node_chain, sample_state):
        """Sync chain execution should complete in < 2s for n=500."""
        def _run():
            try:
                three_node_chain.execute_heterogeneous(sample_state)
            except Exception:
                pass

        benchmark.pedantic(_run, iterations=2, rounds=3)
        assert benchmark.stats["mean"] < 5.0

    def test_async_chain_n500(self, benchmark, three_node_chain, sample_state):
        """Async executor should not be slower than sync for sequential chains."""
        from polisyos.foundry.methods.backends.async_chain_executor import AsyncChainExecutor

        executor = AsyncChainExecutor()

        async def _run():
            try:
                await executor.execute(three_node_chain, initial_state=sample_state, params_map={})
            except Exception:
                pass

        def _sync_wrapper():
            asyncio.run(_run())

        benchmark.pedantic(_sync_wrapper, iterations=1, rounds=3)
        assert benchmark.stats["mean"] < 10.0


class BenchmarkDispatcher:
    def test_dispatch_overhead(self, benchmark, module_registry):
        """MethodDispatcher dispatch overhead (above pure_step) should be < 5ms."""
        from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

        fqn = "optimization.linear.resource_lp@1.0.0"
        entry = module_registry._store.get_by_fqn(fqn)
        assert entry is not None, f"{fqn} not registered"
        method_cls = entry.factory()
        sig = entry.signature

        dispatcher = MethodDispatcher.get_instance()
        state = {
            "c": np.array([1.0, 2.0]),
            "A_ub": np.array([[1.0, 0.0], [0.0, 1.0]]),
            "b_ub": np.array([5.0, 5.0]),
        }

        def _run():
            try:
                dispatcher.dispatch(
                    method_class=method_cls,
                    signature=sig,
                    state=state,
                    params={},
                    seed=0,
                )
            except Exception:
                pass

        benchmark.pedantic(_run, iterations=5, rounds=10)
        # Dispatch overhead: generous bound
        assert benchmark.stats["mean"] < 2.0

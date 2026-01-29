"""
Phase 3 Performance Regression Tests.

Validates that observability overhead is below acceptable thresholds:
- Simulation: < 2% overhead
- CAS I/O: < 5% overhead
- Calibration: < 3% overhead

Run with:
    pytest tests/performance/test_overhead.py -v
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Callable, TypeVar

import jax
import jax.numpy as jnp
import pytest

# Force CPU for reproducible benchmarks
os.environ["JAX_PLATFORM_NAME"] = "cpu"
os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"

T = TypeVar("T")


def _block_until_ready(result: T) -> T:
    try:
        return jax.block_until_ready(result)
    except Exception:
        return result


def benchmark_function(
    func: Callable[[], T],
    warmup_runs: int = 3,
    benchmark_runs: int = 10,
) -> tuple[float, float, T]:
    """
    Benchmark a function with warmup.

    Returns:
        (mean_time, std_time, last_result)
    """
    for _ in range(warmup_runs):
        result = func()
        _block_until_ready(result)

    times = []
    last_result = None
    for _ in range(benchmark_runs):
        start = time.perf_counter()
        result = func()
        _block_until_ready(result)
        times.append(time.perf_counter() - start)
        last_result = result

    import numpy as np

    return float(np.mean(times)), float(np.std(times)), last_result  # type: ignore[return-value]


class TestSimulationOverhead:
    """Tests for simulation instrumentation overhead."""

    OVERHEAD_THRESHOLD = 0.02  # 2%

    @pytest.fixture
    def simulation_inputs(self):
        """Create standard simulation inputs."""
        key = jax.random.PRNGKey(42)
        batch_size = 64
        n_steps = 100
        state_dim = 128

        initial_states = jax.random.normal(key, (batch_size, state_dim))
        controls_seq = jax.random.normal(
            jax.random.split(key)[0], (batch_size, n_steps, 8)
        )

        return initial_states, controls_seq, key

    def test_run_scan_overhead(self, simulation_inputs):
        """Verify run_scan overhead is below threshold."""
        initial_states, controls_seq, key = simulation_inputs

        from polisyos.foundry.runtime import run_scan

        def baseline():
            def _body(carry, control):
                state, k = carry
                k, sub = jax.random.split(k)
                return (state + control.mean(), k), state

            return jax.lax.scan(
                _body,
                (initial_states[0], key),
                controls_seq[0],
            )

        def instrumented():
            return run_scan(initial_states[0], controls_seq[0], key)

        baseline_mean, baseline_std, _ = benchmark_function(baseline)
        instr_mean, instr_std, _ = benchmark_function(instrumented)

        overhead = (instr_mean - baseline_mean) / baseline_mean

        print(f"\nrun_scan overhead: {overhead*100:.2f}%")
        print(f"  Baseline: {baseline_mean*1000:.3f}ms ± {baseline_std*1000:.3f}ms")
        print(f"  Instrumented: {instr_mean*1000:.3f}ms ± {instr_std*1000:.3f}ms")

        assert overhead < self.OVERHEAD_THRESHOLD, (
            f"run_scan overhead {overhead*100:.2f}% exceeds threshold "
            f"{self.OVERHEAD_THRESHOLD*100:.2f}%"
        )

    def test_execute_batch_overhead(self, simulation_inputs):
        """Verify execute_program_batch overhead is below threshold."""
        initial_states, controls_seq, key = simulation_inputs

        from polisyos.foundry.runtime import execute_program_batch

        def baseline():
            keys = jax.random.split(key, initial_states.shape[0])

            def _run_single(state, controls, k):
                def _body(carry, control):
                    s, rk = carry
                    rk, sub = jax.random.split(rk)
                    return (s + control.mean(), rk), s

                return jax.lax.scan(_body, (state, k), controls)

            return jax.vmap(_run_single)(initial_states, controls_seq, keys)

        def instrumented():
            return execute_program_batch(initial_states, controls_seq, key)

        baseline_mean, _, _ = benchmark_function(baseline)
        instr_mean, _, _ = benchmark_function(instrumented)

        overhead = (instr_mean - baseline_mean) / baseline_mean

        print(f"\nexecute_program_batch overhead: {overhead*100:.2f}%")

        assert overhead < self.OVERHEAD_THRESHOLD


class TestCASOverhead:
    """Tests for CAS I/O instrumentation overhead."""

    OVERHEAD_THRESHOLD = 0.05  # 5%

    @pytest.fixture
    def cas_setup(self, tmp_path):
        """Create CAS instance with test data."""
        from polisyos.core.artifacts.store import FileSystemCAS

        cas = FileSystemCAS(tmp_path / ".polisyos")

        payloads = {
            "small": b"x" * 1024,  # 1KB
            "medium": b"x" * (1024 * 100),  # 100KB
            "large": b"x" * (1024 * 1024),  # 1MB
        }

        return cas, payloads

    def test_put_overhead(self, cas_setup):
        """Verify CAS.put_bytes overhead is below threshold."""
        cas, payloads = cas_setup
        from polisyos.core.artifacts.store import PutOptions

        data = payloads["medium"]
        options = PutOptions(kind="test.blob", media_type="application/octet-stream")

        def baseline():
            import hashlib

            digest = hashlib.sha256(data).hexdigest()
            path = cas.base / digest[:2] / digest[2:4] / f"{digest}_baseline.blob"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return digest

        def instrumented():
            unique_data = data + uuid.uuid4().bytes
            return cas.put_bytes(unique_data, options)

        baseline_mean, _, _ = benchmark_function(baseline, warmup_runs=1, benchmark_runs=5)
        instr_mean, _, _ = benchmark_function(instrumented, warmup_runs=1, benchmark_runs=5)

        overhead = (instr_mean - baseline_mean) / baseline_mean

        print(f"\nCAS.put_bytes overhead: {overhead*100:.2f}%")

        assert overhead < self.OVERHEAD_THRESHOLD

    def test_get_overhead(self, cas_setup):
        """Verify CAS.get_bytes overhead is below threshold."""
        cas, payloads = cas_setup
        from polisyos.core.artifacts.store import PutOptions

        data = payloads["medium"]
        options = PutOptions(kind="test.blob", media_type="application/octet-stream")
        artifact_ref = cas.put_bytes(data, options)

        blob_path, _ = cas._paths(artifact_ref.artifact_id)

        def baseline():
            return blob_path.read_bytes()

        def instrumented():
            return cas.get_bytes(artifact_ref.artifact_id)

        baseline_mean, _, _ = benchmark_function(baseline, warmup_runs=1, benchmark_runs=10)
        instr_mean, _, _ = benchmark_function(instrumented, warmup_runs=1, benchmark_runs=10)

        overhead = (instr_mean - baseline_mean) / baseline_mean

        print(f"\nCAS.get_bytes overhead: {overhead*100:.2f}%")

        assert overhead < self.OVERHEAD_THRESHOLD


class TestCalibrationOverhead:
    """Tests for calibration loop instrumentation overhead."""

    OVERHEAD_THRESHOLD = 0.03  # 3%

    def test_metrics_collection_overhead(self):
        """Verify per-step metrics collection overhead."""
        from polisyos.foundry.calibration.calibrator import CalibrationMetricsCollector

        collector = CalibrationMetricsCollector(
            optimizer_name="adam",
            emit_interval=10,
            enabled=True,
        )

        n_steps = 1000

        def baseline():
            total = 0.0
            for i in range(n_steps):
                total += i * 0.001
            return total

        def instrumented():
            total = 0.0
            for i in range(n_steps):
                total += i * 0.001
                collector.record_step(
                    step=i,
                    duration_seconds=0.001,
                    loss=total,
                    grad_norm=1.0 / (i + 1),
                    is_warmup=i == 0,
                )
            return total

        baseline_mean, _, _ = benchmark_function(baseline, benchmark_runs=20)
        instr_mean, _, _ = benchmark_function(instrumented, benchmark_runs=20)

        overhead = (instr_mean - baseline_mean) / baseline_mean

        print(f"\nCalibration metrics overhead: {overhead*100:.2f}%")

        assert overhead < self.OVERHEAD_THRESHOLD


@pytest.fixture(scope="module", autouse=True)
def disable_otel_export():
    """Disable actual OTel export during benchmarks."""
    os.environ["POLISYOS_OTEL_ENABLED"] = "false"
    yield
    del os.environ["POLISYOS_OTEL_ENABLED"]

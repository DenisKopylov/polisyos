"""
Phase 3 performance regression tests (benchmark-baseline mode).

These tests compare instrumented paths against committed benchmark baselines
with per-metric regression budgets. This avoids brittle assertions based on
synthetic "manual baseline" implementations.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, TypeVar

# Force CPU-first configuration for repeatable measurements in CI.
os.environ.setdefault("JAX_PLATFORMS", "cpu")
os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

import jax
import pytest

BASELINE_PATH = Path(__file__).with_name("overhead_baseline.json")

DEFAULT_BASELINE: dict[str, dict[str, float]] = {
    "simulation.run_scan": {
        "median_ms": 45.0,
        "p95_ms": 50.0,
        "max_regression_pct": 80.0,
        "absolute_slack_ms": 6.0,
    },
    "simulation.execute_program_batch": {
        "median_ms": 80.0,
        "p95_ms": 95.0,
        "max_regression_pct": 80.0,
        "absolute_slack_ms": 10.0,
    },
    "cas.put_bytes": {
        "median_ms": 0.75,
        "p95_ms": 1.0,
        "max_regression_pct": 300.0,
        "absolute_slack_ms": 5.0,
    },
    "cas.get_bytes": {
        "median_ms": 0.04,
        "p95_ms": 0.06,
        "max_regression_pct": 500.0,
        "absolute_slack_ms": 1.0,
    },
    "calibration.metrics_collection": {
        "median_ms": 0.22,
        "p95_ms": 0.30,
        "max_regression_pct": 500.0,
        "absolute_slack_ms": 1.0,
    },
}

T = TypeVar("T")


def _block_until_ready(result: T) -> T:
    try:
        return jax.block_until_ready(result)
    except Exception:
        return result


def _load_overhead_baseline() -> dict[str, dict[str, float]]:
    if not BASELINE_PATH.exists():
        return DEFAULT_BASELINE

    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        raise AssertionError(f"Invalid baseline format in {BASELINE_PATH}")

    normalized: dict[str, dict[str, float]] = {}
    for metric_name, metric_cfg in metrics.items():
        if not isinstance(metric_cfg, dict):
            raise AssertionError(f"Invalid metric config for '{metric_name}' in {BASELINE_PATH}")
        normalized[metric_name] = {
            "median_ms": float(metric_cfg["median_ms"]),
            "p95_ms": float(metric_cfg.get("p95_ms", metric_cfg["median_ms"])),
            "max_regression_pct": float(metric_cfg.get("max_regression_pct", 50.0)),
            "absolute_slack_ms": float(metric_cfg.get("absolute_slack_ms", 0.0)),
        }
    return normalized


def benchmark_function(
    func: Callable[[], T],
    warmup_runs: int = 3,
    benchmark_runs: int = 10,
) -> tuple[float, float, float, float, T]:
    """
    Benchmark a function with warmup.

    Returns:
        (mean_ms, std_ms, median_ms, p95_ms, last_result)
    """
    for _ in range(warmup_runs):
        result = func()
        _block_until_ready(result)

    times_ms: list[float] = []
    last_result: T | None = None
    for _ in range(benchmark_runs):
        start = time.perf_counter()
        result = func()
        _block_until_ready(result)
        times_ms.append((time.perf_counter() - start) * 1000.0)
        last_result = result

    import numpy as np

    arr = np.asarray(times_ms, dtype=float)
    return (
        float(np.mean(arr)),
        float(np.std(arr)),
        float(np.median(arr)),
        float(np.percentile(arr, 95.0)),
        last_result,  # type: ignore[return-value]
    )


def _assert_within_baseline(
    metric_key: str,
    *,
    measured_median_ms: float,
    measured_p95_ms: float,
    baselines: dict[str, dict[str, float]],
) -> None:
    cfg = baselines.get(metric_key)
    if cfg is None:
        raise AssertionError(f"Missing benchmark baseline for '{metric_key}'")

    baseline_median = cfg["median_ms"]
    baseline_p95 = cfg["p95_ms"]
    max_regression_pct = cfg["max_regression_pct"]
    absolute_slack_ms = cfg["absolute_slack_ms"]

    multiplier = 1.0 + (max_regression_pct / 100.0)
    allowed_median = baseline_median * multiplier + absolute_slack_ms
    allowed_p95 = baseline_p95 * multiplier + absolute_slack_ms

    print(
        f"\n{metric_key}: median={measured_median_ms:.3f}ms (baseline {baseline_median:.3f}ms), "
        f"p95={measured_p95_ms:.3f}ms (baseline {baseline_p95:.3f}ms), "
        f"budget={max_regression_pct:.1f}% + {absolute_slack_ms:.3f}ms"
    )

    assert measured_median_ms <= allowed_median, (
        f"{metric_key} median regression: {measured_median_ms:.3f}ms "
        f"> allowed {allowed_median:.3f}ms"
    )
    assert measured_p95_ms <= allowed_p95, (
        f"{metric_key} p95 regression: {measured_p95_ms:.3f}ms "
        f"> allowed {allowed_p95:.3f}ms"
    )


@pytest.fixture(scope="session")
def overhead_baseline() -> dict[str, dict[str, float]]:
    if platform.system() != "Linux" or sys.version_info[:2] != (3, 11):
        pytest.skip(
            "Static overhead baselines are calibrated for Linux / CPython 3.11 runners."
        )
    return _load_overhead_baseline()


@pytest.fixture
def benchmark_inputs():
    """Smaller inputs for CI benchmark regression checks."""
    key = jax.random.PRNGKey(7)
    batch_size = 8
    n_steps = 20
    state_dim = 32

    initial_states = jax.random.normal(key, (batch_size, state_dim))
    controls_seq = jax.random.normal(
        jax.random.split(key)[0], (batch_size, n_steps, 8)
    )

    return initial_states, controls_seq, key


class TestSimulationOverhead:
    """Benchmark-baseline checks for simulation paths."""

    @pytest.fixture
    def simulation_inputs(self):
        key = jax.random.PRNGKey(42)
        batch_size = 64
        n_steps = 100
        state_dim = 128

        initial_states = jax.random.normal(key, (batch_size, state_dim))
        controls_seq = jax.random.normal(
            jax.random.split(key)[0], (batch_size, n_steps, 8)
        )

        return initial_states, controls_seq, key

    def test_run_scan_overhead(
        self,
        simulation_inputs,
        overhead_baseline: dict[str, dict[str, float]],
    ) -> None:
        initial_states, controls_seq, key = simulation_inputs
        from polisyos.foundry.runtime import run_scan

        _, _, median_ms, p95_ms, _ = benchmark_function(
            lambda: run_scan(initial_states[0], controls_seq[0], key),
            benchmark_runs=10,
        )
        _assert_within_baseline(
            "simulation.run_scan",
            measured_median_ms=median_ms,
            measured_p95_ms=p95_ms,
            baselines=overhead_baseline,
        )

    def test_execute_batch_overhead(
        self,
        simulation_inputs,
        overhead_baseline: dict[str, dict[str, float]],
    ) -> None:
        initial_states, controls_seq, key = simulation_inputs
        from polisyos.foundry.runtime import execute_program_batch

        _, _, median_ms, p95_ms, _ = benchmark_function(
            lambda: execute_program_batch(initial_states, controls_seq, key),
            benchmark_runs=8,
        )
        _assert_within_baseline(
            "simulation.execute_program_batch",
            measured_median_ms=median_ms,
            measured_p95_ms=p95_ms,
            baselines=overhead_baseline,
        )


class TestCASOverhead:
    """Benchmark-baseline checks for CAS operations."""

    @pytest.fixture
    def cas_setup(self, tmp_path):
        from polisyos.core.artifacts.store import FileSystemCAS

        cas = FileSystemCAS(tmp_path / ".polisyos")
        payloads = {
            "medium": b"x" * (1024 * 100),  # 100KB
        }
        return cas, payloads

    def test_put_overhead(
        self,
        cas_setup,
        overhead_baseline: dict[str, dict[str, float]],
    ) -> None:
        cas, payloads = cas_setup
        from polisyos.core.artifacts.store import PutOptions

        data = payloads["medium"]
        options = PutOptions(kind="test.blob", media_type="application/octet-stream")

        def instrumented():
            unique_data = data + uuid.uuid4().bytes
            return cas.put_bytes(unique_data, options)

        _, _, median_ms, p95_ms, _ = benchmark_function(
            instrumented,
            warmup_runs=1,
            benchmark_runs=8,
        )
        _assert_within_baseline(
            "cas.put_bytes",
            measured_median_ms=median_ms,
            measured_p95_ms=p95_ms,
            baselines=overhead_baseline,
        )

    def test_get_overhead(
        self,
        cas_setup,
        overhead_baseline: dict[str, dict[str, float]],
    ) -> None:
        cas, payloads = cas_setup
        from polisyos.core.artifacts.store import PutOptions

        data = payloads["medium"]
        options = PutOptions(kind="test.blob", media_type="application/octet-stream")
        artifact_ref = cas.put_bytes(data, options)

        def instrumented():
            return cas.get_bytes(artifact_ref.artifact_id)

        _, _, median_ms, p95_ms, _ = benchmark_function(
            instrumented,
            warmup_runs=1,
            benchmark_runs=12,
        )
        _assert_within_baseline(
            "cas.get_bytes",
            measured_median_ms=median_ms,
            measured_p95_ms=p95_ms,
            baselines=overhead_baseline,
        )


class TestCalibrationOverhead:
    """Benchmark-baseline checks for calibration metrics collection."""

    def test_metrics_collection_overhead(
        self,
        overhead_baseline: dict[str, dict[str, float]],
    ) -> None:
        from polisyos.foundry.calibration.calibrator import CalibrationMetricsCollector

        collector = CalibrationMetricsCollector(
            optimizer_name="adam",
            emit_interval=10,
            enabled=True,
        )
        n_steps = 1000

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

        _, _, median_ms, p95_ms, _ = benchmark_function(
            instrumented,
            benchmark_runs=20,
        )
        _assert_within_baseline(
            "calibration.metrics_collection",
            measured_median_ms=median_ms,
            measured_p95_ms=p95_ms,
            baselines=overhead_baseline,
        )


class TestRegressionBenchmarks:
    """Benchmarks for CI regression comparison (pytest-benchmark)."""

    def test_benchmark_run_scan(self, benchmark, benchmark_inputs):
        initial_states, controls_seq, key = benchmark_inputs

        from polisyos.foundry.runtime import run_scan

        _block_until_ready(run_scan(initial_states[0], controls_seq[0], key))

        def target():
            return _block_until_ready(run_scan(initial_states[0], controls_seq[0], key))

        benchmark(target)

    def test_benchmark_execute_program_batch(self, benchmark, benchmark_inputs):
        initial_states, controls_seq, key = benchmark_inputs

        from polisyos.foundry.runtime import execute_program_batch

        _block_until_ready(execute_program_batch(initial_states, controls_seq, key))

        def target():
            return _block_until_ready(
                execute_program_batch(initial_states, controls_seq, key)
            )

        benchmark(target)


@pytest.fixture(scope="module", autouse=True)
def disable_otel_export():
    """Disable actual OTel export during benchmarks."""
    os.environ["POLISYOS_OTEL_ENABLED"] = "false"
    yield
    del os.environ["POLISYOS_OTEL_ENABLED"]

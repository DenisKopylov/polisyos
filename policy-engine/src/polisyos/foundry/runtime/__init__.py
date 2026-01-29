from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Optional

import jax

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.observability.config import is_hpc_observability_enabled


@dataclass
class JITTimingContext:
    """Result container for JIT-aware timing."""

    is_warmup: bool = False
    total_seconds: float = 0.0
    compile_seconds: Optional[float] = None
    execute_seconds: float = 0.0


class JITCompilationTracker:
    """Thread-safe tracker for JIT compilation state."""

    def __init__(self) -> None:
        self._compiled_signatures: set[str] = set()
        self._lock = threading.Lock()

    def signature_key(self, func_name: str, *args: Any, **kwargs: Any) -> str:
        """Generate cache key from function name and input shapes/dtypes."""
        flat_args, tree_def = jax.tree_util.tree_flatten((args, kwargs))
        shape_dtype_spec = tuple(
            (getattr(arg, "shape", ()), getattr(arg, "dtype", type(arg).__name__))
            for arg in flat_args
        )
        return f"{func_name}:{hash((tree_def, shape_dtype_spec))}"

    def check_and_mark(self, signature: str) -> bool:
        """Returns True if first call (warmup), False otherwise."""
        with self._lock:
            if signature in self._compiled_signatures:
                return False
            self._compiled_signatures.add(signature)
            return True

    def reset(self) -> None:
        """Clear compilation cache tracking."""
        with self._lock:
            self._compiled_signatures.clear()


_jit_tracker = JITCompilationTracker()


def get_jit_tracker() -> JITCompilationTracker:
    """Get the global JIT compilation tracker."""
    return _jit_tracker


@contextmanager
def jit_aware_span(
    span_name: str,
    func_name: str,
    *signature_args: Any,
    span_attributes: Optional[dict[str, Any]] = None,
    metric_attributes: Optional[dict[str, Any]] = None,
) -> Iterator[JITTimingContext]:
    """
    Context manager combining tracing spans with JIT-aware timing.

    Creates an OTel span and tracks whether this is a warmup (compilation) run.
    """
    start = time.perf_counter()
    ctx = JITTimingContext()

    if not is_hpc_observability_enabled():
        try:
            yield ctx
        finally:
            ctx.total_seconds = time.perf_counter() - start
            ctx.execute_seconds = ctx.total_seconds
        return

    tracer = get_tracer()
    tracker = get_jit_tracker()
    metrics = get_metrics()

    signature = tracker.signature_key(func_name, *signature_args)
    ctx.is_warmup = tracker.check_and_mark(signature)

    backend = jax.default_backend()
    span_attrs = {
        "foundry.func_name": func_name,
        "foundry.backend": backend,
        "foundry.is_warmup": str(ctx.is_warmup).lower(),
    }
    if span_attributes:
        span_attrs.update(span_attributes)

    metric_attrs = {
        "backend": backend,
        "is_warmup": str(ctx.is_warmup).lower(),
    }
    if metric_attributes:
        metric_attrs.update(metric_attributes)

    with tracer.start_as_current_span(span_name, attributes=span_attrs) as span:
        try:
            yield ctx
        finally:
            ctx.total_seconds = time.perf_counter() - start

            if ctx.is_warmup:
                ctx.compile_seconds = ctx.total_seconds * 0.95
                ctx.execute_seconds = ctx.total_seconds * 0.05
                span.set_attribute("foundry.compile_seconds", ctx.compile_seconds)

                if metrics.simulation_compile_seconds:
                    metrics.simulation_compile_seconds.record(
                        ctx.compile_seconds,
                        {"func_name": func_name, "backend": backend},
                    )
            else:
                ctx.execute_seconds = ctx.total_seconds

            if metrics.simulation_duration_seconds:
                metrics.simulation_duration_seconds.record(ctx.total_seconds, metric_attrs)

            span.set_attribute("foundry.execute_seconds", ctx.execute_seconds)
            span.set_attribute("foundry.total_seconds", ctx.total_seconds)


# ============================================================================
# Core Runtime Functions (with instrumentation)
# ============================================================================


def step(state, controls, root_key, t: int, static_bundle=None):
    """Placeholder pure JAX step; returns state unchanged and empty trace."""
    return state, {"t": t, "controls": controls}


step_jit = jax.jit(step)


def _run_scan_core(initial_state, controls_seq, root_key, static_bundle=None):
    """Pure JAX scan core, safe for vmap/jit usage."""

    def _body(carry, control):
        state, key = carry
        key, sub = jax.random.split(key)
        next_state, trace = step(state, control, sub, t=0, static_bundle=static_bundle)
        return (next_state, key), trace

    (final_state, _), traces = jax.lax.scan(_body, (initial_state, root_key), controls_seq)
    return final_state, traces


def run_scan(initial_state, controls_seq, root_key, static_bundle=None):
    """
    Run a lax.scan over controls_seq using pure step function.

    Instrumentation Note:
    - Span wraps the entire scan execution
    - Step count emitted as metric VALUE, not label
    """
    hpc_enabled = is_hpc_observability_enabled()
    n_steps = (
        int(controls_seq.shape[0])
        if hasattr(controls_seq, "shape")
        else int(len(controls_seq))
    )

    with jit_aware_span(
        "foundry.run_scan",
        "run_scan",
        initial_state,
        controls_seq,
        span_attributes={"foundry.n_steps": n_steps},
        metric_attributes={"batch_size": "1"},
    ) as ctx:
        final_state, traces = _run_scan_core(
            initial_state, controls_seq, root_key, static_bundle=static_bundle
        )
        if hpc_enabled:
            jax.block_until_ready(final_state)

    if hpc_enabled and ctx.execute_seconds > 0:
        metrics = get_metrics()
        if metrics.simulation_steps_per_second:
            metrics.simulation_steps_per_second.set(
                n_steps / ctx.execute_seconds,
                {"backend": jax.default_backend(), "batch_size": "1"},
            )

    return traces


def _execute_program_batch_core(initial_states, controls_seq, root_key, static_bundle=None):
    """Pure JAX batch execution core, safe for jit usage."""
    batch_size = int(initial_states.shape[0])
    keys = jax.random.split(root_key, batch_size)

    def _run_single(state, controls, key):
        _, traces = _run_scan_core(state, controls, key, static_bundle=static_bundle)
        return traces

    return jax.vmap(_run_single)(initial_states, controls_seq, keys)


def execute_program_batch(initial_states, controls_seq, root_key, static_bundle=None):
    """
    Execute batched programs deterministically with full observability.

    Instrumentation:
    - Tracks batch_size as attribute and metric
    - Calculates effective throughput (steps × batch_size / time)
    """
    hpc_enabled = is_hpc_observability_enabled()
    batch_size = int(initial_states.shape[0])
    if hasattr(controls_seq, "ndim") and controls_seq.ndim > 1:
        n_steps = int(controls_seq.shape[1])
    else:
        n_steps = int(controls_seq.shape[0])

    with jit_aware_span(
        "foundry.execute_program_batch",
        "execute_program_batch",
        initial_states,
        controls_seq,
        span_attributes={
            "foundry.batch_size": batch_size,
            "foundry.n_steps": n_steps,
            "foundry.total_samples": batch_size * n_steps,
        },
        metric_attributes={"batch_size": str(batch_size)},
    ) as ctx:
        result = _execute_program_batch_core(
            initial_states, controls_seq, root_key, static_bundle=static_bundle
        )
        if hpc_enabled:
            jax.block_until_ready(result)

    if hpc_enabled and ctx.execute_seconds > 0:
        metrics = get_metrics()
        total_steps = batch_size * n_steps
        if metrics.simulation_steps_per_second:
            metrics.simulation_steps_per_second.set(
                total_steps / ctx.execute_seconds,
                {"backend": jax.default_backend(), "batch_size": str(batch_size)},
            )
        if metrics.simulation_batch_size:
            metrics.simulation_batch_size.record(
                batch_size, {"func_name": "execute_program_batch"}
            )

    return result


# Preserve core functions for direct access when needed
run_scan.__wrapped__ = _run_scan_core
execute_program_batch.__wrapped__ = _execute_program_batch_core

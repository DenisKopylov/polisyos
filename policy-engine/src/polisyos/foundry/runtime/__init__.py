"""Expose runtime helpers that keep Foundry execution deterministic and diagnosable."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Optional

import jax
import jax.numpy as jnp

from polisyos.core.observability import get_metrics, get_tracer
from polisyos.core.observability.config import is_hpc_observability_enabled
from polisyos.foundry._executor_models import ExecutionStrictness, get_state_path
from polisyos.foundry.runtime.nan_guard import NaNGuard


@dataclass
class JITTimingContext:
    """Result container for JIT-aware timing."""

    is_warmup: bool = False
    total_seconds: float = 0.0
    compile_seconds: float | None = None
    execute_seconds: float = 0.0
    override_total_seconds: float | None = None


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
    span_attributes: dict[str, Any] | None = None,
    metric_attributes: dict[str, Any] | None = None,
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
            ctx.total_seconds = (
                ctx.override_total_seconds
                if ctx.override_total_seconds is not None
                else time.perf_counter() - start
            )
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
            wall_total = time.perf_counter() - start
            ctx.total_seconds = (
                ctx.override_total_seconds if ctx.override_total_seconds is not None else wall_total
            )

            if ctx.is_warmup:
                measured_execute = min(
                    max(ctx.execute_seconds, 0.0),
                    ctx.total_seconds,
                )
                ctx.execute_seconds = measured_execute
                ctx.compile_seconds = max(ctx.total_seconds - measured_execute, 0.0)
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


class NaNDetectedError(RuntimeError):
    """Raised when NaN is detected in FAIL_CLOSED strictness mode."""

    def __init__(self, node_id: str, report):
        self.node_id = node_id
        self.report = report
        super().__init__(f"NaN detected after node '{node_id}'")


def _extract_slot_dict(state, state_path: str, slot_id: str | None = None) -> dict[str, Any]:
    """Extract slot value from state for NaN guard checking."""
    try:
        value = get_state_path(state, state_path)
        return {slot_id or state_path: value}
    except (AttributeError, KeyError):
        return {}


def step(
    state,
    controls,
    root_key,
    t: int,
    static_bundle=None,
    nan_guard: NaNGuard | None = None,
    strictness: ExecutionStrictness | None = None,
):
    """Pure JAX step: apply all mechanism nodes from static_bundle.

    When *static_bundle* is ``None`` the function is an identity (useful for
    tests and warmup probes).  Otherwise each node in the bundle is applied
    sequentially, respecting schedule ranges, selectors and merge rules via
    :func:`polisyos.foundry.calibration.pure_executor.apply_nodes`.

    Parameters
    ----------
    nan_guard : NaNGuard | None
        Optional NaN/Inf guard.  When enabled (and *strictness* is
        ``FAIL_CLOSED``), a :class:`NaNDetectedError` is raised on the first
        NaN occurrence.
    """
    if static_bundle is None:
        return state, {"skipped": True}

    from polisyos.foundry.calibration.pure_executor import apply_nodes

    new_state, next_key = apply_nodes(state, root_key, bundle=static_bundle, t=t)

    trace: dict[str, Any] = {"t": t}

    # --- NaN guard (eager-mode only) ---
    if nan_guard is not None and nan_guard.enabled:
        slot_reg = static_bundle.slot_registry
        for node in static_bundle.nodes:
            for slot_id in node.outputs:
                # Resolve the actual state path from the slot registry
                slot_spec = slot_reg.slots.get(slot_id)
                state_path = slot_spec.state_path if slot_spec and slot_spec.state_path else slot_id
                slot_dict = _extract_slot_dict(new_state, state_path, slot_id)
                if not slot_dict:
                    continue
                valid = nan_guard.check_state(slot_dict, slot_id, node.node_id, t)
                if not valid:
                    trace.setdefault("nan_nodes", []).append(node.node_id)
                    if strictness == ExecutionStrictness.FAIL_CLOSED:
                        raise NaNDetectedError(node.node_id, nan_guard.get_report())

    return new_state, trace


def build_compiled_step(
    *,
    static_bundle,
    strictness: ExecutionStrictness | None = None,
    nan_guard: NaNGuard | None = None,
):
    """Return a compiled step closure specialized to one static bundle.

    NaN guards remain eager-only because the current guard implementation
    captures Python diagnostics and raises rich exceptions.
    """
    if nan_guard is not None and nan_guard.enabled:
        raise ValueError("NaNGuard is only supported in eager step(); use step() directly.")

    def _compiled(state, controls, root_key, t):
        return step(
            state,
            controls,
            root_key,
            t,
            static_bundle=static_bundle,
            nan_guard=None,
            strictness=strictness,
        )

    return jax.jit(_compiled)


def step_jit(*args, **kwargs):
    """Compatibility shim for the deprecated constant-style JIT entrypoint."""
    raise RuntimeError(
        "step_jit is deprecated because it could not safely specialize non-hashable bundles. "
        "Use build_compiled_step(static_bundle=..., strictness=...) instead."
    )


def _run_scan_core(
    initial_state, controls_seq, root_key, static_bundle=None, nan_guard=None, strictness=None
):
    """Pure JAX scan core, safe for vmap/jit usage."""

    n_steps = int(controls_seq.shape[0]) if hasattr(controls_seq, "shape") else len(controls_seq)
    step_indices = jnp.arange(n_steps, dtype=jnp.int32)

    def _body(carry, xs):
        step_idx, control = xs
        state, key = carry
        key, sub = jax.random.split(key)
        next_state, trace = step(
            state,
            control,
            sub,
            t=step_idx,
            static_bundle=static_bundle,
            nan_guard=nan_guard,
            strictness=strictness,
        )
        return (next_state, key), trace

    (final_state, _), traces = jax.lax.scan(
        _body,
        (initial_state, root_key),
        (step_indices, controls_seq),
    )
    return final_state, traces


def run_scan(
    initial_state, controls_seq, root_key, static_bundle=None, nan_guard=None, strictness=None
):
    """
    Run a lax.scan over controls_seq using pure step function.

    Instrumentation Note:
    - Span wraps the entire scan execution
    - Step count emitted as metric VALUE, not label
    """
    hpc_enabled = is_hpc_observability_enabled()
    n_steps = int(controls_seq.shape[0]) if hasattr(controls_seq, "shape") else len(controls_seq)

    with jit_aware_span(
        "foundry.run_scan",
        "run_scan",
        initial_state,
        controls_seq,
        span_attributes={"foundry.n_steps": n_steps},
        metric_attributes={"batch_size": "1"},
    ) as ctx:
        run_start = time.perf_counter()
        final_state, traces = _run_scan_core(
            initial_state,
            controls_seq,
            root_key,
            static_bundle=static_bundle,
            nan_guard=nan_guard,
            strictness=strictness,
        )
        if hpc_enabled:
            jax.block_until_ready(final_state)
            ctx.execute_seconds = time.perf_counter() - run_start

    if hpc_enabled and ctx.execute_seconds > 0:
        metrics = get_metrics()
        if metrics.simulation_steps_per_second:
            metrics.simulation_steps_per_second.set(
                n_steps / ctx.execute_seconds,
                {"backend": jax.default_backend(), "batch_size": "1"},
            )

    return traces


def _execute_program_batch_core(
    initial_states, controls_seq, root_key, static_bundle=None, nan_guard=None, strictness=None
):
    """Pure JAX batch execution core, safe for jit usage."""
    batch_size = int(initial_states.shape[0])
    keys = jax.random.split(root_key, batch_size)

    def _run_single(state, controls, key):
        _, traces = _run_scan_core(
            state,
            controls,
            key,
            static_bundle=static_bundle,
            nan_guard=nan_guard,
            strictness=strictness,
        )
        return traces

    return jax.vmap(_run_single)(initial_states, controls_seq, keys)


def execute_program_batch(
    initial_states, controls_seq, root_key, static_bundle=None, nan_guard=None, strictness=None
):
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
        run_start = time.perf_counter()
        result = _execute_program_batch_core(
            initial_states,
            controls_seq,
            root_key,
            static_bundle=static_bundle,
            nan_guard=nan_guard,
            strictness=strictness,
        )
        if hpc_enabled:
            jax.block_until_ready(result)
            ctx.execute_seconds = time.perf_counter() - run_start

    if hpc_enabled and ctx.execute_seconds > 0:
        metrics = get_metrics()
        total_steps = batch_size * n_steps
        if metrics.simulation_steps_per_second:
            metrics.simulation_steps_per_second.set(
                total_steps / ctx.execute_seconds,
                {"backend": jax.default_backend(), "batch_size": str(batch_size)},
            )
        if metrics.simulation_batch_size:
            metrics.simulation_batch_size.record(batch_size, {"func_name": "execute_program_batch"})

    return result


# Preserve core functions for direct access when needed
run_scan.__wrapped__ = _run_scan_core
execute_program_batch.__wrapped__ = _execute_program_batch_core

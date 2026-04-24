"""Propagate OpenTelemetry context across threads, async tasks, and HTTP boundaries.

Provides utilities for propagating trace context across:
- Thread boundaries (ThreadPoolExecutor)
- Async task boundaries
- Cross-service calls (HTTP headers)
- Message queues

Example:
    from polisyos.core.observability.propagation import (
        propagate_context,
        with_trace_context,
        inject_headers,
        extract_headers,
    )

    # Propagate to thread pool
    with propagate_context():
        executor.submit(task_func)

    # Wrap function with context
    wrapped = with_trace_context(task_func)
    executor.submit(wrapped)
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import copy_context
from typing import Any, ParamSpec, TypeVar

from opentelemetry import trace
from opentelemetry.context import Context, attach, detach, get_current
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

P = ParamSpec("P")
T = TypeVar("T")

_propagator = TraceContextTextMapPropagator()


def inject_headers(headers: dict[str, str]) -> dict[str, str]:
    """
    Inject trace context into HTTP headers.

    Args:
        headers: Existing headers dict (will be modified in place)

    Returns:
        Headers dict with trace context added
    """
    _propagator.inject(headers)
    return headers


def extract_headers(headers: dict[str, str]) -> Context:
    """
    Extract trace context from HTTP headers.

    Args:
        headers: HTTP headers containing trace context

    Returns:
        OTel Context that can be used with attach()
    """
    return _propagator.extract(headers)


@contextmanager
def propagate_context() -> Any:
    """
    Preserve the current OTel context while entering a manually managed scope.

    Useful for manually propagating context across thread boundaries.
    """
    ctx = get_current()
    token = attach(ctx)
    try:
        yield
    finally:
        detach(token)


def _bind_trace_context(
    func: Callable[P, T],
    *,
    ctx: Context | None = None,
) -> Callable[P, T]:
    """Capture the current OpenTelemetry context for deferred execution."""
    bound_ctx = ctx or get_current()

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        token = attach(bound_ctx)
        try:
            return func(*args, **kwargs)
        finally:
            detach(token)

    return wrapper


def _bind_context_vars(func: Callable[P, T]) -> Callable[P, T]:
    """Capture the full contextvars snapshot for deferred execution."""
    ctx = copy_context()

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        return ctx.run(func, *args, **kwargs)

    return wrapper


def with_trace_context(func: Callable[P, T]) -> Callable[P, T]:
    """
    Wrap a function so each invocation uses a fresh context snapshot.

    This helper is safe to keep around across multiple requests because it
    does not freeze trace state at decoration time. For deferred work submitted
    to an executor, use `TracedExecutorWrapper`, which snapshots at submit time.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function with captured context
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        bound = _bind_context_vars(_bind_trace_context(func))
        return bound(*args, **kwargs)

    return wrapper


def with_context_vars(func: Callable[P, T]) -> Callable[P, T]:
    """
    Wrap a function so each invocation uses the caller's current contextvars.

    The wrapper itself is safe to reuse across independent requests because
    the snapshot is taken on each invocation instead of decoration time.
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        bound = _bind_context_vars(func)
        return bound(*args, **kwargs)

    return wrapper


class TracedExecutorWrapper:
    """
    Wrap an executor so `submit`/`map` preserve the caller's trace context.

    Example:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor() as executor:
            traced_executor = TracedExecutorWrapper(executor)
            future = traced_executor.submit(my_task, arg1, arg2)
    """

    def __init__(self, executor: Any) -> None:
        self._executor = executor

    def submit(
        self,
        fn: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Any:
        """Submit a task with trace context propagation."""
        wrapped = _bind_context_vars(_bind_trace_context(fn))
        return self._executor.submit(wrapped, *args, **kwargs)

    def map(
        self,
        fn: Callable[..., T],
        *iterables: Any,
        **kwargs: Any,
    ) -> Any:
        """Call `executor.map()` with a context-preserving wrapper around `fn`."""
        wrapped = _bind_context_vars(_bind_trace_context(fn))
        return self._executor.map(wrapped, *iterables, **kwargs)

    def __enter__(self) -> TracedExecutorWrapper:
        """Enter the wrapped executor context and return the tracing wrapper."""
        self._executor.__enter__()
        return self

    def __exit__(self, *args: Any) -> Any:
        """Delegate context-manager teardown to the wrapped executor."""
        return self._executor.__exit__(*args)


def create_child_context(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> tuple[Context, trace.Span]:
    """
    Create a child span/context pair for manually managed parallel work.

    This creates a new span as a child of the current span,
    and returns both the context and span for manual management.

    Example:
        ctx, span = create_child_context("parallel_task")
        try:
            token = attach(ctx)
            # Do work in child context
        finally:
            span.end()
            detach(token)
    """
    tracer = trace.get_tracer("polisyos")
    span = tracer.start_span(name, attributes=attributes)
    ctx = trace.set_span_in_context(span)
    return ctx, span

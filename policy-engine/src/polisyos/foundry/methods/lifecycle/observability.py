"""
OpenTelemetry Instrumentation for Foundry method dispatch.

When ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set in the environment (or when
``opentelemetry-api`` is installed and configured), this module wraps
``MethodDispatcher.dispatch()`` with:

- A **trace span** per invocation (``foundry.method.<name>``).
- A **histogram** recording wall-clock time in ms
  (``foundry.method.duration_ms``).
- A **counter** tracking errors per method/backend pair
  (``foundry.method.errors_total``).

The instrumentation is **opt-in and zero-cost** when OpenTelemetry is not
installed.  Activation options:

1. Install ``opentelemetry-api`` + an exporter (e.g. ``opentelemetry-exporter-otlp``).
2. Set ``OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318`` or call
   ``activate_foundry_instrumentation()`` explicitly.

Attributes attached to every span and metric:
- ``method.fqn``      — fully-qualified method name
- ``method.backend``  — compute backend value
- ``method.fidelity`` — fidelity level
- ``method.tags``     — comma-joined sorted tags (top 5)

Usage
-----
::

    # Explicit activation (optional — auto-activates if OTEL env var is set)
    from polisyos.foundry.methods.lifecycle.observability import activate_foundry_instrumentation
    activate_foundry_instrumentation()

    # Then use MethodDispatcher normally — spans/metrics are emitted automatically
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, TypeVar

__all__ = [
    "InstrumentedDispatcher",
    "activate_foundry_instrumentation",
    "deactivate_foundry_instrumentation",
    "is_instrumentation_active",
]

T = TypeVar("T")

# ---------------------------------------------------------------------------
# OTel availability probe
# ---------------------------------------------------------------------------

_OTEL_AVAILABLE = False
_tracer = None
_method_duration_histogram = None
_method_errors_counter = None
_activation_lock = threading.Lock()
_is_active = False


def _try_import_otel() -> bool:
    """Return True if opentelemetry-api is importable."""
    try:
        import opentelemetry

        return True
    except ImportError:
        return False


def _init_otel_providers() -> None:
    """Initialise OTel tracer and meter (no-op if OTel unavailable)."""
    global _OTEL_AVAILABLE, _tracer, _method_duration_histogram, _method_errors_counter

    if not _try_import_otel():
        return

    try:
        from opentelemetry import metrics, trace

        _tracer = trace.get_tracer(
            "polisyos.foundry.methods",
            schema_url="https://opentelemetry.io/schemas/1.17.0",
        )
        meter = metrics.get_meter("polisyos.foundry")
        _method_duration_histogram = meter.create_histogram(
            name="foundry.method.duration_ms",
            unit="ms",
            description="Wall-clock execution time of a Foundry method dispatch call.",
        )
        _method_errors_counter = meter.create_counter(
            name="foundry.method.errors_total",
            unit="1",
            description="Total number of errors in Foundry method dispatch calls.",
        )
        _OTEL_AVAILABLE = True
    except Exception:
        # OTel initialisation must never break the application
        _OTEL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Attribute builders
# ---------------------------------------------------------------------------


def _build_attributes(signature: Any) -> dict[str, str]:
    """Build standard OTel attributes from a MethodSignature."""
    attrs: dict[str, str] = {
        "method.fqn": getattr(signature, "fqn", "unknown"),
        "method.backend": getattr(getattr(signature, "backend", None), "value", "unknown"),
        "method.fidelity": getattr(getattr(signature, "fidelity", None), "value", "unknown"),
    }
    tags = getattr(signature, "tags", frozenset())
    if tags:
        top_tags = sorted(str(t) for t in tags)[:5]
        attrs["method.tags"] = ",".join(top_tags)
    return attrs


# ---------------------------------------------------------------------------
# InstrumentedDispatcher
# ---------------------------------------------------------------------------


class InstrumentedDispatcher:
    """
    Wraps a ``MethodDispatcher`` with OTel spans and metrics.

    This class is a transparent proxy: all arguments are forwarded
    unchanged to the underlying dispatcher.

    Parameters
    ----------
    inner:
        The real ``MethodDispatcher`` to delegate to.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def dispatch(
        self,
        *,
        method_class: type,
        signature: Any,
        state: Any,
        params: Any,
        seed: int = 0,
    ) -> Any:
        """Dispatch with OTel tracing + metrics."""
        if not _OTEL_AVAILABLE or _tracer is None:
            return self._inner.dispatch(
                method_class=method_class,
                signature=signature,
                state=state,
                params=params,
                seed=seed,
            )

        from opentelemetry.trace import StatusCode

        attrs = _build_attributes(signature)
        span_name = f"foundry.method.{attrs.get('method.fqn', 'unknown')}"

        with _tracer.start_as_current_span(span_name, attributes=attrs) as span:
            t0 = time.perf_counter()
            try:
                result = self._inner.dispatch(
                    method_class=method_class,
                    signature=signature,
                    state=state,
                    params=params,
                    seed=seed,
                )
                span.set_status(StatusCode.OK)
                return result
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                if _method_errors_counter is not None:
                    _method_errors_counter.add(1, attrs)
                raise
            finally:
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                if _method_duration_histogram is not None:
                    _method_duration_histogram.record(elapsed_ms, attrs)

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attribute access to the inner dispatcher."""
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# Activation / deactivation
# ---------------------------------------------------------------------------


def activate_foundry_instrumentation() -> bool:
    """
    Activate OTel instrumentation for ``MethodDispatcher``.

    Patches the global ``MethodDispatcher`` singleton so that all subsequent
    ``dispatch()`` calls are wrapped with tracing + metrics.

    Returns ``True`` if activation succeeded, ``False`` if OTel is
    unavailable or already active.

    This function is idempotent — calling it multiple times is safe.
    """
    global _is_active

    with _activation_lock:
        if _is_active:
            return True

        _init_otel_providers()
        if not _OTEL_AVAILABLE:
            return False

        try:
            from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

            instance = MethodDispatcher.get_instance()
            if not isinstance(instance, InstrumentedDispatcher):
                # Monkey-patch the singleton's dispatch method
                original_dispatch = instance.dispatch

                def _instrumented_dispatch(**kwargs: Any) -> Any:
                    return InstrumentedDispatcher(instance)._inner_dispatch(
                        original_dispatch, **kwargs
                    )

                # Simpler approach: wrap the instance
                instrumented = InstrumentedDispatcher(instance)
                # Replace the singleton
                MethodDispatcher._instance = instrumented  # type: ignore[attr-defined]

            _is_active = True
            return True
        except Exception:
            return False


def deactivate_foundry_instrumentation() -> None:
    """
    Deactivate OTel instrumentation (restore original dispatcher).

    Primarily for testing.
    """
    global _is_active

    with _activation_lock:
        if not _is_active:
            return
        try:
            from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

            instance = MethodDispatcher.get_instance()
            if isinstance(instance, InstrumentedDispatcher):
                MethodDispatcher._instance = instance._inner  # type: ignore[attr-defined]
        except Exception:
            pass
        _is_active = False


def is_instrumentation_active() -> bool:
    """Return True if OTel instrumentation is currently active."""
    return _is_active


# ---------------------------------------------------------------------------
# Auto-activation on import if OTEL env var is set
# ---------------------------------------------------------------------------


def _maybe_auto_activate() -> None:
    """Auto-activate if OTEL_EXPORTER_OTLP_ENDPOINT is configured."""
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        activate_foundry_instrumentation()


_maybe_auto_activate()

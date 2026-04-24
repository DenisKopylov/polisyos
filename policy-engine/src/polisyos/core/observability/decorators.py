"""
PolicyOS Tracing Decorators — Zero-configuration instrumentation.

Provides the @traced decorator for automatic span creation with:
- Function argument capture (configurable)
- Exception recording with stack traces
- Context propagation to child functions
- Integration with PolicyOS semantic conventions

Usage:
    from polisyos.core.observability import traced

    @traced
    def my_function(arg1, arg2):
        return result

    @traced(name="custom_name", capture_args=True)
    def my_function_with_args(policy_ir: dict) -> dict:
        return process(policy_ir)

    @traced(phase="VALIDATE", agent="governor")
    async def validate_policy(bundle: TrinityBundle) -> ValidationResult:
        return await run_validation(bundle)
"""

from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Any, cast, overload

from opentelemetry.trace import SpanKind, Status, StatusCode

from polisyos.core.security.tenant_context import (
    get_current_access_scope_or_none,
    get_current_cell_id,
    get_current_tenant_id_or_none,
)

from .tracer import get_tracer

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Concatenate

    from .tracer import PolicyOSTracer


def _default_tracer() -> PolicyOSTracer:
    return get_tracer()


def _extract_attributes_from_args(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    max_value_length: int = 256,
) -> dict[str, Any]:
    """
    Extract function arguments as span attributes.

    Handles truncation of long values and type conversion.
    """
    attributes: dict[str, Any] = {}
    sig = inspect.signature(func)
    bound = sig.bind_partial(*args, **kwargs)

    for param_name, value in bound.arguments.items():
        # Skip self/cls for methods
        if param_name in ("self", "cls"):
            continue

        # Convert to attribute-safe value
        attr_value = _safe_attribute_value(value, max_value_length)
        if attr_value is not None:
            attributes[f"function.arg.{param_name}"] = attr_value

    return attributes


def _safe_attribute_value(
    value: Any,
    max_length: int = 256,
) -> str | int | float | bool | None:
    """
    Convert a value to a span attribute-safe type.

    OTel attributes support: str, bool, int, float, and sequences thereof.
    """
    if value is None:
        return None

    if isinstance(value, (bool, int, float)):
        return value

    if isinstance(value, str):
        if len(value) > max_length:
            return value[:max_length] + "..."
        return value

    # For complex types, convert to string representation
    try:
        str_val = str(value)
        if len(str_val) > max_length:
            return str_val[:max_length] + "..."
        return str_val
    except Exception:
        return f"<{type(value).__name__}>"


def _attach_tenant_attributes(span: Any) -> None:
    tenant_id = get_current_tenant_id_or_none()
    if tenant_id is not None:
        span.set_attribute("tenant.id", tenant_id)
    cell_id = get_current_cell_id()
    if cell_id is not None:
        span.set_attribute("cell.id", cell_id)
        span.set_attribute("tenant.cell_id", cell_id)

    access_scope = get_current_access_scope_or_none()
    if access_scope is not None:
        for key, value in access_scope.to_otel_attributes().items():
            if value != "":
                span.set_attribute(key, value)


@overload
def traced[**P, T](func: Callable[P, T]) -> Callable[P, T]:
    """Decorate `func` with automatic span creation using default options."""
    ...


@overload
def traced[**P, T](
    *,
    name: str | None = None,
    capture_args: bool = False,
    capture_result: bool = False,
    phase: str | None = None,
    agent: str | None = None,
    node: str | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
    tracer_factory: Callable[[], Any] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Return a configured tracing decorator for sync or async callables."""
    ...


def traced[**P, T](
    func: Callable[P, T] | None = None,
    *,
    name: str | None = None,
    capture_args: bool = False,
    capture_result: bool = False,
    phase: str | None = None,
    agent: str | None = None,
    node: str | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
    tracer_factory: Callable[[], Any] | None = None,
) -> Callable[P, T] | Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator for automatic span creation around functions.

    Can be used with or without parentheses:
        @traced
        def my_func(): ...

        @traced(phase="VALIDATE")
        def my_func(): ...

    Args:
        name: Custom span name (defaults to function name)
        capture_args: If True, record function arguments as attributes
        capture_result: If True, record function return value as attribute
        phase: PolicyOS phase (FRAME, DRAFT, VALIDATE, EXECUTE, etc.)
        agent: Agent name (drafter, formalizer, critic, governor)
        node: Flow node name (draft_ir, formalize, validate, run_sim)
        kind: Span kind (INTERNAL, CLIENT, SERVER, PRODUCER, CONSUMER)
        tracer_factory: Optional provider hook used to resolve a tracer per invocation.

    Returns:
        Decorated function with automatic tracing
    """

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        span_name = name or fn.__qualname__
        resolved_tracer_factory = tracer_factory or _default_tracer

        # Build static attributes
        static_attrs: dict[str, Any] = {}
        if phase:
            static_attrs["polisyos.phase"] = phase
        if agent:
            static_attrs["polisyos.agent.name"] = agent
        if node:
            static_attrs["polisyos.node.name"] = node

        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                tracer = resolved_tracer_factory()

                # Build attributes
                attributes = dict(static_attrs)
                if capture_args:
                    attributes.update(_extract_attributes_from_args(fn, args, kwargs))

                with tracer.start_as_current_span(
                    span_name,
                    attributes=attributes,
                    kind=kind,
                ) as span:
                    _attach_tenant_attributes(span)
                    try:
                        result = await fn(*args, **kwargs)

                        if capture_result:
                            result_attr = _safe_attribute_value(result)
                            if result_attr is not None:
                                span.set_attribute("function.result", result_attr)

                        return cast("T", result)

                    except Exception as exc:
                        span.set_status(Status(status_code=StatusCode.ERROR, description=str(exc)))
                        span.record_exception(exc)
                        raise

            return cast("Callable[P, T]", async_wrapper)

        @functools.wraps(fn)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            tracer = resolved_tracer_factory()

            # Build attributes
            attributes = dict(static_attrs)
            if capture_args:
                attributes.update(_extract_attributes_from_args(fn, args, kwargs))

            with tracer.start_as_current_span(
                span_name,
                attributes=attributes,
                kind=kind,
            ) as span:
                _attach_tenant_attributes(span)
                try:
                    result = fn(*args, **kwargs)

                    if capture_result:
                        result_attr = _safe_attribute_value(result)
                        if result_attr is not None:
                            span.set_attribute("function.result", result_attr)

                    return result

                except Exception as exc:
                    span.set_status(Status(status_code=StatusCode.ERROR, description=str(exc)))
                    span.record_exception(exc)
                    raise

        return cast("Callable[P, T]", sync_wrapper)

    # Handle both @traced and @traced() syntax
    if func is not None:
        return decorator(func)
    return decorator


def traced_method[**P, T](
    *,
    name: str | None = None,
    capture_args: bool = False,
    phase: str | None = None,
    agent: str | None = None,
    tracer_factory: Callable[[], Any] | None = None,
) -> Callable[[Callable[Concatenate[Any, P], T]], Callable[Concatenate[Any, P], T]]:
    """
    Specialized decorator for class methods.

    Automatically extracts run_id from self if available.
    """

    def decorator(fn: Callable[Concatenate[Any, P], T]) -> Callable[Concatenate[Any, P], T]:
        span_name = name or fn.__qualname__
        resolved_tracer_factory = tracer_factory or _default_tracer

        @functools.wraps(fn)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
            tracer = resolved_tracer_factory()

            # Build attributes
            attributes: dict[str, Any] = {}
            if phase:
                attributes["polisyos.phase"] = phase
            if agent:
                attributes["polisyos.agent.name"] = agent

            # Try to extract run_id from self
            run_id = getattr(self, "run_id", None) or getattr(self, "_run_id", None)
            if run_id:
                attributes["polisyos.run_id"] = str(run_id)

            if capture_args:
                attributes.update(_extract_attributes_from_args(fn, (self, *args), kwargs))

            with tracer.start_as_current_span(
                span_name,
                attributes=attributes,
            ) as span:
                try:
                    return fn(self, *args, **kwargs)
                except Exception as exc:
                    span.set_status(Status(status_code=StatusCode.ERROR, description=str(exc)))
                    span.record_exception(exc)
                    raise

        return cast("Callable[Concatenate[Any, P], T]", wrapper)

    return decorator

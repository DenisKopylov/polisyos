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

import asyncio
import functools
import inspect
from typing import Any, Callable, Optional, ParamSpec, TypeVar, Union, overload

from opentelemetry.trace import SpanKind, Status, StatusCode

from .tracer import get_tracer

P = ParamSpec("P")
T = TypeVar("T")


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
) -> Optional[Union[str, int, float, bool]]:
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


@overload
def traced(func: Callable[P, T]) -> Callable[P, T]: ...


@overload
def traced(
    *,
    name: Optional[str] = None,
    capture_args: bool = False,
    capture_result: bool = False,
    phase: Optional[str] = None,
    agent: Optional[str] = None,
    node: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


def traced(
    func: Optional[Callable[P, T]] = None,
    *,
    name: Optional[str] = None,
    capture_args: bool = False,
    capture_result: bool = False,
    phase: Optional[str] = None,
    agent: Optional[str] = None,
    node: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
) -> Union[Callable[P, T], Callable[[Callable[P, T]], Callable[P, T]]]:
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

    Returns:
        Decorated function with automatic tracing
    """

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        span_name = name or fn.__qualname__

        # Build static attributes
        static_attrs: dict[str, Any] = {}
        if phase:
            static_attrs["polisyos.phase"] = phase
        if agent:
            static_attrs["polisyos.agent.name"] = agent
        if node:
            static_attrs["polisyos.node.name"] = node

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                tracer = get_tracer()

                # Build attributes
                attributes = dict(static_attrs)
                if capture_args:
                    attributes.update(_extract_attributes_from_args(fn, args, kwargs))

                with tracer.start_as_current_span(
                    span_name,
                    attributes=attributes,
                    kind=kind,
                ) as span:
                    try:
                        result = await fn(*args, **kwargs)

                        if capture_result:
                            span.set_attribute(
                                "function.result",
                                _safe_attribute_value(result),
                            )

                        return result

                    except Exception as exc:
                        span.set_status(Status(status_code=StatusCode.ERROR, description=str(exc)))
                        span.record_exception(exc)
                        raise

            return async_wrapper  # type: ignore

        @functools.wraps(fn)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            tracer = get_tracer()

            # Build attributes
            attributes = dict(static_attrs)
            if capture_args:
                attributes.update(_extract_attributes_from_args(fn, args, kwargs))

            with tracer.start_as_current_span(
                span_name,
                attributes=attributes,
                kind=kind,
            ) as span:
                try:
                    result = fn(*args, **kwargs)

                    if capture_result:
                        span.set_attribute(
                            "function.result",
                            _safe_attribute_value(result),
                        )

                    return result

                except Exception as exc:
                    span.set_status(Status(status_code=StatusCode.ERROR, description=str(exc)))
                    span.record_exception(exc)
                    raise

        return sync_wrapper  # type: ignore

    # Handle both @traced and @traced() syntax
    if func is not None:
        return decorator(func)
    return decorator


def traced_method(
    *,
    name: Optional[str] = None,
    capture_args: bool = False,
    phase: Optional[str] = None,
    agent: Optional[str] = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Specialized decorator for class methods.

    Automatically extracts run_id from self if available.
    """

    def decorator(fn: Callable[P, T]) -> Callable[P, T]:
        span_name = name or fn.__qualname__

        @functools.wraps(fn)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> T:
            tracer = get_tracer()

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

        return wrapper  # type: ignore

    return decorator

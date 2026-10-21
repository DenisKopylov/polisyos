"""Capability checking utilities and decorators."""

from __future__ import annotations

import ast
import dis
import inspect
import textwrap
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Concatenate,
    ParamSpec,
    Protocol,
    TypeGuard,
    TypeVar,
    overload,
)

from polisyos.ir.connectors import ConnectorCapability

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

    from polisyos.fabric.connectors.base import SourceConnector


P = ParamSpec("P")
R = TypeVar("R")
ConnectorT = TypeVar("ConnectorT", bound="_CapabilitySubject")


class _CapabilitySubject(Protocol):
    """Instance shape needed by capability-guarded methods."""

    @property
    def connector_id(self) -> str: ...

    @property
    def capabilities(self) -> ConnectorCapability: ...


class _CapabilityDecorator(Protocol):
    """Callable contract that preserves decorated method signatures."""

    @overload
    def __call__(
        self,
        func: Callable[Concatenate[ConnectorT, P], Coroutine[object, object, R]],
    ) -> Callable[Concatenate[ConnectorT, P], Coroutine[object, object, R]]: ...

    @overload
    def __call__(
        self,
        func: Callable[Concatenate[ConnectorT, P], R],
    ) -> Callable[Concatenate[ConnectorT, P], R]: ...


def _is_async_method(
    func: Callable[..., object],
) -> TypeGuard[Callable[..., Awaitable[object]]]:
    """Narrow methods recognized by Python as coroutine callables."""
    return inspect.iscoroutinefunction(func)


def _read_dynamic_attribute(receiver: object, attribute_name: str) -> object:
    """Read an attribute from an object undergoing runtime protocol inspection."""
    return getattr(receiver, attribute_name)


# ============================================================================
# Capability Decorators
# ============================================================================


def _wrap_capability_method(
    func: Callable[..., object],
    validate: Callable[[_CapabilitySubject], None],
) -> object:
    """Wrap a typed method while preserving its sync or coroutine execution form."""
    if _is_async_method(func):

        @wraps(func)
        async def async_wrapper(
            self: _CapabilitySubject,
            *args: object,
            **kwargs: object,
        ) -> object:
            validate(self)
            return await func(self, *args, **kwargs)

        return async_wrapper

    @wraps(func)
    def sync_wrapper(
        self: _CapabilitySubject,
        *args: object,
        **kwargs: object,
    ) -> object:
        validate(self)
        return func(self, *args, **kwargs)

    return sync_wrapper


def requires_capability(
    cap: ConnectorCapability,
    *,
    error_message: str | None = None,
) -> _CapabilityDecorator:
    """Decorator that validates connector has required capability before execution."""

    def validate(self: _CapabilitySubject) -> None:
        from polisyos.fabric.connectors.types import CapabilityError

        connector_caps = getattr(self, "capabilities", ConnectorCapability(0))
        connector_id = getattr(self, "connector_id", "unknown")

        if not (connector_caps & cap):
            msg = error_message or f"Method requires capability: {cap.name}"
            raise CapabilityError(
                connector_id=connector_id,
                required=cap,
                available=connector_caps,
                message=msg,
            )

    @overload
    def decorator(
        func: Callable[Concatenate[ConnectorT, P], Coroutine[object, object, R]],
    ) -> Callable[Concatenate[ConnectorT, P], Coroutine[object, object, R]]: ...

    @overload
    def decorator(
        func: Callable[Concatenate[ConnectorT, P], R],
    ) -> Callable[Concatenate[ConnectorT, P], R]: ...

    def decorator(func: Callable[..., object]) -> object:
        return _wrap_capability_method(func, validate)

    return decorator


def requires_any_capability(
    *caps: ConnectorCapability,
    error_message: str | None = None,
) -> _CapabilityDecorator:
    """Decorator that validates connector has at least one of the required capabilities."""

    def validate(self: _CapabilitySubject) -> None:
        from polisyos.fabric.connectors.types import CapabilityError

        connector_caps = getattr(self, "capabilities", ConnectorCapability(0))
        connector_id = getattr(self, "connector_id", "unknown")

        if not any(connector_caps & cap for cap in caps):
            cap_names = ", ".join(cap.name or str(cap) for cap in caps)
            raise CapabilityError(
                connector_id=connector_id,
                required=caps[0],
                available=connector_caps,
                message=error_message or f"Method requires one of: {cap_names}",
            )

    @overload
    def decorator(
        func: Callable[Concatenate[ConnectorT, P], Coroutine[object, object, R]],
    ) -> Callable[Concatenate[ConnectorT, P], Coroutine[object, object, R]]: ...

    @overload
    def decorator(
        func: Callable[Concatenate[ConnectorT, P], R],
    ) -> Callable[Concatenate[ConnectorT, P], R]: ...

    def decorator(func: Callable[..., object]) -> object:
        return _wrap_capability_method(func, validate)

    return decorator


# ============================================================================
# Protocol Compliance Validation
# ============================================================================


CAPABILITY_METHOD_REQUIREMENTS: dict[ConnectorCapability, tuple[str, ...]] = {
    ConnectorCapability.CATALOG_BROWSE: ("list_datasets",),
    ConnectorCapability.STREAMING: ("fetch_stream",),
    ConnectorCapability.FRESHNESS_CHECK: ("check_freshness",),
    ConnectorCapability.SCHEMA_INTROSPECTION: ("get_dataset_schema",),
}

REQUIRED_METHODS = (
    "connect",
    "disconnect",
    "health_check",
    "fetch",
)

REQUIRED_ATTRIBUTES = (
    "connector_id",
    "capabilities",
    "metadata",
)


def validate_protocol_compliance(
    connector_class: type[object],
    *,
    strict: bool = True,
) -> list[str]:
    """Validate that a connector class properly implements the SourceConnector protocol."""
    violations: list[str] = []

    for attr in REQUIRED_ATTRIBUTES:
        if not hasattr(connector_class, attr):
            violations.append(f"Missing required class attribute: {attr}")

    for method in REQUIRED_METHODS:
        if not hasattr(connector_class, method):
            violations.append(f"Missing required method: {method}")
            continue

        if strict:
            method_obj = getattr(connector_class, method)
            if _is_protocol_stub(method_obj):
                violations.append(f"Method '{method}' must be implemented")
            elif not inspect.iscoroutinefunction(method_obj):
                violations.append(f"Method '{method}' must be async")

    caps = getattr(connector_class, "capabilities", ConnectorCapability(0))

    for cap, required_methods in CAPABILITY_METHOD_REQUIREMENTS.items():
        if caps & cap:
            for method in required_methods:
                if not hasattr(connector_class, method):
                    violations.append(
                        f"Capability {cap.name} requires method '{method}' but it's not implemented"
                    )
                    continue

                method_obj = getattr(connector_class, method)
                if _is_baseconnector_default(connector_class, method):
                    violations.append(
                        f"Capability {cap.name} requires method '{method}' "
                        "but only BaseConnector default is present"
                    )
                    continue

                if _is_protocol_stub(method_obj):
                    violations.append(
                        f"Capability {cap.name} requires method '{method}' "
                        "but it's not implemented (only Protocol stub found)"
                    )
                    continue

                if strict and not _is_async_callable(method_obj, method_name=method):
                    violations.append(f"Method '{method}' for capability {cap.name} must be async")

    if hasattr(connector_class, "metadata") and hasattr(connector_class, "capabilities"):
        metadata = _read_dynamic_attribute(connector_class, "metadata")
        declared_caps = _read_dynamic_attribute(connector_class, "capabilities")
        if hasattr(metadata, "capabilities"):
            metadata_caps = ConnectorCapability(_read_dynamic_attribute(metadata, "capabilities"))
            if metadata_caps != declared_caps:
                violations.append(
                    f"Metadata capabilities ({metadata_caps}) don't match "
                    f"class capabilities ({declared_caps})"
                )

    return violations


def _is_async_callable(method: Callable[..., object], *, method_name: str | None = None) -> bool:
    if inspect.iscoroutinefunction(method):
        return True
    return bool(
        method_name in {"list_datasets", "fetch_stream"} and inspect.isasyncgenfunction(method)
    )


def _is_protocol_stub(method: Callable[..., object]) -> bool:
    """Check if a method body is effectively a stub."""
    unwrapped = inspect.unwrap(method)
    try:
        source = textwrap.dedent(inspect.getsource(unwrapped))
        module = ast.parse(source)
    except (OSError, TypeError, SyntaxError):
        return _is_empty_return_stub(unwrapped)

    function_defs = [
        node
        for node in ast.walk(module)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    method_name = getattr(unwrapped, "__name__", "")
    function_def = next((node for node in function_defs if node.name == method_name), None)
    if function_def is None and len(function_defs) == 1:
        function_def = function_defs[0]
    if function_def is None:
        return _is_empty_return_stub(unwrapped)

    body = list(function_def.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]

    if not body:
        return True
    if len(body) != 1:
        return False

    statement = body[0]
    if isinstance(statement, ast.Pass):
        return True
    if (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and statement.value.value is Ellipsis
    ):
        return True
    if isinstance(statement, ast.Raise):
        exc = statement.exc
        if isinstance(exc, ast.Call):
            exc = exc.func
        return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"
    return False


def _is_empty_return_stub(method: Callable[..., object]) -> bool:
    try:
        instructions = [
            instruction
            for instruction in dis.get_instructions(method)
            if instruction.opname
            not in {
                "CACHE",
                "CALL_INTRINSIC_1",
                "COPY_FREE_VARS",
                "EXTENDED_ARG",
                "MAKE_CELL",
                "NOP",
                "POP_TOP",
                "RERAISE",
                "RESUME",
                "RETURN_GENERATOR",
            }
        ]
    except TypeError:
        return False
    return (
        len(instructions) == 2
        and instructions[0].opname == "LOAD_CONST"
        and instructions[0].argval is None
        and instructions[1].opname == "RETURN_VALUE"
    )


def _is_baseconnector_default(connector_class: type[object], method_name: str) -> bool:
    try:
        from polisyos.fabric.connectors.base import BaseConnector
    except ImportError:
        return False

    base_impl = getattr(BaseConnector, method_name, None)
    impl = getattr(connector_class, method_name, None)
    if base_impl is None or impl is None:
        return False
    return impl is base_impl


def check_capability_at_runtime[ConnectorDataT](
    connector: SourceConnector[ConnectorDataT],
    required: ConnectorCapability,
) -> bool:
    """Check if a connector instance has a required capability at runtime."""
    caps = getattr(connector, "capabilities", ConnectorCapability(0))
    return bool(caps & required)


def get_missing_capabilities[ConnectorDataT](
    connector: SourceConnector[ConnectorDataT],
    required: ConnectorCapability,
) -> list[ConnectorCapability]:
    """Get list of missing capabilities from a required set."""
    caps = getattr(connector, "capabilities", ConnectorCapability(0))
    missing: list[ConnectorCapability] = []

    for cap in ConnectorCapability:
        if (required & cap) and not (caps & cap):
            missing.append(cap)

    return missing


# ============================================================================
# Capability Metadata Helpers
# ============================================================================


def describe_capabilities(caps: ConnectorCapability) -> dict[str, list[str]]:
    """Describe capabilities in human-readable categories."""
    categories = {
        "data_access": [
            ConnectorCapability.CATALOG_BROWSE,
            ConnectorCapability.FULL_FETCH,
            ConnectorCapability.INCREMENTAL_FETCH,
            ConnectorCapability.STREAMING,
        ],
        "filtering": [
            ConnectorCapability.DATE_RANGE_FILTER,
            ConnectorCapability.DIMENSION_FILTER,
            ConnectorCapability.CUSTOM_QUERY,
        ],
        "metadata": [
            ConnectorCapability.SCHEMA_INTROSPECTION,
            ConnectorCapability.FRESHNESS_CHECK,
            ConnectorCapability.PROVENANCE_METADATA,
        ],
        "quality": [
            ConnectorCapability.REVISION_HISTORY,
            ConnectorCapability.CONFIDENCE_INTERVALS,
        ],
        "operational": [
            ConnectorCapability.RATE_LIMIT_AWARE,
            ConnectorCapability.RESUMABLE,
        ],
    }

    result: dict[str, list[str]] = {}
    for category, category_caps in categories.items():
        present = [cap.name or str(cap) for cap in category_caps if caps & cap]
        if present:
            result[category] = present

    return result


def capabilities_summary(caps: ConnectorCapability) -> str:
    """Generate a one-line summary of capabilities."""
    present = [cap.name or str(cap) for cap in ConnectorCapability if caps & cap]
    return ", ".join(present) if present else "none"

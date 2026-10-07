"""Project the supported runtime code graph for execution and compiler identity.

The projection delegates source hashing to the artifact owner. Consumers use
the existing canonical digest for their complete request/cache key. It never
executes a helper or descriptor to discover its implementation.
"""

from __future__ import annotations

import dis
import inspect
import sys
from collections.abc import Callable
from dataclasses import fields, is_dataclass
from enum import Enum
from types import CodeType, FunctionType, MappingProxyType, MemberDescriptorType, ModuleType
from typing import Any

from polisyos.core.canon import to_canonical_bytes

from ._fingerprint import compute_source_hash

__all__ = ["SourceIdentityUnavailableError", "implementation_identity_projection"]


class SourceIdentityUnavailableError(ValueError):
    """A code graph includes mutable, dynamic or unavailable identity inputs."""


_CLASS_STRUCTURE = frozenset(
    {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__", "__annotations__"}
)


def implementation_identity_projection(
    implementation: type | Callable[..., Any], *, strict: bool = True
) -> dict[str, Any]:
    """Bind supported class descriptors, Python functions and immutable captures.

    Python classes must use the ordinary ``type`` metaclass. Static/class
    methods, functions and property accessors are inspected without invoking
    them. Immutable scalar/tuple/frozenset values, mapping proxies and frozen
    dataclass field values are supported; mutable captures, custom descriptors,
    callable instances and decorated functions with ``__wrapped__`` are not.
    Captured modules require static global/nonlocal attribute selection. Their
    selected members bind the supported graph. External callable internals and
    unavailable builtins retain an explicit distribution/Python boundary; this
    is not a claim about mutable internals of installed numerical libraries.

    ``strict=False`` records an explicit unavailable marker for legacy request
    identity. That profile does not establish complete implementation closure.
    """
    return {
        "profile": "supported-python-code-graph-v2",
        "implementation": _project(implementation, strict=strict, visiting=set()),
    }


def _unavailable(value: Any, strict: bool) -> dict[str, str]:
    if strict:
        raise SourceIdentityUnavailableError(
            "source identity is unavailable for " + type(value).__name__
        )
    return {"unavailable_type": f"{type(value).__module__}.{type(value).__qualname__}"}


def _version(root: str) -> str | None:
    if root in sys.stdlib_module_names or root == "builtins":
        return sys.version
    # Keep dependency aliases/version resolution with the existing owner.
    from polisyos.foundry.methods.backends.runtime_fingerprint import capture_versions

    return next(iter(capture_versions(base_packages=(), runtime_stack=(root,)).values()), None)


def _module_paths(code: CodeType, name: str) -> set[tuple[str, ...]] | None:
    """Read static selections without evaluating module getters or imports."""
    paths: set[tuple[str, ...]] = set()
    instructions = list(dis.get_instructions(code))
    for index, instruction in enumerate(instructions):
        if instruction.opname not in {"LOAD_GLOBAL", "LOAD_DEREF", "LOAD_NAME"}:
            continue
        if instruction.argval != name:
            continue
        path = []
        for following in instructions[index + 1 :]:
            if following.opname != "LOAD_ATTR":
                break
            path.append(following.argval)
        if not path:
            # Passing/aliasing a module or reflecting over it has no declared
            # static member closure. A version alone cannot admit that graph.
            return None
        paths.add(tuple(path))
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            nested = _module_paths(constant, name)
            if nested is None:
                return None
            paths.update(nested)
    return paths


def _external_member_boundary(value: Any) -> dict[str, Any] | None:
    """Bind an installed callable's selection, without claiming its internals."""
    if not (inspect.isfunction(value) or inspect.isclass(value) or callable(value)):
        return None
    value_type = type(value)
    module = inspect.getattr_static(value, "__module__", value_type.__module__)
    if not isinstance(module, str):
        module = value_type.__module__
    root = module.split(".")[0]
    if root in sys.stdlib_module_names or root == "builtins":
        return None
    version = _version(root)
    if version is None:
        return None
    name = inspect.getattr_static(value, "__qualname__", None)
    if not isinstance(name, str):
        name = inspect.getattr_static(value, "__name__", value_type.__qualname__)
    if not isinstance(name, str):
        name = value_type.__qualname__
    source_value = value if inspect.isfunction(value) or type(value) is type else value_type
    return {
        "external_callable_boundary": {
            "symbol": f"{module}.{name}",
            "type": f"{value_type.__module__}.{value_type.__qualname__}",
            "source_hash": compute_source_hash(source_value),
            "distribution_version": version,
            "mutable_internals": "not_bound",
        }
    }


def _module_capture(
    function: FunctionType, name: str, module: ModuleType, *, strict: bool, visiting: set[int]
) -> Any:
    if type(module) is not ModuleType:
        return _unavailable(module, strict)
    paths = _module_paths(function.__code__, name)
    version = _version(module.__name__.split(".")[0])
    if not paths or version is None:
        return _unavailable(module, strict)
    members = {}
    for path in sorted(paths):
        current: Any = module
        for attribute in path:
            if type(current) is not ModuleType or attribute not in vars(current):
                return _unavailable(module, strict)
            current = vars(current)[attribute]
        try:
            member = _project(current, strict=strict, visiting=visiting)
        except SourceIdentityUnavailableError:
            member = _external_member_boundary(current)
            if member is None:
                raise
        members[".".join(path)] = member
    return {"module": module.__name__, "version": version, "selected_members": members}


def _project(value: Any, *, strict: bool, visiting: set[int]) -> Any:
    if isinstance(value, Enum):
        return {
            "enum": f"{type(value).__module__}.{type(value).__qualname__}",
            "value": _project(value.value, strict=strict, visiting=visiting),
        }
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return {"float_hex": value.hex()}
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, tuple):
        return {"tuple": [_project(item, strict=strict, visiting=visiting) for item in value]}
    if isinstance(value, frozenset):
        projected = [_project(item, strict=strict, visiting=visiting) for item in value]
        return {"frozenset": sorted(projected, key=to_canonical_bytes)}
    if isinstance(value, MappingProxyType):
        if not all(isinstance(key, str) for key in value):
            return _unavailable(value, strict)
        return {
            "mapping_proxy": {
                key: _project(item, strict=strict, visiting=visiting)
                for key, item in sorted(value.items())
            }
        }
    if isinstance(value, (staticmethod, classmethod)):
        return {
            "descriptor": type(value).__name__,
            "function": _project(value.__func__, strict=strict, visiting=visiting),
        }
    if isinstance(value, property):
        return {
            "descriptor": "property",
            "get": _project(value.fget, strict=strict, visiting=visiting),
            "set": _project(value.fset, strict=strict, visiting=visiting),
            "delete": _project(value.fdel, strict=strict, visiting=visiting),
        }
    if isinstance(value, ModuleType):
        # A bare module has no static access context. Only _module_capture may
        # admit its selected members; do not rescue dynamic transport by name.
        return _unavailable(value, strict)
    if is_dataclass(value) and not isinstance(value, type):
        record_type = type(value)
        if (
            type(record_type) is not type
            or not value.__dataclass_params__.frozen
            or record_type.__getattribute__ is not object.__getattribute__
            or any("__getattr__" in vars(base) for base in record_type.__mro__)
        ):
            return _unavailable(value, strict)
        # Records are immutable data inputs; read their fields without calling
        # stable_digest or other user methods during identity capture.
        record_fields = {}
        for item in fields(value):
            descriptor = inspect.getattr_static(record_type, item.name, None)
            if hasattr(type(descriptor), "__get__") and not isinstance(
                descriptor, MemberDescriptorType
            ):
                return _unavailable(value, strict)
            record_fields[item.name] = _project(
                object.__getattribute__(value, item.name), strict=strict, visiting=visiting
            )
        return {
            "frozen_record": f"{record_type.__module__}.{record_type.__qualname__}",
            "source_hash": compute_source_hash(record_type),
            "fields": record_fields,
        }
    if inspect.isfunction(value) or inspect.isclass(value) or inspect.isbuiltin(value):
        symbol = f"{value.__module__ or '<unknown>'}.{value.__qualname__}"
        if id(value) in visiting:
            return {"recursive_symbol": symbol}
        source = compute_source_hash(value)
        if inspect.isbuiltin(value) or (
            source == "unavailable" and str(value.__module__) == "builtins"
        ):
            version = _version(str(value.__module__).split(".")[0])
            if version is not None:
                return {"symbol": symbol, "distribution_version": version}
            return _unavailable(value, strict)
        if inspect.isfunction(value) and (source == "unavailable" or "__wrapped__" in vars(value)):
            return _unavailable(value, strict)
        if inspect.isclass(value) and type(value) is not type:
            return _unavailable(value, strict)
        visiting.add(id(value))
        try:
            result: dict[str, Any] = {"symbol": symbol, "source_hash": source}
            if inspect.isclass(value):
                result["bases"] = [
                    _project(base, strict=strict, visiting=visiting)
                    for base in value.__bases__
                    if base is not object
                ]
                result["attributes"] = {
                    name: _project(item, strict=strict, visiting=visiting)
                    for name, item in sorted(vars(value).items())
                    if name not in _CLASS_STRUCTURE
                }
            else:
                captures = inspect.getclosurevars(value)
                result["captures"] = {
                    name: (
                        _module_capture(value, name, item, strict=strict, visiting=visiting)
                        if isinstance(item, ModuleType)
                        else _project(item, strict=strict, visiting=visiting)
                    )
                    for name, item in sorted(
                        (captures.globals | captures.nonlocals | captures.builtins).items()
                    )
                }
                result["defaults"] = _project(value.__defaults__, strict=strict, visiting=visiting)
                result["keyword_defaults"] = {
                    name: _project(item, strict=strict, visiting=visiting)
                    for name, item in sorted((value.__kwdefaults__ or {}).items())
                }
                result["attributes"] = {
                    name: _project(item, strict=strict, visiting=visiting)
                    for name, item in sorted(vars(value).items())
                }
            return result
        finally:
            visiting.remove(id(value))
    return _unavailable(value, strict)

"""Project the supported runtime code graph for execution and compiler identity.

The projection delegates source hashing to the artifact owner. Consumers use
the existing canonical digest for their complete request/cache key. It never
executes a helper or descriptor to discover its implementation.
"""

from __future__ import annotations

import ast
import builtins
import dis
import inspect
import symtable
import sys
import textwrap
from collections.abc import Callable, Iterator
from dataclasses import fields, is_dataclass
from enum import Enum
from types import CodeType, FunctionType, MappingProxyType, MemberDescriptorType, ModuleType
from typing import Any, cast

from polisyos.core.canon import to_canonical_bytes

from ._fingerprint import compute_source_hash

__all__ = ["SourceIdentityUnavailableError", "implementation_identity_projection"]


class SourceIdentityUnavailableError(ValueError):
    """A code graph includes mutable, dynamic or unavailable identity inputs."""


_CLASS_STRUCTURE = frozenset(
    {"__module__", "__qualname__", "__doc__", "__dict__", "__weakref__", "__annotations__"}
)


# Namespace-producing and reflective builtins have no static selected-member
# graph. Bind by the actual builtin object so renaming a captured alias cannot
# turn their Python version into proof of a module's current selected content.
_DYNAMIC_BUILTINS = frozenset(
    {
        builtins.__import__,
        builtins.compile,
        builtins.delattr,
        builtins.dir,
        builtins.eval,
        builtins.exec,
        builtins.getattr,
        builtins.globals,
        builtins.locals,
        builtins.setattr,
        builtins.vars,
    }
)
_DYNAMIC_ATTRIBUTES = frozenset(
    {
        "__bases__",
        "__builtins__",
        "__closure__",
        "__code__",
        "__dict__",
        "__getattr__",
        "__getattribute__",
        "__globals__",
        "__mro__",
        "__subclasses__",
    }
)


def _instructions(code: CodeType) -> Iterator[dis.Instruction]:
    """Walk the actual nested code, not only the outer function's co_names."""
    yield from dis.get_instructions(code)
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            yield from _instructions(constant)


def _function_captures(function: FunctionType) -> dict[str, Any]:
    captures = inspect.getclosurevars(function)
    result = dict(captures.globals) | dict(captures.nonlocals) | dict(captures.builtins)
    # A nested lambda/comprehension can be the only use of a global module.
    # Resolve its references against the function's actual admitted namespace.
    for instruction in _instructions(function.__code__):
        if instruction.opname not in {"LOAD_GLOBAL", "LOAD_NAME"}:
            continue
        name = instruction.argval
        if name in function.__globals__:
            result[name] = function.__globals__[name]
        elif name in cast("Any", function).__builtins__:
            result[name] = cast("Any", function).__builtins__[name]
    return result


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
    # FunctionType and ordinary type have fixed runtime identity attributes;
    # getattr_static would return their descriptors, not the selected values.
    if value_type is FunctionType or value_type is type:
        module = value.__module__
        name = value.__qualname__
    else:
        module = inspect.getattr_static(value, "__module__", value_type.__module__)
        name = inspect.getattr_static(value, "__qualname__", None)
    if not isinstance(module, str):
        module = value_type.__module__
    root = module.split(".")[0]
    if root in sys.stdlib_module_names or root == "builtins":
        return None
    version = _version(root)
    if version is None:
        return None
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


def _data_field_getattr(
    function: FunctionType, name: str, captures: dict[str, Any]
) -> dict[str, Any] | None:
    """Bind finite public field selection on an unrebound runtime parameter.

    This binds code, the actual builtin and complete immutable field selectors.
    It does not infer the runtime target's type or descriptor/context identity.
    Captured module reflection still has no static member paths and is refused.
    """
    try:
        source = textwrap.dedent(inspect.getsource(function))
        tree = ast.parse(source)
        symbols = symtable.symtable(source, function.__code__.co_filename, "exec")
    except (OSError, TypeError, SyntaxError):
        return None
    definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function.__name__
    ]
    if len(definitions) != 1:
        return None
    definition = definitions[0]
    scopes = [
        scope
        for scope in symbols.get_children()
        if scope.get_type() == symtable.SymbolTableType.FUNCTION
        and scope.get_name() == definition.name
        and scope.get_lineno() == definition.lineno
    ]
    if len(scopes) != 1:
        return None
    parameters = {
        arg.arg
        for arg in (definition.args.posonlyargs + definition.args.args + definition.args.kwonlyargs)
    }
    nodes = list(ast.walk(definition))
    parents = {child: parent for parent in nodes for child in ast.iter_child_nodes(parent)}
    rebound = {
        node.id
        for node in nodes
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }
    # Python's own binding census includes exception names, nested definitions,
    # imports and match captures, whose AST names are strings rather than
    # Name(Store). Keep explicit deletion/comprehension checks as well.
    rebound.update(
        parameter
        for parameter in parameters
        if scopes[0].lookup(parameter).is_assigned() or scopes[0].lookup(parameter).is_imported()
    )
    root_captures = inspect.getclosurevars(function)
    root_bindings = root_captures.builtins | root_captures.globals | root_captures.nonlocals
    missing = object()

    def root_capture(identifier: str) -> Any:
        if identifier in rebound:
            return missing
        try:
            symbol = scopes[0].lookup(identifier)
        except KeyError:
            return missing
        if (
            symbol.is_parameter()
            or symbol.is_local()
            or symbol.is_assigned()
            or symbol.is_imported()
            or not (symbol.is_global() or symbol.is_free())
        ):
            return missing
        value = root_bindings.get(identifier, missing)
        # Recursive globals cannot stand in for a parameter/local or overwrite
        # this function's actual nonlocal binding. Ambiguous captures refuse.
        if value is missing or captures.get(identifier, missing) is not value:
            return missing
        return value

    if root_capture(name) is not builtins.getattr:
        return None
    fields: set[str] = set()
    targets: set[str] = set()
    uses = [
        node
        for node in nodes
        if isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)
    ]
    for use in uses:
        ancestor = parents.get(use)
        while ancestor is not None and ancestor is not definition:
            if isinstance(
                ancestor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
            ):
                return None
            ancestor = parents.get(ancestor)
        call = parents.get(use)
        if not (
            isinstance(call, ast.Call)
            and call.func is use
            and len(call.args) in {2, 3}
            and not call.keywords
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id in parameters - rebound
        ):
            return None
        target = call.args[0].id
        if len(call.args) == 3 and not (
            isinstance(call.args[2], ast.Name) and call.args[2].id == target
        ):
            return None
        selector = call.args[1]
        selected: Any = None
        if isinstance(selector, ast.Constant):
            selected = (selector.value,)
        elif isinstance(selector, ast.Name):
            captured = root_capture(selector.id)
            if isinstance(captured, str):
                selected = (captured,)
            else:
                for comprehension in nodes:
                    if not isinstance(
                        comprehension, (ast.DictComp, ast.ListComp, ast.SetComp, ast.GeneratorExp)
                    ):
                        continue
                    if call not in ast.walk(comprehension):
                        continue
                    if len(comprehension.generators) != 1:
                        return None
                    for generator in comprehension.generators:
                        if (
                            not generator.is_async
                            and isinstance(generator.target, ast.Name)
                            and generator.target.id == selector.id
                            and isinstance(generator.iter, ast.Name)
                            and generator.iter.id not in rebound
                        ):
                            selected = root_capture(generator.iter.id)
        if (
            not isinstance(selected, (tuple, frozenset))
            or not selected
            or not all(
                isinstance(field, str) and field.isidentifier() and not field.startswith("_")
                for field in selected
            )
        ):
            return None
        fields.update(selected)
        targets.add(target)
    if not uses:
        return None
    return {
        "symbol": "builtins.getattr",
        "distribution_version": sys.version,
        "selected_data_fields": sorted(fields),
        "runtime_parameters": sorted(targets),
        "runtime_target_type_and_internals": "not_bound",
    }


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
            or not cast("Any", value).__dataclass_params__.frozen
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
        if inspect.isbuiltin(value) and value in _DYNAMIC_BUILTINS:
            return _unavailable(value, strict)
        if inspect.isbuiltin(value) or (
            source == "unavailable" and str(value.__module__) == "builtins"
        ):
            version = _version(str(value.__module__).split(".")[0])
            if version is not None:
                return {"symbol": symbol, "distribution_version": version}
            return _unavailable(value, strict)
        if inspect.isfunction(value) and any(
            instruction.opname in {"IMPORT_NAME", "IMPORT_FROM"}
            or (instruction.opname == "LOAD_ATTR" and instruction.argval in _DYNAMIC_ATTRIBUTES)
            for instruction in _instructions(value.__code__)
        ):
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
                captures = _function_captures(value)
                result["captures"] = {
                    name: (
                        _module_capture(value, name, item, strict=strict, visiting=visiting)
                        if isinstance(item, ModuleType)
                        else (
                            _data_field_getattr(value, name, captures) or _unavailable(item, strict)
                        )
                        if item is builtins.getattr
                        else _project(item, strict=strict, visiting=visiting)
                    )
                    for name, item in sorted(captures.items())
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

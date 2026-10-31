"""Capture and recompute engine-observed identities for protected builtin producers.

The proof is intentionally limited to the selected in-process implementation. It
does not attest arbitrary transitive imports, dynamic plugins, the deployment image, or a
release signature. Those remain separate custody evidence.
"""

from __future__ import annotations

import dis
import hashlib
import importlib
import inspect
import marshal
import math
import os
import re
import sys
import time
import types
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from types import CodeType
from typing import Any
from uuid import uuid4

from polisyos.core.canon import CanonSpec, from_canonical_bytes, to_canonical_bytes
from polisyos.core.run.manifest import RunInvocationImplementationIdentity

_CANON = CanonSpec(forbid_floats=False, sort_keys=True, exclude_none=False)
_PROCESS_ID = os.getpid()
_PROCESS_NONCE = uuid4().hex


@dataclass(frozen=True)
class _BuiltinOwner:
    component_id: str
    node_type: type[Any]
    execute_function: types.FunctionType
    execute_code: CodeType
    execute_async_function: types.FunctionType | None
    execute_async_code: CodeType | None
    input_contract_sha256: str | None
    bind_function: types.FunctionType | None
    bind_code: CodeType | None
    spec_descriptor: property
    spec_accessor_code: CodeType
    spec_sha256: str
    module_source_sha256: str
    input_callback_owners: tuple[tuple[str, types.FunctionType | None, CodeType | None], ...] = ()
    input_contract_json: bytes | None = None
    input_definition_bindings: tuple[_DefinitionBinding, ...] = ()
    input_definition_sha256: str | None = None
    input_class_sha256: str | None = None


# Import-time references are held independently of the mutable registry. The
# executor imports this module before workflow execution and plugin discovery.
def _load_builtin_node_types() -> tuple[type[Any], ...]:
    from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
        RunTransportabilityNode,
    )
    from polisyos.scientist.nodes.builtins.decide.build_verified_policy_body import (
        BuildVerifiedPolicyBodyNode,
    )
    from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
        BuildVerifiedPolicyReportNode,
    )
    from polisyos.scientist.nodes.builtins.decide.evaluate_verified_policy_phase5 import (
        EvaluateVerifiedPolicyPhase5Node,
    )
    from polisyos.scientist.nodes.builtins.decide.select_policy_candidate import (
        SelectPolicyCandidateNode,
    )
    from polisyos.scientist.nodes.builtins.governance.run_governance import (
        RunGovernanceNode,
    )
    from polisyos.scientist.nodes.builtins.planning.run_evaluator import RunEvaluatorNode
    from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
        RunHierarchicalPolicySearchNode,
    )

    return (
        BuildVerifiedPolicyBodyNode,
        BuildVerifiedPolicyReportNode,
        EvaluateVerifiedPolicyPhase5Node,
        SelectPolicyCandidateNode,
        RunGovernanceNode,
        RunTransportabilityNode,
        RunHierarchicalPolicySearchNode,
        RunEvaluatorNode,
    )


(
    _BuildVerifiedPolicyBodyNode,
    _BuildVerifiedPolicyReportNode,
    _EvaluateVerifiedPolicyPhase5Node,
    _SelectPolicyCandidateNode,
    _RunGovernanceNode,
    _RunTransportabilityNode,
    _RunHierarchicalPolicySearchNode,
    _RunEvaluatorNode,
) = _load_builtin_node_types()


def _function_from_descriptor(value: object) -> types.FunctionType | None:
    if isinstance(value, (staticmethod, classmethod)):
        value = value.__func__
    if isinstance(value, property):
        value = value.fget
    return value if isinstance(value, types.FunctionType) else None


def _digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest_value(value: object) -> str:
    return _digest_bytes(to_canonical_bytes(value, _CANON))


def _normalize_code_constant(value: object) -> object:
    if isinstance(value, CodeType):
        return _normalize_code_object(value)
    if isinstance(value, tuple):
        return tuple(_normalize_code_constant(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(_normalize_code_constant(item) for item in value)
    return value


def _normalize_code_object(code: CodeType) -> CodeType:
    """Remove interpreter-adaptive code state before hashing executable logic."""
    return code.replace(
        co_code=code.co_code,
        co_consts=tuple(_normalize_code_constant(item) for item in code.co_consts),
    )


def _code_sha256(function: types.FunctionType) -> str:
    return _digest_bytes(marshal.dumps(_normalize_code_object(function.__code__)))


def _callable_code_token(function: types.FunctionType) -> str:
    """Bind both callable and immutable code-object identity in this process."""
    return f"{id(function):x}:{id(function.__code__):x}"


def _module_source_digest(node_type: type[Any]) -> str:
    source = inspect.getsourcefile(node_type)
    if source is None:
        raise ValueError("engine_component_source_not_established")
    return _digest_bytes(Path(source).read_bytes())


def _input_callback_owners(
    node_type: type[Any],
) -> tuple[tuple[str, types.FunctionType | None, CodeType | None], ...]:
    callbacks = []
    for name in ("prepare_cache_input", "validate_cache_hit"):
        function = _function_from_descriptor(inspect.getattr_static(node_type, name, None))
        callbacks.append((name, function, function.__code__ if function is not None else None))
    return tuple(callbacks)


@dataclass(frozen=True)
class _DefinitionBinding:
    """One actual definition binding read by the selected producer/source owners."""

    namespace: dict[str, Any] | types.ModuleType
    name: str
    value_sha256: str

    def current(self) -> object:
        if isinstance(self.namespace, types.ModuleType):
            if sys.modules.get(self.namespace.__name__) is not self.namespace:
                raise ValueError("engine_component_dependency_module_changed")
            return getattr(self.namespace, self.name)
        return self.namespace[self.name]


def _wrapped_python_definition(value: object) -> types.FunctionType | None:
    """Read an actual decorator-held Python definition without calling it."""
    wrapped = inspect.getattr_static(value, "__wrapped__", None)
    return wrapped if isinstance(wrapped, types.FunctionType) else None


def _definition_projection(
    value: object,
    files: dict[str, str],
    active: set[int] | None = None,
    source_cache: dict[str, str] | None = None,
) -> object:
    """Bind code, DTO definitions and frozen owner profiles without invoking work."""
    active = set() if active is None else active
    source_cache = {} if source_cache is None else source_cache
    if id(value) in active:
        return ["cycle", f"{id(value):x}"]
    active = {*active, id(value)}
    if value is None or type(value) in (str, int, float, bool):
        return value
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    if isinstance(value, types.ModuleType):
        return ["module", value.__name__, f"{id(value):x}"]
    if isinstance(value, types.FunctionType):
        source = inspect.getsourcefile(value)
        if source is not None and Path(source).is_file() and source not in files:
            if source not in source_cache:
                source_cache[source] = _digest_bytes(Path(source).read_bytes())
            files[source] = source_cache[source]
        return [
            "function",
            _callable_code_token(value),
            _code_sha256(value),
            _definition_projection(value.__defaults__, files, active, source_cache),
            _definition_projection(value.__kwdefaults__, files, active, source_cache),
            [
                _definition_projection(cell.cell_contents, files, active, source_cache)
                for cell in value.__closure__ or ()
            ],
        ]
    if isinstance(value, type):
        functions = {}
        constants = {}
        for name, member in vars(value).items():
            function = _function_from_descriptor(member)
            if function is not None:
                functions[name] = _definition_projection(function, files, active, source_cache)
            elif not name.startswith("_") and type(member) in (
                str,
                int,
                float,
                bool,
                tuple,
                frozenset,
            ):
                constants[name] = _definition_projection(member, files, active, source_cache)
        compiled = {
            name: f"{id(vars(value)[name]):x}"
            for name in ("__pydantic_validator__", "__pydantic_serializer__")
            if name in vars(value)
        }
        return [
            "class",
            value.__module__,
            value.__qualname__,
            f"{id(value):x}",
            functions,
            constants,
            compiled,
        ]
    wrapped = _wrapped_python_definition(value)
    if wrapped is not None:
        return [
            "wrapped_callable",
            type(value).__module__,
            type(value).__qualname__,
            f"{id(value):x}",
            _definition_projection(wrapped, files, active, source_cache),
        ]
    from pydantic import BaseModel

    if isinstance(value, BaseModel):
        return ["model", f"{id(type(value)):x}", value.model_dump(mode="json")]
    if is_dataclass(value) and not isinstance(value, type):
        return [
            "owner",
            f"{id(value):x}",
            {
                field.name: _definition_projection(
                    getattr(value, field.name), files, active, source_cache
                )
                for field in fields(value)
            },
        ]
    if isinstance(value, dict):
        return {
            str(key): _definition_projection(item, files, active, source_cache)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list, frozenset)):
        return [_definition_projection(item, files, active, source_cache) for item in value]
    return ["object", f"{id(value):x}"]


def _definition_sha256(value: object, source_cache: dict[str, str] | None = None) -> str:
    files: dict[str, str] = {}
    projection = _definition_projection(value, files, source_cache=source_cache)
    return _digest_value({"definition": projection, "sources": files})


def _definition_value(value: object) -> bool:
    from pydantic import BaseModel

    return (
        value is None
        or type(value) in (str, int, float, bool, bytes, tuple, frozenset)
        or isinstance(value, (types.FunctionType, types.ModuleType, type, BaseModel))
        or _wrapped_python_definition(value) is not None
        or (
            is_dataclass(value)
            and getattr(vars(type(value)).get("__dataclass_params__"), "frozen", False) is True
        )
    )


def _source_owner_function(function: types.FunctionType, producer_module: str) -> bool:
    module = function.__module__
    return (
        module == producer_module
        or (
            module.startswith("polisyos.scientist.")
            and not module.startswith(
                ("polisyos.scientist.orchestration.engine.", "polisyos.scientist.replay.")
            )
        )
        or module in {"polisyos.ir.trinity.loaders", "polisyos.ir.analytics.causal"}
    )


def _input_definition_bindings(node_type: type[Any]) -> tuple[_DefinitionBinding, ...]:
    """Follow referenced domain helper definitions to existing generic owner seams.

    Core/IR JSON validators, artifact stores, Engine input and replay evidence
    verification owners are terminal owners. This binds their called entrypoints, not arbitrary transitive Python,
    external libraries, process memory or a deployment image.
    """
    roots = [
        function
        for name in (
            "spec",
            "bind",
            "execute",
            "execute_async",
            "prepare_cache_input",
            "validate_cache_hit",
        )
        if (function := _function_from_descriptor(inspect.getattr_static(node_type, name, None)))
        is not None
    ]
    pending = list(roots)
    visited: set[int] = set()
    bindings: dict[tuple[int, str], _DefinitionBinding] = {}

    def remember(namespace: dict[str, Any] | types.ModuleType, name: str, value: object) -> None:
        if not _definition_value(value):
            return
        key = (id(namespace), name)
        if key not in bindings:
            from pydantic import BaseModel

            if isinstance(value, type) and value is not BaseModel and issubclass(value, BaseModel):
                # Compile a deferred DTO once before holding its validator and
                # serializer identities. Revalidation never rebuilds a changed
                # definition or accepts a replacement compiled entrypoint.
                value.model_rebuild()
            bindings[key] = _DefinitionBinding(namespace, name, _definition_sha256(value))
            if isinstance(value, types.FunctionType) and _source_owner_function(
                value, node_type.__module__
            ):
                pending.append(value)
            elif (wrapped := _wrapped_python_definition(value)) is not None:
                if _source_owner_function(wrapped, node_type.__module__):
                    pending.append(wrapped)
            elif isinstance(value, type):
                # A referenced source-owned class executes through its methods;
                # pin those methods' real helper/global bindings by the same
                # traversal as functions, not only their class/source marker.
                for descriptor in vars(value).values():
                    function = _function_from_descriptor(descriptor)
                    if function is not None and _source_owner_function(
                        function, node_type.__module__
                    ):
                        pending.append(function)

    while pending:
        function = pending.pop()
        if id(function) in visited:
            continue
        visited.add(id(function))
        # Context-manager/decorator closures also execute held source functions;
        # their globals must be reconciled by the same actual-definition walk.
        for cell in function.__closure__ or ():
            child = cell.cell_contents
            if isinstance(child, types.FunctionType) and _source_owner_function(
                child, node_type.__module__
            ):
                pending.append(child)
        codes = [function.__code__]
        while codes:
            code = codes.pop()
            codes.extend(value for value in code.co_consts if isinstance(value, CodeType))
            imported = None
            for instruction in dis.get_instructions(code):
                name = instruction.argval
                if (
                    instruction.opname in {"LOAD_GLOBAL", "LOAD_NAME"}
                    and name in function.__globals__
                ):
                    value = function.__globals__[name]
                    remember(function.__globals__, name, value)
                    if isinstance(value, types.ModuleType):
                        for member in code.co_names:
                            if member in vars(value):
                                remember(value, member, vars(value)[member])
                elif instruction.opname == "IMPORT_NAME" and isinstance(name, str) and name:
                    imported = importlib.import_module(name)
                elif (
                    instruction.opname == "IMPORT_FROM"
                    and imported is not None
                    and isinstance(name, str)
                ):
                    remember(imported, name, getattr(imported, name))
    return tuple(bindings.values())


def _require_owner_definition(
    owner: _BuiltinOwner,
) -> tuple[types.FunctionType, types.FunctionType | None, types.FunctionType]:
    node_type = owner.node_type
    execute_function = _function_from_descriptor(inspect.getattr_static(node_type, "execute", None))
    bind_function = _function_from_descriptor(inspect.getattr_static(node_type, "bind", None))
    spec_descriptor = inspect.getattr_static(node_type, "spec", None)
    spec_function = _function_from_descriptor(spec_descriptor)
    if spec_descriptor is not owner.spec_descriptor or spec_function is None:
        raise ValueError("engine_component_spec_descriptor_changed")
    if (
        execute_function is not owner.execute_function
        or execute_function.__code__ is not owner.execute_code
        or bind_function is not owner.bind_function
        or (bind_function.__code__ if bind_function is not None else None) is not owner.bind_code
        or spec_function.__code__ is not owner.spec_accessor_code
    ):
        raise ValueError("engine_component_callable_changed")
    execute_async = _function_from_descriptor(
        inspect.getattr_static(node_type, "execute_async", None)
    )
    if (
        execute_async is not owner.execute_async_function
        or (execute_async.__code__ if execute_async is not None else None)
        is not owner.execute_async_code
    ):
        raise ValueError("engine_component_async_callable_changed")
    if _module_source_digest(node_type) != owner.module_source_sha256:
        raise ValueError("engine_component_source_changed")
    if owner.input_class_sha256 is not None:
        for name, function, code in owner.input_callback_owners:
            current = _function_from_descriptor(inspect.getattr_static(node_type, name, None))
            if (
                current is not function
                or (current.__code__ if current is not None else None) is not code
            ):
                raise ValueError("engine_component_input_callback_changed")
        # One check observes each definition/source once. The next operation
        # starts fresh; no successful identity survives a later source/helper
        # change through a process-global or across-callback cache.
        source_cache: dict[str, str] = {}
        definition_cache: dict[int, str] = {}

        def observed_definition(value: object) -> str:
            key = id(value)
            if key not in definition_cache:
                definition_cache[key] = _definition_sha256(value, source_cache)
            return definition_cache[key]

        if observed_definition(node_type) != owner.input_class_sha256:
            raise ValueError("engine_component_input_class_changed")
        for binding in owner.input_definition_bindings:
            if observed_definition(binding.current()) != binding.value_sha256:
                raise ValueError("engine_component_input_dependency_changed")
    return execute_function, bind_function, spec_function


def _require_input_bind_keys(owner: _BuiltinOwner, params: dict[str, Any]) -> None:
    if owner.input_contract_json is not None:
        from polisyos.scientist.orchestration.engine.protocol import NodeInputContract

        contract = NodeInputContract.model_validate_json(owner.input_contract_json)
        if (
            contract.component_id != owner.component_id
            or _digest_value(contract.model_dump(mode="json")) != owner.input_contract_sha256
            or set(params) - set(contract.bind_param_keys)
        ):
            raise ValueError("engine_component_input_bind_params_invalid")


def _require_input_definition(node: object, params: dict[str, Any]) -> _BuiltinOwner | None:
    owner = next(
        (
            value
            for value in _OWNERS.values()
            if value.node_type is type(node) and value.input_contract_sha256 is not None
        ),
        None,
    )
    if owner is not None:
        _require_owner_definition(owner)
        _require_input_bind_keys(owner, params)
    return owner


def _preflight_registered_input(
    node: object, component_id: str, params: dict[str, Any]
) -> bytes | None:
    owner = _OWNERS.get(component_id)
    by_type = _require_input_definition(node, params)
    if by_type is None and (owner is None or owner.input_contract_sha256 is None):
        return None
    if owner is None or owner is not by_type or type(node) is not owner.node_type:
        raise ValueError("engine_component_input_registration_changed")
    if capture_engine_component_identity(node, component_id, {}) is None:
        raise ValueError("engine_component_input_registration_changed")
    return owner.input_contract_json


def _owner(node_type: type[Any]) -> _BuiltinOwner:
    instance = node_type()
    spec_descriptor = inspect.getattr_static(node_type, "spec", None)
    execute_function = _function_from_descriptor(inspect.getattr_static(node_type, "execute", None))
    execute_async_function = _function_from_descriptor(
        inspect.getattr_static(node_type, "execute_async", None)
    )
    bind_function = _function_from_descriptor(inspect.getattr_static(node_type, "bind", None))
    if not isinstance(spec_descriptor, property) or execute_function is None:
        raise TypeError("engine_component_owner_contract_incomplete")
    spec_function = _function_from_descriptor(spec_descriptor)
    if spec_function is None:
        raise TypeError("engine_component_spec_accessor_missing")
    spec = instance.spec
    spec_sha256 = _digest_value(spec.model_dump(mode="json"))
    input_contract = getattr(spec, "input_contract", None)
    # The fixed C source-currentness roles include ordinary report/governance
    # nodes. Their helper ownership must not depend on selecting a physical port.
    bind_definitions = input_contract is not None or node_type in (
        _BuildVerifiedPolicyReportNode,
        _RunGovernanceNode,
    )
    definition_bindings = _input_definition_bindings(node_type) if bind_definitions else ()
    return _BuiltinOwner(
        component_id=str(spec.metadata.component_id),
        node_type=node_type,
        execute_function=execute_function,
        execute_code=execute_function.__code__,
        execute_async_function=execute_async_function,
        execute_async_code=(
            execute_async_function.__code__ if execute_async_function is not None else None
        ),
        input_contract_sha256=(
            _digest_value(spec.input_contract.model_dump(mode="json"))
            if hasattr(spec, "input_contract")
            else None
        ),
        bind_function=bind_function,
        bind_code=(bind_function.__code__ if bind_function is not None else None),
        spec_descriptor=spec_descriptor,
        spec_accessor_code=spec_function.__code__,
        spec_sha256=spec_sha256,
        module_source_sha256=_module_source_digest(node_type),
        input_callback_owners=_input_callback_owners(node_type),
        input_contract_json=(
            to_canonical_bytes(input_contract.model_dump(mode="json"), _CANON)
            if input_contract is not None
            else None
        ),
        input_definition_bindings=definition_bindings,
        input_definition_sha256=(
            _digest_value(
                {
                    "class": _definition_sha256(node_type),
                    "bindings": [
                        (
                            binding.namespace.__name__
                            if isinstance(binding.namespace, types.ModuleType)
                            else binding.namespace.get("__name__"),
                            binding.name,
                            binding.value_sha256,
                        )
                        for binding in definition_bindings
                    ],
                }
            )
            if bind_definitions
            else None
        ),
        input_class_sha256=(_definition_sha256(node_type) if bind_definitions else None),
    )


_OWNERS = {
    owner.component_id: owner
    for owner in (
        _owner(_BuildVerifiedPolicyBodyNode),
        _owner(_BuildVerifiedPolicyReportNode),
        _owner(_EvaluateVerifiedPolicyPhase5Node),
        _owner(_SelectPolicyCandidateNode),
        _owner(_RunGovernanceNode),
        _owner(_RunTransportabilityNode),
        _owner(_RunHierarchicalPolicySearchNode),
        _owner(_RunEvaluatorNode),
    )
}


def _bound_owner_instance(owner: _BuiltinOwner, params: dict[str, Any]) -> Any:
    node = owner.node_type()
    if params:
        binder = getattr(node, "bind", None)
        if callable(binder):
            bound = binder(params)
            if bound is not None:
                node = bound
    return node


def _node_attributes_sha256(node: object) -> str:
    attributes = getattr(node, "__dict__", None)
    if not isinstance(attributes, dict):
        raise ValueError("engine_component_bound_state_not_established")
    return _digest_value(attributes)


def _identity_for(
    owner: _BuiltinOwner,
    node: object,
    params: dict[str, Any],
) -> RunInvocationImplementationIdentity:
    node_type = owner.node_type
    execute_function, bind_function, spec_function = _require_owner_definition(owner)
    _require_input_bind_keys(owner, params)
    spec = spec_function(node)
    spec_sha256 = _digest_value(spec.model_dump(mode="json"))
    if spec_sha256 != owner.spec_sha256:
        raise ValueError("engine_component_spec_changed")
    module_source_sha256 = _module_source_digest(node_type)
    if module_source_sha256 != owner.module_source_sha256:
        raise ValueError("engine_component_source_changed")
    return RunInvocationImplementationIdentity(
        component_id=owner.component_id,
        owner_module=node_type.__module__,
        owner_qualname=node_type.__qualname__,
        runtime_class_token=f"{id(node_type):x}",
        runtime_process_id=_PROCESS_ID,
        runtime_process_nonce=_PROCESS_NONCE,
        runtime_execute_token=_callable_code_token(execute_function),
        runtime_bind_token=(
            _callable_code_token(bind_function) if bind_function is not None else None
        ),
        runtime_spec_accessor_token=_callable_code_token(spec_function),
        module_source_sha256=owner.module_source_sha256,
        execute_code_sha256=_code_sha256(execute_function),
        bind_code_sha256=(_code_sha256(bind_function) if bind_function is not None else None),
        spec_accessor_code_sha256=_code_sha256(spec_function),
        node_spec_sha256=spec_sha256,
        bound_state_sha256=_node_attributes_sha256(node),
        dispatch_params_sha256=_digest_value(params),
    )


def capture_engine_component_identity(
    node: object, component_id: str, params: dict[str, Any]
) -> RunInvocationImplementationIdentity | None:
    """Capture an exact trusted builtin implementation before an engine attempt.

    Unknown components and changed implementations return no identity. The attempt
    may still execute as candidate work, but consumers cannot treat it as a current
    protected producer.
    """
    owner = _OWNERS.get(component_id)
    if owner is None:
        return None
    node_type = owner.node_type
    if type(node) is not node_type:
        return None
    try:
        _execute_function, _bind_function, spec_function = _require_owner_definition(owner)
        _require_input_bind_keys(owner, params)
        expected = _bound_owner_instance(owner, params)
        if type(expected) is not node_type or vars(expected) != vars(node):
            return None
        if spec_function(node) is not spec_function(expected):
            return None
        return _identity_for(owner, node, params)
    except Exception:
        return None


def matches_engine_component_identity(
    identity: RunInvocationImplementationIdentity | None,
    component_id: str,
    params: dict[str, Any],
) -> bool:
    """Recompute the admitted identity against the import-time builtin owner.

    The volatile object/function tokens deliberately make this an in-process
    selected-implementation claim. A fresh process without those live objects keeps
    the authority result not established; it does not infer deployment provenance.
    """
    owner = _OWNERS.get(component_id)
    if (
        owner is None
        or identity is None
        or identity.runtime_process_id != _PROCESS_ID
        or identity.runtime_process_nonce != _PROCESS_NONCE
    ):
        return False
    try:
        _require_owner_definition(owner)
        _require_input_bind_keys(owner, params)
        expected = _bound_owner_instance(owner, params)
        return identity == _identity_for(owner, expected, params)
    except Exception:
        return False


def matches_spawned_timeout_worker_component_identity(
    ctx: object,
    identity: RunInvocationImplementationIdentity,
    component_id: str,
    node_alias: str,
    params: dict[str, Any],
) -> bool:
    """Recompute the exact selected builtin against a live spawned attempt.

    Runtime process/object tokens remain part of the persisted parent identity;
    this child verifier compares its stable executable/spec/binding fields only
    after independently resolving that identity from the current run-owned
    attempt and the typed parent-dispatch binding.
    """
    try:
        from polisyos.core.canon import from_canonical_bytes
        from polisyos.core.run.worker_lifecycle import (
            WorkerDispatchBinding,
            WorkerRunView,
        )
        from polisyos.scientist.orchestration.engine.context import (
            ExecutionContext,
            _EngineInvocationBinding,
        )
        from polisyos.scientist.orchestration.engine.retry import (
            _AttemptRunFacade,
            _EngineNodeRunView,
            _resolve_exact_worker_run_view,
        )
        from polisyos.scientist.orchestration.engine.runner.serialization import (
            _TIMEOUT_CONTEXT_ENGINE_INVOCATION_NODE_ID,
            _timeout_worker_params_match,
        )
        from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

        if (
            type(ctx) is not ExecutionContext
            or type(identity) is not RunInvocationImplementationIdentity
            or type(component_id) is not str
            or component_id != _TIMEOUT_CONTEXT_ENGINE_INVOCATION_NODE_ID
            or type(node_alias) is not str
            or node_alias != "run_transportability"
            or type(params) is not dict
        ):
            return False

        engine_binding = ctx._engine_invocation
        if type(engine_binding) is not _EngineInvocationBinding:
            return False
        run_view = ctx.run
        if type(run_view) is WorkerRunView:
            worker_run = run_view
        elif type(run_view) is _EngineNodeRunView:
            current = object.__getattribute__(run_view, "_EngineNodeRunView__target")
            if type(current) is not _AttemptRunFacade:
                return False
            resolved_worker_run = _resolve_exact_worker_run_view(current)
            if resolved_worker_run is None:
                return False
            worker_run = resolved_worker_run
        else:
            return False

        effective_timeout_s = engine_binding.effective_timeout_s
        supervisor_deadline = engine_binding.supervisor_deadline_monotonic
        if (
            type(effective_timeout_s) is not float
            or not math.isfinite(effective_timeout_s)
            or effective_timeout_s <= 0.0
            or type(supervisor_deadline) is not float
            or not math.isfinite(supervisor_deadline)
        ):
            return False
        dispatch_binding = run_view.dispatch_binding
        if (
            type(dispatch_binding) is not WorkerDispatchBinding
            or worker_run.run_manifest.run_id != engine_binding.run_id
        ):
            return False
        if (
            dispatch_binding.run_id != engine_binding.run_id
            or dispatch_binding.run_id != ctx.run.run_manifest.run_id
            or re.fullmatch(r"[0-9a-f]{64}", dispatch_binding.invocation_id) is None
            or re.fullmatch(r"[0-9a-f]{64}", dispatch_binding.dispatch_sha256) is None
            or engine_binding.run_id != ctx.run.run_manifest.run_id
            or engine_binding.basis_ref.manifest_profile_sha256 is None
        ):
            return False

        attempts = ctx.run.read_runtime_invocation_attempts()
        matches = [
            item
            for item in attempts
            if item.basis.attempt_id == engine_binding.attempt_id
            and item.basis_ref == engine_binding.basis_ref
        ]
        if len(matches) != 1:
            return False
        attempt = matches[0]
        basis = attempt.basis
        if (
            attempt.outcome is not None
            or basis.run_id != engine_binding.run_id
            or basis.node_alias != node_alias
            or basis.component_id != component_id
            or basis.implementation_identity is None
            or type(basis.implementation_identity) is not RunInvocationImplementationIdentity
            or basis.implementation_identity != identity
            or basis.workflow_spec_ref.manifest_profile_sha256 is None
            or basis.input_state_ref.manifest_profile_sha256 is None
        ):
            return False

        workflow = WorkflowSpec.model_validate(
            from_canonical_bytes(ctx.store.get_bytes(basis.workflow_spec_ref))
        )
        selected_nodes = [item for item in workflow.nodes if item.alias == node_alias]
        if len(selected_nodes) != 1:
            return False
        selected_node = selected_nodes[0]
        if (
            str(selected_node.node_id) != component_id
            or selected_node.timeout_s is None
            or not math.isfinite(selected_node.timeout_s)
            or selected_node.timeout_s < effective_timeout_s
            or not _timeout_worker_params_match(selected_node.params, params)
        ):
            return False

        owner = _OWNERS.get(component_id)
        if owner is None or owner.node_type is not _RunTransportabilityNode:
            return False
        expected = _bound_owner_instance(owner, params)
        if type(expected) is not owner.node_type:
            return False
        recomputed = _identity_for(owner, expected, params)
        stable_fields = (
            "schema_version",
            "scope",
            "component_id",
            "owner_module",
            "owner_qualname",
            "module_source_sha256",
            "execute_code_sha256",
            "bind_code_sha256",
            "spec_accessor_code_sha256",
            "node_spec_sha256",
            "bound_state_sha256",
            "dispatch_params_sha256",
        )
        return all(getattr(identity, name) == getattr(recomputed, name) for name in stable_fields)
    except Exception:
        return False


__all__ = [
    "capture_engine_component_identity",
    "matches_engine_component_identity",
    "matches_spawned_timeout_worker_component_identity",
]


@dataclass(frozen=True)
class _ConfiguredComponentIdentityOwner:
    """Retain the actual authorized bind result and selected callable in this process.

    This is implementation evidence, not an issuer or a grant. The appointed
    admission owner must authorize reconstruction before calling the capture
    function. No closure/global/transitive or hostile-concurrency claim follows.
    """

    registered_node: object
    bound_node: object
    registered_state_sha256: str
    bound_state_sha256: str
    params_sha256: str
    params_json: bytes
    defaults_sha256: str
    implementation: _BuiltinOwner
    bound_execute: types.MethodType

    def reconcile(
        self,
        registered_node: object,
        bound_node: object,
        params: dict[str, Any],
    ) -> RunInvocationImplementationIdentity:
        """Reconcile only the actual retained bind result and its held method."""
        if registered_node is not self.registered_node:
            raise ValueError("child_component_registration_changed")
        if bound_node is not self.bound_node:
            raise ValueError("child_component_bound_object_changed")
        if _node_attributes_sha256(registered_node) != self.registered_state_sha256:
            raise ValueError("child_component_registered_state_changed")
        if _digest_value(params) != self.params_sha256:
            raise ValueError("child_component_dispatch_params_changed")
        if type(bound_node) is not self.implementation.node_type:
            raise ValueError("child_component_runtime_type_changed")
        _require_actual_configured_dispatch(bound_node, self.implementation)
        identity = _identity_for(self.implementation, bound_node, params)
        if identity.bound_state_sha256 != self.bound_state_sha256:
            raise ValueError("child_component_bound_state_changed")
        function = self.bound_execute.__func__
        if _digest_value((function.__defaults__, function.__kwdefaults__)) != self.defaults_sha256:
            raise ValueError("child_component_callable_defaults_changed")
        return identity

    def execute(self, ctx: Any, state: Any) -> Any:
        """Use the actual held checked bound method, without a fresh attribute lookup."""
        params = from_canonical_bytes(self.params_json)
        if not isinstance(params, dict):
            raise ValueError("child_component_owned_params_invalid")
        self.reconcile(self.registered_node, self.bound_node, params)
        return _invoke_configured_dispatch(self, ctx, state)


def _invoke_configured_dispatch(
    owner: _ConfiguredComponentIdentityOwner,
    ctx: Any,
    state: Any,
) -> Any:
    """Invoke the original bound target; do not clone code or look execute up again."""
    return owner.bound_execute(ctx, state)


def _require_actual_configured_dispatch(node: object, owner: _BuiltinOwner) -> types.MethodType:
    """Reconcile attribute lookup with the actual class descriptor being captured."""
    execute = getattr(node, "execute", None)
    if (
        not isinstance(execute, types.MethodType)
        or execute.__self__ is not node
        or execute.__func__ is not owner.execute_function
    ):
        raise ValueError("child_component_actual_dispatch_changed")
    actual_spec = getattr(node, "spec", None)
    spec_function = _function_from_descriptor(owner.spec_descriptor)
    if spec_function is None or actual_spec is None:
        raise ValueError("child_component_actual_spec_missing")
    if _digest_value(actual_spec.model_dump(mode="json")) != _digest_value(
        spec_function(node).model_dump(mode="json")
    ):
        raise ValueError("child_component_actual_spec_changed")
    return execute


def _capture_configured_component_owner(
    registered_node: object,
    params: dict[str, Any],
) -> _ConfiguredComponentIdentityOwner:
    """Perform the admitted real bind and capture its exact produced implementation.

    Call only after the engine owner grants this member reconstruction. This
    function neither appoints that owner nor authorizes a component. It takes no
    independently supplied bound result: relation to the registration/parameters
    is recomputed by invoking the held registered binder. The resulting selected
    method is held and used by managed dispatch. This trusted local profile does
    not isolate mutable globals, closures, collaborators or concurrent Python.
    """
    from polisyos.scientist.orchestration.engine.protocol import NodeSpec

    params_json = to_canonical_bytes(params, _CANON)
    bind_params = from_canonical_bytes(params_json)
    if not isinstance(bind_params, dict):
        raise TypeError("child_component_params_invalid")
    registered_state = _node_attributes_sha256(registered_node)
    node_type = type(registered_node)
    bind_function = _function_from_descriptor(inspect.getattr_static(node_type, "bind", None))
    binder = getattr(registered_node, "bind", None)
    if bind_function is not None and (
        not isinstance(binder, types.MethodType)
        or binder.__self__ is not registered_node
        or binder.__func__ is not bind_function
    ):
        raise ValueError("child_component_actual_bind_changed")
    if bind_params and bind_function is not None:
        if not callable(binder):
            raise ValueError("child_component_actual_bind_changed")
        produced = binder(bind_params)
        bound_node = registered_node if produced is None else produced
    else:
        bound_node = registered_node
    if _digest_value(bind_params) != _digest_value(params):
        raise ValueError("child_component_bind_mutated_params")
    if _node_attributes_sha256(registered_node) != registered_state:
        raise ValueError("child_component_bind_mutated_registration")
    if type(bound_node) is not node_type:
        raise ValueError("child_component_binding_type_changed")
    spec_descriptor = inspect.getattr_static(node_type, "spec", None)
    execute_function = _function_from_descriptor(inspect.getattr_static(node_type, "execute", None))
    execute_async_function = _function_from_descriptor(
        inspect.getattr_static(node_type, "execute_async", None)
    )
    spec_function = _function_from_descriptor(spec_descriptor)
    if (
        not isinstance(spec_descriptor, property)
        or execute_function is None
        or spec_function is None
    ):
        raise ValueError("child_component_implementation_not_established")
    spec = spec_function(bound_node)
    if not isinstance(spec, NodeSpec):
        raise TypeError("child_component_spec_invalid")
    input_contract = getattr(spec, "input_contract", None)
    definition_bindings = (
        _input_definition_bindings(node_type) if input_contract is not None else ()
    )
    owner = _BuiltinOwner(
        component_id=str(spec.metadata.component_id),
        node_type=node_type,
        execute_function=execute_function,
        execute_code=execute_function.__code__,
        execute_async_function=execute_async_function,
        execute_async_code=(
            execute_async_function.__code__ if execute_async_function is not None else None
        ),
        input_contract_sha256=(
            _digest_value(spec.input_contract.model_dump(mode="json"))
            if hasattr(spec, "input_contract")
            else None
        ),
        bind_function=bind_function,
        bind_code=bind_function.__code__ if bind_function is not None else None,
        spec_descriptor=spec_descriptor,
        spec_accessor_code=spec_function.__code__,
        spec_sha256=_digest_value(spec.model_dump(mode="json")),
        module_source_sha256=_module_source_digest(node_type),
        input_callback_owners=_input_callback_owners(node_type),
        input_contract_json=(
            to_canonical_bytes(input_contract.model_dump(mode="json"), _CANON)
            if input_contract is not None
            else None
        ),
        input_definition_bindings=definition_bindings,
        input_definition_sha256=(
            _digest_value(
                {
                    "class": _definition_sha256(node_type),
                    "bindings": [
                        (
                            binding.namespace.__name__
                            if isinstance(binding.namespace, types.ModuleType)
                            else binding.namespace.get("__name__"),
                            binding.name,
                            binding.value_sha256,
                        )
                        for binding in definition_bindings
                    ],
                }
            )
            if input_contract is not None
            else None
        ),
        input_class_sha256=(_definition_sha256(node_type) if input_contract is not None else None),
    )
    actual_execute = _require_actual_configured_dispatch(bound_node, owner)
    captured = _ConfiguredComponentIdentityOwner(
        registered_node=registered_node,
        bound_node=bound_node,
        registered_state_sha256=registered_state,
        bound_state_sha256=_node_attributes_sha256(bound_node),
        params_sha256=_digest_value(params),
        params_json=params_json,
        defaults_sha256=_digest_value(
            (execute_function.__defaults__, execute_function.__kwdefaults__)
        ),
        implementation=owner,
        bound_execute=actual_execute,
    )
    captured.reconcile(registered_node, bound_node, params)
    return captured

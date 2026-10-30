"""Capture and recompute engine-observed identities for protected builtin producers.

The proof is intentionally limited to the selected in-process implementation. It
does not attest transitive imports, dynamic plugins, the deployment image, or a
release signature. Those remain separate custody evidence.
"""

from __future__ import annotations

import hashlib
import inspect
import marshal
import math
import os
import re
import time
import types
from dataclasses import dataclass
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
    bind_function: types.FunctionType | None
    bind_code: CodeType | None
    spec_descriptor: property
    spec_accessor_code: CodeType
    spec_sha256: str
    module_source_sha256: str


# Import-time references are held independently of the mutable registry. The
# executor imports this module before workflow execution and plugin discovery.
def _load_builtin_node_types() -> tuple[type[Any], type[Any], type[Any], type[Any]]:
    from polisyos.scientist.nodes.builtins.causal.resolve_transport import (
        RunTransportabilityNode,
    )
    from polisyos.scientist.nodes.builtins.decide.build_verified_policy_report import (
        BuildVerifiedPolicyReportNode,
    )
    from polisyos.scientist.nodes.builtins.governance.run_governance import (
        RunGovernanceNode,
    )
    from polisyos.scientist.nodes.builtins.planning.run_hierarchical_policy_search import (
        RunHierarchicalPolicySearchNode,
    )

    return (
        BuildVerifiedPolicyReportNode,
        RunGovernanceNode,
        RunTransportabilityNode,
        RunHierarchicalPolicySearchNode,
    )


(
    _BuildVerifiedPolicyReportNode,
    _RunGovernanceNode,
    _RunTransportabilityNode,
    _RunHierarchicalPolicySearchNode,
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


def _owner(node_type: type[Any]) -> _BuiltinOwner:
    instance = node_type()
    spec_descriptor = inspect.getattr_static(node_type, "spec", None)
    execute_function = _function_from_descriptor(inspect.getattr_static(node_type, "execute", None))
    bind_function = _function_from_descriptor(inspect.getattr_static(node_type, "bind", None))
    if not isinstance(spec_descriptor, property) or execute_function is None:
        raise TypeError("engine_component_owner_contract_incomplete")
    spec_function = _function_from_descriptor(spec_descriptor)
    if spec_function is None:
        raise TypeError("engine_component_spec_accessor_missing")
    spec = instance.spec
    spec_sha256 = _digest_value(spec.model_dump(mode="json"))
    return _BuiltinOwner(
        component_id=str(spec.metadata.component_id),
        node_type=node_type,
        execute_function=execute_function,
        execute_code=execute_function.__code__,
        bind_function=bind_function,
        bind_code=(bind_function.__code__ if bind_function is not None else None),
        spec_descriptor=spec_descriptor,
        spec_accessor_code=spec_function.__code__,
        spec_sha256=spec_sha256,
        module_source_sha256=_module_source_digest(node_type),
    )


_OWNERS = {
    owner.component_id: owner
    for owner in (
        _owner(_BuildVerifiedPolicyReportNode),
        _owner(_RunGovernanceNode),
        _owner(_RunTransportabilityNode),
        _owner(_RunHierarchicalPolicySearchNode),
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
    execute_function = _function_from_descriptor(inspect.getattr_static(node_type, "execute", None))
    bind_function = _function_from_descriptor(inspect.getattr_static(node_type, "bind", None))
    spec_descriptor = inspect.getattr_static(node_type, "spec", None)
    if spec_descriptor is not owner.spec_descriptor:
        raise ValueError("engine_component_spec_descriptor_changed")
    spec_function = _function_from_descriptor(spec_descriptor)
    if execute_function is None or spec_function is None:
        raise ValueError("engine_component_callable_identity_not_established")
    if (
        execute_function is not owner.execute_function
        or execute_function.__code__ is not owner.execute_code
        or bind_function is not owner.bind_function
        or (bind_function.__code__ if bind_function is not None else None) is not owner.bind_code
        or spec_function.__code__ is not owner.spec_accessor_code
    ):
        raise ValueError("engine_component_callable_changed")
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
    if inspect.getattr_static(node_type, "execute", None) is not owner.execute_function:
        return None
    if inspect.getattr_static(node_type, "bind", None) is not owner.bind_function:
        return None
    if inspect.getattr_static(node_type, "spec", None) is not owner.spec_descriptor:
        return None
    if (
        owner.execute_function.__code__ is not owner.execute_code
        or (owner.bind_function.__code__ if owner.bind_function is not None else None)
        is not owner.bind_code
        or owner.spec_accessor_code is not owner.spec_descriptor.fget.__code__
    ):
        return None
    try:
        spec_function = _function_from_descriptor(owner.spec_descriptor)
        if spec_function is None:
            return None
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
            worker_run = _resolve_exact_worker_run_view(current)
            if worker_run is None:
                return False
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
    owner = _BuiltinOwner(
        component_id=str(spec.metadata.component_id),
        node_type=node_type,
        execute_function=execute_function,
        execute_code=execute_function.__code__,
        bind_function=bind_function,
        bind_code=bind_function.__code__ if bind_function is not None else None,
        spec_descriptor=spec_descriptor,
        spec_accessor_code=spec_function.__code__,
        spec_sha256=_digest_value(spec.model_dump(mode="json")),
        module_source_sha256=_module_source_digest(node_type),
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

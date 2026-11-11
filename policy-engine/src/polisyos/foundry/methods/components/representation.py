"""Bind registered representation profiles to one observed NumPy call.

These observations support representation compatibility only. They establish no
causal identification, accuracy, calibration, scientific validity, or authority.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from types import FunctionType
from typing import TYPE_CHECKING, Any, Literal

from polisyos.common.serialization import to_python_data
from polisyos.foundry.methods._internal.executable_identity import (
    _ExecutableIdentity,
    _signature_binding,
    _signature_matches,
)
from polisyos.foundry.methods.base import MethodRepresentationProfile, MethodSignature
from polisyos.ir import OutputContractDeclaration

if TYPE_CHECKING:
    from polisyos.foundry.methods.backends.protocol import MethodResult
    from polisyos.foundry.methods.selection.registry import MethodRegistry


def _owner(reference: str) -> type[Any]:
    module, qualname = reference.split(":", 1)
    owner: Any = importlib.import_module(module)
    for name in qualname.split("."):
        owner = getattr(owner, name)
    if not isinstance(owner, type):
        raise TypeError("representation_contract_owner_not_type")
    return owner


@dataclass(frozen=True, slots=True)
class RegisteredRepresentationBinding:
    """Retain actual callable/code and typed contract owners at registry admission."""

    profile: MethodRepresentationProfile
    registry: MethodRegistry
    method_class: type[Any]
    signature: MethodSignature
    operation: FunctionType
    identity: _ExecutableIdentity
    precondition: FunctionType
    precondition_identity: _ExecutableIdentity
    input_owner: type[Any]
    output_owner: type[Any]

    def current(self, operation: object) -> bool:
        """Recheck the retained bindings at this endpoint, without a through-use claim."""
        try:
            return bool(
                operation is self.operation
                and getattr(self.method_class, "pure_step", None) is self.operation
                and _signature_matches(self.method_class, self.signature)
                and _ExecutableIdentity(
                    self.method_class, operation, _signature_binding(self.signature)
                )
                == self.identity
                and getattr(self.method_class, self.profile.precondition_method, None)
                is self.precondition
                and _ExecutableIdentity(
                    self.method_class, self.precondition, _signature_binding(self.signature)
                )
                == self.precondition_identity
                and _owner(self.profile.input_contract_owner) is self.input_owner
                and _owner(self.profile.output_contract_owner) is self.output_owner
                and self.output_owner.contract_id == self.profile.output_contract_id
                and isinstance(
                    self.output_owner.output_contract_declaration, OutputContractDeclaration
                )
                and self.output_owner.output_contract_declaration.contract_id
                == self.profile.output_contract_id
            )
        except (AttributeError, ImportError, TypeError, ValueError):
            return False


def bind_registered_representation_profiles(
    method_class: type[Any],
    signature: MethodSignature,
    *,
    registry: MethodRegistry,
) -> tuple[RegisteredRepresentationBinding, ...]:
    """Resolve maintained method profiles without interpreting tags as support."""
    if not signature.representation_profiles:
        return ()
    if not _signature_matches(method_class, signature):
        raise ValueError("representation_registered_signature_mismatch")
    operation = getattr(method_class, "pure_step", None)
    if type(operation) is not FunctionType:
        raise ValueError("representation_operation_not_python_function")
    bindings = []
    for profile in signature.representation_profiles:
        precondition = getattr(method_class, profile.precondition_method, None)
        if type(precondition) is not FunctionType:
            raise ValueError("representation_precondition_not_python_function")
        try:
            input_owner = _owner(profile.input_contract_owner)
            output_owner = _owner(profile.output_contract_owner)
        except ImportError:
            # An optional contract dependency limits this profile, not the
            # pre-existing raw method's execution availability.
            continue
        binding = RegisteredRepresentationBinding(
            profile,
            registry,
            method_class,
            signature,
            operation,
            _ExecutableIdentity(method_class, operation, _signature_binding(signature)),
            precondition,
            _ExecutableIdentity(method_class, precondition, _signature_binding(signature)),
            input_owner,
            output_owner,
        )
        if not binding.current(operation):
            raise ValueError("representation_native_contract_mismatch")
        bindings.append(binding)
    return tuple(bindings)


def _applicable_representation_bindings(
    *,
    method_class: type[Any],
    signature: MethodSignature,
    operation: object,
    postprocessor: object,
    state: object,
    params: object,
) -> tuple[RegisteredRepresentationBinding, ...]:
    """Retain applicable registered profiles immediately before the captured call."""
    if not signature.representation_profiles or postprocessor is not None:
        return ()
    from polisyos.foundry.methods.selection.registry import get_registry

    entry = get_registry().get_entry(signature.fqn)
    if (
        entry is None
        or entry._cached_class is not method_class
        or _signature_binding(entry.signature) != _signature_binding(signature)
    ):
        return ()
    selected = []
    for binding in entry.representation_bindings:
        if not binding.current(operation):
            continue
        try:
            validated = binding.input_owner.model_validate_json(_wire_bytes(state))
            if binding.precondition(validated, params) is True:
                selected.append(binding)
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    return tuple(selected)


class MethodRepresentationCompatibility:
    """Opaque owner-issued live view of one observed call, not portable authority.

    Ordinary construction, assignment and dataclass replacement are unsupported.
    This is an in-process API boundary, not protection against Python reflection,
    mutation of private implementation state, or replacement of module code.
    """

    __slots__ = ("_binding", "_native_wire", "_output_wire", "_raw_output")

    def __new__(cls) -> MethodRepresentationCompatibility:
        raise TypeError("representation_compatibility_is_owner_issued")

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("representation_compatibility_is_read_only")

    @property
    def binding(self) -> RegisteredRepresentationBinding:
        return self._binding

    @property
    def scope(self) -> Literal["representation_compatibility_only"]:
        return "representation_compatibility_only"

    @property
    def identification_established(self) -> Literal[False]:
        return False

    def valid_for(self, output: object) -> bool:
        """Reconcile the same returned output and current maintained call bindings."""
        entry = self.binding.registry.get_entry(self.binding.signature.fqn)
        if (
            output is not self._raw_output
            or type(output) is not dict
            or entry is None
            or _signature_binding(entry.signature) != _signature_binding(self.binding.signature)
            or not any(binding is self.binding for binding in entry.representation_bindings)
            or not self.binding.current(self.binding.operation)
        ):
            return False
        try:
            current = _native_wire(
                self.binding.output_owner, output[self.binding.profile.output_slot]
            )
            return current == self._native_wire and _wire_bytes(output) == self._output_wire
        except (KeyError, TypeError, ValueError):
            return False

    def summary(self) -> dict[str, object]:
        """Expose an audit declaration which carries no execution authority."""
        return {
            **self.binding.profile._stable_dict(),
            "method_fqn": self.binding.signature.fqn,
            "representation_digest": self.binding.signature.representation_digest(),
            "scope": self.scope,
            "identification_established": False,
            "identity_scope": "retained_class_callable_code_at_observed_endpoints",
        }


def _wire_bytes(value: object) -> bytes:
    return json.dumps(
        to_python_data(value, sort_keys=True),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def _native_wire(owner: type[Any], value: object) -> bytes:
    """Revalidate serialized data independently of a shallowly frozen native model."""
    native = owner.model_validate_json(_wire_bytes(value))
    return _wire_bytes(native.model_dump(mode="json"))


def invoke_representation_call(
    *,
    method_class: type[Any],
    signature: MethodSignature,
    operation: Any,
    postprocessor: object,
    state: object,
    params: object,
) -> tuple[object, tuple[MethodRepresentationCompatibility, ...]]:
    """Invoke the captured callable once and issue endpoint-bound compatibility views."""
    bindings = _applicable_representation_bindings(
        method_class=method_class,
        signature=signature,
        operation=operation,
        postprocessor=postprocessor,
        state=state,
        params=params,
    )
    output = operation(state, params)
    if type(output) is not dict:
        return output, ()
    projections = []
    for binding in bindings:
        if not binding.current(operation):
            continue
        try:
            native = _native_wire(binding.output_owner, output[binding.profile.output_slot])
            whole_wire = _wire_bytes(output)
        except (KeyError, TypeError, ValueError):
            continue
        projection = object.__new__(MethodRepresentationCompatibility)
        object.__setattr__(projection, "_binding", binding)
        object.__setattr__(projection, "_raw_output", output)
        object.__setattr__(projection, "_native_wire", native)
        object.__setattr__(projection, "_output_wire", whole_wire)
        projections.append(projection)
    return output, tuple(projections)


def resolved_execution_representation_modes(result: MethodResult) -> tuple[str, ...]:
    """Read only live projections bound to this returned result, never caller tags."""
    return tuple(
        sorted(
            {
                projection.binding.profile.identification_mode.value
                for projection in result.representation_compatibility
                if isinstance(projection, MethodRepresentationCompatibility)
                and projection.valid_for(result.output)
            }
        )
    )

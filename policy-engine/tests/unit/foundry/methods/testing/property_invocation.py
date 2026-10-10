"""Dispatch property-test inputs through the declared Foundry method ABI."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.backends.protocol import MethodResult
from polisyos.foundry.methods.base import MethodSignature
from polisyos.foundry.methods.components.io import (
    materialize_method_input,
    validate_value_for_slot,
)
from polisyos.foundry.methods.exceptions import MethodContractError


def invoke_property_method(
    *,
    dispatcher: MethodDispatcher,
    method_class: type,
    state: Any,
    params: Mapping[str, Any],
    seed: int,
    bound_inputs: Mapping[str, Any] | None = None,
) -> MethodResult:
    """Validate declared inputs and invoke one method with an explicit seed.

    With ``bound_inputs`` omitted, validate a complete named state mapping and
    pass it unchanged. With ``bound_inputs`` supplied, validate only the provided
    declared slots and materialize them through the existing owner hook. In both
    cases, slotless legacy methods retain their method-specific state shape.

    The default path is a direct-dispatch property harness, not a real chain
    witness. `_collect_node_inputs` in ``backends/chain_executor.py`` uses
    ``materialize_method_input``: without an owner ``materialize_input`` hook, a
    single bound slot becomes its bare value. Mapping-consuming single-slot
    methods such as Monte Carlo/bootstrap therefore remain a separately visible
    chain-integration question; this helper invents no alias or materializer.

    Args:
        dispatcher: Existing backend dispatcher to exercise.
        method_class: Registered or directly imported method implementation.
        state: Method-specific fallback or direct input payload.
        params: Declared execution parameters.
        seed: Explicit backend seed for reproducible property cases.
        bound_inputs: Optional explicit slot bindings to merge using the method's
            existing input materializer. Missing slots may come from ``state``.

    Returns:
        The backend's structured method result.

    Raises:
        MethodContractError: If supplied declared input slots are missing from a
            direct state mapping, undeclared, or malformed.
        TypeError: If the method does not expose a typed ``MethodSignature``.
    """
    signature = getattr(method_class, "signature", None)
    if not isinstance(signature, MethodSignature):
        raise TypeError("property invocation requires a method with MethodSignature")

    if bound_inputs is None:
        if signature.input_slots:
            if not isinstance(state, Mapping):
                raise MethodContractError(
                    signature.fqn, "declared input slots require a named mapping state"
                )
            expected = signature.input_slot_names
            provided = set(state)
            missing = expected - provided
            extra = provided - expected
            if missing or extra:
                reasons: list[str] = []
                if missing:
                    reasons.append(f"missing declared input slots: {sorted(missing)}")
                if extra:
                    reasons.append(f"undeclared input keys: {sorted(extra, key=repr)}")
                raise MethodContractError(signature.fqn, "; ".join(reasons))
            for slot in sorted(signature.input_slots, key=lambda item: item.name):
                validate_value_for_slot(
                    slot, state[slot.name], method_fqn=signature.fqn, label="input"
                )
    else:
        if not isinstance(bound_inputs, Mapping):
            raise MethodContractError(signature.fqn, "bound_inputs must be a named mapping")
        provided = set(bound_inputs)
        undeclared = provided - signature.input_slot_names
        if undeclared:
            raise MethodContractError(
                signature.fqn,
                f"undeclared bound input slots: {sorted(undeclared, key=repr)}",
            )
        for slot in sorted(signature.input_slots, key=lambda item: item.name):
            if slot.name in bound_inputs:
                validate_value_for_slot(
                    slot,
                    bound_inputs[slot.name],
                    method_fqn=signature.fqn,
                    label="input",
                )
        state = materialize_method_input(
            method_class=method_class,
            signature=signature,
            bound_inputs=bound_inputs,
            fallback_state=state,
        )

    return dispatcher.dispatch(
        method_class=method_class,
        signature=signature,
        state=state,
        params=params,
        seed=seed,
    )

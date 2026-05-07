"""Public methods io module API."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from polisyos.foundry.methods.base import MethodSignature, SlotSpec, SlotType
from polisyos.foundry.methods.exceptions import MethodContractError

_META_OUTPUT_KEYS = frozenset({"__determinism_tier__"})
_COMMON_OUTPUT_ALIASES: dict[str, tuple[str, ...]] = {
    "result": (
        "result",
        "report",
        "transport_result",
        "econometric_result",
        "optimization_result",
        "io_result",
        "causal_effect_report",
    ),
    "causal_effect_report": ("causal_effect_report", "report"),
    "donor_weights": ("donor_weights", "weights"),
    "counterfactual_series": ("counterfactual_series", "counterfactual"),
    "uncertainty_envelope": ("uncertainty_envelope", "envelope"),
    "warnings": ("warnings",),
    "solver_info": ("solver_info",),
    "diagnostics": ("diagnostics",),
}


def materialize_method_input(
    *,
    method_class: type,
    signature: MethodSignature,
    bound_inputs: Mapping[str, Any],
    fallback_state: Any,
) -> Any:
    """Materialize method input helper."""
    custom = getattr(method_class, "materialize_input", None)
    if callable(custom):
        return custom(bound_inputs, fallback_state)

    if not bound_inputs:
        return fallback_state

    if len(signature.input_slots) <= 1 and len(bound_inputs) == 1:
        return next(iter(bound_inputs.values()))

    if isinstance(fallback_state, Mapping):
        merged = dict(fallback_state)
        merged.update(bound_inputs)
        return merged

    return dict(bound_inputs)


def dematerialize_method_output(
    *,
    method_class: type,
    signature: MethodSignature,
    output: Any,
) -> dict[str, Any]:
    """Dematerialize method output helper."""
    expected_slots = sorted(signature.output_slots, key=lambda item: item.name)
    custom = getattr(method_class, "dematerialize_output", None)
    if callable(custom):
        materialized = custom(output)
        if not isinstance(materialized, Mapping):
            raise MethodContractError(signature.fqn, "dematerialize_output() must return a mapping")
        result = {str(key): value for key, value in materialized.items()}
        _validate_output_mapping(signature=signature, output_mapping=result, strict_extras=True)
        return result

    result = _coerce_output_mapping(signature=signature, output=output)
    strict_extras = bool(getattr(method_class, "strict_output_contract", False))
    _validate_output_mapping(
        signature=signature, output_mapping=result, strict_extras=strict_extras
    )

    if len(expected_slots) == 1:
        return result

    return result


def validate_value_for_slot(slot: SlotSpec, value: Any, *, method_fqn: str, label: str) -> None:
    """Validate value for slot."""
    if slot.contract_id is not None:
        actual_contract: str | None = None
        if isinstance(value, Mapping):
            raw = value.get("contract_id")
            if raw is not None:
                actual_contract = str(raw)
        elif hasattr(value, "contract_id"):
            raw = value.contract_id
            if raw is not None:
                actual_contract = str(raw)
        if actual_contract is not None and actual_contract != slot.contract_id:
            raise MethodContractError(
                method_fqn,
                f"{label} contract_id mismatch for slot '{slot.name}': "
                f"expected {slot.contract_id!r}, got {actual_contract!r}",
            )

    if slot.shape:
        arr = _as_array_like(value)
        if arr is not None:
            _validate_shape(slot=slot, arr=arr, method_fqn=method_fqn, label=label)
        return

    arr = _as_array_like(value)
    if arr is None:
        return
    if slot.slot_type is SlotType.VECTOR and arr.ndim != 1:
        raise MethodContractError(
            method_fqn,
            f"{label} slot '{slot.name}' expects VECTOR data, got ndim={arr.ndim}",
        )
    if slot.slot_type is SlotType.MATRIX and arr.ndim != 2:
        raise MethodContractError(
            method_fqn,
            f"{label} slot '{slot.name}' expects MATRIX data, got ndim={arr.ndim}",
        )


def _coerce_output_mapping(*, signature: MethodSignature, output: Any) -> dict[str, Any]:
    expected_slots = sorted(signature.output_slots, key=lambda item: item.name)
    if not expected_slots:
        if output is None:
            return {}
        if isinstance(output, Mapping):
            extras = {key: value for key, value in output.items() if key not in _META_OUTPUT_KEYS}
            if extras:
                raise MethodContractError(
                    signature.fqn,
                    f"method declares no output slots but returned {sorted(extras)}",
                )
        return {}

    if len(expected_slots) == 1 and not isinstance(output, Mapping):
        return {expected_slots[0].name: output}

    if not isinstance(output, Mapping):
        raise MethodContractError(
            signature.fqn,
            f"method must return a mapping for output slots {sorted(signature.output_slot_names)}",
        )

    source = dict(output)
    materialized: dict[str, Any] = {}
    for slot in expected_slots:
        aliases = _COMMON_OUTPUT_ALIASES.get(slot.name, ())
        candidates = (slot.name,) + aliases
        found = False
        for candidate in candidates:
            if candidate in source:
                materialized[slot.name] = source[candidate]
                found = True
                break
        if not found:
            raise MethodContractError(
                signature.fqn,
                f"missing output for declared slot '{slot.name}'",
            )
    return materialized


def _validate_output_mapping(
    *,
    signature: MethodSignature,
    output_mapping: Mapping[str, Any],
    strict_extras: bool,
) -> None:
    declared = {slot.name: slot for slot in signature.output_slots}
    missing = sorted(set(declared) - set(output_mapping))
    if missing:
        raise MethodContractError(signature.fqn, f"missing declared outputs: {missing}")

    extras = sorted(set(output_mapping) - set(declared))
    if extras and strict_extras:
        raise MethodContractError(signature.fqn, f"undeclared outputs: {extras}")

    for slot_name, value in output_mapping.items():
        slot = declared.get(slot_name)
        if slot is None:
            continue
        validate_value_for_slot(slot, value, method_fqn=signature.fqn, label="output")


def _as_array_like(value: Any) -> np.ndarray | None:
    if hasattr(value, "shape") and hasattr(value, "dtype"):
        try:
            return np.asarray(value)
        except Exception:
            return None
    return None


def _validate_shape(*, slot: SlotSpec, arr: np.ndarray, method_fqn: str, label: str) -> None:
    expected_shape = slot.shape
    if slot.slot_type is SlotType.VECTOR and arr.ndim != 1:
        raise MethodContractError(
            method_fqn,
            f"{label} slot '{slot.name}' expects VECTOR data, got ndim={arr.ndim}",
        )
    if slot.slot_type is SlotType.MATRIX and arr.ndim != 2:
        raise MethodContractError(
            method_fqn,
            f"{label} slot '{slot.name}' expects MATRIX data, got ndim={arr.ndim}",
        )
    if len(expected_shape) != arr.ndim:
        raise MethodContractError(
            method_fqn,
            f"{label} slot '{slot.name}' expected rank {len(expected_shape)}, got {arr.ndim}",
        )
    for idx, expected_dim in enumerate(expected_shape):
        if isinstance(expected_dim, int) and int(arr.shape[idx]) != expected_dim:
            raise MethodContractError(
                method_fqn,
                f"{label} slot '{slot.name}' expected shape {expected_shape}, got {tuple(arr.shape)}",
            )

"""Project native Foundry method reports onto value evidence.

The projector is deliberately contract-driven: the selected method output slot
names the native contract and the native result owns estimand-bound uncertainty
projection.  Mapping shape is never treated as report authority.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessTier,
    extract_truthfulness_receipt,
)
from polisyos.foundry.methods.backends.protocol import MethodResult
from polisyos.foundry.methods.base import MethodSignature, SlotSpec
from polisyos.foundry.methods.components.consensus import EstimandSpec
from polisyos.ir.analytics.uncertainty import UncertaintyEnvelope

MethodValueEvidenceStatus = Literal["value_ready", "value_limited"]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class MethodValueEvidence(_StrictModel):
    """Estimand-bound uncertainty projected by a native method contract."""

    status: MethodValueEvidenceStatus
    method_fqn: str = Field(min_length=1)
    method_family: str = Field(min_length=1)
    native_contract_id: str = Field(min_length=1)
    selected_output_slot: str = Field(min_length=1)
    estimand: EstimandSpec
    envelope: UncertaintyEnvelope
    diagnostic_refs: tuple[str, ...] = ()
    truthfulness_receipt: TruthfulnessReceipt | None = None
    limitation_codes: tuple[str, ...] = ()
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class MethodValueRefusal(_StrictModel):
    """Typed refusal when native output cannot support the requested estimand."""

    status: Literal["value_refused"] = "value_refused"
    method_fqn: str = Field(min_length=1)
    method_family: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    resolved_contract_id: str | None = None
    selected_output_slot: str | None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def project_method_value_evidence(
    *,
    method_signature: MethodSignature,
    method_result: MethodResult,
    estimand: EstimandSpec,
    selected_output_slot: str | None = None,
) -> MethodValueEvidence | MethodValueRefusal:
    """Project a native output contract without assuming a method family shape."""

    slot = _resolve_output_slot(method_signature, selected_output_slot)
    if slot is None or slot.contract_id is None:
        return _refusal(
            signature=method_signature,
            reason_code="method_output_contract_unresolved",
            resolved_contract_id=None,
            selected_output_slot=selected_output_slot,
        )
    native = _resolve_native_output(method_result, slot)
    native_contract_id = getattr(type(native), "contract_id", None)
    if not isinstance(native_contract_id, str) or native_contract_id != slot.contract_id:
        return _refusal(
            signature=method_signature,
            reason_code="method_output_contract_unresolved",
            resolved_contract_id=(
                native_contract_id if isinstance(native_contract_id, str) else None
            ),
            selected_output_slot=slot.name,
        )
    value_projector = getattr(native, "to_value_uncertainty", None)
    legacy_projector = getattr(native, "to_uncertainty_envelope", None)
    if not callable(value_projector) and not callable(legacy_projector):
        return _refusal(
            signature=method_signature,
            reason_code="method_uncertainty_projection_unsupported",
            resolved_contract_id=native_contract_id,
            selected_output_slot=slot.name,
        )
    try:
        envelope = (
            value_projector(estimand=estimand)
            if callable(value_projector)
            else legacy_projector(param_name=estimand.estimand_id)
        )
    except (TypeError, ValueError):
        envelope = None
    if not isinstance(envelope, UncertaintyEnvelope):
        return _refusal(
            signature=method_signature,
            reason_code="method_estimand_binding_mismatch",
            resolved_contract_id=native_contract_id,
            selected_output_slot=slot.name,
        )
    if not envelope.gate_eligible or envelope.is_heuristic_ci:
        return _refusal(
            signature=method_signature,
            reason_code="method_uncertainty_not_gate_eligible",
            resolved_contract_id=native_contract_id,
            selected_output_slot=slot.name,
        )
    truthfulness = extract_truthfulness_receipt(native)
    if (
        truthfulness is not None
        and truthfulness.effective_truthfulness_tier is TruthfulnessTier.UNVERIFIED
    ):
        return _refusal(
            signature=method_signature,
            reason_code="method_truthfulness_unverified",
            resolved_contract_id=native_contract_id,
            selected_output_slot=slot.name,
        )
    limitation_codes = tuple(
        dict.fromkeys(
            str(item)
            for item in (
                *(truthfulness.degradation_reasons if truthfulness is not None else ()),
                *method_result.warnings,
            )
            if str(item)
        )
    )
    payload = {
        # Projection readiness says only that the native contract supplied an
        # estimand-bound, gate-eligible envelope.  Runtime calibration remains
        # the authority that passes or refuses truthfulness limitations.
        "status": "value_ready",
        "method_fqn": method_signature.fqn,
        "method_family": method_signature.family,
        "native_contract_id": native_contract_id,
        "selected_output_slot": slot.name,
        "estimand": asdict(estimand),
        "envelope": envelope.model_dump(mode="json"),
        "diagnostic_refs": _diagnostic_refs(native),
        "truthfulness_receipt": (
            truthfulness.model_dump(mode="json") if truthfulness is not None else None
        ),
        "limitation_codes": limitation_codes,
    }
    model_payload = {
        **payload,
        "estimand": estimand,
        "envelope": envelope,
        "truthfulness_receipt": truthfulness,
        "content_hash": _content_hash(payload),
    }
    return MethodValueEvidence.model_validate(model_payload)


def _resolve_output_slot(
    signature: MethodSignature,
    selected_output_slot: str | None,
) -> SlotSpec | None:
    slots = tuple(sorted(signature.output_slots, key=lambda item: item.name))
    if selected_output_slot is not None:
        return next((slot for slot in slots if slot.name == selected_output_slot), None)
    contracted = tuple(slot for slot in slots if slot.contract_id is not None)
    return contracted[0] if len(contracted) == 1 else None


def _resolve_native_output(method_result: MethodResult, slot: SlotSpec) -> object | None:
    if slot.name in method_result.slot_outputs:
        return method_result.slot_outputs[slot.name]
    output = method_result.output
    if isinstance(output, dict):
        return output.get(slot.name)
    return output


def _diagnostic_refs(native: object) -> tuple[str, ...]:
    refs: list[str] = []
    for name in (
        "simulator_diagnostic_ref",
        "draws_ref",
        "warmup_draws_ref",
        "dual_certificate_ref",
        "selection_diagram_ref",
    ):
        value = getattr(native, name, None)
        if value is not None and str(value):
            refs.append(str(value))
    return tuple(dict.fromkeys(refs))


def _refusal(
    *,
    signature: MethodSignature,
    reason_code: str,
    resolved_contract_id: str | None,
    selected_output_slot: str | None,
) -> MethodValueRefusal:
    payload = {
        "status": "value_refused",
        "method_fqn": signature.fqn,
        "method_family": signature.family,
        "reason_code": reason_code,
        "resolved_contract_id": resolved_contract_id,
        "selected_output_slot": selected_output_slot,
    }
    return MethodValueRefusal(**payload, content_hash=_content_hash(payload))


def _content_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


__all__ = [
    "MethodValueEvidence",
    "MethodValueEvidenceStatus",
    "MethodValueRefusal",
    "project_method_value_evidence",
]

"""Project native Foundry method reports onto value evidence.

The projector is deliberately contract-driven: the selected method output slot
names the native contract and the native result owns estimand-bound uncertainty
projection.  Mapping shape is never treated as report authority.
"""

from __future__ import annotations

import importlib
import json
from dataclasses import asdict
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.observability.truthfulness import (
    TruthfulnessReceipt,
    TruthfulnessTier,
    extract_truthfulness_receipt,
)
from polisyos.foundry.methods.backends.protocol import MethodResult
from polisyos.foundry.methods.base import MethodSignature, SlotSpec
from polisyos.foundry.methods.components.consensus import EstimandSpec
from polisyos.ir.analytics.uncertainty import (
    NativeValueEstimandBinding,
    OutputContractCapability,
    OutputContractDeclaration,
    UncertaintyEnvelope,
    supports_value_uncertainty_projection_contract,
)

MethodValueEvidenceStatus = Literal[
    "contract_projection_ready",
    "contract_projection_limited",
]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class MethodValueEvidence(_StrictModel):
    """Non-production proof that a native method contract can project uncertainty."""

    status: MethodValueEvidenceStatus
    authority_scope: Literal["contract_only_nonproduction"] = (
        "contract_only_nonproduction"
    )
    production_value_eligible: Literal[False] = False
    method_fqn: str = Field(min_length=1)
    method_family: str = Field(min_length=1)
    native_contract_id: str = Field(min_length=1)
    selected_output_slot: str = Field(min_length=1)
    estimand_binding_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    estimand: EstimandSpec
    envelope: UncertaintyEnvelope
    diagnostic_refs: tuple[str, ...] = ()
    truthfulness_receipt: TruthfulnessReceipt | None = None
    limitation_codes: tuple[str, ...] = ()
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_content_hash(self) -> MethodValueEvidence:
        payload = self.model_dump(mode="json", exclude={"content_hash"})
        if self.content_hash != _content_hash(payload):
            raise ValueError("method_value_evidence_content_hash_mismatch")
        return self


class MethodValueRefusal(_StrictModel):
    """Typed refusal when native output cannot support the requested estimand."""

    status: Literal["value_refused"] = "value_refused"
    method_fqn: str = Field(min_length=1)
    method_family: str = Field(min_length=1)
    reason_code: str = Field(min_length=1)
    resolved_contract_id: str | None = None
    selected_output_slot: str | None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class NativeValueProjectionCapability(_StrictModel):
    """Verified catalog witness for one estimand-aware native output slot."""

    output_slot: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    projector: Literal["to_value_uncertainty"] = "to_value_uncertainty"
    owner_module: str = Field(min_length=1)
    owner_qualname: str = Field(min_length=1)


def resolve_method_value_projection_capabilities(
    *,
    method_cls: type[object],
    method_signature: MethodSignature,
) -> tuple[NativeValueProjectionCapability, ...]:
    """Resolve two-sided output-contract capabilities for catalog selection."""

    if getattr(method_cls, "signature", None) is not method_signature:
        method_class_signature = getattr(method_cls, "signature", None)
        if not isinstance(method_class_signature, MethodSignature) or (
            method_class_signature.stable_digest()
            != method_signature.stable_digest()
        ):
            return ()
    resolved: list[NativeValueProjectionCapability] = []
    for slot in sorted(method_signature.output_slots, key=lambda item: item.name):
        if (
            OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION
            not in slot.contract_capabilities
        ):
            continue
        owner = _resolve_output_contract_owner(slot)
        if owner is None:
            continue
        declaration = getattr(owner, "output_contract_declaration", None)
        if not isinstance(declaration, OutputContractDeclaration):
            continue
        if slot.contract_id != declaration.contract_id:
            continue
        if (
            OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION
            not in declaration.capabilities
        ):
            continue
        if not supports_value_uncertainty_projection_contract(owner):
            continue
        resolved.append(
            NativeValueProjectionCapability(
                output_slot=slot.name,
                contract_id=declaration.contract_id,
                owner_module=owner.__module__,
                owner_qualname=owner.__qualname__,
            )
        )
    return tuple(resolved)


def project_method_value_evidence(
    *,
    method_signature: MethodSignature,
    method_result: MethodResult,
    estimand: EstimandSpec,
    selected_output_slot: str | None = None,
    projection_binding: NativeValueEstimandBinding | None = None,
) -> MethodValueEvidence | MethodValueRefusal:
    """Project a native output contract as a non-production capability proof."""

    slot = _resolve_output_slot(method_signature, selected_output_slot)
    if slot is None or slot.contract_id is None:
        return _refusal(
            signature=method_signature,
            reason_code="method_output_contract_unresolved",
            resolved_contract_id=None,
            selected_output_slot=selected_output_slot,
        )
    if (
        OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION
        not in slot.contract_capabilities
    ):
        return _refusal(
            signature=method_signature,
            reason_code="method_value_projection_capability_undeclared",
            resolved_contract_id=slot.contract_id,
            selected_output_slot=slot.name,
        )
    declared_owner = _resolve_output_contract_owner(slot)
    if declared_owner is None:
        return _refusal(
            signature=method_signature,
            reason_code="method_value_projection_owner_unresolved",
            resolved_contract_id=slot.contract_id,
            selected_output_slot=slot.name,
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
    native_declaration = getattr(type(native), "output_contract_declaration", None)
    if (
        not isinstance(native_declaration, OutputContractDeclaration)
        or native_declaration.contract_id != slot.contract_id
        or OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION
        not in native_declaration.capabilities
        or type(native) is not declared_owner
    ):
        return _refusal(
            signature=method_signature,
            reason_code="method_value_projection_owner_mismatch",
            resolved_contract_id=native_contract_id,
            selected_output_slot=slot.name,
        )
    value_projector = getattr(native, "to_value_uncertainty", None)
    if not callable(value_projector):
        return _refusal(
            signature=method_signature,
            reason_code="method_uncertainty_projection_unsupported",
            resolved_contract_id=native_contract_id,
            selected_output_slot=slot.name,
        )
    if (
        projection_binding is None
        or projection_binding.production_value_eligible is not False
        or projection_binding.authority_scope != "contract_only_nonproduction"
        or projection_binding.native_contract_id != slot.contract_id
        or projection_binding.producer_method_fqn != method_signature.fqn
        or not projection_binding.matches(estimand)
    ):
        return _refusal(
            signature=method_signature,
            reason_code="method_estimand_binding_mismatch",
            resolved_contract_id=native_contract_id,
            selected_output_slot=slot.name,
        )
    try:
        envelope = value_projector(
            estimand=estimand,
            projection_binding=projection_binding,
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
    if (
        envelope.metadata.get("value_estimand_binding_native_contract_id")
        != slot.contract_id
        or envelope.metadata.get("value_estimand_binding_producer_method_fqn")
        != method_signature.fqn
        or not isinstance(
            envelope.metadata.get("value_estimand_binding_content_hash"),
            str,
        )
    ):
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
        # Projection readiness is a contract proof only.  Production value
        # authority requires an independently owner-resolved world receipt.
        "status": "contract_projection_ready",
        "authority_scope": "contract_only_nonproduction",
        "production_value_eligible": False,
        "method_fqn": method_signature.fqn,
        "method_family": method_signature.family,
        "native_contract_id": native_contract_id,
        "selected_output_slot": slot.name,
        "estimand_binding_content_hash": projection_binding.content_hash,
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
    capable = tuple(
        slot
        for slot in slots
        if OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION
        in slot.contract_capabilities
    )
    if len(capable) == 1:
        return capable[0]
    contracted = tuple(slot for slot in slots if slot.contract_id is not None)
    return contracted[0] if len(contracted) == 1 else None


def _resolve_output_contract_owner(slot: SlotSpec) -> type[object] | None:
    owner_ref = slot.contract_owner
    if not isinstance(owner_ref, str) or ":" not in owner_ref:
        return None
    module_name, qualname = owner_ref.split(":", 1)
    try:
        owner: object = importlib.import_module(module_name)
        for segment in qualname.split("."):
            owner = getattr(owner, segment)
    except (AttributeError, ImportError, ValueError):
        return None
    return owner if isinstance(owner, type) else None


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
    "NativeValueProjectionCapability",
    "project_method_value_evidence",
    "resolve_method_value_projection_capabilities",
]

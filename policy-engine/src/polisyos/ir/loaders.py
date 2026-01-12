from __future__ import annotations

import warnings
from typing import Any, Mapping

from polisyos.ir.contract import PolicyRequestIR
from polisyos.ir.surface import PolicySurfaceIR
from polisyos.ir.types import SelectorOperator

ZERO_CONTEXT_REF = "sha256:" + "0" * 64


def _looks_like_surface(payload: Mapping[str, Any]) -> bool:
    return "semantic" in payload or payload.get("schema_version", "").startswith("2.")


def _coerce_v1_to_surface(data: Mapping[str, Any]) -> PolicySurfaceIR:
    """Best-effort adapter from PolicyRequestIR payload to PolicySurfaceIR."""
    model = PolicyRequestIR.model_validate(data)

    interventions = []
    for intervention in model.interventions:
        interventions.append(
            {
                "intervention_id": intervention.id,
                "kind": intervention.mechanism_type,
                # Fallback selector: apply to any entity; legacy target_selector is not compatible.
                "target": {
                    "kind": "predicate",
                    "field": "id",
                    "operator": SelectorOperator.EQUALS,
                    "value": "any",
                },
                # Minimal schedule; legacy model lacks surface schedule semantics.
                "schedule": {"start_step": 0, "duration_steps": 1},
                "params": intervention.parameters or {},
                "priority": None,
                "notes": [],
            }
        )

    constraints = []
    for constraint_id, value in (model.global_constraints or {}).items():
        constraints.append(
            {
                "constraint_id": constraint_id,
                "value": value,
                "notes": [],
            }
        )

    semantic = {
        "context_snapshot_ref": ZERO_CONTEXT_REF,
        "registry_bundle_ref": None,
        "time_semantics": None,
        "objectives": [],
        "interventions": interventions,
        "constraints": constraints,
        "notes": [],
    }

    return PolicySurfaceIR.model_validate({"schema_version": "2.0", "semantic": semantic})


def load_policy(payload: Any) -> PolicySurfaceIR:
    """
    Unified loader that returns PolicySurfaceIR regardless of input flavor.

    Accepted inputs:
    - PolicySurfaceIR instance
    - dict/json-like already in surface format
    - PolicyRequestIR instance or payload (legacy): converted to Surface IR with defaults
    """
    if isinstance(payload, PolicySurfaceIR):
        return payload

    if isinstance(payload, PolicyRequestIR):
        warnings.warn(
            "PolicyRequestIR is deprecated; converting to PolicySurfaceIR.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _coerce_v1_to_surface(payload.model_dump())

    if isinstance(payload, Mapping):
        if _looks_like_surface(payload):
            return PolicySurfaceIR.model_validate(payload)
        # Attempt legacy parse
        warnings.warn(
            "Detected legacy PolicyRequestIR payload; converting to PolicySurfaceIR.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _coerce_v1_to_surface(payload)

    raise TypeError(f"Unsupported policy payload type: {type(payload)}")


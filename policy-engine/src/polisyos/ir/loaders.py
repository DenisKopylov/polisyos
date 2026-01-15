from __future__ import annotations

from typing import Any, Mapping

from polisyos.ir.surface import PolicySurfaceIR


def _looks_like_surface(payload: Mapping[str, Any]) -> bool:
    return "semantic" in payload or payload.get("schema_version", "").startswith("2.")


def load_policy(payload: Any) -> PolicySurfaceIR:
    """
    Loader that returns PolicySurfaceIR.

    Accepted inputs:
    - PolicySurfaceIR instance
    - dict/json-like already in surface format (schema_version 2.x)
    """
    if isinstance(payload, PolicySurfaceIR):
        return payload

    if isinstance(payload, Mapping):
        if _looks_like_surface(payload):
            return PolicySurfaceIR.model_validate(payload)
        raise ValueError("Unsupported policy payload: expected PolicySurfaceIR (schema_version 2.x).")

    raise TypeError(f"Unsupported policy payload type: {type(payload)}")

"""Trinity migration helpers.

Legacy Surface IR migrations were removed in Stage 3 cleanup.
This module keeps a small compatibility surface for callers that
already operate on Trinity payloads.
"""
from __future__ import annotations

from typing import Any, Mapping

from polisyos.ir.trinity import TrinityBundle


def split_surface_ir(_legacy_ir: Any):
    raise ValueError(
        "split_surface_ir() was removed with PolicySurfaceIR decommissioning. "
        "Provide a TrinityBundle payload instead."
    )


def split_to_bundle(payload: TrinityBundle | Mapping[str, Any]) -> TrinityBundle:
    if isinstance(payload, TrinityBundle):
        return payload
    return TrinityBundle.model_validate(payload)


def merge_to_surface_ir(
    _problem_frame: Any,
    _policy_spec: Any,
    _model_spec: Any,
    *,
    target_schema_version: str = "2.0",
):
    raise ValueError(
        "merge_to_surface_ir() was removed with PolicySurfaceIR decommissioning. "
        f"Requested target schema version: {target_schema_version}."
    )


def is_trinity_migrated(data: dict) -> bool:
    try:
        TrinityBundle.model_validate(data)
        return True
    except Exception:
        return False


__all__ = [
    "is_trinity_migrated",
    "merge_to_surface_ir",
    "split_surface_ir",
    "split_to_bundle",
]

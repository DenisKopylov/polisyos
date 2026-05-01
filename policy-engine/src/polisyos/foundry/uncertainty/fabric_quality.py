"""Foundry uncertainty adapters for Fabric trust metadata."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.fabric.product_integration import evidence_path_from_fabric_decision_data


class FabricUncertaintyContext(BaseModel):
    """Uncertainty adjustment metadata derived from Fabric trust envelopes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    inflation_factor: float = Field(ge=1.0)
    reasons: tuple[str, ...] = ()


def fabric_uncertainty_context_from_decision_data(
    decision_data: Iterable[Mapping[str, Any] | Any],
) -> FabricUncertaintyContext:
    """Build a conservative uncertainty adjustment from Fabric trust envelopes."""
    paths = tuple(evidence_path_from_fabric_decision_data(row) for row in decision_data)
    if not paths:
        return FabricUncertaintyContext(
            inflation_factor=2.0,
            reasons=("fabric_evidence_missing",),
        )
    reasons = []
    for path in paths:
        if path.quality_status in {"failed", "unknown_quality"}:
            reasons.append(f"quality:{path.quality_status}")
        if path.stale:
            reasons.append("stale_evidence")
        if path.replay_status == "non_replayable":
            reasons.append("non_replayable")
    return FabricUncertaintyContext(
        inflation_factor=max(path.uncertainty_inflation for path in paths),
        reasons=tuple(sorted(set(reasons))),
    )


__all__ = ["FabricUncertaintyContext", "fabric_uncertainty_context_from_decision_data"]

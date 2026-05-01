"""Foundry calibration adapters for Fabric quality and source-trust metadata."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.fabric.product_integration import (
    FabricProductEvidencePath,
    evidence_path_from_fabric_decision_data,
)


class FabricCalibrationContext(BaseModel):
    """Quality/trust context Foundry can attach to calibration targets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_contract_ids: tuple[str, ...] = ()
    lineage_ids: tuple[str, ...] = ()
    min_quality_score: float | None = None
    calibration_weight: float = Field(ge=0.0, le=1.0)
    uncertainty_inflation: float = Field(ge=1.0)
    downgrade_reasons: tuple[str, ...] = ()


def fabric_calibration_context_from_decision_data(
    decision_data: Iterable[Mapping[str, Any] | Any],
    *,
    source_trust_tier: str | None = None,
) -> FabricCalibrationContext:
    """Build a calibration context from FabricDecisionData rows."""
    paths = tuple(
        evidence_path_from_fabric_decision_data(row, source_trust_tier=source_trust_tier)
        for row in decision_data
    )
    return fabric_calibration_context_from_evidence_paths(paths)


def fabric_calibration_context_from_evidence_paths(
    paths: Iterable[FabricProductEvidencePath],
) -> FabricCalibrationContext:
    """Aggregate normalized Fabric paths into Foundry calibration metadata."""
    rows = tuple(paths)
    if not rows:
        return FabricCalibrationContext(
            calibration_weight=0.0,
            uncertainty_inflation=2.0,
            downgrade_reasons=("fabric_evidence_missing",),
        )
    quality_scores = [row.quality_score for row in rows if row.quality_score is not None]
    min_quality = min(quality_scores) if quality_scores else None
    weight = min(row.calibration_weight for row in rows)
    reasons = []
    for row in rows:
        if row.quality_status in {"failed", "unknown_quality"}:
            reasons.append(f"quality:{row.quality_status}")
        if row.source_trust_tier in {"low", "unknown"}:
            reasons.append(f"source_trust:{row.source_trust_tier}")
        if row.stale:
            reasons.append("stale_evidence")
    return FabricCalibrationContext(
        source_contract_ids=tuple(sorted({row.source_contract_id for row in rows})),
        lineage_ids=tuple(sorted({row.lineage_id for row in rows})),
        min_quality_score=min_quality,
        calibration_weight=weight,
        uncertainty_inflation=max(row.uncertainty_inflation for row in rows),
        downgrade_reasons=tuple(sorted(set(reasons))),
    )


__all__ = [
    "FabricCalibrationContext",
    "fabric_calibration_context_from_decision_data",
    "fabric_calibration_context_from_evidence_paths",
]

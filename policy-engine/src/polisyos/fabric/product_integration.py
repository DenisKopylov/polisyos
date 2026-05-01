"""Shared Fabric provenance adapters for downstream product integrations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FabricProductEvidencePath(BaseModel):
    """Normalized provenance path that Scholar, Lex, Foundry, and UI code can share."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_id: str
    lineage_id: str
    source_contract_id: str
    source_contract_version: str | None = None
    quality_status: str = "unknown_quality"
    quality_score: float | None = None
    access_classification: str = "unknown"
    replay_status: str = "unknown"
    temporal_scope: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    export_links: dict[str, str] = Field(default_factory=dict)
    citation_label: str | None = None
    source_trust_tier: str | None = None
    stale: bool = False

    @property
    def calibration_weight(self) -> float:
        """Conservative quality multiplier used by Foundry calibration paths."""
        score = 0.5 if self.quality_score is None else float(self.quality_score)
        trust_penalty = 0.5 if self.source_trust_tier in {"low", "unknown"} else 1.0
        freshness_penalty = 0.5 if self.stale else 1.0
        return max(0.0, min(1.0, score * trust_penalty * freshness_penalty))

    @property
    def uncertainty_inflation(self) -> float:
        """Simple uncertainty inflation factor derived from Fabric trust posture."""
        return round(1.0 + (1.0 - self.calibration_weight), 6)


def evidence_path_from_fabric_decision_data(
    decision_data: Mapping[str, Any] | Any,
    *,
    citation_label: str | None = None,
    source_trust_tier: str | None = None,
) -> FabricProductEvidencePath:
    """Normalize a FabricDecisionData payload without importing Runtime or frontend code."""
    payload = _mapping(decision_data)
    source_contract = _mapping(payload.get("source_contract"))
    quality = _mapping(payload.get("quality"))
    lineage = _mapping(payload.get("lineage"))
    access = _mapping(payload.get("access"))
    replay = _mapping(payload.get("replay"))
    metadata = _mapping(payload.get("metadata"))
    raw_refs = lineage.get("raw_evidence_refs")
    export_links = lineage.get("export_links")
    lineage_freshness = str(lineage.get("freshness") or "").strip().lower()
    trust_metadata = _mapping(lineage.get("trust_metadata"))
    if not lineage_freshness:
        lineage_freshness = str(trust_metadata.get("freshness") or "").strip().lower()

    return FabricProductEvidencePath(
        subject_id=str(payload.get("id") or lineage.get("id") or "fabric_decision_data"),
        lineage_id=str(lineage.get("id") or "untraced"),
        source_contract_id=str(source_contract.get("id") or "unknown_source_contract"),
        source_contract_version=(
            None
            if source_contract.get("version") is None
            else str(source_contract.get("version"))
        ),
        quality_status=str(quality.get("status") or "unknown_quality"),
        quality_score=_optional_float(quality.get("score")),
        access_classification=str(access.get("classification") or "unknown"),
        replay_status=str(replay.get("status") or "unknown"),
        temporal_scope=_mapping(payload.get("time")),
        evidence_refs=tuple(str(ref) for ref in raw_refs if isinstance(ref, str))
        if isinstance(raw_refs, list)
        else (),
        export_links={
            str(key): str(value)
            for key, value in dict(export_links or {}).items()
            if isinstance(value, str)
        }
        if isinstance(export_links, Mapping)
        else {},
        citation_label=citation_label or _citation_label(payload),
        source_trust_tier=source_trust_tier
        or _optional_str(metadata.get("source_trust_tier")),
        stale=lineage_freshness == "stale",
    )


def evidence_paths_from_fabric_decision_data(
    decision_data: Iterable[Mapping[str, Any] | Any],
    *,
    source_trust_tier: str | None = None,
) -> tuple[FabricProductEvidencePath, ...]:
    """Normalize a batch of FabricDecisionData rows."""
    return tuple(
        evidence_path_from_fabric_decision_data(row, source_trust_tier=source_trust_tier)
        for row in decision_data
    )


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        payload = value.model_dump(mode="json")
        return dict(payload) if isinstance(payload, Mapping) else {}
    return {}


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    rendered = str(value).strip()
    return rendered or None


def _citation_label(payload: Mapping[str, Any]) -> str:
    value = _mapping(payload.get("value"))
    return str(value.get("label") or value.get("metric_id") or payload.get("id") or "Fabric evidence")


__all__ = [
    "FabricProductEvidencePath",
    "evidence_path_from_fabric_decision_data",
    "evidence_paths_from_fabric_decision_data",
]

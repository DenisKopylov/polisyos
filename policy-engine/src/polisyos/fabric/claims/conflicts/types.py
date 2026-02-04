from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from polisyos.ir.fact_log import FactSegmentManifest


@dataclass(frozen=True)
class ConflictDetectOptions:
    key_algorithm_version: str = "conflict_key_v1"
    compare_algorithm_version: str = "compare_v1"
    tolerance: Decimal = Decimal("0")
    agent_id: str = "prov.agent.fabric_claims"
    activity_id: str = "prov.activity.fabric_claims.detect_conflicts"


@dataclass(frozen=True)
class ConflictResolveOptions:
    trust_algorithm_version: str = "trust_v1"
    resolution_algorithm_version: str = "resolve_v1"
    emit_contradicts_to_winner: bool = True
    include_detect_event_inputs: bool = True
    agent_id: str = "prov.agent.fabric_claims"
    activity_id: str = "prov.activity.fabric_claims.resolve_conflicts"


@dataclass(frozen=True)
class RankedClaim:
    claim_id: str
    score_total: Decimal
    score_breakdown: dict[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class ConflictDetectResult:
    conflict_set_ids: list[str]
    conflict_set_artifact_ids: list[str]
    claim_ids: list[str]
    claim_artifact_ids_by_id: dict[str, str]
    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest


@dataclass(frozen=True)
class ConflictResolveResult:
    conflict_set_ids: list[str]
    winner_by_conflict_set: dict[str, str]
    conflict_set_artifact_ids: list[str]
    conflict_resolution_artifact_ids: list[str]
    trust_assessment_ids: list[str]
    quality_report_id: str | None
    quality_report_artifact_id: str | None
    world_event_id: str
    world_event_artifact_id: str
    world_segment_manifest: FactSegmentManifest


__all__ = [
    "ConflictDetectOptions",
    "ConflictDetectResult",
    "ConflictResolveOptions",
    "ConflictResolveResult",
    "RankedClaim",
]

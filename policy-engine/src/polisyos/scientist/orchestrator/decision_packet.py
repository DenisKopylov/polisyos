from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.contracts.fabric import EvidenceBundleRef, FabricResult, UncertaintyBoundsRef
from polisyos.ir.surface import PolicySurfaceIR
from polisyos.core.contracts.scientist import GovernanceReportRef
from polisyos.scientist.orchestrator.decision_card import DecisionCard
from polisyos.scientist.orchestrator.run_timeline import RunTimeline
from polisyos.scientist.orchestrator.run_record import RunRecord
from polisyos.scientist.orchestrator.state import ExperimentState, GovernorFeedback


class DecisionPacket(BaseModel):
    """
    Итоговый артефакт прогона: IR + результаты + аудит + RunRecord.

    Phase 16 additions:
    - run_timeline: Chronological event log for observability
    - decision_card: Deterministic summary (generated on-demand or cached)
    - validation_trace: Phase 9 telemetry data (optional)
    """

    schema_version: str = Field("1.1", pattern=r"^\d+\.\d+$")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    run_id: str
    parent_run_id: Optional[str] = None
    run_record: RunRecord

    policy_ir: Optional[PolicySurfaceIR] = None
    simulation_results: Optional[Dict[str, Any]] = None
    fabric_result: Optional[FabricResult] = None
    feedback: Optional[GovernorFeedback] = None
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_ref: EvidenceBundleRef | None = None
    uncertainty_ref: UncertaintyBoundsRef | None = None
    governance_report_ref: GovernanceReportRef | None = None

    # Phase 16: New fields (all optional for backwards compatibility)
    run_timeline: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Serialized RunTimeline artifact for observability",
    )
    validation_trace: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Serialized ValidationTrace (Phase 9 telemetry)",
    )
    decision_card: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Cached deterministic DecisionCard (serialized)",
    )

    model_config = ConfigDict(extra="forbid")

    def get_decision_card(self) -> DecisionCard:
        """
        Get or generate the DecisionCard.

        If cached in decision_card, reconstruct and return it.
        Otherwise generate deterministically from this packet.
        """
        if self.decision_card:
            try:
                return DecisionCard.from_dict(self.decision_card)
            except Exception:
                # Fall back to regeneration if cache is malformed.
                pass
        return DecisionCard.from_packet(self)

    def get_timeline(self) -> Optional[RunTimeline]:
        """Reconstruct RunTimeline from serialized data (if present)."""
        if self.run_timeline:
            try:
                return RunTimeline.from_artifact(self.run_timeline)
            except Exception:
                return None
        return None


def build_decision_packet(
    state: ExperimentState,
    run_record: RunRecord,
    *,
    timeline: Optional[RunTimeline] = None,
    include_card: bool = True,
) -> DecisionPacket:
    packet = DecisionPacket(
        run_id=run_record.run_id,
        parent_run_id=run_record.parent_run_id,
        run_record=run_record,
        policy_ir=state.get("ir"),
        simulation_results=state.get("simulation_results"),
        fabric_result=state.get("fabric_result"),
        evidence_ref=_resolve_evidence(state),
        uncertainty_ref=_resolve_uncertainty(state),
        governance_report_ref=_resolve_governance_report(state),
        feedback=state.get("feedback"),
        audit_trail=list(state.get("audit_trail") or []),
        run_timeline=timeline.to_artifact() if timeline else None,
        validation_trace=state.get("validation_trace"),
    )
    if include_card:
        card = DecisionCard.from_packet(packet)
        packet.decision_card = card.to_dict()
    return packet


def _resolve_evidence(state: ExperimentState) -> EvidenceBundleRef | None:
    value = state.get("fabric_result")
    if isinstance(value, FabricResult):
        return value.evidence_ref
    if isinstance(value, dict):
        try:
            return EvidenceBundleRef.model_validate(value.get("evidence_ref"))  # type: ignore[arg-type]
        except Exception:
            return None
    return None


def _resolve_uncertainty(state: ExperimentState) -> UncertaintyBoundsRef | None:
    value = state.get("uncertainty_ref")
    if isinstance(value, UncertaintyBoundsRef):
        return value
    if isinstance(value, dict):
        try:
            return UncertaintyBoundsRef.model_validate(value)
        except Exception:
            return None
    if isinstance(state.get("fabric_result"), FabricResult):
        return state["fabric_result"].uncertainty_ref  # type: ignore[index]
    return None


def _resolve_governance_report(state: ExperimentState) -> GovernanceReportRef | None:
    value = state.get("governance_report_ref")
    if isinstance(value, GovernanceReportRef):
        return value
    if isinstance(value, dict):
        try:
            return GovernanceReportRef.model_validate(value)
        except Exception:
            return None
    return None


def save_decision_packet(packet: DecisionPacket, base_dir: Path = Path("runs")) -> Path:
    warnings.warn(
        "save_decision_packet is deprecated; use polisyos.runtime.log_artifact instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    safe_base = Path(base_dir) if base_dir else Path("runs")
    output_dir = safe_base / "decision_packets"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = packet.model_dump(mode="json")
    path = output_dir / f"{packet.run_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return path

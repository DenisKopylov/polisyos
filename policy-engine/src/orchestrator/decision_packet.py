from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.orchestrator.run_record import RunRecord
from src.orchestrator.state import ExperimentState, GovernorFeedback
from src.policy_ir.contract import PolicyRequestIR


class DecisionPacket(BaseModel):
    """
    Итоговый артефакт прогона: IR + результаты + аудит + RunRecord.
    """

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    run_id: str
    parent_run_id: Optional[str] = None
    run_record: RunRecord

    policy_ir: Optional[PolicyRequestIR] = None
    simulation_results: Optional[Dict[str, Any]] = None
    feedback: Optional[GovernorFeedback] = None
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


def build_decision_packet(state: ExperimentState, run_record: RunRecord) -> DecisionPacket:
    return DecisionPacket(
        run_id=run_record.run_id,
        parent_run_id=run_record.parent_run_id,
        run_record=run_record,
        policy_ir=state.get("ir"),
        simulation_results=state.get("simulation_results"),
        feedback=state.get("feedback"),
        audit_trail=list(state.get("audit_trail") or []),
    )


def save_decision_packet(packet: DecisionPacket, base_dir: Path = Path("logs")) -> Path:
    output_dir = base_dir / "decision_packets"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = packet.model_dump()
    path = output_dir / f"{packet.run_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    return path

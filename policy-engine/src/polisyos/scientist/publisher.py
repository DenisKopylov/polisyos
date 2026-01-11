from __future__ import annotations

from polisyos.scientist.orchestrator.decision_packet import build_decision_packet
from polisyos.scientist.orchestrator.state import ExperimentState
from polisyos.scientist.orchestrator.run_record import build_run_record, ReproMode


def publish_decision(state: ExperimentState):
    """Placeholder publisher v2."""
    run_record = state.get("run_record") or build_run_record(
        run_id=state.get("run_id", "unknown"),
        parent_run_id=state.get("parent_run_id"),
        seed=0,
        repro_mode=ReproMode.FAST,
        generator={"name": "policy-engine", "version": "0.1.0"},
    )
    return build_decision_packet(state, run_record)

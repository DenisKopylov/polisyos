"""Candidate experiment phase persistence refuses incomplete owner composition."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
from polisyos.runtime.http.services.control.run_lifecycle import (
    AcquisitionRouteLoopAuthoritySink,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionCandidateExperimentPhaseReceipt,
)
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedPolicyScope,
)
from polisyos.runtime.quality.diagnostic_events import load_diagnostic_event_type_registry
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generation_cycle import LoopVOIDecision


def _hash(digit: str) -> str:
    return "sha256:" + digit * 64


def _ref(kind: str, digit: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=_hash(digit),
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256=_hash("f"),
    )


def _phase() -> AcquisitionCandidateExperimentPhaseReceipt:
    scope = CandidateUnpricedPolicyScope(
        tenant_id="tenant-a",
        cell_id="cell-a",
        run_id="run-a",
        source_job_id="source-a",
        design_problem_ref=_hash("1"),
        design_problem_basis_ref=_hash("2"),
        source_cycle_index=0,
        candidate_id="candidate-a",
        candidate_content_hash=_hash("3"),
        requirement_id="requirement-a",
        compiled_requirement_ref="compiled-requirement-a",
        candidate_digest=_hash("4"),
        planner_report_hash=_hash("5"),
        compiled_ref=_ref("runtime.compiled_recursive_generation_cycle", "6"),
        planner_report_ref=_ref("runtime.acquisition_planner_report", "7"),
        compiler_report_ref=_ref("runtime.data_requirement_compilation_report", "8"),
        configured_port_source_ref=_ref("runtime.quality.n7_configured_candidate_port_source", "9"),
    )
    return AcquisitionCandidateExperimentPhaseReceipt.model_validate(
        {
            "receipt_id": "action-a.requested",
            "tenant_id": "tenant-a",
            "cell_id": "cell-a",
            "run_id": "run-a",
            "source_job_id": "source-a",
            "route_id": _hash("a"),
            "action_generation": 1,
            "job_id": "action-a",
            "source_payload_ref": _hash("b"),
            "capability_manifest_ref": _hash("c"),
            "request_content_hash": _hash("d"),
            "policy_scope": scope,
            "policy_ref": _ref("runtime_quality.candidate_unpriced_acquisition_policy", "e"),
            "authority_decision_ref": _ref("runtime_quality.agent_action_authority_decision", "0"),
            "voi_decision": LoopVOIDecision(
                candidate_id="candidate-a",
                terminal_kind="human_decision_required",
                scheduler_action="reject",
                scheduler_reason="roi_below_threshold",
                priority=0.0,
                next_action="escalate",
                reason="roi_below_threshold",
            ),
            "coarse_phase": "requested",
            "receipt_phase": "requested",
            "recovery_state": "none",
            "generated_at": datetime(2026, 11, 4, tzinfo=UTC),
        }
    )


def test_empty_experiment_history_is_empty_and_requested_phase_requires_atomic_publish(
    tmp_path: Path,
) -> None:
    """A typed phase cannot become a head without the real source and PA2 owners."""
    database = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    artifact_store = FileSystemCAS(tmp_path / "cas").for_tenant("tenant-a", cell_id="cell-a")
    event_log = RuntimeDiagnosticEventLog(store=database, artifact_store=artifact_store)
    sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=artifact_store,
        event_log=event_log,
        control_store=database,
    )
    phase = _phase()

    assert (
        sink.experiment_action_outcomes(
            tenant_id=phase.tenant_id,
            cell_id=phase.cell_id,
            run_id=phase.run_id,
            source_job_id=phase.source_job_id,
            route_id=phase.route_id,
        )
        == ()
    )
    with pytest.raises(
        ValueError, match="candidate_experiment_requested_phase_requires_atomic_job_publish"
    ):
        sink.persist_experiment_phase(phase)
    assert sink.get_head(phase) is None
    assert event_log.list_events(run_id=phase.run_id, job_id=phase.job_id, limit=10) == []


def test_candidate_experiment_phase_event_is_registered_as_cas_authority() -> None:
    contract = load_diagnostic_event_type_registry().event_types[
        "polisyos.runtime.acquisition.candidate_experiment_phase.v1"
    ]
    assert contract.category == "acquisition_candidate_experiment_phase"
    assert contract.allowed_event_sources == ("polisyos.runtime.quality.acquisition_route_loop",)
    assert contract.authority_role == "runtime_authority"
    assert contract.payload_ref_policy == "cas_required"
    assert contract.phase_required is contract.producer_required is True
    assert contract.serious_no_sampling is True

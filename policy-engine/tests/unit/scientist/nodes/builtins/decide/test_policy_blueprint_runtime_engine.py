from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.governance.policy_spec import PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket
from polisyos.scientist.nodes.builtins.decide.policy_blueprint_runtime_engine import (
    _persist_policy_runtime_work_packet,
)
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    PolicyRuntimeEvaluationArtifact,
    PolicyRuntimeProvenance,
)
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    persist_policy_candidate_schema,
)


def _candidate(candidate_id: str) -> PolicyCandidateSchema:
    return PolicyCandidateSchema.from_trinity_bundle(
        TrinityBundle(
            problem_frame=ProblemFrame(
                problem_id=f"problem_{candidate_id}",
                domain=ProblemDomain.FISCAL,
            ),
            policy_spec=PolicySpec(policy_id=f"policy_{candidate_id}"),
            model_spec=ModelSpec(
                model_id=f"model_{candidate_id}",
                data_snapshot_ref="sha256:" + "1" * 64,
            ),
        ),
        candidate_id=candidate_id,
    )


def _runtime_artifact(
    candidate: PolicyCandidateSchema, fidelity: str
) -> PolicyRuntimeEvaluationArtifact:
    vector = PolicyEvaluationVector(
        candidate_id=candidate.candidate_id,
        feasible=True,
        metadata={"fidelity_observed": fidelity},
    )
    provenance = PolicyRuntimeProvenance(
        backend_kind="typed_work_packet_fixture",
        fidelity_mode=fidelity,
        promotable_source=False,
        notes=("Test fixture; no scientific draw loop is exercised.",),
    )
    return PolicyRuntimeEvaluationArtifact(
        simulation_metrics={"gdp_change": 0.2},
        simulation_results={"gdp_change": 0.2, "bootstrap": {"requested_draw_count": 64}},
        evaluation_vector=vector,
        fidelity=fidelity,
        provenance=provenance,
    )


def _initial_state(store: FileSystemCAS, candidate_ref, *, run_id: str) -> dict[str, Any]:
    return {
        "store": store,
        "policy_candidate_ref": candidate_ref,
        "pinned_input_signature": f"signature:{run_id}",
        "policy_runtime_work_identity": {
            "candidate_ref": candidate_ref,
            "run_id": run_id,
            "ticket_id": f"ticket:{run_id}",
            "candidate_hash": f"candidate-hash:{run_id}",
        },
    }


@pytest.mark.parametrize(
    ("fidelity", "stage_level", "stage_name"),
    [
        ("medium", 3, "funnel_L3_medium"),
        ("full", 4, "funnel_L4_full"),
    ],
)
def test_engine_persists_typed_work_packet_with_candidate_and_result_cas_lineage(
    tmp_path: Path,
    fidelity: str,
    stage_level: int,
    stage_name: str,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate("candidate_engine_positive")
    candidate_ref = persist_policy_candidate_schema(store, candidate)

    packet_ref, unavailable_reason = _persist_policy_runtime_work_packet(
        initial_state=_initial_state(store, candidate_ref, run_id="run_engine_positive"),
        fidelity=fidelity,
        evaluation_attempt_id=f"attempt:{fidelity}",
        runtime_artifact=_runtime_artifact(candidate, fidelity),
    )

    assert unavailable_reason is None
    assert packet_ref is not None
    packet = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(store.get_bytes(packet_ref.artifact_id))
    )
    assert packet.run_id == "run_engine_positive"
    assert packet.ticket_id == "ticket:run_engine_positive"
    assert packet.candidate_hash == "candidate-hash:run_engine_positive"
    assert packet.candidate_ref.artifact_id == candidate_ref.artifact_id
    assert (packet.stage_level, packet.stage_name, packet.fidelity) == (
        stage_level,
        stage_name,
        fidelity,
    )
    assert packet.input_signature == "signature:run_engine_positive"
    assert packet.requested_draw_count == 64
    assert packet.draw_execution_status == "not_instrumented"
    assert packet.attempted_draw_count is None
    assert packet.successful_draw_count is None
    # This producer writes through Core FileSystemCAS, so its refs select the
    # default manifest view. Verify those persisted manifests and their edges
    # instead of treating a missing IR profile selector as producer evidence.
    assert packet.source_result_ref.manifest_profile_sha256 is None
    assert packet_ref.manifest_profile_sha256 is None

    result_payload = from_canonical_bytes(store.get_bytes(packet.source_result_ref.artifact_id))
    assert result_payload["candidate_id"] == candidate.candidate_id
    assert result_payload["metadata"]["fidelity_observed"] == fidelity
    result_manifest = store.get_manifest(packet.source_result_ref)
    packet_manifest = store.get_manifest(packet_ref)
    assert result_manifest.artifact_id == packet.source_result_ref.artifact_id
    assert packet_manifest.artifact_id == packet_ref.artifact_id
    assert result_manifest.kind == "scientist.policy_evaluation_vector"
    assert packet_manifest.kind == "scientist.search.funnel_native_work_packet"
    assert any(
        item.artifact_id == candidate_ref.artifact_id and item.role == "candidate"
        for item in result_manifest.inputs
    )
    assert {(str(item.artifact_id), item.role) for item in packet_manifest.inputs} == {
        (str(candidate_ref.artifact_id), "candidate"),
        (str(packet.source_result_ref.artifact_id), "source_result"),
    }


def test_engine_rejects_candidate_ref_drift_before_any_cas_write(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    selected_candidate = _candidate("candidate_engine_selected")
    other_candidate = _candidate("candidate_engine_other")
    selected_ref = persist_policy_candidate_schema(store, selected_candidate)
    other_ref = persist_policy_candidate_schema(store, other_candidate)
    initial_state = _initial_state(store, selected_ref, run_id="run_engine_mismatch")
    initial_state["policy_runtime_work_identity"]["candidate_ref"] = other_ref
    artifacts_before = _artifact_id_snapshot(store)

    packet_ref, unavailable_reason = _persist_policy_runtime_work_packet(
        initial_state=initial_state,
        fidelity="full",
        evaluation_attempt_id="attempt:mismatched-candidate",
        runtime_artifact=_runtime_artifact(selected_candidate, "full"),
    )

    assert packet_ref is None
    assert unavailable_reason == "candidate_ref_unavailable_or_mismatched"
    assert _artifact_id_snapshot(store) == artifacts_before


def test_engine_does_not_publish_selection_as_an_executed_work_packet(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    candidate = _candidate("candidate_engine_selection")
    candidate_ref = persist_policy_candidate_schema(store, candidate)
    artifacts_before = _artifact_id_snapshot(store)

    packet_ref, unavailable_reason = _persist_policy_runtime_work_packet(
        initial_state=_initial_state(store, candidate_ref, run_id="run_engine_selection"),
        fidelity="selection",
        evaluation_attempt_id="attempt:selection",
        runtime_artifact=_runtime_artifact(candidate, "selection"),
    )

    assert packet_ref is None
    assert unavailable_reason == "unsupported_fidelity"
    assert _artifact_id_snapshot(store) == artifacts_before


def _artifact_id_snapshot(store: FileSystemCAS) -> tuple[str, ...]:
    return tuple(sorted(str(artifact_id) for artifact_id in store.iter_artifact_ids()))

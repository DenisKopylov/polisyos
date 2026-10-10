from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts import ensure_ir_artifact_store
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import ArtifactIntegrityError, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.artifacts.io import get_json_artifact, put_json_artifact
from polisyos.scientist.methods.search.funnel.types import FunnelExecutedWorkPacket
from polisyos.scientist.nodes.builtins.decide.policy_runtime_support import (
    persist_funnel_executed_work_packet,
)


def test_work_packet_cas_round_trip_binds_selected_inputs_and_refuses_tampering(
    cas_store,
) -> None:
    """Persisted work packets retain typed lineage and are read through CAS integrity checks."""
    candidate_ref = cas_store.put_json(
        {"candidate_id": "candidate-artifact-boundary"},
        PutOptions(
            kind="scientist.policy_design.candidate",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyCandidate", version="1.0"),
        ),
    )
    result_ref = cas_store.put_json(
        {"candidate_id": "candidate-artifact-boundary", "feasible": True},
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(name="tests.PolicyEvaluationVector", version="1.0"),
        ),
    )
    packet = FunnelExecutedWorkPacket(
        run_id="run-artifact-boundary",
        ticket_id="ticket-artifact-boundary",
        candidate_hash="candidate-content-hash",
        candidate_ref=candidate_ref,
        stage_level=3,
        stage_name="funnel_L3_medium",
        fidelity="medium",
        evaluation_attempt_id="attempt-artifact-boundary",
        observed_at=datetime(2026, 10, 10, tzinfo=UTC),
        backend_kind="production",
        source_result_ref=result_ref,
        requested_draw_count=64,
        input_signature="caller-input-signature",
    )

    packet_ref = persist_funnel_executed_work_packet(cas_store, packet)
    manifest = cas_store.get_manifest(packet_ref)
    restored = FunnelExecutedWorkPacket.model_validate(
        from_canonical_bytes(cas_store.get_bytes(packet_ref))
    )

    assert manifest.kind == "scientist.search.funnel_native_work_packet"
    assert manifest.artifact_schema == SchemaInfo(
        name="polisyos.scientist.search.FunnelExecutedWorkPacket", version="1.0"
    )
    assert manifest.producer is not None
    assert manifest.producer.component == "scientist.policy_runtime_work_packet"
    assert manifest.producer.version == "1.0.0"
    assert {item.role: str(item.artifact_id) for item in manifest.inputs} == {
        "candidate": str(candidate_ref.artifact_id),
        "source_result": str(result_ref.artifact_id),
    }
    assert restored == packet
    assert restored.candidate_ref.manifest_profile_sha256 == candidate_ref.manifest_profile_sha256
    assert restored.source_result_ref.manifest_profile_sha256 == result_ref.manifest_profile_sha256

    # The core producer's default-view ref is not a selected-profile attestation. Exercise
    # selection through the typed IR writer, which returns the exact non-default view selector.
    ir_store = ensure_ir_artifact_store(cas_store)
    selected_ref = put_json_artifact(
        ir_store,
        packet,
        kind="scientist.search.funnel_native_work_packet",
        schema_name="tests.SelectedFunnelExecutedWorkPacketView",
        schema_version="1.0",
    )
    assert selected_ref["manifest_profile_sha256"] is not None
    selected_manifest = ir_store.get_manifest(selected_ref)
    assert selected_manifest.artifact_schema == SchemaInfo(
        name="tests.SelectedFunnelExecutedWorkPacketView", version="1.0"
    )
    assert (
        FunnelExecutedWorkPacket.model_validate(get_json_artifact(ir_store, selected_ref)) == packet
    )

    blob_path, _manifest_path = cas_store._paths(packet_ref.artifact_id)
    blob_path.write_bytes(blob_path.read_bytes() + b"tampered")
    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        cas_store.get_bytes(packet_ref)
    with pytest.raises(ArtifactIntegrityError, match="Blob sha256 mismatch"):
        get_json_artifact(ir_store, selected_ref)

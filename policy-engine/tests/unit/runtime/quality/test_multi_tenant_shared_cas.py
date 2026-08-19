from __future__ import annotations

import json

import pytest

from polisyos.core.artifacts.ownership import ArtifactOwnershipError
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.runtime.quality.approval import (
    build_production_approval_packet,
    persist_production_approval_packet,
)
from polisyos.runtime.quality.public_export import build_public_export_bundle
from tests._helpers.hds_quality import authority_envelope_for, sha


def _scorecard_payload(*, scorecard_ref: str, runtime_ref: str) -> dict[str, object]:
    return {
        "schema_version": "policyos.quality_scorecard.v1",
        "generated_at": "2026-05-15T09:30:00+00:00",
        "canary_kind": "production",
        "job_id": "job-tenant-a",
        "run_id": "run-tenant-a",
        "execution_status": "completed",
        "quality_status": "pass",
        "performance_status": "pass",
        "approval_state": "approval_ready",
        "overall_score": 1,
        "stage_scores": {"ops": 1},
        "quality_gates": [],
        "blocking_quality_failures": [],
        "warnings": [],
        "evidence_refs": {
            "quality_scorecard": scorecard_ref,
            "policy_grounding_matrix": runtime_ref,
        },
        "quality_scorecard_ref": scorecard_ref,
        "scorecard_identity_ref": scorecard_ref,
        "scorecard_identity_verified": True,
    }


def test_shared_cas_blocks_cross_tenant_runtime_lineage_scorecard_approval_and_export_reads(
    tmp_path,
) -> None:
    shared = FileSystemCAS(tmp_path / "cas")
    tenant_a = shared.for_tenant("tenant-a", cell_id="cell-a")
    tenant_b = shared.for_tenant("tenant-b", cell_id="cell-b")
    runtime_opts = PutOptions(
        kind="runtime_quality.policy_grounding_matrix",
        media_type="application/json",
    )

    identical_payload = {"status": "pass", "public_summary": "same materialized finding"}
    tenant_a_identical_ref = tenant_a.put_json(identical_payload, runtime_opts)

    assert tenant_b.has(tenant_a_identical_ref.artifact_id) is False
    with pytest.raises(ArtifactOwnershipError):
        tenant_b.get_bytes(tenant_a_identical_ref.artifact_id)

    tenant_b_identical_ref = tenant_b.put_json(identical_payload, runtime_opts)

    assert tenant_b_identical_ref.artifact_id == tenant_a_identical_ref.artifact_id
    assert tenant_b.get_bytes(tenant_b_identical_ref.artifact_id) == tenant_a.get_bytes(
        tenant_a_identical_ref.artifact_id
    )

    runtime_ref = tenant_a.put_json(
        {"status": "pass", "tenant_private_fact": "tenant-a-only"},
        runtime_opts,
    )
    descendant_ref = tenant_a.put_json(
        {"status": "pass", "derived_from": str(runtime_ref.artifact_id)},
        PutOptions(
            kind="runtime_quality.lineage_descendant",
            media_type="application/json",
            inputs=[{"artifact_id": str(runtime_ref.artifact_id), "role": "runtime_ref"}],
        ),
    )

    with pytest.raises(ArtifactOwnershipError):
        tenant_b.put_json(
            {"status": "pass", "derived_from": str(runtime_ref.artifact_id)},
            PutOptions(
                kind="runtime_quality.governed_lineage_descendant",
                media_type="application/json",
                inputs=[
                    {"artifact_id": str(runtime_ref.artifact_id), "role": "runtime_ref"}
                ],
            ),
        )

    pending_scorecard_ref = sha("4")
    scorecard_payload = _scorecard_payload(
        scorecard_ref=pending_scorecard_ref,
        runtime_ref=str(runtime_ref.artifact_id),
    )
    scorecard_ref = tenant_a.put_json(
        scorecard_payload,
        PutOptions(kind="runtime_quality.quality_scorecard", media_type="application/json"),
    )
    approval_packet = build_production_approval_packet(
        scorecard=_scorecard_payload(
            scorecard_ref=str(scorecard_ref.artifact_id),
            runtime_ref=str(runtime_ref.artifact_id),
        )
    )
    approval_ref = persist_production_approval_packet(
        approval_packet,
        store=tenant_a,
    ).approval_packet_ref
    public_export = build_public_export_bundle(
        run_id="run-tenant-a",
        artifacts={
            "summary": "Public summary",
            "scorecard_ref": str(scorecard_ref.artifact_id),
            "approval_packet_ref": str(approval_ref.artifact_id),
        },
        authority_envelopes=[],
    )
    public_export_ref = tenant_a.put_json(
        public_export,
        PutOptions(kind="runtime_quality.public_export", media_type="application/json"),
    )

    tenant_a_only_refs = {
        "runtime ref": runtime_ref,
        "lineage descendant": descendant_ref,
        "scorecard": scorecard_ref,
        "approval packet": approval_ref,
        "public export": public_export_ref,
    }
    for artifact_name, artifact_ref in tenant_a_only_refs.items():
        assert tenant_a.has(artifact_ref.artifact_id), artifact_name
        assert tenant_b.has(artifact_ref.artifact_id) is False, artifact_name
        with pytest.raises(ArtifactOwnershipError):
            tenant_b.get_bytes(artifact_ref.artifact_id)


def test_public_export_redacts_tenant_private_runtime_refs_from_payload_and_projection() -> None:
    raw_runtime_ref = sha("8")
    raw_scorecard_ref = "cas://sha256/" + "9" * 64
    raw_event_ref = sha("e")
    nested_runtime_ref = sha("a")
    nested_key_ref = sha("b")
    top_level_key_ref = sha("c")
    derived_decision_ref = sha("d")
    authority_envelope = authority_envelope_for(
        report_key="policy_grounding_matrix",
        ref_key="policy_grounding_matrix_ref",
        ref_value=raw_runtime_ref,
    )
    authority_envelope["runtime_event_ref"] = raw_event_ref

    public_bundle = build_public_export_bundle(
        run_id="run-public-tenant-a",
        artifacts={
            "audit": {
                "runtime_quality_refs": {
                    "policy_grounding_matrix_ref": raw_runtime_ref,
                },
                "lineage": {"descendant_ref": raw_scorecard_ref},
                "future_extension": [
                    {"opaque_value": nested_runtime_ref},
                    {"opaque_mapping": {nested_key_ref: {"label": "public"}}},
                ],
                "public_source_refs": ["norm.ua.credit_eligibility"],
                "authority_boundary": {
                    "boundary_id": derived_decision_ref,
                    "authoritative_for": ["publication"],
                    "may_not_use_for": ["scorecard_authority"],
                    "source_authority": "runtime_quality",
                    "posture": "projection_only",
                    "rule_version_refs": ["test-rule-v1"],
                },
            },
            top_level_key_ref: {"summary": "Public summary"},
        },
        authority_envelopes=[authority_envelope],
    )

    rendered = json.dumps(public_bundle, sort_keys=True)
    assert raw_runtime_ref not in rendered
    assert raw_scorecard_ref not in rendered
    assert raw_event_ref not in rendered
    assert nested_runtime_ref not in rendered
    assert nested_key_ref not in rendered
    assert top_level_key_ref not in rendered
    assert derived_decision_ref not in rendered
    assert "norm.ua.credit_eligibility" in rendered

    projection = public_bundle["semantic_audit"]["authority_projections"][0]
    assert "runtime_event_ref" not in projection
    assert projection["runtime_event_ref_fingerprint"].startswith("sha256:")
    redacted_runtime_ref = public_bundle["artifacts"]["audit"]["runtime_quality_refs"][
        "policy_grounding_matrix_ref"
    ]
    assert redacted_runtime_ref["redacted"] is True
    assert redacted_runtime_ref["reason"] == "tenant_private_ref"
    redacted_nested_ref = public_bundle["artifacts"]["audit"]["future_extension"][0][
        "opaque_value"
    ]
    assert redacted_nested_ref["redacted"] is True
    assert redacted_nested_ref["reason"] == "tenant_private_ref"

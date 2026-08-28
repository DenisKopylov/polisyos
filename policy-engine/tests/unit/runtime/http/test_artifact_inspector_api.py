from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import PutOptions, SchemaInfo
from polisyos.core.artifacts.manifest import ProducerInfo
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.pdc import AuthorityBoundary
from polisyos.runtime.quality.authority import authority_surface_decision
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyAuthoritySurfacePacket,
    EvalSafetyCertificate,
    EvalSafetyMetricsProjection,
    EvalSafetySurfaceDisposition,
    evaluation_safety_metrics_projection_identity,
)


def test_eval_safety_projection_is_informational_only(runtime_api_env) -> None:
    runtime_context = runtime_api_env["app"].state.runtime_api_ctx
    store = runtime_context.store
    boundary = AuthorityBoundary(
        boundary_id="eval-safety-artifact-inspector-v1",
        authoritative_for=["runtime_closeout_authority", "dashboard_display"],
        may_not_use_for=[
            "attempted_evaluation_admission",
            "promotion",
            "evaluation_execution",
        ],
        source_authority="deterministic_producer",
        posture="advisory",
        rule_version_refs=["policyos.runtime.eval_safety.metrics_projection.v1"],
        evidence_kind="derivation",
        decision_grade="descriptive_only",
        known_limits=["informational_projection_only"],
    )
    denied_uses = (
        "attempted_evaluation_admission",
        "promotion",
        "evaluation_execution",
    )
    packet = EvalSafetyAuthoritySurfacePacket(
        schema_version="policyos.runtime.eval_safety_surface_packet.v1",
        boundary=boundary,
        surfaces={
            surface: EvalSafetySurfaceDisposition(
                surface=surface,
                purpose=(
                    "dashboard_display"
                    if surface == "dashboard"
                    else "runtime_closeout_authority"
                ),
                status="allow",
                authority_result="informational_projection_only",
                consumed_boundary_id="eval-safety-artifact-inspector-v1",
                projection_scope="faithful_eval_safety_projection",
                may_not_use_for=denied_uses,
            )
            for surface in ("run", "artifact", "lineage", "dashboard")
        },
    )
    projection = EvalSafetyMetricsProjection(
        attempt_disposition="passed",
        selected_decision_artifact_refs=(),
        reconciled_decision_artifact_refs=(),
        unreconciled_decision_artifact_refs=(),
        conflicting_decision_artifact_refs=(),
        denominator_decision_ids=(),
        unsafe_attempt_blocked_count=0,
        near_miss_count=0,
        near_miss_classification_status="complete",
        unclassified_blocked_decision_ids=(),
        reconciliation_status="complete",
        generated_at=datetime(2026, 8, 28, 8, 0, tzinfo=UTC),
        source_event_refs=(),
        authority_boundary=boundary,
        authority_surface_packet=packet,
    )
    identity = evaluation_safety_metrics_projection_identity("artifact")
    ref = store.put_json(
        projection.model_dump(mode="json"),
        PutOptions(
            kind=identity.kind,
            media_type="application/json",
            schema=SchemaInfo(
                name=identity.schema_name,
                version=identity.schema_version,
            ),
        ),
    )
    store.record_artifact_owner(
        ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
        writer="eval-safety-artifact-inspector-test",
    )
    run_id = "R_eval-safety-artifact-inspector"
    run = RunContext.start(
        store,
        build_default_registry_bundle(store).bundle_ref,
        producer=ProducerInfo(
            component="polisyos.runtime.http.control.evaluation_safety",
            version="1.0.0",
        ),
        run_dir=runtime_context.core_runs_root / run_id,
        run_id=run_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=runtime_api_env["cell_a"],
    )
    run.add_output(ref)
    run.finalize(status="completed")
    runtime_context.run_index.refresh(force=True)

    response = runtime_api_env["client"].get(
        f"/api/v1/artifacts/{ref.artifact_id}/content"
    )

    assert response.status_code == 200, response.text
    preview = response.json()["artifact"]["preview"]
    assert EvalSafetyMetricsProjection.model_validate(preview) == projection
    denied = authority_surface_decision(
        preview,
        surface="artifact",
        purpose="promotion",
        artifact_store=store,
        artifact_id=ref.artifact_id,
        require_cas_integrity=True,
    )
    assert denied.blocking
    assert "promotion" in projection.authority_boundary.may_not_use_for
    with pytest.raises(ValidationError):
        EvalSafetyCertificate.model_validate(preview)


def test_artifact_manifest_endpoint_returns_canonical_metadata(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["workflow_report_artifact_id"]
    response = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert response.status_code == 200

    artifact = response.json()["artifact"]
    assert artifact["artifact_id"] == artifact_id
    assert artifact["kind"] == "scientist.workflow_report"
    assert artifact["schema_name"] == "scientist.workflow_report"


def test_artifact_content_preview_enforces_max_bytes(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["binary_artifact_id"]
    response = client.get(f"/api/v1/artifacts/{artifact_id}/content?max_bytes=1024")
    assert response.status_code == 200

    preview = response.json()["artifact"]
    assert preview["artifact_id"] == artifact_id
    assert preview["truncated"] is True
    assert preview["max_bytes"] == 1024

    secret = client.get(f"/api/v1/artifacts/{runtime_api_env['secret_artifact_id']}/content")
    assert secret.status_code == 409
    assert secret.json()["code"] == "authority_surface_admission_blocked"


def test_artifact_lineage_and_schema_endpoints(runtime_api_env) -> None:
    client = runtime_api_env["client"]
    artifact_id = runtime_api_env["workflow_report_artifact_id"]

    lineage = client.get(f"/api/v1/artifacts/{artifact_id}/lineage")
    assert lineage.status_code == 200
    lineage_payload = lineage.json()["lineage"]
    assert lineage_payload["total_nodes"] >= 1
    assert artifact_id in lineage_payload["root_artifact_ids"]

    schema = client.get(f"/api/v1/artifacts/{artifact_id}/schema")
    assert schema.status_code == 200
    schema_payload = schema.json()["schema"]
    assert schema_payload["schema_name"] == "scientist.workflow_report"

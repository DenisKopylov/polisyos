"""Post-source evidence intake through the owned production HTTP route."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from polisyos.core import artifacts, canon
from polisyos.core.security.cell import CellSpec, CellTier, TenantSpec
from polisyos.core.security.registry import CellRegistry
from polisyos.runtime.http.app import create_runtime_api_app
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.dependencies import build_runtime_api_context
from polisyos.runtime.http.services.control import generation_cycle as bridge
from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
from tests.unit.runtime.http.test_control_service_di import (
    _fixture_claims,
    _signed_generation_evidence,
)
from tests.unit.runtime.http.test_control_service_di import (
    test_process_nl_job_enters_persisted_tenant_scope as _worker_example,
)
from tests.unit.runtime.http.test_runtime_api_authz import _CaptureOPA, _IdentityProvider


@pytest.fixture(scope="module")
def completed_worker(tmp_path_factory):
    """Execute the actual default worker before any normative signature is available."""
    tmp_path = tmp_path_factory.mktemp("pa1-temporal-worker")
    captured = {}
    original_process = ControlPlaneService._process_control_job
    original_close = ControlPlaneService.close

    def capture(self, job):
        captured.update(service=self, job_id=job.job_id)
        return original_process(self, job)

    with pytest.MonkeyPatch.context() as patches:
        patches.setattr(ControlPlaneService, "_process_control_job", capture)
        patches.setattr(ControlPlaneService, "close", lambda self: None)
        asyncio.run(_worker_example(patches, tmp_path, "missing"))
    service = captured["service"]
    record = service.get_job_status(captured["job_id"])
    compiled = bridge.CompiledRecursiveGenerationCycleRun.model_validate(
        canon.from_canonical_bytes(
            service._artifact_store.get_bytes(
                artifacts.ArtifactID.model_validate(
                    record.progress["compiled_recursive_generation_cycle_ref"]
                )
            )
        )
    )
    try:
        yield service, record, compiled
    finally:
        original_close(service)


def _secure_client(service):
    from fastapi.testclient import TestClient

    registry = CellRegistry()
    # The existing worker fixture uses stable non-UUID scope identifiers. Provision
    # that explicit test registry; the real route still resolves exact run ownership.
    cell = CellSpec(tier=CellTier.SHARED, region="test").model_copy(
        update={"cell_id": "cell-fixture"}
    )
    registry.register_cell(cell)
    registry.register_tenant(
        TenantSpec(name="fixture", region="test").model_copy(update={"tenant_id": "tenant-fixture"}), cell.cell_id
    )
    registry.register_tenant(
        TenantSpec(name="other", region="test").model_copy(update={"tenant_id": "tenant-other"}), cell.cell_id
    )
    opa = _CaptureOPA()
    context = build_runtime_api_context(
        cas_root=service._cas_root, core_runs_root=service._core_runs_root
    )
    context.store.close()
    context = replace(context, store=service._artifact_store)
    app = create_runtime_api_app(
        cas_root=service._cas_root,
        core_runs_root=service._core_runs_root,
        enable_security_middlewares=True,
        identity_provider=_IdentityProvider({
            "fixture-token": _fixture_claims(),
            "permissionless-token": _fixture_claims().model_copy(update={"roles": frozenset()}),
            "foreign-token": _fixture_claims().model_copy(update={"tenant_id": "tenant-other"}),
        }),
        cell_registry=registry,
        opa_client=opa,
        authz_enforce=True,
        normative_authority_trust=service._normative_authority_trust,
        container_overrides=RuntimeContainerOverrides(
            control_service=service,
            runtime_api_context=context,
            decision_validity_service=service._epoch_claim_lifecycle_bridge.completed_batches,
        ),
    )
    return TestClient(app), opa


def test_post_source_signature_advances_both_current_job_readers(completed_worker, monkeypatch):
    service, before, compiled = completed_worker
    assert before.progress["normative_disposition"]["authorization_status"] == "blocked"
    original_progress = service._control_store.get_job(before.job_id).progress
    signers = {}
    original_sign = service._artifact_store.sign_artifact

    def capture_signer(artifact_id, signer, **kwargs):
        signers[kwargs["signer_identity"]] = signer
        return original_sign(artifact_id, signer, **kwargs)

    monkeypatch.setattr(service._artifact_store, "sign_artifact", capture_signer)
    evidence = _signed_generation_evidence(service, compiled, fault="authorized")
    monkeypatch.setattr(service, "close", lambda: None)
    client, opa = _secure_client(service)
    with client:
        response = client.post(
            f"/api/v1/control/runs/{before.run_id}/normative-evidence",
            headers={"Authorization": "Bearer fixture-token", "X-Cell-Id": "cell-fixture"},
            json={"job_id": before.job_id, "expected_prior_head_ref": None, "evidence": evidence},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        currents = (
            service.get_job_status(before.job_id),
            service.get_latest_job_for_run(before.run_id),
        )
        # The semantic property precedes every reference/receipt marker assertion.
        for current in currents:
            assert current.progress["normative_disposition"]["authorization_status"] == "authorized"
            assert current.progress["normative_disposition"]["ranked_recommendations"]
        assert payload["status"] == "admitted"
        head_ref = payload["head_ref"]
        assert head_ref
        assert any("normative_evidence" in item.resource_kind for item in opa.inputs)
        for current in currents:
            assert current.progress["normative_head_ref"] == head_ref
        assert service._control_store.get_job(before.job_id).progress == original_progress
        head = bridge.NormativeGenerationHead.model_validate(
            canon.from_canonical_bytes(
                service._artifact_store.get_bytes(artifacts.ArtifactID.model_validate(head_ref))
            )
        )
        assert head.job_id == before.job_id
        assert head.run_id == before.run_id
        assert head.compiled_run_ref == before.progress["compiled_recursive_generation_cycle_ref"]
        assert head.evaluated_at <= datetime.now(UTC)

        body = {"job_id": before.job_id, "expected_prior_head_ref": None, "evidence": evidence}
        headers = {"Authorization": "Bearer fixture-token", "X-Cell-Id": "cell-fixture"}
        path = f"/api/v1/control/runs/{before.run_id}/normative-evidence"
        conflict = client.post(path, headers=headers, json=body)
        assert conflict.status_code == 409, conflict.text
        assert conflict.json()["status"] == "conflict"
        assert conflict.json()["head_ref"] == head_ref

        # Sign a source-substituted authorization with the same real fixture signer.
        # IDs, schema markers, frontier, and signature validity all remain intact.
        from polisyos.runtime.quality.design_axes import value_choice_provenance as s8

        node, refs = next(iter(evidence["by_node"].items()))
        authorization = s8.NormativeAuthorizationRecordV2.model_validate(
            canon.from_canonical_bytes(service._artifact_store.get_bytes(
                artifacts.ArtifactID.model_validate(refs["authorization_ref"])
            ))
        )
        substituted = authorization.model_copy(update={
            "generation_binding": authorization.generation_binding.model_copy(
                update={"source_run_ref": "sha256:" + "e" * 64}
            )
        })
        substituted_ref = service._artifact_store.put_json(
            substituted.model_dump(mode="json"),
            artifacts.PutOptions(
                kind=s8.NORMATIVE_AUTHORIZATION_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=s8.NORMATIVE_AUTHORIZATION_KIND,
                    version=s8.NORMATIVE_GENERATION_AUTHORIZATION_SCHEMA_VERSION,
                ),
            ),
        )
        original_sign(substituted_ref.artifact_id, signers[authorization.authorizer_identity],
                      signer_identity=authorization.authorizer_identity)
        wrong_evidence = {"by_node": {node: {**refs, "authorization_ref": str(substituted_ref.artifact_id)}}}
        refused = client.post(path, headers=headers, json={
            **body, "expected_prior_head_ref": head_ref, "evidence": wrong_evidence,
        })
        assert refused.status_code == 422, refused.text
        assert refused.json()["status"] == "refused"
        attempted = service._current_normative_generation_projection(
            disposition_ref=refused.json()["attempted_disposition_ref"],
            compiled_run_ref=head.compiled_run_ref,
            evaluated_at=datetime.now(UTC),
        )
        assert attempted["authorization_status"] == "blocked"
        assert attempted["ranked_recommendations"] == []
        assert attempted["leaf_dispositions"][node]["decision_request"]["reason_codes"] == [
            "p20_normative_generation_binding_mismatch"
        ]
        assert refused.json()["head_ref"] == head_ref
        assert refused.json()["job"]["progress"]["normative_disposition"]["authorization_status"] == "authorized"
        events = service._control_store._fetchall(
            "SELECT event_type, payload_json FROM control_job_events WHERE job_id = ? AND event_type LIKE 'normative_evidence_%' ORDER BY event_id",
            (before.job_id,),
        )
        assert [row[0] for row in events] == [
            "normative_evidence_admitted", "normative_evidence_conflict", "normative_evidence_refused"
        ]
        assert json.loads(events[-1][1])["attempted_disposition_ref"] == refused.json()["attempted_disposition_ref"]

        for token in ("permissionless-token", "foreign-token"):
            denied = client.post(path, headers={**headers, "Authorization": f"Bearer {token}"}, json=body)
            assert denied.status_code == 403, denied.text
            expected_code = "action_permission_denied" if token.startswith("permissionless") else "authorization_binding_run_tenant_mismatch"
            assert denied.json()["code"] == expected_code
        wrong_job = client.post(path, headers=headers, json={**body, "job_id": "other-job"})
        assert wrong_job.status_code == 400
        for extra in ({"compiled_run_ref": head.compiled_run_ref}, {"trust": {}}):
            malformed = client.post(path, headers=headers, json={**body, **extra})
            assert malformed.status_code == 422
        malformed = client.post(path, headers=headers, json={**body, "expected_prior_head_ref": "not-a-ref"})
        assert malformed.status_code == 422
        assert service._control_store.get_normative_evidence_head(before.job_id)["head_ref"] == head_ref
        assert service._control_store.get_job(before.job_id).progress == original_progress


def _another_completed_job(service, before, *, job_id):
    service._control_store.create_job(
        job_id=job_id, kind="natural_language_run", run_id=before.run_id, pipeline_id=None,
        requested_execution_profile=None, effective_execution_profile="dev", policy_flags={},
        capability_manifest_ref=None, payload_ref=None, submitted_by=None,
    )
    # Each clone is explicitly newer; the existing store has second-resolution clocks.
    service._control_store._execute(
        "UPDATE control_jobs SET created_at = ? WHERE job_id = ?",
        (datetime.now(UTC).isoformat(), job_id),
    )
    service._control_store.complete_job(
        job_id=job_id, run_id=before.run_id, progress={
            key: value for key, value in before.progress.items()
            if key not in {"normative_head_ref", "normative_head_strangle_receipt"}
        },
    )


@pytest.mark.parametrize(
    "field", [*bridge.NormativeGenerationHead.model_fields, "missing_cas", "manifest_epoch"]
)
def test_current_head_replays_all_source_bindings_and_preserves_refusal_frontier(
    completed_worker, field
):
    service, before, compiled = completed_worker
    job_id = "zz-head-tamper-" + field
    _another_completed_job(service, before, job_id=job_id)
    evidence = _signed_generation_evidence(service, compiled, fault="authorized")
    result = service.submit_normative_evidence(
        run_id=before.run_id,
        submission=bridge.NormativeEvidenceSubmissionRequest(
            job_id=job_id, expected_prior_head_ref=None, evidence=evidence,
        ),
    )
    assert result.status == "admitted"
    assert result.job.progress["normative_disposition"]["authorization_status"] == "authorized"
    event = service._control_store.get_normative_evidence_head(job_id)
    head = canon.from_canonical_bytes(service._artifact_store.get_bytes(
        artifacts.ArtifactID.model_validate(result.head_ref)
    ))
    if field in {"schema_version", "job_id", "run_id"}:
        head[field] = "foreign"
    elif field in {"compiled_run_ref", "previous_head_ref"}:
        head[field] = "sha256:" + "c" * 64
    elif field == "disposition_ref":
        head[field] = before.progress["normative_disposition_ref"]
    elif field == "evidence":
        head[field] = {"by_node": {}}
    elif field == "evaluated_at":
        head[field] = "2026-01-01T00:00:00Z"
    elif field == "strangle_receipt":
        head[field]["original_disposition_ref"] = "sha256:" + "d" * 64
    elif field not in {"missing_cas", "manifest_epoch"}:
        raise AssertionError(f"head field needs a decisive mutation: {field}")
    if field == "manifest_epoch":
        # Equal decoded instant, distinct stored bytes: CAS otherwise reuses the
        # already correct manifest and no epoch property has actually been broken.
        head["evaluated_at"] = datetime.fromisoformat(head["evaluated_at"]).isoformat()
        assert bridge.NormativeGenerationHead.model_validate(head) == bridge.load_normative_generation_head(
            service._artifact_store, result.head_ref
        )
    if field == "missing_cas":
        corrupt_ref = "sha256:" + "e" * 64
    else:
        corrupt = service._artifact_store.put_json(
            head, artifacts.PutOptions(
                kind=bridge.NORMATIVE_GENERATION_HEAD_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(
                    name=bridge.NORMATIVE_GENERATION_HEAD_KIND,
                    version=("novel-epoch" if field == "manifest_epoch" else bridge.NORMATIVE_GENERATION_HEAD_SCHEMA),
                ),
            ),
        )
        corrupt_ref = str(corrupt.artifact_id)
    # Event/CAS corruption probe, never an admission or a production policy fixture.
    service._control_store.append_event(
        job_id=job_id, event_type="normative_evidence_admitted",
        payload={**event, "head_ref": corrupt_ref},
    )
    source_fronts = {
        node.node_ref: {name: list(ids) for name, ids in node.cycle_run.fronts.candidate_ids_by_front().items()}
        for node in compiled.recursive_run.leaf_nodes
    }
    for current in (service.get_job_status(job_id), service.get_latest_job_for_run(before.run_id)):
        disposition = current.progress["normative_disposition"]
        assert disposition["authorization_status"] == "blocked"
        assert disposition["ranked_recommendations"] == []
        assert current.progress["normative_head_limitation"]
        assert {node: item["candidate_fronts"] for node, item in disposition["leaf_dispositions"].items()} == source_fronts
        assert all(item["decision_request"] is not None for item in disposition["leaf_dispositions"].values())


def test_current_head_survives_shared_progress_copy_and_refuses_owned_source_rebind(
    completed_worker, monkeypatch
):
    service, before, compiled = completed_worker
    job_id = "progress-copy"
    _another_completed_job(service, before, job_id=job_id)
    evidence = _signed_generation_evidence(service, compiled, fault="authorized")
    result = service.submit_normative_evidence(
        run_id=before.run_id,
        submission=bridge.NormativeEvidenceSubmissionRequest(
            job_id=job_id, expected_prior_head_ref=None, evidence=evidence,
        ),
    )
    assert result.status == "admitted"
    # The production approval path can copy current progress while adding its own packet.
    service._control_store.upsert_progress(job_id=job_id, progress=result.job.progress)
    current = service.get_job_status(job_id)
    assert current.progress["normative_disposition"]["authorization_status"] == "authorized"
    source_fronts = {
        node.node_ref: {name: list(ids) for name, ids in node.cycle_run.fronts.candidate_ids_by_front().items()}
        for node in compiled.recursive_run.leaf_nodes
    }

    def assert_source_refusal():
        for current in (service.get_job_status(job_id), service.get_latest_job_for_run(before.run_id)):
            disposition = current.progress["normative_disposition"]
            assert disposition["authorization_status"] == "blocked"
            assert disposition["ranked_recommendations"] == []
            assert {node: item["candidate_fronts"] for node, item in disposition["leaf_dispositions"].items()} == source_fronts
            assert all(item["decision_request"] for item in disposition["leaf_dispositions"].values())
            assert "normative_head_ref" not in current.progress
            assert current.progress["compiled_recursive_generation_cycle_ref"] == before.progress["compiled_recursive_generation_cycle_ref"]

    with monkeypatch.context() as patches:
        patches.setattr(service._control_store, "get_normative_evidence_head", lambda _: None)
        assert_source_refusal()
    service._control_store.upsert_progress(job_id=job_id, progress={
        **result.job.progress, "compiled_recursive_generation_cycle_ref": "sha256:" + "f" * 64,
    })
    assert_source_refusal()


def test_terminal_candidate_publication_reuses_owned_source_and_refuses_replacement(completed_worker):
    service, before, _ = completed_worker
    job = service._control_store.get_job(before.job_id)
    payload = service._load_payload_ref(job.payload_ref)
    compiled_ref = before.progress["compiled_recursive_generation_cycle_ref"]
    normative_ref = before.progress["normative_disposition_ref"]
    source = service._publish_generation_run(
        job=job, payload=payload, compiled_run_ref=compiled_ref,
        normative_disposition_ref=normative_ref,
    )
    assert source == before.progress["manifest_ref"]
    with pytest.raises(ValueError, match="normative_generation_terminal_source_mismatch"):
        service._publish_generation_run(
            job=job, payload=payload, compiled_run_ref=compiled_ref,
            normative_disposition_ref="sha256:" + "f" * 64,
        )
    assert service._publish_generation_run(
        job=job, payload=payload, compiled_run_ref=compiled_ref,
        normative_disposition_ref=normative_ref,
    ) == source

"""Sign external reviewer evidence around an untouched production PA2 refusal."""

from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from polisyos.core import artifacts, canon
from polisyos.pdc import AuthorityBoundary
from polisyos.runtime.http.access_audit import (
    PreparedHumanDecisionExposureEvent,
    RuntimeDataAccessAuditTrail,
    complete_human_decision_exposure_event,
    reserve_human_decision_exposure_event,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services import human_decision_contracts as contracts
from polisyos.runtime.http.services.control.artifacts import write_runtime_authority_artifact
from polisyos.runtime.quality.agent_action_authority import (
    AgentActionAuthorityDecision,
    agent_action_content_hash,
)
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import DelegationContract


def persist_signed(
    control,
    payload,
    *,
    kind: str,
    schema_name: str,
    schema_version: str,
    signer: artifacts.Ed25519Signer,
    signer_identity: str,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    job_id: str,
    now: datetime,
    canon_spec=None,
) -> str:
    """Persist through the existing authority writer, then sign the exact CAS bytes."""
    dumped = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    digest = agent_action_content_hash(dumped)
    result = write_runtime_authority_artifact(
        control._artifact_store,
        control._diagnostic_event_log,
        dumped,
        artifacts.ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=schema_name, version=schema_version),
            producer=artifacts.ProducerInfo(
                component="polisyos.runtime.acquisition_fixture", version="1"
            ),
            governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
            inputs=[],
        ),
        evidence_id=f"acquisition-external-{digest[7:]}",
        evidence_class="authority_bearing",
        authority_role="producer_authority",
        provenance_kind="runtime_emitted",
        owner=signer_identity,
        reader_contract="runtime_quality.acquisition_fixture.reader",
        reader_contract_version="1.0",
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        job_id=job_id,
        trace_id=f"trace-{run_id}",
        span_id="external-fixture",
        parent_span_id=None,
        requested_execution_profile="governed",
        effective_execution_profile="governed",
        phase="acquisition_external_evidence",
        generated_at=now.isoformat(),
        as_of_time=now.isoformat(),
        same_input_closure={
            "closure_id": f"closure-{digest[7:]}",
            "status": "closed",
            "run_id": run_id,
            "job_id": job_id,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "evidence_input_refs": [],
            "closure_sha256": digest[7:],
        },
        input_refs=[],
        effective_mode_ref="sha256:" + "2" * 64,
        degradation_ledger_ref="sha256:" + "3" * 64,
        validation_status="pass",
        blocking_status="non_blocking",
        governance=GovernanceMetadata(
            classification="internal",
            authority_boundary="runtime.acquisition_external_fixture",
            pii="none",
            retention_policy="runtime-quality-90d",
            review_status="runtime_verified",
            override_policy="no_override",
            approval_policy="owner_signature_required",
        ),
        canon_spec=canon_spec or canon.CanonSpec(),
    )
    control._artifact_store.sign_artifact(
        result.cas_ref.artifact_id, signer, signer_identity=signer_identity
    )
    return str(result.cas_ref.artifact_id)


def prepare_human_decision(
    control,
    service,
    source_ref: str,
    *,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    signers: dict[str, artifacts.Ed25519Signer],
    identities: dict[str, str],
    now: datetime,
    audit_path: Path,
) -> contracts.HumanDecisionPA2GateInput:
    """Create signed external predicates and durable exposure; never rewrite the source."""
    store = control._artifact_store
    source_bytes = store.get_bytes(source_ref)
    source = AgentActionAuthorityDecision.model_validate(canon.from_canonical_bytes(source_bytes))
    assert source.outcome == "refused" and source.human_decision_request is not None
    assert source.contract_ref is not None and source.permission_snapshot is not None
    request = source.human_decision_request
    mandate = DelegationContract.model_validate(
        canon.from_canonical_bytes(store.get_bytes(source.contract_ref))
    )
    assert mandate.mandate_owner_ref is not None
    actor_ref = mandate.mandate_owner_ref
    digest = agent_action_content_hash(request)
    required = (source.contract_ref, *request.five_rights_binding.required_information_refs)
    assert len(required) > 1
    epoch = service.custody.verifier_epoch
    assert epoch is not None and service.custody.verifier is not None
    rule = request.rule_version_ref

    def boundary(purpose: str, *, deterministic: bool = False) -> AuthorityBoundary:
        return AuthorityBoundary(
            authoritative_for=[purpose],
            may_not_use_for=["claim_evidence", "publication_authority", "promotion_authority"],
            source_authority="deterministic_producer" if deterministic else "human_governance",
            posture="governed",
            rule_version_refs=[rule],
        )

    def persist(model, role: str, prefix: str, schema_name: str) -> str:
        return persist_signed(
            control,
            model,
            kind=getattr(contracts, prefix + "_ARTIFACT_KIND"),
            schema_name="polisyos.runtime." + schema_name,
            schema_version=getattr(contracts, prefix + "_MANIFEST_VERSION"),
            signer=signers[role],
            signer_identity=identities[role],
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            job_id="job-external-reviewer",
            now=now,
            canon_spec=canon.CanonSpec(forbid_floats=False)
            if prefix == "HUMAN_DECISION_EXPOSURE_EVENT"
            else None,
        )

    common = {
        "tenant_id": tenant_id,
        "run_id": run_id,
        "verifier_epoch": epoch,
        "valid_from": now - timedelta(minutes=1),
        "valid_until": now + timedelta(minutes=30),
        "rule_version_ref": rule,
        "issued_at": now - timedelta(minutes=1),
    }
    principal = contracts.HumanDecisionPrincipalBinding(
        binding_id=f"principal-{digest[7:19]}",
        binding_ref=f"identity://principal/{digest[7:]}",
        principal_issuer=identities["principal"],
        principal_audience="polisyos-runtime",
        principal_subject="human-reviewer-1",
        actor_ref=actor_ref,
        actor_key_id=signers["owner"].key_id,
        decision_roles=(request.required_role,),
        permissions=(RuntimePermission.RUNS_HUMAN_DECISIONS_CREATE.value,),
        authority_boundary=boundary("human_decision_principal_binding"),
        **common,
    )
    principal_ref = persist(
        principal, "principal", "HUMAN_DECISION_PRINCIPAL_BINDING", "HumanDecisionPrincipalBinding"
    )
    separation = contracts.ReviewerSeparationCredential(
        credential_id=f"separation-{digest[7:19]}",
        credential_ref=f"governance://separation/{digest[7:]}",
        case_id=request.case_id,
        decision_request_ref=request.request_ref,
        decision_request_digest=digest,
        reviewer_actor_ref=actor_ref,
        reviewed_actor_refs=(source.permission_snapshot.subject,),
        independence_established=True,
        change_authority_actions=tuple(request.available_actions),
        authority_boundary=boundary("human_decision_reviewer_separation"),
        **common,
    )
    separation_ref = persist(
        separation, "separation", "REVIEWER_SEPARATION_CREDENTIAL", "ReviewerSeparationCredential"
    )
    presentation = contracts.HumanDecisionPresentationContract(
        contract_id=f"presentation-{digest[7:19]}",
        contract_ref=f"governance://presentation/{digest[7:]}",
        decision_request_ref=request.request_ref,
        decision_request_digest=digest,
        required_artifact_digests=required,
        renderer_id="runtime-dashboard.human-decision-gate",
        renderer_version="1",
        channel=request.five_rights_binding.required_channel,
        representation=request.five_rights_binding.required_representation,
        redaction_policy_ref=None,
        truncation_policy_ref=None,
        authority_boundary=boundary("human_decision_presentation"),
        **common,
    )
    presentation_ref = persist(
        presentation,
        "presentation",
        "HUMAN_DECISION_PRESENTATION_CONTRACT",
        "HumanDecisionPresentationContract",
    )
    session = contracts.HumanDecisionExposureSession(
        session_id=f"session-{digest[7:19]}",
        session_ref=f"runtime://human-decision/exposure/{digest[7:]}",
        principal_binding_ref=principal_ref,
        principal_binding_digest=principal_ref,
        principal_subject="human-reviewer-1",
        actor_ref=actor_ref,
        decision_request_ref=request.request_ref,
        decision_request_digest=digest,
        basis_digest=source.contract_ref,
        required_artifact_digests=required,
        presentation_contract_ref=presentation_ref,
        presentation_contract_digest=presentation_ref,
        renderer_id=presentation.renderer_id,
        renderer_version=presentation.renderer_version,
        channel=presentation.channel,
        representation=presentation.representation,
        authority_boundary=boundary("human_decision_evidence_exposure", deterministic=True),
        **common,
    )
    session_ref = persist(
        session, "custody", "HUMAN_DECISION_EXPOSURE_SESSION", "HumanDecisionExposureSession"
    )
    trail = RuntimeDataAccessAuditTrail(path=audit_path)
    multiplicity = Counter(required)
    for index, ref in enumerate(required):
        event = contracts.HumanDecisionExposureAuditEvent(
            timestamp=now.timestamp(),
            event_id=f"exposure-{digest[7:19]}-{index}",
            event_ref=f"runtime://exposure/{digest[7:]}-{index}",
            event_receipt_ref=None,
            tenant_id=tenant_id,
            actor_ref=actor_ref,
            run_id=run_id,
            request_ref=request.request_ref,
            request_digest=digest,
            basis_digest=source.contract_ref,
            session_ref=session_ref,
            artifact_id=ref,
            content_digest=ref,
            delivered_bytes=len(store.get_bytes(ref)),
            allowed_multiplicity=multiplicity[ref],
            verifier_epoch=epoch,
        )
        event_ref = persist(
            event, "custody", "HUMAN_DECISION_EXPOSURE_EVENT", "HumanDecisionExposureAuditEvent"
        )
        prepared = PreparedHumanDecisionExposureEvent(
            unsigned_event=event,
            completed_event=event.model_copy(update={"event_receipt_ref": event_ref}),
            receipt_ref=event_ref,
        )
        custody = {
            "trail": trail,
            "artifact_store": store,
            "signer": signers["custody"],
            "signer_identity": identities["custody"],
            "verifier": service.custody.verifier,
        }
        reserved = reserve_human_decision_exposure_event(prepared=prepared, **custody)
        complete_human_decision_exposure_event(reserved=reserved, **custody)
    assert store.get_bytes(source_ref) == source_bytes
    return contracts.HumanDecisionPA2GateInput(
        source_kind="agent_action_authority",
        source_ref=source_ref,
        action_kind=source.action_kind,
        tenant_id=tenant_id,
        run_id=run_id,
        decision_request_ref=request.request_ref,
        decision_request_digest=digest,
        basis_ref=source.contract_ref,
        basis_digest=source.contract_ref,
        principal_binding_ref=principal_ref,
        reviewer_separation_ref=separation_ref,
        presentation_contract_ref=presentation_ref,
        exposure_session_ref=session_ref,
    )

"""Sanctioned acquisition authority composition for requests and durable workers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.core import canon
from polisyos.runtime.http.deployment_security import (
    RuntimeDeploymentSecurity,
    require_factory_produced_deployment_security,
)
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionRouteMutationRequest,
)
from polisyos.runtime.http.services.acquisition_admission_bundle import (
    AcquisitionAdmissionBundleBlocked,
    AcquisitionAdmissionBundleProducer,
)
from polisyos.runtime.http.services.human_decision_contracts import (
    HumanDecisionPA2GatewayAdapterInput,
)
from polisyos.runtime.http.services.human_decisions import (
    HumanDecisionOperationalResolutionError,
    HumanDecisionService,
)
from polisyos.runtime.quality.agent_action_authority import (
    ACQUISITION_ACTION_KIND,
    AgentActionAuthorityDecision,
    AgentActionAuthorityGateway,
    AgentActionAuthorityOwnerResolutionError,
    AgentActionAuthorityRecordingError,
    AgentActionAuthorityWriteContext,
    AgentActionEffectBinding,
    agent_action_content_hash,
    agent_action_permission_hash,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core import artifacts
    from polisyos.pdc import OperationInvocationRecord
    from polisyos.runtime.http.authorization import BoundActionPermissionVerification
    from polisyos.runtime.http.mutation_policy import RuntimeIdempotencyStore
    from polisyos.runtime.http.services.acquisition_authority_configuration import (
        AcquisitionMandateSlot,
    )
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedAcquisitionRouteClosure
    from polisyos.runtime.quality.agent_action_authority import ResolvedDelegationContract
    from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
        DelegatedActionEnvelope,
        HumanDecisionRecord,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog


class ProductionAcquisitionAuthorityProvider:
    """Resolve appointed evidence through the existing PA2 and DS9 authority owners.

    The provider is always constructible from an attested deployment, including
    one with empty institutional slots. Configuration presence is not an allow:
    each request reopens signed content, currentness, and exact resource scope.
    """

    def __init__(
        self,
        *,
        deployment_security: RuntimeDeploymentSecurity,
        artifact_store: artifacts.ArtifactStore,
        event_log: RuntimeDiagnosticEventLog,
        idempotency_store: RuntimeIdempotencyStore,
        execution_profile: str,
        human_decision_service: HumanDecisionService | None = None,
        production_approval_resolver: object | None = None,
    ) -> None:
        self._deployment = require_factory_produced_deployment_security(deployment_security)
        self._store = artifact_store
        self._event_log = event_log
        self._idempotency = idempotency_store
        self._execution_profile = execution_profile
        self._human_decisions = human_decision_service
        self._approval_resolver = production_approval_resolver

    @property
    def authority_available(self) -> bool:
        """Expose configured slots; the request decision alone establishes authority."""
        deployment = require_factory_produced_deployment_security(self._deployment)
        return deployment.acquisition_authority.authority_available

    @property
    def external_nonclosures(self) -> tuple[str, ...]:
        """Name each unconfigured institutional/signing slot without suppressing the intake."""
        slot = require_factory_produced_deployment_security(self._deployment).acquisition_authority
        return tuple(
            label
            for present, label in (
                (bool(slot.config.mandates), "current_mandate_owner:producer_missing"),
                (
                    slot.signing_slot.signer is not None,
                    "deterministic_admission_bundle:producer_missing",
                ),
                (slot.decision_signer is not None, "acquisition_decision_signer:producer_missing"),
            )
            if not present
        )

    def _context(
        self, closure: VerifiedAcquisitionRouteClosure, job_id: str
    ) -> AgentActionAuthorityWriteContext:
        return AgentActionAuthorityWriteContext(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            job_id=job_id,
            trace_id=job_id,
            span_id=f"{job_id}.authority",
            owner="team-runtime-acquisition",
            requested_execution_profile=self._execution_profile,
            effective_execution_profile=self._execution_profile,
            effective_mode_ref=agent_action_content_hash(self._deployment.config),
        )

    @staticmethod
    def _binding(
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionEffectBinding:
        return AgentActionEffectBinding(
            binding_id="runtime.acquisition_route_loop.owner_port.v1",
            action_kind=ACQUISITION_ACTION_KIND,
            operation_id=ACQUISITION_ACTION_KIND,
            operation_version="v1",
            implementation_ref="polisyos.runtime.acquisition_route_loop.owner_port.v1",
            handler=effect_handler,
        )

    def _slot(
        self, closure: VerifiedAcquisitionRouteClosure, resource_digest: str
    ) -> AcquisitionMandateSlot | None:
        deployment = require_factory_produced_deployment_security(self._deployment)
        return next(
            (
                row
                for row in deployment.acquisition_authority.config.mandates
                if (row.tenant_id, row.cell_id, row.run_id, row.route_id, row.resource_digest)
                == (
                    closure.tenant_id,
                    closure.cell_id,
                    closure.run_id,
                    closure.route_id,
                    resource_digest,
                )
            ),
            None,
        )

    def _options(
        self,
        closure: VerifiedAcquisitionRouteClosure,
        job_id: str,
        binding: AgentActionEffectBinding,
        slot: AcquisitionMandateSlot | None,
    ) -> dict[str, Any]:
        authority = require_factory_produced_deployment_security(
            self._deployment
        ).acquisition_authority
        return {
            "artifact_store": self._store,
            "event_log": self._event_log,
            "idempotency_store": self._idempotency,
            "artifact_verifier": authority.verifier,
            "admission_producer_identity": (
                authority.signing_slot.signer_identity or "unconfigured:acquisition-admission"
            ),
            "write_context": self._context(closure, job_id),
            "contract_refs_by_resource_digest": (
                {slot.resource_digest: slot.delegation_contract_ref} if slot else {}
            ),
            "mandate_authority_evidence_refs_by_owner_ref": (
                {slot.mandate_owner_ref: slot.current_mandate_evidence_ref} if slot else {}
            ),
            "effect_bindings": (binding,),
            "decision_signer_identity": authority.decision_signer_identity,
        }

    @staticmethod
    def _require_slot_binding(
        gateway: AgentActionAuthorityGateway, slot: AcquisitionMandateSlot
    ) -> ResolvedDelegationContract:
        resolved = gateway.resolve_delegation_contract(slot.resource_digest)
        if (
            resolved.signer_identity != slot.mandate_owner_ref
            or resolved.mandate_authority_signer_identity != slot.current_mandate_signer_identity
            or resolved.mandate_authority_evidence_ref != slot.current_mandate_evidence_ref
        ):
            raise AgentActionAuthorityOwnerResolutionError(
                "acquisition_mandate_trust_role_mismatch"
            )
        return resolved

    def for_request(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        request: AcquisitionRouteMutationRequest,
        job_id: str,
        bound_permission: BoundActionPermissionVerification,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway:
        """Bind the live DS20 proof to signed inputs, or return a refusal gateway."""
        agent_action_permission_hash(bound_permission)
        resource_digest = bound_permission.bound_resource.resource_digest
        slot = self._slot(closure, resource_digest)
        binding = self._binding(effect_handler)
        options = self._options(closure, job_id, binding, slot)
        authority = self._deployment.acquisition_authority
        options.update(
            bound_permission=bound_permission,
            admission_refs_by_invocation_hash={},
            decision_signer=authority.decision_signer,
            human_decision_service=self._human_decisions,
            production_approval_resolver=self._approval_resolver,
            human_decision_information_refs=(),
            human_decision_disconfirming_refs=(),
        )
        information_valid = True
        if slot is not None:
            try:
                for ref in slot.decision_information_refs:
                    payload = self._store.get_bytes(ref.artifact_id)
                    manifest = self._store.get_manifest(ref.artifact_id)
                    if (
                        str(ref.artifact_id) != f"sha256:{canon.content_hash(payload)}"
                        or manifest.kind != ref.kind
                        or manifest.media_type != ref.media_type
                    ):
                        raise ValueError("acquisition information content changed")
                options["human_decision_information_refs"] = tuple(
                    str(ref.artifact_id) for ref in slot.decision_information_refs
                )
                options["human_decision_disconfirming_refs"] = tuple(
                    str(ref.artifact_id) for ref in slot.decision_disconfirming_refs
                )
            except (KeyError, OSError, ValueError):
                information_valid = False
                options["contract_refs_by_resource_digest"] = {}
        gateway = AgentActionAuthorityGateway(**options)
        if (
            slot is None
            or not information_valid
            or authority.decision_signer is None
            or authority.signing_slot.signer is None
        ):
            return gateway
        try:
            resolved = self._require_slot_binding(gateway, slot)
        except AgentActionAuthorityOwnerResolutionError:
            # Keep canonical missing/currentness/signature refusals where possible;
            # an independently trusted key in another role cannot act as this issuer.
            options["contract_refs_by_resource_digest"] = {}
            return AgentActionAuthorityGateway(**options)
        operation, invocation, intent = AcquisitionActionService._action_tuple(closure, request)
        selected_human_ref = request.human_decision_record_ref or slot.human_decision_record_ref
        try:
            if selected_human_ref is not None:
                if self._human_decisions is None:
                    return gateway
                record = self._human_decisions.read_record(
                    selected_human_ref,
                    tenant_id=closure.tenant_id,
                    run_id=closure.run_id,
                )
                source = gateway.load_persisted_decision(record.source_ref).decision
                if (
                    record.source_kind != "agent_action_authority"
                    or source.permission_snapshot is None
                    or agent_action_content_hash(source.permission_snapshot)
                    != agent_action_permission_hash(bound_permission)
                    or source.operation_content_hash != agent_action_content_hash(operation)
                    or source.invocation_content_hash != agent_action_content_hash(invocation)
                    or source.intent_content_hash != agent_action_content_hash(intent)
                    or source.bound_resource_digest != resource_digest
                    or source.contract_ref != resolved.contract_cas_ref
                    or source.admission_bundle_ref is None
                ):
                    return gateway
                envelope = next(
                    row
                    for row in resolved.contract.action_envelopes
                    if row.envelope_id == source.envelope_id
                )
                adapter = self._human_adapter(
                    record, selected_human_ref, envelope, operation.operation_id
                )
                options["admission_refs_by_invocation_hash"] = {
                    agent_action_content_hash(invocation): source.admission_bundle_ref
                }
                options["human_decision_adapters_by_request_ref"] = {
                    record.human_decision_request_ref: adapter
                }
            else:
                receipt = AcquisitionAdmissionBundleProducer(
                    artifact_store=self._store,
                    event_log=self._event_log,
                    signing_slot=authority.signing_slot,
                    write_context=options["write_context"],
                ).admit(
                    delegation_contract_ref=resolved.contract_cas_ref,
                    operation=operation,
                    invocation=invocation,
                    intent=intent,
                    bound_permission=bound_permission,
                    effect_binding=binding,
                    admitted_at=datetime.now(UTC),
                )
                options["admission_refs_by_invocation_hash"] = receipt.invocation_refs
        except (
            AcquisitionAdmissionBundleBlocked,
            HumanDecisionOperationalResolutionError,
            AgentActionAuthorityRecordingError,
            ValueError,
            StopIteration,
        ):
            return gateway
        return AgentActionAuthorityGateway(**options)

    @staticmethod
    def _human_adapter(
        record: HumanDecisionRecord,
        record_ref: str,
        envelope: DelegatedActionEnvelope,
        operation_id: str,
    ) -> HumanDecisionPA2GatewayAdapterInput:
        """Derive the DS9 selector only from reopened signed owner artifacts."""
        return HumanDecisionPA2GatewayAdapterInput(
            tenant_id=record.tenant_id,
            run_id=record.run_id,
            source_kind="agent_action_authority",
            decision_request_ref=record.human_decision_request_ref,
            decision_request_digest=record.decision_request_digest,
            record_ref=record_ref,
            record_digest=record_ref,
            source_ref=record.source_ref,
            source_digest=record.source_digest,
            basis_digest=record.basis_digest,
            rule_version_ref=record.rule_version_ref,
            verifier_epoch=record.verifier_epoch,
            valid_from=record.valid_from,
            valid_until=record.valid_until,
            expected_consumer="polisyos.runtime.quality.agent_action_authority",
            expected_operation=operation_id,
            expected_audience="polisyos-runtime",
            delegation_contract_ref=record.basis_ref,
            delegation_contract_digest=record.basis_digest,
            delegation_envelope_ref=envelope.envelope_ref,
            delegation_envelope_digest=agent_action_content_hash(envelope),
        )

    def for_job(
        self,
        *,
        closure: VerifiedAcquisitionRouteClosure,
        request: AcquisitionRouteMutationRequest,
        job_id: str,
        decision_ref: str,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway:
        """Reopen the exact worker decision and all authority inputs after a process restart."""
        self._require_worker_decision_verification()
        decision = AgentActionAuthorityDecision.model_validate(
            canon.from_canonical_bytes(self._store.get_bytes(decision_ref))
        )
        if agent_action_content_hash(decision) != decision_ref:
            raise AgentActionAuthorityRecordingError("acquisition decision content mismatch")
        slot = self._slot(closure, decision.bound_resource_digest or "")
        if slot is None or decision.admission_bundle_ref is None:
            raise AgentActionAuthorityRecordingError("acquisition replay authority slot is empty")
        operation, invocation, intent = AcquisitionActionService._action_tuple(closure, request)
        if (
            decision.operation_content_hash != agent_action_content_hash(operation)
            or decision.invocation_content_hash != agent_action_content_hash(invocation)
            or decision.intent_content_hash != agent_action_content_hash(intent)
        ):
            raise AgentActionAuthorityRecordingError("acquisition replay action tuple changed")
        gateway = AgentActionAuthorityGateway.for_persisted_decision(
            **self._options(closure, job_id, self._binding(effect_handler), slot),
            decision_ref=decision_ref,
            admission_refs_by_invocation_hash={
                decision.invocation_content_hash: decision.admission_bundle_ref
            },
        )
        resolved = self._require_slot_binding(gateway, slot)
        if decision.human_decision_record_ref is None or self._human_decisions is None:
            raise AgentActionAuthorityRecordingError("acquisition replay human custody missing")
        record = self._human_decisions.read_record(
            decision.human_decision_record_ref, tenant_id=closure.tenant_id, run_id=closure.run_id
        )
        envelope = next(
            (
                row
                for row in resolved.contract.action_envelopes
                if row.envelope_id == decision.envelope_id
            ),
            None,
        )
        if envelope is None:
            raise AgentActionAuthorityRecordingError("acquisition replay envelope missing")
        adapter = self._human_adapter(
            record, decision.human_decision_record_ref, envelope, operation.operation_id
        )
        custody = self._human_decisions.revalidate_gateway_adapter_custody(adapter)
        source = custody.source
        if (
            source.permission_snapshot != decision.permission_snapshot
            or source.admission_bundle_ref != decision.admission_bundle_ref
            or source.operation_content_hash != decision.operation_content_hash
            or source.invocation_content_hash != decision.invocation_content_hash
            or source.intent_content_hash != decision.intent_content_hash
            or source.bound_resource_digest != decision.bound_resource_digest
            or source.contract_ref != decision.contract_ref
            or source.envelope_id != decision.envelope_id
            or custody.record.decision_action_exercised != "approve"
        ):
            raise AgentActionAuthorityRecordingError(
                "acquisition replay human custody binding changed"
            )
        return gateway

    def _require_worker_decision_verification(self) -> None:
        """Keep production execution outside the generic unsigned legacy replay mode."""
        authority = require_factory_produced_deployment_security(
            self._deployment
        ).acquisition_authority
        if authority.decision_signer_identity is None:
            raise AgentActionAuthorityRecordingError(
                "acquisition_worker_decision_verification_unallocated"
            )

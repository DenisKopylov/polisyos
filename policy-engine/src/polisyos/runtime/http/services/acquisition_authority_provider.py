"""Sanctioned acquisition authority composition for requests and durable workers."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any

from polisyos.common.canonical_profile import require_declared_profile
from polisyos.core import canon
from polisyos.core.artifacts import (
    ArtifactOwnershipError,
    read_core_json_artifact,
)
from polisyos.runtime.http.deployment_security import (
    RuntimeDeploymentSecurity,
    require_factory_produced_deployment_security,
)
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionActionService,
    AcquisitionRouteMutationRequest,
    CandidateExperimentRouteMutationRequest,
)
from polisyos.runtime.http.services.acquisition_admission_bundle import (
    AcquisitionAdmissionBundleBlocked,
    AcquisitionAdmissionBundleProducer,
    candidate_experiment_request_resource_digest,
    require_candidate_experiment_bound_permission,
    require_candidate_experiment_reuse_bound_permission,
    require_model_input_use_bound_permission,
    require_request_bound_action_snapshot,
)
from polisyos.runtime.http.services.human_decision_contracts import (
    HumanDecisionPA2GatewayAdapterInput,
)
from polisyos.runtime.http.services.human_decisions import (
    HumanDecisionOperationalResolutionError,
    HumanDecisionService,
)
from polisyos.runtime.http.services.model_input_successor_action import (
    MODEL_INPUT_USE_IMPLEMENTATION_REF,
    model_input_successor_action_tuple,
)
from polisyos.runtime.quality.agent_action_authority import (
    ACQUISITION_ACTION_KIND,
    CANDIDATE_EXPERIMENT_ACTION_KIND,
    CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
    MODEL_INPUT_USE_ACTION_KIND,
    AgentActionAuthorityDecision,
    AgentActionAuthorityGateway,
    AgentActionAuthorityOwnerResolutionError,
    AgentActionAuthorityRecordingError,
    AgentActionAuthorityResolutionFailure,
    AgentActionAuthorityWriteContext,
    AgentActionEffectBinding,
    AuthenticatedAgentActionDecisionHistory,
    agent_action_content_hash,
    agent_action_permission_hash,
    load_agent_action_decision_history,
    protected_action_human_review_requirement,
)
from polisyos.runtime.quality.candidate_experiment_reuse import (
    candidate_experiment_reuse_action_tuple,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from polisyos.core import artifacts
    from polisyos.pdc import OperationContract, OperationInvocationRecord
    from polisyos.runtime.http.authorization import BoundActionPermissionVerification
    from polisyos.runtime.http.mutation_policy import RuntimeIdempotencyStore
    from polisyos.runtime.http.services.acquisition_authority_configuration import (
        AcquisitionMandateSlot,
    )
    from polisyos.runtime.http.services.model_input_successor_action import (
        ModelInputSuccessorActionRequest,
        ModelInputSuccessorIdentity,
        SelectedModelInputSuccessorAction,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        VerifiedAcquisitionRouteClosure,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.agent_action_authority import (
        AgentActionIntent,
        ResolvedDelegationContract,
    )
    from polisyos.runtime.quality.candidate_experiment_reuse import (
        CandidateExperimentReuseActionRequest,
        CandidateExperimentReuseActionSelection,
    )
    from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
        DelegatedActionEnvelope,
        HumanDecisionRecord,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog


type _AuthorityOrigin = (
    VerifiedAcquisitionRouteClosure
    | VerifiedCandidateExperimentOrigin
    | ModelInputSuccessorIdentity
    | CandidateExperimentReuseActionSelection
)

_REQUEST_BOUND_CANDIDATE_EFFECTS = {
    MODEL_INPUT_USE_ACTION_KIND: (
        MODEL_INPUT_USE_IMPLEMENTATION_REF,
        "model_input_use_replay_resource_mismatch",
    ),
    CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND: (
        "polisyos.runtime.candidate_experiment_reuse.owner_port.v1",
        "candidate_experiment_reuse_replay_resource_mismatch",
    ),
}


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
                (
                    slot.decision_signer is not None,
                    "acquisition_decision_signer:producer_missing",
                ),
            )
            if not present
        )

    def _context(
        self,
        closure: _AuthorityOrigin,
        job_id: str,
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

    @staticmethod
    def _candidate_experiment_binding(
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionEffectBinding:
        """Bind the candidate-experiment operation to its own exact owner slot."""
        return AgentActionEffectBinding(
            binding_id="runtime.candidate_experiment_route_loop.owner_port.v1",
            action_kind=CANDIDATE_EXPERIMENT_ACTION_KIND,
            operation_id=CANDIDATE_EXPERIMENT_ACTION_KIND,
            operation_version="v1",
            implementation_ref=(
                "polisyos.runtime.acquisition_route_loop.candidate_experiment_owner_port.v1"
            ),
            handler=effect_handler,
        )

    @staticmethod
    def _request_bound_candidate_binding(
        action_kind: str,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionEffectBinding:
        implementation_ref, _ = _REQUEST_BOUND_CANDIDATE_EFFECTS[action_kind]
        return AgentActionEffectBinding(
            binding_id=implementation_ref,
            action_kind=action_kind,
            operation_id=action_kind,
            operation_version="v1",
            implementation_ref=implementation_ref,
            handler=effect_handler,
        )

    def _slot(
        self,
        closure: _AuthorityOrigin,
        resource_digest: str,
    ) -> AcquisitionMandateSlot | None:
        deployment = require_factory_produced_deployment_security(self._deployment)
        return next(
            (
                row
                for row in deployment.acquisition_authority.config.mandates
                if (
                    row.tenant_id,
                    row.cell_id,
                    row.run_id,
                    row.route_id,
                    row.resource_digest,
                )
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
        closure: _AuthorityOrigin,
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
    def _slot_replay_refs(
        slot: AcquisitionMandateSlot,
        *,
        additional_refs: tuple[str, ...] = (),
    ) -> tuple[str, ...]:
        refs = [slot.delegation_contract_ref, slot.current_mandate_evidence_ref]
        refs.extend(str(ref.artifact_id) for ref in slot.decision_information_refs)
        refs.extend(str(ref.artifact_id) for ref in slot.decision_disconfirming_refs)
        if slot.human_decision_record_ref is not None:
            refs.append(slot.human_decision_record_ref)
        refs.extend(additional_refs)
        return tuple(dict.fromkeys(refs))

    @staticmethod
    def _owner_refusal_gateway(
        options: dict[str, Any],
        *,
        resource_digest: str,
        code: str,
        replay_input_refs: tuple[str, ...],
    ) -> AgentActionAuthorityGateway:
        """Carry one exact provider refusal through the existing decision owner."""
        refusal_options = dict(options)
        refusal_options["owner_resolution_failures_by_resource_digest"] = {
            resource_digest: AgentActionAuthorityResolutionFailure(
                code=code,
                replay_input_refs=replay_input_refs,
            )
        }
        return AgentActionAuthorityGateway(**refusal_options)

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
        return self._for_action_request(
            closure=closure,
            request=request,
            job_id=job_id,
            bound_permission=bound_permission,
            effect_handler=effect_handler,
            action_tuple=AcquisitionActionService._action_tuple(closure, request),
            binding=self._binding(effect_handler),
        )

    def for_candidate_experiment_request(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        request: CandidateExperimentRouteMutationRequest,
        job_id: str,
        bound_permission: BoundActionPermissionVerification,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway:
        """Resolve PA2/DS9 authority for the exact unpriced candidate action."""
        self._require_candidate_request_source(origin, request)
        if (
            bound_permission.verification.requirement.permission
            is not RuntimePermission.EVIDENCE_ACQUIRE
        ):
            raise AgentActionAuthorityRecordingError("candidate_experiment_permission_mismatch")
        try:
            require_candidate_experiment_bound_permission(bound_permission, request)
        except AcquisitionAdmissionBundleBlocked as exc:
            raise AgentActionAuthorityRecordingError(
                "candidate_experiment_request_proof_mismatch"
            ) from exc
        return self._for_action_request(
            closure=origin,
            request=request,
            job_id=job_id,
            bound_permission=bound_permission,
            effect_handler=effect_handler,
            action_tuple=AcquisitionActionService._candidate_experiment_action_tuple(
                origin, request
            ),
            binding=self._candidate_experiment_binding(effect_handler),
        )

    def for_model_input_use_request(
        self,
        *,
        selection: SelectedModelInputSuccessorAction,
        bound_permission: BoundActionPermissionVerification,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway:
        """Bind PA2/DS9 to exact candidate use of an already-active observation."""
        try:
            require_model_input_use_bound_permission(bound_permission, selection.request)
        except AcquisitionAdmissionBundleBlocked as exc:
            raise AgentActionAuthorityRecordingError(
                "model_input_use_request_proof_mismatch"
            ) from exc
        return self._for_action_request(
            closure=selection,
            request=selection.request,
            job_id=selection.job_id,
            bound_permission=bound_permission,
            effect_handler=effect_handler,
            action_tuple=model_input_successor_action_tuple(selection),
            binding=self._request_bound_candidate_binding(
                MODEL_INPUT_USE_ACTION_KIND, effect_handler
            ),
        )

    def for_candidate_experiment_reuse_request(
        self,
        *,
        selection: CandidateExperimentReuseActionSelection,
        bound_permission: BoundActionPermissionVerification,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway:
        """Bind PA2 and DS9 to the exact no-fetch candidate reuse request."""
        action_tuple = candidate_experiment_reuse_action_tuple(selection)
        try:
            require_candidate_experiment_reuse_bound_permission(bound_permission, selection.request)
        except AcquisitionAdmissionBundleBlocked as exc:
            raise AgentActionAuthorityRecordingError(
                "candidate_experiment_reuse_request_proof_mismatch"
            ) from exc
        return self._for_action_request(
            closure=selection,
            request=selection.request,
            job_id=selection.action_job_id,
            bound_permission=bound_permission,
            effect_handler=effect_handler,
            action_tuple=action_tuple,
            binding=self._request_bound_candidate_binding(
                CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND, effect_handler
            ),
        )

    def _for_action_request(
        self,
        *,
        closure: _AuthorityOrigin,
        request: (
            AcquisitionRouteMutationRequest
            | CandidateExperimentRouteMutationRequest
            | CandidateExperimentReuseActionRequest
            | ModelInputSuccessorActionRequest
        ),
        job_id: str,
        bound_permission: BoundActionPermissionVerification,
        effect_handler: Callable[[OperationInvocationRecord], object],
        action_tuple: tuple[OperationContract, OperationInvocationRecord, AgentActionIntent],
        binding: AgentActionEffectBinding,
    ) -> AgentActionAuthorityGateway:
        """Resolve one typed acquisition action through shared PA2/DS9 owners."""
        agent_action_permission_hash(bound_permission)
        resource_digest = bound_permission.bound_resource.resource_digest
        slot = self._slot(closure, resource_digest)
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
        if slot is not None:
            try:
                for ref in slot.decision_information_refs:
                    payload = self._store.get_bytes(ref)
                    manifest = self._store.get_manifest(ref)
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
            except (KeyError, FileNotFoundError, ArtifactOwnershipError, ValueError):
                return self._owner_refusal_gateway(
                    options,
                    resource_digest=resource_digest,
                    code="acquisition_decision_information_unverified",
                    replay_input_refs=self._slot_replay_refs(slot),
                )
        gateway = AgentActionAuthorityGateway(**options)
        if (
            slot is None
            or authority.decision_signer is None
            or authority.signing_slot.signer is None
        ):
            return gateway
        try:
            resolved = self._require_slot_binding(gateway, slot)
        except AgentActionAuthorityOwnerResolutionError as exc:
            return self._owner_refusal_gateway(
                options,
                resource_digest=resource_digest,
                code=exc.code,
                replay_input_refs=self._slot_replay_refs(
                    slot,
                    additional_refs=exc.replay_input_refs,
                ),
            )
        operation, invocation, intent = action_tuple
        selected_human_ref = request.human_decision_record_ref or slot.human_decision_record_ref
        source_refs = self._slot_replay_refs(
            slot,
            additional_refs=(selected_human_ref,) if selected_human_ref is not None else (),
        )
        try:
            if selected_human_ref is not None:
                if self._human_decisions is None:
                    return self._owner_refusal_gateway(
                        options,
                        resource_digest=resource_digest,
                        code="acquisition_human_decision_service_unavailable",
                        replay_input_refs=source_refs,
                    )
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
                    return self._owner_refusal_gateway(
                        options,
                        resource_digest=resource_digest,
                        code="acquisition_human_decision_source_mismatch",
                        replay_input_refs=source_refs,
                    )
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
                    request=request,
                )
                options["admission_refs_by_invocation_hash"] = receipt.invocation_refs
        except AcquisitionAdmissionBundleBlocked as exc:
            return self._owner_refusal_gateway(
                options,
                resource_digest=resource_digest,
                code=exc.code,
                replay_input_refs=source_refs,
            )
        except HumanDecisionOperationalResolutionError as exc:
            return self._owner_refusal_gateway(
                options,
                resource_digest=resource_digest,
                code=exc.code,
                replay_input_refs=source_refs,
            )
        except AgentActionAuthorityOwnerResolutionError as exc:
            return self._owner_refusal_gateway(
                options,
                resource_digest=resource_digest,
                code=exc.code,
                replay_input_refs=self._slot_replay_refs(
                    slot,
                    additional_refs=(*source_refs, *exc.replay_input_refs),
                ),
            )
        except AgentActionAuthorityRecordingError:
            return self._owner_refusal_gateway(
                options,
                resource_digest=resource_digest,
                code="acquisition_authority_source_unrecorded",
                replay_input_refs=source_refs,
            )
        except (KeyError, FileNotFoundError, ArtifactOwnershipError):
            return self._owner_refusal_gateway(
                options,
                resource_digest=resource_digest,
                code="acquisition_authority_source_unverified",
                replay_input_refs=source_refs,
            )
        except ValueError:
            return self._owner_refusal_gateway(
                options,
                resource_digest=resource_digest,
                code="acquisition_authority_source_unverified",
                replay_input_refs=source_refs,
            )
        except StopIteration:
            return self._owner_refusal_gateway(
                options,
                resource_digest=resource_digest,
                code="acquisition_human_decision_envelope_unavailable",
                replay_input_refs=source_refs,
            )
        return AgentActionAuthorityGateway(**options)

    @staticmethod
    def _require_candidate_request_source(
        origin: VerifiedCandidateExperimentOrigin,
        request: CandidateExperimentRouteMutationRequest,
    ) -> None:
        """Reject a candidate request whose typed selected views differ from the owner."""
        from polisyos.runtime.quality.acquisition_evaluation import _candidate_model_values_same

        projection = AcquisitionActionService._candidate_experiment_projection(origin)
        if type(request) is not CandidateExperimentRouteMutationRequest or (
            request.route_id != origin.route_id
            or not _candidate_model_values_same(request.replay_pins, projection.replay_pins)
        ):
            raise AgentActionAuthorityRecordingError(
                "candidate_experiment_authority_request_source_mismatch"
            )

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
        return self._for_persisted_decision(
            closure=closure,
            job_id=job_id,
            decision_ref=decision_ref,
            effect_handler=effect_handler,
            action_tuple=AcquisitionActionService._action_tuple(closure, request),
            binding=self._binding(effect_handler),
            expected_human_decision_record_ref=request.human_decision_record_ref,
        )

    def for_candidate_experiment_job(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        request: CandidateExperimentRouteMutationRequest,
        job_id: str,
        decision_ref: str,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway:
        """Reopen candidate PA2 and DS9 evidence for a live worker replay."""
        self._require_candidate_request_source(origin, request)
        return self._for_persisted_decision(
            closure=origin,
            job_id=job_id,
            decision_ref=decision_ref,
            effect_handler=effect_handler,
            action_tuple=AcquisitionActionService._candidate_experiment_action_tuple(
                origin, request
            ),
            binding=self._candidate_experiment_binding(effect_handler),
            expected_human_decision_record_ref=request.human_decision_record_ref,
            expected_action_kind=CANDIDATE_EXPERIMENT_ACTION_KIND,
        )

    def for_model_input_use_job(
        self,
        *,
        selection: SelectedModelInputSuccessorAction,
        decision_ref: str,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway:
        """Reopen current signed model-input use permission for the exact worker tuple."""
        return self._for_persisted_decision(
            closure=selection,
            job_id=selection.job_id,
            decision_ref=decision_ref,
            effect_handler=effect_handler,
            action_tuple=model_input_successor_action_tuple(selection),
            binding=self._request_bound_candidate_binding(
                MODEL_INPUT_USE_ACTION_KIND, effect_handler
            ),
            expected_human_decision_record_ref=selection.request.human_decision_record_ref,
            expected_action_kind=MODEL_INPUT_USE_ACTION_KIND,
            expected_request=selection.request,
        )

    def for_candidate_experiment_reuse_job(
        self,
        *,
        selection: CandidateExperimentReuseActionSelection,
        decision_ref: str,
        effect_handler: Callable[[OperationInvocationRecord], object],
    ) -> AgentActionAuthorityGateway:
        """Reopen the exact signed no-fetch action under the current mandate and DS9."""
        return self._for_persisted_decision(
            closure=selection,
            job_id=selection.action_job_id,
            decision_ref=decision_ref,
            effect_handler=effect_handler,
            action_tuple=candidate_experiment_reuse_action_tuple(selection),
            binding=self._request_bound_candidate_binding(
                CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND, effect_handler
            ),
            expected_human_decision_record_ref=selection.request.human_decision_record_ref,
            expected_action_kind=CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
            expected_request=selection.request,
        )

    def load_model_input_use_decision_history(
        self,
        *,
        identity: ModelInputSuccessorIdentity,
        decision_ref: str,
    ) -> AuthenticatedAgentActionDecisionHistory:
        """Authenticate the original selected-use approval for historical readback."""
        history = self._load_signed_decision_history(
            closure=identity, job_id=identity.job_id, decision_ref=decision_ref
        )
        self._require_persisted_action_tuple(
            history.decision,
            action_tuple=model_input_successor_action_tuple(identity),
            expected_action_kind=MODEL_INPUT_USE_ACTION_KIND,
            expected_human_decision_record_ref=identity.request.human_decision_record_ref,
            expected_request=identity.request,
        )
        if (
            history.decision.outcome != "allowed"
            or history.decision.human_decision_record_ref is None
        ):
            raise AgentActionAuthorityRecordingError("model_input_use_history_approval_missing")
        return history

    def load_candidate_experiment_decision_history(
        self,
        *,
        origin: VerifiedCandidateExperimentOrigin,
        request: CandidateExperimentRouteMutationRequest,
        job_id: str,
        decision_ref: str,
    ) -> AuthenticatedAgentActionDecisionHistory:
        """Authenticate candidate PA2 history without implying a current permit."""
        self._require_candidate_request_source(origin, request)
        expected_job_id = AcquisitionActionService._candidate_experiment_job_id(origin, request)
        if job_id != expected_job_id:
            raise AgentActionAuthorityRecordingError("candidate_experiment_job_identity_mismatch")
        operation, invocation, intent = AcquisitionActionService._candidate_experiment_action_tuple(
            origin, request
        )
        history = self._load_signed_decision_history(
            closure=origin, job_id=job_id, decision_ref=decision_ref
        )
        decision = history.decision
        if (
            decision.action_kind != CANDIDATE_EXPERIMENT_ACTION_KIND
            or decision.operation_id != operation.operation_id
            or decision.operation_version != operation.operation_version
            or decision.operation_content_hash != agent_action_content_hash(operation)
            or decision.invocation_content_hash != agent_action_content_hash(invocation)
            or decision.intent_content_hash != agent_action_content_hash(intent)
            or decision.permission_snapshot is None
            or decision.permission_snapshot.required_permission != "evidence.acquire"
            or decision.permission_snapshot.resource_digest != decision.bound_resource_digest
            or decision.permission_snapshot.resource_kind
            != "runtime.evidence.acquisition.candidate_experiment.request_bound"
            or decision.permission_snapshot.query_sha256 != f"sha256:{sha256(b'').hexdigest()}"
            or decision.permission_snapshot.resource_digest
            != candidate_experiment_request_resource_digest(
                request,
                body_sha256=decision.permission_snapshot.body_sha256,
                query_sha256=decision.permission_snapshot.query_sha256,
            )
            or (
                request.human_decision_record_ref is not None
                and decision.human_decision_record_ref != request.human_decision_record_ref
            )
        ):
            raise AgentActionAuthorityRecordingError(
                "candidate_experiment_history_action_tuple_mismatch"
            )
        return history

    def load_candidate_experiment_reuse_decision_history(
        self,
        *,
        selection: CandidateExperimentReuseActionSelection,
        decision_ref: str,
    ) -> AuthenticatedAgentActionDecisionHistory:
        """Authenticate the exact original reuse approval without a live mandate lookup."""
        action_tuple = candidate_experiment_reuse_action_tuple(selection)
        history = self._load_signed_decision_history(
            closure=selection, job_id=selection.action_job_id, decision_ref=decision_ref
        )
        decision = history.decision
        action_kind = CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND
        self._require_persisted_action_tuple(
            decision,
            action_tuple=action_tuple,
            expected_action_kind=action_kind,
            expected_human_decision_record_ref=selection.request.human_decision_record_ref,
            expected_request=selection.request,
        )
        record_ref = decision.human_decision_record_ref
        if decision.outcome != "allowed" or record_ref is None or self._human_decisions is None:
            raise AgentActionAuthorityRecordingError(
                "candidate_experiment_reuse_history_ds9_not_established"
            )
        record = self._human_decisions.read_record(
            record_ref, tenant_id=selection.tenant_id, run_id=selection.run_id
        )
        if record.source_kind != "agent_action_authority" or record.source_ref is None:
            raise AgentActionAuthorityRecordingError(
                "candidate_experiment_reuse_history_ds9_not_established"
            )
        source_history = self._load_signed_decision_history(
            closure=selection, job_id=selection.action_job_id, decision_ref=record.source_ref
        )
        source = source_history.decision
        self._require_persisted_action_tuple(
            source,
            action_tuple=action_tuple,
            expected_action_kind=action_kind,
            expected_human_decision_record_ref=None,
            expected_request=selection.request,
        )
        request = source.human_decision_request
        implementation_ref, _ = _REQUEST_BOUND_CANDIDATE_EFFECTS[action_kind]
        if (
            source.outcome != "refused"
            or source.refusal_reasons != ("human_decision_missing",)
            or source.human_decision_record_ref is not None
            or request is None
            or request != decision.human_decision_request
            or request.need_reasons != ["mandate_limited"]
            or record.source_digest != source_history.decision_ref
            or record.human_decision_request_ref != request.request_ref
            or record.decision_request_digest != agent_action_content_hash(request)
            or record.case_id != request.case_id
            or record.rule_version_ref != request.rule_version_ref
            or record.basis_ref != source.contract_ref
            or record.basis_digest != source.contract_content_hash
            or source.contract_ref != decision.contract_ref
            or source.contract_content_hash != decision.contract_content_hash
            or source.permission_snapshot != decision.permission_snapshot
            or source.admission_bundle_ref != decision.admission_bundle_ref
            or source.envelope_id != decision.envelope_id
            or source.envelope_ref != decision.envelope_ref
            or source.effect_binding_id != decision.effect_binding_id
            or source.effect_binding_digest != decision.effect_binding_digest
            or source.effect_implementation_ref != implementation_ref
            or decision.effect_implementation_ref != implementation_ref
            or record.decision_action_exercised != "approve"
            or not record.active_choice
            or not record.five_rights_check.all_pass()
            or record.responsibility_integrity.status != "pass"
            or record.valid_from is None
            or record.valid_until is None
            or not (record.valid_from <= decision.decided_at < record.valid_until)
            or record.recorded_at is None
            or not (
                source.decided_at <= record.decided_at <= record.recorded_at <= decision.decided_at
            )
        ):
            raise AgentActionAuthorityRecordingError(
                "candidate_experiment_reuse_history_ds9_binding_mismatch"
            )
        return history

    def _load_signed_decision_history(
        self,
        *,
        closure: _AuthorityOrigin,
        job_id: str,
        decision_ref: str,
    ) -> AuthenticatedAgentActionDecisionHistory:
        authority = require_factory_produced_deployment_security(
            self._deployment
        ).acquisition_authority
        return load_agent_action_decision_history(
            artifact_store=self._store,
            event_log=self._event_log,
            artifact_verifier=authority.verifier,
            expected_signer_identity=authority.decision_signer_identity,
            write_context=self._context(closure, job_id),
            decision_ref=decision_ref,
        )

    def _for_persisted_decision(
        self,
        *,
        closure: _AuthorityOrigin,
        job_id: str,
        decision_ref: str,
        effect_handler: Callable[[OperationInvocationRecord], object],
        action_tuple: tuple[OperationContract, OperationInvocationRecord, AgentActionIntent],
        binding: AgentActionEffectBinding,
        expected_human_decision_record_ref: str | None,
        expected_action_kind: str = ACQUISITION_ACTION_KIND,
        expected_request: (
            ModelInputSuccessorActionRequest | CandidateExperimentReuseActionRequest | None
        ) = None,
    ) -> AgentActionAuthorityGateway:
        """Reopen one exact PA2 decision and its current mandate and DS9 record."""
        self._require_worker_decision_verification()
        decision = AgentActionAuthorityDecision.model_validate(
            require_declared_profile(read_core_json_artifact(self._store, decision_ref))
        )
        if agent_action_content_hash(decision) != decision_ref:
            raise AgentActionAuthorityRecordingError("acquisition decision content mismatch")
        slot = self._slot(closure, decision.bound_resource_digest or "")
        if slot is None or decision.admission_bundle_ref is None:
            raise AgentActionAuthorityRecordingError("acquisition replay authority slot is empty")
        self._require_persisted_action_tuple(
            decision,
            action_tuple=action_tuple,
            expected_action_kind=expected_action_kind,
            expected_human_decision_record_ref=expected_human_decision_record_ref,
            expected_request=expected_request,
        )
        operation, _, _ = action_tuple
        gateway = AgentActionAuthorityGateway.for_persisted_decision(
            **self._options(closure, job_id, binding, slot),
            decision_ref=decision_ref,
            admission_refs_by_invocation_hash={
                decision.invocation_content_hash: decision.admission_bundle_ref
            },
        )
        resolved = self._require_slot_binding(gateway, slot)
        if decision.human_decision_record_ref is None or self._human_decisions is None:
            raise AgentActionAuthorityRecordingError("acquisition replay human custody missing")
        record = self._human_decisions.read_record(
            decision.human_decision_record_ref,
            tenant_id=closure.tenant_id,
            run_id=closure.run_id,
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

    @staticmethod
    def _require_persisted_action_tuple(
        decision: AgentActionAuthorityDecision,
        *,
        action_tuple: tuple[OperationContract, OperationInvocationRecord, AgentActionIntent],
        expected_action_kind: str,
        expected_human_decision_record_ref: str | None,
        expected_request: (
            ModelInputSuccessorActionRequest | CandidateExperimentReuseActionRequest | None
        ),
    ) -> None:
        operation, invocation, intent = action_tuple
        permission_snapshot = decision.permission_snapshot
        protected_review = protected_action_human_review_requirement(
            action_kind=expected_action_kind,
            operation_id=operation.operation_id,
            operation_version=operation.operation_version,
        )
        if (
            protected_review is None
            or decision.action_kind != expected_action_kind
            or decision.operation_id != operation.operation_id
            or decision.operation_version != operation.operation_version
            or decision.operation_content_hash != agent_action_content_hash(operation)
            or decision.invocation_content_hash != agent_action_content_hash(invocation)
            or decision.intent_content_hash != agent_action_content_hash(intent)
            or (
                expected_human_decision_record_ref is not None
                and decision.human_decision_record_ref != expected_human_decision_record_ref
            )
            or permission_snapshot is None
            or permission_snapshot.required_permission != protected_review[0].value
            or permission_snapshot.resource_digest != decision.bound_resource_digest
        ):
            raise AgentActionAuthorityRecordingError("acquisition replay action tuple changed")
        exact_request_effect = _REQUEST_BOUND_CANDIDATE_EFFECTS.get(expected_action_kind)
        if exact_request_effect is not None:
            try:
                require_request_bound_action_snapshot(
                    permission_snapshot,
                    action_kind=expected_action_kind,
                    request=expected_request,
                )
            except AcquisitionAdmissionBundleBlocked as exc:
                raise AgentActionAuthorityRecordingError(exact_request_effect[1]) from exc

    def _require_worker_decision_verification(self) -> None:
        """Keep production execution outside the generic unsigned legacy replay mode."""
        authority = require_factory_produced_deployment_security(
            self._deployment
        ).acquisition_authority
        if authority.decision_signer_identity is None:
            raise AgentActionAuthorityRecordingError(
                "acquisition_worker_decision_verification_unallocated"
            )

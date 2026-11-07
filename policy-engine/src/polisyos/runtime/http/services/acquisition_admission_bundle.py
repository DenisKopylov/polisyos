"""Produce signed, run-bound admission bundles for acquisition actions only.

This module owns the deterministic producer bridge. It does not own institutional
delegation, current-mandate, human-decision, or effect-execution mappings; those
remain empty until the existing authority gateway resolves separately persisted
institutional evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Protocol

from polisyos.core import artifacts
from polisyos.core.artifacts import read_core_json_artifact
from polisyos.pdc import (
    AuthorityBoundary,
    OperationClass,
    OperationContract,
    OperationInvocationRecord,
)
from polisyos.runtime.http.authorization import ResourceBindingSource
from polisyos.runtime.http.permissions import RuntimePermission
from polisyos.runtime.http.resource_binding import (
    BindingAuthority,
    BoundAuthorizationResource,
    _digest_payload,
)
from polisyos.runtime.http.services.control.artifacts import (
    write_runtime_authority_artifact,
)
from polisyos.runtime.quality.agent_action_authority import (
    ACQUISITION_ACTION_KIND,
    AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
    AGENT_ACTION_ADMISSION_SCHEMA_VERSION,
    AGENT_ACTION_AUTHORITY_RULE_VERSION,
    CANDIDATE_EXPERIMENT_ACTION_KIND,
    DELEGATION_CONTRACT_ARTIFACT_KIND,
    AgentActionAdmissionBundle,
    AgentActionAuthorityWriteContext,
    AgentActionEffectBinding,
    AgentActionIntent,
    agent_action_content_hash,
    agent_action_permission_hash,
)
from polisyos.runtime.quality.authority import GovernanceMetadata
from polisyos.runtime.quality.authority_reconciliation import reconcile_authority_ref
from polisyos.runtime.quality.design_axes.mandate_bounded_delegation import (
    LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION,
)

from .acquisition_action_service import (
    AcquisitionRouteMutationRequest,
    CandidateExperimentRouteMutationRequest,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from polisyos.runtime.http.authorization import BoundActionPermissionVerification
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog

_SIGNER_PURPOSE: Literal["acquisition_admission"] = "acquisition_admission"
_EMPTY_QUERY_SHA256 = f"sha256:{sha256(b'').hexdigest()}"


class _AuthorityArtifactStore(Protocol):
    """Minimum signed CAS operations used by the deterministic producer."""

    def has(self, artifact_id: object) -> bool: ...

    def get_manifest(self, artifact_id: object) -> artifacts.ArtifactManifest: ...

    def get_bytes(self, artifact_id: object) -> bytes: ...

    def sign_artifact(
        self,
        artifact_id: object,
        signer: artifacts.Ed25519Signer,
        *,
        signer_identity: str | None = ...,
    ) -> object: ...

    def verify_signature(
        self,
        artifact_id: object,
        verifier: artifacts.Ed25519Verifier,
        *,
        strict_identity: bool | None = ...,
    ) -> artifacts.SignatureVerificationResult: ...


class AcquisitionAdmissionBundleBlocked(ValueError):  # noqa: N818 - governed admission outcome
    """Typed fail-closed outcome from deterministic acquisition admission."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AcquisitionAdmissionSigningSlot:
    """One purpose-scoped signer and verifier slot, empty in production by default."""

    signer: artifacts.Ed25519Signer | None = None
    verifier: artifacts.Ed25519Verifier | None = None
    signer_identity: str | None = None
    purpose: Literal["acquisition_admission"] = _SIGNER_PURPOSE

    @classmethod
    def empty(cls) -> AcquisitionAdmissionSigningSlot:
        """Return the intentionally unconfigured production signing slot."""

        return cls()

    @classmethod
    def configured(
        cls,
        *,
        signer: artifacts.Ed25519Signer,
        verifier: artifacts.Ed25519Verifier,
        signer_identity: str,
    ) -> AcquisitionAdmissionSigningSlot:
        """Construct one fully typed, acquisition-purpose signing configuration."""

        return cls(signer=signer, verifier=verifier, signer_identity=signer_identity)

    def require_configured(
        self,
    ) -> tuple[artifacts.Ed25519Signer, artifacts.Ed25519Verifier, str]:
        """Return the complete signing tuple or fail before an artifact write."""

        if (
            type(self.signer) is not artifacts.Ed25519Signer
            or type(self.verifier) is not artifacts.Ed25519Verifier
            or not isinstance(self.signer_identity, str)
            or not self.signer_identity.strip()
            or self.purpose != _SIGNER_PURPOSE
        ):
            raise AcquisitionAdmissionBundleBlocked("acquisition_admission_signer_unconfigured")
        return self.signer, self.verifier, self.signer_identity


PRODUCTION_ACQUISITION_ADMISSION_SIGNING_SLOT = AcquisitionAdmissionSigningSlot.empty()


@dataclass(frozen=True, slots=True)
class AcquisitionAdmissionBundleReceipt:
    """Read-back-verified bundle receipt and the exact gateway invocation mapping."""

    bundle: AgentActionAdmissionBundle
    artifact_ref: str
    payload_sha256: str
    durable_event_id: str
    invocation_refs: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class AcquisitionAdmissionBundleProducer:
    """Persist and sign deterministic admission bundles for acquisition-only tuples."""

    artifact_store: _AuthorityArtifactStore
    event_log: RuntimeDiagnosticEventLog
    signing_slot: AcquisitionAdmissionSigningSlot
    write_context: AgentActionAuthorityWriteContext

    def admit(
        self,
        *,
        delegation_contract_ref: str,
        operation: OperationContract,
        invocation: OperationInvocationRecord,
        intent: AgentActionIntent,
        bound_permission: BoundActionPermissionVerification,
        effect_binding: AgentActionEffectBinding,
        admitted_at: datetime,
        request: (
            AcquisitionRouteMutationRequest | CandidateExperimentRouteMutationRequest | None
        ) = None,
    ) -> AcquisitionAdmissionBundleReceipt:
        """Persist, sign, reconcile, and map one exact acquisition invocation bundle."""

        signer, verifier, signer_identity = self.signing_slot.require_configured()
        self._require_acquisition_tuple(operation=operation, invocation=invocation, intent=intent)
        self._require_effect_binding(
            operation=operation,
            intent=intent,
            effect_binding=effect_binding,
        )
        self._require_persisted_delegation_contract(delegation_contract_ref)

        invocation_hash = agent_action_content_hash(invocation)
        operation_hash = agent_action_content_hash(operation)
        intent_hash = agent_action_content_hash(intent)
        try:
            permission_hash = agent_action_permission_hash(bound_permission)
        except (TypeError, ValueError) as exc:
            raise AcquisitionAdmissionBundleBlocked("acquisition_permission_proof_invalid") from exc
        resource_digest = _recompute_resource_digest(
            bound_permission, action_kind=intent.action_kind, request=request
        )

        bundle = AgentActionAdmissionBundle(
            bundle_id=f"acquisition-admission.{invocation_hash[7:31]}",
            bundle_ref=f"runtime://acquisition-admission/{invocation_hash[7:]}",
            invocation_content_hash=invocation_hash,
            operation_content_hash=operation_hash,
            intent_content_hash=intent_hash,
            permission_proof_hash=permission_hash,
            bound_resource_digest=resource_digest,
            delegation_contract_ref=delegation_contract_ref,
            effect_binding_digest=effect_binding.binding_digest,
            memory_claim_payload={},
            authority_input_payload={},
            tool_ledger=None,
            hypothesis_ledger=None,
            authority_boundary=_admission_boundary(),
            rule_version_ref=AGENT_ACTION_AUTHORITY_RULE_VERSION,
            admitted_at=admitted_at,
        )
        result = write_runtime_authority_artifact(
            self.artifact_store,
            self.event_log,
            bundle.model_dump(mode="json"),
            _admission_write_options(),
            **self._authority_fields(bundle=bundle, contract_ref=delegation_contract_ref),
        )
        artifact_ref = str(result.cas_ref.artifact_id)
        self.artifact_store.sign_artifact(
            result.cas_ref.artifact_id,
            signer,
            signer_identity=signer_identity,
        )
        signature = self.artifact_store.verify_signature(
            result.cas_ref.artifact_id,
            verifier,
            strict_identity=True,
        )
        if (
            signature.status is not artifacts.SignatureVerificationStatus.VALID
            or signature.signer_identity != signer_identity
        ):
            raise AcquisitionAdmissionBundleBlocked("acquisition_admission_signer_untrusted")
        report = reconcile_authority_ref(
            artifact_store=self.artifact_store,
            event_log=self.event_log,
            cas_ref=artifact_ref,
            expected_tenant_id=self.write_context.tenant_id,
            expected_cell_id=self.write_context.cell_id,
            expected_run_id=self.write_context.run_id,
            expected_job_id=self.write_context.job_id,
        )
        read_back = read_core_json_artifact(self.artifact_store, result.cas_ref).value
        try:
            persisted_bundle = AgentActionAdmissionBundle.model_validate(read_back)
        except (
            TypeError,
            ValueError,
        ) as exc:  # pragma: no cover - writer/readback invariant
            raise AcquisitionAdmissionBundleBlocked(
                "acquisition_admission_readback_invalid"
            ) from exc
        if persisted_bundle != bundle:
            raise AcquisitionAdmissionBundleBlocked("acquisition_admission_readback_mismatch")
        payload_sha256 = f"sha256:{result.payload_sha256}"
        if payload_sha256 != artifact_ref:
            raise AcquisitionAdmissionBundleBlocked("acquisition_admission_hash_mismatch")
        if report.durable_event_id is None:  # pragma: no cover - reconciliation invariant
            raise AcquisitionAdmissionBundleBlocked("acquisition_admission_event_missing")
        return AcquisitionAdmissionBundleReceipt(
            bundle=bundle,
            artifact_ref=artifact_ref,
            payload_sha256=payload_sha256,
            durable_event_id=report.durable_event_id,
            invocation_refs=MappingProxyType({invocation_hash: artifact_ref}),
        )

    def _require_acquisition_tuple(
        self,
        *,
        operation: OperationContract,
        invocation: OperationInvocationRecord,
        intent: AgentActionIntent,
    ) -> None:
        action_kind = intent.action_kind
        expected_class: OperationClass | None = None
        if action_kind == CANDIDATE_EXPERIMENT_ACTION_KIND:
            expected_class = OperationClass.ACQUIRE
        elif action_kind != ACQUISITION_ACTION_KIND:
            raise AcquisitionAdmissionBundleBlocked("acquisition_action_tuple_invalid")
        if (
            getattr(operation, "operation_id", None) != action_kind
            or getattr(operation, "operation_version", None) != "v1"
            or getattr(invocation, "operation_id", None) != action_kind
            or getattr(invocation, "operation_version", None) != "v1"
            or (expected_class is not None and operation.operation_class is not expected_class)
        ):
            raise AcquisitionAdmissionBundleBlocked("acquisition_action_tuple_invalid")

    @staticmethod
    def _require_effect_binding(
        *,
        operation: OperationContract,
        intent: AgentActionIntent,
        effect_binding: AgentActionEffectBinding,
    ) -> None:
        if effect_binding.key != (
            intent.action_kind,
            operation.operation_id,
            operation.operation_version,
        ):
            raise AcquisitionAdmissionBundleBlocked("acquisition_effect_binding_invalid")

    def _require_persisted_delegation_contract(self, contract_ref: str) -> None:
        try:
            artifact_id = artifacts.ArtifactID.model_validate(contract_ref)
            if not self.artifact_store.has(artifact_id):
                raise ValueError("delegation contract is absent from CAS")
            manifest = self.artifact_store.get_manifest(artifact_id)
            schema = manifest.artifact_schema
            if (
                manifest.kind != DELEGATION_CONTRACT_ARTIFACT_KIND
                or schema is None
                or schema.name != "polisyos.runtime.DelegationContract"
                or schema.version != LAYER2_S7_AGENT_ACTION_DELEGATION_SCHEMA_VERSION
            ):
                raise ValueError("delegation contract artifact contract does not match")
            reconcile_authority_ref(
                artifact_store=self.artifact_store,
                event_log=self.event_log,
                cas_ref=contract_ref,
                expected_tenant_id=self.write_context.tenant_id,
                expected_cell_id=self.write_context.cell_id,
                expected_run_id=self.write_context.run_id,
                expected_job_id=self.write_context.job_id,
            )
        except Exception as exc:
            raise AcquisitionAdmissionBundleBlocked(
                "acquisition_delegation_contract_not_persisted"
            ) from exc

    def _authority_fields(
        self,
        *,
        bundle: AgentActionAdmissionBundle,
        contract_ref: str,
    ) -> dict[str, object]:
        context = self.write_context
        closure_hash = agent_action_content_hash(
            {
                "tenant_id": context.tenant_id,
                "cell_id": context.cell_id,
                "run_id": context.run_id,
                "job_id": context.job_id,
                "contract_ref": contract_ref,
                "invocation_content_hash": bundle.invocation_content_hash,
            }
        )
        timestamp = bundle.admitted_at.isoformat()
        return {
            "evidence_id": bundle.bundle_id,
            "evidence_class": "authority_bearing",
            "authority_role": "producer_authority",
            "provenance_kind": "runtime_emitted",
            "owner": context.owner,
            "reader_contract": "runtime.acquisition_admission_bundle.reader",
            "reader_contract_version": "1.0",
            "tenant_id": context.tenant_id,
            "cell_id": context.cell_id,
            "run_id": context.run_id,
            "job_id": context.job_id,
            "trace_id": context.trace_id,
            "span_id": context.span_id,
            "parent_span_id": context.parent_span_id,
            "requested_execution_profile": context.requested_execution_profile,
            "effective_execution_profile": context.effective_execution_profile,
            "phase": "acquisition_admission_bundle",
            "generated_at": timestamp,
            "as_of_time": timestamp,
            "same_input_closure": {
                "closure_id": f"acquisition-admission.{closure_hash[7:31]}",
                "status": "closed",
                "run_id": context.run_id,
                "job_id": context.job_id,
                "tenant_id": context.tenant_id,
                "cell_id": context.cell_id,
                "effective_mode_ref": context.effective_mode_ref,
                "degradation_ledger_ref": context.degradation_ledger_ref,
                "evidence_input_refs": [contract_ref],
                "closure_sha256": closure_hash[7:],
            },
            "input_refs": [contract_ref],
            "effective_mode_ref": context.effective_mode_ref,
            "degradation_ledger_ref": context.degradation_ledger_ref,
            "semantic_binding_ref": bundle.effect_binding_digest,
            "validation_status": "pass",
            "blocking_status": "non_blocking",
            "governance": GovernanceMetadata(
                classification="internal",
                authority_boundary="runtime.acquisition_admission_bundle",
                pii="none",
                retention_policy="runtime-quality-90d",
                review_status="runtime_verified",
                override_policy="no_override",
                approval_policy="owner_signature_required",
            ),
        }


def _admission_boundary() -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=["agent_action_input_admission"],
        may_not_use_for=[
            "claim_evidence",
            "publication_authority",
            "promotion_authority",
        ],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[AGENT_ACTION_AUTHORITY_RULE_VERSION],
    )


def _recompute_resource_digest(
    bound_permission: BoundActionPermissionVerification,
    *,
    action_kind: str,
    request: AcquisitionRouteMutationRequest | CandidateExperimentRouteMutationRequest | None,
) -> str:
    """Recompute only the request schema canonically bound to this action kind."""

    resource = bound_permission.bound_resource
    requirement = bound_permission.verification.requirement
    binding = requirement.resource_binding
    if action_kind == ACQUISITION_ACTION_KIND:
        request_model = AcquisitionRouteMutationRequest
        resource_kind = "runtime.evidence.acquisition"
    elif action_kind == CANDIDATE_EXPERIMENT_ACTION_KIND:
        request_model = CandidateExperimentRouteMutationRequest
        resource_kind = "runtime.evidence.acquisition.candidate_experiment"
    else:
        raise AcquisitionAdmissionBundleBlocked("acquisition_action_tuple_invalid")
    request_fields = tuple(request_model.model_fields)
    required_request_fields = tuple(
        field_name
        for field_name, field in request_model.model_fields.items()
        if field.is_required()
    )
    selector_names = tuple(name for name, _value in resource.canonical_selectors)
    expected_request = request
    if expected_request is None:
        if action_kind == CANDIDATE_EXPERIMENT_ACTION_KIND:
            raise AcquisitionAdmissionBundleBlocked("acquisition_resource_binding_invalid")
    elif type(expected_request) is not request_model:
        raise AcquisitionAdmissionBundleBlocked("acquisition_resource_binding_invalid")
    expected_selectors = None
    if expected_request is not None:
        body = expected_request.model_dump(mode="json")
        expected_selectors = tuple(
            sorted(
                (
                    field,
                    '{"present":false}'
                    if body[field] is None
                    else json.dumps(
                        body[field],
                        ensure_ascii=True,
                        allow_nan=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                )
                for field in request_fields
            )
        )
    if (
        type(resource) is not BoundAuthorizationResource
        or resource.requirement is not requirement
        or resource.resource_kind != f"{resource_kind}.{resource.authority.value}"
        or requirement.permission is not RuntimePermission.EVIDENCE_ACQUIRE
        or binding.source is not ResourceBindingSource.REQUEST_COMPOSITE
        or binding.resource_kind != resource_kind
        or binding.selector_fields != request_fields
        or binding.required_selector_fields != required_request_fields
        or binding.required_selector_alternatives
        or selector_names != tuple(sorted(request_fields))
        or (expected_selectors is not None and resource.canonical_selectors != expected_selectors)
        or resource.authority is not BindingAuthority.REQUEST_BOUND
        or resource.tenant_id is not None
        or resource.resolved_context is not None
        or (
            action_kind == CANDIDATE_EXPERIMENT_ACTION_KIND
            and resource.query_sha256 != _EMPTY_QUERY_SHA256
        )
    ):
        raise AcquisitionAdmissionBundleBlocked("acquisition_resource_binding_invalid")
    digest = _digest_payload(
        {
            "binding_version": "runtime.authorization.resource.v1",
            "permission": requirement.permission.value,
            "resource_kind": binding.resource_kind,
            "authority": resource.authority.value,
            "tenant_id": resource.tenant_id,
            "body_sha256": resource.body_sha256,
            "query_sha256": resource.query_sha256,
            "selectors": resource.canonical_selectors,
            "resolved_context_sha256": None,
        }
    )
    if resource.resource_digest != digest:
        raise AcquisitionAdmissionBundleBlocked("acquisition_resource_digest_mismatch")
    return digest


def require_candidate_experiment_bound_permission(
    bound_permission: BoundActionPermissionVerification,
    request: CandidateExperimentRouteMutationRequest,
) -> str:
    """Require a real DS20 proof bound to this exact candidate DTO and no query."""
    return _recompute_resource_digest(
        bound_permission,
        action_kind=CANDIDATE_EXPERIMENT_ACTION_KIND,
        request=request,
    )


def candidate_experiment_request_resource_digest(
    request: CandidateExperimentRouteMutationRequest,
    *,
    body_sha256: str,
    query_sha256: str,
) -> str:
    """Rebuild the exact request-bound candidate resource digest from PA2 snapshot hashes."""
    if type(request) is not CandidateExperimentRouteMutationRequest:
        raise AcquisitionAdmissionBundleBlocked("acquisition_resource_binding_invalid")
    return _request_resource_digest(
        action_kind=CANDIDATE_EXPERIMENT_ACTION_KIND,
        request=request,
        body_sha256=body_sha256,
        query_sha256=query_sha256,
        authority=BindingAuthority.REQUEST_BOUND,
        tenant_id=None,
    )


def _request_resource_digest(
    *,
    action_kind: str,
    request: AcquisitionRouteMutationRequest | CandidateExperimentRouteMutationRequest,
    body_sha256: str,
    query_sha256: str,
    authority: BindingAuthority,
    tenant_id: str | None,
) -> str:
    """Hash one closed action-kind/request-model pair using authorization encoding."""
    if action_kind == ACQUISITION_ACTION_KIND and type(request) is AcquisitionRouteMutationRequest:
        resource_kind = "runtime.evidence.acquisition"
    elif (
        action_kind == CANDIDATE_EXPERIMENT_ACTION_KIND
        and type(request) is CandidateExperimentRouteMutationRequest
    ):
        resource_kind = "runtime.evidence.acquisition.candidate_experiment"
    else:
        raise AcquisitionAdmissionBundleBlocked("acquisition_action_tuple_invalid")
    body = request.model_dump(mode="json")
    selectors = tuple(
        sorted(
            (
                field,
                '{"present":false}'
                if body[field] is None
                else json.dumps(
                    body[field],
                    ensure_ascii=True,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
            for field in type(request).model_fields
        )
    )
    return _digest_payload(
        {
            "binding_version": "runtime.authorization.resource.v1",
            "permission": RuntimePermission.EVIDENCE_ACQUIRE.value,
            "resource_kind": resource_kind,
            "authority": authority.value,
            "tenant_id": tenant_id,
            "body_sha256": body_sha256,
            "query_sha256": query_sha256,
            "selectors": selectors,
            "resolved_context_sha256": None,
        }
    )


def _admission_write_options() -> artifacts.ArtifactWriteOptions:
    return artifacts.ArtifactWriteOptions(
        kind=AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
        media_type="application/json",
        schema=artifacts.SchemaInfo(
            name="polisyos.runtime.AgentActionAdmissionBundle",
            version=AGENT_ACTION_ADMISSION_SCHEMA_VERSION,
        ),
        producer=artifacts.ProducerInfo(
            component="polisyos.runtime.http.services.acquisition_admission_bundle",
            version="2026.08.30+deterministic-admission",
        ),
        governance=artifacts.ArtifactGovernanceInfo(classification="internal"),
        inputs=[],
    )


__all__ = [
    "PRODUCTION_ACQUISITION_ADMISSION_SIGNING_SLOT",
    "AcquisitionAdmissionBundleBlocked",
    "AcquisitionAdmissionBundleProducer",
    "AcquisitionAdmissionBundleReceipt",
    "AcquisitionAdmissionSigningSlot",
]

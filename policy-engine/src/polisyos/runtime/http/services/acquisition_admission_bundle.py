"""Produce signed, run-bound admission bundles for acquisition actions only.

This module owns the deterministic producer bridge. It does not own institutional
delegation, current-mandate, human-decision, or effect-execution mappings; those
remain empty until the existing authority gateway resolves separately persisted
institutional evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Protocol

from polisyos.core import artifacts, canon
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactManifest,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.signing import (
    Ed25519Signer,
    Ed25519Verifier,
    SignatureVerificationResult,
    SignatureVerificationStatus,
)
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.pdc import AuthorityBoundary, OperationContract, OperationInvocationRecord
from polisyos.runtime.http.services.control.artifacts import write_runtime_authority_artifact
from polisyos.runtime.quality.agent_action_authority import (
    ACQUISITION_ACTION_KIND,
    AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
    AGENT_ACTION_ADMISSION_SCHEMA_VERSION,
    AGENT_ACTION_AUTHORITY_RULE_VERSION,
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

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from polisyos.runtime.http.authorization import BoundActionPermissionVerification

_SIGNER_PURPOSE: Literal["acquisition_admission"] = "acquisition_admission"


class _AuthorityArtifactStore(Protocol):
    """Minimum signed CAS operations used by the deterministic producer."""

    def has(self, artifact_id: object) -> bool: ...

    def get_manifest(self, artifact_id: object) -> ArtifactManifest: ...

    def get_bytes(self, artifact_id: object) -> bytes: ...

    def sign_artifact(
        self,
        artifact_id: object,
        signer: Ed25519Signer,
        *,
        signer_identity: str | None = ...,
    ) -> object: ...

    def verify_signature(
        self,
        artifact_id: object,
        verifier: Ed25519Verifier,
        *,
        strict_identity: bool | None = ...,
    ) -> SignatureVerificationResult: ...


class AcquisitionAdmissionBundleBlocked(ValueError):  # noqa: N818 - governed admission outcome
    """Typed fail-closed outcome from deterministic acquisition admission."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AcquisitionAdmissionSigningSlot:
    """One purpose-scoped signer and verifier slot, empty in production by default."""

    signer: Ed25519Signer | None = None
    verifier: Ed25519Verifier | None = None
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
        signer: Ed25519Signer,
        verifier: Ed25519Verifier,
        signer_identity: str,
    ) -> AcquisitionAdmissionSigningSlot:
        """Construct one fully typed, acquisition-purpose signing configuration."""

        return cls(signer=signer, verifier=verifier, signer_identity=signer_identity)

    def require_configured(self) -> tuple[Ed25519Signer, Ed25519Verifier, str]:
        """Return the complete signing tuple or fail before an artifact write."""

        if (
            type(self.signer) is not Ed25519Signer
            or type(self.verifier) is not Ed25519Verifier
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
    event_log: object
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
        resource_digest = getattr(
            getattr(bound_permission, "bound_resource", None),
            "resource_digest",
            None,
        )
        if not isinstance(resource_digest, str):
            raise AcquisitionAdmissionBundleBlocked("acquisition_resource_binding_invalid")

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
            signature.status is not SignatureVerificationStatus.VALID
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
        read_back = canon.from_canonical_bytes(
            self.artifact_store.get_bytes(result.cas_ref.artifact_id)
        )
        try:
            persisted_bundle = AgentActionAdmissionBundle.model_validate(read_back)
        except (TypeError, ValueError) as exc:  # pragma: no cover - writer/readback invariant
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
        if (
            intent.action_kind != ACQUISITION_ACTION_KIND
            or getattr(operation, "operation_id", None) != ACQUISITION_ACTION_KIND
            or getattr(operation, "operation_version", None) != "v1"
            or getattr(invocation, "operation_id", None) != ACQUISITION_ACTION_KIND
            or getattr(invocation, "operation_version", None) != "v1"
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
        may_not_use_for=["claim_evidence", "publication_authority", "promotion_authority"],
        source_authority="deterministic_producer",
        posture="governed",
        rule_version_refs=[AGENT_ACTION_AUTHORITY_RULE_VERSION],
    )


def _admission_write_options() -> ArtifactWriteOptions:
    return ArtifactWriteOptions(
        kind=AGENT_ACTION_ADMISSION_ARTIFACT_KIND,
        media_type="application/json",
        schema=SchemaInfo(
            name="polisyos.runtime.AgentActionAdmissionBundle",
            version=AGENT_ACTION_ADMISSION_SCHEMA_VERSION,
        ),
        producer=ProducerInfo(
            component="polisyos.runtime.http.services.acquisition_admission_bundle",
            version="2026.08.30+deterministic-admission",
        ),
        governance=ArtifactGovernanceInfo(classification="internal"),
        inputs=[],
    )


__all__ = [
    "PRODUCTION_ACQUISITION_ADMISSION_SIGNING_SLOT",
    "AcquisitionAdmissionBundleBlocked",
    "AcquisitionAdmissionBundleProducer",
    "AcquisitionAdmissionBundleReceipt",
    "AcquisitionAdmissionSigningSlot",
]

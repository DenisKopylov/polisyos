"""Deployment-owned epoch evidence and appointment selection.

Configuration supplies public trust and exact evidence selectors.  Candidates
cannot appoint their own verifier, and verification never supplies signing keys.
Each factory instance has a separate registry and a scoped composition context.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003 - Pydantic resolves configuration annotations at runtime.
from typing import TYPE_CHECKING, Literal, TypeVar
from weakref import WeakKeyDictionary

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import FileSystemSignedArtifactEvidenceRepository, artifacts, contracts, security

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from polisyos.runtime.quality.chronology_proof import _ChronologyPersistenceRegistry
    from polisyos.runtime.quality.epoch_certificate_issuance import (
        EpochCertificateIssuanceInputResolver,
    )
    from polisyos.runtime.quality.epoch_transition_inputs import EpochOwnerDispositionEvidenceReader
    from polisyos.runtime.quality.epoch_transition_origin import (
        AdmittedEpochTransitionSigningProfile,
    )
    from polisyos.runtime.quality.epoch_validity_cascade import (
        EpochPerturbationAdjudicationProvider,
    )

contract = contracts.chronology
_Model = TypeVar("_Model", bound=BaseModel)
EpochTrustRole = Literal[
    "signing_profile_admission",
    "transition_signature",
    "predicate_policy_admission",
    "predicate_owner_verification",
    "acceptance_appointment",
    "holder_appointment",
]


class EpochTrustedIssuerConfig(BaseModel):
    """Explicit public key and the evidence roles for which it is trusted."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    identity: str = Field(min_length=1)
    public_key_path: Path
    roles: tuple[EpochTrustRole, ...] = ()


class EpochTransitionSigningProfile(BaseModel):
    """Exact public verifier policy for one transition authority purpose."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["polisyos.epoch.transition-signing-profile.v1"] = (
        "polisyos.epoch.transition-signing-profile.v1"
    )
    signer_key_ids: tuple[str, ...] = Field(min_length=1)
    authority_purpose: str = Field(min_length=1)


class EpochSigningProfileAdmissionStatement(BaseModel):
    """Owner-signed admission of exact profile bytes for an exact query."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["polisyos.epoch.signing-profile-admission.v1"] = (
        "polisyos.epoch.signing-profile-admission.v1"
    )
    signing_profile_ref: artifacts.ArtifactRef
    signing_profile_content_hash: contract.Digest
    authority_purpose: str = Field(min_length=1)
    requested_query_context_ref: contract.Digest


class EpochAppointmentEvidenceConfig(BaseModel):
    """Select exact signed appointment and independent verification records."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    appointment_evidence_ref: artifacts.ArtifactRef
    verification_evidence_ref: artifacts.ArtifactRef


class EpochDeploymentConfig(BaseModel):
    """Optional epoch trust, policy and institutional evidence exchange inputs.

    Receipt selectors refer to existing canonical DTOs in the evidence CAS.
    Their contents remain evidence until the unchanged consumers verify them.
    No path is a signer appointment and no private key is accepted here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_cas_root: Path | None = None
    native_epoch_history_root: Path | None = None
    trusted_issuers: tuple[EpochTrustedIssuerConfig, ...] = ()
    revoked_key_ids: tuple[str, ...] = ()
    signing_profile_admission_refs: tuple[artifacts.ArtifactRef, ...] = ()
    transition_signed_evidence_refs: tuple[artifacts.ArtifactRef, ...] = ()
    predicate_policy_admission_refs: tuple[artifacts.ArtifactRef, ...] = ()
    predicate_owner_verification_refs: tuple[artifacts.ArtifactRef, ...] = ()
    native_candidate_refs: tuple[artifacts.ArtifactRef, ...] = ()
    acceptance_appointments: tuple[EpochAppointmentEvidenceConfig, ...] = ()
    holder_appointments: tuple[EpochAppointmentEvidenceConfig, ...] = ()
    acceptance_receipt_refs: tuple[artifacts.ArtifactRef, ...] = ()
    retention_receipt_refs: tuple[artifacts.ArtifactRef, ...] = ()
    readback_receipt_refs: tuple[artifacts.ArtifactRef, ...] = ()
    acceptance_lineage_root: Path | None = None


@dataclass(frozen=True, slots=True)
class _EpochDeploymentState:
    config: EpochDeploymentConfig
    keys: tuple[tuple[str, bytes, tuple[EpochTrustRole, ...]], ...]
    store: artifacts.FileSystemCAS | None
    registry: _ChronologyPersistenceRegistry
    native_policy_verifier: contract.PredicatePolicyOwnerProvenanceVerifier | None
    native_policy_operation: (
        Callable[
            ...,
            contract.VerifiedPredicatePolicyOwnerRelation
            | contract.PredicatePolicyOwnerRelationFailure,
        ]
        | None
    )
    issuance_input_resolver: EpochCertificateIssuanceInputResolver | None
    adjudication_provider: EpochPerturbationAdjudicationProvider | None
    disposition_reader: EpochOwnerDispositionEvidenceReader | None
    component_operations: tuple[tuple[object, str, Callable[..., object]], ...]


_OWNERS: WeakKeyDictionary[EpochDeployment, _EpochDeploymentState] = WeakKeyDictionary()
_COMPOSITION: ContextVar[EpochDeployment | None] = ContextVar("epoch_deployment", default=None)


class EpochDeployment:
    """Factory identity whose immutable owner state is held outside callers."""

    __slots__ = ("__weakref__",)

    def __init__(self) -> None:
        raise TypeError("use build_epoch_deployment(config)")

    def _state(self) -> _EpochDeploymentState:
        if type(self) is not EpochDeployment or self not in _OWNERS:
            raise ValueError("epoch deployment is not a registered factory identity")
        return _OWNERS[self]

    def attestation_state(self) -> dict[str, object]:
        """Return the pinned configuration and public-key snapshot identity."""
        state = self._state()
        operation = state.native_policy_operation
        if (
            state.native_policy_verifier is not None
            and getattr(state.native_policy_verifier, "verify_owner_relation", None) != operation
        ):
            raise ValueError("native policy verifier operation changed after deployment")
        for component, method, captured in state.component_operations:
            if getattr(component, method, None) != captured:
                raise ValueError("epoch owner component operation changed after deployment")
        return {
            "config": state.config.model_dump(mode="json"),
            "keys": [
                (identity, security.raw_content_hash(pem), roles)
                for identity, pem, roles in state.keys
            ],
            "native_policy_verifier": id(state.native_policy_verifier)
            if operation is not None
            else None,
            "native_policy_operation": id(getattr(operation, "__func__", operation))
            if operation is not None
            else None,
            "owner_components": [
                (id(component), method, id(getattr(captured, "__func__", captured)))
                for component, method, captured in state.component_operations
            ],
        }

    @contextmanager
    def composition_scope(self) -> Iterator[None]:
        """Bind no-argument composition only for this lexical execution scope."""
        self._state()
        token = _COMPOSITION.set(self)
        try:
            yield
        finally:
            _COMPOSITION.reset(token)

    def _repository(self) -> FileSystemSignedArtifactEvidenceRepository:
        store = self._state().store
        if store is None:
            raise ValueError("epoch evidence repository is not configured")
        return FileSystemSignedArtifactEvidenceRepository(store)

    def _verifier(self, role: EpochTrustRole) -> artifacts.Ed25519Verifier:
        state = self._state()
        verifier = artifacts.Ed25519Verifier(strict_identity=True)
        for identity, pem, roles in state.keys:
            if role in roles:
                verifier.load_trusted_key_pem(pem, identity=identity)
        for key_id in state.config.revoked_key_ids:
            verifier.add_revoked_key_id(key_id)
        return verifier

    def _read_model(self, ref: artifacts.ArtifactRef, model: type[_Model]) -> _Model:
        raw = self._repository().read_raw(artifact_ref=ref)
        return security.parse_canonical_statement(raw, model)

    def _signed_model(
        self,
        ref: artifacts.ArtifactRef,
        model: type[_Model],
        role: EpochTrustRole,
    ) -> tuple[_Model, contract.SignedArtifactEvidenceRecord, contract.SignedArtifactEvidence]:
        evidence = self._repository().read_exact(evidence_record_ref=ref)
        if not security.verify_signed_evidence(evidence, verifier=self._verifier(role)):
            raise ValueError("epoch evidence signature is not trusted for its role")
        record = security.parse_canonical_statement(
            evidence.persisted.record_bytes,
            contract.SignedArtifactEvidenceRecord,
        )
        return security.parse_canonical_statement(evidence.blob_bytes, model), record, evidence

    def resolve_admitted_signing_profile(
        self,
        *,
        signing_profile_ref: artifacts.ArtifactRef,
        authority_purpose: str,
        requested_query_context_ref: contract.Digest,
    ) -> AdmittedEpochTransitionSigningProfile:
        """Resolve one exact independently signed profile admission and its bytes."""
        from polisyos.runtime.quality.epoch_transition_origin import (
            AdmittedEpochTransitionSigningProfile,
        )

        try:
            matches = []
            for ref in self._state().config.signing_profile_admission_refs:
                admission, record, _ = self._signed_model(
                    ref,
                    EpochSigningProfileAdmissionStatement,
                    "signing_profile_admission",
                )
                if (
                    admission.signing_profile_ref == signing_profile_ref
                    and admission.authority_purpose == authority_purpose
                    and admission.requested_query_context_ref == requested_query_context_ref
                ):
                    matches.append((admission, record))
            if len(matches) != 1:
                raise ValueError("epoch signing profile admission missing or ambiguous")
            admission, record = matches[0]
            profile = self._read_model(signing_profile_ref, EpochTransitionSigningProfile)
            if (
                profile.authority_purpose != authority_purpose
                or admission.signing_profile_content_hash != str(signing_profile_ref.artifact_id)
            ):
                raise ValueError("epoch signing profile admission binding mismatch")
            return AdmittedEpochTransitionSigningProfile(
                signing_profile_ref=signing_profile_ref,
                signing_profile_content_hash=admission.signing_profile_content_hash,
                admission_ref=record.artifact_ref,
                admission_content_hash=record.raw_blob_bytes_hash,
                authority_purpose=authority_purpose,
                requested_query_context_ref=requested_query_context_ref,
            )
        except (KeyError, OSError, RuntimeError, TypeError) as exc:
            raise ValueError("epoch signing profile evidence unavailable") from exc

    def verify_transition_signature(
        self,
        *,
        evidence: contract.SignedArtifactEvidence,
        signing_profile_ref: artifacts.ArtifactRef,
        authority_purpose: str,
        requested_query_context_ref: contract.Digest,
    ) -> bool:
        """Verify exact evidence under an independently resolved admitted profile."""
        try:
            self.resolve_admitted_signing_profile(
                signing_profile_ref=signing_profile_ref,
                authority_purpose=authority_purpose,
                requested_query_context_ref=requested_query_context_ref,
            )
            profile = self._read_model(signing_profile_ref, EpochTransitionSigningProfile)
            record = security.parse_canonical_statement(
                evidence.persisted.record_bytes,
                contract.SignedArtifactEvidenceRecord,
            )
            signature = artifacts.DetachedSignature.model_validate_json(
                evidence.detached_signature_bytes,
            )
            return (
                record.signing_profile_ref == signing_profile_ref
                and signature.key_id in profile.signer_key_ids
                and security.verify_signed_evidence(
                    evidence,
                    verifier=self._verifier("transition_signature"),
                )
            )
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return False

    @property
    def epoch_certificate_issuance_input_resolver(
        self,
    ) -> EpochCertificateIssuanceInputResolver | None:
        """Return the privileged admitted issuance source captured at deployment."""
        self.attestation_state()
        return self._state().issuance_input_resolver

    @property
    def epoch_perturbation_adjudication_provider(
        self,
    ) -> EpochPerturbationAdjudicationProvider | None:
        """Return the complete target-owner adjudication source, if configured."""
        self.attestation_state()
        return self._state().adjudication_provider

    @property
    def epoch_owner_disposition_evidence_reader(self) -> EpochOwnerDispositionEvidenceReader | None:
        """Return the independently admitted disposition read authority."""
        self.attestation_state()
        return self._state().disposition_reader

    @property
    def native_epoch_history_root(self) -> Path | None:
        """Return the explicit native history owner path without appointing authority."""
        return self._state().config.native_epoch_history_root

    @property
    def has_transition_evidence_configuration(self) -> bool:
        """Report concrete evidence inputs; this does not admit any transition."""
        state = self._state()
        roles = {role for _, _, roles in state.keys for role in roles}
        return bool(
            state.store is not None
            and state.config.signing_profile_admission_refs
            and state.config.transition_signed_evidence_refs
            and {"signing_profile_admission", "transition_signature"} <= roles
        )

    def resolve_exact_signed_transition(
        self,
        *,
        transition_bytes: bytes,
        authority_purpose: str,
        requested_query_context_ref: contract.Digest,
    ) -> contract.SignedArtifactEvidence:
        """Read externally signed exact transition bytes under admitted public trust."""
        try:
            matches = []
            for ref in self._state().config.transition_signed_evidence_refs:
                evidence = self._repository().read_exact(evidence_record_ref=ref)
                if evidence.blob_bytes != transition_bytes:
                    continue
                record = security.parse_canonical_statement(
                    evidence.persisted.record_bytes,
                    contract.SignedArtifactEvidenceRecord,
                )
                if not self.verify_transition_signature(
                    evidence=evidence,
                    signing_profile_ref=record.signing_profile_ref,
                    authority_purpose=authority_purpose,
                    requested_query_context_ref=requested_query_context_ref,
                ):
                    raise ValueError("configured exact transition signature is unverified")
                matches.append(evidence)
            if len(matches) != 1:
                raise ValueError("exact signed transition missing or ambiguous")
            return matches[0]
        except (KeyError, OSError, RuntimeError, TypeError) as exc:
            raise ValueError("exact signed transition evidence unavailable") from exc


def build_epoch_deployment(
    config: EpochDeploymentConfig | None,
    *,
    native_policy_verifier: contract.PredicatePolicyOwnerProvenanceVerifier | None = None,
    epoch_certificate_issuance_input_resolver: EpochCertificateIssuanceInputResolver | None = None,
    epoch_perturbation_adjudication_provider: EpochPerturbationAdjudicationProvider | None = None,
    epoch_owner_disposition_evidence_reader: EpochOwnerDispositionEvidenceReader | None = None,
) -> EpochDeployment:
    """Build a deployment-local owner with an optional privileged native verifier.

    The verifier is an implementation of the existing native contract supplied
    by trusted deployment assembly; it is never decoded from candidate evidence
    or JSON configuration. Its operation is captured for this deployment only.
    """
    from polisyos.runtime.quality.chronology_proof import _ChronologyPersistenceRegistry
    from polisyos.runtime.quality.epoch_evidence_exchange import EpochEvidenceExchange

    config = (
        EpochDeploymentConfig()
        if config is None
        else EpochDeploymentConfig.model_validate(
            config.model_dump(mode="python"),
        )
    )
    keys = tuple(
        (row.identity, row.public_key_path.read_bytes(), row.roles)
        for row in config.trusted_issuers
    )
    owner = object.__new__(EpochDeployment)
    native_operation = getattr(native_policy_verifier, "verify_owner_relation", None)
    if native_policy_verifier is not None and not callable(native_operation):
        raise TypeError("native policy verifier does not implement its owner contract")
    component_operations = []
    for component, method in (
        (epoch_certificate_issuance_input_resolver, "resolve_verified_inputs"),
        (epoch_certificate_issuance_input_resolver, "resolve_admitted_execution_closure"),
        (epoch_perturbation_adjudication_provider, "resolve_complete_owner_adjudications"),
        (epoch_owner_disposition_evidence_reader, "resolve_admitted_owner_disposition"),
    ):
        if component is not None:
            operation = getattr(component, method, None)
            if not callable(operation):
                raise TypeError("epoch owner component does not implement its contract")
            component_operations.append((component, method, operation))
    registry = _ChronologyPersistenceRegistry()
    state = _EpochDeploymentState(
        config=config,
        keys=keys,
        store=artifacts.FileSystemCAS(config.evidence_cas_root)
        if config.evidence_cas_root is not None
        else None,
        registry=registry,
        native_policy_verifier=native_policy_verifier,
        native_policy_operation=native_operation,
        issuance_input_resolver=epoch_certificate_issuance_input_resolver,
        adjudication_provider=epoch_perturbation_adjudication_provider,
        disposition_reader=epoch_owner_disposition_evidence_reader,
        component_operations=tuple(component_operations),
    )
    _OWNERS[owner] = state
    if state.store is not None:
        registry._bind_deployment(owner, EpochEvidenceExchange(owner))
    return owner


def current_epoch_deployment() -> EpochDeployment | None:
    """Return the owner selected only while assembling this provider."""
    owner = _COMPOSITION.get()
    if owner is not None:
        owner._state()
    return owner

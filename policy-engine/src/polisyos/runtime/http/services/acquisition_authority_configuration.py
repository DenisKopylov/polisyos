"""Purpose-scoped deployment inputs for acquisition authority custody.

Configuration selects externally persisted evidence and exact institutional keys;
it never emits a mandate or establishes an appointment. Empty slots are usable
composition inputs whose authority decision remains a refusal.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path  # noqa: TC003 - Pydantic resolves deployment DTO annotations
from typing import Literal, Self

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts
from polisyos.runtime.http.services.acquisition_admission_bundle import (
    AcquisitionAdmissionSigningSlot,
)

_SHA = r"^sha256:[0-9a-f]{64}$"


class AcquisitionMandateSlot(BaseModel):
    """Select one exact request resource and independently signed mandate head."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    authority_purpose: Literal["agent_action_delegation"] = "agent_action_delegation"
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    route_id: str = Field(pattern=_SHA)
    resource_digest: str = Field(pattern=_SHA)
    delegation_contract_ref: str = Field(pattern=_SHA)
    mandate_owner_ref: str = Field(min_length=1)
    delegation_public_key_path: Path
    current_mandate_evidence_ref: str = Field(pattern=_SHA)
    current_mandate_signer_identity: str = Field(min_length=1)
    current_mandate_public_key_path: Path
    verifier_provenance_ref: str = Field(min_length=1)
    human_decision_record_ref: str | None = Field(default=None, pattern=_SHA)
    decision_information_refs: tuple[artifacts.ArtifactRef, ...] = ()
    decision_disconfirming_refs: tuple[artifacts.ArtifactRef, ...] = ()

    @model_validator(mode="after")
    def _independent_currentness_identity(self) -> Self:
        if self.mandate_owner_ref == self.current_mandate_signer_identity:
            raise ValueError("mandate owner cannot attest its own current appointment")
        information = {str(ref.artifact_id) for ref in self.decision_information_refs}
        if not {str(ref.artifact_id) for ref in self.decision_disconfirming_refs} <= information:
            raise ValueError("disconfirming evidence must be included in the information shown")
        return self


class AcquisitionAdmissionSignerConfig(BaseModel):
    """Deployment appointment for the existing deterministic admission signer."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    purpose: Literal["acquisition_admission"] = "acquisition_admission"
    signer_identity: str = Field(min_length=1)
    private_key_path: Path
    public_key_path: Path
    verifier_provenance_ref: str = Field(min_length=1)


class AcquisitionDecisionSignerConfig(BaseModel):
    """Separate exact signer appointment for a DS9-consumable decision source."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    purpose: Literal["acquisition_authority_decision"] = "acquisition_authority_decision"
    signer_identity: str = Field(min_length=1)
    private_key_path: Path
    public_key_path: Path
    verifier_provenance_ref: str = Field(min_length=1)


class AcquisitionAuthorityConfig(BaseModel):
    """Exact institutional selectors and distinct runtime signing appointments."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mandates: tuple[AcquisitionMandateSlot, ...] = ()
    admission_signer: AcquisitionAdmissionSignerConfig | None = None
    decision_signer: AcquisitionDecisionSignerConfig | None = None
    revoked_key_ids: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def _unique_request_selectors(self) -> Self:
        selectors = [
            (row.tenant_id, row.cell_id, row.run_id, row.route_id, row.resource_digest)
            for row in self.mandates
        ]
        if len(selectors) != len(set(selectors)):
            raise ValueError("ambiguous acquisition mandate selection")
        return self


@dataclass(frozen=True, slots=True)
class DeploymentAcquisitionAuthority:
    """Deployment-owned verification and signing slots, including typed absence."""

    config: AcquisitionAuthorityConfig
    verifier: artifacts.Ed25519Verifier
    signing_slot: AcquisitionAdmissionSigningSlot
    decision_signer: artifacts.Ed25519Signer | None = None
    decision_signer_identity: str | None = None

    @property
    def authority_available(self) -> bool:
        """Report configured slots, never admission/currentness of selected evidence."""
        return bool(
            self.config.mandates
            and self.signing_slot.signer is not None
            and self.decision_signer is not None
        )

    def attestation_state(self) -> dict[str, object]:
        """Bind actual trust and signer state, not just the configuration declaration."""
        verifier = self.verifier
        if type(verifier) is not artifacts.Ed25519Verifier or not verifier._strict_identity:
            raise TypeError("acquisition verifier identity policy changed")
        keys = {
            key: sha256(value.public_bytes(Encoding.Raw, PublicFormat.Raw)).hexdigest()
            for key, value in verifier._trusted_keys.items()
        }
        for key, digest in keys.items():
            if key != f"sha256:{digest}":
                raise TypeError("acquisition trusted key content changed")

        def signer_state(signer: artifacts.Ed25519Signer | None) -> object:
            if signer is None:
                return None
            key = signer._private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
            if signer.key_id != f"sha256:{sha256(key).hexdigest()}":
                raise TypeError("acquisition signing key identity changed")
            return {
                "identity": id(signer),
                "key_id": signer.key_id,
                "callables": sorted(
                    (name, id(value)) for name, value in vars(signer).items() if callable(value)
                ),
            }

        return {
            "config": self.config.model_dump(mode="json"),
            "verifier_identity": id(verifier),
            "keys": keys,
            "identity_bindings": sorted(verifier._identity_bindings.items()),
            "revoked": sorted(verifier._revoked_key_ids),
            "verifier_callables": sorted(
                (name, id(value)) for name, value in vars(verifier).items() if callable(value)
            ),
            "admission_signer": signer_state(self.signing_slot.signer),
            "admission_identity": self.signing_slot.signer_identity,
            "admission_purpose": self.signing_slot.purpose,
            "admission_verifier_identity": id(self.signing_slot.verifier),
            "decision_signer": signer_state(self.decision_signer),
            "decision_identity": self.decision_signer_identity,
        }


def build_acquisition_authority(
    config: AcquisitionAuthorityConfig | None,
) -> DeploymentAcquisitionAuthority:
    """Load only declared purpose-scoped keys; retain every absent slot as empty."""
    config = config if config is not None else AcquisitionAuthorityConfig()
    verifier = artifacts.Ed25519Verifier(strict_identity=True)
    identities: dict[str, str] = {}

    def trust(path: Path, identity: str) -> str:
        key = verifier.load_trusted_key_file(path.expanduser(), identity=identity)
        if key in identities and identities[key] != identity:
            raise ValueError("one acquisition key cannot bind multiple institutional identities")
        identities[key] = identity
        return key

    for row in config.mandates:
        owner_key = trust(row.delegation_public_key_path, row.mandate_owner_ref)
        current_key = trust(
            row.current_mandate_public_key_path, row.current_mandate_signer_identity
        )
        if owner_key == current_key:
            raise ValueError("mandate currentness requires an independent key")

    def signing(
        configured: AcquisitionAdmissionSignerConfig | AcquisitionDecisionSignerConfig,
    ) -> artifacts.Ed25519Signer:
        signer = artifacts.Ed25519Signer.from_path(configured.private_key_path.expanduser())
        key = trust(configured.public_key_path, configured.signer_identity)
        if key != signer.key_id or key in config.revoked_key_ids:
            raise ValueError("acquisition signer key mismatch or revoked")
        return signer

    slot = AcquisitionAdmissionSigningSlot.empty()
    if config.admission_signer is not None:
        slot = AcquisitionAdmissionSigningSlot.configured(
            signer=signing(config.admission_signer),
            verifier=verifier,
            signer_identity=config.admission_signer.signer_identity,
        )
    decision_signer = (
        signing(config.decision_signer) if config.decision_signer is not None else None
    )
    for key_id in config.revoked_key_ids:
        verifier.add_revoked_key_id(key_id)
    return DeploymentAcquisitionAuthority(
        config=config,
        verifier=verifier,
        signing_slot=slot,
        decision_signer=decision_signer,
        decision_signer_identity=(
            config.decision_signer.signer_identity if config.decision_signer is not None else None
        ),
    )

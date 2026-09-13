"""Load separately scoped deployment trust for reports and governed publication."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts
from polisyos.core.artifacts.backends.config import ArtifactStoreConfig, build_artifact_store
from polisyos.runtime.http.services.public_decision_verification import (
    PublicDecisionVerificationService,
    PublicDecisionVerificationTrustedKey,
)

if TYPE_CHECKING:
    from polisyos.scientist import ClaimLedgerOwnerPort
    from polisyos.scientist.governance.continuous import (
        GovernedPublicRecordOwner,
    )


class _KeyConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    public_key_path: str = Field(min_length=1)
    issuer_id: str = Field(min_length=1)
    purposes: list[str] = Field(min_length=1)
    revoked: bool = False


class _Configuration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    issuer_id: str = Field(min_length=1)
    private_key_path: str | None = None
    trusted_keys: list[_KeyConfiguration]


class _PublicationConfiguration(BaseModel):
    """Separate deployment appointment; report keys cannot implicitly fill this slot."""

    model_config = ConfigDict(extra="forbid", strict=True)

    issuer_id: str = Field(min_length=1)
    private_key_path: str | None = None
    publisher_trusted_keys: list[_KeyConfiguration]
    mandate_trusted_keys: list[_KeyConfiguration]
    mandate_ref: artifacts.ArtifactRef | None = None


def _build_governed_public_record_owner(
    *,
    cas_root: Path,
    store: artifacts.ArtifactStore,
    claim_owner: ClaimLedgerOwnerPort,
) -> GovernedPublicRecordOwner:
    """Load publication-only trust and evidence without manufacturing an appointment."""
    from polisyos.scientist.governance.continuous import (
        GovernedPublicRecordOwner,
        PublicationSigningSlot,
        PublicationTrustedKey,
        publication_trust_epoch,
    )

    slot = PublicationSigningSlot.empty()
    configured_path = os.environ.get("POLISYOS_PUBLIC_PUBLICATION_CONFIG")
    if configured_path is not None:
        path = Path(configured_path).resolve(strict=True)
        config = _PublicationConfiguration.model_validate_json(path.read_bytes())
        signer = None
        if config.private_key_path is not None:
            private_path = path.parent / config.private_key_path
            permitted, _ = artifacts.ensure_private_key_permissions(private_path)
            if not permitted:
                raise ValueError("public publication private key permissions invalid")
            signer = artifacts.Ed25519Signer.from_path(private_path)

        def read_keys(rows: list[_KeyConfiguration]) -> tuple[PublicationTrustedKey, ...]:
            return tuple(
                PublicationTrustedKey(
                    public_key_pem=(path.parent / key.public_key_path).read_bytes(),
                    issuer_id=key.issuer_id,
                    purposes=frozenset(key.purposes),
                    revoked=key.revoked,
                )
                for key in rows
            )

        publisher_keys = read_keys(config.publisher_trusted_keys)
        mandate_keys = read_keys(config.mandate_trusted_keys)
        # Trust excludes the mandate subject, which may itself bind this epoch.
        # Including that reference here would create a content-address cycle.
        epoch = publication_trust_epoch(
            issuer_id=config.issuer_id,
            publisher_trusted_keys=publisher_keys,
            mandate_trusted_keys=mandate_keys,
        )
        slot = PublicationSigningSlot(
            signer=signer,
            issuer_id=config.issuer_id,
            publisher_trusted_keys=publisher_keys,
            mandate_trusted_keys=mandate_keys,
            mandate_ref=config.mandate_ref,
            verifier_epoch=epoch,
        )
    return GovernedPublicRecordOwner(
        store=store,
        claim_owner=claim_owner,
        index_root=cas_root / "runtime" / "governed-public-record",
        slot=slot,
    )


def build_public_decision_verification_service(
    *,
    cas_root: Path,
    store: artifacts.ArtifactStore | None = None,
    claim_owner: ClaimLedgerOwnerPort | None = None,
) -> PublicDecisionVerificationService:
    """Load server-owned key policy; absent configuration leaves issuance unavailable.

    ``POLISYOS_PUBLIC_VERIFICATION_CONFIG`` names a JSON file with an issuer ID,
    optional private key path, and explicit public-key/issuer/purpose bindings.
    Relative key paths resolve against that file. Malformed configured trust fails
    startup; keys are never generated or accepted from a request.
    """
    root = cas_root / "runtime" / "public-verification"
    configured_path = os.environ.get("POLISYOS_PUBLIC_VERIFICATION_CONFIG")
    signer = None
    trusted_keys: tuple[PublicDecisionVerificationTrustedKey, ...] = ()
    issuer_id = "unconfigured-verification-report-issuer"
    if configured_path is not None:
        path = Path(configured_path).resolve(strict=True)
        config = _Configuration.model_validate_json(path.read_bytes())
        issuer_id = config.issuer_id
        if config.private_key_path is not None:
            private_path = path.parent / config.private_key_path
            permitted, _ = artifacts.ensure_private_key_permissions(private_path)
            if not permitted:
                raise ValueError("public verification private key permissions invalid")
            signer = artifacts.Ed25519Signer.from_path(private_path)
        trusted_keys = tuple(
            PublicDecisionVerificationTrustedKey(
                public_key_pem=(path.parent / key.public_key_path).read_bytes(),
                issuer_id=key.issuer_id,
                purposes=frozenset(key.purposes),
                revoked=key.revoked,
            )
            for key in config.trusted_keys
        )
    return PublicDecisionVerificationService(
        store=build_artifact_store(
            ArtifactStoreConfig(
                backend="filesystem",
                root=str(root / "cas"),
            ),
        ),
        index_root=root / "issued",
        issuer_id=issuer_id,
        signer=signer,
        trusted_keys=trusted_keys,
        governed_owner=(
            _build_governed_public_record_owner(
                cas_root=cas_root, store=store, claim_owner=claim_owner
            )
            if store is not None and claim_owner is not None
            else None
        ),
    )

from __future__ import annotations

# ruff: noqa: S101
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from polisyos.core import contracts as core_contracts
from polisyos.runtime.quality.epoch_deployment import (
    EpochAppointmentEvidenceConfig,
    EpochDeploymentConfig,
    EpochTrustedIssuerConfig,
    build_epoch_deployment,
)
from polisyos.runtime.quality.epoch_evidence_exchange import EpochEvidenceExchange
from tests._helpers.chronology_qualification import AppointedAnchorFixture

contracts = core_contracts.chronology


def _configured_owner(tmp_path: Path, fixture: AppointedAnchorFixture):
    key = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"gy-n12-c3-appointed-fixture-key-v1").digest()
    )
    public_key_path = tmp_path / "appointment-issuer.pem"
    public_key_path.write_bytes(
        key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
    )
    config = EpochDeploymentConfig(
        evidence_cas_root=fixture.store.root,
        trusted_issuers=(
            EpochTrustedIssuerConfig(
                identity="fixture-appointment-issuer",
                public_key_path=public_key_path,
                roles=("acceptance_appointment", "holder_appointment"),
            ),
        ),
        acceptance_appointments=(
            EpochAppointmentEvidenceConfig(
                appointment_evidence_ref=(
                    fixture.acceptance_appointment.signed_appointment_evidence.persisted.evidence_record_ref
                ),
                verification_evidence_ref=(
                    fixture.acceptance_appointment.signed_verification_evidence.persisted.evidence_record_ref
                ),
            ),
        ),
        holder_appointments=(
            EpochAppointmentEvidenceConfig(
                appointment_evidence_ref=(
                    fixture.holder_appointment.signed_appointment_evidence.persisted.evidence_record_ref
                ),
                verification_evidence_ref=(
                    fixture.holder_appointment.signed_verification_evidence.persisted.evidence_record_ref
                ),
            ),
        ),
    )
    return config


def test_old_appointment_cannot_authorize_against_a_revoked_current_owner(tmp_path) -> None:
    fixture = AppointedAnchorFixture(tmp_path / "fixture")
    config = _configured_owner(tmp_path, fixture)
    first_exchange = EpochEvidenceExchange(build_epoch_deployment(config))
    resolved = first_exchange.resolve_epoch_appointments(
        family="epoch",
        proof_domain="epoch",
        authority_purpose="publication",
    )
    assert resolved.acceptance.status == "established"
    old_appointment = resolved.acceptance.appointment
    current_authority = first_exchange.resolve_acceptance_authority(appointment=old_appointment)
    assert callable(getattr(current_authority, "recompute_and_accept", None))

    revoked_config = config.model_copy(update={"revoked_key_ids": (fixture.signer.key_id,)})
    current_exchange = EpochEvidenceExchange(build_epoch_deployment(revoked_config))
    stale_authority = current_exchange.resolve_acceptance_authority(appointment=old_appointment)

    assert isinstance(stale_authority, contracts.AcceptanceUnavailableNonReceipt)
    assert stale_authority.status == "not_established"
    assert stale_authority.code == "anchor_acceptance_trust_not_established"

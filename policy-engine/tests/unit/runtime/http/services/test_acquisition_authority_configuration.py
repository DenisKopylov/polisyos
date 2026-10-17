"""Behavioral mirror for acquisition signer identity and revocation controls.

All keys and selectors here are synthetic deployment inputs. A configured slot
is not proof of an external appointment, evidence currentness, or custody.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.core.artifacts.signing import KeyPair
from polisyos.runtime.http.services.acquisition_authority_configuration import (
    AcquisitionAdmissionSignerConfig,
    AcquisitionAuthorityConfig,
    AcquisitionDecisionSignerConfig,
    AcquisitionMandateSlot,
    build_acquisition_authority,
)

_OWNER = "principal://mandate-owner/synthetic-test"
_CURRENTNESS = "service://mandate-registry/synthetic-test"
_ADMISSION = "service://runtime/acquisition-admission/synthetic-test"
_DECISION = "service://runtime/acquisition-decision/synthetic-test"


def _write_pair(tmp_path: Path, name: str) -> tuple[KeyPair, Path, Path]:
    pair = KeyPair.generate()
    private_path = tmp_path / f"{name}.private.pem"
    public_path = tmp_path / f"{name}.public.pem"
    private_path.write_bytes(pair.private_pem())
    public_path.write_bytes(pair.public_pem())
    return pair, private_path, public_path


def _config(
    tmp_path: Path,
    *,
    owner_pair: tuple[KeyPair, Path, Path] | None = None,
    current_pair: tuple[KeyPair, Path, Path] | None = None,
    admission_pair: tuple[KeyPair, Path, Path] | None = None,
    decision_pair: tuple[KeyPair, Path, Path] | None = None,
    revoked_key_ids: frozenset[str] = frozenset(),
) -> AcquisitionAuthorityConfig:
    owner = owner_pair or _write_pair(tmp_path, "owner")
    current = current_pair or _write_pair(tmp_path, "current")
    admission = admission_pair or _write_pair(tmp_path, "admission")
    decision = decision_pair or _write_pair(tmp_path, "decision")
    return AcquisitionAuthorityConfig(
        mandates=(
            AcquisitionMandateSlot(
                tenant_id="tenant-synthetic-test",
                cell_id="cell-synthetic-test",
                run_id="run-synthetic-test",
                route_id="sha256:" + "1" * 64,
                resource_digest="sha256:" + "2" * 64,
                delegation_contract_ref="sha256:" + "3" * 64,
                mandate_owner_ref=_OWNER,
                delegation_public_key_path=owner[2],
                current_mandate_evidence_ref="sha256:" + "4" * 64,
                current_mandate_signer_identity=_CURRENTNESS,
                current_mandate_public_key_path=current[2],
                verifier_provenance_ref="synthetic-test-only",
            ),
        ),
        admission_signer=AcquisitionAdmissionSignerConfig(
            signer_identity=_ADMISSION,
            private_key_path=admission[1],
            public_key_path=admission[2],
            verifier_provenance_ref="synthetic-test-only",
        ),
        decision_signer=AcquisitionDecisionSignerConfig(
            signer_identity=_DECISION,
            private_key_path=decision[1],
            public_key_path=decision[2],
            verifier_provenance_ref="synthetic-test-only",
        ),
        revoked_key_ids=revoked_key_ids,
    )


def test_builder_binds_each_configured_role_to_its_own_generated_key(
    tmp_path: Path,
) -> None:
    owner = _write_pair(tmp_path, "owner")
    current = _write_pair(tmp_path, "current")
    admission = _write_pair(tmp_path, "admission")
    decision = _write_pair(tmp_path, "decision")

    authority = build_acquisition_authority(
        _config(
            tmp_path,
            owner_pair=owner,
            current_pair=current,
            admission_pair=admission,
            decision_pair=decision,
        )
    )

    state = authority.attestation_state()
    identity_bindings = dict(state["identity_bindings"])
    assert identity_bindings == {
        owner[0].key_id: _OWNER,
        current[0].key_id: _CURRENTNESS,
        admission[0].key_id: _ADMISSION,
        decision[0].key_id: _DECISION,
    }
    assert state["admission_identity"] == _ADMISSION
    assert state["decision_identity"] == _DECISION
    assert authority.signing_slot.signer is not None
    assert authority.signing_slot.signer.key_id == admission[0].key_id
    assert authority.decision_signer is not None
    assert authority.decision_signer.key_id == decision[0].key_id
    # This is configured-slot presence only; it does not validate the selected
    # evidence or establish external appointment/currentness/custody.
    assert authority.authority_available is True


def test_builder_rejects_owner_and_currentness_roles_reusing_one_key(
    tmp_path: Path,
) -> None:
    shared = _write_pair(tmp_path, "shared-owner-current")

    with pytest.raises(ValueError, match="one acquisition key cannot bind multiple"):
        build_acquisition_authority(_config(tmp_path, owner_pair=shared, current_pair=shared))


def test_builder_rejects_revoked_admission_signer_key(tmp_path: Path) -> None:
    admission = _write_pair(tmp_path, "revoked-admission")
    config = _config(
        tmp_path,
        admission_pair=admission,
        revoked_key_ids=frozenset({admission[0].key_id}),
    )

    with pytest.raises(ValueError, match="mismatch or revoked"):
        build_acquisition_authority(config)

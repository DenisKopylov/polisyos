"""Persisted epoch receipt evolution preserves the original statement bytes."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import FileSystemCAS, PutOptions
from polisyos.core.contracts import chronology as chronology_contract
from polisyos.core.contracts import epoch as epoch_contract
from polisyos.runtime.quality import semantic_epoch


@pytest.mark.parametrize("positive", [False, True])
def test_legacy_production_receipt_cas_readback_preserves_exact_statement(
    tmp_path: Path, positive: bool
) -> None:
    """Old statement grammar remains readable without acquiring native custody."""
    store = FileSystemCAS(tmp_path / "cas")
    evidence = store.put_bytes(
        b"legacy-proof",
        PutOptions(kind="epoch.legacy-test-evidence", media_type="application/octet-stream"),
    )
    digest = f"sha256:{hashlib.sha256(b'legacy-query').hexdigest()}"
    # These are the complete pre-projection receipt fields. The old positive
    # shape is evidence for codec compatibility, never a native qualification.
    statement = {
        "production_mode": "ordinary",
        "status": "appended" if positive else "not_established",
        "prepared_epoch_ref": None,
        "admitted_boundary_evidence_ref": None,
        "epoch_ref": digest if positive else None,
        "semantic_manifest_ref": evidence.model_dump(mode="json") if positive else None,
        "owner_denominator_receipt_refs": [],
        "history_append_receipt_ref": evidence.model_dump(mode="json") if positive else None,
        "chronology_bundle_ref": evidence.model_dump(mode="json") if positive else None,
        "chronology_verification_ref": evidence.model_dump(mode="json") if positive else None,
        "requested_query_context_ref": digest,
        "failure_codes": [] if positive else ["policy_admission_missing"],
    }
    raw = chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(statement))
    ref = store.put_bytes(
        raw,
        PutOptions(
            kind="epoch.production_receipt",
            media_type="application/vnd.polisyos.epoch-production-receipt+json",
        ),
    )
    content_hash = epoch_contract.epoch_semantic_content_hash(
        domain="polisyos.epoch.production-receipt.v1", value=statement
    )
    decoded = epoch_contract.load_verified_epoch_statement(
        store=store,
        ref=ref,
        expected_kind=ref.kind,
        expected_media_type=ref.media_type,
    )
    assert decoded == statement
    receipt = semantic_epoch.PersistedSemanticEpochProductionReceipt.model_validate(
        {**decoded, "receipt_ref": ref, "receipt_content_hash": content_hash}
    )
    assert receipt.chronology_projection_ref is None
    serialized = receipt.model_dump(mode="json")
    assert "chronology_projection_ref" not in serialized
    assert (
        semantic_epoch.PersistedSemanticEpochProductionReceipt.model_validate_json(
            receipt.model_dump_json()
        )
        == receipt
    )
    exact = {
        key: value
        for key, value in serialized.items()
        if key not in {"receipt_ref", "receipt_content_hash"}
    }
    assert chronology_contract._frame_record(epoch_contract.canonical_epoch_bytes(exact)) == raw
    assert store.get_bytes(ref.artifact_id) == raw
    assert str(ref.artifact_id) == f"sha256:{hashlib.sha256(raw).hexdigest()}"
    assert receipt.receipt_content_hash == content_hash

    # Presence with null changes exact bytes just as presence with a ref does.
    # Neither may borrow the old persisted identity or content hash.
    for projection in (None, evidence.model_dump(mode="json")):
        with pytest.raises(ValidationError):
            semantic_epoch.PersistedSemanticEpochProductionReceipt.model_validate(
                {**serialized, "chronology_projection_ref": projection}
            )
